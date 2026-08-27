#!/usr/bin/env bash
# test/codex.sh — self-contained regression harness for domestique.sh's
# native Codex projection. Each scenario runs in an isolated mktemp sandbox,
# reports PASS/FAIL, and the harness exits non-zero if any scenario failed.
# No external test framework and no network access are required.
#
# Run: bash test/codex.sh
#
# Intentionally does NOT use `set -e`: scenarios exercise failure-sensitive
# installer paths and should collect every failed assertion before exiting.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DOM="$REPO_DIR/domestique.sh"
UPDATER="$REPO_DIR/update.sh"

if [ ! -f "$DOM" ]; then
  echo "FATAL: cannot find domestique.sh at $DOM" >&2
  exit 1
fi

WORKROOT="$(mktemp -d)"
cleanup() { rm -rf "$WORKROOT"; }
trap cleanup EXIT

PASS_COUNT=0
FAIL_COUNT=0

# check "<description>" <command...>
# Records a scenario-scoped failure without aborting the rest of the scenario.
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

# filehash <file> — loud, stable hash used for byte-preservation checks.
filehash() {
  if [ ! -e "$1" ]; then
    printf 'MISSING:%s' "$1"
    return 0
  fi
  shasum -a 256 "$1" 2>/dev/null | awk '{print $1}'
}

# treehash <dir> — stable content+layout fingerprint, including hidden files.
treehash() {
  local dir="$1"
  (
    cd "$dir" || exit 1
    find . -type f -print | LC_ALL=C sort | while IFS= read -r file; do
      printf '%s  ' "$file"
      shasum -a 256 "$file" | awk '{print $1}'
    done
  ) | shasum -a 256 | awk '{print $1}'
}

# git_init <dir> — repository-local identity only.
git_init() {
  local d="$1"
  git -C "$d" init -q
  git -C "$d" config user.email "domestique-test@example.com"
  git -C "$d" config user.name "domestique test"
}

assert_skill_name() {
  local file="$1" expected="$2"
  awk -v expected="$expected" '
    NR == 1 && $0 != "---" { exit 1 }
    NR > 1 && $0 == "---" { exit found ? 0 : 1 }
    NR > 1 && $1 == "name:" && $2 == expected { found = 1 }
    END { if (!found) exit 1 }
  ' "$file"
}

# replace_exact_line <source> <destination> <old> <new>
# Makes a one-line synthetic emitter/user edit without relying on GNU/BSD
# variants of sed -i. Fails if the expected source line is not present.
replace_exact_line() {
  local source="$1" destination="$2" old="$3" new="$4"
  awk -v old="$old" -v new="$new" '
    $0 == old { print new; found=1; next }
    { print }
    END { if (!found) exit 1 }
  ' "$source" > "$destination"
}

# make_fake_bd <bin-dir>
# The fixture advertises every safe init flag during the installer's help
# probe, logs only commands that would mutate provider/beads state, and creates
# the .beads directory expected from a successful init.
make_fake_bd() {
  local bindir="$1"
  mkdir -p "$bindir"
  cat > "$bindir/bd" <<'FAKE_BD'
#!/bin/sh
if [ "${1:-}" = "init" ] && [ "${2:-}" = "--help" ]; then
  printf '%s\n' 'usage: bd init [--stealth] [--skip-agents] [--skip-hooks] [--non-interactive]'
  exit 0
fi
printf '%s\n' "$*" >> "$FAKE_BD_LOG"
if [ "${1:-}" = "init" ]; then
  mkdir -p .beads
fi
exit 0
FAKE_BD
  chmod +x "$bindir/bd"
}

IMPL_REL=".codex/agents/implementer.toml"
REVIEWER_REL=".codex/agents/reviewer.toml"
BASE_SKILL_REL=".agents/skills/domestique/SKILL.md"
DECOMPOSE_SKILL_REL=".agents/skills/domestique-decompose/SKILL.md"
GOAL_SKILL_REL=".agents/skills/domestique-goal/SKILL.md"
GOAL_META_REL=".agents/skills/domestique-goal/agents/openai.yaml"

