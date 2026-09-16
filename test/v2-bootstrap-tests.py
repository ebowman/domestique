"""Focused CURRENT bootstrap scope. Real packages/publication, no native/network.

Inspection cases run serially in this scope, with no other fixture writers.
Transport is deterministic stdlib mocks/stubs; no GitHub asset is contacted.
"""
import contextlib
import gzip
import importlib.util
import io
import json
import os
from pathlib import Path
import shlex
import sys
import tarfile
import unittest
from unittest.mock import patch

import inspect_fixture as F
sys.path.insert(0, str(F.ROOT))
from v2 import build as B
from v2 import bootstrap as BO
from v2 import dispatcher as D
from v2 import publisher as P
from v2 import transport as T
from v2.cli import Misuse, parse_cli
from v2.package import DIRS, LEAVES, package_from_data, verify_package
from v2.safe import Refusal, sha

spec = importlib.util.spec_from_file_location("publisher_fixture", F.ROOT / "test/v2-publisher-tests.py")
V = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V)
SCRIPT = F.ROOT / "install-v2.sh"


def run(s, *args, **kw):
    return s.run(["/bin/bash", SCRIPT, *args], check=False, operation="install", **kw)


def archive(data, extra=(), omit=()):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        for name in ("domestique2", *("domestique2/" + p for p in DIRS), *(
                "domestique2/" + p for p in LEAVES)):
            if name in omit:
                continue
            info = tarfile.TarInfo(name)
            if name == "domestique2" or name[len("domestique2/"):] in DIRS:
                info.type = tarfile.DIRTYPE
                tar.addfile(info)
            else:
                body = data[name[len("domestique2/"):]]
                info.size = len(body)
                tar.addfile(info, io.BytesIO(body))
        for info, body in extra:
            tar.addfile(info, io.BytesIO(body))
    return gzip.compress(buffer.getvalue(), mtime=0)


def sidecar(raw, version="2.0.0"):
    return (sha(raw) + "  domestique2-" + version + ".tar.gz\n").encode()


def response(body=b"", status=200, location=None):
    return (f"HTTP/1.1 {status} Fixture\r\n".encode() +
            (b"Location: " + location.encode() + b"\r\n" if location else b"") +
            b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body)


def dispatch_marker(s):
    marker = s.root / "calls/management-executed"
    source = V.source(s)
    (source / "domestique2.sh").write_text(
        "#!/bin/bash\nprintf executed > " + shlex.quote(str(marker)) + "\n")
    V.rewrite_sums(source)
    selected = P.publish_local(source, s.env)["runtime"]
    return V.root(s) / "releases" / selected, marker


def curl_stub(s):
    wire = s.root / "sources/wire"
    wire.mkdir()
    program = wire / "curl.py"
    program.write_text(
        "import json, pathlib, sys\n"
        f"p = pathlib.Path({str(wire)!r})\n"
        "log = p / 'calls'\n"
        "index = len(log.read_text().splitlines())\n"
        "with log.open('a') as out: out.write(json.dumps(sys.argv[1:])+'\\n')\n"
        f"print({F.SECRET!r}, file=sys.stderr)\n"
        "sys.stdout.buffer.write((p / str(index)).read_bytes())\n")
    (s.root / "bin/curl").write_text(
        "#!/bin/sh\nexec " + shlex.quote(sys.executable) +
        " -I -S -B -Werror " + shlex.quote(str(program)) + ' "$@"\n')
    return wire


def generated_bootstrap():
    """Execute the actual emitted body, omitting only the terminal CLI call."""
    raw = SCRIPT.read_bytes()
    body = raw.decode().split("<<'DOMESTIQUE_V2_TRUSTED_PY'\n", 1)[1]
    body = body.rsplit("\nDOMESTIQUE_V2_TRUSTED_PY\n", 1)[0]
    suffix = "sys.exit(bootstrap_main())\n"
    if not body.endswith(suffix):
        raise AssertionError("generated bootstrap entry boundary changed")
    namespace = {"__name__": "generated_bootstrap_fixture"}
    exec(compile(body[:-len(suffix)], "<actual-install-v2.sh>", "exec"), namespace)
    return namespace


def operator_change(s, path, change):
    """Fixture-owned edits; return an exact post-edit oracle, never verified data."""
    original, before = path.read_bytes(), path.lstat()
    body = original + b"\n# " + F.SECRET.encode() + b"\n" if change.endswith(
        "different") else original
    auxiliary = s.root / "sources/operator-object"
    if change.startswith("inplace-"):
        path.write_bytes(body)
    elif change.startswith("replace-"):
        auxiliary.write_bytes(body)
        auxiliary.chmod(before.st_mode & 0o777)
        os.utime(auxiliary, ns=(before.st_atime_ns, before.st_mtime_ns))
        os.replace(auxiliary, path)
    elif change == "mode":
        path.chmod((before.st_mode & 0o777) ^ 0o100)
    elif change == "mtime":
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns + 10**9))
    elif change == "hardlink":
        os.link(path, auxiliary)
    elif change == "symlink":
        auxiliary.write_bytes(original)
        path.unlink()
        path.symlink_to(auxiliary)
    else:
        raise AssertionError(change)
    return original, before, auxiliary


