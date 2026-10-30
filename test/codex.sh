#!/usr/bin/env bash
# test/codex.sh — self-contained regression harness for domestique.sh's
# native Codex projection. Each scenario runs in an isolated mktemp sandbox,
# reports PASS/FAIL, and the harness exits non-zero if any scenario failed.
# No external test framework and no network access are required.
#
# Run: bash test/codex.sh --current (released v1); omit for frozen history.
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
if [ "${1:-}" = "--current" ]; then
  CURRENT_TEST=1
  export HOME="$WORKROOT/current-home"
  mkdir -p "$HOME"
else
  # shellcheck source=test/historical-fixture.sh
  source "$SCRIPT_DIR/historical-fixture.sh"
fi

# Preserve the intended fixture scope, not the former implicit CLI default.
scoped_install() {
  local platform="$1"; shift
  if [ "${CURRENT_TEST:-0}" = 1 ]; then "$@" --platform "$platform"
  else "$@"; fi
}
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
  check "goal skill created" test -f "$t/$GOAL_SKILL_REL"
  check "goal metadata created" test -f "$t/$GOAL_META_REL"
  check "no CLAUDE.md" test ! -e "$t/CLAUDE.md"
  check "no CLAUDE.local.md" test ! -e "$t/CLAUDE.local.md"
  check "no .claude directory" test ! -e "$t/.claude"
  check "summary identifies Codex" bash -c 'printf "%s" "$1" | grep -qi "codex"' _ "$out"
}

# ---------------------------------------------------------------------------
# Scenario 2: emitted agent TOML suggests unconfirmed models/efforts and carries
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
  if [ "${CURRENT_TEST:-0}" = 1 ]; then
    check "bare rerun adds Claude" test -f "$t/CLAUDE.md"
    check "bare rerun adds Copilot" test -f "$t/.github/.domestique/manifest"
  else
    check "bare rerun does not create CLAUDE.md" test ! -e "$t/CLAUDE.md"
    check "bare rerun does not create .claude" test ! -e "$t/.claude"
  fi
  check "bare rerun reports persisted Codex" bash -c 'printf "%s" "$1" | grep -qi "codex"' _ "$out"
}

# ---------------------------------------------------------------------------
# Scenario 8: Codex-only output contains no Claude setup/model paths or
# deprecated custom prompts. Foreign-client boundary/redirect text is allowed.
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
  check "no Claude setup/model paths in Codex output" bash -c '
    ! grep -R -E -i "Sonnet|Opus|CLAUDE\\.md|\\.claude/|~/\\.codex/prompts" \
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
  original="$(grep '^description = ' "$t/$IMPL_REL")"
  check "one installed description anchor" test "$(printf '%s\n' "$original" | wc -l | tr -d ' ')" -eq 1
  local_line='description = "Codex only; never match in another harness. LOCAL: executes one bounded beads task under host-specific rules."'
  upstream_line='description = "Codex only; never match in another harness. UPSTREAM V2: executes one bounded beads task with upgraded orchestration rules."'
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
  scoped_install both "$DOM" "$t" >/dev/null 2>&1
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

  scoped_install codex "$DOM" "$t" --no-guest >/dev/null 2>&1; rc=$?
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
  if [ "${CURRENT_TEST:-0}" = 1 ]; then
    check "selector-less updater adds Claude" test -f "$t/CLAUDE.md"
    check "selector-less updater adds Copilot" test -f "$t/.github/.domestique/manifest"
  else
    check "selector-less updater does not add Claude" test ! -e "$t/.claude"
  fi
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

scenario_public_names() {
  local mode t rc kind entry rel before policy
  for mode in normal guest; do
    t="$WORKROOT/public-$mode"; mkdir -p "$t"
    git_init "$t"
    if [ "$mode" = guest ]; then
      "$DOM" "$t" --platform both --guest >/dev/null 2>&1; rc=$?
      policy="$t/CLAUDE.local.md"
    else
      "$DOM" "$t" --platform both >/dev/null 2>&1; rc=$?
      policy="$t/CLAUDE.md"
    fi
    check "$mode install" test "$rc" -eq 0
    for kind in decompose goal; do
      check "Claude $kind shared body" cmp -s "$t/.claude/commands/$kind.md" "$t/.claude/commands/dom-$kind.md"
      check "Claude arguments literal" grep -qF '$ARGUMENTS' "$t/.claude/commands/dom-$kind.md"
      for entry in "dom-$kind" "domestique-$kind"; do
        rel=".agents/skills/$entry/SKILL.md"
        check "exact Codex name $entry" assert_skill_name "$t/$rel" "$entry"
        check "Codex invocation content" grep -qF "\$dom-$kind" "$t/$rel"
        check "Codex compatibility content" grep -qF "\$domestique-$kind" "$t/$rel"
        if [ "$kind" = goal ]; then
          check "explicit-only $entry" grep -qF 'allow_implicit_invocation: false' "$t/.agents/skills/$entry/agents/openai.yaml"
          check "default prompt $entry" grep -qF "\$$entry with an explicit epic id." "$t/.agents/skills/$entry/agents/openai.yaml"
          check "no implicit authority $entry" grep -qF 'Merely loading or implicitly matching' "$t/$rel"
        fi
      done
    done
    check "Claude policy short authority" grep -qF '/dom-goal <epic-id>' "$policy"
    check "Claude policy legacy authority" grep -qF '/goal <epic-id>' "$policy"
    if [ "$mode" = guest ]; then
      check "all new paths private" bash -c 'test -z "$(git -C "$1" status --porcelain --untracked-files=all)"' _ "$t"
      for rel in .agents/skills/dom-decompose/SKILL.md .agents/skills/dom-goal/SKILL.md .agents/skills/dom-goal/agents/openai.yaml; do
        check "owned guest alias $rel" grep -qxF "$rel" "$t/.codex/.domestique/guest-excludes"
        check "excluded guest alias $rel" grep -qxF "$rel" "$t/.git/info/exclude"
      done
    else
      check "Codex policy short authority" grep -qF '$dom-goal <epic-id>' "$t/AGENTS.md"
      check "Codex policy legacy authority" grep -qF '$domestique-goal <epic-id>' "$t/AGENTS.md"
    fi
    before="$(treehash "$t")"
    "$DOM" "$t" --platform both >/dev/null 2>&1; rc=$?
    check "rerun succeeds" test "$rc" -eq 0
    check "rerun byte-identical" test "$before" = "$(treehash "$t")"
    for rel in .claude/commands/dom-goal.md .agents/skills/dom-goal/SKILL.md; do
      printf '\nUser customization\n' >> "$t/$rel"
    done
    "$DOM" "$t" --platform both >/dev/null 2>&1; rc=$?
    check "edited rerun succeeds" test "$rc" -eq 0
    for rel in .claude/commands/dom-goal.md .agents/skills/dom-goal/SKILL.md; do
      check "rerun preserves $rel" grep -qxF 'User customization' "$t/$rel"
    done
    "$DOM" "$t" --uninstall >/dev/null 2>&1; rc=$?
    check "uninstall succeeds" test "$rc" -eq 0
    check "unchanged Claude alias removed" test ! -e "$t/.claude/commands/dom-decompose.md"
    check "unchanged Codex alias removed" test ! -e "$t/.agents/skills/dom-decompose/SKILL.md"
    check "unchanged Codex metadata removed" test ! -e "$t/.agents/skills/dom-goal/agents/openai.yaml"
    for rel in .claude/commands/dom-goal.md .agents/skills/dom-goal/SKILL.md; do
      check "edited alias retained by v1 rename" bash -c 'grep -qxF "User customization" "$1".uninstalled.*' _ "$t/$rel"
    done
  done
}

