"""Test-only, stdlib-only qualified native fixture selection. Never downloads."""
import hashlib
import os
from pathlib import Path
import stat

OVERRIDE = "DOMESTIQUE_TEST_BEADS_BINARY"
DEFAULT = Path("/opt/homebrew/Cellar/beads/1.1.2/bin/beads")
SHA256 = "cb77069648d90fef8876f775d647997beb7bb0ab5461509394c29d5bf14b7c42"
SCOPES = ("beads-native-context.py", "beads-production.py", "beads-cleanup.py")


class MissingDefault(FileNotFoundError):
    """Only the absent default may retain a harness's missing-tool blocker."""


def resolve(environ=None, *, default=DEFAULT):
    """Return physical path/digest; explicit invalid input always fails closed."""
    environ = os.environ if environ is None else environ
    explicit = OVERRIDE in environ
    candidate = environ[OVERRIDE] if explicit else str(default)
    if (not isinstance(candidate, str) or not candidate or
            any(ord(c) < 32 or ord(c) == 127 for c in candidate) or
            not Path(candidate).is_absolute()):
        raise ValueError(f"{OVERRIDE}: requires a nonempty absolute executable path")
    try:
        path = Path(candidate).resolve(strict=True)
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or not os.access(path, os.R_OK | os.X_OK):
            raise ValueError(f"{OVERRIDE}: not a regular readable executable: {path}")
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
    except FileNotFoundError as exc:
        if not explicit:
            raise MissingDefault(f"qualified Beads default absent: {candidate}") from exc
        raise ValueError(f"{OVERRIDE}: explicit executable missing: {candidate}") from exc
    if digest != SHA256:
        raise ValueError(f"{OVERRIDE}: SHA-256 mismatch for {path}; expected {SHA256}, got {digest}")
    return {"path": str(path), "sha256": digest}
