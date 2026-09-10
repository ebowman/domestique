#!/usr/bin/env bash
# Focused payload tests. Emitters remain dormant until the Copilot installer
# projection is added; this harness extracts them without running main flow.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOM="$SCRIPT_DIR/../domestique.sh"
PASS=0
FAIL=0

check() {
  local description="$1"; shift
  if "$@"; then PASS=$((PASS + 1)); else
    echo "FAIL: $description" >&2; FAIL=$((FAIL + 1))
  fi
}

# emit <function>: execute just one embedded emitter definition, never the
# installer body. This checks payload text, not full YAML schema compliance.
emit() {
  local function="$1"
  { awk -v fn="$function" '$0 ~ "^" fn "\\(\\)" { inside=1 } inside { print } inside && /^}$/ { exit }' "$DOM"
    printf '%s\n' "$function"
  } | bash
}

emit_without_no_persistence() {
  { sed 's/Never persist choices to files, settings, beads, or memory\./Persist choices to files, settings, beads, or memory./' "$DOM" |
      awk -v fn="emit_copilot_skill" '$0 ~ "^" fn "\\(\\)" { inside=1 } inside { print } inside && /^}$/ { exit }'
    printf '%s\n' "emit_copilot_skill"
  } | bash
}

impl="$(emit emit_copilot_implementer)"
review="$(emit emit_copilot_reviewer)"
base="$(emit emit_copilot_skill)"
decompose="$(emit emit_copilot_decompose_skill)"
goal="$(emit emit_copilot_goal_skill)"
policy="$(emit emit_copilot_policy)"
base_without_no_persistence="$(emit_without_no_persistence)"

WORKROOT="$(mktemp -d)"
trap 'rm -rf "$WORKROOT"' EXIT

treehash() {
  ( cd "$1" && find . -type f -print | LC_ALL=C sort | while IFS= read -r f; do shasum -a 256 "$f"; done ) | shasum -a 256 | awk '{print $1}'
}

normal_install_checks() {
  local t="$WORKROOT/normal" rc
  mkdir -p "$t"
  bash "$DOM" "$t" --platform copilot >/dev/null 2>&1; rc=$?
  check "Copilot normal install exits 0" test "$rc" -eq 0
  check "Copilot agents installed" bash -c 'test -f "$1/.github/agents/domestique-implementer.agent.md" && test -f "$1/.github/agents/domestique-reviewer.agent.md"' _ "$t"
  check "Copilot skills installed" bash -c 'test -f "$1/.github/skills/domestique/SKILL.md" && test -f "$1/.github/skills/domestique-decompose/SKILL.md" && test -f "$1/.github/skills/domestique-goal/SKILL.md"' _ "$t"
  check "Copilot managed policy and state installed" bash -c 'grep -qF "BEGIN domestique (managed)" "$1/.github/copilot-instructions.md" && test -f "$1/.github/.domestique/manifest" && test -f "$1/.github/.domestique/base/.github/copilot-instructions.md.block"' _ "$t"
  check "Copilot-only creates no other provider artifacts" bash -c '! test -e "$1/CLAUDE.md" && ! test -e "$1/.claude" && ! test -e "$1/AGENTS.md" && ! test -e "$1/.codex" && ! test -e "$1/.agents"' _ "$t"
  check "Copilot state is canonical" bash -c 'test "$(cat "$1/.github/.domestique/platforms")" = copilot' _ "$t"
}

