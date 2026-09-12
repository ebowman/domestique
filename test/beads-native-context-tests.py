"""Pure offline guards/protocol tests. Synthetic records are NOT native DB proof."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location(
    "beads_context", Path(__file__).with_name("beads-native-context.py"))
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="domestique-beads-context-", dir="/private/tmp")
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name).resolve()
        self.tools = {key: None for key in (*M.N.CLIENTS, "node", "git", "sandbox-exec")}
        self.e = M.Experiment(self.work, self.tools)

    def test_no_opt_in_never_resolves_or_executes(self):
        with mock.patch.object(sys, "argv", ["beads-native-context.py"]), \
                mock.patch.object(M.N, "resolve_tools", side_effect=AssertionError("native")), \
                mock.patch.object(M.tempfile, "TemporaryDirectory", side_effect=AssertionError("fixture")), \
                mock.patch("builtins.print") as output:
            self.assertEqual(M.main(), 2)
            self.assertEqual(json.loads(output.call_args.args[0])["status"], "STATIC_ONLY")

    def test_optimized_python_refuses(self):
        result = subprocess.run(
            [sys.executable, "-O", str(Path(M.__file__)), "--run"],
            capture_output=True, text=True, timeout=10,
            env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["status"], "FAILED")

    def test_nonfixture_path_refused(self):
        with self.assertRaisesRegex(AssertionError, "disposable fixture"):
            M.Experiment(Path(M.__file__).parent, self.tools)

    def test_nonempty_fixture_refused(self):
        (self.work / "sentinel").write_text("not fresh")
        with self.assertRaisesRegex(AssertionError, "fresh, empty"):
            M.Experiment(self.work, self.tools)

    def test_native_requires_actual_sandbox_probe(self):
        with mock.patch.object(M.N, "run", side_effect=AssertionError("executed")):
            with self.assertRaisesRegex(AssertionError, "verified sandbox"):
                self.e.bd(None, "--version")

    def test_unknown_context_refused(self):
        self.e.report["proofs"]["sandbox"] = "PASS"
        with self.assertRaisesRegex(AssertionError, "unknown native context"):
            self.e.bd(None, "--version")

    def test_nonexperiment_command_refused(self):
        self.e.report["proofs"]["sandbox"] = "PASS"
        self.e.contexts = [None]
        with self.assertRaisesRegex(AssertionError, "non-experiment"):
            self.e.bd(None, "setup")

    def test_missing_os_sandbox_never_runs(self):
        with mock.patch.object(M.N, "run", side_effect=AssertionError("executed")):
            with self.assertRaisesRegex(M.N.Blocked, "sandbox-exec unavailable"):
                self.e.safe(["unused"], self.work, {}, "")

    def test_environment_allowlist(self):
        private = self.work / "A/.domestique-private/beads-context"
        private.mkdir(parents=True)
        with mock.patch.dict(os.environ, {"BEADS_DB": "host", "BD_DB": "host",
                                         "GIT_DIR": "host", "HTTP_PROXY": "host",
                                         "BD_OTEL_STDOUT": "true", "SECRET": "host"}):
            env = M.private_env(private, self.work / "A", self.tools)
        for key in ("BEADS_DB", "BD_DB", "GIT_DIR", "HTTP_PROXY", "BD_OTEL_STDOUT",
                    "SECRET", "BEADS_DOLT_SHARED_SERVER", "BEADS_DOLT_SERVER_MODE"):
            self.assertNotIn(key, env)
        self.assertEqual(env["BD_DOLT_MODE"], "embedded")
        self.assertEqual(env["GIT_CEILING_DIRECTORIES"], str(private))
        self.assertEqual(env["BEADS_DIR"], str(self.work / "A/.beads"))
        for key in ("HOME", "TMPDIR", "XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME"):
            self.assertTrue(Path(env[key]).is_relative_to(private))

    def test_profile_only_private_database_write_grants(self):
        private, beads = self.work / "A/private", self.work / "A/.beads"
        profile = M.native_profile(self.work, self.tools, private, beads)
        self.assertNotIn(f'(allow file-write* (subpath "{self.work}"))', profile)
        self.assertEqual(profile.count("(allow file-write*"), 2)
        self.assertIn(f'(allow file-write* (subpath "{private}"))', profile)
        self.assertIn(f'(allow file-write* (subpath "{beads}"))', profile)
        self.assertNotIn("(allow network", profile)
        self.assertNotIn("mach-lookup", profile)
        self.assertIn('(deny process-exec (regex #"/dolt$"))', profile)

    def test_snapshot_prunes_only_allowed_trees(self):
        host = self.work / "host"
        host.write_text("original")
        private = self.work / "private"
        private.mkdir()
        before = M.protected_snapshot(self.work, [private])
        (private / "cache").write_text("allowed")
        self.assertEqual(before, M.protected_snapshot(self.work, [private]))
        host.write_text("changed")
        self.assertEqual(M.N.differences(before, M.protected_snapshot(self.work, [private])), ["host"])

    def test_ping_real_shape_not_identity(self):
        M.check_ping(dict(status="ok", resolve_ms=0, store_ms=0, query_ms=2, total_ms=2))
        for value in ({}, [], {"status": "ok"}, {"status": "error"},
                      dict(status="ok", resolve_ms=True, store_ms=0, query_ms=2, total_ms=2)):
            with self.subTest(value=value), self.assertRaises(AssertionError):
                M.check_ping(value)

    def test_export_discriminates_issue_and_memory(self):
        text = '{"_type":"issue","id":"synthetic-1"}\n' \
               '{"_type":"memory","key":"fixture","value":"synthetic only"}\n'
        issues, memories = M.export_records(text)
        self.assertEqual(set(issues), {"synthetic-1"})
        self.assertEqual(memories, {"fixture": "synthetic only"})

    def test_export_unknown_or_duplicate_is_not_success(self):
        for text in ('{"id":"synthetic-1"}', '[]',
                     '{"_type":"issue","id":"synthetic-1"}\n' * 2):
            with self.subTest(text=text), self.assertRaises(AssertionError):
                M.export_records(text)

    def test_warning_classifier_blocks_unknown_warning(self):
        self.assertEqual(M.warnings("warning: beads.role not configured (GH#2950).\n"),
                         ["warning: beads.role not configured (GH#2950)."])
        with self.assertRaises(M.N.Blocked):
            M.warnings("Warning: could not save metadata")
        self.assertIsNotNone(M.DENIAL.search("operation not permitted"))

    def test_partial_or_blocked_never_reports_success(self):
        proofs = {key: "PASS" for key in M.PROOFS}
        self.assertEqual(M.exit_code(proofs), 0)
        proofs["database-uuid-query"] = "BLOCKED"
        self.assertEqual(M.exit_code(proofs), 2)
        proofs["host-privacy"] = "FAILED"
        self.assertEqual(M.exit_code(proofs), 1)
        self.assertEqual(M.exit_code({}), 2)

    ORIGINAL = "00000000-0000-4000-8000-000000000001"
    REPLACEMENT = "00000000-0000-4000-8000-000000000002"

    def refusal(self, original=None, replacement=None):
        return subprocess.CompletedProcess([], 1, "", (
            "Error: workspace identity mismatch detected\n\n"
            f"  metadata.json project_id: {replacement or self.REPLACEMENT}\n"
            f"  database _project_id:     {original or self.ORIGINAL}\n\n"
            "Synthetic offline diagnostic only\n"))

    def test_identity_classifier_requires_both_pinned_fields(self):
        evidence = M.check_identity_refusal(self.refusal(), self.ORIGINAL, self.REPLACEMENT)
        self.assertEqual(evidence["database_project_id"], self.ORIGINAL)
        self.assertEqual(evidence["metadata_project_id"], self.REPLACEMENT)

    def test_identity_classifier_rejects_success_or_signal(self):
        for code in (0, -9):
            result = self.refusal()
            result.returncode = code
            with self.subTest(code=code), self.assertRaises(AssertionError):
                M.check_identity_refusal(result, self.ORIGINAL, self.REPLACEMENT)

    def test_identity_classifier_requires_original_db_uuid_not_metadata_echo(self):
        for text in ("Error: workspace identity mismatch detected\n",
                     self.refusal(original=self.REPLACEMENT).stderr,
                     self.refusal(replacement=self.ORIGINAL).stderr,
                     self.refusal().stderr + self.refusal().stderr):
            result = subprocess.CompletedProcess([], 1, "", text)
            with self.subTest(text=text), self.assertRaises(AssertionError):
                M.check_identity_refusal(result, self.ORIGINAL, self.REPLACEMENT)

    def test_identity_classifier_unknown_error_is_failure(self):
        result = subprocess.CompletedProcess([], 1, "", "Error: unsupported embedded command")
        with self.assertRaises(AssertionError):
            M.check_identity_refusal(result, self.ORIGINAL, self.REPLACEMENT)

    def test_identity_classifier_unexpected_stdout_is_failure(self):
        result = self.refusal()
        result.stdout = '{"id":"unexpected-write"}'
        with self.assertRaises(AssertionError):
            M.check_identity_refusal(result, self.ORIGINAL, self.REPLACEMENT)

    def test_identity_classifier_rejects_equal_or_invalid_uuids(self):
        for replacement in (self.ORIGINAL, "not-a-uuid"):
            with self.subTest(replacement=replacement), self.assertRaises((AssertionError, ValueError)):
                M.check_identity_refusal(self.refusal(), self.ORIGINAL, replacement)

    def identity_fixture(self):
        """Synthetic metadata and mocked process output; no native identity evidence."""
        repo = self.work / "A"
        private = repo / ".domestique-private/beads-context"
        private.mkdir(parents=True)
        (repo / ".beads").mkdir()
        path = repo / ".beads/metadata.json"
        original_bytes = (
            '{\n  "project_id": "' + self.ORIGINAL + '",\n  "fixture": true\n}\n').encode()
        path.write_bytes(original_bytes)
        context = (repo, private, {"BEADS_DIR": str(repo / ".beads")}, "synthetic")
        self.e.contexts = [context]
        self.e.report.update(initialized=["A"], operations_completed=["A"],
                             metadata={"A": json.loads(original_bytes)})
        self.e.report["proofs"]["sandbox"] = "PASS"  # Mocked runner only below.
        ids = ["synthetic-1", "synthetic-2", "synthetic-3"]
        queued = [{"id": i, "title": i} for i in ids]
        return context, path, original_bytes, ids, queued

    def exercise_identity_control(self, write="refuse", query="unchanged"):
        context, path, original_bytes, ids, queued = self.identity_fixture()
        calls = []

        def safe(argv, cwd, env, profile):
            calls.append(argv[2])
            if argv[2] == "create":
                modified = json.loads(path.read_bytes())
                self.assertNotEqual(modified["project_id"], self.ORIGINAL)
                self.assertEqual(modified, {**json.loads(original_bytes),
                                            "project_id": modified["project_id"]})
                if write == "blocked":
                    raise M.N.Blocked("synthetic timeout")
                if write == "error":
                    return subprocess.CompletedProcess(argv, 1, "", "unrelated failure")
                if write == "success":
                    queued.append({"id": "synthetic-rejected", "title": argv[3]})
                    return subprocess.CompletedProcess(argv, 0, "{}", "")
                return self.refusal(replacement=modified["project_id"])
            self.assertEqual(argv[2:4], ["list", "--all"])
            self.assertEqual(path.read_bytes(), original_bytes)
            if query == "error":
                return subprocess.CompletedProcess(argv, 1, "", "synthetic list failure")
            if query == "changed":
                queued[0]["id"] = "synthetic-foreign"
            return subprocess.CompletedProcess(argv, 0, json.dumps(queued), "")

        with mock.patch.object(self.e, "safe", side_effect=safe):
            try:
                self.e.identity_binding(context, ids)
            finally:
                self.assertEqual(path.read_bytes(), original_bytes)
                self.assertEqual(calls, ["create", "list"])

    def test_identity_control_restores_exact_bytes_on_normal_return(self):
        self.exercise_identity_control()
        control = self.e.report["identity_controls"]["A"]
        self.assertEqual(control["status"], "PASS")
        self.assertTrue(control["metadata_restored"])
        self.assertTrue(control["rejected_issue_absent"])
        self.assertNotIn("stderr", self.e.report["commands"][0])
        # One synthetic fixture must not award the three-context aggregate proof.
        self.assertEqual(self.e.report["proofs"]["IDENTITY_BINDING"], "BLOCKED")

    def test_identity_control_restores_and_queries_after_unknown_error(self):
        with self.assertRaises(AssertionError):
            self.exercise_identity_control(write="error")
        self.assertEqual(self.e.report["proofs"]["IDENTITY_BINDING"], "FAILED")

    def test_identity_control_missing_key_skipped_check_write_is_failure(self):
        with self.assertRaisesRegex(AssertionError, "issue count"):
            self.exercise_identity_control(write="success")
        self.assertEqual(self.e.report["proofs"]["IDENTITY_BINDING"], "FAILED")
        self.assertNotIn("rejected_issue_absent", self.e.report["identity_controls"]["A"])

    def test_identity_control_restores_and_queries_after_blocked_runner(self):
        with self.assertRaises(M.N.Blocked):
            self.exercise_identity_control(write="blocked")
        self.assertEqual(self.e.report["proofs"]["IDENTITY_BINDING"], "BLOCKED")

    def test_identity_control_list_failure_never_passes(self):
        with self.assertRaises(M.N.Blocked):
            self.exercise_identity_control(query="error")
        self.assertEqual(self.e.report["identity_controls"]["A"]["status"], "BLOCKED")

    def test_identity_control_successful_write_still_fails_when_list_blocked(self):
        with self.assertRaises(M.N.Blocked):
            self.exercise_identity_control(write="success", query="error")
        self.assertEqual(self.e.report["proofs"]["IDENTITY_BINDING"], "FAILED")
        self.assertEqual(self.e.report["identity_controls"]["A"]["status"], "FAILED")

    def test_identity_control_changed_ids_fail_despite_valid_refusal(self):
        with self.assertRaisesRegex(AssertionError, "changed issue IDs"):
            self.exercise_identity_control(query="changed")
        self.assertEqual(self.e.report["proofs"]["IDENTITY_BINDING"], "FAILED")

    def test_identity_control_unknown_metadata_not_mutated(self):
        context, path, original_bytes, ids, queued = self.identity_fixture()
        drifted = original_bytes.replace(b"true", b"false")
        path.write_bytes(drifted)
        with mock.patch.object(self.e, "safe", side_effect=AssertionError("native")):
            with self.assertRaisesRegex(AssertionError, "generated metadata drift"):
                self.e.identity_binding(context, ids)
        self.assertEqual(path.read_bytes(), drifted)
        self.assertEqual(self.e.report["proofs"]["IDENTITY_BINDING"], "FAILED")

    def test_main_fixture_cleanup_on_normal_return_and_failure(self):
        for fails in (False, True):
            made = []
            real_experiment = M.Experiment

            def experiment(work, tools):
                instance = real_experiment(work, tools)
                made.append(work)

                def probe():
                    (work / "generated-sentinel").write_text("synthetic only")
                    if fails:
                        raise AssertionError("synthetic failure")
                instance.probe = probe
                return instance

            with self.subTest(fails=fails), \
                    mock.patch.object(sys, "argv", ["beads-native-context.py", "--run"]), \
                    mock.patch.object(M.N, "resolve_tools", return_value=dict(self.tools)), \
                    mock.patch.object(M.N, "run", side_effect=AssertionError("native")), \
                    mock.patch.object(M, "Experiment", side_effect=experiment), \
                    mock.patch("builtins.print") as output:
                self.assertEqual(M.main(), 1 if fails else 2)
                report = json.loads(output.call_args.args[0])
                self.assertEqual(report["proofs"]["cleanup"], "PASS")
                self.assertEqual(len(made), 1)
                self.assertFalse(made[0].exists())


if __name__ == "__main__":
    unittest.main()
