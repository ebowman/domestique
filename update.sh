#!/usr/bin/env bash
# update.sh — fetch the latest domestique.sh from GitHub and re-run it
# against a target directory, reusing the existing 3-way-merge install path
# (see docs/install-upgrade-design.md §5). This is intentionally a thin
# wrapper: all merge/backup/conflict logic lives in domestique.sh itself.
set -euo pipefail

DEFAULT_SOURCE="https://raw.githubusercontent.com/ebowman/domestique/main/domestique.sh"

usage() {
  cat <<EOF
Usage: update.sh [TARGET_DIR] [options]

Fetches the latest domestique.sh (default source:
  $DEFAULT_SOURCE
) and runs it against TARGET_DIR (default: current directory), reusing the
existing 3-way-merge install/upgrade logic. Safe to run periodically:
  1. Runs a --dry-run pass first and prints what would change.
  2. Unless --dry-run was passed to this updater, applies for real.

Options:
  --source <path|url>  Override the source domestique.sh (local file path or
                        URL). Also settable via DOMESTIQUE_UPDATE_SOURCE.
  --dry-run            Only show the preview; do not apply.
  --force              Pass through to domestique.sh (discard local edits,
                        take upstream verbatim; see domestique.sh --help).
  --help, -h           Show this help.

Exit codes (propagated from the underlying domestique.sh run):
  0  everything applied cleanly (or already up to date — a clean no-op).
  1  operational refusal (e.g. missing target dir).
  2  invocation error (bad options passed to the underlying script).
  3  one or more files ended in conflict/error during merge — needs a human.
  4  could not obtain a valid domestique.sh from the given source.
EOF
}

TARGET_DIR=""
SOURCE="${DOMESTIQUE_UPDATE_SOURCE:-$DEFAULT_SOURCE}"
UPDATER_DRY_RUN=0
FORCE=0

while [ $# -gt 0 ]; do
  case "$1" in
    --source)
      [ $# -ge 2 ] || { echo "Missing argument for --source" >&2; exit 2; }
      SOURCE="$2"; shift ;;
    --source=*) SOURCE="${1#--source=}" ;;
    --dry-run) UPDATER_DRY_RUN=1 ;;
    --force)   FORCE=1 ;;
    -h|--help) usage; exit 0 ;;
    --) shift; break ;;
    -*) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    *)
      if [ -z "$TARGET_DIR" ]; then TARGET_DIR="$1"
      else echo "Unexpected argument: $1" >&2; exit 2; fi
      ;;
  esac
  shift
done
TARGET_DIR="${TARGET_DIR:-.}"

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

FORCE_ARGS=()
[ "$FORCE" -eq 1 ] && FORCE_ARGS+=(--force)

echo
echo "--- Preview (dry run) ---"
rc=0
bash "$FETCHED" --dry-run "${FORCE_ARGS[@]+"${FORCE_ARGS[@]}"}" "$TARGET_DIR" || rc=$?

if [ "$UPDATER_DRY_RUN" -eq 1 ]; then
  echo
  echo "domestique update: --dry-run requested; not applying."
  exit "$rc"
fi

echo
echo "--- Applying ---"
rc=0
bash "$FETCHED" "${FORCE_ARGS[@]+"${FORCE_ARGS[@]}"}" "$TARGET_DIR" || rc=$?

echo
case "$rc" in
  0) echo "domestique update: applied cleanly (or already up to date)." ;;
  3) echo "domestique update: applied with conflicts — see 'Conflicted' above and the .new/.bak files. Human attention needed." >&2 ;;
  *) echo "domestique update: underlying install failed (exit $rc)." >&2 ;;
esac

exit "$rc"
