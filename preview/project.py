"""Exact-root Copilot definition lifecycle; trusted cooperative single writer.

No sibling registry, native execution, Beads access, or historical v2 imports.
"""
import os
from pathlib import Path
import uuid

from machine import Refusal, git, identity, make_parents, need, safe, writable_directory
from native import DEFINITIONS, LEAVES, templates
from project_data import (KIND, LIMIT, MARKER, PATHS, RECEIPT, block, inventory, load,
                          owned_identity, read_bytes, regular, removable, save, sha)

LEGACY_STATE = (
    ".domestique-private/v2", ".domestique-private/manifest",
    ".domestique-private/pending", ".domestique-private/previous",
    ".domestique-private/published", ".domestique-private/routing",
    ".domestique-private/beads-context", ".domestique-private/beads-attempt",
    ".domestique-private/exports", ".domestique-private/exclude-afterimage",
    *(f"{base}/.domestique" for base in (".claude", ".codex", ".github", ".copilot", ".agents")),
    *(f".github/skills/domestique{suffix}" for suffix in ("", "-decompose", "-goal")),
    *(f".github/agents/domestique-{role}.agent.md" for role in ("implementer", "reviewer")),
)
POLICIES = ("CLAUDE.md", "CLAUDE.local.md", "AGENTS.md", "AGENTS.override.md",
            ".github/copilot-instructions.md")
COMMAND_ANCHORS = {
    ".claude/commands/decompose.md": b"Decompose the following into a beads work graph:",
    ".claude/commands/goal.md": b"Drive epic $ARGUMENTS to completion, unattended",
    ".claude/commands/dom-decompose.md": b"Decompose the following into a beads work graph:",
    ".claude/commands/dom-goal.md": b"Drive epic $ARGUMENTS to completion, unattended",
}


def arguments(args):
    """Only [TARGET] [--dry-run], with the optional flag last."""
    dry_run = bool(args and args[-1] == "--dry-run")
    values = args[:-1] if dry_run else args
    if len(values) > 1 or any(not v or v.startswith("-") for v in values):
        raise ValueError("expected [TARGET] [--dry-run]; no other project options")
    return (values[0] if values else None), dry_run


def project_identity(target):
    root = Path(os.getcwd()) if target is None else Path(target)
    if not root.is_absolute():
        root = Path(os.getcwd()) / root
    safe(root)
    need(root.is_dir() and root.resolve() == root, "target must be an exact physical directory")
    # PWD can describe a shell directory alias, but is often stale in subprocesses.
    pwd = Path(os.environ.get("PWD", "/"))
    if target is None and pwd.is_absolute() and pwd.resolve() == root:
        need(pwd == root, "symlink cwd is not an exact physical target")
    need(git(root, "rev-parse", "--is-bare-repository").strip() == b"false" and
         git(root, "rev-parse", "--is-inside-work-tree").strip() == b"true", "non-worktree/bare target")
    top = Path(os.fsdecode(git(root, "rev-parse", "--show-toplevel")).removesuffix("\n"))
    need(top == root, "target must be the exact physical Git worktree root, not a subdirectory")
    marker = root / ".git"
    safe(marker)
    if marker.is_file():
        regular(marker)
    git_dir = Path(os.fsdecode(git(root, "rev-parse", "--absolute-git-dir")).removesuffix("\n"))
    common = Path(os.fsdecode(git(root, "rev-parse", "--git-common-dir")).removesuffix("\n"))
    if not common.is_absolute():
        common = root / common
    # Resolve independently; normal Git ../ components are not user target aliases.
    git_dir, common = Path(os.path.abspath(git_dir)), Path(os.path.abspath(common))
    for directory in (git_dir, common):
        safe(directory)
        need(directory.is_dir(), f"missing Git directory: {directory}")
    return root, {
        "root": str(root), "root_identity": identity(root),
        "git_dir": str(git_dir), "git_identity": identity(git_dir),
        "common_dir": str(common), "common_identity": identity(common),
    }


def installation_identity(machine_root, receipt):
    return {"root": str(machine_root), "root_identity": identity(machine_root),
            "launcher": receipt["launcher"], "launcher_identity": receipt["launcher_identity"],
            "launcher_sha256": receipt["launcher_sha256"]}


def tracked_paths(root):
    parents = {str(p) for leaf in PATHS for p in Path(leaf).parents if str(p) != "."}
    raw = git(root, "ls-files", "--cached", "-z", "--",
              *(":(top,literal)" + p for p in sorted(set(PATHS) | parents)))
    tracked = {os.fsdecode(p) for p in raw.split(b"\0") if p}
    return {leaf for leaf in PATHS if any(
        name == leaf or name.startswith(leaf + "/") or name in
        {str(p) for p in Path(leaf).parents} for name in tracked)}


