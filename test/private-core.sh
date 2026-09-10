#!/usr/bin/env bash
# Focused Core API 1 renderer/resolver coverage; native discovery is .8 work.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOM="$ROOT/domestique.sh"
PASS=0 FAIL=0
check() { local d="$1"; shift; if "$@"; then PASS=$((PASS + 1)); else printf 'FAIL: %s\n' "$d" >&2; FAIL=$((FAIL + 1)); fi; }
WORK="$(mktemp -d)"; WORK="$(cd "$WORK" && pwd -P)"; trap 'rm -rf "$WORK"' EXIT

EXTRACT="$WORK/emitter-definitions.sh"
awk '/^usage\(\)/ { exit } { print }' "$DOM" > "$EXTRACT"
# shellcheck source=/dev/null
source "$EXTRACT"
set +e
emit_private_core_resolver > "$WORK/resolve-core"; chmod +x "$WORK/resolve-core"
hash() { shasum -a 256 < "$1" | awk '{print $1}'; }
treehash() { (cd "$1" && find . -print | LC_ALL=C sort | while IFS= read -r p; do [ -f "$p" ] && { printf '%s ' "$p"; hash "$p"; }; done) | shasum -a 256 | awk '{print $1}'; }
make_release() {
  local root="$1" tag="$2" p rel
  mkdir -p "$root/releases/.stage/roles"
  for p in goal implementer orchestrator reviewer; do printf '%s:%s\n' "$tag" "$p" > "$root/releases/.stage/roles/$p.md"; done
  for p in goal implementer orchestrator reviewer; do hash "$root/releases/.stage/roles/$p.md" | awk -v p="roles/$p.md" '{print $1 "  " p}'; done > "$root/releases/.stage/SHA256SUMS"
  rel="r-$(hash "$root/releases/.stage/SHA256SUMS")"
  printf 'format=1\ncore_api=1\nrelease=%s\n' "$rel" > "$root/releases/.stage/API"
  mv "$root/releases/.stage" "$root/releases/$rel"; printf '%s\n' "$rel"
}
run() { "$WORK/resolve-core" "$@" >"$WORK/out" 2>"$WORK/err"; RUN_RC=$?; RUN_OUT="$(<"$WORK/out")"; RUN_ERR="$(<"$WORK/err")"; }
core="$WORK/core"; mkdir -p "$core/releases"; r1="$(make_release "$core" one)"; printf 'release=%s\n' "$r1" > "$core/active"
before="$(treehash "$core")"
run bind "$core" implementer
after="$(treehash "$core")"
check "valid bind stdout is release" bash -c 'test "$1" -eq 0 && test "$2" = "$3"' _ "$RUN_RC" "$RUN_OUT" "$r1"
check "valid resolver performs no writes" test "$before" = "$after"
run read "$core" implementer "$r1"
check "valid bound read returns role" bash -c 'test "$1" -eq 0 && test "$2" = one:implementer' _ "$RUN_RC" "$RUN_OUT"
r2="$(make_release "$core" two)"; printf 'release=%s\n' "$r2" > "$core/active"
run read "$core" implementer "$r1"
check "bound release ignores active change" bash -c 'test "$1" -eq 0 && test "$2" = one:implementer' _ "$RUN_RC" "$RUN_OUT"
run bind "$core" implementer "$r1"
check "explicit bound bind is valid" bash -c 'test "$1" -eq 0 && test "$2" = "$3"' _ "$RUN_RC" "$RUN_OUT" "$r1"
run bind "$core" implementer ""
check "explicit empty binding rejects without active fallback" bash -c 'test "$1" -ne 0 && test -z "$2" && test -n "$3"' _ "$RUN_RC" "$RUN_OUT" "$RUN_ERR"