# ---------------------------------------------------------------------------
# Scenario 1: a fresh normal Codex install uses only native Codex surfaces.
# ---------------------------------------------------------------------------
scenario_fresh_normal_codex() {
  local t="$WORKROOT/s1"; mkdir -p "$t"
  local out rc
  out="$("$DOM" "$t" --platform codex 2>&1)"; rc=$?

  check "exit 0" test "$rc" -eq 0
  check "AGENTS.md created" test -f "$t/AGENTS.md"
  check "AGENTS.md has managed block" grep -qF "BEGIN domestique (managed)" "$t/AGENTS.md"
  check "implementer TOML created" test -f "$t/$IMPL_REL"
  check "reviewer TOML created" test -f "$t/$REVIEWER_REL"
  check "base skill created" test -f "$t/$BASE_SKILL_REL"
  check "decompose skill created" test -f "$t/$DECOMPOSE_SKILL_REL"
  check "decompose skill has grilling pre-step" grep -q 'grilling' "$t/$DECOMPOSE_SKILL_REL"
  check "decompose skill has ponytail-audit post-step" grep -q 'ponytail-audit' "$t/$DECOMPOSE_SKILL_REL"
  check "decompose skill has grilling fallback notice" grep -q 'No grilling skill installed' "$t/$DECOMPOSE_SKILL_REL"
  check "decompose skill has ponytail-audit fallback notice" grep -q 'No ponytail-audit skill found' "$t/$DECOMPOSE_SKILL_REL"
  check "goal skill created" test -f "$t/$GOAL_SKILL_REL"
  check "goal metadata created" test -f "$t/$GOAL_META_REL"
  check "no CLAUDE.md" test ! -e "$t/CLAUDE.md"
  check "no CLAUDE.local.md" test ! -e "$t/CLAUDE.local.md"
  check "no .claude directory" test ! -e "$t/.claude"
  check "summary identifies Codex" bash -c 'printf "%s" "$1" | grep -qi "codex"' _ "$out"
}

# ---------------------------------------------------------------------------
# Scenario 2: emitted agent TOML pins the approved models/efforts and carries
# Codex's required custom-agent fields without a read-only reviewer sandbox.
# ---------------------------------------------------------------------------
scenario_agent_toml() {
  local t="$WORKROOT/s2"; mkdir -p "$t"
  local rc
  "$DOM" "$t" --platform codex >/dev/null 2>&1; rc=$?

  check "install exits 0" test "$rc" -eq 0

  check "implementer name field" grep -Eq '^name[[:space:]]*=[[:space:]]*"implementer"' "$t/$IMPL_REL"
  check "implementer description field" grep -Eq '^description[[:space:]]*=' "$t/$IMPL_REL"
  check "implementer developer_instructions field" grep -Eq '^developer_instructions[[:space:]]*=' "$t/$IMPL_REL"
  check "implementer model terra" grep -Eq '^model[[:space:]]*=[[:space:]]*"gpt-5\.6-terra"' "$t/$IMPL_REL"
  check "implementer effort medium" grep -Eq '^model_reasoning_effort[[:space:]]*=[[:space:]]*"medium"' "$t/$IMPL_REL"

  check "reviewer name field" grep -Eq '^name[[:space:]]*=[[:space:]]*"reviewer"' "$t/$REVIEWER_REL"
  check "reviewer description field" grep -Eq '^description[[:space:]]*=' "$t/$REVIEWER_REL"
  check "reviewer developer_instructions field" grep -Eq '^developer_instructions[[:space:]]*=' "$t/$REVIEWER_REL"
  check "reviewer model gpt-5.6" grep -Eq '^model[[:space:]]*=[[:space:]]*"gpt-5\.6"' "$t/$REVIEWER_REL"
  check "reviewer effort high" grep -Eq '^model_reasoning_effort[[:space:]]*=[[:space:]]*"high"' "$t/$REVIEWER_REL"
  check "reviewer is not forced read-only" bash -c '! grep -Eq '\''^sandbox_mode[[:space:]]*=[[:space:]]*"read-only"'\'' "$1"' _ "$t/$REVIEWER_REL"
  check "reviewer forbids source edits" grep -Eqi 'do not (edit|modify)|never (edit|modify)|must not (edit|modify)' "$t/$REVIEWER_REL"
  check "orchestrator policy has pre/post diff guard" bash -c '
    grep -Eqi "fingerprint|before and after|pre.review|post.review|diff guard" "$1" "$2"
  ' _ "$t/AGENTS.md" "$t/$BASE_SKILL_REL"

  if command -v python3 >/dev/null 2>&1 && python3 -c 'import tomllib' >/dev/null 2>&1; then
    check "implementer is valid TOML" python3 -c 'import pathlib,tomllib,sys; tomllib.loads(pathlib.Path(sys.argv[1]).read_text())' "$t/$IMPL_REL"
    check "reviewer is valid TOML" python3 -c 'import pathlib,tomllib,sys; tomllib.loads(pathlib.Path(sys.argv[1]).read_text())' "$t/$REVIEWER_REL"
  fi
}

