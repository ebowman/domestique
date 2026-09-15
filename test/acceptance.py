"""Acceptance runner. Default QUICK is NOT full-offline acceptance.

EXHAUSTIVE requires serial execution and explicit total AND per-suite budgets.
Native flags additionally require explicit operator (non-model) native consent.
Repeatable --suite CATEGORY:NAME selects exact permitted scopes in caller order;
explicit selections are always partial coverage, never full-offline acceptance.

Exit 0: requested checks pass; 1: failure/error; 2: validated native blockers.
Logs are retained in a private OS temporary session directory printed on startup.
Fixture TMPDIR is private and checkout-local (required by the cleanup harness),
and is removed on completion. No installations, network or user configuration.
"""
import argparse
import ast
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import contextmanager
import datetime
import hashlib
import importlib.util
import json
import math
import os
import platform
from pathlib import Path
import re
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parent.parent
PYTHON = str(Path(sys.executable).resolve())
SPEC = importlib.util.spec_from_file_location("beads_fixture", ROOT / "test/beads_fixture.py")
F = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(F)
CURRENT = (
    "private-core.sh", "global.sh", "local-preflight.sh", "local-profiles.sh",
    "global-uninstall.py", "local-uninstall.py", "beads-guard.py",
    "beads-private.py", "beads-cleanup.py", "native-discovery-tests.py",
    "beads-native-context-tests.py", "acceptance-tests.py", "global-path-tests.py",
    "local-index-tests.py", "native-supervision-tests.py", "beads-fixture-tests.py",
    "beads-execution-tests.py",
)
HISTORICAL = ("codex.sh", "copilot.sh", "guest.sh", "uninstall.sh", "upgrade.sh")
QUICK = ("private-core.sh", "native-discovery-tests.py", "beads-native-context-tests.py",
         "acceptance-tests.py", "global-path-tests.py", "local-index-tests.py",
         "global-diagnostics-tests.py", "native-supervision-tests.py", "beads-fixture-tests.py",
         "beads-execution-tests.py")
UNIT_EXTRA = ("global-diagnostics-tests.py",)
NATIVE = ("native-discovery.py", "beads-native-context.py",
          "beads-production.py", "beads-cleanup.py")
PROOFS = {"sandbox", "native-init", "readiness", "required-operations",
          "separation", "IDENTITY_BINDING", "database-uuid-query", "host-privacy", "cleanup"}
SUMMARY = {
    "private-core.sh": r"private-core: (\d+) passed, 0 failed",
    "global.sh": r"global: (\d+) passed, 0 failed",
    "local-preflight.sh": r"local preflight: (\d+) passed, 0 failed",
    "local-profiles.sh": r"local-profiles current production: (\d+) passed",
    "global-uninstall.py": r"global-uninstall: (\d+) checks passed \(current source; isolated, no native clients\)",
    "local-uninstall.py": r"local-uninstall: (\d+) checks passed \(current source; isolated; no clients\)",
    "beads-guard.py": r"beads-guard current missing/unowned backend: (\d+) passed",
    "beads-private.py": r"private Beads SYNTHETIC protocol/production integration: (\d+) passed",
    "beads-cleanup.py": (r"beads-cleanup: (\d+) checks; SYNTHETIC ONLY; [1-9]\d* fake bd calls / "
                         r"[1-9]\d* instrumented process calls; ZERO cleanup-native calls"),
}


class Parser(argparse.ArgumentParser):
    def error(self, message):
        # Exit 2 is reserved for validated native reports, not CLI mistakes.
        self.exit(1, f"{self.prog}: {message}\n")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def text(value):
    return type(value) is str and bool(value.strip())


def positive(value):
    return type(value) is int and value > 0


def counts_match(counts, statuses):
    require(type(counts) is dict and set(counts) == set(statuses), "invalid count keys")
    for key, values in statuses.items():
        require(type(counts[key]) is int and counts[key] == values, f"invalid {key} count")


def fixture_evidence(value):
    require(type(value) is dict and set(value) == {"path", "sha256"}
            and text(value["path"]) and Path(value["path"]).is_absolute()
            and value["sha256"] == F.SHA256, "invalid qualified native fixture provenance")
    return value


