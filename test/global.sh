#!/usr/bin/env bash
# Native global lifecycle tests: no network, client invocation, or real HOME.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
DOM="$ROOT/domestique.sh"
UP="$ROOT/update.sh"
WORK="$(mktemp -d)"; WORK="$(cd "$WORK" && pwd -P)"
trap 'rm -rf "$WORK"' EXIT
mkdir "$WORK/never-call"
for forbidden in curl wget bd claude codex copilot; do
  printf '#!/usr/bin/env bash\nprintf "forbidden runtime call\\n" >&2\nexit 99\n' > "$WORK/never-call/$forbidden"
  chmod +x "$WORK/never-call/$forbidden"
done
export PATH="$WORK/never-call:$PATH"
PASS=0 FAIL=0 N=0
check() {
  local label="$1"; shift
  if "$@"; then PASS=$((PASS + 1))
  else printf 'FAIL: %s\n' "$label" >&2; FAIL=$((FAIL + 1)); fi
}
fixture() {
  N=$((N + 1)); F="$WORK/f$N"
  mkdir -p "$F/home" "$F/tmp" "$F/cwd" "$F/repo1" "$F/repo2"
  export HOME="$F/home" TMPDIR="$F/tmp" XDG_STATE_HOME="$F/state"
  unset DOMESTIQUE_HOME
  CORE="$XDG_STATE_HOME/domestique"
  for r in repo1 repo2; do
    git -C "$F/$r" init -q
    printf 'untouched local metadata\n' > "$F/$r/CLAUDE.local.md"
    mkdir "$F/$r/.domestique-private"
    printf 'custom local profile\n' > "$F/$r/.domestique-private/manifest"
  done
}
run() {
  (cd "$F/cwd" && bash "$@") > "$F/out" 2> "$F/err"
  RC=$?
}
# Include directories, regular bytes, symlink targets, modes and file mtimes.
# Directory mtimes excluded: transient staging must not alter leaf metadata.
tree() {
  python3 - "$@" <<'PY'
import hashlib,os,pathlib,stat,sys
h=hashlib.sha256()
for name in sys.argv[1:]:
    root=pathlib.Path(name)
    if not root.exists():
        h.update(b"absent"); continue
    for p in [root,*sorted(root.rglob("*"))]:
        s=p.lstat()
        h.update(repr((str(p.relative_to(root)),s.st_mode)).encode())
        if stat.S_ISREG(s.st_mode):
            h.update(str(s.st_mtime_ns).encode()); h.update(p.read_bytes())
        elif stat.S_ISLNK(s.st_mode): h.update(os.readlink(p).encode())
print(h.hexdigest())
PY
}
native_inventory() {
  python3 - "$HOME" "$CORE" "$1" <<'PY'
import pathlib,sys
h,c=map(pathlib.Path,sys.argv[1:3]); selection=sys.argv[3]
sets={"claude":["claude"],"codex":["codex"],"copilot":["copilot"],
      "both":["claude","codex"],"claude-copilot":["claude","copilot"],
      "codex-copilot":["codex","copilot"],"all":["claude","codex","copilot"]}
expected=set()
for p in sets[selection]:
    skill=".agents" if p=="codex" else "."+p
    ext={"claude":"md","codex":"toml","copilot":"agent.md"}[p]
    for suffix in ("","-decompose","-goal"):
        expected.add(f"{skill}/skills/domestique-{p}{suffix}/SKILL.md")
    for role in ("implementer","reviewer"):
        expected.add(f".{p}/agents/domestique-{p}-{role}.{ext}")
    if p=="codex": expected.add(".agents/skills/domestique-codex-goal/agents/openai.yaml")
actual={str(p.relative_to(h)) for p in h.rglob("*") if p.is_file()}
assert actual==expected,(actual-expected,expected-actual)
lines=(c/"state/global-manifest").read_text().splitlines()
assert lines[:5]==["format=1","scope=global",f"core_root={c}","core_api=1",f"providers={selection}"]
assert sum(x.startswith("created=") for x in lines)==len(expected)+8
assert sum(x.startswith("baseline=") for x in lines)==len(expected)+8
r=(c/"active").read_text().strip().removeprefix("release=")
assert {str(p.relative_to(c/"releases"/r)) for p in (c/"releases"/r).rglob("*") if p.is_file()}=={
    "API","SHA256SUMS",*[f"roles/{r}.md" for r in ("orchestrator","goal","implementer","reviewer")]}
PY
}
refusal() {
  local label="$1"; shift
  local before after
  before="$(tree "$HOME" "$CORE" "$F/repo1" "$F/repo2")"
  run "$@"
  check "$label refuses" test "$RC" -ne 0
  after="$(tree "$HOME" "$CORE" "$F/repo1" "$F/repo2")"
  check "$label writes nothing" test "$before" = "$after"
}