# ---------------------------------------------------------------------------
# Scenario 3: skills are namespaced and unattended goal invocation is
# explicitly disabled for implicit matching through agents/openai.yaml.
# ---------------------------------------------------------------------------
scenario_skill_metadata() {
  local t="$WORKROOT/s3"; mkdir -p "$t"
  local rc
  "$DOM" "$t" --platform codex >/dev/null 2>&1; rc=$?

  check "install exits 0" test "$rc" -eq 0

  check "base skill namespaced" assert_skill_name "$t/$BASE_SKILL_REL" "domestique"
  check "decompose skill namespaced" assert_skill_name "$t/$DECOMPOSE_SKILL_REL" "domestique-decompose"
  check "goal skill namespaced" assert_skill_name "$t/$GOAL_SKILL_REL" "domestique-goal"
  check "base skill has description" grep -Eq '^description:[[:space:]]*[^[:space:]]' "$t/$BASE_SKILL_REL"
  check "decompose skill has description" grep -Eq '^description:[[:space:]]*[^[:space:]]' "$t/$DECOMPOSE_SKILL_REL"
  check "goal skill has description" grep -Eq '^description:[[:space:]]*[^[:space:]]' "$t/$GOAL_SKILL_REL"
  check "goal is explicit-only" grep -Eq '^[[:space:]]*allow_implicit_invocation:[[:space:]]*false[[:space:]]*$' "$t/$GOAL_META_REL"
}

# ---------------------------------------------------------------------------
# Scenario 4: guest Codex is skills-only. It neither creates nor modifies a
# root instruction file and it does not hide unrelated .agents/.codex files.
# ---------------------------------------------------------------------------
scenario_guest_skills_only_isolation() {
  local t="$WORKROOT/s4"; mkdir -p "$t"
  git_init "$t"
  printf '# Host root guidance\n' > "$t/AGENTS.md"
  printf '# Host active override\n' > "$t/AGENTS.override.md"
  printf 'echo host\n' > "$t/main.sh"
  git -C "$t" add AGENTS.md AGENTS.override.md main.sh
  git -C "$t" commit -q -m "initial"

  mkdir -p "$t/.agents" "$t/.codex"
  printf 'keep me visible\n' > "$t/.agents/host-note.txt"
  printf 'keep me visible too\n' > "$t/.codex/host-note.toml"

  local agents_before override_before status_before out rc status_after
  agents_before="$(filehash "$t/AGENTS.md")"
  override_before="$(filehash "$t/AGENTS.override.md")"
  status_before="$(git -C "$t" status --porcelain --untracked-files=all)"
  out="$("$DOM" "$t" --platform codex --guest 2>&1)"; rc=$?
  status_after="$(git -C "$t" status --porcelain --untracked-files=all)"

  check "exit 0" test "$rc" -eq 0
  check "AGENTS.md byte-identical" test "$agents_before" = "$(filehash "$t/AGENTS.md")"
  check "AGENTS.override.md byte-identical" test "$override_before" = "$(filehash "$t/AGENTS.override.md")"
  check "root AGENTS.md has no managed block" bash -c '! grep -qF "BEGIN domestique (managed)" "$1"' _ "$t/AGENTS.md"
  check "root override has no managed block" bash -c '! grep -qF "BEGIN domestique (managed)" "$1"' _ "$t/AGENTS.override.md"
  check "guest install preserves exact visible status" test "$status_before" = "$status_after"
  check "guest implementer installed" test -f "$t/$IMPL_REL"
  check "guest reviewer installed" test -f "$t/$REVIEWER_REL"
  check "guest base skill installed" test -f "$t/$BASE_SKILL_REL"
  check "guest decompose skill installed" test -f "$t/$DECOMPOSE_SKILL_REL"
  check "guest goal skill installed" test -f "$t/$GOAL_SKILL_REL"
  check "guest goal metadata installed" test -f "$t/$GOAL_META_REL"
  check "output explains skills-only mode" bash -c 'printf "%s" "$1" | grep -qi "skills-only"' _ "$out"
  check "output names bootstrap invocation" bash -c 'printf "%s" "$1" | grep -qF '\''$domestique'\''' _ "$out"
  check "exclude does not hide all .agents" bash -c '! grep -qxF ".agents/" "$1"' _ "$t/.git/info/exclude"
  check "exclude does not hide all .codex" bash -c '! grep -qxF ".codex/" "$1"' _ "$t/.git/info/exclude"
}

# ---------------------------------------------------------------------------
# Scenario 5: --platform both emits both projections without either replacing
# the other.
# ---------------------------------------------------------------------------
scenario_both_mode() {
  local t="$WORKROOT/s5"; mkdir -p "$t"
  local out rc
  out="$("$DOM" "$t" --platform both 2>&1)"; rc=$?

  check "exit 0" test "$rc" -eq 0
  check "Claude policy created" test -f "$t/CLAUDE.md"
  check "Claude implementer created" test -f "$t/.claude/agents/implementer.md"
  check "Claude reviewer created" test -f "$t/.claude/agents/reviewer.md"
  check "Codex policy created" test -f "$t/AGENTS.md"
  check "Codex implementer created" test -f "$t/$IMPL_REL"
  check "Codex reviewer created" test -f "$t/$REVIEWER_REL"
  check "Codex base skill created" test -f "$t/$BASE_SKILL_REL"
  check "Codex decompose skill created" test -f "$t/$DECOMPOSE_SKILL_REL"
  check "Codex goal skill created" test -f "$t/$GOAL_SKILL_REL"
  check "summary identifies both" bash -c 'printf "%s" "$1" | grep -Eqi "both|claude.*codex|codex.*claude"' _ "$out"
}

