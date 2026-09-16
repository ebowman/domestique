#!/bin/bash -p
set -eu
command -v python3 >/dev/null 2>&1 || exit 1
if [ "$(command -v python3)" = /usr/bin/python3 ] && [ "$(uname -s)" = Darwin ]; then exit 1; fi
exec python3 -I -S -B - "$@" <<'DOMESTIQUE_V2_TRUSTED_PY'
import sys
if sys.version_info < (3, 9): sys.exit(1)
"""V2 filesystem primitives, adapted from global_path/global_link_new and stdio bridge.

No shell evaluation, native discovery, retries, permission repair or adoption.
Only Python stdlib; the internal API requires an already available Python 3.9+.
"""
import hashlib
from contextlib import contextmanager, nullcontext
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


def write_created(fd, path, data, mode, guard, before=None):
    """The open descriptor, not the name or equal bytes, witnesses creation."""
    initial = os.fstat(fd)
    need(before is None or attributes(initial) == before[0], "changed creation handoff")
    need(initial.st_uid == os.getuid() and stat.S_ISREG(initial.st_mode) and
         initial.st_nlink == 1 and initial.st_size == 0, "invalid creation witness")
    checked_write(fd, path, b"", (attributes(initial), b""), guard)
    need(attributes(os.fstat(fd)) == attributes(initial) and
         snapshot(path) == (attributes(initial), b""), "changed pre-chmod creation")
    os.fchmod(fd, mode)
    changed = os.fstat(fd)
    need(identity(changed)[:3] == identity(initial)[:3] and
         changed.st_mode == stat.S_IFREG | mode and changed.st_nlink == 1 and
         changed.st_size == 0 and changed.st_mtime_ns == initial.st_mtime_ns,
         "changed creation mode")
    return checked_write(fd, path, data, (attributes(changed), b""), guard)


def exclusive(path, data, mode, guard=None, watch=None):
    """O_EXCL is the single-leaf equivalent of global_link_new, without links."""
    safe(path)
    guard = guard or (lambda: safe(path))
    guard()
    fd = None
    try:
        with watch.namespace(Path(path).parent, entry_delta=1) if watch else nullcontext():
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
            before = (attributes(os.fstat(fd)), b"")
        return write_created(fd, path, data, mode, guard, before)
    finally:
        if fd is not None:
            os.close(fd)


def moved_witness(fd, before, links):
    """A link/rename/unlink may change ctime/link count, not bytes or mtime."""
    after = attributes(os.fstat(fd))
    need(after[:4] == before[0][:4] and after[4] == links and
         after[5:7] == before[0][5:7], "changed moved afterimage")
    return after, before[1]


class Watch:
    """Checked preflight snapshots; only our witnessed mutations advance them."""
    def __init__(self, boundary=None):
        self.paths = {}
        self.ancestors = {}
        self.boundary = boundary or (lambda: None)

    def _observe(self, path):
        # Bind ancestors before opening the leaf, never to a later replacement.
        for p in path.parents:
            if p.exists():
                current = identity(p.lstat())
                need(self.ancestors.setdefault(p, current) == current,
                     "changed ancestor identity")
        return snapshot(path)

    def add(self, path):
        """Register before validation; revisiting cannot erase an earlier proof."""
        path = Path(path)
        current = self._observe(path)
        need(self.paths.setdefault(path, current) == current, "changed preflight path")
        return current

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

    @contextmanager
    def namespace(self, parent, entry_delta, directory_delta=0):
        """Witness parent metadata at the namespace syscall, not after file I/O.

        The caller checks its leaf preconditions separately (including the
        two-link transition). Only this directory's namespace metadata can move.
        """
        parent = Path(parent)
        self.check_boundary()
        before = self.add(parent)
        need(before is not None and before[1] is None, "missing publication parent")
        fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            need(attributes(os.fstat(fd)) == before[0], "changed opened parent")
            yield
            after = (attributes(os.fstat(fd)), None)
            # Unix directories count subdirectories; APFS counts all entries.
            need(after[0][:4] == before[0][:4] and
                 (after[0][4] - before[0][4] in (directory_delta, entry_delta) or
                  after[0][4] == before[0][4] == 1), "changed publication parent")
            self.advance(parent, after)
        finally:
            os.close(fd)

    def mkdir(self, path, mode=0o700):
        path = Path(path)
        self.add(path)
        self.check()
        need(self.paths[path] is None, "directory creation collision")
        fd = None
        try:
            with self.namespace(path.parent, entry_delta=1, directory_delta=1):
                os.mkdir(path, mode)
                fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                created = (attributes(os.fstat(fd)), None)
            need(created[0][0] == os.getuid() and
                 created[0][3] == stat.S_IFDIR | mode, "invalid directory creation")
            with os.scandir(fd) as entries:
                need(next(entries, None) is None, "nonempty directory creation")
            self.advance(path, created)
            return created
        finally:
            if fd is not None:
                os.close(fd)

    def advance(self, path, witnessed):
        """Bind an actual result; never acquire authority from a later pathname."""
        path = Path(path)
        need(self._observe(path) == witnessed, "changed witnessed publication")
        self.paths[path] = witnessed
        if witnessed is None:
            self.ancestors.pop(path, None)

"""Closed format-2 local package verifier. Never executes input."""
# Bundle imports are removed by build.py; source imports share these primitives.

ROLES = ("goal", "implementer", "orchestrator", "reviewer")
PROVIDERS = ("claude", "codex", "copilot")
LEAVES = tuple(sorted(("PACKAGE", "SHA256SUMS", "domestique2.sh", "update2.sh",
                       "bin/resolve-core") +
                      tuple("roles/" + r + ".md" for r in ROLES) +
                      tuple("adapters/" + p + ".templates" for p in PROVIDERS)))
EXECUTABLES = ("domestique2.sh", "update2.sh", "bin/resolve-core")
DIRS = ("adapters", "bin", "roles")
VERSION = r"2\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
RELEASE = r"r-[0-9a-f]{64}"


def payload_mode(leaf):
    return 0o755 if leaf in EXECUTABLES else 0o644


def package_header(version):
    need(re.fullmatch(VERSION, version) is not None, "unsupported package version")
    return ("format=2\nproduct=domestique\nmajor=2\nversion=" + version +
            "\ncore_api=1\nadapter_abi=2\nactivation_format=2\nhelper_abi=2\n"
            "launcher_abi=2\n").encode()


def inventory(root, leaves, directories):
    """Bounded exact enumeration, including empty unexpected directories."""
    expected = set(leaves) | set(directories)
    actual = set()
    parents = [root] + [root / d for d in directories]
    before = {}
    for parent in parents:
        snap = snapshot(parent)
        need(snap is not None and snap[1] is None, "missing package directory")
        before[parent] = snap
        # scandir streams; never materialize an unbounded foreign inventory.
        import os
        with os.scandir(parent) as entries:
            for entry in entries:
                rel = str(Path(entry.path).relative_to(root))
                need(rel in expected and rel not in actual, "extra/duplicate inventory")
                actual.add(rel)
    need(actual == expected, "incomplete inventory")
    need(all(snapshot(p) == s for p, s in before.items()), "changed inventory")


def verify_package(root, expected_version=None, installed=False, watch=None):
    root = physical(root)
    watch = watch if watch is not None else Watch()
    # Retained package authority must travel with these very observations, not
    # a traversal/snapshot taken after the verifier returns its in-memory data.
    for p in (root, *(root / d for d in DIRS)):
        watch.add(p)
    inventory(root, LEAVES, DIRS)
    # Check the aggregate before allocating payload snapshots.
    need(sum((root / p).lstat().st_size for p in LEAVES) <= PAYLOAD_LIMIT,
         "expanded payload cap")
    for leaf in LEAVES:
        watch.add(root / leaf)
    data = {}
    total = 0
    for leaf in LEAVES:
        data[leaf] = read(root / leaf, META_LIMIT if leaf in
                          ("PACKAGE", "SHA256SUMS") else PAYLOAD_LIMIT,
                          payload_mode(leaf) if installed else None)
        need(data[leaf] == watch.paths[root / leaf][1], "changed package read bytes")
        total += len(data[leaf])
        need(total <= PAYLOAD_LIMIT, "expanded payload cap")
    result = package_from_data(data, expected_version)
    inventory(root, LEAVES, DIRS)
    watch.check()
    return result


def package_from_data(data, expected_version=None):
    """Same closed verifier for archive bytes and physical directory snapshots."""
    need(tuple(sorted(data)) == LEAVES and
         sum(len(value) for value in data.values()) <= PAYLOAD_LIMIT, "payload inventory/cap")
    text = text_bounds(data["PACKAGE"])
    lines = text.splitlines()
    need(len(lines) == 9 and lines[3].startswith("version="), "PACKAGE fields")
    version = lines[3][8:]
    need(data["PACKAGE"] == package_header(version), "PACKAGE schema/ABI")
    need(expected_version is None or version == expected_version, "version mismatch")
    text_bounds(data["SHA256SUMS"])
    sums = b"".join((sha(data[p]) + "  " + p + "\n").encode()
                    for p in LEAVES if p != "SHA256SUMS")
    need(sums == data["SHA256SUMS"], "checksum inventory/digest mismatch")
    return {"release": "r-" + sha(sums), "version": version, "data": data,
            "source_kind": "local", "official_version": "-"}

"""Appendix A/B/D machine encoders and strict readers (no general record engine)."""


def encoded(lines):
    data = "".join(k + "=" + str(v) + "\n" for k, v in lines).encode()
    return data


def record(lines):
    data = encoded(lines)
    result = data + ("checksum=" + sha(data) + "\n").encode()
    text_bounds(result)
    return result


def parse_record(data):
    lines = text_bounds(data).splitlines()
    need(lines and re.fullmatch(r"checksum=[0-9a-f]{64}", lines[-1]), "record checksum")
    need(sha(data[:-(len(lines[-1]) + 1)]) == lines[-1][9:], "record corruption")
    pairs = []
    for line in lines[:-1]:
        key, sep, value = line.partition("=")
        need(sep and key and value, "empty record field")
        pairs.append((key, value))
    need(record(pairs) == data, "noncanonical record")
    return pairs


def number(value):
    need(re.fullmatch(r"0|[1-9][0-9]*", value) and int(value) <= MAX_NUMBER,
         "invalid decimal")
    return int(value)


def machine(root, launcher, placeholder=False):
    s = root.stat() if not placeholder else None
    return [("core_root", str(root)), ("core_dev", str(s.st_dev if s else MAX_NUMBER)),
            ("core_ino", str(s.st_ino if s else MAX_NUMBER)),
            ("owner_uid", str(s.st_uid if s else MAX_NUMBER)),
            ("launcher_path", str(launcher)), ("launcher_abi", "2")]


def pair(path, data, mode):
    value = f"{path}:{sha(data)}:{mode:04o}"
    return [("created", value), ("baseline", value)]


def manifest_bytes(m, launcher_data, releases):
    need(0 < len(releases) <= 1024, "release block bounds")
    lines = [("format", "2"), ("scope", "runtime"), *m, ("core_api", "1"),
             ("adapter_abi", "2"), ("activation_format", "2"), ("helper_abi", "2")]
    lines += pair(dict(m)["launcher_path"], launcher_data, 0o755)
    for r, package in sorted(releases.items()):
        lines += [("release", r), ("version", package["version"]),
                  ("source_kind", package["source_kind"]),
                  ("official_version", package["official_version"])]
        for leaf in LEAVES:
            lines += pair(f"releases/{r}/{leaf}", package["data"][leaf], payload_mode(leaf))
        lines += [("end_release", r)]
    return record(lines)


def manifest_read(data, m, launcher_data, load):
    rows = parse_record(data)
    prefix = [("format", "2"), ("scope", "runtime"), *m, ("core_api", "1"),
              ("adapter_abi", "2"), ("activation_format", "2"), ("helper_abi", "2")]
    prefix += pair(dict(m)["launcher_path"], launcher_data, 0o755)
    need(rows[:len(prefix)] == prefix, "runtime identity/launcher provenance")
    rest = rows[len(prefix):]
    releases = {}
    official = set()
    while rest:
        need(len(releases) < 1024 and len(rest) >= 29, "release block bounds")
        (key, r), (vk, v), (sk, source), (ok, mapping) = rest[:4]
        need(key == "release" and re.fullmatch(RELEASE, r) and r not in releases
             and (not releases or r > next(reversed(releases))) and vk == "version"
             and re.fullmatch(VERSION, v) and sk == "source_kind" and
             source in ("local", "official") and ok == "official_version" and
             mapping == ("-" if source == "local" else v), "release metadata")
        if source == "official":
            need(v not in official, "duplicate official version")
            official.add(v)
        package = load(r)
        need(package["release"] == r and package["version"] == v, "release identity")
        expected = rest[:4]
        for leaf in LEAVES:
            expected += pair(f"releases/{r}/{leaf}", package["data"][leaf], payload_mode(leaf))
        expected += [("end_release", r)]
        need(rest[:len(expected)] == expected, "release creation/baseline")
        package = dict(package, source_kind=source, official_version=mapping)
        releases[r] = package
        rest = rest[len(expected):]
    need(manifest_bytes(m, launcher_data, releases) == data, "manifest encoding")
    return releases


