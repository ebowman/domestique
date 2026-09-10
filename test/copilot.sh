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

echo "$PASS/$((PASS + FAIL)) passed"
[ "$FAIL" -eq 0 ]
