#!/usr/bin/env bash
# test/guest.sh — self-contained test harness for domestique.sh's --guest
# (guest-mode install) behavior. Runs each scenario in an isolated mktemp -d
# sandbox, reports PASS/FAIL per scenario, prints a final tally, and exits
# non-zero if any scenario failed. No external test framework, no network.
#
# Run: bash test/guest.sh
#
# Conventions follow test/upgrade.sh exactly: scratch dirs via mktemp -d,
# check()/run_scenario() helpers, collect-then-report (never exit early on a
# single failed assertion), byte-identical comparisons via cmp -s/shasum.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DOM="$REPO_DIR/domestique.sh"

if [ ! -f "$DOM" ]; then
  echo "FATAL: cannot find domestique.sh at $DOM" >&2
  exit 1
fi

WORKROOT="$(mktemp -d)"
cleanup() { rm -rf "$WORKROOT"; }
trap cleanup EXIT

PASS_COUNT=0
FAIL_COUNT=0

# ---------------------------------------------------------------------------
# check "<description>" <command...>
# Runs <command...>; on failure records the description into SCEN_REASON and
# flips SCEN_OK to 0 (scenario-scoped globals, reset by run_scenario). Always
# returns the underlying command's status so callers may also branch on it.
# ---------------------------------------------------------------------------
check() {
  local desc="$1"; shift
  if "$@"; then
    return 0
  else
    SCEN_OK=0
    SCEN_REASON="${SCEN_REASON:+$SCEN_REASON; }$desc"
    return 1
  fi
}

# run_scenario <name> <function>
# Resets scenario-scoped state, runs the scenario function, prints
# PASS/FAIL, and tallies the result.
run_scenario() {
  local name="$1" func="$2"
  SCEN_OK=1
  SCEN_REASON=""
  "$func"
  if [ "$SCEN_OK" -eq 1 ]; then
    echo "PASS: $name"
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    echo "FAIL: $name ($SCEN_REASON)"
    FAIL_COUNT=$((FAIL_COUNT + 1))
  fi
}

# filehash <file> — sha256 of a single file, used for byte-identical checks.
# Fails loud on a missing file (prints a MISSING:<path> sentinel instead of
# empty) so equality comparisons against a missing file can never silently
# degrade to empty == empty.
filehash() {
  if [ ! -e "$1" ]; then
    printf 'MISSING:%s' "$1"
    return 0
  fi
  shasum -a 256 "$1" 2>/dev/null | awk '{print $1}'
}

# git_init <dir> — init a git repo with local (non-global) identity so the
# harness never depends on (or pollutes) the user's global git config.
git_init() {
  local d="$1"
  git -C "$d" init -q
  git -C "$d" config user.email "domestique-test@example.com"
  git -C "$d" config user.name "domestique test"
}

# ---------------------------------------------------------------------------
# V2G.sh — a modified copy of domestique.sh simulating an upstream change to
# emit_policy, per test/upgrade.sh's technique: copy the real script, sed-edit
# ONE line inside the COMMON part of the emit_policy heredoc (shared by both
# normal and guest mode, above the `case "$mode" in` split) so the same change
# is visible whether the destination is CLAUDE.md or CLAUDE.local.md.
# ---------------------------------------------------------------------------
V2G="$WORKROOT/v2g.sh"
cp "$DOM" "$V2G"
ANCHOR='Do not drain the queue unattended unless explicitly told to.'
ANCHOR_COUNT="$(grep -cF "$ANCHOR" "$DOM")"
if [ "$ANCHOR_COUNT" -ne 1 ]; then
  echo "FATAL: expected exactly one occurrence of anchor line in $DOM, found $ANCHOR_COUNT" >&2
  exit 1
fi
sed -i.orig \
  "s/Do not drain the queue unattended unless explicitly told to\\./Do not drain the queue unattended unless explicitly told to (v2-guest-test)./" \
  "$V2G"
rm -f "$V2G.orig"
chmod +x "$V2G"

MODE_MARKER_REL=".claude/.domestique/mode"
EXCLUDE_PATTERNS=("CLAUDE.local.md" ".claude/")
DECOMPOSE_CMD_REL=".claude/commands/decompose.md"
GOAL_CMD_REL=".claude/commands/goal.md"