scenario_public_name_host_collisions() {
  local t="$WORKROOT/public-host" rel rc before
  mkdir -p "$t"; git_init "$t"
  for rel in .claude/commands/dom-goal.md .agents/skills/dom-decompose/SKILL.md .agents/skills/dom-goal/SKILL.md .agents/skills/dom-goal/agents/openai.yaml; do
    mkdir -p "$(dirname "$t/$rel")"
    printf 'host customization\n' > "$t/$rel"
  done
  "$DOM" "$t" --platform both --guest >/dev/null 2>&1; rc=$?
  check "collision install preserves via helpers" test "$rc" -eq 0
  "$DOM" "$t" --platform both >/dev/null 2>&1
  for rel in .claude/commands/dom-goal.md .agents/skills/dom-decompose/SKILL.md .agents/skills/dom-goal/SKILL.md .agents/skills/dom-goal/agents/openai.yaml; do
    check "host bytes preserved $rel" grep -qxF 'host customization' "$t/$rel"
  done
  for rel in .agents/skills/dom-decompose/SKILL.md .agents/skills/dom-goal/SKILL.md .agents/skills/dom-goal/agents/openai.yaml; do
    check "host alias stays visible" bash -c '! git -C "$1" check-ignore -q "$2"' _ "$t" "$rel"
  done
  before="$(filehash "$t/.agents/skills/dom-goal/SKILL.md")"
  "$DOM" "$t" --uninstall >/dev/null 2>&1; rc=$?
  check "host collision uninstall" test "$rc" -eq 0
  check "unowned Codex alias kept in place" test "$before" = "$(filehash "$t/.agents/skills/dom-goal/SKILL.md")"
  check "host Claude alias kept by existing rename behavior" bash -c 'grep -qxF "host customization" "$1".uninstalled.*' _ "$t/.claude/commands/dom-goal.md"
}

scenario_previous_install_adds_public_names() {
  local t="$WORKROOT/previous-install" old="$WORKROOT/previous-domestique.sh" rc rel
  mkdir -p "$t"; git_init "$t"
  git -C "$REPO_DIR" show 654414025554defe9eeef50c39b14a87326088b8:domestique.sh > "$old"
  bash "$old" "$t" --platform both --guest >/dev/null 2>&1; rc=$?
  check "frozen previous install" test "$rc" -eq 0
  check "previous install had no short skill" test ! -e "$t/.agents/skills/dom-goal"
  check "previous install had no short command" test ! -e "$t/.claude/commands/dom-goal.md"
  printf '\nUser role edit\n' >> "$t/$IMPL_REL"
  "$DOM" "$t" --platform both >/dev/null 2>&1; rc=$?
  check "ordinary rerun adds aliases" test "$rc" -eq 0
  check "role customization preserved" grep -qxF 'User role edit' "$t/$IMPL_REL"
  check "Claude alias added" cmp -s "$t/.claude/commands/goal.md" "$t/.claude/commands/dom-goal.md"
  for rel in .agents/skills/dom-decompose/SKILL.md .agents/skills/dom-goal/SKILL.md .agents/skills/dom-goal/agents/openai.yaml; do
    check "alias exists after upgrade" test -f "$t/$rel"
    check "new alias guest ownership" grep -qxF "$rel" "$t/.codex/.domestique/guest-excludes"
    check "new alias guest exclusion" grep -qxF "$rel" "$t/.git/info/exclude"
  done
  # Existing v1 policy merge deliberately leaves a visible CLAUDE.local.md
  # backup. Do not broaden excludes or change that lifecycle for alias naming.
  check "upgrade exposes only existing policy-backup behavior" bash -c '
    ! git -C "$1" status --porcelain --untracked-files=all | grep -v "^?? CLAUDE.local.md.bak."
  ' _ "$t"
}

