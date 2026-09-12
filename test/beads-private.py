"""Synthetic protocol/ownership tests for the embedded production bridge.

The fake executable is NOT native evidence. Its digest is substituted ONLY in
a disposable copy of the installer. Production has no test environment bypass.
All fake native calls still pass through the production OS sandbox.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parent.parent
SOURCE = (ROOT / "domestique.sh").read_text()
CODE = SOURCE.split("<<'DOM_BEADS_PY'\n", 1)[1].split("\nDOM_BEADS_PY", 1)[0]
NS = {}
exec(CODE.split("\ntry:\n    main()", 1)[0], NS)
COUNT = 0


def check(ok, why):
    global COUNT
    assert ok, why
    COUNT += 1


def reject(fn, *args):
    try:
        fn(*args)
    except (NS["Refusal"], OSError, ValueError):
        check(True, "refused")
    else:
        check(False, ("unexpected acceptance", args))


def snap(root):
    return [(str(p.relative_to(root)), p.lstat().st_mode,
             p.lstat().st_mtime_ns if p.is_file() else None,
             os.readlink(p) if p.is_symlink() else p.read_bytes() if p.is_file() else None)
            for p in sorted(root.rglob("*"))]


def help_tests():
    with tempfile.TemporaryDirectory(prefix="domestique-help-") as temp:
        work = Path(temp).resolve()
        env = dict(HOME=str(work), DOMESTIQUE_HOME=str(work / "core"),
                   XDG_STATE_HOME=str(work / "state"), TMPDIR=str(work),
                   PATH="/usr/bin:/bin", LC_ALL="C")
        for script in ("domestique.sh", "update.sh"):
            before = snap(work)
            result = subprocess.run(
                ["/bin/bash", str(ROOT / script), "--help"], cwd=work, env=env,
                capture_output=True, text=True, timeout=30)
            text = " ".join(result.stdout.split())
            check(result.returncode == 0 and not result.stderr, script + " help succeeds")
            check(all(s in text for s in ("Darwin arm64", "Beads 1.1.2",
                                          "existing Python 3.9+", "macOS sandbox-exec")),
                  script + " help scopes qualification")
            check(all(s in text for s in ("--local TARGET --with-beads", "--state-only")),
                  script + " help requires explicit state-only initialization")
            check(not any(s in text for s in ("initialization is unsupported",
                                              "ALL database guards STOP",
                                              "never home, root policy, settings, skills, or Beads")),
                  script + " help has no universal unsupported claim")
            check(snap(work) == before, script + " help has zero fixture writes")
            if script == "domestique.sh":
                check("exact digest-pinned" in text and "not every 1.1.2 build qualifies" in text,
                      "help limits support to the pinned artifact")
                check("No new PROJECT adapters/local profiles" in text,
                      "state-only help excludes project adapters")
                check("does not initialize Beads unless explicitly requested" in text,
                      "ordinary profile help excludes implicit initialization")
                check("missing/unowned/failed/unqualified state must STOP" in text and
                      "Verified private Beads operations use the installed wrapper" in text,
                      "help distinguishes supported operations from failed guards")
                check("never call bd" in text and
                      "uninstall/purge remains unsupported pending .7" in text,
                      "help preserves pure loading and pending cleanup limits")


def unit_tests():
    root, prefix = Path("/private/synthetic"), "dm0123456789ab"
    issue = prefix + "-abc"
    grammar = NS["grammar"]
    for args in (
        ["ready", "--json"], ["ready", "--parent", issue, "--json"],
        ["list", "--all", "--json"], ["show", issue, "--json"],
        ["create", "title", "--type", "epic", "--description", "--db SECRET; ' $(touch x)"],
        ["create", "--description", "x", "--", "--db"], ["create", "task", "--type", "task"],
        ["create", "task", "--deps", "discovered-from:" + issue, "--priority", "2"],
        ["update", issue, "--claim"], ["update", issue, "--status", "in_progress"],
        ["update", issue, "--title", "--directory=x"], ["close", issue, "--reason", "--db=x"],
        ["dep", "add", issue, prefix + "-def", "--type", "blocks"],
        ["dep", "remove", issue, prefix + "-def"], ["remember", "insight", "--key", "insight"],
        ["export"], ["export", "--include-memories"],
    ):
        result = grammar(args, root, prefix)
        check(result[0] == args[0], "approved command")
        check("--sandbox" not in result, "global flag is controller-owned")
    for cmd in ("init", "setup", "doctor", "sql", "sync", "dolt", "import", "server",
                "config", "upgrade", "exec", "auth", "reopen", "--db", "--directory"):
        reject(grammar, [cmd], root, prefix)
    for flag in ("--db", "--directory", "--config", "--actor", "--remote", "--sandbox",
                 "--output", "--help", "--dry-run", "--force", "--no-daemon"):
        for cmd in ("ready", "list", "export", "create"):
            reject(grammar, [cmd, flag, "x"], root, prefix)
    for args in (["show"], ["show", "foreign-abc"], ["create", "a", "b"],
                 ["create", "x", "--type", "bug"], ["ready", "--json", "--json"],
                 ["update", issue, "--status", "invalid"], ["remember", "x", "--key", "../x"],
                 ["dep", "delete", issue, issue], ["dep", "remove", issue, issue, "--type", "blocks"],
                 ["close", issue, "--reason"],
                 ["export", "--output", "/private/elsewhere"], ["ready", "--parent", "secret"]):
        reject(grammar, args, root, prefix)
    env = NS["environment"](root / "context", root / ".beads", Path("/usr/bin/git"))
    for name in ("SECRET", "BEADS_DB", "BD_DB", "GIT_DIR", "GIT_WORK_TREE", "HTTP_PROXY",
                 "OTEL_EXPORTER_OTLP_ENDPOINT", "BEADS_SKIP_IDENTITY_CHECK", "BEADS_DOLT_SERVER_MODE"):
        check(name not in env, "environment strict allowlist")
    check(env["GIT_CEILING_DIRECTORIES"] == str(root / "context"), "Git ceiling above run")
    reject(NS["decode"], '{"a":1,"a":2}')
    reject(NS["decode"], '{"a":"\0"}')
    reject(NS["decode"], '{"a":NaN}')
    reject(NS["records"], "beads_status=ready\n")
    check("--title=--db" in grammar(["create", "--", "--db"], root, prefix),
          "native explicit title form, not pinned positional-title rejection")
    for system, machine in (("Linux", "aarch64"), ("Darwin", "x86_64"), ("Windows", "arm64")):
        with patch.object(NS["platform"], "system", return_value=system), \
             patch.object(NS["platform"], "machine", return_value=machine):
            reject(NS["qualify"])
    with patch.object(NS["shutil"], "which", return_value=None):
        reject(NS["qualify"])
    # Qualification protocol negatives only; never native version evidence.
    with patch.dict(NS, digest=lambda _: NS["PIN"],
                    process=lambda argv, *a, **kw: "bd version 1.2.2 (synthetic)\n"), \
         patch.object(NS["shutil"], "which", return_value="/usr/bin/true"):
        reject(NS["qualify"])
    child = Mock(pid=123, returncode=0)
    child.communicate.return_value = ('{"title":"permission denied is issue text"}\n', "")
    with patch.object(NS["subprocess"], "Popen", return_value=child), \
         patch.object(NS["os"], "killpg"):
        check(NS["process"](["/usr/bin/true"], root / "context", root / ".beads",
                            Path("/usr/bin/true"), Path("/usr/bin/git")) ==
              child.communicate.return_value[0], "stdout is data, not a denial substring filter")


FAKE = r'''
import json, os, pathlib, sys, uuid
args = sys.argv[1:]
assert args.pop(0) == "--sandbox"
db = pathlib.Path(os.environ["BEADS_DIR"])
assert pathlib.Path.cwd().name == "run"
assert os.environ["BD_DOLT_MODE"] == "embedded"
assert os.environ["GIT_CEILING_DIRECTORIES"] == str(pathlib.Path.cwd().parent)
assert all(x not in os.environ for x in ("SECRET", "BD_DB", "BEADS_DB", "GIT_DIR", "HTTP_PROXY"))
cmd = args.pop(0)
if cmd == "--version":
    print("bd version 1.1.2 (synthetic)"); sys.exit()
if args == ["--help"]:
    print("--stealth --skip-agents --skip-hooks --non-interactive --prefix --remote --sandbox")
    sys.exit()
assert db.is_dir()
if cmd == "init":
    assert not list(db.iterdir()), "initializer did not exclusively claim empty dir"
    if db.parent.name in ("partial", "partialunknown"):
        if db.parent.name == "partialunknown":
            (db/"unknown-host-file").write_text("synthetic unknown")
        (db/"metadata.json").write_text("partial"); sys.exit(1)
    if db.parent.name == "zeroexit":
        sys.exit()
    prefix = args[args.index("--prefix")+1]
    (db/"metadata.json").write_text(json.dumps(dict(database="dolt", backend="dolt",
        dolt_mode="embedded", dolt_database=prefix, project_id=str(uuid.uuid4()))))
    for name, data in (("config.yaml", "no-git-ops: true\n"), (".local_version", "1.1.2\n"),
                       (".gitignore", "# synthetic\n"), ("README.md", "synthetic\n"),
                       ("interactions.jsonl", "")):
        (db/name).write_text(data)
    engine = db/"embeddeddolt"
    dot = engine/prefix/".dolt"
    (dot/"noms").mkdir(parents=True)
    (dot/"noms/manifest").write_text("synthetic engine")
    (engine/".lock").touch()
    (dot/"config.json").write_text("{}")
    (dot/"repo_state.json").write_text(json.dumps(dict(
        head="refs/heads/main", remotes={}, backups={}, branches={})))
    home = pathlib.Path(os.environ["HOME"])/".dolt"
    home.mkdir(); (home/"config_global.json").write_text("{}")
    if db.parent.name == "badmetadata":
        (db/"metadata.json").write_text("{")
    sys.exit()
metadata = json.loads((db/"metadata.json").read_text())
prefix = metadata["dolt_database"]
with (db/"interactions.jsonl").open("a") as f:
    f.write(json.dumps([cmd, *args])+"\n")
if cmd == "ping":
    if db.parent.name == "badready": print('{"status":"bad"}')
    else: print(json.dumps(dict(status="ok", resolve_ms=1, store_ms=1, query_ms=1, total_ms=3)))
elif cmd == "where":
    print(json.dumps(dict(path=str(db), database_path=str(db/"embeddeddolt"), prefix=prefix)))
elif cmd == "export":
    pathlib.Path(args[args.index("--output")+1]).write_text('{"_type":"issue","id":"synthetic"}\n')
else:
    print("[]")
'''


def integration():
    if sys.platform != "darwin":
        print("synthetic OS integration skipped: Darwin sandbox required")
        return
    with tempfile.TemporaryDirectory(prefix="domestique-beads-synthetic-") as temp:
        work = Path(temp).resolve()
        home, core, bin_dir = work / "home", work / "core", work / "bin"
        home.mkdir(); bin_dir.mkdir(); (work / "tmp").mkdir()
        fake = bin_dir / "bd"
        fake.write_text(f"#!{Path(sys.executable).resolve()} -ISB\n" + FAKE)
        fake.chmod(0o700)
        sha = hashlib.sha256(fake.read_bytes()).hexdigest()
        dom = work / "domestique.sh"
        dom.write_text(SOURCE.replace(NS["PIN"], sha))
        env = dict(os.environ, HOME=str(home), DOMESTIQUE_HOME=str(core),
                   TMPDIR=str(work / "tmp"), PATH=str(bin_dir) + ":" + os.environ["PATH"],
                   SECRET="SECRET-ENV", BD_DB="SECRET-ROUTE", BEADS_DB="SECRET-ROUTE",
                   PYTHONDONTWRITEBYTECODE="1")
        env.pop("XDG_STATE_HOME", None)

        def run(*args, ok=True):
            proc = subprocess.Popen(list(map(str, args)), cwd=work, env=env,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                    stdin=subprocess.DEVNULL, start_new_session=True)
            try:
                out, err = proc.communicate(timeout=600)
                result = subprocess.CompletedProcess(args, proc.returncode, out, err)
            finally:
                proc.poll()
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                except PermissionError:
                    if proc.poll() is None:
                        raise
                proc.communicate(timeout=5)
            check((result.returncode == 0) == ok, (args, result.stderr, result.stdout))
            check("SECRET" not in result.stdout + result.stderr, "no secret diagnostics")
            return result

        def repo(name):
            p = work / name
            p.mkdir()
            run("git", "init", "-q", p)
            (p / ".git/info").mkdir(exist_ok=True)
            (p / "CLAUDE.md").write_text("SECRET-HOST\n")
            return p

        def refuse_unchanged(*args):
            before = snap(work)
            run(*args, ok=False)
            check(before == snap(work), "whole fixture unchanged on refusal")

        run("bash", dom, "--global", "--platform", "all")
        helper = core / "bin/resolve-core"
        release = (core / "active").read_text().strip().split("=")[1]
        p = repo("positive")
        before = snap(work)
        run("bash", dom, "--local", p, "--with-beads", "--state-only", "--dry-run")
        check(before == snap(work), "dry-run no project/core/index/exclude writes")
        run("bash", dom, "--local", p, "--with-beads", "--state-only")
        mf = p / ".domestique-private/manifest"
        original = mf.read_text()
        check("providers=none\n" in original and not list(p.glob(".*/*/*implementer*")),
              "state-only none zero agents")
        before = snap(work)
        run("bash", dom, "--local", p)
        check(before == snap(work), "bare none rerun creates nothing and preserves Beads")
        beads = original[original.index("beads_path="):]
        for action in ("bind", "read"):
            before = snap(work)
            run("bash", helper, action, core, "orchestrator", release)
            check(before == snap(work), "pure global load no native calls")
        run("bash", dom, "--local", p, "--platform", "codex")
        check(mf.read_text().endswith(beads), "profile selection preserves Beads records")
        role = next(p.glob(".codex/agents/*implementer*"))
        role.write_text(role.read_text() + "\nSECRET-EDIT\n")
        before = snap(work)
        run("bash", dom, "--local", p, "--with-beads", "--state-only")
        check(before == snap(work), "edited native state-only preserves every byte and mtime")
        # Ordered headers/pairs do not require native role records to be sorted.
        # Preserve a valid existing pair/receipt order when not refreshing roles.
        lines = mf.read_text().splitlines(keepends=True)
        mf.write_text("".join(lines[:6] + lines[8:10] + lines[6:8] + lines[10:]))
        receipt = p / ".domestique-private/routing/codex.receipt"
        lines = receipt.read_text().splitlines(keepends=True)
        receipt.write_text("".join(lines[:5] + list(reversed(lines[5:]))))
        before = snap(work)
        run("bash", dom, "--local", p, "--with-beads", "--state-only")
        check(before == snap(work), "state-only preserves valid original metadata ordering")
        refuse_unchanged("bash", dom, "--local", p, "--with-beads", "--platform", "codex", "--force")
        refuse_unchanged("bash", dom, "--uninstall", "--local", p)
        cmd = ["bash", helper, "beads", core, p, release]
        for argv in (["create", "title", "--description", "--db=SECRET-ARG"],
                     ["update", re.search(r"beads_prefix=(.*)", beads)[1] + "-abc", "--claim"],
                     ["export", "--include-memories"]):
            run(*cmd, *argv)
        check((p / ".domestique-private/exports/issues.jsonl").is_file(), "fixed owned export")
        check(mf.read_text().endswith(beads), "runtime does not rewrite initial purge baseline")
        for argv in (["--db", "/elsewhere", "list"], ["export", "--output", "/elsewhere"],
                     ["setup"], ["sql", "SELECT 1"], ["init"], ["reopen", "foreign-id"]):
            refuse_unchanged(*cmd, *argv)
        # Known mutable engine content remains eligible, not a pristine DB test.
        engine = p / ".beads/embeddeddolt"
        (next(engine.glob("*/.dolt/noms")) / "synthetic-runtime-data").write_text("mutation")
        run("bash", helper, "beads-guard", core, p, release)
        for name, content in (("redirect", "/elsewhere"), (".env", "SECRET-ROUTE"),
                              ("dolt-server.yaml", "SECRET-CONFIG")):
            path = p / ".beads" / name
            path.write_text(content)
            refuse_unchanged(*cmd, "list")
            path.unlink()
        metadata = p / ".beads/metadata.json"
        good = metadata.read_bytes()
        for bad in (b"{", b'{"duplicate":1,"duplicate":2}', b"\0",
                    good.replace(b'"embedded"', b'"server"'),
                    good.replace(json.loads(good)["project_id"].encode(),
                                 b"11111111-1111-4111-8111-111111111111")):
            metadata.write_bytes(bad)
            refuse_unchanged(*cmd, "list")
        metadata.write_bytes(good)
        original = mf.read_text()
        for tail in ("unknown=bad\n", "beads_status=ready\n", "beads_created=.beads/foreign:" + "0"*64 + "\n"):
            mf.write_text(original + tail)
            refuse_unchanged(*cmd, "list")
        mf.write_text(original)
        mf.write_text(original.replace("beads_version=1.1.2", "beads_version=1.2.2"))
        refuse_unchanged(*cmd, "list")
        mf.write_text(original)
        for status in ("failed", "future"):
            mf.write_text(original.replace("beads_status=ready", "beads_status=" + status))
            refuse_unchanged(*cmd, "list")
        mf.write_text(original.replace("beads_status=ready", "beads_status=retained"))
        run("bash", helper, "beads-guard", core, p, release)
        mf.write_text(original)
        binary = fake.read_bytes()
        fake.write_bytes(binary + b"\n# changed\n")
        refuse_unchanged(*cmd, "ready")
        unqualified = repo("unqualified")
        refuse_unchanged("bash", dom, "--local", unqualified, "--with-beads", "--state-only")
        fake.write_bytes(binary)
        missing = repo("missing-python")
        missing_script = work / "missing-python.sh"
        dependency_check = "  command -v python3 >/dev/null 2>&1 ||"
        check(dom.read_text().count(dependency_check) == 1, "missing dependency fault anchor")
        missing_script.write_text(dom.read_text().replace(dependency_check, "  false ||"))
        refuse_unchanged("bash", missing_script, "--local", missing, "--with-beads", "--state-only")
        def private_attempt(failed):
            visible = run("git", "-C", failed, "ls-files", "--others",
                          "--exclude-standard").stdout.splitlines()
            status = run("git", "-C", failed, "status", "--porcelain", "-uall").stdout
            for base in (failed / ".domestique-private", failed / ".beads"):
                for path in sorted(base.rglob("*")):
                    if not path.is_file():
                        continue
                    rel = str(path.relative_to(failed))
                    unknown = path.name == "unknown-host-file"
                    run("git", "-C", failed, "check-ignore", "-q", rel, ok=not unknown)
                    check((rel in visible) == unknown, ("actual visibility", rel))
                    check((rel in status) == unknown, ("actual status", rel))

        for name in ("partial", "partialunknown", "zeroexit", "badmetadata", "badready"):
            failed = repo(name)
            (failed / ".gitignore").write_text("# host ignore\n")
            (failed / "unknown-host-file").write_text("synthetic host")
            run("git", "-C", failed, "add", ".gitignore")
            protected = {p: p.read_bytes() for p in
                         [failed / ".gitignore", failed / ".git/config",
                          failed / ".git/index", failed / "CLAUDE.md"]}
            global_before = snap(home), snap(core)
            before = snap(work)
            run("bash", dom, "--local", failed, "--with-beads", "--state-only", "--dry-run")
            check(before == snap(work), "failed-init dry-run writes nothing and invokes no init")
            run("bash", dom, "--local", failed, "--with-beads", "--state-only", ok=False)
            state = failed / ".domestique-private"
            check("beads_status=failed\n" in (state / "beads-attempt").read_text(),
                  "truthful failed attempt")
            check("beads_reservation=.beads:" in (state / "beads-attempt").read_text() and
                  "beads_path_created=" not in (state / "beads-attempt").read_text(),
                  "exclusive reservation is not successful native creation")
            check(not (state / "manifest").exists(), "no success-shaped manifest")
            check("beads_created=" not in (state / "pending").read_text(), "no successful provenance")
            exclude = failed / ".git/info/exclude"
            check(f"protected-exclude={exclude}:{hashlib.sha256(exclude.read_bytes()).hexdigest()}\n"
                  in (state / "published").read_text(), "actual exclude publication recorded")
            private_attempt(failed)
            run("git", "-C", failed, "check-ignore", "-q", "unknown-host-file", ok=False)
            check(all(p.read_bytes() == data for p, data in protected.items()),
                  "failed init preserves host policy/config")
            check(global_before == (snap(home), snap(core)), "failed init preserves HOME/core")
            refuse_unchanged("bash", dom, "--local", failed, "--with-beads", "--state-only")
            refuse_unchanged("bash", dom, "--uninstall", "--local", failed)
        host = repo("host")
        (host / ".beads").mkdir()
        (host / ".beads/metadata.json").write_text("synthetic foreign")
        refuse_unchanged("bash", dom, "--local", host, "--with-beads", "--platform", "all")
        run("git", "-C", host, "check-ignore", "-q", ".beads/metadata.json", ok=False)
        check(not (host / ".claude").exists(), "combined host collision before profiles")
        combined = repo("combined")
        run("bash", dom, "--local", combined, "--platform", "claude")
        manifest = combined / ".domestique-private/manifest"
        lines = manifest.read_text().splitlines(keepends=True)
        # Deliberately distinct creation history must survive too.
        lines[6] = lines[6].rsplit(":", 1)[0] + ":" + "a" * 64 + "\n"
        manifest.write_text("".join(lines[:6] + lines[8:10] + lines[6:8]))
        original_pairs = manifest.read_text().splitlines()[6:]
        receipt = combined / ".domestique-private/routing/claude.receipt"
        lines = receipt.read_text().splitlines(keepends=True)
        receipt.write_text("".join(lines[:5] + list(reversed(lines[5:]))))
        original_receipt = receipt.read_bytes()
        unselected = next(combined.glob(".claude/agents/*implementer*"))
        unselected.write_text(unselected.read_text() + "\nSECRET-UNSELECTED\n")
        original_unselected = unselected.read_bytes()
        before = snap(work)
        run("bash", dom, "--local", combined, "--with-beads", "--platform", "copilot", "--dry-run")
        check(before == snap(work), "mixed-provider projected dry-run no writes")
        run("bash", dom, "--local", combined, "--with-beads", "--platform", "copilot")
        check(unselected.read_bytes() == original_unselected, "unrefreshed edited provider untouched")
        check("providers=claude-copilot\n" in (combined / ".domestique-private/manifest").read_text(),
              "combined selection preserves provider union")
        check(manifest.read_text().splitlines()[6:10] == original_pairs and
              receipt.read_bytes() == original_receipt, "unselected pair/receipt order and history preserved")
        link = combined / ".beads/redirect"
        link.symlink_to(host)
        refuse_unchanged("bash", helper, "beads", core, combined, release, "list")
        link.unlink()
        run("git", "-C", combined, "add", "-f", ".beads/metadata.json")
        refuse_unchanged("bash", helper, "beads", core, combined, release, "list")
        parent = repo("shared-parent")
        wt = work / "shared-linked"
        run("git", "-C", parent, "worktree", "add", "--orphan", "-b", "synthetic-linked", wt)
        (wt / ".beads").mkdir()
        refuse_unchanged("bash", dom, "--local", parent, "--with-beads", "--platform", "all")
        check(not (parent / ".beads").exists(), "shared foreign collision before exclusive DB claim")
        (wt / ".beads").rmdir()  # Only our own known empty synthetic collision.
        run("bash", dom, "--local", parent, "--with-beads", "--state-only")
        parent_manifest = (parent / ".domestique-private/manifest").read_bytes()
        run("bash", dom, "--local", wt, "--with-beads", "--state-only")
        check((parent / ".domestique-private/manifest").read_bytes() == parent_manifest,
              "linked init preserves other attachment")
        exclude = (parent / ".git/info/exclude").read_text()
        check(exclude.count("/.beads/metadata.json\n") == 1 and "\n/.beads/\n" not in exclude,
              "shared exact Beads union, never whole DB ignore")
        for target in (parent, wt):
            run("git", "-C", target, "check-ignore", "-q", ".beads/metadata.json")
        shared_fail = work / "shared-failure"
        shared_fail.mkdir()
        failed_wt = shared_fail / "badready"
        run("git", "-C", parent, "worktree", "add", "--orphan", "-b", "failed-linked", failed_wt)
        shared_before = (parent / ".git/info/exclude").read_bytes()
        def shared_protected():
            # Owned info/exclude publication may change its mtime. Its exact
            # bytes (including unrelated patterns) are checked separately.
            return ([row for row in snap(parent) if row[0] != ".git/info/exclude"],
                    snap(wt), snap(home), snap(core))
        parent_before = shared_protected()
        run("bash", dom, "--local", failed_wt, "--with-beads", "--state-only", ok=False)
        check(shared_before == (parent / ".git/info/exclude").read_bytes(),
              "failed linked initialization preserves existing shared exact rules")
        check(parent_before == shared_protected(),
              "failed linked initialization preserves other projects, Git admin, HOME/core")
        private_attempt(failed_wt)
        refuse_unchanged("bash", dom, "--local", failed_wt, "--with-beads", "--state-only")
        refuse_unchanged("bash", dom, "--uninstall", "--local", failed_wt)

        # Mandatory-trigger source faults, never production environment hooks.
        for name, anchor in (
            ("claim-collision", '    L_DB_CLAIM="$(local_beads_python claim "$L_ROOT/.beads")" || exit 1\n'),
            ("postclaim-collision", "    L_MANIFEST_PURPOSE=reservation\n"),
            ("protected-callback", '    newbeads="$(local_beads_python init "$L_ROOT" "${beads_args[@]}" "$L_DB_CLAIM")" || exit 1\n'),
        ):
            collision = repo(name)
            faulty = work / (name + ".sh")
            source = dom.read_text()
            check(source.count(anchor) == 1, "fault injection anchor unique")
            fault = ('    mkdir -p "$L_ROOT/.beads"\n'
                     '    printf "synthetic foreign\\n" > "$L_ROOT/.beads/metadata.json"\n')
            if name == "protected-callback":
                fault = '    exit 0 # simulate an erroneously successful callback exit\n'
            faulty.write_text(source.replace(anchor, fault + anchor))
            run("bash", faulty, "--local", collision, "--with-beads", "--state-only", ok=False)
            state = collision / ".domestique-private"
            if name == "protected-callback":
                check((state / "pending").is_file() and (state / "published").is_file(),
                      "callback failure retains actual protected publication evidence")
                check("protected-exclude=" in (state / "published").read_text() and
                      "beads_created=" not in (state / "published").read_text(),
                      "callback evidence is protection, never success")
                private_attempt(collision)
            else:
                check((collision / ".beads/metadata.json").read_text() == "synthetic foreign\n",
                      "collision injection triggered; foreign bytes preserved")
                run("git", "-C", collision, "check-ignore", "-q", ".beads/metadata.json", ok=False)
                check(".beads/metadata.json" in run(
                    "git", "-C", collision, "ls-files", "--others", "--exclude-standard").stdout,
                    "late foreign collision remains visible")
                check(not (state / "pending").exists(), "collision precedes journal writes")
            refuse_unchanged("bash", dom, "--local", collision, "--with-beads", "--state-only")
            refuse_unchanged("bash", dom, "--uninstall", "--local", collision)
        # Compatible older owned helper: removing only its capability marker
        # must require a global update before any local change/native operation.
        old_helper = helper.read_bytes()
        gm = core / "state/global-manifest"
        old_gm = gm.read_bytes()
        old_hash = hashlib.sha256(old_helper).hexdigest().encode()
        missing_api = old_helper.replace(b"# beads_guard_api=2", b"# beads_guard_api=1")
        helper.write_bytes(missing_api)
        gm.write_bytes(old_gm.replace(old_hash, hashlib.sha256(missing_api).hexdigest().encode()))
        fresh = repo("old-helper")
        refuse_unchanged("bash", dom, "--local", fresh, "--with-beads", "--state-only")
        helper.write_bytes(old_helper); gm.write_bytes(old_gm)
        colon = repo("colon:context")
        refuse_unchanged("bash", dom, "--local", colon, "--with-beads", "--state-only")
        # Historical source is only a fixture factory, not current acceptance.
        # This gives .4 positive legacy creation evidence; state-only must not
        # silently perform even that otherwise-eligible profile migration.
        legacy = repo("legacy-state-only")
        historical = work / "historical-fixture.sh"
        historical.write_bytes(subprocess.check_output(
            ["git", "-C", str(ROOT), "show", "b60feef:domestique.sh"]))
        run("bash", historical, "--guest", "--platform", "codex", legacy)
        refuse_unchanged("bash", dom, "--local", legacy, "--with-beads", "--state-only")
        late = repo("late-exclusion")
        hook, marker = work / "late-exclusion.sh", work / "late-exclusion-trigger"
        hook.write_text("""set -T
trap 'if [ "$BASH_COMMAND" = "$INJECT_COMMAND" ] && [ -n "${newbeads:-}" ] && [ ! -e "$INJECT_MARKER" ]; then
  printf "# fixture late exclusion change\\n" > "$L_EXCLUDE"
  printf "triggered\\n" > "$INJECT_MARKER"
fi' DEBUG
""")
        injected_env = dict(env, BASH_ENV=str(hook), INJECT_MARKER=str(marker),
                            INJECT_COMMAND='local_remove_check "$state/pending" "$pending_hash" "$L_ROOT"')
        result = subprocess.run(
            ["bash", str(dom), "--local", str(late), "--with-beads", "--state-only"],
            cwd=work, env=injected_env, capture_output=True, text=True)
        check(marker.is_file(), "late exclusion mutation actually triggered")
        check(result.returncode != 0 and "PARTIAL" in result.stderr and
              "installed providers=" not in result.stdout, "no success after lost privacy")
        check((late / ".domestique-private/pending").is_file(), "pending retained for reconciliation")
        refuse_unchanged("bash", helper, "beads", core, late, release, "ready")


help_tests()
unit_tests()
integration()
print(f"private Beads SYNTHETIC protocol/production integration: {COUNT} passed")
