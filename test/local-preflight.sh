#!/usr/bin/env bash
# Executable internal-local API tests; no native client, network, or real HOME.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
DOM="$ROOT/domestique.sh"
WORK="$(mktemp -d)"; WORK="$(cd "$WORK" && pwd -P)"
trap 'rm -rf "$WORK"' EXIT
mkdir "$WORK/home" "$WORK/tmp" "$WORK/forbidden"
export HOME="$WORK/home" TMPDIR="$WORK/tmp" DOMESTIQUE_HOME="$WORK/core"
unset XDG_STATE_HOME
for name in bd curl wget claude codex copilot; do
  printf '#!/usr/bin/env bash\nexit 99\n' > "$WORK/forbidden/$name"
  chmod +x "$WORK/forbidden/$name"
done
export PATH="$WORK/forbidden:$PATH"
EXTRACT="$WORK/definitions.sh"
awk '/^usage\(\)/ { exit } { print }' "$DOM" > "$EXTRACT"
# shellcheck source=/dev/null
source "$EXTRACT"
set +e
PASS=0 FAIL=0 N=0
check() {
  local label="$1"; shift
  if "$@"; then PASS=$((PASS + 1))
  else printf 'FAIL: %s\n%s\n' "$label" "${OUTPUT:-}" >&2; FAIL=$((FAIL + 1)); fi
}
tree() {
  python3 - "$WORK" <<'PY'
import hashlib,os,pathlib,stat,sys
r=pathlib.Path(sys.argv[1]); h=hashlib.sha256()
for p in [r,*sorted(r.rglob("*"))]:
    s=p.lstat(); h.update(repr((str(p.relative_to(r)),s.st_mode)).encode())
    if stat.S_ISREG(s.st_mode): h.update(p.read_bytes()); h.update(str(s.st_mtime_ns).encode())
    elif stat.S_ISLNK(s.st_mode): h.update(os.readlink(p).encode())
print(h.hexdigest())
PY
}
fixture() {
  N=$((N + 1)); R="$WORK/repo$N"
  mkdir "$R"
  git -C "$R" init -q
}
call() { OUTPUT="$("$@" 2>&1)"; RC=$?; }
refuse() {
  local label="$1" before; shift
  before="$(tree)"
  call "$@"
  check "$label refuses" test "$RC" -ne 0
  check "$label zero changes incl index/exclude/home/core" test "$before" = "$(tree)"
  check "$label actionable" bash -c '[[ "$1" == *"manually"* ]]' _ "$OUTPUT"
}
owned() {
  local selection="$1" key provider role path digest
  mkdir -p "$R/.domestique-private"
  {
    printf 'format=1\nscope=local\nworktree_root=%s\ncore_root=%s\ncore_api=1\nproviders=%s\n' "$R" "$DOMESTIQUE_HOME" "$selection"
    while IFS= read -r key; do
      provider="${key%%:*}"
      local_selected "$selection" "$provider" || continue
      path="$R/${key#*:}"; mkdir -p "${path%/*}"
      case "$path" in *implementer*) role=implementer;; *) role=reviewer;; esac
      "emit_private_${provider}_agent" local "$role" "$DOMESTIQUE_HOME" > "$path"
      digest="$(global_hash < "$path")"
      printf 'created=%s:%s\nbaseline=%s:%s\n' "$key" "$digest" "$key" "$digest"
    done < <(local_inventory)
  } > "$R/.domestique-private/manifest"
}
legacy() {
  # Production emitters, snapshot and immutable created-file formats. No bd.
  bash "$DOM" --platform "$1" "$R" >/dev/null 2>&1
}
call bash "$DOM" --global --platform codex
check 'isolated real core installed' test "$RC" = 0
fixture
before="$(tree)"
call local_preflight "$R" all
check 'fresh all-provider preflight' test "$RC" = 0
check 'fresh read-only identity' test "$before" = "$(tree)"
call bash -c 'source "$1"; local_preflight "$2" codex; [[ "$L_RELEASE" == r-* && ${#L_RELEASE} == 66 ]]' _ "$EXTRACT" "$R"
check 'preflight binds actual strict core identity' test "$RC" = 0
refuse 'fresh apply cannot pretend profiles installed' local_exclude_apply "$R" all
mkdir "$R/sub"
refuse 'subdir' local_preflight "$R/sub" claude
refuse 'missing target' local_preflight "$R/missing" claude
mkdir "$WORK/notgit"
refuse 'non-Git' local_preflight "$WORK/notgit" claude
ln -s "$R" "$WORK/link"
refuse 'symlink target' local_preflight "$WORK/link" claude
refuse 'symlink parent with dotdot' local_preflight "$WORK/link/../repo$N" claude
for odd in 'equals=root' $'newline\nroot'; do
  mkdir "$WORK/$odd"; git -C "$WORK/$odd" init -q
  refuse 'unserializable physical root' local_preflight "$WORK/$odd" claude
