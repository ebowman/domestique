#!/usr/bin/env bash
# test/upgrade.sh — self-contained test harness for domestique.sh's
# install + 3-way-merge upgrade behavior. Runs each scenario in an isolated
# mktemp -d sandbox, reports PASS/FAIL per scenario, prints a final tally,
# and exits non-zero if any scenario failed. No external test framework.
#
# Run: bash test/upgrade.sh
#
# Intentionally does NOT use `set -e`: scenarios expect nonzero exit codes
# (conflicts exit 3) and we want to keep running all scenarios even if one
# assertion fails, so we check return codes explicitly throughout.
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

# treehash <dir> — a stable content+layout fingerprint of a directory tree,
# used to assert "no writes happened" (e.g. --dry-run) or "byte-identical
# snapshot across runs" (idempotency). Sorted file list makes it order-stable.
treehash() {
  local dir="$1"
  ( cd "$dir" && find . -type f | sort | xargs shasum -a 256 2>/dev/null ) | shasum -a 256 | awk '{print $1}'
}

# ---------------------------------------------------------------------------
# v2.sh — a modified copy of domestique.sh simulating an upstream change,
# per the brief's suggested technique: copy the real script, then sed-edit
# ONE line inside an emitter body (not the emitter machinery itself). We
# change two independent lines so both the plain-file merge path
# (emit_implementer) and the CLAUDE.md block merge path (emit_policy) can be
# exercised by upgrade scenarios, each on a line distinct from what test
# "local edits" touch (so we can construct both clean-merge and
# conflicting-merge cases deliberately).
# ---------------------------------------------------------------------------
V2="$WORKROOT/v2.sh"
cp "$DOM" "$V2"
# emit_implementer: change the "Blockers or decisions..." line (plain-file
# upgrade target).
sed -i.orig \
  's/Blockers or decisions the orchestrator should know about/Blockers or decisions the orchestrator should know about (v2)/' \
  "$V2"
# emit_policy: change the "Do not drain the queue..." line (CLAUDE.md
# managed-block upgrade target).
sed -i.orig \
  "s/Do not drain the queue unattended unless explicitly told to\\./Do not drain the queue unattended unless explicitly told to (v2-policy)./" \
  "$V2"
rm -f "$V2.orig"
chmod +x "$V2"

# ---------------------------------------------------------------------------
# v0.sh — a modified copy of domestique.sh simulating an OLDER upstream
# version than the one under test, used only to construct a "predates the
# emitter change" legacy install: a file whose pristine content differs from
# the CURRENT script's pristine emit at the same spot v2.sh changes further
# still. Same sed-one-line technique as v2.sh.
# ---------------------------------------------------------------------------
V0="$WORKROOT/v0.sh"
cp "$DOM" "$V0"
sed -i.orig \
  's/Blockers or decisions the orchestrator should know about/Old-style blockers wording (predates-emitter-change)/' \
  "$V0"
rm -f "$V0.orig"
chmod +x "$V0"

IMPL_REL=".claude/agents/implementer.md"
CLAUDE_REL="CLAUDE.md"
BASE_IMPL_REL=".claude/.domestique/base/.claude/agents/implementer.md"
BASE_CLAUDE_BLOCK_REL=".claude/.domestique/base/CLAUDE.md.block"
MANIFEST_REL=".claude/.domestique/manifest"