platform_and_provenance_checks() {
  local t="$WORKROOT/platforms" s spec sequence expected n
  mkdir -p "$t"
  bash "$DOM" "$t" --platform claude >/dev/null 2>&1
  bash "$DOM" "$t" --platform copilot >/dev/null 2>&1
  s="$(cat "$t/.github/.domestique/platforms")"
  check "additive Claude plus Copilot set" test "$s" = "claude,copilot"
  bash "$DOM" "$t" --platform codex >/dev/null 2>&1
  check "additive all set" test "$(cat "$t/.github/.domestique/platforms")" = all
  bash "$DOM" "$t" >/dev/null 2>&1
  check "bare rerun preserves all set" test "$(cat "$t/.github/.domestique/platforms")" = all
  check "all creates all provider policies" bash -c 'test -f "$1/CLAUDE.md" && test -f "$1/AGENTS.md" && test -f "$1/.github/copilot-instructions.md"' _ "$t"

  n=0
  for spec in \
    "claude:claude" "codex:codex" "both:both" "copilot:copilot" \
    "claude copilot:claude,copilot" "codex copilot:codex,copilot" "all:all"; do
    n=$((n + 1)); sequence="${spec%%:*}"; expected="${spec#*:}"
    local setdir="$WORKROOT/set-$n"; mkdir -p "$setdir"
    local selector
    for selector in $sequence; do bash "$DOM" "$setdir" --platform "$selector" >/dev/null 2>&1; done
    check "canonical persisted set $expected" test "$(cat "$setdir/.github/.domestique/platforms" 2>/dev/null || cat "$setdir/.claude/.domestique/platforms" 2>/dev/null || cat "$setdir/.codex/.domestique/platforms")" = "$expected"
  done

  local host="$WORKROOT/host"; mkdir -p "$host/.github/agents"
  emit emit_copilot_implementer > "$host/.github/agents/domestique-implementer.agent.md"
  printf 'host reviewer\n' > "$host/.github/agents/domestique-reviewer.agent.md"
  bash "$DOM" "$host" --platform copilot >/dev/null 2>&1
  check "identical preexisting leaf excluded from provenance" bash -c '! grep -qxF ".github/agents/domestique-implementer.agent.md" "$1/.github/.domestique/created-files"' _ "$host"
  check "adopted differing leaf excluded from provenance" bash -c '! grep -qxF ".github/agents/domestique-reviewer.agent.md" "$1/.github/.domestique/created-files"' _ "$host"
  check "created leaf recorded in provenance" grep -qxF ".github/skills/domestique/SKILL.md" "$host/.github/.domestique/created-files"
  bash "$DOM" "$host" >/dev/null 2>&1
  check "provenance survives bare rerun" bash -c '! grep -qxF ".github/agents/domestique-reviewer.agent.md" "$1/.github/.domestique/created-files" && grep -qxF ".github/skills/domestique/SKILL.md" "$1/.github/.domestique/created-files"' _ "$host"

  local created="$WORKROOT/policy-created"; mkdir -p "$created"
  bash "$DOM" "$created" --platform copilot >/dev/null 2>&1
  check "created policy recorded in provenance" grep -qxF ".github/copilot-instructions.md" "$created/.github/.domestique/created-files"
  local identical="$WORKROOT/policy-identical"; mkdir -p "$identical"
  bash "$DOM" "$identical" --platform copilot >/dev/null 2>&1
  rm -rf "$identical/.github/.domestique"
  bash "$DOM" "$identical" --platform copilot >/dev/null 2>&1; rc=$?
  check "identical preexisting policy install succeeds" test "$rc" -eq 0
  check "identical preexisting policy is not claimed" bash -c 'test -f "$1/.github/.domestique/created-files" && ! grep -qxF ".github/copilot-instructions.md" "$1/.github/.domestique/created-files"' _ "$identical"
}

