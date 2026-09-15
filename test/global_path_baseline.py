"""Frozen pre-batching helpers, independent of HEAD and Git history."""
import hashlib
from pathlib import Path

COMMIT = "20b6fe8d924d50c943242dc730725e59ce1ef956"
SHA256 = "2b2d7b84a6a91bcdf36b5c0927bdc388e6e1e1aa2094757918d35e41c48b021e"
FIXTURE = Path(__file__).with_name("global-path-baseline.sh")
START, END = "global_stat() {", "global_no_repo() {"
EMISSION = "global_stat global_path_metadata global_path"


def baseline(current):
    """Replace only the path block and resolver emission list; fail closed."""
    fixture = FIXTURE.read_text()
    block = fixture[fixture.index(START):]
    if hashlib.sha256(block.encode()).hexdigest() != SHA256:
        raise ValueError(f"invalid path baseline from {COMMIT}")
    if (current.count(START) != 1 or current.count(END) != 1
            or current.count(EMISSION) != 1
            or current.index(START) >= current.index(END)):
        raise ValueError("unrecognized current path helper/emission layout")
    source = current[:current.index(START)] + block + current[current.index(END):]
    return source.replace(EMISSION, "global_stat global_path")