# ---------------------------------------------------------------------------
# Scenario 1: fresh install
# ---------------------------------------------------------------------------
scenario_fresh_install() {
  local t="$WORKROOT/s1"; mkdir -p "$t"
  local out rc
  out="$("$DOM" "$t" 2>&1)"; rc=$?

  check "exit 0" test "$rc" -eq 0
  check "CLAUDE.md created" test -f "$t/$CLAUDE_REL"
  check "implementer.md created" test -f "$t/$IMPL_REL"
  check "reviewer.md created" test -f "$t/.claude/agents/reviewer.md"
  check "decompose.md created" test -f "$t/.claude/commands/decompose.md"
  check "decompose.md has grilling pre-step" grep -q 'grilling' "$t/.claude/commands/decompose.md"
  check "decompose.md has ponytail-audit post-step" grep -q 'ponytail-audit' "$t/.claude/commands/decompose.md"
  check "decompose.md has grilling fallback notice" grep -q 'No grilling skill installed' "$t/.claude/commands/decompose.md"
  check "decompose.md has ponytail-audit fallback notice" grep -q 'No ponytail-audit skill found' "$t/.claude/commands/decompose.md"
  check "base snapshot for implementer.md written" test -f "$t/$BASE_IMPL_REL"
  check "base snapshot for reviewer.md written" test -f "$t/.claude/.domestique/base/.claude/agents/reviewer.md"
  check "base snapshot for decompose.md written" test -f "$t/.claude/.domestique/base/.claude/commands/decompose.md"
  check "base CLAUDE.md.block snapshot written" test -f "$t/$BASE_CLAUDE_BLOCK_REL"
  check "manifest written" test -f "$t/$MANIFEST_REL"
}

# ---------------------------------------------------------------------------
# Scenario 2: idempotent re-install
# ---------------------------------------------------------------------------
scenario_idempotent_reinstall() {
  local t="$WORKROOT/s2"; mkdir -p "$t"
  "$DOM" "$t" >/dev/null 2>&1

  local hash_before hash_after out rc
  hash_before="$(treehash "$t")"
  out="$("$DOM" "$t" 2>&1)"; rc=$?
  hash_after="$(treehash "$t")"

  check "exit 0" test "$rc" -eq 0
  check "all managed files reported Skipped" bash -c 'printf "%s" "$1" | grep -q "Skipped"' _ "$out"
  check "no .new files" bash -c '! find "$1" -name "*.new" | grep -q .' _ "$t"
  check "no .bak files" bash -c '! find "$1" -name "*.bak.*" | grep -q .' _ "$t"
  check "no Merged/Updated/Created/Conflicted reported" bash -c '
    ! printf "%s" "$1" | grep -Eq "^  (Created|Updated|Merged|Conflicted):"
  ' _ "$out"
  check ".claude/.domestique byte-identical across the two runs" test "$hash_before" = "$hash_after"
}

# ---------------------------------------------------------------------------
# Scenario 3: upgrade, no local edits — clean/trivial merge, no .new
# ---------------------------------------------------------------------------
scenario_upgrade_no_local_edits() {
  local t="$WORKROOT/s3"; mkdir -p "$t"
  "$DOM" "$t" >/dev/null 2>&1

  local out rc
  out="$("$V2" "$t" 2>&1)"; rc=$?

  check "exit 0" test "$rc" -eq 0
  check "implementer.md picked up upstream change" grep -q "(v2)" "$t/$IMPL_REL"
  check "no .new written" test ! -e "$t/$IMPL_REL.new"
  check "base snapshot advanced to v2 content" grep -q "(v2)" "$t/$BASE_IMPL_REL"
}

# ---------------------------------------------------------------------------
# Scenario 4: upgrade preserves a local edit (plain file), different lines
# ---------------------------------------------------------------------------
scenario_upgrade_preserves_local_edit_plain() {
  local t="$WORKROOT/s4"; mkdir -p "$t"
  "$DOM" "$t" >/dev/null 2>&1

  # Edit a DIFFERENT line than the one v2 changes.
  sed -i.orig \
    's/Never touch credentials, secrets, access controls, or destructive git operations\. Surface these to the orchestrator instead\./Never touch credentials, secrets, access controls, or destructive git operations. Surface these to the orchestrator instead. (user-edit)/' \
    "$t/$IMPL_REL"
  rm -f "$t/$IMPL_REL.orig"

  local out rc
  out="$("$V2" "$t" 2>&1)"; rc=$?

  check "exit 0" test "$rc" -eq 0
  check "user edit preserved" grep -q "(user-edit)" "$t/$IMPL_REL"
  check "upstream edit merged in" grep -q "(v2)" "$t/$IMPL_REL"
  check "reported as Merged" bash -c 'printf "%s" "$1" | grep -q "Merged"' _ "$out"
  check "no .new written" test ! -e "$t/$IMPL_REL.new"
}

