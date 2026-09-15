"""Disposable probes of actual global.sh helpers; never run the lifecycle matrix."""
import importlib.util
import os
from pathlib import Path
import shutil
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("acceptance", ROOT / "test/acceptance.py")
A = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(A)
SOURCE = (ROOT / "test/global.sh").read_text()
HELPERS = SOURCE.split("PASS=0 FAIL=0 N=0\n", 1)[1].split("\ndiag_setup\n", 1)[0]


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.work = self.base / "fixtures"
        self.work.mkdir()
        self.log = self.base / "progress.tsv"
        self.env = {"PATH": os.environ["PATH"], "HOME": str(self.work / "home"),
                    "WORK": str(self.work), "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONHASHSEED": "0", "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_CONFIG_GLOBAL": "/dev/null"}
        self.prefix = ('set -uo pipefail\nPASS=0 FAIL=0 N=1\n'
                       'F="$WORK/f1"; mkdir -p "$F/cwd" "$HOME"\nCORE="$WORK/core"\n'
                       + HELPERS + '\ndiag_setup\n')

    def probe(self, body, enabled=True, timeout=5):
        env = dict(self.env)
        if enabled:
            env["DOM_TEST_DIAG"] = str(self.log)
        return A.execute(["/bin/bash", "-c", self.prefix + body], env, timeout)

    def events(self):
        rows = [line.split("\t") for line in self.log.read_text().splitlines()]
        for row in rows:
            self.assertEqual(len(row), 7)
            self.assertEqual(row[0], "global-diag-v1")
            self.assertTrue(row[1].isdigit())
            self.assertRegex(row[2], r"^f\d+$")
            self.assertTrue(row[3].isdigit())
            self.assertGreater(int(row[3]), 0)
            self.assertIn(row[4], ("run", "check", "tree", "fixture", "native_inventory",
                                   "direct", "summary"))
            self.assertIn(row[5], ("start", "end"))
            self.assertRegex(row[6], r"^(?:-|\d+)$")
        return rows

    def test_disabled_enabled_equivalence_and_payload_nonleakage(self):
        body = ("run -c 'printf payload_7392; printf error_7392 >&2; exit 7'\n"
                'printf "helper=%s RC=%s\\n" "$?" "$RC"\n'
                'cat "$F/out"; cat "$F/err" >&2\n'
                'check "arbitrary_label_7392" test "$RC" -eq 7\n'
                'tree "$HOME"\nprintf "snapshot=%s\\n" "$?"\n')
        disabled = self.probe(body, False)
        self.assertFalse(self.log.exists())
        enabled = self.probe(body)
        self.assertEqual(disabled, enabled)
        self.assertIn("helper=0 RC=7", enabled[0])
        self.assertIn("payload_7392", enabled[0])
        self.assertEqual(enabled[1], "error_7392")
        self.assertNotIn("7392", self.log.read_text())
        rows = self.events()
        self.assertEqual([(r[4], r[5], r[6]) for r in rows],
                         [("run", "start", "-"), ("run", "end", "7"),
                          ("check", "start", "-"), ("check", "end", "0"),
                          ("tree", "start", "-"), ("tree", "end", "0")])
        for start, end in zip(rows[::2], rows[1::2]):
            self.assertEqual(start[2:5], end[2:5])
            self.assertLessEqual(int(start[1]), int(end[1]))

    def test_failed_check_preserves_counts_and_stderr(self):
        body = 'check "failed_label_7392" false\nprintf "%s %s %s\\n" "$?" "$PASS" "$FAIL"\n'
        self.assertEqual(self.probe(body, False), self.probe(body))
        self.assertEqual(self.events()[-1][4:], ["check", "end", "1"])
        self.assertNotIn("failed_label", self.log.read_text())

    def test_snapshot_injected_failure_status_and_streams(self):
        body = ('python3() { printf injected_out; printf injected_err >&2; return 23; }\n'
                'tree "$HOME"\n')
        self.assertEqual(self.probe(body, False), ("injected_out", "injected_err", 23))
        self.assertEqual(self.probe(body), ("injected_out", "injected_err", 23))
        self.assertEqual(self.events()[-1][4:], ["tree", "end", "23"])

    def test_native_inventory_failure_status_and_streams(self):
        body = 'native_inventory claude\n'
        disabled = self.probe(body, False)
        self.assertNotEqual(disabled[2], 0)
        self.assertIn("AssertionError", disabled[1])
        self.assertEqual(disabled, self.probe(body))
        self.assertEqual(self.events()[-1][4:], ["native_inventory", "end", "1"])

    def test_native_inventory_injected_success_preserves_streams(self):
        body = ('python3() { printf inventory_out; printf inventory_err >&2; return 0; }\n'
                'native_inventory claude\n')
        self.assertEqual(self.probe(body, False), self.probe(body))
        self.assertEqual(self.events()[-1][4:], ["native_inventory", "end", "0"])

    def test_fixture_identity_and_append_only(self):
        self.log.write_text("prior-record\n")
        # Probe diagnostic identity, not git-init performance or lifecycle.
        body = 'git() { return 0; }\nfixture\nfixture\n'
        disabled = self.probe(body, False)
        shutil.rmtree(self.work / "f2")
        shutil.rmtree(self.work / "f3")
        self.assertEqual(self.probe(body), disabled)
        lines = self.log.read_text().splitlines()
        self.assertEqual(lines[0], "prior-record")
        self.assertEqual([r.split("\t")[2] for r in lines[1:]], ["f2", "f2", "f3", "f3"])

    def test_open_failure_explicit(self):
        self.log = self.base
        out, err, rc = self.probe("printf must_not_run\n")
        self.assertEqual((out, rc), ("", 1))
        self.assertIn("diag: open failed", err)

    def test_write_failure_explicit_even_in_command_substitution(self):
        for body in ('diag run start -\n', 'ignored="$(tree "$HOME")"\nprintf must_not_run\n'):
            with self.subTest(body=body):
                out, err, rc = self.probe("exec 9>&-\n" + body)
                self.assertEqual((out, rc), ("", 1))
                self.assertIn("diag: write failed", err)

    def test_diagnostic_path_outside_snapshot_roots(self):
        for path in (self.work / "bad.tsv", self.base / "link/bad.tsv"):
            link = self.base / "link"
            if not link.exists():
                link.symlink_to(self.work, target_is_directory=True)
            self.log = path
            out, err, rc = self.probe("printf must_not_run\n")
            self.assertEqual((out, rc), ("", 1))
            self.assertIn("outside fixture/snapshot roots", err)
            self.assertFalse(path.exists())

    def test_partial_progress_survives_cancellation_and_owned_cleanup(self):
        control = A.Control(8)
        import threading

        def cancel_after_start():
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                if self.log.exists() and "\trun\tstart\t" in self.log.read_text():
                    break
                time.sleep(.02)
            control.cancel.set()

        watcher = threading.Thread(target=cancel_after_start)
        watcher.start()
        try:
            env = dict(self.env, DOM_TEST_DIAG=str(self.log))
            with self.assertRaises(A.Cancelled):
                A.execute(["/bin/bash", "-c", self.prefix +
                           'run -c "sleep 60"\n'], env, 6, control)
        finally:
            watcher.join()
        rows = self.events()
        self.assertEqual(rows[0][4:6], ["run", "start"])
        # TERM may let the waiting shell record its child's signal exit before
        # that shell is itself terminated. Either partial form is valid.
        self.assertLessEqual(len(rows), 2)
        if len(rows) == 2:
            self.assertEqual(rows[1][4:6], ["run", "end"])
            self.assertNotEqual(rows[1][6], "0")
        self.assertTrue(self.log.exists())

    def test_helpers_and_test_are_source_bound(self):
        self.assertIn('python3 - "$@"', HELPERS)
        self.assertIn('python3 - "$HOME" "$CORE" "$1"', HELPERS)
        pins = A.provenance(A.Control(5))["source_sha256"]
        self.assertIn("test/global.sh", pins)
        self.assertIn("test/global-diagnostics-tests.py", pins)
        self.assertIn("global-diagnostics-tests.py", A.QUICK)
        self.assertIn("global-diagnostics-tests.py", A.UNIT_EXTRA)


if __name__ == "__main__":
    unittest.main()