# ---------------------------------------------------------------------------
# Scenario 1: fresh guest install
# ---------------------------------------------------------------------------
scenario_fresh_guest_install() {
  local t="$WORKROOT/s1"; mkdir -p "$t"
  git_init "$t"
  printf '# My project\n' > "$t/CLAUDE.md"
  printf 'echo hello\n' > "$t/main.sh"
  git -C "$t" add CLAUDE.md main.sh
  git -C "$t" commit -q -m "initial"

  local sha_before out rc sha_after
  sha_before="$(filehash "$t/CLAUDE.md")"
  out="$("$DOM" "$t" --guest 2>&1)"; rc=$?
  sha_after="$(filehash "$t/CLAUDE.md")"

  check "exit 0" test "$rc" -eq 0
  check "git status --porcelain empty" bash -c '[ -z "$(git -C "$1" status --porcelain)" ]' _ "$t"
  check "CLAUDE.md byte-identical (sha)" test "$sha_before" = "$sha_after"
  check "CLAUDE.local.md created" test -f "$t/CLAUDE.local.md"
  check "CLAUDE.local.md has BEGIN marker" grep -qF "BEGIN domestique (managed)" "$t/CLAUDE.local.md"
  check "CLAUDE.local.md has guest never-commit guidance" \
    grep -q "never commit \`.beads/\`, \`CLAUDE.local.md\`, or \`.claude/\`" "$t/CLAUDE.local.md"
  check "CLAUDE.local.md does NOT have plain-mode commit phrasing" \
    bash -c '! grep -q "then commit \`.beads/\`" "$1"' _ "$t/CLAUDE.local.md"
  check "exclude file exists" test -f "$t/.git/info/exclude"
  local pat allpats=1
  for pat in "${EXCLUDE_PATTERNS[@]}"; do
    grep -qxF "$pat" "$t/.git/info/exclude" || allpats=0
  done
  check "exclude file has exact Claude guest patterns" test "$allpats" -eq 1
  check "exclude does not broadly hide beads or suffixes" bash -c '
    ! grep -Eq "^(\\.beads/|\\*\\.bak|\\*\\.new)$" "$1"
  ' _ "$t/.git/info/exclude"
  check "exclude file has managed BEGIN marker" grep -qF "# BEGIN domestique (managed)" "$t/.git/info/exclude"
  check "mode marker == guest" bash -c '[ "$(cat "$1")" = "guest" ]' _ "$t/$MODE_MARKER_REL"
  check "CLAUDE.local.md has model:opus routing rubric" grep -qF "model:opus" "$t/CLAUDE.local.md"
  check "decompose command has model:opus routing rubric" grep -qF "model:opus" "$t/$DECOMPOSE_CMD_REL"
  check "goal command has model:opus routing rubric" grep -qF "model:opus" "$t/$GOAL_CMD_REL"
}

# ---------------------------------------------------------------------------
# Scenario 2: idempotency — second guest run is all-skip, byte-identical
# ---------------------------------------------------------------------------
scenario_guest_idempotent() {
  local t="$WORKROOT/s2"; mkdir -p "$t"
  git_init "$t"
  printf '# My project\n' > "$t/CLAUDE.md"
  git -C "$t" add CLAUDE.md
  git -C "$t" commit -q -m "initial"
  "$DOM" "$t" --guest >/dev/null 2>&1

  local sha_claude_local_before sha_exclude_before out rc
  sha_claude_local_before="$(filehash "$t/CLAUDE.local.md")"
  sha_exclude_before="$(filehash "$t/.git/info/exclude")"
  out="$("$DOM" "$t" --guest 2>&1)"; rc=$?
  local sha_claude_local_after sha_exclude_after
  sha_claude_local_after="$(filehash "$t/CLAUDE.local.md")"
  sha_exclude_after="$(filehash "$t/.git/info/exclude")"

  check "exit 0" test "$rc" -eq 0
  check "no Created/Updated/Merged/Adopted/Conflicted entries" bash -c '
    ! printf "%s" "$1" | grep -Eq "^  (Created|Updated|Merged|Adopted|Conflicted):"
  ' _ "$out"
  check "CLAUDE.local.md byte-identical across runs" test "$sha_claude_local_before" = "$sha_claude_local_after"
  check "exclude file byte-identical across runs" test "$sha_exclude_before" = "$sha_exclude_after"
}