# ---------------------------------------------------------------------------
# Scenario 5: conflict (plain file) — same line edited on both sides
# ---------------------------------------------------------------------------
scenario_conflict_plain() {
  local t="$WORKROOT/s5"; mkdir -p "$t"
  "$DOM" "$t" >/dev/null 2>&1

  # Edit the SAME line v2 changes, to a colliding value.
  sed -i.orig \
    's/Blockers or decisions the orchestrator should know about/Blockers or decisions the orchestrator should know about (conflicting-user-edit)/' \
    "$t/$IMPL_REL"
  rm -f "$t/$IMPL_REL.orig"

  local before="$WORKROOT/s5.before" out rc
  cp "$t/$IMPL_REL" "$before"
  out="$("$V2" "$t" 2>&1)"; rc=$?

  check "exit 3" test "$rc" -eq 3
  check ".new written with conflict markers" bash -c 'grep -q "<<<<<<<" "$1" && grep -q ">>>>>>>" "$1"' _ "$t/$IMPL_REL.new"
  check "live file byte-unchanged" cmp -s "$before" "$t/$IMPL_REL"
  check ".bak present" bash -c 'find "$1" -maxdepth 1 -name "implementer.md.bak.*" | grep -q .' _ "$(dirname "$t/$IMPL_REL")"
}

# ---------------------------------------------------------------------------
# Scenario 6: CLAUDE.md in-block edit preserved + outside-marker edit intact
# ---------------------------------------------------------------------------
scenario_claude_md_inblock_preserved() {
  local t="$WORKROOT/s6"; mkdir -p "$t"
  "$DOM" "$t" >/dev/null 2>&1

  # Edit inside the block, on a DIFFERENT line than v2's emit_policy change.
  sed -i.orig \
    's/- The plan of record lives in beads (`bd`), not in markdown TODO lists\./- The plan of record lives in beads (`bd`), not in markdown TODO lists. (user-edit-block)/' \
    "$t/$CLAUDE_REL"
  rm -f "$t/$CLAUDE_REL.orig"
  # Add content OUTSIDE the managed markers.
  printf '\n## My own notes\nSome text outside the managed block.\n' >> "$t/$CLAUDE_REL"

  local out rc
  out="$("$V2" "$t" 2>&1)"; rc=$?

  check "exit 0" test "$rc" -eq 0
  check "in-block user edit preserved" grep -q "(user-edit-block)" "$t/$CLAUDE_REL"
  check "upstream policy edit merged in" grep -q "(v2-policy)" "$t/$CLAUDE_REL"
  check "outside-marker text unchanged" grep -q "Some text outside the managed block." "$t/$CLAUDE_REL"
  check "outside-marker heading unchanged" grep -q "## My own notes" "$t/$CLAUDE_REL"
  check "reported as Merged" bash -c 'printf "%s" "$1" | grep -q "Merged"' _ "$out"
}

# ---------------------------------------------------------------------------
# Scenario 7: CLAUDE.md conflict — colliding in-block edit
# ---------------------------------------------------------------------------
scenario_claude_md_conflict() {
  local t="$WORKROOT/s7"; mkdir -p "$t"
  "$DOM" "$t" >/dev/null 2>&1

  # Edit the SAME in-block line v2's emit_policy change touches.
  sed -i.orig \
    "s/Do not drain the queue unattended unless explicitly told to\\./Do not drain the queue unattended unless explicitly told to (conflicting-edit)./" \
    "$t/$CLAUDE_REL"
  rm -f "$t/$CLAUDE_REL.orig"

  local before="$WORKROOT/s7.before" out rc
  cp "$t/$CLAUDE_REL" "$before"
  out="$("$V2" "$t" 2>&1)"; rc=$?

  check "exit 3" test "$rc" -eq 3
  check "CLAUDE.md.new written with conflict markers" bash -c 'grep -q "<<<<<<<" "$1" && grep -q ">>>>>>>" "$1"' _ "$t/$CLAUDE_REL.new"
  check "live CLAUDE.md unchanged" cmp -s "$before" "$t/$CLAUDE_REL"
  check ".bak present" bash -c 'find "$1" -maxdepth 1 -name "CLAUDE.md.bak.*" | grep -q .' _ "$t"
}

