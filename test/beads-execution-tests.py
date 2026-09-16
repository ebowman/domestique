"""Actual embedded execution primitive: synthetic ownership + harmless children.

No Beads/native client, sandbox qualification, user data, or foreign signal.
All PID-reuse/permission/ownership faults are fully mocked.
"""
from contextlib import ExitStack, contextmanager
import ast
import ctypes
import errno
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parent.parent
CODE = (ROOT / "domestique2.sh").read_text().split("<<'DOM_BEADS_PY'\n", 1)[1].split(
    "\nDOM_BEADS_PY", 1)[0]
NS = {}
exec(CODE.split("\ntry:\n    main()", 1)[0], NS)

# Positive protocol runs are functional checks, not host-latency promises.
FUNCTIONAL_SECONDS = 30
# Reserve the deliberate .2s timeout and unchanged five-second cleanup budget.
READINESS_SECONDS = FUNCTIONAL_SECONDS - 5.5


@contextmanager
def fake_child(statuses=(0,), output=(b"out\r\n", b"err\r"), kill_error=None,
               setup_error=None, premature=False):
    """The numeric PGID becomes FOREIGN at wait(), never a real signal target."""
    calls, statuses = [], list(statuses)
    proc = Mock(pid=987654321, returncode=None)
    proc.stdout = Mock(encoding="utf-8", errors="strict")
    proc.stderr = Mock(encoding="utf-8", errors="strict")
    proc.stdout.fileno.return_value = 20
    proc.stderr.fileno.return_value = 21
    pipes = {20: [output[0], b""], 21: [output[1], b""]}
    state = SimpleNamespace(foreign=False, foreign_signals=0, clock=0)

    class Selector:
        def __init__(self):
            self.keys = {}

        def register(self, stream, events, index):
            if setup_error:
                raise setup_error
            self.keys[stream] = SimpleNamespace(fileobj=stream, fd=stream.fileno(), data=index)

        def unregister(self, stream):
            del self.keys[stream]

        def get_map(self):
            return self.keys

        def select(self, seconds):
            state.clock += seconds
            return [(key, 1) for key in self.keys.values()]

        def close(self):
            calls.append("close")

    def waitid(kind, pid, flags):
        if pid == os.getpid():
            raise ChildProcessError(errno.ECHILD, "not a child")
        calls.append("observe")
        if premature:
            proc.returncode = 0
            state.foreign = True
            raise ChildProcessError(errno.ECHILD, "competing reaper")
        value = statuses.pop(0) if len(statuses) > 1 else statuses[0]
        if isinstance(value, Exception):
            raise value
        if value is None:
            return None
        return SimpleNamespace(si_pid=proc.pid, si_code=NS["os"].CLD_EXITED, si_status=value)

    def killpg(pid, sig):
        calls.append("signal")
        if state.foreign:
            state.foreign_signals += 1
        if kill_error:
            raise kill_error

    def wait(timeout):
        calls.append("reap")
        state.foreign = True
        proc.returncode = statuses[-1] if isinstance(statuses[-1], int) else 0
        return proc.returncode

    def advance(seconds):
        state.clock += seconds

    proc.wait.side_effect = wait
    proc.poll.side_effect = AssertionError("early/implicit poll")
    proc.communicate.side_effect = AssertionError("early/implicit communicate")
    with ExitStack() as stack:
        stack.enter_context(patch.dict(NS, darwin_listpids=Mock()))
        stack.enter_context(patch.object(NS["subprocess"], "Popen", return_value=proc))
        stack.enter_context(patch.object(NS["os"], "waitid", side_effect=waitid))
        stack.enter_context(patch.object(NS["os"], "killpg", side_effect=killpg))
        stack.enter_context(patch.object(NS["os"], "set_blocking"))
        stack.enter_context(patch.object(NS["os"], "read", side_effect=lambda fd, _: pipes[fd].pop(0)))
        stack.enter_context(patch.object(NS["io_selectors"], "DefaultSelector", Selector))
        stack.enter_context(patch.object(NS["time"], "monotonic", side_effect=lambda: state.clock))
        stack.enter_context(patch.object(NS["time"], "sleep", side_effect=advance))
        try:
            yield proc, calls, state
        finally:
            NS["_UNREAPED_CHILDREN"].clear()  # Mock handles only.