done
fixture
printf 'host policy\n' > "$R/CLAUDE.md"
printf 'host Codex policy\n' > "$R/AGENTS.md"
mkdir "$R/.github"; printf 'host instructions\n' > "$R/.github/copilot-instructions.md"
call local_preflight "$R" claude
check 'unmarked host policies allowed' test "$RC" = 0
for marker in '<!-- BEGIN domestique (managed) -->' '<!-- END domestique -->' 'prefix <!-- BEGIN domestique (managed) -->'; do
  printf '%s\n' "$marker" > "$R/CLAUDE.md"
  refuse 'malformed root marker' local_migrate "$R" claude
done
fixture
owned all
call local_preflight "$R" none
check 'valid all-provider owned manifest' test "$RC" = 0
before="$(tree)"
call local_exclude_apply "$R" none 1
check 'owned exclude dry-run' test "$RC" = 0
check 'owned dry-run identity' test "$before" = "$(tree)"
call local_exclude_apply "$R" none
check 'exact exclusions apply' test "$RC" = 0
check 'owned leaves ignored' git -C "$R" check-ignore -q .claude/agents/domestique-claude-local-implementer.md
mkdir -p "$R/.beads"
printf 'host\n' > "$R/.claude/host.md"
check 'provider host visible' bash -c '! git -C "$1" check-ignore -q .claude/host.md' _ "$R"
check 'Beads root not hidden' bash -c '! git -C "$1" check-ignore -q .beads/host' _ "$R"
check 'no broad provider patterns' bash -c '! grep -xE "/?\\.(claude|codex|github|beads)/" "$1/.git/info/exclude"' _ "$R"
before="$(tree)"
call local_exclude_apply "$R" none
check 'exact exclude no-op' test "$RC" = 0
check 'exclude no-op identity' test "$before" = "$(tree)"
printf 'inline-secret-edited\n' >> "$R/.codex/agents/domestique-codex-local-reviewer.toml"
export FORCE=1
refuse 'edited owned force cannot bypass' local_preflight "$R" all
fixture
owned none
call local_preflight "$R" none
check 'providers none retained state' test "$RC" = 0
fixture
owned claude
leaf="$R/.claude/agents/domestique-claude-local-implementer.md"
git -C "$R" add -f "$leaf"
refuse 'indexed owned leaf' local_preflight "$R" claude
rm "$leaf"
refuse 'indexed but missing leaf' local_preflight "$R" claude
fixture
owned claude
rm "$R/.domestique-private/manifest"
refuse 'missing manifest with destinations' local_preflight "$R" claude
fixture
owned codex
rm -rf "$R/.domestique-private"
refuse 'preexisting identical native bytes not owned' local_preflight "$R" codex
fixture
mkdir -p "$R/.claude/agents/domestique-claude-local-reviewer.md"
refuse 'unknown directory destination' local_preflight "$R" all
fixture
mkdir "$R/.claude"; ln -s "$WORK/home" "$R/.claude/agents"
refuse 'provider parent symlink' local_preflight "$R" all
for corruption in hash traversal duplicate baseline newline unknown nul identity; do
  fixture; owned claude
  python3 - "$R/.domestique-private/manifest" "$corruption" <<'PY'