def native_report(name, stdout, rc):
    """Validate the harness's actual report grammar, never just trust exit 2."""
    require(rc in (0, 2), f"native process exit {rc}")
    if name == "beads-cleanup.py":
        evidence, separator, stdout = stdout.partition("\n")
        require(separator and evidence.startswith("NATIVE_FIXTURE="),
                "missing native cleanup fixture provenance")
        selected = fixture_evidence(json.loads(evidence.removeprefix("NATIVE_FIXTURE=")))
        match = re.fullmatch(
            r"beads-cleanup: ([1-9]\d*) checks; PINNED NATIVE; "
            r"([1-9]\d*) native bd calls / ([1-9]\d*) instrumented process calls; "
            r"ZERO cleanup-native calls\n?", stdout)
        require(rc == 0 and match is not None, "missing native cleanup completion report")
        require(int(match[3]) >= int(match[2]), "invalid native cleanup call counts")
        return {"status": "NATIVE_OBSERVED", "checks": int(match[1]),
                "native_fixture": selected,
                "bd_calls": int(match[2]), "process_calls": int(match[3])}
    report = json.loads(stdout)
    require(type(report) is dict and text(report.get("scope")), "missing report scope")
    def no_failure(value):
        if type(value) is dict:
            require(not ({"failure_kind", "failure", "privacy_error", "orphan"} & value.keys()),
                    "structured native failure is not a blocker")
            require(value.get("status") not in ("FAILED", "ASSERTION_FAILURE", "INCOMPLETE")
                    and value.get("classification") != "FAILED", "nested native failure")
            for child in value.values():
                no_failure(child)
        elif type(value) is list:
            for child in value:
                no_failure(child)
    no_failure(report)
    blocker_kinds = {"absent-tool", "unsupported-interface", "denied-approval"}
    if name == "beads-production.py":
        selected = fixture_evidence(report.get("native_fixture"))
        require(rc == 0 and report.get("production") == "PASS", "production did not pass")
        for field in ("checked_processes", "protected_host_leaves", "protected_entries"):
            require(positive(report.get(field)), f"invalid production {field}")
        require(report.get("projects") == ["A", "B", "W"], "missing production projects")
        require(report.get("mixed_provider_ordering") == "PASS (actual native C)",
                "missing mixed-provider proof")
        require(report.get("native") == "Beads 1.1.2 CGO embedded, Darwin arm64",
                "unexpected native qualification")
        return {"status": "NATIVE_OBSERVED", "report": report, "native_fixture": selected}
    require(text(report.get("date")), "missing report date")
    datetime.datetime.fromisoformat(report["date"])
    if name == "native-discovery.py":
        rows = report.get("results")
        require(type(rows) is list and bool(rows), "missing discovery results")
        states = ("NATIVE_DISCOVERY_OBSERVED", "BLOCKED", "STATIC_ONLY", "ASSERTION_FAILURE")
        for row in rows:
            require(type(row) is dict and text(row.get("component")) and
                    row.get("status") in states, "invalid discovery row")
            if row["status"] == "BLOCKED":
                require(text(row.get("diagnostic")), "blocker needs a diagnostic")
                require(row.get("blocker_kind") in blocker_kinds, "untyped native blocker")
            if row["status"] == "NATIVE_DISCOVERY_OBSERVED":
                require(row.get("repo") in ("A", "B") and text(row.get("version")) and
                        row.get("stage") in ("global-only", "after-local-A-fresh-process",
                                             "metadata-reload"), "invalid observation context")
                skills = row.get("skills")
                require(type(skills) is list and bool(skills), "missing observed skills")
                require(all(type(s) is dict and text(s.get("name")) and text(s.get("source"))
                            for s in skills), "invalid observed skill")
            if "changes" in row:
                require(row["changes"] == {"A": [], "B": []}, "native probe changed projects")
        counts_match(report.get("counts"), {s: sum(r["status"] == s for r in rows) for s in states})
        require(not report["counts"]["ASSERTION_FAILURE"], "native assertion failure")
        blocked = bool(report["counts"]["BLOCKED"])
        require(blocked or report["counts"]["NATIVE_DISCOVERY_OBSERVED"] > 0,
                "no discovery and no precise blocker")
        require(rc == (2 if blocked else 0), "discovery exit/status mismatch")
        return {"status": "BLOCKED" if blocked else "NATIVE_OBSERVED", "report": report}
    require(name == "beads-native-context.py", "unknown native report")
    proofs = report.get("proofs")
    require(type(proofs) is dict and set(proofs) == PROOFS, "invalid context proofs")
    require(all(v in ("PASS", "BLOCKED", "FAILED") for v in proofs.values()),
            "unknown context proof status")
    counts_match(report.get("counts"),
                 {s: sum(v == s for v in proofs.values()) for s in ("PASS", "BLOCKED", "FAILED")})
    require("FAILED" not in proofs.values(), "context proof failed")
    require(proofs["cleanup"] == "PASS", "native context cleanup incomplete")
    require(type(report.get("commands")) is list and type(report.get("contexts")) is list
            and type(report.get("limits")) is list and bool(report["limits"]),
            "missing context execution fields")
    require(text(report.get("source_pin")) and text(report.get("binary")),
            "missing context provenance")
    blocked = {k for k, v in proofs.items() if v == "BLOCKED"}
    if blocked:
        require((text(report.get("blocker")) and report.get("blocker_kind") in blocker_kinds) or
                (blocked == {"database-uuid-query"} and
                 text(report.get("database_uuid_limit")) and
                 "'bd sql' is not yet supported in embedded mode" in report["database_uuid_limit"]),
                "context blocker lacks precise diagnostic")
    if proofs["native-init"] == "PASS":
        fixture_evidence({"path": report["binary"], "sha256": report.get("binary_sha256")})
        require(text(report.get("version")) and
                text(report.get("binary_sha256")) and
                re.fullmatch(r"[a-f0-9]{64}", report.get("binary_sha256", "")) is not None
                and len(report["contexts"]) == 3 and bool(report["commands"]),
                "missing native init provenance")
    expected = "BLOCKED" if blocked else "PASS"
    require(report.get("status") == expected and rc == (2 if blocked else 0),
            "context exit/status mismatch")
    return {"status": "BLOCKED" if blocked else "NATIVE_OBSERVED", "report": report}


def offline_report(name, stdout, stderr, rc):
    require(rc == 0, f"test exit {rc}")
    require(not re.search(r"\b(?:skipped|SKIP|FAILED)\b|^FAIL:", stdout + stderr, re.M),
            "suite skipped coverage or reported failure")
    if name.endswith("-tests.py"):
        matches = re.findall(r"^Ran ([1-9]\d*) tests? in [\d.]+s$", stderr, re.M)
        require(len(matches) == 1 and len(re.findall(r"^OK$", stderr, re.M)) == 1
                and re.search(r"\nOK\n?\Z", stderr), "missing/ambiguous unit completion")
    elif name in HISTORICAL:
        require("HISTORICAL b60feef fixture coverage (not current production CLI)" in stdout,
                "missing historical source qualification")
        pairs = re.findall(r"^(\d+)/(\d+) passed$", stdout, re.M)
        require(len(pairs) == 1 and pairs[0][0] == pairs[0][1], "historical count mismatch")
        matches = [pairs[0][0]]
    else:
        matches = re.findall("^" + SUMMARY[name] + "$", stdout, re.M)
        require(len(matches) == 1, "missing/ambiguous suite completion")
    require(int(matches[0]) > 0, "empty suite")
    return {"status": "PASS", "checks": int(matches[0])}


class Cancelled(Exception):
    pass


class FailFast(Exception):
    pass


class SupervisionError(RuntimeError):
    pass


class ProcessInspectionError(SupervisionError):
    pass


def failure_status(exc):
    if isinstance(exc, Cancelled):
        return {"status": "CANCELLED", "failure_kind": "cancellation"}
    if isinstance(exc, FailFast):
        return {"status": "INCOMPLETE", "failure_kind": "fail-fast"}
    if isinstance(exc, SupervisionError):
        return {"status": "INCOMPLETE", "failure_kind": "supervision"}
    if isinstance(exc, subprocess.TimeoutExpired):
        return {"status": "INCOMPLETE", "failure_kind": "timeout"}
    return {"status": "ASSERTION_FAILURE", "failure_kind": "error"}


