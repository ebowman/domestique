"""Small offline installed-CLI cohort; no native, DB, historical fixture or network."""
import hashlib
import io
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
from contextlib import redirect_stdout
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "preview"))
import project as P
import model_setup as S
from machine import Refusal, read_json
from native import ALIASES, ENTRIES, LEAVES, templates
from project_data import RECEIPT, PATHS


def setup_models(case, root=None, implementer="fixture-openai", reviewer="fixture-openai",
                 consent="Save setup only\n", interactive=True, support=True):
    """Real local writer, synthetic terminal/support only; NOT native evidence."""
    stdin = io.StringIO(consent)
    output = io.StringIO()
    options = {"--harness": "copilot", "--implementer-model": implementer,
               "--reviewer-model": reviewer, "--confirm-model-support": support}
    with patch.dict(os.environ, case.env, clear=True), patch.object(sys, "stdin", stdin), \
            patch.object(stdin, "isatty", return_value=interactive), redirect_stdout(output):
        result = S.write_setup(str(root or case.a), case.machine_root,
                               read_json(case.machine_root / "receipt.json"), options)
    return result, output.getvalue()


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
        # Freeze the actual prior five-definition lifecycle and exact block,
        # not today's constants with two files removed after activation.
        frozen = "654414025554defe9eeef50c39b14a87326088b8"
        names = ("native.py", "project_data.py", "project.py", "workflow.py", "footprint.py")
        current = {name: (cls.source / "preview" / name).read_bytes() for name in names}
        for name in names:
            old = subprocess.check_output(
                ["git", "--no-pager", "-C", str(ROOT), "show", f"{frozen}:preview/{name}"],
                env=cls.env)
            (cls.source / "preview" / name).write_bytes(old)
        # Historical goal metadata must remain owned bytes, not be migrated.
        native = cls.source / "preview/native.py"
        current_native = native.read_text()
        native.write_text(current_native.replace(
            '        text += "---\\n\\n"',
            '        if kind == "goal":\n'
            '            text += "disable-model-invocation: true\\n"\n'
            '        text += "---\\n\\n"'))
        cls.git(cls.source, "add", ".")
        cls.git(cls.source, "commit", "-m", "legacy goal metadata fixture")
        cls.legacy = cls.git(cls.source, "rev-parse", "HEAD").strip()
        for name, data in current.items():
            (cls.source / "preview" / name).write_bytes(data)
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

    def assert_legacy_enable_refused(self, root):
        def identities():
            return {str(p): (p.lstat().st_dev, p.lstat().st_ino, p.lstat().st_mtime_ns)
                    for p in root.rglob("*")}

        before = identities()
        for suffix in ((), ("--dry-run",)):
            self.assertIn("legacy/experimental authority collision",
                          self.unchanged_call("enable", root, *suffix, code=1))
            self.assertEqual(identities(), before, "not even same-byte replacement/touch")

    def test_copilot_first_v1_pairs_are_isolated_not_coexistence_support(self):
        # Real lifecycles, then synthetic V1 pairs / real Copilot writer with
        # synthetic terminal consent. No questionnaire or native model proof.
        for mode in ("normal", "guest"):
            with self.subTest(mode=mode):
                root = self.area / mode
                self.repo(root)
                note = root / "project-sentinel"
                note.write_bytes(b"unrelated project settings\n")
                namespaces = {"claude": (".claude",), "codex": (".codex", ".agents"),
                              "copilot": (".github", ".domestique-private")}

                def inventories():
                    return {h: {p: snapshot(root / p) for p in paths}
                            for h, paths in namespaces.items()}

                def isolated(harnesses, action):
                    before = inventories()
                    sentinels = (snapshot(self.home), snapshot(self.b),
                                 snapshot(self.source), note.read_bytes(),
                                 (root / "host.txt").read_bytes())
                    result = action()
                    for other in namespaces.keys() - set(harnesses):
                        self.assertEqual(inventories()[other], before[other], other)
                    self.assertEqual(
                        (snapshot(self.home), snapshot(self.b), snapshot(self.source),
                         note.read_bytes(), (root / "host.txt").read_bytes()), sentinels)
                    return result

                isolated(("copilot",), lambda: self.command("enable", root))
                creation = self.receipt(root)["files"]
                args = ("--guest",) if mode == "guest" else ()
                # V1's supported both-provider install also records shared
                # platform selection; don't mistake that for a role setup edit.
                isolated(("claude", "codex"), lambda: self.run_raw(
                    ["bash", ROOT / "domestique.sh", root, "--platform", "both", *args], root))
                # The V1 installer accepts this order. It does not make repeat
                # preview activation legal, even with an intact active receipt.
                self.assert_legacy_enable_refused(root)

                definitions = {}
                for kind in ("decompose", "goal"):
                    claude = root / f".claude/commands/{kind}.md"
                    alias = root / f".claude/commands/dom-{kind}.md"
                    self.assertEqual(claude.read_bytes(), alias.read_bytes())
                    codex = root / f".agents/skills/domestique-{kind}/SKILL.md"
                    short = root / f".agents/skills/dom-{kind}/SKILL.md"
                    # The canonical skill is a shared router, not a second
                    # Codex body. Check the actual installed route and its
                    # authority boundary, not native execution/qualification.
                    self.assertFalse(short.is_symlink())
                    self.assertEqual(short.stat().st_nlink, 1)
                    shared = short.read_text()
                    self.assertEqual(shared.split("---\n", 2)[1].splitlines()[0],
                                     f"name: dom-{kind}")
                    self.assertIn("description: Codex or Copilot only.", shared)
                    self.assertEqual(
                        [line for line in shared.splitlines()
                         if line.startswith(("- Codex:", "- Copilot:"))],
                        [f"- Codex: `.agents/skills/domestique-{kind}/SKILL.md` "
                         f"(compatibility `$domestique-{kind}`); ordinary loop "
                         "`.agents/skills/domestique/SKILL.md`, native roles "
                         "`implementer` / `reviewer`.",
                         f"- Copilot: `.github/skills/domestique-v2-copilot-{kind}/SKILL.md`; "
                         "ordinary loop `.github/skills/domestique-v2-copilot/SKILL.md`, "
                         "native roles `domestique-v2-copilot-implementer` / "
                         "`domestique-v2-copilot-reviewer`."])
                    routed = " ".join(shared.split())
                    for text in (
                            "ACTUAL native caller using the client's available session context "
                            "and native tools",
                            "Installed directories, file names, skill matching/loading and this "
                            "text do NOT identify the client",
                            "Unknown, ambiguous, or unsupported callers STOP explicitly, "
                            "without setup, Beads, task, branch or dispatch writes",
                            "Read only the body for the established native caller",
                            "relative to ROOT; never search another checkout/ancestor, invoke "
                            "a global/machine launcher, or fall back across harnesses",
                            "Missing, unreadable or foreign native bodies mean STOP",
                            "this installer does not yet emit Copilot bodies",
                            "ORIGINAL user request verbatim, including explicit epic arguments "
                            "and its authorization provenance",
                            "Never synthesize a new user invocation",
                            "Merely loading or implicitly matching this skill is not unattended "
                            "authority and must not start setup",
                            "Goal requires an original explicit dom-goal invocation naming "
                            "the epic (Codex $dom-goal; Copilot /dom-goal)",
                            "loading the routed body cannot grant it",
                            "Setup consumes that request; fresh-session explicit reinvocation "
                            "is required, not automatic continuation"):
                        self.assertIn(text, routed)
                    self.assertNotIn("first-use role setup", shared)
                    self.assertNotIn("bd create", shared)
                    if kind == "decompose":
                        for path in (claude, codex):
                            body = path.read_text()
                            self.assertLess(body.index("End role setup gate"),
                                            body.index("Do not implement anything."))
                            self.assertIn("bounded", body)
                            self.assertIn("bd ready", body)
                            self.assertIn("epic tree", body)
                    if kind == "goal":
                        # Emitted protocol ordering, NOT execution by a native
                        # assistant or proof that it obeys these instructions.
                        for path in (claude, codex):
                            # Assert shared obligations, not provider-specific
                            # headings or Markdown line wrapping.
                            body = " ".join(path.read_text().split())
                            ordered = (
                                "Match declared model AND effort and required tools",
                                "Save the displayed minimal diff to these two files?",
                                "setup mean ZERO writes and NO Beads/workflow calls",
                                "Invalidate any old implementer completion marker first",
                                "Write the reviewer update.",
                                "Publish implementer with the new pair marker LAST.",
                                "SETUP ONLY: no planning beads, claim, code, dispatch, "
                                "branch/commit or goal cycle.",
                                "NOT queued for automatic continuation",
                                "Only an unchanged confirmed, ready pair can enter "
                                "the unattended loop below.",
                                "Only after the role setup gate passes without setup writes",
                                "check ALL tracked/index dirtiness",
                                "Then create")
                            required = (
                                "registration must be present and unambiguous",
                                "Verify the stored pair, ownership, physical ROOT, "
                                "BOTH marker hashes",
                                "known defeating override/unavailability means STOP "
                                "without workflow or writes.",
                                "A catalog, file syntax, user assertion or marker alone "
                                "is not dispatch proof.",
                                "Missing optional exact-origin/loaded-byte APIs or "
                                "not-yet-existent child telemetry alone do not block",
                                "After saving, require a fresh client session and "
                                "explicit reinvocation.",
                                "never auto-stage, commit, stash, discard or hide it.")
                            explicit = ("/dom-goal <epic-id>" if path == claude
                                        else "$dom-goal <epic-id>")
                            compatibility = ("/goal <epic-id>" if path == claude
                                             else "$domestique-goal <epic-id>")
                            with self.subTest(protocol=str(path.relative_to(root))):
                                for text in ordered + required + (explicit, compatibility):
                                    self.assertIn(text, body)
                                self.assertIn("not unattended authority", body)
                                positions = [body.index(text) for text in ordered]
                                self.assertEqual(positions, sorted(positions))
                    for path in (claude, alias, codex, short):
                        definitions[path] = path.read_bytes()
                    locators = []
                    for entry in (kind, "dom-" + kind):
                        path = root / LEAVES[entry]
                        definitions[path] = path.read_bytes()
                        locators.append(path.read_text().split("```sh\n")[1].split("\n```")[0])
                    self.assertEqual(locators[0], locators[1])

                # Copilot discovers all .agents skills, not just the public
                # aliases, and reads root instructions. Unique names alone
                # cannot isolate the bootstrap, legacy bodies or policies.
                entries = list((root / ".agents/skills").glob("domestique*/SKILL.md"))
                entries += list((root / ".claude/commands").glob("*.md"))
                entries += list((root / ".claude/agents").glob("*.md"))
                self.assertEqual(len(entries), 9)
                for path in entries:
                    harness = "claude" if ".claude" in path.parts else "codex"
                    text = path.read_text()
                    description = next(line for line in text.splitlines()
                                       if line.startswith("description:"))
                    self.assertIn("Claude Code only" if harness == "claude"
                                  else "Codex only", description)
                    self.assertIn("never match", description)
                    self.assertIn(f"Active harness boundary ({harness} only)", text)
                    body = " ".join(text.split())
                    self.assertIn("An explicit foreign-harness invocation must STOP "
                                  "without setup, Beads, task, branch or dispatch writes", body)
                    self.assertIn("do not invoke them automatically", body)
                    for gate in ("first-use role setup", "Role model gate"):
                        if gate in text:
                            self.assertLess(text.index("Active harness boundary"), text.index(gate))
                    if path.parent.name != "agents":
                        definitions[path] = path.read_bytes()
                policies = (("CLAUDE.local.md" if mode == "guest" else "CLAUDE.md", "claude"),
                            ("AGENTS.md", "codex"))
                for filename, harness in policies:
                    path = root / filename
                    if mode == "guest" and harness == "codex":
                        self.assertFalse(path.exists(), "guest bootstrap must not add root policy")
                        continue
                    text = path.read_text()
                    self.assertIn(f"Active harness boundary ({harness} only)", text)
                    self.assertIn("Other harnesses must ignore this entire owned policy block", text)
                    self.assertIn("Unrelated host instructions still apply", text)
                    self.assertLess(text.index("Active harness boundary"), text.index("This session is"))
                    definitions[path] = path.read_bytes()

                for harness in ("claude", "codex", "copilot"):
                    before = snapshot(root)
                    if harness == "copilot":
                        result, _ = isolated((harness,), lambda: setup_models(self, root))
                        self.assertIn("Saved setup only", result)
                        allowed = {LEAVES[r] for r in S.ROLES} | {RECEIPT}
                    else:
                        extra = ["explicit"] if harness == "codex" else []
                        isolated((harness,), lambda: self.run_raw(
                            [sys.executable, "-B", ROOT / "test/fixtures" /
                             f"{harness}-configured-pair.py", root, *extra], root))
                        extension = "md" if harness == "claude" else "toml"
                        allowed = {f".{harness}/agents/{r}.{extension}" for r in S.ROLES}
                    after = snapshot(root)
                    self.assertEqual({p for p in before.keys() | after.keys()
                                      if before.get(p) != after.get(p)}, allowed)
                    self.assertEqual({p: p.read_bytes() for p in definitions}, definitions,
                                     "canonical/legacy entries retain the same pair and gate")
                    for leaf, facts in self.receipt(root)["files"].items():
                        self.assertEqual({k: v for k, v in facts.items() if k != "model_setup"},
                                         creation[leaf], "creation facts never rebaseline")
                    output = self.unchanged_call(
                        "workflow", "goal", "--project", root, "--harness", "copilot",
                        "--epic", "fixture-epic", "--domestique-goal")
                    confirmation = ("confirmed file pair" if harness == "copilot"
                                    else "UNCONFIRMED")
                    self.assertIn("Role model confirmation: " + confirmation, output,
                                  "V1 confirmation must not authorize Copilot")

                inspected = self.unchanged_call("inspect", root)
                self.assertIn("Preview activation: active", inspected)
                self.assertIn("confirmed file pair/receipt", inspected)
                self.assertIn('".claude/.domestique"', inspected)
                self.assertIn('".codex/.domestique"', inspected)
                self.assert_legacy_enable_refused(root)
                record = self.receipt(root)
                exclude = root / ".git/info/exclude"
                contribution = (record["exclusion"]["separator"] +
                                record["exclusion"]["block"]).encode()
                expected = exclude.read_bytes().replace(contribution, b"", 1)
                self.unchanged_call("disable", root, "--dry-run")
                isolated(("copilot",), lambda: self.command("disable", root))
                self.assertEqual(exclude.read_bytes(), expected,
                                 "remove only the preview contribution; keep V1/host suffix")
                self.assertFalse((root / RECEIPT).exists())
                self.assertTrue(all(not (root / leaf).exists() for leaf in LEAVES.values()))
                self.unchanged_call("disable", root)
                self.assertIn("Preview activation: absent", self.unchanged_call("inspect", root))
                self.assert_legacy_enable_refused(root)

    def test_v1_first_preview_enable_refuses_without_writes(self):
        self.run_raw(["bash", ROOT / "domestique.sh", self.a, "--platform", "both"], self.a)
        self.assert_legacy_enable_refused(self.a)
        self.assertFalse((self.a / RECEIPT).exists())
        self.assertFalse((self.a / ".github").exists())
        output = self.unchanged_call("inspect", self.a)
        self.assertIn("Preview activation: absent", output)
        self.assertIn('".claude/.domestique"', output)
        self.assertIn('".codex/.domestique"', output)
        self.unchanged_call("disable", self.a)

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
            name, description = ENTRIES[kind]
            workflow_kind = ALIASES.get(kind, kind)
            expected = f"name: {name}\ndescription: {description}\n"
            if workflow_kind == "goal":
                # Metadata permits model loading; the body still gates intent.
                self.assertNotIn("disable-model-invocation", front)
                self.assertIn("explicit Domestique goal request naming an epic", body)
                self.assertIn("Native goal/autopilot", body)
            self.assertEqual(front, expected)  # No models/tools/MCP/default grants.
            command = body.split("```sh\n")[1].split("\n```")[0]
            self.assertEqual(shlex.split(command),
                             [str(self.launcher), "workflow", workflow_kind, "--project", str(self.a),
                              "--harness", "copilot"])
            if kind in ("implementer", "reviewer"):
                self.assertIn("await the caller", body)
                self.assertIn("or run this locator autonomously", body)
            baseline = snapshot(self.area), snapshot(self.home)
            self.assertIn("Beads readiness: NOT CHECKED", self.run_raw(
                ["bash", "-p", "-c", command], self.b))
            self.assertEqual((snapshot(self.area), snapshot(self.home)), baseline)
        # Common ignores affect discovery in Git, not project activation.
        self.assertEqual(len(self.git(self.a, "check-ignore", *PATHS).splitlines()), 8)
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
        self.command("update", "--ref", self.legacy)
        self.host = snapshot(self.home)
        self.command("enable", self.a)
        receipt = self.receipt()
        self.assertNotIn("inventory", receipt)
        old_paths = [
            ".github/skills/domestique-v2-copilot/SKILL.md",
            ".github/skills/domestique-v2-copilot-decompose/SKILL.md",
            ".github/skills/domestique-v2-copilot-goal/SKILL.md",
            ".github/agents/domestique-v2-copilot-implementer.agent.md",
            ".github/agents/domestique-v2-copilot-reviewer.agent.md",
        ]
        self.assertEqual(set(receipt["files"]), set(old_paths))
        token = receipt["token"]
        self.assertEqual(receipt["exclusion"]["block"],
                         f"# domestique-copilot-preview BEGIN {token}\n" +
                         "".join("/" + p + "\n" for p in [*old_paths, RECEIPT]) +
                         f"# domestique-copilot-preview END {token}\n")
        goal = self.a / LEAVES["goal"]
        old_goal = goal.read_bytes()
        self.assertIn(b"disable-model-invocation: true\n", old_goal)
        self.unchanged_call("enable", self.a)
        role = self.a / LEAVES["implementer"]
        # Arbitrary user bytes (including malformed metadata) are opaque.
        role.write_bytes(b"---\nname: user override\nmodel: [unparsed\n---\n$local body ' edits\n\xff")
        edited = role.read_bytes()
        self.assertIn("customized", self.unchanged_call("enable", self.a))
        self.command("update", "--ref", self.second)
        self.host = snapshot(self.home)  # Only this explicit machine update may change it.
        self.assertIn("customized", self.unchanged_call("enable", self.a))
        self.assertEqual(self.receipt(), receipt, "creation hashes never advance after update")
        self.assertIn("legacy five-definition layout", self.unchanged_call("enable", self.a))
        inspected = self.unchanged_call("inspect", self.a)
        self.assertIn("legacy five-definition layout", inspected)
        self.assertIn("Preview activation: active", inspected)
        self.assertEqual(inspected.count(": unchanged"), 4)
        self.assertIn("UTF-8", self.unchanged_call("workflow", "goal", "--project", self.a, code=1))
        self.assertIn("UTF-8",
                      self.unchanged_call("workflow", "decompose", "--project", self.a, code=1))
        for alias in ALIASES:
            self.assertFalse((self.a / LEAVES[alias]).exists())
        unowned = self.a / LEAVES["dom-decompose"]
        unowned.parent.mkdir(parents=True)
        unowned.write_bytes(b"Unowned short-name adapter\n")
        self.assertIn("legacy five-definition layout", self.unchanged_call("enable", self.a))
        self.assertEqual(self.receipt(), receipt, "no alias adoption on legacy repeat enable")
        self.assertEqual(goal.read_bytes(), old_goal, "owned legacy metadata is not rewritten")
        self.assertEqual(role.read_bytes(), edited)
        self.unchanged_call("disable", self.a, "--dry-run", code=1)
        self.assertIn("receipt revoked", self.command("disable", self.a, code=1))
        self.assertEqual(role.read_bytes(), edited)
        self.assertEqual(self.receipt()["state"], "disabled")
        self.assertEqual(self.receipt()["files"], receipt["files"])
        self.assertFalse((self.a / LEAVES["reviewer"]).exists())
        self.assertFalse(goal.exists(), "unchanged legacy goal is removable by its creation hash")
        self.unchanged_call("enable", self.a, code=1)
        partial = self.command("disable", self.a, code=1)
        self.assertIn("customized", partial)
        self.assertEqual(role.read_bytes(), edited)
        role.unlink()  # Explicit fixture-owner cleanup of the retained local edit.
        self.command("disable", self.a)
        self.assertEqual(unowned.read_bytes(), b"Unowned short-name adapter\n")
        self.unchanged_call("enable", self.a, code=1)
        unowned.unlink()  # Fixture owner resolves the unrelated alias collision.
        unowned.parent.rmdir()
        self.command("enable", self.a)
        self.assertNotIn(b"disable-model-invocation", goal.read_bytes())
        self.assertEqual(len(self.receipt()["files"]), 7)
        self.command("disable", self.a)

    def test_public_alias_collisions_and_partial_removal(self):
        for alias in ALIASES:
            leaf = self.a / LEAVES[alias]
            leaf.parent.mkdir(parents=True)
            for collision in ("identical", "tracked", "index-only", "symlink"):
                with self.subTest(alias=alias, collision=collision):
                    if collision == "symlink":
                        leaf.symlink_to(self.a / "host.txt")
                    else:
                        leaf.write_bytes(templates(self.launcher, self.a)[LEAVES[alias]])
                    if collision in ("tracked", "index-only"):
                        self.git(self.a, "add", "--", LEAVES[alias])
                        if collision == "index-only":
                            leaf.unlink()
                    self.unchanged_call("enable", code=1)
                    self.unchanged_call("enable", "--dry-run", code=1)
                    if collision in ("tracked", "index-only"):
                        self.git(self.a, "rm", "--cached", "--", LEAVES[alias])
                    if leaf.exists() or leaf.is_symlink():
                        leaf.unlink()
            self.unchanged_call("enable", code=1)  # Empty unowned skill dir is a collision.
            leaf.parent.rmdir()
        self.command("enable")
        leaf = self.a / LEAVES["dom-goal"]
        leaf.write_bytes(leaf.read_bytes() + b"\nUser customization\n")
        edited = leaf.read_bytes()
        receipt = self.receipt()
        self.assertIn("customized", self.unchanged_call("enable"))
        self.assertEqual(self.receipt(), receipt)
        self.assertIn("customized", self.unchanged_call("inspect"))
        self.assertIn("PARTIAL", self.command("disable", code=1))
        self.assertEqual(leaf.read_bytes(), edited)
        self.assertFalse((self.a / LEAVES["dom-decompose"]).exists())
        self.assertEqual(self.receipt()["state"], "disabled")
        self.unchanged_call("disable", "--dry-run", code=1)
        self.command("disable", code=1)
        self.assertEqual(leaf.read_bytes(), edited)
        self.assertEqual(self.receipt()["files"], receipt["files"])
        leaf.unlink()  # Fixture owner explicitly resolves retained customization.
        self.command("disable")

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
        self.assertEqual(len(self.git(self.a, "check-ignore", *PATHS).splitlines()), 8)
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

    def test_role_model_writer_lifecycle(self):
        self.command("enable")
        creation = self.receipt()["files"]
        modes = {r: (self.a / LEAVES[r]).stat().st_mode for r in S.ROLES}
        message, display = setup_models(self)
        self.assertIn("Saved setup only", message)
        self.assertIn("--- " + LEAVES["implementer"], display)
        self.assertIn("current", display)
        self.assertIn(RECEIPT, display)
        for role in S.ROLES:
            path = self.a / LEAVES[role]
            entry = self.receipt()["files"][LEAVES[role]]
            self.assertEqual({k: entry[k] for k in ("identity", "sha256")}, creation[LEAVES[role]])
            self.assertEqual(entry["model_setup"]["sha256"], S.sha(path.read_bytes()))
            self.assertTrue(entry["model_setup"]["removable"])
            self.assertEqual(path.stat().st_mode, modes[role])
            self.assertIn(b'model: "fixture-openai"\n', path.read_bytes())
        self.unchanged_call("enable")
        self.assertIn("confirmed file pair", self.unchanged_call("inspect"))
        message, _ = setup_models(self, implementer="inherit", reviewer="inherit")
        for role in S.ROLES:
            self.assertNotIn(b"\nmodel:", (self.a / LEAVES[role]).read_bytes())
            self.assertTrue(self.receipt()["files"][LEAVES[role]]["model_setup"]["removable"])
        self.assertIn("fresh Copilot client", message)
        self.command("disable")
        self.assertFalse((self.a / RECEIPT).exists())
        self.assertTrue(all(not (self.a / leaf).exists() for leaf in LEAVES.values()))

    def test_role_model_customization_and_invalidation(self):
        self.command("enable")
        creation = self.receipt()["files"]
        path = self.a / LEAVES["implementer"]
        data = path.read_bytes().replace(b"---\n", b'---\ntools: ["read", "edit"]\n', 1)
        path.write_bytes(data + b"\nKeep these custom instructions.\n")
        setup_models(self, implementer='fixture-"quoted"')
        self.assertIn(b'tools: ["read", "edit"]\n', path.read_bytes())
        self.assertTrue(path.read_bytes().endswith(b"\nKeep these custom instructions.\n"))
        self.assertFalse(self.receipt()["files"][LEAVES["implementer"]]["model_setup"]["removable"])
        self.assertTrue(self.receipt()["files"][LEAVES["reviewer"]]["model_setup"]["removable"])
        self.assertIn("confirmed file pair", self.command("inspect"))
        path.write_bytes(path.read_bytes() + b"\nAnother edit.\n")
        self.assertIn("Role model setup: unconfirmed", self.command("inspect"))
        setup_models(self, implementer="inherit")
        for role in S.ROLES:
            entry = self.receipt()["files"][LEAVES[role]]
            self.assertEqual({k: entry[k] for k in ("identity", "sha256")}, creation[LEAVES[role]])
        custom = path.read_bytes()
        self.assertIn("PARTIAL", self.command("disable", code=1))
        self.assertEqual(path.read_bytes(), custom)
        self.assertFalse((self.a / LEAVES["reviewer"]).exists())

    def test_role_model_no_consent_and_unsafe_refusals(self):
        self.command("enable")
        before = snapshot(self.a)
        for kwargs in ({"consent": ""}, {"consent": "Cancel\n"}, {"consent": "yes\n"}):
            self.assertIn("Cancelled", setup_models(self, **kwargs)[0])
            self.assertEqual(snapshot(self.a), before)
        for kwargs in ({"interactive": False}, {"support": False},
                       {"reviewer": None}, {"implementer": "bad\nmodel"}):
            with self.assertRaises(Refusal):
                setup_models(self, **kwargs)
            self.assertEqual(snapshot(self.a), before)
        path = self.a / LEAVES["reviewer"]
        original = path.read_bytes()
        for bad in (b"model: one\nmodel: two\n", b"model: |\n  block\n",
                    b"tools: &anchor something\n", b"effort: high\n",
                    b"model: null\n", b'model: "embedded\\nnewline"\n',
                    b"# domestique-model-setup: {}\n"):
            path.write_bytes(original.replace(b"---\n", b"---\n" + bad, 1))
            before_bad = snapshot(self.a)
            with self.assertRaises((Refusal, ValueError)):
                setup_models(self)
            self.assertEqual(snapshot(self.a), before_bad)
        path.write_bytes(original)
        held = self.area / "held-reviewer"
        path.rename(held)
        path.write_bytes(original)
        before_bad = snapshot(self.a)
        with self.assertRaisesRegex(Refusal, "replaced identity"):
            setup_models(self)
        self.assertEqual(snapshot(self.a), before_bad)

    def test_role_model_partial_writes_and_receipt_failure(self):
        # Fresh independent activations per failure; faults wrap real publication.
        real_write, real_save = S.atomic_write, S.save
        for failure in ("invalidation", "reviewer", "implementer", "receipt"):
            root = self.area / failure
            self.repo(root)
            self.command("enable", root)
            setup_models(self, root)
            creation = json.loads((root / RECEIPT).read_bytes())["files"]
            calls = []

            def write(path, render, mode):
                calls.append(path.name)
                index = {"invalidation": 1, "reviewer": 2, "implementer": 3}.get(failure)
                if len(calls) == index:
                    raise OSError("fixture write failure")
                return real_write(path, render, mode)

            def save(path, record):
                if failure == "receipt":
                    raise OSError("fixture receipt failure")
                return real_save(path, record)

            before = snapshot(root)
            with patch.object(S, "atomic_write", side_effect=write), \
                    patch.object(S, "save", side_effect=save), \
                    self.assertRaisesRegex(Refusal, "PARTIAL role setup; changed paths:") as caught:
                setup_models(self, root, implementer="new-fixture")
            reported = json.loads(str(caught.exception).split("changed paths: ", 1)[1].split(";")[0])
            expected = ([] if failure == "invalidation" else [LEAVES["implementer"]] +
                        ([LEAVES["reviewer"]] if failure in ("implementer", "receipt") else []))
            self.assertEqual(set(reported), set(expected))
            record = json.loads((root / RECEIPT).read_bytes())
            self.assertEqual(record["files"], creation)
            if failure == "invalidation":
                self.assertEqual(snapshot(root), before)
                self.assertIn("confirmed file pair", self.command("inspect", root))
            else:
                self.assertIn("Role model setup: unconfirmed", self.command("inspect", root))
                self.command("disable", root, code=1)
                self.assertTrue((root / LEAVES["implementer"]).exists())

    def test_role_model_recheck_links_and_atomic_failure(self):
        self.command("enable")
        path = self.a / LEAVES["reviewer"]
        original = path.read_bytes()
        held = self.area / "held"
        path.rename(held)
        for linked in ("symlink", "hardlink"):
            if linked == "symlink":
                path.symlink_to(held)
            else:
                os.link(held, path)
            before = snapshot(self.a)
            with self.assertRaises(Refusal):
                setup_models(self)
            self.assertEqual(snapshot(self.a), before)
            path.unlink()
        held.rename(path)
        self.git(self.a, "add", "-f", "--", LEAVES["reviewer"])
        before = snapshot(self.a)
        with self.assertRaisesRegex(Refusal, "tracked"):
            setup_models(self)
        self.assertEqual(snapshot(self.a), before)
        self.git(self.a, "rm", "--cached", "--", LEAVES["reviewer"])
        real_context = S.context
        count = 0

        def changing_context(*args):
            nonlocal count
            count += 1
            if count == 2:
                path.write_bytes(original + b"\nConcurrent fixture edit\n")
            return real_context(*args)

        with patch.object(S, "context", side_effect=changing_context), \
                self.assertRaisesRegex(Refusal, "inputs changed during consent"):
            setup_models(self)
        self.assertEqual(path.read_bytes(), original + b"\nConcurrent fixture edit\n")
        self.assertNotIn("model_setup", self.receipt()["files"][LEAVES["implementer"]])
        path.write_bytes(original)
        before = snapshot(self.a)
        with patch.object(os, "replace", side_effect=OSError("atomic fixture failure")), \
                self.assertRaisesRegex(Refusal, r"changed paths: \[\]"):
            setup_models(self)
        self.assertEqual(snapshot(self.a), before, "failed temp publication cleans only its own temp")

    def test_y_role_models_legacy_receipt(self):
        self.command("update", "--ref", self.legacy)
        self.host = snapshot(self.home)
        self.command("enable")
        before = self.receipt()
        native = {k: (self.a / leaf).read_bytes() for k, leaf in LEAVES.items()
                  if (self.a / leaf).exists() and k not in S.ROLES}
        self.command("update", "--ref", self.second)
        self.host = snapshot(self.home)
        setup_models(self, implementer="inherit", reviewer="inherit")
        after = self.receipt()
        self.assertNotIn("inventory", after)
        self.assertEqual(after["exclusion"], before["exclusion"])
        for leaf, entry in before["files"].items():
            self.assertEqual({k: after["files"][leaf][k] for k in entry}, entry)
        for kind, data in native.items():
            self.assertEqual((self.a / LEAVES[kind]).read_bytes(), data)
        for alias in ALIASES:
            self.assertFalse((self.a / LEAVES[alias]).exists())
        self.unchanged_call("enable")
        self.assertIn("confirmed file pair", self.unchanged_call("inspect"))
        self.command("disable")


if __name__ == "__main__":
    unittest.main(verbosity=2)
