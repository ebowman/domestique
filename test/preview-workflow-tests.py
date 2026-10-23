"""Installed-runtime + fake-argv/policy tests. NOT actual native lifecycle proof."""
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "preview"))
from native import ALIASES, DEFINITIONS, LEAVES
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
        return self.command("workflow", kind, "--project", root or self.a,
                            "--harness", "copilot", *args, code=code)

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
            kind = ALIASES.get(kind, kind)
            body = (self.a / leaf).read_text()
            locator = body.split("```sh\n")[1].split("\n```")[0]
            self.assertEqual(shlex.split(locator),
                             [str(self.launcher), "workflow", kind, "--project", str(self.a),
                              "--harness", "copilot"])
            output = self.run_raw(shlex.split(locator), self.b)
            self.assertIn("Beads readiness: NOT CHECKED", output)
            if kind in ("implementer", "reviewer"):
                self.assertIn("Role model confirmation: UNCONFIRMED", output)
                self.assertNotIn("## Delegated", output)
            if kind == "goal":
                self.assertNotIn("disable-model-invocation", body.split("---\n")[1])
                self.assertIn("SETUP ONLY", output)
                self.assertIn("Goal request consumed, not queued", output)
                self.assertNotIn("## Explicit Domestique goal", output)
        for args in (("help",), ("inspect", self.a), ("enable", self.a),
                     ("disable", self.a, "--dry-run")):
            self.command(*args)
        self.assertEqual(PF.snapshot(self.a), before)
        self.assertEqual(self.calls(), [])
        for args in (("--epic", "fixture-epic"), ("--domestique-goal",)):
            self.assertIn("SETUP ONLY", self.load("goal", *args))
        output = self.load("goal", "--epic", "fixture-epic", "--domestique-goal")
        self.assertIn("Beads readiness: NOT CHECKED; no bd invoked.", output)
        self.assertIn("Role model confirmation: UNCONFIRMED", output)
        self.assertEqual(PF.snapshot(self.a), before)
        self.assertEqual(self.calls(), [])
        for args in (("--ready",), ("--epic", "fixture-epic", "--ready"),
                     ("--domestique-goal", "--ready")):
            self.assertIn("readiness requires", self.load("goal", *args, code=1))
        for kind, args in (("decompose", ("--brief", "plan")),
                           ("goal", ("--epic", "fixture-epic", "--domestique-goal")),
                           ("ordinary", ("--task", "fixture-epic.1", "--brief", "bounded"))):
            self.assertIn("unconfirmed", self.load(kind, *args, "--ready",
                          "--confirm-native", "--confirm-model-selection", code=1))
        self.assertEqual(self.calls(), [])
        self.command("disable", self.a)
        self.assertEqual(self.calls(), [])

    def test_readiness_failures_and_planning_argv_only(self):
        PF.setup_models(self)
        ready = ("--confirm-native", "--confirm-model-selection")
        self.load("decompose", "--brief", "plan only", "--ready", code=1)
        self.assertEqual(self.calls(), [])
        self.anchor()
        held = self.bin / "held-bd"
        self.fake.rename(held)
        try:
            self.assertIn("existing user-managed bd", self.load(
                "decompose", "--brief", "plan only", "--ready", *ready, code=1))
        finally:
            held.rename(self.fake)
        for state, count, exit_code in (("fail-version", 1, 32), ("bad-state", 2, 31)):
            self.env["FAKE_BD_STATE"] = state
            output = self.load("decompose", "--brief", "plan only", "--ready", *ready, code=1)
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
            output = self.load("decompose", "--brief", brief, "--ready", *ready)
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

    def test_post_publication_failure_revokes_confirmation(self):
        real_save, real_context = PF.S.save, PF.S.context
        for fault in ("save-after", "final-check", "cleanup-before", "cleanup-after"):
            with self.subTest(fault=fault):
                root = self.area / fault
                self.repo(root)
                self.command("enable", root)
                role_path = root / LEAVES["implementer"]
                custom = b"\nPreserve custom role instructions.\n"
                role_path.write_bytes(role_path.read_bytes() + custom)
                creation = json.loads((root / RECEIPT).read_bytes())["files"]
                mode = role_path.stat().st_mode
                save_calls = context_calls = 0

                def save(path, record):
                    nonlocal save_calls
                    save_calls += 1
                    if fault == "cleanup-before" and save_calls == 2:
                        raise OSError("fixture cleanup before publication")
                    real_save(path, record)
                    if save_calls == 1 and fault != "final-check":
                        raise OSError("fixture save after receipt publication")
                    if fault == "cleanup-after" and save_calls == 2:
                        raise OSError("fixture cleanup after publication")

                def context(*args):
                    nonlocal context_calls
                    context_calls += 1
                    result = real_context(*args)
                    if fault == "final-check" and context_calls == 3:
                        self.assertTrue(PF.S.confirmed(*result))
                        raise PF.Refusal("fixture final verification after publication")
                    return result

                with patch.object(PF.S, "save", side_effect=save), \
                        patch.object(PF.S, "context", side_effect=context), \
                        self.assertRaisesRegex(PF.Refusal, "PARTIAL role setup") as caught:
                    PF.setup_models(self, root, implementer="inherit", reviewer="inherit")
                message = str(caught.exception)
                self.assertIn(RECEIPT, message)
                self.assertIn("no success or workflow authority", message)
                self.assertEqual(save_calls, 2)
                record = json.loads((root / RECEIPT).read_bytes())
                for role in PF.S.ROLES:
                    path = root / LEAVES[role]
                    facts = record["files"][LEAVES[role]]
                    self.assertEqual({k: facts[k] for k in ("identity", "sha256")},
                                     creation[LEAVES[role]])
                    self.assertEqual(facts["model_setup"]["identity"], PF.S.identity(path))
                    self.assertEqual(facts["model_setup"]["sha256"], PF.S.sha(path.read_bytes()))
                self.assertEqual(role_path.stat().st_mode, mode)
                self.assertTrue(role_path.read_bytes().endswith(custom))
                self.assertFalse(record["files"][LEAVES["implementer"]]["model_setup"]["removable"])
                if fault.startswith("cleanup"):
                    self.assertIn("fixture cleanup", message)
                else:
                    self.assertIn("cleanup errors: []", message)
                if fault == "cleanup-before":
                    # No optimistic rollback claim when invalidation itself cannot publish.
                    self.assertIn("CONFIRMED persists", message)
                    self.assertIn("future gate may pass", message)
                    self.assertIn("confirmed file pair", self.command("inspect", root))
                    continue
                self.assertIn("observed confirmation: unconfirmed", message)
                self.assertIn("Role model setup: unconfirmed", self.command("inspect", root))
                self.assertIn("Role model confirmation: UNCONFIRMED",
                              self.load("decompose", "--brief", "plan", root=root))
                self.assertIn("role models unconfirmed", self.load(
                    "decompose", "--brief", "plan", "--ready", "--confirm-native",
                    "--confirm-model-selection", root=root, code=1))
                self.assertEqual(self.calls(), [], "failed setup must stop before even fake Beads")
                # Explicit retry clears only completion revocation, not creation/customization.
                PF.setup_models(self, root, implementer="inherit", reviewer="inherit")
                self.assertIn("confirmed file pair", self.command("inspect", root))
                self.assertTrue(role_path.read_bytes().endswith(custom))

    def test_emitted_readiness_after_explicit_caller_confirmation(self):
        PF.setup_models(self, implementer="inherit", reviewer="inherit")
        self.anchor()
        brief = "plan ' literal;\nsecond line"
        output = self.load("decompose", "--brief", brief)
        self.assertEqual(self.calls(), [])
        self.assertIn("AND actual native confirmation", output)
        self.assertIn("unknown means STOP, do not run it", output)
        self.assertIn("Setup writer assertions and a model catalog do not establish", output)
        emitted = output.split("if not already supplied):\n\n", 1)[1].split(
            "\n\nCaller role commands:", 1)[0]
        cli = str(self.machine_root / "releases" / self.first / "preview/cli.py")
        expected = [str(self.bin / "python3"), "-I", "-S", "-B", cli, "workflow", "decompose",
                    "--project", str(self.a), "--source", cli, "--harness", "copilot",
                    "--brief", brief, "--confirm-model-selection", "--confirm-native", "--ready"]
        self.assertEqual(emitted, shlex.join(expected))
        # Establish the caller's checks explicitly in this synthetic fixture.
        # This is NOT a native check, catalog inference or dispatch qualification.
        caller_confirmation = dict(exact_loaded_ids=True, capabilities=True, required_tools=True,
                                   inherited_effective_models=True, overrides_checked=True)
        self.assertTrue(all(caller_confirmation.values()))
        without_native = [arg for arg in expected if arg != "--confirm-native"]
        self.assertIn("require fresh native confirmation", self.run_raw(without_native, self.b, 1))
        self.assertEqual(self.calls(), [])
        result = self.run_raw(shlex.split(emitted), self.b)
        self.assertIn("PLANNING ONLY", result)
        self.assertIn("Beads readiness: requested --version and project status succeeded", result)
        self.assertNotIn("Only after the user's explicit action request AND", result)
        self.assertEqual([c["argv"] for c in self.calls()],
                         [["--version"], ["-C", str(self.a), "status"]])

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
        output = self.load("ordinary", code=1)
        self.assertIn("UTF-8", output)
        self.anchor()
        args = ["--task", "fixture-epic.1", "--brief", "bounded", "--ready"]
        self.load("ordinary", *args, code=1)
        self.assertEqual(self.calls(), [])
        role.write_bytes(self.native_bytes[LEAVES["implementer"]] + b"\nCustom instructions.\n")
        PF.setup_models(self, implementer="inherit", reviewer="inherit")
        customized = role.read_bytes()
        receipt = (self.a / RECEIPT).read_bytes()
        model = "fixture-openai-exact"
        output = self.load("ordinary", *args, "--confirm-native", "--confirm-model-selection",
                           "--implementer-model", model)
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
        self.assertEqual((self.a / RECEIPT).read_bytes(), receipt)

    def test_public_alias_guards(self):
        for alias in ALIASES:
            leaf = self.a / LEAVES[alias]
            original = leaf.read_bytes()
            leaf.write_bytes(original + b"\nCustomized alias\n")
            output = self.load("goal")
            self.assertIn("SETUP ONLY", output)
            self.assertIn(alias, output)
            self.load("goal", "--epic", "fixture-epic", "--domestique-goal", "--ready", code=1)
            self.assertEqual(self.calls(), [])
            held = self.area / alias
            leaf.rename(held)
            self.assertIn("missing owned native", self.load("ordinary", code=1))
            self.assertEqual(self.calls(), [])
            held.rename(leaf)
            leaf.write_bytes(original)
        self.assertEqual((self.a / RECEIPT).read_bytes(), self.record)

    def test_explicit_goal_bounded_transcript_and_blocked_not_complete(self):
        PF.setup_models(self)
        self.anchor()
        output = self.load("goal", "--epic", "fixture-epic", "--domestique-goal", "--ready",
                           "--confirm-native", "--confirm-model-selection")
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
        PF.setup_models(self, plain)
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

    def test_model_setup_repeat_reconfigure_and_retained_cli_gate(self):
        before = PF.snapshot(self.a)
        old = self.machine_root / "releases" / self.first / "preview/cli.py"
        write = ("--brief", "configure role models", "--source", str(old),
                 "--save-role-models", "--confirm-model-support",
                 "--implementer-model", "fixture-openai", "--reviewer-model", "fixture-openai")
        self.assertIn("noninteractive setup refused", self.load("decompose", *write, code=1))
        self.assertEqual(PF.snapshot(self.a), before)
        PF.setup_models(self)
        before = PF.snapshot(self.a)
        for kind in ("ordinary", "decompose", "goal"):
            output = self.load(kind)
            self.assertIn("Role model confirmation: confirmed file pair", output)
            self.assertNotIn("Ask ONE two-role question", output)
        self.assertEqual(PF.snapshot(self.a), before)
        output = self.load("decompose", "--brief", "configure role models")
        self.assertIn("explicit reconfiguration", output)
        self.assertIn("Ask ONE two-role question", output)
        self.load("decompose", "--brief", "configure role models", "--ready", code=1)
        self.assertIn("effective loaded role selection unknown", self.load(
            "decompose", "--brief", "plan", "--ready", "--confirm-native", code=1))
        self.assertIn("conflicts", self.load("decompose", "--brief", "plan", "--ready",
            "--confirm-native", "--confirm-model-selection", "--implementer-model", "other", code=1))
        role = self.a / LEAVES["reviewer"]
        role.write_bytes(role.read_bytes() + b"\nManual customization.\n")
        output = self.run_raw([sys.executable, "-I", "-S", "-B", old, "workflow", "decompose",
                              "--project", self.a, "--harness", "copilot", "--brief", "plan",
                              "--ready", "--confirm-native", "--confirm-model-selection"], self.b, 1)
        self.assertIn("unconfirmed", output)
        self.assertEqual(self.calls(), [])

    def test_installed_writer_synthetic_terminal_not_native_evidence(self):
        old = self.machine_root / "releases" / self.first / "preview/cli.py"
        argv = [sys.executable, "-I", "-S", "-B", str(old), "workflow", "decompose",
                "--project", str(self.a), "--source", str(old), "--harness", "copilot",
                "--brief", "configure role models", "--save-role-models",
                "--confirm-model-support", "--implementer-model", "inherit",
                "--reviewer-model", "inherit"]
        master, slave = os.openpty()
        try:
            process = subprocess.Popen(argv, cwd=self.a, env=self.env, stdin=slave,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            os.write(master, b"Save setup only\n")
            try:
                out, err = process.communicate(timeout=30)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
            self.assertEqual(process.returncode, 0, err)
            self.assertIn("Caller support assertion is NOT native evidence", out)
            self.assertIn("Saved setup only", out)
            self.assertNotIn("## Explicit Domestique goal", out)
        finally:
            os.close(master)
            os.close(slave)
        self.assertEqual(self.calls(), [])
        before = PF.snapshot(self.a)
        self.assertIn("confirmed file pair", self.load("decompose"))
        self.assertEqual(PF.snapshot(self.a), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
