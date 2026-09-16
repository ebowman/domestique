"""Fixed management dispatch protocol, not workflow policy or a resolver.

This supersedes, but NEVER migrates/adopts, the help-only development prototype.
Compatible package changes must not change this bundle's bytes.
"""
import os
import subprocess
import sys
from .safe import (META_LIMIT, PAYLOAD_LIMIT, Refusal, Watch, need, physical, read,
                   sha, snapshot, stat, Path, re)
from .package import LEAVES, VERSION, RELEASE, package_header, payload_mode
from .records import machine, pair, parse_record
from .cli import Misuse, parse_cli, usage


def management_index(raw, m, dispatcher):
    """Strict B index without opening workflow bodies, helpers or native data.

    Creation/baseline pairs authenticate the selected management bytes against
    local provenance. Closed sums reproduce each R; hashes are not signatures.
    Full payload validation remains the publisher's separate runtime_read.
    """
    rows = parse_record(raw)
    prefix = [("format", "2"), ("scope", "runtime"), *m, ("core_api", "1"),
              ("adapter_abi", "2"), ("activation_format", "2"), ("helper_abi", "2")]
    prefix += pair(dict(m)["launcher_path"], dispatcher, 0o755)
    need(rows[:len(prefix)] == prefix, "runtime identity/launcher provenance")
    rows = rows[len(prefix):]
    releases, versions = {}, set()
    while rows:
        need(len(releases) < 1024 and len(rows) >= 29, "release block bounds")
        (rk, r), (vk, v), (sk, source), (ok, official) = rows[:4]
        need(rk == "release" and re.fullmatch(RELEASE, r) and r not in releases and
             (not releases or r > next(reversed(releases))) and vk == "version" and
             re.fullmatch(VERSION, v) and sk == "source_kind" and
             source in ("local", "official") and ok == "official_version" and
             official == ("-" if source == "local" else v), "release metadata")
        if source == "official":
            need(v not in versions, "duplicate official mapping")
            versions.add(v)
        hashes = {}
        for n, leaf in enumerate(LEAVES):
            created, baseline = rows[4 + 2*n:6 + 2*n]
            stem = f"releases/{r}/{leaf}:"
            value = created[1]
            need(created[0] == "created" and baseline == ("baseline", value) and
                 value.startswith(stem), "creation/baseline inventory")
            digest, sep, mode = value[len(stem):].partition(":")
            need(re.fullmatch(r"[0-9a-f]{64}", digest) and sep and
                 mode == f"{payload_mode(leaf):04o}", "creation digest/mode")
            hashes[leaf] = digest
        end = 4 + 2*len(LEAVES)
        need(rows[end] == ("end_release", r), "release end")
        sums = b"".join((hashes[p] + "  " + p + "\n").encode()
                        for p in LEAVES if p != "SHA256SUMS")
        need(r == "r-" + sha(sums) and hashes["SHA256SUMS"] == sha(sums) and
             hashes["PACKAGE"] == sha(package_header(v)), "release identity/sums")
        releases[r] = dict(version=v, hashes=hashes, sums=sums)
        rows = rows[end + 1:]
    need(releases, "empty manifest")
    return releases


def management_read(root, launcher):
    watch = Watch()
    for p in (root, root / "state", root / "releases"):
        watch.add(p)
        snap = snapshot(p)
        need(snap is not None and snap[1] is None and
             stat.S_IMODE(snap[0][3]) == 0o700, "unsafe runtime directory")
    # Register BEFORE validation; a later observation is never a new baseline.
    watch.add(launcher)
    dispatcher = read(launcher, mode=0o755)
    manifest = root / "state/runtime-manifest"
    watch.add(manifest)
    releases = management_index(read(manifest, mode=0o600), machine(root, launcher), dispatcher)
    watch.add(root / "active")
    active = read(root / "active", mode=0o600)
    need(re.fullmatch(rb"release=r-[0-9a-f]{64}\n", active), "invalid active")
    selected = active.decode()[8:-1]
    need(selected in releases, "unlisted active")
    package = releases[selected]
    release = root / "releases" / selected
    watch.add(release)
    snap = snapshot(release)
    need(snap is not None and snap[1] is None and
         stat.S_IMODE(snap[0][3]) == 0o700, "unsafe release directory")
    data = {}
    for leaf in ("PACKAGE", "SHA256SUMS", "domestique2.sh"):
        p = release / leaf
        watch.add(p)
        data[leaf] = read(p, PAYLOAD_LIMIT if leaf.endswith(".sh") else META_LIMIT,
                          payload_mode(leaf))
        need(sha(data[leaf]) == package["hashes"][leaf], "edited management payload")
    # Management does not open workflow payloads even to classify a journal.
    # Any machine/retirement journal therefore conservatively means unknown.
    recovery = "none"
    for directory in (root / "state", root / "state/retire-global"):
        for name in ("pending", "previous", "published"):
            p = directory / name
            watch.add(p)
            if watch.paths[p] is not None:
                recovery = "unknown"
    watch.check()
    return selected, package["version"], recovery, data["domestique2.sh"], watch


def dispatch_main(root, home):
    try:
        parsed = parse_cli(sys.argv[1:])
        command = parsed["command"]
        if command == "help":
            print(usage(parsed["topic"]))
            return 0
        home, root = physical(home), physical(root)
        need(os.environ.get("HOME") == str(home), "conflicting HOME")
        override, xdg = os.environ.get("DOMESTIQUE_HOME"), os.environ.get("XDG_STATE_HOME")
        if xdg:
            physical(xdg)
        if override:
            need(physical(override) / "v2" == root, "conflicting runtime override")
        elif xdg:
            need(physical(xdg) / "domestique/v2" == root, "conflicting state override")
        if command in ("update", "enable", "disable", "retire-global"):
            if command == "update" and os.environ.get("DOMESTIQUE_UPDATE_SOURCE"):
                raise Misuse("DOMESTIQUE_UPDATE_SOURCE refused; use explicit selectors")
            print("domestique2: " + command + " UNIMPLEMENTED; no fallback", file=sys.stderr)
            return 1
        selected, version, recovery, payload, watch = management_read(
            root, home / ".local/bin/domestique2")
        watch.check()
        if command == "bare":
            print(usage())
        print("runtime=" + selected + " version=" + version +
              " contract=V2/1 launcher_abi=2 management=verified workflow=not-assessed "
              "recovery=" + recovery, flush=True)
        if command == "version":
            return 0 if recovery == "none" else 1
        print("activation=not-assessed (inventory unimplemented); native-evidence=BLOCKED",
              flush=True)
        watch.check()
        # Execute only the immutable VERIFIED in-memory afterimage, never a
        # mutable source path. No BASH_ENV, exported functions or startup imports.
        env = {k: v for k, v in os.environ.items() if k in
               ("PATH", "HOME", "TMPDIR", "DOMESTIQUE_HOME", "XDG_STATE_HOME")}
        env["DOMESTIQUE_HOME"] = str(root.parent)
        result = subprocess.run(["/bin/bash", "--noprofile", "--norc", "-s", "--",
                                 "inspect", parsed["target"]], input=payload,
                                env=env, stderr=subprocess.DEVNULL, check=False)
        watch.check()
        need(result.returncode in (0, 1, 2), "management runtime failure")
        return result.returncode if recovery == "none" else 1
    except Misuse as exc:
        print("domestique2: " + str(exc), file=sys.stderr)
        return 2
    except (Refusal, OSError, ValueError, IndexError):
        print("domestique2: runtime unavailable/invalid or conflicting root; no fallback",
              file=sys.stderr)
        return 1