# ---------------------------------------------------------------------------
# Scenario 3: --dry-run --guest on a fresh clone creates nothing
# ---------------------------------------------------------------------------
scenario_guest_dry_run_fresh() {
  local t="$WORKROOT/s3"; mkdir -p "$t"
  git_init "$t"
  printf '# My project\n' > "$t/CLAUDE.md"
  git -C "$t" add CLAUDE.md
  git -C "$t" commit -q -m "initial"

  # `git init` itself pre-creates an empty (comments-only) .git/info/exclude,
  # so "created" is judged by content (no managed block), not by existence.
  local exclude_before
  exclude_before="$(filehash "$t/.git/info/exclude")"

  local out rc exclude_after
  out="$("$DOM" "$t" --guest --dry-run 2>&1)"; rc=$?
  exclude_after="$(filehash "$t/.git/info/exclude")"

  check "exit 0" test "$rc" -eq 0
  check "no CLAUDE.local.md created" test ! -e "$t/CLAUDE.local.md"
  check "no .claude/ created" test ! -e "$t/.claude"
  check "exclude file unchanged (byte-identical)" test "$exclude_before" = "$exclude_after"
  check "exclude file has no managed block" bash -c '! grep -qF "# BEGIN domestique (managed)" "$1"' _ "$t/.git/info/exclude"
}

# ---------------------------------------------------------------------------
# Scenario 4: non-git target dir — warns, exits 0, installs .claude/ files,
# no exclude anywhere.
# ---------------------------------------------------------------------------
scenario_non_git_target() {
  local t="$WORKROOT/s4"; mkdir -p "$t"

  local out rc
  out="$("$DOM" "$t" --guest 2>&1)"; rc=$?

  check "exit 0" test "$rc" -eq 0
  check "warning mentions git" bash -c 'printf "%s" "$1" | grep -qi "git repository"' _ "$out"
  check ".claude/agents/implementer.md installed" test -f "$t/.claude/agents/implementer.md"
  check "CLAUDE.local.md installed" test -f "$t/CLAUDE.local.md"
  check "no exclude file anywhere under target" bash -c '! find "$1" -iname "exclude" 2>/dev/null | grep -q .' _ "$t"
}

