"""Internal enable-plan journal/effect and activation-record publication interfaces.

NOT wired to enable, native discovery or a loader. hq-5jc.7 must supply/admit its
final native serialization before using these primitives. No automatic driver,
recovery, adoption, native replacement, rollback or failure-time cleanup.
"""
import os
from contextlib import contextmanager
from pathlib import Path
import stat
import uuid
import re
from types import MappingProxyType
from .safe import (MAX_NUMBER, attributes, checked_write, exclusive, moved_witness,
                   need, read, sha, snapshot, text_bounds)
from .records import encoded, record, parse_record, published_header, fact_bytes, number
from .project_records import (STATE, core_lines, identity_lines, native_inventory,
                              project_manifest_read, receipt_read)
from .project_preflight import JOURNALS, write_permissions
from .project_identity import identity_guard, index_untracked
from .package import PROVIDERS


def project_previous_bytes(tx, plan, items):
    need(re.fullmatch(r"[0-9a-f]{32}", tx) and len(items) <= 4096, "project transaction")
    lines = [("format", "2"), ("scope", "previous"), ("tx", tx),
             ("transaction_scope", "project"), *identity_lines(plan.i), *core_lines(plan.root)]
    for item in sorted(items, key=lambda i: str(i["path"]).encode()):
        p = item["path"]
        snap = plan.watch.paths[p]
        attrs, data = snap if snap is not None else (None, None)
        state = "absent" if snap is None else "directory" if data is None else "file"
        retained = b""
        if data is not None and (p == plan.worktree / STATE / "manifest" or
                                 p.parent == plan.worktree / STATE / "routing"):
            if p.name == "manifest":
                project_manifest_read(data)
            else:
                provider = p.name.removesuffix(".receipt")
                receipt_read(data, plan.i, plan.root, provider, plan.providers[provider])
            retained = data
        chunks = [retained[n:n + 4000] for n in range(0, len(retained), 4000)]
        lines += [("path", str(p)), ("state", state),
                  ("sha256", sha(data) if data is not None else "-"),
                  ("mode", f"{stat.S_IMODE(attrs[3]):04o}" if attrs else "-"),
                  ("dev", str(attrs[1]) if attrs else "-"), ("ino", str(attrs[2]) if attrs else "-"),
                  ("record_bytes", str(len(retained))), ("record_chunks", str(len(chunks)))]
        lines += [("record_chunk", f"{n}:{chunk.hex()}") for n, chunk in enumerate(chunks, 1)]
        lines += [("end_path", str(p))]
    return record(lines)


def project_pending_bytes(tx, plan, previous, items):
    need(re.fullmatch(r"[0-9a-f]{32}", tx) and len(items) <= 4096, "project item bounds")
    lines = [("format", "2"), ("scope", "pending"), ("tx", tx), ("operation", "enable"),
             ("transaction_scope", "project"), *identity_lines(plan.i), *core_lines(plan.root),
             ("previous_sha256", sha(previous)), ("selected", ",".join(plan.selected)),
             ("old_release", "-"), ("new_release", "-"), ("outcome", "complete")]
    for n, item in enumerate(items, 1):
        lines += [("item", str(n)), ("phase", item["phase"]), ("action", item["action"]),
                  ("path", str(item["path"])),
                  ("after_sha256", sha(item["data"]) if item["data"] is not None else "-"),
                  ("after_mode", f'{item["mode"]:04o}'), ("reason", "none"), ("end_item", str(n))]
    return record(lines)


