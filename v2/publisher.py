"""Trusted provider-independent local machine publisher, Appendix A/B/D.

publish_local(source, env, dry_run=False, hook=None) is the internal API.
hook is a trusted test callback, never an environment/CLI escape or candidate.
No recovery, native/project operation or GC. Bootstrap supplies a trusted
selection callback for official transport, after existing-state validation.
"""
from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
from .safe import (META_LIMIT, MAX_NUMBER, PAYLOAD_LIMIT, Refusal, Watch, attributes,
                   checked_write, exclusive, moved_witness, write_created,
                   need, physical, read, safe, sha, snapshot, text_bounds)
from .package import DIRS, LEAVES, inventory, payload_mode, verify_package
from .records import (machine, manifest_bytes, previous_bytes, previous_read,
                      pending_bytes, published_header, fact_bytes, published_read)
from .runtime import active_read, runtime_read
from .journal import recovery_state
from .build import launcher_bytes


class PublicationFailure(Refusal):
    def __init__(self, selected, recovery):
        self.selected, self.recovery = selected, recovery
        super().__init__(f"publication failed: runtime={selected}; recovery={recovery}; "
                         "preserve evidence; no rollback or takeover")


def no_repo(path, env):
    # Every call observes the exact ancestors afresh. Gitfiles, dangling
    # redirects and .git directories refuse without invoking Git. Bare Git
    # discovery needs Git only when an ancestor has its HEAD entry.
    ancestors = (path, *path.parents)
    for parent in ancestors:
        need(not os.path.lexists(parent / ".git") and parent.name != ".git",
             "machine destination overlaps Git")
    p = path
    while not p.is_dir():
        p = p.parent
    git = shutil.which("git", path=env.get("PATH", ""))
    need(git, "missing Git capability")
    git_env = {"PATH": env["PATH"], "HOME": env["HOME"], "LC_ALL": "C",
               "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_SYSTEM": os.devnull,
               "GIT_CONFIG_GLOBAL": os.devnull, "GIT_OPTIONAL_LOCKS": "0",
               "GIT_TERMINAL_PROMPT": "0", "GIT_PAGER": "cat"}
    proc = subprocess.run([git, "-C", str(p), "rev-parse", "--absolute-git-dir"],
                          env=git_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=120, check=False)
    need(proc.returncode == 128 and b"not a git repository" in proc.stderr,
         "machine destination overlaps Git or Git validation unavailable")


def boundary(paths, env):
    ancestors = {a for p in paths for a in (p, *p.parents)}
    for p in ancestors:
        need(p.name not in {".claude", ".agents", ".codex", ".copilot", ".github",
                           ".domestique-private", ".beads", ".git"},
             "machine/native overlap")
        need(not os.path.lexists(p / ".git"), "machine destination overlaps Git")
        if os.path.lexists(p / "HEAD"):
            no_repo(p, env)


@contextmanager
def staging_area(temp, watch):
    """Only our closed staging inventory; never auto-delete across a new boundary."""
    watch.check_boundary()
    staging = temp / ("domestique-v2-stage-" + uuid.uuid4().hex)
    created = watch.mkdir(staging)
    watch.advance(staging, created)
    stage = staging / "package"
    cleaned = False

    def clean():
        nonlocal cleaned
        watch.check()
        for p in (*(stage / p for p in reversed(LEAVES)),
                  *(stage / d for d in reversed(DIRS)), stage, staging):
            watch.check()
            need(snapshot(p) == watch.paths[p], "changed staging cleanup path")
            if os.path.lexists(p):
                safe(p)
                directory = p.is_dir()
                with watch.namespace(p.parent, entry_delta=-1,
                                     directory_delta=-1 if directory else 0):
                    if directory:
                        p.rmdir()
                    else:
                        p.unlink()
                watch.advance(p, None)
        cleaned = True

    # An exception thrown at yield leaves private evidence untouched, with no
    # automatic cleanup writes after a Git/native/identity boundary refusal.
    yield stage, clean
    if not cleaned:
        clean()
    watch.check_boundary()


