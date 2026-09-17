"""Read-only project/exclusion planner. No candidate execution or destination writes.

The returned plan retains ORIGINAL witnesses. It is not creation authority.
No sibling enumeration, .beads access, Git mutation, repair or native preimages.
"""
import os
from pathlib import Path
import re
import stat
from .safe import META_LIMIT, Watch, need, physical, read, sha, text_bounds
from .package import PROVIDERS
from .project_records import (STATE, encoded, exclusion_block, generation, native_inventory,
                              patterns, project_manifest_bytes, project_manifest_read,
                              receipt_bytes, receipt_read)
from .project_identity import project_identity, identity_guard, index_untracked, git_query
from .guard_core import core_index, helper_provenance, template_inventory
from .admission import admit

JOURNALS = ("pending", "previous", "published", "exclude-afterimage")

# Exact retained emitter/inspector inventory: domestique.sh configure_provider;
# domestique2.sh LEGACY_LAYOUTS, local_legacy_inventory and legacy_native.
# Claude guest policy is independent of CLAUDE.md. Generic Claude commands
# require the retained content anchors, not ownership inferred from their names.
POLICY_LEAVES = ("CLAUDE.md", "CLAUDE.local.md", "AGENTS.md", "AGENTS.override.md",
                 ".github/copilot-instructions.md")
LEGACY_COMMANDS = {
    ".claude/commands/decompose.md": b"Decompose the following into a beads work graph:",
    ".claude/commands/goal.md": b"Drive epic $ARGUMENTS to completion, unattended",
}


def policy_boundaries(worktree, watch):
    """Shared read-only predicate, retaining original absence/byte witnesses.

    No arbitrary policy, ancestor discovery or recursive scan. Host instructions
    may coexist; Domestique-marked/named policy and retained command bodies may
    not. Malformed/partial product markers are still evidence, not host text.
    """
    for leaf in POLICY_LEAVES:
        snap = watch.add(worktree / leaf)
        if snap is not None:
            need(snap[1] is not None and len(snap[1]) <= META_LIMIT and
                 b"domestique" not in snap[1].lower(), "legacy/unknown policy authority")
    directory = worktree / ".claude/commands"
    for name in directory_entries(directory, watch, recheck=False):
        need("domestique" not in name.lower(), "unknown Domestique command fork")
    for leaf, anchor in LEGACY_COMMANDS.items():
        snap = watch.add(worktree / leaf)
        if snap is not None:
            need(snap[1] is not None and len(snap[1]) <= META_LIMIT,
                 "legacy command type/bounds")
            need(b"domestique" not in snap[1].lower() and
                 not (anchor in snap[1] and b"bd " in snap[1]), "legacy command authority")


def no_project_pending(root, watch):
    for name in JOURNALS:
        need(watch.add(root / STATE / name) is None, "project-pending/unknown")


def directory_entries(path, watch, limit=4096, recheck=True):
    snap = watch.add(path)
    if snap is None:
        return ()
    need(snap[1] is None, "directory collision")
    result = []
    with os.scandir(path) as entries:
        for e in entries:
            need(len(result) < limit, "directory inventory bounds")
            result.append(e.name)
    # Publication boundary callbacks cannot recursively call Watch.check().
    # Revisit the SAME original directory witness after enumeration instead.
    if recheck:
        watch.check()
    else:
        watch.add(path)
    return tuple(sorted(result))


def state_read(i, root, watch):
    worktree = Path(i["worktree_root"])
    j = worktree / STATE
    no_project_pending(worktree, watch)
    parent_entries = directory_entries(j.parent, watch)
    need(set(parent_entries) <= {"v2"}, "v1/preview/unknown private authority")
    parent = watch.paths[j.parent]
    need(parent is None or stat.S_IMODE(parent[0][3]) == 0o700, "private parent mode")
    snap = watch.add(j)
    if snap is None:
        need(parent is None, "unowned private directory collision")
        return {}, {}
    need(snap[1] is None and stat.S_IMODE(snap[0][3]) == 0o700, "private state mode")
    need(set(directory_entries(j, watch)) <= {"manifest", "routing"}, "unknown private state")
    watch.add(j / "manifest")
    actual_i, actual_root, providers, exclusions = project_manifest_read(
        read(j / "manifest", mode=0o600))
    need(actual_i == i and actual_root == str(root), "foreign project/core identity")
    routing = watch.add(j / "routing")
    need(routing is not None and routing[1] is None and
         stat.S_IMODE(routing[0][3]) == 0o700, "routing directory")
    enabled = {p for p, b in providers.items() if b["status"] == "enabled"}
    need(set(directory_entries(j / "routing", watch)) ==
         {p + ".receipt" for p in enabled}, "receipt state inventory")
    for p in PROVIDERS:
        file = j / "routing" / (p + ".receipt")
        snap = watch.add(file)
        if p in enabled:
            receipt_read(read(file, mode=0o600), i, root, p, providers[p])
        else:
            need(snap is None, "disabled/absent receipt")
    return providers, exclusions