def previous_bytes(tx, m, items, snapshots):
    lines = [("format", "2"), ("scope", "previous"), ("tx", tx),
             ("transaction_scope", "machine"), *m]
    for item in sorted(items, key=lambda i: str(i["path"]).encode()):
        p = item["path"]
        snap = snapshots[p]
        attrs, data = snap if snap is not None else (None, None)
        state = "absent" if snap is None else "directory" if data is None else "file"
        retained = data if p.name in ("active", "runtime-manifest") and data else b""
        chunks = [retained[i:i + 4000] for i in range(0, len(retained), 4000)]
        lines += [("path", p), ("state", state), ("sha256", sha(data) if data is not None else "-"),
                  ("mode", f"{stat.S_IMODE(attrs[3]):04o}" if attrs else "-"),
                  ("dev", attrs[1] if attrs else "-"), ("ino", attrs[2] if attrs else "-"),
                  ("record_bytes", len(retained)), ("record_chunks", len(chunks))]
        lines += [("record_chunk", f"{i}:{chunk.hex()}") for i, chunk in enumerate(chunks, 1)]
        lines += [("end_path", p)]
    return record(lines)


def previous_read(data, expected, validate_metadata):
    """Validate chunks independently, then exact plan/snapshot encoding."""
    rows = parse_record(data)
    index = 10  # format, scope, tx, transaction_scope, M
    while index < len(rows):
        block = rows[index:index + 8]
        need([k for k, _ in block] == ["path", "state", "sha256", "mode", "dev", "ino",
                                     "record_bytes", "record_chunks"], "previous fields")
        p, state, digest, mode, dev, ino, size, count = [v for _, v in block]
        path_value(p)
        b, c = number(size), number(count)
        need(b <= META_LIMIT and c == (b + 3999) // 4000, "previous chunk counts")
        index += 8
        chunks = []
        for i in range(1, c + 1):
            need(index < len(rows) and rows[index][0] == "record_chunk", "missing chunk")
            value = rows[index][1]
            prefix = str(i) + ":"
            need(value.startswith(prefix) and re.fullmatch(r"(?:[0-9a-f]{2})+", value[len(prefix):]),
                 "chunk encoding/order")
            chunk = bytes.fromhex(value[len(prefix):])
            need(len(chunk) == (4000 if i < c else b - 4000 * (c - 1)), "chunk size")
            chunks.append(chunk)
            index += 1
        need(index < len(rows) and rows[index] == ("end_path", p), "previous end")
        if b:
            raw = b"".join(chunks)
            need(sha(raw) == digest and state == "file" and
                 Path(p).name in ("active", "runtime-manifest"), "nonmetadata preimage")
            validate_metadata(Path(p), raw)
        index += 1
    need(data == expected, "previous plan/snapshot mismatch")


def pending_bytes(tx, m, previous, old, new, items):
    need(len(items) <= 4096, "transaction item bounds")
    lines = [("format", "2"), ("scope", "pending"), ("tx", tx),
             ("operation", "update" if old else "install"), ("transaction_scope", "machine"),
             *m, ("previous_sha256", sha(previous)), ("selected", "-"),
             ("old_release", old or "-"), ("new_release", new), ("outcome", "complete")]
    for i, item in enumerate(items, 1):
        lines += [("item", i), ("phase", item["phase"]), ("action", item["action"]),
                  ("path", item["path"]), ("after_sha256", sha(item["data"])
                   if item["data"] is not None else "-"),
                  ("after_mode", f'{item["mode"]:04o}'), ("reason", "none"), ("end_item", i)]
    return record(lines)


def published_header(tx, pending):
    data = encoded([("format", "2"), ("scope", "published"), ("tx", tx),
                    ("pending_sha256", sha(pending))])
    return data + encoded([("header_sha256", sha(data))])


def fact_bytes(previous_hash, sequence, phase, item, result, snap=None):
    attrs, data = snap if snap else (None, None)
    lines = [("sequence", sequence), ("phase", phase), ("item", item), ("result", result),
             ("provider", "-"), ("generation", "-"),
             ("sha256", sha(data) if data is not None else "-"),
             ("mode", f"{stat.S_IMODE(attrs[3]):04o}" if attrs else "-"),
             ("dev", attrs[1] if attrs else "-"), ("ino", attrs[2] if attrs else "-")]
    raw = encoded(lines)
    return raw + encoded([("fact_sha256", sha(previous_hash.encode() + b"\n" + raw))])


def published_read(data, tx, pending, items, complete=False):
    text_bounds(data)
    header = published_header(tx, pending)
    need(data.startswith(header), "published header")
    tail = data[len(header):].splitlines(keepends=True)
    need(len(tail) % 11 == 0, "torn fact")
    chain = header.splitlines()[-1].split(b"=")[1].decode()
    last = 0
    for sequence in range(1, len(tail) // 11 + 1):
        block = tail[(sequence - 1) * 11:sequence * 11]
        raw = b"".join(block[:-1])
        rows = [line.decode().rstrip("\n").split("=", 1) for line in block]
        need([r[0] for r in rows] == ["sequence", "phase", "item", "result", "provider",
             "generation", "sha256", "mode", "dev", "ino", "fact_sha256"], "fact fields")
        values = [r[1] for r in rows]
        seq, phase, idx, result, provider, generation, digest, mode, dev, ino, h = values
        need(number(seq) == sequence and provider == generation == "-" and
             h == sha(chain.encode() + b"\n" + raw), "fact hash chain")
        n = number(idx)
        if n == 0:
            need(result == "committed" and phase == "complete" and
                 digest == mode == dev == ino == "-" and last == len(items) and
                 sequence == len(tail) // 11, "premature commit")
        else:
            need(n == last + 1 and n <= len(items), "fact plan order")
            item = items[n - 1]
            need(phase == item["phase"] and result == {"mkdir": "directory-created",
                 "create": "created", "replace": "replaced"}[item["action"]] and
                 digest == (item["after_sha256"] if "after_sha256" in item else
                            sha(item["data"]) if item["data"] is not None else "-") and
                 mode == f'{item["mode"]:04o}', "fact action/result")
            number(dev)
            number(ino)
            last = n
        chain = h
    if complete:
        need(bool(tail) and len(tail) // 11 == len(items) + 1 and n == 0, "missing commit")
    return chain, len(tail) // 11


def published_prefix(data, tx, pending, items):
    """Validate ALL bytes; only a possible next fact's strict prefix may tear."""
    text_bounds(data, torn=True)
    header = published_header(tx, pending)
    need(data.startswith(header), "published header")
    tail = data[len(header):]
    lines = tail.split(b"\n")
    blocks = (len(lines) - 1) // 11
    prefix = header + b"".join(line + b"\n" for line in lines[:blocks * 11])
    chain, count = published_read(prefix, tx, pending, items)
    suffix = data[len(prefix):]
    if not suffix:
        return prefix, count
    need(count <= len(items), "bytes after committed")
    if count == len(items):
        expected = fact_bytes(chain, count + 1, "complete", 0, "committed")
        need(expected.startswith(suffix), "impossible committed prefix")
        return prefix, count
    item = items[count]
    digest = (item["after_sha256"] if "after_sha256" in item else
              sha(item["data"]) if item["data"] is not None else "-")
    fixed = encoded([("sequence", count + 1), ("phase", item["phase"]),
                     ("item", count + 1), ("result", {"mkdir": "directory-created",
                      "create": "created", "replace": "replaced"}[item["action"]]),
                     ("provider", "-"), ("generation", "-"), ("sha256", digest),
                     ("mode", f'{item["mode"]:04o}')])
    if len(suffix) < len(fixed):
        need(fixed.startswith(suffix), "impossible fact prefix")
        return prefix, count
    need(suffix.startswith(fixed), "invalid partial fact fields")
    rest = suffix[len(fixed):]
    raw = fixed
    for key in (b"dev=", b"ino="):
        if len(rest) < len(key):
            need(key.startswith(rest), "impossible fact field")
            return prefix, count
        need(rest.startswith(key), "invalid fact field")
        value, sep, remainder = rest[len(key):].partition(b"\n")
        if value:
            number(value.decode())
        else:
            need(not sep, "empty decimal")
        if not sep:
            return prefix, count
        raw += key + value + b"\n"
        rest = remainder
    checksum = encoded([("fact_sha256", sha(chain.encode() + b"\n" + raw))])
    need(checksum.startswith(rest), "impossible fact checksum prefix")
    return prefix, count

"""Read-only machine journal classification; no recovery/adoption authority."""
import os
from pathlib import Path
import re


def journal_plan(raw, m, root, launcher):
    rows = parse_record(raw)
    need(len(rows) >= 16 and rows[:2] == [("format", "2"), ("scope", "pending")],
         "pending framing")
    tx = rows[2][1]
    need(rows[2][0] == "tx" and re.fullmatch(r"[0-9a-f]{32}", tx), "transaction ID")
    need(rows[4:11] == [("transaction_scope", "machine"), *m], "pending identity")
    need([k for k, _ in rows[11:16]] == ["previous_sha256", "selected",
         "old_release", "new_release", "outcome"], "pending fields")
    previous_hash, selected, old, new, outcome = [v for _, v in rows[11:16]]
    need(re.fullmatch(r"[0-9a-f]{64}", previous_hash) and selected == "-" and
         (old == "-" or re.fullmatch(RELEASE, old)) and re.fullmatch(RELEASE, new) and
         outcome == "complete" and rows[3] == ("operation", "install" if old == "-" else "update"),
         "machine plan selection")
    release = root / "releases" / new
    allowed = {root / "releases": ("release", 0o700),
               release: ("release", 0o700),
               launcher.parent.parent: ("launcher", 0o700),
               launcher.parent: ("launcher", 0o700), launcher: ("launcher", 0o755),
               root / "state/runtime-manifest": ("manifest", 0o600),
               root / "active": ("active", 0o600)}
    allowed.update({release / d: ("release", 0o700) for d in DIRS})
    allowed.update({release / p: ("release", payload_mode(p)) for p in LEAVES})
    tail, items, seen, ordered = rows[16:], [], set(), []
    need(len(tail) % 8 == 0 and len(tail) // 8 <= 4096, "item bounds")
    phases = {"release": 0, "launcher": 1, "manifest": 2, "active": 3}
    for offset in range(0, len(tail), 8):
        block = tail[offset:offset + 8]
        need([k for k, _ in block] == ["item", "phase", "action", "path",
             "after_sha256", "after_mode", "reason", "end_item"], "item fields")
        idx, phase, action, path, digest, mode, reason, end = [v for _, v in block]
        p = Path(path)
        need(idx == end == str(len(items) + 1) and p in allowed and str(p) == path and
             p not in seen and phase in phases and
             (phase, int(mode, 8)) == allowed[p] and mode == f"{allowed[p][1]:04o}" and
             reason == "none", "item identity/mode")
        directory = allowed[p][1] == 0o700
        need(action == "mkdir" if directory else action in ("create", "replace"),
             "item action")
        need(digest == "-" if directory else re.fullmatch(r"[0-9a-f]{64}", digest),
             "item digest")
        need(action != "replace" or p in (root / "active", root / "state/runtime-manifest"),
             "unowned replacement plan")
        items.append(dict(path=p, phase=phase, action=action, after_sha256=digest,
                          mode=allowed[p][1]))
        ordered.append((phases[phase], path.encode()))
        seen.add(p)
    need(ordered == sorted(ordered) and items, "machine phase/path order")
    return tx, previous_hash, old, new, items


def journal_previous(raw, tx, m, items, old, root, dispatcher):
    rows = parse_record(raw)
    need(rows[:10] == [("format", "2"), ("scope", "previous"), ("tx", tx),
                       ("transaction_scope", "machine"), *m], "previous identity")
    def metadata(path, data):
        if path.name == "active":
            need(data == ("release=" + old + "\n").encode() and old != "-", "prior active")
        else:
            releases = manifest_read(data, m, dispatcher, lambda r: verify_package(
                root / "releases" / r, installed=True))
            need(old in releases, "prior selection missing")
    previous_read(raw, raw, metadata)
    index, paths = 10, []
    planned = {str(i["path"]): i for i in items}
    while index < len(rows):
        values = dict(rows[index:index + 8])
        p, state = values["path"], values["state"]
        need(p in planned and p not in paths, "previous path inventory")
        item = planned[p]
        need(state == ("file" if item["action"] == "replace" else "absent"),
             "action lacks prior absence/ownership")
        if state == "absent":
            need(all(values[k] == "-" for k in ("sha256", "mode", "dev", "ino")) and
                 values["record_bytes"] == values["record_chunks"] == "0", "absent preimage")
        else:
            need(values["mode"] == "0600" and number(values["record_bytes"]) > 0 and
                 re.fullmatch(r"[0-9a-f]{64}", values["sha256"]), "metadata preimage")
            number(values["dev"])
            number(values["ino"])
        paths.append(p)
        index += 9 + number(values["record_chunks"])
    need(paths == sorted(planned, key=lambda p: p.encode()), "previous exact plan inventory")


def recovery_state(root, launcher, dispatcher):
    """none / pending / cleanup-pending / unknown, never a mutating decision."""
    try:
        state = root / "state"
        paths = [state / n for n in ("pending", "previous", "published")]
        present = [os.path.lexists(p) for p in paths]
        if not any(present):
            return "none"
        need(all(present), "orphan/missing journal framing")
        snaps = [snapshot(p) for p in paths]
        pending, previous, published = [read(p, mode=0o600) for p in paths]
        m = machine(root, launcher)
        tx, previous_hash, old, _, items = journal_plan(pending, m, root, launcher)
        need(sha(previous) == previous_hash, "previous digest")
        journal_previous(previous, tx, m, items, old, root, dispatcher)
        prefix, blocks = published_prefix(published, tx, pending, items)
        tail = prefix[len(published_header(tx, pending)):].splitlines(keepends=True)
        committed = blocks == len(items) + 1
        if committed:
            need(prefix == published, "bytes after committed")
            published_read(prefix, tx, pending, items, complete=True)
        for offset in range(0, blocks * 11, 11):
            row = dict(line.decode().rstrip("\n").split("=", 1)
                       for line in tail[offset:offset + 11])
            if row["item"] == "0":
                continue
            p = items[int(row["item"]) - 1]["path"]
            snap = snapshot(p)
            need(snap is not None and row["dev"] == str(snap[0][1]) and
                 row["ino"] == str(snap[0][2]) and
                 row["mode"] == f"{stat.S_IMODE(snap[0][3]):04o}" and
                 row["sha256"] == (sha(snap[1]) if snap[1] is not None else "-"),
                 "stale publication facts")
        need(all(snapshot(p) == before for p, before in zip(paths, snaps)), "changed journal read")
        return "cleanup-pending" if committed else "pending"
    except (Refusal, OSError, ValueError, IndexError, KeyError):
        return "unknown"

"""Trusted verification/availability protocol; activation/body APIs fail closed."""
import os
import sys


def active_read(data, releases):
    need(re.fullmatch(rb"release=r-[0-9a-f]{64}\n", data), "invalid active")
    release = data.decode()[8:-1]
    need(release in releases, "unlisted active")
    return release


def runtime_read(root, launcher, launcher_data, watch=None):
    """Pending is not rollback or revocation. Never guess a missing selection."""
    root, launcher = physical(root), physical(launcher)
    watch = watch if watch is not None else Watch()
    for p in (root, root / "state", root / "releases"):
        watch.add(p)
        snap = snapshot(p)
        need(snap is not None and snap[1] is None and
             stat.S_IMODE(snap[0][3]) == 0o700, "missing/unsafe runtime directory")
    watch.add(launcher)
    need(read(launcher, mode=0o755) == launcher_data, "edited launcher")
    m = machine(root, launcher)
    watch.add(root / "state/runtime-manifest")
    raw = read(root / "state/runtime-manifest", mode=0o600)

    def load(r):
        return verify_package(root / "releases" / r, installed=True, watch=watch)

    releases = manifest_read(raw, m, launcher_data, load)
    watch.add(root / "active")
    active = read(root / "active", mode=0o600)
    selected = active_read(active, releases)
    watch.check()
    return selected, releases, watch


def launcher_main(root, home):
    """Only availability/version is implemented here, never candidate dispatch."""
    try:
        if sys.argv[1:] in (["--help"], ["-h"], ["help"]):
            print("domestique2: local runtime protocol ABI 2; activation/management unavailable")
            return 0
        need(sys.argv[1:] in (["version"], ["--version"]),
             "unsupported operation; activation/management guards unavailable")
        home = physical(home)
        need(os.environ.get("HOME") == str(home), "conflicting HOME")
        override = os.environ.get("DOMESTIQUE_HOME")
        xdg = os.environ.get("XDG_STATE_HOME")
        if override:
            need(physical(override) / "v2" == Path(root), "conflicting runtime override")
        elif xdg:
            need(physical(xdg) / "domestique/v2" == Path(root), "conflicting state override")
        launcher = home / ".local/bin/domestique2"
        watch = Watch()
        watch.add(launcher)
        launcher_data = read(launcher, mode=0o755)
        selected, releases, watch = runtime_read(root, launcher, launcher_data, watch=watch)
        recovery = recovery_state(Path(root), launcher, launcher_data)
        watch.check()
        print("runtime=" + selected + " version=" + releases[selected]["version"] +
              " launcher_abi=2 recovery=" + recovery)
        return 0 if recovery == "none" else 1
    except (Refusal, OSError, ValueError):
        # Never print file contents, ambient values or unsafe path spellings.
        print("domestique2: runtime unavailable or unsupported; no fallback", file=sys.stderr)
        return 1

"""Frozen V2/1 argv grammar. Parsing never discovers files or runs operations."""
import re

COMMANDS = ("enable", "disable", "update", "inspect", "retire-global", "version", "help")
PLATFORMS = ("claude", "codex", "copilot", "both", "claude-copilot",
             "codex-copilot", "all")


class Misuse(Refusal):
    pass


def argument(ok):
    if not ok:
        raise Misuse("invalid arguments; use help")


def literal(value):
    argument(bool(value) and len(value.encode("utf-8")) <= 4096 and
             not any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in value))
    return value


def parse_cli(argv, bootstrap=False):
    args = list(argv)
    if "--" in args:
        argument(args.count("--") == 1 and args[-1] == "--")
        args.pop()
    if bootstrap:
        if args in (["--help"], ["-h"], ["help"]):
            return {"command": "help", "topic": "install"}
        command = "install"
    else:
        if not args:
            return {"command": "bare", "target": "."}
        if args in (["--help"], ["-h"]):
            return {"command": "help", "topic": None}
        if args == ["--version"]:
            return {"command": "version"}
        if args[0] == "--inspect":
            args[0] = "inspect"
        elif len(args) == 2 and args[-1] == "--inspect":
            argument(not args[0].startswith("-"))
            args = ["inspect", args[0]]
        command = args.pop(0)
        argument(command in COMMANDS)
        if args in (["--help"], ["-h"]):
            return {"command": "help", "topic": command}
        if command == "help":
            argument(len(args) <= 1 and (not args or args[0] in COMMANDS))
            return {"command": "help", "topic": args[0] if args else None}
    result = {"command": command}
    allowed = {
        "install": ("source", "version", "dry-run"),
        "update": ("source", "version", "dry-run"),
        "enable": ("platform", "dry-run"), "disable": ("platform", "dry-run"),
        "retire-global": ("platform", "dry-run"), "inspect": (), "version": (),
    }[command]
    while args:
        value = args.pop(0)
        if value.startswith("-"):
            flag, equal, item = value.partition("=")
            key = flag[2:] if flag.startswith("--") else ""
            argument(key in allowed and key not in result)
            if key == "dry-run":
                argument(not equal)
                result[key] = True
                continue
            if not equal:
                argument(bool(args))
                item = args.pop(0)
            literal(item)
            argument(not item.startswith("-"))
            result[key] = item
        else:
            argument(command in ("enable", "disable", "inspect") and "target" not in result)
            result["target"] = literal(value)
    if command in ("install", "update"):
        argument(("version" in result) != ("source" in result))
        if "version" in result:
            argument(re.fullmatch(VERSION, result["version"]) is not None)
        if "source" in result:
            argument("://" not in result["source"])
    if "platform" in result:
        argument(result["platform"] in PLATFORMS)
    argument(command != "retire-global" or "platform" in result)
    if command in ("enable", "disable", "inspect"):
        result.setdefault("target", ".")
    return result


def usage(topic=None):
    if topic == "install":
        return ("install-v2.sh (--version 2.MINOR.PATCH | --source PACKAGE_DIRECTORY) "
                "[--dry-run]\n"
                "Verified runtime-only bootstrap; no activation, PATH or alias edits.\n"
                "Official URLs are a future publication contract, not a release claim.")
    return ("domestique2 [help [COMMAND] | version | inspect [TARGET]]\n"
            "Aliases: --help, -h, --version, --inspect [TARGET], TARGET --inspect.\n"
            "Bare invocation: read-only help and inspect .; always offline.\n"
            "enable/disable [TARGET] [--platform P] [--dry-run],\n"
            "update (--version V | --source PATH) [--dry-run],\n"
            "retire-global --platform P [--dry-run]: UNIMPLEMENTED, exit 1.\n"
            "Inspection retains legacy/preview inventory; V2 activation inventory "
            "and native/workflow guards are unavailable.")

def dispatcher_program():
    return '"""V2 filesystem primitives, adapted from global_path/global_link_new and stdio bridge.\n\nNo shell evaluation, native discovery, retries, permission repair or adoption.\nOnly Python stdlib; the internal API requires an already available Python 3.9+.\n"""\nimport hashlib\nfrom contextlib import contextmanager, nullcontext\nimport os\nfrom pathlib import Path\nimport re\nimport stat\n\nMETA_LIMIT = 1048576\nPAYLOAD_LIMIT = 64 * 1048576\nMAX_NUMBER = 2**63 - 1\n\n\nclass Refusal(Exception):\n    pass\n\n\ndef need(ok, why):\n    if not ok:\n        raise Refusal(why)\n\n\ndef sha(data):\n    return hashlib.sha256(data).hexdigest()\n\n\ndef path_value(value):\n    need(isinstance(value, str) and value and len(value.encode("utf-8")) <= 4096,\n         "invalid path length")\n    need(not any(ord(c) < 32 or 127 <= ord(c) <= 159 or c == "=" for c in value),\n         "non-data path")\n    need(value != "/" and not value.endswith("/") and\n         all(p not in ("", ".", "..") for p in value.lstrip("/").split("/")) and\n         not value.startswith("//"), "noncanonical path")\n    return value\n\n\ndef physical(value):\n    path_value(str(value))\n    p = Path(value)\n    need(p.is_absolute(), "absolute physical path required")\n    safe(p)\n    return p\n\n\ndef attributes(s):\n    return (s.st_uid, s.st_dev, s.st_ino, s.st_mode, s.st_nlink,\n            s.st_size, s.st_mtime_ns, s.st_ctime_ns)\n\n\ndef identity(s):\n    return (s.st_uid, s.st_dev, s.st_ino, s.st_mode)\n\n\ndef safe(path):\n    """Exact ancestors only, root-owned sticky system ancestors permitted."""\n    path = Path(path)\n    if path != Path("/"):  # System root is an ancestor, never a supplied scope.\n        path_value(str(path))\n    need(path.is_absolute(), "absolute path required")\n    for p in reversed((path, *path.parents)):\n        try:\n            s = p.lstat()\n        except FileNotFoundError:\n            continue\n        directory = stat.S_ISDIR(s.st_mode)\n        need(directory or stat.S_ISREG(s.st_mode), "unsafe filesystem object")\n        need(p == path or directory, "non-directory ancestor")\n        need(s.st_uid in (0, os.getuid()), "foreign ancestor owner")\n        need(not s.st_mode & 0o022 or\n             (directory and s.st_uid == 0 and s.st_mode & stat.S_ISVTX),\n             "unsafe writable ancestry")\n        need(not stat.S_ISREG(s.st_mode) or s.st_nlink == 1, "hard-linked leaf")\n        need(s.st_mode & 0o400 and os.access(p, os.R_OK), "unreadable path")\n        need(not directory or (s.st_mode & 0o100 and os.access(p, os.X_OK)),\n             "unsearchable directory")\n\n\ndef snapshot(path, limit=PAYLOAD_LIMIT):\n    path = Path(path)\n    safe(path)\n    try:\n        before = path.lstat()\n    except FileNotFoundError:\n        return None\n    need(before.st_uid == os.getuid(), "unowned destination/input")\n    if stat.S_ISDIR(before.st_mode):\n        return (attributes(before), None)\n    need(before.st_size <= limit, "input too large")\n    ancestors = [(p, identity(p.lstat())) for p in path.parents]\n    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)\n    try:\n        need(attributes(os.fstat(fd)) == attributes(before), "changed opened file")\n        with os.fdopen(fd, "rb", closefd=False) as stream:\n            data = stream.read(limit + 1)\n        need(len(data) <= limit and attributes(os.fstat(fd)) == attributes(before),\n             "changed/oversize read")\n    finally:\n        os.close(fd)\n    safe(path)\n    need(attributes(path.lstat()) == attributes(before) and\n         all(identity(p.lstat()) == old for p, old in ancestors), "changed read identity")\n    return (attributes(before), data)\n\n\ndef read(path, limit=META_LIMIT, mode=None):\n    snap = snapshot(path, limit)\n    need(snap is not None and snap[1] is not None, "missing regular file")\n    if mode is not None:\n        need(stat.S_IMODE(snap[0][3]) == mode, "incorrect file mode")\n    return snap[1]\n\n\ndef text_bounds(data, torn=False):\n    need(len(data) <= META_LIMIT and (torn or data.endswith(b"\\n")) and\n         not data.startswith(b"\\xef\\xbb\\xbf"), "invalid metadata framing/size")\n    lines = data.split(b"\\n")\n    need(len(lines) - int(data.endswith(b"\\n")) <= 16384 and\n         all(len(line) + 1 <= 8192 for line in lines), "metadata line bounds")\n    try:\n        text = data.decode("utf-8")\n    except UnicodeError as exc:\n        raise Refusal("invalid UTF-8") from exc\n    need(not any(ord(c) < 32 and c != "\\n" or 127 <= ord(c) <= 159 for c in text),\n         "metadata controls")\n    return text\n\n\ndef checked_write(fd, path, data, before, guard):\n    """Write only from a witnessed snapshot; close has no buffered write debt.\n\n    Short writes advance by their actual count. EINTR retries only after fresh\n    checks; other errors and zero progress retain the partial file, never truncate\n    or clean it. This is observation-bound, not hostile-writer atomicity.\n    """\n    offset = 0\n    current = before\n    while True:\n        guard()\n        need(attributes(os.fstat(fd)) == current[0] and snapshot(path) == current,\n             "changed write identity/bytes")\n        if offset == len(data):\n            return current\n        try:\n            count = os.write(fd, memoryview(data)[offset:])\n        except InterruptedError:\n            continue\n        need(0 < count <= len(data) - offset, "write made no valid progress")\n        raw = current[1] + data[offset:offset + count]\n        after = os.fstat(fd)\n        need(identity(after) == current[0][:4] and after.st_nlink == 1 and\n             after.st_size == len(raw), "changed partial write")\n        current = (attributes(after), raw)\n        offset += count\n\n\ndef write_created(fd, path, data, mode, guard, before=None):\n    """The open descriptor, not the name or equal bytes, witnesses creation."""\n    initial = os.fstat(fd)\n    need(before is None or attributes(initial) == before[0], "changed creation handoff")\n    need(initial.st_uid == os.getuid() and stat.S_ISREG(initial.st_mode) and\n         initial.st_nlink == 1 and initial.st_size == 0, "invalid creation witness")\n    checked_write(fd, path, b"", (attributes(initial), b""), guard)\n    need(attributes(os.fstat(fd)) == attributes(initial) and\n         snapshot(path) == (attributes(initial), b""), "changed pre-chmod creation")\n    os.fchmod(fd, mode)\n    changed = os.fstat(fd)\n    need(identity(changed)[:3] == identity(initial)[:3] and\n         changed.st_mode == stat.S_IFREG | mode and changed.st_nlink == 1 and\n         changed.st_size == 0 and changed.st_mtime_ns == initial.st_mtime_ns,\n         "changed creation mode")\n    return checked_write(fd, path, data, (attributes(changed), b""), guard)\n\n\ndef exclusive(path, data, mode, guard=None, watch=None):\n    """O_EXCL is the single-leaf equivalent of global_link_new, without links."""\n    safe(path)\n    guard = guard or (lambda: safe(path))\n    guard()\n    fd = None\n    try:\n        with watch.namespace(Path(path).parent, entry_delta=1) if watch else nullcontext():\n            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)\n            before = (attributes(os.fstat(fd)), b"")\n        return write_created(fd, path, data, mode, guard, before)\n    finally:\n        if fd is not None:\n            os.close(fd)\n\n\ndef moved_witness(fd, before, links):\n    """A link/rename/unlink may change ctime/link count, not bytes or mtime."""\n    after = attributes(os.fstat(fd))\n    need(after[:4] == before[0][:4] and after[4] == links and\n         after[5:7] == before[0][5:7], "changed moved afterimage")\n    return after, before[1]\n\n\nclass Watch:\n    """Checked preflight snapshots; only our witnessed mutations advance them."""\n    def __init__(self, boundary=None):\n        self.paths = {}\n        self.ancestors = {}\n        self.boundary = boundary or (lambda: None)\n\n    def _observe(self, path):\n        # Bind ancestors before opening the leaf, never to a later replacement.\n        for p in path.parents:\n            if p.exists():\n                current = identity(p.lstat())\n                need(self.ancestors.setdefault(p, current) == current,\n                     "changed ancestor identity")\n        return snapshot(path)\n\n    def add(self, path):\n        """Register before validation; revisiting cannot erase an earlier proof."""\n        path = Path(path)\n        current = self._observe(path)\n        need(self.paths.setdefault(path, current) == current, "changed preflight path")\n        return current\n\n    def check(self):\n        self.check_boundary()\n        for p, old in self.paths.items():\n            need(snapshot(p) == old, "changed preflight path")\n\n    def check_boundary(self):\n        """Fresh overlap and identity checks, also during witnessed mutations."""\n        for p, old in self.ancestors.items():\n            safe(p)\n            need(identity(p.lstat()) == old, "changed ancestor identity")\n        for p, old in self.paths.items():\n            if old is not None and old[1] is None:\n                safe(p)\n                need(identity(p.lstat()) == old[0][:4], "changed directory identity")\n        self.boundary()\n\n    @contextmanager\n    def namespace(self, parent, entry_delta, directory_delta=0):\n        """Witness parent metadata at the namespace syscall, not after file I/O.\n\n        The caller checks its leaf preconditions separately (including the\n        two-link transition). Only this directory\'s namespace metadata can move.\n        """\n        parent = Path(parent)\n        self.check_boundary()\n        before = self.add(parent)\n        need(before is not None and before[1] is None, "missing publication parent")\n        fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)\n        try:\n            need(attributes(os.fstat(fd)) == before[0], "changed opened parent")\n            yield\n            after = (attributes(os.fstat(fd)), None)\n            # Unix directories count subdirectories; APFS counts all entries.\n            need(after[0][:4] == before[0][:4] and\n                 (after[0][4] - before[0][4] in (directory_delta, entry_delta) or\n                  after[0][4] == before[0][4] == 1), "changed publication parent")\n            self.advance(parent, after)\n        finally:\n            os.close(fd)\n\n    def mkdir(self, path, mode=0o700):\n        path = Path(path)\n        self.add(path)\n        self.check()\n        need(self.paths[path] is None, "directory creation collision")\n        fd = None\n        try:\n            with self.namespace(path.parent, entry_delta=1, directory_delta=1):\n                os.mkdir(path, mode)\n                fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)\n                created = (attributes(os.fstat(fd)), None)\n            need(created[0][0] == os.getuid() and\n                 created[0][3] == stat.S_IFDIR | mode, "invalid directory creation")\n            with os.scandir(fd) as entries:\n                need(next(entries, None) is None, "nonempty directory creation")\n            self.advance(path, created)\n            return created\n        finally:\n            if fd is not None:\n                os.close(fd)\n\n    def advance(self, path, witnessed):\n        """Bind an actual result; never acquire authority from a later pathname."""\n        path = Path(path)\n        need(self._observe(path) == witnessed, "changed witnessed publication")\n        self.paths[path] = witnessed\n        if witnessed is None:\n            self.ancestors.pop(path, None)\n\n"""Closed format-2 local package verifier. Never executes input."""\n# Bundle imports are removed by build.py; source imports share these primitives.\n\nROLES = ("goal", "implementer", "orchestrator", "reviewer")\nPROVIDERS = ("claude", "codex", "copilot")\nLEAVES = tuple(sorted(("PACKAGE", "SHA256SUMS", "domestique2.sh", "update2.sh",\n                       "bin/resolve-core") +\n                      tuple("roles/" + r + ".md" for r in ROLES) +\n                      tuple("adapters/" + p + ".templates" for p in PROVIDERS)))\nEXECUTABLES = ("domestique2.sh", "update2.sh", "bin/resolve-core")\nDIRS = ("adapters", "bin", "roles")\nVERSION = r"2\\.(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)"\nRELEASE = r"r-[0-9a-f]{64}"\n\n\ndef payload_mode(leaf):\n    return 0o755 if leaf in EXECUTABLES else 0o644\n\n\ndef package_header(version):\n    need(re.fullmatch(VERSION, version) is not None, "unsupported package version")\n    return ("format=2\\nproduct=domestique\\nmajor=2\\nversion=" + version +\n            "\\ncore_api=1\\nadapter_abi=2\\nactivation_format=2\\nhelper_abi=2\\n"\n            "launcher_abi=2\\n").encode()\n\n\ndef inventory(root, leaves, directories):\n    """Bounded exact enumeration, including empty unexpected directories."""\n    expected = set(leaves) | set(directories)\n    actual = set()\n    parents = [root] + [root / d for d in directories]\n    before = {}\n    for parent in parents:\n        snap = snapshot(parent)\n        need(snap is not None and snap[1] is None, "missing package directory")\n        before[parent] = snap\n        # scandir streams; never materialize an unbounded foreign inventory.\n        import os\n        with os.scandir(parent) as entries:\n            for entry in entries:\n                rel = str(Path(entry.path).relative_to(root))\n                need(rel in expected and rel not in actual, "extra/duplicate inventory")\n                actual.add(rel)\n    need(actual == expected, "incomplete inventory")\n    need(all(snapshot(p) == s for p, s in before.items()), "changed inventory")\n\n\ndef verify_package(root, expected_version=None, installed=False, watch=None):\n    root = physical(root)\n    watch = watch if watch is not None else Watch()\n    # Retained package authority must travel with these very observations, not\n    # a traversal/snapshot taken after the verifier returns its in-memory data.\n    for p in (root, *(root / d for d in DIRS)):\n        watch.add(p)\n    inventory(root, LEAVES, DIRS)\n    # Check the aggregate before allocating payload snapshots.\n    need(sum((root / p).lstat().st_size for p in LEAVES) <= PAYLOAD_LIMIT,\n         "expanded payload cap")\n    for leaf in LEAVES:\n        watch.add(root / leaf)\n    data = {}\n    total = 0\n    for leaf in LEAVES:\n        data[leaf] = read(root / leaf, META_LIMIT if leaf in\n                          ("PACKAGE", "SHA256SUMS") else PAYLOAD_LIMIT,\n                          payload_mode(leaf) if installed else None)\n        need(data[leaf] == watch.paths[root / leaf][1], "changed package read bytes")\n        total += len(data[leaf])\n        need(total <= PAYLOAD_LIMIT, "expanded payload cap")\n    result = package_from_data(data, expected_version)\n    inventory(root, LEAVES, DIRS)\n    watch.check()\n    return result\n\n\ndef package_from_data(data, expected_version=None):\n    """Same closed verifier for archive bytes and physical directory snapshots."""\n    need(tuple(sorted(data)) == LEAVES and\n         sum(len(value) for value in data.values()) <= PAYLOAD_LIMIT, "payload inventory/cap")\n    text = text_bounds(data["PACKAGE"])\n    lines = text.splitlines()\n    need(len(lines) == 9 and lines[3].startswith("version="), "PACKAGE fields")\n    version = lines[3][8:]\n    need(data["PACKAGE"] == package_header(version), "PACKAGE schema/ABI")\n    need(expected_version is None or version == expected_version, "version mismatch")\n    text_bounds(data["SHA256SUMS"])\n    sums = b"".join((sha(data[p]) + "  " + p + "\\n").encode()\n                    for p in LEAVES if p != "SHA256SUMS")\n    need(sums == data["SHA256SUMS"], "checksum inventory/digest mismatch")\n    return {"release": "r-" + sha(sums), "version": version, "data": data,\n            "source_kind": "local", "official_version": "-"}\n\n"""Appendix A/B/D machine encoders and strict readers (no general record engine)."""\n\n\ndef encoded(lines):\n    data = "".join(k + "=" + str(v) + "\\n" for k, v in lines).encode()\n    return data\n\n\ndef record(lines):\n    data = encoded(lines)\n    result = data + ("checksum=" + sha(data) + "\\n").encode()\n    text_bounds(result)\n    return result\n\n\ndef parse_record(data):\n    lines = text_bounds(data).splitlines()\n    need(lines and re.fullmatch(r"checksum=[0-9a-f]{64}", lines[-1]), "record checksum")\n    need(sha(data[:-(len(lines[-1]) + 1)]) == lines[-1][9:], "record corruption")\n    pairs = []\n    for line in lines[:-1]:\n        key, sep, value = line.partition("=")\n        need(sep and key and value, "empty record field")\n        pairs.append((key, value))\n    need(record(pairs) == data, "noncanonical record")\n    return pairs\n\n\ndef number(value):\n    need(re.fullmatch(r"0|[1-9][0-9]*", value) and int(value) <= MAX_NUMBER,\n         "invalid decimal")\n    return int(value)\n\n\ndef machine(root, launcher, placeholder=False):\n    s = root.stat() if not placeholder else None\n    return [("core_root", str(root)), ("core_dev", str(s.st_dev if s else MAX_NUMBER)),\n            ("core_ino", str(s.st_ino if s else MAX_NUMBER)),\n            ("owner_uid", str(s.st_uid if s else MAX_NUMBER)),\n            ("launcher_path", str(launcher)), ("launcher_abi", "2")]\n\n\ndef pair(path, data, mode):\n    value = f"{path}:{sha(data)}:{mode:04o}"\n    return [("created", value), ("baseline", value)]\n\n\ndef manifest_bytes(m, launcher_data, releases):\n    need(0 < len(releases) <= 1024, "release block bounds")\n    lines = [("format", "2"), ("scope", "runtime"), *m, ("core_api", "1"),\n             ("adapter_abi", "2"), ("activation_format", "2"), ("helper_abi", "2")]\n    lines += pair(dict(m)["launcher_path"], launcher_data, 0o755)\n    for r, package in sorted(releases.items()):\n        lines += [("release", r), ("version", package["version"]),\n                  ("source_kind", package["source_kind"]),\n                  ("official_version", package["official_version"])]\n        for leaf in LEAVES:\n            lines += pair(f"releases/{r}/{leaf}", package["data"][leaf], payload_mode(leaf))\n        lines += [("end_release", r)]\n    return record(lines)\n\n\ndef manifest_read(data, m, launcher_data, load):\n    rows = parse_record(data)\n    prefix = [("format", "2"), ("scope", "runtime"), *m, ("core_api", "1"),\n              ("adapter_abi", "2"), ("activation_format", "2"), ("helper_abi", "2")]\n    prefix += pair(dict(m)["launcher_path"], launcher_data, 0o755)\n    need(rows[:len(prefix)] == prefix, "runtime identity/launcher provenance")\n    rest = rows[len(prefix):]\n    releases = {}\n    official = set()\n    while rest:\n        need(len(releases) < 1024 and len(rest) >= 29, "release block bounds")\n        (key, r), (vk, v), (sk, source), (ok, mapping) = rest[:4]\n        need(key == "release" and re.fullmatch(RELEASE, r) and r not in releases\n             and (not releases or r > next(reversed(releases))) and vk == "version"\n             and re.fullmatch(VERSION, v) and sk == "source_kind" and\n             source in ("local", "official") and ok == "official_version" and\n             mapping == ("-" if source == "local" else v), "release metadata")\n        if source == "official":\n            need(v not in official, "duplicate official version")\n            official.add(v)\n        package = load(r)\n        need(package["release"] == r and package["version"] == v, "release identity")\n        expected = rest[:4]\n        for leaf in LEAVES:\n            expected += pair(f"releases/{r}/{leaf}", package["data"][leaf], payload_mode(leaf))\n        expected += [("end_release", r)]\n        need(rest[:len(expected)] == expected, "release creation/baseline")\n        package = dict(package, source_kind=source, official_version=mapping)\n        releases[r] = package\n        rest = rest[len(expected):]\n    need(manifest_bytes(m, launcher_data, releases) == data, "manifest encoding")\n    return releases\n\n\ndef previous_bytes(tx, m, items, snapshots):\n    lines = [("format", "2"), ("scope", "previous"), ("tx", tx),\n             ("transaction_scope", "machine"), *m]\n    for item in sorted(items, key=lambda i: str(i["path"]).encode()):\n        p = item["path"]\n        snap = snapshots[p]\n        attrs, data = snap if snap is not None else (None, None)\n        state = "absent" if snap is None else "directory" if data is None else "file"\n        retained = data if p.name in ("active", "runtime-manifest") and data else b""\n        chunks = [retained[i:i + 4000] for i in range(0, len(retained), 4000)]\n        lines += [("path", p), ("state", state), ("sha256", sha(data) if data is not None else "-"),\n                  ("mode", f"{stat.S_IMODE(attrs[3]):04o}" if attrs else "-"),\n                  ("dev", attrs[1] if attrs else "-"), ("ino", attrs[2] if attrs else "-"),\n                  ("record_bytes", len(retained)), ("record_chunks", len(chunks))]\n        lines += [("record_chunk", f"{i}:{chunk.hex()}") for i, chunk in enumerate(chunks, 1)]\n        lines += [("end_path", p)]\n    return record(lines)\n\n\ndef previous_read(data, expected, validate_metadata):\n    """Validate chunks independently, then exact plan/snapshot encoding."""\n    rows = parse_record(data)\n    index = 10  # format, scope, tx, transaction_scope, M\n    while index < len(rows):\n        block = rows[index:index + 8]\n        need([k for k, _ in block] == ["path", "state", "sha256", "mode", "dev", "ino",\n                                     "record_bytes", "record_chunks"], "previous fields")\n        p, state, digest, mode, dev, ino, size, count = [v for _, v in block]\n        path_value(p)\n        b, c = number(size), number(count)\n        need(b <= META_LIMIT and c == (b + 3999) // 4000, "previous chunk counts")\n        index += 8\n        chunks = []\n        for i in range(1, c + 1):\n            need(index < len(rows) and rows[index][0] == "record_chunk", "missing chunk")\n            value = rows[index][1]\n            prefix = str(i) + ":"\n            need(value.startswith(prefix) and re.fullmatch(r"(?:[0-9a-f]{2})+", value[len(prefix):]),\n                 "chunk encoding/order")\n            chunk = bytes.fromhex(value[len(prefix):])\n            need(len(chunk) == (4000 if i < c else b - 4000 * (c - 1)), "chunk size")\n            chunks.append(chunk)\n            index += 1\n        need(index < len(rows) and rows[index] == ("end_path", p), "previous end")\n        if b:\n            raw = b"".join(chunks)\n            need(sha(raw) == digest and state == "file" and\n                 Path(p).name in ("active", "runtime-manifest"), "nonmetadata preimage")\n            validate_metadata(Path(p), raw)\n        index += 1\n    need(data == expected, "previous plan/snapshot mismatch")\n\n\ndef pending_bytes(tx, m, previous, old, new, items):\n    need(len(items) <= 4096, "transaction item bounds")\n    lines = [("format", "2"), ("scope", "pending"), ("tx", tx),\n             ("operation", "update" if old else "install"), ("transaction_scope", "machine"),\n             *m, ("previous_sha256", sha(previous)), ("selected", "-"),\n             ("old_release", old or "-"), ("new_release", new), ("outcome", "complete")]\n    for i, item in enumerate(items, 1):\n        lines += [("item", i), ("phase", item["phase"]), ("action", item["action"]),\n                  ("path", item["path"]), ("after_sha256", sha(item["data"])\n                   if item["data"] is not None else "-"),\n                  ("after_mode", f\'{item["mode"]:04o}\'), ("reason", "none"), ("end_item", i)]\n    return record(lines)\n\n\ndef published_header(tx, pending):\n    data = encoded([("format", "2"), ("scope", "published"), ("tx", tx),\n                    ("pending_sha256", sha(pending))])\n    return data + encoded([("header_sha256", sha(data))])\n\n\ndef fact_bytes(previous_hash, sequence, phase, item, result, snap=None):\n    attrs, data = snap if snap else (None, None)\n    lines = [("sequence", sequence), ("phase", phase), ("item", item), ("result", result),\n             ("provider", "-"), ("generation", "-"),\n             ("sha256", sha(data) if data is not None else "-"),\n             ("mode", f"{stat.S_IMODE(attrs[3]):04o}" if attrs else "-"),\n             ("dev", attrs[1] if attrs else "-"), ("ino", attrs[2] if attrs else "-")]\n    raw = encoded(lines)\n    return raw + encoded([("fact_sha256", sha(previous_hash.encode() + b"\\n" + raw))])\n\n\ndef published_read(data, tx, pending, items, complete=False):\n    text_bounds(data)\n    header = published_header(tx, pending)\n    need(data.startswith(header), "published header")\n    tail = data[len(header):].splitlines(keepends=True)\n    need(len(tail) % 11 == 0, "torn fact")\n    chain = header.splitlines()[-1].split(b"=")[1].decode()\n    last = 0\n    for sequence in range(1, len(tail) // 11 + 1):\n        block = tail[(sequence - 1) * 11:sequence * 11]\n        raw = b"".join(block[:-1])\n        rows = [line.decode().rstrip("\\n").split("=", 1) for line in block]\n        need([r[0] for r in rows] == ["sequence", "phase", "item", "result", "provider",\n             "generation", "sha256", "mode", "dev", "ino", "fact_sha256"], "fact fields")\n        values = [r[1] for r in rows]\n        seq, phase, idx, result, provider, generation, digest, mode, dev, ino, h = values\n        need(number(seq) == sequence and provider == generation == "-" and\n             h == sha(chain.encode() + b"\\n" + raw), "fact hash chain")\n        n = number(idx)\n        if n == 0:\n            need(result == "committed" and phase == "complete" and\n                 digest == mode == dev == ino == "-" and last == len(items) and\n                 sequence == len(tail) // 11, "premature commit")\n        else:\n            need(n == last + 1 and n <= len(items), "fact plan order")\n            item = items[n - 1]\n            need(phase == item["phase"] and result == {"mkdir": "directory-created",\n                 "create": "created", "replace": "replaced"}[item["action"]] and\n                 digest == (item["after_sha256"] if "after_sha256" in item else\n                            sha(item["data"]) if item["data"] is not None else "-") and\n                 mode == f\'{item["mode"]:04o}\', "fact action/result")\n            number(dev)\n            number(ino)\n            last = n\n        chain = h\n    if complete:\n        need(bool(tail) and len(tail) // 11 == len(items) + 1 and n == 0, "missing commit")\n    return chain, len(tail) // 11\n\n\ndef published_prefix(data, tx, pending, items):\n    """Validate ALL bytes; only a possible next fact\'s strict prefix may tear."""\n    text_bounds(data, torn=True)\n    header = published_header(tx, pending)\n    need(data.startswith(header), "published header")\n    tail = data[len(header):]\n    lines = tail.split(b"\\n")\n    blocks = (len(lines) - 1) // 11\n    prefix = header + b"".join(line + b"\\n" for line in lines[:blocks * 11])\n    chain, count = published_read(prefix, tx, pending, items)\n    suffix = data[len(prefix):]\n    if not suffix:\n        return prefix, count\n    need(count <= len(items), "bytes after committed")\n    if count == len(items):\n        expected = fact_bytes(chain, count + 1, "complete", 0, "committed")\n        need(expected.startswith(suffix), "impossible committed prefix")\n        return prefix, count\n    item = items[count]\n    digest = (item["after_sha256"] if "after_sha256" in item else\n              sha(item["data"]) if item["data"] is not None else "-")\n    fixed = encoded([("sequence", count + 1), ("phase", item["phase"]),\n                     ("item", count + 1), ("result", {"mkdir": "directory-created",\n                      "create": "created", "replace": "replaced"}[item["action"]]),\n                     ("provider", "-"), ("generation", "-"), ("sha256", digest),\n                     ("mode", f\'{item["mode"]:04o}\')])\n    if len(suffix) < len(fixed):\n        need(fixed.startswith(suffix), "impossible fact prefix")\n        return prefix, count\n    need(suffix.startswith(fixed), "invalid partial fact fields")\n    rest = suffix[len(fixed):]\n    raw = fixed\n    for key in (b"dev=", b"ino="):\n        if len(rest) < len(key):\n            need(key.startswith(rest), "impossible fact field")\n            return prefix, count\n        need(rest.startswith(key), "invalid fact field")\n        value, sep, remainder = rest[len(key):].partition(b"\\n")\n        if value:\n            number(value.decode())\n        else:\n            need(not sep, "empty decimal")\n        if not sep:\n            return prefix, count\n        raw += key + value + b"\\n"\n        rest = remainder\n    checksum = encoded([("fact_sha256", sha(chain.encode() + b"\\n" + raw))])\n    need(checksum.startswith(rest), "impossible fact checksum prefix")\n    return prefix, count\n\n"""Frozen V2/1 argv grammar. Parsing never discovers files or runs operations."""\nimport re\n\nCOMMANDS = ("enable", "disable", "update", "inspect", "retire-global", "version", "help")\nPLATFORMS = ("claude", "codex", "copilot", "both", "claude-copilot",\n             "codex-copilot", "all")\n\n\nclass Misuse(Refusal):\n    pass\n\n\ndef argument(ok):\n    if not ok:\n        raise Misuse("invalid arguments; use help")\n\n\ndef literal(value):\n    argument(bool(value) and len(value.encode("utf-8")) <= 4096 and\n             not any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in value))\n    return value\n\n\ndef parse_cli(argv, bootstrap=False):\n    args = list(argv)\n    if "--" in args:\n        argument(args.count("--") == 1 and args[-1] == "--")\n        args.pop()\n    if bootstrap:\n        if args in (["--help"], ["-h"], ["help"]):\n            return {"command": "help", "topic": "install"}\n        command = "install"\n    else:\n        if not args:\n            return {"command": "bare", "target": "."}\n        if args in (["--help"], ["-h"]):\n            return {"command": "help", "topic": None}\n        if args == ["--version"]:\n            return {"command": "version"}\n        if args[0] == "--inspect":\n            args[0] = "inspect"\n        elif len(args) == 2 and args[-1] == "--inspect":\n            argument(not args[0].startswith("-"))\n            args = ["inspect", args[0]]\n        command = args.pop(0)\n        argument(command in COMMANDS)\n        if args in (["--help"], ["-h"]):\n            return {"command": "help", "topic": command}\n        if command == "help":\n            argument(len(args) <= 1 and (not args or args[0] in COMMANDS))\n            return {"command": "help", "topic": args[0] if args else None}\n    result = {"command": command}\n    allowed = {\n        "install": ("source", "version", "dry-run"),\n        "update": ("source", "version", "dry-run"),\n        "enable": ("platform", "dry-run"), "disable": ("platform", "dry-run"),\n        "retire-global": ("platform", "dry-run"), "inspect": (), "version": (),\n    }[command]\n    while args:\n        value = args.pop(0)\n        if value.startswith("-"):\n            flag, equal, item = value.partition("=")\n            key = flag[2:] if flag.startswith("--") else ""\n            argument(key in allowed and key not in result)\n            if key == "dry-run":\n                argument(not equal)\n                result[key] = True\n                continue\n            if not equal:\n                argument(bool(args))\n                item = args.pop(0)\n            literal(item)\n            argument(not item.startswith("-"))\n            result[key] = item\n        else:\n            argument(command in ("enable", "disable", "inspect") and "target" not in result)\n            result["target"] = literal(value)\n    if command in ("install", "update"):\n        argument(("version" in result) != ("source" in result))\n        if "version" in result:\n            argument(re.fullmatch(VERSION, result["version"]) is not None)\n        if "source" in result:\n            argument("://" not in result["source"])\n    if "platform" in result:\n        argument(result["platform"] in PLATFORMS)\n    argument(command != "retire-global" or "platform" in result)\n    if command in ("enable", "disable", "inspect"):\n        result.setdefault("target", ".")\n    return result\n\n\ndef usage(topic=None):\n    if topic == "install":\n        return ("install-v2.sh (--version 2.MINOR.PATCH | --source PACKAGE_DIRECTORY) "\n                "[--dry-run]\\n"\n                "Verified runtime-only bootstrap; no activation, PATH or alias edits.\\n"\n                "Official URLs are a future publication contract, not a release claim.")\n    return ("domestique2 [help [COMMAND] | version | inspect [TARGET]]\\n"\n            "Aliases: --help, -h, --version, --inspect [TARGET], TARGET --inspect.\\n"\n            "Bare invocation: read-only help and inspect .; always offline.\\n"\n            "enable/disable [TARGET] [--platform P] [--dry-run],\\n"\n            "update (--version V | --source PATH) [--dry-run],\\n"\n            "retire-global --platform P [--dry-run]: UNIMPLEMENTED, exit 1.\\n"\n            "Inspection retains legacy/preview inventory; V2 activation inventory "\n            "and native/workflow guards are unavailable.")\n\n"""Fixed management dispatch protocol, not workflow policy or a resolver.\n\nThis supersedes, but NEVER migrates/adopts, the help-only development prototype.\nCompatible package changes must not change this bundle\'s bytes.\n"""\nimport os\nimport subprocess\nimport sys\n\n\ndef management_index(raw, m, dispatcher):\n    """Strict B index without opening workflow bodies, helpers or native data.\n\n    Creation/baseline pairs authenticate the selected management bytes against\n    local provenance. Closed sums reproduce each R; hashes are not signatures.\n    Full payload validation remains the publisher\'s separate runtime_read.\n    """\n    rows = parse_record(raw)\n    prefix = [("format", "2"), ("scope", "runtime"), *m, ("core_api", "1"),\n              ("adapter_abi", "2"), ("activation_format", "2"), ("helper_abi", "2")]\n    prefix += pair(dict(m)["launcher_path"], dispatcher, 0o755)\n    need(rows[:len(prefix)] == prefix, "runtime identity/launcher provenance")\n    rows = rows[len(prefix):]\n    releases, versions = {}, set()\n    while rows:\n        need(len(releases) < 1024 and len(rows) >= 29, "release block bounds")\n        (rk, r), (vk, v), (sk, source), (ok, official) = rows[:4]\n        need(rk == "release" and re.fullmatch(RELEASE, r) and r not in releases and\n             (not releases or r > next(reversed(releases))) and vk == "version" and\n             re.fullmatch(VERSION, v) and sk == "source_kind" and\n             source in ("local", "official") and ok == "official_version" and\n             official == ("-" if source == "local" else v), "release metadata")\n        if source == "official":\n            need(v not in versions, "duplicate official mapping")\n            versions.add(v)\n        hashes = {}\n        for n, leaf in enumerate(LEAVES):\n            created, baseline = rows[4 + 2*n:6 + 2*n]\n            stem = f"releases/{r}/{leaf}:"\n            value = created[1]\n            need(created[0] == "created" and baseline == ("baseline", value) and\n                 value.startswith(stem), "creation/baseline inventory")\n            digest, sep, mode = value[len(stem):].partition(":")\n            need(re.fullmatch(r"[0-9a-f]{64}", digest) and sep and\n                 mode == f"{payload_mode(leaf):04o}", "creation digest/mode")\n            hashes[leaf] = digest\n        end = 4 + 2*len(LEAVES)\n        need(rows[end] == ("end_release", r), "release end")\n        sums = b"".join((hashes[p] + "  " + p + "\\n").encode()\n                        for p in LEAVES if p != "SHA256SUMS")\n        need(r == "r-" + sha(sums) and hashes["SHA256SUMS"] == sha(sums) and\n             hashes["PACKAGE"] == sha(package_header(v)), "release identity/sums")\n        releases[r] = dict(version=v, hashes=hashes, sums=sums)\n        rows = rows[end + 1:]\n    need(releases, "empty manifest")\n    return releases\n\n\ndef management_read(root, launcher):\n    watch = Watch()\n    for p in (root, root / "state", root / "releases"):\n        watch.add(p)\n        snap = snapshot(p)\n        need(snap is not None and snap[1] is None and\n             stat.S_IMODE(snap[0][3]) == 0o700, "unsafe runtime directory")\n    # Register BEFORE validation; a later observation is never a new baseline.\n    watch.add(launcher)\n    dispatcher = read(launcher, mode=0o755)\n    manifest = root / "state/runtime-manifest"\n    watch.add(manifest)\n    releases = management_index(read(manifest, mode=0o600), machine(root, launcher), dispatcher)\n    watch.add(root / "active")\n    active = read(root / "active", mode=0o600)\n    need(re.fullmatch(rb"release=r-[0-9a-f]{64}\\n", active), "invalid active")\n    selected = active.decode()[8:-1]\n    need(selected in releases, "unlisted active")\n    package = releases[selected]\n    release = root / "releases" / selected\n    watch.add(release)\n    snap = snapshot(release)\n    need(snap is not None and snap[1] is None and\n         stat.S_IMODE(snap[0][3]) == 0o700, "unsafe release directory")\n    data = {}\n    for leaf in ("PACKAGE", "SHA256SUMS", "domestique2.sh"):\n        p = release / leaf\n        watch.add(p)\n        data[leaf] = read(p, PAYLOAD_LIMIT if leaf.endswith(".sh") else META_LIMIT,\n                          payload_mode(leaf))\n        need(sha(data[leaf]) == package["hashes"][leaf], "edited management payload")\n    # Management does not open workflow payloads even to classify a journal.\n    # Any machine/retirement journal therefore conservatively means unknown.\n    recovery = "none"\n    for directory in (root / "state", root / "state/retire-global"):\n        for name in ("pending", "previous", "published"):\n            p = directory / name\n            watch.add(p)\n            if watch.paths[p] is not None:\n                recovery = "unknown"\n    watch.check()\n    return selected, package["version"], recovery, data["domestique2.sh"], watch\n\n\ndef dispatch_main(root, home):\n    try:\n        parsed = parse_cli(sys.argv[1:])\n        command = parsed["command"]\n        if command == "help":\n            print(usage(parsed["topic"]))\n            return 0\n        home, root = physical(home), physical(root)\n        need(os.environ.get("HOME") == str(home), "conflicting HOME")\n        override, xdg = os.environ.get("DOMESTIQUE_HOME"), os.environ.get("XDG_STATE_HOME")\n        if xdg:\n            physical(xdg)\n        if override:\n            need(physical(override) / "v2" == root, "conflicting runtime override")\n        elif xdg:\n            need(physical(xdg) / "domestique/v2" == root, "conflicting state override")\n        if command in ("update", "enable", "disable", "retire-global"):\n            if command == "update" and os.environ.get("DOMESTIQUE_UPDATE_SOURCE"):\n                raise Misuse("DOMESTIQUE_UPDATE_SOURCE refused; use explicit selectors")\n            print("domestique2: " + command + " UNIMPLEMENTED; no fallback", file=sys.stderr)\n            return 1\n        selected, version, recovery, payload, watch = management_read(\n            root, home / ".local/bin/domestique2")\n        watch.check()\n        if command == "bare":\n            print(usage())\n        print("runtime=" + selected + " version=" + version +\n              " contract=V2/1 launcher_abi=2 management=verified workflow=not-assessed "\n              "recovery=" + recovery, flush=True)\n        if command == "version":\n            return 0 if recovery == "none" else 1\n        print("activation=not-assessed (inventory unimplemented); native-evidence=BLOCKED",\n              flush=True)\n        watch.check()\n        # Execute only the immutable VERIFIED in-memory afterimage, never a\n        # mutable source path. No BASH_ENV, exported functions or startup imports.\n        env = {k: v for k, v in os.environ.items() if k in\n               ("PATH", "HOME", "TMPDIR", "DOMESTIQUE_HOME", "XDG_STATE_HOME")}\n        env["DOMESTIQUE_HOME"] = str(root.parent)\n        result = subprocess.run(["/bin/bash", "--noprofile", "--norc", "-s", "--",\n                                 "inspect", parsed["target"]], input=payload,\n                                env=env, stderr=subprocess.DEVNULL, check=False)\n        watch.check()\n        need(result.returncode in (0, 1, 2), "management runtime failure")\n        return result.returncode if recovery == "none" else 1\n    except Misuse as exc:\n        print("domestique2: " + str(exc), file=sys.stderr)\n        return 2\n    except (Refusal, OSError, ValueError, IndexError):\n        print("domestique2: runtime unavailable/invalid or conflicting root; no fallback",\n              file=sys.stderr)\n        return 1\n'
def python_shell(program):
    # -I -S -B: no cwd/site/user imports, environment startup or bytecode writes.
    return ("#!/bin/bash -p\nset -eu\ncommand -v python3 >/dev/null 2>&1 || exit 1\n"
            "if [ \"$(command -v python3)\" = /usr/bin/python3 ] && "
            "[ \"$(uname -s)\" = Darwin ]; then exit 1; fi\n"
            "exec python3 -I -S -B - \"$@\" <<'DOMESTIQUE_V2_TRUSTED_PY'\n" +
            "import sys\nif sys.version_info < (3, 9): sys.exit(1)\n" +
            program + "\nDOMESTIQUE_V2_TRUSTED_PY\n").encode()
def launcher_bytes(root, home):
    return python_shell(dispatcher_program() +
                        f"\nsys.exit(dispatch_main({str(root)!r}, {str(home)!r}))\n")
"""Trusted provider-independent local machine publisher, Appendix A/B/D.

publish_local(source, env, dry_run=False, hook=None) is the internal API.
hook is a trusted test callback, never an environment/CLI escape or candidate.
No recovery, native/project operation or GC. Bootstrap supplies a trusted
selection callback for official transport, after existing-state validation.
"""
from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid


class PublicationFailure(Refusal):
    def __init__(self, selected, recovery):
        self.selected, self.recovery = selected, recovery
        super().__init__(f"publication failed: runtime={selected}; recovery={recovery}; "
                         "preserve evidence; no rollback or takeover")


def no_repo(path, env):
    # Every call observes the exact ancestors afresh. Gitfiles, dangling
    # redirects and .git directories refuse without invoking Git. Bare Git
    # discovery needs Git only when an ancestor has its HEAD entry.
    ancestors = (path, *path.parents)
    for parent in ancestors:
        need(not os.path.lexists(parent / ".git") and parent.name != ".git",
             "machine destination overlaps Git")
    p = path
    while not p.is_dir():
        p = p.parent
    git = shutil.which("git", path=env.get("PATH", ""))
    need(git, "missing Git capability")
    git_env = {"PATH": env["PATH"], "HOME": env["HOME"], "LC_ALL": "C",
               "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_SYSTEM": os.devnull,
               "GIT_CONFIG_GLOBAL": os.devnull, "GIT_OPTIONAL_LOCKS": "0",
               "GIT_TERMINAL_PROMPT": "0", "GIT_PAGER": "cat"}
    proc = subprocess.run([git, "-C", str(p), "rev-parse", "--absolute-git-dir"],
                          env=git_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=120, check=False)
    need(proc.returncode == 128 and b"not a git repository" in proc.stderr,
         "machine destination overlaps Git or Git validation unavailable")


def boundary(paths, env):
    ancestors = {a for p in paths for a in (p, *p.parents)}
    for p in ancestors:
        need(p.name not in {".claude", ".agents", ".codex", ".copilot", ".github",
                           ".domestique-private", ".beads", ".git"},
             "machine/native overlap")
        need(not os.path.lexists(p / ".git"), "machine destination overlaps Git")
        if os.path.lexists(p / "HEAD"):
            no_repo(p, env)


@contextmanager
def staging_area(temp, watch):
    """Only our closed staging inventory; never auto-delete across a new boundary."""
    watch.check_boundary()
    staging = temp / ("domestique-v2-stage-" + uuid.uuid4().hex)
    created = watch.mkdir(staging)
    watch.advance(staging, created)
    stage = staging / "package"
    cleaned = False

    def clean():
        nonlocal cleaned
        watch.check()
        for p in (*(stage / p for p in reversed(LEAVES)),
                  *(stage / d for d in reversed(DIRS)), stage, staging):
            watch.check()
            need(snapshot(p) == watch.paths[p], "changed staging cleanup path")
            if os.path.lexists(p):
                safe(p)
                directory = p.is_dir()
                with watch.namespace(p.parent, entry_delta=-1,
                                     directory_delta=-1 if directory else 0):
                    if directory:
                        p.rmdir()
                    else:
                        p.unlink()
                watch.advance(p, None)
        cleaned = True

    # An exception thrown at yield leaves private evidence untouched, with no
    # automatic cleanup writes after a Git/native/identity boundary refusal.
    yield stage, clean
    if not cleaned:
        clean()
    watch.check_boundary()


def roots(env):
    need(not env.get("DOMESTIQUE_UPDATE_SOURCE"), "explicit local source required")
    home = physical(env.get("HOME", ""))
    need(home.is_dir(), "HOME unavailable")
    if env.get("XDG_STATE_HOME"):
        physical(env["XDG_STATE_HOME"])
    base = physical(env.get("DOMESTIQUE_HOME") or
                    str(Path(env.get("XDG_STATE_HOME") or str(home / ".local/state")) /
                        "domestique"))
    root, launcher = base / "v2", home / ".local/bin/domestique2"
    need(root != home and root not in home.parents and launcher != root and
         root not in launcher.parents and launcher not in root.parents, "overlapping roots")
    native = {".claude", ".agents", ".codex", ".copilot", ".github",
              ".domestique-private", ".beads", ".git"}
    for p in (root, launcher):
        safe(p)
        need(not native.intersection(p.parts), "machine/native overlap")
        no_repo(p, env)
    tools = {name: shutil.which(name, path=env.get("PATH", "")) for name in ("python3", "bash")}
    need(all(tools.values()), "missing runtime capability")
    need(sys.platform != "darwin" or tools["python3"] != "/usr/bin/python3",
         "Python setup launcher is not a runtime capability")
    for argv in ([tools["python3"], "-I", "-S", "-B", "-c",
                  "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)"],
                 [tools["bash"], "--noprofile", "--norc", "-c",
                  "(( BASH_VERSINFO[0] > 3 || (BASH_VERSINFO[0] == 3 && BASH_VERSINFO[1] >= 2) ))"]):
        check = subprocess.run(argv, env={"PATH": env["PATH"], "HOME": str(home)},
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               timeout=120, check=False)
        need(check.returncode == 0 and not check.stdout, "unsupported runtime capability")
    return home, root, launcher


def pending_refusal(root):
    for j in (root / "state", root / "state/retire-global"):
        for name in ("pending", "previous", "published"):
            p = j / name
            safe(p)
            need(not os.path.lexists(p), "pending/orphan evidence; no takeover")


def runtime_inventory(root, releases, journals=()):
    leaves = ["active", "state/runtime-manifest", *("state/" + p for p in journals)]
    dirs = ["state", "releases"]
    for r in releases:
        dirs += ["releases/" + r, *("releases/" + r + "/" + d for d in DIRS)]
        leaves += ["releases/" + r + "/" + p for p in LEAVES]
    inventory(root, leaves, dirs)
    for d in dirs:
        snap = snapshot(root / d)
        need(stat.S_IMODE(snap[0][3]) == 0o700, "private directory mode")


def missing_parents(path):
    result = []
    p = path
    while not p.exists():
        result.append(p)
        p = p.parent
    return list(reversed(result))


def plan(root, launcher, packages, selected, dispatcher, m, watch, framing):
    items = []

    def add(p, phase, data=None, mode=0o700, owned=False):
        if p not in watch.paths:
            watch.add(p)
        prior = watch.paths[p]
        if data is None and prior is not None:
            need(prior[1] is None, "directory collision")
            return
        if data is not None and prior is not None:
            need(owned and prior[1] is not None, "unowned matching/colliding leaf")
            if prior[1] == data and stat.S_IMODE(prior[0][3]) == mode:
                return
        action = "mkdir" if data is None else "replace" if prior else "create"
        items.append(dict(path=p, phase=phase, action=action, data=data, mode=mode))

    new = selected["release"] not in packages
    combined = dict(packages)
    if selected["source_kind"] == "official":
        need(all(p["official_version"] != selected["version"] or
                 r == selected["release"] for r, p in packages.items()),
             "conflicting retained official mapping")
        # An actual verified official selection may qualify a retained local R.
        # This changes only mapping metadata, never creation/baseline facts.
        combined[selected["release"]] = selected
    if new:
        combined[selected["release"]] = selected
        release = root / "releases" / selected["release"]
        for d in (root / "releases", release, *(release / d for d in DIRS)):
            add(d, "release")
        for leaf in LEAVES:
            add(release / leaf, "release", selected["data"][leaf], payload_mode(leaf))
    for p in missing_parents(launcher.parent):
        if p not in framing:
            add(p, "launcher")
    add(launcher, "launcher", dispatcher, 0o755, bool(packages))
    manifest = manifest_bytes(m, dispatcher, combined)
    add(root / "state/runtime-manifest", "manifest", manifest, 0o600, bool(packages))
    add(root / "active", "active", ("release=" + selected["release"] + "\n").encode(),
        0o600, bool(packages))
    order = {"release": 0, "launcher": 1, "manifest": 2, "active": 3}
    items.sort(key=lambda i: (order[i["phase"]], str(i["path"]).encode()))
    return items, combined


def publish_local(source, env, dry_run=False, hook=None):
    """Returns {runtime, recovery, changed, dry_run}; failures never claim rollback.

    Source is a local package directory, not a checkout/script/archive/URL.
    No source path is retained in destination metadata. env is an explicit
    trusted invocation environment, not candidate metadata.
    """
    hook = hook or (lambda event, path: None)
    def select(packages):
        path = str(source)
        need("://" not in path, "only local package directories")
        if not path.startswith("/"):
            path = str(Path.cwd() / path)
        candidate = verify_package(path)
        hook("verified-source", Path(path))
        return candidate
    return _publish(select, env, dry_run, hook)


def _publish(select, env, dry_run=False, hook=None):
    """One publisher; select is trusted bootstrap logic, never candidate code."""
    hook = hook or (lambda event, path: None)
    home, root, launcher = roots(env)
    dispatcher = launcher_bytes(root, home)
    pending_refusal(root)
    watch = Watch(lambda: boundary((root, launcher), env))
    watch.add(root)
    packages, old = {}, None
    if root.exists():
        old, packages, _ = runtime_read(root, launcher, dispatcher, watch=watch)
        runtime_inventory(root, packages)
        watch.check()
    else:
        need(not os.path.lexists(launcher), "unowned launcher; equality is not ownership")
    for p in (launcher, root / "state", *(root / "state" / n for n in
                                       ("pending", "previous", "published"))):
        watch.add(p)
    for p in (root, launcher):
        ancestor = p.parent
        while not ancestor.exists():
            watch.add(ancestor)
            ancestor = ancestor.parent
        need(os.access(ancestor, os.W_OK), "unwritable destination parent")
        watch.add(ancestor)
    candidate = select(packages)
    # A retained mapping is authorized by the original runtime/package proof.
    # Refuse drift at this hand-off, before any staging or publication writes.
    watch.check()
    temp = physical(env.get("TMPDIR", tempfile.gettempdir()))
    need(temp.is_dir() and temp != home and home not in temp.parents and
         temp != root and root not in temp.parents, "staging overlaps destination")
    no_repo(temp, env)
    def fresh_boundary():
        for p in (root, launcher.parent, temp):
            safe(p)
        need(not launcher.is_symlink(), "redirected launcher")
        boundary((root, launcher, temp, *watch.paths), env)
    watch.boundary = fresh_boundary
    watch.add(temp)
    writing = False
    with staging_area(temp, watch) as (stage, clean_stage):
        created = watch.mkdir(stage)
        watch.advance(stage, created)
        for d in DIRS:
            created = watch.mkdir(stage / d)
            watch.advance(stage / d, created)
        for p in LEAVES:
            watch.check()
            created = exclusive(stage / p, candidate["data"][p], payload_mode(p),
                                watch.check_boundary, watch=watch)
            watch.advance(stage / p, created)
        selected = verify_package(stage, installed=True, watch=watch)
        need(all(selected[k] == candidate[k] for k in ("release", "version", "data")),
             "stage differs from verified input")
        selected = dict(selected, source_kind=candidate["source_kind"],
                        official_version=candidate["official_version"])
        hook("stage", stage)
        framing = missing_parents(root) + ([] if (root / "state").exists()
                                          else [root / "state"])
        items, combined = plan(root, launcher, packages, selected, dispatcher,
                               machine(root, launcher, not root.exists()), watch, framing)
        tx = uuid.uuid4().hex
        # Worst-case machine identity and fact sizes are bounded before any claim.
        maximum_m = machine(root, launcher, True)
        maximal_items = [dict(i) for i in items]
        for i in maximal_items:
            if i["phase"] == "manifest":
                i["data"] = manifest_bytes(maximum_m, dispatcher, combined)
        pre = previous_bytes(tx, maximum_m, maximal_items, watch.paths)
        pen = pending_bytes(tx, maximum_m, pre, old, selected["release"], maximal_items)
        header = published_header(tx, pen)
        maximal = header
        h = header.splitlines()[-1].split(b"=")[1].decode()
        for n, i in enumerate(maximal_items, 1):
            fake = ((MAX_NUMBER, MAX_NUMBER, MAX_NUMBER,
                     stat.S_IFDIR | i["mode"] if i["data"] is None else
                     stat.S_IFREG | i["mode"], 1, 0, 0, 0), i["data"])
            raw = fact_bytes(h, n, i["phase"], n, {"mkdir": "directory-created",
                             "create": "created", "replace": "replaced"}[i["action"]], fake)
            maximal += raw
            h = raw.splitlines()[-1].split(b"=")[1].decode()
        maximal += fact_bytes(h, len(items) + 1, "complete", 0, "committed")
        text_bounds(maximal)
        watch.check()
        pending_refusal(root)
        hook("preflight", root)
        watch.check()
        if dry_run or not items:
            clean_stage()
            watch.check()
            return dict(runtime=old if dry_run else selected["release"], recovery="none",
                        changed=bool(items), dry_run=dry_run)
        try:
            for p in framing:
                watch.check()
                hook("before-claim", p)
                watch.check()
                writing = True
                created = watch.mkdir(p)
                watch.advance(p, created)
                hook("claim", p)
            m = machine(root, launcher)
            items, combined = plan(root, launcher, packages, selected, dispatcher,
                                   m, watch, framing)
            previous = previous_bytes(tx, m, items, watch.paths)
            pending = pending_bytes(tx, m, previous, old, selected["release"], items)

            def metadata(p, raw):
                if p.name == "active":
                    active_read(raw, packages)
                else:
                    need(raw == read(p, mode=0o600), "previous manifest changed")

            previous_read(previous, previous, metadata)
            published = published_header(tx, pending)
            for name, raw in (("pending", pending), ("previous", previous), ("published", published)):
                watch.check()
                p = root / "state" / name
                writing = True
                created = exclusive(p, raw, 0o600, watch.check_boundary, watch=watch)
                watch.advance(p, created)
                hook(name, p)

            def append(phase, n, result, snap=None):
                nonlocal published
                watch.check()
                h, seq = published_read(published, tx, pending, items)
                raw = fact_bytes(h, seq + 1, phase, n, result, snap)
                p = root / "state/published"
                watch.check_boundary()
                fd = os.open(p, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
                try:
                    appended = checked_write(fd, p, raw, watch.paths[p], watch.check_boundary)
                finally:
                    os.close(fd)
                published += raw
                need(read(p, mode=0o600) == published, "journal append failed")
                watch.advance(p, appended)
                watch.check()
                published_read(published, tx, pending, items)

            for n, i in enumerate(items, 1):
                p = i["path"]
                hook("before-" + i["phase"], p)
                watch.check()
                if i["phase"] in ("launcher", "manifest", "active"):
                    verified = verify_package(root / "releases" / selected["release"],
                                              installed=True, watch=watch)
                    need(verified["data"] == selected["data"], "final release changed")
                if i["phase"] in ("manifest", "active"):
                    # Final creations and facts, not intent/equal bytes, authorize B.
                    need(read(launcher, mode=0o755) == dispatcher, "final launcher changed")
                    _, count = published_read(published, tx, pending, items)
                    need(count == n - 1, "missing creation facts")
                watch.check()
                if i["action"] == "mkdir":
                    created = watch.mkdir(p, i["mode"])
                elif i["action"] == "create" and i["phase"] not in ("launcher", "active"):
                    created = exclusive(p, i["data"], i["mode"], watch.check_boundary,
                                        watch=watch)
                else:
                    fd = None
                    try:
                        with watch.namespace(p.parent, entry_delta=1):
                            fd, name = tempfile.mkstemp(prefix=".publication-", dir=p.parent)
                            tmp = Path(name)
                            initial = (attributes(os.fstat(fd)), b"")
                        created = write_created(fd, tmp, i["data"], i["mode"],
                                                watch.check_boundary, initial)
                        watch.advance(tmp, created)
                        watch.check()
                        hook("before-rename-" + i["phase"], p)
                        watch.check()
                        if i["action"] == "replace":
                            with watch.namespace(p.parent, entry_delta=-1):
                                os.replace(tmp, p)
                                created = moved_witness(fd, created, 1)
                        else:
                            # global_link_new pattern: atomic no-clobber final
                            # name, then remove our temporary link before verify.
                            # A partially written executable/selector is never visible.
                            with watch.namespace(p.parent, entry_delta=1):
                                os.link(tmp, p, follow_symlinks=False)
                                linked_witness = moved_witness(fd, created, 2)
                            watch.check_boundary()
                            # The two links are our witnessed transition, not a
                            # general exception to single-link safe reads. Keep
                            # the original descriptor through byte/identity checks.
                            linked = os.fstat(fd)
                            need(attributes(linked) == linked_witness[0],
                                 "changed linked afterimage")
                            with os.fdopen(fd, "rb", closefd=False) as stream:
                                stream.seek(0)
                                need(stream.read(len(i["data"]) + 1) == i["data"],
                                     "changed linked bytes")
                            watch.check_boundary()
                            need(attributes(os.fstat(fd)) == attributes(linked) ==
                                 attributes(tmp.lstat()) == attributes(p.lstat()),
                                 "changed linked identity")
                            with watch.namespace(p.parent, entry_delta=-1):
                                tmp.unlink()
                                created = moved_witness(fd, linked_witness, 1)
                        # Retain an absence watch: a new object at the old name
                        # must not be leaked by a falsely successful publication.
                        watch.advance(tmp, None)
                    finally:
                        # No failure-time unlink/restore/adoption. Even an empty
                        # or partially written afterimage is manual evidence.
                        if fd is not None:
                            os.close(fd)
                watch.advance(p, created)
                snap = snapshot(p)
                need(snap == created, "changed published identity/bytes")
                need(snap is not None and stat.S_IMODE(snap[0][3]) == i["mode"] and
                     snap[1] == i["data"], "post-publication verification")
                hook("written-" + i["phase"], p)
                append(i["phase"], n, {"mkdir": "directory-created", "create": "created",
                                      "replace": "replaced"}[i["action"]], snap)
                hook("after-" + i["phase"], p)
            actual, retained, checked = runtime_read(root, launcher, dispatcher, watch=watch)
            need(actual == selected["release"], "incorrect final selection")
            runtime_inventory(root, retained, ("pending", "previous", "published"))
            checked.check()
            watch.check()
            clean_stage()
            append("complete", 0, "committed")
            published_read(published, tx, pending, items, complete=True)
            hook("complete", root)
            for name in ("published", "previous", "pending"):
                hook("before-clear-" + name, root / "state" / name)
                watch.check()
                p = root / "state" / name
                with watch.namespace(p.parent, entry_delta=-1):
                    p.unlink()
                watch.advance(p, None)
                hook("clear-" + name, p)
            watch.check()
            return dict(runtime=actual, recovery="none", changed=True, dry_run=False)
        except Exception as exc:
            if not writing:
                raise
            actual = "unavailable"
            try:
                actual, _, _ = runtime_read(root, launcher, dispatcher)
            except (Refusal, OSError, ValueError):
                pass
            recovery = recovery_state(root, launcher, dispatcher)
            if recovery == "none" and actual == "unavailable":
                recovery = "unknown"
            raise PublicationFailure(actual, recovery) from exc

"""Fixed future GitHub release transport and closed, non-extracting tar decoder.

Checksums detect corruption, not independent publisher authentication. No
candidate code is executed here; no requests/third-party networking libraries.
"""
import gzip
import io
import os
import selectors
import shutil
import subprocess
import tarfile
import time
from urllib.parse import urljoin, urlsplit

HOSTS = ("github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com")


def release_url(version, sidecar=False):
    need(re.fullmatch(VERSION, version), "invalid official version")
    name = "domestique2-" + version + ".tar.gz"
    return ("https://github.com/ebowman/domestique/releases/download/v" +
            version + "/" + name + (".sha256" if sidecar else ""))


def https_release(url):
    parts = urlsplit(url)
    need(parts.scheme == "https" and parts.netloc in HOSTS and not parts.fragment and
         not any(ord(c) <= 32 or ord(c) >= 127 for c in url),
         "release redirect outside HTTPS allowlist")


def curl_response(url, cap, remaining, env):
    """One bounded response including headers. Kill/reap only our direct child."""
    curl = shutil.which("curl", path=env.get("PATH", ""))
    need(curl, "curl unavailable")
    argv = [curl, "-q", "--silent", "--show-error", "--fail",
            "--proto", "=https", "--proto-redir", "=https",
            "--connect-timeout", "10", "--max-time", str(remaining),
            "--retry", "0", "--proxy", "", "--noproxy", "*",
            "--max-filesize", str(cap), "--dump-header", "-", "--", url]
    process = subprocess.Popen(argv, env={"PATH": env.get("PATH", os.defpath), "LC_ALL": "C"},
                               stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL)
    end = time.monotonic() + remaining
    output = bytearray()
    header_end = None
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                left = end - time.monotonic()
                need(left > 0 and selector.select(left), "release fetch timeout")
                # Even a chunk straddling the header/body boundary can consume
                # at most the remaining body budget plus one overflow witness.
                size = (min(cap + 1, META_LIMIT + 1 - len(output))
                        if header_end is None else cap + 1 - (len(output) - header_end))
                chunk = os.read(process.stdout.fileno(), min(65536, size))
                if not chunk:
                    break
                search = max(0, len(output) - 3)
                output.extend(chunk)
                if header_end is None:
                    separator = output.find(b"\r\n\r\n", search)
                    if separator >= 0:
                        header_end = separator + 4
                    need((len(output) if header_end is None else header_end) <= META_LIMIT,
                         "release response header too large")
                if header_end is not None:
                    need(len(output) - header_end <= cap, "release response too large")
        need(process.wait(timeout=max(.001, end - time.monotonic())) == 0,
             "release fetch failed")
        return bytes(output)
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        process.stdout.close()


def fetch_asset(url, cap, env):
    deadline = time.monotonic() + 120
    budget = cap
    for redirects in range(4):
        https_release(url)
        left = deadline - time.monotonic()
        need(left > 0, "release fetch timeout")
        response = curl_response(url, budget, left, env)
        header, separator, body = response.partition(b"\r\n\r\n")
        need(separator and len(header) + 4 <= META_LIMIT and len(body) <= budget,
             "invalid/oversize release response")
        budget -= len(body)
        lines = header.split(b"\r\n")
        need(len(lines) <= 16384 and all(len(x) + 2 <= 8192 for x in lines),
             "response header bounds")
        match = re.fullmatch(rb"HTTP/(?:1\.[01]|2|3) ([0-9]{3})(?: [^\r\n]*)?", lines[0])
        need(match is not None, "invalid release HTTP status")
        fields = {}
        for line in lines[1:]:
            key, sep, value = line.partition(b":")
            need(sep and re.fullmatch(rb"[A-Za-z0-9-]+", key), "invalid HTTP field")
            key = key.lower()
            if key in (b"location", b"content-length"):
                need(key not in fields, "duplicate HTTP selection field")
                fields[key] = value.strip()
        status = int(match[1])
        if b"content-length" in fields:
            size = fields[b"content-length"]
            need(re.fullmatch(rb"0|[1-9][0-9]*", size) and len(size) < 20 and
                 int(size) == len(body), "truncated release response")
        if status in (301, 302, 303, 307, 308):
            need(redirects < 3 and b"location" in fields, "release redirect limit/location")
            url = urljoin(url, fields[b"location"].decode("ascii"))
            continue
        need(status == 200, "release unavailable")
        return body
    raise Refusal("release redirect limit")


def archive_data(archive, sidecar, version):
    """Verify archive BEFORE parsing; inspect every raw header before staging.

    Deliberately reject GNU/PAX extension records as extra inventory rather than
    letting tarfile silently hide them. Fixed leaf names need no extensions.
    Never tar.extract/all; archive owners, modes and timestamps are ignored.
    """
    need(len(archive) <= PAYLOAD_LIMIT, "archive cap")
    text_bounds(sidecar)
    name = "domestique2-" + version + ".tar.gz"
    need(sidecar == (sha(archive) + "  " + name + "\n").encode(),
         "archive sidecar format/digest")
    # Bound decompression including tar framing, not merely member-size claims.
    with gzip.GzipFile(fileobj=io.BytesIO(archive)) as stream:
        raw = stream.read(PAYLOAD_LIMIT + 1)
    need(len(raw) <= PAYLOAD_LIMIT and len(raw) % 512 == 0,
         "expanded archive cap/framing")
    directories = {"domestique2", *("domestique2/" + p for p in DIRS)}
    leaves = {"domestique2/" + p for p in LEAVES}
    seen, data, offset, total = set(), {}, 0, 0
    while offset + 512 <= len(raw) and raw[offset:offset + 512] != bytes(512):
        info = tarfile.TarInfo.frombuf(raw[offset:offset + 512], "utf-8", "strict")
        path = info.name
        need(path not in seen and path in directories | leaves, "archive inventory/path")
        seen.add(path)
        directory = path in directories
        need(info.type == tarfile.DIRTYPE if directory else
             info.type in (tarfile.REGTYPE, tarfile.AREGTYPE),
             "archive links/extensions/nonregular member")
        need(not info.linkname and not info.pax_headers and info.size >= 0,
             "archive link/size")
        size = info.size
        need(size == 0 if directory else size <= (
            META_LIMIT if path in ("domestique2/PACKAGE", "domestique2/SHA256SUMS")
            else PAYLOAD_LIMIT), "archive member cap")
        start = offset + 512
        offset = start + ((size + 511) // 512) * 512
        need(offset <= len(raw), "truncated archive member")
        if not directory:
            total += size
            need(total <= PAYLOAD_LIMIT, "expanded payload cap")
            data[path[len("domestique2/"):]] = raw[start:start + size]
    need(seen == directories | leaves and len(raw) - offset >= 1024 and
         not any(raw[offset:]), "incomplete/extra/truncated archive")
    return data


def fetch_package(version, env):
    sidecar = fetch_asset(release_url(version, True), META_LIMIT, env)
    archive = fetch_asset(release_url(version), PAYLOAD_LIMIT, env)
    return archive_data(archive, sidecar, version)

"""Trusted bootstrap orchestration; public update deliberately not implemented."""
import os
import sys


def publish_version(version, env, dry_run=False, hook=None):
    def select(packages):
        # _publish validates ALL retained mappings/packages first. A known
        # corrupt mapping can never fall through into a network overwrite.
        for package in packages.values():
            if package["official_version"] == version:
                return package
        candidate = package_from_data(fetch_package(version, env), version)
        return dict(candidate, source_kind="official", official_version=version)
    return _publish(select, env, dry_run, hook)


def bootstrap_main():
    try:
        parsed = parse_cli(sys.argv[1:], bootstrap=True)
        if parsed["command"] == "help":
            print(usage("install"))
            return 0
        if os.environ.get("DOMESTIQUE_UPDATE_SOURCE"):
            raise Misuse("DOMESTIQUE_UPDATE_SOURCE refused; use explicit selectors")
        env = dict(os.environ)
        if "source" in parsed:
            result = publish_local(parsed["source"], env, parsed.get("dry-run", False))
        else:
            result = publish_version(parsed["version"], env, parsed.get("dry-run", False))
        print("domestique2 bootstrap: runtime=" + str(result["runtime"] or "unavailable") +
              " recovery=" + result["recovery"] + " changed=" + str(result["changed"]) +
              " dry_run=" + str(result["dry_run"]))
        return 0
    except Misuse as exc:
        print("install-v2.sh: " + str(exc), file=sys.stderr)
        return 2
    except PublicationFailure as exc:
        print("install-v2.sh: " + str(exc), file=sys.stderr)
        return 1
    except Exception:
        # No raw candidate/HTTP/native content, path values or interpreter traces.
        print("install-v2.sh: verification/publication refused; preserve existing state. "
              "Unknown, edited or different development-prototype launchers are not "
              "adopted/migrated; no fallback.", file=sys.stderr)
        return 1

sys.exit(bootstrap_main())

DOMESTIQUE_V2_TRUSTED_PY