# ---------------------------------------------------------------------------
# Scenario 6: repeated install is byte-identical, while a fresh dry run writes
# nothing at all.
# ---------------------------------------------------------------------------
scenario_idempotency_and_dry_run() {
  local t="$WORKROOT/s6-idem"; mkdir -p "$t"
  "$DOM" "$t" --platform codex >/dev/null 2>&1
  local before after out rc
  before="$(treehash "$t")"
  out="$("$DOM" "$t" --platform codex 2>&1)"; rc=$?
  after="$(treehash "$t")"

  check "second install exits 0" test "$rc" -eq 0
  check "second install byte-identical" test "$before" = "$after"
  check "second install reports skipped" bash -c 'printf "%s" "$1" | grep -q "Skipped"' _ "$out"

  local d="$WORKROOT/s6-dry"; mkdir -p "$d"
  before="$(treehash "$d")"
  out="$("$DOM" "$d" --platform codex --dry-run 2>&1)"; rc=$?
  after="$(treehash "$d")"

  check "dry run exits 0" test "$rc" -eq 0
  check "dry run writes nothing" test "$before" = "$after"
  check "dry run creates no AGENTS.md" test ! -e "$d/AGENTS.md"
  check "dry run creates no .codex" test ! -e "$d/.codex"
  check "dry run creates no .agents" test ! -e "$d/.agents"
  check "dry run reports Codex plan" bash -c 'printf "%s" "$1" | grep -qi "codex"' _ "$out"
}

# ---------------------------------------------------------------------------
# Scenario 7: after an explicit Codex install, a selector-less rerun restores
# a deleted Codex-managed file and does not fall back to the Claude default.
# ---------------------------------------------------------------------------
scenario_persisted_platform_selection() {
  local t="$WORKROOT/s7"; mkdir -p "$t"
  "$DOM" "$t" --platform codex >/dev/null 2>&1
  rm -f "$t/$REVIEWER_REL"

  local out rc
  out="$("$DOM" "$t" 2>&1)"; rc=$?

  check "bare rerun exits 0" test "$rc" -eq 0
  check "bare rerun restores Codex reviewer" test -f "$t/$REVIEWER_REL"
  check "bare rerun does not create CLAUDE.md" test ! -e "$t/CLAUDE.md"
  check "bare rerun does not create .claude" test ! -e "$t/.claude"
  check "bare rerun reports persisted Codex" bash -c 'printf "%s" "$1" | grep -qi "codex"' _ "$out"
}

# ---------------------------------------------------------------------------
# Scenario 8: Codex-only output contains no Claude projection terminology,
# model names, paths, or deprecated custom-prompt instructions.
# ---------------------------------------------------------------------------
scenario_no_claude_leakage() {
  local t="$WORKROOT/s8"; mkdir -p "$t"
  local rc
  "$DOM" "$t" --platform codex >/dev/null 2>&1; rc=$?

  check "install exits 0" test "$rc" -eq 0
  check "Codex policy exists" test -f "$t/AGENTS.md"
  check "Codex agents exist" bash -c 'test -f "$1" && test -f "$2"' _ "$t/$IMPL_REL" "$t/$REVIEWER_REL"
  check "no Claude artifacts" test ! -e "$t/CLAUDE.md"
  check "no Claude state" test ! -e "$t/.claude"
  check "no Claude terminology in Codex output" bash -c '
    ! grep -R -E -i "Claude|Sonnet|Opus|CLAUDE\\.md|\\.claude/|~/\\.codex/prompts" \
      "$1/AGENTS.md" "$1/.codex" "$1/.agents/skills/domestique" \
      "$1/.agents/skills/domestique-decompose" "$1/.agents/skills/domestique-goal"
  ' _ "$t"
}