# Each canonical set is accepted explicitly and reused by a bare rerun.
for selection in claude codex copilot both claude-copilot codex-copilot all; do
  fixture
  before="$(tree "$HOME" "$CORE")"
  run "$DOM" --global --platform "$selection" --dry-run
  check "$selection fresh dry-run" test "$RC" -eq 0
  check "$selection dry-run absent roots unchanged" test "$before" = "$(tree "$HOME" "$CORE")"
  run "$DOM" --global --platform "$selection"
  check "$selection fresh install" test "$RC" -eq 0
  check "$selection exact inventory and manifest" native_inventory "$selection"
  before="$(tree "$HOME" "$CORE")"
  run "$DOM" --global
  check "$selection bare persists" test "$RC" -eq 0
  check "$selection exact no-op" test "$before" = "$(tree "$HOME" "$CORE")"
done

fixture
run "$DOM" --global
check "fresh global defaults Claude" native_inventory claude
for selection in copilot codex; do
  run "$DOM" --global --platform "$selection"
  check "add $selection" test "$RC" -eq 0
done
check "additive union is all" native_inventory all
active="$(sed 's/^release=//' "$CORE/active")"
for role in orchestrator goal implementer reviewer; do
  run "$CORE/bin/resolve-core" bind "$CORE" "$role"
  check "actual helper bind $role" test "$(cat "$F/out")" = "$active"
  run "$CORE/bin/resolve-core" read "$CORE" "$role" "$active"
  check "actual helper read $role" cmp -s "$F/out" "$CORE/releases/$active/roles/$role.md"
done
run "$CORE/bin/resolve-core" bind "$CORE" goal ""
check "empty explicit binding fails" test "$RC" -ne 0
check "empty binding stdout empty" test ! -s "$F/out"

# Global operations from two unrelated worktrees leave all project and host
# instructions/settings untouched. Native clients are never launched.
for p in .claude .codex .copilot; do
  printf 'host instructions\n' > "$HOME/$p/AGENTS.md"
  printf 'host settings\n' > "$HOME/$p/settings.json"
done
printf 'host instruction\n' > "$HOME/CLAUDE.md"
before="$(tree "$HOME" "$F/repo1" "$F/repo2")"
for r in repo1 repo2; do
  (cd "$F/$r" && bash "$DOM" --global) > "$F/out" 2> "$F/err"
  check "global from $r" test "$?" -eq 0
done
check "both repos and global host files untouched" test "$before" = "$(tree "$HOME" "$F/repo1" "$F/repo2")"

# Source-only version fixture: never copy any user-native input to a baseline.
V2="$WORK/v2.sh"
python3 - "$DOM" "$V2" <<'PY'
import pathlib,sys
s=pathlib.Path(sys.argv[1]).read_text()
s=s.replace("# Domestique private core: reviewer", "# Domestique private core: reviewer v2")
s=s.replace("description: Provider-qualified Domestique $scope $role adapter.",
            "description: Provider-qualified Domestique $scope $role adapter v2.")
pathlib.Path(sys.argv[2]).write_text(s)
PY
old_release="$active"; before="$(tree "$CORE/releases/$old_release" "$F/repo1" "$F/repo2")"
run "$V2" --global
check "global refresh succeeds" test "$RC" -eq 0
active="$(sed 's/^release=//' "$CORE/active")"
check "refresh changes active release" test "$old_release" != "$active"
check "old release and local metadata untouched" test "$before" = "$(tree "$CORE/releases/$old_release" "$F/repo1" "$F/repo2")"
check "refresh clears journal" test ! -e "$CORE/state/pending"
run "$CORE/bin/resolve-core" bind "$CORE" orchestrator
check "refresh new active validates" test "$RC" -eq 0
check "refresh unbound helper selects new release" test "$(cat "$F/out")" = "$active"
run "$CORE/bin/resolve-core" read "$CORE" reviewer "$old_release"
check "bound old release remains usable" test "$RC" -eq 0
run "$V2" --global --dry-run
check "refresh dry-run" test "$RC" -eq 0