reconciliation_and_guard_checks() {
  local t="$WORKROOT/reconcile" before after rc out
  mkdir -p "$t/.github"
  printf '# host text\n' > "$t/.github/copilot-instructions.md"
  bash "$DOM" "$t" --platform copilot >/dev/null 2>&1
  check "host instruction text survives managed block" grep -qxF '# host text' "$t/.github/copilot-instructions.md"
  before="$(treehash "$t")"
  bash "$DOM" "$t" --dry-run >/dev/null 2>&1; rc=$?
  after="$(treehash "$t")"
  check "Copilot dry run exits 0 and writes nothing" bash -c 'test "$1" -eq 0 && test "$2" = "$3"' _ "$rc" "$before" "$after"
  out="$(bash "$DOM" "$t" --guest 2>&1)"; rc=$?
  check "Copilot guest refusal is early and nonzero" bash -c 'test "$1" -ne 0 && grep -qi "Copilot guest" <<<"$2"' _ "$rc" "$out"
  check "guest refusal writes nothing" test "$before" = "$(treehash "$t")"
  out="$(bash "$DOM" "$t" --uninstall --platform copilot 2>&1)"; rc=$?
  check "Copilot uninstall refusal is early and nonzero" bash -c 'test "$1" -ne 0 && grep -qi "Copilot uninstall" <<<"$2"' _ "$rc" "$out"
  check "uninstall refusal writes nothing" test "$before" = "$(treehash "$t")"

  local marker="$WORKROOT/marker-only"; mkdir -p "$marker"
  bash "$DOM" "$marker" --platform copilot >/dev/null 2>&1
  rm -rf "$marker/.github/.domestique"
  before="$(treehash "$marker")"
  out="$(bash "$DOM" "$marker" --guest 2>&1)"; rc=$?
  check "marker-only Copilot bare guest refuses" bash -c 'test "$1" -ne 0 && grep -qi "Copilot guest" <<<"$2"' _ "$rc" "$out"
  check "marker-only guest refusal is byte-identical" test "$before" = "$(treehash "$marker")"
  out="$(bash "$DOM" "$marker" --platform both --guest 2>&1)"; rc=$?
  check "marker-only mixed guest refuses before Claude writes" bash -c 'test "$1" -ne 0 && grep -qi "Copilot guest" <<<"$2"' _ "$rc" "$out"
  check "marker-only mixed refusal is byte-identical" test "$before" = "$(treehash "$marker")"
  out="$(bash "$DOM" "$marker" --guest --dry-run 2>&1)"; rc=$?
  check "marker-only dry guest refuses without writes" bash -c 'test "$1" -ne 0 && test "$2" = "$3"' _ "$rc" "$before" "$(treehash "$marker")"

  local legacy="$WORKROOT/legacy"; mkdir -p "$legacy"
  bash "$DOM" "$legacy" --platform claude >/dev/null 2>&1
  rm -rf "$legacy/.claude/.domestique/base"
  sed -i '' 's/Runtime scope:/Legacy scope:/' "$legacy/CLAUDE.md"
  sed -i '' 's/This command is for Claude Code only./Legacy command scope./' "$legacy/.claude/commands/goal.md"
  before="$(treehash "$legacy")"
  out="$(bash "$DOM" "$legacy" --platform copilot 2>&1)"; rc=$?
  check "legacy unguarded Claude refuses Copilot enablement" bash -c 'test "$1" -ne 0 && grep -qi "authorization guards" <<<"$2"' _ "$rc" "$out"
  check "legacy guard refusal writes nothing" test "$before" = "$(treehash "$legacy")"

  local scoped="$WORKROOT/scoped-uninstall"; mkdir -p "$scoped"
  bash "$DOM" "$scoped" --platform all >/dev/null 2>&1
  printf 'guest\n' > "$scoped/.github/.domestique/mode"
  before="$(shasum -a 256 "$scoped/.github/copilot-instructions.md" | awk '{print $1}')"
  bash "$DOM" "$scoped" --uninstall --platform claude >/dev/null 2>&1; rc=$?
  check "scoped Claude uninstall retains guest Copilot" bash -c 'test "$1" -eq 0 && test -d "$2/.github/.domestique" && ! test -e "$2/.claude/.domestique" && test "$(cat "$2/.github/.domestique/platforms")" = codex,copilot' _ "$rc" "$scoped"
  check "scoped uninstall leaves Copilot policy bytes unchanged" test "$before" = "$(shasum -a 256 "$scoped/.github/copilot-instructions.md" | awk '{print $1}')"

  local u="$WORKROOT/updater"; mkdir -p "$u"
  out="$(bash "$SCRIPT_DIR/../update.sh" "$u" --source "$DOM" --platform copilot --dry-run 2>&1)"; rc=$?
  check "updater forwards Copilot preview selector" bash -c 'test "$1" -eq 0 && grep -q "platforms=copilot" <<<"$2" && ! test -e "$3/.github"' _ "$rc" "$out" "$u"
  out="$(bash "$SCRIPT_DIR/../update.sh" "$u" --source "$DOM" --platform copilot 2>&1)"; rc=$?
  check "updater applies Copilot selector after preview" bash -c 'test "$1" -eq 0 && test -f "$2/.github/copilot-instructions.md" && grep -q "Applying" <<<"$3"' _ "$rc" "$u" "$out"
}

