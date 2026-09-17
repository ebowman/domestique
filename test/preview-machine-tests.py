"""Bounded offline preview lifecycle; no historical fixture/runtime imports."""
import hashlib
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from preview import machine as M


def snapshot(root):
    result = {}
    for path in sorted(root.rglob("*")):
        relative = str(path.relative_to(root))
        info = path.lstat()
        content = (os.readlink(path) if path.is_symlink() else
                   hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None)
        result[relative] = (stat.S_IMODE(info.st_mode), content)
    return result


class PreviewMachineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="domestique preview ", dir="/private/tmp")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.base = Path(cls.temp.name)
        cls.source = cls.base / "trusted source ' $literal; checkout"
        cls.source.mkdir()
        cls.env = {k: v for k, v in os.environ.items()
                   if not k.startswith(("GIT_", "XDG_", "DOMESTIQUE_", "PYTHON"))
                   and k not in ("BASH_ENV", "ENV")}
        cls.env.update(HOME=str(cls.base), GIT_CONFIG_GLOBAL=os.devnull,
                       GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_SYSTEM=os.devnull,
                       GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0")

        def git(*args):
            return subprocess.check_output(
                ["git", "-c", "core.hooksPath=/dev/null", "-C", str(cls.source), *args],
                env=cls.env, stderr=subprocess.PIPE).decode().strip()

        cls.fixture_git = staticmethod(git)
        git("init", "--template=")
        git("config", "user.name", "Local Fixture")
        git("config", "user.email", "fixture@example.invalid")
        shutil.copytree(ROOT / "preview", cls.source / "preview",
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(ROOT / "install-v2.sh", cls.source / "install-v2.sh")
        git("add", ".")
        git("commit", "-m", "first preview runtime")
        cls.first = git("rev-parse", "HEAD")
        git("tag", "literal;$value", cls.first)
        cli = cls.source / "preview/cli.py"
        cli.write_text(cli.read_text().replace(
            "        ref = None\n",
            '        if args == ["fixture-behavior"]:\n'
            '            print((Path(__file__).parent / "message.txt").read_text().strip().upper())\n'
            '            return 0\n'
            "        ref = None\n"))
        (cls.source / "preview/message.txt").write_text("second runtime computes this\n")
        git("add", ".")
        git("commit", "-m", "second preview adds actual command behavior")
        cls.second = git("rev-parse", "HEAD")
        cli.unlink()
        git("add", ".")
        git("commit", "-m", "unusable candidate missing CLI")
        cls.broken = git("rev-parse", "HEAD")
        git("checkout", "--detach", cls.second)
        # Deliberately uncommitted: must never become selected revision content.
        cli.write_text("raise AssertionError('uncommitted source executed')\n")
        cls.template = cls.base / "ambient template"
        hooks = cls.template / "hooks"
        hooks.mkdir(parents=True)
        marker = cls.base / "HOOK-RAN"
        for name in ("post-checkout", "post-merge", "pre-auto-gc"):
            hook = hooks / name
            hook.write_text("#!/bin/bash\n/bin/touch " + str(marker).replace(" ", "\\ ") + "\nexit 91\n")
            hook.chmod(0o700)
        shutil.copytree(hooks, cls.source / ".git/hooks")
        cls.protected = snapshot(cls.source)

    def setUp(self):
        self.home = self.base / (self._testMethodName + " home ' $literal;")
        self.home.mkdir()
        self.env = dict(type(self).env, HOME=str(self.home),
                        XDG_DATA_HOME=str(self.home / "data with spaces ' $data;"),
                        GIT_DIR=str(self.source / ".git"),
                        GIT_WORK_TREE=str(self.source),
                        GIT_INDEX_FILE=str(self.source / ".git/index"),
                        GIT_TEMPLATE_DIR=str(self.template),
                        GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="core.hooksPath",
                        GIT_CONFIG_VALUE_0=str(self.template / "hooks"))
        self.root = Path(self.env["XDG_DATA_HOME"]) / "domestique-preview"
        self.launcher = self.home / ".local/bin/domestique2"

    def tearDown(self):
        self.assertEqual(snapshot(self.source), self.protected, "source project/index/config/hooks changed")
        self.assertFalse((self.base / "HOOK-RAN").exists())
        for name in (".github", ".agents", ".claude", ".beads", ".domestique-private"):
            self.assertFalse(list(self.home.rglob(name)), f"unexpected native/project/DB path: {name}")

    def run_command(self, args, code=0):
        proc = subprocess.run([str(arg) for arg in args], cwd=self.source, env=self.env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
        self.assertEqual(proc.returncode, code, (args, proc.stdout, proc.stderr))
        return proc.stdout + proc.stderr

    def install(self, ref=None, code=0):
        return self.run_command(["/bin/bash", "-p", ROOT / "install-v2.sh",
                                 "--source", self.source, "--ref", ref or self.first], code)

    def command(self, *args, code=0):
        return self.run_command([self.launcher, *args], code)

    def test_lifecycle_and_prepare_failures(self):
        # Legitimate host bin contents and startup bytes must survive untouched.
        self.launcher.parent.mkdir(parents=True)
        other = self.launcher.parent / "other-command"
        other.write_text("host command\n")
        startup = self.home / ".zshrc"
        startup.write_text("host aliases stay here\n")
        self.assertIn(self.first, self.install("literal;$value"))
        with patch.dict(os.environ, self.env, clear=True):
            old = M.resolve_source(self.root)
        self.assertEqual(old, self.root / "releases" / self.first)
        self.assertFalse((old / ".git/objects/info/alternates").exists())
        self.assertIn(self.first, self.command("version"))
        self.assertIn(self.first, self.command("--version"))
        for args in ((), ("help",), ("--help",)):
            self.assertIn("NOT READY", self.command(*args))
        self.command("fixture-behavior", code=2)
        before = snapshot(self.home)
        self.assertIn("unchanged", self.install(self.first))
        self.assertIn("unchanged", self.command("update", "--ref", "literal;$value"))
        self.assertEqual(snapshot(self.home), before, "same commit and read-only commands write nothing")

        for ref in ("missing-ref", self.broken, "literal;$(not-a-command)"):
            self.command("update", "--ref", ref, code=1)
            self.assertEqual(snapshot(self.home), before)
            self.assertIn(self.first, self.command("version"))

        # Ordinary mid-checkout failure: only our temporary directory is cleaned.
        real_git = M.git
        def fail_checkout(path, *args):
            if args[0] == "checkout":
                raise OSError("fixture preparation I/O failure")
            return real_git(path, *args)
        with patch.dict(os.environ, self.env, clear=True):
            receipt = M.check_install(self.root, old)
            with patch.object(M, "git", side_effect=fail_checkout):
                with self.assertRaisesRegex(OSError, "preparation I/O"):
                    M.update(self.root, old, receipt, self.second)
        self.assertEqual(snapshot(self.home), before)

        tracked = old / "preview/__init__.py"
        original = tracked.read_bytes()
        tracked.write_bytes(original + b"\n# local edit\n")
        dirty = snapshot(self.home)
        self.assertIn("dirty managed", self.command("update", "--ref", self.second, code=1))
        self.assertEqual(snapshot(self.home), dirty)
        tracked.write_bytes(original)
        foreign = self.root / "releases" / self.second
        foreign.mkdir()
        collision = snapshot(self.home)
        self.command("update", "--ref", self.second, code=1)
        self.assertEqual(snapshot(self.home), collision)
        foreign.rmdir()
        foreign.symlink_to(self.source)
        collision = snapshot(self.home)
        self.command("update", "--ref", self.second, code=1)
        self.assertEqual(snapshot(self.home), collision)
        foreign.unlink()
        self.root.chmod(0o500)
        try:
            unwritable = snapshot(self.home)
            self.command("update", "--ref", self.second, code=1)
            self.assertEqual(snapshot(self.home), unwritable)
        finally:
            self.root.chmod(0o700)
        unknown = self.root / "unknown"
        unknown.write_text("do not adopt\n")
        collision = snapshot(self.home)
        self.command("update", "--ref", self.second, code=1)
        self.assertEqual(snapshot(self.home), collision)
        unknown.unlink()
        launcher_bytes = self.launcher.read_bytes()
        held = self.home / "held launcher"
        self.launcher.rename(held)
        shutil.copyfile(held, self.launcher)
        self.launcher.chmod(0o700)
        collision = snapshot(self.home)
        self.command("update", "--ref", self.second, code=1)
        self.assertEqual(snapshot(self.home), collision, "identical unowned launcher was adopted")
        self.launcher.unlink()
        held.rename(self.launcher)

        self.assertIn(self.second, self.command("update", "--ref", self.second))
        self.assertEqual(self.launcher.read_bytes(), launcher_bytes, "update rewrote the dispatcher")
        self.assertIn(self.second, self.command("version"))
        self.assertEqual(self.command("fixture-behavior").strip(), "SECOND RUNTIME COMPUTES THIS")
        self.assertIn(self.first, self.run_command(
            [sys.executable, "-I", "-S", "-B", old / "preview/cli.py", "version"]))
        self.run_command([sys.executable, "-I", "-S", "-B", old / "preview/cli.py",
                          "fixture-behavior"], 2)
        self.assertTrue(old.is_dir())
        before = snapshot(self.home)
        self.assertIn("unchanged", self.command("update", "--ref", self.second))
        self.assertEqual(snapshot(self.home), before)

        # Source disappears; installed content remains complete and offline.
        moved = self.base / "temporarily moved source"
        self.source.rename(moved)
        try:
            def offline(*args, code=0):
                proc = subprocess.run([str(self.launcher), *args], cwd=self.home, env=self.env,
                                      capture_output=True, text=True, timeout=30)
                self.assertEqual(proc.returncode, code, proc.stderr)
                return proc.stdout + proc.stderr
            self.assertIn(self.second, offline("--version"))
            self.assertIn("Usage", offline("--help"))
            self.assertIn("SECOND RUNTIME", offline("fixture-behavior"))
            self.assertIn("source is missing", offline("update", "--ref", self.first, code=1))
            self.assertEqual(snapshot(self.home), before)
        finally:
            moved.rename(self.source)
        self.assertEqual(other.read_text(), "host command\n")
        self.assertEqual(startup.read_text(), "host aliases stay here\n")

    def test_exact_grammar_before_effects(self):
        before = snapshot(self.home)
        invalid = ([], ["--source", str(self.source)], ["--ref", self.first],
                   ["--source", str(self.source), "--ref", ""],
                   ["--source", str(self.source), "--source", str(self.source)],
                   ["--ref", self.first, "--source", str(self.source), "--force"],
                   ["--help", "--ref", self.first], ["--version", "2.0.0"])
        for args in invalid:
            self.run_command(["/bin/bash", "-p", ROOT / "install-v2.sh", *args], 2)
            self.assertEqual(snapshot(self.home), before)
        self.run_command(["/bin/bash", "-p", ROOT / "install-v2.sh", "--help"])
        self.assertEqual(snapshot(self.home), before)
        self.install()
        before = snapshot(self.home)
        for args in (("update",), ("update", "--ref", ""), ("update", "--ref", self.second, "--force"),
                     ("version", "extra"), ("--help", "extra"), ("unknown",),
                     ("inspect", "one", "two"), ("enable", "--force")):
            self.command(*args, code=2)
            self.assertEqual(snapshot(self.home), before)
        for name in ("inspect", "--inspect"):
            self.assertIn("unavailable", self.command(name, "literal ' $target; with spaces", code=1))
            self.assertEqual(snapshot(self.home), before)
        for name in ("enable", "disable"):
            self.assertIn("refused", self.command(name, "literal ' $target; with spaces", code=1))
            self.assertEqual(snapshot(self.home), before)

    def test_fresh_collisions_and_unsafe_parents(self):
        self.launcher.parent.mkdir(parents=True)
        self.launcher.write_text("ABI2/3 or any unknown command\n")
        before = snapshot(self.home)
        self.install(code=1)
        self.assertEqual(snapshot(self.home), before)
        self.launcher.unlink()
        self.launcher.symlink_to(self.home / "absent")
        before = snapshot(self.home)
        self.install(code=1)
        self.assertEqual(snapshot(self.home), before)
        self.launcher.unlink()
        legacy = self.home / ".local/state/domestique/v2"
        legacy.mkdir(parents=True)
        before = snapshot(self.home)
        self.install(code=1)
        self.assertEqual(snapshot(self.home), before)
        legacy.rmdir()
        self.root.parent.mkdir()
        self.root.mkdir()
        before = snapshot(self.home)
        self.install(code=1)
        self.assertEqual(snapshot(self.home), before)
        self.root.rmdir()
        self.root.symlink_to(self.home / "absent")
        before = snapshot(self.home)
        self.install(code=1)
        self.assertEqual(snapshot(self.home), before)
        self.root.unlink()
        for mode in (0o500, 0o777):
            self.launcher.parent.chmod(mode)
            try:
                before = snapshot(self.home)
                self.install(code=1)
                self.assertEqual(snapshot(self.home), before)
            finally:
                self.launcher.parent.chmod(0o700)
        before = snapshot(self.home)
        self.install(self.broken, code=1)
        self.install("no-such-ref", code=1)
        self.assertEqual(snapshot(self.home), before)
        # A machine root inside a project is refused before any project writes.
        self.env["XDG_DATA_HOME"] = str(self.source / "unowned data")
        self.install(code=1)

    def test_default_data_home(self):
        del self.env["XDG_DATA_HOME"]
        self.run_command([ROOT / "install-v2.sh", "--ref", self.first,
                          "--source", self.source])
        self.assertTrue((self.home / ".local/share/domestique-preview/current").is_symlink())
        self.assertIn(self.first, self.command("version"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