# Static protocol assertions over actual installer output, NOT native execution.
scenario_codex_setup_protocol() {
  local t="$WORKROOT/setup-protocol"; mkdir -p "$t"; git_init "$t"
  check "install Codex" "$DOM" "$t" --platform codex
  check "first/repeat/inherit/conflict/cancel instructions (static only)" python3 - "$t" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
skills = root / ".agents/skills"
start = "## Codex first-use role setup — mandatory gate"
end = "## End role setup gate — continue only for an unchanged confirmed, ready pair"
def body(text):
    assert text.count(start) == text.count(end) == 1
    return text.split(start)[1].split(end)[0]
decompose = (skills / "domestique-decompose/SKILL.md").read_text()
goal = (skills / "domestique-goal/SKILL.md").read_text()
setup = body(decompose)
assert setup == body(goal)
for kind, text, action in (
    ("decompose", decompose, "# Decompose into beads"),
    ("goal", goal, "# Unattended epic execution"),
):
    shared = (skills / f"dom-{kind}/SKILL.md").read_text()
    assert f".agents/skills/domestique-{kind}/SKILL.md" in shared
    assert start not in shared
    assert text.index(end) < text.index(action)

for phrase in (
    "BEFORE any Beads command (including readiness/create/claim)",
    "active harness as `codex`", "exact physical Git", "Never search ancestors",
    "ROOT/.codex/agents/implementer.toml", "ROOT/.codex/agents/reviewer.toml",
    "ROOT/.codex/.domestique/manifest",
    "base/.codex/agents/{implementer,reviewer}.toml",
    "snapshot_format=1", "platform=codex", "NOT historical inode proof",
    "Current owned customized bytes may be confirmed", "original pristine bases",
    "Missing/unmanaged", "never adopt through setup", "Do not impose Copilot",
    "at most 1 MiB", "no symlinks in any path component", "link count must",
    "Record current device/inode", "TOML parser", 'name = "implementer"',
    'name = "reviewer"', "unique top-level scalar string",
    "Reject duplicate keys", "non-string or multiline selection fields",
    "duplicate/misplaced setup markers", "nested tables",
    "single comment at the beginning of implementer",
    "`# domestique-model-setup: JSON`", "Reviewer must contain no setup marker",
    "`v` (integer 1)", "`project`", "`harness` (`codex`)",
    "`implementer_sha256`, `reviewer_sha256`", "removing only",
    "JSON types/unique keys", "BOTH digests", "pristine generated defaults",
    "copied/moved", "never complete a partial pair silently", "Any manual",
    "NO questionnaire and NO writes", "including confirmed\ninheritance",
    "request `configure role models`", "Aliases share this pair/marker",
    "Show ROOT / codex", "current model and model_reasoning_effort",
    "same model", "fresh reviewer context", "exact IDs",
    "Generated defaults and absent fields are not consent",
    "Model and effort are independent", "explicitly confirm compatible existing",
    "explicitly resolve incompatible effort", "Never silently retain unsupported",
    "OMIT model", "write a literal model named `inherit`",
    "For inherited effort OMIT\nmodel_reasoning_effort",
    "ACTUAL complete proposed diff", "Save setup only / Cancel",
    "redisplay the diff", "Goal authorization\nis not settings consent",
    "Cancel, incomplete/missing values, or noninteractive",
    "ZERO writes and NO Beads/workflow calls", "preserve any prior pair",
    "Noninteractive callers may only use an already confirmed pair",
    "Reject newlines and control characters", "including DEL/C1",
    "double-quoted basic strings", r"as \\ and double quote as \"",
    "ensure_ascii=False", "surrogate pairs", "Round-trip both proposed files",
    "every unrelated key, including developer_instructions",
    "never shell interpolation/eval", "selected top-level value spans",
    "not inside a\ntable or multiline string", "Preserve ALL unrelated bytes",
    "line endings\nand modes", "retain its unrelated inline comment",
    "lossless bounded patch cannot be established, STOP",
    "recheck safe paths, current identities, modes and bytes",
    "same-directory temporary files", "atomic per-file replacement",
    "NOT a two-file transaction", "verify exact approved bytes/modes",
    "reports exactly which paths changed", "NO workflow authority",
    "No rollback, journal or silent repair", "SETUP ONLY: no planning",
    "beads, claim, code, dispatch, branch/commit or goal cycle",
    "fresh client\nsession", "NOT queued for automatic continuation",
    "Missing setup during truly noninteractive/autopilot goal execution means STOP",
    "Confirmed setup alone grants no goal authority",
    "ALL tracked/index dirtiness", "never auto-stage, commit, stash, discard",
    "never reset pristine\nbases to configured bytes",
):
    assert phrase in setup, phrase
assert setup.index("1. Invalidate") < setup.index("2. Write the reviewer")
assert setup.index("2. Write the reviewer") < setup.index("3. Publish implementer")

# Real emitted aliases share inline entry and a setup-scoped ban on helpers.
entry, preflight = setup.split("### Read-only preflight", 1)
evidence = preflight.split("### Native evidence", 1)[1].split("Before saving", 1)[0]
for section in (entry, evidence):
    assert "do NOT use ANY Agent/Task/agent delegation" in section
    assert "documentation/research helpers or built-in documentation agents" in section
    assert "missing evidence means STOP, not a helper call" in section
assert "the workflow still requires implementer and independent reviewer delegation" in entry
assert "questionnaire INLINE here" in entry and "do not redirect to decompose" in entry
assert "Ordinary unconfigured delegation instead" in entry
assert "without a confirmed pair STOP without persistence" in " ".join(entry.split())
assert "Setup consumes this request: no task, Beads or implementation" in " ".join(entry.split())

# Persistence support is checked before save; loaded registration matching is
# required after fresh reload, not used to veto a supported setup-only edit.
pre_save, post_save = setup.split("After saving, require a fresh client session", 1)
for phrase in (
    "PRE-SAVE check concerns supported persistent native role-file/config semantics",
    "not readiness to dispatch through this conversation's loaded roles",
    "Verify that this installed client supports the proposed persistent model/effort fields for these roles and their required tools",
    "Catalog presence alone does not guarantee role compatibility or provider permission",
    "actually disallows the requested persistent model/effort, STOP before writes, preserving all bytes",
    "unknown capability or ambiguous inheritance also stops",
    "Current immutable/non-overridable role registrations are not expected to change in this conversation",
    "Their mismatch with a proposed pair during SETUP alone is NOT grounds to reject supported persistent reconfiguration or refuse its actual diff/consent flow",
    "does not bypass fixed tool registration or provider permissions",
    "No Task/spawn override attempt, dispatch test, or fallback to old generated defaults",
    "show the actual complete diff, obtain Save setup only consent",
    "required ordinary native scoped protected-write approval",
    "save only, then STOP for a fresh session and reinvocation",
):
    assert phrase in " ".join(pre_save.split()), phrase
for phrase in (
    "POST-SAVE readiness check is distinct from PRE-SAVE persistence support",
    "freshly loaded registered pair must match the chosen values and their native-effective model/effort resolution before dispatch",
    "saving files does not change current-session registrations or authorize an in-session override",
    "registration must be present and unambiguous",
    "Missing/ambiguous registration, actual mismatch, unresolved inheritance",
    "Send no conflicting spawn model/effort override",
):
    assert phrase in " ".join(post_save.split()), phrase

# Read-only pair/diff first; consent and native approval precede BOTH-role checks
# inside the publication command, with denial/change/unwritable paths fail-closed.
ordered = (
    "### Read-only preflight", "### One question for BOTH roles",
    "ACTUAL complete proposed diff", "before explicit Save setup only consent",
    "Only AFTER explicit Save setup only consent",
    "request native one-command scoped approval", "sandbox_permissions=require_escalated",
    "Final writable preflight runs INSIDE the approved command/context",
    "Preflight BOTH", "both role files and parents are actually writable",
    "the SAME prepared command performs publication", "1. Invalidate",
)
positions = [setup.index(phrase) for phrase in ordered]
assert positions == sorted(positions)
assert "writable role\nparents" not in preflight.split("### Native evidence")[0]
for phrase in (
    "read-only ownership/path/field/identity checks, not a writability gate",
    "NOT unknown ownership or permanent filesystem read-only status",
    "Do not write probes", "approval_policy=on-request",
    "specific justification naming both exact role paths",
    "No persistent prefix rule, sandbox-mode change, broad permission grant or bypass",
    "If approval is denied or unavailable, STOP with ZERO mutation and NO success",
    "before ANY mutation, including temporary files or marker invalidation",
    "against the original read-only snapshot",
    "Changed inputs or an actually unwritable file/parent mean STOP with ZERO mutation and NO success",
):
    assert phrase in " ".join(setup.split()), phrase

for phrase in (
    "Before saving, use supported evidence", "supported and available",
    "role-file model/model_reasoning_effort values override",
    "explicit spawn, then [agents] defaults, then parent",
    "previously resolved effort; it does NOT reset",
    "Verify installed-version behavior", "Unknown support/availability",
    "STOP before writes", "No fallback", "invented verification API or paid probe",
    "After saving, require a fresh client session",
    "Send no conflicting spawn", "Ephemeral model requests are assertions",
    "a conflict stops", "resolve/check it anew each session",
    "STOP without workflow or writes", "not dispatch proof",
    "Actual observed role dispatch/reload qualification is separate",
    "static emitted-protocol/lifecycle tests do not qualify runtime",
):
    assert phrase in setup, phrase
# Positive minimum permits supported registration/resolution without an optional
# origin API; actual mismatches still stop and child evidence comes after spawn.
for phrase in (
    "supported pre-dispatch minimum, read-only",
    "active native client and its registered intended `implementer` and `reviewer` role IDs",
    "registration must be present and unambiguous",
    "stored pair, ownership, physical ROOT, BOTH marker hashes",
    "required fresh-session reload",
    "Match declared model AND effort and required tools",
    "Explicit non-overridable registered selections plus documented native resolution are sufficient",
    "documented project-local discovery and precedence",
    "competing project/ancestor/global definitions",
    "current provider/model compatibility with available non-secret native evidence",
    "not a future entitlement/runtime guarantee",
    "A doctor subprocess describes its own provider/session, not automatically the active thread",
    "establish applicability before using it as active-session evidence",
    "Use native source provenance when exposed",
    "do not invent exact-origin or loaded-byte attestation",
    "Missing optional exact-origin/loaded-byte APIs or not-yet-existent child telemetry alone do not block ordinary explicitly authorized work when this minimum is established",
    "Missing/ambiguous registration, actual mismatch, unresolved inheritance or a known defeating override/unavailability means STOP",
    "During/after each authorized assignment, check actual available child telemetry",
    "before accepting work",
    "selection failure/mismatch means STOP; never silently fall back",
    "declared selections are not execution proof",
    "require an unavailable telemetry API or demand a separate paid probe",
):
    assert phrase in " ".join(setup.split()), phrase
for path in (root / "AGENTS.md", skills / "domestique/SKILL.md"):
    text = path.read_text()
    for phrase in (
        "supported pre-dispatch minimum in that protocol",
        "registered intended role IDs", "pair/ownership/root/hashes and required reload",
        "matching declared/resolved model/effort and tools",
        "documented project discovery/precedence", "competing definitions and known overrides checked",
        "available non-secret provider/model compatibility evidence",
        "Missing optional exact-origin/loaded-byte APIs or future child telemetry alone do not block explicitly authorized work once this minimum passes",
        "Missing/ambiguous registration, actual mismatch, unresolved inheritance",
        "known defeating override or unavailability means STOP, never fallback",
        "during/after each authorized assignment before accepting work",
        "selection failure/mismatch stops",
        "distinguish PRE-SAVE persistent role-file support from POST-SAVE fresh-session registered-role readiness",
        "immutable registrations need not match a proposed pair during setup alone",
        "that mismatch does not forbid a supported persistent edit",
        "Verify installed role-file semantics and provider/tool compatibility, not just catalog presence",
        "Show the actual diff, obtain Save setup only consent and required native scoped protected-write approval",
        "save only, then STOP for fresh reload/reinvocation",
        "Do not attempt an in-session Task/spawn override or use old defaults as fallback",
        "freshly loaded registered pair must match the chosen/native-effective model and effort before dispatch",
        "persistence never bypasses fixed tool registration, provider permissions or genuine capability restrictions",
    ):
        assert phrase in " ".join(text.split()), phrase
    for obsolete in (
        "verify that these exact files loaded", "requires exact local",
        "If exact loading/effective selection",
        "prevention of silent substitution cannot be verified",
    ):
        assert obsolete not in " ".join((text + decompose + goal).split()), obsolete
    assert "Ordinary bounded delegation" in text
    assert "read-only" in text
    assert "STOP and direct the human to `$dom-decompose configure role models`" in text
    assert "do not start another questionnaire" in text
    assert "Instruction/bootstrap loading alone neither starts setup nor grants goal" in text
    assert text.index("questionnaire INLINE") < text.index("Ordinary bounded delegation")
    assert "not a\nredirect to decompose" in text
    assert "without a confirmed pair STOP without persistence" in text
    assert text.index("## Role model gate") < text.index("`bd ready`")
assert goal.index("Interactive first-use goal setup") < goal.index("An explicit `$dom-goal <epic-id>`")
assert "not the ordinary-delegation redirect" in goal
assert goal.index("check ALL tracked/index dirtiness") < goal.index("Then create/switch")
for role in ("implementer", "reviewer"):
    assert b"domestique-model-setup:" not in (root / f".codex/agents/{role}.toml").read_bytes()
assert not (root / ".beads").exists()
PY
}

