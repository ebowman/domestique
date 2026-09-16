"""Retained format-1 engine fixtures, NOT public V2 installation coverage.

The one reviewed payload remains in each explicit source artifact. Only tests
extract it into their own disposable roots; no production bypass exists.
Historical Git-object fixtures and their inventories are unrelated and intact.
"""
import hashlib
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
MARKER = b"# BEGIN RETAINED PREVIEW SOURCE\n"


def source(name="domestique2.sh"):
    if name not in ("domestique2.sh", "update2.sh"):
        raise ValueError("unknown retained preview artifact")
    raw = (ROOT / name).read_bytes()
    if raw.count(MARKER) != 1:
        raise ValueError("ambiguous retained preview boundary")
    body = raw.split(MARKER, 1)[1]
    if not body.startswith(b"#!/usr/bin/env bash\n"):
        raise ValueError("invalid retained preview source")
    return body


def sha256(name="domestique2.sh"):
    return hashlib.sha256(source(name)).hexdigest()


def materialize(directory, name="domestique2.sh"):
    directory = Path(directory)
    if (not directory.is_dir() or directory.is_symlink() or
            directory.stat().st_uid != os.getuid()):
        raise ValueError("owned fixture directory required")
    path = directory / ("retained-" + name)
    with path.open("xb") as output:
        output.write(source(name))
    return path


if __name__ == "__main__":
    # Shell harnesses already own and clean this root. Never install here.
    print(materialize(sys.argv[1], sys.argv[2]))