compatibility_preflight_regressions() {
  local old="$WORKROOT/legacy-domestique.sh" current="$WORKROOT/current-guards" lost="$WORKROOT/lost-state" inactive="$WORKROOT/inactive-policy" mixed="$WORKROOT/mixed-policy" clean="$WORKROOT/clean-upgrade" before out rc
  git show 2896937:domestique.sh > "$old" && chmod +x "$old"

  # A first-line/prefix match is not a guard: every authoritative paragraph
  # must survive the projected reconciliation before Copilot can be created.
  mkdir -p "$current"
  bash "$DOM" "$current" --platform both >/dev/null 2>&1
  sed -i '' 's/\*\*Runtime scope:\*\*/Runtime scope:/' "$current/CLAUDE.md"
  sed -i '' 's/This command is for Claude Code only\./Runtime scope:/' "$current/.claude/commands/goal.md"
  sed -i '' 's/\*\*Runtime scope:\*\*/Runtime scope:/' "$current/AGENTS.md"
  sed -i '' 's/Runtime scope: this `\$domestique` skill/Runtime scope:/' "$current/.agents/skills/domestique/SKILL.md"
  sed -i '' 's/Runtime scope: this Codex skill/Runtime scope:/' "$current/.agents/skills/domestique-goal/SKILL.md"
  before="$(treehash "$current")"
  out="$(bash "$DOM" "$current" --platform copilot --dry-run 2>&1)"; rc=$?
  check "truncated guard dry-run preflight refuses" bash -c 'test "$1" -eq 1 && grep -q "complete runtime authorization guard" <<<"$2"' _ "$rc" "$out"
  check "truncated guard dry-run preflight is byte-identical" test "$before" = "$(treehash "$current")"
  out="$(bash "$DOM" "$current" --platform copilot 2>&1)"; rc=$?
  check "truncated managed guard paragraphs refuse Copilot" bash -c 'test "$1" -eq 1 && grep -q "complete runtime authorization guard" <<<"$2"' _ "$rc" "$out"
  check "truncated guard preflight is byte-identical" test "$before" = "$(treehash "$current")"

  mkdir -p "$lost"
  bash "$old" "$lost" --platform both >/dev/null 2>&1
  rm -rf "$lost/.claude/.domestique" "$lost/.codex/.domestique"
  before="$(treehash "$lost")"
  out="$(bash "$DOM" "$lost" --platform all 2>&1)"; rc=$?
  check "lost state does not adopt unguarded managed legacy policies" bash -c 'test "$1" -eq 1 && grep -q "CLAUDE.md" <<<"$2"' _ "$rc" "$out"
  check "lost-state refusal precedes Copilot writes" test "$before" = "$(treehash "$lost")"

  mkdir -p "$inactive"
  bash "$old" "$inactive" --platform codex >/dev/null 2>&1
  sed -i '' '/^<!-- END domestique -->$/d' "$inactive/AGENTS.md"
  check "inactive-policy fixture is missing its END marker" bash -c 'grep -qxF "<!-- BEGIN domestique (managed) -->" "$1" && ! grep -qxF "<!-- END domestique -->" "$1"' _ "$inactive/AGENTS.md"
  printf 'host override\n' > "$inactive/AGENTS.override.md"
  before="$(treehash "$inactive")"
  out="$(bash "$DOM" "$inactive" --platform copilot --force 2>&1)"; rc=$?
  check "force refuses malformed inactive owned Codex policy" bash -c 'test "$1" -eq 1 && grep -q "AGENTS.md" <<<"$2" && grep -q "inactive policy" <<<"$2" && ! test -e "$3/.github/copilot-instructions.md"' _ "$rc" "$out" "$inactive"
  check "malformed inactive-policy force refusal is byte-identical" test "$before" = "$(treehash "$inactive")"
  out="$(bash "$DOM" "$inactive" --platform copilot --force --dry-run 2>&1)"; rc=$?
  check "dry-run refuses malformed inactive owned Codex policy" bash -c 'test "$1" -eq 1 && grep -q "AGENTS.md" <<<"$2" && ! test -e "$3/.github/copilot-instructions.md"' _ "$rc" "$out" "$inactive"
  check "malformed inactive-policy dry-run refusal is byte-identical" test "$before" = "$(treehash "$inactive")"

  mkdir -p "$clean"
  bash "$old" "$clean" --platform both >/dev/null 2>&1
  bash "$DOM" "$clean" --platform all >/dev/null 2>&1; rc=$?
  check "clean legacy merge establishes guards before Copilot" bash -c 'test "$1" -eq 0 && test -f "$2/.github/copilot-instructions.md" && grep -qF "GitHub Copilot may read this file" "$2/CLAUDE.md" && grep -qF "GitHub Copilot may read this file" "$2/AGENTS.md"' _ "$rc" "$clean"

  mkdir -p "$mixed"
  printf 'unmanaged host AGENTS bytes\n' > "$mixed/AGENTS.md"
  printf 'host override\n' > "$mixed/AGENTS.override.md"
  bash "$DOM" "$mixed" --platform codex >/dev/null 2>&1
  before="$(shasum -a 256 "$mixed/AGENTS.md" | awk '{print $1}')"
  bash "$DOM" "$mixed" --platform copilot >/dev/null 2>&1; rc=$?
  check "guarded managed override ignores unmanaged host AGENTS" bash -c 'test "$1" -eq 0 && test -f "$2/.github/copilot-instructions.md" && test "$3" = "$(shasum -a 256 "$2/AGENTS.md" | awk '"'"'{print $1}'"'"')"' _ "$rc" "$mixed" "$before"
}