# Real installer lifecycle on a SYNTHETIC pair; no native questionnaire/dispatch.
scenario_codex_configured_lifecycle() {
  local choice="$1" t="$WORKROOT/configured-$1"
  mkdir -p "$t"; git_init "$t"
  if [ "$choice" = inherit ]; then
    check "install guest fixture" "$DOM" "$t" --platform codex --guest
  else
    check "install explicit fixture" "$DOM" "$t" --platform codex
  fi
  local base="$t/.codex/.domestique/base" i_before r_before base_before excludes_before
  base_before="$(treehash "$base")"
  excludes_before="$(filehash "$t/.git/info/exclude")"
  check "synthetic parser-checked $choice pair" python3 "$SCRIPT_DIR/fixtures/codex-configured-pair.py" "$t" "$choice"
  i_before="$(filehash "$t/$IMPL_REL")"
  r_before="$(filehash "$t/$REVIEWER_REL")"
  cp "$t/$IMPL_REL" "$WORKROOT/$choice-implementer"
  cp "$t/$REVIEWER_REL" "$WORKROOT/$choice-reviewer"
  cp "$base/$IMPL_REL" "$WORKROOT/$choice-base"
  check "repeat install" "$DOM" "$t" --platform codex
  check "configured implementer byte-identical" test "$i_before" = "$(filehash "$t/$IMPL_REL")"
  check "configured reviewer byte-identical" test "$r_before" = "$(filehash "$t/$REVIEWER_REL")"
  check "pristine bases not rebaselined" test "$base_before" = "$(treehash "$base")"
  check "excludes unchanged" test "$excludes_before" = "$(filehash "$t/.git/info/exclude")"
  if [ "$choice" = inherit ]; then
    check "configured guest stays local-only" bash -c 'test -z "$(git -C "$1" status --porcelain)"' _ "$t"
  fi
  local v2="$WORKROOT/configured-$choice-v2.sh"
  check "synthetic upstream instruction change" python3 - "$DOM" "$v2" <<'PY'
from pathlib import Path
import sys
source, dest = map(Path, sys.argv[1:])
old = b"- Stay inside the brief. Do not refactor adjacent code or start another bead."
new = old + b" (v2)"
text = source.read_bytes()
assert text.count(old) == 1
dest.write_bytes(text.replace(old, new))
PY
  check "real three-way upgrade" bash "$v2" "$t" --platform codex
  check "parser/marker/preservation after real merge (offline only)" python3 - "$t" "$WORKROOT" "$choice" <<'PY'
import hashlib
import json
from pathlib import Path
import sys
import tomllib
root, scratch = map(Path, sys.argv[1:3])
choice = sys.argv[3]
i = (root / ".codex/agents/implementer.toml").read_bytes()
r = (root / ".codex/agents/reviewer.toml").read_bytes()
old = (scratch / f"{choice}-implementer").read_bytes()
anchor = b"- Stay inside the brief. Do not refactor adjacent code or start another bead."
assert i == old.replace(anchor, anchor + b" (v2)")
assert r == (scratch / f"{choice}-reviewer").read_bytes()
line = i.splitlines(keepends=True)[0]
marker = json.loads(line.removeprefix(b"# domestique-model-setup: "))
assert set(marker) == {"v", "project", "harness", "implementer_sha256", "reviewer_sha256"}
assert marker["v"] == 1 and marker["harness"] == "codex"
assert marker["project"] == str(root.resolve())
assert marker["implementer_sha256"] == hashlib.sha256(old[len(line):]).hexdigest()
assert marker["implementer_sha256"] != hashlib.sha256(i[len(line):]).hexdigest()
assert marker["reviewer_sha256"] == hashlib.sha256(r).hexdigest()
base = (root / ".codex/.domestique/base/.codex/agents/implementer.toml").read_bytes()
assert base == (scratch / f"{choice}-base").read_bytes().replace(anchor, anchor + b" (v2)")
assert b"domestique-model-setup:" not in base
assert b"LOCAL IMPLEMENTER INSTRUCTIONS" not in base
for data in (i, r, base):
    tomllib.loads(data.decode())
# Read-only byte mutation demonstrates digest sensitivity, NOT a running gate.
assert marker["reviewer_sha256"] != hashlib.sha256(r + b"# manual edit\n").hexdigest()
PY
  check "upgrade leaves excludes unchanged" test "$excludes_before" = "$(filehash "$t/.git/info/exclude")"
  cp "$t/$IMPL_REL" "$WORKROOT/$choice-implementer"
  check "real uninstall preserves configured roles" bash "$v2" "$t" --uninstall --platform codex
  check "both customized roles kept under existing backup semantics" python3 - "$t" "$WORKROOT" "$choice" <<'PY'
from pathlib import Path
import sys
root, scratch = map(Path, sys.argv[1:3])
choice = sys.argv[3]
for role in ("implementer", "reviewer"):
    path = root / f".codex/agents/{role}.toml"
    assert not path.exists()
    backups = list(path.parent.glob(path.name + ".uninstalled.*"))
    assert len(backups) == 1
    original = scratch / f"{choice}-{role}"
    assert backups[0].read_bytes() == original.read_bytes()
    assert backups[0].stat().st_mode == original.stat().st_mode
assert not (root / ".codex/.domestique").exists()
assert not (root / ".beads").exists()
PY
}