def legacy(root):
    for name in LEGACY_STATE:
        path = root / name
        safe(path.parent)
        need(not os.path.lexists(path), f"legacy/experimental authority collision: {name}")
    for name in (*POLICIES, *COMMAND_ANCHORS):
        path = root / name
        safe(path.parent)
        if os.path.lexists(path):
            data = read_bytes(path)
            need(b"domestique" not in data.lower() and
                 not (name in COMMAND_ANCHORS and COMMAND_ANCHORS[name] in data and b"bd " in data),
                 f"legacy/unknown Domestique policy authority: {name}")


def exclusion_path(project):
    # Common info must already exist; never repair Git administration.
    directory = Path(project["common_dir"]) / "info"
    need(directory.is_dir(), "missing ordinary Git-common info directory; no repair")
    writable_directory(directory)
    path = directory / "exclude"
    safe(path)
    if os.path.lexists(path):
        info = regular(path)
        need(info.st_mode & 0o200 and os.access(path, os.W_OK), "exclude is not writable")
        return path, read_bytes(path)
    return path, b""


def exclusion_remainder(path, data, record):
    item = record["exclusion"]
    if item["state"] == "removed":
        need(MARKER not in data, "foreign/shared exclusion contribution")
        return data
    if item["state"] == "planned":
        need(len(data) == item["prefix_size"] and sha(data) == item["prefix_sha256"],
             "incomplete exclusion write; retain ambiguous contribution")
        return data
    need(os.path.lexists(path) and identity(path) == item["identity"],
         "replaced/missing exclusion file")
    contribution = item["separator"].encode() + block(record)
    offset = item["prefix_size"]
    need(data.count(MARKER) == 2 and data[offset:offset + len(contribution)] == contribution and
         sha(data[:offset]) == item["prefix_sha256"],
         "edited/duplicate/foreign/shared exclusion contribution")
    return data[:offset] + data[offset + len(contribution):]


def leaf_status(root, leaf, created, tracked):
    path = root / leaf
    need(leaf not in tracked, f"tracked/index-only path: {leaf}")
    safe(path)
    writable_directory(path.parent)
    if not os.path.lexists(path):
        return "missing"
    regular(path)
    need(created is not None, f"unowned collision (even identical): {leaf}")
    if not owned_identity(path, created):
        return "customized/replaced"
    if created["sha256"] is None or path.stat().st_size > LIMIT:
        return "customized/incomplete"
    return ("unchanged" if identity(path) == created["identity"] and
            sha(read_bytes(path)) == created["sha256"] else "customized")


def operate(command, target, dry_run, machine_root, machine_receipt):
    root, project = project_identity(target)
    need(machine_root != root and machine_root not in root.parents,
         "cannot activate the managed machine source")
    installation = installation_identity(machine_root, machine_receipt)
    receipt_path = root / RECEIPT
    tracked = tracked_paths(root)
    need(RECEIPT not in tracked, "tracked/index-only preview receipt or parent")
    safe(receipt_path)
    writable_directory(receipt_path.parent)
    record = load(receipt_path, project, installation) if os.path.lexists(receipt_path) else None
    if command == "enable":
        legacy(root)
        return enable(root, project, installation, record, tracked, dry_run)
    return disable(root, project, record, tracked, dry_run)