def project_previous_read(data, tx, plan, items):
    """Exact frozen-plan reader, not independent recovery or ownership inference."""
    rows = parse_record(data)
    need(rows[:19] == [("format", "2"), ("scope", "previous"), ("tx", tx),
                       ("transaction_scope", "project"), *identity_lines(plan.i),
                       *core_lines(plan.root)], "project previous identity")
    offset = 19
    for item in sorted(items, key=lambda i: str(i["path"]).encode()):
        part = rows[offset:offset + 8]
        need([k for k, _ in part] == ["path", "state", "sha256", "mode", "dev",
             "ino", "record_bytes", "record_chunks"], "project previous fields")
        path, state, digest, mode, dev, ino, size, count = [v for _, v in part]
        need(path == str(item["path"]), "project previous path")
        size, count = number(size), number(count)
        need(size <= 1048576 and count == (size + 3999) // 4000, "project chunk bounds")
        chunks = []
        offset += 8
        for n in range(1, count + 1):
            need(offset < len(rows) and rows[offset][0] == "record_chunk", "missing chunk")
            prefix = str(n) + ":"
            value = rows[offset][1]
            need(value.startswith(prefix) and
                 re.fullmatch(r"(?:[0-9a-f]{2})+", value[len(prefix):]), "project chunk encoding")
            chunk = bytes.fromhex(value[len(prefix):])
            need(len(chunk) == (4000 if n < count else size - 4000 * (count - 1)),
                 "project chunk size")
            chunks.append(chunk)
            offset += 1
        need(offset < len(rows) and rows[offset] == ("end_path", path), "project previous end")
        offset += 1
        if size:
            raw = b"".join(chunks)
            need(state == "file" and sha(raw) == digest and mode == "0600",
                 "project metadata preimage")
            p = item["path"]
            if p == plan.worktree / STATE / "manifest":
                i, root, providers, _ = project_manifest_read(raw)
                need(i == plan.i and root == str(plan.root) and providers == plan.providers,
                     "project prior metadata identity")
            else:
                need(p.parent == plan.worktree / STATE / "routing", "nonmetadata preimage")
                provider = p.name.removesuffix(".receipt")
                receipt_read(raw, plan.i, plan.root, provider, plan.providers[provider])
    need(offset == len(rows) and data == project_previous_bytes(tx, plan, items),
         "project previous snapshot/roundtrip")


def project_pending_read(data, tx, plan, previous, items):
    parse_record(data)
    project_previous_read(previous, tx, plan, items)
    need(data == project_pending_bytes(tx, plan, previous, items), "project pending roundtrip")


def project_facts_read(raw, tx, pending, items, complete=False):
    text_bounds(raw)
    header = published_header(tx, pending)
    need(raw.startswith(header), "project published header")
    rows = raw[len(header):].splitlines(keepends=True)
    need(len(rows) % 11 == 0, "project torn fact")
    chain = header.splitlines()[-1].split(b"=")[1].decode()
    count = len(rows) // 11
    need(count <= len(items) + 1, "project fact bounds")
    for n in range(count):
        part = rows[11*n:11*(n + 1)]
        values = [line.decode().rstrip("\n").split("=", 1) for line in part]
        need([v[0] for v in values] == ["sequence", "phase", "item", "result", "provider",
             "generation", "sha256", "mode", "dev", "ino", "fact_sha256"], "project fact fields")
        seq, phase, idx, result, provider, gen, digest, mode, dev, ino, h = [v[1] for v in values]
        need(seq == str(n + 1) and provider == gen == "-" and
             sha(chain.encode() + b"\n" + b"".join(part[:-1])) == h, "project fact chain")
        if n == len(items):
            need((phase, idx, result, digest, mode, dev, ino) ==
                 ("complete", "0", "committed", "-", "-", "-", "-"), "project commit")
        else:
            item = items[n]
            need(idx == str(n + 1) and phase == item["phase"] and result ==
                 {"mkdir": "directory-created", "create": "created", "replace": "replaced",
                  "edit-exclude": "exclude-edited"}[item["action"]] and
                 digest == (sha(item["data"]) if item["data"] is not None else "-") and
                 mode == f'{item["mode"]:04o}', "project fact effect")
            number(dev)
            number(ino)
        chain = h
    need(not complete or count == len(items) + 1, "project missing commit")
    return chain, count


def project_facts_prefix(data, tx, pending, items):
    """Only a possible next complete fact may tear; all other bytes are unknown."""
    text_bounds(data, torn=True)
    header = published_header(tx, pending)
    need(data.startswith(header), "project published header")
    lines = data[len(header):].split(b"\n")
    blocks = (len(lines) - 1) // 11
    prefix = header + b"".join(line + b"\n" for line in lines[:blocks * 11])
    chain, count = project_facts_read(prefix, tx, pending, items)
    suffix = data[len(prefix):]
    if not suffix:
        return prefix, count
    need(count <= len(items), "bytes after project commit")
    if count == len(items):
        need(fact_bytes(chain, count + 1, "complete", 0, "committed").startswith(suffix),
             "impossible project commit prefix")
        return prefix, count
    item = items[count]
    fixed = encoded([("sequence", count + 1), ("phase", item["phase"]), ("item", count + 1),
                     ("result", {"mkdir": "directory-created", "create": "created",
                      "replace": "replaced", "edit-exclude": "exclude-edited"}[item["action"]]),
                     ("provider", "-"), ("generation", "-"),
                     ("sha256", sha(item["data"]) if item["data"] is not None else "-"),
                     ("mode", f'{item["mode"]:04o}')])
    if len(suffix) < len(fixed):
        need(fixed.startswith(suffix), "impossible project fact prefix")
        return prefix, count
    need(suffix.startswith(fixed), "invalid project partial fields")
    rest, raw = suffix[len(fixed):], fixed
    for key in (b"dev=", b"ino="):
        if len(rest) < len(key):
            need(key.startswith(rest), "impossible project fact field")
            return prefix, count
        need(rest.startswith(key), "invalid project fact field")
        value, sep, remainder = rest[len(key):].partition(b"\n")
        if value:
            number(value.decode())
        else:
            need(not sep, "empty project fact decimal")
        if not sep:
            return prefix, count
        raw += key + value + b"\n"
        rest = remainder
    need(encoded([("fact_sha256", sha(chain.encode() + b"\n" + raw))]).startswith(rest),
         "impossible project fact checksum prefix")
    return prefix, count


class _WriteGuard:
    """Delegate exactly the in-flight leaf to safe.checked_write's OS witness.

    That primitive checks the original/open creation inode and exact accumulated
    bytes AFTER this callback and BEFORE every os.write, including EINTR, short
    writes and final validation. All other observations are checked here. There
    is no resnapshot/adoption of partial bytes or lasting mutable-path exemption.
    Namespace operations always use the full Watch boundary, including the
    original absence immediately before exclusive creation.
    """
    def __init__(self, publication, path):
        self.publication, self.path = publication, path

    def __call__(self):
        tx = self.publication
        need(tx.checking_write is None, "nested project write guard")
        tx.checking_write = self.path
        try:
            tx.watch.check_boundary()
        finally:
            tx.checking_write = None


class ActivationPublication:
    """Fixed allowlisted effects, authenticated against the original ProjectPlan.

    Constructing/preparing is read-only, including on no-op. begin claims the
    journal; apply_next effects ONE fixed item; finish publishes a commit and
    clears last. No caller-supplied creation claims or native bytes are accepted.
    Native creation hashes enter manifest only after verified exclusive facts.
    """
    def __init__(self, plan):
        plan.check()
        self.plan, self.watch = plan, plan.watch
        self.checking_write = None
        self.j = plan.worktree / STATE
        self.tx = uuid.uuid4().hex
        self.begun = False
        self.count = 0
        self.items = []
        self.providers = plan.next_providers
        self.manifest = plan.manifest
        self.framing = []
        for directory in (self.j.parent, self.j):
            if self.watch.add(directory) is None:
                self.framing.append(directory)
        if plan.exclusion["action"]:
            self._item(plan.exclusion["path"], "exclusions", plan.exclusion["after"],
                       plan.exclusion["mode"], plan.exclusion["action"])
        for p in plan.selected:
            for leaf, data in plan.templates[p].items():
                path = plan.worktree / leaf
                if self.watch.paths[path] is None:
                    self._parents(path.parent, "native", 0o755)
                    self._item(path, "native", data, 0o644, "create")
        self._metadata(self.j / "manifest", "manifest", self.manifest)
        self._parents(self.j / "routing", "receipt", 0o700)
        for p in plan.selected:
            self._metadata(self.j / "routing" / (p + ".receipt"), "receipt",
                           plan.receipts[p])
        phases = {"exclusions": 0, "native": 1, "manifest": 2, "receipt": 3}
        self.items.sort(key=lambda v: (phases[v["phase"]], str(v["path"]).encode()))
        self.previous = project_previous_bytes(self.tx, plan, self.items)
        self.pending = project_pending_bytes(self.tx, plan, self.previous, self.items)
        project_pending_read(self.pending, self.tx, plan, self.previous, self.items)
        self.published = published_header(self.tx, self.pending)
        # Bound the maximum COMPLETED journal and metadata before directory claims.
        maximal, chain = self.published, self.published.splitlines()[-1].split(b"=")[1].decode()
        for n, item in enumerate(self.items, 1):
            attrs = (MAX_NUMBER, MAX_NUMBER, MAX_NUMBER, item["mode"], 1, 0, 0, 0)
            fact = fact_bytes(chain, n, item["phase"], n, {
                "mkdir": "directory-created", "create": "created", "replace": "replaced",
                "edit-exclude": "exclude-edited"}[item["action"]], (attrs, item["data"]))
            maximal += fact
            chain = fact.splitlines()[-1].split(b"=")[1].decode()
        maximal += fact_bytes(chain, len(self.items) + 1, "complete", 0, "committed")
        text_bounds(maximal)
        # Independently qualify the exact direct effect closure, including
        # framing, intermediate mkdirs, journal append/unlink and rename source.
        writes = [*self.framing, *(item["path"] for item in self.items)]
        if self.items:
            writes += [self.j / name for name in JOURNALS[:3]]
            if plan.exclusion["action"] == "edit-exclude":
                writes.append(self.j / "exclude-afterimage")
        self.write_paths = tuple(writes)
        write_permissions(self.write_paths, self.watch, observe=True)
        plan.check()
        # Retain the immutable preflight set even as exact completed effects
        # advance Watch's expected afterimages. Equal bytes never replace proof.
        self.originals = MappingProxyType(dict(self.watch.paths))
        self.original_ancestors = MappingProxyType(dict(self.watch.ancestors))
        self.watch.boundary = self._boundary
        # safe.namespace witnesses its parent descriptor but delegates leaf
        # preconditions to the caller. Recheck this transaction AFTER its open
        # handoff, also for safe.mkdir/exclusive using this same Watch.
        self.parent_namespace = self.watch.namespace
        self.watch.namespace = self._namespace

    @contextmanager
    def _namespace(self, parent, entry_delta, directory_delta=0):
        with self.parent_namespace(parent, entry_delta, directory_delta):
            self.check()
            yield

    def _item(self, path, phase, data, mode, action):
        self.watch.add(path)
        need(path not in [i["path"] for i in self.items], "duplicate planned path")
        self.items.append(dict(path=path, phase=phase, data=data, mode=mode, action=action))

    def _parents(self, path, phase, mode):
        missing = []
        while self.watch.add(path) is None and path not in self.framing:
            missing.append(path)
            path = path.parent
        for p in reversed(missing):
            if p not in [i["path"] for i in self.items]:
                self._item(p, phase, None, mode, "mkdir")

    def _metadata(self, path, phase, data):
        snap = self.watch.add(path)
        if snap is not None and snap[1] == data:
            need(stat.S_IMODE(snap[0][3]) == 0o600, "metadata mode")
            return
        self._item(path, phase, data, 0o600, "replace" if snap else "create")

    def _boundary(self):
        from .project_preflight import policy_boundaries
        policy_boundaries(self.plan.worktree, self.watch)
        identity_guard(self.plan.i)
        index_untracked(self.plan.i, [STATE, *(leaf for p in PROVIDERS
                                             for leaf in native_inventory(p))])
        # ALL providers, state/receipts/journals, exclusion, core/helper, index,
        # absent paths and directories remain relevant inside OS-write handoffs.
        # The only changes allowed are exact open-inode/namespace witnesses from
        # our own effects. The one checked-I/O destination is verified by the
        # safe primitive immediately after this callback; it is not resampled.
        for path, expected in self.watch.paths.items():
            if path != self.checking_write:
                need(snapshot(path) == expected, "changed project publication witness")
        write_permissions(self.write_paths, self.watch)

    def check(self):
        self.watch.check_boundary()

    def begin(self):
        need(not self.begun, "transaction already begun")
        self.plan.check()
        if not self.items:
            return False  # Exact no-op has no framing, journal or mtime effects.
        for directory in self.framing:
            self.watch.mkdir(directory)
        for name, data in (("pending", self.pending), ("previous", self.previous),
                           ("published", self.published)):
            self.check()
            path = self.j / name
            created = exclusive(path, data, 0o600, _WriteGuard(self, path), self.watch)
            self.watch.advance(path, created)
        self.begun = True
        return True

    def _fact(self, phase, item, result, snap=None):
        self.check()
        chain, count = project_facts_read(self.published, self.tx, self.pending, self.items)
        raw = fact_bytes(chain, count + 1, phase, item, result, snap)
        path = self.j / "published"
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
        try:
            created = checked_write(fd, path, raw, self.watch.paths[path], _WriteGuard(self, path))
        finally:
            os.close(fd)
        self.watch.advance(path, created)
        self.published += raw
        project_facts_read(self.published, self.tx, self.pending, self.items)

    def _replace(self, item):
        path = item["path"]
        # Only the frozen private exclusion afterimage name is admitted. For
        # mutable scope metadata, hold its original inode open, truncate/write
        # under pending; a failed write is retained as partial, never restored.
        if item["action"] == "replace":
            before = self.watch.paths[path]
            fd = os.open(path, os.O_WRONLY | os.O_NOFOLLOW)
            try:
                checked_write(fd, path, b"", before, _WriteGuard(self, path))
                os.ftruncate(fd, 0)
                empty = (attributes(os.fstat(fd)), b"")
                need(empty[0][:5] == before[0][:5] and empty[0][5] == 0,
                     "changed metadata truncation witness")
                self.watch.advance(path, empty)
                return checked_write(fd, path, item["data"], empty, _WriteGuard(self, path))
            finally:
                os.close(fd)
        stage = self.j / "exclude-afterimage"
        self.watch.add(stage)
        created = exclusive(stage, item["data"], 0o600, _WriteGuard(self, stage), self.watch)
        self.watch.advance(stage, created)
        self.check()
        fd = os.open(stage, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            # A read-only reopen is a new boundary, not permission to chmod.
            # Empty checked I/O checks all originals, then this exact open inode
            # AND its current pathname/bytes; it does not adopt a new baseline.
            checked_write(fd, stage, b"", created, _WriteGuard(self, stage))
            os.fchmod(fd, item["mode"])
            changed = (attributes(os.fstat(fd)), created[1])
            need(changed[0][:3] == created[0][:3] and changed[0][4:7] == created[0][4:7] and
                 changed[0][3] == stat.S_IFREG | item["mode"], "exclude afterimage mode")
            self.watch.advance(stage, changed)
            self.check()
            with self.watch.namespace(stage.parent, -1), self.watch.namespace(path.parent, 0):
                checked_write(fd, stage, b"", changed, _WriteGuard(self, stage))
                os.replace(stage, path)
                result = moved_witness(fd, changed, 1)
            self.watch.advance(stage, None)
            return result
        finally:
            os.close(fd)

    def apply_next(self):
        need(self.begun and self.count < len(self.items), "no pending effect")
        item = self.items[self.count]
        self.check()
        # No manifest/receipt assertion until ALL preceding actual facts exist.
        _, facts = project_facts_read(self.published, self.tx, self.pending, self.items)
        need(facts == self.count, "unwitnessed prior effect")
        path, action = item["path"], item["action"]
        if action == "mkdir":
            created = self.watch.mkdir(path, item["mode"])
        elif action == "create":
            created = exclusive(path, item["data"], item["mode"], _WriteGuard(self, path),
                                self.watch)
        else:
            created = self._replace(item)
        self.watch.advance(path, created)
        need(created[1] == item["data"] and stat.S_IMODE(created[0][3]) == item["mode"],
             "project post-effect mismatch")
        self._fact(item["phase"], self.count + 1, {
            "mkdir": "directory-created", "create": "created", "replace": "replaced",
            "edit-exclude": "exclude-edited"}[action], created)
        self.count += 1
        return path

    def finish(self):
        need(self.begun and self.count == len(self.items), "incomplete activation effects")
        self.check()
        need(read(self.j / "manifest", mode=0o600) == self.manifest, "final manifest")
        for p in self.plan.selected:
            receipt_read(read(self.j / "routing" / (p + ".receipt"), mode=0o600),
                         self.plan.i, self.plan.root, p, self.providers[p])
        self._fact("complete", 0, "committed")
        project_facts_read(self.published, self.tx, self.pending, self.items, complete=True)
        for name in ("published", "previous", "pending"):
            self.check()
            path = self.j / name
            with self.watch.namespace(path.parent, -1):
                path.unlink()
            self.watch.advance(path, None)
        self.check()