# Unknown files are collisions regardless of matching renderer bytes or force.
for content in identical different; do
  fixture
  run "$DOM" --global --platform all
  if [ "$content" = different ]; then printf 'host custom\n' > "$HOME/.claude/agents/domestique-claude-reviewer.md"; fi
  rm -rf "$CORE"
  refusal "$content unknown all force" "$DOM" --global --platform all --force
done
fixture
mkdir -p "$HOME/.copilot/agents"
printf 'unowned last-provider collision\n' > "$HOME/.copilot/agents/domestique-copilot-reviewer.agent.md"
refusal "last provider collision preflights before first provider" "$DOM" --global --platform all
check "last provider failure creates no Claude root" test ! -e "$HOME/.claude"
fixture
run "$DOM" --global --platform all
printf '\nSECRET_SENTINEL_global_do_not_copy_7392\n' >> "$HOME/.codex/agents/domestique-codex-reviewer.toml"
for flags in '' --force --dry-run; do
  # Intentional one optional word, not a shell command from user content.
  refusal "owned edited ${flags:-normal}" "$V2" --global ${flags:+"$flags"}
done
check "sentinel never copied or logged" python3 - "$F" <<'PY'
import pathlib,sys
root=pathlib.Path(sys.argv[1]); needle=b"SECRET_SENTINEL_global_do_not_copy_7392"
found=[p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and needle in p.read_bytes()]
assert found==["home/.codex/agents/domestique-codex-reviewer.toml"],found
PY

# Safe literal roots, including both quote types and backslash.
fixture
export HOME="$F/home space'\"\\literal" DOMESTIQUE_HOME="$F/core space'\"\\literal"
mkdir "$HOME"; CORE="$DOMESTIQUE_HOME"
run "$DOM" --global --platform all
check "literal quoted roots install" test "$RC" -eq 0
check "literal quoted inventory" native_inventory all
active="$(sed 's/^release=//' "$CORE/active")"
run "$CORE/bin/resolve-core" bind "$CORE" goal
check "literal quoted helper executes" test "$(cat "$F/out")" = "$active"
check "quoted Codex TOML parses" python3 - "$HOME/.codex/agents/domestique-codex-implementer.toml" "$CORE" <<'PY'
import pathlib,sys,tomllib
assert sys.argv[2] in tomllib.loads(pathlib.Path(sys.argv[1]).read_text())["developer_instructions"]
PY
for invalid in relative "$F/../escape" "$F/noncanonical/" "$F/key=value" "$F/"$'control\nline'; do
  export DOMESTIQUE_HOME="$invalid"
  refusal "invalid root" "$DOM" --global
done
export DOMESTIQUE_HOME="$HOME/.agents/core"
refusal "native overlap" "$DOM" --global
export DOMESTIQUE_HOME="$HOME"
refusal "HOME overlap" "$DOM" --global
export DOMESTIQUE_HOME="$F/repo1/core"
refusal "core in repo" "$DOM" --global
export DOMESTIQUE_HOME="$F/symlink/core"
mkdir "$F/real"; ln -s "$F/real" "$F/symlink"
refusal "symlink ancestor" "$DOM" --global
unset DOMESTIQUE_HOME
export XDG_STATE_HOME=relative
refusal "relative XDG" "$DOM" --global
fixture
ln -s "$F/repo1" "$HOME/.claude"
refusal "native symlink" "$DOM" --global --platform all
fixture
chmod 777 "$HOME"
refusal "unsafe HOME mode" "$DOM" --global
fixture
unset XDG_STATE_HOME
CORE="$HOME/.local/state/domestique"
run "$DOM" --global
check "default HOME state root" test "$RC" -eq 0
check "default core helper installed" test -f "$CORE/bin/resolve-core"
check "default native skill installed" test -f "$HOME/.claude/skills/domestique-claude/SKILL.md"
fixture
export HOME=relative
run "$DOM" --global
check "relative HOME refuses" test "$RC" -ne 0
fixture
mkdir -p "$CORE"
refusal "empty unowned core root refuses" "$DOM" --global

# Malformed/forged bounded manifest and core corruption are never repaired by
# guessing ownership. Isolate every mutation so each check has its own cause.
for fault in missing-state empty-state duplicate root api providers escape baseline helper missing-role hash active extra-core; do
  fixture
  run "$DOM" --global
  python3 - "$CORE" "$fault" <<'PY'