copilot_policy_merge_checks() {
  local v2="$WORKROOT/copilot-v2.sh" vplain="$WORKROOT/copilot-plain-v2.sh" clean="$WORKROOT/policy-clean" conflict="$WORKROOT/policy-conflict" adopt="$WORKROOT/policy-adopt" plain_adopt="$WORKROOT/plain-adopt" plain_clean="$WORKROOT/plain-clean" plain_conflict="$WORKROOT/plain-conflict" rc out live base backup
  cp "$DOM" "$v2"
  sed -i.orig 's/# Domestique orchestration policy (Copilot)/# Domestique orchestration policy (Copilot v2)/' "$v2"
  rm -f "$v2.orig"
  chmod +x "$v2"
  cp "$DOM" "$vplain"
  sed -i.orig 's/inventing semantics\./inventing semantics (Copilot v2)./' "$vplain"
  rm -f "$vplain.orig"
  chmod +x "$vplain"

  mkdir -p "$clean"
  bash "$DOM" "$clean" --platform copilot >/dev/null 2>&1
  sed -i.orig 's/Stop and report between tasks\./Stop and report between locally customized tasks./' "$clean/.github/copilot-instructions.md"
  rm -f "$clean/.github/copilot-instructions.md.orig"
  bash "$v2" "$clean" >/dev/null 2>&1; rc=$?
  check "Copilot policy clean merge preserves local and upstream edits" bash -c 'test "$1" -eq 0 && grep -qF "locally customized tasks" "$2/.github/copilot-instructions.md" && grep -qF "Copilot v2" "$2/.github/copilot-instructions.md"' _ "$rc" "$clean"

  mkdir -p "$conflict"
  bash "$DOM" "$conflict" --platform copilot >/dev/null 2>&1
  sed -i.orig 's/# Domestique orchestration policy (Copilot)/# locally customized Copilot policy/' "$conflict/.github/copilot-instructions.md"
  rm -f "$conflict/.github/copilot-instructions.md.orig"
  live="$(shasum -a 256 "$conflict/.github/copilot-instructions.md" | awk '{print $1}')"
  base="$(shasum -a 256 "$conflict/.github/.domestique/base/.github/copilot-instructions.md.block" | awk '{print $1}')"
  out="$(bash "$v2" "$conflict" 2>&1)"; rc=$?
  backup="$(find "$conflict/.github" -name 'copilot-instructions.md.bak.*' | head -1)"
  check "Copilot policy conflict preserves live base and backup bytes" bash -c 'test "$1" -eq 3 && test -f "$2/.github/copilot-instructions.md.new" && test "$3" = "$(shasum -a 256 "$2/.github/copilot-instructions.md" | awk '"'"'{print $1}'"'"')" && test "$4" = "$(shasum -a 256 "$2/.github/.domestique/base/.github/copilot-instructions.md.block" | awk '"'"'{print $1}'"'"')" && test "$3" = "$(shasum -a 256 "$5" | awk '"'"'{print $1}'"'"')" && grep -qF "Copilot v2" "$2/.github/copilot-instructions.md.new" && grep -qi conflict <<<"$6"' _ "$rc" "$conflict" "$live" "$base" "$backup" "$out"
  bash "$v2" "$conflict" --force >/dev/null 2>&1; rc=$?
  check "Copilot policy force resolves conflict with upstream" bash -c 'test "$1" -eq 0 && grep -qF "Copilot v2" "$2/.github/copilot-instructions.md"' _ "$rc" "$conflict"

  local update_conflict="$WORKROOT/update-conflict"; mkdir -p "$update_conflict"
  bash "$DOM" "$update_conflict" --platform copilot >/dev/null 2>&1
  sed -i.orig 's/# Domestique orchestration policy (Copilot)/# updater local Copilot policy/' "$update_conflict/.github/copilot-instructions.md"
  rm -f "$update_conflict/.github/copilot-instructions.md.orig"
  out="$(bash "$SCRIPT_DIR/../update.sh" "$update_conflict" --source "$v2" --platform copilot 2>&1)"; rc=$?
  check "updater propagates Copilot policy conflict exit 3" bash -c 'test "$1" -eq 3 && test -f "$2/.github/copilot-instructions.md.new" && grep -qi "conflicts" <<<"$3"' _ "$rc" "$update_conflict" "$out"

  mkdir -p "$adopt"
  bash "$DOM" "$adopt" --platform copilot >/dev/null 2>&1
  rm -rf "$adopt/.github/.domestique/base"
  sed -i.orig 's/Stop and report between tasks\./Stop and report between adopted local tasks./' "$adopt/.github/copilot-instructions.md"
  rm -f "$adopt/.github/copilot-instructions.md.orig"
  bash "$v2" "$adopt" >/dev/null 2>&1; rc=$?
  check "Copilot policy no-base adoption retains live content" bash -c 'test "$1" -eq 0 && grep -qF "adopted local tasks" "$2/.github/copilot-instructions.md" && ! grep -qF "Copilot v2" "$2/.github/copilot-instructions.md" && test -f "$2/.github/.domestique/base/.github/copilot-instructions.md.block"' _ "$rc" "$adopt"

  mkdir -p "$plain_adopt/.github/agents"
  printf 'host implementer bytes\n' > "$plain_adopt/.github/agents/domestique-implementer.agent.md"
  bash "$DOM" "$plain_adopt" --platform copilot >/dev/null 2>&1; rc=$?
  check "Copilot plain agent adoption retains host bytes and seeds base" bash -c 'test "$1" -eq 0 && test "$(cat "$2/.github/agents/domestique-implementer.agent.md")" = "host implementer bytes" && test -f "$2/.github/.domestique/base/.github/agents/domestique-implementer.agent.md"' _ "$rc" "$plain_adopt"

  mkdir -p "$plain_clean"
  bash "$DOM" "$plain_clean" --platform copilot >/dev/null 2>&1
  sed -i.orig 's/Follow the brief exactly;/Follow the locally customized brief exactly;/' "$plain_clean/.github/agents/domestique-implementer.agent.md"
  rm -f "$plain_clean/.github/agents/domestique-implementer.agent.md.orig"
  bash "$vplain" "$plain_clean" >/dev/null 2>&1; rc=$?
  check "Copilot plain agent nonoverlap merge retains local and upstream edits" bash -c 'test "$1" -eq 0 && grep -qF "locally customized brief" "$2/.github/agents/domestique-implementer.agent.md" && grep -qF "semantics (Copilot v2)" "$2/.github/agents/domestique-implementer.agent.md"' _ "$rc" "$plain_clean"

  mkdir -p "$plain_conflict"
  bash "$DOM" "$plain_conflict" --platform copilot >/dev/null 2>&1
  sed -i.orig 's/inventing semantics\./local conflicting report rule./' "$plain_conflict/.github/agents/domestique-implementer.agent.md"
  rm -f "$plain_conflict/.github/agents/domestique-implementer.agent.md.orig"
  live="$(shasum -a 256 "$plain_conflict/.github/agents/domestique-implementer.agent.md" | awk '{print $1}')"
  base="$(shasum -a 256 "$plain_conflict/.github/.domestique/base/.github/agents/domestique-implementer.agent.md" | awk '{print $1}')"
  out="$(bash "$vplain" "$plain_conflict" 2>&1)"; rc=$?
  backup="$(find "$plain_conflict/.github/agents" -name 'domestique-implementer.agent.md.bak.*' | head -1)"
  check "Copilot plain conflict preserves live base backup and writes upstream .new" bash -c 'test "$1" -eq 3 && test "$3" = "$(shasum -a 256 "$2/.github/agents/domestique-implementer.agent.md" | awk '"'"'{print $1}'"'"')" && test "$4" = "$(shasum -a 256 "$2/.github/.domestique/base/.github/agents/domestique-implementer.agent.md" | awk '"'"'{print $1}'"'"')" && test "$3" = "$(shasum -a 256 "$5" | awk '"'"'{print $1}'"'"')" && grep -qF "semantics (Copilot v2)" "$2/.github/agents/domestique-implementer.agent.md.new" && grep -qi conflict <<<"$6"' _ "$rc" "$plain_conflict" "$live" "$base" "$backup" "$out"
  bash "$vplain" "$plain_conflict" --force >/dev/null 2>&1; rc=$?
  check "Copilot plain force resolves conflict with upstream" bash -c 'test "$1" -eq 0 && grep -qF "semantics (Copilot v2)" "$2/.github/agents/domestique-implementer.agent.md"' _ "$rc" "$plain_conflict"
}