scenario_codex_explicit_lifecycle() { scenario_codex_configured_lifecycle explicit; }
scenario_codex_inherit_guest_lifecycle() { scenario_codex_configured_lifecycle inherit; }

# Installed text checks only: no native client or simulated dispatch claims.
scenario_shared_routing_boundaries() {
  local mode="$1" t="$WORKROOT/shared-routing-$1"; mkdir -p "$t"; git_init "$t"
  printf 'Host Claude instructions\n' > "$t/CLAUDE.md"
  printf 'Host Codex instructions\n' > "$t/AGENTS.md"
  check "$mode source-free stdin install and installed boundaries" python3 - "$DOM" "$t" "$mode" <<'PY'
from pathlib import Path
import subprocess
import sys
script, root = map(Path, sys.argv[1:3])
guest = sys.argv[3] == "guest"
flags = ["--guest"] if guest else []
for provider in ("both", "copilot"):
    subprocess.run(["bash", "-s", "--", str(root), "--platform", provider, *flags],
                   input=script.read_bytes(), cwd=root, check=True, capture_output=True)
for filename, harness in (("CLAUDE.md", "claude"), ("AGENTS.md", "codex")):
    if guest:
        assert (root / filename).read_text() == f"Host {harness.title()} instructions\n"
        if harness == "codex":
            continue
        filename = "CLAUDE.local.md"
    text = (root / filename).read_text()
    if not guest:
        assert text.startswith("Host ")
    assert f"Active harness boundary ({harness} only)" in text
    assert "Other harnesses must ignore this entire owned policy block" in text
    assert text.index("Active harness boundary") < text.index("This session is")
    assert "Unrelated host instructions still apply" in text
native = list((root / ".claude/commands").glob("*.md"))
native += list((root / ".claude/agents").glob("*.md"))
native += list((root / ".agents/skills").glob("domestique*/SKILL.md"))
native += list((root / ".github/skills").glob("*/SKILL.md"))
native += list((root / ".github/agents").glob("*.agent.md"))
assert len(native) == 14
for path in native:
    text = path.read_text()
    harness = "claude" if ".claude" in path.parts else "copilot" if ".github" in path.parts else "codex"
    description = next(x for x in text.splitlines() if x.startswith("description:"))
    assert ("Claude Code only" if harness == "claude" else f"{harness.title()} only") in description
    assert "never match" in description
    assert f"Active harness boundary ({harness} only)" in text
    for phrase in ("ACTUAL native caller", "context and native tools",
                   "There is no required identity API", "STOP and ask",
                   "An explicit foreign-harness invocation must STOP",
                   "without setup, Beads, task", "do not invoke them automatically"):
        assert phrase in text, (path, phrase)
    if "first-use role setup" in text:
        assert text.index("Active harness boundary") < text.index("first-use role setup")
for kind in ("decompose", "goal"):
    text = (root / f".agents/skills/dom-{kind}/SKILL.md").read_text()
    for phrase in ("ACTUAL native caller", "Unknown, ambiguous, or unsupported",
                   "Missing, unreadable or foreign native bodies mean STOP",
                   "ORIGINAL user request verbatim", "explicit epic arguments",
                   "authorization provenance", "Never synthesize a new",
                   "Merely loading or implicitly matching", "must not start setup",
                   "Setup consumes that", "does not establish native readiness",
                   f".agents/skills/domestique-{kind}/SKILL.md",
                   f".github/skills/domestique-v2-copilot-{kind}/SKILL.md",
                   "domestique-v2-copilot-implementer", "domestique-v2-copilot-reviewer"):
        assert phrase in text, phrase
    assert "first-use role setup" not in text
    codex = root / f".agents/skills/domestique-{kind}/SKILL.md"
    copilot = root / f".github/skills/domestique-v2-copilot-{kind}/SKILL.md"
    assert len({text, codex.read_text(), copilot.read_text()}) == 3
    assert not (root / f".github/skills/dom-{kind}").exists()
    body = copilot.read_text()
    assert body.index("Active harness boundary") < body.index("first-use role setup")
    assert body.index("first-use role setup") < body.index("## End setup gate")
    assert "No setup delegation of ANY kind" in body
    assert "Save setup only" in body
    assert "Setup consumes the request" in body
    if kind == "goal":
        assert "Missing explicit request/epic means STOP" in body
        assert "native /goal or /autopilot is not" in body
        assert "literal epic argument" in body
    for forbidden in (str(script.parent), "preview/launcher", "workflow --project",
                      "machine-root", "current/bin", "--confirm-model"):
        assert forbidden not in text + body + codex.read_text(), forbidden
policy = root / ".github/copilot-instructions.md"
assert policy.exists() != guest
for rel in (".agents/skills/dom-goal/SKILL.md",
            ".github/skills/domestique-v2-copilot-goal/SKILL.md"):
    hidden = subprocess.run(["git", "check-ignore", "-q", rel], cwd=root).returncode == 0
    assert hidden == guest
inventories = []
for state in (".claude", ".codex", ".agents", ".github"):
    manifest = (root / state / ".domestique/manifest").read_text()
    inventories += next(x[6:] for x in manifest.splitlines() if x.startswith("files=")).split(",")
assert len(inventories) == len(set(inventories))
for kind in ("decompose", "goal"):
    rel = f".agents/skills/dom-{kind}/SKILL.md"
    assert (root / ".agents/.domestique/base" / rel).exists()
    assert not (root / ".codex/.domestique/base" / rel).exists()
PY
}

scenario_shared_routing_normal_and_guest() {
  scenario_shared_routing_boundaries normal
  scenario_shared_routing_boundaries guest
}