import pathlib,sys
c=pathlib.Path(sys.argv[1]); fault=sys.argv[2]; m=c/"state/global-manifest"
s=m.read_text(); r=c/"releases"/(c/"active").read_text().strip().removeprefix("release=")
if fault=="missing-state": m.unlink()
elif fault=="empty-state": m.write_text("")
elif fault=="duplicate": m.write_text(s+"format=1\n")
elif fault=="root": m.write_text(s.replace(f"core_root={c}", "core_root=/elsewhere"))
elif fault=="api": (r/"API").write_text("format=1\ncore_api=2\n")
elif fault=="providers": m.write_text(s.replace("providers=claude","providers=all"))
elif fault=="escape": m.write_text(s.replace("claude:.claude/agents/domestique-claude-reviewer.md","claude:../escape"))
elif fault=="baseline": m.write_text(s.replace("baseline=", "unknown=", 1))
elif fault=="helper": (c/"bin/resolve-core").write_text("echo never-execute-me\n")
elif fault=="missing-role": (r/"roles/goal.md").unlink()
elif fault=="hash": (r/"SHA256SUMS").write_text("0"*64+"\n")
elif fault=="active": (c/"active").write_text("release=../escape\n")
elif fault=="extra-core": (c/"unknown").write_text("not ours\n")
PY
  refusal "$fault" "$DOM" --global --force
done

# Parser invalid mixes fail before writes. Updater must reject before fetching.
fixture
for script in "$DOM" "$UP"; do
  for flag in --with-beads --purge-beads --no-guest --uninstall --local --state-only --model; do
    [ "$script:$flag" != "$DOM:--uninstall" ] || continue
    refusal "$(basename "$script") global $flag" "$script" --global "$flag"
    check "invocation exit 2 $flag" test "$RC" -eq 2
  done
  refusal "global positional target" "$script" --global "$F/repo1"
  refusal "global empty target" "$script" --global ""
  refusal "global target after --" "$script" --global -- "$F/repo1"
  refusal "global empty platform" "$script" --global --platform=
done
run "$DOM" --global --guest
check "global guest no-op" test "$RC" -eq 0
check "guest emits warning" grep -q 'deprecated no-op' "$F/err"
check "guest does not install legacy files" native_inventory claude

# Wrapper forwarding and preview failure gating use a local stub source only.
STUB="$WORK/source.sh"
cat > "$STUB" <<'SH'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$HOME/calls"
case "$*" in *--dry-run*) exit "${PREVIEW_EXIT:-0}";; esac
exit "${APPLY_EXIT:-0}"
SH
fixture
run "$UP" --source "$STUB" --global --platform codex-copilot --guest --force
check "wrapper apply succeeds" test "$RC" -eq 0
check "wrapper forwards no implicit target" python3 - "$HOME/calls" <<'PY'
import pathlib,sys
assert pathlib.Path(sys.argv[1]).read_text().splitlines()==[
    "--dry-run --global --force --guest --platform codex-copilot",
    "--global --force --guest --platform codex-copilot"]
PY
rm "$HOME/calls"; export PREVIEW_EXIT=7
run "$UP" --source "$STUB" --global
check "wrapper propagates failed global preview" test "$RC" -eq 7
check "wrapper never applies after global failure" test "$(wc -l < "$HOME/calls" | tr -d ' ')" = 1
unset PREVIEW_EXIT; rm "$HOME/calls"; export APPLY_EXIT=6
run "$UP" --source "$STUB" --global
check "wrapper propagates apply failure" test "$RC" -eq 6
unset APPLY_EXIT
fixture
before="$(tree "$HOME" "$CORE")"
run "$UP" --source "$DOM" --global --platform all --dry-run
check "real wrapper global preview works" test "$RC" -eq 0
check "real wrapper preview no writes" test "$before" = "$(tree "$HOME" "$CORE")"
run "$UP" --source "$DOM" --global --platform all
check "real wrapper global apply works" test "$RC" -eq 0
check "real wrapper global inventory" native_inventory all

# PATH-stub command failures, not public installer test flags. Stage failure,
# mid-native publication and active switch failures leave the old core usable.
REAL_MV="$(command -v mv)"
REAL_MKDIR="$(command -v mkdir)"
export REAL_MV REAL_MKDIR
mkdir "$WORK/stubs"
cat > "$WORK/stubs/mkdir" <<'SH'
#!/usr/bin/env bash
if [ "$#" = 1 ]; then
  case "$1" in "$FAIL_DEST"*) echo 'injected mkdir failure' >&2; exit 1;; esac