import pathlib,sys
p=pathlib.Path(sys.argv[1]); s=p.read_text(); kind=sys.argv[2]
if kind=="hash": s=s.replace("created=claude:", "created=claude:",1); s=s.replace(s.splitlines()[6].rsplit(":",1)[1],"invalid")
if kind=="traversal": s=s.replace(".claude/agents/", "../agents/")
if kind=="duplicate": s+="\n".join(s.splitlines()[6:8])+"\n"
if kind=="baseline": s="\n".join(x for x in s.splitlines() if not x.startswith("created="))+"\n"
if kind=="newline": s=s.rstrip("\n")
if kind=="unknown": s+="beads_path=../../host\n"
if kind=="nul": s=s.replace("format=1", "format=\x001")
if kind=="identity": s=s.replace("worktree_root=", "worktree_root=/wrong",1)
p.write_text(s)
PY
  refuse "manifest $corruption" local_preflight "$R" claude
done
fixture; owned claude
ln -s "$WORK/home" "$R/.domestique-private/routing"
refuse 'private state symlink' local_preflight "$R" claude
fixture; owned claude
# Explicit mode-bit denial simulation works even with privileged host tests.
refuse 'permission denial simulated and triggered' bash -c '
source "$1"
global_stat() {
  if [ "$1" = "$DENIED" ]; then printf "%s 000\n" "$(id -u)"
  elif [ "$(uname -s)" = Darwin ]; then stat -f "%u %Lp" "$1"
  else stat -c "%u %a" "$1"; fi
}
export DENIED="$2/.domestique-private/manifest"
local_preflight "$2" claude
' _ "$EXTRACT" "$R"
check 'permission hook actually triggered' bash -c '[[ "$1" == *"owner read/write"* ]]' _ "$OUTPUT"
fixture
DOMESTIQUE_HOME="$WORK/missing-core" refuse 'local never installs missing global core' local_preflight "$R" claude
active="$(cat "$DOMESTIQUE_HOME/active")"
printf 'release=bad\n' > "$DOMESTIQUE_HOME/active"
refuse 'corrupt global active fails strict resolver' local_preflight "$R" claude
printf '%s\n' "$active" > "$DOMESTIQUE_HOME/active"
fixture; owned claude
mkdir "$R/.domestique-private/routing"
{
  printf 'format=1\nworktree_root=%s\nprovider=claude\ncore_root=%s\ncore_api=1\n' "$R" "$DOMESTIQUE_HOME"
  printf 'role=domestique-claude-local-implementer\nrole=domestique-claude-local-reviewer\n'
} > "$R/.domestique-private/routing/claude.receipt"
call local_preflight "$R" none
check 'valid bounded receipt accepted' test "$RC" = 0
printf 'role=unknown\n' >> "$R/.domestique-private/routing/claude.receipt"
refuse 'corrupt routing receipt' local_preflight "$R" claude

