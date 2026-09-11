"""Current unsupported backend boundary; isolated metadata fixtures, never bd.

Synthetic ownership/failed records are rejection fixtures, NOT a safe backend.
Execute emitted Markdown/TOML fences separately to prove load != database use.
"""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parent.parent
DOM, UP = ROOT / "domestique.sh", ROOT / "update.sh"
COUNT = 0


def check(value, label):
    global COUNT
    assert value, label
    COUNT += 1


def tree():
    result = []
    for p in sorted(W.rglob("*")):
        s = p.lstat()
        data = os.readlink(p) if p.is_symlink() else p.read_bytes() if p.is_file() else None
        result.append((str(p.relative_to(W)), s.st_mode,
                       s.st_mtime_ns if p.is_file() else None, data))
    return result


def run(*args, cwd=None, env=None):
    return subprocess.run([str(x) for x in args], cwd=cwd or W, env=env or ENV,
                          capture_output=True, text=True)


def succeeds(*args, **kwargs):
    p = run(*args, **kwargs)
    check(p.returncode == 0, (args, p.stderr))
    return p


def refuses(*args, status=1, diagnostic=None, **kwargs):
    before = tree()
    p = run(*args, **kwargs)
    check(p.returncode != 0 if status is None else p.returncode == status,
          (args, p.returncode, p.stderr))
    check(p.stdout == "", ("refusal stdout", p.stdout))
    check(bool(p.stderr) and "SECRET" not in p.stderr, "metadata-only diagnostic")
    if diagnostic:
        check(diagnostic in p.stderr, (diagnostic, p.stderr))
    check(before == tree(), ("whole fixture byte/mode/mtime identity", args))
    check(not LOG.exists(), "zero forbidden calls, even ignored failures")
    return p


def repo(name):
    p = W / name
    p.mkdir()
    succeeds("git", "init", "-q", p)
    return p


def manifest(p, tail=""):
    state = p / ".domestique-private"
    state.mkdir(exist_ok=True)
    (state / "manifest").write_text(
        f"format=1\nscope=local\nworktree_root={p}\ncore_root={CORE}\n"
        f"core_api=1\nproviders=none\n{tail}")


def guard(p, diagnostic):
    return refuses("bash", HELPER, "beads-guard", CORE, p, RELEASE,
                   diagnostic=f"domestique Beads: {diagnostic};")