fi
exec "$REAL_MKDIR" "$@"
SH
cat > "$WORK/stubs/mv" <<'SH'
#!/usr/bin/env bash
case "$*" in *"$FAIL_DEST"*) echo 'injected mv failure' >&2; exit 1;; esac
source="${@: -2:1}"; destination="${@: -1}"
if [ "$destination/${source##*/}" = "$FAIL_DEST" ]; then
  echo 'injected mv failure' >&2; exit 1
fi
exec "$REAL_MV" "$@"
SH
chmod +x "$WORK/stubs/mkdir" "$WORK/stubs/mv"
ORIGINAL_PATH="$PATH"
for point in release native active; do
  fixture
  run "$DOM" --global --platform all
  active="$(sed 's/^release=//' "$CORE/active")"
  case "$point" in
    release) export FAIL_DEST="$CORE/releases/";;
    native) export FAIL_DEST="$HOME/.claude/agents/domestique-claude-reviewer.md";;
    active) export FAIL_DEST="$CORE/active";;
  esac
  export PATH="$WORK/stubs:$ORIGINAL_PATH"
  run "$V2" --global
  export PATH="$ORIGINAL_PATH"
  check "$point failure propagates" test "$RC" -ne 0
  check "$point reports explicit partial" grep -q PARTIAL "$F/err"
  check "$point retains journal" test -f "$CORE/state/pending"
  check "$point retains previous manifest" test -f "$CORE/state/previous"
  check "$point retains old active" test "$(sed 's/^release=//' "$CORE/active")" = "$active"
  run "$CORE/bin/resolve-core" read "$CORE" reviewer "$active"
  check "$point old bound release usable" test "$RC" -eq 0
  refusal "$point retry is explicit recovery refusal" "$V2" --global
done
unset FAIL_DEST
rm "$WORK/stubs/mkdir" "$WORK/stubs/mv"

# Failure before publication, and a destination appearing after preflight.
REAL_LN="$(command -v ln)"
export REAL_LN
fixture
run "$DOM" --global
before="$(tree "$HOME" "$CORE")"
# Fail rendering at shasum instead of publication; no target writes at all.
cat > "$WORK/stubs/shasum" <<'SH'
#!/usr/bin/env bash
echo 'injected stage hash failure' >&2
exit 1
SH
chmod +x "$WORK/stubs/shasum"
export PATH="$WORK/stubs:$ORIGINAL_PATH"
run "$V2" --global
export PATH="$ORIGINAL_PATH"
check "stage hash failure propagates" test "$RC" -ne 0
check "stage hash failure no destination writes" test "$before" = "$(tree "$HOME" "$CORE")"
rm "$WORK/stubs/shasum"
cat > "$WORK/stubs/ln" <<'SH'
#!/usr/bin/env bash
if [ "$2" = "$HOME/.claude/agents" ] && [ "${1##*/}" = domestique-claude-reviewer.md ]; then
  target="$2/${1##*/}"
  case "${RACE_KIND:-file}" in
    file) printf 'NEW_UNKNOWN_SENTINEL\n' > "$target";;
    directory) mkdir "$target";;
    symlink) mkdir "$TMPDIR/race-target"; "$REAL_LN" -s "$TMPDIR/race-target" "$target";;
  esac
fi
exec "$REAL_LN" "$@"
SH
chmod +x "$WORK/stubs/ln"
fixture
export PATH="$WORK/stubs:$ORIGINAL_PATH"
run "$DOM" --global
export PATH="$ORIGINAL_PATH"
check "newly appearing native asset refuses" test "$RC" -ne 0
check "newly appearing asset never overwritten" grep -qx NEW_UNKNOWN_SENTINEL "$HOME/.claude/agents/domestique-claude-reviewer.md"
check "unknown collision not recorded as completed publication" bash -c '! grep -q "published=claude:.claude/agents/domestique-claude-reviewer.md" "$1"' _ "$CORE/state/published"
check "unknown collision never copied" python3 - "$F" <<'PY'
import pathlib,sys
r=pathlib.Path(sys.argv[1])
found=[str(p.relative_to(r)) for p in r.rglob("*") if p.is_file() and b"NEW_UNKNOWN_SENTINEL" in p.read_bytes()]
assert found==["home/.claude/agents/domestique-claude-reviewer.md"],found
PY
refusal "newly appearing collision retry remains blocked" "$DOM" --global --force
for kind in directory symlink; do
  fixture
  export RACE_KIND="$kind" PATH="$WORK/stubs:$ORIGINAL_PATH"
  run "$DOM" --global
  export PATH="$ORIGINAL_PATH"
  check "newly appearing $kind refuses" test "$RC" -ne 0
  check "no link inside newly appearing $kind" python3 - "$HOME/.claude/agents/domestique-claude-reviewer.md" <<'PY'