def roots(env):
    need(not env.get("DOMESTIQUE_UPDATE_SOURCE"), "explicit local source required")
    home = physical(env.get("HOME", ""))
    need(home.is_dir(), "HOME unavailable")
    if env.get("XDG_STATE_HOME"):
        physical(env["XDG_STATE_HOME"])
    base = physical(env.get("DOMESTIQUE_HOME") or
                    str(Path(env.get("XDG_STATE_HOME") or str(home / ".local/state")) /
                        "domestique"))
    root, launcher = base / "v2", home / ".local/bin/domestique2"
    need(root != home and root not in home.parents and launcher != root and
         root not in launcher.parents and launcher not in root.parents, "overlapping roots")
    native = {".claude", ".agents", ".codex", ".copilot", ".github",
              ".domestique-private", ".beads", ".git"}
    for p in (root, launcher):
        safe(p)
        need(not native.intersection(p.parts), "machine/native overlap")
        no_repo(p, env)
    tools = {name: shutil.which(name, path=env.get("PATH", "")) for name in ("python3", "bash")}
    need(all(tools.values()), "missing runtime capability")
    need(sys.platform != "darwin" or tools["python3"] != "/usr/bin/python3",
         "Python setup launcher is not a runtime capability")
    for argv in ([tools["python3"], "-I", "-S", "-B", "-c",
                  "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)"],
                 [tools["bash"], "--noprofile", "--norc", "-c",
                  "(( BASH_VERSINFO[0] > 3 || (BASH_VERSINFO[0] == 3 && BASH_VERSINFO[1] >= 2) ))"]):
        check = subprocess.run(argv, env={"PATH": env["PATH"], "HOME": str(home)},
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               timeout=120, check=False)
        need(check.returncode == 0 and not check.stdout, "unsupported runtime capability")
    return home, root, launcher


def pending_refusal(root):
    for j in (root / "state", root / "state/retire-global"):
        for name in ("pending", "previous", "published"):
            p = j / name
            safe(p)
            need(not os.path.lexists(p), "pending/orphan evidence; no takeover")


def runtime_inventory(root, releases, journals=()):
    leaves = ["active", "state/runtime-manifest", *("state/" + p for p in journals)]
    dirs = ["state", "releases"]
    for r in releases:
        dirs += ["releases/" + r, *("releases/" + r + "/" + d for d in DIRS)]
        leaves += ["releases/" + r + "/" + p for p in LEAVES]
    inventory(root, leaves, dirs)
    for d in dirs:
        snap = snapshot(root / d)
        need(stat.S_IMODE(snap[0][3]) == 0o700, "private directory mode")


def missing_parents(path):
    result = []
    p = path
    while not p.exists():
        result.append(p)
        p = p.parent
    return list(reversed(result))


def plan(root, launcher, packages, selected, dispatcher, m, watch, framing):
    items = []

    def add(p, phase, data=None, mode=0o700, owned=False):
        if p not in watch.paths:
            watch.add(p)
        prior = watch.paths[p]
        if data is None and prior is not None:
            need(prior[1] is None, "directory collision")
            return
        if data is not None and prior is not None:
            need(owned and prior[1] is not None, "unowned matching/colliding leaf")
            if prior[1] == data and stat.S_IMODE(prior[0][3]) == mode:
                return
        action = "mkdir" if data is None else "replace" if prior else "create"
        items.append(dict(path=p, phase=phase, action=action, data=data, mode=mode))

    new = selected["release"] not in packages
    combined = dict(packages)
    if selected["source_kind"] == "official":
        need(all(p["official_version"] != selected["version"] or
                 r == selected["release"] for r, p in packages.items()),
             "conflicting retained official mapping")
        # An actual verified official selection may qualify a retained local R.
        # This changes only mapping metadata, never creation/baseline facts.
        combined[selected["release"]] = selected
    if new:
        combined[selected["release"]] = selected
        release = root / "releases" / selected["release"]
        for d in (root / "releases", release, *(release / d for d in DIRS)):
            add(d, "release")
        for leaf in LEAVES:
            add(release / leaf, "release", selected["data"][leaf], payload_mode(leaf))
    for p in missing_parents(launcher.parent):
        if p not in framing:
            add(p, "launcher")
    add(launcher, "launcher", dispatcher, 0o755, bool(packages))
    manifest = manifest_bytes(m, dispatcher, combined)
    add(root / "state/runtime-manifest", "manifest", manifest, 0o600, bool(packages))
    add(root / "active", "active", ("release=" + selected["release"] + "\n").encode(),
        0o600, bool(packages))
    order = {"release": 0, "launcher": 1, "manifest": 2, "active": 3}
    items.sort(key=lambda i: (order[i["phase"]], str(i["path"]).encode()))
    return items, combined


