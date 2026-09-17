"""Bounded ordinary ownership data for cooperative local project operations."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile

from machine import identity, need, safe
from native import DEFINITIONS, LEAVES

KIND = "domestique-copilot-preview"
RECEIPT = ".domestique-private/copilot-preview.json"
PATHS = (*LEAVES.values(), RECEIPT)
PARENTS = {str(p) for leaf in PATHS for p in Path(leaf).parents if str(p) != "."}
MARKER = b"# domestique-copilot-preview "
LIMIT = 1024 * 1024
HASH = re.compile(r"[0-9a-f]{64}")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def regular(path):
    safe(path)
    info = path.lstat()
    identity(path)
    need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
         f"nonregular/hardlinked leaf: {path}")
    need(info.st_mode & 0o400, f"unreadable leaf: {path}")
    return info


def read_bytes(path, limit=LIMIT):
    info = regular(path)
    need(info.st_size <= limit, f"oversize leaf: {path}")
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    need(len(data) <= limit, f"oversize leaf: {path}")
    return data


def valid_identity(value):
    return (type(value) is list and len(value) == 2 and
            all(type(n) is int and n >= 0 for n in value))


def block(record):
    token = record["token"]
    return (f"# {KIND} BEGIN {token}\n" +
            "".join(f"/{leaf}\n" for leaf in PATHS) +
            f"# {KIND} END {token}\n").encode()


def load(path, project, installation):
    record = json.loads(read_bytes(path, 65536))
    need(type(record) is dict and record.get("kind") == KIND, "incompatible preview receipt")
    need(record.get("project") == project, "foreign/copied/moved project receipt")
    need(record.get("installation") == installation, "foreign installed native identity")
    need(record.get("native_ids") == {k: v[0] for k, v in DEFINITIONS.items()},
         "incompatible native identity")
    need(record.get("receipt_identity") == identity(path), "copied/replaced preview receipt")
    need(record.get("state") in ("partial-enable", "active", "disabled"), "invalid receipt state")
    need(type(record.get("token")) is str and
         re.fullmatch(r"[0-9a-f]{32}", record["token"]), "invalid exclusion token")
    files, directories = record.get("files"), record.get("directories")
    need(type(files) is dict and files.keys() <= set(LEAVES.values()), "invalid created paths")
    for value in files.values():
        need(type(value) is dict and "sha256" in value and valid_identity(value.get("identity")) and
             (value.get("sha256") is None or
              (type(value["sha256"]) is str and HASH.fullmatch(value["sha256"]))),
             "invalid native creation data")
    need(type(directories) is dict and directories.keys() <= PARENTS and
         all(valid_identity(v) for v in directories.values()), "invalid created directories")
    exclusion = record.get("exclusion")
    need(type(exclusion) is dict and "identity" in exclusion and
         exclusion.get("state") in ("planned", "present", "removed") and
         (exclusion.get("identity") is None or valid_identity(exclusion["identity"])) and
         type(exclusion.get("prefix_size")) is int and 0 <= exclusion["prefix_size"] <= LIMIT and
         type(exclusion.get("prefix_sha256")) is str and HASH.fullmatch(exclusion["prefix_sha256"]) and
         exclusion.get("separator") in ("", "\n") and exclusion.get("block") == block(record).decode(),
         "invalid exclusion contribution")
    need(record["state"] != "active" or
         (set(files) == set(LEAVES.values()) and
          all(v["sha256"] is not None for v in files.values()) and exclusion["state"] == "present"),
         "incomplete active receipt")
    return record


def save(path, record, fresh=False):
    """One atomic small state replacement; interruptions are not transactions."""
    if fresh:
        with path.open("xb") as stream:
            record["receipt_identity"] = identity(path)
            stream.write((json.dumps(record, indent=2) + "\n").encode())
        return
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".copilot-preview-", delete=False) as stream:
            temporary = Path(stream.name)
            record["receipt_identity"] = identity(temporary)
            stream.write((json.dumps(record, indent=2) + "\n").encode())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