@contextmanager
def membership(members=(), size=None, error=0, action=None):
    """Mock the C PID-only call, not the production validation/proof."""
    def query(kind, pgid, buffer, capacity):
        assert kind == 2 and pgid == 987654321 and capacity == 8
        assert ctypes.get_errno() == 0
        for index, pid in enumerate(members):
            buffer[index] = pid
        ctypes.set_errno(error)
        if action:
            action()
        return len(members) * 4 if size is None else size
    fn = Mock(side_effect=query)
    with patch.dict(NS, darwin_listpids=lambda: fn), patch.object(sys, "platform", "darwin"):
        yield fn


class ExecutionTests(unittest.TestCase):
    def execute(self, timeout=1):
        return NS["execute_child"](["SECRET-ARGV"], cwd=ROOT, env={}, timeout=timeout)

    def assert_order(self, proc, calls, state):
        self.assertEqual(calls.count("signal"), 1)
        self.assertLess(calls.index("signal"), calls.index("reap"))
        self.assertEqual(calls[calls.index("signal") - 1], "observe")
        self.assertEqual(state.foreign_signals, 0)
        proc.poll.assert_not_called()
        proc.communicate.assert_not_called()

    def test_natural_and_nonzero_retain_until_last_signal(self):
        for code in (0, 7, 128):
            with self.subTest(code=code), fake_child((code,)) as (proc, calls, state):
                result = self.execute()
                self.assertEqual((result.returncode, result.stdout, result.stderr),
                                 (code, "out\n", "err\n"))
                self.assert_order(proc, calls, state)
                NS["subprocess"].Popen.assert_called_once_with(
                    ["SECRET-ARGV"], cwd=ROOT, env={}, text=True,
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    pass_fds=(), start_new_session=True)

    def test_timeout_preserves_partial_bytes_and_safe_original(self):
        with fake_child((None, None, None, 0)) as (proc, calls, state):
            with self.assertRaises(NS["ExecutionFailure"]) as caught:
                self.execute(timeout=.01)
            error = caught.exception
            self.assertIsInstance(error.failure, subprocess.TimeoutExpired)
            self.assertEqual(error.failure.timeout, .01)
            self.assertEqual(error.failure.output, b"out\r\n")
            self.assertEqual(error.stdout, "out\n")
            self.assertNotIn("SECRET", str(error))
            self.assert_order(proc, calls, state)

    def test_unknown_permission_error_is_not_zombie_success(self):
        for code in (0, 9):
            with self.subTest(code=code), fake_child(
                    (code,), kill_error=PermissionError("SECRET-PAYLOAD")) as (proc, calls, state):
                with self.assertRaises(NS["ExecutionFailure"]) as caught:
                    self.execute()
                error = caught.exception
                self.assertEqual(error.returncode, code)
                self.assertEqual(error.stdout, "out\n")
                self.assertIsInstance(error.cleanup[0], PermissionError)
                self.assertIn("cleanup unproved", str(error))
                self.assertNotIn("SECRET", str(error))
                self.assert_order(proc, calls, state)

    def test_eperm_completed_only_or_empty_is_success(self):
        for code in (0, 7):
            for members in ((), (987654321,)):
                with self.subTest(code=code, members=members), fake_child(
                        (code,), kill_error=PermissionError(errno.EPERM, "SECRET")) as (
                        proc, calls, state), membership(members) as query:
                    result = self.execute()
                    self.assertEqual((result.returncode, result.stdout, result.stderr),
                                     (code, "out\n", "err\n"))
                    query.assert_called_once()
                    self.assert_order(proc, calls, state)

    def test_eperm_extra_pid_is_never_state_filtered(self):
        # The same extra PID must refuse whether it is live, exits/forks during
        # the query, or is another zombie. There is deliberately NO state reader.
        for members in ((123,), (987654321, 123), (123, 987654321)):
            with self.subTest(members=members), fake_child(
                    kill_error=PermissionError(errno.EPERM, "SECRET")) as (
                    proc, calls, state), membership(members) as query, \
                    patch.object(NS["subprocess"], "run",
                                 side_effect=AssertionError("whole-host ps/state read")), \
                    patch.object(NS["os"], "getpgid",
                                 side_effect=AssertionError("per-PID second pass")):
                with self.assertRaises(NS["ExecutionFailure"]) as caught:
                    self.execute()
                self.assertIsInstance(caught.exception.cleanup[0], PermissionError)
                query.assert_called_once()
                self.assert_order(proc, calls, state)
        module = ast.parse(CODE.split("\ntry:\n    main()", 1)[0])
        helper = next(node for node in module.body
                      if isinstance(node, ast.FunctionDef) and node.name == "darwin_group_pids")
        text = ast.unparse(helper)
        self.assertNotIn("subprocess", text)
        self.assertNotIn("proc_pidinfo", CODE)
        self.assertNotIn("proc_listallpids", CODE)
        self.assertEqual(text.count("fn("), 1)  # One locked membership call, no sizing pass.

    def test_eperm_live_leader_never_uses_membership(self):
        with fake_child((None, None, None, None, 0),
                        kill_error=PermissionError(errno.EPERM, "SECRET")) as (
                        proc, calls, state), membership((987654321,)) as query:
            with self.assertRaises(NS["ExecutionFailure"]) as caught:
                self.execute(timeout=.01)
            self.assertIsInstance(caught.exception.failure, subprocess.TimeoutExpired)
            self.assertIsInstance(caught.exception.cleanup[0], PermissionError)
            query.assert_not_called()
            self.assert_order(proc, calls, state)

    def test_eperm_malformed_full_error_errno_and_unknown_results_refuse(self):
        for members, size, error in (
            ((), -1, 0), ((), 1, 0), ((), 3, 0), ((), 5, 0),
            ((), 8, 0), ((), 12, 0), ((), "4", 0),
            ((), 0, errno.EPERM), ((), 0, errno.ENOSYS),
            ((987654321,), 4, errno.EIO), ((0,), 4, 0), ((-1,), 4, 0),
            ((), 4, 0),  # Length claims a PID without writing the sentinel.
        ):
            with self.subTest(members=members, size=size, error=error), fake_child(
                    kill_error=PermissionError(errno.EPERM, "SECRET")) as (
                    proc, calls, state), membership(members, size, error):
                with self.assertRaises(NS["ExecutionFailure"]) as caught:
                    self.execute()
                self.assertIsInstance(caught.exception.cleanup[0], PermissionError)
                self.assertNotIn("SECRET", str(caught.exception))
                self.assert_order(proc, calls, state)

    def test_eperm_query_exception_is_explicit_failure(self):
        def fail():
            raise OSError(errno.EIO, "SECRET")
        with fake_child(kill_error=PermissionError(errno.EPERM, "SECRET")) as (
                proc, calls, state), membership(action=fail):
            with self.assertRaises(NS["ExecutionFailure"]) as caught:
                self.execute()
            self.assertIsInstance(caught.exception.cleanup[0], PermissionError)
            self.assert_order(proc, calls, state)

    def test_eperm_revalidates_before_and_after_membership(self):
        for statuses, queried in (((0, 0, 0, 0, None), False),
                                  ((0, 0, 0, 0, 0, None), True),
                                  ((0, 0, 0, 0, 0, 7), True),
                                  ((0, 0, 0, 0, 0, ChildProcessError(errno.ECHILD, "lost")), True)):
            with self.subTest(statuses=statuses), fake_child(
                    statuses, kill_error=PermissionError(errno.EPERM, "SECRET")) as (
                    proc, calls, state), membership((987654321,)) as query:
                with self.assertRaises(NS["ExecutionFailure"]):
                    self.execute()
                self.assertEqual(query.called, queried)
                proc.wait.assert_not_called()
                self.assertEqual(state.foreign_signals, 0)
                self.assertEqual(calls.count("signal"), 1)
        with fake_child(kill_error=PermissionError(errno.EPERM, "SECRET")) as (
                proc, calls, state):
            def steal():
                proc.returncode = 0
                state.foreign = True
            with membership((987654321,), action=steal):
                with self.assertRaises(NS["ExecutionFailure"]):
                    self.execute()
            proc.wait.assert_not_called()
            self.assertEqual(state.foreign_signals, 0)
            self.assertEqual(calls.count("signal"), 1)

    def test_eperm_query_uses_original_remaining_cleanup_deadline(self):
        for before, during, queried in ((5, 0, False), (4.9, .11, True), (4.9, .09, True)):
            with self.subTest(before=before, during=during), fake_child(
                    kill_error=PermissionError(errno.EPERM, "SECRET")) as (
                    proc, calls, state):
                original = NS["os"].killpg.side_effect
                def delayed_signal(*args):
                    state.clock += before
                    original(*args)
                NS["os"].killpg.side_effect = delayed_signal
                def delayed_query():
                    state.clock += during
                with membership((987654321,), action=delayed_query) as query:
                    if before + during >= 5:
                        with self.assertRaises(NS["ExecutionFailure"]) as caught:
                            self.execute()
                        self.assertIsInstance(caught.exception.cleanup[0], PermissionError)
                    else:
                        self.assertEqual(self.execute().returncode, 0)
                    self.assertEqual(query.called, queried)
                self.assert_order(proc, calls, state)

    def test_eperm_proved_cleanup_preserves_primary_timeout_and_output(self):
        with fake_child((None, None, 0),
                        kill_error=PermissionError(errno.EPERM, "SECRET")) as (
                        proc, calls, state), membership((987654321,)):
            with self.assertRaises(NS["ExecutionFailure"]) as caught:
                self.execute(timeout=.01)
            self.assertIsInstance(caught.exception.failure, subprocess.TimeoutExpired)
            self.assertFalse(caught.exception.cleanup)
            self.assertEqual(caught.exception.stdout, "out\n")
            self.assertEqual(caught.exception.failure.output, b"out\r\n")
            self.assert_order(proc, calls, state)

    def test_timeout_and_cleanup_error_both_survive(self):
        with fake_child((None, None, None, 0),
                        kill_error=PermissionError("SECRET")) as (proc, calls, state):
            with self.assertRaises(NS["ExecutionFailure"]) as caught:
                self.execute(timeout=.01)
            self.assertIsInstance(caught.exception.failure, subprocess.TimeoutExpired)
            self.assertIsInstance(caught.exception.cleanup[0], PermissionError)
            self.assert_order(proc, calls, state)

    def test_gone_group_is_safe_before_reap(self):
        with fake_child(kill_error=ProcessLookupError()) as (proc, calls, state):
            self.assertEqual(self.execute().returncode, 0)
            self.assert_order(proc, calls, state)

    def test_lost_ownership_never_signals_reused_foreign_group(self):
        with fake_child(premature=True) as (proc, calls, state):
            with self.assertRaises(NS["ExecutionFailure"]):
                self.execute()
            self.assertTrue(state.foreign)
            self.assertEqual(state.foreign_signals, 0)
            self.assertNotIn("signal", calls)
            proc.wait.assert_not_called()

    def test_echild_and_contradictory_completion_revoke_signaling(self):
        for statuses in ((ChildProcessError(errno.ECHILD, "SECRET"),), (0, None), (0, 1)):
            with self.subTest(statuses=statuses), fake_child(statuses) as (proc, calls, state):
                with self.assertRaises(NS["ExecutionFailure"]):
                    self.execute()
                self.assertNotIn("signal", calls)
                proc.wait.assert_not_called()
                self.assertEqual(state.foreign_signals, 0)

    def test_pipe_setup_error_still_signals_before_reap(self):
        with fake_child(setup_error=OSError("SECRET")) as (proc, calls, state):
            with self.assertRaises(NS["ExecutionFailure"]) as caught:
                self.execute()
            self.assertIsInstance(caught.exception.failure, OSError)
            self.assert_order(proc, calls, state)

    def test_close_failure_does_not_mask_timeout_or_output(self):
        with fake_child((None, None, None, 0)) as (proc, calls, state):
            proc.stdout.close.side_effect = OSError("SECRET")
            with self.assertRaises(NS["ExecutionFailure"]) as caught:
                self.execute(timeout=.01)
            self.assertIsInstance(caught.exception.failure, subprocess.TimeoutExpired)
            self.assertEqual(caught.exception.stdout, "out\n")
            self.assertIsInstance(caught.exception.cleanup[0], OSError)
            self.assertNotIn("SECRET", str(caught.exception))
            self.assert_order(proc, calls, state)

    def test_synthetic_integration_run_reuses_production_with_600_seconds(self):
        module = ast.parse((ROOT / "test/beads-private.py").read_text())
        integration = next(node for node in module.body
                           if isinstance(node, ast.FunctionDef) and node.name == "integration")
        run = next(node for node in ast.walk(integration)
                   if isinstance(node, ast.FunctionDef) and node.name == "run")
        # Execute the actual nested body, not integration()/native fixtures.
        namespace = dict(NS=NS, work=ROOT, env={}, check=self.assertTrue)
        exec(compile(ast.Module(body=[run], type_ignores=[]), "<actual integration.run>", "exec"),
             namespace)
        with fake_child(output=(b"synthetic", b"")) as (proc, calls, state):
            result = namespace["run"]("harmless", "argument")
            self.assertEqual(result.stdout, "synthetic")
            self.assert_order(proc, calls, state)
        execute = Mock(return_value=subprocess.CompletedProcess("<fake>", 0, "", ""))
        with patch.dict(NS, execute_child=execute):
            namespace["run"]("harmless")
        execute.assert_called_once_with(["harmless"], cwd=ROOT, env={}, timeout=600)

    def test_cleanup_budget_is_five_seconds_not_inflated(self):
        with fake_child((None,), kill_error=PermissionError()) as (proc, calls, state):
            with self.assertRaises(NS["ExecutionFailure"]) as caught:
                self.execute(timeout=.01)
            self.assertLessEqual(state.clock, 5.011)
            self.assertGreaterEqual(state.clock, 5)
            self.assertIsInstance(caught.exception.failure, subprocess.TimeoutExpired)
            self.assertEqual(len(caught.exception.cleanup), 2)
            self.assertNotIn("reap", calls)
            self.assertEqual(state.foreign_signals, 0)
            with patch.object(NS["subprocess"], "Popen") as spawn:
                with self.assertRaises(NS["Refusal"]):
                    self.execute()
                spawn.assert_not_called()

    def test_process_forwards_exact_contract_and_assertions(self):
        context, beads, binary, git = map(Path, ("/context", "/db", "/bd", "/git"))
        for coordinated in (False, True):
            for expected, code, out, err, allowed in (
                (0, 0, "permission denied is data\n", "", True),
                (128, 128, "", "fatal: not a git repository\n", True),
                (0, 1, "", "", False), (0, 0, "", "sandbox denied", False),
                (128, 128, "unexpected", "not a git repository", False),
                (128, 128, "", "other refusal", False),
            ):
                result = subprocess.CompletedProcess("<fake>", code, out, err)
                execute = Mock(return_value=result)
                with patch.dict(NS, execute_child=execute):
                    args = (["/bd", "SECRET"], context, beads, binary, git)
                    if allowed:
                        self.assertEqual(NS["process"](*args, expected=expected,
                                                     coordinated=coordinated), out)
                    else:
                        with self.assertRaises(NS["Refusal"]):
                            NS["process"](*args, expected=expected, coordinated=coordinated)
                execute.assert_called_once_with(
                    ["/usr/bin/sandbox-exec", "-p", NS["policy"](context, beads, binary, git),
                     "/bd", "SECRET"], cwd=context / "run",
                    env=NS["environment"](context, beads, git), timeout=60,
                    pass_fds=(8,) if coordinated else ())

    def test_unsupported_runtime_refuses_before_spawn_or_mutation(self):
        def unsupported(*args):
            raise OSError(errno.ENOSYS, "SECRET")
        for target, name, value in (
            (NS["signal"], "getsignal", Mock(return_value=signal.SIG_IGN)),
            (NS["signal"], "getsignal", Mock(return_value=lambda *_: None)),
            (NS["threading"], "active_count", Mock(return_value=2)),
            (NS["os"], "waitid", unsupported),
        ):
            with self.subTest(name=name), patch.object(target, name, value), \
                    patch.object(NS["subprocess"], "Popen") as spawn, \
                    tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                with self.assertRaisesRegex(NS["Refusal"], "Beads (requires|waitid)"):
                    self.execute()
                with self.assertRaisesRegex(NS["Refusal"], "Beads (requires|waitid)"):
                    NS["qualify"]()
                for action in ("claim", "init", "run", "query"):
                    with patch.object(sys, "argv", ["bridge", action, str(root / "missing")]):
                        with self.assertRaisesRegex(NS["Refusal"], "Beads (requires|waitid)"):
                            NS["main"]()
                self.assertEqual(list(root.iterdir()), [])
                spawn.assert_not_called()
        with patch.object(NS["os"], "waitid") as waitid, \
                patch.object(NS["subprocess"], "Popen") as spawn:
            del NS["os"].waitid
            with self.assertRaisesRegex(NS["Refusal"], "waitid"):
                self.execute()
            spawn.assert_not_called()
            NS["os"].waitid = waitid

    def test_missing_darwin_libproc_refuses_before_spawn_and_mutation(self):
        for library in (Mock(side_effect=OSError("missing")),
                        Mock(return_value=SimpleNamespace()),
                        Mock(return_value=SimpleNamespace(proc_listpids=Mock(return_value=0)))):
            with self.subTest(library=library), patch.object(ctypes, "CDLL", library), \
                    patch.object(sys, "platform", "darwin"), \
                    patch.dict(NS, _DARWIN_LISTPIDS=None), \
                    patch.object(NS["subprocess"], "Popen") as spawn, \
                    tempfile.TemporaryDirectory() as temp:
                with self.assertRaisesRegex(NS["Refusal"], "requires working Darwin libproc"):
                    self.execute()
                with self.assertRaisesRegex(NS["Refusal"], "requires working Darwin libproc"):
                    NS["qualify"]()
                for action in ("claim", "init", "run", "query"):
                    with patch.object(sys, "argv", ["bridge", action, str(Path(temp) / "missing")]):
                        with self.assertRaisesRegex(NS["Refusal"], "requires working Darwin libproc"):
                            NS["main"]()
                spawn.assert_not_called()
                self.assertEqual(list(Path(temp).iterdir()), [])

    def real(self, code, timeout=FUNCTIONAL_SECONDS, pass_fds=(), cwd=ROOT, env=None):
        return NS["execute_child"](
            [sys.executable, "-I", "-S", "-B", "-c", code], cwd=cwd,
            env=dict(os.environ) if env is None else env, timeout=timeout, pass_fds=pass_fds)

    def natural(self, code, **kwargs):
        return self.real(code, **kwargs)  # Happy paths MUST succeed, including Darwin.

    @unittest.skipUnless(sys.platform == "darwin", "Darwin libproc primitive")
    def test_real_api_only_disposable_owned_retained_group(self):
        NS["require_execution_support"]()
        child = ("import os,signal,sys,time\n"
                 "pid=os.fork()\n"
                 "if pid==0: time.sleep(20); os._exit(0)\n"
                 "print('pair',flush=True)\n"
                 "sys.stdin.read(1)\n"
                 "os.kill(pid,signal.SIGKILL); os.waitpid(pid,0)\n"
                 "print('solo',flush=True)\n"
                 "sys.stdin.read(1)\n")
        proc = subprocess.Popen([sys.executable, "-I", "-S", "-B", "-c", child],
                                start_new_session=True, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(proc.stdout.readline(), "pair\n")
            # Two matching PIDs fill the tiny buffer; production must refuse.
            with self.assertRaises(NS["Refusal"]):
                NS["darwin_group_pids"](proc.pid)
            proc.stdin.write("x")
            proc.stdin.flush()
            self.assertEqual(proc.stdout.readline(), "solo\n")
            self.assertEqual(NS["darwin_group_pids"](proc.pid), (proc.pid,))
            self.assertIsNone(os.waitid(os.P_PID, proc.pid,
                                       os.WEXITED | os.WNOHANG | os.WNOWAIT))
            proc.stdin.close()
            deadline = time.monotonic() + 2
            while os.waitid(os.P_PID, proc.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is None:
                self.assertLess(time.monotonic(), deadline)
                time.sleep(.01)
            self.assertIn(NS["darwin_group_pids"](proc.pid), ((), (proc.pid,)))
            self.assertIsNone(proc.returncode)  # Still exclusively unreaped.
        finally:
            # Only this disposable, still-retained group; never after wait().
            status = os.waitid(os.P_PID, proc.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
            if status is None:
                os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=2)
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                stream.close()
        self.assertEqual(proc.returncode, 0)

    def test_real_utf8_boundaries_newlines_and_natural_exit(self):
        code = ("import os,time; os.write(1,b'a\\r'); time.sleep(.03);"
                "os.write(1,b'\\n\\xe2'); time.sleep(.03);"
                "os.write(1,b'\\x82\\xac\\rZ'); os.write(2,b'err\\r\\n'); raise SystemExit(7)")
        result = self.natural(code)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (7, "a\n€\nZ", "err\n"))

    def test_real_large_simultaneous_streams(self):
        result = self.natural(
            "import os,threading; n=128;"
            "t=threading.Thread(target=lambda: [os.write(2,b'e'*65536) for _ in range(n)]);"
            "t.start(); [os.write(1,b'o'*65536) for _ in range(n)]; t.join()",
            timeout=FUNCTIONAL_SECONDS)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "o" * (128 * 65536))
        self.assertEqual(result.stderr, "e" * (128 * 65536))

    def test_real_timeout_and_own_group_pipe_cleanup(self):
        # Fork only our own harmless group member. Inherited pipes closing
        # proves its termination; never probe/signal a numeric foreign PID.
        start = time.monotonic()
        original = subprocess.Popen
        readiness = {}

        def spawn(*args, **kwargs):
            proc = original(*args, **kwargs)
            # execute_child starts its deadline AFTER Popen returns. Leave
            # output untouched for its real pipe draining/cleanup assertions.
            # On readiness failure still return the owned handle for cleanup.
            readiness["seen"] = bool(select.select(
                [proc.stdout], [], [], READINESS_SECONDS)[0])
            readiness["at"] = time.monotonic()
            return proc

        with patch.object(NS["subprocess"], "Popen", spawn), \
                self.assertRaises(NS["ExecutionFailure"]) as caught:
            self.real("import os,time; pid=os.fork();"
                      "time.sleep(60) if pid==0 else os.write(1,b'partial\\n')", timeout=.2)
        self.assertTrue(readiness["seen"], "child did not become ready")
        self.assertIsInstance(caught.exception.failure, subprocess.TimeoutExpired)
        self.assertEqual(caught.exception.failure.timeout, .2)
        self.assertFalse(caught.exception.cleanup)
        self.assertEqual(caught.exception.stdout, "partial\n")
        self.assertGreaterEqual(time.monotonic() - readiness["at"], .2)
        self.assertLess(time.monotonic() - readiness["at"], 5.5)
        self.assertLess(time.monotonic() - start, FUNCTIONAL_SECONDS)

    def test_real_gate_inheritance_session_stdin_cwd_env(self):
        # A subprocess owns disposable FD8: never replace an existing caller
        # descriptor. It extracts the same production function independently.
        with tempfile.TemporaryDirectory() as temp:
            driver = """
import fcntl,os,pathlib,select,sys,time
source=pathlib.Path(sys.argv[1]).read_text()
code=source.split("<<'DOM_BEADS_PY'\\n",1)[1].split("\\nDOM_BEADS_PY",1)[0]
ns={}
exec(code.split("\\ntry:\\n    main()",1)[0],ns)
gate=pathlib.Path(sys.argv[2])/"gate"
fd=os.open(gate,os.O_CREAT|os.O_RDWR,0o600)
os.dup2(fd,8) if fd != 8 else None
fcntl.flock(8,fcntl.LOCK_EX)
child='''import os,sys
assert os.getpid()==os.getsid(0)==os.getpgrp()
assert os.read(0,1)==b""
assert os.environ["ONLY"]=="allowed"
assert os.stat("gate").st_ino==os.fstat(8).st_ino
print("gate inherited")
'''
result=ns["execute_child"]([sys.executable,"-I","-S","-B","-c",child],
    cwd=gate.parent,env={"ONLY":"allowed"},timeout=FUNCTIONAL_SECONDS,pass_fds=(8,))
assert result.returncode==0, result.returncode
assert result.stdout=="gate inherited\\n", result.stdout
os.close(8)
if fd != 8: os.close(fd)

# Transfer the only locked descriptor to a live child, then close the
# controller's copy. Its inherited gate must survive until timeout kills it.
fd=os.open(gate,os.O_RDWR)
if fd != 8:
    os.dup2(fd,8)
    os.close(fd)
fcntl.flock(8,fcntl.LOCK_EX)
original=ns["subprocess"].Popen
probe=os.open(gate,os.O_RDWR)
readiness={}
def spawn(*args,**kwargs):
    proc=original(*args,**kwargs)
    os.close(8)
    try: fcntl.flock(probe,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError: pass
    else: raise AssertionError("live native leader lost inherited gate")
    readiness["seen"]=bool(select.select([proc.stdout],[],[],READINESS_SECONDS)[0])
    readiness["at"]=time.monotonic()
    return proc
ns["subprocess"].Popen=spawn
try:
    ns["execute_child"]([sys.executable,"-I","-S","-B","-c",
        "import os,time; os.fstat(8); print('live',flush=True); time.sleep(60)"],
        cwd=gate.parent,env={},timeout=.2,pass_fds=(8,))
except ns["ExecutionFailure"] as exc:
    assert readiness["seen"], "child did not become ready"
    assert isinstance(exc.failure,ns["subprocess"].TimeoutExpired)
    assert exc.failure.timeout==.2
    assert not exc.cleanup
    assert exc.stdout=="live\\n"
    assert .2<=time.monotonic()-readiness["at"]<5.5
else: raise AssertionError("timeout did not fire")
finally: ns["subprocess"].Popen=original
fcntl.flock(probe,fcntl.LOCK_EX|fcntl.LOCK_NB)
os.close(probe)
"""
            driver = (f"FUNCTIONAL_SECONDS={FUNCTIONAL_SECONDS}\n"
                      f"READINESS_SECONDS={READINESS_SECONDS}\n" + driver)
            result = self.natural("import sys; exec(" + repr(driver.replace(
                "sys.argv[1]", repr(str(ROOT / "domestique2.sh"))).replace(
                "sys.argv[2]", repr(temp))) + ")", timeout=FUNCTIONAL_SECONDS)
            self.assertEqual((result.returncode, result.stderr), (0, ""))


if __name__ == "__main__":
    unittest.main()