class Control:
    def __init__(self, seconds):
        self.deadline = time.monotonic() + seconds
        # Reserve shutdown/report/fixture-cleanup time INSIDE the total budget.
        self.work_deadline = self.deadline - min(5, seconds / 5)
        self.cancel = threading.Event()
        self.exhausted = threading.Event()
        self.failed = threading.Event()
        self.total_limited = True
        self.signum = None
        self.inspection_recoveries = 0

    def signal(self, signum, _frame):
        self.signum = signum
        self.cancel.set()

    def check(self):
        if self.failed.is_set():
            raise FailFast("remaining coverage stopped after suite failure/timeout/supervision error")
        if self.cancel.is_set():
            raise Cancelled("cancellation requested")
        if self.exhausted.is_set() or time.monotonic() >= self.work_deadline:
            raise subprocess.TimeoutExpired(
                "total-run budget" if self.total_limited else "per-suite budget", 0)


def inspection_recovered():
    # Fixed identity-free diagnostic: never include partial ps output/stderr.
    print("PROCESS_INSPECTION_RECOVERED: transient TimeoutExpired; "
          "fresh snapshot parsed on retry within original deadline", file=sys.stderr, flush=True)


def process_table(deadline, *, check=None, recovered=inspection_recovered):
    """Identity-only snapshot; never inspect command lines or environments."""
    transient = None
    for attempt in range(2):
        if attempt and check:
            check()  # Work cancellation/fail-fast; cleanup deliberately omits this.
        left = deadline - time.monotonic()
        if left <= 0:
            raise ProcessInspectionError("process inspection deadline exhausted") from transient
        allowance = min(5, left)
        try:
            listing = subprocess.run(
                ["/bin/ps", "-axo", "pid=,ppid=,pgid=,stat=,lstart="],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, timeout=allowance, check=True)
            break
        except (OSError, subprocess.SubprocessError) as exc:
            if isinstance(exc, subprocess.TimeoutExpired) and not attempt:
                transient = exc
                continue  # Discard all partial output; always launch a fresh ps.
            raise ProcessInspectionError(
                f"process inspection failed (attempt={attempt + 1}, "
                f"allowance={allowance:.6f}s, remaining={left:.6f}s): "
                f"{type(exc).__name__}: {exc}; stderr={getattr(exc, 'stderr', None)!r}") from exc
    table = {}
    for number, line in enumerate(listing.stdout.removesuffix("\n").split("\n"), 1):
        fields = line.split(None, 4)
        try:
            if any((ord(c) < 32 and c != "\t") or ord(c) >= 127 for c in line):
                raise ValueError("control character in process inspection")
            if len(fields) != 5:
                raise ValueError("expected pid, ppid, pgid, state and birth")
            pid, parent, group = map(int, fields[:3])
            if pid <= 0 or parent < 0 or group < 0 or pid in table:
                raise ValueError("invalid or duplicate process identity")
            # Darwin ps(1) and Linux procps: one primary state, then flags.
            # Darwin's S/X flags are legitimate; Z is never a suffix flag.
            # Darwin also emits ? for a transient/indeterminate state: live.
            state = fields[3]
            if (re.fullmatch(r"(?:[?IRSTUZ][+<>AELNSsVWX]*|[DIRSTtWXxZPK][<NLsl+]*)",
                             state) is None or len(set(state[1:])) != len(state[1:])):
                raise ValueError("invalid process state/flags")
            datetime.datetime.strptime(fields[4].strip(), "%a %b %d %H:%M:%S %Y")
            table[pid] = (parent, group, fields[3], fields[4])
        except ValueError as exc:
            raise ProcessInspectionError(
                f"malformed process inspection row {number}: {line!r}: {exc}") from exc
    if not table:
        raise ProcessInspectionError("empty process inspection")
    if time.monotonic() >= deadline:
        raise ProcessInspectionError("process inspection deadline exhausted after parsing") from transient
    if transient is not None:
        recovered()
    return table


def remember_descendants(proc, owned, table):
    parents = {pid for pid, birth in owned.items()
               if pid in table and table[pid][3] == birth}
    # Caller holds the direct child unreaped and validates its snapshot.
    # Never poll here: even a completed leader must keep its PID reserved.
    parents.add(proc.pid)
    while True:
        found = {pid for pid, row in table.items() if row[0] in parents} - parents
        if not found:
            break
        parents.update(found)
    for pid in parents:
        if pid in table:
            owned[pid] = table[pid][3]


def require_retained_child_support():
    if (not all(hasattr(os, name) for name in
                ("waitid", "WNOWAIT", "WEXITED", "WNOHANG", "P_PID",
                 "CLD_EXITED", "CLD_KILLED", "CLD_DUMPED")) or
            signal.getsignal(signal.SIGCHLD) != signal.SIG_DFL):
        raise SupervisionError("retained-child supervision requires waitid(WNOWAIT) "
                               "and default SIGCHLD; no competing child reaper is supported")


