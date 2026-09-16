#!/usr/bin/env python3
"""Small path-guard differential suite; native BSD, synthetic GNU on Darwin.

No native clients or databases. Checksum-pinned 20b6fe8 helpers are the oracle.
Run: python3 test/global-path-tests.py
"""
import importlib.util
import os
from pathlib import Path
import platform
import tempfile
import unittest
from unittest import mock

import global_path_baseline as oracle
import preview_fixture

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("acceptance", ROOT / "test/acceptance.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class Paths(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.control = runner.Control(100)
        cls.temp = tempfile.TemporaryDirectory(prefix="dom-path-")
        cls.work = Path(cls.temp.name).resolve()
        cls.env = runner.environment(cls.work)
        current = preview_fixture.source().decode()
        cls.sources = []
        for name, source in (("old", oracle.baseline(current)), ("new", current)):
            p = cls.work / (name + ".sh")
            p.write_text(source.split("\nusage()", 1)[0])
            cls.sources.append(p)
        # Keep the real batch implementation available to fault injections.
        start = current.index("global_stat() {")
        end = current.index("\n}\n", start) + 3
        cls.native = current[start:end].replace("global_stat()", "native_stat()", 1)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.base = self.work / self._testMethodName
        self.base.mkdir()
        self.leaf = self.base / "directory" / "file"
        self.leaf.parent.mkdir()
        self.leaf.write_text("data")

    def run_guard(self, source, path=None, boundary=None, readonly=0, hook="", tail=""):
        command = (
            'source "$1"\nG_UID="$(id -u)"\nG_READONLY="$4"\n'
            + hook + '\nglobal_path "$2" "$3"\n' + tail)
        return runner.execute(
            ["/bin/bash", "-c", command, "_", str(source),
             str(path or self.leaf), str(boundary or self.base), str(readonly)],
            self.env, 8, self.control)

    def compare(self, expected, **kwargs):
        for source in self.sources:
            with self.subTest(source=source.name, **kwargs):
                out, err, rc = self.run_guard(source, **kwargs)
                self.assertEqual(rc == 0, expected, (out, err))

    def fault(self, body, **kwargs):
        hook = self.native + '\nTARGET="$2"\nglobal_stat() {\n' + body + "\n}\n"
        out, err, rc = self.run_guard(self.sources[1], hook=hook, **kwargs)
        self.assertNotEqual(rc, 0, (out, err))
        self.assertIn("domestique global:", err)
        return err

    def test_positive_and_missing(self):
        self.compare(True)
        self.compare(True, path=self.base / "absent" / "tail")
        self.compare(False, path=self.leaf / "tail")

    def test_unusual_names(self):
        for name in ("a b", "quote'\"\\%*?[]", "-dash", "é雪", " space "):
            p = self.base / name
            p.write_text("data")
            self.compare(True, path=p)

    def test_noncanonical(self):
        for p in ("relative", "/", str(self.base) + "//x", str(self.base) + "/../x",
                  str(self.base) + "/", str(self.base) + "/.", str(self.base) + "/..",
                  str(self.base) + "/x=y", str(self.base) + "/x\nz",
                  str(self.base) + "/x\tz", str(self.base) + "/x\x7fz"):
            self.compare(False, path=p)

    def test_symlink_and_type(self):
        link = self.base / "link"
        link.symlink_to(self.leaf.parent)
        self.compare(False, path=link / "file")
        link.unlink()
        link.symlink_to(self.base / "absent")
        self.compare(False, path=link / "tail")
        fifo = self.base / "fifo"
        os.mkfifo(fifo)
        self.compare(False, path=fifo)

    def test_modes_readonly_and_ancestor(self):
        self.leaf.chmod(0o666)
        self.compare(False)
        self.leaf.chmod(0o400)
        self.compare(False)
        self.compare(True, readonly=1)
        self.leaf.chmod(0)
        self.compare(False, readonly=1)
        self.leaf.chmod(0o600)
        self.leaf.parent.chmod(0o777)
        self.compare(False, boundary=self.leaf)
        self.leaf.parent.chmod(0o1777)
        for source in self.sources:
            out, err, rc = self.run_guard(source, boundary=self.leaf)
            allowed = os.getuid() == 0 and (
                source == self.sources[1] or platform.system() != "Darwin")
            self.assertEqual(rc == 0, allowed, (out, err))
        # Even a sticky root-owned path is unsafe INSIDE the boundary.
        self.compare(False)
        self.leaf.parent.chmod(0o700)

    def test_synthetic_owner(self):
        # No chown/privilege requirement: both guards see the same false UID.
        self.compare(False, hook="G_UID=4294967294")

    def test_native_shared_system_ancestor(self):
        directory = "/private/tmp" if platform.system() == "Darwin" else "/tmp"
        with tempfile.TemporaryDirectory(prefix="dom-sticky-", dir=directory) as tmp:
            p = Path(tmp).resolve()
            info = Path(directory).stat()
            safe = (info.st_uid in (0, os.getuid())
                    and (not info.st_mode & 0o022
                         or (info.st_uid == 0 and bool(info.st_mode & 0o1000))))
            if platform.system() == "Darwin":
                # Real host metadata, never chmod/chown the shared ancestor.
                self.assertEqual(info.st_uid, 0)
                self.assertTrue(info.st_mode & 0o1000)
                self.assertTrue(info.st_mode & 0o022)
                self.assertTrue(safe)
            for source in self.sources:
                out, err, rc = self.run_guard(source, path=p / "missing", boundary=p)
                legacy_bug = (source == self.sources[0]
                              and platform.system() == "Darwin"
                              and bool(info.st_mode & 0o022))
                self.assertEqual(rc == 0, safe and not legacy_bug, (out, err))
                if legacy_bug:
                    self.assertIn("unsafe writable ancestor", err)
            self.compare(False, path=p / "missing", boundary=directory)

    def test_special_bit_metadata_changes(self):
        # Only special bits change: ordinary permission/type checks still pass.
        for bit in (0o1000, 0o2000, 0o4000):
            with self.subTest(bit=oct(bit)):
                self.leaf.parent.chmod(0o700)
                err = self.fault('native_stat "$@"; chmod %o "$TARGET"' % (bit | 0o700),
                                 path=self.leaf.parent)
                self.assertIn("changed path metadata", err)
                self.assertEqual(self.leaf.parent.stat().st_mode & 0o7777, bit | 0o700)
        self.leaf.parent.chmod(0o700)

    def test_immutable_baseline_fails_closed(self):
        current = preview_fixture.source().decode()
        original = oracle.FIXTURE.read_text()
        # No Git invocation: this exact helper-only delta works in shallow trees.
        old = oracle.baseline(current)
        start, end = current.index(oracle.START), current.index(oracle.END)
        self.assertEqual(old[:old.index(oracle.START)], current[:start].replace(
            oracle.EMISSION, "global_stat global_path"))
        self.assertEqual(old[old.index(oracle.END):], current[end:])
        for bad in ("", original.replace("%Lp", "%Mp%03Lp")):
            with mock.patch.object(Path, "read_text", return_value=bad):
                with self.assertRaises(ValueError):
                    oracle.baseline(current)
        with mock.patch.object(Path, "read_text", side_effect=FileNotFoundError):
            with self.assertRaises(FileNotFoundError):
                oracle.baseline(current)
        with self.assertRaises(ValueError):
            oracle.baseline(current.replace(oracle.EMISSION, "missing"))

    def test_missing_readonly_parent(self):
        self.leaf.parent.chmod(0o500)
        try:
            self.compare(True, path=self.leaf.parent / "absent",
                         boundary=self.base, readonly=1)
            self.compare(False, path=self.leaf.parent / "absent")
        finally:
            self.leaf.parent.chmod(0o700)

    def test_deep_byte_and_count_boundaries(self):
        p = self.base
        # >32 ancestors and >8192 cumulative argv bytes, <Darwin PATH_MAX.
        for i in range(70):
            p = p / ("d%02dxxxx" % i)
            p.mkdir()
        self.compare(True, path=p)
        self.compare(True, path=p / "missing" / "tail")
        hook = self.native + '''
global_stat() {
  local bytes=0 item
  for item in "$@"; do bytes=$((bytes + ${#item} + 1)); done
  printf 'BATCH %s %s\\n' "$#" "$bytes" >&2
  native_stat "$@"
}
'''
        out, err, rc = self.run_guard(self.sources[1], path=p, hook=hook)
        self.assertEqual(rc, 0, (out, err))
        batches = [tuple(map(int, line.split()[1:])) for line in err.splitlines()]
        self.assertGreater(len(batches), 2)
        self.assertEqual(batches[:len(batches) // 2], batches[len(batches) // 2:])
        self.assertTrue(all(1 <= count <= 32 and size <= 8192
                            for count, size in batches))
        self.assertGreater(max(count for count, _ in batches), 1)
        p.chmod(0o777)
        self.compare(False, path=p)
        p.chmod(0o700)

    def test_command_failures(self):
        self.fault("native_stat \"$@\"; return 1")
        self.fault("return 1")
        self.compare(False, hook="uname() { return 1; }; stat() { return 1; }")
        out, err, rc = self.run_guard(self.sources[1], hook="uname() { return 1; }")
        self.assertNotEqual(rc, 0, (out, err))

    def test_malformed_partial_and_association(self):
        for body in (
            'native_stat "$@"; printf "\\n"',
            'native_stat "$@"; native_stat "$1"',
            'native_stat "$1"',
            'printf "0 888 1 1 %s\\n" "$1"',
            'printf "0 77777 1 1 %s\\n" "$1"',
            'printf "x 700 1 1 %s\\n" "$1"',
            'printf "0 700 1 1 %s" "$1"',
            'native_stat "$@" | sed "s/ /x /" | tr x "\\000"',
            'local p; for p in "$@"; do native_stat "$p"; done | sed "s| /| /wrong/|"',
            'local i; local -a reverse; reverse=("$@"); '
            'for ((i=${#reverse[@]}-1; i>=0; i--)); do native_stat "${reverse[i]}"; done',
        ):
            with self.subTest(body=body):
                self.fault(body)

    def test_mutation_during_batch(self):
        # Actual isolated filesystem mutations, after the first real stat.
        self.fault('native_stat "$@"; chmod 666 "$TARGET"')

    def test_mutation_inventory(self):
        # Hook references a fixed fixture path, not a possibly shared ancestor.
        self.fault('native_stat "$@"; mkdir -p "$TARGET"',
                   path=self.base / "absent" / "tail",
                   tail="")

    def test_mutation_identity_and_symlink(self):
        self.fault('native_stat "$@"; if [ ! -e "$TARGET.old" ]; then '
                   'mv "$TARGET" "$TARGET.old"; cp "$TARGET.old" "$TARGET"; fi')
        self.leaf.unlink()
        self.leaf.write_text("data")
        self.fault('native_stat "$@"; if [ ! -L "$TARGET" ]; then '
                   'rm "$TARGET"; ln -s "$TARGET.old" "$TARGET"; fi')

    def test_fresh_validation(self):
        # A second call must not reuse prior safe metadata.
        for source in self.sources:
            out, err, rc = self.run_guard(
                source, tail='chmod 666 "$2"; global_path "$2" "$3"')
            self.assertNotEqual(rc, 0, (out, err))
            self.leaf.chmod(0o600)

    def test_synthetic_other_stat_dialect(self):
        if platform.system() != "Darwin":
            self.skipTest("GNU native host; BSD translation not available")
        # GNU flag/format dispatch and path serialization via native BSD stat.
        hook = '''
uname() { printf 'Linux\\n'; }
stat() {
  [ "$1" = -c ] && [ "$2" = '%u %a %d %i %n' ] && [ "$3" = -- ] || return 1
  shift 3
  /usr/bin/stat -f '%u %Mp%03Lp %d %i %N' "$@"
}
'''
        out, err, rc = self.run_guard(self.sources[1], hook=hook)
        self.assertEqual(rc, 0, (out, err))


if __name__ == "__main__":
    unittest.main()