# Real legacy main Codex and draft #11 Copilot, not fabricated provenance.
fixture; check 'main-layout Codex fixture' legacy codex
refuse 'legacy normal requires opt-in' local_preflight "$R" codex
refuse 'Codex root policy lacks whole-leaf creation authority' local_migrate "$R" codex
fixture
printf 'host normal policy\n' > "$R/AGENTS.md"
call bash "$DOM" --platform codex --guest "$R"
check 'actual main guest fixture' test "$RC" = 0
refuse 'guest authority blocks implicit local install' local_preflight "$R" codex
before="$(tree)"
call local_migrate "$R" codex 1
check 'exact-rule guest migration preview' test "$RC" = 0
check 'guest migration dry-run identity' test "$before" = "$(tree)"
excludehash="$(global_hash < "$R/.git/info/exclude")"
call local_migrate "$R" codex
check 'proven main guest migration' test "$RC" = 0
check 'guest only created leaf removed' test ! -e "$R/.codex/agents/implementer.toml"
check 'host normal policy retained' grep -qxF 'host normal policy' "$R/AGENTS.md"
check 'old exact exclusions retained without adopting' test "$excludehash" = "$(global_hash < "$R/.git/info/exclude")"
fixture
call bash "$DOM" --guest "$R"
check 'actual Claude guest fixture' test "$RC" = 0
refuse 'Claude snapshots are not creation provenance' local_migrate "$R" claude
fixture; check 'draft-layout Copilot fixture' legacy copilot
before="$(tree)"
call local_migrate "$R" copilot 1
check 'Copilot migration dry-run' test "$RC" = 0
check 'migration preview identity' test "$before" = "$(tree)"
policyhash="$(global_hash < "$R/.github/.domestique/base/.github/copilot-instructions.md.block")"
call local_migrate "$R" copilot
check 'proven unchanged Copilot migration' test "$RC" = 0
check 'owned whole policy removed' test ! -e "$R/.github/copilot-instructions.md"
check 'owned agent removed' test ! -e "$R/.github/agents/domestique-implementer.agent.md"
check 'legacy recovery baseline retained unchanged' test "$policyhash" = "$(global_hash < "$R/.github/.domestique/base/.github/copilot-instructions.md.block")"
fixture; legacy copilot; legacy claude
refuse 'mixed legacy preflights all before cleanup' local_migrate "$R" all
fixture; owned claude; legacy copilot
nativehash="$(global_hash < "$R/.claude/agents/domestique-claude-local-reviewer.md")"
call local_migrate "$R" all
check 'valid mixed private and legacy migration' test "$RC" = 0
check 'mixed migration preserves private owned leaves' test "$nativehash" = "$(global_hash < "$R/.claude/agents/domestique-claude-local-reviewer.md")"
fixture; legacy copilot
printf '%s\n' "$MARKER_BEGIN" >> "$R/.github/.domestique/base/.github/copilot-instructions.md.block"
{
  printf '%s\n' "$MARKER_BEGIN"
  cat "$R/.github/.domestique/base/.github/copilot-instructions.md.block"
  printf '%s\n' "$MARKER_END"
} > "$R/.github/copilot-instructions.md"
refuse 'malformed root markers even when snapshot matches' local_migrate "$R" copilot
fixture
mkdir -p "$R/.github/agents"
emit_copilot_reviewer > "$R/.github/agents/domestique-reviewer.agent.md"
legacy copilot
refuse 'real adopted identical legacy leaf never owned' local_migrate "$R" copilot
fixture; legacy copilot
printf 'host text\n' >> "$R/.github/copilot-instructions.md"
refuse 'whole policy host text retained' local_migrate "$R" copilot
fixture; legacy copilot
printf 'secret edit\n' >> "$R/.github/agents/domestique-reviewer.agent.md"
refuse 'edited legacy blocks whole migration' local_migrate "$R" copilot
fixture; legacy copilot
printf 'bogus\n' > "$R/.github/.domestique/mode"
refuse 'corrupt mode never normal fallback' local_migrate "$R" copilot
fixture; legacy copilot
printf '../outside\n' >> "$R/.github/.domestique/created-files"
refuse 'legacy traversal provenance' local_migrate "$R" copilot
fixture; legacy copilot
git -C "$R" add .github/agents/domestique-reviewer.agent.md
refuse 'tracked legacy blocks cleanup' local_migrate "$R" copilot
fixture; legacy copilot
refuse 'injected removal fails honestly' bash -c '
source "$1"
rm() { printf "INJECTED removal failure\n" >&2; return 75; }
local_migrate "$2" copilot
' _ "$EXTRACT" "$R"
check 'removal injection triggered and PARTIAL' bash -c '[[ "$1" == *INJECTED* && "$1" == *PARTIAL* ]]' _ "$OUTPUT"
fixture; legacy copilot
call bash -c '
source "$1"
count=0
rm() {
  count=$((count + 1))
  if [ "$count" = 2 ]; then printf "INJECTED second removal\n" >&2; return 75; fi
  command rm "$@"
}
local_migrate "$2" copilot
' _ "$EXTRACT" "$R"
check 'mid-migration failure triggered and non-success' test "$RC" -ne 0
check 'mid-migration reports PARTIAL' bash -c '[[ "$1" == *"INJECTED second"* && "$1" == *PARTIAL* ]]' _ "$OUTPUT"
check 'completed owned deletion not disguised as rollback' test ! -e "$R/.github/agents/domestique-implementer.agent.md"
check 'uncompleted owned deletion remains' test -f "$R/.github/agents/domestique-reviewer.agent.md"