def publish_local(source, env, dry_run=False, hook=None):
    """Returns {runtime, recovery, changed, dry_run}; failures never claim rollback.

    Source is a local package directory, not a checkout/script/archive/URL.
    No source path is retained in destination metadata. env is an explicit
    trusted invocation environment, not candidate metadata.
    """
    hook = hook or (lambda event, path: None)
    def select(packages):
        path = str(source)
        need("://" not in path, "only local package directories")
        if not path.startswith("/"):
            path = str(Path.cwd() / path)
        candidate = verify_package(path)
        hook("verified-source", Path(path))
        return candidate
    return _publish(select, env, dry_run, hook)


def _publish(select, env, dry_run=False, hook=None):
    """One publisher; select is trusted bootstrap logic, never candidate code."""
    hook = hook or (lambda event, path: None)
    home, root, launcher = roots(env)
    dispatcher = launcher_bytes(root, home)
    pending_refusal(root)
    watch = Watch(lambda: boundary((root, launcher), env))
    watch.add(root)
    packages, old = {}, None
    if root.exists():
        old, packages, _ = runtime_read(root, launcher, dispatcher, watch=watch)
        runtime_inventory(root, packages)
        watch.check()
    else:
        need(not os.path.lexists(launcher), "unowned launcher; equality is not ownership")
    for p in (launcher, root / "state", *(root / "state" / n for n in
                                       ("pending", "previous", "published"))):
        watch.add(p)
    for p in (root, launcher):
        ancestor = p.parent
        while not ancestor.exists():
            watch.add(ancestor)
            ancestor = ancestor.parent
        need(os.access(ancestor, os.W_OK), "unwritable destination parent")
        watch.add(ancestor)
    candidate = select(packages)
    # A retained mapping is authorized by the original runtime/package proof.
    # Refuse drift at this hand-off, before any staging or publication writes.
    watch.check()
    temp = physical(env.get("TMPDIR", tempfile.gettempdir()))
    need(temp.is_dir() and temp != home and home not in temp.parents and
         temp != root and root not in temp.parents, "staging overlaps destination")
    no_repo(temp, env)
    def fresh_boundary():
        for p in (root, launcher.parent, temp):
            safe(p)
        need(not launcher.is_symlink(), "redirected launcher")
        boundary((root, launcher, temp, *watch.paths), env)
    watch.boundary = fresh_boundary
    watch.add(temp)
    writing = False
    with staging_area(temp, watch) as (stage, clean_stage):
        created = watch.mkdir(stage)
        watch.advance(stage, created)
        for d in DIRS:
            created = watch.mkdir(stage / d)
            watch.advance(stage / d, created)
        for p in LEAVES:
            watch.check()
            created = exclusive(stage / p, candidate["data"][p], payload_mode(p),
                                watch.check_boundary, watch=watch)
            watch.advance(stage / p, created)
        selected = verify_package(stage, installed=True, watch=watch)
        need(all(selected[k] == candidate[k] for k in ("release", "version", "data")),
             "stage differs from verified input")
        selected = dict(selected, source_kind=candidate["source_kind"],
                        official_version=candidate["official_version"])
        hook("stage", stage)
        framing = missing_parents(root) + ([] if (root / "state").exists()
                                          else [root / "state"])
        items, combined = plan(root, launcher, packages, selected, dispatcher,
                               machine(root, launcher, not root.exists()), watch, framing)
        tx = uuid.uuid4().hex
        # Worst-case machine identity and fact sizes are bounded before any claim.
        maximum_m = machine(root, launcher, True)
        maximal_items = [dict(i) for i in items]
        for i in maximal_items:
            if i["phase"] == "manifest":
                i["data"] = manifest_bytes(maximum_m, dispatcher, combined)
        pre = previous_bytes(tx, maximum_m, maximal_items, watch.paths)
        pen = pending_bytes(tx, maximum_m, pre, old, selected["release"], maximal_items)
        header = published_header(tx, pen)
        maximal = header
        h = header.splitlines()[-1].split(b"=")[1].decode()
        for n, i in enumerate(maximal_items, 1):
            fake = ((MAX_NUMBER, MAX_NUMBER, MAX_NUMBER,
                     stat.S_IFDIR | i["mode"] if i["data"] is None else
                     stat.S_IFREG | i["mode"], 1, 0, 0, 0), i["data"])
            raw = fact_bytes(h, n, i["phase"], n, {"mkdir": "directory-created",
                             "create": "created", "replace": "replaced"}[i["action"]], fake)
            maximal += raw
            h = raw.splitlines()[-1].split(b"=")[1].decode()
        maximal += fact_bytes(h, len(items) + 1, "complete", 0, "committed")
        text_bounds(maximal)
        watch.check()
        pending_refusal(root)
        hook("preflight", root)
        watch.check()
        if dry_run or not items:
            clean_stage()
            watch.check()
            return dict(runtime=old if dry_run else selected["release"], recovery="none",
                        changed=bool(items), dry_run=dry_run)
        try:
            for p in framing:
                watch.check()
                hook("before-claim", p)
                watch.check()
                writing = True
                created = watch.mkdir(p)
                watch.advance(p, created)
                hook("claim", p)
            m = machine(root, launcher)
            items, combined = plan(root, launcher, packages, selected, dispatcher,
                                   m, watch, framing)
            previous = previous_bytes(tx, m, items, watch.paths)
            pending = pending_bytes(tx, m, previous, old, selected["release"], items)

            def metadata(p, raw):
                if p.name == "active":
                    active_read(raw, packages)
                else:
                    need(raw == read(p, mode=0o600), "previous manifest changed")

            previous_read(previous, previous, metadata)
            published = published_header(tx, pending)
            for name, raw in (("pending", pending), ("previous", previous), ("published", published)):
                watch.check()
                p = root / "state" / name
                writing = True
                created = exclusive(p, raw, 0o600, watch.check_boundary, watch=watch)
                watch.advance(p, created)
                hook(name, p)

            def append(phase, n, result, snap=None):
                nonlocal published
                watch.check()
                h, seq = published_read(published, tx, pending, items)
                raw = fact_bytes(h, seq + 1, phase, n, result, snap)
                p = root / "state/published"
                watch.check_boundary()
                fd = os.open(p, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
                try:
                    appended = checked_write(fd, p, raw, watch.paths[p], watch.check_boundary)
                finally:
                    os.close(fd)
                published += raw
                need(read(p, mode=0o600) == published, "journal append failed")
                watch.advance(p, appended)
                watch.check()
                published_read(published, tx, pending, items)

            for n, i in enumerate(items, 1):
                p = i["path"]
                hook("before-" + i["phase"], p)
                watch.check()
                if i["phase"] in ("launcher", "manifest", "active"):
                    verified = verify_package(root / "releases" / selected["release"],
                                              installed=True, watch=watch)
                    need(verified["data"] == selected["data"], "final release changed")
                if i["phase"] in ("manifest", "active"):
                    # Final creations and facts, not intent/equal bytes, authorize B.
                    need(read(launcher, mode=0o755) == dispatcher, "final launcher changed")
                    _, count = published_read(published, tx, pending, items)
                    need(count == n - 1, "missing creation facts")
                watch.check()
                if i["action"] == "mkdir":
                    created = watch.mkdir(p, i["mode"])
                elif i["action"] == "create" and i["phase"] not in ("launcher", "active"):
                    created = exclusive(p, i["data"], i["mode"], watch.check_boundary,
                                        watch=watch)
                else:
                    fd = None
                    try:
                        with watch.namespace(p.parent, entry_delta=1):
                            fd, name = tempfile.mkstemp(prefix=".publication-", dir=p.parent)
                            tmp = Path(name)
                            initial = (attributes(os.fstat(fd)), b"")
                        created = write_created(fd, tmp, i["data"], i["mode"],
                                                watch.check_boundary, initial)
                        watch.advance(tmp, created)
                        watch.check()
                        hook("before-rename-" + i["phase"], p)
                        watch.check()
                        if i["action"] == "replace":
                            with watch.namespace(p.parent, entry_delta=-1):
                                os.replace(tmp, p)
                                created = moved_witness(fd, created, 1)
                        else:
                            # global_link_new pattern: atomic no-clobber final
                            # name, then remove our temporary link before verify.
                            # A partially written executable/selector is never visible.
                            with watch.namespace(p.parent, entry_delta=1):
                                os.link(tmp, p, follow_symlinks=False)
                                linked_witness = moved_witness(fd, created, 2)
                            watch.check_boundary()
                            # The two links are our witnessed transition, not a
                            # general exception to single-link safe reads. Keep
                            # the original descriptor through byte/identity checks.
                            linked = os.fstat(fd)
                            need(attributes(linked) == linked_witness[0],
                                 "changed linked afterimage")
                            with os.fdopen(fd, "rb", closefd=False) as stream:
                                stream.seek(0)
                                need(stream.read(len(i["data"]) + 1) == i["data"],
                                     "changed linked bytes")
                            watch.check_boundary()
                            need(attributes(os.fstat(fd)) == attributes(linked) ==
                                 attributes(tmp.lstat()) == attributes(p.lstat()),
                                 "changed linked identity")
                            with watch.namespace(p.parent, entry_delta=-1):
                                tmp.unlink()
                                created = moved_witness(fd, linked_witness, 1)
                        # Retain an absence watch: a new object at the old name
                        # must not be leaked by a falsely successful publication.
                        watch.advance(tmp, None)
                    finally:
                        # No failure-time unlink/restore/adoption. Even an empty
                        # or partially written afterimage is manual evidence.
                        if fd is not None:
                            os.close(fd)
                watch.advance(p, created)
                snap = snapshot(p)
                need(snap == created, "changed published identity/bytes")
                need(snap is not None and stat.S_IMODE(snap[0][3]) == i["mode"] and
                     snap[1] == i["data"], "post-publication verification")
                hook("written-" + i["phase"], p)
                append(i["phase"], n, {"mkdir": "directory-created", "create": "created",
                                      "replace": "replaced"}[i["action"]], snap)
                hook("after-" + i["phase"], p)
            actual, retained, checked = runtime_read(root, launcher, dispatcher, watch=watch)
            need(actual == selected["release"], "incorrect final selection")
            runtime_inventory(root, retained, ("pending", "previous", "published"))
            checked.check()
            watch.check()
            clean_stage()
            append("complete", 0, "committed")
            published_read(published, tx, pending, items, complete=True)
            hook("complete", root)
            for name in ("published", "previous", "pending"):
                hook("before-clear-" + name, root / "state" / name)
                watch.check()
                p = root / "state" / name
                with watch.namespace(p.parent, entry_delta=-1):
                    p.unlink()
                watch.advance(p, None)
                hook("clear-" + name, p)
            watch.check()
            return dict(runtime=actual, recovery="none", changed=True, dry_run=False)
        except Exception as exc:
            if not writing:
                raise
            actual = "unavailable"
            try:
                actual, _, _ = runtime_read(root, launcher, dispatcher)
            except (Refusal, OSError, ValueError):
                pass
            recovery = recovery_state(root, launcher, dispatcher)
            if recovery == "none" and actual == "unavailable":
                recovery = "unknown"
            raise PublicationFailure(actual, recovery) from exc