with tempfile.TemporaryDirectory() as temp:
    W = Path(temp).resolve()
    HOME, CORE = W / "home", W / "core"
    HOME.mkdir()
    (W / "tmp").mkdir()
    LOG = W / "forbidden-calls"
    forbidden = W / "forbidden"
    forbidden.mkdir()
    # The marker is checked after EVERY refusal, and whole-W snapshots catch
    # calls even if their nonzero result was swallowed by production code.
    for cmd in ("bd", "curl", "wget", "claude", "codex", "copilot", "cp"):
        f = forbidden / cmd
        f.write_text("#!/usr/bin/env python3\nimport os\nfrom pathlib import Path\n"
                     "p=Path(os.environ['FORBIDDEN_LOG'])\n"
                     "p.write_text('FORBIDDEN-CALL')\nraise SystemExit(99)\n")
        f.chmod(0o700)
    ENV = dict(os.environ, HOME=str(HOME), DOMESTIQUE_HOME=str(CORE),
               TMPDIR=str(W / "tmp"), FORBIDDEN_LOG=str(LOG),
               PYTHONDONTWRITEBYTECODE="1",
               PATH=f"{forbidden}:{os.environ['PATH']}")
    ENV.pop("XDG_STATE_HOME", None)
    empty = repo("empty")
    # Refusal is before core lookup, target creation, bd lookup/probe, fetch,
    # copying local source, preview/apply, profile/none-manifest installation.
    for script in (DOM, UP):
        sources = [()] if script == DOM else [
            ("--source", DOM), ("--source", "https://invalid.invalid/never"),
            ("--source", W / "absent-source")]
        for source in sources:
            for target in (empty, W / "absent-target"):
                for mode in ((), ("--state-only",), ("--platform", "all")):
                    for dry in ((), ("--dry-run",)):
                        refuses("bash", script, "--local", target, "--with-beads",
                                *mode, *dry, *source, diagnostic="no certified private backend")
        for args in (
            ("--with-beads",), (empty, "--with-beads"),
            ("--state-only",), ("--local", empty, "--state-only"),
            ("--with-beads", "--state-only"),
            ("--global", "--with-beads"),
            ("--global", "--local", empty, "--with-beads"),
            ("--local", empty, "--with-beads", "--state-only", "--platform", "all"),
            ("--local", empty, "--with-beads", "--platform", "bad"),
            ("--local", empty, "--with-beads", "--uninstall"),
            ("--local", empty, "--with-beads", "--purge-beads"),
            ("--local", empty, "--with-beads", "--no-guest"),
        ):
            refuses("bash", script, *args, status=2)
    check(not CORE.exists() and list(HOME.iterdir()) == [], "no implicit global install")
    # cp is permitted ONLY for ordinary real profile/core fixture installation.
    (forbidden / "cp").unlink()
    succeeds("bash", DOM, "--global", "--platform", "all")
    HELPER = CORE / "bin/resolve-core"
    RELEASE = (CORE / "active").read_text().strip().split("=")[1]
    definitions = DOM.read_text().split("\nusage() {", 1)[0]
    before = tree()
    succeeds("bash", "-c", definitions)  # load installer definitions alone
    succeeds("bash", "-c", definitions + '\nlocal_preflight "$1" none',
             "--", empty)
    succeeds("bash", HELPER, "bind", CORE, "orchestrator", RELEASE)
    succeeds("bash", HELPER, "read", CORE, "orchestrator", RELEASE)
    check(tree() == before and not LOG.exists(), "load and preflight are purely read-only")
    guard(empty, "missing")
    normal = repo("normal-profile")
    succeeds("bash", DOM, "--local", normal, "--platform", "all")
    guard(normal, "missing")
    none = repo("none")
    manifest(none)
    guard(none, "missing")
    host = repo("host")
    (host / ".beads").mkdir()
    (host / ".beads/host.db").write_text("SECRET-HOST-DB")
    guard(host, "host-unowned")
    (none / ".beads").mkdir()
    guard(none, "host-unowned")
    symlink = repo("symlink")
    (symlink / ".beads").symlink_to(host / ".beads")
    guard(symlink, "unsafe-path")
    for rel in (".beads", ".beads/missing.db", ".domestique-private",
                ".domestique-private/manifest"):
        for kind in ("file", "symlink", "gitlink"):
            p = repo(f"indexed-{rel.replace('/', '-')}-{kind}")
            leaf = p / rel
            leaf.parent.mkdir(parents=True, exist_ok=True)
            if kind == "gitlink":
                succeeds("git", "-C", p, "-c", "user.name=Test",
                         "-c", "user.email=test@example.invalid", "commit",
                         "--allow-empty", "-qm", "fixture")
                oid = succeeds("git", "-C", p, "rev-parse", "HEAD").stdout.strip()
                succeeds("git", "-C", p, "update-index", "--add",
                         "--cacheinfo", f"160000,{oid},{rel}")
            else:
                if kind == "symlink":
                    leaf.symlink_to(W / "absent")
                else:
                    leaf.write_text("SECRET-INDEX")
                succeeds("git", "-C", p, "add", "--", f":(literal){rel}")
                leaf.unlink()  # index-only leaf/ancestor evidence
            guard(p, "tracked-index")
    for tail in ("beads_status=ready\n", "beads_status=failed\n",
                 "beads_path=.beads\n", "beads_path_created=by-init:fake\n",
                 "unknown=SECRET\n", "\0"):
        p = repo(f"bad-record-{COUNT}")
        manifest(p, tail)
        guard(p, "invalid-private")
    for record in ("pending", "published", "failed", "unknown"):
        p = repo(f"bad-private-{record}")
        manifest(p)
        (p / ".domestique-private" / record).write_text("SECRET")
        guard(p, "invalid-private")
    missing_manifest = repo("missing-manifest")
    (missing_manifest / ".domestique-private").mkdir()
    guard(missing_manifest, "invalid-private")
    bad_core = repo("manifest-other-core")
    manifest(bad_core)
    mf = bad_core / ".domestique-private/manifest"
    mf.write_text(mf.read_text().replace(f"core_root={CORE}", f"core_root={HOME}"))
    guard(bad_core, "invalid-private")
    for target in (W / "absent", HOME, str(empty) + "/.", W):
        refuses("bash", HELPER, "beads-guard", CORE, target, RELEASE,
                diagnostic="invalid-project")
    for args in ((), (CORE,), (CORE, empty), (CORE, empty, RELEASE, "extra")):
        refuses("bash", HELPER, "beads-guard", *args, status=2, diagnostic="usage")
    refuses("bash", HELPER, "bad-action", status=2, diagnostic="usage")
    for release in ("", "bad", "r-" + "0" * 64):
        refuses("bash", HELPER, "beads-guard", CORE, empty, release,
                diagnostic="invalid-core")
    refuses("bash", HELPER, "beads-guard", W / "absent-core", empty, RELEASE,
            diagnostic="invalid-core")

    # Actual installed wrappers: TOML decode, execute all three fences. Guard
    # failure must prevent a following bd command, even in a shell without -e.
    wrappers = list(HOME.rglob("SKILL.md")) + list(HOME.rglob("*implementer.*")) + list(HOME.rglob("*reviewer.*"))
    wrappers += list(normal.glob(".*/*/*implementer.*")) + list(normal.glob(".*/*/*reviewer.*"))
    check(len(wrappers) == 21, "9 skills, 6 global and 6 local roles")
    helper_bytes = HELPER.read_bytes()
    active = CORE / "active"
    active_bytes = active.read_bytes()
    for wrapper in wrappers:
        text = wrapper.read_text()
        if wrapper.suffix == ".toml":
            text = tomllib.loads(text)["developer_instructions"]
        blocks = re.findall(r"^```bash\n(.*?)^```$", text, re.M | re.S)
        check(len(blocks) == 3, "separate executable load/route/guard")
        for block in blocks:
            succeeds("bash", "-n", "-c", block)
        before = tree()
        succeeds("bash", "-c", blocks[0], "--", RELEASE, cwd=normal)
        check(before == tree() and not LOG.exists(), "emitted loader no bd/writes")
        command = blocks[2] + "\nbd create MUST-NOT-RUN\n"
        refuses("bash", "-c", command, "--", RELEASE, cwd=normal,
                diagnostic="domestique Beads: missing;")
        # Ambient release/active cannot rescue a missing/invalid literal.
        for args in ((), ("",), ("bad",)):
            refuses("bash", "-c", command, "--", *args, cwd=normal,
                    status=None, env=dict(ENV, DOMESTIQUE_BOUND_RELEASE=RELEASE))
        active.write_text("release=bad\n")
        refuses("bash", "-c", command, "--", RELEASE, cwd=normal,
                diagnostic="domestique Beads: missing;")
        active.write_bytes(active_bytes)
        # Missing capability is a stop even if an old helper exits success.
        HELPER.write_bytes(b"#!/bin/bash\nexit 0\n")
        refuses("bash", "-c", command, "--", RELEASE, cwd=normal,
                diagnostic="bash update.sh --global")
        HELPER.unlink()
        refuses("bash", "-c", command, "--", RELEASE, cwd=normal,
                diagnostic="bash update.sh --global")
        HELPER.write_bytes(helper_bytes)
    check(not LOG.exists(), "zero bd/network/native calls throughout")

print(f"beads-guard current unsupported backend: {COUNT} passed")