fixture; owned claude
git -C "$R" -c user.name=Test -c user.email=test@example.invalid commit -q --allow-empty -m fixture
W2="$WORK/worktree2"
git -C "$R" worktree add -q -b second "$W2"
R1="$R"; R="$W2"; owned claude; R="$R1"
call local_exclude_apply "$R" claude
check 'two same-path owned worktrees allowed' test "$RC" = 0
check 'other attachment stays private' git -C "$W2" check-ignore -q .domestique-private/manifest
printf '# host custom rule\n/visible-host\n' >> "$R/.git/info/exclude"
call local_exclude_apply "$R" claude
check 'unknown existing exclude rules preserved' test "$RC" = 0
check 'host custom rule remains' grep -qxF /visible-host "$R/.git/info/exclude"
rm -rf "$W2/.domestique-private"
refuse 'other same-path host collision' local_exclude_apply "$R" claude
rm -rf "$W2/.claude"
mkdir "$W2/.domestique-private"
refuse 'shared missing manifest' local_preflight "$R" claude
rm -rf "$W2/.domestique-private"
printf '# END domestique private\n' >> "$R/.git/info/exclude"
refuse 'malformed shared exclude block' local_preflight "$R" claude
fixture
printf '# BEGIN domestique (managed)\n.claude/\n.beads/\n# END domestique\n' >> "$R/.git/info/exclude"
refuse 'legacy broad exclusions require manual recovery accounting' local_preflight "$R" claude
fixture
printf '# BEGIN domestique private (format=1)\n/.domestique-private/\n# END domestique private\n' >> "$R/.git/info/exclude"
refuse 'shared patterns missing all ownership state' local_preflight "$R" claude
check 'literal Git metacharacter escaping' test "$(local_pattern 'a[*?]\ space/leaf')" = '/a\[\*\?\]\\\ space/leaf'
fixture
local_pattern 'a[*?]\ space/leaf' >> "$R/.git/info/exclude"
check 'Git actually matches literal metacharacters' git -C "$R" check-ignore -q 'a[*?]\ space/leaf'
check 'Git does not hide glob-like host sibling' bash -c '! git -C "$1" check-ignore -q "ab space/leaf"' _ "$R"
refuse 'worktree enumeration failure' bash -c '
source "$1"
git() {
  if [ "${3:-}" = worktree ]; then printf "INJECTED enumeration failure\n" >&2; return 76; fi
  command git "$@"
}
local_preflight "$2" claude
' _ "$EXTRACT" "$R"
check 'enumeration failure actually triggered' bash -c '[[ "$1" == *"INJECTED enumeration"* ]]' _ "$OUTPUT"
fixture
printf '!/.domestique-private/\n!/.domestique-private/manifest\n' > "$R/.gitignore"
refuse 'host negation overrides shared info exclude' local_preflight "$R" claude
fixture
mkdir -p "$R/.claude/agents"
printf '!domestique-claude-local-implementer.md\n' > "$R/.claude/agents/.gitignore"
refuse 'nested host negation blocks planned native exclusion' local_preflight "$R" claude

# Review regressions: raw NUL must never become creation authority or rewritten
# host text, and a deleted working file does not remove its index object.
fixture; legacy copilot
python3 - "$R/.github/.domestique/created-files" <<'PY'
import pathlib,sys
p=pathlib.Path(sys.argv[1])
p.write_bytes(p.read_bytes().replace(b".github/copilot-instructions.md\n",
                                    b".github/copilot-instructions.md\0INVALID\n"))
PY
refuse 'NUL legacy policy creation evidence' local_migrate "$R" copilot
check 'NUL provenance preserves root policy' test -f "$R/.github/copilot-instructions.md"
fixture; owned none
printf '/host\0pattern\n' > "$R/.git/info/exclude"
refuse 'NUL host exclude bytes' local_exclude_apply "$R" none
fixture
printf 'host file\n' > "$R/.claude"
git -C "$R" add .claude
rm "$R/.claude"
refuse 'indexed deleted regular native ancestor' local_preflight "$R" claude
check 'indexed ancestor diagnostic names exact path' bash -c '[[ "$1" == *"$2/.claude;"* ]]' _ "$OUTPUT" "$R"

