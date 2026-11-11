"""Fast negative controls for the opt-in published gate (no installer matrix)."""
import argparse
from functools import partial
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import sys
import time
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "published", Path(__file__).with_name("published-upgrades.py"))
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
SOURCE = (gate.REPO / "domestique.sh").read_text()


class PublishedGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name).resolve()

    def put(self, root, path, data):
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        target.chmod(0o644)

    def fixture(self):
        root, ref = self.work / "actual", self.work / "reference"
        for directory in (root, ref):
            self.put(directory, ".git/info/exclude",
                     b"# release-gate host exclusion\nhost-private.txt\n")
            self.put(directory, ".claude/commands/dom-goal.md", b"current workflow\n")
        self.put(root, "host.txt", b"host text\n")
        self.put(root, "CLAUDE.md.bak.20000101000000", b"old backup\n")
        return root, ref, gate.history.snapshot(root)

    def test_exact_finite_plan_and_capabilities(self):
        cases = gate.plan()
        self.assertEqual(len(cases), 74)
        self.assertEqual(len({case["id"] for case in cases}), 74)
        self.assertEqual({case["tag"] for case in cases}, set(gate.TAGS))
        self.assertTrue(all(case["expected"] == "success" for case in cases))
        self.assertEqual(sum(case["mode"] == "guest" for case in cases), 36)
        self.assertEqual(sum(case["install"] == "default" for case in cases), 20)
        with self.assertRaisesRegex(AssertionError, "do not skip"):
            gate.capabilities("v0.2.0", "broken installer")

    def test_only_explicit_capability_rejection_is_unsupported(self):
        classify = gate.history.outcome
        result = dict(returncode=2, stdout="", stderr="Unknown option: --guest", timeout=False)
        self.assertEqual(classify(result), "unsupported")
        for changed in (dict(returncode=3), dict(stderr="missing historical core"),
                        dict(timeout=True)):
            self.assertEqual(classify(dict(result, **changed)), "failure")

    def test_same_revision_archive_includes_matching_support(self):
        destination = self.work / "released"
        digest = gate.export("HEAD", destination)
        self.assertEqual(len(digest), 64)
        self.assertEqual((destination / "domestique.sh").read_text(),
                         gate.history.git("show", "HEAD:domestique.sh"))
        self.assertEqual((destination / "tools/historical-identities.py").read_text(),
                         gate.history.git("show", "HEAD:tools/historical-identities.py"))

    def test_preview_detects_bytes_modes_mtime_and_index(self):
        root, _ref, _old = self.fixture()
        path = root / "host.txt"
        for change in (lambda: path.write_bytes(b"edited\n"),
                       lambda: path.chmod(0o600),
                       lambda: os.utime(path, ns=(1, 1)),
                       lambda: self.put(root, ".git/index", b"index")):
            before = gate.tree(root)
            change()
            with self.assertRaisesRegex(AssertionError, "changed paths"):
                gate.unchanged(before, gate.tree(root), "preview")
        before = gate.tree(root, mtimes=False)
        os.utime(path, ns=(2, 2))
        gate.unchanged(before, gate.tree(root, mtimes=False), "byte-only rerun")

    def test_current_body_and_backups_have_negative_controls(self):
        root, ref, old = self.fixture()
        gate.compare_contract(root, ref, old, SOURCE, [])
        target = root / ".claude/commands/dom-goal.md"
        target.write_bytes(b"stale workflow\n")
        with self.assertRaisesRegex(AssertionError, "current projection differs"):
            gate.compare_contract(root, ref, old, SOURCE, [])
        target.write_bytes(b"current workflow\n")
        (root / "CLAUDE.md.bak.20000101000000").write_bytes(b"clobbered\n")
        with self.assertRaisesRegex(AssertionError, "existing host/backup lost"):
            gate.compare_contract(root, ref, old, SOURCE, [])

    def test_guest_provenance_is_not_fresh_equality_but_must_be_excluded(self):
        root, ref, old = self.fixture()
        exclude = root / ".git/info/exclude"
        exclude.write_bytes(exclude.read_bytes() + b".beads/\n")
        self.put(root, ".claude/.domestique/guest-excludes", b".beads/\n")
        old = gate.history.snapshot(root)
        gate.compare_contract(root, ref, old, SOURCE, [], guest=True)
        exclude.write_bytes(b"# release-gate host exclusion\nhost-private.txt\n")
        with self.assertRaisesRegex(AssertionError, "lacks exclusion"):
            gate.compare_contract(root, ref, old, SOURCE, [], guest=True)

    def test_retired_shared_base_not_required_live_projection_is(self):
        root, ref, _old = self.fixture()
        retired = ".codex/.domestique/base/.agents/skills/dom-goal/SKILL.md"
        self.put(root, retired, b"old shared base\n")
        for directory in (root, ref):
            self.put(directory, ".agents/.domestique/base/.agents/skills/dom-goal/SKILL.md",
                     b"current shared base\n")
        unknown = (".codex/.domestique/unknown-data",
                   ".codex/.domestique/base/.agents/skills/unknown/SKILL.md",
                   "unknown-host-data")
        for path in unknown:
            self.put(root, path, b"unclassified original\n")
        old = gate.history.snapshot(root)
        (root / retired).unlink()
        gate.compare_contract(root, ref, old, SOURCE, [])
        for path in unknown:
            for changed in (b"tampered\n", None):
                if changed is None:
                    (root / path).unlink()
                else:
                    self.put(root, path, changed)
                with self.assertRaisesRegex(AssertionError, "unclassified old file changed/lost"):
                    gate.compare_contract(root, ref, old, SOURCE, [])
                self.put(root, path, b"unclassified original\n")
        (root / ".claude/commands/dom-goal.md").unlink()
        with self.assertRaisesRegex(AssertionError, "missing current projection"):
            gate.compare_contract(root, ref, old, SOURCE, [])

    def test_exact_unchanged_manifest_provenance_not_arbitrary_stale_metadata(self):
        path = ".agents/.domestique/manifest"
        common = ("snapshot_format=1\nplatform=shared\nfiles=skill\n"
                  "installed_at=2026-11-10T00:00:00Z\n")
        old = ((common + "domestique_version=0.4.0\nscript_sha256=old\n").encode(), 0o644)
        fresh = ((common + "domestique_version=0.4.3\nscript_sha256=new\n").encode(), 0o644)
        gate.check_manifest(path, old, fresh, old)
        gate.check_manifest(path, fresh, fresh, old)
        changed = (old[0].replace(b"sha256=old", b"sha256=tampered"), old[1])
        with self.assertRaisesRegex(AssertionError, "current manifest differs"):
            gate.check_manifest(path, changed, fresh, old)
        stale = (old[0].replace(b"files=skill", b"files=retired-skill"), old[1])
        with self.assertRaisesRegex(AssertionError, "inventory differs"):
            gate.check_manifest(path, stale, fresh, stale)

    def test_native_model_choice_cannot_be_hidden_by_body_normalization(self):
        root, ref, _old = self.fixture()
        role = ".claude/agents/implementer.md"
        data = b"---\nname: implementer\ndescription: Fixture\nmodel: sonnet\n---\nBody\n"
        for directory in (root, ref):
            self.put(directory, role, data)
        old = gate.history.snapshot(root)
        gate.compare_contract(root, ref, old, SOURCE, [])
        changed = data.replace(b"sonnet", b"opus")
        self.assertEqual(gate.role_body(role, data, SOURCE),
                         gate.role_body(role, changed, SOURCE))
        self.put(root, role, changed)
        with self.assertRaisesRegex(AssertionError, "model/effort changed"):
            gate.compare_contract(root, ref, old, SOURCE, [])

    def test_raw_marker_must_attest_before_comparison(self):
        root, ref, _old = self.fixture()
        for directory in (root, ref):
            for role in ("implementer", "reviewer"):
                self.put(directory, f".claude/agents/{role}.md",
                         f"---\nname: {role}\ndescription: Fixture\n---\nBody\n".encode())
        old = gate.history.snapshot(root)
        path = ".claude/agents/implementer.md"
        for directory in (root, ref):
            data = (directory / path).read_bytes()
            marker = dict(v=1, project=str(directory), harness="claude",
                          implementer_sha256=gate.history.sha(data),
                          reviewer_sha256=gate.history.sha(
                              (directory / path.replace("implementer", "reviewer")).read_bytes()))
            encoded = json.dumps(marker, sort_keys=True, separators=(",", ":")).encode()
            self.put(directory, path, data.replace(
                b"---\n", b"---\n# domestique-model-setup: " + encoded + b"\n", 1))
        gate.compare_contract(root, ref, old, SOURCE, [])
        self.put(root, path, (root / path).read_bytes().replace(
            str(root).encode(), b"<PHYSICAL-PROJECT-ROOT>"))
        with self.assertRaisesRegex(ValueError, "invalid model marker"):
            gate.compare_contract(root, ref, old, SOURCE, [])

    def test_timeout_and_unexpected_exit_are_fail_with_immutable_evidence(self):
        for code, timed_out in ((None, True), (3, False), (2, False)):
            case = dict(id=f"failed-{code}", expected="success")
            fake = dict(returncode=code, stdout="evidence stdout", stderr="specific failure",
                        timeout=timed_out)
            with patch.object(gate.history, "run", return_value=fake):
                result = gate.execute(case, self.work, self.work, self.work, 900, 120)
            self.assertEqual(result["status"], "FAIL")
            evidence = self.work / case["id"] / "result.json"
            self.assertEqual(json.loads(evidence.read_text()), result)
            self.assertEqual(result["commands"][0]["budget_seconds"], 120)
            self.assertEqual(result["commands"][0]["stderr"], "specific failure")
            with self.assertRaises(FileExistsError):
                gate.write_json(evidence, {})

    def test_real_process_group_timeout(self):
        result = gate.history.run(["/bin/sleep", "5"], cwd=self.work,
                                  env={"PATH": "/usr/bin:/bin"}, timeout=0.05)
        self.assertTrue(result["timeout"])
        self.assertIsNone(result["returncode"])

    def test_finite_budget_validation(self):
        for value in ("nan", "inf", "0", "-1"):
            with self.assertRaises(Exception):
                gate.positive(value)
        self.assertEqual(gate.positive("900"), 900)