class RetainedChild:
    """Sole-reaper ownership, not a ps/PID lease. No wait/poll until release.

    A live or zombie direct session leader reserves its PID and hence PGID.
    waitid observes completion without releasing that kernel reservation.
    Contradictions permanently revoke signalling, including on error paths.
    """
    def __init__(self, proc):
        self.proc = proc
        self.birth = None
        self.completed = None
        self.lost = False
        self.released = False

    def reject(self, message):
        self.lost = True
        raise SupervisionError("retained child ownership unproved: " + message)

    def observe(self):
        if self.lost or self.released or self.proc.returncode is not None:
            self.reject("lost, released or already reaped")
        try:
            require_retained_child_support()
            status = os.waitid(os.P_PID, self.proc.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
        except (OSError, RuntimeError) as exc:
            self.lost = True
            raise SupervisionError(f"retained child ownership observation failed: {exc}") from exc
        if status is not None:
            if status.si_pid != self.proc.pid or status.si_code not in (
                    os.CLD_EXITED, os.CLD_KILLED, os.CLD_DUMPED):
                self.reject("unexpected waitid identity/status")
            completed = (status.si_status if status.si_code == os.CLD_EXITED
                         else -status.si_status)
            if self.completed is not None and self.completed != completed:
                self.reject("completed child status changed")
            self.completed = completed
        elif self.completed is not None:
            self.reject("completed child disappeared from waitid")
        return self.completed

    def inspect(self, table):
        if self.lost or self.released:
            self.reject("cannot adopt descendants after ownership loss/release")
        row = table.get(self.proc.pid)
        if (row is None or row[0] != os.getpid() or row[1] != self.proc.pid or
                (self.birth is not None and row[3] != self.birth)):
            self.reject("leader snapshot contradicts retained child identity/group")
        self.birth = row[3]


class PipeDrain:
    """Bounded nonblocking reads; EOF is independent of leader completion."""
    def __init__(self, proc, max_output=64 * 1024 * 1024):
        self.selector = selectors.DefaultSelector()
        self.streams = (proc.stdout, proc.stderr)
        self.chunks = [bytearray(), bytearray()]
        self.stdin = proc.stdin
        self.pending_input = bytearray()
        self.close_input = False
        self.size, self.max_output = 0, max_output
        try:
            if self.stdin is not None:
                os.set_blocking(self.stdin.fileno(), False)
            for index, stream in enumerate(self.streams):
                os.set_blocking(stream.fileno(), False)
                self.selector.register(stream, selectors.EVENT_READ, index)
        except BaseException:
            self.selector.close()
            raise

    def send(self, data, close=False):
        if self.stdin is None or self.stdin.closed:
            raise BrokenPipeError("child stdin is closed")
        self.pending_input.extend(data)
        self.close_input = close
        if self.pending_input:
            if self.stdin not in self.selector.get_map():
                self.selector.register(self.stdin, selectors.EVENT_WRITE, "stdin")
        elif close:
            self.stdin.close()

    def step(self, seconds):
        if not self.selector.get_map():
            if seconds:
                time.sleep(seconds)
            return
        for key, _ in self.selector.select(seconds):
            if key.data == "stdin":
                try:
                    count = os.write(key.fd, self.pending_input[:65536])
                except BlockingIOError:
                    continue
                except BrokenPipeError:
                    self.selector.unregister(self.stdin)
                    self.stdin.close()
                    self.pending_input.clear()
                    # communicate-compatible batch semantics; RPC checks EOF.
                    continue
                del self.pending_input[:count]
                if not self.pending_input:
                    self.selector.unregister(self.stdin)
                    if self.close_input:
                        self.stdin.close()
                continue
            # Fairness and bounded work even for a continuously writing child.
            for _ in range(16):
                try:
                    data = os.read(key.fd, 65536)
                except BlockingIOError:
                    break
                if not data:
                    self.selector.unregister(key.fileobj)
                    break
                self.chunks[key.data].extend(data)
                self.size += len(data)
                if self.size > self.max_output:
                    raise SupervisionError("output exceeded bounded pipe limit")

    def stop_input(self):
        if self.stdin is not None and not self.stdin.closed:
            if self.stdin in self.selector.get_map():
                self.selector.unregister(self.stdin)
            self.stdin.close()
        self.pending_input.clear()

    def finish(self, deadline):
        self.step(0)  # Preserve already queued pre-timeout bytes even at expiry.
        while self.selector.get_map():
            left = deadline - time.monotonic()
            if left <= 0:
                raise SupervisionError("output pipes did not close within cleanup budget")
            self.step(min(.02, left))

    def output(self):
        return tuple(bytes(data).decode(getattr(stream, "encoding", "utf-8"),
                                        getattr(stream, "errors", "strict"))
                     .replace("\r\n", "\n").replace("\r", "\n")
                     for data, stream in zip(self.chunks, self.streams))

    def close(self):
        self.stop_input()
        self.selector.close()
        for stream in self.streams:
            stream.close()


class ProcessSession:
    """Interactive and batch access without exposing a reaping operation."""
    def __init__(self, proc, leader, drain, check):
        self.proc, self.leader, self.drain, self.check = proc, leader, drain, check
        # Published by cleanup, frozen at its first signaling boundary.
        # None means no completion observed BEFORE supervisor signals.
        self.completed_returncode = None

    def step(self, seconds=.02):
        self.check()
        self.drain.step(seconds)
        return self.leader.observe()


@contextmanager
def supervised_process(argv, env, timeout, control=None, *, cwd=None,
                       stdin=False, binary=False, max_output=64 * 1024 * 1024):
    """Shared ownership lifecycle for batch execution AND interactive RPC.

    The unreaped direct session leader reserves the group ID through the LAST
    group signal. Observed descendants use best-effort fresh ps birth checks,
    not this kernel guarantee. Detach/reparent between snapshots can escape
    observation. No other code may reap this execute call's direct child.
    """
    if control:
        control.check()
    deadline = min(time.monotonic() + timeout,
                   control.work_deadline if control else float("inf"))
    run_deadline = deadline - min(1, max(0, deadline - time.monotonic()) / 5)
    if run_deadline <= time.monotonic():
        raise subprocess.TimeoutExpired(argv, timeout)
    require_retained_child_support()
    try:
        proc = subprocess.Popen(argv, cwd=ROOT if cwd is None else cwd, env=env,
                                stdin=subprocess.PIPE if stdin else subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=not binary,
                                start_new_session=True)
    except OSError as exc:
        raise SupervisionError(f"process launch failed: {type(exc).__name__}: {exc}") from exc
    owned = {}
    leader = RetainedChild(proc)
    drain = None
    session = None
    failure = None
    out = err = ""
    completed_returncode = None
    cleanup_signals_started = False

    def recovered():
        if control:
            control.inspection_recoveries += 1
        inspection_recovered()

    def inspect(cleanup=False):
        return process_table(deadline if cleanup else run_deadline,
                             check=control.check if control and not cleanup else None,
                             recovered=recovered)

    def signal_group(sig):
        nonlocal completed_returncode, cleanup_signals_started
        try:
            leader.observe()
        finally:
            if not cleanup_signals_started:
                completed_returncode = leader.completed
                cleanup_signals_started = True
        try:
            os.killpg(proc.pid, sig)
        except ProcessLookupError:
            pass
        except PermissionError:
            # Darwin can return EPERM for a group containing only zombies.
            # Ignore that case only after positive identity-only inspection.
            table = inspect(cleanup=True)
            leader.inspect(table)
            if any(row[1] == proc.pid and row[2][0] != "Z" for row in table.values()):
                raise

    def remember(table):
        leader.inspect(table)
        remember_descendants(proc, owned, table)

    def check():
        if control:
            control.check()
        if time.monotonic() >= run_deadline:
            if control and control.total_limited and deadline == control.work_deadline:
                control.exhausted.set()
            raise subprocess.TimeoutExpired(argv, timeout)
        leader.observe()
        remember(inspect())
        if control:
            control.check()
        if time.monotonic() >= run_deadline:
            if control and control.total_limited and deadline == control.work_deadline:
                control.exhausted.set()
            raise subprocess.TimeoutExpired(argv, timeout)

    try:
        drain = PipeDrain(proc, max_output)
        session = ProcessSession(proc, leader, drain, check)
        yield session
    except Exception as exc:
        failure = (SupervisionError(
            f"execution supervision failed: {type(exc).__name__}: {exc}")
            if isinstance(exc, (OSError, RuntimeError, subprocess.SubprocessError))
            and not isinstance(exc, (SupervisionError, subprocess.TimeoutExpired)) else exc)
    finally:
        # Capture only pre-cleanup completion, never our own TERM/KILL exit.
        # Snapshot before terminating the parent: nested harnesses use setsid.
        # Keep known descendants even if they subsequently become orphans.
        cleanup_errors = []

        def attempt(label, action):
            try:
                return action()
            except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                cleanup_errors.append((label, exc))
                return None

        attempt("observe pre-cleanup child completion", leader.observe)
        completed_returncode = leader.completed

        def signal_pid(pid, sig):
            # A round's old snapshot is not permission to signal an individual.
            table = inspect(cleanup=True)
            row = table.get(pid)
            if not row or row[3] != owned[pid] or row[2][0] == "Z":
                return
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                pass

        for sig in (signal.SIGTERM, signal.SIGKILL):
            table = attempt(f"{sig.name} identity inspection",
                            lambda: inspect(cleanup=True))
            if table is not None:
                attempt(f"{sig.name} remember descendants", lambda: remember(table))
            # One denied group/PID must not prevent the other owned targets
            # from receiving this signal, or any target from receiving KILL.
            attempt(f"{sig.name} group {proc.pid}", lambda: signal_group(sig))
            if table is not None:
                for pid, birth in owned.items():
                    row = table.get(pid)
                    if pid != proc.pid and row and row[3] == birth and row[2][0] != "Z":
                        attempt(f"{sig.name} pid {pid}",
                                lambda: signal_pid(pid, sig))
            # Even a completed leader remains unreaped through both signals.
            if sig == signal.SIGTERM:
                time.sleep(min(.05, max(0, deadline - time.monotonic()) / 4))
        def verify():
            while True:
                table = inspect(cleanup=True)
                live = {pid for pid, birth in owned.items()
                        if pid in table and table[pid][3] == birth and table[pid][2][0] != "Z"}
                # Group membership is meaningful only while kernel ownership
                # is retained. Also verify ordinary, unobserved group members.
                if not leader.lost:
                    leader.observe()
                    leader.inspect(table)
                    live.update(pid for pid, row in table.items()
                                if row[1] == proc.pid and row[2][0] != "Z")
                if not live:
                    break
                if time.monotonic() + .02 >= deadline:
                    raise RuntimeError(f"owned process cleanup incomplete: {live}")
                time.sleep(.02)

        attempt("verify owned descendants terminated", verify)
        # Irreversible boundary. NO group signal (including fallback) below.
        leader.released = True
        if drain is not None:
            attempt("close direct child stdin", drain.stop_input)
            attempt("drain direct child pipes", lambda: drain.finish(deadline))
            output = attempt("decode direct child output", drain.output)
            if output is not None:
                out, err = output
            attempt("close direct child pipes", drain.close)
        else:
            if proc.stdin is not None:
                attempt("close direct child stdin", proc.stdin.close)
            attempt("close direct child stdout", proc.stdout.close)
            attempt("close direct child stderr", proc.stderr.close)
        attempt(f"reap pid {proc.pid}",
                lambda: proc.wait(timeout=max(0, deadline - time.monotonic())))
        if session is not None:
            session.completed_returncode = completed_returncode
        if cleanup_errors:
            if failure is None and completed_returncode not in (None, 0):
                failure = subprocess.CalledProcessError(completed_returncode, argv,
                                                        output=out, stderr=err)
            details = "; ".join(f"{label}: {type(exc).__name__}: {exc}"
                                for label, exc in cleanup_errors)
            prior = f"{type(failure).__name__}: {failure}" if failure else "none"
            error = SupervisionError(f"cleanup failed ({details}); prior failure: {prior}; "
                                     f"completed child exit: {completed_returncode}")
            error.primary_failure = failure
            if completed_returncode is not None:
                error.returncode = completed_returncode
            error.output, error.stderr = out, err
            raise error from cleanup_errors[0][1]
    if failure:
        failure.output, failure.stderr = out, err
        raise failure


def execute(argv, env, timeout, control=None, *, cwd=None, input_text=None):
    """Batch API, also used by native helpers; preserves completed-child status."""
    with supervised_process(argv, env, timeout, control, cwd=cwd,
                            stdin=input_text is not None) as session:
        if input_text is not None:
            session.drain.send(input_text.encode(session.proc.stdin.encoding), close=True)
        while True:
            if session.step(0) is not None:
                break
            for _ in range(5):
                session.drain.step(.02)
                if session.leader.observe() is not None:
                    break
            if session.leader.completed is not None:
                break
    out, err = session.drain.output()
    return out, err, session.proc.returncode


def environment(work, native=False, suite=None):
    for leaf in ("home", "tmp", "template/info"):
        (work / leaf).mkdir(parents=True, exist_ok=True)
    # Empty templates omit .git/info, which older fixtures correctly expect
    # ordinary git init to create. Supply only that container, no host hooks.
    (work / "template/info/exclude").write_text("")
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(work / "home"), "TMPDIR": str(work / "tmp"),
        "GIT_CEILING_DIRECTORIES": str(work), "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_SYSTEM": "/dev/null", "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_TEMPLATE_DIR": str(work / "template"), "GIT_TERMINAL_PROMPT": "0",
        "GIT_PAGER": "cat", "PAGER": "cat", "LC_ALL": "C",
        "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1",
    }
    # Native harnesses resolve executable paths from PATH, then construct their
    # own sandbox environment. No native client ever uses this outer HOME.
    if native and suite in F.SCOPES and F.OVERRIDE in os.environ:
        env[F.OVERRIDE] = os.environ[F.OVERRIDE]
    if not native:
        (work / "forbidden").mkdir()
        for name in ("bd", "beads", "claude", "codex", "copilot", "curl", "wget"):
            path = work / "forbidden" / name
            path.write_text("#!/bin/bash\nprintf 'forbidden acceptance runtime call\\n' >&2\nexit 99\n")
            path.chmod(0o700)
        env["PATH"] = f"{work / 'forbidden'}:{env['PATH']}"
    return env


