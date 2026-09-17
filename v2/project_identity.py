"""Physical Git boundary and bounded read-only index queries; no ambient routing."""
import os
from pathlib import Path
import selectors
import shutil
import stat
import subprocess
import time
from .safe import META_LIMIT, Refusal, Watch, identity, need, path_value, safe, snapshot
from .project_records import I_KEYS, identity_lines


def git_query(directory, args, input_data=None, pass_fds=(), accepted=(0,)):
    git = shutil.which("git")
    need(git is not None, "Git unavailable")
    env = {"PATH": os.environ.get("PATH", ""), "HOME": "/", "LC_ALL": "C",
           "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_SYSTEM": os.devnull,
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_OPTIONAL_LOCKS": "0",
           "GIT_TERMINAL_PROMPT": "0", "GIT_PAGER": "cat"}
    argv = [git, "-C", str(directory), "-c", "core.fsmonitor=false", *args]
    # Bound pipe allocation as well as elapsed time; never spool Git output.
    proc = subprocess.Popen(argv, env=env, stdin=subprocess.PIPE if input_data else
                            subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, pass_fds=pass_fds)
    output, errors = bytearray(), bytearray()
    deadline = time.monotonic() + 120
    try:
        with selectors.DefaultSelector() as poll:
            for stream, dest in ((proc.stdout, output), (proc.stderr, errors)):
                os.set_blocking(stream.fileno(), False)
                poll.register(stream, selectors.EVENT_READ, dest)
            if input_data:
                need(len(input_data) <= META_LIMIT, "Git input bounds")
                os.set_blocking(proc.stdin.fileno(), False)
                poll.register(proc.stdin, selectors.EVENT_WRITE, memoryview(input_data))
            while poll.get_map():
                remaining = deadline - time.monotonic()
                need(remaining > 0, "Git timeout")
                for key, event in poll.select(remaining):
                    if event & selectors.EVENT_WRITE:
                        n = os.write(key.fd, key.data)
                        rest = key.data[n:]
                        if rest:
                            poll.modify(key.fileobj, selectors.EVENT_WRITE, rest)
                        else:
                            poll.unregister(key.fileobj)
                            key.fileobj.close()
                    else:
                        chunk = os.read(key.fd, 65536)
                        if chunk:
                            key.data.extend(chunk)
                            need(len(output) + len(errors) <= META_LIMIT, "Git output bounds")
                        else:
                            poll.unregister(key.fileobj)
            need(proc.wait(timeout=max(0.001, deadline - time.monotonic())) in accepted,
                 "Git boundary unavailable")
        return bytes(output)
    finally:
        if proc.poll() is None:
            proc.kill()  # This exclusively owned subprocess, never a name-based kill.
            proc.wait()
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            if stream and not stream.closed:
                stream.close()


def target_path(value):
    need(isinstance(value, str) and value, "target required")
    need(not any(ord(c) < 32 or 127 <= ord(c) <= 159 or c == "=" for c in value),
         "target characters")
    raw = value if value.startswith("/") else str(Path.cwd()) + "/" + value
    walk = Path("/")
    for part in raw.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            walk = walk.parent
        else:
            walk = walk / part
            safe(walk)  # Before normalization can erase a link/unsafe component.
            need(walk.is_dir(), "target component missing")
    path_value(str(walk))
    return walk


def _git_path(top, arg):
    data = git_query(top, ["rev-parse", arg])
    need(data.endswith(b"\n") and data.count(b"\n") == 1, "Git path framing")
    value = data[:-1].decode("utf-8")
    path = Path(os.path.normpath(value if value.startswith("/") else str(top / value)))
    path_value(str(path))
    return path