reject() {
  local name="$1" change="$2" c before after
  c="$WORK/$name"; cp -R "$core" "$c"; "$change" "$c"
  before="$(treehash "$c")"; run bind "$c" implementer; after="$(treehash "$c")"
  check "$name rejects with empty stdout" bash -c 'test "$1" -ne 0 && test -z "$2" && grep -q "^domestique core:" <<<"$3"' _ "$RUN_RC" "$RUN_OUT" "$RUN_ERR"
  check "$name performs no writes" test "$before" = "$after"
  case "$name" in
    api-*|release-hash-mismatch)
      run read "$c" implementer "$(sed 's/^release=//' "$c/active")"
      check "$name bound read rejects with empty stdout" bash -c 'test "$1" -ne 0 && test -z "$2"' _ "$RUN_RC" "$RUN_OUT"
      ;;
  esac
}
run bind relative implementer
check "relative root rejects with empty stdout" bash -c 'test "$1" -ne 0 && test -z "$2"' _ "$RUN_RC" "$RUN_OUT"
bad_active() { printf 'release=bad\n' > "$1/active"; }
missing_role() { rm "$1/releases/$r2/roles/reviewer.md"; }
bad_bound() { rm "$1/releases/$r1/roles/implementer.md"; }
bad_sum() { printf 'bad\n' > "$1/releases/$r2/SHA256SUMS"; }
bad_api_order() { printf 'core_api=1\nformat=1\nrelease=%s\n' "$r2" > "$1/releases/$r2/API"; }
bad_api_unknown() { printf 'format=1\ncore_api=1\nrelease=%s\nunknown=1\n' "$r2" > "$1/releases/$r2/API"; }
bad_api_extra() { printf 'format=1\ncore_api=1\nrelease=%s\n\n' "$r2" > "$1/releases/$r2/API"; }
bad_api_version() { printf 'format=1\ncore_api=2\nrelease=%s\n' "$r2" > "$1/releases/$r2/API"; }
bad_api_newline() { printf 'format=1\ncore_api=1\nrelease=%s' "$r2" > "$1/releases/$r2/API"; }
bad_release_hash() {
  local fake
  fake="r-$(printf '%064d' 0)"
  mv "$1/releases/$r2" "$1/releases/$fake"
  printf 'format=1\ncore_api=1\nrelease=%s\n' "$fake" > "$1/releases/$fake/API"
  printf 'release=%s\n' "$fake" > "$1/active"
}
reject bad-active bad_active
reject missing-role missing_role
reject bad-sums bad_sum
reject api-order bad_api_order
reject api-unknown-key bad_api_unknown
reject api-extra-line bad_api_extra
reject api-version bad_api_version
reject api-missing-newline bad_api_newline
reject release-hash-mismatch bad_release_hash
c="$WORK/missing-bound"; cp -R "$core" "$c"; bad_bound "$c"; run read "$c" implementer "$r1"
check "missing bound resource rejects empty stdout" bash -c 'test "$1" -ne 0 && test -z "$2"' _ "$RUN_RC" "$RUN_OUT"
rm -rf "$c/releases/$r1"
run bind "$c" implementer "$r1"
check "removed bound release bind rejects without active fallback" bash -c 'test "$1" -ne 0 && test -z "$2"' _ "$RUN_RC" "$RUN_OUT"
run read "$c" implementer "$r1"
check "removed bound release read rejects empty stdout" bash -c 'test "$1" -ne 0 && test -z "$2"' _ "$RUN_RC" "$RUN_OUT"
# Inject effective -r denial only in an isolated helper shell. No fixture or
# host permissions/ACLs are changed; this tests the unreadability branch.
for resource in API SHA256SUMS roles/implementer.md; do
  for op in bind read; do
    check "$op rejects simulated unreadable $resource with empty stdout" python3 -c '
import subprocess,sys
script = """function [() {
  if builtin [ "$#" -eq 3 ] && builtin [ "$1" = -r ] && builtin [ "$2" = "$DENIED" ]; then return 1; fi
  builtin [ "$@"
}
source "$1" "$2" "$3" implementer "$4"
"""
import os
env = dict(os.environ, DENIED=sys.argv[4])
p = subprocess.run(["bash", "-c", script, "--", *sys.argv[1:4], sys.argv[5]], env=env, capture_output=True)
assert p.returncode != 0 and p.stdout == b"" and b"unreadable" in p.stderr, p
' "$WORK/resolve-core" "$op" "$core" "$core/releases/$r1/$resource" "$r1"
  done
done
mkdir "$WORK/real"; ln -s "$WORK/real" "$WORK/symlink-root"; mkdir -p "$WORK/real/releases"
run bind "$WORK/symlink-root" implementer
check "symlinked ancestor rejects" bash -c 'test "$1" -ne 0 && test -z "$2"' _ "$RUN_RC" "$RUN_OUT"
quoted="$WORK/root space'\"\"\"\\backslash"; mkdir -p "$quoted/releases"; qr="$(make_release "$quoted" quoted)"; printf 'release=%s\n' "$qr" > "$quoted/active"
run bind "$quoted" reviewer
check "literal single/triple quote and backslash root binds" bash -c 'test "$1" -eq 0 && test "$2" = "$3"' _ "$RUN_RC" "$RUN_OUT" "$qr"
qb="$(make_release "$quoted" newer)"
printf 'release=%s\n' "$qb" > "$quoted/active"
mkdir "$quoted/bin"; cp "$WORK/resolve-core" "$quoted/bin/resolve-core"

