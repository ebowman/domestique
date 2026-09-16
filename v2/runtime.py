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


def runtime_read(root, launcher, launcher_data, watch=None):
    """Pending is not rollback or revocation. Never guess a missing selection."""
    root, launcher = physical(root), physical(launcher)
    watch = watch if watch is not None else Watch()
    for p in (root, root / "state", root / "releases"):
        watch.add(p)
        snap = snapshot(p)
        need(snap is not None and snap[1] is None and
             stat.S_IMODE(snap[0][3]) == 0o700, "missing/unsafe runtime directory")
    watch.add(launcher)
    need(read(launcher, mode=0o755) == launcher_data, "edited launcher")
    m = machine(root, launcher)
    watch.add(root / "state/runtime-manifest")
    raw = read(root / "state/runtime-manifest", mode=0o600)

    def load(r):
        return verify_package(root / "releases" / r, installed=True, watch=watch)

    releases = manifest_read(raw, m, launcher_data, load)
    watch.add(root / "active")
    active = read(root / "active", mode=0o600)
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
        watch = Watch()
        watch.add(launcher)
        launcher_data = read(launcher, mode=0o755)
        selected, releases, watch = runtime_read(root, launcher, launcher_data, watch=watch)
        recovery = recovery_state(Path(root), launcher, launcher_data)
        watch.check()
        print("runtime=" + selected + " version=" + releases[selected]["version"] +
              " launcher_abi=2 recovery=" + recovery)
        return 0 if recovery == "none" else 1
    except (Refusal, OSError, ValueError):
        # Never print file contents, ambient values or unsafe path spellings.
        print("domestique2: runtime unavailable or unsupported; no fallback", file=sys.stderr)
        return 1