# Exercise every reused line-parser boundary without disclosing corrupt bytes.
for field in created-files manifest platforms mode; do
  for corruption in nul no-lf; do
    fixture
    if [ "$field" = mode ]; then
      test_provider=codex; state_prefix=.codex
      call bash "$DOM" --platform codex --guest "$R"
    else
      test_provider=copilot; state_prefix=.github
      call bash "$DOM" --platform copilot "$R"
    fi
    check "legacy fixture for $field $corruption" test "$RC" = 0
    python3 - "$R/$state_prefix/.domestique/$field" "$corruption" <<'PY'
import pathlib,sys
p=pathlib.Path(sys.argv[1]); data=p.read_bytes()
if sys.argv[2] == "nul":
    data=data.replace(b"\n", b"\0INVALID\n", 1)
else:
    data=data.rstrip(b"\n")
p.write_bytes(data)
PY
    refuse "legacy $field $corruption dry-run force" local_migrate "$R" "$test_provider" 1
    check 'corrupt content not disclosed' bash -c '[[ "$1" != *INVALID* ]]' _ "$OUTPUT"
  done
done
fixture
call bash "$DOM" --platform codex --guest "$R"
check 'Codex raw provenance fixture' test "$RC" = 0
python3 - "$R/.codex/.domestique/guest-excludes" <<'PY'
import pathlib,sys
p=pathlib.Path(sys.argv[1])
p.write_bytes(p.read_bytes().replace(b".codex/.domestique/\n",
                                    b".codex/.domestique/\0INVALID\n"))
PY
refuse 'NUL Codex ignored metadata provenance entry' local_migrate "$R" codex
fixture; legacy copilot
python3 - "$R/.github/copilot-instructions.md" <<'PY'
import pathlib,sys
p=pathlib.Path(sys.argv[1]); p.write_bytes(p.read_bytes()+b"\0INVALID\n")
PY
refuse 'NUL policy marker input' local_migrate "$R" copilot
fixture; owned none
for bytes in '/host-without-LF' $'# BEGIN domestique private (format=1)\n/.domestique-private/\n# END domestique private'; do
  printf '%s' "$bytes" > "$R/.git/info/exclude"
  refuse 'unterminated shared exclude' local_exclude_apply "$R" none
done
printf '# BEGIN domestique private (format=1)\0INVALID\n/.domestique-private/\n# END domestique private\n' > "$R/.git/info/exclude"
refuse 'NUL exclude marker dry-run force' local_exclude_apply "$R" none 1
python3 - "$R/.git/info/exclude" <<'PY'
import pathlib,sys
# All non-NUL bytes, including CR, tabs, non-UTF8 and trailing blank lines:
# host text outside managed blocks is opaque, not normalized.
pathlib.Path(sys.argv[1]).write_bytes(b"/host"+bytes(range(1,256))+b"\n\n")
PY
call local_exclude_apply "$R" none
check 'non-NUL host bytes remain supported' test "$RC" = 0
check 'exact host byte prefix preserved' python3 - "$R/.git/info/exclude" <<'PY'
import pathlib,sys
host=b"/host"+bytes(range(1,256))+b"\n\n"
block=b"# BEGIN domestique private (format=1)\n/.domestique-private/\n# END domestique private\n"
assert pathlib.Path(sys.argv[1]).read_bytes() == host+block
PY
before="$(tree)"
call local_exclude_apply "$R" none
check 'arbitrary host byte no-op succeeds' test "$RC" = 0
check 'arbitrary host byte no-op identity' test "$before" = "$(tree)"

# The local API must validate raw global input before reusing global parsers.
for field in state/global-manifest active; do
  saved="$(python3 - "$DOMESTIQUE_HOME/$field" <<'PY'
import pathlib,sys
print(pathlib.Path(sys.argv[1]).read_bytes().hex())
PY
)"
  python3 - "$DOMESTIQUE_HOME/$field" <<'PY'
import pathlib,sys
p=pathlib.Path(sys.argv[1]); p.write_bytes(p.read_bytes().replace(b"\n", b"\0INVALID\n", 1))
PY
  refuse "NUL reused global $field" local_preflight "$R" none
  python3 - "$DOMESTIQUE_HOME/$field" "$saved" <<'PY'