def native_boundaries(i, recorded, selected, watch):
    worktree = Path(i["worktree_root"])
    allowed = {leaf for p in recorded for leaf in native_inventory(p)}
    selected_leaves = {leaf for p in selected for leaf in native_inventory(p)}
    # Shared native containers are host-owned; exact Domestique skill directories
    # are not. Even an empty unknown skill directory cannot become our claim.
    known_dirs = {str(Path(leaf).parent) for leaf in allowed}
    known_dirs |= {str(Path(leaf).parent.parent) for leaf in allowed
                   if leaf.endswith("/agents/openai.yaml")}
    for p in PROVIDERS:
        for leaf in native_inventory(p):
            path = worktree / leaf
            snap = watch.add(path)
            need(snap is None or leaf in allowed, "equal/unowned native collision")
            if snap is not None:
                need(snap[1] is not None and stat.S_IMODE(snap[0][3]) == 0o644,
                     "native mode/type")
            if leaf in selected_leaves:
                for parent in path.parents:
                    s = watch.add(parent)
                    if s is not None:
                        need(s[1] is None, "native parent type")
                        rel = str(parent.relative_to(worktree))
                        if "/skills/domestique-" in rel:
                            need(rel in known_dirs, "unknown native directory collision")
                    if parent == worktree:
                        break
    # Exact native discovery containers only; no recursive project/sibling crawl.
    # Unknown Domestique-named forks and known old generic role leaves refuse.
    for base in (".claude", ".agents", ".codex", ".github", ".copilot"):
        need(watch.add(worktree / base / ".domestique") is None, "legacy authority")
        for category in ("skills", "agents"):
            directory = worktree / base / category
            names = directory_entries(directory, watch)
            for name in names:
                if "domestique" in name.lower() or name in (
                        "implementer.md", "reviewer.md", "implementer.toml", "reviewer.toml"):
                    rel = str((directory / name).relative_to(worktree))
                    need(rel in allowed or rel in known_dirs, "unknown Domestique fork")
    for directory in sorted(known_dirs):
        if "/skills/domestique-" in directory:
            children = directory_entries(worktree / directory, watch)
            need(all(directory + "/" + name in allowed | known_dirs for name in children),
                 "unknown owned native directory member")
    policy_boundaries(worktree, watch)
    index_untracked(i, [STATE, *sorted(selected_leaves)])
    raw = git_query(worktree, ["ls-files", "-z", "--", *(
        ":(top,literal)" + p for p in
        (".domestique-private", ".claude", ".agents", ".codex", ".github", ".copilot"))])
    need(not raw or raw.endswith(b"\0"), "authority index framing")
    for value in raw.split(b"\0")[:-1]:
        parts = value.decode("utf-8").split("/")
        need(not any("domestique" in p.lower() for p in parts) and
             parts[-1] not in ("implementer.md", "reviewer.md", "implementer.toml",
                               "reviewer.toml"), "indexed native authority")