import pathlib,sys
assert not list(pathlib.Path(sys.argv[1]).iterdir())
PY
done
unset RACE_KIND

# Race at the release publication operation itself, not at a preflight check.
# Hook both the original directory mv and the exclusive mkdir replacement so
# this regression also demonstrates the original failure on the old source.
rm "$WORK/stubs/ln"
REAL_MKDIR="$(command -v mkdir)"
export REAL_MKDIR
cat > "$WORK/stubs/mkdir" <<'SH'
#!/usr/bin/env bash
tool="${0##*/}"
target="${@: -1}"
case "$target" in
  "$RACE_CORE"/releases/r-*)
    if { [ "$tool" = mkdir ] && [ "$#" = 1 ]; } ||
       { [ "$tool" = mv ] && [ "$#" = 2 ] && [ -d "$1" ]; }; then
      printf '%s\n' "$target" > "$RACE_TRIGGER"
      case "$RACE_KIND" in
        directory) "$REAL_MKDIR" "$target";;
        symlink) "$REAL_LN" -s "$RACE_OUTSIDE" "$target";;
      esac
    fi;;
esac
case "$tool" in
  mkdir) exec "$REAL_MKDIR" "$@";;
  mv) exec "$REAL_MV" "$@";;
esac
SH
cp "$WORK/stubs/mkdir" "$WORK/stubs/mv"
chmod +x "$WORK/stubs/mkdir" "$WORK/stubs/mv"
for kind in directory symlink; do
  fixture
  run "$DOM" --global
  check "release $kind race setup" test "$RC" -eq 0
  active="$(sed 's/^release=//' "$CORE/active")"
  before="$(tree "$CORE/releases/$active" "$HOME")"
  mkdir "$F/outside"
  printf 'outside fixture must remain byte-identical\n' > "$F/outside/sentinel"
  outside_before="$(tree "$F/outside")"
  manifest_before="$(tree "$CORE/state/global-manifest")"
  export RACE_KIND="$kind" RACE_CORE="$CORE" RACE_OUTSIDE="$F/outside" RACE_TRIGGER="$F/trigger"
  export PATH="$WORK/stubs:$ORIGINAL_PATH"
  run "$V2" --global
  export PATH="$ORIGINAL_PATH"
  check "release $kind publication race actually triggered" test -s "$F/trigger"
  check "release $kind collision refuses" test "$RC" -ne 0
  check "release $kind reports partial" grep -q PARTIAL "$F/err"
  check "release $kind no success" bash -c '! grep -Eq "domestique global: (published|up to date)" "$1"' _ "$F/out"
  check "release $kind old active retained" test "$(sed 's/^release=//' "$CORE/active")" = "$active"
  check "release $kind old bindings and native bytes untouched" test "$before" = "$(tree "$CORE/releases/$active" "$HOME")"
  check "release $kind outside fixture unchanged" test "$outside_before" = "$(tree "$F/outside")"
  check "release $kind manifest unchanged" test "$manifest_before" = "$(tree "$CORE/state/global-manifest")"
  check "release $kind pending retained" test -s "$CORE/state/pending"
  check "release $kind previous accurate" cmp -s "$CORE/state/previous" "$CORE/state/global-manifest"
  check "release $kind no claimed or published collision" test -f "$CORE/state/published"
  check "release $kind publication log empty" test ! -s "$CORE/state/published"
  check "release $kind collision not populated or adopted" python3 - "$F/trigger" "$kind" "$F/outside" <<'PY'
import pathlib,sys
p=pathlib.Path(pathlib.Path(sys.argv[1]).read_text().strip())
if sys.argv[2]=="directory":
    assert p.is_dir() and not p.is_symlink() and not list(p.iterdir())
else:
    assert p.is_symlink() and p.readlink()==pathlib.Path(sys.argv[3])