# ---------------------------------------------------------------------------
# Scenario 9: unchanged emitter output never overwrites a local Codex edit.
# When both the user and a later domestique emitter edit the same line, the
# upgrade must preserve the live file and merge base, emit conflict artifacts,
# and return the documented conflict status.
# ---------------------------------------------------------------------------
scenario_codex_local_edit_and_upgrade_conflict() {
  local t="$WORKROOT/s9"; mkdir -p "$t"
  local out rc
  "$DOM" "$t" --platform codex >/dev/null 2>&1; rc=$?
  check "initial install exits 0" test "$rc" -eq 0

  printf '\n# USER REVIEWER NOTE\n' >> "$t/$REVIEWER_REL"
  "$DOM" "$t" --platform codex >/dev/null 2>&1; rc=$?
  check "rerun with local edit exits 0" test "$rc" -eq 0
  check "local reviewer edit survives rerun" grep -qxF '# USER REVIEWER NOTE' "$t/$REVIEWER_REL"

  local original local_line upstream_line edit_tmp v2
  original='description = "Executes one bounded beads task, validates it, and returns a terse handoff without closing the bead."'
  local_line='description = "LOCAL: executes one bounded beads task under host-specific rules."'
  upstream_line='description = "UPSTREAM V2: executes one bounded beads task with upgraded orchestration rules."'
  edit_tmp="$WORKROOT/s9-live-edit"
  check "live conflict edit anchor found" replace_exact_line "$t/$IMPL_REL" "$edit_tmp" "$original" "$local_line"
  if [ -f "$edit_tmp" ]; then cp "$edit_tmp" "$t/$IMPL_REL"; fi

  v2="$WORKROOT/domestique-v2.sh"
  check "synthetic V2 emitter anchor found" replace_exact_line "$DOM" "$v2" "$original" "$upstream_line"
  chmod +x "$v2" 2>/dev/null || true

  local live_before base base_before
  base="$t/.codex/.domestique/base/$IMPL_REL"
  live_before="$(filehash "$t/$IMPL_REL")"
  base_before="$(filehash "$base")"
  out="$("$v2" "$t" --platform codex 2>&1)"; rc=$?

  check "conflicting upgrade exits 3" test "$rc" -eq 3
  check "conflicting upgrade preserves live file" test "$live_before" = "$(filehash "$t/$IMPL_REL")"
  check "conflicting upgrade preserves merge base" test "$base_before" = "$(filehash "$base")"
  check "conflict output identifies implementer" bash -c 'printf "%s" "$1" | grep -q "implementer.toml"' _ "$out"
  check "conflict output reports conflict" bash -c 'printf "%s" "$1" | grep -qi "conflict"' _ "$out"
  check "conflict .new emitted" test -f "$t/$IMPL_REL.new"
  check "conflict .new has ours marker" grep -q '^<<<<<<< ' "$t/$IMPL_REL.new"
  check "conflict .new has base marker" grep -q '^||||||| ' "$t/$IMPL_REL.new"
  check "conflict .new has separator" grep -q '^=======$' "$t/$IMPL_REL.new"
  check "conflict .new has theirs marker" grep -q '^>>>>>>> ' "$t/$IMPL_REL.new"
  check "conflict .new retains local side" grep -qF "$local_line" "$t/$IMPL_REL.new"
  check "conflict .new includes upstream side" grep -qF "$upstream_line" "$t/$IMPL_REL.new"
  check "conflict backup emitted" bash -c 'compgen -G "$1.bak.*" >/dev/null' _ "$t/$IMPL_REL"
}

# ---------------------------------------------------------------------------
# Scenario 10: a pristine normal Codex install/uninstall is an exact visible
# round trip. A Codex-scoped uninstall from `both` removes only Codex and makes
# Claude's persisted provider set authoritative for selector-less reruns.
# ---------------------------------------------------------------------------
scenario_codex_uninstall_roundtrip_and_scope() {
  local t="$WORKROOT/s10-full"; mkdir -p "$t"
  git_init "$t"
  printf 'host\n' > "$t/main.txt"
  git -C "$t" add main.txt
  git -C "$t" commit -q -m initial
  local before after rc
  before="$(git -C "$t" status --porcelain --untracked-files=all)"
  "$DOM" "$t" --platform codex >/dev/null 2>&1
  "$DOM" "$t" --uninstall >/dev/null 2>&1; rc=$?
  after="$(git -C "$t" status --porcelain --untracked-files=all)"

  check "full uninstall exits 0" test "$rc" -eq 0
  check "Codex install/uninstall restores clean status" test "$before" = "$after"
  check "full uninstall removes AGENTS.md" test ! -e "$t/AGENTS.md"
  check "full uninstall removes Codex state" test ! -e "$t/.codex"
  check "full uninstall removes namespaced skills" test ! -e "$t/.agents"

  local b="$WORKROOT/s10-scoped"; mkdir -p "$b"
  "$DOM" "$b" --platform both >/dev/null 2>&1
  "$DOM" "$b" --uninstall --platform codex >/dev/null 2>&1; rc=$?

  check "Codex-scoped uninstall exits 0" test "$rc" -eq 0
  check "scoped uninstall preserves CLAUDE.md" test -f "$b/CLAUDE.md"
  check "scoped uninstall preserves Claude implementer" test -f "$b/.claude/agents/implementer.md"
  check "scoped uninstall preserves Claude reviewer" test -f "$b/.claude/agents/reviewer.md"
  check "scoped uninstall preserves Claude commands" bash -c 'test -f "$1" && test -f "$2"' _ "$b/.claude/commands/decompose.md" "$b/.claude/commands/goal.md"
  check "scoped uninstall persists platforms=claude" bash -c 'test "$(cat "$1")" = claude' _ "$b/.claude/.domestique/platforms"
  check "scoped uninstall removes Codex policy" test ! -e "$b/AGENTS.md"
  check "scoped uninstall removes Codex state" test ! -e "$b/.codex"
  check "scoped uninstall removes Codex skills" test ! -e "$b/.agents"
}

