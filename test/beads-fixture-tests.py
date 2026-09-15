"""Explicitly SYNTHETIC selection/wiring tests. Never execute a native binary."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), HERE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


F = load("beads_fixture")
A = load("acceptance")
C = load("beads-native-context")
P = load("beads-production")
FUNCTIONAL_SECONDS = 30


class FixtureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="domestique-beads-selection-")
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name).resolve()
        self.binary = self.work / 'private "quoted" executable'
        self.binary.write_bytes(b"SYNTHETIC ONLY: must never execute\n")
        self.binary.chmod(0o700)
        self.digest = hashlib.sha256(self.binary.read_bytes()).hexdigest()

    def test_immutable_default_and_production_pin(self):
        self.assertEqual(F.DEFAULT, Path("/opt/homebrew/Cellar/beads/1.1.2/bin/beads"))
        source = (HERE.parent / "domestique.sh").read_text()
        self.assertIn('PIN = "' + F.SHA256 + '"', source)
        self.assertEqual(F.SHA256,
                         "cb77069648d90fef8876f775d647997beb7bb0ab5461509394c29d5bf14b7c42")

    def test_exact_default_without_ambient_bd_lookup(self):
        with mock.patch.object(F, "SHA256", self.digest):
            self.assertEqual(F.resolve({}, default=self.binary),
                             {"path": str(self.binary), "sha256": self.digest})

    def test_explicit_physical_path_and_digest(self):
        link = self.work / "link"
        link.symlink_to(self.binary)
        with mock.patch.object(F, "SHA256", self.digest):
            self.assertEqual(F.resolve({F.OVERRIDE: str(link)}, default=self.work / "missing"),
                             {"path": str(self.binary), "sha256": self.digest})

    def test_invalid_explicit_never_falls_back_to_valid_default(self):
        for value in ("", " ", "relative", "~/beads", "/bad\npath", "/bad\0path",
                      str(self.work / "missing"), None, 1, str(self.work)):
            with self.subTest(value=value), mock.patch.object(F, "SHA256", self.digest), \
                    self.assertRaises((ValueError, OSError)):
                F.resolve({F.OVERRIDE: value}, default=self.binary)

    def test_default_missing_distinct_from_explicit_failure(self):
        missing = self.work / "absent"
        with self.assertRaises(F.MissingDefault):
            F.resolve({}, default=missing)
        with self.assertRaises(ValueError):
            F.resolve({F.OVERRIDE: str(missing)}, default=self.binary)

    def test_wrong_digest_no_execution(self):
        with mock.patch("subprocess.Popen", side_effect=AssertionError("execution")), \
                self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            F.resolve({F.OVERRIDE: str(self.binary)})

    def test_executable_and_readable_required(self):
        self.binary.chmod(0o600)
        with self.assertRaisesRegex(ValueError, "regular readable executable"):
            F.resolve({F.OVERRIDE: str(self.binary)})
        self.binary.chmod(0o700)
        with mock.patch.object(F.os, "access", return_value=False), \
                self.assertRaisesRegex(ValueError, "regular readable executable"):
            F.resolve({F.OVERRIDE: str(self.binary)})

    def test_no_opt_in_ignores_even_invalid_override(self):
        for module in (C, P):
            with self.subTest(module=module.__name__), \
                    mock.patch.dict(os.environ, {F.OVERRIDE: ""}), \
                    mock.patch.object(sys, "argv", [module.__file__]), \
                    mock.patch.object(module.F, "resolve", side_effect=AssertionError("resolve")), \
                    mock.patch.object(module.N, "run", side_effect=AssertionError("execute")), \
                    mock.patch("builtins.print"):
                self.assertEqual(module.main(), 2)

    def test_native_harness_invalid_override_fails_before_execution(self):
        for module in (C, P):
            with self.subTest(module=module.__name__), \
                    mock.patch.dict(os.environ, {F.OVERRIDE: str(self.binary)}), \
                    mock.patch.object(sys, "argv", [module.__file__, "--run"]), \
                    mock.patch.object(module.N, "resolve_tools", return_value={
                        key: None for key in (*module.N.CLIENTS, "node", "git", "sandbox-exec")}), \
                    mock.patch.object(module.N, "run", side_effect=AssertionError("executed")) as run, \
                    mock.patch("builtins.print"):
                self.assertEqual(module.main(), 1)
                run.assert_not_called()

    def test_context_records_selection_without_global_link_assumption(self):
        with tempfile.TemporaryDirectory(prefix="domestique-beads-context-", dir="/private/tmp") as temp:
            e = C.Experiment(Path(temp).resolve(), {"sandbox-exec": None})
            selected = {"path": str(self.binary), "sha256": self.digest}
            with mock.patch.object(C.F, "resolve", return_value=selected), \
                    self.assertRaises(C.N.Blocked):
                e.setup()
            self.assertEqual(e.binary, self.binary)
            self.assertEqual(e.report["binary"], selected["path"])
            self.assertEqual(e.report["binary_sha256"], selected["sha256"])
            self.assertEqual(e.tools["beads"], self.binary)

    def test_only_literal_selected_read_grant_added(self):
        tools = {key: None for key in (*C.N.CLIENTS, "node", "git", "sandbox-exec")}
        before = C.N.sandbox_profile(self.work, tools).splitlines()
        after = C.N.sandbox_profile(self.work, {**tools, "beads": self.binary}).splitlines()
        self.assertEqual([line for line in after if line not in before],
                         [f"(allow file-read* (literal {json.dumps(str(self.binary))}))"])
        private, beads = self.work / "private", self.work / ".beads"
        profile = C.native_profile(self.work, {**tools, "beads": self.binary}, private, beads)
        self.assertNotIn("(allow network", profile)
        self.assertNotIn("mach-lookup", profile)

    def test_native_only_forwarding_including_empty_failure_input(self):
        for value in ("", str(self.binary)):
            with mock.patch.dict(os.environ, {F.OVERRIDE: value}):
                for native, name in [(True, n) for n in A.NATIVE] + [
                        (False, n) for n in (*A.CURRENT, *A.HISTORICAL)] + [(True, None)]:
                    with self.subTest(native=native, name=name), tempfile.TemporaryDirectory() as temp:
                        env = A.environment(Path(temp), native, name)
                        self.assertEqual(F.OVERRIDE in env, native and name in F.SCOPES)
                        if F.OVERRIDE in env:
                            self.assertEqual(env[F.OVERRIDE], value)

    def test_native_command_environment_drops_override(self):
        tools = {key: None for key in (*C.N.CLIENTS, "node", "git", "sandbox-exec")}
        with mock.patch.dict(os.environ, {F.OVERRIDE: str(self.binary)}):
            env = C.private_env(self.work / "private", self.work / "repo", tools)
        self.assertNotIn(F.OVERRIDE, env)

    def test_cleanup_synthetic_branch_never_imports_or_resolves_override(self):
        # Execute only setup through the fixture's first run; no product/native
        # subprocesses. This tests the actual default branch, not a fake resolver.
        with mock.patch.object(sys, "argv", ["beads-cleanup.py"]):
            cleanup = load("beads-cleanup")

        def inspect_instrumentation(argv, **kwargs):
            source = Path(argv[1]).read_text()
            anchor = "    result = execute_child(\n"
            self.assertEqual(cleanup.SOURCE.count(anchor), 1)
            self.assertEqual(source.count(anchor), 1)
            code = source.split("<<'DOM_BEADS_PY'\n", 1)[1].split("\nDOM_BEADS_PY", 1)[0]
            namespace = {}
            exec(code.split("\ntry:\n    main()", 1)[0], namespace)
            result = cleanup.subprocess.CompletedProcess([], 0, "instrumented", "")
            with mock.patch.dict(namespace, execute_child=mock.Mock(return_value=result)):
                self.assertEqual(namespace["process"](
                    ["synthetic-controller-call"], self.work, self.work,
                    self.binary, self.binary), "instrumented")
            self.assertEqual((Path(argv[1]).parent / "native-calls").read_text(),
                             "synthetic-controller-call\n")
            raise RuntimeError("STOP")

        with tempfile.TemporaryDirectory(prefix=".beads-selection-", dir=HERE.parent) as temp:
            with mock.patch.dict(os.environ, {"TMPDIR": temp, F.OVERRIDE: ""}), \
                    mock.patch.object(cleanup.importlib.util, "spec_from_file_location",
                                      side_effect=AssertionError("native selector imported")), \
                    mock.patch.object(cleanup.subprocess, "run", side_effect=inspect_instrumentation), \
                    self.assertRaisesRegex(RuntimeError, "STOP"):
                cleanup.main()
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_cleanup_native_refuses_before_fixture_or_execution(self):
        with mock.patch.object(sys, "argv", ["beads-cleanup.py", "--native"]):
            cleanup = load("beads-cleanup")
        with mock.patch.dict(os.environ, {F.OVERRIDE: ""}), \
                mock.patch.object(cleanup.tempfile, "TemporaryDirectory") as temp, \
                mock.patch.object(cleanup.subprocess, "run") as run, \
                self.assertRaises(ValueError):
            cleanup.main()
        temp.assert_not_called()
        run.assert_not_called()

    def test_cleanup_pause_real_process_waits_for_explicit_release(self):
        with mock.patch.object(sys, "argv", ["beads-cleanup.py"]):
            cleanup = load("beads-cleanup")
        mark, release = self.work / "active", self.work / "release"
        generated = cleanup.inject_pause(cleanup.SOURCE, mark, release)
        code = generated.split("<<'DOM_BEADS_PY'\n", 1)[1].split("\nDOM_BEADS_PY", 1)[0]
        ast.parse(code)
        helper = self.work / "paused.py"
        helper.write_text(code)
        # Only this harmless Python child runs. Native execution is mocked and
        # any accidental subprocess launch inside it is an immediate failure.
        probe = r"""
