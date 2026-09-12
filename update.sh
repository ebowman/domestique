#!/usr/bin/env bash
# update.sh — fetch the latest domestique.sh from GitHub and re-run it
# against an explicit global or private local scope. This is intentionally
# thin: ownership, pristine-only refresh and publication live in domestique.sh.
set -euo pipefail

DEFAULT_SOURCE="https://raw.githubusercontent.com/ebowman/domestique/main/domestique.sh"

usage() {
  cat <<EOF
Usage: update.sh --global [options]
       update.sh --local TARGET [options]
       update.sh [TARGET] [options]  (private local; default .)

IMPLEMENTED PREVIEW: definitions/profile lifecycle, NOT end-to-end readiness.
Default source is main, NOT this preview; draft #11 lacks these changes too.
Use this checkout until published:
  bash ./update.sh --source ./domestique.sh --global
  bash ./update.sh --source ./domestique.sh --local /absolute/project
Fetches $DEFAULT_SOURCE unless overridden.
Always previews first; ANY failed preview prevents apply.
  --source PATH/URL  Override source (also DOMESTIQUE_UPDATE_SOURCE).
  --platform P  claude, codex, copilot, both, claude-copilot, codex-copilot, all
                both = Claude+Codex; all = all three; other pairs as named.
                Additive union, reused when omitted; fresh default Claude.
  --dry-run     Preview only.
  --force       Does not override edited/unknown private native assets.
  --guest       Deprecated warning-only no-op; --no-guest is invalid.
  --with-beads  Explicit --local TARGET only; qualified private embedded DB init.
  --state-only  Requires --local TARGET --with-beads; no --platform.
                No new profiles; preserves existing edited profiles.
  --help, -h    Help.
Local requires an existing Git top-level and compatible global core; no
implicit global writes. Beads requires the observed Darwin arm64 Beads 1.1.2
CGO embedded artifact, existing Python 3.9+ and macOS sandbox-exec. Other versions,
platforms/backends refuse before project writes. Dry-run has no DB calls or
destination writes. Native operations use a private non-Git context and actual
OS sandbox; --sandbox alone only disables auto-push. Existing host .beads is
never adopted. Every workflow operation requires the installed controlled
resolve-core beads dispatcher with literal core/project/release bindings.
No unsafe init/rollback, setup, arbitrary flags or force bypass.
Definitions/routing can load; full native role/tool/MCP execution is unverified.
No implicit client/plugin/auth/environment/MCP setup. This wrapper only updates;
use domestique.sh --uninstall --global for owned-only global removal, or
domestique.sh --uninstall --local TARGET for profile-only local removal.
Removal retains edited selected providers whole, nonzero even force. No live
backups/merges. Local last-profile removal retains providers=none/private exclusion.
Global final removal leaves unproven empty containers; see README safe manual
empty-core reconciliation before reinstall. Beads purge/integrated cleanup is open.
No model, MCP, or tool options are accepted; customize native metadata locally.
Edited metadata requires native reload/trust/core-protocol confirmation; automatic
refresh refuses untouched, even force. Global core updates do not rewrite locals.
EOF
}

TARGET_DIR=""
TARGET_EXPLICIT=0
SOURCE="${DOMESTIQUE_UPDATE_SOURCE:-$DEFAULT_SOURCE}"
UPDATER_DRY_RUN=0
FORCE=0
GUEST=0
NO_GUEST=0
PLATFORM=""
PLATFORM_EXPLICIT=0
GLOBAL=0
LOCAL=0
WITH_BEADS=0
STATE_ONLY=0

while [ $# -gt 0 ]; do
  case "$1" in
    --global) GLOBAL=1 ;;
    --with-beads) WITH_BEADS=1 ;;
    --state-only) STATE_ONLY=1 ;;
    --local)
      [ "$#" -ge 2 ] && [ -n "$2" ] && [ "$TARGET_EXPLICIT" = 0 ] ||
        { echo "--local requires one target" >&2; exit 2; }
      case "$2" in -*) echo "Invalid --local target" >&2; exit 2;; esac
      LOCAL=1; TARGET_EXPLICIT=1; TARGET_DIR="$2"; shift;;
    --source)
      [ $# -ge 2 ] && [ -n "$2" ] || { echo "Missing argument for --source" >&2; exit 2; }
      case "$2" in -*) echo "Invalid --source" >&2; exit 2;; esac
      SOURCE="$2"; shift ;;
    --source=*) SOURCE="${1#--source=}" ;;
    --dry-run) UPDATER_DRY_RUN=1 ;;
    --force)   FORCE=1 ;;
    --platform)
      [ $# -ge 2 ] || { echo "Missing argument for --platform" >&2; exit 2; }
      PLATFORM="$2"; PLATFORM_EXPLICIT=1; shift ;;
    --platform=*) PLATFORM="${1#--platform=}"; PLATFORM_EXPLICIT=1 ;;
    --guest)     GUEST=1 ;;
    --no-guest)  NO_GUEST=1 ;;
    -h|--help) usage; exit 0 ;;
    --) shift; break ;;
    -*) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    *)
      [ -n "$1" ] || { echo "Empty target" >&2; exit 2; }
      TARGET_EXPLICIT=1
      if [ -z "$TARGET_DIR" ]; then TARGET_DIR="$1"
      else echo "Unexpected argument: $1" >&2; exit 2; fi
      ;;
  esac
  shift