# ---------------------------------------------------------------------------
# Scenario 5: worktree — guest install into a second worktree lands the
# managed block in the COMMON git dir's info/exclude, not a per-worktree one.
# ---------------------------------------------------------------------------
scenario_worktree_common_dir() {
  local main="$WORKROOT/s5-main" second="$WORKROOT/s5-second"
  mkdir -p "$main"
  git_init "$main"
  printf '# My project\n' > "$main/CLAUDE.md"
  git -C "$main" add CLAUDE.md
  git -C "$main" commit -q -m "initial"
  git -C "$main" worktree add -q -b s5-wt-branch "$second" >/dev/null 2>&1

  local out rc
  out="$("$DOM" "$second" --guest 2>&1)"; rc=$?

  check "exit 0" test "$rc" -eq 0
  check "common dir exclude has managed block" grep -qF "# BEGIN domestique (managed)" "$main/.git/info/exclude"
  check "worktree's own .git is a file, not a dir (sanity)" test -f "$second/.git"
  # The meaningful assertion: the managed exclude block must not appear
  # anywhere under the worktree's own PRIVATE git dir (resolved via
  # `git rev-parse --git-dir`, which for a worktree is distinct from the
  # common dir asserted above). This replaces a vacuous
  # `test ! -e "$second/.git/info/exclude"` check (which passed trivially
  # since $second/.git is a file, not a directory, so that path can never
  # exist regardless of correctness).
  local private_gitdir
  private_gitdir="$(git -C "$second" rev-parse --git-dir 2>/dev/null)"
  case "$private_gitdir" in
    /*) : ;;
    *) private_gitdir="$second/$private_gitdir" ;;
  esac
  check "worktree's private gitdir resolved" test -n "$private_gitdir" -a -d "$private_gitdir"
  check "no managed block anywhere under worktree's private gitdir" \
    bash -c '! grep -rlF "# BEGIN domestique (managed)" "$1" >/dev/null 2>&1' _ "$private_gitdir"
  check "git status --porcelain clean in worktree" bash -c '[ -z "$(git -C "$1" status --porcelain)" ]' _ "$second"
}

# ---------------------------------------------------------------------------
# Scenario 6a: sticky mode — plain re-run (no flags) on a guest install stays
# guest: note printed, CLAUDE.md NOT created, status still clean.
# ---------------------------------------------------------------------------
scenario_sticky_plain_rerun() {
  local t="$WORKROOT/s6a"; mkdir -p "$t"
  git_init "$t"
  "$DOM" "$t" --guest >/dev/null 2>&1

  local out rc
  out="$("$DOM" "$t" 2>&1)"; rc=$?

  check "exit 0" test "$rc" -eq 0
  check "sticky note printed" bash -c 'printf "%s" "$1" | grep -q "staying in guest mode"' _ "$out"
  check "CLAUDE.md NOT created" test ! -e "$t/CLAUDE.md"
  check "git status --porcelain still clean" bash -c '[ -z "$(git -C "$1" status --porcelain)" ]' _ "$t"
  check "mode marker still guest" bash -c '[ "$(cat "$1")" = "guest" ]' _ "$t/$MODE_MARKER_REL"
}

# ---------------------------------------------------------------------------
# Scenario 6b: --no-guest converts — marker gone, conversion instructions
# printed, CLAUDE.md now has the managed block (this run installs normally),
# CLAUDE.local.md still present (not auto-migrated/deleted).
# ---------------------------------------------------------------------------
scenario_no_guest_conversion() {
  local t="$WORKROOT/s6b"; mkdir -p "$t"
  git_init "$t"
  "$DOM" "$t" --guest >/dev/null 2>&1

  local out rc
  out="$("$DOM" "$t" --no-guest 2>&1)"; rc=$?

  check "exit 0" test "$rc" -eq 0
  check "mode marker removed" test ! -e "$t/$MODE_MARKER_REL"
  check "conversion instructions printed" bash -c 'printf "%s" "$1" | grep -q "converting guest install"' _ "$out"
  check "CLAUDE.md now created with managed block" grep -qF "BEGIN domestique (managed)" "$t/CLAUDE.md"
  check "CLAUDE.local.md still present" test -f "$t/CLAUDE.local.md"
}

# ---------------------------------------------------------------------------
# Scenario 7a: --guest --no-guest together is a usage error, exit 2.
# ---------------------------------------------------------------------------
scenario_guest_and_no_guest_conflict() {
  local t="$WORKROOT/s7a"; mkdir -p "$t"

  local out rc
  out="$("$DOM" "$t" --guest --no-guest 2>&1)"
  rc=$?

  check "exit 2" test "$rc" -eq 2
  # Also assert the error message names both flags, so an unrelated usage
  # error (e.g. a different flag conflict) that also happens to exit 2
  # cannot satisfy this scenario.
  check "error message mentions --guest" bash -c 'printf "%s" "$1" | grep -qF -- "--guest"' _ "$out"
  check "error message mentions --no-guest" bash -c 'printf "%s" "$1" | grep -qF -- "--no-guest"' _ "$out"
}

# ---------------------------------------------------------------------------
# Scenario 7b: corrupt marker — warns, proceeds in normal mode (no --guest
# flag on this run, so GUEST stays 0; the corrupt marker must not force guest
# mode on).
# ---------------------------------------------------------------------------
scenario_corrupt_marker() {
  local t="$WORKROOT/s7b"; mkdir -p "$t"
  git_init "$t"
  "$DOM" "$t" --guest >/dev/null 2>&1
  printf 'banana\n' > "$t/$MODE_MARKER_REL"

  local out rc
  out="$("$DOM" "$t" 2>&1)"; rc=$?

  check "exit 0" test "$rc" -eq 0
  check "warning mentions unexpected content" bash -c 'printf "%s" "$1" | grep -q "unexpected content"' _ "$out"
  check "CLAUDE.md created (normal mode proceeded)" test -f "$t/CLAUDE.md"
}

# ---------------------------------------------------------------------------
# Scenario 8a: sticky under --dry-run — plain --dry-run on a guest dir plans
# in guest mode; the marker file content is unchanged.
# ---------------------------------------------------------------------------
scenario_sticky_dry_run() {
  local t="$WORKROOT/s8a"; mkdir -p "$t"
  git_init "$t"
  "$DOM" "$t" --guest >/dev/null 2>&1
  local sha_before
  sha_before="$(filehash "$t/$MODE_MARKER_REL")"

  local out rc sha_after
  out="$("$DOM" "$t" --dry-run 2>&1)"; rc=$?
  sha_after="$(filehash "$t/$MODE_MARKER_REL")"

  check "exit 0" test "$rc" -eq 0
  check "sticky note printed under dry-run" bash -c 'printf "%s" "$1" | grep -q "staying in guest mode"' _ "$out"
  check "marker file unchanged" test "$sha_before" = "$sha_after"
  check "marker still contains guest" bash -c '[ "$(cat "$1")" = "guest" ]' _ "$t/$MODE_MARKER_REL"
}

# ---------------------------------------------------------------------------
# Scenario 8b: --no-guest --dry-run does NOT remove the marker.
# ---------------------------------------------------------------------------
scenario_no_guest_dry_run_keeps_marker() {
  local t="$WORKROOT/s8b"; mkdir -p "$t"
  git_init "$t"
  "$DOM" "$t" --guest >/dev/null 2>&1

  local out rc
  out="$("$DOM" "$t" --no-guest --dry-run 2>&1)"; rc=$?

  check "exit 0" test "$rc" -eq 0
  check "marker still present" test -e "$t/$MODE_MARKER_REL"
  check "marker content still guest" bash -c '[ "$(cat "$1")" = "guest" ]' _ "$t/$MODE_MARKER_REL"
  check "dry-run removal note printed" bash -c 'printf "%s" "$1" | grep -q "remove mode marker"' _ "$out"
}

# ---------------------------------------------------------------------------
# Scenario 9: tracked-path warning — CLAUDE.local.md already committed to the
# repo triggers a warning (a git-exclude entry cannot hide a tracked path).
# ---------------------------------------------------------------------------
scenario_tracked_path_warning() {
  local t="$WORKROOT/s9"; mkdir -p "$t"
  git_init "$t"
  printf 'pre-existing personal notes\n' > "$t/CLAUDE.local.md"
  git -C "$t" add CLAUDE.local.md
  git -C "$t" commit -q -m "accidentally tracked CLAUDE.local.md"

  local out rc
  out="$("$DOM" "$t" --guest 2>&1)"; rc=$?

  check "exit 0" test "$rc" -eq 0
  check "warning about already-tracked path printed" bash -c 'printf "%s" "$1" | grep -q "already tracked"' _ "$out"
}

# ---------------------------------------------------------------------------
# Scenario 10a: upstream merge (guest) — per-destination base
# (CLAUDE.local.md.block) lets a later run of a modified ("v2") script merge
# a new upstream line into CLAUDE.local.md.
# ---------------------------------------------------------------------------
scenario_guest_upstream_merge() {
  local t="$WORKROOT/s10a"; mkdir -p "$t"
  git_init "$t"
  "$DOM" "$t" --guest >/dev/null 2>&1

  # Local edit OUTSIDE the managed block, added after the v1 install and
  # before the v2 run. This is v1 evidence that (a) can only exist if the v1
  # install actually ran, and (b) must survive a genuine 3-way merge (it's
  # untouched by the upstream change, so git merge-file should carry it
  # through cleanly). Without a real v1 CLAUDE.local.md.block base to diff
  # against, the v2 run would just overwrite the file from scratch and this
  # sentinel would be lost — closing the "no merge actually occurred" gap.
  printf '\nMY LOCAL NOTE SENTINEL\n' >> "$t/CLAUDE.local.md"

  local out rc
  out="$("$V2G" "$t" --guest 2>&1)"; rc=$?

  check "exit 0" test "$rc" -eq 0
  check "upstream v2 line merged into CLAUDE.local.md" grep -q "(v2-guest-test)" "$t/CLAUDE.local.md"
  check "base snapshot key is per-destination (CLAUDE.local.md.block)" \
    test -f "$t/.claude/.domestique/base/CLAUDE.local.md.block"
  check "no stray CLAUDE.md.block base written under guest" \
    test ! -e "$t/.claude/.domestique/base/CLAUDE.md.block"
  # A real v2-over-v1 guest run reports the file as merged (not created); a
  # from-scratch create (i.e. no actual merge) would instead show up under
  # "Created:", never "Merged:". This is the direct check that a merge
  # actually happened, closing the blocking gap where neutering the v1 setup
  # still passed the scenario.
  check "summary reports Merged for CLAUDE.local.md" bash -c '
    printf "%s" "$1" | grep -A1 "^  Merged:$" | grep -qF "CLAUDE.local.md"
  ' _ "$out"
  # The pre-existing v1 local edit must have survived the merge — proof this
  # was a real 3-way merge against v1 content, not a from-scratch overwrite.
  check "pre-existing v1 local edit survived the merge" \
    grep -qF "MY LOCAL NOTE SENTINEL" "$t/CLAUDE.local.md"
}

# ---------------------------------------------------------------------------
# Scenario 10b: mixed-dir variant — plain v1 install, then guest v1 install
# into the SAME dir, then plain v2 (no --guest): CLAUDE.md still merges the
# upstream line (guest install alongside it doesn't interfere with the plain
# merge base).
# ---------------------------------------------------------------------------
#
# DEVIATION FROM BRIEF (reported, not silently resolved): the brief describes
# this as "plain v1 + guest v1 + plain v2" with a THIRD run taking no flags at
# all. But sticky guest mode (domestique.sh's documented behavior — see
# "Sticky mode" in usage() and the MODE_MARKER block) means a flag-less re-run
# against a dir carrying the guest marker stays in guest mode and would route
# into CLAUDE.local.md, not CLAUDE.md — verified empirically before writing
# this scenario. To exercise "a plain install's merge base is unaffected by a
# guest install having also touched the same dir" as the brief intends, the
# third run here uses --no-guest (the only way to force a genuinely plain run
# against a guest-marked dir) rather than no flags. This is a scenario-design
# adjustment to match actual product behavior, not a change to domestique.sh.
scenario_mixed_dir_plain_merge() {
  local t="$WORKROOT/s10b"; mkdir -p "$t"
  git_init "$t"
  "$DOM" "$t" >/dev/null 2>&1
  "$DOM" "$t" --guest >/dev/null 2>&1

  local out rc
  out="$("$V2G" "$t" --no-guest 2>&1)"; rc=$?

  check "exit 0" test "$rc" -eq 0
  check "upstream v2 line merged into CLAUDE.md" grep -q "(v2-guest-test)" "$t/CLAUDE.md"
  # Direct check that a real merge (not a from-scratch create) happened:
  # the summary must report CLAUDE.md under "Merged:". Neutering either v1
  # setup call above removes the base snapshot the merge depends on, which
  # would make this line disappear (the file would be Created or Adopted
  # instead), closing the blocking gap.
  check "summary reports Merged for CLAUDE.md" bash -c '
    printf "%s" "$1" | grep -A1 "^  Merged:$" | grep -qF "CLAUDE.md"
  ' _ "$out"
  # CLAUDE.local.md must actually exist (from the guest v1 install) before
  # the negative grep below is meaningful — otherwise "not containing the
  # sentinel" is trivially true of a nonexistent file.
  check "CLAUDE.local.md exists (from guest v1 install)" test -f "$t/CLAUDE.local.md"
  check "CLAUDE.local.md untouched by plain v2 run" bash -c '! grep -q "(v2-guest-test)" "$1"' _ "$t/CLAUDE.local.md"
  # This scenario's premise is that the third run is "genuinely plain"
  # (see the DEVIATION FROM BRIEF note above) — verify --no-guest actually
  # did its job of removing the sticky guest-mode marker within this run,
  # rather than assuming it from scenario 6b.
  check "--no-guest removed the mode marker" test ! -e "$t/$MODE_MARKER_REL"
}

# ---------------------------------------------------------------------------
echo "domestique guest-mode test harness"
echo "repo: $REPO_DIR"
echo

run_scenario "fresh guest install"                              scenario_fresh_guest_install
run_scenario "guest idempotency"                                scenario_guest_idempotent
run_scenario "--dry-run --guest on fresh clone creates nothing" scenario_guest_dry_run_fresh
run_scenario "non-git target dir"                               scenario_non_git_target
run_scenario "worktree — common git dir exclude"                scenario_worktree_common_dir
run_scenario "sticky mode: plain re-run stays guest"            scenario_sticky_plain_rerun
run_scenario "--no-guest converts"                              scenario_no_guest_conversion
run_scenario "--guest --no-guest is a usage error (exit 2)"     scenario_guest_and_no_guest_conflict
run_scenario "corrupt marker warns, normal mode"                scenario_corrupt_marker
run_scenario "sticky mode under --dry-run"                      scenario_sticky_dry_run
run_scenario "--no-guest --dry-run keeps the marker"            scenario_no_guest_dry_run_keeps_marker
run_scenario "tracked CLAUDE.local.md warning"                  scenario_tracked_path_warning
run_scenario "upstream merge (guest, CLAUDE.local.md)"          scenario_guest_upstream_merge
run_scenario "mixed-dir: plain merge unaffected by guest"       scenario_mixed_dir_plain_merge

echo
TOTAL=$((PASS_COUNT + FAIL_COUNT))
echo "$PASS_COUNT/$TOTAL passed"

if [ "$FAIL_COUNT" -gt 0 ]; then
  exit 1
fi
exit 0