def exclusions_plan(i, required, prior, watch):
    """Block-scoped append/transform. Other blocks are opaque, not authority.

    Overlapping other-worktree patterns are shared ambiguity and refuse. Exact
    unmanaged lines can serve multiple worktrees without claiming ownership.
    """
    worktree, common = Path(i["worktree_root"]), Path(i["git_common_dir"])
    info = common / "info"
    snap = watch.add(info)
    need(snap is not None and snap[1] is None, "missing ordinary Git info: prepublication refusal")
    exclude = info / "exclude"
    snap = watch.add(exclude)
    need(snap is None or snap[1] is not None, "exclude type")
    before = snap[1] if snap else b""
    if before:
        text_bounds(before)
    mode = stat.S_IMODE(snap[0][3]) if snap else 0o644
    need(not mode & 0o7000, "exclude mode")
    lines = before.decode().splitlines(keepends=True)
    own = sha(encoded(list(i.items())))
    managed, outside, blocks, current, start = {}, [], {}, None, 0
    for n, line in enumerate(lines):
        match = re.fullmatch(r"# (BEGIN|END) domestique-v2 ([0-9a-f]{64})\n", line)
        if match:
            action, h = match.groups()
            if action == "BEGIN":
                need(current is None and h not in blocks, "duplicate/half exclusion block")
                current, start = h, n
                managed[h] = []
            else:
                need(current == h, "half exclusion block")
                values = managed[h]
                need(values and values == sorted(set(values)) and
                     set(values) <= set(patterns(PROVIDERS)), "edited exclusion block")
                blocks[h] = (start, n + 1, "".join(lines[start:n + 1]).encode())
                current = None
        elif current is not None:
            managed[current].append(line[:-1])
        else:
            need(not ("domestique" in line.lower() and line.startswith("#")),
                 "unknown exclusion authority")
            outside.append(line)
    need(current is None, "half exclusion block")
    old_created = tuple(p for p, v in prior.items() if v[0] == "created")
    if old_created:
        expected = exclusion_block(i, old_created)
        need(own in blocks and blocks[own][2] == expected and
             all(prior[p][1] == sha(expected) for p in old_created), "stale exclusion provenance")
    else:
        need(own not in blocks, "equal/unowned exclusion block")
    for p, (origin, digest) in prior.items():
        if origin == "preexisting":
            need(outside.count(p + "\n") == 1 and digest == sha((p + "\n").encode()),
                 "changed preexisting exclusion")
    required = tuple(sorted(set(required) | set(prior)))
    for h, values in managed.items():
        if h != own:
            need(not set(values).intersection(required), "shared exclusion ambiguity")
    created, result = [], {}
    for p in required:
        need(p in patterns(PROVIDERS), "unallowlisted exclusion")
        count = outside.count(p + "\n")
        need(count <= 1 and not (count and p in old_created), "duplicate exclusion")
        if count:
            result[p] = ("preexisting", sha((p + "\n").encode()))
        else:
            created.append(p)
    block = exclusion_block(i, tuple(created)) if created else b""
    result.update({p: ("created", sha(block)) for p in created})
    result = dict(sorted(result.items()))
    if own in blocks:
        start, end, _ = blocks[own]
        after = "".join(lines[:start]).encode() + block + "".join(lines[end:]).encode()
    else:
        after = before + block
    if after:
        text_bounds(after)
    # No private afterimage can rename across a mount boundary. Use the nearest
    # existing parent without claiming a missing directory or repairing info.
    parent = worktree / STATE
    while watch.add(parent) is None:
        parent = parent.parent
    if before != after and snap is not None:
        need(watch.paths[parent][0][1] == watch.paths[info][0][1] == snap[0][1],
             "cross-filesystem exclude afterimage")
    return dict(path=exclude, before=before, after=after, mode=mode, records=result,
                action=None if before == after else "edit-exclude" if snap else "create",
                shared_effect=Path(i["git_dir"]) != common)


def ignore_preflight(i, required, watch):
    """Prove ignore precedence without any destination/scratch-file creation."""
    worktree = Path(i["worktree_root"])
    probes = []
    for pattern in required:
        rel = pattern[1:]
        if rel.endswith("/"):
            rel += "manifest"
        probes.append(rel)
        for parent in (worktree / rel).parents:
            if parent == worktree.parent:
                break
            snap = watch.add(parent / ".gitignore")
            need(snap is None or snap[1] is not None, "ignore boundary")
    # A pipe is a read-only lower-priority excludesFile, as in retained preflight.
    # Exact patterns have no wildcards; higher-priority negations must refuse.
    fd, writer = os.pipe()
    try:
        data = "".join(p + "\n" for p in required).encode()
        need(len(data) < 4096 and os.write(writer, data) == len(data), "ignore probe bounds")
        os.close(writer)
        writer = None
        raw = git_query(worktree, ["-c", f"core.excludesFile=/dev/fd/{fd}",
                                  "check-ignore", "--no-index", "-z", "--stdin"],
                        b"".join(p.encode() + b"\0" for p in probes), (fd,), (0, 1))
        need(set(raw.split(b"\0")[:-1]) == {p.encode() for p in probes} and
             raw.endswith(b"\0"), "planned exclusions ineffective")
    finally:
        os.close(fd)
        if writer is not None:
            os.close(writer)
    watch.check()


def activation_records(plan):
    """Exact prospective metadata shared by dry-run and publication, not facts."""
    providers = {p: dict(b, created=dict(b["created"]), baseline=dict(b["baseline"]))
                 for p, b in plan.providers.items()}
    for p in plan.selected:
        old = plan.providers.get(p)
        pristine = {leaf: (sha(data), "0644") for leaf, data in plan.templates[p].items()}
        block = dict(status="enabled", generation=generation(old),
                     template_release=plan.releases[p],
                     created=dict(old["created"]) if old else dict(pristine),
                     baseline=dict(old["baseline"]) if old else dict(pristine))
        for leaf in pristine:
            if plan.watch.paths[plan.worktree / leaf] is None:
                block["created"][leaf] = pristine[leaf]
        providers[p] = block
    providers = {p: providers[p] for p in PROVIDERS if p in providers}
    return (providers,
            project_manifest_bytes(plan.i, plan.root, providers, plan.exclusion["records"]),
            {p: receipt_bytes(plan.i, plan.root, p, providers[p]) for p in plan.selected})