def project_identity(target, invocation=False, watch=None):
    watch = watch if watch is not None else Watch()
    path = target_path(str(target))
    watch.add(path)
    boundary = path
    while True:
        watch.add(boundary)
        if watch.add(boundary / ".git") is not None:
            break
        need(boundary != Path("/"), "not a physical worktree")
        boundary = boundary.parent
    watch.add(boundary)
    watch.add(boundary / ".git")
    top = _git_path(path, "--show-toplevel")
    need(top == boundary and (invocation or top == path), "exact Git top-level required")
    need(git_query(top, ["rev-parse", "--is-bare-repository"]) == b"false\n",
         "bare repository")
    gitdir = _git_path(top, "--absolute-git-dir")
    watch.add(gitdir)
    watch.add(gitdir / "commondir")
    common = _git_path(top, "--git-common-dir")
    watch.add(common)
    directories = (top, gitdir, common)
    attrs = []
    for directory in directories:
        snap = watch.add(directory)
        need(snap is not None and snap[1] is None and snap[0][0] == os.getuid(),
             "foreign/missing Git identity")
        attrs.extend((str(snap[0][1]), str(snap[0][2])))
    result = dict(zip(I_KEYS, [*(str(p) for p in directories), *attrs, str(os.getuid())]))
    identity_lines(result)
    # Snapshot before any Git index/config use; do not adopt a later observation.
    for p in (common / "config", gitdir / "config.worktree", gitdir / "index",
              gitdir / "index.lock", common / "info/sparse-checkout"):
        snap = watch.add(p)
        need(snap is None or snap[1] is not None, "Git metadata collision")
        need(p.name != "index.lock" or snap is None, "index pending")
    shared = git_query(top, ["rev-parse", "--shared-index-path"])
    if shared not in (b"", b"\n"):
        need(shared.endswith(b"\n") and shared.count(b"\n") == 1, "shared index framing")
        value = shared[:-1].decode()
        sp = Path(os.path.normpath(value if value.startswith("/") else str(top / value)))
        need(sp.parent in (gitdir, common) and sp.name.startswith("sharedindex."),
             "shared index boundary")
        watch.add(sp)
    need(_git_path(top, "--absolute-git-dir") == gitdir and
         _git_path(top, "--git-common-dir") == common and
         _git_path(path, "--show-toplevel") == top, "changed Git identity")
    watch.check()
    return result, watch


def index_untracked(i, candidates):
    top = Path(i["worktree_root"])
    candidates = tuple(candidates)
    for p in candidates:
        need(not path_value(p).startswith("/"), "relative index candidate")
    outer = sorted({p.split("/")[0] for p in candidates})
    raw = git_query(top, ["ls-files", "-z", "--", *(":(top,literal)" + p for p in outer)])
    need(not raw or raw.endswith(b"\0"), "index framing")
    for value in raw.split(b"\0")[:-1]:
        need(value and not value.startswith(b"/") and
             all(p not in (b"", b".", b"..") for p in value.split(b"/")),
             "index path framing")
        need(value.split(b"/")[0] in [p.encode() for p in outer], "index query scope")
        for candidate in candidates:
            c = candidate.encode()
            need(value != c and not value.startswith(c + b"/") and
                 not c.startswith(value + b"/"), "tracked/index-only collision")


def identity_guard(i, watch=None):
    """Cheap exact witnesses plus fresh Git resolution/index at scope boundaries."""
    top = Path(i["worktree_root"])
    for directory, dev, ino in ((top, "worktree_dev", "worktree_ino"),
                               (Path(i["git_dir"]), "git_dir_dev", "git_dir_ino"),
                               (Path(i["git_common_dir"]), "git_common_dev", "git_common_ino")):
        safe(directory)
        s = directory.lstat()
        need(stat.S_ISDIR(s.st_mode) and s.st_uid == int(i["owner_uid"]) == os.getuid()
             and (s.st_dev, s.st_ino) == (int(i[dev]), int(i[ino])), "changed project identity")
    need(_git_path(top, "--show-toplevel") == top and
         _git_path(top, "--absolute-git-dir") == Path(i["git_dir"]) and
         _git_path(top, "--git-common-dir") == Path(i["git_common_dir"]), "changed Git boundary")
    if watch is not None:
        watch.check()