REPORTED = (
    "test_historical_claude_retained_guard_only",
    "test_historical_claude_policy_identity_upgrade",
    "test_removed_provider_stale_platform_history_does_not_resurrect",
    "test_guest_tracked_shared_active_and_new_pairs_preflight",
    "test_staged_presnapshot_adoption",
    "test_tracked_old_guest_policy_no_guest_recovery",
    "test_unowned_converted_roles_refuse_then_explicit_backup",
)


def reported_suite(names=REPORTED, installer_timeout=1800):
    """Reuse current helpers; only the named reported risks, never the full suite."""
    spec = importlib.util.spec_from_file_location("current", gate.REPO / "test/all-current.py")
    current = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(current)

    class Reported(current.AllProviders):
        def setUp(self):
            super().setUp()
            sandbox = self.work / "isolation"
            sandbox.mkdir()
            self.env = gate.history.isolated(sandbox)
            self.env.update(GIT_OPTIONAL_LOCKS="0", GIT_TEMPLATE_DIR=str(sandbox / "template"))
            # Existing fixture helpers occasionally use subprocess.check_output
            # without env=. Cover those as well, without caller configuration.
            self.environment = patch.dict(os.environ, self.env, clear=True)
            self.environment.start()
            self.addCleanup(self.environment.stop)
            # Keep the reviewed real-pipe transport and its owned-group cleanup.
            # Bound each invocation, not the combined seven-test workload.
            transport = patch.object(
                current, "run_stdin",
                partial(current.run_stdin, timeout=installer_timeout))
            transport.start()
            self.addCleanup(transport.stop)

        def tearDown(self):
            sandbox = self.work / "isolation"
            self.assertFalse((sandbox / "dependency.log").exists(), "blocked dependency called")
            for name in ("home", "config", "cache", "data", "state"):
                self.assertEqual(gate.history.snapshot(sandbox / name), {}, name)

        def test_staged_presnapshot_adoption(self):
            # The existing committed presnapshot fixture cannot run under the
            # gate's no-commits restriction. Same historical bytes, staged only.
            root = self.root("presnapshot-staged")
            self.run_dom(root, script=gate.history.git("show", "e12f0fc:domestique.sh"))
            policy = root / "CLAUDE.md"
            original = gate.PREFIX + policy.read_bytes() + gate.SUFFIX
            policy.write_bytes(original)
            self.assertFalse((root / current.STATES["claude"]).exists())
            backup = root / "CLAUDE.md.bak.20000101000000"
            backup.write_bytes(b"existing backup\n")
            subprocess_result = gate.history.run(["git", "add", "."], cwd=root, env=self.env)
            self.assertEqual(subprocess_result["returncode"], 0, subprocess_result)
            index = (root / ".git/index").read_bytes()
            before = current.snapshot(root)
            self.run_dom(root, "--platform=claude", "--dry-run")
            self.assertEqual(before, current.snapshot(root))
            self.run_dom(root, "--platform=claude")
            self.assertEqual(index, (root / ".git/index").read_bytes())
            self.assertTrue(policy.read_bytes().startswith(gate.PREFIX))
            self.assertTrue(policy.read_bytes().endswith(gate.SUFFIX))
            self.assertEqual(backup.read_bytes(), b"existing backup\n")
            new = [p for p in root.glob("CLAUDE.md.bak.*") if p != backup]
            self.assertEqual([p.read_bytes() for p in new], [original])
            state = root / current.STATES["claude"]
            inventory = dict(line.split("=", 1) for line in
                             (state / "manifest").read_text().splitlines())["files"].split(",")
            reference = self.root("presnapshot-current-reference")
            self.run_dom(reference, "--platform=claude")
            for path in inventory:
                relative = path + (".block" if path == "CLAUDE.md" else "")
                self.assertEqual((state / "base" / relative).read_bytes(),
                                 (reference / current.STATES["claude"] / "base" /
                                  relative).read_bytes(), relative)
            for role, model in (("implementer", "sonnet"), ("reviewer", "opus")):
                data = (root / f".claude/agents/{role}.md").read_bytes()
                self.assertEqual(self.model_library("claude")["parse"](data, role)[1]["model"],
                                 model)
            gate.history.normalize(".claude/agents/implementer.md",
                                   (root / ".claude/agents/implementer.md").read_bytes(),
                                   root, gate.history.snapshot(root))
            after = current.byte_snapshot(root)
            self.run_dom(root, "--platform=claude")
            self.assertEqual(after, current.byte_snapshot(root))

        def test_tracked_old_guest_policy_no_guest_recovery(self):
            root = self.root("tracked-old-guest")
            self.run_dom(root, script=gate.history.git("show", "v0.1.0:domestique.sh"))
            staged = gate.history.run(["git", "add", "."], cwd=root, env=self.env)
            self.assertEqual(staged["returncode"], 0, staged)
            before = current.snapshot(root)
            for flags in (("--dry-run",), ()):
                result = self.run_dom(root, "--platform=claude", "--guest", *flags, ok=False)
                self.assertEqual(result.returncode, 3)
                self.assertIn("--no-guest", result.stderr)
                self.assertIn("CLAUDE.md", result.stderr)
                self.assertEqual(before, current.snapshot(root))
            self.run_dom(root, "--platform=claude", "--no-guest", "--dry-run")
            self.assertEqual(before, current.snapshot(root))
            self.run_dom(root, "--platform=claude", "--no-guest")
            after = current.byte_snapshot(root)
            self.run_dom(root, "--platform=claude", "--no-guest")
            self.assertEqual(after, current.byte_snapshot(root))

        def test_unowned_converted_roles_refuse_then_explicit_backup(self):
            owned = self.root("owned-source")
            self.run_dom(owned, "--platform=claude")
            root = self.root("unowned-converted")
            originals = {}
            for role in ("implementer", "reviewer"):
                rel = f".claude/agents/{role}.md"
                # Converted/current native bodies alone are not ownership. Do
                # not transplant a physical-root model approval marker either.
                data = self.model_library("claude")["split_marker"](
                    (owned / rel).read_bytes(), role)[0].encode()
                data += b"\nManually converted user-owned role notes.\n"
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                originals[rel] = data
            before = current.snapshot(root)
            for flags in (("--dry-run",), (), ("--force",)):
                result = self.run_dom(root, "--platform=claude", *flags, ok=False)
                self.assertEqual(result.returncode, 3)
                self.assertIn("No project writes", result.stderr)
                self.assertIn("cannot establish ownership of native path", result.stderr)
                self.assertIn("preserve and reconcile explicitly", result.stderr)
                self.assertEqual(before, current.snapshot(root))
            # Explicit fixture-owner disposition, NOT an installer recovery
            # shortcut: move the entire unowned pair aside before fresh install.
            saved = root / "owner-reviewed-backup"
            (root / ".claude/agents").rename(saved)
            reviewed = current.snapshot(root)
            self.run_dom(root, "--platform=claude", "--dry-run")
            self.assertEqual(reviewed, current.snapshot(root))
            self.run_dom(root, "--platform=claude")
            for rel, data in originals.items():
                self.assertEqual((saved / Path(rel).name).read_bytes(), data)
            stable = current.byte_snapshot(root)
            self.run_dom(root, "--platform=claude")
            self.assertEqual(stable, current.byte_snapshot(root))

    return unittest.TestSuite(Reported(name) for name in names)


