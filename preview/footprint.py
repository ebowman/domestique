"""Bounded read-only observations, not native admission or workflow readiness."""
import json
import os
from pathlib import Path
import stat

from machine import Refusal, git, identity, need, resolve_source, safe
from native import LEAVES, ROLES
from model_setup import confirmed, parse
from project import (COMMAND_ANCHORS, LEGACY_STATE, POLICIES, exclusion_remainder,
                     installation_identity, project_identity, tracked_paths)
from project_data import (LIMIT, MARKER, RECEIPT, inventory, load, owned_identity,
                          read_bytes, regular, sha)


def display(path):
    # Same small convention as the retained inspector: paths, never native bytes.
    return json.dumps(os.fspath(path), ensure_ascii=True)


def probe(path):
    safe(path)
    try:
        return path.lstat()
    except FileNotFoundError:
        return None


def target_identity(target):
    root = Path(os.getcwd()) if target is None else Path(target)
    if not root.is_absolute():
        root = Path(os.getcwd()) / root
    try:
        info = probe(root)
    except Refusal:
        # Do not echo arbitrary paths or Git diagnostic/config contents.
        raise Refusal("target unsafe (symlinks or unsafe ancestors refused)") from None
    need(info is not None, "target unavailable")
    need(stat.S_ISDIR(info.st_mode), "target is not a directory")
    need(info.st_mode & 0o400 and info.st_mode & 0o100 and
         os.access(root, os.R_OK | os.X_OK), "target unreadable")
    try:
        return project_identity(target)
    except Refusal as exc:
        if str(exc) == "target must be the exact physical Git worktree root, not a subdirectory":
            raise Refusal("target is a subdirectory, not the exact physical Git worktree root") from None
        raise Refusal("target must be the exact physical Git worktree root; "
                      "non-Git, subdirectory, bare or unsafe targets refuse") from None


def created_status(root, leaf, created, tracked):
    info = probe(root / leaf)
    if leaf in tracked:
        return "unknown (tracked/index-only path)"
    if info is None:
        if not created and leaf.endswith("/SKILL.md") and probe((root / leaf).parent) is not None:
            return "unknown (unowned skill directory; file absent)"
        return "missing" if created else "absent (not owned)"
    regular(root / leaf)
    if created is None:
        return "unknown (unowned file)"
    if not owned_identity(root / leaf, created):
        return "customized/replaced"
    if created["sha256"] is None:
        return "unknown (incomplete creation hash)"
    if info.st_size > LIMIT:
        return "customized/oversize"
    return ("unchanged" if identity(root / leaf) == created["identity"] and
            sha(read_bytes(root / leaf)) == created["sha256"] else "customized")


def legacy_evidence(root):
    """Only existing lifecycle anchors and provider containers; no metadata parser."""
    rows = []
    for name in dict.fromkeys((*LEGACY_STATE, *POLICIES, *COMMAND_ANCHORS)):
        try:
            if probe(root / name) is None:
                continue
            if name in POLICIES or name in COMMAND_ANCHORS:
                data = read_bytes(root / name)
                if (b"domestique" not in data.lower() and
                        not (name in COMMAND_ANCHORS and
                             COMMAND_ANCHORS[name] in data and b"bd " in data)):
                    continue
                evidence = "Domestique reference; installation/generation unknown"
            else:
                evidence = "legacy/experimental named footprint; generation unknown"
            tracked = git(root, "ls-files", "--cached", "-z", "--",
                          ":(top,literal)" + name)
            mode = "tracked evidence" if tracked else "unknown (untracked is not proof of guest)"
            rows.append(f"  {display(name)}: {evidence}; mode: {mode}")
        except (Refusal, OSError, ValueError):
            rows.append(f"  {display(name)}: unknown (unsafe/unreadable evidence); mode: unknown")
    for name in (".claude", ".codex", ".github", ".copilot", ".agents"):
        try:
            if probe(root / name) is not None:
                rows.append(f"  {display(name)}: provider container only; "
                            "other Domestique installation/mode unknown")
        except (Refusal, OSError, ValueError):
            rows.append(f"  {display(name)}: unknown (unsafe/unreadable container)")
    return rows


