"""Stdlib runner/report regressions. Synthetic reports are NOT native evidence."""
import copy
import argparse
from contextlib import contextmanager
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location("acceptance", Path(__file__).with_name("acceptance.py"))
A = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(A)


class AcceptanceTests(unittest.TestCase):
    @contextmanager
    def expire_after(self, ready):
        """Real children/identities, controlled supervisor clock (not ps latency)."""
        clock = mock.Mock(wraps=time)
        clock.monotonic.return_value = time.monotonic()
        original = A.process_table
        expired = False
        limit = time.monotonic() + 10

        def inspect(deadline, **kwargs):
            nonlocal expired
            if time.monotonic() >= limit:
                raise A.ProcessInspectionError("real-child readiness protocol exceeded 10 seconds")
            with mock.patch.object(A, "time", time):
                table = original(time.monotonic() + 5, **kwargs)
            if not expired and ready(table):
                clock.monotonic.return_value = deadline
                expired = True
            return table

        with mock.patch.object(A, "time", clock), \
                mock.patch.object(A, "process_table", side_effect=inspect):
            yield

    def test_inspection_allowance_and_actual_remaining_deadline(self):
        row = "123 1 123 S Mon Sep 14 10:00:00 2026\n"
        for remaining, duration, expected in ((30, 1.5, 5), (.25, .1, .25),
                                               (.25, 1.5, .25), (30, 6, 5)):
            with self.subTest(remaining=remaining, duration=duration):
                clock = mock.Mock(wraps=time)
                clock.monotonic.return_value = 100

                def inspect(argv, **kw):
                    self.assertEqual(kw["timeout"], expected)
                    clock.monotonic.return_value += min(duration, kw["timeout"])
                    if duration > kw["timeout"]:
                        raise subprocess.TimeoutExpired(argv, kw["timeout"])
                    return subprocess.CompletedProcess(argv, 0, row, "")

                with mock.patch.object(A, "time", clock), \
                        mock.patch.object(A.subprocess, "run", side_effect=inspect):
                    if duration > expected:
                        with self.assertRaises(A.ProcessInspectionError) as failure:
                            A.process_table(100 + remaining)
                        self.assertIsInstance(failure.exception.__cause__, subprocess.TimeoutExpired)
                        self.assertEqual(A.failure_status(failure.exception),
                                         {"status": "INCOMPLETE", "failure_kind": "supervision"})
                    else:
                        self.assertEqual(A.process_table(100 + remaining)[123],
                                         (1, 123, "S", "Mon Sep 14 10:00:00 2026"))
                self.assertLessEqual(clock.monotonic(), 100 + remaining)
        with mock.patch.object(A.time, "monotonic", return_value=100), \
                mock.patch.object(A.subprocess, "run") as run, \
                self.assertRaises(A.ProcessInspectionError):
            A.process_table(100)
        run.assert_not_called()

    def test_slow_inspection_does_not_abort_real_child(self):
        clock = mock.Mock(wraps=time)
        offset = 0
        clock.monotonic.side_effect = lambda: time.monotonic() + offset
        original = subprocess.run
        allowances = []

        def inspect(argv, **kw):
            nonlocal offset
            allowances.append(kw["timeout"])
            if len(allowances) == 1:
                if kw["timeout"] < 1.5:
                    raise subprocess.TimeoutExpired(argv, kw["timeout"])
                offset += 1.5
            return original(argv, **kw)

        with mock.patch.object(A, "time", clock), \
                mock.patch.object(A.subprocess, "run", side_effect=inspect):
            self.assertEqual(A.execute([sys.executable, "-c", "print('healthy')"],
                                       dict(os.environ), 30), ("healthy\n", "", 0))
        self.assertEqual(allowances[0], 5)

    def test_single_transient_inspection_recovers_only_fresh_snapshot(self):
        # Synthetic reproduction of dob5a35l's exception/remaining allowance,
        # not evidence of native ps latency or an explanation of the host stall.
        clock = mock.Mock(wraps=time)
        clock.monotonic.return_value = 100
        partial = "999 1 999 S Mon Sep 14 10:00:00 2026\n"
        fresh = "123 1 123 S Mon Sep 14 10:01:00 2026\n"
        calls = []

        def inspect(argv, **kw):
            calls.append(kw["timeout"])
            if len(calls) == 1:
                clock.monotonic.return_value += 5
                raise subprocess.TimeoutExpired(argv, 5, output=partial, stderr="private fixture")
            return subprocess.CompletedProcess(argv, 0, fresh, "")

        diagnostic = io.StringIO()
        with mock.patch.object(A, "time", clock), \
                mock.patch.object(A.subprocess, "run", side_effect=inspect), \
                mock.patch.object(sys, "stderr", diagnostic):
            table = A.process_table(100 + 8751.503281)
        self.assertEqual(set(table), {123})
        self.assertEqual(calls, [5, 5])
        self.assertIn("PROCESS_INSPECTION_RECOVERED", diagnostic.getvalue())
        self.assertNotIn("private fixture", diagnostic.getvalue())
        self.assertNotIn("999", diagnostic.getvalue())

    def test_retry_caps_remaining_deadline_and_never_accepts_late_snapshot(self):
        for remaining, late, expected_calls in ((5, False, [5]), (5.25, False, [5, .25]),
                                                 (5.25, True, [5, .25])):
            with self.subTest(remaining=remaining, late=late):
                clock = mock.Mock(wraps=time)
                clock.monotonic.return_value = 100
                calls, recovered = [], mock.Mock()

                def inspect(argv, **kw):
                    calls.append(kw["timeout"])
                    if len(calls) == 1:
                        clock.monotonic.return_value += 5
                        raise subprocess.TimeoutExpired(argv, 5)
                    clock.monotonic.return_value += .25 if late else .1
                    return subprocess.CompletedProcess(
                        argv, 0, "123 1 123 S Mon Sep 14 10:00:00 2026\n", "")

                with mock.patch.object(A, "time", clock), \
                        mock.patch.object(A.subprocess, "run", side_effect=inspect):
                    if remaining == 5 or late:
                        with self.assertRaises(A.ProcessInspectionError):
                            A.process_table(100 + remaining, recovered=recovered)
                        recovered.assert_not_called()
                    else:
                        self.assertIn(123, A.process_table(100 + remaining, recovered=recovered))
                        recovered.assert_called_once_with()
                self.assertEqual(calls, expected_calls)

    def test_retry_repeated_timeout_or_nonretriable_failure_is_explicit(self):
        timeout = subprocess.TimeoutExpired("/bin/ps", 5, output="partial")
        valid = subprocess.CompletedProcess("ps", 0,
                                             "123 1 123 S Mon Sep 14 10:00:00 2026\n", "")
        for error in (timeout, OSError("unavailable"),
                      subprocess.CalledProcessError(7, "/bin/ps"),
                      subprocess.CompletedProcess("ps", 0, valid.stdout + "malformed\n", "")):
            for first_timeout in (False, True):
                if error is timeout and not first_timeout:
                    continue
                with self.subTest(error=error, first_timeout=first_timeout):
                    effects = ([timeout] if first_timeout else []) + [error, valid]
                    recovered = mock.Mock()
                    with mock.patch.object(A.subprocess, "run", side_effect=effects) as run, \
                            self.assertRaises(A.ProcessInspectionError):
                        A.process_table(time.monotonic() + 30, recovered=recovered)
                    self.assertEqual(run.call_count, 2 if first_timeout else 1)
                    recovered.assert_not_called()

    def test_work_cancellation_or_fail_fast_prevents_retry(self):
        for event, error in (("cancel", A.Cancelled), ("failed", A.FailFast)):
            control = A.Control(30)

            def inspect(argv, **kw):
                getattr(control, event).set()
                raise subprocess.TimeoutExpired(argv, kw["timeout"], output="partial")

            recovered = mock.Mock()
            with self.subTest(event=event), \
                    mock.patch.object(A.subprocess, "run", side_effect=inspect) as run, \
                    self.assertRaises(error):
                A.process_table(control.work_deadline, check=control.check, recovered=recovered)
            self.assertEqual(run.call_count, 1)
            recovered.assert_not_called()

    def test_transient_cleanup_retry_ignores_cancel_and_retains_real_child(self):
        # A real benign owned child; only the inspector timeout is synthetic.
        control = A.Control(30)
        original = subprocess.run
        injected, children, signals = [], [], []
        killpg = os.killpg

        def inspect(argv, **kw):
            if control.cancel.is_set() and not injected:
                injected.append(True)
                raise subprocess.TimeoutExpired(argv, kw["timeout"], output="partial")
            return original(argv, **kw)

        def group(pid, sig):
            self.assertIsNone(children[0].proc.returncode)
            self.assertFalse(children[0].leader.released)
            signals.append(sig)
            return killpg(pid, sig)

        diagnostic = io.StringIO()
        with mock.patch.object(A.subprocess, "run", side_effect=inspect), \
                mock.patch.object(A.os, "killpg", side_effect=group), \
                mock.patch.object(sys, "stderr", diagnostic), \
                self.assertRaises(A.Cancelled):
            with A.supervised_process([sys.executable, "-c", "import time; time.sleep(30)"],
                                      dict(os.environ), 30, control) as child:
                children.append(child)
                child.check()
                control.cancel.set()
                child.check()
        self.assertEqual(injected, [True])
        self.assertEqual(signals, [signal.SIGTERM, signal.SIGKILL])
        self.assertIsNotNone(children[0].proc.returncode)
        self.assertTrue(children[0].leader.released)
        self.assertEqual(control.inspection_recoveries, 1)
        self.assertIn("PROCESS_INSPECTION_RECOVERED", diagnostic.getvalue())

    def test_failed_or_malformed_inspection_is_not_empty_success(self):
        padded = "    1     0     1 Ss   Mon Sep  7 13:51:50 2026    \n"
        with mock.patch.object(A.subprocess, "run",
                               return_value=subprocess.CompletedProcess("ps", 0, padded, "")):
            self.assertEqual(A.process_table(time.monotonic() + 30)[1],
                             (0, 1, "Ss", "Mon Sep  7 13:51:50 2026    "))
        for stdout in ("", "\n", "123 1\n", "bad 1 123 S Mon Sep 14 10:00:00 2026",
                       "123 1 123 S invalid birth",
                       "123 1 123 S Mon Sep 14 10:00:00 2026\n" * 2):
            with self.subTest(stdout=stdout), \
                    mock.patch.object(A.subprocess, "run",
                                      return_value=subprocess.CompletedProcess("ps", 0, stdout, "")), \
                    self.assertRaises(A.ProcessInspectionError):
                A.process_table(time.monotonic() + 30)
        for cause in (OSError("inspection unavailable"),
                      subprocess.CalledProcessError(7, "/bin/ps", stderr="inspection denied")):
            with self.subTest(cause=cause), \
                    mock.patch.object(A.subprocess, "run", side_effect=cause), \
                    self.assertRaises(A.ProcessInspectionError) as failure:
                A.process_table(time.monotonic() + 30)
            self.assertIn(str(cause), str(failure.exception))
            self.assertIs(failure.exception.__cause__, cause)

    def discovery(self):
        return {"date": "2026-09-13T01:00:00+00:00", "scope": "synthetic test only",
                "counts": {"BLOCKED": 1, "NATIVE_DISCOVERY_OBSERVED": 0,
                           "ASSERTION_FAILURE": 0, "STATIC_ONLY": 0},
                "results": [{"component": "prerequisite", "status": "BLOCKED",
                             "blocker_kind": "absent-tool",
                             "diagnostic": "sandbox unavailable; no client invoked"}]}

    def test_process_state_native_grammars(self):
        states = [*"?IRSTUZDtWXxPK",
                  *("R" + flag for flag in "+<>AELNSsVWX"),
                  *("D" + flag for flag in "<NLsl+"),
                  "RWNA", "Ss", "R<", "S+Es", "SNLs+", "Ssl+", "I<", "Zs", "ZX",
                  "?s", "?+"]
        for state in states:
            with self.subTest(state=state), \
                    mock.patch.object(A.subprocess, "run", return_value=
                                      subprocess.CompletedProcess("ps", 0,
                                          f"123 1 123 {state} Mon Sep 14 10:00:00 2026\n", "")):
                self.assertEqual(A.process_table(time.monotonic() + 5)[123][2], state)

    def test_malformed_process_states_fail_closed(self):
        states = ("Zgarbage", "SZ", "RZ", "ZZ", "Z+Z", "s", "<Z", "S++", "Q",
                  "", " ", "\t", "Z\0", "Z\x1f", "Z\r", "Z\v", "Z\f", "Z\x7f",
                  "Z\u0085", "Z\u2028", "S Z", "Z\n")
        for state in states:
            with self.subTest(state=state), \
                    mock.patch.object(A.subprocess, "run", return_value=
                                      subprocess.CompletedProcess("ps", 0,
                                          f"123 1 123 {state} Mon Sep 14 10:00:00 2026\n", "")), \
                    self.assertRaises(A.ProcessInspectionError):
                A.process_table(time.monotonic() + 5)

    def test_actual_native_process_table_live_and_zombie(self):
        child = subprocess.Popen([sys.executable, "-c", "pass"])
        try:
            deadline = time.monotonic() + 5
            while True:
                table = A.process_table(deadline)
                self.assertEqual(table[os.getpid()][0], os.getppid())
                self.assertNotEqual(table[os.getpid()][2][0], "Z")
                self.assertEqual(table[child.pid][0], os.getpid())
                if table[child.pid][2][0] == "Z":
                    break
                time.sleep(.02)
        finally:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=5)

    @contextmanager
    def fail_completed_child_cleanup(self):
        original_table, original_observe = A.process_table, A.RetainedChild.observe
        children, injected = [], []

        def observe(leader):
            if leader not in children:
                children.append(leader)
            return original_observe(leader)

        def inspect(deadline, **kwargs):
            if children and children[0].completed is not None and not injected:
                error = A.ProcessInspectionError("injected completed-child cleanup inspection")
                injected.append(error)
                raise error
            return original_table(deadline, **kwargs)

        with mock.patch.object(A.RetainedChild, "observe", observe), \
                mock.patch.object(A, "process_table", side_effect=inspect):
            yield injected
        self.assertEqual(len(injected), 1)

    @contextmanager
    def synthetic_child(self, rc=7):
        """No real PID is owned or signalled in ownership/reuse regressions."""
        proc = mock.Mock(pid=987654, returncode=None, stdin=None)
        streams = []
        for data in (b"child stdout\n", b"child stderr\n"):
            read, write = os.pipe()
            os.write(write, data)
            os.close(write)
            streams.append(os.fdopen(read, "r"))
        proc.stdout, proc.stderr = streams
        events = []
        proc.poll.side_effect = AssertionError("poll would release kernel ownership")
        proc.communicate.side_effect = AssertionError("communicate would reap")

        def reap(**kw):
            events.append("reap")
            proc.returncode = rc
            return rc

        proc.wait.side_effect = reap

        def observe(*args):
            self.assertEqual(args, (os.P_PID, proc.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT))
            self.assertIsNone(proc.returncode)
            events.append("observe")
            return types.SimpleNamespace(si_pid=proc.pid, si_code=os.CLD_EXITED, si_status=rc)

        def group(pid, sig):
            self.assertEqual(pid, proc.pid)
            self.assertNotIn("reap", events)
            events.append(sig)

        table = {proc.pid: (os.getpid(), proc.pid, "Z", "Mon Sep 14 10:00:00 2026")}
        try:
            with mock.patch.object(A.subprocess, "Popen", return_value=proc), \
                    mock.patch.object(A.os, "waitid", side_effect=observe) as waitid, \
                    mock.patch.object(A.os, "killpg", side_effect=group) as killpg, \
                    mock.patch.object(A.os, "kill") as kill, \
                    mock.patch.object(A, "process_table", return_value=table) as inspect:
                yield proc, table, events, waitid, killpg, kill, inspect
        finally:
            for stream in streams:
                stream.close()

    def test_retained_leader_no_reap_before_last_group_signal(self):
        with self.synthetic_child() as (proc, _, events, _, killpg, kill, _):
            self.assertEqual(A.execute(["synthetic"], {}, 5),
                             ("child stdout\n", "child stderr\n", 7))
            self.assertEqual(killpg.call_count, 2)
            kill.assert_not_called()
            proc.poll.assert_not_called()
            proc.communicate.assert_not_called()
            self.assertLess(events.index(signal.SIGKILL), events.index("reap"))

    def test_live_leader_retention_through_cancellation_and_last_signal(self):
        with self.synthetic_child(rc=-signal.SIGTERM) as (
                proc, table, events, waitid, killpg, _, _):
            row = table[proc.pid]
            table[proc.pid] = (*row[:2], "S", row[3])
            original = killpg.side_effect

            def group(pid, sig):
                original(pid, sig)
                table[proc.pid] = row

            killpg.side_effect = group
            waitid.side_effect = lambda *_: (
                types.SimpleNamespace(si_pid=proc.pid, si_code=os.CLD_KILLED,
                                      si_status=signal.SIGTERM)
                if signal.SIGTERM in events else None)
            control = A.Control(5)
            control.check = mock.Mock(side_effect=[None, None, A.Cancelled("cancel live child")])
            with self.assertRaises(A.Cancelled) as failure:
                A.execute(["synthetic"], {}, 5, control)
            self.assertEqual(failure.exception.output, "child stdout\n")
            self.assertEqual(killpg.call_count, 2)
            self.assertLess(events.index(signal.SIGKILL), events.index("reap"))
            proc.poll.assert_not_called()
            proc.communicate.assert_not_called()

    def test_exact_different_birth_reused_pid_pgid_probe_is_rejected(self):
        with self.synthetic_child() as (proc, table, _, _, killpg, kill, inspect):
            foreign = {proc.pid: (os.getpid(), proc.pid, "S", "Mon Sep 14 10:01:00 2026")}
            inspect.side_effect = [table, foreign, foreign, foreign]
            with self.assertRaisesRegex(A.SupervisionError, "contradicts") as failure:
                A.execute(["synthetic"], {}, 5)
            killpg.assert_not_called()
            kill.assert_not_called()
            self.assertEqual((failure.exception.returncode, failure.exception.output,
                              failure.exception.stderr),
                             (7, "child stdout\n", "child stderr\n"))

    def test_echild_lost_ownership_never_signals_foreign_group(self):
        for completed in (False, True):
            with self.subTest(completed=completed), self.synthetic_child() as (
                    proc, _, _, waitid, killpg, kill, _):
                observe = waitid.side_effect
                calls = 0

                def lost(*args):
                    nonlocal calls
                    calls += 1
                    if completed and calls <= 2:
                        return observe(*args)
                    raise ChildProcessError("ECHILD: competing reaper")

                waitid.side_effect = lost
                with self.assertRaisesRegex(A.SupervisionError, "ownership"):
                    A.execute(["synthetic"], {}, 5)
                killpg.assert_not_called()
                kill.assert_not_called()
                proc.poll.assert_not_called()

    def test_unsupported_retention_fails_before_launch_without_signal_changes(self):
        for handler in (signal.SIG_IGN, lambda *_: None):
            with self.subTest(handler=handler), \
                    mock.patch.object(A.signal, "getsignal", return_value=handler), \
                    mock.patch.object(A.signal, "signal") as change, \
                    mock.patch.object(A.subprocess, "Popen") as spawn, \
                    self.assertRaises(A.SupervisionError):
                A.execute(["synthetic"], {}, 5)
            spawn.assert_not_called()
            change.assert_not_called()
        with mock.patch.object(A.os, "waitid"):
            del A.os.waitid
            with mock.patch.object(A.subprocess, "Popen") as spawn, \
                    self.assertRaises(A.SupervisionError):
                A.execute(["synthetic"], {}, 5)
            spawn.assert_not_called()

    def test_reaped_or_contradictory_child_permanently_revokes_signals(self):
        for contradiction in ("reaped", "parent", "group", "missing", "status"):
            with self.subTest(contradiction=contradiction), self.synthetic_child() as (
                    proc, table, _, waitid, killpg, kill, inspect):
                def changed(_deadline, **_kwargs):
                    if contradiction == "reaped":
                        proc.returncode = 7
                    if contradiction == "missing":
                        return {}
                    row = table[proc.pid]
                    return {proc.pid: (0 if contradiction == "parent" else row[0],
                                       1 if contradiction == "group" else row[1], *row[2:])}

                inspect.side_effect = changed
                if contradiction == "status":
                    waitid.return_value = types.SimpleNamespace(si_pid=1, si_code=os.CLD_EXITED,
                                                                si_status=7)
                    waitid.side_effect = None
                with self.assertRaises(A.SupervisionError):
                    A.execute(["synthetic"], {}, 5)
                killpg.assert_not_called()
                kill.assert_not_called()

    def test_drain_failure_has_no_post_reap_signal_fallback(self):
        with self.synthetic_child() as (proc, _, events, _, killpg, _, _), \
                mock.patch.object(A.PipeDrain, "finish", side_effect=OSError("drain failed")), \
                self.assertRaisesRegex(A.SupervisionError, "drain failed"):
            A.execute(["synthetic"], {}, 5)
        self.assertEqual(killpg.call_count, 2)
        self.assertLess(events.index(signal.SIGKILL), events.index("reap"))
        proc.communicate.assert_not_called()

    def test_ownership_lost_between_signals_blocks_kill(self):
        with self.synthetic_child() as (_, _, events, waitid, killpg, _, _):
            original = waitid.side_effect

            def lost(*args):
                if signal.SIGTERM in events:
                    raise ChildProcessError("ECHILD after TERM")
                return original(*args)

            waitid.side_effect = lost
            with self.assertRaisesRegex(A.SupervisionError, "ECHILD after TERM"):
                A.execute(["synthetic"], {}, 5)
            self.assertEqual([call.args[1] for call in killpg.call_args_list], [signal.SIGTERM])

    def test_individual_descendant_reuse_gets_fresh_birth_check(self):
        with self.synthetic_child() as (proc, table, _, _, _, kill, inspect):
            child = proc.pid + 1
            initial = {**table, child: (proc.pid, child, "S", "Mon Sep 14 10:00:00 2026")}
            foreign = {**table, child: (1, child, "S", "Mon Sep 14 10:01:00 2026")}
            inspect.side_effect = [initial, initial, foreign, foreign, foreign]
            self.assertEqual(A.execute(["synthetic"], {}, 5)[2], 7)
            kill.assert_not_called()

    def test_known_surviving_descendant_cannot_return_success(self):
        with self.synthetic_child() as (proc, table, _, _, _, _, _):
            table[proc.pid + 1] = (proc.pid, proc.pid + 1, "S",
                                   "Mon Sep 14 10:00:00 2026")
            clock = mock.Mock(wraps=time)
            clock.monotonic.side_effect = iter(n / 10 for n in range(1000))
            clock.sleep.return_value = None
            with mock.patch.object(A, "time", clock), \
                    self.assertRaisesRegex(A.SupervisionError, "owned process cleanup incomplete"):
                A.execute(["synthetic"], {}, 5)

    def test_large_output_closed_streams_and_real_signal_exit(self):
        code = ("import os,sys\n"
                "for _ in range(64):\n"
                " os.write(1,b'o'*32768); os.write(2,b'e'*32768)\n"
                "sys.exit(7)\n")
        self.assertEqual(A.execute([sys.executable, "-c", code], dict(os.environ), 30),
                         ("o" * (2 * 1024 * 1024), "e" * (2 * 1024 * 1024), 7))
        code = "import os,signal; print('signal output',flush=True); os.kill(os.getpid(),signal.SIGUSR1)"
        self.assertEqual(A.execute([sys.executable, "-c", code], dict(os.environ), 30),
                         ("signal output\n", "", -signal.SIGUSR1))
        with tempfile.TemporaryDirectory() as temp:
            ready = Path(temp) / "ready"
            code = ("import os,pathlib,time; print('before close',flush=True);"
                    "os.close(1);os.close(2);"
                    f"pathlib.Path({str(ready)!r}).touch();time.sleep(60)")
            with self.expire_after(lambda table: ready.exists()), \
                    self.assertRaises(subprocess.TimeoutExpired) as failure:
                A.execute([sys.executable, "-c", code], dict(os.environ), 30)
            self.assertEqual(failure.exception.output, "before close\n")

    def test_completed_and_live_leaders_cleanup_observed_descendant_kinds(self):
        for completed in (True, False):
            for kind in ("ordinary", "background-closed-pipes", "new-session"):
                with self.subTest(completed=completed, kind=kind), tempfile.TemporaryDirectory() as temp:
                    pidfile, release = Path(temp) / "pid", Path(temp) / "release"
                    child = ("import os,pathlib,signal,time;"
                             "signal.signal(signal.SIGTERM,signal.SIG_IGN);"
                             f"pathlib.Path({str(pidfile)!r}).write_text(str(os.getpid()));"
                             "time.sleep(60)")
                    options = (",start_new_session=True" if kind == "new-session" else
                               ",stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL"
                               if kind == "background-closed-pipes" else "")
                    parent = ("import pathlib,subprocess,sys,time\n"
                              "print('leader output',flush=True)\n"
                              f"subprocess.Popen([sys.executable,'-c',{child!r}]{options})\n"
                              f"while not pathlib.Path({str(release)!r}).exists(): time.sleep(.01)\n"
                              "sys.exit(7)\n")
                    original = A.remember_descendants
                    observed = {}
                    control = A.Control(30)

                    def remember(proc, owned, table):
                        original(proc, owned, table)
                        observed.update(owned)
                        if pidfile.exists() and int(pidfile.read_text()) in owned:
                            if completed:
                                release.touch()
                            else:
                                control.cancel.set()

                    with mock.patch.object(A, "remember_descendants", side_effect=remember):
                        if completed:
                            self.assertEqual(A.execute([sys.executable, "-c", parent],
                                                       dict(os.environ), 30, control),
                                             ("leader output\n", "", 7))
                        else:
                            with self.assertRaises(A.Cancelled) as failure:
                                A.execute([sys.executable, "-c", parent], dict(os.environ), 30, control)
                            self.assertEqual(failure.exception.output, "leader output\n")
                    table = A.process_table(time.monotonic() + 5)
                    for pid, birth in observed.items():
                        row = table.get(pid)
                        self.assertTrue(row is None or row[3] != birth or row[2][0] == "Z")

    def test_completed_child_exit_and_output_survive_cleanup_failure(self):
        for rc in (7, 0):
            with self.subTest(rc=rc), self.fail_completed_child_cleanup() as injected, \
                    self.assertRaises(A.SupervisionError) as failure:
                A.execute([sys.executable, "-c",
                           "import sys; print('child stdout'); "
                           f"print('child stderr', file=sys.stderr); sys.exit({rc})"],
                          dict(os.environ), 30)
            error = failure.exception
            self.assertIs(error.__cause__, injected[0])
            self.assertEqual((error.returncode, error.output, error.stderr),
                             (rc, "child stdout\n", "child stderr\n"))
            self.assertIn(f"completed child exit: {rc}", str(error))
            self.assertNotIn("NoneType", str(error))
            if rc:
                self.assertIsInstance(error.primary_failure, subprocess.CalledProcessError)
                self.assertEqual((error.primary_failure.returncode,
                                  error.primary_failure.output, error.primary_failure.stderr),
                                 (rc, "child stdout\n", "child stderr\n"))
            else:
                self.assertIsNone(error.primary_failure)

    def test_cleanup_signals_are_not_primary_exit_and_preserve_original_exception(self):
        for primary in (subprocess.TimeoutExpired("synthetic budget", 30),
                        A.Cancelled("synthetic cancellation"), A.FailFast("synthetic fail-fast"),
                        A.ProcessInspectionError("synthetic inspection failure")):
            control = A.Control(30)
            original_table, original_remember = A.process_table, A.remember_descendants
            children = []
            cleanup_error = A.ProcessInspectionError("injected cleanup inspection")

            def remember(proc, owned, table):
                children.append(proc)
                original_remember(proc, owned, table)

            def inspect(deadline, **kwargs):
                if children:
                    raise cleanup_error
                return original_table(deadline, **kwargs)

            with self.subTest(primary=primary), \
                    mock.patch.object(control, "check", side_effect=[None, None, primary]), \
                    mock.patch.object(A, "remember_descendants", side_effect=remember), \
                    mock.patch.object(A, "process_table", side_effect=inspect), \
                    self.assertRaises(A.SupervisionError) as failure:
                A.execute([sys.executable, "-c", "import time; time.sleep(60)"],
                          dict(os.environ), 30, control)
            self.assertIs(failure.exception.primary_failure, primary)
            self.assertIs(failure.exception.__cause__, cleanup_error)
            self.assertFalse(hasattr(failure.exception, "returncode"))
            self.assertEqual(children[0].returncode, -signal.SIGTERM)

    def test_completed_child_cleanup_failure_persists_exit_and_logs(self):
        for rc in (7, 0):
            with self.subTest(rc=rc), tempfile.TemporaryDirectory() as temp:
                base = Path(temp).resolve()
                root, artifacts = base / "checkout", base / "artifacts"
                (root / "test").mkdir(parents=True)
                artifacts.mkdir()
                name = "completed-tests.py"
                (root / "test" / name).write_text(
                    "import sys\nprint('child stdout')\n"
                    f"print('child stderr', file=sys.stderr)\nsys.exit({rc})\n")
                original = A.tempfile.mkdtemp

                def create(**kw):
                    return (str(artifacts) if kw.get("prefix") == "domestique-acceptance-"
                            else original(**kw))

                with mock.patch.object(sys, "argv", ["acceptance.py"]), \
                        mock.patch.object(A, "ROOT", root), \
                        mock.patch.object(A, "selection", return_value=[("CURRENT", name)]), \
                        mock.patch.object(A.tempfile, "mkdtemp", side_effect=create), \
                        mock.patch.object(A, "provenance", return_value={"synthetic": True}), \
                        mock.patch("builtins.print"), self.fail_completed_child_cleanup():
                    self.assertEqual(A.main(), 1)
                report = json.loads((artifacts / "report.json").read_text())
                self.assertEqual((report["status"], report["exit"]), ("INCOMPLETE", 1))
                self.assertFalse(report["full_offline_acceptance"])
                row = report["results"][0]
                self.assertEqual((row["exit"], row["status"], row["failure_kind"]),
                                 (rc, "INCOMPLETE", "supervision"))
                if rc:
                    self.assertEqual(row["primary_failure"],
                                     {"type": "CalledProcessError", "status": "ASSERTION_FAILURE",
                                      "failure_kind": "error", "exit": rc})
                else:
                    self.assertNotIn("primary_failure", row)
                key = artifacts / ("CURRENT-" + name)
                self.assertEqual(Path(str(key) + ".stdout").read_text(), "child stdout\n")
                self.assertEqual(Path(str(key) + ".stderr").read_text(), "child stderr\n")
                diagnostic = Path(str(key) + ".error").read_text()
                self.assertIn("injected completed-child cleanup inspection", diagnostic)
                self.assertIn(f"completed child exit: {rc}", diagnostic)
                self.assertNotIn("NoneType", diagnostic)

    def context(self):
        return {"date": "2026-09-13T01:00:00+00:00", "scope": "synthetic test only",
                "proofs": {k: "PASS" if k == "cleanup" else "BLOCKED" for k in A.PROOFS},
                "counts": {"PASS": 1, "BLOCKED": 8, "FAILED": 0},
                "commands": [], "contexts": [], "limits": ["test only"],
                "source_pin": "synthetic", "binary": "/fixture/bd",
                "blocker": "sandbox unavailable", "blocker_kind": "absent-tool", "status": "BLOCKED"}

    def parse(self, report, name="native-discovery.py", rc=2):
        return A.native_report(name, json.dumps(report), rc)

    def test_valid_discovery_blocker(self):
        self.assertEqual(self.parse(self.discovery())["status"], "BLOCKED")

    def test_exit_two_is_not_evidence(self):
        for value in ({}, [], None, True, {"status": "BLOCKED"}, {"scope": "test"}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.parse(value)

    def test_malformed_json(self):
        with self.assertRaises(ValueError):
            A.native_report("native-discovery.py", "not JSON", 2)

    def test_discovery_missing_required_fields(self):
        for key in self.discovery():
            value = self.discovery()
            del value[key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.parse(value)

    def test_bad_counts(self):
        for bad in (-1, True, "1", 0, 2):
            value = self.discovery()
            value["counts"]["BLOCKED"] = bad
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.parse(value)

    def test_unknown_status(self):
        value = self.discovery()
        value["results"][0]["status"] = "SUCCESS"
        with self.assertRaises(ValueError):
            self.parse(value)

    def test_missing_diagnostic(self):
        value = self.discovery()
        del value["results"][0]["diagnostic"]
        with self.assertRaises(ValueError):
            self.parse(value)

    def test_wrong_exit(self):
        for rc in (0, 1, -9, 99):
            with self.subTest(rc=rc), self.assertRaises(ValueError):
                self.parse(self.discovery(), rc=rc)

    def test_assertion_not_blocker(self):
        value = self.discovery()
        value["results"].append({"component": "fixture", "status": "ASSERTION_FAILURE"})
        value["counts"]["ASSERTION_FAILURE"] = 1
        with self.assertRaises(ValueError):
            self.parse(value)

    def test_project_changes_not_static_success(self):
        value = self.discovery()
        value["results"][0]["changes"] = {"A": ["host-policy"], "B": []}
        with self.assertRaises(ValueError):
            self.parse(value)

    def test_observation_requires_context(self):
        value = self.discovery()
        value["results"][0]["status"] = "NATIVE_DISCOVERY_OBSERVED"
        value["counts"].update(BLOCKED=0, NATIVE_DISCOVERY_OBSERVED=1)
        with self.assertRaises(ValueError):
            self.parse(value, rc=0)

    def test_static_only_not_full_pass(self):
        value = self.discovery()
        value["results"][0]["status"] = "STATIC_ONLY"
        value["counts"].update(BLOCKED=0, STATIC_ONLY=1)
        for rc in (0, 2):
            with self.assertRaises(ValueError):
                self.parse(value, rc=rc)

    def test_valid_context_prerequisite_blocker(self):
        self.assertEqual(self.parse(self.context(), "beads-native-context.py")["status"], "BLOCKED")

    def test_context_required_fields(self):
        for key in self.context():
            value = self.context()
            del value[key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.parse(value, "beads-native-context.py")

    def test_context_proofs_must_be_complete(self):
        value = self.context()
        del value["proofs"]["IDENTITY_BINDING"]
        with self.assertRaises(ValueError):
            self.parse(value, "beads-native-context.py")

    def test_context_cleanup_failure(self):
        value = self.context()
        value["proofs"]["cleanup"] = "FAILED"
        value["counts"].update(PASS=0, FAILED=1)
        with self.assertRaises(ValueError):
            self.parse(value, "beads-native-context.py")

    def test_context_native_init_requires_provenance(self):
        value = self.context()
        value["proofs"]["native-init"] = "PASS"
        value["counts"].update(PASS=2, BLOCKED=7)
        with self.assertRaises(ValueError):
            self.parse(value, "beads-native-context.py")

    def test_production_report(self):
        value = {"scope": "synthetic", "production": "PASS", "checked_processes": 1,
                 "protected_host_leaves": 1, "protected_entries": 1,
                 "projects": ["A", "B", "W"], "mixed_provider_ordering": "PASS (actual native C)",
                 "native_fixture": {"path": "/synthetic/beads", "sha256": A.F.SHA256},
                 "native": "Beads 1.1.2 CGO embedded, Darwin arm64"}
        self.assertEqual(self.parse(value, "beads-production.py", 0)["status"], "NATIVE_OBSERVED")
        for key in value:
            broken = copy.deepcopy(value)
            del broken[key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.parse(broken, "beads-production.py", 0)
        with self.assertRaises(ValueError):
            self.parse(value, "beads-production.py", 2)

    def test_native_cleanup_exact_completion(self):
        line = ("NATIVE_FIXTURE=" + json.dumps({"path": "/synthetic/beads", "sha256": A.F.SHA256})
                + "\nbeads-cleanup: 92 checks; PINNED NATIVE; 10 native bd calls / "
                "20 instrumented process calls; ZERO cleanup-native calls\n")
        self.assertEqual(A.native_report("beads-cleanup.py", line, 0)["checks"], 92)
        for bad in (line + line, line.replace("ZERO", "1"),
                    line.replace("PINNED NATIVE", "SYNTHETIC ONLY"),
                    line.replace("92 checks", "0 checks"), "PASS"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                A.native_report("beads-cleanup.py", bad, 0)
        with self.assertRaises(ValueError):
            A.native_report("beads-cleanup.py", line, 2)

    def test_offline_completion(self):
        self.assertEqual(A.offline_report("private-core.sh", "private-core: 117 passed, 0 failed\n",
                                          "", 0)["checks"], 117)
        for out in ("", "117 passed", "private-core: 117 passed, 1 failed\n",
                    "private-core: 117 passed, 0 failed\nSKIP test\n",
                    "private-core: 117 passed, 0 failed\nFAIL: unexpected failure\n",
                    "private-core: 117 passed, 0 failed\n" * 2):
            with self.assertRaises(ValueError):
                A.offline_report("private-core.sh", out, "", 0)

    def test_offline_nonzero_not_success(self):
        with self.assertRaises(ValueError):
            A.offline_report("private-core.sh", "private-core: 117 passed, 0 failed\n", "", 1)

    def test_historical_pin_required(self):
        with self.assertRaises(ValueError):
            A.offline_report("codex.sh", "4/4 passed\n", "", 0)

    def test_unit_completion(self):
        self.assertEqual(A.offline_report("acceptance-tests.py", "",
                                          "Ran 24 tests in 0.2s\n\nOK\n", 0)["checks"], 24)
        with self.assertRaises(ValueError):
            A.offline_report("acceptance-tests.py", "", "Ran 24 tests in 0.2s\nOK (skipped=1)", 0)

    def inspection_example(self, name):
        """Synthetic grammar witness, never an execution/acceptance artifact."""
        f = A.INSPECTION
        tests = f.test_inventory(name)
        matrix = [row.name for row in f.MATRIX]
        cli = matrix + list(f.CLI_EXTRA_CASES) if name == "inspect-tests.py" else []
        sources = f.qualification_sources()
        origins = {key: dict(label="retained-private-preview" if key == "current" else key,
                              revision=revision, sha256=A.preview_fixture.sha256() if key == "current"
                              else "a" * 64, installer="/synthetic/" + key)
                   for key, revision in (("historical", f.HISTORICAL_PIN),
                                         ("pre-snapshot", f.PRE_SNAPSHOT_PIN),
                                         ("current", "a" * 40))}
        cohort = dict(
            origins=origins, setup_counts=f.SETUP_COUNTS.copy(), installer_seconds=1.0,
            declared_matrix_cases=len(matrix), root="/synthetic/owned", root_identity=[1, 2],
            native_calls=0, beads="synthetic metadata only", commands={
                "install": 6, "git-init": 5, "git-worktree": 1,
                "source-probe": 2, "source-read": 2, "source-revision": 1, "command": 100},
            command_seconds=2.0, forbidden_stubs=list(f.FORBIDDEN), cleaned=True,
            tools={tool: {"path": "/synthetic/" + tool, "sha256": "b" * 64}
                   for tool in ("python3", "bash", "git")})
        report = dict(
            suite=name, scope=f.QUALIFICATION_SUITES[name], coverage="COMPLETE_INSPECTION_SCOPE",
            explicit_selection=False, unittest=dict(run=len(tests), started=tests,
                successful=tests.copy(), failures=0, errors=0, skips=0, expected_failures=0,
                unexpected_successes=0), matrix_completed=matrix, matrix_count=len(matrix),
            cli_completed=cli, cli_count=len(cli), qualified_cohorts=[cohort],
            source_sha256=sources, source_unchanged=True,
            runtime=dict(python="3.14.7", system="darwin", machine="arm64"), elapsed_seconds=3.0,
            limits=f.QUALIFICATION_LIMITS)
        events = "".join(("CLI source-qualified: " if cli else "fixture oracle accepted: ") + v + "\n"
                         for v in cli or matrix)
        return report, events, f"Ran {len(tests)} tests in 3.0s\n\nOK\n"

    def test_inspection_registration_and_complete_scoped_report(self):
        for name in A.INSPECTION.QUALIFICATION_SUITES:
            with self.subTest(suite=name):
                self.assertEqual(A.CURRENT.count(name), 1)
                self.assertNotIn(name, A.QUICK + A.HISTORICAL + A.NATIVE)
                report, events, err = self.inspection_example(name)
                out = events + A.INSPECTION.QUALIFICATION_PREFIX + json.dumps(report) + "\n"
                result = A.offline_report(name, out, err, 0)
                self.assertEqual(result["inspection_qualification"], report)
                self.assertEqual(result["checks"], report["unittest"]["run"])
                with self.assertRaises(ValueError):
                    A.offline_report(name, "", "Ran 1 test in 0.1s\n\nOK\n", 0)
                # Fresh location-bound import, with no test directory on the
                # search path. Use the actual validator, not a subprocess stub.
                # The input remains a synthetic grammar witness, not evidence
                # that either complete inspection suite has executed.
                for mode in ("fresh", "preloaded", "foreign"):
                    code = (
                        "import dataclasses,importlib.util,json,pathlib,sys,types\n"
                        f"path=pathlib.Path({str(Path(A.__file__).resolve())!r})\n"
                        f"mode={mode!r}\n"
                        "search_path=sys.path.copy()\n"
                        "assert str(path.parent) not in sys.path\n"
                        "assert 'inspect_fixture' not in sys.modules\n"
                        "def load(name,path,register=False):\n"
                        "    s=importlib.util.spec_from_file_location(name,path)\n"
                        "    m=importlib.util.module_from_spec(s)\n"
                        "    if register: sys.modules[name]=m\n"
                        "    s.loader.exec_module(m)\n"
                        "    return m\n"
                        "if mode=='preloaded':\n"
                        "    public=load('inspect_fixture',path.with_name('inspect_fixture.py'),True)\n"
                        "elif mode=='foreign':\n"
                        "    public=types.ModuleType('inspect_fixture')\n"
                        "    public.__file__='/foreign/inspect_fixture.py'\n"
                        "    public.marker=object()\n"
                        "    sys.modules['inspect_fixture']=public\n"
                        "if mode!='fresh': original=vars(public).copy()\n"
                        "a=load('isolated_acceptance',path)\n"
                        "f=a.INSPECTION\n"
                        "matrix=f.MATRIX; scenario=f.Scenario; baseline=f.Baseline\n"
                        "assert sys.modules[f.__name__] is f\n"
                        "assert pathlib.Path(f.__file__).resolve()==path.with_name('inspect_fixture.py')\n"
                        "if mode=='preloaded': assert f is public\n"
                        "if mode=='foreign': assert f is not public\n"
                        "if mode=='fresh': assert sys.modules['inspect_fixture'] is f\n"
                        "name,out,err=json.load(sys.stdin)\n"
                        "for index in range(3):\n"
                        "    b=load('repeated_acceptance_'+str(index),path)\n"
                        "    assert b.INSPECTION is f\n"
                        "    assert b.INSPECTION.Scenario is scenario\n"
                        "    assert b.INSPECTION.Baseline is baseline\n"
                        "    assert b.INSPECTION.MATRIX is matrix\n"
                        "    assert b.INSPECTION.MATRIX==tuple(dataclasses.replace(r) for r in matrix)\n"
                        "    assert type(b.INSPECTION.MATRIX[0]) is scenario\n"
                        "    for runner in (a,b):\n"
                        "        result=runner.offline_report(name,out,err,0)\n"
                        "        assert result['inspection_qualification']['suite']==name\n"
                        "        assert result['checks']==len(f.test_inventory(name))\n"
                        "        try: runner.offline_report(name,out,err,1)\n"
                        "        except ValueError: pass\n"
                        "        else: raise AssertionError('accepted failed report')\n"
                        "if mode!='fresh':\n"
                        "    assert sys.modules['inspect_fixture'] is public\n"
                        "    assert vars(public)==original\n"
                        "assert sys.modules[f.__name__] is f\n"
                        "assert sys.path==search_path\n"
                        "print('isolated offline_report validated synthetic grammar')\n")
                    with self.subTest(module_mode=mode), tempfile.TemporaryDirectory() as temp:
                        child = subprocess.run(
                            [sys.executable, "-I", "-B", "-W", "error", "-c", code], cwd=temp,
                            input=json.dumps([name, out, err]), text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
                        self.assertEqual(child.returncode, 0, "isolated offline_report failed")
                        self.assertEqual(child.stderr, "")
                        self.assertEqual(child.stdout,
                                         "isolated offline_report validated synthetic grammar\n")
        sources = A.provenance(A.Control(10))["source_sha256"]
        self.assertLessEqual(set(A.INSPECTION.qualification_sources()), set(sources))

    def test_inspection_malformed_incomplete_duplicate_and_selected_reports(self):
        for name in A.INSPECTION.QUALIFICATION_SUITES:
            good, events, err = self.inspection_example(name)
            mutations = [
                lambda r: r.update(coverage="PARTIAL_INSPECTION_SCOPE"),
                lambda r: r.update(coverage="INCOMPLETE_INSPECTION_SCOPE"),
                lambda r: r.update(explicit_selection=True),
                lambda r: r.update(scope="native-ready"),
                lambda r: r.update(suite="acceptance-tests.py"),
                lambda r: r.update(source_unchanged=False),
                lambda r: r["source_sha256"].update({"domestique2.sh": "0" * 64}),
                lambda r: r["unittest"].update(run=1),
                lambda r: r["unittest"].update(run=True),
                lambda r: r["unittest"].update(skips=1),
                lambda r: r["unittest"].update(errors=1),
                lambda r: r["unittest"].update(expected_failures=1),
                lambda r: r["unittest"]["successful"].pop(),
                lambda r: r["unittest"]["started"].append(r["unittest"]["started"][0]),
                lambda r: r["unittest"]["successful"].__setitem__(0, "Invented.test_case"),
                lambda r: r["matrix_completed"].pop(),
                lambda r: r["matrix_completed"].append(r["matrix_completed"][0]),
                lambda r: r["matrix_completed"].__setitem__(0, "invented"),
                lambda r: r.update(matrix_count=True),
                lambda r: r.update(cli_count=-1),
                lambda r: r["cli_completed"].append("invented"),
                lambda r: r.update(qualified_cohorts=[]),
                lambda r: r["qualified_cohorts"].append(r["qualified_cohorts"][0]),
                lambda r: r["qualified_cohorts"][0].update(cleaned=False),
                lambda r: r["qualified_cohorts"][0]["setup_counts"].update(current_local=2),
                lambda r: r["qualified_cohorts"][0].update(native_calls=1),
                lambda r: r["qualified_cohorts"][0]["forbidden_stubs"].pop(),
                lambda r: r["qualified_cohorts"][0]["commands"].update(install=1),
                lambda r: r["qualified_cohorts"][0]["origins"]["historical"].update(revision="0" * 40),
                lambda r: r["qualified_cohorts"][0]["tools"].pop("git"),
                lambda r: r.update(runtime={}),
                lambda r: r["runtime"].update(python="not-a-version"),
                lambda r: r["runtime"].update(python="3.8.0"),
                lambda r: r.update(limits="native readiness"),
                lambda r: r.update(elapsed_seconds=float("nan")),
                lambda r: r.update(elapsed_seconds=1),
                lambda r: r.update(invented="extra"),
            ]
            if name == "inspect-tests.py":
                mutations += [
                    lambda r: r["cli_completed"].pop(),
                    lambda r: r["cli_completed"].append(r["cli_completed"][0]),
                    lambda r: r["cli_completed"].__setitem__(0, "invented"),
                ]
            for index, mutate in enumerate(mutations):
                bad = copy.deepcopy(good)
                mutate(bad)
                with self.subTest(suite=name, mutation=index), self.assertRaises(ValueError):
                    A.offline_report(name, events + A.INSPECTION.QUALIFICATION_PREFIX +
                                     json.dumps(bad) + "\n", err, 0)
            marker = A.INSPECTION.QUALIFICATION_PREFIX
            summary = marker + json.dumps(good) + "\n"
            for out in (events, events + marker + "{\n", events + marker + "[]\n",
                        events + summary * 2, summary, events + events + summary,
                        "invented\n" + summary, "\n".join(events.splitlines()[1:]) + "\n" + summary):
                with self.subTest(suite=name, shape=out[:40]), self.assertRaises(ValueError):
                    A.offline_report(name, out, err, 0)
            for stderr, rc in ((err, 1), (err + err, 0), (err.replace("OK", "OK (skipped=1)"), 0),
                               ("Ran 1 test in 0.1s\n\nOK\n", 0)):
                with self.assertRaises(ValueError):
                    A.offline_report(name, events + summary, stderr, rc)

    def test_inspection_actual_selected_unittest_summary_is_partial_without_setup(self):
        for name, selector in (
                ("inspect-tests.py", "MatrixCLIAssemblyTests"),
                ("inspect-fixture-tests.py", "ContractTests.test_named_matrix_and_exit_contract")):
            result = subprocess.run(
                [sys.executable, "-B", "-W", "error", str(A.ROOT / "test" / name), selector],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            prefix = A.INSPECTION.QUALIFICATION_PREFIX
            summary = [line[len(prefix):] for line in result.stdout.splitlines()
                       if line.startswith(prefix)]
            self.assertEqual(len(summary), 1)
            report = json.loads(summary[0])
            self.assertEqual(report["coverage"], "PARTIAL_INSPECTION_SCOPE")
            self.assertIs(report["explicit_selection"], True)
            self.assertEqual(report["qualified_cohorts"], [])
            self.assertEqual(report["matrix_completed"], [])
            self.assertEqual(report["cli_completed"], [])
            self.assertEqual(report["unittest"]["run"], len(report["unittest"]["successful"]))
            with self.assertRaises(ValueError):
                A.offline_report(name, result.stdout, result.stderr, result.returncode)

    def test_timeout_reaps_exact_process_group(self):
        with tempfile.TemporaryDirectory() as temp:
            pidfile = Path(temp) / "pid"
            code = ("import os,pathlib,time\n"
                    "print('started', flush=True)\n"
                    f"pathlib.Path({str(pidfile)!r}).write_text(str(os.getpid()))\n"
                    "time.sleep(60)\n")
            with self.expire_after(lambda table: pidfile.exists()), \
                    self.assertRaises(subprocess.TimeoutExpired) as failure:
                A.execute([sys.executable, "-c", code], dict(os.environ), 30)
            self.assertEqual(failure.exception.output, "started\n")
            with self.assertRaises(ProcessLookupError):
                os.kill(int(pidfile.read_text()), 0)

    def test_normal_exit_also_cleans_group(self):
        with mock.patch.object(A.os, "killpg", wraps=os.killpg) as kill:
            out, err, rc = A.execute([sys.executable, "-c", "print('done')"], dict(os.environ), 5)
        self.assertEqual((out, err, rc), ("done\n", "", 0))
        self.assertEqual(kill.call_count, 2)
        self.assertGreater(kill.call_args.args[0], 0)

    def test_stdin_is_devnull_and_cwd_is_checkout(self):
        code = "import os,sys; print(os.getcwd()); print(repr(sys.stdin.read()))"
        out, _, rc = A.execute([sys.executable, "-c", code], dict(os.environ), 5)
        self.assertEqual((out, rc), (str(A.ROOT) + "\n''\n", 0))

    def test_environment_is_allowlisted_and_private(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp).resolve()
            with mock.patch.dict(os.environ, {"UNRELATED_ENV": "fixture", "HTTP_PROXY": "fixture"}):
                env = A.environment(work)
            self.assertNotIn("UNRELATED_ENV", env)
            self.assertNotIn("HTTP_PROXY", env)
            self.assertEqual(env["HOME"], str(work / "home"))
            self.assertEqual(env["TMPDIR"], str(work / "tmp"))
            self.assertTrue((work / "template/info/exclude").is_file())
            self.assertEqual(A.execute([str(work / "forbidden/bd")], env, 5)[2], 99)

    def test_inventory_does_not_double_count_helpers(self):
        self.assertIn("local-profiles.sh", A.CURRENT)
        self.assertNotIn("local-profiles.py", A.CURRENT)
        self.assertNotIn("private-core-commands.py", A.CURRENT)
        self.assertEqual(len(A.CURRENT), len(set(A.CURRENT)))
        self.assertFalse(set(A.CURRENT) & set(A.HISTORICAL))

    def test_global_path_membership_and_classification(self):
        self.assertEqual(A.CURRENT.count("global-path-tests.py"), 1)
        self.assertNotIn("global-path-tests.py", A.HISTORICAL + A.NATIVE)
        for helper in ("global-path-benchmark.py", "global-path-baseline.sh",
                       "global_path_baseline.py"):
            self.assertNotIn(helper, A.CURRENT + A.HISTORICAL + A.NATIVE)
        self.assertEqual(A.offline_report("global-path-tests.py", "",
                                          "Ran 18 tests in 1.2s\n\nOK\n", 0)["checks"], 18)
        for stderr, rc in (("", 0), ("Ran 18 tests in 1.2s\nOK (skipped=1)", 0),
                           ("Ran 18 tests in 1.2s\nOK\n", 1)):
            with self.assertRaises(ValueError):
                A.offline_report("global-path-tests.py", "", stderr, rc)
        sources = A.provenance(A.Control(10))["source_sha256"]
        self.assertIn("test/global-path-baseline.sh", sources)
        self.assertIn("test/global_path_baseline.py", sources)

    def test_usage_error_is_not_native_blocker(self):
        with mock.patch.object(sys, "argv", ["acceptance.py", "--jobs", "0"]), \
                mock.patch.object(sys, "stderr"), self.assertRaises(SystemExit) as failure:
            A.main()
        self.assertEqual(failure.exception.code, 1)

    def test_local_index_membership_protocol_and_provenance(self):
        name = "local-index-tests.py"
        self.assertEqual(A.CURRENT.count(name), 1)
        self.assertNotIn(name, A.HISTORICAL + A.NATIVE)
        for helper in ("local-index-baseline.sh", "local_index_baseline.py",
                       "local-index-benchmark.py"):
            self.assertNotIn(helper, A.CURRENT + A.HISTORICAL + A.NATIVE)
        valid = "Ran 12 tests in 1.2s\n\nOK\n"
        self.assertEqual(A.offline_report(name, "", valid, 0),
                         {"status": "PASS", "checks": 12})
        for stderr, rc in (("", 0), (valid, 1), (valid + valid, 0),
                           (valid + "OK\n", 0), (valid + "trailing\n", 0),
                           (valid.replace("12", "0"), 0),
                           (valid.replace("OK", "OK (skipped=1)"), 0),
                           (valid.replace("OK", "FAILED (errors=1)"), 0)):
            with self.subTest(stderr=stderr, rc=rc), self.assertRaises(ValueError):
                A.offline_report(name, "", stderr, rc)
        sources = A.provenance(A.Control(10))["source_sha256"]
        for file in (name, "local-index-baseline.sh", "local_index_baseline.py",
                     "local-index-benchmark.py"):
            self.assertIn("test/" + file, sources)

    def test_invalid_budgets_create_no_fixture(self):
        for flag in ("--total-seconds", "--suite-seconds"):
            for value in ("0", "-1", "nan", "inf", "-inf", "bad"):
                with self.subTest(flag=flag, value=value), \
                        mock.patch.object(sys, "argv", ["acceptance.py", flag + "=" + value]), \
                        mock.patch.object(sys, "stderr"), \
                        mock.patch.object(A.tempfile, "mkdtemp") as create, \
                        self.assertRaises(SystemExit) as failure:
                    A.main()
                self.assertEqual(failure.exception.code, 1)
                create.assert_not_called()

    def test_policy_rejects_before_artifacts(self):
        for flags in (["--native"], ["--native-only"], ["--exhaustive"],
                      ["--exhaustive", "--total-seconds", "43200"],
                      ["--exhaustive", "--suite-seconds", "14400"],
                      ["--exhaustive", "--jobs", "2", "--total-seconds", "43200",
                       "--suite-seconds", "14400"],
                      ["--total-seconds", "1201"], ["--suite-seconds", "601"],
                      ["--global-diagnostics"],
                      ["--exhaustive", "--native-only", "--global-diagnostics",
                       "--total-seconds", "5", "--suite-seconds", "3"]):
            with self.subTest(flags=flags), \
                    mock.patch.object(sys, "argv", ["acceptance.py", *flags]), \
                    mock.patch.object(sys, "stderr"), \
                    mock.patch.object(A.tempfile, "mkdtemp") as create, \
                    self.assertRaises(SystemExit) as failure:
                A.main()
            self.assertEqual(failure.exception.code, 1)
            create.assert_not_called()

    def test_exact_quick_and_exhaustive_selection(self):
        args = argparse.Namespace(exhaustive=False, native=False, native_only=False)
        expected = ("private-core.sh", "native-discovery-tests.py", "beads-native-context-tests.py",
                    "acceptance-tests.py", "global-path-tests.py", "local-index-tests.py",
                    "global-diagnostics-tests.py", "native-supervision-tests.py",
                    "beads-fixture-tests.py", "beads-execution-tests.py",
                    "syntax-lint-ast-diff")
        self.assertEqual(A.selection(args), [("CURRENT", n) for n in expected])
        args.exhaustive = True
        self.assertEqual(A.selection(args),
                         [("CURRENT", n) for n in A.CURRENT + A.UNIT_EXTRA] +
                         [("HISTORICAL_FIXTURE", n) for n in A.HISTORICAL] +
                         [("CURRENT", "syntax-lint-ast-diff")])
        args.native = True
        self.assertEqual(A.selection(args),
                         [("CURRENT", n) for n in A.CURRENT + A.UNIT_EXTRA] +
                         [("HISTORICAL_FIXTURE", n) for n in A.HISTORICAL] +
                         [("NATIVE", n) for n in A.NATIVE] +
                         [("CURRENT", "syntax-lint-ast-diff")])
        args.native_only = True
        self.assertEqual(A.selection(args), [("NATIVE", n) for n in A.NATIVE])

    def test_embedded_execution_membership_and_report(self):
        name = "beads-execution-tests.py"
        self.assertEqual(A.CURRENT.count(name), 1)
        self.assertEqual(A.QUICK.count(name), 1)
        self.assertNotIn(name, A.HISTORICAL + A.NATIVE)
        self.assertEqual(A.offline_report(name, "", "Ran 17 tests in 0.8s\n\nOK\n", 0),
                         {"status": "PASS", "checks": 17})
        with self.assertRaises(ValueError):
            A.offline_report(name, "", "Ran 17 tests in 0.8s\n\nOK (skipped=1)\n", 0)
        self.assertIn("test/" + name, A.provenance(A.Control(10))["source_sha256"])

    def test_exact_selected_filter_and_caller_order(self):
        args = argparse.Namespace(exhaustive=False, native=False, native_only=False,
                                  suite=["CURRENT:syntax-lint-ast-diff",
                                         "CURRENT:private-core.sh"])
        self.assertEqual(A.selection(args),
                         [("CURRENT", "syntax-lint-ast-diff"), ("CURRENT", "private-core.sh")])
        args.exhaustive, args.native = True, True
        args.suite = ["NATIVE:beads-cleanup.py", "HISTORICAL_FIXTURE:upgrade.sh",
                      "CURRENT:beads-cleanup.py", "CURRENT:local-uninstall.py"]
        self.assertEqual(A.selection(args),
                         [("NATIVE", "beads-cleanup.py"), ("HISTORICAL_FIXTURE", "upgrade.sh"),
                          ("CURRENT", "beads-cleanup.py"), ("CURRENT", "local-uninstall.py")])
        args.native_only = True
        args.suite = ["NATIVE:beads-cleanup.py", "NATIVE:native-discovery.py"]
        self.assertEqual(A.selection(args),
                         [("NATIVE", "beads-cleanup.py"), ("NATIVE", "native-discovery.py")])

    def test_invalid_selectors_fail_before_provenance_fixtures_or_launch(self):
        exhaustive = ["--exhaustive", "--total-seconds", "5", "--suite-seconds", "3"]
        cases = [([], [token]) for token in
                 ("", ":", "CURRENT:", ":private-core.sh", "private-core.sh", "CURRENT",
                  "current:private-core.sh", "BOGUS:private-core.sh", "CURRENT:unknown.py",
                  "NATIVE:private-core.sh", "HISTORICAL_FIXTURE:private-core.sh",
                  "CURRENT:upgrade.sh", "CURRENT:local-uninstall.py",
                  "HISTORICAL_FIXTURE:upgrade.sh", "NATIVE:beads-cleanup.py",
                  "CURRENT:test/private-core.sh", "CURRENT:../test/private-core.sh",
                  "CURRENT:/tmp/private-core.sh", "CURRENT:*.sh", "CURRENT:.*",
                  "CURRENT:private-core", "CURRENT:private-core.sh:extra",
                  " CURRENT:private-core.sh", "CURRENT:private-core.sh ")]
        cases += [([], ["CURRENT:private-core.sh"] * 2),
                  (exhaustive, ["NATIVE:beads-cleanup.py"]),
                  (exhaustive + ["--native"], ["NATIVE:beads-cleanup.py"] * 2),
                  (exhaustive + ["--native-only"], ["CURRENT:beads-cleanup.py"]),
                  (exhaustive + ["--native-only"], ["CURRENT:syntax-lint-ast-diff"])]
        for flags, tokens in cases:
            argv = ["acceptance.py", *flags]
            for token in tokens:
                argv += ["--suite", token]
            with self.subTest(argv=argv), mock.patch.object(sys, "argv", argv), \
                    mock.patch.object(sys, "stderr"), \
                    mock.patch.object(A, "provenance") as provenance, \
                    mock.patch.object(A.tempfile, "mkdtemp") as create, \
                    mock.patch.object(A, "run_tasks") as launch, \
                    mock.patch.object(A, "execute") as execute, \
                    self.assertRaises(SystemExit) as failure:
                A.main()
            self.assertEqual(failure.exception.code, 1)
            for operation in (provenance, create, launch, execute):
                operation.assert_not_called()

    def test_selectors_do_not_bypass_native_budget_or_serial_guards(self):
        cases = [(["--native"], "NATIVE:beads-cleanup.py"),
                 (["--native-only"], "NATIVE:beads-cleanup.py"),
                 (["--exhaustive"], "NATIVE:beads-cleanup.py"),
                 (["--total-seconds", "1201"], "CURRENT:syntax-lint-ast-diff"),
                 (["--suite-seconds", "601"], "CURRENT:syntax-lint-ast-diff")]
        for native in ("--native", "--native-only"):
            for budgets in ([], ["--total-seconds", "5"], ["--suite-seconds", "3"],
                            ["--total-seconds", "5", "--suite-seconds", "3", "--jobs", "2"]):
                cases.append((["--exhaustive", native, *budgets], "NATIVE:beads-cleanup.py"))
        cases.append((["--exhaustive", "--total-seconds", "5", "--suite-seconds", "3",
                       "--jobs", "2"], "CURRENT:syntax-lint-ast-diff"))
        for flags, token in cases:
            with self.subTest(flags=flags), \
                    mock.patch.object(sys, "argv", ["acceptance.py", *flags, "--suite", token]), \
                    mock.patch.object(sys, "stderr"), \
                    mock.patch.object(A, "provenance") as provenance, \
                    mock.patch.object(A.tempfile, "mkdtemp") as create, \
                    mock.patch.object(A, "execute") as execute, \
                    self.assertRaises(SystemExit) as failure:
                A.main()
            self.assertEqual(failure.exception.code, 1)
            for operation in (provenance, create, execute):
                operation.assert_not_called()

    def selected_report(self, flags, tokens, synthetic):
        """Existing suite mock pattern; no selected fixture/client is executed."""
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp).resolve()
            root, artifacts = base / "checkout", base / "artifacts"
            root.mkdir()
            artifacts.mkdir()
            original = A.tempfile.mkdtemp

            def create(**kw):
                return str(artifacts) if kw.get("prefix") == "domestique-acceptance-" else original(**kw)

            argv = ["acceptance.py", *flags]
            for token in tokens:
                argv += ["--suite", token]
            with mock.patch.object(sys, "argv", argv), \
                    mock.patch.object(A, "ROOT", root), \
                    mock.patch.object(A.tempfile, "mkdtemp", side_effect=create), \
                    mock.patch.object(A, "provenance", return_value={"synthetic": True}), \
                    mock.patch.object(A, "run_tasks", side_effect=synthetic), \
                    mock.patch("builtins.print") as output:
                rc = A.main()
            report = json.loads((artifacts / "report.json").read_text())
            self.assertEqual(report["coverage"], "SELECTED_SCOPES_NOT_FULL_ACCEPTANCE")
            self.assertFalse(report["full_offline_acceptance"])
            self.assertEqual(report["exit"], rc)
            self.assertEqual(report["requested"],
                             [dict(zip(("category", "suite"), t.split(":"))) for t in tokens])
            self.assertEqual(report["provenance"], {"synthetic": True})
            self.assertTrue(any("SELECTED_SCOPES_NOT_FULL_ACCEPTANCE" in str(c)
                                for c in output.call_args_list))
            return rc, report

    def test_selected_all_is_still_partial_in_every_mode(self):
        for exhaustive, native, native_only in ((False, False, False), (True, False, False),
                                                (True, True, False), (True, False, True)):
            args = argparse.Namespace(exhaustive=exhaustive, native=native, native_only=native_only)
            # Reverse the entire unmodified manifest, including both cleanup identities.
            tasks = list(reversed(A.selection(args)))
            flags = (["--exhaustive", "--total-seconds", "5", "--suite-seconds", "3"]
                     if exhaustive else [])
            flags += ["--native"] if native else ["--native-only"] if native_only else []

            def synthetic(selected, _suite, jobs, _control, record):
                self.assertEqual(selected, tasks)
                self.assertEqual(jobs, 1)
                for c, n in selected:
                    record({"category": c, "suite": n,
                            "status": "NATIVE_OBSERVED" if c == "NATIVE" else "PASS"})

            with self.subTest(flags=flags):
                rc, report = self.selected_report(flags, [c + ":" + n for c, n in tasks], synthetic)
                self.assertEqual((rc, report["status"]), (0, "COMPLETE"))
                self.assertEqual([(r["category"], r["suite"]) for r in report["results"]], tasks)
                self.assertEqual(report["budgets"],
                                 {"total_seconds": 5, "suite_seconds": 3} if exhaustive else
                                 {"total_seconds": 1200, "suite_seconds": 600})

    def test_selected_failure_interruption_blocker_and_identity(self):
        tasks = [("NATIVE", "beads-cleanup.py"), ("CURRENT", "beads-cleanup.py")]
        for outcome in ("ASSERTION_FAILURE", "INCOMPLETE", "cancel", "BLOCKED",
                        "missing", "duplicate", "wrong-category"):
            def synthetic(selected, _suite, _jobs, control, record):
                self.assertEqual(selected, tasks)
                if outcome == "cancel":
                    control.signal(signal.SIGTERM, None)
                for i, (c, n) in enumerate(selected):
                    if outcome == "missing" and i == 1:
                        continue
                    if outcome == "wrong-category" and i == 1:
                        c = "NATIVE"
                    row = {"category": c, "suite": n,
                           "status": "CANCELLED" if outcome == "cancel" else
                           outcome if i == 0 and outcome in
                           ("ASSERTION_FAILURE", "INCOMPLETE", "BLOCKED") else
                           "NATIVE_OBSERVED" if c == "NATIVE" else "PASS"}
                    record(row)
                    if outcome == "duplicate" and i == 0:
                        record(dict(row))

            with self.subTest(outcome=outcome):
                rc, report = self.selected_report(
                    ["--exhaustive", "--native", "--total-seconds", "5", "--suite-seconds", "3"],
                    [c + ":" + n for c, n in tasks], synthetic)
                self.assertEqual(rc, 2 if outcome == "BLOCKED" else 1)
                self.assertEqual(report["status"], "COMPLETE" if outcome == "BLOCKED" else
                                 "CANCELLED" if outcome == "cancel" else "INCOMPLETE")
                if outcome in ("missing", "duplicate", "wrong-category"):
                    self.assertTrue(any(r["suite"] == "coverage-completeness" and
                                        r["status"] == "INCOMPLETE" for r in report["results"]))
                else:
                    self.assertEqual([(r["category"], r["suite"]) for r in report["results"]
                                      if r["category"] != "RUNNER"], tasks)

    def test_quick_green_never_full_offline_acceptance(self):
        args = argparse.Namespace(exhaustive=False, native=False, native_only=False)
        report = {"mode": "QUICK", "coverage": "QUICK_SUBSET_NOT_FULL_OFFLINE",
                  "status": "COMPLETE", "exit": 0,
                  "results": [{"category": c, "suite": n, "status": "PASS"}
                              for c, n in A.selection(args)]}
        self.assertFalse(A.full_offline_acceptance(report))
        report.update(mode="EXHAUSTIVE", coverage="FULL_OFFLINE")
        self.assertFalse(A.full_offline_acceptance(report))
        args.exhaustive = True
        report["results"] = [{"category": c, "suite": n, "status": "PASS"}
                             for c, n in A.selection(args)]
        self.assertTrue(A.full_offline_acceptance(report))
        for coverage in ("FULL_OFFLINE", "FULL_OFFLINE_AND_NATIVE"):
            report["coverage"] = coverage
            self.assertTrue(A.full_offline_acceptance(report))
        for coverage in ("NATIVE_ONLY", "SELECTED_SCOPES_NOT_FULL_ACCEPTANCE",
                         "QUICK_SUBSET_NOT_FULL_OFFLINE", "UNKNOWN", ""):
            report["coverage"] = coverage
            self.assertFalse(A.full_offline_acceptance(report))

    def test_default_report_is_quick_subset_even_with_exit_zero(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp).resolve()
            root, artifacts = base / "checkout", base / "artifacts"
            root.mkdir()
            artifacts.mkdir()
            original = A.tempfile.mkdtemp

            def create(**kw):
                return str(artifacts) if kw.get("prefix") == "domestique-acceptance-" else original(**kw)

            def synthetic(tasks, _suite, jobs, _control, record):
                self.assertEqual(jobs, 1)
                for c, n in tasks:
                    record({"category": c, "suite": n, "status": "PASS"})

            with mock.patch.object(sys, "argv", ["acceptance.py"]), \
                    mock.patch.object(A, "ROOT", root), \
                    mock.patch.object(A.tempfile, "mkdtemp", side_effect=create), \
                    mock.patch.object(A, "provenance", return_value={"synthetic": True}), \
                    mock.patch.object(A, "run_tasks", side_effect=synthetic), \
                    mock.patch("builtins.print") as output:
                self.assertEqual(A.main(), 0)
            report = json.loads((artifacts / "report.json").read_text())
            self.assertEqual(report["mode"], "QUICK")
            self.assertEqual(report["coverage"], "QUICK_SUBSET_NOT_FULL_OFFLINE")
            self.assertFalse(report["full_offline_acceptance"])
            self.assertEqual(report["budgets"], {"total_seconds": 1200, "suite_seconds": 600})
            self.assertEqual([r["suite"] for r in report["requested"]],
                             [*A.QUICK, "syntax-lint-ast-diff"])
            self.assertTrue(any("QUICK_SUBSET_NOT_FULL_OFFLINE" in str(c)
                                for c in output.call_args_list))

    def test_recovered_inspection_qualifies_existing_report_without_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp).resolve()
            root, artifacts = base / "checkout", base / "artifacts"
            root.mkdir()
            artifacts.mkdir()
            original = A.tempfile.mkdtemp

            def create(**kw):
                return str(artifacts) if kw.get("prefix") == "domestique-acceptance-" else original(**kw)

            def execute(argv, env, timeout, control=None, **kw):
                if control:
                    control.inspection_recoveries += 1
                    return "private-core: 1 passed, 0 failed\n", "", 0
                return "", "", 0

            with mock.patch.object(sys, "argv", ["acceptance.py"]), \
                    mock.patch.object(A, "ROOT", root), \
                    mock.patch.object(A.tempfile, "mkdtemp", side_effect=create), \
                    mock.patch.object(A, "provenance", return_value={"synthetic": True}), \
                    mock.patch.object(A, "selection", return_value=[("CURRENT", "private-core.sh")]), \
                    mock.patch.object(A, "execute", side_effect=execute), \
                    mock.patch("builtins.print") as output:
                self.assertEqual(A.main(), 0)
            report = json.loads((artifacts / "report.json").read_text())
            self.assertEqual(report["results"][0]["status"], "PASS")
            self.assertEqual(report["results"][0]["process_inspection_recoveries"], 1)
            self.assertTrue(any("process_inspection_recoveries" in str(c)
                                for c in output.call_args_list))

    def test_failure_or_timeout_stops_queue_without_user_cancellation(self):
        for status in ("ASSERTION_FAILURE", "INCOMPLETE"):
            with self.subTest(status=status):
                control = A.Control(5)
                started, results = [], []

                def suite(task):
                    started.append(task)
                    return {"category": task[0], "suite": task[1], "status": status}

                A.run_tasks([("CURRENT", str(n)) for n in range(3)], suite, 1,
                            control, results.append)
                self.assertEqual(len(started), 1)
                self.assertEqual([r["status"] for r in results],
                                 [status, "INCOMPLETE", "INCOMPLETE"])
                self.assertFalse(control.cancel.is_set())
                self.assertTrue(control.failed.is_set())
                self.assertEqual(A.exit_code(results), 1)

    def test_valid_blocker_does_not_stop_queue(self):
        results = []
        control = A.Control(5)
        A.run_tasks([("NATIVE", str(n)) for n in range(3)],
                    lambda task: {"category": task[0], "suite": task[1], "status": "BLOCKED"},
                    1, control, results.append)
        self.assertEqual(len(results), 3)
        self.assertTrue(all(r["status"] == "BLOCKED" for r in results))
        self.assertFalse(control.failed.is_set())
        self.assertEqual(A.exit_code(results), 2)

    def test_fail_fast_preserves_partial_output_and_cleans_active_process(self):
        control = A.Control(30)
        original = A.process_table
        with tempfile.TemporaryDirectory() as temp:
            ready = Path(temp) / "ready"

            def inspect(deadline, **kwargs):
                table = original(deadline, **kwargs)
                if ready.exists():
                    control.failed.set()
                return table

            with mock.patch.object(A, "process_table", side_effect=inspect), \
                    self.assertRaises(A.FailFast) as failure:
                A.execute([sys.executable, "-c",
                           "import pathlib,time; print('partial',flush=True); "
                           f"pathlib.Path({str(ready)!r}).touch(); time.sleep(60)"],
                          dict(os.environ), 30, control)
            self.assertEqual(failure.exception.output, "partial\n")

    def test_exit_precedence_and_native_only_regression(self):
        self.assertEqual(A.exit_code([{"status": "NATIVE_OBSERVED"}]), 0)
        self.assertEqual(A.exit_code([{"status": "BLOCKED"}]), 2)
        for state in ("ASSERTION_FAILURE", "CANCELLED", "INCOMPLETE"):
            self.assertEqual(A.exit_code([{"status": "BLOCKED"}, {"status": state}]), 1)

    def test_total_caps_execution_and_shutdown(self):
        control = A.Control(30)
        with self.expire_after(lambda table: True), \
                self.assertRaises(subprocess.TimeoutExpired):
            A.execute([sys.executable, "-c", "import time; time.sleep(60)"],
                      dict(os.environ), 60, control)
        self.assertTrue(control.exhausted.is_set())

    def test_budget_expiry_names_actual_scope(self):
        for total, label in ((True, "total-run budget"), (False, "per-suite budget")):
            control = A.Control(30)
            control.total_limited = total
            with mock.patch.object(A.time, "monotonic", return_value=control.work_deadline), \
                    self.assertRaises(subprocess.TimeoutExpired) as failure:
                control.check()
            self.assertEqual(failure.exception.cmd, label)
            self.assertEqual(A.failure_status(failure.exception),
                             {"status": "INCOMPLETE", "failure_kind": "timeout"})

    def test_observed_nested_session_ignoring_term_is_terminated(self):
        with tempfile.TemporaryDirectory() as temp:
            pidfile = Path(temp) / "nested"
            child = ("import os,pathlib,signal,time;"
                     "signal.signal(signal.SIGTERM,signal.SIG_IGN);"
                     f"pathlib.Path({str(pidfile)!r}).write_text(str(os.getpid()));"
                     "time.sleep(60)")
            parent = ("import subprocess,sys,time;"
                      f"subprocess.Popen([sys.executable,'-c',{child!r}],start_new_session=True);"
                      "time.sleep(60)")
            start = time.monotonic()
            try:
                with self.expire_after(lambda table: pidfile.exists() and
                                       int(pidfile.read_text()) in table), \
                        self.assertRaises(subprocess.TimeoutExpired):
                    A.execute([sys.executable, "-c", parent], dict(os.environ), 30)
                pid = int(pidfile.read_text())
                table = A.process_table(time.monotonic() + 5)
                self.assertTrue(pid not in table or table[pid][2][0] == "Z")
                self.assertLess(time.monotonic() - start, 30)
            finally:
                if pidfile.exists():
                    try:
                        os.kill(int(pidfile.read_text()), signal.SIGKILL)
                    except ProcessLookupError:
                        pass

    def test_cancelled_queue_never_starts(self):
        control = A.Control(5)
        started, results = [], []

        def suite(task):
            started.append(task)
            control.signal(signal.SIGINT, None)
            return {"status": "CANCELLED", "suite": task[1]}

        A.run_tasks([("CURRENT", str(n)) for n in range(4)],
                    suite, 1, control, results.append)
        self.assertEqual(len(started), 1)
        self.assertEqual(len(results), 4)
        self.assertTrue(all(r["status"] == "CANCELLED" for r in results))

    def test_bounded_progress_heartbeat(self):
        control = A.Control(5)

        def slow(_task):
            time.sleep(.35)
            return {"status": "PASS"}

        with mock.patch("builtins.print") as output:
            A.run_tasks([("CURRENT", "harmless")], slow, 1, control,
                        lambda _result: None, heartbeat=.1)
        self.assertGreaterEqual(output.call_count, 1)
        self.assertLessEqual(output.call_count, 4)
        self.assertTrue(all("PROGRESS" in c.args[0] for c in output.call_args_list))

    def test_expired_validation_does_not_launch_a_process(self):
        control = A.Control(1)
        control.exhausted.set()
        with mock.patch.object(A.subprocess, "Popen") as spawn, \
                self.assertRaises(subprocess.TimeoutExpired):
            A.validation({}, control)
        spawn.assert_not_called()

    def test_cleanup_failure_is_not_swallowed(self):
        real = A.os.killpg

        def denied(pid, sig):
            if sig == signal.SIGTERM:
                raise PermissionError("synthetic denial")
            return real(pid, sig)

        with self.expire_after(lambda table: True), \
                mock.patch.object(A.os, "killpg", side_effect=denied), \
                self.assertRaisesRegex(RuntimeError, "cleanup failed"):
            A.execute([sys.executable, "-c", "import time; time.sleep(60)"],
                      dict(os.environ), 30)

    def test_termination_failure_still_cleans_observed_nested_session(self):
        for target in ("group", "pid", "inspection"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temp:
                pidfile = Path(temp) / "nested"
                child = ("import os,pathlib,signal,time;"
                         "signal.signal(signal.SIGTERM,signal.SIG_IGN);"
                         f"pathlib.Path({str(pidfile)!r}).write_text(str(os.getpid()));"
                         "time.sleep(60)")
                parent = ("import subprocess,sys,time;"
                          f"subprocess.Popen([sys.executable,'-c',{child!r}],"
                          "start_new_session=True);time.sleep(60)")
                observed = {}
                original_remember = A.remember_descendants
                original_kill = os.killpg if target == "group" else os.kill
                injected = []
                attempts = []
                inspection_injected = []

                def remember(proc, owned, table):
                    original_remember(proc, owned, table)
                    observed.update(owned)
                    if (target == "inspection" and not inspection_injected and pidfile.exists()
                            and int(pidfile.read_text()) in owned):
                        inspection_injected.append(True)
                        raise A.ProcessInspectionError("injected observed-descendant inspection failure")

                def denied_once(pid, sig):
                    attempts.append((pid, sig))
                    if sig == signal.SIGTERM and not injected:
                        injected.append(pid)
                        raise PermissionError("injected first termination failure")
                    return original_kill(pid, sig)

                start = time.monotonic()
                try:
                    with self.expire_after(lambda table: pidfile.exists() and
                                           int(pidfile.read_text()) in table), \
                            mock.patch.object(A, "remember_descendants", side_effect=remember), \
                            mock.patch.object(A.os, "killpg" if target == "group" else "kill",
                                              side_effect=denied_once), \
                            self.assertRaisesRegex(RuntimeError,
                                                   "PermissionError: injected first") as failure:
                        A.execute([sys.executable, "-c", parent], dict(os.environ), 30)
                    nested = int(pidfile.read_text())
                    self.assertIn(nested, observed, "probe must have been positively observed")
                    self.assertEqual(len(injected), 1)
                    self.assertIn((injected[0] if target == "group" else nested,
                                   signal.SIGKILL), attempts)
                    primary = ("ProcessInspectionError: injected observed-descendant inspection failure"
                               if target == "inspection" else "TimeoutExpired")
                    self.assertIn("prior failure: " + primary, str(failure.exception))
                    self.assertEqual(A.failure_status(failure.exception),
                                     {"status": "INCOMPLETE", "failure_kind": "supervision"})
                    table = A.process_table(time.monotonic() + 5)
                    for pid, birth in observed.items():
                        row = table.get(pid)
                        self.assertTrue(row is None or row[3] != birth or row[2][0] == "Z",
                                        f"owned pid {pid} survived cleanup")
                    self.assertLess(time.monotonic() - start, 30)
                finally:
                    # No name-based killing, including on a failed assertion.
                    table = A.process_table(time.monotonic() + 5)
                    for pid, birth in observed.items():
                        row = table.get(pid)
                        if row and row[3] == birth and row[2][0] != "Z":
                            try:
                                os.kill(pid, signal.SIGKILL)
                            except ProcessLookupError:
                                pass
                    if pidfile.exists():
                        pid = int(pidfile.read_text())
                        if pid not in observed:
                            try:
                                os.kill(pid, signal.SIGKILL)
                            except ProcessLookupError:
                                pass

    def finalization_fixture(self, signum=None, phase="cleanup", status="NATIVE_OBSERVED",
                             native=False):
        """Real runner exit/signals; mocked suites and harmless fixture cleanup."""
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp).resolve()
            root, artifacts = base / "checkout", base / "artifacts"
            root.mkdir()
            artifacts.mkdir()
            code = (
                "import importlib.util,json,os,pathlib,shutil,signal,sys\n"
                f"s=importlib.util.spec_from_file_location('a',{str(Path(A.__file__))!r})\n"
                "a=importlib.util.module_from_spec(s);s.loader.exec_module(a)\n"
                f"a.ROOT=pathlib.Path({str(root)!r})\n"
                "a.NATIVE=('synthetic',)\n"
                "a.provenance=lambda c: {'synthetic':'not native evidence'}\n"
                "a.run_tasks=lambda tasks,suite,jobs,control,record: "
                f"record({{'category':'NATIVE','suite':'synthetic','status':{status!r}}})\n"
                "original=a.tempfile.mkdtemp\n"
                f"a.tempfile.mkdtemp=lambda **kw: {str(artifacts)!r} "
                "if kw.get('prefix')=='domestique-acceptance-' else original(**kw)\n"
                f"signum={int(signum) if signum else None!r}\n"
                f"phase={phase!r}\n"
                "cleaned=False\n"
                "def cleanup(argv,env,timeout):\n"
                "    global cleaned\n"
                "    cleaned=True\n"
                "    assert timeout > 0\n"
                "    if phase=='cleanup-error': raise OSError('injected cleanup failure')\n"
                "    if phase=='cleanup' and signum: os.kill(os.getpid(),signum)\n"
                "    for p in argv[4:]: shutil.rmtree(p)\n"
                "    return '', '', 0\n"
                "a.execute=cleanup\n"
                "original_replace=pathlib.Path.replace\n"
                "injected=False\n"
                "def replace(path,target):\n"
                "    global injected\n"
                "    final=json.loads(path.read_text())['status']=='COMPLETE'\n"
                "    if cleaned and phase in ('report','report-before','staged-report-error') "
                "and not injected:\n"
                "        injected=True\n"
                "        assert not final\n"
                "        if phase=='staged-report-error': "
                "raise OSError('injected staged report failure')\n"
                "        if phase=='report-before':\n"
                "            os.kill(os.getpid(),signum)\n"
                "            return original_replace(path,target)\n"
                "        result=original_replace(path,target)\n"
                "        os.kill(os.getpid(),signum)\n"
                "        return result\n"
                "    if final and not injected:\n"
                "        injected=True\n"
                "        if phase=='report-error': raise OSError('injected report failure')\n"
                "        result=original_replace(path,target)\n"
                "        if phase in ('native-report','native-return'):\n"
                "            os.kill(os.getpid(),signum)\n"
                "        return result\n"
                "    return original_replace(path,target)\n"
                "pathlib.Path.replace=replace\n"
                "original_signal=signal.signal\n"
                "prior={s: signal.getsignal(s) for s in (signal.SIGINT,signal.SIGTERM)}\n"
                "native_calls=[]\n"
                "if phase=='native-return':\n"
                "    def native_handler(sig,frame): native_calls.append(sig)\n"
                "    original_signal(signum,native_handler)\n"
                "    prior[signum]=native_handler\n"
                "def restore(sig,handler):\n"
                "    global injected\n"
                "    restoring=handler==prior[sig]\n"
                "    if restoring and not injected and (\n"
                "            (phase=='restore-own' and sig==signum) or\n"
                "            (phase=='restore-other-before' and sig!=signum)):\n"
                "        injected=True\n"
                "        assert signal.getsignal(signum)!=prior[signum]\n"
                "        os.kill(os.getpid(),signum)\n"
                "    result=original_signal(sig,handler)\n"
                "    if restoring and not injected and sig==signal.SIGINT and phase in (\n"
                "            'restore-other-after','native-partial'):\n"
                "        injected=True\n"
                "        assert (signal.getsignal(signum)==prior[signum]) == "
                "(phase=='native-partial')\n"
                "        os.kill(os.getpid(),signum)\n"
                "    return result\n"
                "signal.signal=restore\n"
                "sys.argv=['acceptance.py','--exhaustive','--native-only',"
                "'--total-seconds','5','--suite-seconds','3']\n"
                "try:\n"
                "    rc=a.main()\n"
                "finally:\n"
                "    assert all(signal.getsignal(s)==h for s,h in prior.items())\n"
                "if phase=='native-return': assert native_calls==[signum]\n"
                "raise SystemExit(rc)\n")
            proc = subprocess.run([sys.executable, "-B", "-W", "error", "-c", code],
                                  capture_output=True, text=True, timeout=7)
            if native and signum == signal.SIGINT:
                self.assertIn("KeyboardInterrupt", proc.stderr)
            else:
                self.assertEqual(proc.stderr, "", proc.stdout)
            report = json.loads((artifacts / "report.json").read_text())
            if not native:
                self.assertEqual(report["exit"], proc.returncode)
            else:
                self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(len(report["requested"]), 1)
            self.assertEqual(report["results"][0]["status"], status)
            return proc.returncode, report

    def test_sigint_during_final_cleanup_is_nonzero_and_cancelled(self):
        rc, report = self.finalization_fixture(signal.SIGINT)
        self.assertEqual((rc, report["status"], report["signal"]),
                         (1, "CANCELLED", signal.SIGINT))

    def test_sigterm_during_final_cleanup_is_nonzero_and_cancelled(self):
        rc, report = self.finalization_fixture(signal.SIGTERM)
        self.assertEqual((rc, report["status"], report["signal"]),
                         (1, "CANCELLED", signal.SIGTERM))

    def test_finalization_preserves_success_and_native_blocked_exits(self):
        for status, expected in (("NATIVE_OBSERVED", 0), ("BLOCKED", 2)):
            with self.subTest(status=status):
                rc, report = self.finalization_fixture(status=status)
                self.assertEqual((rc, report["status"]), (expected, "COMPLETE"))
                rc, report = self.finalization_fixture(signal.SIGTERM, status=status)
                self.assertEqual((rc, report["status"]), (1, "CANCELLED"))

    def test_signal_during_owned_report_serialization_is_cancelled(self):
        for signum in (signal.SIGINT, signal.SIGTERM):
            for phase in ("report-before", "report"):
                with self.subTest(signum=signum, phase=phase):
                    rc, report = self.finalization_fixture(signum, phase=phase)
                    self.assertEqual((rc, report["status"], report["signal"]),
                                     (1, "CANCELLED", signum))

    def test_signals_immediately_before_own_handler_restoration(self):
        for signum in (signal.SIGINT, signal.SIGTERM):
            with self.subTest(signum=signum):
                rc, report = self.finalization_fixture(signum, phase="restore-own")
                self.assertEqual((rc, report["status"], report["signal"]),
                                 (1, "CANCELLED", signum))

    def test_sigterm_during_sigint_restoration_is_consumed(self):
        for phase in ("restore-other-before", "restore-other-after"):
            with self.subTest(phase=phase):
                rc, report = self.finalization_fixture(signal.SIGTERM, phase=phase)
                self.assertEqual((rc, report["status"], report["signal"]),
                                 (1, "CANCELLED", signal.SIGTERM))

    def test_restored_sigint_during_sigterm_ownership_is_native(self):
        rc, report = self.finalization_fixture(signal.SIGINT, phase="native-partial",
                                              native=True)
        self.assertNotEqual(rc, 0)
        self.assertEqual((report["status"], report["exit"]), ("INCOMPLETE", 1))
        self.assertIsNone(report.get("signal"))

    def test_signals_after_restoration_have_native_default_behavior(self):
        for signum in (signal.SIGINT, signal.SIGTERM):
            with self.subTest(signum=signum):
                rc, report = self.finalization_fixture(signum, phase="native-report",
                                                      native=True)
                if signum == signal.SIGTERM:
                    self.assertEqual(rc, -signal.SIGTERM)
                self.assertEqual((report["status"], report["exit"], report["signal"]),
                                 ("COMPLETE", 0, None))

    def test_returning_previous_handlers_do_not_set_runner_cancellation(self):
        for signum in (signal.SIGINT, signal.SIGTERM):
            for status, expected in (("NATIVE_OBSERVED", 0), ("BLOCKED", 2)):
                with self.subTest(signum=signum, status=status):
                    rc, report = self.finalization_fixture(signum, phase="native-return",
                                                          status=status)
                    self.assertEqual((rc, report["status"], report["signal"]),
                                     (expected, "COMPLETE", None))

    def test_cleanup_or_report_error_cannot_publish_success(self):
        for phase in ("cleanup-error", "staged-report-error", "report-error"):
            with self.subTest(phase=phase):
                rc, report = self.finalization_fixture(phase=phase)
                self.assertEqual((rc, report["status"]), (1, "INCOMPLETE"))
                self.assertEqual(report["results"][-1]["status"],
                                 "INCOMPLETE" if phase == "cleanup-error" else "ASSERTION_FAILURE")

    def runner_fixture(self, signum=None, total=30, per_suite=10, assertion=False,
                       expire=False, inspection_failure=False, cleanup_failure=False):
        """A separate runner process with ONLY harmless synthetic test scripts."""
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp).resolve()
            root = base / "checkout"
            (root / "test").mkdir(parents=True)
            artifacts = base / "artifacts"
            artifacts.mkdir()
            (root / "test/fast.py").write_text("print('synthetic')\n")
            (root / "test/slow.py").write_text(
                "import pathlib,sys,time\n"
                "print('primary stdout',flush=True)\n"
                "print('primary stderr',file=sys.stderr,flush=True)\n"
                "pathlib.Path('started').touch()\n" +
                ("raise AssertionError('injected command assertion')\n" if assertion else
                 "time.sleep(60)\n"))
            (root / "test/queued.py").write_text("raise RuntimeError('must not start')\n")
            code = (
                "import importlib.util,pathlib,sys,time,types,signal\n"
                f"s=importlib.util.spec_from_file_location('a',{str(Path(A.__file__))!r})\n"
                "a=importlib.util.module_from_spec(s);s.loader.exec_module(a)\n"
                f"a.ROOT=pathlib.Path({str(root)!r})\n"
                "a.NATIVE=('fast.py','slow.py','queued.py')\n"
                "a.provenance=lambda c: {'source_sha256':{'synthetic':'fixture'},"
                "'tools':{'python':sys.version}}\n"
                "a.native_report=lambda n,out,rc: a.require(rc==0,'synthetic assertion exit') "
                "or {'status':'NATIVE_OBSERVED'}\n"
                "original=a.tempfile.mkdtemp\n"
                f"a.tempfile.mkdtemp=lambda **kw: {str(artifacts)!r} "
                "if kw.get('prefix')=='domestique-acceptance-' else original(**kw)\n"
                "offset=0\n"
                "injected=False\n"
                "a.time=types.SimpleNamespace(monotonic=lambda:time.monotonic()+offset,"
                "sleep=time.sleep)\n"
                "original_table=a.process_table\n"
                "def inspect(deadline, **kwargs):\n"
                "    global offset,injected\n"
                "    table=original_table(deadline, **kwargs)\n"
                "    if not injected and (a.ROOT/'started').exists():\n"
                "        injected=True\n"
                f"        if {inspection_failure!r}:\n"
                "            raise a.ProcessInspectionError('injected ps timeout after 5 seconds')\n"
                f"        if {expire!r}: offset=deadline-time.monotonic()+0.001\n"
                "    return table\n"
                "a.process_table=inspect\n"
                "original_killpg=a.os.killpg\n"
                "def killpg(pid,sig):\n"
                f"    if {cleanup_failure!r} and (a.ROOT/'started').exists() "
                "and sig==signal.SIGTERM:\n"
                "        raise PermissionError('injected cleanup denial')\n"
                "    return original_killpg(pid,sig)\n"
                "a.os.killpg=killpg\n"
                f"sys.argv=['acceptance.py','--exhaustive','--native-only','--total-seconds',{str(total)!r},"
                f"'--suite-seconds',{str(per_suite)!r}]\n"
                "raise SystemExit(a.main())\n")
            start = time.monotonic()
            proc = subprocess.Popen([sys.executable, "-B", "-W", "error", "-c", code],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                limit = time.monotonic() + 10
                while not (root / "started").exists() and proc.poll() is None:
                    self.assertLess(time.monotonic(), limit)
                    time.sleep(.02)
                partial = json.loads((artifacts / "report.json").read_text())
                self.assertEqual(partial["status"], "INCOMPLETE")
                self.assertEqual(partial["exit"], 1)
                self.assertEqual(partial["results"][0]["suite"], "fast.py")
                self.assertIn("provenance", partial)
                self.assertEqual(partial["mode"], "EXHAUSTIVE")
                self.assertEqual(partial["coverage"], "NATIVE_ONLY")
                self.assertFalse(partial["full_offline_acceptance"])
                if signum:
                    proc.send_signal(signum)
                out, err = proc.communicate(timeout=15)
                self.assertEqual(proc.returncode, 1, (out, err))
                self.assertEqual(err, "")
                self.assertLess(time.monotonic() - start, total + 1)
                report = json.loads((artifacts / "report.json").read_text())
                self.assertNotIn(str(root), json.dumps(report))
                self.assertFalse(list(root.glob(".acceptance-*")))
                if inspection_failure:
                    error_path = artifacts / "NATIVE-slow.py.error"
                    self.assertTrue(error_path.exists(), report)
                    error = error_path.read_text()
                    self.assertIn("injected ps timeout after 5 seconds", error)
                    self.assertEqual((artifacts / "NATIVE-slow.py.stdout").read_text(),
                                     "primary stdout\n")
                    self.assertEqual((artifacts / "NATIVE-slow.py.stderr").read_text(),
                                     "primary stderr\n")
                    if cleanup_failure:
                        self.assertIn("injected cleanup denial", error)
                        self.assertIn("prior failure: ProcessInspectionError:", error)
                return report
            finally:
                if proc.poll() is None:
                    proc.send_signal(signal.SIGTERM)
                    proc.communicate(timeout=7)

    def test_sigint_incremental_cancelled_evidence(self):
        report = self.runner_fixture(signal.SIGINT)
        self.assertEqual(report["status"], "CANCELLED")
        self.assertEqual(report["signal"], signal.SIGINT)
        self.assertEqual(next(r for r in report["results"] if r["suite"] == "queued.py")
                         ["status"], "CANCELLED")

    def test_sigterm_incremental_cancelled_evidence(self):
        report = self.runner_fixture(signal.SIGTERM)
        self.assertEqual(report["status"], "CANCELLED")
        self.assertEqual(report["signal"], signal.SIGTERM)

    def test_total_deadline_incomplete_evidence(self):
        report = self.runner_fixture(total=30, per_suite=60, expire=True)
        self.assertEqual(report["status"], "INCOMPLETE")
        self.assertTrue(any(r.get("failure_kind") == "timeout" for r in report["results"]))
        self.assertEqual(next(r for r in report["results"] if r["suite"] == "queued.py")
                         ["status"], "INCOMPLETE")

    def test_suite_deadline_is_failure_not_native_pass(self):
        report = self.runner_fixture(expire=True)
        row = next(r for r in report["results"] if r["suite"] == "slow.py")
        self.assertEqual((row["status"], row["failure_kind"]), ("INCOMPLETE", "timeout"))

    def test_inspection_and_cleanup_failures_persist_as_supervision_not_native_blocker(self):
        for cleanup in (False, True):
            with self.subTest(cleanup=cleanup):
                report = self.runner_fixture(inspection_failure=True, cleanup_failure=cleanup)
                self.assertEqual((report["status"], report["exit"]), ("INCOMPLETE", 1))
                row = next(r for r in report["results"] if r["suite"] == "slow.py")
                self.assertEqual((row["status"], row["failure_kind"]),
                                 ("INCOMPLETE", "supervision"))
                self.assertNotIn("exit", row)
                if cleanup:
                    self.assertEqual(row["primary_failure"]["type"], "ProcessInspectionError")
                queued = next(r for r in report["results"] if r["suite"] == "queued.py")
                self.assertEqual(queued["status"], "INCOMPLETE")

    def test_cancellation_with_cleanup_error_keeps_primary_signal_failure(self):
        report = self.runner_fixture(signal.SIGTERM, cleanup_failure=True)
        self.assertEqual((report["status"], report["exit"], report["signal"]),
                         ("CANCELLED", 1, signal.SIGTERM))
        row = next(r for r in report["results"] if r["suite"] == "slow.py")
        self.assertEqual((row["status"], row["failure_kind"]), ("INCOMPLETE", "supervision"))
        self.assertEqual(row["primary_failure"]["type"], "Cancelled")
        self.assertNotIn("exit", row)
        self.assertNotIn("exit", row["primary_failure"])

    def test_timeout_with_cleanup_error_keeps_primary_timeout(self):
        report = self.runner_fixture(expire=True, cleanup_failure=True)
        row = next(r for r in report["results"] if r["suite"] == "slow.py")
        self.assertEqual((row["status"], row["failure_kind"]), ("INCOMPLETE", "supervision"))
        self.assertEqual(row["primary_failure"],
                         {"type": "TimeoutExpired", "status": "INCOMPLETE",
                          "failure_kind": "timeout"})
        self.assertNotIn("exit", row)

    def test_actual_command_assertion_fail_fast_report(self):
        report = self.runner_fixture(assertion=True)
        self.assertEqual(report["status"], "INCOMPLETE")
        self.assertIsNone(report["signal"])
        failed = next(r for r in report["results"] if r["suite"] == "slow.py")
        self.assertEqual((failed["status"], failed["exit"]), ("ASSERTION_FAILURE", 1))
        queued = next(r for r in report["results"] if r["suite"] == "queued.py")
        self.assertEqual(queued["status"], "INCOMPLETE")
        self.assertIn("not started", queued["diagnostic"])
        self.assertNotIn("exit", queued)

    def test_retained_preview_help_describes_attachment_without_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp).resolve()
            env = A.environment(work)
            retained = A.preview_fixture.materialize(work)
            def snapshot():
                return [(str(p.relative_to(work)), p.read_bytes() if p.is_file() else None)
                        for p in sorted(work.rglob("*"))]
            before = snapshot()
            out, err, rc = A.execute(["/bin/bash", str(retained), "--help"], env, 30)
            self.assertEqual((err, rc), ("", 0))
            self.assertIn("Successful Beads purge still retains\n"
                          "the valid private attachment and its exclusion for reuse.", out)
            self.assertNotIn("final private-state cleanup is future", out)
            self.assertEqual(snapshot(), before)


if __name__ == "__main__":
    unittest.main()