for provider in claude codex copilot; do
  for role in implementer reviewer; do
    body="$(emit_private_${provider}_agent global "$role" "$quoted")"
    check "$provider adapter calls helper" grep -qF "/bin/resolve-core bind" <<<"$body"
    check "$provider adapter has exact global ID" grep -q "domestique-$provider-$role" <<<"$body"
    local_body="$(emit_private_${provider}_agent local "$role" "$quoted")"
    check "$provider adapter has exact local ID" grep -q "domestique-$provider-local-$role" <<<"$local_body"
    check "$provider adapter has runtime guard" grep -q "Runtime guard: act only when Provider is $provider" <<<"$body"
    check "$provider adapter states receipt routing" grep -q ".domestique-private/routing/$provider.receipt" <<<"$body"
    for scope in global local; do
      emit_private_"${provider}"_agent "$scope" "$role" "$quoted" > "$WORK/adapter"
      check "$provider $scope $role executes serialized fenced commands" python3 "$ROOT/test/private-core-commands.py" "$WORK/adapter" "$provider" "$role" "$quoted" "$qr" "$qb"
    done
  done
  for suffix in '' -decompose -goal; do
    skill="$(emit_private_${provider}_skill "$suffix" "$quoted")"
    check "$provider skill has runtime guard" grep -q "Runtime guard: act only when Provider is $provider" <<<"$skill"
    check "$provider skill has no global dispatch directive" bash -c '! grep -q "Dispatch only" <<<"$1"' _ "$skill"
    emit_private_"${provider}"_skill "$suffix" "$quoted" > "$WORK/adapter"
    skill_role=orchestrator; [ "$suffix" = -goal ] && skill_role=goal
    check "$provider $suffix skill executes fenced bootstrap and bound continuation" python3 "$ROOT/test/private-core-commands.py" "$WORK/adapter" markdown "$skill_role" "$quoted" "$qr" "$qb"
  done
done
goal="$(emit_private_claude_skill -goal "$quoted")"
check "Claude goal is explicit-only" bash -c 'grep -qx "user-invocable: true" <<<"$1" && grep -qx "disable-model-invocation: true" <<<"$1"' _ "$goal"
check "Codex goal metadata policy occurs once" bash -c 'test "$(grep -c "allow_implicit_invocation: false" <<<"$1")" -eq 1' _ "$(emit_private_codex_goal_metadata)"
copilot_goal="$(emit_private_copilot_skill -goal "$quoted")"
check "Copilot goal remains explicit-only" bash -c 'grep -qx "user-invocable: true" <<<"$1" && grep -qx "disable-model-invocation: true" <<<"$1"' _ "$copilot_goal"
orchestrator="$(emit_private_core_orchestrator)"
check "core states native model and unavailable-request policy" bash -c 'grep -q "native Anthropic" <<<"$1" && grep -q "native OpenAI" <<<"$1" && grep -q "available or stop" <<<"$1"' _ "$orchestrator"
check "new shared core exact routing and model contract" python3 -c '
import sys
s = sys.argv[1]
flat = " ".join(s.split())
for phrase in [
    "git rev-parse --show-toplevel", "pwd -P",
    "<physical-worktree-root>/.domestique-private/routing/<provider>.receipt",
    "LF-terminated key=value lines, in this exact order: format=1 worktree_root=<absolute physical Git worktree root> provider=<wrapper Provider> core_root=<wrapper core_root> core_api=1 role=<exact local implementer or reviewer ID>",
    "Repeat only role, once per installed implementer/reviewer",
    "readable non-symlinked receipt", "exact wrapper provider/core_root and core_api=1",
    "Reject unknown or missing fields, extra lines, duplicate singleton fields (including conflicting duplicates), duplicate roles",
    "Choose global-only or local-required separately for implementer and reviewer",
    "valid receipt listing the requested role or native adapter evidence for that requested local role makes it local-required",
    "present unreadable/broken receipt is local evidence: STOP",
    "no local intent or receipt/adapter evidence for that role, choose global-only",
    "receipt listing only one role does not require the other role to be local",
    "exact native ID discovery after the client",
    "project/server trust", "unavailable read/shell means STOP, never global fallback",
    "map stays fixed: mid-run receipt/adapter disappearance or changed required evidence means STOP",
    "Orchestrator and goal are core loads in the current session, never subagent IDs",
    "Pass the same verified DOMESTIQUE_BOUND_RELEASE field",
    "explicit ephemeral per-call/session role/model/vendor request",
    "state the requested role-to-model mapping and pass the explicit native per-call arguments",
    "never persist it to files, settings, beads, or memory",
    "Native client precedence still applies",
    "Copilot has no Domestique pin",
    "Copilot runtime may fall back if the requested model or effort is unavailable.",
    "stop/no-substitution instruction is not hard vendor or billing enforcement; avoid Auto when vendor selection matters."
]:
    assert phrase in flat, phrase
for provider in ("claude", "codex", "copilot"):
    for role in ("implementer", "reviewer"):
        assert f"| {provider} | {role} | domestique-{provider}-{role} | domestique-{provider}-local-{role} |" in s
' "$orchestrator"
toml="$WORK/agent.toml"; emit_private_codex_agent global implementer "$quoted" > "$toml"
check "Codex TOML parses and preserves literal root" python3 -c 'import pathlib,sys,tomllib; d=tomllib.loads(pathlib.Path(sys.argv[1]).read_text()); assert sys.argv[2] in d["developer_instructions"]' "$toml" "$quoted"
echo "private-core: $PASS passed, $FAIL failed"
exit "$FAIL"