# ---------------------------------------------------------------------------
# Scenario 11: removing Codex from a both-provider guest install must regenerate
# the shared exclude block as the exact Claude-only projection. The surviving
# guest artifacts remain invisible and the host worktree remains clean.
# ---------------------------------------------------------------------------
scenario_guest_scoped_uninstall_exact_excludes() {
  local t="$WORKROOT/s11"; mkdir -p "$t"
  git_init "$t"
  printf 'host\n' > "$t/main.txt"
  git -C "$t" add main.txt
  git -C "$t" commit -q -m initial

  local rc before after actual expected exclude
  before="$(git -C "$t" status --porcelain --untracked-files=all)"
  "$DOM" "$t" --platform both --guest >/dev/null 2>&1
  check "both guest install stays clean" test "$before" = "$(git -C "$t" status --porcelain --untracked-files=all)"
  "$DOM" "$t" --uninstall --platform codex >/dev/null 2>&1; rc=$?
  after="$(git -C "$t" status --porcelain --untracked-files=all)"

  check "guest Codex-scoped uninstall exits 0" test "$rc" -eq 0
  check "guest scoped uninstall stays clean" test "$before" = "$after"
  check "guest scoped uninstall preserves Claude policy" test -f "$t/CLAUDE.local.md"
  check "guest scoped uninstall preserves Claude agents" bash -c 'test -f "$1" && test -f "$2"' _ "$t/.claude/agents/implementer.md" "$t/.claude/agents/reviewer.md"
  check "guest scoped uninstall persists platforms=claude" bash -c 'test "$(cat "$1")" = claude' _ "$t/.claude/.domestique/platforms"
  check "guest scoped uninstall removes Codex state" test ! -e "$t/.codex"
  check "guest scoped uninstall removes Codex skills" test ! -e "$t/.agents"

  exclude="$t/.git/info/exclude"
  actual="$WORKROOT/s11-exclude-actual"
  expected="$WORKROOT/s11-exclude-expected"
  awk '
    $0 == "# BEGIN domestique (managed)" { inblock=1 }
    inblock { print }
    $0 == "# END domestique" { exit }
  ' "$exclude" > "$actual"
  printf '%s\n' \
    '# BEGIN domestique (managed)' \
    'CLAUDE.local.md' \
    '.claude/' \
    '# END domestique' > "$expected"
  check "remaining guest exclude entries are exact" cmp -s "$expected" "$actual"
  check "remaining exclude has no Codex paths" bash -c '! grep -E "^\\.codex/|^\\.agents/" "$1"' _ "$actual"
}

# ---------------------------------------------------------------------------
# Scenario 13: ownership survives reruns and scoped uninstall. Pre-existing
# untracked Codex paths and generic suffixes remain visible, and --no-guest
# removes the managed ignore block instead of leaving normal assets hidden.
# ---------------------------------------------------------------------------
scenario_guest_visibility_ownership() {
  local t="$WORKROOT/s13"; mkdir -p "$t"
  git_init "$t"
  printf 'host\n' > "$t/main.txt"
  git -C "$t" add main.txt
  git -C "$t" commit -q -m initial

  mkdir -p "$t/.codex/agents" "$t/.beads"
  printf 'host-owned agent\n' > "$t/$IMPL_REL"
  printf 'host beads\n' > "$t/.beads/user.txt"
  printf 'host suffix\n' > "$t/notes.new"

  local before after_first after_second after_scope rc
  before="$(git -C "$t" status --porcelain --untracked-files=all)"
  "$DOM" "$t" --platform both --guest >/dev/null 2>&1; rc=$?
  after_first="$(git -C "$t" status --porcelain --untracked-files=all)"
  "$DOM" "$t" >/dev/null 2>&1
  after_second="$(git -C "$t" status --porcelain --untracked-files=all)"
  "$DOM" "$t" --uninstall --platform claude >/dev/null 2>&1
  after_scope="$(git -C "$t" status --porcelain --untracked-files=all)"

  check "mixed guest install exits 0" test "$rc" -eq 0
  check "first run preserves pre-existing visibility" test "$before" = "$after_first"
  check "selector-less rerun preserves ownership" test "$before" = "$after_second"
  check "scoped uninstall preserves adopted visibility" test "$before" = "$after_scope"
  check "pre-existing Codex file is not ignored" bash -c '! git -C "$1" check-ignore -q "$2"' _ "$t" "$IMPL_REL"
  check "pre-existing .beads is not ignored" bash -c '! git -C "$1" check-ignore -q .beads/user.txt' _ "$t"
  check "generic .new suffix is not ignored" bash -c '! git -C "$1" check-ignore -q notes.new' _ "$t"

  "$DOM" "$t" --no-guest >/dev/null 2>&1; rc=$?
  check "no-guest conversion exits 0" test "$rc" -eq 0
  check "no-guest removes managed exclude block" bash -c '! grep -qF "# BEGIN domestique (managed)" "$1"' _ "$t/.git/info/exclude"

  "$DOM" "$t" --uninstall --platform codex >/dev/null 2>&1; rc=$?
  check "Codex uninstall exits 0 after conversion" test "$rc" -eq 0
  check "uninstall leaves adopted host file in place" grep -qxF 'host-owned agent' "$t/$IMPL_REL"
  check "uninstall does not rename adopted host file" bash -c '! compgen -G "$1.uninstalled.*" >/dev/null' _ "$t/$IMPL_REL"
}