check "implementer native namespaced id" bash -c 'grep -qx "name: domestique-implementer" <<<"$1"' _ "$impl"
check "reviewer native namespaced id" bash -c 'grep -qx "name: domestique-reviewer" <<<"$1"' _ "$review"
check "agent descriptions present" bash -c 'grep -Eq "^description: .+" <<<"$1" && grep -Eq "^description: .+" <<<"$2"' _ "$impl" "$review"
check "agent tool arrays present" bash -c 'grep -Eq "^tools: \\[.+\\]$" <<<"$1" && grep -Eq "^tools: \\[.+\\]$" <<<"$2"' _ "$impl" "$review"
check "reviewer may test but cannot change" bash -c 'grep -qi "may execute tests" <<<"$1" && grep -qi "never edit" <<<"$1" && grep -qi "modify bead state" <<<"$1"' _ "$review"
check "no Copilot model pins" bash -c '! grep -Eqi "^(model|model_reasoning_effort):|model:[[:space:]]*(sonnet|opus|gpt)" <<<"$1$2"' _ "$impl" "$review"
check "agents do not autoapprove tools" bash -c '! grep -qi "allowed-tools" <<<"$1$2"' _ "$impl" "$review"

check "base skill supports normal dispatch" bash -c 'grep -q "highest-priority unblocked task" <<<"$1" && grep -q "stop and report before another task" <<<"$1"' _ "$base"
check "decompose loads base policy and is planning only" bash -c 'grep -qF ".github/skills/domestique/SKILL.md" <<<"$1" && grep -qi "If it is unavailable, stop" <<<"$1" && grep -qi "planning only" <<<"$1"' _ "$decompose"
check "goal is explicitly user invocable only" bash -c 'grep -qx "user-invocable: true" <<<"$1" && grep -qx "disable-model-invocation: true" <<<"$1" && grep -q "/domestique-goal <epic-id>" <<<"$1"' _ "$goal"
check "goal rejects native goal authorization and argument substitution" bash -c 'grep -Eq "native .*/goal.*or.*/autopilot" <<<"$1" && grep -qF "\$ARGUMENTS" <<<"$1"' _ "$goal"
check "goal loads base policy before effects and stops when missing" bash -c 'grep -qF "Before model selection, task dispatch, branch changes, or any other effect" <<<"$1" && grep -qF ".github/skills/domestique/SKILL.md" <<<"$1" && grep -qF "If it is unavailable, stop and report" <<<"$1"' _ "$goal"
check "goal enforces workflow invariants" bash -c 'grep -q "clean worktree" <<<"$1" && grep -q "non-default" <<<"$1" && grep -q "blocked, open" <<<"$1" && grep -q "in_progress unfinished" <<<"$1" && grep -qF "Allow at most one corrective" <<<"$1" && grep -qF "implementer pass and one re-review per bead." <<<"$1" && grep -q "15 closed beads" <<<"$1" && grep -q "never push or merge" <<<"$1"' _ "$goal"
check "goal requires full suite and real diff before close or commit" bash -c 'grep -qF "Before each bead is closed or committed" <<<"$1" && grep -qF "independent reviewer must inspect the real diff" <<<"$1" && grep -qF "project suite. A full-suite regression stops immediately" <<<"$1" && grep -qF "never deferred" <<<"$1" && grep -qF "to epic completion" <<<"$1"' _ "$goal"
check "fingerprints fail visible untracked reviewer changes" bash -c 'grep -qF "nonignored untracked files (names and content)" <<<"$1" && grep -qF "including a change to visible untracked source or test files" <<<"$1" && grep -qF "affected new visible files" <<<"$1"' _ "$goal"
check "base has explicit ephemeral model policy and precedence" bash -c 'grep -qF "do not add a per-call override" <<<"$1" && grep -qF "/model" <<<"$1" && grep -qF "controls the parent session" <<<"$1" && grep -qF "/subagents" <<<"$1" && grep -qF "persistent" <<<"$1" && grep -qF "personal settings" <<<"$1" && grep -qF "explicit per-call user choice" <<<"$1" && grep -qF "native user subagent settings" <<<"$1" && grep -qF "agent definition" <<<"$1" && grep -qF "parent session" <<<"$1" && grep -qF "state the requested role-to-model mapping and pass those explicit" <<<"$1" && grep -qF "per-call model arguments" <<<"$1"' _ "$base"
check "base prohibits persistence of model choices" bash -c 'grep -qF "Never persist choices to files, settings, beads, or memory." <<<"$1"' _ "$base"
check "no-persistence assertion rejects in-memory reversed mutation" bash -c '! grep -qF "Never persist choices to files, settings, beads, or memory." <<<"$1"' _ "$base_without_no_persistence"
check "incompatible or failed requested model stops without substitution" bash -c 'grep -qF "incomplete vendor restriction must not invent a model" <<<"$1" && grep -qF "stop for clarification" <<<"$1" && grep -qF "If a requested model fails or is" <<<"$1" && grep -qF "unavailable, stop and report" <<<"$1" && grep -qF "never deliberately substitute another model or" <<<"$1" && grep -qF "vendor. Copilot fallback" <<<"$1"' _ "$base"
check "normal and guest landing are explicit" bash -c 'grep -qF "In normal mode," <<<"$1" && grep -qF "landing files loose discovered work as beads" <<<"$1" && grep -qF "bd export -o .beads/issues.jsonl" <<<"$1" && grep -qF "commits only authorized intended" <<<"$1" && grep -qF "artifacts while preserving unrelated work" <<<"$1" && grep -qF "personal state" <<<"$1" && grep -qF "is never staged or committed" <<<"$1"' _ "$base"
check "guest marker overrides retained normal policy" bash -c 'grep -qF ".github/.domestique/mode" <<<"$1" && grep -qF "exactly" <<<"$1" && grep -qF "guest mode, even when a" <<<"$1" && grep -qF "normal managed" <<<"$1" && grep -qF ".github/copilot-instructions.md" <<<"$1" && grep -qF "policy is retained from a" <<<"$1" && grep -qF "normal-to-guest conversion" <<<"$1" && grep -qF "When the marker is absent, normal landing is permitted only" <<<"$1"' _ "$base"
check "guest skills and policy are self-contained" bash -c 'grep -qi "guest.*personal state" <<<"$1" && grep -q "complete workflow.*guest.*model-selection" <<<"$2"' _ "$base" "$policy"

normal_install_checks
platform_and_provenance_checks
reconciliation_and_guard_checks
compatibility_preflight_regressions
copilot_policy_merge_checks

echo "$PASS/$((PASS + FAIL)) passed"
[ "$FAIL" -eq 0 ]