import pathlib,sys
pathlib.Path(sys.argv[1]).write_bytes(bytes.fromhex(sys.argv[2]))
PY
done

# All planned provider/state parents, and legacy-only parents. Force remains
# enabled from above. Deleting disk objects never authorizes their index paths.
for ancestor in .claude/agents .codex .codex/agents .github .github/agents \
  .domestique-private .agents .agents/skills .agents/skills/domestique \
  .github/skills .github/.domestique .codex/.domestique .claude/.domestique; do
  fixture
  mkdir -p "$R/$(dirname "$ancestor")"
  printf 'host file\n' > "$R/$ancestor"
  git -C "$R" add "$ancestor"
  rm "$R/$ancestor"
  refuse "indexed missing $ancestor" local_migrate "$R" all 1
  check 'ancestor diagnostic exact' bash -c '[[ "$1" == *"$2;"* ]]' _ "$OUTPUT" "$R/$ancestor"
done
for kind in symlink gitlink; do
  fixture
  if [ "$kind" = symlink ]; then
    ln -s "$WORK/home" "$R/.claude"
    git -C "$R" add .claude
    rm "$R/.claude"
  else
    git -C "$R" -c user.name=Test -c user.email=test@example.invalid commit -q --allow-empty -m fixture
    git -C "$R" update-index --add --cacheinfo "160000,$(git -C "$R" rev-parse HEAD),.claude"
  fi
  refuse "indexed missing $kind ancestor" local_preflight "$R" claude
done
fixture; owned all
for parent in .claude/agents .codex/agents .github/agents .agents/skills/domestique; do
  mkdir -p "$R/$parent"
  printf 'tracked host\n' > "$R/$parent/host"
  git -C "$R" add "$parent/host"
done
before="$(tree)"
call local_preflight "$R" all
check 'tracked siblings in native and legacy parents allowed' test "$RC" = 0
check 'tracked siblings preflight unchanged' test "$before" = "$(tree)"
fixture
mkdir "$R/literal[ab]" "$R/literala"
printf 'host\n' > "$R/literala/leaf"
git -C "$R" add literala/leaf
call local_untracked "$R" 'literal[ab]/leaf'
check 'index pathspec not a glob' test "$RC" = 0
printf 'host\n' > "$R/literal[ab]/host"
git -C "$R" add ':(literal)literal[ab]/host'
call local_untracked "$R" 'literal[ab]/leaf'
check 'literal parent tracked contents allowed' test "$RC" = 0
printf 'host\n' > "$R/literal[ab]/block"
git -C "$R" add ':(literal)literal[ab]/block'
rm "$R/literal[ab]/block"
refuse 'literal indexed ancestor object' local_untracked "$R" 'literal[ab]/block/leaf'

# A candidate exclusion must check ancestor objects in OTHER worktree indexes.
for ancestor in .claude .codex/agents .github/agents .domestique-private; do
  fixture; owned all
  git -C "$R" -c user.name=Test -c user.email=test@example.invalid commit -q --allow-empty -m fixture
  W2="$WORK/index-worktree$N"
  git -C "$R" worktree add -q -b second "$W2"
  mkdir -p "$W2/$(dirname "$ancestor")"
  printf 'other host\n' > "$W2/$ancestor"
  git -C "$W2" add "$ancestor"
  rm "$W2/$ancestor"
  refuse "shared indexed ancestor $ancestor" local_exclude_apply "$R" all
  check 'shared diagnostic names other worktree ancestor' bash -c '[[ "$1" == *"$2;"* ]]' _ "$OUTPUT" "$W2/$ancestor"
done
fixture
refuse 'truncated worktree enumeration' bash -c '
source "$1"
git() {
  if [ "${3:-}" = worktree ]; then printf "worktree %s" "$2"; return 0; fi
  command git "$@"
}
local_preflight "$2" claude
' _ "$EXTRACT" "$R"
printf 'local preflight: %s passed, %s failed\n' "$PASS" "$FAIL"
[ "$FAIL" = 0 ]