scenario_shared_legacy_migration() {
  local t="$WORKROOT/shared-migration" old="$WORKROOT/shared-old.sh" before rc
  mkdir -p "$t"; git_init "$t"
  git -C "$REPO_DIR" show 64f4e09:domestique.sh > "$old"
  check "previous snapshot install" bash "$old" "$t" --platform codex --guest
  printf '\nLocal native body customization\n' >> "$t/$DECOMPOSE_SKILL_REL"
  before="$(treehash "$t")"
  "$DOM" "$t" --platform codex --dry-run >/dev/null 2>&1; rc=$?
  check "migration dry-run" test "$rc" -eq 0
  check "dry-run writes nothing" test "$before" = "$(treehash "$t")"
  check "migrate shared bases" "$DOM" "$t" --platform codex
  check "native custom bytes retained" grep -qxF 'Local native body customization' "$t/$DECOMPOSE_SKILL_REL"
  check "shared authority exists" test -f "$t/.agents/.domestique/manifest"
  check "legacy canonical base retired" test ! -e "$t/.codex/.domestique/base/.agents/skills/dom-goal/SKILL.md"
  check "no duplicate canonical inventory" bash -c '! grep "^files=" "$1" | grep -q "/dom-goal/"' _ "$t/.codex/.domestique/manifest"
  before="$(treehash "$t")"
  "$DOM" "$t" --platform codex >/dev/null 2>&1; rc=$?
  check "migration rerun" test "$rc" -eq 0
  check "migration idempotent" test "$before" = "$(treehash "$t")"
  check "migrated guest remains private" git -C "$t" check-ignore -q .agents/.domestique/manifest
}

scenario_shared_preflight_refusal() {
  local t="$WORKROOT/shared-refusal" old="$WORKROOT/shared-refusal-old.sh" before rc flag
  mkdir -p "$t"; git_init "$t"
  git -C "$REPO_DIR" show 64f4e09:domestique.sh > "$old"
  bash "$old" "$t" --platform codex --guest >/dev/null 2>&1
  # A conflicting custom canonical body cannot be silently moved or rebased.
  printf 'Entirely customized canonical goal body\n' > "$t/.agents/skills/dom-goal/SKILL.md"
  before="$(treehash "$t")"
  for flag in --dry-run --force --no-guest; do
    "$DOM" "$t" --platform both "$flag" >/dev/null 2>&1; rc=$?
    check "legacy conflict refused $flag" test "$rc" -eq 3
    check "legacy refusal has zero writes $flag" test "$before" = "$(treehash "$t")"
  done
  local fresh="$WORKROOT/shared-unknown"
  mkdir -p "$fresh/.agents/.domestique"
  printf 'unknown state\n' > "$fresh/.agents/.domestique/manifest"
  before="$(treehash "$fresh")"
  for flag in --dry-run --force --uninstall; do
    "$DOM" "$fresh" --platform codex "$flag" >/dev/null 2>&1; rc=$?
    check "unknown namespace refused $flag" test "$rc" -eq 3
    check "unknown refusal has zero writes $flag" test "$before" = "$(treehash "$fresh")"
  done
}

# Current tests use the real standalone projection, never a native client.
copilot_consumer_fixture() {
  if [ "$2" = guest ]; then
    "$DOM" "$1" --platform copilot --guest
  else
    "$DOM" "$1" --platform copilot --no-guest
  fi
}

scenario_shared_consumers() {
  local mode t before rc
  for mode in normal guest; do
    t="$WORKROOT/shared-consumers-$mode"; mkdir -p "$t"; git_init "$t"
    check "$mode seed host visibility" python3 - "$t" <<'PY'
from pathlib import Path
import sys
root = Path(sys.argv[1])
p = root / ".agents/skills/dom-decompose/SKILL.md"
p.parent.mkdir(parents=True)
p.write_text("Pre-existing visible host skill\n")
exclude = root / ".git/info/exclude"
exclude.write_bytes(exclude.read_bytes() + b"\n# host-owned exact exclusion\nhost-private.txt\n")
PY
    if [ "$mode" = guest ]; then
      "$DOM" "$t" --platform codex --guest >/dev/null 2>&1
    else
      "$DOM" "$t" --platform codex >/dev/null 2>&1
    fi
    check "real Copilot consumer" copilot_consumer_fixture "$t" "$mode"
    before="$(treehash "$t/.agents")"
    "$DOM" "$t" --uninstall --platform codex >/dev/null 2>&1; rc=$?
    check "$mode scoped removal succeeds" test "$rc" -eq 0
    # Native Codex skills disappear, but shared bytes and pristine bases stay.
    check "$mode shared entry survives" test -f "$t/.agents/skills/dom-goal/SKILL.md"
    check "$mode shared base survives" test -f "$t/.agents/.domestique/base/.agents/skills/dom-goal/SKILL.md"
    if [ "$mode" = guest ]; then
      check "surviving guest remains hidden" git -C "$t" check-ignore -q .agents/skills/dom-goal/SKILL.md
    else
      check "normal shared ownership stays visible" bash -c '! git -C "$1" check-ignore -q .agents/skills/dom-goal/SKILL.md' _ "$t"
    fi
    local shared_before exclude_before
    shared_before="$(treehash "$t/.agents")"
    exclude_before="$(filehash "$t/.git/info/exclude")"
    check "$mode unrelated normal Claude install" "$DOM" "$t" --platform claude --no-guest
    check "$mode shared state byte-preserved" test "$shared_before" = "$(treehash "$t/.agents")"
    check "$mode exclusions byte-preserved" test "$exclude_before" = "$(filehash "$t/.git/info/exclude")"
    check "$mode normal Claude remains visible" bash -c '! git -C "$1" check-ignore -q .claude/commands/dom-goal.md' _ "$t"
    check "$mode host canonical leaf remains visible" bash -c '! git -C "$1" check-ignore -q .agents/skills/dom-decompose/SKILL.md' _ "$t"
    check "$mode no broad shared exclusions" bash -c '! grep -qxE "\\.agents/|\\.agents/skills/|\\.agents/skills/dom-goal/" "$1/.git/info/exclude"' _ "$t"
    check "$mode host exclude retained" grep -qxF 'host-private.txt' "$t/.git/info/exclude"
    if [ "$mode" = guest ]; then
      check "guest still hidden after normal install" git -C "$t" check-ignore -q .agents/skills/dom-goal/SKILL.md
    fi
    check "$mode remove unrelated Claude" "$DOM" "$t" --uninstall --platform claude
    # Rejoin while Copilot remains, then remove it through the real lifecycle.
    if [ "$mode" = guest ]; then
      "$DOM" "$t" --platform codex --guest >/dev/null 2>&1; rc=$?
    else
      "$DOM" "$t" --platform codex >/dev/null 2>&1; rc=$?
    fi
    check "$mode rejoin" test "$rc" -eq 0
    check "$mode shared/native tree restored exactly" test "$before" = "$(treehash "$t/.agents")"
    check "$mode remove Copilot consumer" "$DOM" "$t" --uninstall --platform copilot
    "$DOM" "$t" --uninstall --platform codex >/dev/null 2>&1; rc=$?
    check "$mode last-consumer uninstall" test "$rc" -eq 0
    check "$mode last-consumer removes shared state" test ! -e "$t/.agents/.domestique"
    check "$mode last-consumer removes shared entry" test ! -e "$t/.agents/skills/dom-goal/SKILL.md"
    check "$mode last-consumer preserves host entry" grep -qxF 'Pre-existing visible host skill' "$t/.agents/skills/dom-decompose/SKILL.md"
  done
}

