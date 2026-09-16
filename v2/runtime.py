"""Trusted verification/availability protocol; activation/body APIs fail closed."""
import os
import sys
from .safe import Watch, need, physical, read, snapshot, stat, Path, Refusal
from .package import RELEASE, verify_package, re
from .records import machine, manifest_read
from .journal import recovery_state


def active_read(data, releases):
    need(re.fullmatch(rb"release=r-[0-9a-f]{64}\n", data), "invalid active")
    release = data.decode()[8:-1]
    need(release in releases, "unlisted active")
    return release


def runtime_read(root, launcher, launcher_data):
    """Pending is not rollback or revocation. Never guess a missing selection."""
    root, launcher = physical(root), physical(launcher)
    watch = Watch()
    for p in (root, root / "state", root / "releases"):
        snap = snapshot(p)
        need(snap is not None and snap[1] is None and
             stat.S_IMODE(snap[0][3]) == 0o700, "missing/unsafe runtime directory")
        watch.add(p)
    need(read(launcher, mode=0o755) == launcher_data, "edited launcher")
    watch.add(launcher)
    m = machine(root, launcher)
    raw = read(root / "state/runtime-manifest", mode=0o600)
    watch.add(root / "state/runtime-manifest")

    def load(r):
        package = verify_package(root / "releases" / r, installed=True)
        for p in (root / "releases" / r).rglob("*"):
            watch.add(p)
        watch.add(root / "releases" / r)
        return package

    releases = manifest_read(raw, m, launcher_data, load)
    active = read(root / "active", mode=0o600)
    watch.add(root / "active")
    selected = active_read(active, releases)
    watch.check()
    return selected, releases, watch


def launcher_main(root, home):
    """Only availability/version is implemented here, never candidate dispatch."""
    try:
        if sys.argv[1:] in (["--help"], ["-h"], ["help"]):
            print("domestique2: local runtime protocol ABI 2; activation/management unavailable")
            return 0
        need(sys.argv[1:] in (["version"], ["--version"]),
             "unsupported operation; activation/management guards unavailable")
        home = physical(home)
        need(os.environ.get("HOME") == str(home), "conflicting HOME")
        override = os.environ.get("DOMESTIQUE_HOME")
        xdg = os.environ.get("XDG_STATE_HOME")
        if override:
            need(physical(override) / "v2" == Path(root), "conflicting runtime override")
        elif xdg:
            need(physical(xdg) / "domestique/v2" == Path(root), "conflicting state override")
        launcher = home / ".local/bin/domestique2"
        selected, releases, watch = runtime_read(root, launcher, read(launcher, mode=0o755))
        recovery = recovery_state(Path(root), launcher, read(launcher, mode=0o755))
        watch.check()
        print("runtime=" + selected + " version=" + releases[selected]["version"] +
              " launcher_abi=2 recovery=" + recovery)
        return 0 if recovery == "none" else 1
    except (Refusal, OSError, ValueError):
        # Never print file contents, ambient values or unsafe path spellings.
        print("domestique2: runtime unavailable or unsupported; no fallback", file=sys.stderr)
        return 1
