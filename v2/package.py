"""Closed format-2 local package verifier. Never executes input."""
# Bundle imports are removed by build.py; source imports share these primitives.
from .safe import (META_LIMIT, PAYLOAD_LIMIT, Refusal, Watch, need, path_value, physical,
                   read, sha, snapshot, stat, text_bounds, Path, re)

ROLES = ("goal", "implementer", "orchestrator", "reviewer")
PROVIDERS = ("claude", "codex", "copilot")
LEAVES = tuple(sorted(("PACKAGE", "SHA256SUMS", "domestique2.sh", "update2.sh",
                       "bin/resolve-core") +
                      tuple("roles/" + r + ".md" for r in ROLES) +
                      tuple("adapters/" + p + ".templates" for p in PROVIDERS)))
EXECUTABLES = ("domestique2.sh", "update2.sh", "bin/resolve-core")
DIRS = ("adapters", "bin", "roles")
VERSION = r"2\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
RELEASE = r"r-[0-9a-f]{64}"


def payload_mode(leaf):
    return 0o755 if leaf in EXECUTABLES else 0o644


def package_header(version):
    need(re.fullmatch(VERSION, version) is not None, "unsupported package version")
    return ("format=2\nproduct=domestique\nmajor=2\nversion=" + version +
            "\ncore_api=1\nadapter_abi=2\nactivation_format=2\nhelper_abi=2\n"
            "launcher_abi=2\n").encode()


def inventory(root, leaves, directories):
    """Bounded exact enumeration, including empty unexpected directories."""
    expected = set(leaves) | set(directories)
    actual = set()
    parents = [root] + [root / d for d in directories]
    before = {}
    for parent in parents:
        snap = snapshot(parent)
        need(snap is not None and snap[1] is None, "missing package directory")
        before[parent] = snap
        # scandir streams; never materialize an unbounded foreign inventory.
        import os
        with os.scandir(parent) as entries:
            for entry in entries:
                rel = str(Path(entry.path).relative_to(root))
                need(rel in expected and rel not in actual, "extra/duplicate inventory")
                actual.add(rel)
    need(actual == expected, "incomplete inventory")
    need(all(snapshot(p) == s for p, s in before.items()), "changed inventory")


def verify_package(root, expected_version=None, installed=False, watch=None):
    root = physical(root)
    watch = watch if watch is not None else Watch()
    # Retained package authority must travel with these very observations, not
    # a traversal/snapshot taken after the verifier returns its in-memory data.
    for p in (root, *(root / d for d in DIRS)):
        watch.add(p)
    inventory(root, LEAVES, DIRS)
    # Check the aggregate before allocating payload snapshots.
    need(sum((root / p).lstat().st_size for p in LEAVES) <= PAYLOAD_LIMIT,
         "expanded payload cap")
    for leaf in LEAVES:
        watch.add(root / leaf)
    data = {}
    total = 0
    for leaf in LEAVES:
        data[leaf] = read(root / leaf, META_LIMIT if leaf in
                          ("PACKAGE", "SHA256SUMS") else PAYLOAD_LIMIT,
                          payload_mode(leaf) if installed else None)
        need(data[leaf] == watch.paths[root / leaf][1], "changed package read bytes")
        total += len(data[leaf])
        need(total <= PAYLOAD_LIMIT, "expanded payload cap")
    result = package_from_data(data, expected_version)
    inventory(root, LEAVES, DIRS)
    watch.check()
    return result


def package_from_data(data, expected_version=None):
    """Same closed verifier for archive bytes and physical directory snapshots."""
    need(tuple(sorted(data)) == LEAVES and
         sum(len(value) for value in data.values()) <= PAYLOAD_LIMIT, "payload inventory/cap")
    text = text_bounds(data["PACKAGE"])
    lines = text.splitlines()
    need(len(lines) == 9 and lines[3].startswith("version="), "PACKAGE fields")
    version = lines[3][8:]
    need(data["PACKAGE"] == package_header(version), "PACKAGE schema/ABI")
    need(expected_version is None or version == expected_version, "version mismatch")
    text_bounds(data["SHA256SUMS"])
    sums = b"".join((sha(data[p]) + "  " + p + "\n").encode()
                    for p in LEAVES if p != "SHA256SUMS")
    need(sums == data["SHA256SUMS"], "checksum inventory/digest mismatch")
    return {"release": "r-" + sha(sums), "version": version, "data": data,
            "source_kind": "local", "official_version": "-"}