# ---------------------------------------------------------------------------
# Scenario 14: the updater forwards an explicit platform selector and later
# selector-less updater runs reuse the provider set persisted by the installer.
# ---------------------------------------------------------------------------
scenario_updater_platform_forwarding() {
  local t="$WORKROOT/s14"; mkdir -p "$t"
  local out rc
  out="$("$UPDATER" "$t" --source "$DOM" --platform codex 2>&1)"; rc=$?
  check "updater Codex install exits 0" test "$rc" -eq 0
  check "updater creates Codex policy" test -f "$t/AGENTS.md"
  check "updater creates Codex agents" test -f "$t/$IMPL_REL"
  check "updater creates no Claude projection" test ! -e "$t/.claude"
  check "updater output identifies Codex" bash -c 'printf "%s" "$1" | grep -qi codex' _ "$out"

  out="$("$UPDATER" "$t" --source "$DOM" 2>&1)"; rc=$?
  check "selector-less updater rerun exits 0" test "$rc" -eq 0
  check "selector-less updater retains Codex" test -f "$t/$REVIEWER_REL"
  check "selector-less updater does not add Claude" test ! -e "$t/.claude"
}

# ---------------------------------------------------------------------------
# Scenario 15: normal Codex manages an existing active AGENTS.override.md,
# leaves the shadowed AGENTS.md untouched, and uninstall restores both host
# files byte-for-byte.
# ---------------------------------------------------------------------------
scenario_active_agents_override() {
  local t="$WORKROOT/s15"; mkdir -p "$t"
  printf '# Host base instructions\n' > "$t/AGENTS.md"
  printf '# Host active override\n' > "$t/AGENTS.override.md"
  local agents_before override_before rc
  agents_before="$(filehash "$t/AGENTS.md")"
  override_before="$(filehash "$t/AGENTS.override.md")"

  "$DOM" "$t" --platform codex >/dev/null 2>&1; rc=$?
  check "override install exits 0" test "$rc" -eq 0
  check "shadowed AGENTS.md remains byte-identical" test "$agents_before" = "$(filehash "$t/AGENTS.md")"
  check "active override gets one managed block" bash -c '
    test "$(grep -cF "<!-- BEGIN domestique (managed) -->" "$1")" -eq 1
  ' _ "$t/AGENTS.override.md"
  check "AGENTS.md gets no managed block" bash -c '! grep -qF "BEGIN domestique (managed)" "$1"' _ "$t/AGENTS.md"

  "$DOM" "$t" --uninstall --platform codex >/dev/null 2>&1; rc=$?
  check "override uninstall exits 0" test "$rc" -eq 0
  check "uninstall restores host AGENTS.md" test "$agents_before" = "$(filehash "$t/AGENTS.md")"
  check "uninstall restores host override" test "$override_before" = "$(filehash "$t/AGENTS.override.md")"
}

# ---------------------------------------------------------------------------
# Scenario 16: a fixed inventory path is not ownership proof. A never-installed
# target containing a byte-identical Codex template must survive uninstall.
# ---------------------------------------------------------------------------
scenario_uninstall_requires_ownership_evidence() {
  local source="$WORKROOT/s16-source" target="$WORKROOT/s16-target"
  mkdir -p "$source" "$target/.codex/agents"
  "$DOM" "$source" --platform codex >/dev/null 2>&1
  cp "$source/$IMPL_REL" "$target/$IMPL_REL"
  local before rc
  before="$(filehash "$target/$IMPL_REL")"

  "$DOM" "$target" --uninstall --platform codex >/dev/null 2>&1; rc=$?
  check "never-installed uninstall exits 0" test "$rc" -eq 0
  check "matching host file remains present" test -f "$target/$IMPL_REL"
  check "matching host file remains byte-identical" test "$before" = "$(filehash "$target/$IMPL_REL")"
  check "matching host file is not renamed" bash -c '! compgen -G "$1.uninstalled.*" >/dev/null' _ "$target/$IMPL_REL"
}

