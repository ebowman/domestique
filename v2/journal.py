"""Read-only machine journal classification; no recovery/adoption authority."""
import os
from pathlib import Path
import re
from .safe import Refusal, need, read, sha, snapshot, stat, text_bounds
from .package import DIRS, LEAVES, RELEASE, payload_mode, verify_package
from .records import (machine, manifest_read, number, parse_record, previous_read,
                      published_header, published_read, published_prefix)


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
