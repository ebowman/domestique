"""Harmless native-helper wiring/ownership tests. Never native evidence."""
import importlib.util
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(file))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


N = load("native_fixture", "native-discovery.py")
T = load("supervisor_regressions", "acceptance-tests.py")
M = load("context_fixture", "beads-native-context.py")


class NativeSupervisionTests(unittest.TestCase):
    def synthetic(self, rc=0):
        # Reuse, not weaken or duplicate, the foreign-target-safe fixture.
        self.enterContext(mock.patch.object(T, "A", N.S))
        return T.AcceptanceTests().synthetic_child(rc)

    def test_batch_uses_retained_leader_and_preserves_completed_status(self):
        for rc in (0, 7):
            with self.subTest(rc=rc), self.synthetic(rc) as (proc, _, events, _, group, kill, _):
                result = N.run(["synthetic"], "/fixture", {"ONLY": "fixture"})
                self.assertEqual((result.args, result.returncode, result.stdout, result.stderr),
                                 (["synthetic"], rc, "child stdout\n", "child stderr\n"))
                self.assertEqual(group.call_count, 2)
                self.assertLess(events.index(N.S.signal.SIGKILL), events.index("reap"))
                proc.poll.assert_not_called()
                proc.communicate.assert_not_called()
                kill.assert_not_called()

    def test_recovered_inspection_does_not_change_native_exit_classification(self):
        original = N.S.process_table
        for rc in (0, 7):
            with self.subTest(rc=rc), self.synthetic(rc) as (
                    proc, table, events, _, group, _, inspect):
                inspect.side_effect = original
                parent, pgid, state, birth = table[proc.pid]
                listing = subprocess.CompletedProcess(
                    "ps", 0, f"{proc.pid} {parent} {pgid} {state} {birth}\n", "")
                calls = []

                def ps(argv, **kw):
                    calls.append(kw["timeout"])
                    if len(calls) == 1:
                        raise subprocess.TimeoutExpired(argv, kw["timeout"], output="partial")
                    return listing

                diagnostic = io.StringIO()
                with mock.patch.object(N.S.subprocess, "run", side_effect=ps), \
                        mock.patch.object(sys, "stderr", diagnostic):
                    result = N.run(["synthetic"], "/fixture", {})
                self.assertEqual(result.returncode, rc)
                self.assertEqual((result.stdout, result.stderr),
                                 ("child stdout\n", "child stderr\n"))
                self.assertIn("PROCESS_INSPECTION_RECOVERED", diagnostic.getvalue())
                self.assertEqual(group.call_count, 2)
                self.assertLess(events.index(N.S.signal.SIGKILL), events.index("reap"))
                # A qualified successful native report stays exit 0, not BLOCKED/2.
                report = T.AcceptanceTests().discovery()
                report["results"] = [{
                    "component": "synthetic", "status": "NATIVE_DISCOVERY_OBSERVED",
                    "repo": "A", "version": "fixture", "stage": "global-only",
                    "skills": [{"name": "fixture", "source": "fixture"}]}]
                report["counts"].update(BLOCKED=0, NATIVE_DISCOVERY_OBSERVED=1)
                if rc:
                    with self.assertRaises(ValueError):
                        N.S.native_report("native-discovery.py", json.dumps(report), rc)
                else:
                    row = N.S.native_report("native-discovery.py", json.dumps(report), rc)
                    self.assertEqual(N.S.exit_code([row]), 0)

    def test_batch_reused_group_never_signalled(self):
        with self.synthetic() as (proc, table, _, _, group, kill, inspect):
            foreign = {proc.pid: (os.getpid(), proc.pid, "S", "Mon Sep 14 10:01:00 2026")}
            inspect.side_effect = [table, foreign, foreign, foreign]
            with self.assertRaises(N.SupervisionError):
                N.run(["synthetic"], "/fixture", {})
            group.assert_not_called()
            kill.assert_not_called()

    def test_completed_child_cleanup_error_preserves_exit_and_output(self):
        for rc in (0, 7):
            with self.subTest(rc=rc), self.synthetic(rc) as (_, _, _, _, group, _, inspect):
                original = inspect.return_value
                inspect.side_effect = [original, N.S.ProcessInspectionError("cleanup fixture"),
                                       original, original]
                with self.assertRaises(N.SupervisionError) as failure:
                    N.run(["synthetic"], "/fixture", {})
                self.assertEqual(failure.exception.returncode, rc)
                self.assertEqual(failure.exception.output, "child stdout\n")
                self.assertEqual(failure.exception.stderr, "child stderr\n")
                self.assertEqual(group.call_count, 2)
                if rc:
                    self.assertIsInstance(failure.exception.primary_failure,
                                          subprocess.CalledProcessError)

    def test_rpc_reused_group_close_fails_without_foreign_signal(self):
        with self.synthetic() as (proc, table, _, _, group, kill, _):
            rpc = N.Rpc(["synthetic"], "/fixture", {})
            table[proc.pid] = (os.getpid(), proc.pid, "S", "Mon Sep 14 10:01:00 2026")
            with self.assertRaises(N.SupervisionError):
                rpc.close()
            rpc.close()  # Idempotent even after failed ownership.
            group.assert_not_called()
            kill.assert_not_called()

    def test_rpc_close_retains_leader_until_last_signal(self):
        with self.synthetic() as (proc, _, events, _, group, _, _):
            rpc = N.Rpc(["synthetic"], "/fixture", {})
            rpc.close()
            rpc.close()
            self.assertEqual(group.call_count, 2)
            self.assertLess(events.index(N.S.signal.SIGKILL), events.index("reap"))
            proc.poll.assert_not_called()
            proc.communicate.assert_not_called()

    def completed_rpc(self, rc=0, message=None):
        message = message or {"id": 1, "result": {"fixture": True}}
        script = ("import sys,json; sys.stdin.readline(); "
                  "print('child stderr',file=sys.stderr,flush=True); "
                  f"print(json.dumps({message!r}),flush=True); sys.exit({rc})")
        rpc = N.Rpc([sys.executable, "-c", script], Path.cwd(), {}, timeout=5)
        self.addCleanup(rpc.close)
        return rpc

    def observe_completion(self, rpc, rc):
        deadline = time.monotonic() + 5
        while rpc.session.leader.observe() is None:
            self.assertLess(time.monotonic(), deadline, "fixture did not complete")
            time.sleep(.01)
        self.assertEqual(rpc.session.leader.completed, rc)
        self.assertIsNone(rpc.proc.returncode, "completion observation must not reap")

    def assert_rpc_reaped(self, rpc):
        rpc.close()  # Close stays idempotent, even after failure.
        self.assertTrue(rpc.closed)
        self.assertTrue(rpc.session.leader.released)
        self.assertIsNotNone(rpc.proc.returncode)
        for stream in (rpc.proc.stdin, rpc.proc.stdout, rpc.proc.stderr):
            self.assertTrue(stream.closed)
        self.assertIsNone(rpc.session.drain.selector.get_map())
        with self.assertRaises(ChildProcessError):
            os.waitid(os.P_PID, rpc.proc.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)

    def assert_close_report_failure(self, rpc, rc):
        # Exercise the actual main/report/exit path, not a native client.
        output = io.StringIO()
        tools = {name: None for name in (*N.CLIENTS, "node", "git", "sandbox-exec")}

        def probe(harness):
            harness.repos = []
            harness.observed_step("synthetic-rpc", rpc.close)

        with mock.patch.object(N, "resolve_tools", return_value=tools), \
                mock.patch.object(N.Harness, "probe", probe), \
                mock.patch.object(sys, "argv", ["fixture", "--run"]), \
                mock.patch.object(sys, "stdout", output):
            self.assertEqual(N.main(), 1)
        report = json.loads(output.getvalue())
        row = report["results"][0]
        self.assertEqual(row["status"], "ASSERTION_FAILURE")
        self.assertEqual(row["exit"], rc)
        self.assertEqual(report["counts"]["BLOCKED"], 0)
        for code in (0, 2):
            with self.assertRaises(ValueError):
                N.S.native_report("native-discovery.py", json.dumps(report), code)
        return row

    def test_valid_rpc_reply_then_natural_exit_is_not_hidden(self):
        for rc in (0, 7):
            with self.subTest(rc=rc):
                rpc = self.completed_rpc(rc)
                self.assertEqual(rpc.request("skills/list", {}), {"fixture": True})
                self.observe_completion(rpc, rc)
                if rc:
                    row = self.assert_close_report_failure(rpc, rc)
                    self.assertEqual(row["failure_kind"], "error")
                    self.assertIsInstance(rpc.failure, subprocess.CalledProcessError)
                    self.assertIn('"fixture": true', rpc.failure.output)
                    self.assertEqual(rpc.failure.stderr, "child stderr\n")
                else:
                    rpc.close()
                    self.assertIsNone(rpc.failure)
                self.assertEqual(rpc.session.completed_returncode, rc)
                self.assertEqual(rpc.proc.returncode, rc)
                self.assert_rpc_reaped(rpc)

    def test_live_rpc_intentionally_stopped_is_not_natural_failure(self):
        script = ("import sys,json,time; sys.stdin.readline(); "
                  "print(json.dumps({'id':1,'result':{}}),flush=True); time.sleep(30)")
        rpc = N.Rpc([sys.executable, "-c", script], Path.cwd(), {}, timeout=5)
        self.addCleanup(rpc.close)
        self.assertEqual(rpc.request("skills/list", {}), {})
        self.assertIsNone(rpc.session.leader.observe())
        rpc.close()
        self.assertIsNone(rpc.session.completed_returncode)
        self.assertIsNone(rpc.failure)
        self.assertIn(rpc.proc.returncode, (-N.S.signal.SIGTERM, -N.S.signal.SIGKILL))
        self.assert_rpc_reaped(rpc)

    def test_rpc_primary_failure_and_natural_exit_survive_cleanup(self):
        for kind in ("protocol", "timeout", "blocker"):
            with self.subTest(kind=kind):
                message = ({"id": 1, "result": {}} if kind == "timeout" else
                           {"id": 1, "error": {"code": -32601 if kind == "blocker" else -32603,
                                               "message": "fixture"}})
                rpc = self.completed_rpc(7, message)
                if kind == "timeout":
                    rpc.request("skills/list", {})
                    rpc.deadline = time.monotonic() - 1
                error = (subprocess.TimeoutExpired if kind == "timeout" else
                         N.Blocked if kind == "blocker" else AssertionError)
                with self.assertRaises(error) as primary:
                    rpc.request("skills/list", {})
                self.observe_completion(rpc, 7)
                row = self.assert_close_report_failure(rpc, 7)
                self.assertIs(rpc.failure.primary_failure, primary.exception)
                self.assertEqual(row["primary_failure"]["failure_kind"],
                                 "timeout" if kind == "timeout" else "error")
                self.assertEqual(primary.exception.stderr, "child stderr\n")
                self.assert_rpc_reaped(rpc)

    def test_rpc_cleanup_error_retains_natural_exit_and_consumed_output(self):
        for rc in (0, 7):
            for primary in (None, subprocess.TimeoutExpired("fixture protocol", 5)):
                with self.subTest(rc=rc, primary=primary):
                    rpc = self.completed_rpc(rc)
                    rpc.request("skills/list", {})
                    self.observe_completion(rpc, rc)
                    rpc.failure = primary
                    original = N.S.process_table
                    calls = 0

                    def inspect(deadline, **kwargs):
                        nonlocal calls
                        calls += 1
                        if calls == 1:
                            raise N.S.ProcessInspectionError("fixture cleanup")
                        return original(deadline, **kwargs)

                    with mock.patch.object(N.S, "process_table", side_effect=inspect):
                        row = self.assert_close_report_failure(rpc, rc)
                    self.assertIsInstance(rpc.failure, N.SupervisionError)
                    self.assertEqual(row["failure_kind"], "supervision")
                    self.assertEqual(rpc.failure.returncode, rc)
                    self.assertIn('"fixture": true', rpc.failure.output)
                    self.assertEqual(rpc.failure.stderr, "child stderr\n")
                    if primary is not None:
                        self.assertIs(rpc.failure.primary_failure, primary)
                    elif rc:
                        self.assertEqual(rpc.failure.primary_failure.returncode, rc)
                    self.assert_rpc_reaped(rpc)

    def test_rpc_completion_during_cleanup_inspection_captured_at_signal_boundary(self):
        with self.synthetic(7) as (proc, table, events, waitid, group, kill, inspect):
            completed = waitid.side_effect
            waitid.side_effect = lambda *_: None
            rpc = N.Rpc(["synthetic"], "/fixture", {})

            def finish_during_inspection(_deadline, **_kwargs):
                waitid.side_effect = completed
                return table

            inspect.side_effect = finish_during_inspection
            with self.assertRaises(subprocess.CalledProcessError) as raised:
                rpc.close()
            self.assertIs(rpc.failure, raised.exception)
            self.assertEqual(rpc.session.completed_returncode, 7)
            self.assertEqual(raised.exception.returncode, 7)
            self.assertEqual(group.call_count, 2)
            self.assertLess(events.index(N.S.signal.SIGKILL), events.index("reap"))
            proc.poll.assert_not_called()
            proc.communicate.assert_not_called()
            kill.assert_not_called()
            rpc.close()

    def test_stdin_cwd_environment_and_stderr_are_forwarded(self):
        with tempfile.TemporaryDirectory() as temp:
            script = ("import os,sys; print(os.getcwd()); print(os.environ['FIXTURE']); "
                      "sys.stdout.write(sys.stdin.read()); print('error',file=sys.stderr); "
                      "sys.exit(9)")
            payload = "fixture input\n" * 20000  # Larger than a pipe; no blocking writes.
            result = N.run([sys.executable, "-c", script], temp, {"FIXTURE": "only"},
                           input_text=payload)
            self.assertEqual(result.returncode, 9)
            self.assertEqual(result.stdout, str(Path(temp).resolve()) + "\nonly\n" + payload)
            self.assertEqual(result.stderr, "error\n")
            empty = N.run([sys.executable, "-c", "import sys; print(repr(sys.stdin.read()))"],
                          temp, {}, input_text="")
            self.assertEqual(empty.stdout, "''\n")

    def test_optional_stdin_and_sandbox_argv_forward_at_shared_boundary(self):
        argv = [Path("/fixture/sandbox-exec"), "-p", "unchanged policy", "/fixture/client"]
        with mock.patch.object(N.S, "execute", return_value=("out", "err", 3)) as execute:
            self.assertEqual(N.run(argv, "/fixture/cwd", {"X": "Y"}).args, argv)
        execute.assert_called_once_with(list(map(str, argv)), {"X": "Y"}, N.TIMEOUT,
                                        cwd="/fixture/cwd", input_text=None)

    def test_importlib_runpy_and_all_native_batch_callers_share_owner(self):
        namespace = runpy.run_path(str(Path(N.__file__)))
        production = load("production_fixture", "beads-production.py")
        self.assertIs(namespace["S"], N.S)
        self.assertIs(M.N.S, N.S)
        self.assertIs(production.N.S, N.S)

    def test_structured_failures_never_validate_as_blockers(self):
        for kind in ("timeout", "supervision", "error"):
            for name, factory in (("native-discovery.py", T.AcceptanceTests().discovery),
                                  ("beads-native-context.py", T.AcceptanceTests().context)):
                for nested in (False, True):
                    report = factory()
                    target = report
                    if nested:
                        target = report["results"][0] if "results" in report else {}
                        if "commands" in report:
                            report["commands"].append(target)
                    target["failure_kind"] = kind
                    with self.subTest(kind=kind, name=name, nested=nested), \
                            self.assertRaises(ValueError):
                        N.S.native_report(name, json.dumps(report), 2)

    def test_untyped_and_unknown_blocker_kinds_are_rejected(self):
        for kind in (None, "timeout", "runtime-refusal"):
            report = T.AcceptanceTests().discovery()
            report["results"][0]["blocker_kind"] = kind
            with self.assertRaises(ValueError):
                N.S.native_report("native-discovery.py", json.dumps(report), 2)

    def test_discovery_handlers_record_typed_timeout_and_cleanup_failures(self):
        with tempfile.TemporaryDirectory() as temp:
            h = N.Harness.__new__(N.Harness)
            h.repos, h.results = [Path(temp)], []
            for exc, kind in ((subprocess.TimeoutExpired("fixture", 1), "timeout"),
                              (N.SupervisionError("fixture cleanup"), "supervision")):
                h.observed_step("fixture", mock.Mock(side_effect=exc))
                self.assertEqual(h.results[-2]["failure_kind"], kind)
                self.assertEqual(h.results[-2]["status"], "ASSERTION_FAILURE")
                self.assertEqual(N.exit_code(h.results), 1)

    def test_context_deadline_is_typed_failure_without_launch(self):
        experiment = M.Experiment.__new__(M.Experiment)
        experiment.tools = {"sandbox-exec": "/fixture/sandbox-exec"}
        experiment.deadline = time.monotonic() - 1
        with mock.patch.object(M.N, "run") as run, self.assertRaises(subprocess.TimeoutExpired):
            experiment.safe(["fixture"], "/fixture", {}, "policy")
        run.assert_not_called()

    def test_rpc_runtime_error_fails_but_documented_approval_is_blocked(self):
        for message, error in (
                ({"id": 1, "error": {"code": -32603, "message": "runtime failure"}}, AssertionError),
                ({"id": 4, "method": "item/commandExecution/requestApproval"}, N.Blocked)):
            script = ("import sys,json; sys.stdin.readline(); "
                      f"print(json.dumps({message!r}),flush=True)")
            rpc = N.Rpc([sys.executable, "-c", script], Path.cwd(), {})
            try:
                with self.assertRaises(error):
                    rpc.request("skills/list", {})
            finally:
                rpc.close()

    def test_rpc_timeout_cleanup_failure_retains_primary_timeout(self):
        with self.synthetic() as (_, _, _, _, group, _, _):
            rpc = N.Rpc(["synthetic"], "/fixture", {})
            failure = subprocess.TimeoutExpired("app-server protocol", 30)
            rpc.failure = failure
            group.side_effect = OSError("synthetic cleanup failure")
            with self.assertRaises(N.SupervisionError) as raised:
                rpc.close()
            self.assertIs(raised.exception.primary_failure, failure)
            self.assertEqual(group.call_count, 2)

    def test_rpc_stdout_eof_does_not_wait_for_stderr_or_live_leader(self):
        # Real harmless child closes stdout but keeps stderr open until cleanup.
        script = "import os,sys,time; sys.stdin.readline(); os.close(1); time.sleep(30)"
        rpc = N.Rpc([sys.executable, "-c", script], Path.cwd(), {})
        try:
            with self.assertRaisesRegex(AssertionError, "EOF"):
                rpc.request("skills/list", {})
        finally:
            rpc.close()

    def test_rpc_protocol_deadline_is_deterministic_typed_failure(self):
        rpc = N.Rpc([sys.executable, "-c", "import time; time.sleep(30)"], Path.cwd(), {})
        try:
            rpc.deadline = time.monotonic() - 1
            with self.assertRaises(subprocess.TimeoutExpired):
                rpc.request("skills/list", {})
        finally:
            rpc.close()

    def test_rpc_startup_inspection_failure_still_cleans_and_reaps(self):
        with self.synthetic() as (proc, table, events, _, group, _, inspect):
            inspect.side_effect = [N.S.ProcessInspectionError("startup fixture"),
                                   table, table, table]
            with self.assertRaises(N.SupervisionError):
                N.Rpc(["synthetic"], "/fixture", {})
            self.assertEqual(group.call_count, 2)
            self.assertLess(events.index(N.S.signal.SIGKILL), events.index("reap"))
            proc.wait.assert_called_once()

    def test_production_error_handler_reports_typed_failure_exit_one(self):
        production = load("production_errors", "beads-production.py")
        for failure, kind in ((subprocess.TimeoutExpired("fixture", 1), "timeout"),
                              (N.SupervisionError("fixture"), "supervision")):
            output = io.StringIO()
            with mock.patch.object(production, "experiment", side_effect=failure), \
                    mock.patch.object(sys, "stdout", output):
                self.assertEqual(production.main(), 1)
            report = json.loads(output.getvalue())
            self.assertEqual(report["failure_kind"], kind)
            self.assertEqual(report["production"], "FAILED")

    def test_context_error_handlers_report_typed_failure_exit_one(self):
        for phase in ("probe", "privacy"):
            for failure, kind in ((subprocess.TimeoutExpired("fixture", 1), "timeout"),
                                  (N.SupervisionError("fixture"), "supervision")):
                instance = mock.Mock()
                instance.report = {"proofs": {key: "BLOCKED" for key in M.PROOFS}}
                getattr(instance, phase).side_effect = failure
                output = io.StringIO()
                # main owns only disposable fixture cleanup; no setup/native call.
                with mock.patch.object(M, "Experiment", return_value=instance), \
                        mock.patch.object(M.N, "resolve_tools",
                                          return_value={name: None for name in N.CLIENTS}), \
                        mock.patch.object(sys, "argv", ["fixture", "--run"]), \
                        mock.patch.object(sys, "stdout", output):
                    self.assertEqual(M.main(), 1)
                report = json.loads(output.getvalue())
                self.assertEqual(report["status"], "FAILED")
                self.assertEqual(report["failure_kind"], kind)
                self.assertEqual(report["proofs"]["cleanup"], "PASS")

    def test_selection_and_provenance_include_shared_helper_once(self):
        for suites in (N.S.QUICK, N.S.CURRENT + N.S.UNIT_EXTRA):
            self.assertEqual(suites.count("native-supervision-tests.py"), 1)
        provenance = N.S.provenance(N.S.Control(30))["source_sha256"]
        for name in ("acceptance.py", "native-discovery.py", "native-supervision-tests.py"):
            self.assertIn("test/" + name, provenance)


if __name__ == "__main__":
    unittest.main()