from pathlib import Path
import subprocess, sys, time
from unittest import mock
helper, mark, release = map(Path, sys.argv[1:])
namespace = {}
exec(helper.read_text().split("\ntry:\n    main()", 1)[0], namespace)
sleep = time.sleep
def observed_sleep(seconds):
    assert mark.read_text() == "active"
    print("PAUSED", flush=True)
    sleep(seconds)
def invoked(*args, **kwargs):
    assert mark.read_text() == "active" and release.exists()
    assert kwargs["pass_fds"] == (8,) and kwargs["timeout"] == 60
    print("CALLED", flush=True)
    return subprocess.CompletedProcess([], 0, "mocked-output", "")
execute = mock.Mock(side_effect=invoked)
assert not mark.exists() and not release.exists()
with mock.patch.dict(namespace, execute_child=execute), \
        mock.patch.object(subprocess, "Popen", side_effect=AssertionError("native launch")), \
        mock.patch.object(time, "sleep", side_effect=observed_sleep):
    assert namespace["process"](
        ["synthetic-ready"], helper.parent, helper.parent,
        helper, helper, coordinated=True) == "mocked-output"
execute.assert_called_once()
print("DONE", flush=True)
"""
        deadline = time.monotonic() + FUNCTIONAL_SECONDS
        child = subprocess.Popen(
            [sys.executable, "-I", "-S", "-B", "-W", "error", "-c", probe,
             str(helper), str(mark), str(release)],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            def event():
                data = b""
                while not data.endswith(b"\n"):
                    remaining = deadline - time.monotonic()
                    self.assertGreater(remaining, 0, "pause readiness deadline")
                    ready, _, _ = select.select([child.stdout], [], [], remaining)
                    self.assertTrue(ready, "pause readiness missing")
                    byte = os.read(child.stdout.fileno(), 1)
                    self.assertTrue(byte, "probe exited before readiness")
                    data += byte
                return data

            # Two positive loop observations, not a timeout accepted as proof.
            # A missing/bypassed pause instead emits CALLED or exits and fails.
            self.assertEqual(event(), b"PAUSED\n")
            self.assertEqual(mark.read_text(), "active")
            self.assertFalse(release.exists())
            self.assertEqual(event(), b"PAUSED\n")
            self.assertIsNone(child.poll())
            release.touch()
            remaining = deadline - time.monotonic()
            self.assertGreater(remaining, 0)
            out, err = child.communicate(timeout=remaining)
            self.assertEqual(child.returncode, 0, (out, err))
            self.assertEqual(err, b"")
            self.assertEqual(out.splitlines().count(b"CALLED"), 1)
            self.assertEqual(out.splitlines()[-1], b"DONE")
        finally:
            # Failure/cancellation never releases an unverified operation.
            # Signal/reap only our owned, direct, harmless child; no PID scan.
            if child.poll() is None:
                child.terminate()
            try:
                child.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                child.kill()
                child.communicate(timeout=2)

    def test_cleanup_pause_refuses_missing_duplicate_and_malformed_boundary(self):
        with mock.patch.object(sys, "argv", ["beads-cleanup.py"]):
            cleanup = load("beads-cleanup")
        anchor = cleanup.PROCESS_BOUNDARY
        for replacement, error in (
                ("", AssertionError),
                (anchor + anchor, AssertionError),
                ("    result = execute_child (\n", AssertionError),
                (anchor + "        !!!\n", SyntaxError)):
            with self.subTest(replacement=replacement), self.assertRaises(error):
                cleanup.inject_pause(cleanup.SOURCE.replace(anchor, replacement),
                                     self.work / "active", self.work / "release")
        self.assertFalse((self.work / "active").exists())
        self.assertFalse((self.work / "release").exists())

    def test_cleanup_native_instrumentation_byte_and_behavior_equivalent(self):
        with mock.patch.object(sys, "argv", ["beads-cleanup.py", "--native"]):
            cleanup = load("beads-cleanup")

        def inspect(argv, **kwargs):
            source = Path(argv[1]).read_text()
            native_log = Path(argv[1]).parent / "native-calls"
            # Exact previously reviewed native assembly, including whitespace.
            anchor = "    result = execute_child(\n"
            expected = cleanup.SOURCE.replace(
                anchor, f"    with open({str(native_log)!r}, 'a') as trace:\n"
                "        trace.write(str(argv[0]) + '\\n')\n" + anchor)
            self.assertEqual(source.encode(), expected.encode())
            code = source.split("<<'DOM_BEADS_PY'\n", 1)[1].split("\nDOM_BEADS_PY", 1)[0]
            ast.parse(code)
            namespace = {}
            exec(code.split("\ntry:\n    main()", 1)[0], namespace)
            execute = mock.Mock(return_value=subprocess.CompletedProcess([], 0, "native-mock", ""))
            with mock.patch.dict(namespace, execute_child=execute):
                self.assertEqual(namespace["process"](
                    ["native-mock"], self.work, self.work, self.binary, self.binary,
                    coordinated=True), "native-mock")
            execute.assert_called_once()
            self.assertEqual(execute.call_args.kwargs["pass_fds"], (8,))
            self.assertEqual(execute.call_args.kwargs["timeout"], 60)
            self.assertEqual(native_log.read_text(), "native-mock\n")
            raise RuntimeError("STOP before native execution")

        with tempfile.TemporaryDirectory(prefix=".beads-selection-", dir=HERE.parent) as temp:
            with mock.patch.dict(os.environ, {"TMPDIR": temp}), \
                    mock.patch.object(cleanup.importlib.util, "spec_from_file_location",
                                      return_value=mock.Mock()), \
                    mock.patch.object(cleanup.importlib.util, "module_from_spec", return_value=F), \
                    mock.patch.object(F, "resolve", return_value={
                        "path": str(self.binary), "sha256": cleanup.NS["PIN"]}), \
                    mock.patch.dict(cleanup.NS, digest=mock.Mock(return_value=cleanup.NS["PIN"])), \
                    mock.patch.object(cleanup, "inject_pause", side_effect=AssertionError("native pause")), \
                    mock.patch.object(cleanup.subprocess, "run", side_effect=inspect), \
                    mock.patch("builtins.print"), \
                    self.assertRaisesRegex(RuntimeError, "STOP before native execution"):
                cleanup.main()
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_evidence_and_suite_source_wiring(self):
        selected = {"path": str(self.binary), "sha256": F.SHA256}
        self.assertEqual(A.fixture_evidence(selected), selected)
        for bad in ({}, {**selected, "path": "relative"}, {**selected, "sha256": self.digest}):
            with self.assertRaises(ValueError):
                A.fixture_evidence(bad)
        name = "beads-fixture-tests.py"
        self.assertIn(name, A.CURRENT)
        self.assertIn(name, A.QUICK)
        sources = A.provenance(A.Control(10))["source_sha256"]
        for name in ("beads_fixture.py", "beads-fixture-tests.py", *F.SCOPES):
            self.assertIn("test/" + name, sources)
            ast.parse((HERE / name).read_text())

    def test_outer_native_scope_provenance_and_invalid_refusal(self):
        # Mocked native completion only; actual controller persists reports and
        # removes disposable fixtures. No product/native commands are spawned.
        selected = {"path": str(self.binary), "sha256": self.digest}
        for invalid in (False, True):
            with self.subTest(invalid=invalid), tempfile.TemporaryDirectory() as temp:
                base = Path(temp).resolve()
                root, artifacts = base / "checkout", base / "artifacts"
                root.mkdir()
                artifacts.mkdir()
                original = A.tempfile.mkdtemp
                calls = []

                def create(**kw):
                    return str(artifacts) if kw.get("prefix") == "domestique-acceptance-" else original(**kw)

                def execute(argv, env, timeout, control=None):
                    if "-c" in argv:  # Runner's own final fixture cleanup.
                        for path in argv[argv.index("-c") + 2:]:
                            shutil.rmtree(path)
                    else:
                        calls.append(argv)
                        self.assertEqual(env[F.OVERRIDE], str(self.binary))
                    return "", "", 0

                args = ["acceptance.py", "--exhaustive", "--native-only",
                        "--total-seconds", "30", "--suite-seconds", "10"]
                for name in F.SCOPES:
                    args += ["--suite", "NATIVE:" + name]
                with mock.patch.object(sys, "argv", args), \
                        mock.patch.dict(os.environ, {F.OVERRIDE: "" if invalid else str(self.binary)}), \
                        mock.patch.object(A, "ROOT", root), \
                        mock.patch.object(A.F, "SHA256", self.digest), \
                        mock.patch.object(A.tempfile, "mkdtemp", side_effect=create), \
                        mock.patch.object(A, "provenance", return_value={"source_sha256": {"synthetic": "only"}}), \
                        mock.patch.object(A, "execute", side_effect=execute), \
                        mock.patch.object(A, "native_report", return_value={
                            "status": "NATIVE_OBSERVED", "native_fixture": selected,
                            "report": {"binary": selected["path"], "binary_sha256": selected["sha256"]}}), \
                        mock.patch("builtins.print"):
                    self.assertEqual(A.main(), 1 if invalid else 0)
                report = json.loads((artifacts / "report.json").read_text())
                self.assertEqual(list(root.iterdir()), [])
                self.assertIn("source_sha256", report["provenance"])
                if invalid:
                    self.assertEqual(calls, [])
                    self.assertEqual(report["results"][0]["status"], "ASSERTION_FAILURE")
                else:
                    self.assertEqual(len(calls), 3)
                    for result in report["results"]:
                        self.assertEqual(result["native_fixture"], selected)
                        self.assertEqual(result["status"], "NATIVE_OBSERVED")


if __name__ == "__main__":
    unittest.main()
