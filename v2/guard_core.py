"""Body-free machine provenance for project guards; never reads active implicitly."""
from pathlib import Path
import json
import stat
from .safe import META_LIMIT, PAYLOAD_LIMIT, need, physical, read, sha, snapshot
from .records import machine, parse_record
from .dispatcher import management_index
from .package import DIRS, LEAVES, RELEASE, inventory, payload_mode, re
from .build import launcher_bytes
from .project_records import native_inventory


def core_index(root, watch):
    root = physical(root)
    for p in (root, root / "state", root / "releases"):
        snap = watch.add(p)
        need(snap is not None and snap[1] is None and
             stat.S_IMODE(snap[0][3]) == 0o700, "core directory")
    path = root / "state/runtime-manifest"
    watch.add(path)
    raw = read(path, mode=0o600)
    rows = parse_record(raw)
    need(len(rows) >= 12 and rows[6][0] == "launcher_path", "machine manifest framing")
    launcher = physical(rows[6][1])
    need(launcher.parts[-3:] == (".local", "bin", "domestique2"), "launcher identity")
    home = launcher.parent.parent.parent
    expected = launcher_bytes(root, home)
    watch.add(launcher)
    need(read(launcher, mode=0o755) == expected, "launcher provenance")
    index = management_index(raw, machine(root, launcher), expected)
    watch.check()
    return index, (root.stat().st_dev, root.stat().st_ino)


def core_leaf(root, release, leaf, index, watch):
    need(re.fullmatch(RELEASE, release) and release in index and leaf in LEAVES,
         "unlisted release/leaf")
    need(not leaf.startswith("roles/"), "body requires scoped guard")
    directory = root / "releases" / release
    for p in (directory, directory / Path(leaf).parent):
        snap = watch.add(p)
        need(snap is not None and snap[1] is None and
             stat.S_IMODE(snap[0][3]) == 0o700, "release directory")
    path = directory / leaf
    watch.add(path)
    data = read(path, META_LIMIT if leaf in ("PACKAGE", "SHA256SUMS") else PAYLOAD_LIMIT,
                payload_mode(leaf))
    need(sha(data) == index[release]["hashes"][leaf], "immutable payload provenance")
    return data


def helper_provenance(root, release, index, watch):
    """Future loader MUST call before executing the candidate/helper afterimage."""
    for leaf in ("PACKAGE", "SHA256SUMS", "bin/resolve-core"):
        data = core_leaf(root, release, leaf, index, watch)
    watch.check()
    return root / "releases" / release / "bin/resolve-core", data


def template_inventory(root, release, provider, index, watch):
    data = core_leaf(root, release, "adapters/" + provider + ".templates", index, watch)
    def unique(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, "template duplicate")
            result[key] = value
        return result
    values = json.loads(data, object_pairs_hook=unique)
    need(type(values) is dict and tuple(values) == native_inventory(provider) and
         all(type(v) is str for v in values.values()), "template closed inventory")
    need((json.dumps(values, sort_keys=True, ensure_ascii=True, separators=(",", ":")) +
          "\n").encode() == data, "template serialization")
    return {k: v.encode() for k, v in values.items()}


def guarded_body_read(root, release, leaf, index, watch, before_body, original=None):
    """Body snapshots NEVER enter a general Watch that could reopen them unguarded."""
    need(leaf in LEAVES and leaf.startswith("roles/") and release in index, "body inventory")
    directory = root / "releases" / release
    for p in (directory, directory / "roles"):
        s = watch.add(p)
        need(s is not None and s[1] is None and stat.S_IMODE(s[0][3]) == 0o700,
             "body directory")
    before_body()
    snap = snapshot(directory / leaf, PAYLOAD_LIMIT)
    need(snap is not None and snap[1] is not None and
         stat.S_IMODE(snap[0][3]) == 0o644 and
         sha(snap[1]) == index[release]["hashes"][leaf] and
         (original is None or original == snap), "body provenance/witness")
    return snap


def release_validate(root, release, index, watch, before_body):
    """Only after activation. Invoke the scoped guard before EACH shared body open."""
    directory = root / "releases" / release
    inventory(directory, LEAVES, DIRS)
    bodies = {}
    for leaf in LEAVES:
        if leaf.startswith("roles/"):
            bodies[leaf] = guarded_body_read(root, release, leaf, index, watch, before_body)
        else:
            core_leaf(root, release, leaf, index, watch)
    watch.check()
    return bodies