done
[ -n "$SOURCE" ] || { echo "Empty --source" >&2; exit 2; }
[ "$#" = 0 ] && [ "$NO_GUEST" = 0 ] ||
  { echo "Invalid target/options; --no-guest is unsupported" >&2; exit 2; }
[ "$PLATFORM_EXPLICIT" = 0 ] || [ -n "$PLATFORM" ] ||
  { echo "Empty --platform" >&2; exit 2; }
[ "$STATE_ONLY" = 0 ] || {
  [ "$LOCAL$WITH_BEADS$GLOBAL$PLATFORM_EXPLICIT" = 1100 ] ||
    { echo "--state-only requires explicit --local TARGET --with-beads and no --platform/--global" >&2; exit 2; }
}
[ "$WITH_BEADS" = 0 ] || {
  [ "$LOCAL$GLOBAL" = 10 ] ||
    { echo "--with-beads requires explicit --local TARGET, not bare/positional or --global" >&2; exit 2; }
}
TARGET_ARGS=()
if [ "$GLOBAL" = 1 ]; then
  [ "$LOCAL" = 0 ] && [ "$TARGET_EXPLICIT" = 0 ] && [ "$#" = 0 ] && [ "$NO_GUEST" = 0 ] ||
    { echo "Invalid --global scope/target/options" >&2; exit 2; }
  [ "$PLATFORM_EXPLICIT" = 0 ] || [ -n "$PLATFORM" ] ||
    { echo "Empty --platform" >&2; exit 2; }
else
  TARGET_DIR="${TARGET_DIR:-.}"
  TARGET_ARGS+=(--local "$TARGET_DIR")
fi

case "$PLATFORM" in
  ""|claude|codex|copilot|both|all|claude-copilot|codex-copilot) : ;;
  *) echo "Invalid --platform value: $PLATFORM (expected claude, codex, copilot, both, or all)" >&2; exit 2 ;;
esac

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
FETCHED="$WORK_DIR/domestique.sh"

echo "domestique update: source = $SOURCE"

case "$SOURCE" in
  http://*|https://*)
    fetch_ok=1
    if command -v curl >/dev/null 2>&1; then
      curl -fsSL "$SOURCE" -o "$FETCHED" || fetch_ok=0
    elif command -v wget >/dev/null 2>&1; then
      wget -q -O "$FETCHED" "$SOURCE" || fetch_ok=0
    else
      echo "Neither curl nor wget is available to fetch $SOURCE" >&2
      exit 4
    fi
    if [ "$fetch_ok" -ne 1 ] || [ ! -s "$FETCHED" ]; then
      echo "Failed to download domestique.sh from: $SOURCE" >&2
      exit 4
    fi
    ;;
  *)
    if [ ! -f "$SOURCE" ]; then
      echo "Source file not found: $SOURCE" >&2
      exit 4
    fi
    cp "$SOURCE" "$FETCHED"
    ;;
esac

if ! bash -n "$FETCHED"; then
  echo "Downloaded/copied domestique.sh from $SOURCE failed syntax check (bash -n) — aborting." >&2
  exit 4
fi

# Pass scope and provider intent through; omitted selection reuses that
# scope's persisted union. --guest is only a deprecated warning-producing alias.
FORCE_ARGS=()
[ "$GLOBAL" -eq 1 ] && FORCE_ARGS+=(--global)
[ "$FORCE" -eq 1 ] && FORCE_ARGS+=(--force)
[ "$GUEST" -eq 1 ] && FORCE_ARGS+=(--guest)
[ "$NO_GUEST" -eq 1 ] && FORCE_ARGS+=(--no-guest)
[ -n "$PLATFORM" ] && FORCE_ARGS+=(--platform "$PLATFORM")
[ "$WITH_BEADS" = 1 ] && FORCE_ARGS+=(--with-beads)
[ "$STATE_ONLY" = 1 ] && FORCE_ARGS+=(--state-only)

echo
echo "--- Preview (dry run) ---"
rc=0
bash "$FETCHED" --dry-run "${FORCE_ARGS[@]+"${FORCE_ARGS[@]}"}" "${TARGET_ARGS[@]+"${TARGET_ARGS[@]}"}" || rc=$?

if [ "$rc" -ne 0 ]; then
  echo "domestique update: preview failed; not applying." >&2
  exit "$rc"
fi

if [ "$UPDATER_DRY_RUN" -eq 1 ]; then
  echo
  echo "domestique update: --dry-run requested; not applying."
  exit "$rc"
fi

echo
echo "--- Applying ---"
rc=0
bash "$FETCHED" "${FORCE_ARGS[@]+"${FORCE_ARGS[@]}"}" "${TARGET_ARGS[@]+"${TARGET_ARGS[@]}"}" || rc=$?

echo
case "$rc" in
  0) echo "domestique update: applied cleanly (or already up to date)." ;;
  3) echo "domestique update: applied with conflicts — see 'Conflicted' above and the .new/.bak files. Human attention needed." >&2 ;;
  *) echo "domestique update: underlying install failed (exit $rc)." >&2 ;;
esac

exit "$rc"
