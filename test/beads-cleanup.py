"""Public cleanup CLI, cooperative flock, and opt-in pinned native fixtures.

Default: clearly synthetic protocol (digest substituted in a disposable script).
--native: actual .6 production init/query/CRUD under its unchanged OS sandbox;
no AI/auth/MCP workloads. Never copy a native database or restore native state.
--native-smoke / --smoke: targeted native / fake purge and reactivation regression.
All scratch, HOME and TMPDIR live beneath an explicitly supplied project-local
TMPDIR. Faults modify only a disposable installer and must actually trigger.
"""
import ast
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
SOURCE = (ROOT / "domestique.sh").read_text()
CODE = SOURCE.split("<<'DOM_BEADS_PY'\n", 1)[1].split("\nDOM_BEADS_PY", 1)[0]
NS = {}
exec(CODE.split("\ntry:\n    main()", 1)[0], NS)
COUNT = 0
NATIVE = sys.argv[1:] in (["--native"], ["--native-smoke"])
SMOKE = sys.argv[1:] in (["--native-smoke"], ["--smoke"])
assert not sys.argv[1:] or NATIVE or SMOKE
PROCESS_BOUNDARY = "    result = execute_child(\n"


def check(ok, why):
    global COUNT
    assert ok, why
    COUNT += 1


def snapshot(root):
    return [(str(p.relative_to(root)), p.lstat().st_mode,
             p.lstat().st_mtime_ns if p.is_file() else None,
             os.readlink(p) if p.is_symlink() else p.read_bytes() if p.is_file() else None)
            for p in sorted(root.rglob("*"))]


def beads(p):
    return "".join(line + "\n" for line in
                   (p / ".domestique-private/manifest").read_text().splitlines()
                   if line.startswith("beads_"))


def inject_pause(source, mark, release_gate):
    """Prepend at the complete call boundary; refuse stale or broken helpers."""
    check(source.count(PROCESS_BOUNDARY) == 1, "wrapped-operation pause anchor")
    pause = (f"    if not Path({str(mark)!r}).exists():\n"
             "        import time\n"
             f"        Path({str(mark)!r}).write_text('active')\n"
             f"        while not Path({str(release_gate)!r}).exists(): time.sleep(0.05)\n")
    source = source.replace(PROCESS_BOUNDARY, pause + PROCESS_BOUNDARY)
    ast.parse(source.split("<<'DOM_BEADS_PY'\n", 1)[1].split("\nDOM_BEADS_PY", 1)[0])
    return source