# ---------------------------------------------------------------------------
# Scenario 8: legacy adopt — no snapshot present, differing file is adopted
# (local edit preserved, no clobber) rather than backed up + overwritten.
# ---------------------------------------------------------------------------
scenario_legacy_fallback() {
  local t="$WORKROOT/s8"; mkdir -p "$t"
  "$DOM" "$t" >/dev/null 2>&1
  rm -rf "$t/.claude/.domestique"

  sed -i.orig 's/^tools:/tools: EDITED/' "$t/$IMPL_REL"
  rm -f "$t/$IMPL_REL.orig"
  local before; before="$(cat "$t/$IMPL_REL")"

  local out rc
  out="$("$DOM" "$t" 2>&1)"; rc=$?

  check "exit 0" test "$rc" -eq 0
  check "no backup written" bash -c '! find "$1" -maxdepth 1 -name "implementer.md.bak.*" | grep -q .' _ "$(dirname "$t/$IMPL_REL")"
  check "live file unchanged (local edit preserved)" bash -c '[ "$1" = "$(cat "$2")" ]' _ "$before" "$t/$IMPL_REL"
  check "edit still present" grep -q "tools: EDITED" "$t/$IMPL_REL"
  check "base snapshot seeded from pristine emit (no edit)" bash -c '! grep -q "tools: EDITED" "$1"' _ "$t/$BASE_IMPL_REL"
  check "fresh manifest recreated" test -f "$t/$MANIFEST_REL"
  check "reported as adopted" bash -c 'printf "%s" "$1" | grep -q "Adopted"' _ "$out"
}

# ---------------------------------------------------------------------------
# Scenario 9: --dry-run with a pending merge makes no writes
# ---------------------------------------------------------------------------
scenario_dry_run_no_writes() {
  local t="$WORKROOT/s9"; mkdir -p "$t"
  "$DOM" "$t" >/dev/null 2>&1

  # A pending (mergeable, non-conflicting) upstream change is queued up by
  # using v2 as the "next run" against an untouched install.
  local hash_before out rc hash_after
  hash_before="$(treehash "$t")"
  out="$("$V2" "$t" --dry-run 2>&1)"; rc=$?
  hash_after="$(treehash "$t")"

  check "exit 0" test "$rc" -eq 0
  check "no writes: whole-tree checksum unchanged" test "$hash_before" = "$hash_after"
  check "dry-run banner present" bash -c 'printf "%s" "$1" | grep -q "dry run"' _ "$out"
}

# ---------------------------------------------------------------------------
# Scenario 10: adopt then upgrade merges (plain file) — a legacy install with
# a local edit gets adopted (no clobber), and the NEXT run 3-way-merges in
# the upstream change while keeping the local edit.
# ---------------------------------------------------------------------------
scenario_adopt_then_upgrade_merges_plain() {
  local t="$WORKROOT/s10"; mkdir -p "$t"
  "$DOM" "$t" >/dev/null 2>&1
  rm -rf "$t/.claude/.domestique"

  # Local edit: append an mcp__ tool to the tools: line.
  sed -i.orig \
    's/^tools: Read, Write, Edit, Bash, Glob, Grep$/tools: Read, Write, Edit, Bash, Glob, Grep, mcp__filesystem/' \
    "$t/$IMPL_REL"
  rm -f "$t/$IMPL_REL.orig"
  local before; before="$(cat "$t/$IMPL_REL")"

  local out1 rc1
  out1="$("$DOM" "$t" 2>&1)"; rc1=$?

  check "adopt: exit 0" test "$rc1" -eq 0
  check "adopt: reported as Adopted" bash -c 'printf "%s" "$1" | grep -q "Adopted"' _ "$out1"
  check "adopt: live file byte-unchanged" bash -c '[ "$1" = "$(cat "$2")" ]' _ "$before" "$t/$IMPL_REL"
  check "adopt: no .bak written" bash -c '! find "$1" -maxdepth 1 -name "implementer.md.bak.*" | grep -q .' _ "$(dirname "$t/$IMPL_REL")"
  check "adopt: base snapshot seeded (pristine, no local edit)" bash -c '! grep -q "mcp__filesystem" "$1"' _ "$t/$BASE_IMPL_REL"

  local out2 rc2
  out2="$("$V2" "$t" 2>&1)"; rc2=$?

  check "upgrade: exit 0" test "$rc2" -eq 0
  check "upgrade: local mcp__ edit preserved" grep -q "mcp__filesystem" "$t/$IMPL_REL"
  check "upgrade: upstream (v2) change merged in" grep -q "(v2)" "$t/$IMPL_REL"
  check "upgrade: no .new written" test ! -e "$t/$IMPL_REL.new"
}

