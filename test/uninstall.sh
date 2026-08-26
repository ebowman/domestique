#!/usr/bin/env bash
# test/uninstall.sh — self-contained test harness for domestique.sh's
# `--uninstall` behavior. Runs each scenario in an isolated mktemp -d
# sandbox, reports PASS/FAIL per scenario, prints a final tally, and exits
# non-zero if any scenario failed. No external test framework, no network.
#
# Run: bash test/uninstall.sh
#
# Conventions follow test/guest.sh and test/upgrade.sh: single mktemp
# WORKROOT with an EXIT-trap cleanup, check()/run_scenario() harness,
# filehash()/treehash() for byte-identical comparisons, deterministic,
# hermetic. Intentionally does NOT use `set -e`: several scenarios expect
# nonzero exit codes (usage errors exit 2, marker-corruption refusals exit 3)
# and we want every assertion in a scenario to run even if an earlier one in
# the same scenario fails.
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

# treehash <dir> — a stable content+layout fingerprint of a directory tree,
# used to assert "no writes happened" (e.g. --dry-run). Sorted file list
# makes it order-stable.
treehash() {
  local dir="$1"
  ( cd "$dir" && find . -type f | sort | xargs shasum -a 256 2>/dev/null ) | shasum -a 256 | awk '{print $1}'
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
# Marker constants — literal duplicates of domestique.sh's own MARKER_BEGIN /
# MARKER_END / GITEXCLUDE_MARKER_BEGIN / GITEXCLUDE_MARKER_END (kept
# self-contained per test/guest.sh's convention rather than sourcing the
# product script's internals).
# ---------------------------------------------------------------------------
MARKER_BEGIN='<!-- BEGIN domestique (managed) -->'
MARKER_END='<!-- END domestique -->'

IMPL_REL=".claude/agents/implementer.md"
REVIEWER_REL=".claude/agents/reviewer.md"
DRAIN_REL=".claude/commands/drain.md"
SNAPSHOT_REL=".claude/.domestique"
MODE_MARKER_REL=".claude/.domestique/mode"

# ---------------------------------------------------------------------------
# Marker-corruption helpers — mutate an on-disk managed-block file to exercise
# markers_sane()'s refusal paths. Test-only; never touch domestique.sh.
# ---------------------------------------------------------------------------

# corrupt_remove_begin <file> — deletes the BEGIN marker line, leaving a lone
# END marker ("half", END-only).
corrupt_remove_begin() {
  local f="$1" tmp; tmp="$f.corrupt.tmp"
  grep -vxF "$MARKER_BEGIN" "$f" > "$tmp" && mv "$tmp" "$f"
}

# corrupt_remove_end <file> — deletes the END marker line, leaving a lone
# BEGIN marker ("half", BEGIN-only).
corrupt_remove_end() {
  local f="$1" tmp; tmp="$f.corrupt.tmp"
  grep -vxF "$MARKER_END" "$f" > "$tmp" && mv "$tmp" "$f"
}

# corrupt_dup_begin <file> — duplicates the BEGIN marker line immediately
# after its first occurrence ("dup_begin").
corrupt_dup_begin() {
  local f="$1" tmp; tmp="$f.corrupt.tmp"
  awk -v b="$MARKER_BEGIN" '
    { print }
    $0 == b && !done { print b; done=1 }
  ' "$f" > "$tmp" && mv "$tmp" "$f"
}

# corrupt_dup_end <file> — duplicates the END marker line immediately after
# its first occurrence ("dup_end").
corrupt_dup_end() {
  local f="$1" tmp; tmp="$f.corrupt.tmp"
  awk -v e="$MARKER_END" '
    { print }
    $0 == e && !done { print e; done=1 }
  ' "$f" > "$tmp" && mv "$tmp" "$f"
}

# corrupt_invert <file> — swaps the BEGIN and END marker lines' text in
# place, so the (earlier-positioned) line now reads END and the
# (later-positioned) line now reads BEGIN: END now appears before BEGIN
# ("inverted"), with the block body between them unchanged.
corrupt_invert() {
  local f="$1" tmp; tmp="$f.corrupt.tmp"
  awk -v b="$MARKER_BEGIN" -v e="$MARKER_END" '
    $0 == b { print e; next }
    $0 == e { print b; next }
    { print }
  ' "$f" > "$tmp" && mv "$tmp" "$f"
}

# corrupt_trailing_space_begin <file> — appends a trailing space to the
# BEGIN marker line so it no longer exact-line-matches MARKER_BEGIN (grep
# -cxF sees zero BEGIN occurrences), while the END marker is untouched. This
# regression-tests guard/strip consistency: the guard (markers_sane, exact
# whole-line match) and the strip (awk, exact whole-line match) must agree
# that this is NOT a well-formed block ("half", END-only) rather than the
# guard passing it while the strip's own exact match then fails to find the
# BEGIN line (which would corrupt a different span).
corrupt_trailing_space_begin() {
  local f="$1" tmp; tmp="$f.corrupt.tmp"
  awk -v b="$MARKER_BEGIN" '
    $0 == b { print $0 " "; next }
    { print }
  ' "$f" > "$tmp" && mv "$tmp" "$f"
}

# only_bak_in_status <dir> — true iff `git status --porcelain` in <dir> has
# exactly one line, and that line is an untracked CLAUDE.md.bak.<timestamp>.
only_bak_in_status() {
  local dir="$1" status nlines
  status="$(git -C "$dir" status --porcelain)"
  [ -n "$status" ] || return 1
  nlines="$(printf '%s\n' "$status" | grep -c '.')"
  [ "$nlines" -eq 1 ] || return 1
  printf '%s\n' "$status" | grep -qE '^\?\? CLAUDE\.md\.bak\.[0-9]+$'
}

# ---------------------------------------------------------------------------
# Scenario 1: plain round-trip — install then uninstall restores CLAUDE.md
# byte-for-byte, leaving only the install-created .bak as residue.
# ---------------------------------------------------------------------------
scenario_plain_roundtrip() {
  local t="$WORKROOT/s1"; mkdir -p "$t"
  git_init "$t"
  printf '# My Project\n\nSome existing docs.\n' > "$t/CLAUDE.md"
  printf 'echo hi\n' > "$t/main.sh"
  git -C "$t" add CLAUDE.md main.sh
  git -C "$t" commit -q -m "initial"

  local sha_pre; sha_pre="$(filehash "$t/CLAUDE.md")"

  local out_i rc_i
  out_i="$("$DOM" "$t" 2>&1)"; rc_i=$?
  check "install: exit 0" test "$rc_i" -eq 0
  check "install: implementer.md installed (setup ran)" test -f "$t/$IMPL_REL"
  check "install: CLAUDE.md carries managed block (setup ran)" grep -qF "$MARKER_BEGIN" "$t/CLAUDE.md"
  check "install: drain.md installed (setup ran)" test -f "$t/$DRAIN_REL"

  local out_u rc_u
  out_u="$("$DOM" "$t" --uninstall 2>&1)"; rc_u=$?
  local sha_post; sha_post="$(filehash "$t/CLAUDE.md")"

  check "uninstall: exit 0" test "$rc_u" -eq 0
  check "CLAUDE.md byte-identical to pre-install" test "$sha_pre" = "$sha_post"
  check ".claude/ gone" test ! -e "$t/.claude"
  check "git status --porcelain shows ONLY the install .bak" only_bak_in_status "$t"
}

# ---------------------------------------------------------------------------
# Scenario 2: guest round-trip — guest install then uninstall leaves the
# working tree exactly as it started (git status empty), preserving
# pre-seeded exclude lines.
# ---------------------------------------------------------------------------
scenario_guest_roundtrip() {
  local t="$WORKROOT/s2"; mkdir -p "$t"
  git_init "$t"
  printf 'custom-user-pattern\n' >> "$t/.git/info/exclude"

  local out_i rc_i
  out_i="$("$DOM" "$t" --guest 2>&1)"; rc_i=$?
  check "install: exit 0" test "$rc_i" -eq 0
  check "install: CLAUDE.local.md created (setup ran)" test -f "$t/CLAUDE.local.md"
  check "install: exclude has managed block (setup ran)" grep -qF "# BEGIN domestique (managed)" "$t/.git/info/exclude"
  check "install: exclude still has pre-seeded user line (setup ran)" grep -qxF "custom-user-pattern" "$t/.git/info/exclude"
  check "install: drain.md installed (setup ran)" test -f "$t/$DRAIN_REL"

  local out_u rc_u
  out_u="$("$DOM" "$t" --uninstall 2>&1)"; rc_u=$?

  check "uninstall: exit 0" test "$rc_u" -eq 0
  check "git status --porcelain empty" bash -c '[ -z "$(git -C "$1" status --porcelain)" ]' _ "$t"
  check "CLAUDE.local.md gone" test ! -e "$t/CLAUDE.local.md"
  check "exclude block gone" bash -c '! grep -qF "# BEGIN domestique (managed)" "$1"' _ "$t/.git/info/exclude"
  check "exclude pre-seeded user line preserved" grep -qxF "custom-user-pattern" "$t/.git/info/exclude"
  check "mode marker gone" test ! -e "$t/$MODE_MARKER_REL"
  check ".claude/ gone" test ! -e "$t/.claude"
}

# ---------------------------------------------------------------------------
# Scenario 3a: modified .claude/ file is kept, renamed .uninstalled.<TS>.
# ---------------------------------------------------------------------------
scenario_modified_file_kept() {
  local t="$WORKROOT/s3a"; mkdir -p "$t"
  git_init "$t"
  "$DOM" "$t" >/dev/null 2>&1
  check "install: reviewer.md present (setup ran)" test -f "$t/$REVIEWER_REL"

  printf '\nUSER EDIT SENTINEL\n' >> "$t/$REVIEWER_REL"
  check "edit applied before uninstall (setup ran)" grep -qF "USER EDIT SENTINEL" "$t/$REVIEWER_REL"

  local out rc
  out="$("$DOM" "$t" --uninstall 2>&1)"; rc=$?

  check "exit 0" test "$rc" -eq 0
  check "original path gone" test ! -e "$t/$REVIEWER_REL"
  check "kept as reviewer.md.uninstalled.<TS> (glob)" bash -c '
    shopt -s nullglob
    files=("$1".uninstalled.*)
    [ "${#files[@]}" -eq 1 ] && grep -qF "USER EDIT SENTINEL" "${files[0]}"
  ' _ "$t/$REVIEWER_REL"
  check "reported under Kept (modified)" bash -c '
    printf "%s" "$1" | grep -A3 "^  Kept (modified):$" | grep -q "reviewer.md.uninstalled"
  ' _ "$out"
}

# ---------------------------------------------------------------------------
# Scenario 3b: modified .claude/ file with --force is deleted, not kept.
# ---------------------------------------------------------------------------
scenario_modified_file_force_removed() {
  local t="$WORKROOT/s3b"; mkdir -p "$t"
  git_init "$t"
  "$DOM" "$t" >/dev/null 2>&1
  printf '\nUSER EDIT SENTINEL\n' >> "$t/$REVIEWER_REL"
  check "edit applied before uninstall (setup ran)" grep -qF "USER EDIT SENTINEL" "$t/$REVIEWER_REL"

  local out rc
  out="$("$DOM" "$t" --uninstall --force 2>&1)"; rc=$?

  check "exit 0" test "$rc" -eq 0
  check "original path gone" test ! -e "$t/$REVIEWER_REL"
  check "no .uninstalled residue left" bash -c '
    shopt -s nullglob
    files=("$1".uninstalled.*)
    [ "${#files[@]}" -eq 0 ]
  ' _ "$t/$REVIEWER_REL"
  check "reported Removed (modified, --force)" bash -c '
    printf "%s" "$1" | grep -A6 "^  Removed:$" | grep -q "reviewer.md (modified, --force)"
  ' _ "$out"
}

# ---------------------------------------------------------------------------
# Scenario 4: policy file user-modified in-block edit — strip backs up (user
# modified rule), preserves content outside the managed block.
# ---------------------------------------------------------------------------
scenario_policy_modified_backup() {
  local t="$WORKROOT/s4"; mkdir -p "$t"
  git_init "$t"
  printf '# Header\n\nExtra outside text.\n' > "$t/CLAUDE.md"
  git -C "$t" add CLAUDE.md
  git -C "$t" commit -q -m "initial"
  "$DOM" "$t" >/dev/null 2>&1
  check "install: managed block present (setup ran)" grep -qF "$MARKER_BEGIN" "$t/CLAUDE.md"

  sed -i.orig \
    's/- The plan of record lives in beads (`bd`), not in markdown TODO lists\./- The plan of record lives in beads (`bd`), not in markdown TODO lists. (user-edit)/' \
    "$t/CLAUDE.md"
  rm -f "$t/CLAUDE.md.orig"
  check "in-block edit applied before uninstall (setup ran)" grep -qF "(user-edit)" "$t/CLAUDE.md"

  local out rc
  out="$("$DOM" "$t" --uninstall 2>&1)"; rc=$?

  check "exit 0" test "$rc" -eq 0
  check "managed block gone" bash -c '! grep -qF "$2" "$1"' _ "$t/CLAUDE.md" "$MARKER_BEGIN"
  check "a CLAUDE.md.bak.* backup captured the user-modified block" bash -c '
    shopt -s nullglob
    for f in "$1"/CLAUDE.md.bak.*; do
      grep -qF "(user-edit)" "$f" && exit 0
    done
    exit 1
  ' _ "$t"
  check "outside-block header preserved" grep -qF "# Header" "$t/CLAUDE.md"
  check "outside-block text preserved" grep -qF "Extra outside text." "$t/CLAUDE.md"
}

# ---------------------------------------------------------------------------
# Scenario 5a: .beads/ is preserved by default, with an informational note.
# ---------------------------------------------------------------------------
scenario_beads_preserved() {
  local t="$WORKROOT/s5a"; mkdir -p "$t"
  git_init "$t"
  "$DOM" "$t" >/dev/null 2>&1
  mkdir -p "$t/.beads"
  printf 'dummy\n' > "$t/.beads/dummy.txt"

  local out rc
  out="$("$DOM" "$t" --uninstall 2>&1)"; rc=$?

  check "exit 0" test "$rc" -eq 0
  check ".beads/ preserved" test -d "$t/.beads"
  check ".beads/dummy.txt preserved" test -f "$t/.beads/dummy.txt"
  check "informational note printed" bash -c 'printf "%s" "$1" | grep -q "left in place"' _ "$out"
}

# ---------------------------------------------------------------------------
# Scenario 5b: --purge-beads removes .beads/ and reports it.
# ---------------------------------------------------------------------------
scenario_beads_purged() {
  local t="$WORKROOT/s5b"; mkdir -p "$t"
  git_init "$t"
  "$DOM" "$t" >/dev/null 2>&1
  mkdir -p "$t/.beads"
  printf 'dummy\n' > "$t/.beads/dummy.txt"

  local out rc
  out="$("$DOM" "$t" --uninstall --purge-beads 2>&1)"; rc=$?

  check "exit 0" test "$rc" -eq 0
  check ".beads/ removed" test ! -e "$t/.beads"
  check "reported Removed (--purge-beads)" bash -c '
    printf "%s" "$1" | grep -A8 "^  Removed:$" | grep -q ".beads (--purge-beads)"
  ' _ "$out"
}

# ---------------------------------------------------------------------------
# Scenario 5c: --purge-beads without --uninstall is a usage error, exit 2.
# ---------------------------------------------------------------------------
scenario_purge_beads_alone_exit2() {
  local t="$WORKROOT/s5c"; mkdir -p "$t"

  local out rc
  out="$("$DOM" "$t" --purge-beads 2>&1)"; rc=$?

  check "exit 2" test "$rc" -eq 2
  check "error message mentions --purge-beads" bash -c 'printf "%s" "$1" | grep -qF -- "--purge-beads"' _ "$out"
}

# ---------------------------------------------------------------------------
# Scenario 6: --dry-run --uninstall prints a full plan and makes no writes.
# ---------------------------------------------------------------------------
scenario_dry_run_full_plan() {
  local t="$WORKROOT/s6"; mkdir -p "$t"
  git_init "$t"
  "$DOM" "$t" >/dev/null 2>&1
  check "install: implementer.md present (setup ran)" test -f "$t/$IMPL_REL"

  local hash_before out rc hash_after
  hash_before="$(treehash "$t")"
  out="$("$DOM" "$t" --uninstall --dry-run 2>&1)"; rc=$?
  hash_after="$(treehash "$t")"

  check "exit 0" test "$rc" -eq 0
  check "at least one [dry-run] line names a real target" bash -c '
    printf "%s" "$1" | grep -Eq "\[dry-run\].*implementer\.md"
  ' _ "$out"
  check "tree unchanged (recursive sha compare)" test "$hash_before" = "$hash_after"
}

# ---------------------------------------------------------------------------
# Scenario 7a: never-installed dir — no-op, exact phrasing, exit 0.
# ---------------------------------------------------------------------------
scenario_noop_never_installed() {
  local t="$WORKROOT/s7a"; mkdir -p "$t"
  git_init "$t"

  local out rc
  out="$("$DOM" "$t" --uninstall 2>&1)"; rc=$?

  check "exit 0" test "$rc" -eq 0
  check "exact 'no domestique install detected' phrasing" bash -c '
    printf "%s" "$1" | grep -qF "no domestique install detected"
  ' _ "$out"
}

# ---------------------------------------------------------------------------
# Scenario 7b: double uninstall — second run is a no-op, exit 0.
# ---------------------------------------------------------------------------
scenario_noop_double_uninstall() {
  local t="$WORKROOT/s7b"; mkdir -p "$t"
  git_init "$t"
  "$DOM" "$t" >/dev/null 2>&1

  local out1 rc1
  out1="$("$DOM" "$t" --uninstall 2>&1)"; rc1=$?
  check "first uninstall: exit 0" test "$rc1" -eq 0

  local out2 rc2
  out2="$("$DOM" "$t" --uninstall 2>&1)"; rc2=$?

  check "second uninstall: exit 0" test "$rc2" -eq 0
  check "second uninstall: no-op phrasing" bash -c '
    printf "%s" "$1" | grep -qF "no domestique install detected"
  ' _ "$out2"
}

# ---------------------------------------------------------------------------
# Scenario 8: mixed dir — plain install then guest install into the same
# dir; uninstall strips both policy files' managed blocks.
# ---------------------------------------------------------------------------
scenario_mixed_dir() {
  local t="$WORKROOT/s8"; mkdir -p "$t"
  git_init "$t"
  "$DOM" "$t" >/dev/null 2>&1
  "$DOM" "$t" --guest >/dev/null 2>&1

  check "install: CLAUDE.md has managed block (setup ran)" grep -qF "$MARKER_BEGIN" "$t/CLAUDE.md"
  check "install: CLAUDE.local.md has managed block (setup ran)" grep -qF "$MARKER_BEGIN" "$t/CLAUDE.local.md"

  local out rc
  out="$("$DOM" "$t" --uninstall 2>&1)"; rc=$?

  check "exit 0" test "$rc" -eq 0
  # Both policy files here consist ONLY of the managed block (no other
  # content was ever added), so a correct strip leaves nothing behind and the
  # whole file is removed by do_uninstall's "empty after stripping" path —
  # deterministically, not merely "possibly". Assert the file is gone
  # outright rather than a removed-OR-block-free disjunction (which would
  # also pass if a bug wrongly deleted a file that should have survived).
  check "CLAUDE.md removed (block was its only content)" test ! -e "$t/CLAUDE.md"
  check "CLAUDE.local.md removed (block was its only content)" test ! -e "$t/CLAUDE.local.md"
  check "snapshot dir gone" test ! -e "$t/$SNAPSHOT_REL"
  check "exclude block gone" bash -c '! grep -qF "# BEGIN domestique (managed)" "$1"' _ "$t/.git/info/exclude"
}

# ---------------------------------------------------------------------------
# Scenario 9: --uninstall combined with --guest / --no-guest / --with-beads
# is a usage error, exit 2.
# ---------------------------------------------------------------------------
# NOTE ON BRIEF DEVIATION: the brief asks each bad-combo error to "mention
# the offending flag". Empirically (domestique.sh:319-325) all three combos
# share ONE generic error line ("--uninstall is only combinable with
# --dry-run, --force, --purge-beads, and TARGET_DIR.") that never names
# --guest/--no-guest/--with-beads specifically; usage() is then dumped to
# stderr afterward and happens to list every flag regardless of which one was
# actually invalid, so a naive `grep -qF -- "--guest"` on the combined output
# would pass identically for the --with-beads case too — it asserts nothing.
# That per-flag distinction is not satisfiable against the current product
# behavior, so instead we assert the specific generic error line verbatim
# (proving usage() was in fact triggered and it's THIS error, not some other
# exit-2 path) plus evidence the run aborted before doing any install/
# uninstall work at all.
scenario_bad_combo_guest() {
  local t="$WORKROOT/s9a"; mkdir -p "$t"
  local out rc
  out="$("$DOM" "$t" --uninstall --guest 2>&1)"; rc=$?
  check "exit 2" test "$rc" -eq 2
  check "exact combinability error line" bash -c 'printf "%s" "$1" | grep -qF "Error: --uninstall is only combinable with"' _ "$out"
  check "aborted before touching the target: no .claude/ created" test ! -e "$t/.claude"
  check "aborted before touching the target: no CLAUDE.md created" test ! -e "$t/CLAUDE.md"
}

scenario_bad_combo_no_guest() {
  local t="$WORKROOT/s9b"; mkdir -p "$t"
  local out rc
  out="$("$DOM" "$t" --uninstall --no-guest 2>&1)"; rc=$?
  check "exit 2" test "$rc" -eq 2
  check "exact combinability error line" bash -c 'printf "%s" "$1" | grep -qF "Error: --uninstall is only combinable with"' _ "$out"
  check "aborted before touching the target: no .claude/ created" test ! -e "$t/.claude"
  check "aborted before touching the target: no CLAUDE.md created" test ! -e "$t/CLAUDE.md"
}

scenario_bad_combo_with_beads() {
  local t="$WORKROOT/s9c"; mkdir -p "$t"
  local out rc
  out="$("$DOM" "$t" --uninstall --with-beads 2>&1)"; rc=$?
  check "exit 2" test "$rc" -eq 2
  check "exact combinability error line" bash -c 'printf "%s" "$1" | grep -qF "Error: --uninstall is only combinable with"' _ "$out"
  check "aborted before touching the target: no .claude/ created" test ! -e "$t/.claude"
  check "aborted before touching the target: no CLAUDE.md created" test ! -e "$t/CLAUDE.md"
}

# ---------------------------------------------------------------------------
# Scenario 10: marker-corruption refusals — a structurally unsound managed
# block in CLAUDE.md must be refused (rc 3), left byte-untouched, named under
# Conflicted, while sibling components are still removed.
# ---------------------------------------------------------------------------
# run_marker_refusal_scenario <dir> <corrupt_fn> <discriminator>
# <discriminator> is a literal substring unique to the SPECIFIC marker
# problem being exercised (distinct wording per case — see markers_sane()'s
# case-specific stderr lines and Conflicted-bucket text in domestique.sh's
# do_uninstall). Asserting it (not just "Conflicted names CLAUDE.md") is what
# stops one corruption variant's test from silently passing when the
# dispatch table is mutated to a DIFFERENT corruption function — the half/
# half and dup/dup pairs would otherwise be indistinguishable.
run_marker_refusal_scenario() {
  local t="$1" corrupt_fn="$2" discriminator="$3"
  git_init "$t"
  "$DOM" "$t" >/dev/null 2>&1
  check "install: implementer.md present (setup ran)" test -f "$t/$IMPL_REL"

  local sha_pre; sha_pre="$(filehash "$t/CLAUDE.md")"
  "$corrupt_fn" "$t/CLAUDE.md"
  local sha_corrupt; sha_corrupt="$(filehash "$t/CLAUDE.md")"
  check "corruption actually applied (setup ran)" bash -c '[ "$1" != "$2" ]' _ "$sha_pre" "$sha_corrupt"

  local out rc
  out="$("$DOM" "$t" --uninstall 2>&1)"; rc=$?
  local sha_post; sha_post="$(filehash "$t/CLAUDE.md")"

  check "exit 3" test "$rc" -eq 3
  check "CLAUDE.md byte-untouched by the refusal" test "$sha_corrupt" = "$sha_post"
  check "Conflicted bucket names CLAUDE.md" bash -c '
    printf "%s" "$1" | grep -A6 "^  Conflicted:$" | grep -q "CLAUDE.md"
  ' _ "$out"
  check "run output names this specific marker problem" bash -c '
    printf "%s" "$1" | grep -qF -- "$2"
  ' _ "$out" "$discriminator"
  check "sibling component (implementer.md) still removed" test ! -e "$t/$IMPL_REL"
  check "snapshot dir still removed despite the conflict" test ! -e "$t/$SNAPSHOT_REL"
}

scenario_marker_half_begin_only() {
  local t="$WORKROOT/s10-half-begin"; mkdir -p "$t"
  run_marker_refusal_scenario "$t" corrupt_remove_end \
    "has a '$MARKER_BEGIN' marker but no matching '$MARKER_END'"
}

scenario_marker_half_end_only() {
  local t="$WORKROOT/s10-half-end"; mkdir -p "$t"
  run_marker_refusal_scenario "$t" corrupt_remove_begin \
    "has a '$MARKER_END' marker but no matching '$MARKER_BEGIN'"
}

scenario_marker_dup_begin() {
  local t="$WORKROOT/s10-dup-begin"; mkdir -p "$t"
  run_marker_refusal_scenario "$t" corrupt_dup_begin "duplicate BEGIN marker"
}

scenario_marker_dup_end() {
  local t="$WORKROOT/s10-dup-end"; mkdir -p "$t"
  run_marker_refusal_scenario "$t" corrupt_dup_end "duplicate END marker"
}

scenario_marker_inverted() {
  local t="$WORKROOT/s10-inverted"; mkdir -p "$t"
  run_marker_refusal_scenario "$t" corrupt_invert "markers in wrong order (END before BEGIN)"
}

# ---------------------------------------------------------------------------
# Scenario 10 (guest variant): a corrupted CLAUDE.local.md is refused, but the
# exclude-block strip proceeds independently — CLAUDE.local.md ends up newly
# untracked (its exclude entry is gone) and the run's summary names it.
# ---------------------------------------------------------------------------
scenario_marker_guest_variant() {
  local t="$WORKROOT/s10-guest"; mkdir -p "$t"
  git_init "$t"
  "$DOM" "$t" --guest >/dev/null 2>&1
  check "install: CLAUDE.local.md present (setup ran)" test -f "$t/CLAUDE.local.md"

  local sha_pre; sha_pre="$(filehash "$t/CLAUDE.local.md")"
  corrupt_remove_end "$t/CLAUDE.local.md"
  local sha_corrupt; sha_corrupt="$(filehash "$t/CLAUDE.local.md")"
  check "corruption actually applied (setup ran)" bash -c '[ "$1" != "$2" ]' _ "$sha_pre" "$sha_corrupt"

  local out rc
  out="$("$DOM" "$t" --uninstall 2>&1)"; rc=$?
  local sha_post; sha_post="$(filehash "$t/CLAUDE.local.md")"

  check "exit 3" test "$rc" -eq 3
  check "CLAUDE.local.md byte-untouched by the refusal" test "$sha_corrupt" = "$sha_post"
  check "Conflicted bucket names CLAUDE.local.md" bash -c '
    printf "%s" "$1" | grep -A6 "^  Conflicted:$" | grep -q "CLAUDE.local.md"
  ' _ "$out"
  check "run output names this specific marker problem (BEGIN-only)" bash -c '
    printf "%s" "$1" | grep -qF -- "$2"
  ' _ "$out" "has a '$MARKER_BEGIN' marker but no matching '$MARKER_END'"
  check "exclude block strip proceeded despite the policy-file conflict" bash -c '
    ! grep -qF "# BEGIN domestique (managed)" "$1"
  ' _ "$t/.git/info/exclude"
  check "CLAUDE.local.md now shows as untracked in git status" bash -c '
    git -C "$1" status --porcelain | grep -qE "^\?\? CLAUDE\.local\.md$"
  ' _ "$t"
}

# ---------------------------------------------------------------------------
# Scenario 11: guard/strip consistency — a BEGIN marker line with a trailing
# space must be refused (treated as half-marked, END-only), not silently
# accepted by the guard and then mishandled by the strip.
# ---------------------------------------------------------------------------
scenario_guard_trailing_space() {
  local t="$WORKROOT/s11"; mkdir -p "$t"
  # The trailing-space BEGIN line fails markers_sane's exact whole-line match
  # (bc=0), while the real END marker is untouched (ec=1) — i.e. this must be
  # classified and reported as the SAME "END-only, no matching BEGIN" case as
  # corrupt_remove_begin, proving the guard treats the doctored line as
  # absent rather than accepting it loosely.
  run_marker_refusal_scenario "$t" corrupt_trailing_space_begin \
    "has a '$MARKER_END' marker but no matching '$MARKER_BEGIN'"
}

# ---------------------------------------------------------------------------
# Scenario 12: prunes only EMPTY dirs — a dir left with user content must
# never be pruned/deleted, while a dir left genuinely empty by the removal of
# managed files must be. The highest-consequence safety property in
# uninstall's contract, so this pins both halves: .claude/ and
# .claude/agents/ survive (each holds a user file after the managed files are
# removed) and are untouched byte-for-byte, while .claude/commands/ (which
# held only the two managed command files) is gone.
# ---------------------------------------------------------------------------
scenario_prune_only_empty_dirs() {
  local t="$WORKROOT/s12"; mkdir -p "$t"
  git_init "$t"
  "$DOM" "$t" >/dev/null 2>&1
  check "install: .claude/commands present (setup ran)" test -d "$t/.claude/commands"

  printf '{"user":"settings"}\n' > "$t/.claude/settings.local.json"
  printf 'user agent notes\n' > "$t/.claude/agents/my-notes.md"
  local sha_settings_pre sha_notes_pre
  sha_settings_pre="$(filehash "$t/.claude/settings.local.json")"
  sha_notes_pre="$(filehash "$t/.claude/agents/my-notes.md")"

  local out rc
  out="$("$DOM" "$t" --uninstall 2>&1)"; rc=$?

  local sha_settings_post sha_notes_post
  sha_settings_post="$(filehash "$t/.claude/settings.local.json")"
  sha_notes_post="$(filehash "$t/.claude/agents/my-notes.md")"

  check "exit 0" test "$rc" -eq 0
  check ".claude/ NOT pruned (user file present)" test -d "$t/.claude"
  check ".claude/agents/ NOT pruned (user file present)" test -d "$t/.claude/agents"
  check ".claude/commands/ pruned (left empty)" test ! -e "$t/.claude/commands"
  check "settings.local.json untouched (sha)" test "$sha_settings_pre" = "$sha_settings_post"
  check "my-notes.md untouched (sha)" test "$sha_notes_pre" = "$sha_notes_post"
}

# ---------------------------------------------------------------------------
echo "domestique uninstall test harness"
echo "repo: $REPO_DIR"
echo

run_scenario "plain round-trip"                                 scenario_plain_roundtrip
run_scenario "guest round-trip"                                 scenario_guest_roundtrip
run_scenario "modified .claude/ file kept (.uninstalled.<TS>)"  scenario_modified_file_kept
run_scenario "modified .claude/ file --force removed"           scenario_modified_file_force_removed
run_scenario "policy file user-modified: backup + outside text" scenario_policy_modified_backup
run_scenario ".beads/ preserved by default + note"               scenario_beads_preserved
run_scenario "--purge-beads removes .beads/"                     scenario_beads_purged
run_scenario "--purge-beads alone is a usage error (exit 2)"     scenario_purge_beads_alone_exit2
run_scenario "--dry-run --uninstall: full plan, no writes"       scenario_dry_run_full_plan
run_scenario "no-op: never-installed dir"                        scenario_noop_never_installed
run_scenario "no-op: double uninstall"                           scenario_noop_double_uninstall
run_scenario "mixed dir: plain + guest both stripped"            scenario_mixed_dir
run_scenario "--uninstall --guest is a usage error (exit 2)"     scenario_bad_combo_guest
run_scenario "--uninstall --no-guest is a usage error (exit 2)"  scenario_bad_combo_no_guest
run_scenario "--uninstall --with-beads is a usage error (exit 2)" scenario_bad_combo_with_beads
run_scenario "marker refusal: half-marked BEGIN-only"            scenario_marker_half_begin_only
run_scenario "marker refusal: half-marked END-only"              scenario_marker_half_end_only
run_scenario "marker refusal: duplicate BEGIN"                   scenario_marker_dup_begin
run_scenario "marker refusal: duplicate END"                     scenario_marker_dup_end
run_scenario "marker refusal: inverted order"                    scenario_marker_inverted
run_scenario "marker refusal: guest variant (CLAUDE.local.md)"   scenario_marker_guest_variant
run_scenario "guard/strip consistency: BEGIN with trailing space" scenario_guard_trailing_space
run_scenario "prunes only empty dirs"                            scenario_prune_only_empty_dirs

echo
TOTAL=$((PASS_COUNT + FAIL_COUNT))
echo "$PASS_COUNT/$TOTAL passed"

if [ "$FAIL_COUNT" -gt 0 ]; then
  exit 1
fi
exit 0
