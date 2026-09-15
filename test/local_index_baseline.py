"""Immutable index-only oracle; leaves reviewed path/signal helpers untouched."""
import hashlib
from pathlib import Path

COMMIT = "20b6fe8d924d50c943242dc730725e59ce1ef956"
SHA256 = "930fd3fa19b40b82d874b0d6c38568516dba084df4bca369f6aa1172cb3a9493"
FIXTURE = Path(__file__).with_name("local-index-baseline.sh")
START, END = "local_untracked() (", "local_core() {"


def baseline(current):
    fixture = FIXTURE.read_text()
    block = fixture[fixture.index(START):]
    if hashlib.sha256(block.encode()).hexdigest() != SHA256:
        raise ValueError(f"invalid index baseline from {COMMIT}")
    if (current.count(START) != 1 or current.count(END) != 1
            or current.index(START) >= current.index(END)):
        raise ValueError("unrecognized current index helper layout")
    return current[:current.index(START)] + block + current[current.index(END):]