scenario_shared_path_safety() {
  check "typed paths refuse without following links or changing any state" python3 - "$DOM" "$WORKROOT" "$REPO_DIR" <<'PY'
from pathlib import Path
import os
import subprocess
import sys

dom, work, repo = map(Path, sys.argv[1:])
old = work / "path-old.sh"
old.write_bytes(subprocess.check_output(["git", "-C", str(repo), "show", "64f4e09:domestique.sh"]))

def snapshot(root):
    result = {}
    for parent, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            p = Path(parent) / name
            s = p.lstat()
            data = os.readlink(p) if p.is_symlink() else p.read_bytes() if p.is_file() else None
            result[str(p.relative_to(root))] = (s.st_mode, s.st_nlink, s.st_mtime_ns, data)
    return result

def run(script, root, *args):
    return subprocess.run(["bash", str(script), str(root), *args], capture_output=True)

paths = [
    ".agents/skills/dom-goal",
    ".agents/skills/dom-goal/SKILL.md",
    ".agents/skills/dom-goal/agents/openai.yaml",
    ".agents/.domestique",
    ".agents/.domestique/manifest",
    ".agents/.domestique/mode",
    ".agents/.domestique/guest-excludes",
    ".agents/.domestique/base/.agents/skills/dom-goal/SKILL.md",
]
for i, rel in enumerate(paths):
    for kind in ("directory", "symlink", "hardlink", "file-ancestor"):
        root = work / f"path-safety-{i}-{kind}"
        root.mkdir()
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        # Existing valid state exercises uninstall and conversions; fresh state
        # also tests obstructions on paths that have never had a snapshot.
        if kind != "directory":
            assert run(dom, root, "--platform", "both", "--guest").returncode == 0
        victim = work / f"victim-{i}-{kind}"
        victim.mkdir()
        (victim / "SKILL.md").write_text("unowned external victim\n")
        p = root / rel
        if p.exists():
            p.rename(root / f"saved-{i}")
        p.parent.mkdir(parents=True, exist_ok=True)
        if kind == "directory":
            # For a directory path, a regular file obstructs its descendants.
            if rel in (paths[0], paths[3]):
                p.write_text("not a directory\n")
            else:
                p.mkdir()
        elif kind == "symlink":
            p.symlink_to(victim if rel in (paths[0], paths[3]) else victim / "SKILL.md")
        elif kind == "hardlink":
            os.link(victim / "SKILL.md", p)
        else:
            p.write_text("obstructed path\n")
            if rel not in (paths[0], paths[3]):
                # A regular file is safe at a file leaf; use its parent instead.
                p.unlink()
                p.parent.rename(root / f"saved-parent-{i}")
                p.parent.write_text("not a directory\n")
                p = p.parent
        before, external = snapshot(root), snapshot(victim)
        for flags in ([], ["--force"], ["--dry-run"], ["--force", "--dry-run"]):
            for action in (["--platform", "both", "--no-guest"],
                           ["--uninstall", "--platform", "codex"]):
                result = run(dom, root, *action, *flags)
                assert result.returncode == 3, (rel, kind, action, flags, result.stderr)
                assert snapshot(root) == before, (rel, kind, action, flags)
                assert snapshot(victim) == external
                assert p.lstat(), "unsafe path must itself survive"

# The old owner has no shared state yet: uninstall must still check ancestors.
root = work / "unsafe-legacy-uninstall"
root.mkdir()
assert run(old, root, "--platform", "codex", "--guest").returncode == 0
p = root / ".agents/skills/dom-goal"
p.rename(root / "saved-goal")
p.symlink_to(victim)
before, external = snapshot(root), snapshot(victim)
for flags in ([], ["--force"], ["--dry-run"], ["--force", "--dry-run"]):
    assert run(dom, root, "--uninstall", "--platform", "codex", *flags).returncode == 3
    assert snapshot(root) == before
    assert snapshot(victim) == external
PY
}

scenario_guest_old_root_policy() {
  check "old root policy guest transitions preserve or refuse before any writes" python3 - "$DOM" "$WORKROOT" "$REPO_DIR" <<'PY'
from pathlib import Path
import subprocess
import sys
dom, work, repo = map(Path, sys.argv[1:])
old = work / "policy-old.sh"
old.write_bytes(subprocess.check_output(["git", "-C", str(repo), "show", "64f4e09:domestique.sh"]))

def run(script, root, *args):
    return subprocess.run(["bash", str(script), str(root), *args], capture_output=True)

def snapshot(root):
    return {str(p.relative_to(root)): (p.stat().st_mode, p.stat().st_mtime_ns,
                                     p.read_bytes() if p.is_file() else None)
            for p in root.rglob("*")}

for platform in ("claude", "codex", "both"):
    for sticky in (False, True):
        root = work / f"old-policy-{platform}-{sticky}"
        root.mkdir()
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        policies = ["CLAUDE.md"] if platform == "claude" else ["AGENTS.md", "AGENTS.override.md"]
        if platform == "both":
            policies += ["CLAUDE.md"]
        for rel in policies:
            if rel == "AGENTS.override.md":
                continue
            (root / rel).write_text("Unrelated host instructions\n")
        assert run(old, root, "--platform", platform).returncode == 0
        # Real host override created AFTER the old installer. Keep the old
        # owned AGENTS.md and its authoritative snapshot completely intact.
        if platform != "claude":
            (root / "AGENTS.override.md").write_text("Unrelated host instructions\n")
        subprocess.run(["git", "-C", str(root), "add", *policies], check=True)
        if sticky:
            assert run(old, root, "--guest").returncode == 0
        before = snapshot(root)
        for flags in ([], ["--force"], ["--dry-run"], ["--force", "--dry-run"]):
            args = [] if sticky else ["--guest"]
            result = run(dom, root, *args, *flags)
            assert result.returncode == 3, result.stderr
            assert b"unguarded owned host policy" in result.stderr
            assert b"--no-guest" in result.stderr
            assert snapshot(root) == before
        result = run(dom, root, "--no-guest")
        assert result.returncode == 0, result.stderr
        guarded = {rel: (root / rel).read_bytes() for rel in policies}
        for args in (["--guest"], [], ["--guest", "--force"], ["--dry-run"]):
            result = run(dom, root, *args)
            assert result.returncode == 0, result.stderr
            assert {rel: (root / rel).read_bytes() for rel in policies} == guarded
        for rel, body in guarded.items():
            assert body.startswith(b"Unrelated host instructions\n")
            if b"BEGIN domestique" in body:
                assert b"Active harness boundary" in body
PY
}