def validation(env, control=None):
    def run(argv, env, timeout):
        return execute(argv, env, timeout, control)

    shells = sorted([*ROOT.glob("*.sh"), *ROOT.glob("test/*.sh")])
    python_files = sorted(ROOT.glob("test/*.py"))
    for path in python_files:
        if control:
            control.check()
        ast.parse(path.read_text(), filename=str(path))
    source = (ROOT / "domestique.sh").read_text()
    ast.parse(source.split("<<'DOM_BEADS_PY'\n", 1)[1].split("\nDOM_BEADS_PY", 1)[0])
    require(shutil.which("shellcheck", path=env["PATH"]), "ShellCheck missing; install outside this task")
    # Main owns fixture cleanup under the total deadline.
    helper = Path(env["TMPDIR"]) / "resolve-core"
    definitions = Path(env["TMPDIR"]) / "definitions.sh"
    definitions.write_text(source.split("\nusage()", 1)[0])
    out, err, rc = run(
        ["/bin/bash", "-c", 'source "$1"; emit_private_core_resolver', "_", str(definitions)],
        env, 60)
    require(rc == 0, f"resolver emission: {err}")
    helper.write_text(out)
    for path in [*shells, helper]:
        out, err, rc = run(["/bin/bash", "-n", str(path)], env, 60)
        require(rc == 0, f"Bash syntax {path}: {err}")
    out, err, rc = run(["shellcheck", "--severity=warning", "--format=json",
                       *map(str, shells), str(helper)], env, 120)
    require(rc in (0, 1), f"ShellCheck error: {err}")
    diagnostics = json.loads(out)
    require(rc == 0 and diagnostics == [], f"ShellCheck exit {rc}, warnings: {diagnostics}")
    out, err, rc = run(["git", "--no-pager", "diff", "--check"], env, 60)
    require(rc == 0, f"git diff --check: {out}{err}")
    return {"status": "PASS", "shell_files": len(shells), "emitted_helpers": 1,
            "python_files": len(python_files), "embedded_python": 1,
            "shellcheck_warning_exceptions": 0}