def main():
    # Synthetic/default mode does not even import the native selector.
    if NATIVE:
        spec = importlib.util.spec_from_file_location("beads_fixture", ROOT / "test/beads_fixture.py")
        fixture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixture)
        selected = fixture.resolve()
        print("NATIVE_FIXTURE=" + json.dumps(selected), flush=True)
    parent = Path(os.environ["TMPDIR"]).resolve()
    assert ROOT in parent.parents and parent.is_dir(), "use a project-local private TMPDIR"
    with tempfile.TemporaryDirectory(prefix="beads-cleanup-", dir=parent) as temp:
        work = Path(temp).resolve()
        for name in ("home", "bin", "tmp", "empty"):
            (work / name).mkdir(mode=0o700)
        binary = work / "bin/bd"
        if NATIVE:
            binary.symlink_to(selected["path"])
            check(NS["digest"](binary) == NS["PIN"], "actual pinned native artifact")
            source = SOURCE
        else:
            module = ast.parse((ROOT / "test/beads-private.py").read_text())
            fake = next(ast.literal_eval(node.value) for node in module.body
                        if isinstance(node, ast.Assign) and
                        any(isinstance(x, ast.Name) and x.id == "FAKE" for x in node.targets))
            binary.write_text(f"#!{Path(sys.executable).resolve()} -ISB\n" + fake)
            binary.chmod(0o700)
            source = SOURCE.replace(NS["PIN"], NS["digest"](binary))
        (work / "bin/python3").symlink_to(Path(sys.executable).resolve())
        native_log = work / "native-calls"
        native_log.touch()
        # Instrument the production controller, not a proxy for native behavior.
        anchor = PROCESS_BOUNDARY
        check(source.count(anchor) == 1, "native call instrumentation anchor")
        source = source.replace(anchor,
            f"    with open({str(native_log)!r}, 'a') as trace:\n"
            "        trace.write(str(argv[0]) + '\\n')\n" + anchor)
        dom = work / "domestique.sh"
        dom.write_text(source)
        env = {
            "HOME": str(work / "home"), "DOMESTIQUE_HOME": str(work / "core"),
            "TMPDIR": str(work / "tmp"), "PATH": f"{work / 'bin'}:/opt/homebrew/bin:/usr/bin:/bin",
            "GIT_CEILING_DIRECTORIES": str(parent),
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_SYSTEM": "/dev/null",
            "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.hooksPath",
            "GIT_CONFIG_VALUE_0": str(work / "empty"), "GIT_TEMPLATE_DIR": str(work / "empty"),
            "LC_ALL": "C", "PYTHONDONTWRITEBYTECODE": "1",
        }

        def run(*args, ok=True, cwd=work, extra=None):
            result = subprocess.run(list(map(str, args)), cwd=cwd, env={**env, **(extra or {})},
                                    stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                    timeout=600)
            check((result.returncode == 0) == ok, (args, result.stdout, result.stderr))
            return result

        def install(name, profiles=None):
            p = work / name
            p.mkdir(mode=0o700)
            run("git", "init", "-q", p)
            (p / ".git/info").mkdir(exist_ok=True)
            (p / ".git/info/exclude").write_text("# host excludes\n")
            run("bash", dom, "--local", p, "--with-beads",
                *(["--platform", profiles] if profiles else ["--state-only"]))
            return p

        def cleanup(p, *args, ok=True, script=dom):
            before_calls = native_log.read_bytes()
            result = run("bash", script, "--uninstall", "--local", p, *args, ok=ok)
            check(native_log.read_bytes() == before_calls, "ZERO native calls during cleanup")
            return result

        def refusal(p, *args):
            before = snapshot(work)
            cleanup(p, *args, ok=False)
            check(snapshot(work) == before, "refusal before ANY fixture write")

        run("bash", dom, "--global", "--platform", "all")
        core = work / "core"
        helper = core / "bin/resolve-core"
        release = (core / "active").read_text().strip().split("=")[1]
        protected = snapshot(core), snapshot(work / "home")
        p = install("fresh", None if SMOKE else "all")
        for variable in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE"):
            before = snapshot(work)
            run("bash", dom, "--uninstall", "--local", p, "--purge-beads", "--force",
                ok=False, extra={variable: str(work / "unowned-git-route")})
            check(snapshot(work) == before, "Git routing override cannot authorize purge: " + variable)
        if SMOKE:
            cleanup(p, "--purge-beads")
            check(not (p / ".beads").exists() and not beads(p), "native pristine purge")
            used = install("used-smoke")
            original = beads(used)
            run("bash", helper, "beads", core, used, release, "create", "Smoke fixture", "--json")
            cleanup(used)
            check(beads(used) == original.replace("beads_status=ready\n", "beads_status=retained\n"),
                  "native mutation retained without rebaseline")
            run("bash", dom, "--local", used, "--with-beads", "--state-only")
            check(beads(used) == original, "native qualified reactivation preserves original hashes")
            refusal(used, "--purge-beads", "--force")
            check((snapshot(core), snapshot(work / "home")) == protected, "global and HOME unchanged")
            calls = native_log.read_text().splitlines()
            bd_calls = sum(Path(call).name in ("bd", "beads") for call in calls)
            label = "PINNED native" if NATIVE else "SYNTHETIC fake"
            print(f"beads-cleanup smoke: {COUNT} checks; {bd_calls} {label} bd calls / "
                  f"{len(calls)} process calls; ZERO cleanup-native calls")
            return
        original = beads(p)
        before = snapshot(work)
        cleanup(p, "--purge-beads", "--dry-run")
        check(snapshot(work) == before, "purge dry-run absolutely read-only")
        refusal(p, "--platform", "claude", "--purge-beads", "--force")
        metadata = p / ".beads/metadata.json"

        # A child locks the inherited SAME open description, exits, and the
        # independent contender remains blocked until its parent closes it.
        fd = os.open(metadata, os.O_RDONLY | os.O_NOFOLLOW)
        subprocess.run([sys.executable, "-I", "-S", "-c",
                        "import fcntl,sys;fcntl.flock(int(sys.argv[1]),fcntl.LOCK_EX|fcntl.LOCK_NB)",
                        str(fd)], pass_fds=(fd,), check=True)
        contender = ("import fcntl,sys\n"
                     "with open(sys.argv[1],'rb') as f:\n"
                     " try: fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)\n"
                     " except BlockingIOError: sys.exit(7)\n")
        check(subprocess.run([sys.executable, "-I", "-S", "-c", contender, str(metadata)]).returncode == 7,
              "child exited: parent still holds inherited flock")
        refusal(p, "--purge-beads")
        before = snapshot(work)
        run("bash", helper, "beads", core, p, release, "ready", ok=False)
        check(snapshot(work) == before, "purge gate prevents wrapped native calls")
        os.close(fd)
        check(subprocess.run([sys.executable, "-I", "-S", "-c", contender, str(metadata)]).returncode == 0,
              "independent process acquires only after parent closes")

        if not NATIVE:
            # No synthetic mutation/restore is represented as native evidence.
            for rel in (".beads/interactions.jsonl", ".domestique-private/exports/issues.jsonl",
                        ".domestique-private/beads-context/tmp/unknown"):
                path = p / rel
                previous = path.read_bytes() if path.exists() else None
                path.write_text("synthetic changed content\n")
                refusal(p, "--purge-beads", "--force")
                if previous is None:
                    path.unlink()
                else:
                    path.write_bytes(previous)
            for bad in ("beads_status=failed", "beads_status=ready\0",
                        "beads_status=ready\nbeads_status=ready"):
                mf = p / ".domestique-private/manifest"
                old = mf.read_bytes()
                mf.write_bytes(old.replace(b"beads_status=ready", bad.encode()))
                refusal(p, "--purge-beads", "--force")
                mf.write_bytes(old)
            mf = p / ".domestique-private/manifest"
            old = mf.read_bytes()
            lines = old.splitlines(keepends=True)
            created = [line for line in lines if line.startswith(b"beads_created=")]
            for bad in (
                b"".join(line for line in lines if not line.startswith(b"beads_")),
                old + created[0],
                old.replace(created[0], b""),
                old.replace(b"beads_created=.beads/.gitignore:", b"beads_created=.beads/unknown:"),
                old.replace(b"beads_path_created=by-init:", b"beads_path_created=reservation:"),
                old.replace(b"beads_created=.beads/.gitignore:", b"beads_created=../outside:"),
                old.replace(b"beads_prefix=dm", b"beads_prefix=xx"),
                old.replace(b"beads_sha256=", b"beads_unknown="),
            ):
                mf.write_bytes(bad)
                refusal(p, "--purge-beads", "--force")
                mf.write_bytes(old)
            extra = p / ".beads/unknown"
            extra.touch()
            refusal(p, "--purge-beads")
            extra.unlink()
            leaf = p / ".beads/last-touched"
            old = leaf.read_bytes()
            leaf.unlink()
            refusal(p, "--purge-beads")
            leaf.symlink_to(metadata)
            refusal(p, "--purge-beads")
            leaf.unlink()
            os.link(metadata, leaf)
            refusal(p, "--purge-beads")
            leaf.unlink()
            leaf.write_bytes(old)
            run("git", "-C", p, "add", "-f", ".beads/metadata.json")
            refusal(p, "--purge-beads")
            run("git", "-C", p, "rm", "--cached", "-q", ".beads/metadata.json")

            # A stale open descriptor must not lock a replacement generation.
            fd = os.open(metadata, os.O_RDONLY | os.O_NOFOLLOW)
            old = metadata.read_bytes()
            metadata.unlink()
            metadata.write_bytes(old)
            bridge = work / "bridge.py"
            bridge.write_text(CODE)
            probe = ("import os,subprocess,sys\n"
                     "os.dup2(int(sys.argv[1]),8,inheritable=True)\n"
                     "r=subprocess.run(sys.argv[2:],pass_fds=(8,));sys.exit(r.returncode)\n")
            result = subprocess.run([sys.executable, "-c", probe, str(fd), sys.executable,
                                     str(bridge), "gate", str(p), beads(p)],
                                    pass_fds=(fd,), capture_output=True, text=True, env=env)
            check(result.returncode != 0 and "generation" in result.stderr,
                  "old descriptor rejects replaced metadata generation")
            os.close(fd)
            bridge.unlink()

        cleanup(p, "--platform", "claude")
        check(beads(p) == original, "subset retains EXACT ordered Beads records")
        cleanup(p)
        retained = original.replace("beads_status=ready\n", "beads_status=retained\n")
        check(beads(p) == retained, "last provider only changes ready to retained")
        before = snapshot(work)
        cleanup(p)
        check(snapshot(work) == before, "none retained idempotence")
        cleanup(p, "--purge-beads")
        check(not (p / ".beads").exists() and not beads(p), "actual retained-none purge")
        check(not (p / ".domestique-private/beads-context").exists() and
              not (p / ".domestique-private/exports").exists(), "context and exports removed")
        check("providers=none\n" in (p / ".domestique-private/manifest").read_text(),
              "valid reusable private none attachment")
        run("git", "-C", p, "check-ignore", "-q", ".domestique-private/manifest")
        run("git", "-C", p, "check-ignore", "-q", ".beads/metadata.json", ok=False)

        used = install("used", "all")
        original = beads(used)
        run("bash", helper, "beads", core, used, release, "create", "Cleanup fixture", "--json")
        refusal(used, "--purge-beads", "--force")
        if not NATIVE:
            mark, release_gate = work / "wrapped-active", work / "wrapped-release"
            paused = work / "paused-wrapper"
            paused.write_text(inject_pause(helper.read_text(), mark, release_gate))
            child = subprocess.Popen(["bash", str(paused), "beads", str(core), str(used),
                                      release, "ready"], cwd=work, env=env,
                                     stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True)
            try:
                deadline = time.monotonic() + 60
                while not mark.exists() and child.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.1)
                check(mark.exists(), "actual current wrapper reached gated native operation")
                before = snapshot(work)
                result = cleanup(used, "--purge-beads", ok=False)
                check("qualification, ownership" in result.stderr, "busy gate refused before native query")
                check(snapshot(work) == before, "busy wrapped operation refuses purge without writes")
                release_gate.touch()
                out, err = child.communicate(timeout=60)
                check(child.returncode == 0, ("paused current operation completed", out, err))
            finally:
                release_gate.touch(exist_ok=True)
                if child.poll() is None:
                    child.terminate()
                child.communicate(timeout=10)
        role = used / ".codex/agents/domestique-codex-local-implementer.toml"
        role.write_text(role.read_text() + "\n# synthetic/local customization\n")
        refusal(used, "--purge-beads", "--force")
        cleanup(used, "--platform", "claude")
        check(role.is_file() and beads(used) == original, "unselected edited provider untouched")
        cleanup(used, "--force", ok=False)
        check(role.is_file() and "providers=codex\n" in
              (used / ".domestique-private/manifest").read_text(), "whole edited provider retained")
        cleanup(used, "--platform", "codex", ok=False)
        # Do not erase customization to force cleanup. A separate none fixture
        # exercises real used-DB retention/reactivation without any DB restore.
        none = install("used-none")
        original = beads(none)
        run("bash", helper, "beads", core, none, release, "create", "Used none", "--json")
        cleanup(none)
        check(beads(none) == original.replace("beads_status=ready\n", "beads_status=retained\n"),
              "already-none ready becomes retained")
        calls = native_log.read_bytes()
        run("bash", dom, "--local", none, "--with-beads", "--state-only")
        check(native_log.read_bytes() != calls and beads(none) == original,
              "qualified reactivation queried engine but NEVER rewrote initial hashes")
        refusal(none, "--purge-beads", "--force")

        linked = work / "linked"
        run("git", "-C", used, "worktree", "add", "--orphan", "-b", "cleanup-linked", linked)
        run("bash", dom, "--local", linked, "--with-beads", "--state-only")
        other_before = snapshot(used / ".beads"), snapshot(used / ".domestique-private")
        shared = used / ".git/info/exclude"
        shared_before = shared.read_bytes()
        cleanup(linked, "--purge-beads")
        check((snapshot(used / ".beads"), snapshot(used / ".domestique-private")) == other_before,
              "linked purge leaves other worktree DB/profile/private bytes untouched")
        check(shared.read_bytes() == shared_before, "other worktree keeps every required shared rule")
        run("git", "-C", used, "check-ignore", "-q", ".beads/metadata.json")
        run("git", "-C", used, "check-ignore", "-q", ".codex/agents/host.toml", ok=False)
        run("git", "-C", linked, "check-ignore", "-q", ".domestique-private/manifest")

        fresh = install("fresh-purge")
        cleanup(fresh, "--purge-beads")
        check(not (fresh / ".beads").exists(), "fresh ready-none pristine purge")

        if not NATIVE:
            fault_cases = (
                ("unlink", "    unlink \"${remove_paths[i]}\" || exit 1",
                 '    false || exit 1'),
                ("journal", '  U_LOG_HASH=absent\n  local_remove_validate || exit 1',
                 '  printf "changed\\n" >> "$U_STATE/pending"'),
                ("exclude", '  local_remove_exclude "$final_exclude" || exit 1',
                 '  printf "# changed\\n" >> "$L_EXCLUDE"'),
                ("generation", '  U_PURGED=1\n    local_remove_validate || exit 1',
                 '  mkdir "$L_ROOT/.beads"\n  printf "reappeared\\n" > "$L_ROOT/.beads/metadata.json"'),
                ("late-final", '  U_PENDING_HASH=absent\n  local_remove_validate || exit 1',
                 '  printf "unknown\\n" > "$U_STATE/late-unknown"'),
            )
            for name, anchor, fault in fault_cases:
                case = install("fault-" + name, "claude")
                mark = work / ("trigger-" + name)
                body_start = source.index("local_uninstall() (")
                body_end = source.index("\nlocal_install() (", body_start)
                body = source[body_start:body_end]
                check(body.count(anchor) == 1, "unique fault anchor: " + name)
                insertion = f'\n  printf "triggered\\n" > "{mark}"\n' + fault + "\n"
                replacement = insertion + anchor if name == "unlink" else anchor.replace(
                    "local_remove_validate || exit 1", insertion + "  local_remove_validate || exit 1"
                ) if name in ("generation", "late-final") else anchor + insertion
                script = work / ("fault-" + name + ".sh")
                script.write_text(source[:body_start] + body.replace(anchor, replacement) + source[body_end:])
                result = cleanup(case, "--purge-beads", script=script, ok=False)
                check(mark.read_text() == "triggered\n" and "PARTIAL" in result.stderr,
                      "actual injection trigger and partial refusal: " + name)
                check((case / ".domestique-private/pending").is_file(), "private pending survives")
                run("git", "-C", case, "check-ignore", "-q", ".domestique-private/pending")
                check("profiles removed;" not in result.stdout, "no false cleanup success")

            # Inject inside the actual bottom-up Python deleter, after a real
            # completed leaf unlink; old baselines and accurate log must survive.
            case = install("fault-native-leaf")
            mark = work / "trigger-native-leaf"
            anchor = "        need(not os.path.lexists(p), \"removed purge path reappeared\")"
            check(source.count(anchor) == 1, "unique inner-deletion fault anchor")
            script = work / "fault-native-leaf.sh"
            script.write_text(source.replace(anchor, anchor +
                f"\n        Path({str(mark)!r}).write_text('triggered\\n')"
                "\n        raise Refusal('injected after actual leaf deletion')"))
            original = beads(case)
            cleanup(case, "--purge-beads", script=script, ok=False)
            check(mark.read_text() == "triggered\n", "inner deletion fault actually triggered")
            check(beads(case) == original, "partial deletion preserves ALL original Beads fields")
            log = (case / ".domestique-private/published").read_text()
            removed = [x.split("=", 1)[1].rsplit(":", 1)[0] for x in log.splitlines()
                       if x.startswith("removed=")]
            check(bool(removed) and all(not (case / x).exists() for x in removed),
                  "partial log records actual removed paths, not intentions")
            check((case / ".domestique-private/pending").exists(), "inner failure leaves pending")

        # Pure FS cleanup must remain available after both installed core and
        # qualified executable disappear. No native calls are permitted here.
        missing = install("missing")
        os.rename(core, work / "unavailable-core")
        binary.unlink()
        cleanup(missing)
        cleanup(missing, "--purge-beads")
        check(not (missing / ".beads").exists(), "missing core/binary filesystem purge")
        os.rename(work / "unavailable-core", core)
        check((snapshot(core), snapshot(work / "home")) == protected, "global and HOME unchanged")
        calls = native_log.read_text().splitlines()
        bd_calls = sum(Path(call).name in ("bd", "beads") for call in calls)
        print(f"beads-cleanup: {COUNT} checks; {'PINNED NATIVE' if NATIVE else 'SYNTHETIC ONLY'}; "
              f"{bd_calls} {'native' if NATIVE else 'fake'} bd calls / "
              f"{len(calls)} instrumented process calls; ZERO cleanup-native calls")


if __name__ == "__main__":
    main()