def report(target, machine_root, machine_receipt):
    source = resolve_source(machine_root)
    rows = [f"Machine installation: {display(machine_root)}",
            f"Selected shared revision (current): {source.name}",
            "Source checkout alone is not an installed machine or project activation."]
    try:
        root, project = target_identity(target)
    except Refusal as exc:
        return 1, "\n".join([*rows, f"Target: refused; {exc}",
                            "Activation/discovery: unknown; workflow readiness: NOT CHECKED"])
    except (OSError, ValueError):
        return 1, "\n".join([*rows, "Target: refused (unavailable/unreadable)",
                            "Activation/discovery: unknown; workflow readiness: NOT CHECKED"])
    rows.append(f"Target: {display(root)} (exact physical Git worktree root)")
    record, partial = None, False
    try:
        tracked = tracked_paths(root)
        need(RECEIPT not in tracked, "tracked receipt")
        if probe(root / RECEIPT) is not None:
            record = load(root / RECEIPT, project,
                          installation_identity(machine_root, machine_receipt))
        receipt_status = record["state"] if record else "absent"
    except (Refusal, OSError, ValueError):
        tracked = set()
        partial = True
        receipt_status = "unknown (unreadable, corrupt, incompatible or foreign receipt/index)"
    rows.append(f"Receipt {display(RECEIPT)}: {receipt_status}")
    if record and "inventory" not in record:
        rows.append("Native inventory: legacy five-definition layout; short names not installed "
                    "by this activation; "
                    "review customizations before disable/re-enable.")
    for leaf in (inventory(record) if record else LEAVES).values():
        try:
            status = created_status(root, leaf, record["files"].get(leaf) if record else None, tracked)
        except (Refusal, OSError, ValueError):
            status = "unknown (unsafe/unreadable file)"
        partial |= status.startswith(("unknown", "missing"))
        rows.append(f"  {display(leaf)}: {status}")
    confirmation = "unconfirmed"
    if record and record["state"] == "active":
        try:
            roles = {}
            for role in ROLES:
                data = read_bytes(root / LEAVES[role])
                roles[role] = (data, None, None, parse(data, role))
            if confirmed(root, record, roles):
                confirmation = "confirmed file pair/receipt (not native evidence)"
        except (Refusal, OSError, ValueError):
            confirmation = "unconfirmed (unsafe/invalid/partial role data)"
    rows.append("Role model setup: " + confirmation + "; separate from customization versus creation.")
    try:
        path = Path(project["common_dir"]) / "info/exclude"
        data = read_bytes(path) if probe(path) is not None else b""
        if record:
            exclusion_remainder(path, data, record)
            exclusion = record["exclusion"]["state"] + " (verified contribution only)"
        else:
            need(MARKER not in data, "preview exclusion without valid receipt")
            exclusion = "no preview marker observed"
    except (Refusal, OSError, ValueError):
        partial = True
        exclusion = "unknown (missing/changed/unsafe contribution or no valid receipt)"
    rows.append("Git-common exclusion: " + exclusion)
    partial |= bool(record and record["state"] != "active")
    activation = ("partial/unknown" if partial else
                  "active (receipt and owned footprint)" if record else "absent")
    rows.append("Preview activation: " + activation)
    evidence = legacy_evidence(root)
    rows.append("Selected-target legacy evidence (not a machine scan):")
    rows.extend(evidence or ["  No known markers observed; other legacy presence/mode unknown."])
    rows.extend([
        "Project discovery: filesystem evidence only; effective client loading NOT CHECKED.",
        "Workflow readiness: NOT CHECKED; Beads/native/model/MCP never invoked.",
        "Creation hashes, not current templates; model confirmation is not native capability/permission proof.",
        "No ancestor/global inventory, legacy baseline or guest-mode inference.",
    ])
    return int(partial), "\n".join(rows)