def budget(value):
    try:
        seconds = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("budget must be positive finite seconds") from None
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError("budget must be positive finite seconds")
    return seconds


def exit_code(results):
    return (1 if any(r["status"] in ("ASSERTION_FAILURE", "CANCELLED", "INCOMPLETE")
                     for r in results) else
            2 if any(r["status"] == "BLOCKED" for r in results) else 0)


def run_tasks(tasks, suite, jobs, control, record, heartbeat=10):
    """Only submit available slots; cancellation never drains a queued backlog."""
    pending = list(tasks)
    active = {}
    next_beat = time.monotonic() + heartbeat
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        while pending or active:
            try:
                control.check()
            except (Cancelled, FailFast, subprocess.TimeoutExpired) as exc:
                for category, name in pending:
                    record({"category": category, "suite": name,
                            "status": "CANCELLED" if isinstance(exc, Cancelled) else "INCOMPLETE",
                            "diagnostic": type(exc).__name__ + "; not started"})
                pending.clear()
            else:
                while pending and len(active) < jobs:
                    task = pending.pop(0)
                    active[pool.submit(suite, task)] = task
            if not active:
                break
            done, _ = wait(active, timeout=.1, return_when=FIRST_COMPLETED)
            for future in done:
                category, name = active.pop(future)
                try:
                    result = future.result()
                except Exception as exc:
                    result = {"category": category, "suite": name, "status": "ASSERTION_FAILURE",
                              "diagnostic": "runner worker error: " + type(exc).__name__}
                if result["status"] in ("ASSERTION_FAILURE", "INCOMPLETE"):
                    control.failed.set()
                record(result)
            if time.monotonic() >= next_beat:
                print(f"PROGRESS running={len(active)} pending={len(pending)} "
                      f"remaining={max(0, control.deadline - time.monotonic()):.1f}s",
                      flush=True)
                next_beat = time.monotonic() + heartbeat