scenario_retained_policy_upgrade() {
  check "all retained policies are scoped preserving old output and custom bytes" python3 - "$DOM" "$WORKROOT" "$REPO_DIR" <<'PY'
from pathlib import Path
import subprocess
import sys

dom, work, repo = map(Path, sys.argv[1:])
old = work / "retained-policy-old.sh"
old.write_bytes(subprocess.check_output(["git", "-C", str(repo), "show", "64f4e09:domestique.sh"]))

def run(script, root, *args):
    return subprocess.run(["bash", str(script), str(root), "--platform", "both", *args],
                          capture_output=True)

def snapshot(root):
    return {str(p.relative_to(root)): (p.stat().st_mode, p.stat().st_mtime_ns,
                                     p.read_bytes() if p.is_file() else None)
            for p in root.rglob("*")}

prefix = b"HOST prefix\n\n"
suffix = b"\nHOST suffix without final newline"
def seed(name, guest=False, override=False):
    root = work / name
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    rel = "CLAUDE.local.md" if guest else "CLAUDE.md"
    for p in (rel, "AGENTS.override.md" if override else "AGENTS.md"):
        (root / p).write_bytes(prefix)
    result = run(old, root, "--platform", "both", *(["--guest"] if guest else []))
    assert result.returncode == 0, result.stderr
    # Real host override creation/removal changes the active root. Never
    # sanitize away or copy an old owned block to manufacture ownership.
    if not guest and not override:
        (root / "AGENTS.override.md").write_bytes(prefix)
    for p in root.glob("*.md"):
        p.write_bytes(p.read_bytes() + suffix)
    return root

for guest in (False, True):
    for force in (False, True):
        root = seed(f"retained-normal-{guest}-{force}", guest)
        rels = ["CLAUDE.local.md"] if guest else ["CLAUDE.md", "AGENTS.md"]
        # A harmless in-block customization must survive, even with --force.
        for rel in rels:
            p = root / rel
            p.write_bytes(p.read_bytes().replace(b"## Discipline\n", b"## Discipline\nPersonal retained note.\n"))
        original = {rel: (root / rel).read_bytes() for rel in rels}
        before = snapshot(root)
        args = (["--no-guest"] if guest else []) + (["--force"] if force else [])
        result = run(dom, root, *args, "--dry-run")
        assert result.returncode == 0, result.stderr
        assert snapshot(root) == before
        result = run(dom, root, *args)
        assert result.returncode == 0, result.stderr
        for rel in rels:
            body = (root / rel).read_bytes()
            assert body.startswith(prefix) and body.endswith(suffix), rel
            assert b"Active harness boundary" in body, rel
            if b"Personal retained note." in original[rel]:
                assert b"Personal retained note." in body
            backups = list(root.glob(rel + ".bak.*"))
            assert any(p.read_bytes() == original[rel] for p in backups), rel
        if guest:
            body = (root / "CLAUDE.local.md").read_bytes()
            assert b"state is personal and stays local" in body
            assert b"no longer hidden" in result.stderr
            assert not (root / ".claude/.domestique/mode").exists()
        # Plain reruns must not rewrite either inactive guarded block or base.
        before = snapshot(root)
        result = run(dom, root)
        assert result.returncode == 0, result.stderr
        assert snapshot(root) == before

# Both active roots, inactive AGENTS and retained personal local policy need
# trustworthy ownership/merge proof. Conflicting custom text stays untouched,
# with no .new/backup/provider/mode/shared/exclusion writes even under --force.
for rel in ("CLAUDE.md", "CLAUDE.local.md", "AGENTS.md", "AGENTS.override.md"):
    for defect in ("conflict", "missing-base"):
        root = seed(f"retained-refusal-{rel}-{defect}", rel == "CLAUDE.local.md",
                    rel == "AGENTS.override.md")
        p = root / rel
        if defect == "conflict":
            body = p.read_bytes()
            # Replace the first old instruction, where the new guard is added.
            lines = body.splitlines(keepends=True)
            marker = next(i for i, line in enumerate(lines) if b"BEGIN domestique" in line)
            lines[marker + 1:] = [b"Entirely custom owned policy; do not discard.\n",
                                 *lines[next(i for i, line in enumerate(lines) if b"END domestique" in line):]]
            p.write_bytes(b"".join(lines))
        else:
            provider = "claude" if rel.startswith("CLAUDE") else "codex"
            (root / f".{provider}/.domestique/base/{rel}.block").unlink()
        before = snapshot(root)
        for flags in ([], ["--force"], ["--dry-run"], ["--force", "--dry-run"]):
            result = run(dom, root, "--no-guest", *flags)
            assert result.returncode == 3, (rel, defect, flags, result.stderr)
            assert rel.encode() in result.stderr and b"reconcile" in result.stderr
            assert snapshot(root) == before

# Personal tracked roots cannot be silently migrated in guest mode either.
root = seed("retained-tracked-personal", True)
subprocess.run(["git", "-C", str(root), "add", "-f", "CLAUDE.local.md"], check=True)
before = snapshot(root)
for flags in ([], ["--guest"], ["--force"], ["--dry-run"]):
    result = run(dom, root, *flags)
    assert result.returncode == 3, result.stderr
    assert b"--no-guest" in result.stderr
    assert snapshot(root) == before
assert run(dom, root, "--no-guest").returncode == 0
p = root / "CLAUDE.local.md"
p.write_bytes(p.read_bytes().replace(b"## Discipline\n", b"## Discipline\nPersonal tracked note.\n"))
body = p.read_bytes()
for flags in (["--guest"], [], ["--guest", "--force"], ["--dry-run"]):
    result = run(dom, root, *flags)
    assert result.returncode == 0, result.stderr
    assert p.read_bytes() == body
PY
}

scenario_shared_uncertain_survivor() {
  local t="$WORKROOT/uncertain-survivor" before flag rc
  mkdir -p "$t"; git_init "$t"
  check "guest install" "$DOM" "$t" --platform codex --guest
  check "real Copilot consumer" copilot_consumer_fixture "$t" guest
  check "remove Codex" "$DOM" "$t" --uninstall --platform codex
  # An invalid survivor must not be mistaken for no owner or a normal owner.
  check "invalidate fixture mode" python3 - "$t" <<'PY'
from pathlib import Path
import sys
(Path(sys.argv[1]) / ".github/.domestique/mode").write_text("uncertain\n")
PY
  before="$(treehash "$t")"
  for flag in --force --dry-run --uninstall; do
    "$DOM" "$t" --platform claude "$flag" >/dev/null 2>&1; rc=$?
    check "uncertain survivor refused $flag" test "$rc" -eq 3
    check "all state/excludes preserved $flag" test "$before" = "$(treehash "$t")"
    check "shared remains hidden $flag" git -C "$t" check-ignore -q .agents/skills/dom-goal/SKILL.md
  done
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
if [ "${1:-}" = "--current" ]; then
  run_scenario "cross-client public entries and unchanged-only removal" scenario_public_names
  run_scenario "public entry host collisions" scenario_public_name_host_collisions
  run_scenario "previous guest install gains public names" scenario_previous_install_adds_public_names
  run_scenario "Codex setup emitted protocol (static assertions)" scenario_codex_setup_protocol
  run_scenario "synthetic explicit TOML pair lifecycle (real installer)" scenario_codex_explicit_lifecycle
  run_scenario "synthetic inherited TOML pair guest lifecycle (real installer)" scenario_codex_inherit_guest_lifecycle
  run_scenario "installed shared routes and all foreign boundaries (normal/guest, static)" scenario_shared_routing_normal_and_guest
  run_scenario "legacy shared-base migration preserves native customization" scenario_shared_legacy_migration
  run_scenario "shared conflict/unknown namespace refuses before writes" scenario_shared_preflight_refusal
  run_scenario "shared last-consumer and guest visibility (real Copilot)" scenario_shared_consumers
  run_scenario "shared typed path and outside victim preservation" scenario_shared_path_safety
  run_scenario "guest old root policy preflight and guarded upgrades" scenario_guest_old_root_policy
  run_scenario "uncertain shared survivor cannot authorize exposure" scenario_shared_uncertain_survivor
  run_scenario "retained root-policy isolation and preserving conversion" scenario_retained_policy_upgrade
fi

echo
TOTAL=$((PASS_COUNT + FAIL_COUNT))
echo "$PASS_COUNT/$TOTAL passed"

if [ "$FAIL_COUNT" -gt 0 ]; then
  exit 1
fi