# ---------------------------------------------------------------------------
# Scenario 11: CLAUDE.md managed-block adopt then merge — a legacy install
# with a local in-block edit gets adopted, and the NEXT run 3-way-merges the
# upstream policy change while keeping the local edit and everything outside
# the markers.
# ---------------------------------------------------------------------------
scenario_adopt_then_upgrade_merges_claude_md() {
  local t="$WORKROOT/s11"; mkdir -p "$t"
  "$DOM" "$t" >/dev/null 2>&1
  rm -rf "$t/.claude/.domestique"

  # Local edit inside the block, on a DIFFERENT line than v2's emit_policy change.
  sed -i.orig \
    's/- The plan of record lives in beads (`bd`), not in markdown TODO lists\./- The plan of record lives in beads (`bd`), not in markdown TODO lists. (user-edit-block2)/' \
    "$t/$CLAUDE_REL"
  rm -f "$t/$CLAUDE_REL.orig"
  # Content outside the managed markers.
  printf '\n## My own notes (s11)\nSome other text outside the managed block.\n' >> "$t/$CLAUDE_REL"
  local before; before="$(cat "$t/$CLAUDE_REL")"

  local out1 rc1
  out1="$("$DOM" "$t" 2>&1)"; rc1=$?

  check "adopt: exit 0" test "$rc1" -eq 0
  check "adopt: reported as Adopted" bash -c 'printf "%s" "$1" | grep -q "Adopted"' _ "$out1"
  check "adopt: CLAUDE.md byte-unchanged" bash -c '[ "$1" = "$(cat "$2")" ]' _ "$before" "$t/$CLAUDE_REL"
  check "adopt: no .bak written" bash -c '! find "$1" -maxdepth 1 -name "CLAUDE.md.bak.*" | grep -q .' _ "$t"
  check "adopt: base block snapshot seeded (pristine, no local edit)" bash -c '! grep -q "user-edit-block2" "$1"' _ "$t/$BASE_CLAUDE_BLOCK_REL"

  local out2 rc2
  out2="$("$V2" "$t" 2>&1)"; rc2=$?

  check "upgrade: exit 0" test "$rc2" -eq 0
  check "upgrade: local in-block edit preserved" grep -q "user-edit-block2" "$t/$CLAUDE_REL"
  check "upgrade: upstream policy edit merged in" grep -q "(v2-policy)" "$t/$CLAUDE_REL"
  check "upgrade: outside-marker heading unchanged" grep -q "## My own notes (s11)" "$t/$CLAUDE_REL"
  check "upgrade: outside-marker text unchanged" grep -q "Some other text outside the managed block." "$t/$CLAUDE_REL"
}

