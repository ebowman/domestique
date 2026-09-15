"""In-memory reset of positively owned, synthetic uninstall test trees only.

No database state, filesystem backups, validator caching, or root replacement.
The caller must finish ALL case assertions (including forbidden-call checks)
before accept(); an unaccepted/failed case can never be restored or cleaned.
"""
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import stat
import tempfile
from types import MappingProxyType


@dataclass(frozen=True)
class Entry:
    mode: int
    mtime: int
    data: object
    generation: object = None


class SyntheticTree:
    PREFIX = "domestique-remove-test-"

    def __init__(self, root, *, roots=()):
        self.root = Path(root)
        s = self.root.lstat()
        if (not self.root.is_absolute() or self.root.resolve() != self.root or
                self.root.parent != Path(tempfile.gettempdir()).resolve() or
                not self.root.name.startswith(self.PREFIX) or
                not stat.S_ISDIR(s.st_mode) or s.st_uid != os.getuid() or
                stat.S_IMODE(s.st_mode) != 0o700):
            raise ValueError("unsafe synthetic fixture root")
        self.identity = (s.st_dev, s.st_ino)
        self.root_identities = {}
        for rel in roots:
            rel = Path(rel)
            if rel.is_absolute() or ".." in rel.parts:
                raise ValueError("unsafe pinned fixture root")
            p = self.root / rel
            s = p.lstat()
            if p.resolve() != p or not stat.S_ISDIR(s.st_mode):
                raise ValueError("unsafe pinned fixture root")
            self.root_identities[rel] = (s.st_dev, s.st_ino)
        self.pristine = MappingProxyType(self._scan(payload=True))
        self.observed = None

    def _root_check(self):
        s = self.root.lstat()
        if (self.root.resolve() != self.root or not stat.S_ISDIR(s.st_mode) or
                (s.st_dev, s.st_ino) != self.identity or s.st_uid != os.getuid() or
                stat.S_IMODE(s.st_mode) != 0o700):
            raise ValueError("synthetic fixture root changed")
        for rel, identity in self.root_identities.items():
            p = self.root / rel
            s = p.lstat()
            if (p.resolve() != p or not stat.S_ISDIR(s.st_mode) or
                    (s.st_dev, s.st_ino) != identity):
                raise ValueError("pinned fixture root changed")

    def _scan(self, *, payload=False):
        self._root_check()
        result = {}

        def visit(p):
            s = p.lstat()
            rel = p.relative_to(self.root)
            if (s.st_dev != self.identity[0] or s.st_uid != os.getuid() or
                    any(part.lower() in {".beads", ".dolt", "dolt", "beads.db"} or
                        part.lower().endswith((".db", ".sqlite", ".sqlite3",
                                             ".db-wal", ".db-shm"))
                        for part in rel.parts)):
                raise ValueError("non-synthetic or database fixture state")
            if stat.S_ISDIR(s.st_mode):
                if stat.S_IMODE(s.st_mode) & 0o700 != 0o700:
                    raise PermissionError("fixture directory is not accessible")
                data = None
            elif stat.S_ISLNK(s.st_mode):
                data = os.readlink(p)
            elif stat.S_ISREG(s.st_mode):
                if s.st_nlink != 1:
                    raise ValueError("hardlinked mutable fixture file")
                if not s.st_mode & stat.S_IRUSR:
                    raise PermissionError("fixture file is not readable")
                fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW)
                with os.fdopen(fd, "rb") as f:
                    opened = os.fstat(f.fileno())
                    if (opened.st_dev, opened.st_ino, opened.st_nlink) != (
                            s.st_dev, s.st_ino, 1):
                        raise ValueError("fixture file changed while observing")
                    raw = f.read()
                data = raw if payload else hashlib.sha256(raw).digest()
            else:
                raise ValueError("unknown fixture file kind")
            result[rel] = Entry(s.st_mode, s.st_mtime_ns, data,
                               None if payload else (s.st_dev, s.st_ino,
                                                     s.st_nlink, s.st_ctime_ns))
            if stat.S_ISDIR(s.st_mode):
                for child in sorted(p.iterdir()):
                    visit(child)

        visit(self.root)
        return result

    def accept(self):
        """Called only after a successful case, never from a finally block."""
        if self.observed is not None:
            raise RuntimeError("case already accepted")
        self.observed = self._scan()

    def begin(self):
        """Disarm permission to restore before any new case assertions run."""
        if self.observed is not None:
            raise RuntimeError("restore or cleanup accepted case first")

    def _erase_observed(self, *, restoring=False):
        if self.observed is None:
            raise RuntimeError("failed/unasserted case: evidence retained")
        if self._scan() != self.observed:
            raise ValueError("fixture changed after case assertions")
        # All paths were positively observed inside our physical disposable
        # root. Never follow symlinks or recursively remove a directory/root.
        for rel in sorted(self.observed, key=lambda x: len(x.parts), reverse=True):
            if rel == Path("."):
                continue
            p = self.root / rel
            if stat.S_ISDIR(self.observed[rel].mode):
                if not (restoring and rel in self.pristine and
                        stat.S_ISDIR(self.pristine[rel].mode)):
                    p.rmdir()
            else:
                p.unlink()
        self.observed = None

    def restore(self):
        self._erase_observed(restoring=True)
        for rel, entry in self.pristine.items():
            p = self.root / rel
            if rel != Path("."):
                if stat.S_ISDIR(entry.mode):
                    if not p.exists():
                        p.mkdir()
                elif stat.S_ISLNK(entry.mode):
                    p.symlink_to(entry.data)
                else:
                    with p.open("xb") as f:
                        f.write(entry.data)
        # Children first: creating leaves changes parent directory mtimes.
        for rel, entry in reversed(list(self.pristine.items())):
            p = self.root / rel
            if stat.S_IMODE(p.lstat().st_mode) != stat.S_IMODE(entry.mode):
                os.chmod(p, stat.S_IMODE(entry.mode), follow_symlinks=False)
            os.utime(p, ns=(entry.mtime, entry.mtime), follow_symlinks=False)
        if self._scan(payload=True) != self.pristine:
            raise ValueError("pristine fixture restoration mismatch")

    def clean(self):
        self._erase_observed()
        # Pinned child roots have now been explicitly emptied/removed; only
        # the outer owned root must still have its original generation.
        self.root_identities = {}
        self._root_check()
        self.root.rmdir()