PY
  run "$CORE/bin/resolve-core" bind "$CORE" orchestrator
  check "release $kind unbound helper usable" test "$RC" -eq 0
  check "release $kind unbound helper still selects old" test "$(cat "$F/out")" = "$active"
  run "$CORE/bin/resolve-core" read "$CORE" reviewer "$active"
  check "release $kind bound helper usable" test "$RC" -eq 0
  check "release $kind bound helper bytes" cmp -s "$F/out" "$CORE/releases/$active/roles/reviewer.md"
  refusal "release $kind retry requires recovery" "$V2" --global --force
done
unset RACE_KIND RACE_CORE RACE_OUTSIDE RACE_TRIGGER

# Incomplete population must record a claim, not a completed release.
rm "$WORK/stubs/mv"
cat > "$WORK/stubs/mkdir" <<'SH'
#!/usr/bin/env bash
if [ "$#" = 1 ]; then
  case "$1" in "$RACE_CORE"/releases/r-*/roles)
    printf '%s\n' "${1%/roles}" > "$RACE_TRIGGER"
    exit 1;;
  esac
fi
exec "$REAL_MKDIR" "$@"
SH
fixture
run "$DOM" --global
active="$(sed 's/^release=//' "$CORE/active")"
export RACE_CORE="$CORE" RACE_TRIGGER="$F/trigger"
export PATH="$WORK/stubs:$ORIGINAL_PATH"
run "$V2" --global
export PATH="$ORIGINAL_PATH"
check "incomplete release population triggered" test -s "$F/trigger"
check "incomplete release refuses" test "$RC" -ne 0
check "incomplete release old active" test "$(sed 's/^release=//' "$CORE/active")" = "$active"
check "incomplete release pending" test -s "$CORE/state/pending"
check "incomplete release claim only" python3 - "$CORE/state/published" "$F/trigger" <<'PY'
import pathlib,sys
release=pathlib.Path(pathlib.Path(sys.argv[2]).read_text().strip()).name
assert pathlib.Path(sys.argv[1]).read_text()==f"release-claimed={release}\n"
PY
rm "$WORK/stubs/mkdir"

# Corrupt the final release after its initial validation, at manifest rename.
# Activation must independently validate the final path, including inventory.
cat > "$WORK/stubs/mv" <<'SH'
#!/usr/bin/env bash
source="${@: -2:1}"; destination="${@: -1}"
if [ "$destination" = "$RACE_CORE/state" ] && [ "${source##*/}" = global-manifest ]; then
  release="$(sed -n 's/^release=//p' "$RACE_CORE/state/published")"
  target="$RACE_CORE/releases/$release"
  printf '%s\n' "$target" > "$RACE_TRIGGER"
  case "$RACE_KIND" in
    api) printf 'invalid API\n' > "$target/API";;
    extra) printf 'unexpected release leaf\n' > "$target/extra";;
    symlink) "$REAL_MV" "$target" "$target.saved"; "$REAL_LN" -s "$target.saved" "$target";;
  esac
fi
exec "$REAL_MV" "$@"
SH
chmod +x "$WORK/stubs/mv"
for kind in api extra symlink; do
  fixture
  run "$DOM" --global
  active="$(sed 's/^release=//' "$CORE/active")"
  export RACE_KIND="$kind" RACE_CORE="$CORE" RACE_TRIGGER="$F/trigger"
  export PATH="$WORK/stubs:$ORIGINAL_PATH"
  run "$V2" --global
  export PATH="$ORIGINAL_PATH"
  check "final $kind validation race triggered" test -s "$F/trigger"
  check "final $kind validation refuses" test "$RC" -ne 0
  check "final $kind validation reports partial" grep -q PARTIAL "$F/err"
  check "final $kind no success" bash -c '! grep -Eq "domestique global: (published|up to date)" "$1"' _ "$F/out"
  check "final $kind old active retained" test "$(sed 's/^release=//' "$CORE/active")" = "$active"
  check "final $kind pending retained" test -s "$CORE/state/pending"
  check "final $kind previous retained" test -s "$CORE/state/previous"
  check "final $kind active not recorded published" bash -c '! grep -q "^published=core:active:" "$1"' _ "$CORE/state/published"
  run "$CORE/bin/resolve-core" read "$CORE" reviewer "$active"
  check "final $kind old bound helper usable" test "$RC" -eq 0
done
unset RACE_KIND RACE_CORE RACE_TRIGGER

echo "global: $PASS passed, $FAIL failed"
exit "$FAIL"
