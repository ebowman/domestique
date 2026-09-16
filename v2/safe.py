"""V2 filesystem primitives, adapted from global_path/global_link_new and stdio bridge.

No shell evaluation, native discovery, retries, permission repair or adoption.
Only Python stdlib; the internal API requires an already available Python 3.9+.
"""
import hashlib
import os
from pathlib import Path
import re
import stat

META_LIMIT = 1048576
PAYLOAD_LIMIT = 64 * 1048576
MAX_NUMBER = 2**63 - 1


class Refusal(Exception):
    pass


def need(ok, why):
    if not ok:
        raise Refusal(why)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def path_value(value):
    need(isinstance(value, str) and value and len(value.encode("utf-8")) <= 4096,
         "invalid path length")
    need(not any(ord(c) < 32 or 127 <= ord(c) <= 159 or c == "=" for c in value),
         "non-data path")
    need(value != "/" and not value.endswith("/") and
         all(p not in ("", ".", "..") for p in value.lstrip("/").split("/")) and
         not value.startswith("//"), "noncanonical path")
    return value


def physical(value):
    path_value(str(value))
    p = Path(value)
    need(p.is_absolute(), "absolute physical path required")
    safe(p)
    return p


def attributes(s):
    return (s.st_uid, s.st_dev, s.st_ino, s.st_mode, s.st_nlink,
            s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def identity(s):
    return (s.st_uid, s.st_dev, s.st_ino, s.st_mode)


def safe(path):
    """Exact ancestors only, root-owned sticky system ancestors permitted."""
    path = Path(path)
    if path != Path("/"):  # System root is an ancestor, never a supplied scope.
        path_value(str(path))
    need(path.is_absolute(), "absolute path required")
    for p in reversed((path, *path.parents)):
        try:
            s = p.lstat()
        except FileNotFoundError:
            continue
        directory = stat.S_ISDIR(s.st_mode)
        need(directory or stat.S_ISREG(s.st_mode), "unsafe filesystem object")
        need(p == path or directory, "non-directory ancestor")
        need(s.st_uid in (0, os.getuid()), "foreign ancestor owner")
        need(not s.st_mode & 0o022 or
             (directory and s.st_uid == 0 and s.st_mode & stat.S_ISVTX),
             "unsafe writable ancestry")
        need(not stat.S_ISREG(s.st_mode) or s.st_nlink == 1, "hard-linked leaf")
        need(s.st_mode & 0o400 and os.access(p, os.R_OK), "unreadable path")
        need(not directory or (s.st_mode & 0o100 and os.access(p, os.X_OK)),
             "unsearchable directory")


def snapshot(path, limit=PAYLOAD_LIMIT):
    path = Path(path)
    safe(path)
    try:
        before = path.lstat()
    except FileNotFoundError:
        return None
    need(before.st_uid == os.getuid(), "unowned destination/input")
    if stat.S_ISDIR(before.st_mode):
        return (attributes(before), None)
    need(before.st_size <= limit, "input too large")
    ancestors = [(p, identity(p.lstat())) for p in path.parents]
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        need(attributes(os.fstat(fd)) == attributes(before), "changed opened file")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(limit + 1)
        need(len(data) <= limit and attributes(os.fstat(fd)) == attributes(before),
             "changed/oversize read")
    finally:
        os.close(fd)
    safe(path)
    need(attributes(path.lstat()) == attributes(before) and
         all(identity(p.lstat()) == old for p, old in ancestors), "changed read identity")
    return (attributes(before), data)


def read(path, limit=META_LIMIT, mode=None):
    snap = snapshot(path, limit)
    need(snap is not None and snap[1] is not None, "missing regular file")
    if mode is not None:
        need(stat.S_IMODE(snap[0][3]) == mode, "incorrect file mode")
    return snap[1]


def text_bounds(data, torn=False):
    need(len(data) <= META_LIMIT and (torn or data.endswith(b"\n")) and
         not data.startswith(b"\xef\xbb\xbf"), "invalid metadata framing/size")
    lines = data.split(b"\n")
    need(len(lines) - int(data.endswith(b"\n")) <= 16384 and
         all(len(line) + 1 <= 8192 for line in lines), "metadata line bounds")
    try:
        text = data.decode("utf-8")
    except UnicodeError as exc:
        raise Refusal("invalid UTF-8") from exc
    need(not any(ord(c) < 32 and c != "\n" or 127 <= ord(c) <= 159 for c in text),
         "metadata controls")
    return text


def checked_write(fd, path, data, before, guard):
    """Write only from a witnessed snapshot; close has no buffered write debt.

    Short writes advance by their actual count. EINTR retries only after fresh
    checks; other errors and zero progress retain the partial file, never truncate
    or clean it. This is observation-bound, not hostile-writer atomicity.
    """
    offset = 0
    current = before
    while True:
        guard()
        need(attributes(os.fstat(fd)) == current[0] and snapshot(path) == current,
             "changed write identity/bytes")
        if offset == len(data):
            return current
        try:
            count = os.write(fd, memoryview(data)[offset:])
        except InterruptedError:
            continue
        need(0 < count <= len(data) - offset, "write made no valid progress")
        raw = current[1] + data[offset:offset + count]
        after = os.fstat(fd)
        need(identity(after) == current[0][:4] and after.st_nlink == 1 and
             after.st_size == len(raw), "changed partial write")
        current = (attributes(after), raw)
        offset += count


def write_created(fd, path, data, mode, guard):
    """The open descriptor, not the name or equal bytes, witnesses creation."""
    initial = os.fstat(fd)
    need(initial.st_uid == os.getuid() and stat.S_ISREG(initial.st_mode) and
         initial.st_nlink == 1 and initial.st_size == 0, "invalid creation witness")
    checked_write(fd, path, b"", (attributes(initial), b""), guard)
    os.fchmod(fd, mode)
    changed = os.fstat(fd)
    need(identity(changed)[:3] == identity(initial)[:3] and
         changed.st_mode == stat.S_IFREG | mode and changed.st_nlink == 1 and
         changed.st_size == 0, "changed creation mode")
    return checked_write(fd, path, data, (attributes(changed), b""), guard)


def exclusive(path, data, mode, guard=None):
    """O_EXCL is the single-leaf equivalent of global_link_new, without links."""
    safe(path)
    guard = guard or (lambda: safe(path))
    guard()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    try:
        return write_created(fd, path, data, mode, guard)
    finally:
        os.close(fd)


class Watch:
    """Checked preflight snapshots; only our witnessed mutations advance them."""
    def __init__(self, boundary=None):
        self.paths = {}
        self.ancestors = {}
        self.boundary = boundary or (lambda: None)

    def add(self, path):
        path = Path(path)
        self.paths[path] = snapshot(path)
        for p in path.parents:
            if p.exists():
                self.ancestors.setdefault(p, identity(p.lstat()))

    def check(self):
        self.check_boundary()
        for p, old in self.paths.items():
            need(snapshot(p) == old, "changed preflight path")

    def check_boundary(self):
        """Fresh overlap and identity checks, also during witnessed mutations."""
        for p, old in self.ancestors.items():
            safe(p)
            need(identity(p.lstat()) == old, "changed ancestor identity")
        for p, old in self.paths.items():
            if old is not None and old[1] is None:
                safe(p)
                need(identity(p.lstat()) == old[0][:4], "changed directory identity")
        self.boundary()

    def advance(self, path):
        """After a checked write, refresh just its parent and actual result."""
        path = Path(path)
        parent = path.parent
        if parent in self.paths and self.paths[parent] is not None:
            old = self.paths[parent][0]
            s = parent.lstat()
            need((s.st_uid, s.st_dev, s.st_ino, s.st_mode) == old[:4],
                 "changed publication parent")
            self.paths[parent] = snapshot(parent)
        self.add(path)