class BootstrapTests(unittest.TestCase):
    def retained_bundle(self, s):
        source = V.source(s)
        marker = s.root / "calls/candidate-executed"
        (source / "domestique2.sh").write_text(
            "#!/bin/bash\nprintf executed > " + shlex.quote(str(marker)) + "\n")
        V.rewrite_sums(source)
        data = verify_package(source)["data"]
        wire = curl_stub(s)
        raw = archive(data)
        (wire / "calls").write_text("")
        (wire / "0").write_bytes(response(sidecar(raw)))
        (wire / "1").write_bytes(response(raw))
        self.assertEqual(run(s, "--version=2.0.0").returncode, 0)
        self.assertEqual(len((wire / "calls").read_text().splitlines()), 2)
        ns = generated_bootstrap()
        before = V.protected(s)
        self.assertEqual(self.invoke_bundle(ns, ["--version=2.0.0"])[0], 0)
        self.assertEqual(V.protected(s), before)
        release = V.root(s) / "releases" / verify_package(source)["release"]
        return ns, source, release, marker, wire

    def invoke_bundle(self, ns, args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(sys, "argv", ["install-v2.sh", *map(str, args)]), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            rc = ns["bootstrap_main"]()
        self.assertNotIn(F.SECRET, stdout.getvalue() + stderr.getvalue())
        return rc, stdout.getvalue(), stderr.getvalue()

    def assert_bootstrap_mutation(self, s, ns, marker, wire, args, mutated, label):
        rc, stdout, stderr = self.invoke_bundle(ns, args)
        self.assertEqual(len(mutated), 1, label)
        saved = mutated[0]
        preserved = V.protected(s) == saved["live"]
        witness = dict(case=label, exit=rc, preserved=preserved,
                       before_attributes=saved["before"], edited_attributes=saved["after"],
                       edited_sha256=saved["digest"], candidate_executed=marker.exists(),
                       network_calls=len((wire / "calls").read_text().splitlines()) - 2,
                       journals=sorted(p.name for p in (V.root(s) / "state").iterdir()
                                       if p.name != "runtime-manifest"))
        print("BOOTSTRAP_MUTATION=" + json.dumps(witness, sort_keys=True), flush=True)
        self.assertEqual(rc, 1, witness)
        self.assertEqual(stdout, "", witness)
        self.assertTrue(preserved, witness)
        self.assertFalse(marker.exists(), witness)
        self.assertEqual(witness["network_calls"], 0, witness)
        self.assertIn("preserve", stderr, witness)
        self.assertNotIn("recovery=none", stderr, witness)

    def change_and_save(self, s, path, change, mutated):
        original, before, auxiliary = operator_change(s, path, change)
        mutated.append(dict(live=V.protected(s), before=V.S.attributes(before),
                            after=V.S.attributes(path.lstat()),
                            digest=sha(path.read_bytes()), original=original,
                            path=path, auxiliary=auxiliary))

    def reset_fixture_edit(self, saved):
        # Only after exact preservation assertions, prepare the next independent
        # invocation in this owned fixture. Production never restores these edits.
        path, auxiliary = saved["path"], saved["auxiliary"]
        if path.is_symlink():
            path.unlink()
        if auxiliary.exists():
            auxiliary.unlink()
        path.write_bytes(saved["original"])
        path.chmod(saved["before"][3] & 0o777)

    def test_generated_retained_bootstrap_binds_every_authenticated_read(self):
        with V.fixture() as s:
            ns, source, release, marker, wire = self.retained_bundle(s)
            paths = [V.launcher(s), V.root(s) / "state/runtime-manifest",
                     V.root(s) / "active", *(release / leaf for leaf in LEAVES)]
            for path in paths:
                for change in ("inplace-different", "inplace-same", "replace-different",
                               "replace-same", "mode", "mtime", "hardlink", "symlink"):
                    with self.subTest(path=path.name, change=change):
                        mutated = []
                        read = ns["read"]
                        def read_then_change(p, *args, **kwargs):
                            raw = read(p, *args, **kwargs)
                            if Path(p) == path and not mutated:
                                self.change_and_save(s, path, change, mutated)
                            return raw
                        with patch.dict(ns, read=read_then_change):
                            self.assert_bootstrap_mutation(
                                s, ns, marker, wire, ["--version=2.0.0"], mutated,
                                [str(path.relative_to(s.root)), change, "post-auth-read"])
                        self.reset_fixture_edit(mutated[0])
            # Local reselection has the same retained-runtime proof, not a bypass.
            mutated = []
            read = ns["read"]
            path = V.launcher(s)
            def local_read(p, *args, **kwargs):
                raw = read(p, *args, **kwargs)
                if Path(p) == path and not mutated:
                    self.change_and_save(s, path, "inplace-different", mutated)
                return raw
            with patch.dict(ns, read=local_read):
                self.assert_bootstrap_mutation(s, ns, marker, wire,
                    ["--source", source], mutated, ["local", "launcher", "post-auth-read"])

    def test_generated_bootstrap_predicate_handoffs_preserve_original_watches(self):
        with V.fixture() as s:
            ns, source, release, marker, wire = self.retained_bundle(s)
            for function in ("verify_package", "manifest_read", "runtime_read",
                             "runtime_inventory", "plan"):
                for path in (V.launcher(s), V.root(s) / "state/runtime-manifest",
                             V.root(s) / "active", release / "domestique2.sh"):
                    for change in ("inplace-different", "replace-same"):
                        with self.subTest(function=function, path=path.name, change=change):
                            mutated = []
                            original = ns[function]
                            def after_predicate(*args, **kwargs):
                                result = original(*args, **kwargs)
                                if not mutated:
                                    self.change_and_save(s, path, change, mutated)
                                return result
                            with patch.dict(ns, {function: after_predicate}):
                                self.assert_bootstrap_mutation(s, ns, marker, wire,
                                    ["--version=2.0.0"], mutated, [function, path.name, change])
                            self.reset_fixture_edit(mutated[0])
            # A second visit must compare, not register modified bytes/identity.
            watch = ns["Watch"]()
            path = V.launcher(s)
            watch.add(path)
            prior = watch.paths[path]
            path.write_bytes(path.read_bytes() + b"# changed\n")
            with self.assertRaises(ns["Refusal"]):
                watch.add(path)
            self.assertEqual(watch.paths[path], prior)

    def test_generated_bootstrap_preflight_and_written_pending_refuse_drift(self):
        for event in ("preflight", "before-rename-manifest", "before-rename-active"):
            for leaf in ("launcher", "runtime-manifest", "active", "payload"):
                with self.subTest(event=event, leaf=leaf), V.fixture() as s:
                    ns, _, release, marker, wire = self.retained_bundle(s)
                    second = V.source(s, "2.1.0", "second")
                    path = {"launcher": V.launcher(s),
                            "runtime-manifest": V.root(s) / "state/runtime-manifest",
                            "active": V.root(s) / "active",
                            "payload": release / "roles/goal.md"}[leaf]
                    mutated = []
                    def observe_hook(name, p):
                        if name == event and not mutated:
                            self.change_and_save(s, path, "replace-different", mutated)
                    publish = ns["_publish"]
                    def inject(select, env, dry_run=False, hook=None):
                        return publish(select, env, dry_run, observe_hook)
                    with patch.dict(ns, _publish=inject):
                        self.assert_bootstrap_mutation(s, ns, marker, wire,
                            ["--source", second], mutated, [event, leaf])
                    journals = V.root(s) / "state"
                    if event == "preflight":
                        self.assertFalse((journals / "pending").exists())
                    else:
                        self.assertTrue((journals / "pending").exists())
                        prior = dict(V.parse_record((journals / "previous").read_bytes()))
                        self.assertEqual(prior["core_ino"], str(V.root(s).stat().st_ino))

    def test_generated_bootstrap_staged_creation_never_adopts_equal_replacement(self):
        with V.fixture() as s:
            ns, _, _, marker, wire = self.retained_bundle(s)
            exclusive = ns["exclusive"]
            changed = []
            def create_then_replace(path, *args, **kwargs):
                result = exclusive(path, *args, **kwargs)
                if path.name == "PACKAGE" and "domestique-v2-stage-" in str(path):
                    auxiliary = s.root / "sources/replacement"
                    auxiliary.write_bytes(path.read_bytes())
                    auxiliary.chmod(path.stat().st_mode & 0o777)
                    os.replace(auxiliary, path)
                    changed.append((path, V.S.snapshot(path)))
                return result
            before = V.protected(s)
            with patch.dict(ns, exclusive=create_then_replace):
                rc, stdout, stderr = self.invoke_bundle(ns, ["--version=2.0.0"])
            self.assertEqual(rc, 1)
            self.assertEqual(stdout, "")
            self.assertIn("preserve", stderr)
            self.assertEqual(len(changed), 1)
            self.assertEqual(V.S.snapshot(changed[0][0]), changed[0][1])
            self.assertEqual(V.protected(s), before)
            self.assertFalse(marker.exists())
            self.assertEqual(len((wire / "calls").read_text().splitlines()), 2)

    def creation_handoff(self, window, change, update=True):
        with V.fixture() as s:
            first = V.source(s)
            if update:
                self.assertEqual(run(s, "--source", first).returncode, 0)
            source = V.source(s, "2.1.0", "handoff-candidate")
            ns = generated_bootstrap()
            observed = []
            active = V.root(s) / "active"
            old_active = V.S.snapshot(active)

            def mutate(path, created):
                if observed:
                    return
                before = path.lstat()
                if path.is_dir():
                    if change == "replace-same":
                        path.rename(s.root / "sources/operator-directory")
                        path.mkdir(mode=before.st_mode & 0o777)
                    elif change == "mode":
                        path.chmod(0o750)
                    else:
                        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns + 10**9))
                else:
                    operator_change(s, path, change)
                observed.append(dict(path=path, created=created, tree=s.snapshot(),
                                     attributes=V.S.attributes(path.lstat()),
                                     active=V.S.snapshot(active)))

            exclusive, write, moved = ns["exclusive"], ns["write_created"], ns["moved_witness"]
            checked_write = ns["checked_write"]
            mkdir, advance = ns["Watch"].mkdir, ns["Watch"].advance
            written = []

            def exclusive_then_edit(path, *args, **kwargs):
                result = exclusive(path, *args, **kwargs)
                journal = path.parent == V.root(s) / "state" and path.name == window
                payload = (window == "created-payload" and path.name == "PACKAGE" and
                           V.root(s) / "releases" in path.parents)
                manifest = window == "created-manifest" and path.name == "runtime-manifest"
                parent = window == "parent-after-create" and path.name == "previous"
                if journal or payload or manifest or parent:
                    mutate(path.parent if parent else path, result)
                return result

            def write_then_edit(fd, path, *args, **kwargs):
                result = write(fd, path, *args, **kwargs)
                if path.name.startswith(".publication-"):
                    written.append(path)
                    if window == "afterimage":
                        mutate(path, result)
                return result

            def move_then_edit(fd, before, links):
                result = moved(fd, before, links)
                if window == "linked-afterimage" and links == 2:
                    # The temporary and final link share the original descriptor.
                    mutate(written[-1], result)
                elif window == "moved-active" and links == 1 and written[-1].parent == V.root(s):
                    mutate(active, result)
                return result

            def append_then_edit(fd, path, data, before, guard):
                result = checked_write(fd, path, data, before, guard)
                if window == "appended-journal" and path.name == "published" and before[1]:
                    mutate(path, result)
                return result

            def mkdir_then_edit(watch, path, *args, **kwargs):
                result = mkdir(watch, path, *args, **kwargs)
                match = ((window == "stage-directory" and path.name == "package") or
                         (window == "framing-directory" and path == V.root(s) / "state") or
                         (window == "release-directory" and path.parent == V.root(s) / "releases"))
                if match:
                    mutate(path, result)
                return result

            def advance_then_edit(watch, path, witnessed):
                result = advance(watch, path, witnessed)
                if window == "bound-previous" and path == V.root(s) / "state/previous" \
                        and witnessed is not None:
                    mutate(path, witnessed)
                return result

            publish = ns["_publish"]
            def observe_hook(event, path):
                if window == "before-clear" and event == "before-clear-previous":
                    mutate(path, ns["snapshot"](path))
                if window == "before-commit" and event == "after-active":
                    mutate(V.root(s) / "state/previous", ns["snapshot"](
                        V.root(s) / "state/previous"))
            def inject(select, env, dry_run=False, hook=None):
                return publish(select, env, dry_run, observe_hook)
            with patch.dict(ns, exclusive=exclusive_then_edit, write_created=write_then_edit,
                            moved_witness=move_then_edit, checked_write=append_then_edit,
                            _publish=inject), \
                    patch.object(ns["Watch"], "mkdir", mkdir_then_edit), \
                    patch.object(ns["Watch"], "advance", advance_then_edit):
                rc, stdout, stderr = self.invoke_bundle(ns, ["--source", source])
            self.assertEqual(len(observed), 1, (window, change, rc, stderr))
            saved = observed[0]
            preserved = s.snapshot() == saved["tree"]
            same_attributes = V.S.attributes(saved["path"].lstat()) == saved["attributes"]
            selected_preserved = V.S.snapshot(active) == saved["active"]
            journals = V.root(s) / "state"
            witness = dict(window=window, change=change, update=update, exit=rc,
                           preserved=preserved, exact_attributes=same_attributes,
                           selection_preserved=selected_preserved,
                           creation_attributes=saved["created"][0],
                           edited_attributes=saved["attributes"],
                           path=str(saved["path"]), stderr=stderr,
                           journals=sorted(p.name for p in journals.iterdir()
                                           if p.name in ("pending", "previous", "published"))
                           if journals.exists() else [])
            print("CREATION_HANDOFF=" + json.dumps(witness, sort_keys=True), flush=True)
            self.assertEqual(rc, 1, witness)
            self.assertEqual(stdout, "", witness)
            self.assertIn("preserve", stderr, witness)
            self.assertNotIn("recovery=none", stderr, witness)
            self.assertTrue(preserved and same_attributes and selected_preserved, witness)
            if window not in ("moved-active", "before-clear", "before-commit"):
                self.assertEqual(V.S.snapshot(active), old_active, witness)
            if change.startswith("replace-") and window != "parent-after-create":
                self.assertNotEqual(saved["created"][0][2], saved["attributes"][2], witness)
            if window not in ("stage-directory", "framing-directory"):
                self.assertTrue((journals / "pending").exists(), witness)
            if window in ("created-payload", "created-manifest"):
                pending = ns["parse_record"]((journals / "pending").read_bytes())
                item = next(dict(pending[i:i + 8]) for i, row in enumerate(pending)
                            if row[0] == "item" and
                            dict(pending[i:i + 8])["path"] == str(saved["path"]))
                self.assertNotIn(("\nitem=" + item["item"] + "\n").encode(),
                                 (journals / "published").read_bytes(), witness)

    def test_generated_journal_creation_handoff_matrix(self):
        for name in ("pending", "previous", "published"):
            for change in ("replace-different", "replace-same", "inplace-different",
                           "inplace-same", "mode", "mtime", "hardlink"):
                with self.subTest(name=name, change=change):
                    self.creation_handoff(name, change)

    def test_generated_created_record_and_afterimage_handoff_matrix(self):
        for window, update in (("created-payload", True), ("created-manifest", False),
                               ("afterimage", True), ("linked-afterimage", False),
                               ("moved-active", True)):
            changes = ("inplace-different", "mode", "mtime") if window == "linked-afterimage" else (
                "replace-same", "inplace-different", "mode", "mtime")
            for change in changes:
                with self.subTest(window=window, change=change):
                    self.creation_handoff(window, change, update)

    def test_generated_directory_creation_and_parent_handoff_matrix(self):
        for window in ("stage-directory", "framing-directory", "release-directory",
                       "parent-after-create"):
            changes = ("mode", "mtime") if window == "parent-after-create" else (
                "replace-same", "mode", "mtime")
            for change in changes:
                with self.subTest(window=window, change=change):
                    self.creation_handoff(window, change, window != "framing-directory")

    def test_generated_late_journal_handoff_never_authorizes_cleanup(self):
        for window in ("bound-previous", "appended-journal", "before-commit", "before-clear"):
            for change in ("replace-same", "inplace-different", "mode", "mtime"):
                with self.subTest(window=window, change=change):
                    self.creation_handoff(window, change)

    def test_generated_retained_directory_validation_keeps_first_observation(self):
        with V.fixture() as s:
            ns, _, release, marker, wire = self.retained_bundle(s)
            for path in (V.root(s), V.root(s) / "state", V.root(s) / "releases",
                         release, *(release / d for d in DIRS)):
                for change in ("mode", "mtime"):
                    with self.subTest(path=path.name, change=change):
                        before = path.stat()
                        changed = []
                        snapshot = ns["snapshot"]
                        def observe_then_change(p, *args, **kwargs):
                            result = snapshot(p, *args, **kwargs)
                            if Path(p) == path and not changed:
                                if change == "mode":
                                    path.chmod(0o750)
                                else:
                                    os.utime(path, ns=(before.st_atime_ns,
                                                      before.st_mtime_ns + 10**9))
                                changed.append(V.protected(s))
                            return result
                        with patch.dict(ns, snapshot=observe_then_change):
                            rc, stdout, stderr = self.invoke_bundle(ns, ["--version=2.0.0"])
                        self.assertEqual(rc, 1)
                        self.assertEqual(stdout, "")
                        self.assertIn("preserve", stderr)
                        self.assertEqual(len(changed), 1)
                        self.assertEqual(V.protected(s), changed[0])
                        self.assertFalse(marker.exists())
                        self.assertEqual(len((wire / "calls").read_text().splitlines()), 2)
                        print("BOOTSTRAP_DIRECTORY=" + json.dumps(dict(
                            path=str(path.relative_to(s.root)), change=change, exit=rc,
                            before=V.S.attributes(before), after=V.S.attributes(path.stat()),
                            preserved=True)), flush=True)
                        path.chmod(before.st_mode & 0o777)
                        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))

    def assert_dispatch_refused(self, s, marker, changed, args=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        args = ["inspect", str(s.root / "cohorts")] if args is None else args
        with patch.object(D.subprocess, "run", wraps=D.subprocess.run) as execute, \
                patch.object(sys, "argv", ["domestique2", *args]), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            rc = D.dispatch_main(V.root(s), s.env["HOME"])
        witness = dict(changed, exit=rc, executions=execute.call_count,
                       execution_marker=marker.exists())
        print("DISPATCH_MUTATION=" + json.dumps(witness, sort_keys=True), flush=True)
        self.assertEqual(rc, 1, witness)
        execute.assert_not_called()
        self.assertFalse(marker.exists())
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("no fallback", stderr.getvalue())

    def fetch_chain(self, s, wire, replies, cap, expected_calls):
        for index, reply in enumerate(replies):
            (wire / str(index)).write_bytes(reply)
        (wire / "calls").write_text("")
        processes, reads = [], []
        active = None
        popen, read = T.subprocess.Popen, T.os.read

        def launch(argv, **kwargs):
            nonlocal active
            active = None
            process = popen(argv, **kwargs)
            active = process.stdout.fileno()
            processes.append(process)
            reads.append({"cap": int(argv[argv.index("--max-filesize") + 1]),
                          "wire": bytearray(), "requests": []})
            return process

        def consume(fd, size):
            chunk = read(fd, size)
            if fd == active:
                reads[-1]["requests"].append(size)
                reads[-1]["wire"].extend(chunk)
            return chunk

        refused = False
        try:
            with patch.object(T.subprocess, "Popen", launch), patch.object(T.os, "read", consume):
                return T.fetch_asset(T.release_url("2.0.0"), cap, s.env)
        except Refusal as exc:
            refused = True
            self.assertNotIn(F.SECRET, str(exc))
            self.assertNotIn("https://", str(exc))
            raise
        finally:
            calls = [json.loads(line) for line in (wire / "calls").read_text().splitlines()]
            bodies = [bytes(row["wire"]).partition(b"\r\n\r\n")[2] for row in reads]
            print("TRANSPORT_WITNESS=" + json.dumps({
                "cap": cap, "refused": refused, "response_count": len(calls),
                "budgets": [row["cap"] for row in reads],
                "consumed_bodies": [len(body) for body in bodies],
                "max_reads": [max(row["requests"], default=0) for row in reads],
                "children_reaped": all(p.returncode is not None for p in processes),
                "pipes_closed": all(p.stdout.closed for p in processes),
            }, sort_keys=True), flush=True)
            self.assertEqual(len(calls), expected_calls)
            self.assertEqual(len(processes), len(calls))
            self.assertLessEqual(sum(map(len, bodies)), cap + int(refused))
            used, deadlines = 0, []
            for row, body, argv, process in zip(reads, bodies, calls, processes):
                self.assertEqual(row["cap"], cap - used)
                self.assertTrue(all(0 < size <= min(65536, row["cap"] + 1)
                                    for size in row["requests"]))
                used += len(body)
                self.assertIsNotNone(process.returncode)
                self.assertTrue(process.stdout.closed)
                self.assertEqual(argv[0], "-q")
                self.assertNotIn("--location", argv)
                self.assertEqual(argv[argv.index("--connect-timeout") + 1], "10")
                self.assertEqual(argv[argv.index("--retry") + 1], "0")
                self.assertEqual(argv[argv.index("--proxy") + 1], "")
                self.assertEqual(argv[argv.index("--noproxy") + 1], "*")
                deadlines.append(float(argv[argv.index("--max-time") + 1]))
            self.assertTrue(all(0 < left <= 120 for left in deadlines))
            self.assertEqual(deadlines, sorted(deadlines, reverse=True))

    def test_current_artifact_and_closed_bundle_fingerprints(self):
        import acceptance as A
        self.assertEqual(SCRIPT.read_bytes(), B.bootstrap_bytes())
        self.assertEqual(A.CURRENT.count("v2-bootstrap-tests.py"), 1)
        self.assertNotIn("v2-bootstrap-tests.py", A.RETAINED_PREVIEW)
        hashes = A.provenance(A.Control(30))["source_sha256"]
        self.assertEqual(hashes["install-v2.sh"], sha(SCRIPT.read_bytes()))
        data = B.package_data("2.0.0")
        self.assertEqual(tuple(sorted(data)), LEAVES)
        self.assertIn(B.inspector_source().encode().splitlines()[0], data["domestique2.sh"])
        self.assertEqual(package_from_data(data)["source_kind"], "local")
        print("BOOTSTRAP_SOURCE_SHA256=" + json.dumps(hashes, sort_keys=True))

    def test_frozen_parser_forms_and_misuse_before_operation(self):
        for args in (["--source", "a"], ["--source=a", "--"], ["--version=2.12.0"],
                     ["--dry-run", "--version", "2.0.0"]):
            self.assertEqual(parse_cli(args, True)["command"], "install")
        for command in ("enable", "disable"):
            for platform in ("claude", "codex", "copilot", "both", "claude-copilot",
                             "codex-copilot", "all"):
                for args in ([command, "--platform=" + platform, "./-literal"],
                             [command, "quotes ' \" \\", "--platform", platform, "--dry-run"]):
                    self.assertEqual(parse_cli(args)["platform"], platform)
        for args in (["inspect", "a"], ["--inspect", "a"], ["a", "--inspect"]):
            self.assertEqual(parse_cli(args), {"command": "inspect", "target": "a"})
        for command in ("enable", "disable", "update", "inspect", "retire-global", "version", "help"):
            for args in (["help", command], [command, "-h"], [command, "--help", "--"]):
                self.assertEqual(parse_cli(args)["command"], "help")
        invalid = [[], ["--source"], ["--source="], ["--source", ""],
                   ["--source=a", "--version=2.0.0"], ["--source=a", "--source=a"],
                   ["--version=2.0.0", "--dry-run", "--dry-run"], ["--source=a", "--help"],
                   ["--source=https://fixture.invalid/x"], ["--", "a"], ["--", "--"],
                   ["--source", "--dry-run"], ["--source=a\nb"], ["--source=a", "--force"]]
        for version in ("1.0.0", "3.0.0", "v2.0.0", "2.01.0", "2.0.00", "2.0", "latest",
                        "main", "2.0.0-rc1", ""):
            invalid.append(["--version=" + version])
        for args in invalid:
            with self.subTest(args=args), self.assertRaises(Misuse):
                parse_cli(args, True)
        for args in (["a"], ["--inspect=a"], ["inspect", ""], ["inspect", "a", "b"],
                     ["inspect", "--dry-run"], ["help", "unknown"], ["--version", "2.0.0"],
                     ["enable", "--platform=none"], ["disable", "--platform="],
                     ["retire-global"], ["retire-global", "--platform=all", "a"],
                     ["enable", "--platform=all", "--platform=all"],
                     ["help", "--help", "inspect"], ["update", "--source=a", "--platform=all"]):
            with self.subTest(args=args), self.assertRaises(Misuse):
                parse_cli(args)
        with V.fixture() as s:
            before = s.snapshot()
            for args in invalid:
                self.assertEqual(run(s, *args).returncode, 2, args)
            self.assertEqual(run(s, "--version=2.0.0", env=dict(
                s.env, DOMESTIQUE_UPDATE_SOURCE="not-executed")).returncode, 2)
            self.assertEqual(s.snapshot(), before)

    def test_first_local_offline_installed_cli_noop_and_refusals(self):
        with V.fixture() as s:
            source = V.source(s)
            target = s.project("literal ' \" \\ scope")
            marker = s.root / "calls/startup"
            (s.root / "sources/sitecustomize.py").write_text(
                f"open({str(marker)!r}, 'w').write('executed')\n")
            env = dict(s.env, PYTHONPATH=str(s.root / "sources"),
                       BASH_ENV=str(s.root / "sources/sitecustomize.py"))
            # Bash's own outer startup is not under a script's control: use the
            # ordinary clean fixture to launch the trusted bootstrap.
            before = V.protected(s)
            self.assertEqual(run(s, "--source", source, "--dry-run").returncode, 0)
            self.assertEqual(V.protected(s), before)
            self.assertEqual(run(s, "--source=" + str(source)).returncode, 0)
            selected = verify_package(source)["release"]
            relocated = source.with_name("relocated ' source")
            source.rename(relocated)
            before = V.protected(s)
            self.assertEqual(run(s, "--source", relocated).returncode, 0)
            self.assertEqual(V.protected(s), before)
            launch = V.launcher(s)
            # Direct executable uses bash -p, ignoring BASH_ENV/exported startup.
            for args in (["help"], ["help", "enable"], ["--help"], ["version"], ["--version"],
                         [], ["inspect", str(target)], ["--inspect", str(target)],
                         [str(target), "--inspect"], ["inspect", "--"]):
                out = s.run([launch, *args], cwd=target, env=env, check=False)
                self.assertEqual(out.returncode, 0, (args, out.stdout, out.stderr))
                self.assertNotIn(F.SECRET.encode(), out.stdout + out.stderr)
                if not args or "inspect" in args or "--inspect" in args:
                    self.assertIn(b"activation=not-assessed", out.stdout)
                    self.assertIn(b"database contents unopened", out.stdout)
                self.assertEqual(V.protected(s), before)
            for args in (["enable"], ["disable", str(target)], ["update", "--version=2.0.0"],
                         ["retire-global", "--platform=all"]):
                out = s.run([launch, *args], check=False)
                self.assertEqual(out.returncode, 1)
                self.assertIn(b"UNIMPLEMENTED", out.stderr)
            for args in (["bogus"], [str(target)], ["inspect", "--force"]):
                self.assertEqual(s.run([launch, *args], check=False).returncode, 2)
            self.assertEqual(s.run([launch, "version"], env=dict(
                s.env, DOMESTIQUE_HOME=str(s.root / "other")), check=False).returncode, 1)
            # Fail before publication: previous command and active remain usable.
            (relocated / "PACKAGE").write_bytes(b"format=1\n")
            self.assertEqual(run(s, "--source", relocated).returncode, 1)
            self.assertEqual(V.protected(s), before)
            self.assertIn(selected.encode(), s.run([launch, "version"]).stdout)
            self.assertFalse(marker.exists())
            # A local V is NOT an offline official mapping.
            with patch.object(BO, "fetch_package", side_effect=Refusal("offline")) as fetch:
                with self.assertRaises(Refusal):
                    BO.publish_version("2.0.0", s.env)
                fetch.assert_called_once()
            release = V.root(s) / "releases" / selected
            (release / "roles/orchestrator.md").unlink()
            (release / "bin/resolve-core").write_text(
                "#!/bin/bash\nprintf x > " + shlex.quote(str(marker)) + "\n")
            before = V.protected(s)
            self.assertEqual(s.run([launch, "inspect", target], check=False).returncode, 0)
            self.assertEqual(V.protected(s), before)
            (release / "domestique2.sh").write_text(
                "#!/bin/bash\nprintf x > " + shlex.quote(str(marker)) + "\n")
            before = V.protected(s)
            self.assertEqual(s.run([launch, "inspect", target], check=False).returncode, 1)
            self.assertEqual(V.protected(s), before)
            self.assertFalse(marker.exists())

    def test_invalid_sources_dryrun_and_candidate_execution_witness(self):
        with V.fixture() as s:
            source = V.source(s)
            marker = s.root / "calls/candidate"
            (source / "domestique2.sh").write_text(
                "#!/bin/bash\nprintf x > " + shlex.quote(str(marker)) + "\n")
            V.rewrite_sums(source)
            pristine = {p: (source / p).read_bytes() for p in LEAVES}
            before = V.protected(s)
            self.assertEqual(run(s, "--source", source, "--dry-run").returncode, 0)
            cases = [(p, b"") for p in ("PACKAGE", "SHA256SUMS", "update2.sh")]
            for old, new in ((b"major=2", b"major=1"), (b"core_api=1", b"core_api=9"),
                             (b"launcher_abi=2", b"launcher_abi=9"),
                             (b"helper_abi=2", b"helper_abi=9"),
                             (b"adapter_abi=2", b"adapter_abi=9"),
                             (b"activation_format=2", b"activation_format=9")):
                cases.append(("PACKAGE", pristine["PACKAGE"].replace(old, new)))
            for leaf, value in cases:
                (source / leaf).write_bytes(value)
                self.assertEqual(run(s, "--source", source).returncode, 1, leaf)
                (source / leaf).write_bytes(pristine[leaf])
            for path in (source / "missing", source / "domestique2.sh",
                         "https://fixture.invalid/package"):
                self.assertNotEqual(run(s, "--source", path).returncode, 0)
            (source / "update2.sh").unlink()
            self.assertEqual(run(s, "--source", source).returncode, 1)
            (source / "update2.sh").symlink_to(source / "domestique2.sh")
            self.assertEqual(run(s, "--source", source).returncode, 1)
            self.assertEqual(V.protected(s), before)
            self.assertFalse(marker.exists())

    def test_unowned_launchers_unsafe_roots_and_native_git_overlap(self):
        for case in ("identical", "edited", "symlink", "relative", "control",
                     "native", "git", "launcher-git"):
            with self.subTest(case=case), V.fixture() as s:
                source = V.source(s)
                env = dict(s.env)
                if case in ("identical", "edited", "symlink"):
                    launch = V.launcher(s)
                    launch.parent.mkdir(parents=True)
                    if case == "symlink":
                        launch.symlink_to(source / "domestique2.sh")
                    else:
                        launch.write_bytes(B.launcher_bytes(V.root(s), Path(env["HOME"]))
                                           if case == "identical" else b"# unknown edit\n")
                        launch.chmod(0o755)
                elif case in ("relative", "control"):
                    env["DOMESTIQUE_HOME"] = ("relative" if case == "relative" else
                                              str(s.root / "bad\nroot"))
                elif case == "native":
                    env["DOMESTIQUE_HOME"] = str(Path(env["HOME"]) / ".claude/state")
                elif case == "git":
                    env["DOMESTIQUE_HOME"] = str(s.project("git", git=True) / "state")
                else:
                    s.run(["git", "init", "-q", env["HOME"]])
                before = V.protected(s)
                self.assertEqual(run(s, "--source", source, env=env).returncode, 1)
                self.assertEqual(V.protected(s), before)

    def test_official_stub_transport_then_offline_retained_and_corrupt_refusal(self):
        with V.fixture() as s:
            data = B.package_data("2.0.0")
            raw = archive(data)
            for name, body in (("archive", raw), ("sidecar", sidecar(raw))):
                (s.root / "sources" / name).write_bytes(response(body))
            log = s.root / "sources/fetch.log"
            stub = s.root / "bin/curl"
            stub.write_text("#!" + sys.executable + "\nimport json, pathlib, sys\n"
                            f"p = pathlib.Path({str(s.root / 'sources')!r})\n"
                            f"with open({str(log)!r}, 'a') as f: f.write(json.dumps(sys.argv[1:])+'\\n')\n"
                            "sys.stdout.buffer.write((p / ('sidecar' if sys.argv[-1].endswith("
                            "'.sha256') else 'archive')).read_bytes())\n")
            source = V.source(s)
            self.assertEqual(run(s, "--source", source).returncode, 0)
            manifest = V.root(s) / "state/runtime-manifest"
            creations = [line for line in manifest.read_bytes().splitlines()
                         if line.startswith((b"created=", b"baseline="))]
            launch_before = V.launcher(s).stat()
            self.assertEqual(run(s, "--version=2.0.0").returncode, 0)
            self.assertEqual(creations, [line for line in manifest.read_bytes().splitlines()
                                        if line.startswith((b"created=", b"baseline="))])
            self.assertEqual(V.launcher(s).stat(), launch_before)
            calls = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual(len(calls), 2)
            for call in calls:
                self.assertEqual(call[0], "-q")
                self.assertNotIn("--location", call)
                self.assertEqual(call[call.index("--connect-timeout") + 1], "10")
                self.assertEqual(call[call.index("--retry") + 1], "0")
                self.assertEqual(call[call.index("--proxy") + 1], "")
                self.assertIn(call[-1], (T.release_url("2.0.0"), T.release_url("2.0.0", True)))
            before = V.protected(s)
            self.assertEqual(run(s, "--version", "2.0.0").returncode, 0)
            self.assertEqual(V.protected(s), before)
            self.assertEqual(len(log.read_text().splitlines()), 2)
            manifest.write_bytes(manifest.read_bytes().replace(b"official_version=2.0.0",
                                                               b"official_version=2.1.0"))
            before = V.protected(s)
            self.assertEqual(run(s, "--version=2.0.0").returncode, 1)
            self.assertEqual(V.protected(s), before)
            self.assertEqual(len(log.read_text().splitlines()), 2)

    def test_archive_closed_inventory_bounds_and_sidecar(self):
        data = B.package_data("2.0.0")
        raw = archive(data)
        self.assertEqual(T.archive_data(raw, sidecar(raw), "2.0.0"), data)
        for checksum in (b"", sidecar(raw).replace(b"  ", b" "),
                         sidecar(raw) + b"\n", sidecar(raw, "2.1.0"), b"0"*64 + sidecar(raw)[64:]):
            with self.subTest(checksum=checksum[:12]), self.assertRaises(Refusal):
                T.archive_data(raw, checksum, "2.0.0")
        bad = [archive(data, omit=("domestique2/PACKAGE",)),
               raw[:-8], gzip.compress(gzip.decompress(raw)[:1024])]
        for name, kind in (("domestique2/PACKAGE", tarfile.REGTYPE),
                           ("domestique2/extra", tarfile.DIRTYPE),
                           ("../escape", tarfile.REGTYPE), ("/absolute", tarfile.REGTYPE),
                           ("domestique2/link", tarfile.SYMTYPE),
                           ("domestique2/hard", tarfile.LNKTYPE),
                           ("domestique2/device", tarfile.CHRTYPE),
                           ("domestique2/pax", tarfile.XHDTYPE)):
            info = tarfile.TarInfo(name)
            info.type = kind
            info.linkname = "PACKAGE" if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE) else ""
            bad.append(archive(data, ((info, b""),)))
        for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.CHRTYPE, tarfile.FIFOTYPE):
            info = tarfile.TarInfo("domestique2/update2.sh")
            info.type = kind
            if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE):
                info.linkname = "domestique2.sh"
            bad.append(archive(data, ((info, b""),), ("domestique2/update2.sh",)))
        for item in bad:
            with self.assertRaises((Refusal, EOFError, tarfile.TarError, OSError)):
                T.archive_data(item, sidecar(item), "2.0.0")
        with patch.object(T, "PAYLOAD_LIMIT", 10), self.assertRaises(Refusal):
            T.archive_data(raw, sidecar(raw), "2.0.0")
        with self.assertRaises(Refusal):
            package_from_data(data, "2.1.0")

    def test_redirect_deadlines_offline_no_ambient_configuration(self):
        url = T.release_url("2.0.0")
        permitted = "https://release-assets.githubusercontent.com/file?signature=fixture"
        with patch.object(T, "curl_response", side_effect=[
                response(status=302, location=permitted)]*3 + [response(b"ok")]) as curl:
            self.assertEqual(T.fetch_asset(url, 100, {}), b"ok")
            self.assertEqual(curl.call_count, 4)
        for destination in ("http://github.com/file", "https://fixture.invalid/file",
                            "https://user@github.com/file", "https://github.com:443/file"):
            with patch.object(T, "curl_response", return_value=response(
                    status=302, location=destination)) as curl, self.assertRaises(Refusal):
                T.fetch_asset(url, 100, {})
            self.assertEqual(curl.call_count, 1)
        with patch.object(T, "curl_response", return_value=response(
                status=302, location=permitted)) as curl, self.assertRaises(Refusal):
            T.fetch_asset(url, 100, {})
        self.assertEqual(curl.call_count, 4)
        for reply in (response(b"oversize"), b"HTTP/1.1 200 X\r\nContent-Length: 9\r\n\r\nx"):
            with patch.object(T, "curl_response", return_value=reply), self.assertRaises(Refusal):
                T.fetch_asset(url, 3, {})
        with patch.object(T, "curl_response", side_effect=Refusal("offline")), self.assertRaises(Refusal):
            T.fetch_asset(url, 100, {})

    def test_dispatch_authenticated_reads_never_adopt_post_read_mutations(self):
        with V.fixture() as s:
            release, marker = dispatch_marker(s)
            paths = [V.launcher(s), V.root(s) / "state/runtime-manifest",
                     V.root(s) / "active", *(release / leaf for leaf in
                                            ("PACKAGE", "SHA256SUMS", "domestique2.sh"))]
            for path in paths:
                for change in ("inplace-different", "inplace-same", "replace-different",
                               "replace-same", "mtime", "mode", "symlink"):
                    with self.subTest(path=path.name, change=change):
                        original, before = path.read_bytes(), path.stat()
                        witness = {"path": path.name, "change": change}
                        read = D.read
                        mutated = []

                        def read_then_change(p, *args, **kwargs):
                            raw = read(p, *args, **kwargs)
                            if p == path and not mutated:
                                body = (bytes([raw[0] ^ 1]) + raw[1:]
                                        if change.endswith("-different") else raw)
                                if change.startswith("inplace-"):
                                    p.write_bytes(body)
                                elif change.startswith("replace-"):
                                    replacement = s.root / "sources/replacement"
                                    replacement.write_bytes(body)
                                    replacement.chmod(before.st_mode & 0o777)
                                    os.utime(replacement, ns=(before.st_atime_ns, before.st_mtime_ns))
                                    os.replace(replacement, p)
                                elif change == "mtime":
                                    os.utime(p, ns=(before.st_atime_ns, before.st_mtime_ns + 10**9))
                                elif change == "mode":
                                    p.chmod((before.st_mode & 0o777) ^ 0o100)
                                else:
                                    target = s.root / "sources/symlink-target"
                                    target.write_bytes(raw)
                                    p.unlink()
                                    p.symlink_to(target)
                                after = p.lstat()
                                witness.update(before=V.S.attributes(before),
                                               after=V.S.attributes(after),
                                               before_sha256=sha(raw), after_sha256=sha(body))
                                mutated.append(True)
                            return raw

                        with patch.object(D, "read", read_then_change):
                            self.assert_dispatch_refused(s, marker, witness)
                        self.assertEqual(mutated, [True])
                        self.assertNotEqual(witness["before"], witness["after"])
                        if path.is_symlink():
                            path.unlink()
                        path.write_bytes(original)
                        path.chmod(before.st_mode & 0o777)
                        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))

    def test_dispatch_rechecks_before_releasing_version_or_inspection_status(self):
        with V.fixture() as s:
            release, marker = dispatch_marker(s)
            path = release / "domestique2.sh"
            original = path.read_bytes()
            management_read = D.management_read
            for args in (["version"], ["--version"], [], ["inspect", str(s.root / "cohorts")]):
                with self.subTest(args=args):
                    def read_then_change(*params):
                        result = management_read(*params)
                        path.write_bytes(original + b"# changed after validation\n")
                        return result
                    with patch.object(D, "management_read", read_then_change):
                        self.assert_dispatch_refused(s, marker, {"after_chain": args}, args)
                    path.write_bytes(original)

    def test_dispatch_directory_validation_never_adopts_later_metadata(self):
        with V.fixture() as s:
            release, marker = dispatch_marker(s)
            for path in (V.root(s), V.root(s) / "state", V.root(s) / "releases", release):
                for change in ("mtime", "mode"):
                    with self.subTest(path=path.name, change=change):
                        before = path.stat()
                        witness = {"path": str(path.relative_to(V.root(s))), "change": change}
                        snapshot = D.snapshot
                        mutated = []

                        def snapshot_then_change(p, *args, **kwargs):
                            snap = snapshot(p, *args, **kwargs)
                            if p == path and not mutated:
                                if change == "mtime":
                                    os.utime(p, ns=(before.st_atime_ns, before.st_mtime_ns + 10**9))
                                else:
                                    p.chmod(0o750)
                                witness.update(before=V.S.attributes(before),
                                               after=V.S.attributes(p.stat()))
                                mutated.append(True)
                            return snap

                        with patch.object(D, "snapshot", snapshot_then_change):
                            self.assert_dispatch_refused(s, marker, witness)
                        self.assertEqual(mutated, [True])
                        path.chmod(before.st_mode & 0o777)
                        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))

    def test_actual_transport_cumulative_body_budget_boundary_and_overflow(self):
        location = "https://github.com/next"
        with V.fixture() as s:
            wire = curl_stub(s)
            # The independent counterexample: 4 * 8 cannot fit a cap of 8.
            with self.assertRaises(Refusal):
                self.fetch_chain(s, wire, [response(b"abcdefgh", 302, location)] * 3 +
                                 [response(b"abcdefgh")], 8, 2)
            cases = (
                ("boundary", [b"ab", b"cd", b"ef", b"gh"], 8, b"gh"),
                ("plus-one", [b"ab", b"cd", b"ef", b"ghi"], 8, None),
                ("empty-redirects", [b"", b"", b"", b"abcdefgh"], 8, b"abcdefgh"),
                ("empty-final", [b"ab", b"cd", b"efgh", b""], 8, b""),
                ("empty-all", [b"", b"", b"", b""], 0, b""),
                ("zero-plus-one", [b"", b"", b"", b"x"], 0, None),
            )
            for name, bodies, cap, expected in cases:
                with self.subTest(case=name):
                    replies = [response(body, 302, location) for body in bodies[:-1]]
                    replies.append(response(bodies[-1]))
                    if expected is None:
                        with self.assertRaises(Refusal):
                            self.fetch_chain(s, wire, replies, cap, 4)
                    else:
                        self.assertEqual(self.fetch_chain(s, wire, replies, cap, 4), expected)

    def test_actual_transport_redirect_policies_and_header_body_boundaries(self):
        with V.fixture() as s:
            wire = curl_stub(s)
            for status in (301, 302, 303, 307, 308):
                for location in ("https://github.com/next",
                                 "https://release-assets.githubusercontent.com/asset?q=fixture",
                                 "https://objects.githubusercontent.com/asset", "/relative",
                                 "//objects.githubusercontent.com/relative"):
                    with self.subTest(status=status, location=location):
                        self.assertEqual(self.fetch_chain(s, wire, [
                            response(b"ab", status, location), response(b"cd")], 4, 2), b"cd")
            for destination in ("http://github.com/file", "https://fixture.invalid/file",
                                "https://user:credential@github.com/file",
                                "https://github.com:443/file", "https://github.com/file#fragment",
                                "https://github.com/file with space"):
                with self.subTest(destination=destination), self.assertRaises(Refusal):
                    self.fetch_chain(s, wire, [response(b"", 302, destination)], 0, 1)
            with self.assertRaises(Refusal):
                self.fetch_chain(s, wire, [response(b"", 302, "/next")] * 5, 0, 4)
            clock = [10]
            curl_response = T.curl_response

            def response_then_expire(*args):
                result = curl_response(*args)
                clock[0] += 121
                return result

            with patch.object(T.time, "monotonic", lambda: clock[0]), \
                    patch.object(T, "curl_response", response_then_expire), \
                    self.assertRaises(Refusal):
                self.fetch_chain(s, wire, [response(b"", 302, "/next"), response()], 0, 1)
            for reply in (response(b"", 302), response(b"", 304), response(b"", 404),
                          b"HTTP/1.1 302 X\r\nLocation: /next\r\nContent-Length: 1\r\n\r\n",
                          b"HTTP/1.1 200 X\r\nContent-Length: 1\r\n\r\n",
                          b"HTTP/1.1 200 X\r\nContent-Length: 0\r\nContent-Length: 0\r\n\r\n",
                          b"HTTP/1.1 302 X\r\nLocation: /a\r\nLocation: /b\r\n\r\n",
                          b"HTTP/1.1 200 X\r\nmalformed\r\n\r\n"):
                with self.subTest(reply=reply), self.assertRaises(Refusal):
                    self.fetch_chain(s, wire, [reply], 0, 1)
            # Headers split across many small reads still obey their own cap.
            for cap, allowed in ((len(response()), True), (len(response()) - 1, False)):
                with patch.object(T, "META_LIMIT", cap):
                    if allowed:
                        self.assertEqual(self.fetch_chain(s, wire, [response()], 0, 1), b"")
                    else:
                        with self.assertRaises(Refusal):
                            self.fetch_chain(s, wire, [response()], 0, 1)

    def test_actual_gzip_tar_stream_exact_expansion_ceiling(self):
        data = {leaf: b"x" for leaf in LEAVES}
        # Minimal complete tar: directory headers, leaf headers/data, two EOF blocks.
        size = (1 + len(DIRS) + 2 * len(LEAVES) + 2) * 512
        raw = gzip.decompress(archive(data))[:size]
        packed = gzip.compress(raw, mtime=0)
        cases = (
            ("exact", packed, size, True),
            ("overflow-one", packed, size - 1, False),
            ("padding-exact", gzip.compress(raw + bytes(512)), size + 512, True),
            ("padding-overflow", gzip.compress(raw + bytes(512)), size, False),
            ("gzip-member-exact", packed + gzip.compress(bytes(512)), size + 512, True),
            ("gzip-member-overflow-one", packed + gzip.compress(bytes(512)), size + 511, False),
            ("empty-gzip-member", packed + gzip.compress(b""), size, True),
            ("extra-tar-member", packed + packed, size * 2, False),
            ("nonzero-trailer", gzip.compress(raw + b"x" + bytes(511)), size + 512, False),
            ("truncated-gzip", packed[:-1], size, False),
            ("missing-gzip-trailer", packed[:-8], size, False),
            ("bad-gzip-crc", packed[:-8] + bytes([packed[-8] ^ 1]) + packed[-7:], size, False),
            ("truncated-tar-eof", gzip.compress(raw[:-512]), size, False),
            ("truncated-tar-data", gzip.compress(raw[:-(3 * 512)]), size, False),
        )
        gzip_file = T.gzip.GzipFile
        for name, compressed, cap, allowed in cases:
            with self.subTest(case=name), patch.object(T, "PAYLOAD_LIMIT", cap):
                streams, requests, consumed = [], [], []

                class MeteredGzip(gzip_file):
                    def read(self, amount=-1):
                        requests.append(amount)
                        result = super().read(amount)
                        consumed.append(len(result))
                        return result

                def open_stream(*args, **kwargs):
                    stream = MeteredGzip(*args, **kwargs)
                    streams.append(stream)
                    return stream

                with patch.object(T.gzip, "GzipFile", open_stream):
                    if allowed:
                        self.assertEqual(T.archive_data(compressed, sidecar(compressed), "2.0.0"),
                                         data)
                    else:
                        with self.assertRaises((Refusal, EOFError, OSError, tarfile.TarError)):
                            T.archive_data(compressed, sidecar(compressed), "2.0.0")
                print("EXPANSION_WITNESS=" + json.dumps({
                    "case": name, "cap": cap, "accepted": allowed,
                    "requests": requests, "returned_bytes": consumed,
                    "streams_closed": all(stream.closed for stream in streams),
                }, sort_keys=True), flush=True)
                self.assertEqual(requests, [cap + 1])
                self.assertLessEqual(sum(consumed), cap + 1)
                self.assertTrue(all(stream.closed for stream in streams))
                if "overflow" in name:
                    self.assertEqual(consumed, [cap + 1])

    def test_small_bounded_stream_still_requires_closed_tar_inventory(self):
        data = {leaf: b"x" for leaf in LEAVES}
        for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.CHRTYPE, tarfile.BLKTYPE,
                     tarfile.FIFOTYPE, tarfile.DIRTYPE, tarfile.XHDTYPE, tarfile.XGLTYPE,
                     tarfile.GNUTYPE_LONGNAME, tarfile.GNUTYPE_LONGLINK, tarfile.GNUTYPE_SPARSE):
            with self.subTest(kind=kind):
                info = tarfile.TarInfo("domestique2/update2.sh")
                info.type = kind
                packed = archive(data, ((info, b""),), ("domestique2/update2.sh",))
                with patch.object(T, "PAYLOAD_LIMIT", len(gzip.decompress(packed))), \
                        self.assertRaises((Refusal, tarfile.TarError)):
                    T.archive_data(packed, sidecar(packed), "2.0.0")
        for name, omit in (("domestique2/PACKAGE", ()), ("domestique2/extra", ()),
                           ("domestique2/../escape", ()), ("/absolute", ()),
                           ("domestique2/PACKAGE", ("domestique2/SHA256SUMS",))):
            with self.subTest(name=name, omit=omit):
                packed = archive(data, ((tarfile.TarInfo(name), b""),), omit)
                with patch.object(T, "PAYLOAD_LIMIT", len(gzip.decompress(packed))), \
                        self.assertRaises(Refusal):
                    T.archive_data(packed, sidecar(packed), "2.0.0")

    def test_publication_failure_preserves_old_selection_and_pending(self):
        with V.fixture() as s:
            first = V.source(s)
            self.assertEqual(run(s, "--source", first).returncode, 0)
            active = (V.root(s) / "active").read_bytes()
            launcher = V.launcher(s).read_bytes()
            second = V.source(s, "2.1.0", "second")
            def hook(event, path):
                if event == "before-rename-manifest":
                    raise OSError("injected publication failure")
            with self.assertRaises(P.PublicationFailure) as failure:
                P.publish_local(second, s.env, hook=hook)
            self.assertEqual(failure.exception.recovery, "pending")
            self.assertEqual((V.root(s) / "active").read_bytes(), active)
            self.assertEqual(V.launcher(s).read_bytes(), launcher)
            out = s.run([V.launcher(s), "version"], check=False)
            self.assertEqual(out.returncode, 1)
            self.assertIn(active[8:-1], out.stdout)
            self.assertIn(b"recovery=unknown", out.stdout)
            before = s.snapshot()
            self.assertEqual(run(s, "--source", first).returncode, 1)
            self.assertEqual(s.snapshot(), before)

    def test_actual_development_prototype_is_refused_not_migrated(self):
        with V.fixture() as s:
            old = s.root / "sources/prototype"
            old.mkdir()
            for name in ("safe", "package", "records", "journal", "runtime"):
                (old / (name + ".py")).write_bytes(s.run([
                    "git", "-C", F.ROOT, "show", "8b48b6a:v2/" + name + ".py"]).stdout)
            with patch.object(B, "SOURCE", old):
                program = B.bundle(("safe", "package", "records", "journal", "runtime"))
            def prototype(root, home):
                # 8b48b6a's exact wrapper predates the fresh dispatcher's -p.
                return B.python_shell(program +
                                      f"\nsys.exit(launcher_main({str(root)!r}, {str(home)!r}))\n"
                                      ).replace(b"#!/bin/bash -p\n", b"#!/bin/bash\n", 1)
            source = V.source(s)
            with patch.object(P, "launcher_bytes", prototype):
                P.publish_local(source, s.env)
            self.assertEqual(s.run([V.launcher(s), "version"]).returncode, 0)
            before = s.snapshot()
            self.assertEqual(run(s, "--source", source).returncode, 1)
            self.assertEqual(s.snapshot(), before)
            self.assertEqual(s.run([V.launcher(s), "version"]).returncode, 0)


if __name__ == "__main__":
    unittest.main()