# ---------------------------------------------------------------------------
# Scenario 12: fake-bd command logging proves provider routing. Normal Codex
# gets safe init followed only by `setup codex`; guest gets stealth safe init
# and never receives any provider setup recipe.
# ---------------------------------------------------------------------------
scenario_beads_provider_routing() {
  local bindir="$WORKROOT/s12-bin"; make_fake_bd "$bindir"
  local t="$WORKROOT/s12-normal" log="$WORKROOT/s12-normal.log" rc
  mkdir -p "$t"
  : > "$log"
  PATH="$bindir:$PATH" FAKE_BD_LOG="$log" "$DOM" "$t" --platform codex --with-beads >/dev/null 2>&1; rc=$?

  local normal_expected="$WORKROOT/s12-normal-expected"
  printf '%s\n' \
    'init --skip-agents --skip-hooks --non-interactive' \
    'setup codex' > "$normal_expected"
  check "normal Codex beads install exits 0" test "$rc" -eq 0
  check "normal Codex routes exact bd commands" cmp -s "$normal_expected" "$log"
  check "normal Codex never sets up Claude" bash -c '! grep -q "setup claude" "$1"' _ "$log"

  local both="$WORKROOT/s12-both" bothlog="$WORKROOT/s12-both.log"
  mkdir -p "$both"
  : > "$bothlog"
  PATH="$bindir:$PATH" FAKE_BD_LOG="$bothlog" "$DOM" "$both" --platform both --with-beads >/dev/null 2>&1; rc=$?
  local both_expected="$WORKROOT/s12-both-expected"
  printf '%s\n' \
    'init --skip-agents --skip-hooks --non-interactive' \
    'setup claude' \
    'setup codex' > "$both_expected"
  check "both-provider beads install exits 0" test "$rc" -eq 0
  check "both-provider routes both setup recipes" cmp -s "$both_expected" "$bothlog"

  local g="$WORKROOT/s12-guest" glog="$WORKROOT/s12-guest.log"
  mkdir -p "$g"
  git_init "$g"
  printf 'host\n' > "$g/main.txt"
  git -C "$g" add main.txt
  git -C "$g" commit -q -m initial
  : > "$glog"
  PATH="$bindir:$PATH" FAKE_BD_LOG="$glog" "$DOM" "$g" --platform codex --guest --with-beads >/dev/null 2>&1; rc=$?

  local guest_expected="$WORKROOT/s12-guest-expected"
  printf '%s\n' 'init --stealth --skip-agents --skip-hooks --non-interactive' > "$guest_expected"
  check "guest Codex beads install exits 0" test "$rc" -eq 0
  check "guest Codex routes exact stealth init" cmp -s "$guest_expected" "$glog"
  check "guest Codex never runs setup" bash -c '! grep -q "^setup " "$1"' _ "$glog"
  check "guest beads install remains clean" bash -c 'test -z "$(git -C "$1" status --porcelain --untracked-files=all)"' _ "$g"

  printf 'shared state\n' > "$g/.beads/data"
  "$DOM" "$g" --platform claude --guest >/dev/null 2>&1
  check "later Claude guest inherits shared beads ownership" test -e "$g/.claude/.domestique/beads-owned"
  "$DOM" "$g" --uninstall --platform codex >/dev/null 2>&1; rc=$?
  check "scoped original-owner uninstall exits 0" test "$rc" -eq 0
  check "surviving guest still hides shared beads" bash -c 'test -z "$(git -C "$1" status --porcelain --untracked-files=all)"' _ "$g"
  check "surviving exclude retains .beads" grep -qxF '.beads/' "$g/.git/info/exclude"
}

echo "domestique Codex test harness"
echo

run_scenario "fresh normal Codex install"                 scenario_fresh_normal_codex
run_scenario "Codex custom-agent TOML"                    scenario_agent_toml
run_scenario "namespaced skills + explicit-only goal"     scenario_skill_metadata
run_scenario "guest skills-only isolation"                scenario_guest_skills_only_isolation
run_scenario "both-platform coexistence"                  scenario_both_mode
run_scenario "Codex idempotency + dry run"                scenario_idempotency_and_dry_run
run_scenario "persisted platform selection"               scenario_persisted_platform_selection
run_scenario "no Claude leakage in Codex-only install"    scenario_no_claude_leakage
run_scenario "Codex local edit + upgrade conflict"        scenario_codex_local_edit_and_upgrade_conflict
run_scenario "Codex uninstall round trip + scope"         scenario_codex_uninstall_roundtrip_and_scope
run_scenario "guest scoped uninstall exact excludes"      scenario_guest_scoped_uninstall_exact_excludes
run_scenario "beads provider routing"                     scenario_beads_provider_routing
run_scenario "guest visibility ownership"                 scenario_guest_visibility_ownership
run_scenario "updater platform forwarding"                scenario_updater_platform_forwarding
run_scenario "active AGENTS.override routing"              scenario_active_agents_override
run_scenario "uninstall requires ownership evidence"      scenario_uninstall_requires_ownership_evidence

echo
TOTAL=$((PASS_COUNT + FAIL_COUNT))
echo "$PASS_COUNT/$TOTAL passed"

if [ "$FAIL_COUNT" -gt 0 ]; then
  exit 1
fi
