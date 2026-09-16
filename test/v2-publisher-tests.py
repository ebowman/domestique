"""Actual format-2 publisher/API scope, not retained-preview execution evidence."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

import inspect_fixture as F
sys.path.insert(0, str(F.ROOT))
from v2.build import emit_package, launcher_bytes, package_data
from v2.factories import LOADER
from v2.package import LEAVES, payload_mode, verify_package
from v2.publisher import PublicationFailure, publish_local
from v2.records import parse_record, published_read
from v2.safe import Refusal, sha
import v2.publisher as P
import v2.safe as S


@contextmanager
def fixture():
    # Real machine roots cannot be hidden inside this checkout by a Git ceiling.
    # Reuse the existing identity/snapshot/cleanup/stdio harness outside Git.
    mkdtemp = tempfile.mkdtemp
    with patch.object(F.tempfile, "mkdtemp", lambda **kw: mkdtemp(
            prefix=kw["prefix"], dir=Path("/tmp").resolve())):
        s = F.FixtureSession()
    print("V2_FIXTURE=" + json.dumps({"root": str(s.root), "identity": s.identity}), flush=True)
    try:
        with patch.dict(os.environ, s.env, clear=True):
            yield s
        s.assert_no_calls()
        s.pristine = s.snapshot()
        s.clean()
        print("V2_CLEANED=" + str(s.root), flush=True)
    except BaseException:
        print("V2_RETAINED=" + json.dumps({"root": str(s.root), "identity": s.identity}), flush=True)
        raise


def source(s, version="2.0.0", name="local package ' \""):
    p = s.root / "sources" / name
    emit_package(p, version)
    return p


def root(s):
    return Path(s.env["DOMESTIQUE_HOME"]) / "v2"


def launcher(s):
    return Path(s.env["HOME"]) / ".local/bin/domestique2"


def protected(s):
    return {p: e for p, e in s.snapshot().items() if p.split("/")[0] in ("home", "global", "cohorts")}


def rewrite_sums(p):
    (p / "SHA256SUMS").write_bytes(b"".join(
        (sha((p / leaf).read_bytes()) + "  " + leaf + "\n").encode()
        for leaf in LEAVES if leaf != "SHA256SUMS"))


class PublisherTests(unittest.TestCase):
    def test_current_registration_and_source_fingerprints_are_actual_v2(self):
        import acceptance as A
        hashes = A.provenance(A.Control(30))["source_sha256"]
        for name in ("v2-publisher-tests.py", "v2-records-tests.py"):
            self.assertEqual(A.CURRENT.count(name), 1)
            self.assertNotIn(name, A.RETAINED_PREVIEW)
            self.assertIn("test/" + name, hashes)
        for p in (F.ROOT / "v2").rglob("*"):
            if p.is_file() and "__pycache__" not in str(p):
                self.assertEqual(hashes[str(p.relative_to(F.ROOT))], sha(p.read_bytes()))

    def test_fresh_exact_package_manifest_modes_and_noop(self):
        with fixture() as s:
            p = source(s)
            expected = verify_package(p)
            result = publish_local(p, s.env)
            self.assertEqual(result, dict(runtime=expected["release"], recovery="none",
                                          changed=True, dry_run=False))
            release = root(s) / "releases" / result["runtime"]
            self.assertEqual(verify_package(release, installed=True)["data"], expected["data"])
            self.assertEqual(len(LEAVES), 12)
            self.assertEqual({str(x.relative_to(release)) for x in release.rglob("*") if x.is_file()},
                             set(LEAVES))
            raw = (root(s) / "state/runtime-manifest").read_bytes()
            rows = parse_record(raw)
            fields = dict(rows[:12])
            self.assertEqual(fields["format"], "2")
            self.assertEqual(fields["scope"], "runtime")
            self.assertEqual(fields["core_dev"], str(root(s).stat().st_dev))
            self.assertEqual(fields["core_ino"], str(root(s).stat().st_ino))
            self.assertEqual(fields["owner_uid"], str(os.getuid()))
            self.assertEqual(fields["launcher_path"], str(launcher(s)))
            self.assertIn(("source_kind", "local"), rows)
            self.assertIn(("official_version", "-"), rows)
            pairs = [v for k, v in rows if k == "created"]
            self.assertEqual(len(pairs), 13)
            self.assertEqual(pairs, [v for k, v in rows if k == "baseline"])
            self.assertEqual(launcher(s).read_bytes(), launcher_bytes(root(s), Path(s.env["HOME"])))
            for path in root(s).rglob("*"):
                mode = 0o700 if path.is_dir() else payload_mode(str(path.relative_to(release))) \
                    if release in path.parents else 0o600
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), mode)
            self.assertFalse((root(s) / "bin").exists())
            self.assertEqual(sorted(p.name for p in (root(s) / "state").iterdir()), ["runtime-manifest"])
            before = protected(s)
            self.assertFalse(publish_local(p, s.env)["changed"])
            self.assertEqual(protected(s), before)
            out = s.run([launcher(s), "version"])
            self.assertIn(result["runtime"].encode(), out.stdout)
            self.assertIn(b"recovery=none", out.stdout)
            self.assertEqual(protected(s), before)

    def test_deterministic_bundle_three_inert_schemas_and_one_policy(self):
        a, b = package_data("2.4.3"), package_data("2.4.3")
        self.assertEqual(a, b)
        for provider in F.PROVIDERS:
            leaves = json.loads(a[f"adapters/{provider}.templates"])
            self.assertEqual(len(leaves), 6 if provider == "codex" else 5)
            for path, body in leaves.items():
                self.assertIn("domestique-v2-" + provider, path)
                if path.endswith("openai.yaml"):
                    self.assertEqual(body, "policy:\n  allow_implicit_invocation: false\n")
                else:
                    self.assertIn(LOADER, body)
                    self.assertNotIn("model =", body)
                    self.assertNotIn("tools:", body)
                    if path.endswith(".toml"):
                        self.assertTrue(body.startswith('name = "domestique-v2-codex-'))
                    else:
                        self.assertTrue(body.startswith("---\nname: domestique-v2-"))
                self.assertNotIn("config", path)
        self.assertEqual(sum("orchestrator.md" in x for x in a), 1)
        # The management payload now embeds the unchanged legacy inspector.
        # Only inspection understands format 1; no legacy writer is bundled.
        self.assertNotIn(b"format=1", b"".join(v for k, v in a.items()
                                             if k != "domestique2.sh"))
        self.assertNotIn(b"emit_policy()", a["domestique2.sh"])

    def test_provider_independence_native_and_three_git_projects_untouched(self):
        with fixture() as s:
            projects = [s.project(p, git=True) for p in ("A", "B", "C")]
            for p in projects:
                (p / "user.txt").write_text(F.SECRET)
            for d in (".claude", ".agents", ".codex", ".copilot", ".github"):
                p = Path(s.env["HOME"]) / d
                p.mkdir()
                (p / "existing-user-data").write_text(F.SECRET)
            # Old S definitions are left intact, not adopted or certified quiet.
            old = Path(s.env["DOMESTIQUE_HOME"])
            old.mkdir()
            (old / "active").write_text("old-preview-active\n")
            (old / "bin").mkdir()
            (old / "bin/resolve-core").write_text(F.SECRET)
            p = source(s)
            before = protected(s)
            result = publish_local(p, s.env)
            after = protected(s)
            excluded = ("global/core/v2", "home/.local")
            def old_only(tree):
                return {k: v for k, v in tree.items() if not k.startswith(excluded)
                        and k not in ("home", "global/core")}
            self.assertEqual(old_only(before), old_only(after))
            self.assertNotIn("quiet", str(result))

    def test_dryrun_fresh_and_update_zero_destination_mutations_no_execution(self):
        with fixture() as s:
            p = source(s)
            marker = s.root / "calls/candidate"
            (p / "domestique2.sh").write_text(f"#!/bin/bash\ntouch '{marker}'\n")
            rewrite_sums(p)
            before = protected(s)
            self.assertTrue(publish_local(p, s.env, dry_run=True)["changed"])
            self.assertEqual(before, protected(s))
            self.assertFalse(marker.exists())
            publish_local(p, s.env)
            second = source(s, "2.1.0", "next")
            before = protected(s)
            publish_local(second, s.env, dry_run=True)
            self.assertEqual(before, protected(s))
            self.assertFalse(marker.exists())

    def test_update_retains_old_release_bytes_inode_and_local_reselection(self):
        with fixture() as s:
            p = source(s)
            first = publish_local(p, s.env)["runtime"]
            old = root(s) / "releases" / first
            before = {str(x.relative_to(old)): (x.read_bytes(), x.stat().st_ino)
                      for x in old.rglob("*") if x.is_file()}
            launch = launcher(s).stat()
            second = source(s, "2.0.0", "same version different local digest")
            (second / "roles/goal.md").write_text("Different development policy\n")
            rewrite_sums(second)
            next_r = publish_local(second, s.env)["runtime"]
            self.assertNotEqual(first, next_r)
            self.assertEqual(before, {str(x.relative_to(old)): (x.read_bytes(), x.stat().st_ino)
                                     for x in old.rglob("*") if x.is_file()})
            self.assertEqual(launch, launcher(s).stat())
            self.assertEqual(publish_local(p, s.env)["runtime"], first)
            self.assertTrue((root(s) / "releases" / next_r).is_dir())

    def test_mutable_source_after_verified_is_never_executed_or_reread(self):
        with fixture() as s:
            p = source(s)
            expected = verify_package(p)
            def hook(event, path):
                if event == "verified-source":
                    (path / "domestique2.sh").write_text("# candidate altered after snapshot\n")
            result = publish_local(p, s.env, hook=hook)
            self.assertEqual(result["runtime"], expected["release"])
            self.assertEqual(verify_package(root(s) / "releases" / result["runtime"])["data"],
                             expected["data"])

    def test_runtime_all_execution_bypasses_refuse_before_body(self):
        with fixture() as s:
            result = publish_local(source(s), s.env)
            r = root(s) / "releases" / result["runtime"]
            for command in (["enable"], ["read"], ["start"], ["route"], ["bootstrap"],
                            ["beads"], ["bind"], ["goal"]):
                for exe in (launcher(s), r / "bin/resolve-core", r / "domestique2.sh", r / "update2.sh"):
                    out = s.run([exe, *command], check=False)
                    expected = 1 if command == ["enable"] or exe in (
                        r / "bin/resolve-core", r / "update2.sh") else 2
                    self.assertEqual((out.returncode, out.stdout), (expected, b""))
            env = dict(s.env, DOMESTIQUE_HOME=str(s.root / "alternate"))
            self.assertEqual(s.run([launcher(s), "version"], env=env, check=False).returncode, 1)
            (root(s) / "active").unlink()
            self.assertEqual(s.run([launcher(s), "version"], check=False).returncode, 1)

    def test_default_xdg_and_literal_custom_roots(self):
        for layout in ("default", "xdg", "literal"):
            with self.subTest(layout=layout), fixture() as s:
                env = dict(s.env)
                if layout == "default":
                    env.pop("DOMESTIQUE_HOME")
                    env.pop("XDG_STATE_HOME")
                    base = Path(env["HOME"]) / ".local/state/domestique"
                elif layout == "xdg":
                    env.pop("DOMESTIQUE_HOME")
                    base = Path(env["XDG_STATE_HOME"]) / "domestique"
                else:
                    env["DOMESTIQUE_HOME"] = str(s.root / "global/base ' \" \\ : space")
                    base = Path(env["DOMESTIQUE_HOME"])
                result = publish_local(source(s), env)
                self.assertTrue((base / "v2/releases" / result["runtime"]).is_dir())
                self.assertEqual(s.run([launcher(s), "version"], env=env).returncode, 0)

    def test_invalid_input_complete_inventory_abi_digest_and_limits(self):
        mutations = {
            "major": lambda p: (p / "PACKAGE").write_bytes((p / "PACKAGE").read_bytes().replace(b"major=2", b"major=1")),
            "abi": lambda p: (p / "PACKAGE").write_bytes((p / "PACKAGE").read_bytes().replace(b"helper_abi=2", b"helper_abi=3")),
            "metadata": lambda p: (p / "PACKAGE").write_bytes((p / "PACKAGE").read_bytes() + b"unknown=x\n"),
            "meta-size": lambda p: (p / "PACKAGE").write_bytes(b"x" * 1048577),
            "meta-line": lambda p: (p / "PACKAGE").write_bytes(b"x" * 8192 + b"\n"),
            "meta-lines": lambda p: (p / "PACKAGE").write_bytes(b"x\n" * 16385),
            "extra": lambda p: (p / "extra").write_text("extra"),
            "extra-empty-dir": lambda p: (p / "extra-dir").mkdir(),
            "missing": lambda p: (p / "roles/goal.md").unlink(),
            "digest": lambda p: (p / "roles/goal.md").write_text("bad"),
            "duplicate-sums": lambda p: (p / "SHA256SUMS").write_bytes((p / "SHA256SUMS").read_bytes() * 2),
            "traversal-sums": lambda p: (p / "SHA256SUMS").write_bytes((p / "SHA256SUMS").read_bytes().replace(b"PACKAGE", b"../PACKAGE")),
            "hardlink": lambda p: os.link(p / "roles/goal.md", p.parent / "link"),
            "symlink": lambda p: ((p / "roles/goal.md").unlink(), (p / "roles/goal.md").symlink_to("reviewer.md")),
            "fifo": lambda p: ((p / "roles/goal.md").unlink(), os.mkfifo(p / "roles/goal.md")),
            "oversize": lambda p: truncate(p / "roles/goal.md", 64 * 1048576 + 1),
            "aggregate": lambda p: truncate(p / "roles/goal.md", 64 * 1048576),
        }
        for name, mutate in mutations.items():
            with self.subTest(case=name), fixture() as s:
                p = source(s)
                mutate(p)
                before = protected(s)
                with self.assertRaises((Refusal, OSError)):
                    publish_local(p, s.env)
                self.assertEqual(before, protected(s))
                print("V2_INVALID_CASE=" + name)

    def test_missing_empty_old_scripts_and_source_symlink_refuse_before_publication(self):
        with fixture() as s:
            empty = s.root / "sources/empty"
            empty.mkdir()
            p = source(s)
            alias = s.root / "sources/alias"
            alias.symlink_to(p)
            for invalid in (s.root / "missing", empty, F.ROOT / "domestique.sh",
                            F.ROOT / "domestique2.sh", alias, F.ROOT):
                before = protected(s)
                with self.assertRaises((Refusal, OSError)):
                    publish_local(invalid, s.env)
                self.assertEqual(before, protected(s))

    def test_destination_unknown_edited_pending_collision_and_path_refusals(self):
        for case in ("unknown-root", "unowned-matching-launcher", "edited-launcher",
                     "edited-release", "old-preview", "extra-runtime", "unowned-release", "orphan",
                     "retire-pending", "relative", "control", "symlink", "hardlink",
                     "native", "git", "launcher-git", "unsafe-mode", "missing-capability"):
            with self.subTest(case=case), fixture() as s:
                p = source(s)
                env = dict(s.env)
                if case in ("edited-launcher", "edited-release", "extra-runtime", "unowned-release", "orphan", "retire-pending", "hardlink"):
                    result = publish_local(p, env)
                if case in ("unknown-root", "old-preview"):
                    root(s).mkdir(parents=True)
                    if case == "old-preview":
                        (root(s) / "manifest").write_text("format=1\n")
                elif case == "unowned-matching-launcher":
                    launcher(s).parent.mkdir(parents=True)
                    launcher(s).write_bytes(launcher_bytes(root(s), Path(env["HOME"])))
                    launcher(s).chmod(0o755)
                elif case == "edited-launcher":
                    launcher(s).write_text("# edited\n")
                elif case == "edited-release":
                    (root(s) / "releases" / result["runtime"] / "roles/goal.md").write_text("edited")
                elif case == "extra-runtime":
                    (root(s) / "unowned").mkdir()
                elif case == "unowned-release":
                    other = source(s, "2.1.0", "unowned candidate")
                    rid = verify_package(other)["release"]
                    emit_package(root(s) / "releases" / rid, "2.1.0")
                    p = other
                elif case == "orphan":
                    (root(s) / "state/previous").write_text("orphan")
                elif case == "retire-pending":
                    (root(s) / "state/retire-global").mkdir()
                    (root(s) / "state/retire-global/pending").write_text("pending")
                elif case == "relative":
                    env["DOMESTIQUE_HOME"] = "relative"
                elif case == "control":
                    env["DOMESTIQUE_HOME"] = str(s.root / "global") + "/bad\nroot"
                elif case == "symlink":
                    Path(env["DOMESTIQUE_HOME"]).symlink_to(s.root / "tmp")
                elif case == "hardlink":
                    os.link(launcher(s), s.root / "sources/launcher-link")
                elif case == "native":
                    env["DOMESTIQUE_HOME"] = str(Path(env["HOME"]) / ".claude/state")
                elif case == "git":
                    repo = s.project("machine-git", git=True)
                    env["DOMESTIQUE_HOME"] = str(repo / "state")
                    env["GIT_CEILING_DIRECTORIES"] = str(repo)
                    env["GIT_DIR"] = str(s.root / "hide-real-git")
                elif case == "launcher-git":
                    s.run(["git", "init", env["HOME"]])
                elif case == "unsafe-mode":
                    (s.root / "global").chmod(0o777)
                elif case == "missing-capability":
                    env["PATH"] = str(s.root / "bin")
                before = protected(s)
                with self.assertRaises((Refusal, OSError)):
                    publish_local(p, env)
                self.assertEqual(before, protected(s))
                print("V2_DESTINATION_CASE=" + case)

    def test_preflight_race_refuses_without_adopting_identical_leaf(self):
        with fixture() as s:
            p = source(s)
            def hook(event, path):
                if event == "preflight":
                    launcher(s).parent.mkdir(parents=True)
                    launcher(s).write_bytes(launcher_bytes(root(s), Path(s.env["HOME"])))
                    launcher(s).chmod(0o755)
            with self.assertRaises(Refusal):
                publish_local(p, s.env, hook=hook)
            self.assertFalse(root(s).exists())

    def test_fresh_git_boundary_after_preflight_with_existing_parents(self):
        for mode in ("install", "dry-run", "noop"):
            with self.subTest(mode=mode), fixture() as s:
                p = source(s)
                launcher(s).parent.mkdir(parents=True)
                if mode == "noop":
                    publish_local(p, s.env)
                observed = []
                def hook(event, path):
                    if event == "preflight":
                        s.run(["git", "init", s.env["HOME"]])
                        observed.append(protected(s))
                with self.assertRaises(Refusal):
                    publish_local(p, s.env, dry_run=mode == "dry-run", hook=hook)
                self.assertEqual(len(observed), 1)
                self.assertEqual(observed[0], protected(s))
                if mode != "noop":
                    self.assertFalse(root(s).exists())
                    self.assertFalse(launcher(s).exists())
                print("V2_FRESH_GIT=" + mode + " zero-additional-writes")

    def test_boundary_mutations_at_every_publication_phase_stop_all_writes(self):
        events = ("before-claim", "claim", "pending", "previous", "published",
                  "before-release", "written-release", "after-release",
                  "before-launcher", "before-rename-launcher", "written-launcher",
                  "after-launcher", "before-manifest", "written-manifest",
                  "after-manifest", "before-active", "before-rename-active",
                  "written-active", "after-active", "complete",
                  "before-clear-published", "clear-published", "clear-previous",
                  "clear-pending")
        for event in events:
            with self.subTest(event=event), fixture() as s:
                p = source(s)
                launcher(s).parent.mkdir(parents=True)
                observed = []
                def hook(name, path):
                    if name == event and not observed:
                        s.run(["git", "init", s.env["HOME"]])
                        # Include temporary afterimages, not just final leaves.
                        observed.append(s.snapshot())
                with self.assertRaises(Refusal) as error:
                    publish_local(p, s.env, hook=hook)
                self.assertEqual(len(observed), 1)
                self.assertEqual(observed[0], s.snapshot())
                if event != "before-claim":
                    self.assertIsInstance(error.exception, PublicationFailure)
                print("V2_BOUNDARY_PHASE=" + event + " zero-additional-writes")

    def test_update_boundary_forms_roots_redirects_and_old_selection(self):
        cases = ("gitfile", "worktree", "bare", "root-git", "release-git",
                 "native-redirect", "identity", "ancestor-git")
        for case in cases:
            with self.subTest(case=case), fixture() as s:
                old = publish_local(source(s), s.env)["runtime"]
                p = source(s, "2.1.0", "next")
                repo = s.project("git-metadata", git=True) if case in ("gitfile", "worktree") else None
                if case == "worktree":
                    s.run(["git", "-C", repo, "-c", "user.name=Fixture",
                           "-c", "user.email=fixture@invalid", "commit", "--allow-empty", "-m", "fixture"])
                    work = s.root / "sources/worktree"
                    s.run(["git", "-C", repo, "worktree", "add", str(work)])
                observed = []
                event = "written-release" if case == "release-git" else "before-rename-active"
                def hook(name, path):
                    if name != event or observed:
                        return
                    home = Path(s.env["HOME"])
                    if case == "gitfile":
                        (home / ".git").write_text("gitdir: " + str(repo / ".git") + "\n")
                    elif case == "worktree":
                        (home / ".git").write_bytes((work / ".git").read_bytes())
                    elif case == "bare":
                        s.run(["git", "init", "--bare", str(root(s))])
                    elif case in ("root-git", "ancestor-git", "release-git"):
                        target = root(s) if case == "root-git" else root(s).parent \
                            if case == "ancestor-git" else path
                        s.run(["git", "init", str(target)])
                    else:
                        parent = launcher(s).parent
                        destination = home / ".claude" if case == "native-redirect" else home / "saved-bin"
                        parent.rename(destination)
                        if case == "native-redirect":
                            parent.symlink_to(destination)
                        else:
                            parent.mkdir()
                    observed.append(s.snapshot())
                with self.assertRaises(PublicationFailure) as error:
                    publish_local(p, s.env, hook=hook)
                self.assertEqual(len(observed), 1)
                self.assertEqual(observed[0], s.snapshot())
                self.assertEqual((root(s) / "active").read_bytes(), ("release=" + old + "\n").encode())
                if case not in ("native-redirect", "identity"):
                    self.assertEqual(error.exception.selected, old)
                print("V2_BOUNDARY_FORM=" + case + " old-active-preserved zero-additional-writes")

    def test_staging_boundary_change_preserves_staging_without_cleanup(self):
        with fixture() as s:
            p = source(s)
            observed = []
            def hook(event, path):
                if event == "stage":
                    s.run(["git", "init", str(path)])
                    observed.append(s.snapshot())
            with self.assertRaises(Refusal):
                publish_local(p, s.env, hook=hook)
            self.assertEqual(observed, [s.snapshot()])
            self.assertFalse(root(s).exists())

    def test_changed_afterimage_is_preserved_not_cleanup_authority(self):
        cases = [(False, c) for c in ("different", "identical", "edited", "mode",
                                      "symlink", "hardlink", "git", "native", "root")]
        cases += [(True, c) for c in ("identical", "edited")]
        for update, case in cases:
            with self.subTest(update=update, case=case), fixture() as s:
                old = publish_local(source(s), s.env)["runtime"] if update else "unavailable"
                package = source(s, "2.1.0", "candidate")
                tracked, observed = [], []
                original = P.tempfile.mkstemp
                def capture(*args, **kwargs):
                    fd, name = original(*args, **kwargs)
                    tracked.append(Path(name))
                    return fd, name
                def hook(event, path):
                    if event != "before-rename-active":
                        return
                    tmp = tracked[-1]
                    before = tmp.lstat()
                    raw = tmp.read_bytes()
                    saved = s.root / "sources/retained-original-afterimage"
                    if case in ("edited", "mode", "hardlink"):
                        if case == "edited":
                            tmp.write_bytes(b"TEST-OWNED-EDIT\n")
                        elif case == "mode":
                            tmp.chmod(0o640)
                        else:
                            os.link(tmp, saved)
                    elif case == "root":
                        root(s).rename(s.root / "sources/retained-runtime")
                        root(s).mkdir(mode=0o700)
                        tmp.write_bytes(raw)
                        tmp.chmod(0o600)
                    else:
                        tmp.rename(saved)
                        if case == "symlink":
                            tmp.symlink_to(saved)
                        else:
                            tmp.write_bytes(raw if case == "identical" else b"TEST-OWNED-REPLACEMENT\n")
                            tmp.chmod(0o600)
                        if case == "git":
                            s.run(["git", "init", s.env["HOME"]])
                        elif case == "native":
                            native = Path(s.env["HOME"]) / ".claude"
                            launcher(s).parent.rename(native)
                            launcher(s).parent.symlink_to(native)
                    after = tmp.lstat()
                    if case in ("edited", "mode", "hardlink"):
                        self.assertEqual(before.st_ino, after.st_ino)
                    else:
                        self.assertNotEqual(before.st_ino, after.st_ino)
                    observed.append(s.snapshot())
                    print("V2_AFTERIMAGE_WITNESS=" + json.dumps({
                        "case": case, "update": update, "path": str(tmp),
                        "original": S.attributes(before), "replacement": S.attributes(after),
                        "bytes_sha256": sha(os.fsencode(os.readlink(tmp)) if tmp.is_symlink()
                                            else tmp.read_bytes())}), flush=True)
                with patch.object(P.tempfile, "mkstemp", capture):
                    with self.assertRaises(PublicationFailure) as error:
                        publish_local(package, s.env, hook=hook)
                self.assertEqual(observed, [s.snapshot()])
                self.assertTrue(os.path.lexists(tracked[-1]))
                self.assertIsInstance(error.exception.__cause__, Refusal)
                expected = "unavailable" if case in ("root", "native") else old
                self.assertEqual(error.exception.selected, expected)
                self.assertEqual(error.exception.recovery, "unknown" if case in ("root", "native")
                                 else "pending")
                actual_root = s.root / "sources/retained-runtime" if case == "root" else root(s)
                if update:
                    self.assertEqual((actual_root / "active").read_bytes(),
                                     ("release=" + old + "\n").encode())
                else:
                    self.assertFalse((actual_root / "active").exists())
                self.assertNotIn(b"phase=active\n", (actual_root / "state/published").read_bytes())
                print("V2_AFTERIMAGE_PRESERVED=" + case + " " + str(update), flush=True)
                # Every replacement and saved original is explicitly test-owned.
                # fixture() snapshots/qualifies those exact entries before clean.

    def test_afterimage_creation_exception_has_no_invented_cleanup_witness(self):
        with fixture() as s:
            package = source(s)
            original = P.tempfile.mkstemp
            observed, paths = [], []
            failure = OSError("test creation failed before returning ownership witness")
            def failed(*args, **kwargs):
                fd, name = original(*args, **kwargs)
                os.close(fd)
                p = Path(name)
                p.write_bytes(b"TEST-OWNED-UNKNOWN-CREATION\n")
                paths.append(p)
                observed.append(s.snapshot())
                raise failure
            with patch.object(P.tempfile, "mkstemp", failed):
                with self.assertRaises(PublicationFailure) as error:
                    publish_local(package, s.env)
            self.assertIs(error.exception.__cause__, failure)
            self.assertEqual(observed, [s.snapshot()])
            self.assertTrue(paths[0].exists())
            self.assertFalse(launcher(s).exists())
            self.assertFalse((root(s) / "state/runtime-manifest").exists())

    def test_link_cleanup_requires_original_inode_bytes_mode_and_boundary(self):
        for case in ("identical-replacement", "edited", "mode", "git"):
            with self.subTest(case=case), fixture() as s:
                package = source(s)
                original = os.link
                observed, paths = [], []
                def linked(src, dst, **kwargs):
                    original(src, dst, **kwargs)
                    tmp = Path(src)
                    paths.append(tmp)
                    if case == "identical-replacement":
                        raw = tmp.read_bytes()
                        tmp.rename(s.root / "sources/retained-linked-afterimage")
                        tmp.write_bytes(raw)
                        tmp.chmod(0o755)
                    elif case == "edited":
                        tmp.write_bytes(b"TEST-OWNED-LINK-EDIT\n")
                    elif case == "mode":
                        tmp.chmod(0o700)
                    else:
                        s.run(["git", "init", s.env["HOME"]])
                    observed.append(s.snapshot())
                with patch.object(P.os, "link", linked):
                    with self.assertRaises(PublicationFailure):
                        publish_local(package, s.env)
                self.assertEqual(observed, [s.snapshot()])
                self.assertTrue(paths[0].exists())
                self.assertFalse((root(s) / "state/runtime-manifest").exists())
                self.assertNotRegex((root(s) / "state/published").read_bytes(),
                                    rb"phase=launcher\nitem=[0-9]+\nresult=created\n")
                print("V2_LINK_PRESERVED=" + case, flush=True)

    def test_shared_writer_boundary_refusal_has_no_close_writes_or_cleanup(self):
        for kind in ("staging", "journal-header", "journal-append", "active-afterimage"):
            for portion in ("before", "partial", "full"):
                with self.subTest(kind=kind, portion=portion), fixture() as s:
                    package = source(s)
                    original = S.checked_write
                    original_write, original_unlink = os.write, Path.unlink
                    observed, witness, forbidden = [], {}, []
                    invalid = False
                    def wrapped(fd, path, data, before, guard):
                        nonlocal invalid
                        match = ((kind == "staging" and "domestique-v2-stage-" in str(path)) or
                                 (kind == "journal-header" and path == root(s) / "state/published"
                                  and not before[1]) or
                                 (kind == "journal-append" and path == root(s) / "state/published"
                                  and bool(before[1])) or
                                 (kind == "active-afterimage" and path.parent == root(s)
                                  and path.name.startswith(".publication-")))
                        if not data or not match or witness:
                            return original(fd, path, data, before, guard)
                        calls = 0
                        def checked():
                            nonlocal calls, invalid
                            calls += 1
                            if calls == (1 if portion == "before" else 2):
                                s.run(["git", "init", s.env["HOME"]])
                                witness.update(path=str(path), before_size=len(before[1]),
                                               at_refusal=path.stat().st_size)
                                observed.append(s.snapshot())
                                invalid = True
                            guard()
                        def write(target, raw):
                            if invalid:
                                forbidden.append("write")
                            return original_write(target, raw[:7] if portion == "partial" else raw)
                        with patch.object(S.os, "write", write):
                            return original(fd, path, data, before, checked)
                    def unlink(path, *args, **kwargs):
                        if invalid:
                            forbidden.append("unlink")
                        return original_unlink(path, *args, **kwargs)
                    with patch.object(S, "checked_write", wrapped), \
                            patch.object(P, "checked_write", wrapped), \
                            patch.object(Path, "unlink", unlink):
                        with self.assertRaises(Refusal):
                            publish_local(package, s.env)
                    self.assertEqual(len(observed), 1)
                    self.assertEqual(observed, [s.snapshot()])
                    self.assertEqual(forbidden, [])
                    witness["after_close"] = Path(witness["path"]).stat().st_size
                    self.assertEqual(witness["at_refusal"], witness["after_close"])
                    if portion != "full":
                        self.assertEqual(witness["at_refusal"] - witness["before_size"],
                                         0 if portion == "before" else 7)
                    self.assertFalse((root(s) / "active").exists())
                    print("V2_NO_LATENT_WRITE=" + json.dumps(
                        dict(witness, kind=kind, portion=portion, forbidden=forbidden)), flush=True)


class WriteTests(unittest.TestCase):
    def test_exclusive_fourth_guard_exact_size_witness(self):
        with fixture() as s:
            target = Path(s.env["HOME"]) / "exclusive-probe"
            sizes, calls, forbidden = [], [], []
            real_write, real_unlink = os.write, Path.unlink
            def guard():
                calls.append(1)
                if len(calls) == 4:
                    s.run(["git", "init", s.env["HOME"]])
                    sizes.append(target.stat().st_size)
                P.boundary((target,), s.env)
            def write(fd, data):
                if sizes:
                    forbidden.append("write")
                return real_write(fd, data)
            def unlink(path, *args, **kwargs):
                if sizes:
                    forbidden.append("unlink")
                return real_unlink(path, *args, **kwargs)
            raw = b"format=2\nscope=published\n"
            with patch.object(S.os, "write", write), patch.object(Path, "unlink", unlink):
                with self.assertRaisesRegex(Refusal, "overlaps Git"):
                    S.exclusive(target, raw, 0o600, guard)
            self.assertEqual(len(calls), 4)
            self.assertEqual(sizes, [target.stat().st_size])
            self.assertEqual(sizes, [len(raw)])  # written BEFORE the observed boundary
            self.assertEqual(forbidden, [])
            print("V2_FOURTH_GUARD=" + json.dumps(dict(
                at_refusal=sizes[0], after_close=target.stat().st_size,
                forbidden=forbidden)), flush=True)

    def test_exclusive_empty_full_short_interrupted_zero_and_partial_errors(self):
        with fixture() as s:
            for case in ("empty", "full", "short", "interrupted", "error", "partial-error", "zero"):
                with self.subTest(case=case):
                    target = Path(s.env["HOME"]) / case
                    data = b"" if case == "empty" else b"0123456789abcdefghijklmno"
                    calls, guards = [], []
                    original = os.write
                    error = OSError("test short-write failure")
                    def write(fd, raw):
                        calls.append(len(guards))
                        if case == "interrupted" and len(calls) == 1:
                            raise InterruptedError()
                        if case == "error" or case == "partial-error" and len(calls) == 2:
                            raise error
                        if case == "zero":
                            return 0
                        return original(fd, raw[:7] if case in ("short", "interrupted", "partial-error")
                                        else raw)
                    def guard():
                        guards.append(1)
                        S.safe(target)
                    with patch.object(S.os, "write", write):
                        if case in ("error", "partial-error", "zero"):
                            with self.assertRaises((OSError, Refusal)) as caught:
                                S.exclusive(target, data, 0o600, guard)
                            if case != "zero":
                                self.assertIs(caught.exception, error)
                        else:
                            S.exclusive(target, data, 0o600, guard)
                    expected = data[:7] if case == "partial-error" else b"" \
                        if case in ("error", "zero") else data
                    self.assertEqual(target.read_bytes(), expected)
                    self.assertEqual(target.stat().st_size, len(expected))
                    self.assertEqual(calls, sorted(set(calls)))  # guard before EACH attempt
                    if case == "empty":
                        self.assertEqual(calls, [])
                    print("V2_WRITE_RESULT=" + json.dumps(dict(case=case,
                          size=target.stat().st_size, attempts=len(calls))), flush=True)


def truncate(path, size):
    with path.open("wb") as stream:
        stream.truncate(size)


if __name__ == "__main__":
    print("V2_SOURCE_SHA256=" + json.dumps({
        str(p.relative_to(F.ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((F.ROOT / "v2").rglob("*")) if p.is_file() and "__pycache__" not in str(p)
    }, sort_keys=True), flush=True)
    unittest.main()