# ---------------------------------------------------------------------------
# Scenario 12: predates-emitter-change — a legacy file whose pristine content
# is OLDER than the current script's pristine emit (differs at the same spot
# v2 changes further), plus an unrelated local edit. Adopting with the
# CURRENT script seeds base from current-pristine (which already differs
# from ours at that spot); upgrading to v2 then touches that same region
# again. Assert the local edit is never silently dropped: it must survive in
# the live file (clean merge or untouched-on-conflict) and/or be visible in a
# surfaced .new conflict, with a non-zero-but-known (3) exit on conflict.
# ---------------------------------------------------------------------------
scenario_predates_emitter_change_conflict() {
  local t="$WORKROOT/s12"; mkdir -p "$t"
  "$V0" "$t" >/dev/null 2>&1
  rm -rf "$t/.claude/.domestique"

  # Unrelated local edit (legacy user edit), on a different line than the
  # Blockers region v0/v2 touch.
  sed -i.orig \
    's/^tools: Read, Write, Edit, Bash, Glob, Grep$/tools: EDITED-legacy/' \
    "$t/$IMPL_REL"
  rm -f "$t/$IMPL_REL.orig"
  local before1; before1="$(cat "$t/$IMPL_REL")"

  # Adopt with the CURRENT script: seeds base from current-pristine, which
  # differs from ours at the Blockers line (ours still has v0's old wording).
  local out1 rc1
  out1="$("$DOM" "$t" 2>&1)"; rc1=$?

  check "adopt: exit 0" test "$rc1" -eq 0
  check "adopt: reported as Adopted" bash -c 'printf "%s" "$1" | grep -q "Adopted"' _ "$out1"
  check "adopt: live file unchanged" bash -c '[ "$1" = "$(cat "$2")" ]' _ "$before1" "$t/$IMPL_REL"

  # Upgrade to v2, which changes the SAME region (Blockers line) that already
  # diverges between ours (old wording) and base (current wording).
  local before2; before2="$(cat "$t/$IMPL_REL")"
  local out2 rc2
  out2="$("$V2" "$t" 2>&1)"; rc2=$?

  if [ "$rc2" -eq 0 ]; then
    check "clean-merge exit 0 implies local edit preserved" grep -q "EDITED-legacy" "$t/$IMPL_REL"
  elif [ "$rc2" -eq 3 ]; then
    check "conflict: exit 3" test "$rc2" -eq 3
    check "conflict: .new written with conflict markers" bash -c 'grep -q "<<<<<<<" "$1"' _ "$t/$IMPL_REL.new"
    check "conflict: live file left untouched" bash -c '[ "$1" = "$(cat "$2")" ]' _ "$before2" "$t/$IMPL_REL"
    check "conflict: local edit present in (untouched) live file" grep -q "EDITED-legacy" "$t/$IMPL_REL"
  else
    check "upgrade exit code is either 0 (merged) or 3 (conflict) — no silent loss" false
  fi
}

# ---------------------------------------------------------------------------
echo "domestique upgrade test harness"
echo "repo: $REPO_DIR"
echo

run_scenario "fresh install"                                   scenario_fresh_install
run_scenario "idempotent re-install"                            scenario_idempotent_reinstall
run_scenario "upgrade, no local edits"                          scenario_upgrade_no_local_edits
run_scenario "upgrade preserves a local edit (plain file)"      scenario_upgrade_preserves_local_edit_plain
run_scenario "conflict (plain file)"                            scenario_conflict_plain
run_scenario "CLAUDE.md in-block edit preserved"                scenario_claude_md_inblock_preserved
run_scenario "CLAUDE.md conflict"                               scenario_claude_md_conflict
run_scenario "legacy fallback (no snapshot)"                    scenario_legacy_fallback
run_scenario "--dry-run makes no writes"                        scenario_dry_run_no_writes
run_scenario "adopt then upgrade merges (plain)"                scenario_adopt_then_upgrade_merges_plain
run_scenario "adopt then upgrade merges (CLAUDE.md block)"      scenario_adopt_then_upgrade_merges_claude_md
run_scenario "predates-emitter-change conflict"                 scenario_predates_emitter_change_conflict

echo
TOTAL=$((PASS_COUNT + FAIL_COUNT))
echo "$PASS_COUNT/$TOTAL passed"

if [ "$FAIL_COUNT" -gt 0 ]; then
  exit 1
fi
exit 0
