"""Installed-runtime + fake-argv/policy tests. NOT actual native lifecycle proof."""
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "preview"))
from native import DEFINITIONS, LEAVES
from project_data import RECEIPT

# Reuse only the existing installed-cohort Git/argv/snapshot helpers, not its tests.
spec = importlib.util.spec_from_file_location("project_fixtures", ROOT / "test/preview-project-tests.py")
PF = importlib.util.module_from_spec(spec)
spec.loader.exec_module(PF)


class PreviewWorkflowTests(unittest.TestCase):
    run_raw = classmethod(PF.PreviewProjectTests.run_raw.__func__)
    git = classmethod(PF.PreviewProjectTests.git.__func__)
    repo = classmethod(PF.PreviewProjectTests.repo.__func__)

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="domestique workflow ", dir="/private/tmp")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.base = Path(cls.temp.name)
        cls.home = cls.base / "HOME ' $literal;"
        cls.home.mkdir()
        cls.bin = cls.base / "bin"
        cls.bin.mkdir()
        for tool in ("python3", "bash", "git", "dirname"):
            (cls.bin / tool).symlink_to(shutil.which(tool))
        cls.fake = cls.bin / "bd"
        cls.fake.write_text("#!" + sys.executable + "\n" +
                            (ROOT / "test/fixtures/preview-workflow/bd.py").read_text())
        cls.fake.chmod(0o700)
        cls.log = cls.base / "fakebd.jsonl"
        cls.env = dict(PATH=str(cls.bin), HOME=str(cls.home),
                       XDG_DATA_HOME=str(cls.home / "data"), LC_ALL="C",
                       GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
                       GIT_CONFIG_SYSTEM=os.devnull, GIT_OPTIONAL_LOCKS="0",
                       GIT_TERMINAL_PROMPT="0", FAKE_BD_LOG=str(cls.log),
                       FAKE_BD_PROJECT="no-project-yet")
        cls.source = cls.base / "trusted source"
        cls.repo(cls.source)
        shutil.copytree(ROOT / "preview", cls.source / "preview",
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(ROOT / "install-v2.sh", cls.source / "install-v2.sh")
        cls.git(cls.source, "add", "--", "preview", "install-v2.sh")
        cls.git(cls.source, "commit", "-m", "workflow runtime fixture")
        cls.first = cls.git(cls.source, "rev-parse", "HEAD").strip()
        common = cls.source / "preview/workflows/common.md"
        common.write_text(common.read_text() + "\nSECOND SHARED INSTRUCTION FIXTURE\n")
        cls.git(cls.source, "add", "--", "preview/workflows/common.md")
        cls.git(cls.source, "commit", "-m", "shared instruction update fixture")
        cls.second = cls.git(cls.source, "rev-parse", "HEAD").strip()
        cls.machine_root = cls.home / "data/domestique-preview"
        cls.launcher = cls.home / ".local/bin/domestique2"
        cls.run_raw(["bash", "-p", ROOT / "install-v2.sh", "--source", cls.source,
                     "--ref", cls.first], cls.base)
        assert not cls.log.exists(), "installer invoked bd"
        cls.protected_source = PF.snapshot(cls.source)
        print("COHORT " + json.dumps({"fixture": str(cls.base), "first": cls.first,
                                      "second": cls.second, "proof": "fake CLI/policy only"}), flush=True)

    def setUp(self):
        self.area = self.base / self._testMethodName
        self.area.mkdir()
        self.a = self.area / "A ' $literal;\nproject"
        self.b = self.area / "B unactivated"
        self.repo(self.a)
        self.repo(self.b)
        self.env["FAKE_BD_PROJECT"] = str(self.a)
        self.env.pop("FAKE_BD_STATE", None)
        if self.log.exists():
            self.log.unlink()
        self.command("enable", self.a)
        self.record = (self.a / RECEIPT).read_bytes()
        self.native_bytes = {leaf: (self.a / leaf).read_bytes() for leaf in LEAVES.values()}
        self.protected_b = PF.snapshot(self.b)
        self.protected_home = PF.snapshot(self.home)

    def tearDown(self):
        self.assertEqual(PF.snapshot(self.source), self.protected_source)
        self.assertEqual(PF.snapshot(self.b), self.protected_b)
        self.assertEqual(PF.snapshot(self.home), self.protected_home)
        if self.log.exists():
            print("FAKE_BD_TRANSCRIPT " + self.log.read_text(), flush=True)

    def command(self, *args, code=0):
        return self.run_raw([self.launcher, *args], self.b, code)

    def load(self, kind, *args, code=0, root=None):
        return self.command("workflow", kind, "--project", root or self.a, *args, code=code)

    def anchor(self):
        (self.a / ".beads").mkdir()
        (self.a / ".beads/note").write_text("not a database")

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def role_commands(self, output):
        suffix = output.split("No CLI can authenticate")[1].split("\n\n", 1)[1]
        commands, tokens = [], shlex.split(suffix)
        executable = tokens[0]
        while tokens:
            index = tokens.index(executable, 1) if executable in tokens[1:] else len(tokens)
            commands.append(tokens[:index])
            tokens = tokens[index:]
        return commands

    def test_definition_loading_and_old_locators_no_bd(self):
        before = PF.snapshot(self.a)
        for kind, leaf in LEAVES.items():
            body = (self.a / leaf).read_text()
            locator = body.split("```sh\n")[1].split("\n```")[0]
            self.assertEqual(shlex.split(locator),
                             [str(self.launcher), "workflow", kind, "--project", str(self.a)])
            output = self.run_raw(shlex.split(locator), self.b)
            self.assertIn("Beads readiness: NOT CHECKED", output)
            if kind in ("implementer", "reviewer"):
                self.assertIn("ROLE LOCATOR ONLY", output)
                self.assertNotIn("## Delegated", output)
            if kind == "goal":
                self.assertIn("SETUP ONLY", output)
                self.assertIn("--domestique-goal --ready", output)
                self.assertNotIn("## Explicit Domestique goal", output)
        for args in (("help",), ("inspect", self.a), ("enable", self.a),
                     ("disable", self.a, "--dry-run")):
            self.command(*args, code=1 if args[0] == "inspect" else 0)
        self.assertEqual(PF.snapshot(self.a), before)
        self.assertEqual(self.calls(), [])
        for args in (("--ready",), ("--epic", "fixture-epic", "--ready"),
                     ("--domestique-goal", "--ready")):
            self.assertIn("readiness requires", self.load("goal", *args, code=1))
        self.assertEqual(self.calls(), [])
        self.command("disable", self.a)
        self.assertEqual(self.calls(), [])

    def test_readiness_failures_and_planning_argv_only(self):
        self.load("decompose", "--brief", "plan only", "--ready", code=1)
        self.assertEqual(self.calls(), [])
        self.anchor()
        held = self.bin / "held-bd"
        self.fake.rename(held)
        try:
            self.assertIn("existing user-managed bd", self.load(
                "decompose", "--brief", "plan only", "--ready", code=1))
        finally:
            held.rename(self.fake)
        for state, count, exit_code in (("fail-version", 1, 32), ("bad-state", 2, 31)):
            self.env["FAKE_BD_STATE"] = state
            output = self.load("decompose", "--brief", "plan only", "--ready", code=1)
            self.assertIn(f"exit {exit_code}", output)
            self.assertNotIn("FAKE-PRIVATE-CONFIG", output)
            self.assertNotIn("## Decompose", output)
            self.assertEqual(self.calls()[-1]["exit"], exit_code)
            self.assertEqual(len(self.calls()), count if state == "fail-version" else 3)
        self.env.pop("FAKE_BD_STATE")
        # Even when ambient variables name B, readiness must invoke A explicitly.
        self.env.update(GIT_DIR=str(self.b / ".git"), BEADS_DIR=str(self.b / ".beads"),
                        BEADS_DB="wrong-project", BD_DB="wrong-project")
        try:
            before = PF.snapshot(self.a)
            brief = "plan ' $literal;\nsecond line"
            output = self.load("decompose", "--brief", brief, "--ready")
            self.assertIn("PLANNING ONLY", output)
            self.assertIn("No code", output)
            self.assertEqual(PF.snapshot(self.a), before)
            self.assertEqual([c["argv"] for c in self.calls()[-2:]],
                             [["--version"], ["-C", str(self.a), "status"]])
            self.assertTrue(all(c["cwd"] == str(self.a) and not c["retarget_keys"]
                                for c in self.calls()[-2:]))
        finally:
            for key in ("GIT_DIR", "BEADS_DIR", "BEADS_DB", "BD_DB"):
                self.env.pop(key)
        # Explicit fake planning transcript, not execution by a native caller.
        argv = [self.fake, "-C", self.a, "create", brief, "-t", "epic", "-p", "1",
                "--description", brief]
        self.run_raw(argv, self.a)
        self.assertEqual(self.calls()[-1]["argv"], [str(a) for a in argv[1:]])
        self.assertEqual(PF.snapshot(self.a), before, "fake planning must not write code")

    def test_activation_role_and_context_refusals(self):
        self.assertIn("not activated", self.load("ordinary", root=self.b, code=1))
        sub = self.a / "nested"
        sub.mkdir()
        self.load("ordinary", root=sub, code=1)
        copied = self.area / "copy"
        shutil.copytree(self.a, copied)
        self.assertIn("copied/moved", self.load("ordinary", root=copied, code=1))
        moved = self.area / "moved"
        self.a.rename(moved)
        self.load("ordinary", root=moved, code=1)
        moved.rename(self.a)
        path = self.a / RECEIPT
        record = json.loads(self.record)
        for field, replacement in (("state", "disabled"), ("installation", {}),
                                   ("native_ids", {})):
            changed = dict(record, **{field: replacement})
            path.write_text(json.dumps(changed))
            self.load("ordinary", code=1)
            path.write_bytes(self.record)
        leaf = self.a / LEAVES["reviewer"]
        held = self.area / "held-role"
        leaf.rename(held)
        self.assertIn("missing owned", self.load("ordinary", code=1))
        held.rename(leaf)
        old = self.machine_root / "releases" / self.first / "preview/cli.py"
        for extra in (["--task", "fixture-epic.1"],
                      ["--task", "fixture-epic.1", "--brief", "bounded",
                       "--source", str(old), "--role-id", DEFINITIONS["reviewer"][0]],
                      ["--task", "fixture-epic.1", "--brief", "bounded",
                       "--source", str(self.source / "preview/cli.py"),
                       "--role-id", DEFINITIONS["implementer"][0]]):
            self.load("implementer", *extra, code=1)
        for args in (("--task", "two tasks"), ("--unknown", "x"),
                     ("--project", str(self.a)), ("--brief", ""),
                     ("--ready", "--ready")):
            self.load("ordinary", *args, code=2)
        self.assertEqual(self.calls(), [])

    def test_customized_bytes_and_model_transport_policy(self):
        role = self.a / LEAVES["implementer"]
        role.write_bytes(b"---\nname: [invalid YAML\nmodel: user\n---\n\xff\n")
        customized = role.read_bytes()
        output = self.load("ordinary")
        self.assertIn("customized", output)
        self.assertIn("fresh native", output)
        self.anchor()
        args = ["--task", "fixture-epic.1", "--brief", "bounded", "--ready"]
        self.load("ordinary", *args, code=1)
        self.assertEqual(self.calls(), [])
        model = "gpt-requested ' $literal;\nexact second line"
        output = self.load("ordinary", *args, "--confirm-native", "--implementer-model", model)
        self.assertIn("STOP before delegation; no substitute model or fallback vendor", output)
        commands = self.role_commands(output)
        self.assertEqual(len(commands), 2)
        for argv in commands:
            self.assertEqual(argv[argv.index("--implementer-model") + 1], model)
        # A fake capability list only establishes policy/transport, NOT dispatch.
        fake_available = {"different-openai-id"}
        self.assertNotIn(model, fake_available)
        self.assertIn("exact dispatch cannot be confirmed", output)
        self.assertEqual(role.read_bytes(), customized)
        self.assertEqual((self.a / RECEIPT).read_bytes(), self.record)

    def test_explicit_goal_bounded_transcript_and_blocked_not_complete(self):
        self.anchor()
        output = self.load("goal", "--epic", "fixture-epic", "--domestique-goal", "--ready")
        for policy in ("Stop after ONE reviewed bead", "at most 15", "BLOCKED, not complete",
                       "At most one corrective", "Never close an unpassed task",
                       "git --literal-pathspecs add -- PATH", "fresh independent reviewer"):
            self.assertIn(policy, output)
        self.run_raw([self.fake, "-C", self.a, "ready", "--parent", "fixture-epic"], self.a)
        self.run_raw([self.fake, "-C", self.a, "list", "--parent", "fixture-epic", "--all"], self.a)
        self.assertFalse(any("close" in c["argv"] for c in self.calls()))
        brief = "one bounded task ' $data;\ninput/output/done: fixture only"
        output = self.load("ordinary", "--task", "fixture-epic.1", "--brief", brief)
        # Parse multiline shell literal commands without executing a shell.
        commands = self.role_commands(output)
        self.assertEqual(len(commands), 2)
        # A scripted fixture lifecycle exercises transport/argv, not a native
        # implementer or reviewer. It grants no qualification to their verdicts.
        self.run_raw([self.fake, "-C", self.a, "update", "fixture-epic.1", "--claim"], self.a)
        transcript = [{"event": "fake claim; explicit ordinary task, not blocked goal continuation"}]
        for role, argv in zip(("implementer", "reviewer"), commands):
            self.assertEqual(argv[argv.index("--project") + 1], str(self.a))
            self.assertEqual(argv[argv.index("--task") + 1], "fixture-epic.1")
            self.assertEqual(argv[argv.index("--brief") + 1], brief)
            self.assertEqual(argv[argv.index("--role-id") + 1], DEFINITIONS[role][0])
            text = self.run_raw(argv, self.b)
            self.assertIn("## Delegated", text)
            transcript.append({"role": role, "source": argv[4], "task": "fixture-epic.1",
                               "kind": "instruction load only, no native delegation"})
        self.assertFalse(any("close" in c["argv"] for c in self.calls()))
        transcript.append({"event": "scripted PASS, NOT actual review; no close on prior non-PASS"})
        self.git(self.a, "switch", "-c", "fixture/reviewed-bead")
        (self.a / "host.txt").write_text("scripted reviewed fixture edit\n")
        self.git(self.a, "--literal-pathspecs", "add", "--", "host.txt")
        self.git(self.a, "commit", "-m", "fixture-epic.1 scripted reviewed fixture only")
        transcript.append({"commit": self.git(self.a, "rev-parse", "HEAD").strip()})
        self.run_raw([self.fake, "-C", self.a, "close", "fixture-epic.1"], self.a)
        self.assertEqual(sum("close" in c["argv"] for c in self.calls()), 1)
        print("BOUNDED_TRANSCRIPT " + json.dumps(transcript), flush=True)

    def test_z_shared_update_retains_old_role_commands_and_provenance(self):
        # Use a single-line root here so ordinary shlex line extraction is useful.
        plain = self.area / "plain A"
        self.repo(plain)
        self.command("enable", plain)
        before = PF.snapshot(plain)
        output = self.load("ordinary", "--task", "fixture-epic.1", "--brief", "bounded", root=plain)
        old_commands = self.role_commands(output)[-2:]
        self.command("update", "--ref", self.second)
        self.protected_home = PF.snapshot(self.home)
        self.assertEqual(PF.snapshot(plain), before)
        self.assertEqual((self.a / RECEIPT).read_bytes(), self.record)
        for leaf, data in self.native_bytes.items():
            self.assertEqual((self.a / leaf).read_bytes(), data)
            locator = data.decode().split("```sh\n")[1].split("\n```")[0]
            text = self.run_raw(shlex.split(locator), self.b)
            self.assertIn(self.second, text)
        self.assertIn("SECOND SHARED", self.load("ordinary", root=plain))
        self.assertEqual(len(old_commands), 2)
        for argv in old_commands:
            self.assertIn(self.first, argv[4])
            text = self.run_raw(argv, self.b)
            self.assertNotIn("SECOND SHARED", text)
            wrong = list(argv)
            wrong[4] = wrong[4].replace(self.first, self.second)
            self.assertIn("wrong retained source", self.run_raw(wrong, self.b, 1))
        self.assertEqual(self.calls(), [])
        provenance = (ROOT / "preview/workflows/provenance.md").read_text()
        for digest in ("3160002319c36f1e815ea55684b11407b646c4b494b1856db3eb4ff1f01ff847",
                       "90c77aeaa5b51a07e5e5ee6bc46954e75e6dbf837ea0fb69b757dc800f507a69",
                       "d50fdb9a7bec1d457ea21547038985a46965b02e0b71416fde6969ccfb1e9e8c",
                       "ed4ed88a3d16684dc4f9733d66753af86d3d6d91349c12c34666e97acb793631"):
            self.assertIn(digest, provenance)


if __name__ == "__main__":
    unittest.main(verbosity=2)
