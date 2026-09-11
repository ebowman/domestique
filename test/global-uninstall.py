"""Current owned-global removal. Physical isolated HOME/core/projects; no clients.

No recursive root deletion, even for fixtures: cleanup unlinks explicit observed
fixture leaves then rmdirs empty fixture directories (never follows symlinks).
"""
import ast
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
DOM = ROOT / "domestique.sh"
SETS = {"claude": {"claude"}, "codex": {"codex"}, "copilot": {"copilot"},
        "both": {"claude", "codex"}, "claude-copilot": {"claude", "copilot"},
        "codex-copilot": {"codex", "copilot"}, "all": {"claude", "codex", "copilot"}}
COUNT = 0


def check(value, label):
    global COUNT
    assert value, label
    COUNT += 1


def snapshot(root):
    h = hashlib.sha256()
    for p in [root, *sorted(root.rglob("*"))]:
        if not p.exists() and not p.is_symlink():
            h.update(b"absent")
            continue
        s = p.lstat()
        h.update(repr((str(p.relative_to(root)), s.st_mode)).encode())
        if p.is_symlink():
            h.update(os.readlink(p).encode())
        elif p.is_file():
            h.update(str(s.st_mtime_ns).encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def clean(root):
    # Explicit fixture paths only, bottom-up, no shutil.rmtree/rm -rf.
    for p in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if p.is_symlink() or not p.is_dir():
            p.unlink()
        else:
            p.rmdir()
    root.rmdir()


@contextmanager
def fixture():
    global W, HOME, CORE, ENV, LOG
    W = Path(tempfile.mkdtemp(prefix="domestique-remove-test-")).resolve()
    HOME, CORE = W / "home", W / "core"
    for name in ("home", "tmp", "forbidden"):
        (W / name).mkdir()
    LOG = W / "forbidden-call"
    for cmd in ("bd", "claude", "codex", "copilot", "curl", "wget"):
        p = W / "forbidden" / cmd
        p.write_text("#!/usr/bin/env python3\nimport os\nfrom pathlib import Path\n"
                     "Path(os.environ['FORBIDDEN_LOG']).write_text('called')\n"
                     "raise SystemExit(99)\n")
        p.chmod(0o700)
    ENV = dict(os.environ, HOME=str(HOME), DOMESTIQUE_HOME=str(CORE),
               TMPDIR=str(W / "tmp"), PYTHONDONTWRITEBYTECODE="1",
               FORBIDDEN_LOG=str(LOG), PATH=f"{W / 'forbidden'}:{os.environ['PATH']}")
    ENV.pop("XDG_STATE_HOME", None)
    try:
        yield
        check(not LOG.exists(), "zero native/network/Beads calls")
    finally:
        clean(W)


def run(*args, env=None, cwd=None):
    return subprocess.run([str(x) for x in args], env=env or ENV, cwd=cwd or W,
                          capture_output=True, text=True)


def success(*args, **kwargs):
    p = run(*args, **kwargs)
    check(p.returncode == 0, (args, p.returncode, p.stdout, p.stderr))
    return p


def install(selection="all", script=DOM):
    success("/bin/bash", script, "--global", "--platform", selection)


def remove(*args, status=0, **kwargs):
    p = run("/bin/bash", DOM, "--uninstall", "--global", *args, **kwargs)
    check(p.returncode == status, (args, p.returncode, p.stdout, p.stderr))
    check("SECRET" not in p.stdout + p.stderr, "no secret diagnostics")
    return p


def refusal(*args, status=1, **kwargs):
    before = snapshot(W)
    p = remove(*args, status=status, **kwargs)
    check(snapshot(W) == before, ("refusal whole-tree identity", p.stderr))
    return p


def records():
    lines = (CORE / "state/global-manifest").read_text().splitlines()
    result = {}
    for line in lines[5::2]:
        key, digest = line.removeprefix("created=").rsplit(":", 1)
        base = lines[lines.index(line) + 1].removeprefix("baseline=")
        check(base.rsplit(":", 1)[0] == key, "paired metadata")
        result[key] = (digest, base.rsplit(":", 1)[1])
    return result


def dest(key):
    provider, rel = key.split(":", 1)
    return (CORE if provider == "core" else HOME) / rel


def project(name):
    p = W / name
    p.mkdir()
    success("git", "init", "-q", p)
    success("/bin/bash", DOM, "--local", p, "--platform", "all")
    return p


def empty_core_containers():
    check(not any(p.is_file() or p.is_symlink() for p in CORE.rglob("*")),
          "last removal leaves only empty unproven containers")
    # Explicit manual reconciliation, NOT installer directory adoption.
    for p in sorted(CORE.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        p.rmdir()
    CORE.rmdir()


# Each actual canonical installed union supports selectorless dry-run/removal.
for selection in SETS:
    with fixture():
        install(selection)
        owned = records()
        if selection != "all":
            absent_provider = next(iter(SETS["all"] - SETS[selection]))
            before = snapshot(W)
            remove("--platform", absent_provider)
            check(snapshot(W) == before, "valid state with no selected ownership is clean no-op")
        before = snapshot(W)
        p = remove("--dry-run")
        check("would remove" in p.stdout and snapshot(W) == before,
              "dry-run complete identity and honest plan")
        p = remove()
        check("local profiles remain" in p.stderr, "last-provider warning")
        check(all(not dest(k).exists() for k in owned), "every exact owned leaf gone")
        refusal()  # explicit no-state refusal, not unknown adoption
        check(CORE.is_dir() and HOME.is_dir(), "unproven roots retained")

# Every selected subset from all, with two REAL local project trees and host
# settings/instructions/forks. Reinstall follows documented manual empty-dir
# reconciliation; local adapter fences stop without core, then work again.
for selection, providers in SETS.items():
    with fixture():
        install()
        projects = [project("project-a"), project("project-b")]
        project_hashes = [snapshot(p) for p in projects]
        host = HOME / ".claude/settings.json"
        host.write_text("SECRET-HOST-SETTINGS\n")
        fork = HOME / ".claude/agents/my-own-fork.md"
        fork.write_text("user-maintained fork\n")
        host_hashes = [snapshot(p) for p in (host, fork)]
        owned = records()
        kept = {k: snapshot(dest(k)) for k in owned
                if k.split(":")[0] not in providers and
                (k.split(":")[0] != "core" or selection != "all")}
        before = snapshot(W)
        remove("--platform", selection, "--dry-run")
        check(snapshot(W) == before, "scoped dry-run whole-tree identity")
        remove("--platform", selection, cwd=projects[0])
        check([snapshot(p) for p in projects] == project_hashes,
              "multiple actual local project trees unchanged")
        check([snapshot(p) for p in (host, fork)] == host_hashes, "host/fork untouched")
        check(all(snapshot(dest(k)) == v for k, v in kept.items()),
              "all unselected and shared core bytes/modes/mtimes identical")
        check(all(not dest(k).exists() for k in owned if k not in kept),
              "only selected owned exact leaves removed")
        if selection != "all":
            check(records() == {k: v for k, v in owned.items() if k in kept},
                  "retained original provenance, no rebaseline")
            remaining = SETS["all"] - providers
            m = (CORE / "state/global-manifest").read_text()
            check(f"providers={next(k for k, v in SETS.items() if v == remaining)}\n" in m,
                  "canonical remaining provider union")
            success("/bin/bash", CORE / "bin/resolve-core", "bind", CORE, "reviewer")
        else:
            leaf = projects[0] / ".claude/agents/domestique-claude-local-reviewer.md"
            fence = re.search(r"```bash\n(.*?)```", leaf.read_text(), re.S)[1]
            p = run("/bin/bash", "-c", fence, "--", "r-" + "0" * 64)
            check(p.returncode != 0 and not p.stdout, "actual local fence stops at missing core")
            before = snapshot(W)
            p = run("/bin/bash", DOM, "--global")
            check(p.returncode != 0 and snapshot(W) == before,
                  "empty unproven core containers not adopted on reinstall")
            empty_core_containers()
            install()
            release = success("/bin/bash", CORE / "bin/resolve-core", "bind",
                              CORE, "reviewer").stdout.strip()
            success("/bin/bash", "-c", fence, "--", release)
            check([snapshot(p) for p in projects] == project_hashes,
                  "explicit global restoration requires no local repair")

# Edited selected provider retained WHOLE; clean selected providers removed,
# original baselines unchanged; unselected edits aren't copied or rewritten.
for selected in ("all", "claude"):
    for force in ((), ("--force",)):
        with fixture():
            install()
            edited = HOME / ".codex/agents/domestique-codex-reviewer.toml"
            with edited.open("a") as f:
                f.write("\nSECRET-EDITED-NATIVE-NO-COPY\n")
            owned = records()
            retained = {k: snapshot(dest(k)) for k in owned
                        if k.startswith("core:") or k.startswith("codex:") or
                        (selected == "claude" and k.startswith("copilot:"))}
            before = snapshot(W)
            rc = 1 if selected == "all" else 0
            p = remove("--platform", selected, "--dry-run", *force, status=rc)
            check(snapshot(W) == before, "edited dry-run full identity")
            if rc:
                check("would retain WHOLE" in p.stderr, "dry retained notice")
            p = remove("--platform", selected, *force, status=rc)
            if rc:
                check("retain WHOLE" in p.stderr, "apply retained notice")
            check(all(snapshot(dest(k)) == h for k, h in retained.items()),
                  "retained edited whole provider/shared core unchanged")
            check(records() == {k: v for k, v in owned.items() if k in retained},
                  "original valid metadata retained exactly")
            check([p for p in W.rglob("*") if p.is_file() and
                   b"SECRET-EDITED-NATIVE-NO-COPY" in p.read_bytes()] == [edited],
                  "no secret copies, snapshots, backups, logs")
            refusal("--platform", "codex", "--force")

# Missing/malformed/NUL/unknown ownership, exact symlink/index collisions, old
# retained release history and unknown extra files are all prewrite refusals.
with fixture():
    install()
    m = CORE / "state/global-manifest"
    original = m.read_bytes()
    for data in (b"", original + b"unknown=SECRET\n", original + b"\0\n",
                 original.replace(b"scope=global", b"scope=glo\0bal"),
                 original[:-1], original.replace(b"created=", b"baseline=", 1),
                 original.replace(b"providers=all", b"providers=none"),
                 original.replace(b"core_api=1", b"core_api=2"),
                 original.replace(b"core:active", b"core:../escape")):
        m.write_bytes(data)
        refusal("--force")
        m.write_bytes(original)
    # Baseline-identical native files with missing state are never adopted.
    m.unlink()
    refusal("--force")
    m.write_bytes(original)
    m.rename(CORE / "saved-manifest")
    m.symlink_to(CORE / "saved-manifest")
    refusal()
    m.unlink()
    (CORE / "saved-manifest").rename(m)
    for rel in ("bin/resolve-core", "active"):
        path = CORE / rel
        original_leaf = path.read_bytes()
        path.write_bytes(b"SECRET-CORRUPT-CORE\n")
        refusal("--force")
        path.write_bytes(original_leaf)
    native = HOME / ".claude/agents/domestique-claude-reviewer.md"
    pristine = native.read_bytes()
    native.unlink()
    refusal()
    native.symlink_to(W / "missing")
    refusal("--force")
    native.unlink()
    native.mkdir()
    refusal()
    native.rmdir()
    native.write_bytes(pristine)
    parent = HOME / ".claude/agents"
    parent.rename(HOME / "agents-saved")
    parent.symlink_to(HOME / "agents-saved", target_is_directory=True)
    refusal("--force")
    parent.unlink()
    (HOME / "agents-saved").rename(parent)
    unknown = CORE / "unknown"
    unknown.write_text("SECRET-UNKNOWN\n")
    refusal("--force")
    unknown.unlink()
    unknown = CORE / "newline\nentry"
    unknown.write_text("unknown\n")
    refusal("--force")
    unknown.unlink()
    for bad in ("relative", str(CORE) + "/../escape", str(HOME),
                str(HOME / ".claude/core")):
        refusal("--force", env=dict(ENV, DOMESTIQUE_HOME=bad))
    alias = W / "core-link"
    alias.symlink_to(CORE, target_is_directory=True)
    refusal("--force", env=dict(ENV, DOMESTIQUE_HOME=str(alias)))
    alias.unlink()
    alias = W / "home-link"
    alias.symlink_to(HOME, target_is_directory=True)
    refusal("--force", env=dict(ENV, HOME=str(alias)))
    alias.unlink()

for index_path in ("skills/domestique-claude/SKILL.md", "skills"):
    with fixture():
        install()
        native_root = HOME / ".claude"
        success("git", "init", "-q", native_root)
        # Exact index-only ancestor object; no working-tree manipulation.
        oid = success("git", "-C", native_root, "hash-object", "-w", "--stdin",
                      ).stdout.strip()
        success("git", "-C", native_root, "update-index", "--add", "--cacheinfo",
                f"100644,{oid},{index_path}")
        p = refusal("--force")
        check("indexed" in p.stderr or "index validation" in p.stderr,
              ("bounded exact index query detects leaf/ancestor object", p.stderr))

with fixture():
    install()
    old = (CORE / "active").read_text().strip().split("=")[1]
    v2 = W / "v2.sh"
    v2.write_text(DOM.read_text().replace("# Domestique private core: reviewer",
                                        "# Domestique private core: reviewer test-v2"))
    install(script=v2)
    check(old != (CORE / "active").read_text().strip().split("=")[1],
          "real upgrade retains different historical release")
    manifest = CORE / "state/global-manifest"
    metadata = manifest.read_text()
    manifest.write_text("".join(line for line in metadata.splitlines(keepends=True)
                                if f"core:releases/{old}/roles/goal.md:" not in line))
    refusal("--force")
    manifest.write_text(metadata)
    unknown = CORE / "releases" / old / "unknown-extra"
    unknown.write_text("SECRET-OLD-EXTRA\n")
    refusal("--force")
    unknown.unlink()
    owned = records()
    remove()
    check(all(not dest(k).exists() for k in owned), "all positively owned release history removed")

# PATH command failure and races are real, triggered operations, no production
# test hooks. Journals record completed unlinks, not the planned inventory.
for fault in ("unlink", "leaf-edit", "manifest-directory", "manifest-edited", "journal-directory"):
    with fixture():
        install()
        owned = records()
        old_manifest = (CORE / "state/global-manifest").read_bytes()
        stubs = W / "stubs"
        stubs.mkdir()
        trigger = W / "trigger"
        tool = "mv" if fault.startswith("manifest") else "unlink"
        real = shutil.which(tool)
        target = (HOME / ".claude/agents/domestique-claude-reviewer.md"
                  if tool == "unlink" else CORE / "state")
        if fault == "leaf-edit":
            target = HOME / ".claude/skills/domestique-claude/SKILL.md"
        stub = stubs / tool
        stub.write_text(
            "#!/usr/bin/env python3\nimport os,sys\nfrom pathlib import Path\n"
            f"target={str(target)!r}\ntrigger=Path({str(trigger)!r})\n"
            "if sys.argv[-1] == target and not trigger.exists():\n"
            " trigger.write_text('triggered')\n" +
            (" raise SystemExit(73)\n" if fault == "unlink" else
             f" Path({str(HOME / '.claude/agents/domestique-claude-reviewer.md')!r}).write_text('SECRET-RACING-LEAF\\n')\n"
             if fault == "leaf-edit" else
             f" p=Path({str(CORE / 'state/published')!r}); p.unlink(); p.mkdir()\n"
             if fault == "journal-directory" else
             f" p=Path({str(CORE / 'state/global-manifest')!r}); p.unlink(); p.mkdir()\n"
             if fault == "manifest-directory" else "") +
            (f" os.spawnv(os.P_WAIT, {real!r}, [{real!r}, *sys.argv[1:]])\n"
             f" Path({str(CORE / 'state/global-manifest')!r}).write_text('SECRET-RACING-STATE\\n')\n"
             " raise SystemExit(0)\n" if fault == "manifest-edited" else "") +
            f"os.execv({real!r}, [{real!r}, *sys.argv[1:]])\n")
        stub.chmod(0o700)
        env = dict(ENV, PATH=f"{stubs}:{ENV['PATH']}")
        p = remove("--platform", "claude", env=env, status=1)
        check(trigger.exists(), ("injection actually triggered", fault))
        check("PARTIAL removal" in p.stderr, "honest interrupted removal")
        check((CORE / "state/pending").is_file(), "pending protects interrupted uninstall")
        check((CORE / "state/previous").read_bytes() == old_manifest,
              "previous canonical metadata protects old remaining state")
        if fault in ("unlink", "leaf-edit"):
            check((CORE / "state/global-manifest").read_bytes() == old_manifest,
                  "old manifest not advanced on partial deletion")
        if fault == "leaf-edit":
            check((HOME / ".claude/agents/domestique-claude-reviewer.md").read_text()
                  == "SECRET-RACING-LEAF\n", "actual deletion leaf rechecked, edit retained")
        log = CORE / "state/published"
        if log.is_file():
            logged = {x.removeprefix("removed=").rsplit(":", 1)[0]
                      for x in log.read_text().splitlines() if x.startswith("removed=")}
            gone = {k for k in owned if not dest(k).exists()}
            check(logged == gone, "completed journal equals actual deletions, not plan")
            check("replaced=" not in log.read_text(), "no falsely completed manifest publication")
        for args in (("--uninstall", "--global"), ("--global", "--force")):
            before = snapshot(W)
            p = run("/bin/bash", DOM, *args)
            check(p.returncode != 0 and snapshot(W) == before,
                  "pending rerun fails closed for uninstall AND install")

def inject_removal(boundary, victim, action, *, tool="unlink"):
    stubs = W / "stubs"
    stubs.mkdir()
    trigger = W / "trigger"
    real = shutil.which(tool)
    check(real is not None, ("real mutation boundary command available", tool))
    stub = stubs / tool
    stub.write_text(
        "#!/usr/bin/env python3\nimport os,sys\nfrom pathlib import Path\n"
        f"trigger=Path({str(trigger)!r})\np=Path({str(victim)!r})\n"
        f"if sys.argv[-1] == {str(boundary)!r} and not trigger.exists():\n"
        " trigger.write_text('triggered')\n" +
        (f" rc=os.spawnv(os.P_WAIT, {real!r}, [{real!r}, *sys.argv[1:]])\n"
         " if rc: raise SystemExit(rc)\n" if tool == "mv" else "") +
        "".join(f" {line}\n" for line in action.splitlines()) +
        (" raise SystemExit(0)\n" if tool == "mv" else "") +
        f"os.execv({real!r}, [{real!r}, *sys.argv[1:]])\n")
    stub.chmod(0o700)
    result = run("/bin/bash", DOM, "--uninstall", "--global", "--platform", "claude",
                 env=dict(ENV, PATH=f"{stubs}:{ENV['PATH']}"))
    # Check the actual command boundary BEFORE exit/diagnostic assertions, so
    # changing deletion primitives cannot make a never-fired probe pass.
    check(trigger.read_text() == "triggered" if trigger.exists() else False,
          ("mutation wrapper actually fired", boundary, victim))
    check(result.returncode == 1, ("mutation refuses", result.stdout, result.stderr))
    check("PARTIAL removal" in result.stderr, "mutation reports honest partial removal")
    check("completed eligible removal" not in result.stdout + result.stderr,
          "no false all-removed success")
    check("SECRET" not in result.stdout + result.stderr, "no mutated content diagnostics")
    return result


def recovery_refuses():
    check((CORE / "state/pending").exists(), "pending retained until safe completion")
    for args in (("--uninstall", "--global"), ("--global", "--force")):
        before = snapshot(W)
        p = run("/bin/bash", DOM, *args)
        check(p.returncode != 0 and snapshot(W) == before,
              "mutated recovery rerun refuses without any writes")
        check("SECRET" not in p.stdout + p.stderr, "rerun does not expose changed content")


def protected_fixture():
    projects = [project("project-a"), project("project-b")]
    protected = W / "protected-root"
    protected.mkdir()
    (protected / "secret").write_text("SECRET-PROTECTED-ROOT\n")
    paths = [*projects, protected, HOME / ".agents", HOME / ".codex", HOME / ".copilot"]
    return paths, [snapshot(p) for p in paths]


# Each journal is attacked at a real earlier unlink, including a previously
# cleared published log reappearing while previous is being unlinked.
for boundary_name, journal in (
    ("native", "published"), ("published", "previous"), ("published", "pending"),
    ("previous", "pending"), ("previous", "published"),
):
    for kind in ("edit", "symlink", "directory"):
        with fixture():
            install()
            protected, before = protected_fixture()
            core_before = {k: snapshot(dest(k)) for k in records() if k.startswith("core:")}
            victim = CORE / "state" / journal
            boundary = (HOME / ".claude/skills/domestique-claude/SKILL.md"
                        if boundary_name == "native" else CORE / "state" / boundary_name)
            action = ("p.write_bytes(b'SECRET-CHANGED-JOURNAL\\n')" if kind == "edit" else
                      "if p.exists(): p.unlink()\n" +
                      (f"p.symlink_to({str(W / 'protected-root/secret')!r})"
                       if kind == "symlink" else
                       "p.mkdir()\n(p / 'secret').write_bytes(b'SECRET-CHANGED-JOURNAL\\n')"))
            inject_removal(boundary, victim, action)
            if kind == "edit":
                check(victim.read_bytes() == b"SECRET-CHANGED-JOURNAL\n",
                      "changed journal bytes survive exact")
            elif kind == "symlink":
                check(victim.is_symlink() and os.readlink(victim) ==
                      str(W / "protected-root/secret"), "unexpected journal symlink survives")
            else:
                check(victim.is_dir() and (victim / "secret").read_bytes() ==
                      b"SECRET-CHANGED-JOURNAL\n", "unexpected journal directory survives")
            check([snapshot(p) for p in protected] == before,
                  "protected root/projects/remaining native providers byte-identical")
            check(all(snapshot(dest(k)) == v for k, v in core_before.items()),
                  "journal fault leaves all required core bytes unchanged")
            check([p for p in W.rglob("*") if p.is_file() and not p.is_symlink() and
                   p.read_bytes() == b"SECRET-CHANGED-JOURNAL\n"] ==
                  ([victim] if kind == "edit" else [victim / "secret"]
                   if kind == "directory" else []), "no changed journal content copied")
            if boundary_name == "native":
                check((CORE / "state/previous").is_file(), "early fault retains previous")
            recovery_refuses()


# Every required core leaf, including all six historical release leaves, is
# rechecked after native deletion, not just active existence or helper execution.
release_leaves = ("API", "SHA256SUMS", "roles/goal.md", "roles/implementer.md",
                  "roles/orchestrator.md", "roles/reviewer.md")
core_faults = [("native", "active", "missing"), ("native", "bin/resolve-core", "edit")]
core_faults += [("native", f"{version}/{leaf}", "missing" if i % 2 else "edit")
                for version in ("current", "old") for i, leaf in enumerate(release_leaves)]
core_faults += [(boundary, leaf, kind)
                for boundary in ("manifest", "published", "previous")
                for leaf, kind in (("active", "missing"), ("bin/resolve-core", "edit"),
                                   ("old/API", "edit"))]
core_faults += [("native", "active", "repoint")]
for boundary_name, leaf, kind in core_faults:
    with fixture():
        install()
        old = (CORE / "active").read_text().strip().split("=")[1]
        v2 = W / "v2.sh"
        v2.write_text(DOM.read_text().replace("# Domestique private core: reviewer",
                                            "# Domestique private core: reviewer test-v2"))
        install(script=v2)
        current = (CORE / "active").read_text().strip().split("=")[1]
        check(old != current, "mutation fixture has actual retained release history")
        protected, before = protected_fixture()
        old_manifest = (CORE / "state/global-manifest").read_bytes()
        core_before = {k: snapshot(dest(k)) for k in records() if k.startswith("core:")}
        rel = leaf.replace("current/", f"releases/{current}/").replace("old/", f"releases/{old}/")
        victim = CORE / rel
        boundary = (HOME / ".claude/skills/domestique-claude/SKILL.md"
                    if boundary_name == "native" else CORE / "state"
                    if boundary_name == "manifest" else CORE / "state" / boundary_name)
        changed = (f"release={old}\n".encode() if kind == "repoint"
                   else b"SECRET-CHANGED-CORE\n")
        action = "p.unlink()" if kind == "missing" else f"p.write_bytes({changed!r})"
        inject_removal(boundary, victim, action,
                       tool="mv" if boundary_name == "manifest" else "unlink")
        check(not victim.exists() if kind == "missing" else victim.read_bytes() == changed,
              "missing/changed retained core is not restored or replaced")
        check([snapshot(p) for p in protected] == before,
              "core fault preserves protected root/projects/unselected native bytes")
        check(all(snapshot(dest(k)) == v for k, v in core_before.items() if dest(k) != victim),
              "other current and historical core leaves remain byte-identical")
        if boundary_name == "native":
            check((CORE / "state/global-manifest").read_bytes() == old_manifest,
                  "invalid retained core prevents manifest commit")
        else:
            check(b"providers=codex-copilot\n" in (CORE / "state/global-manifest").read_bytes(),
                  "late fault actually happened after manifest commit")
        if boundary_name in ("native", "manifest"):
            check((CORE / "state/previous").read_bytes() == old_manifest and
                  (CORE / "state/published").is_file(), "precleanup fault retains all journals")
        check([p for p in W.rglob("*") if p.is_file() and
               p.read_bytes() == b"SECRET-CHANGED-CORE\n"] ==
              ([victim] if kind == "edit" else []), "no changed core bytes copied")
        recovery_refuses()


# Invalid grammar remains status 2 before writes, including all .10 combinations.
with fixture():
    for args in (
        ("--uninstall",), ("--uninstall", W), ("--uninstall", "--local", W),
        ("--uninstall", "--global", W), ("--uninstall", "--global", "--local", W),
        ("--uninstall", "--global", "--with-beads"),
        ("--uninstall", "--global", "--purge-beads"),
        ("--uninstall", "--global", "--state-only"),
        ("--uninstall", "--global", "--no-guest"),
        ("--uninstall", "--global", "--model", "bad"),
        ("--uninstall", "--global", "--platform", "none"),
        ("--uninstall", "--global", "--platform="),
        ("--uninstall", "--global", "--", W),
    ):
        before = snapshot(W)
        p = run("/bin/bash", DOM, *args)
        check(p.returncode == 2 and snapshot(W) == before, ("invalid grammar prewrite", args))
    refusal()  # genuinely absent scope is a documented non-success, too
    install("claude")
    p = remove("--guest")
    check("deprecated no-op" in p.stderr, "guest remains deprecated no-op")

ast.parse(Path(__file__).read_text())
print(f"global-uninstall: {COUNT} checks passed (current source; isolated, no native clients)")
