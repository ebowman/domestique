"""Small offline installed-CLI cohort; no native, DB, historical fixture or network."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "preview"))
import project as P
from native import DEFINITIONS, LEAVES, templates
from project_data import RECEIPT, PATHS


def snapshot(root):
    result = {}
    for path in sorted(root.rglob("*")):
        info = path.lstat()
        result[str(path.relative_to(root))] = (
            stat.S_IMODE(info.st_mode),
            os.readlink(path) if path.is_symlink() else
            hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None)
    return result


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


class PreviewProjectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="domestique preview projects ", dir="/private/tmp")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.base = Path(cls.temp.name)
        cls.home = cls.base / "HOME ' $literal;"
        cls.home.mkdir()
        (cls.home / ".zshrc").write_bytes(b"host startup untouched\n")
        cls.env = {k: v for k, v in os.environ.items()
                   if not k.startswith(("GIT_", "XDG_", "DOMESTIQUE_", "PYTHON"))
                   and k not in ("BASH_ENV", "ENV", "PWD")}
        cls.env.update(HOME=str(cls.home), XDG_DATA_HOME=str(cls.home / "data"),
                       GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
                       GIT_CONFIG_SYSTEM=os.devnull, GIT_OPTIONAL_LOCKS="0",
                       GIT_TERMINAL_PROMPT="0", LC_ALL="C")
        cls.source = cls.base / "trusted local source"
        cls.repo(cls.source)
        shutil.copytree(ROOT / "preview", cls.source / "preview")
        shutil.copyfile(ROOT / "install-v2.sh", cls.source / "install-v2.sh")
        cls.git(cls.source, "add", ".")
        cls.git(cls.source, "commit", "-m", "project runtime fixture")
        cls.first = cls.git(cls.source, "rev-parse", "HEAD").strip()
        # An update of immutable source, including changed factory text, must not
        # rebaseline or overwrite local wrappers.
        native = cls.source / "preview/native.py"
        native.write_text(native.read_text().replace("Load the shared", "Load the updated shared"))
        cls.git(cls.source, "add", ".")
        cls.git(cls.source, "commit", "-m", "shared template update fixture")
        cls.second = cls.git(cls.source, "rev-parse", "HEAD").strip()
        (cls.source / ".beads").mkdir()
        (cls.source / ".beads/user-managed-sentinel").write_bytes(b"not a database; never opened by CLI\n")
        cls.machine_root = cls.home / "data/domestique-preview"
        cls.launcher = cls.home / ".local/bin/domestique2"
        cls.run_raw(["bash", "-p", ROOT / "install-v2.sh", "--source", cls.source,
                     "--ref", cls.first], cls.source)
        cls.protected_source = snapshot(cls.source)
        print("COHORT " + json.dumps({"fixture": str(cls.base), "first": cls.first,
                                      "second": cls.second,
                                      "source_sha256": fingerprint(cls.protected_source)}), flush=True)

    @classmethod
    def run_raw(cls, argv, cwd, code=0):
        start = time.monotonic()
        proc = subprocess.run([str(a) for a in argv], cwd=cwd, env=cls.env,
                              capture_output=True, text=True, timeout=30)
        print("COMMAND " + json.dumps({"argv": [str(a) for a in argv], "cwd": str(cwd),
                                       "exit": proc.returncode,
                                       "seconds": round(time.monotonic() - start, 3),
                                       "stdout": proc.stdout, "stderr": proc.stderr}), flush=True)
        if proc.returncode != code:
            raise AssertionError((argv, code, proc.returncode, proc.stdout, proc.stderr))
        return proc.stdout + proc.stderr

    @classmethod
    def git(cls, root, *args):
        return cls.run_raw(["git", "--no-pager", "-c", "core.hooksPath=/dev/null",
                            "-c", "protocol.allow=never", "-C", root, *args], cls.base)

    @classmethod
    def repo(cls, root):
        root.mkdir()
        cls.git(root, "init", "--template=")
        # --template= intentionally omits even ordinary info/. Supply host Git
        # administration in fixtures; project enable must never repair it.
        (root / ".git/info").mkdir()
        (root / ".git/info/exclude").write_bytes(b"# host excludes\n")
        cls.git(root, "config", "user.name", "Local Fixture")
        cls.git(root, "config", "user.email", "fixture@example.invalid")
        (root / "host.txt").write_text("host tracked bytes\n")
        cls.git(root, "add", "host.txt")
        cls.git(root, "commit", "-m", "host fixture")

    def setUp(self):
        self.area = self.base / self._testMethodName
        self.area.mkdir()
        self.a = self.area / "A ' quotes $literal; project"
        self.b = self.area / "B untouched"
        self.repo(self.a)
        self.repo(self.b)
        (self.a / ".beads").mkdir()
        (self.a / ".beads/user-note").write_text("user-managed project bytes\n")
        self.host = snapshot(self.home)
        self.untouched_b = snapshot(self.b)

    def tearDown(self):
        after = snapshot(self.source)
        self.assertEqual(after, self.protected_source, "source/.beads changed")
        self.assertEqual(snapshot(self.home), self.host, "project operation changed HOME/core")
        self.assertEqual(snapshot(self.b), self.untouched_b, "B changed without selection")
        print("PROTECTED " + json.dumps({
            "test": self._testMethodName,
            "source_before": fingerprint(self.protected_source), "source_after": fingerprint(after),
            "home_before": fingerprint(self.host), "home_after": fingerprint(snapshot(self.home)),
            "B_before": fingerprint(self.untouched_b), "B_after": fingerprint(snapshot(self.b)),
        }), flush=True)

    def command(self, *args, code=0, cwd=None):
        return self.run_raw([self.launcher, *args], cwd or self.a, code)

    def receipt(self, root=None):
        return json.loads(((root or self.a) / RECEIPT).read_bytes())

    def unchanged_call(self, *args, code=0, cwd=None):
        before = snapshot(self.area), snapshot(self.home), snapshot(self.source)
        result = self.command(*args, code=code, cwd=cwd)
        self.assertEqual((snapshot(self.area), snapshot(self.home), snapshot(self.source)), before)
        return result

    def test_lifecycle_and_loader_contract(self):
        # Existing host containers/files and matching ignore lines are unowned.
        (self.a / ".github").mkdir()
        (self.a / ".github/host.md").write_bytes(b"host native metadata\n")
        (self.a / ".domestique-private").mkdir()
        (self.a / ".domestique-private/host-note").write_bytes(b"unrelated private note\n")
        exclude = self.a / ".git/info/exclude"
        host_exclude = (b"# other owner\n/" + next(iter(LEAVES.values())).encode() +
                        b"\n# host bytes without final newline")
        exclude.write_bytes(host_exclude)
        exclude.chmod(0o640)
        before = snapshot(self.a)
        self.unchanged_call("enable", "--dry-run")
        self.assertIn("NOT READY", self.command("enable"))  # Default cwd is exact root.
        record = self.receipt()
        self.assertEqual(record["state"], "active")
        self.assertEqual(set(record["files"]), set(LEAVES.values()))
        expected_files = set(PATHS) | {".git/info/exclude"}
        after = snapshot(self.a)
        changed_files = {n for n, v in after.items() if v[1] is not None and before.get(n) != v}
        self.assertEqual(changed_files, expected_files)
        self.assertEqual(after[".git/info/exclude"][0], 0o640)
        self.assertTrue(exclude.read_bytes().startswith(host_exclude + b"\n"))
        self.unchanged_call("enable", self.a)
        self.unchanged_call("enable", self.a, "--dry-run")
        self.unchanged_call("disable", self.a, "--dry-run")
        for kind, leaf in LEAVES.items():
            data = (self.a / leaf).read_text()
            front, body = data[4:].split("---\n", 1)
            name, description = DEFINITIONS[kind]
            expected = f"name: {name}\ndescription: {description}\n"
            if kind == "goal":
                expected += "disable-model-invocation: true\n"
                self.assertIn("explicit Domestique goal request naming an epic", body)
                self.assertIn("Native goal/autopilot", body)
            self.assertEqual(front, expected)  # No models/tools/MCP/default grants.
            command = body.split("```sh\n")[1].split("\n```")[0]
            self.assertEqual(shlex.split(command),
                             [str(self.launcher), "workflow", kind, "--project", str(self.a)])
            if kind in ("implementer", "reviewer"):
                self.assertIn("await the caller", body)
                self.assertIn("or run this locator autonomously", body)
            baseline = snapshot(self.area), snapshot(self.home)
            self.assertIn("forthcoming hq-iyu.4", self.run_raw(
                ["bash", "-p", "-c", command], self.b, 1))
            self.assertEqual((snapshot(self.area), snapshot(self.home)), baseline)
        # Common ignores affect discovery in Git, not project activation.
        self.assertEqual(len(self.git(self.a, "check-ignore", *PATHS).splitlines()), 6)
        self.command("disable")
        self.assertEqual(snapshot(self.a), before)
        self.unchanged_call("disable")
        self.command("enable", self.a)
        self.command("disable", self.a)
        self.assertEqual(snapshot(self.a), before, "re-enable cleanup is coherent")
        # Explicit selection of B, using the same installed runtime.
        b_before = snapshot(self.b)
        self.command("enable", self.b)
        self.assertEqual(self.receipt(self.b)["project"]["root"], str(self.b))
        self.command("disable", self.b)
        self.assertEqual(snapshot(self.b), b_before)

    def test_z_customized_partial_and_source_update(self):
        self.command("enable", self.a)
        receipt = self.receipt()
        role = self.a / LEAVES["implementer"]
        # Arbitrary user bytes (including malformed metadata) are opaque.
        role.write_bytes(b"---\nname: user override\nmodel: [unparsed\n---\n$local body ' edits\n\xff")
        edited = role.read_bytes()
        self.assertIn("customized", self.unchanged_call("enable", self.a))
        self.command("update", "--ref", self.second)
        self.host = snapshot(self.home)  # Only this explicit machine update may change it.
        self.assertIn("customized", self.unchanged_call("enable", self.a))
        self.assertEqual(self.receipt(), receipt, "creation hashes never advance after update")
        self.assertEqual(role.read_bytes(), edited)
        self.unchanged_call("disable", self.a, "--dry-run", code=1)
        self.assertIn("receipt revoked", self.command("disable", self.a, code=1))
        self.assertEqual(role.read_bytes(), edited)
        self.assertEqual(self.receipt()["state"], "disabled")
        self.assertEqual(self.receipt()["files"], receipt["files"])
        self.assertFalse((self.a / LEAVES["reviewer"]).exists())
        self.unchanged_call("enable", self.a, code=1)
        partial = self.command("disable", self.a, code=1)
        self.assertIn("customized", partial)
        self.assertEqual(role.read_bytes(), edited)
        role.unlink()  # Explicit fixture-owner cleanup of the retained local edit.
        self.command("disable", self.a)
        self.command("enable", self.a)
        self.command("disable", self.a)

    def test_collisions_and_exact_grammar(self):
        leaf = self.a / LEAVES["implementer"]
        leaf.parent.mkdir(parents=True)
        for collision in ("identical", "tracked", "index-only", "hardlink", "directory"):
            with self.subTest(collision=collision):
                leaf.write_bytes(templates(self.launcher, self.a)[LEAVES["implementer"]])
                if collision in ("tracked", "index-only"):
                    self.git(self.a, "add", "--", LEAVES["implementer"])
                    if collision == "index-only":
                        leaf.unlink()
                elif collision == "hardlink":
                    os.link(leaf, self.area / "held hardlink")
                elif collision == "directory":
                    leaf.unlink()
                    leaf.mkdir()
                self.unchanged_call("enable", self.a, code=1)
                self.unchanged_call("enable", self.a, "--dry-run", code=1)
                if collision in ("tracked", "index-only"):
                    self.git(self.a, "rm", "--cached", "--", LEAVES["implementer"])
                if collision == "hardlink":
                    (self.area / "held hardlink").unlink()
                if leaf.is_dir():
                    leaf.rmdir()
                elif leaf.exists():
                    leaf.unlink()
        for args in (("enable", "--platform", "copilot"), ("enable", "", "--dry-run"),
                     ("enable", "--dry-run", self.a), ("disable", "--dry-run", "--dry-run"),
                     ("enable", self.a, "extra"), ("workflow", "goal"),
                     ("workflow", "goal", "--project", "relative")):
            self.unchanged_call(*args, code=2)
        legacy = self.a / ".domestique-private"
        legacy.mkdir()
        for anchor in ("manifest", "v2"):
            path = legacy / anchor
            path.write_bytes(b"foreign legacy authority\n")
            self.unchanged_call("enable", self.a, code=1)
            path.unlink()
        policy = self.a / "CLAUDE.local.md"
        policy.write_text("# Domestique existing v1 policy\n")
        self.unchanged_call("enable", self.a, code=1)

    def test_unsafe_targets_and_receipts(self):
        sub = self.a / "subdirectory"
        sub.mkdir()
        alias = self.area / "alias"
        alias.symlink_to(self.a, target_is_directory=True)
        bare = self.area / "bare"
        self.git(self.a, "init", "--bare", "--template=", bare)
        for target in (sub, alias, self.area, bare):
            self.unchanged_call("enable", target, code=1)
        self.unchanged_call("enable", cwd=sub, code=1)
        github = self.a / ".github"
        github.symlink_to(self.b)
        self.unchanged_call("enable", self.a, code=1)
        github.unlink()
        github.mkdir()
        for mode in (0o500, 0o777):
            github.chmod(mode)
            try:
                self.unchanged_call("enable", self.a, code=1)
            finally:
                github.chmod(0o700)
        info = self.a / ".git/info"
        held = self.a / ".git/held-info"
        info.rename(held)
        self.unchanged_call("enable", self.a, code=1)
        held.rename(info)
        exclude = info / "exclude"
        exclude.chmod(0o400)
        self.unchanged_call("enable", self.a, code=1)
        exclude.chmod(0o600)
        self.command("enable", self.a)
        record = self.receipt()
        receipt_path = self.a / RECEIPT
        record["files"]["../outside"] = next(iter(record["files"].values()))
        receipt_path.write_text(json.dumps(record))
        self.unchanged_call("disable", self.a, code=1)
        del record["files"]["../outside"]
        receipt_path.write_text(json.dumps(record))
        moved = self.area / "moved project"
        self.a.rename(moved)
        self.unchanged_call("enable", moved, cwd=moved, code=1)
        moved.rename(self.a)
        copied = self.area / "copied project"
        shutil.copytree(self.a, copied)
        self.unchanged_call("disable", copied, code=1)
        # A now-tracked owned definition is retained, but others can be disabled.
        self.git(self.a, "add", "-f", "--", LEAVES["reviewer"])
        self.command("disable", self.a, code=1)
        self.assertEqual(self.receipt()["state"], "disabled")
        self.assertTrue((self.a / LEAVES["reviewer"]).exists())

    def test_linked_common_exclusion_attribution(self):
        linked = self.area / "linked ' $worktree;"
        self.git(self.a, "worktree", "add", "--detach", linked)
        self.command("enable", linked)
        record = self.receipt(linked)
        self.assertNotEqual(record["project"]["git_dir"], record["project"]["common_dir"])
        self.assertEqual(record["project"]["common_dir"], str(self.a / ".git"))
        self.assertFalse((self.a / RECEIPT).exists())
        self.unchanged_call("enable", self.a, code=1)
        self.unchanged_call("disable", self.a, code=1)
        self.assertEqual(len(self.git(self.a, "check-ignore", *PATHS).splitlines()), 6)
        exclude = self.a / ".git/info/exclude"
        original = exclude.read_bytes()
        for kind in ("duplicate", "edited", "foreign"):
            with self.subTest(kind=kind):
                if kind == "duplicate":
                    exclude.write_bytes(original + record["exclusion"]["block"].encode())
                elif kind == "edited":
                    exclude.write_bytes(original.replace(b"/.github/skills/", b"/.github/altered/", 1))
                else:
                    exclude.write_bytes(original + b"# domestique-copilot-preview BEGIN foreign\n")
                self.unchanged_call("enable", linked, code=1)
                self.unchanged_call("disable", linked, "--dry-run", code=1)
                exclude.write_bytes(original)
        exclude.write_bytes(original + b"# domestique-copilot-preview BEGIN foreign\n")
        ambiguous = exclude.read_bytes()
        self.command("disable", linked, code=1)
        self.assertEqual(self.receipt(linked)["state"], "disabled")
        self.assertEqual(exclude.read_bytes(), ambiguous, "ambiguous common block must remain")
        exclude.write_bytes(original)  # Cooperative fixture owner resolves ambiguity.
        self.command("disable", linked)
        self.command("enable", self.a)
        self.command("disable", self.a)
        self.git(self.a, "worktree", "remove", linked)

    def test_ordinary_write_failure_is_partial(self):
        from machine import read_json
        real_open = Path.open

        def fail_open(path, *args, **kwargs):
            if path == self.a / LEAVES["goal"] and args == ("xb",):
                raise OSError("ordinary fixture write failure")
            return real_open(path, *args, **kwargs)

        with patch.dict(os.environ, self.env, clear=True), patch.object(Path, "open", fail_open):
            receipt = read_json(self.machine_root / "receipt.json")
            code, message = P.operate("enable", str(self.a), False, self.machine_root, receipt)
        self.assertEqual(code, 1)
        self.assertIn("PARTIAL", message)
        record = self.receipt()
        self.assertEqual(record["state"], "partial-enable")
        self.assertEqual(len(record["files"]), 2)
        self.unchanged_call("enable", self.a, code=1)
        self.command("disable", self.a)
        self.unchanged_call("disable", self.a)


if __name__ == "__main__":
    unittest.main(verbosity=2)