def reported_main():
    parser = argparse.ArgumentParser(description="Serial, per-case reported-risk evidence")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--reported", action="store_true")
    mode.add_argument("--reported-child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--case", action="append", choices=REPORTED)
    parser.add_argument("--timeout", type=gate.positive, default=7200,
                        help="seconds per test (default: 7200)")
    parser.add_argument("--installer-timeout", type=gate.positive, default=1800,
                        help="seconds per piped installer invocation (default: 1800)")
    parser.add_argument("--output", type=Path, help="new evidence directory")
    args = parser.parse_args()
    names = args.case or REPORTED
    if args.reported_child:
        # A Python deadline unwinds run_stdin's cleanup even though its Bash
        # owns a separate session. The parent has a further 60s safety margin.
        import signal

        def expired(_signum, _frame):
            raise TimeoutError("reported test exceeded its finite case budget")

        signal.signal(signal.SIGALRM, expired)
        signal.setitimer(signal.ITIMER_REAL, args.timeout)
        try:
            result = unittest.TextTestRunner(verbosity=2).run(
                reported_suite(names, args.installer_timeout))
            return not result.wasSuccessful()
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
    if args.output:
        work = args.output.resolve()
        work.mkdir(parents=True, exist_ok=False)
    else:
        work = Path(tempfile.mkdtemp(prefix="domestique-published-reported-")).resolve()
    sources = {path: gate.history.sha((gate.REPO / path).read_bytes()) for path in (
        "domestique.sh", "test/all-current.py", "test/published-upgrades-tests.py",
        "test/published-upgrades.py", "tools/historical-identities.py")}
    gate.write_json(work / "reported-plan.json", dict(
        tests=list(names), source_sha256=sources, revision=gate.history.git("rev-parse", "HEAD").strip(),
        budget_seconds=args.timeout, installer_budget_seconds=args.installer_timeout))
    records = []
    for name in names:
        directory = work / name
        directory.mkdir()
        env = gate.history.isolated(directory)
        command = [sys.executable, "-B", "-Werror", str(Path(__file__).resolve()),
                   "--reported-child", "--case", name, "--timeout", str(args.timeout),
                   "--installer-timeout", str(args.installer_timeout)]
        record = dict(command=command, budget_seconds=args.timeout,
                      outer_budget_seconds=args.timeout + 60, expected_returncode=0,
                      test=name, source_sha256=sources)
        gate.write_json(directory / "plan.json", record)
        print(json.dumps(record, indent=2), flush=True)
        started = time.monotonic()
        record.update(gate.history.run(
            command, cwd=gate.REPO, env=env, timeout=args.timeout + 60))
        record["seconds"] = time.monotonic() - started
        record["status"] = "PASS" if record["returncode"] == 0 and not record["timeout"] else "FAIL"
        gate.write_json(directory / "result.json", record)
        print(record["stdout"], end="")
        print(record["stderr"], end="", file=sys.stderr)
        print(f"Evidence: {directory / 'result.json'}", flush=True)
        records.append(dict(test=name, status=record["status"], seconds=record["seconds"],
                            evidence=str(directory / "result.json")))
        if record["status"] != "PASS":
            break  # Diagnose a real failure; never unattended retries.
    gate.write_json(work / "summary.json", records)
    return len(records) != len(names) or any(row["status"] != "PASS" for row in records)


if __name__ == "__main__":
    if "--reported" in sys.argv or "--reported-child" in sys.argv:
        sys.exit(reported_main())
    else:
        unittest.main()
