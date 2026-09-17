"""Local Git + owned filesystem lifecycle, cooperative single writer only.

resolve_source(root) is the read-only internal API for future workflow entry:
retain its returned Path, never re-resolve current during that workflow.
Revisions are immutable by convention and checked with ordinary Git status.
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid

COMMIT = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
REQUIRED = ("preview/__init__.py", "preview/cli.py", "preview/machine.py",
            "preview/launcher.sh")


class Refusal(Exception):
    pass


def need(ok, message):
    if not ok:
        raise Refusal(message)


def parse_pairs(args, keys):
    if len(args) != 2 * len(keys):
        raise ValueError("exact explicit options required: " + " ".join(keys))
    result = {}
    for key, value in zip(args[::2], args[1::2]):
        if key not in keys or key in result or not value or value.startswith("-"):
            raise ValueError("unknown, duplicate or empty option/value")
        result[key] = value
    if set(result) != set(keys):
        raise ValueError("missing required option")
    return result


def tools():
    need(sys.version_info >= (3, 9), "provide existing Python 3.9+; nothing installed")
    for tool in ("bash", "git"):
        need(shutil.which(tool), f"provide existing {tool}; dependencies are never installed")


def git(path, *args):
    tools()
    # No ambient repository redirection, global setup, template hooks, filters
    # from user config, optional index refresh, maintenance or remote protocols.
    env = {key: os.environ[key] for key in ("PATH", "HOME") if key in os.environ}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_CONFIG_SYSTEM=os.devnull, GIT_OPTIONAL_LOCKS="0",
               GIT_TERMINAL_PROMPT="0", GIT_PAGER="cat", LC_ALL="C")
    options = ("core.hooksPath=/dev/null", "core.fsmonitor=false",
               "core.excludesFile=/dev/null", "core.attributesFile=/dev/null",
               "core.autocrlf=false", "core.eol=lf", "gc.auto=0",
               "maintenance.auto=false", "submodule.recurse=false",
               "protocol.allow=never", "protocol.file.allow=always")
    argv = ["git", "--no-pager"]
    for option in options:
        argv += ["-c", option]
    proc = subprocess.run([*argv, "-C", str(path), *args], env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    need(proc.returncode == 0,
         f"Git {args[0]} failed: {proc.stderr.decode(errors='replace').strip()}")
    return proc.stdout


def identity(path):
    info = path.lstat()
    need(info.st_uid == os.getuid(), f"foreign owner: {path}")
    return [info.st_dev, info.st_ino]


def safe(path):
    """Check actual ancestors once; root-owned sticky system temp is allowed."""
    need(path.is_absolute() and ".." not in path.parts, f"absolute safe path required: {path}")
    for parent in reversed((path, *path.parents)):
        if not os.path.lexists(parent):
            continue
        info = parent.lstat()
        need(stat.S_ISDIR(info.st_mode) or
             (parent == path and stat.S_ISREG(info.st_mode)), f"symlink/unsafe path: {parent}")
        need(info.st_uid in (0, os.getuid()), f"foreign parent: {parent}")
        need(not info.st_mode & 0o022 or
             (stat.S_ISDIR(info.st_mode) and info.st_uid == 0 and
              info.st_mode & stat.S_ISVTX), f"unsafe writable parent: {parent}")


def writable_directory(path):
    safe(path)
    existing = path
    while not existing.exists():
        existing = existing.parent
    need(existing.is_dir(), f"not a directory: {existing}")
    identity(existing)
    need(existing.stat().st_mode & 0o200 and
         os.access(existing, os.W_OK | os.X_OK), f"directory not writable: {existing}")


def boundary(path):
    safe(path)
    for parent in (path, *path.parents):
        need(parent.name not in {".git", ".beads", ".github", ".agents", ".claude",
                                 ".copilot", ".codex", ".domestique-private"},
             f"machine/native overlap: {path}")
        need(not os.path.lexists(parent / ".git") and
             not ((parent / "HEAD").exists() and (parent / "objects").is_dir()),
             f"machine destination inside Git repository: {path}")


def digest(path):
    safe(path)
    identity(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    safe(path)
    identity(path)
    value = json.loads(path.read_text())
    need(isinstance(value, dict), f"invalid ownership receipt: {path}")
    return value


def write_json(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def legacy_state(home):
    state = Path(os.environ.get("XDG_STATE_HOME") or home / ".local/state")
    base = Path(os.environ.get("DOMESTIQUE_HOME") or state / "domestique")
    need(not os.path.lexists(base / "v2"),
         "existing ABI2/3 state; no automatic migration or adoption")


def selection(source, ref):
    source = Path(source).resolve(strict=True)
    need(source.is_dir() and os.path.lexists(source / ".git"),
         "source must be a local Git checkout root")
    top = Path(os.fsdecode(git(source, "rev-parse", "--show-toplevel")).removesuffix("\n"))
    need(top.resolve() == source, "source must be the checkout root")
    commit = git(source, "rev-parse", "--verify", "--end-of-options",
                 ref + "^{commit}").decode().strip()
    need(COMMIT.fullmatch(commit), "ref did not resolve to a commit")
    return source, commit


def candidate(source, commit):
    # Inspect committed bytes, never execute candidate hooks, main or setup.
    entries = git(source, "ls-tree", "-r", "-z", commit).split(b"\0")
    files = []
    for entry in filter(None, entries):
        metadata, name = entry.split(b"\t", 1)
        need(metadata.split()[0] in (b"100644", b"100755"),
             "preview revisions require regular files (no submodules or symlinks)")
        files.append(os.fsdecode(name))
    need(all(name in files for name in REQUIRED), "revision lacks the preview CLI/runtime")
    for name in files:
        if name.startswith("preview/") and name.endswith(".py"):
            data = git(source, "show", f"{commit}:{name}")
            try:
                tree = ast.parse(data, filename=name)
                compile(tree, name, "exec")
            except (SyntaxError, ValueError) as exc:
                raise Refusal(f"unrunnable preview Python: {name}: {exc}") from exc
            if name == "preview/cli.py":
                need(any(isinstance(node, ast.FunctionDef) and node.name == "main"
                         for node in tree.body), "preview CLI has no main entry")
    shell = git(source, "show", f"{commit}:preview/launcher.sh")
    need(shell.count(b"@ROOT@") == 1, "revision lacks a matching preview launcher")
    proc = subprocess.run(["bash", "-p", "-n"], input=shell,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    need(proc.returncode == 0, "invalid preview launcher syntax")


def check_release(root, release):
    safe(release)
    need(release.parent == root / "releases" and COMMIT.fullmatch(release.name),
         "invalid revision destination")
    safe(release / ".git")
    record = read_json(release / ".git/preview-receipt.json")
    need(record.get("root") == identity(root) and record.get("directory") == identity(release)
         and record.get("commit") == release.name, "unowned revision directory")
    need(not os.path.lexists(release / ".git/objects/info/alternates"),
         "revision has a live alternate dependency")
    need(record.get("config_sha256") == digest(release / ".git/config"),
         "modified managed Git configuration")
    need(git(release, "rev-parse", "--verify", "HEAD").decode().strip() == release.name,
         "modified managed HEAD")
    need(not git(release, "status", "--porcelain=v1", "--untracked-files=all", "--ignored"),
         "dirty managed revision; preserve edits and use a clean owned revision")


def check_install(root, source):
    boundary(root)
    receipt = read_json(root / "receipt.json")
    need(receipt.get("root") == identity(root) and
         receipt.get("releases") == identity(root / "releases"), "unowned installation root")
    need({p.name for p in root.iterdir()} == {"receipt.json", "releases", "current"},
         "unknown installation root contents")
    need(all(COMMIT.fullmatch(p.name) for p in (root / "releases").iterdir()),
         "unknown release directory collision")
    launcher = Path(receipt.get("launcher", ""))
    boundary(launcher)
    need(receipt.get("launcher_identity") == identity(launcher) and
         receipt.get("launcher_sha256") == digest(launcher) and os.access(launcher, os.X_OK),
         "unowned or changed launcher; no adoption")
    current = root / "current"
    need(current.is_symlink() and identity(current) and
         re.fullmatch(r"releases/([0-9a-f]{40}|[0-9a-f]{64})", os.readlink(current)),
         "invalid owned current pointer")
    check_release(root, source)
    return receipt


def resolve_source(root):
    """Read-only. Return the selected immutable path to retain for a workflow."""
    root = Path(root)
    target = os.readlink(root / "current")
    need(re.fullmatch(r"releases/([0-9a-f]{40}|[0-9a-f]{64})", target),
         "invalid current pointer")
    source = root / target
    check_install(root, source)
    return source


def prepare(root, source, commit):
    final = root / "releases" / commit
    if os.path.lexists(final):
        check_release(root, final)
        return final
    with tempfile.TemporaryDirectory(prefix=".prepare-", dir=root / "releases") as temporary:
        stage = Path(temporary) / "checkout"
        stage.mkdir()
        git(stage, "init", "--template=", "--object-format=" +
            ("sha256" if len(commit) == 64 else "sha1"))
        git(stage, "fetch", "--depth=1", "--no-tags", "--no-recurse-submodules",
            "--", str(source), commit)
        git(stage, "checkout", "--detach", commit)
        need(not git(stage, "status", "--porcelain=v1", "--untracked-files=all", "--ignored"),
             "prepared revision is dirty")
        write_json(stage / ".git/preview-receipt.json",
                   {"root": identity(root), "directory": identity(stage), "commit": commit,
                    "config_sha256": digest(stage / ".git/config")})
        stage.rename(final)
    check_release(root, final)
    return final


def switch(root, release):
    temp = root / (".current-" + uuid.uuid4().hex)
    os.symlink(str(release.relative_to(root)), temp)
    try:
        os.replace(temp, root / "current")
    finally:
        if temp.is_symlink():
            temp.unlink()


def update(root, current, receipt, ref):
    need(os.readlink(root / "current") == str(current.relative_to(root)),
         "update must use the current launcher, not a retained old revision")
    writable_directory(root)
    writable_directory(root / "releases")
    legacy_state(Path(receipt["launcher"]).parent.parent.parent)
    try:
        source, commit = selection(receipt["source"], ref)
    except OSError as exc:
        raise Refusal("recorded local source is missing/unavailable; current remains selected") from exc
    if commit == current.name:
        return False, commit
    candidate(source, commit)
    release = prepare(root, source, commit)
    switch(root, release)
    return True, commit


def make_parents(path, created):
    if not path.exists():
        make_parents(path.parent, created)
        path.mkdir(mode=0o700)
        created.append(path)


def install(source, ref):
    tools()
    home = Path(os.environ.get("HOME", ""))
    data = Path(os.environ.get("XDG_DATA_HOME") or home / ".local/share")
    root, launcher = data / "domestique-preview", home / ".local/bin/domestique2"
    need(home.is_absolute() and home.is_dir(), "HOME must be an existing absolute directory")
    for path in (root, launcher):
        boundary(path)
    need(root not in launcher.parents and launcher not in root.parents and
         root != launcher, "overlapping machine paths")
    legacy_state(home)
    source, commit = selection(source, ref)
    if os.path.lexists(root):
        current = resolve_source(root)
        receipt = read_json(root / "receipt.json")
        need(receipt.get("source") == str(source) and receipt.get("launcher") == str(launcher),
             "installation belongs to a different source or HOME")
        need(current.name == commit, "already installed; use domestique2 update --ref REV")
        return False, commit
    need(not os.path.lexists(launcher), "unowned launcher collision; no adoption or migration")
    writable_directory(root.parent)
    writable_directory(launcher.parent)
    candidate(source, commit)
    parents = []
    made_root = made_launcher = False
    try:
        make_parents(root.parent, parents)
        make_parents(launcher.parent, parents)
        root.mkdir(mode=0o700)
        made_root = True
        (root / "releases").mkdir(mode=0o700)
        release = prepare(root, source, commit)
        shell = (release / "preview/launcher.sh").read_text().replace("@ROOT@", shlex.quote(str(root)))
        fd = os.open(launcher, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o700)
        made_launcher = True
        with os.fdopen(fd, "w") as stream:
            stream.write(shell)
        write_json(root / "receipt.json",
                   {"root": identity(root), "releases": identity(root / "releases"),
                    "source": str(source), "launcher": str(launcher),
                    "launcher_identity": identity(launcher), "launcher_sha256": digest(launcher)})
        switch(root, release)
    except BaseException:
        # Only this invocation's new, unpublished installation and parents.
        if made_launcher:
            launcher.unlink()
        if made_root:
            shutil.rmtree(root)
        for parent in reversed(parents):
            parent.rmdir()
        raise
    return True, commit