def provenance(control):
    """Content pin includes uncommitted runner/tests, not just an old HEAD."""
    sources = sorted({*ROOT.glob("*.sh"), *ROOT.glob("test/*.py"),
                      *ROOT.glob("test/*.sh"), ROOT / "README.md",
                      ROOT / "docs/install-upgrade-design.md"})
    hashes = {}
    for path in sources:
        control.check()
        hashes[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    tools = {}
    for name in ("python3", "bash", "git", "shellcheck", "ps"):
        path = (PYTHON if name == "python3" else "/bin/" + name
                if name in ("bash", "ps") else shutil.which(name))
        control.check()
        tools[name] = {"path": path, "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()
                       if path else None}
    return {"source_sha256": hashes, "tools": tools, "python": platform.python_version(),
            "platform": {"system": sys.platform, "machine": platform.machine()}}


def selection(args):
    """Filter the mode's intact manifest; explicit order is submission order."""
    tasks = []
    if not args.native_only:
        tasks += [("CURRENT", n) for n in (CURRENT + UNIT_EXTRA if args.exhaustive else QUICK)]
        if args.exhaustive:
            tasks += [("HISTORICAL_FIXTURE", n) for n in HISTORICAL]
    if args.native or args.native_only:
        tasks += [("NATIVE", n) for n in NATIVE]
    if not args.native_only:
        tasks.append(("CURRENT", "syntax-lint-ast-diff"))
    if getattr(args, "suite", None) is not None:
        selected = []
        for token in args.suite:
            task = tuple(token.split(":"))
            require(task in tasks, f"invalid or unavailable --suite {token!r}; "
                    "expected exact CATEGORY:NAME permitted by the mode/flags")
            require(task not in selected, f"duplicate --suite {token!r}")
            selected.append(task)
        require(selected, "--suite selection must not be empty")
        return selected
    return tasks


def full_offline_acceptance(report):
    expected = {("CURRENT", n) for n in CURRENT + UNIT_EXTRA}
    expected |= {("HISTORICAL_FIXTURE", n) for n in HISTORICAL}
    expected.add(("CURRENT", "syntax-lint-ast-diff"))
    passed = [(r["category"], r["suite"]) for r in report["results"] if r["status"] == "PASS"]
    return (report["mode"] == "EXHAUSTIVE"
            and report["coverage"] in ("FULL_OFFLINE", "FULL_OFFLINE_AND_NATIVE")
            and report["status"] == "COMPLETE" and report["exit"] in (0, 2)
            and expected <= set(passed) and len(passed) == len(set(passed)))


def main():
    parser = Parser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--native", action="store_true", help="offline suite plus native fixtures")
    mode.add_argument("--native-only", action="store_true", help="native fixtures only; NOT offline acceptance")
    parser.add_argument("--exhaustive", action="store_true", help="full coverage; may take hours")
    parser.add_argument("--suite", action="append", metavar="CATEGORY:NAME",
                        help="repeatable exact mode-permitted scope; caller submission order; "
                        "always partial coverage, even when selecting all scopes")
    parser.add_argument("--global-diagnostics", action="store_true",
                        help="exhaustive offline only: opt-in global helper timing evidence")
    parser.add_argument("--jobs", type=int, choices=(1, 2), default=1,
                        help="QUICK parallelism (default 1); EXHAUSTIVE requires 1")
    parser.add_argument("--total-seconds", type=budget,
                        help="total including cleanup (QUICK default/max 1200; EXHAUSTIVE explicit)")
    parser.add_argument("--suite-seconds", type=budget,
                        help="per-suite cap (QUICK default/max 600; EXHAUSTIVE explicit)")
    args = parser.parse_args()
    if (args.native or args.native_only) and not args.exhaustive:
        parser.error("native selection requires --exhaustive and explicit non-model native consent")
    if args.exhaustive:
        if args.jobs != 1:
            parser.error("EXHAUSTIVE must be serial (--jobs 1)")
        if args.total_seconds is None or args.suite_seconds is None:
            parser.error("EXHAUSTIVE requires explicit --total-seconds AND --suite-seconds")
    elif ((args.total_seconds or 1200) > 1200 or (args.suite_seconds or 600) > 600):
        parser.error("QUICK budgets cannot exceed 1200 total / 600 suite; select --exhaustive")
    if args.global_diagnostics and (not args.exhaustive or args.native_only):
        parser.error("--global-diagnostics requires exhaustive offline coverage")
    args.total_seconds = 1200 if args.total_seconds is None else args.total_seconds
    args.suite_seconds = 600 if args.suite_seconds is None else args.suite_seconds
    try:
        tasks = selection(args)
    except ValueError as exc:
        parser.error(str(exc))
    require(not sys.flags.optimize, "run without -O/-OO; harness assertions are required")
    control = Control(args.total_seconds)
    previous = {sig: signal.signal(sig, control.signal)
                for sig in (signal.SIGINT, signal.SIGTERM)}
    artifacts = Path(tempfile.mkdtemp(prefix="domestique-acceptance-")).resolve()
    print(f"SESSION_ARTIFACTS={artifacts}", flush=True)
    require(ROOT not in artifacts.parents,
            "discovery/protocol fixtures need the ordinary OS-private TMPDIR outside this checkout; "
            "unset a checkout-local TMPDIR before invoking the runner")
    results = []
    work = None
    report = {"date": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "session": artifacts.name, "status": "INCOMPLETE", "exit": 1,
              "mode": "EXHAUSTIVE" if args.exhaustive else "QUICK",
              "coverage": "SELECTED_SCOPES_NOT_FULL_ACCEPTANCE" if args.suite is not None else
              "NATIVE_ONLY" if args.native_only else
              "FULL_OFFLINE_AND_NATIVE" if args.native else
              "FULL_OFFLINE" if args.exhaustive else "QUICK_SUBSET_NOT_FULL_OFFLINE",
              "full_offline_acceptance": False, "jobs": args.jobs,
              "requested": [{"category": c, "suite": n} for c, n in tasks],
              "diagnostics": {"global_enabled": args.global_diagnostics,
                              "format": "global-diag-v1; elapsed integer seconds",
                              "timings": "paired helper start/end by case/caller; nested, not additive",
                              "unattributed": "setup, direct operations, gaps; unfinished starts on cancellation"},
              "budgets": {"total_seconds": args.total_seconds, "suite_seconds": args.suite_seconds},
              "results": results, "provenance": None}
    print(json.dumps({k: report[k] for k in
                      ("mode", "coverage", "requested", "jobs", "budgets", "diagnostics")}), flush=True)

    def persist():
        report["updated"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        # Raw fixture diagnostics stay in isolated stdout/stderr files only.
        encoded = json.dumps(report, indent=2)
        for path, replacement in ((str(artifacts), "<artifacts>"), (str(work), "<fixture>"),
                                  (str(ROOT), "<checkout>")):
            if path != "None":
                encoded = encoded.replace(path, replacement)
        temp_report = artifacts / "report.json.tmp"
        temp_report.write_text(encoded + "\n")
        temp_report.replace(artifacts / "report.json")

    def record(result):
        results.append(result)
        persist()
        print(json.dumps({k: v for k, v in result.items()
                          if k not in ("diagnostic", "command")}), flush=True)

    persist()
    try:
        report["provenance"] = provenance(control)
        persist()
        control.check()
        work = Path(tempfile.mkdtemp(prefix=".acceptance-", dir=ROOT)).resolve()
        def suite(task):
            category, name = task
            key = category + "-" + name
            start = time.monotonic()
            local = Control(args.suite_seconds)
            local.cancel, local.signum = control.cancel, control.signum
            local.deadline = min(local.deadline, control.work_deadline)
            local.work_deadline = local.deadline
            local.total_limited = local.deadline == control.work_deadline
            local.exhausted = control.exhausted
            local.failed = control.failed
            result = {"category": category, "suite": name}
            try:
                local.check()
                scratch = work / key
                scratch.mkdir(mode=0o700)
                env = environment(scratch, category == "NATIVE", name)
                selected = None
                if category == "NATIVE" and name in F.SCOPES:
                    try:
                        selected = F.resolve(env)
                        result["native_fixture"] = selected
                    except F.MissingDefault:
                        pass  # Harness retains its ordinary missing-tool behavior.
                if name == "global.sh" and args.global_diagnostics:
                    env["DOM_TEST_DIAG"] = str(artifacts / "global-progress.tsv")
                print(f"START {category} {name}", flush=True)
                if name == "syntax-lint-ast-diff":
                    result.update(validation(env, local))
                    local.check()
                    return result
                argv = (["/bin/bash"] if name.endswith(".sh") else [PYTHON, "-B", "-W", "error"])
                argv.append(str(ROOT / "test" / name))
                if category == "NATIVE":
                    argv.append("--native" if name == "beads-cleanup.py" else "--run")
                result["command"] = argv
                if name in ("native-discovery.py", "native-discovery-tests.py"):
                    native_tmp = artifacts / (key + "-fixture")
                    native_tmp.mkdir(mode=0o700)
                    env["TMPDIR"] = str(native_tmp)
                out, err, rc = execute(argv, env, args.suite_seconds, local)
                (artifacts / (key + ".stdout")).write_text(out)
                (artifacts / (key + ".stderr")).write_text(err)
                result["exit"] = rc
                local.check()
                result.update(native_report(name, out, rc) if category == "NATIVE" else
                              offline_report(name, out, err, rc))
                if category == "NATIVE" and name in F.SCOPES and "native_fixture" in result:
                    require(F.resolve(env) == result["native_fixture"] == selected,
                            "qualified native fixture changed during scope")
                    evidence = result.get("report", {})
                    if name == "beads-native-context.py":
                        require({"path": evidence.get("binary"),
                                 "sha256": evidence.get("binary_sha256")} == result["native_fixture"],
                                "context fixture provenance differs from selection")
                if "counts" in result.get("report", {}):
                    result["counts"] = {
                        ("NATIVE_OBSERVED" if k == "NATIVE_DISCOVERY_OBSERVED" else k): v
                        for k, v in result["report"]["counts"].items()}
                result.pop("report", None)
                local.check()
            except (Cancelled, FailFast, ValueError, OSError, RuntimeError,
                    subprocess.SubprocessError, SyntaxError) as exc:
                if hasattr(exc, "output"):
                    (artifacts / (key + ".stdout")).write_text(exc.output or "")
                    (artifacts / (key + ".stderr")).write_text(exc.stderr or "")
                result.pop("report", None)
                (artifacts / (key + ".error")).write_text(str(exc))
                result.update(failure_status(exc),
                              diagnostic=type(exc).__name__ + "; see isolated .error diagnostic")
                if getattr(exc, "returncode", None) is not None:
                    result["exit"] = exc.returncode
                if getattr(exc, "primary_failure", None) is not None:
                    primary = exc.primary_failure
                    result["primary_failure"] = {
                        "type": type(primary).__name__, **failure_status(primary)}
                    if getattr(primary, "returncode", None) is not None:
                        result["primary_failure"]["exit"] = primary.returncode
            finally:
                if local.inspection_recoveries:
                    result["process_inspection_recoveries"] = local.inspection_recoveries
            result["seconds"] = round(time.monotonic() - start, 2)
            return result

        run_tasks(tasks, suite, args.jobs, control, record)
        control.check()
        require(provenance(control) == report["provenance"], "source/tools changed during run")
    except (Cancelled, FailFast, ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
        record({"category": "RUNNER", "suite": "run-control",
                **failure_status(exc), "diagnostic": str(exc)})
    finally:
        # No unbounded TemporaryDirectory teardown in the parent. Keep evidence
        # and explicitly fail if the remaining total cannot finish cleanup.
        targets = ([work] if work else []) + list(artifacts.glob("*-fixture"))
        if targets:
            try:
                left = control.deadline - time.monotonic()
                if left <= 0:
                    raise subprocess.TimeoutExpired("total-run budget before fixture cleanup", 0)
                _, _, rc = execute(
                    [PYTHON, "-B", "-c",
                     "import shutil,sys; [shutil.rmtree(p) for p in sys.argv[1:]]",
                     *map(str, targets)], {"PATH": "/usr/bin:/bin"}, left)
                require(rc == 0, f"fixture cleanup exit {rc}")
            except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
                record({"category": "RUNNER", "suite": "fixture-cleanup",
                        "status": "INCOMPLETE",
                        "failure_kind": "timeout" if isinstance(exc, subprocess.TimeoutExpired)
                        else "supervision",
                        "diagnostic": str(exc)})
        if time.monotonic() >= control.deadline:
            record({"category": "RUNNER", "suite": "total-deadline",
                    "status": "INCOMPLETE", "failure_kind": "timeout",
                    "diagnostic": "total budget exhausted"})
    def outcome():
        # Cancellation during cleanup is still an overall failure even when
        # every requested suite has already passed (or validated a blocker).
        cancelled = control.cancel.is_set()
        completed = [(r["category"], r["suite"]) for r in results if r["category"] != "RUNNER"]
        if (sorted(completed) != sorted(tasks)
                and not any(r["suite"] == "coverage-completeness" for r in results)):
            results.append({"category": "RUNNER", "suite": "coverage-completeness",
                            "status": "INCOMPLETE", "diagnostic": "missing/duplicate requested result"})
        rc = 1 if cancelled else exit_code(results)
        report.update(exit=rc, signal=control.signum,
                      status="CANCELLED" if cancelled else
                      "INCOMPLETE" if rc == 1 else "COMPLETE")
        report["full_offline_acceptance"] = full_offline_acceptance(report)
        return rc

    try:
        try:
            # Flush still-incomplete evidence while cancellation is owned.
            # No COMPLETE snapshot is published with runner handlers installed.
            persist()
        finally:
            # A signal caught immediately before either restoration (including
            # SIGTERM while restoring SIGINT) must precede the final snapshot.
            # Restore the second disposition even if native SIGINT interrupts
            # the first restoration. Restored signals have native behavior.
            try:
                signal.signal(signal.SIGINT, previous[signal.SIGINT])
            finally:
                signal.signal(signal.SIGTERM, previous[signal.SIGTERM])
        rc = outcome()
        persist()
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
        results.append({"category": "RUNNER", "suite": "report-finalization",
                        "status": "ASSERTION_FAILURE", "diagnostic": str(exc)})
        rc = outcome()
        try:
            persist()
        except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as retry:
            # Surface both persistence errors, never turn them into exit zero.
            print(f"report finalization failed: {exc}; retry failed: {retry}", file=sys.stderr)
    print(f"ACCEPTANCE mode={report['mode']} coverage={report['coverage']} "
          f"full_offline_acceptance={report['full_offline_acceptance']} "
          f"exit={rc}; report={artifacts / 'report.json'}", flush=True)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