def enable(root, project, installation, record, tracked, dry_run):
    path, data = exclusion_path(project)
    if record:
        need(record["state"] == "active", "partial/revoked preview; finish disable before enabling")
        exclusion_remainder(path, data, record)
        statuses = {leaf: leaf_status(root, leaf, record["files"][leaf], tracked)
                    for leaf in inventory(record).values()}
        need("missing" not in statuses.values(), "missing owned definition; no repair, use disable")
        customized = [leaf for leaf, status in statuses.items() if status != "unchanged"]
        return 0, ("dry-run: " if dry_run else "") + (
            "definitions unchanged" if not customized else
            "definitions customized (preserved, not approved): " + ", ".join(customized)
        ) + ("; legacy five-definition layout; disable/re-enable after customization review "
             "to add /dom-decompose and /dom-goal" if "inventory" not in record else ""
        ) + "; workflows NOT READY"
    need(MARKER not in data, "foreign/shared preview exclusion; no sibling activation or adoption")
    for leaf in LEAVES.values():
        need(leaf_status(root, leaf, None, tracked) == "missing", f"unowned collision: {leaf}")
        if leaf.endswith("/SKILL.md"):
            need(not os.path.lexists((root / leaf).parent),
                 f"unowned native skill directory: {Path(leaf).parent}")
    need(len(data) + 2048 <= LIMIT, "exclude too large for bounded contribution")
    if dry_run:
        return 0, "dry-run: would install seven Copilot definitions and receipt; workflows NOT READY"
    record = {
        "kind": KIND, "state": "partial-enable", "project": project, "inventory": "public-names",
        "installation": installation, "native_ids": {k: v[0] for k, v in DEFINITIONS.items()},
        "token": uuid.uuid4().hex, "files": {}, "directories": {},
        "exclusion": {"state": "planned", "identity": identity(path) if path.exists() else None,
                      "prefix_size": len(data), "prefix_sha256": sha(data),
                      "separator": "\n" if data and not data.endswith(b"\n") else ""},
    }
    record["exclusion"]["block"] = block(record).decode()
    receipt_path = root / RECEIPT
    directories = []
    make_parents(receipt_path.parent, directories)
    record["directories"].update({str(p.relative_to(root)): identity(p) for p in directories})
    save(receipt_path, record, fresh=True)
    try:
        for leaf, content in templates(installation["launcher"], root).items():
            directories = []
            make_parents((root / leaf).parent, directories)
            record["directories"].update({str(p.relative_to(root)): identity(p) for p in directories})
            # Exclusive create; an ordinary incomplete write is recorded, not reset.
            with (root / leaf).open("xb") as stream:
                record["files"][leaf] = {"identity": identity(root / leaf), "sha256": None}
                stream.write(content)
            record["files"][leaf]["sha256"] = sha(content)
            save(receipt_path, record)
        with path.open("ab" if path.exists() else "xb") as stream:
            stream.write(record["exclusion"]["separator"].encode() + block(record))
        record["exclusion"].update(state="present", identity=identity(path))
        record["state"] = "active"
        save(receipt_path, record)
    except (OSError, Refusal) as exc:
        record["state"] = "partial-enable"
        try:
            save(receipt_path, record)
        except OSError:
            pass  # Last durable partial receipt remains; unknown assets are never adopted.
        return 1, f"PARTIAL definition installation: {exc}; use disable; workflows NOT READY"
    return 0, "installed seven Copilot definitions (not operational workflow readiness); workflows NOT READY"


def disable(root, project, record, tracked, dry_run):
    reasons, eligible = [], []
    # Preflight every leaf and exclusion before revoking or deleting anything.
    for leaf in (inventory(record) if record else LEAVES).values():
        try:
            status = leaf_status(root, leaf, record["files"].get(leaf) if record else None, tracked)
            if status == "unchanged" or (status == "customized" and
                                        removable(root / leaf, record["files"][leaf])):
                eligible.append(root / leaf)
            elif status != "missing":
                reasons.append(f"{leaf}: {status}; retained")
        except (Refusal, OSError) as exc:
            reasons.append(str(exc))
    path = remainder = None
    try:
        path, data = exclusion_path(project)
        if record:
            remainder = exclusion_remainder(path, data, record)
        else:
            need(MARKER not in data, "foreign/shared exclusion without this worktree's receipt")
    except (Refusal, OSError) as exc:
        reasons.append(str(exc))
    if dry_run or record is None:
        prefix = "dry-run: " if dry_run else ""
        return (1, prefix + "PARTIAL/refused: " + "; ".join(reasons)) if reasons else (
            0, prefix + ("would revoke and remove unchanged definitions" if record else "already disabled"))
    # Future workflow guards MUST require state == active. Revocation is first.
    record["state"] = "disabled"
    save(root / RECEIPT, record)
    for leaf in eligible:
        try:
            leaf.unlink()
        except OSError as exc:
            reasons.append(f"{leaf}: {exc}")
    if remainder is not None:
        try:
            if remainder != data:
                # In-place edit preserves host mode/inode and all unowned bytes.
                with path.open("r+b") as stream:
                    stream.write(remainder)
                    stream.truncate()
            record["exclusion"]["state"] = "removed"
        except OSError as exc:
            reasons.append(f"exclusion removal incomplete: {exc}")
    save(root / RECEIPT, record)
    if reasons:
        return 1, "PARTIAL disabled (receipt revoked): " + "; ".join(reasons)
    (root / RECEIPT).unlink()
    for name, original in sorted(record["directories"].items(),
                                 key=lambda pair: len(Path(pair[0]).parts), reverse=True):
        directory = root / name
        try:
            safe(directory)
            if identity(directory) == original:
                directory.rmdir()  # Never remove unrelated contents or foreign directories.
        except (OSError, Refusal):
            pass
    return 0, "disabled; unchanged owned definitions and receipt removed"