def write_permissions(destinations, watch, observe=False):
    """Qualify actual effects, including framing and both rename/unlink parents.

    Missing directory chains use their nearest existing creation ancestor, W
    included. Higher ancestors need safe()'s read/search, not write permission
    for an effect they will not receive. Original witnesses are retained; later
    checks use only those or exact own afterimages, never resnapshot/adoption.
    Mode AND invoking-UID access checks follow safe.py's ACL-aware convention.
    Read-only guards and genuine no-ops have no destinations.
    """
    parents = set()
    for path in destinations:
        snap = watch.add(path) if observe else watch.paths[path]
        if snap is not None and snap[1] is not None:
            need(snap[0][3] & 0o200 and os.access(path, os.R_OK | os.W_OK),
                 "planned leaf not writable")
        parent = path.parent
        while True:
            snap = watch.add(parent) if observe else watch.paths[parent]
            if snap is not None:
                need(snap[1] is None, "planned parent type")
                parents.add(parent)
                break
            parent = parent.parent
    for parent in parents:
        snap = watch.paths[parent]
        need(snap[0][0] == os.getuid() and snap[0][3] & 0o700 == 0o700 and
             os.access(parent, os.R_OK | os.W_OK | os.X_OK), "planned parent not writable")


class ProjectPlan:
    """Original preflight observations; successful effects must explicitly advance."""
    def __init__(self, target, root, selected):
        need(tuple(selected) == tuple(p for p in PROVIDERS if p in selected) and selected,
             "selected provider set")
        self.i, self.watch = project_identity(target)
        self.worktree, self.root = Path(self.i["worktree_root"]), physical(root)
        self.index, self.core = core_index(self.root, self.watch)
        self.providers, old_exclusions = state_read(self.i, self.root, self.watch)
        self.selected = tuple(p for p in PROVIDERS if p in selected or
                              self.providers.get(p, {}).get("status") == "enabled")
        native_boundaries(self.i, self.providers, self.selected, self.watch)
        self.templates, self.releases = {}, {}
        # Active is selection only for FRESH provider templates, never a repeat's T.
        fresh = any(p not in self.providers for p in self.selected)
        active = None
        if fresh:
            self.watch.add(self.root / "active")
            raw = read(self.root / "active", mode=0o600)
            need(re.fullmatch(rb"release=r-[0-9a-f]{64}\n", raw), "invalid active")
            active = raw[8:-1].decode()
            need(active in self.index, "unlisted active")
        for p in self.selected:
            block = self.providers.get(p)
            generation(block)  # Includes disabled generation overflow before writes.
            t = block["template_release"] if block else active
            helper_provenance(self.root, t, self.index, self.watch)
            pristine = template_inventory(self.root, t, p, self.index, self.watch)
            self.templates[p], self.releases[p] = pristine, t
            for leaf, template in pristine.items():
                if block:
                    need(block["baseline"][leaf] == (sha(template), "0644"),
                         "pristine T baseline")
                snap = self.watch.paths[self.worktree / leaf]
                if snap is not None:
                    need(block is not None, "native creation provenance")
                    admit(p, leaf, snap[1], template)
                else:
                    need(block is None or block["status"] == "disabled", "missing enabled leaf")
        self.exclusion = exclusions_plan(self.i, patterns(self.selected), old_exclusions, self.watch)
        ignore_preflight(self.i, tuple(self.exclusion["records"]), self.watch)
        self.next_providers, self.manifest, self.receipts = activation_records(self)
        metadata = {self.worktree / STATE / "manifest": self.manifest,
                    **{self.worktree / STATE / "routing" / (p + ".receipt"): data
                       for p, data in self.receipts.items()}}
        writes = [self.worktree / leaf for p in self.selected for leaf in self.templates[p]
                  if self.watch.paths[self.worktree / leaf] is None]
        for path, data in metadata.items():
            snap = self.watch.add(path)
            if snap is None or snap[1] != data:
                writes.append(path)
        if self.exclusion["action"]:
            writes.append(self.exclusion["path"])
        if writes:
            writes += [self.worktree / STATE / name for name in JOURNALS[:3]]
            if self.exclusion["action"] == "edit-exclude":
                writes.append(self.worktree / STATE / "exclude-afterimage")
        self.write_paths = tuple(writes)
        write_permissions(self.write_paths, self.watch, observe=True)
        self.check()

    def check(self):
        no_project_pending(self.worktree, self.watch)
        identity_guard(self.i, self.watch)
        index_untracked(self.i, [STATE, *(leaf for p in self.selected for leaf in native_inventory(p))])
        self.watch.check()
        write_permissions(self.write_paths, self.watch)


def project_preflight(target, root, providers=("claude",)):
    """Internal read-only API. Public enable remains explicitly unavailable."""
    return ProjectPlan(target, root, providers)
