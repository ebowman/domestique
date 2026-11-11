"""Offline current-candidate projection tests; never native qualification."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest

DOM = Path(sys.argv.pop(1)).resolve()
WORK = Path(sys.argv.pop(1))
ROLES = {
    role: f".github/agents/domestique-v2-copilot-{role}.agent.md"
    for role in ("implementer", "reviewer")
}
SHARED = ".agents/skills/dom-goal/SKILL.md"
STATE = ".github/.domestique"
MARKER = "# domestique-model-setup: "
OLD_ROLES = Path(__file__).parent / "fixtures/copilot-9f33930"
DELEGATED = "This delegated role inherits Copilot routing"
DESCRIPTION_GUARDS = {
    "codex": "Codex only; never match in another harness.",
    "copilot": "Copilot only; never match in Claude, Codex or an unknown harness.",
}


def snapshot(root):
    return {
        str(p.relative_to(root)): (p.lstat().st_mode, p.read_bytes())
        for p in root.rglob("*") if p.is_file() and not p.is_symlink()
    }


class Copilot(unittest.TestCase):
    def setUp(self):
        # Retain prior runs for diagnosis; never reuse or clean caller-owned paths.
        self.work = Path(tempfile.mkdtemp(prefix=self._testMethodName + "-", dir=WORK)).resolve()
        self.root = self.work / "project"
        self.root.mkdir()
        self.git("init", "-q")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args],
                              capture_output=True, text=True)

    def run_dom(self, *flags, ok=True, env=None, dom=DOM):
        result = subprocess.run(["bash", str(dom), str(self.root), *flags],
                                capture_output=True, text=True, env=env)
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def run_dom_unconfirmed(self, *flags, dom=DOM):
        # Custom native model fields make the pair custom-unconfirmed/stale, so
        # since 3d1a3d3 (hq-c6o.4) a run exits 3 until dom-models --confirm
        # (README, install-upgrade-design). Exit 3 must come only from that
        # reconfirmation, never from a real file conflict or refusal.
        result = self.run_dom(*flags, dom=dom, ok=False)
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn("reconfirmation-required", result.stdout)
        self.assertIn("dom-models --confirm", result.stdout + result.stderr)
        self.assertNotIn("Conflicted:", result.stdout)
        return result

    def install(self, *flags, **kwargs):
        return self.run_dom("--platform", "copilot", *flags, **kwargs)

    def hidden(self, path):
        return self.git("check-ignore", "-q", path).returncode == 0

    def test_setup_reused_workroot_preserves_prior_results(self):
        self.install("--guest")
        (self.root / "prior-result").write_text("keep prior project\n")
        for name in ("outside-role", "conflict-dom.sh"):
            (self.work / name).write_text("keep prior fixture\n")
        before = snapshot(self.work)

        repeated = type(self)(self._testMethodName)
        repeated.setUp()
        self.assertEqual(repeated.work.parent, WORK.resolve())
        self.assertNotEqual(repeated.work, self.work)
        self.assertFalse((repeated.root / "prior-result").exists())
        self.assertFalse((repeated.root / STATE).exists())
        for name in ("outside-role", "conflict-dom.sh"):
            self.assertFalse((repeated.work / name).exists())
            (repeated.work / name).write_text("independent new fixture\n")
        repeated.install("--guest")
        for case in (self, repeated):
            marker = json.loads(next(
                line[len(MARKER):] for line in
                (case.root / ROLES["implementer"]).read_text().splitlines()
                if line.startswith(MARKER)))
            self.assertEqual(marker["project"], str(case.root.resolve()))
        self.assertEqual(snapshot(self.work), before)

    def test_install_native_contents_and_routing(self):
        # A restricted PATH proves missing Copilot does not block installation.
        bindir = self.work / "bin"
        bindir.mkdir()
        python = bindir / "python3"
        python.symlink_to(sys.executable)
        env = dict(os.environ, PATH=f"{bindir}:/usr/bin:/bin:/usr/sbin:/sbin")
        self.assertIsNone(shutil.which("copilot", path=env["PATH"]))
        result = self.install(env=env)
        self.assertIn("native readiness is NOT established", result.stdout)
        for role, rel in ROLES.items():
            body = (self.root / rel).read_text()
            self.assertIn(f"name: domestique-v2-copilot-{role}\n", body)
            self.assertIn("description: Copilot only;", body)
            self.assertNotIn("\nmodel:", body)
            self.assertEqual(MARKER in body, role == "implementer")
            tools = '["read", "edit", "search", "execute"]' if role == "implementer" else '["read", "search", "execute"]'
            self.assertIn(f"tools: {tools}", body)
        for kind in ("decompose", "goal"):
            alias = (self.root / f".agents/skills/dom-{kind}/SKILL.md").read_text()
            self.assertIn(f".github/skills/domestique-v2-copilot-{kind}/SKILL.md", alias)
            self.assertIn("Preserve the ORIGINAL user request verbatim", alias)
            self.assertIn("Installed directories", alias)
            self.assertFalse((self.root / f".github/skills/dom-{kind}").exists())
        for p in self.root.rglob("*.md"):
            text = p.read_text()
            for forbidden in (str(DOM.parent), "preview/launcher", "--confirm-model",
                              "workflow --project", "machine-root", "current/bin"):
                self.assertNotIn(forbidden, text)
        self.assertFalse((self.root / ".claude").exists())
        self.assertFalse((self.root / ".codex").exists())
        self.assertFalse(self.hidden(SHARED))

    def test_setup_and_readiness_protocol(self):
        self.install()
        for kind in ("decompose", "goal"):
            text = (self.root / f".github/skills/domestique-v2-copilot-{kind}/SKILL.md").read_text()
            for required in (
                "copilot read-only execution gate", "NO questionnaire and NO writes",
                "exact physical Git worktree root", "BOTH marker hashes",
                "Visible default values without a valid marker are NOT confirmation",
                "Fresh defaults omit model in BOTH roles", "native resolution",
                "not necessarily the direct parent's model",
                "/dom-models --confirm", "/dom-models --configure",
                "exec(compile(code", "assert code == read(base)",
                "not a freshly installed role already registered",
                "independent inherited-model attestation", "MUST NOT block",
                "Genuinely unknown required registration/discovery",
                "known unavailable/unsupported selection",
                "Never substitute another model", "conflicting spawn",
            ):
                self.assertIn(required, text)
            self.assertNotIn("Save these choices?", text)
            self.assertNotIn("questionnaire INLINE", text)
        ordinary = (self.root / ".github/skills/domestique-v2-copilot/SKILL.md").read_text()
        self.assertIn("no ordinary/bootstrap questionnaire", ordinary)
        self.assertIn("one explicitly assigned bounded bead", ordinary)
        self.assertIn("explicitly read the native goal body", ordinary)
        self.assertLess(ordinary.index("## Goal intent routing"),
                        ordinary.index("## Read-only role gate"))
        goal = (self.root / ".github/skills/domestique-v2-copilot-goal/SKILL.md").read_text()
        self.assertIn("clear user execution request or native named objective", goal)
        self.assertNotIn("Default bound is ONE", goal)
        self.assertNotIn("native /goal or /autopilot is not", goal)
        for role, rel in ROLES.items():
            body = (self.root / rel).read_text()
            self.assertNotIn("## Goal intent routing", body)
            self.assertIn(DELEGATED, body)

    def test_old_role_guard_upgrade_preserves_custom_pair(self):
        # Bounded pristine role bytes from 9f339305a4f900176b647248f68907499dcc0620.
        # Seed only the two owned role snapshots, as in old-inventory helper tests.
        # Installed helper review/Save confirms filesystem bytes, NOT native consent.
        parent = self.root
        for mode in ("normal", "guest"):
            for custom in (False, True):
                with self.subTest(mode=mode, custom=custom):
                    self.root = parent / f"{mode}-{custom}"
                    self.root.mkdir()
                    self.git("init", "-q")
                    self.install(*(["--guest"] if mode == "guest" else []))
                    current = {r: (self.root / STATE / "base" / rel).read_text()
                               for r, rel in ROLES.items()}
                    pair = {}
                    for role, rel in ROLES.items():
                        old = (OLD_ROLES / f"{role}.agent.md").read_text()
                        (self.root / STATE / "base" / rel).write_text(old)
                        if custom:
                            old = old.replace("\n---\n", '\nmodel: "custom-native-id"\n'
                                              'custom: "retained"\n---\n', 1)
                            old = old.replace('"search", "execute"', '"search"')
                            old = old.replace("an unknown harness.", "an unknown harness. Custom discovery.", 1)
                            old += "\nUser-owned instructions.\n"
                        pair[role] = old
                    for role, rel in ROLES.items():
                        (self.root / rel).write_text(pair[role])
                    models = self.root / ".github/skills/domestique-v2-copilot-models/SKILL.md"
                    bootstrap = models.read_text().split("```python\n", 1)[1].split("\n```", 1)[0]

                    def helper(*args, plan=None):
                        result = subprocess.run(
                            [sys.executable, "-I", "-B", "-Werror", "-c", bootstrap, *args],
                            input=json.dumps(plan) if plan is not None else None,
                            cwd=self.root, text=True, capture_output=True)
                        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                        return json.loads(result.stdout)

                    before = snapshot(self.root)
                    if custom:
                        # Current-inventory custom roles must await Save unchanged;
                        # legacy guard migration is a separate, qualified step.
                        self.run_dom_unconfirmed("--platform", "copilot", "--dry-run")
                        self.assertEqual(snapshot(self.root), before)
                        self.run_dom_unconfirmed("--platform", "copilot")
                        self.assertEqual(snapshot(self.root), before)
                    review = helper("request", "--confirm")
                    self.assertFalse(review["configured"])
                    selected = {r: {"model": "custom-native-id" if custom else None,
                                    "effort": None} for r in ROLES}
                    self.assertEqual(review["chosen"], selected)
                    self.assertEqual(review["current"], selected)
                    self.assertEqual(snapshot(self.root), before)
                    self.assertTrue(helper(
                        "apply", review["digest"], plan=review["plan"])["confirmed"])
                    marker = json.loads(next(
                        line[len(MARKER):] for line in
                        (self.root / ROLES["implementer"]).read_text().splitlines()
                        if line.startswith(MARKER)))
                    for role, rel in ROLES.items():
                        clean = "".join(line for line in (self.root / rel).read_text().splitlines(True)
                                        if not line.startswith(MARKER))
                        self.assertEqual(clean, pair[role])
                        self.assertEqual(marker[role + "_sha256"],
                                         hashlib.sha256(clean.encode()).hexdigest())
                        self.assertEqual((self.root / STATE / "base" / rel).read_text(),
                                         (OLD_ROLES / f"{role}.agent.md").read_text())
                    before = snapshot(self.root)
                    self.install("--dry-run")
                    self.assertEqual(snapshot(self.root), before)
                    self.install()
                    for role, rel in ROLES.items():
                        path = self.root / rel
                        text = path.read_text()
                        self.assertIn(DELEGATED, text)
                        self.assertNotIn("Before applying ANY instructions below", text)
                        # 2264890 (hq-xc2.3) adds ownership handoff and revises
                        # the delegated task. Compare current emitter + ALL edits.
                        expected = current[role]
                        if custom:
                            expected = expected.replace(
                                "\n---\n", '\nmodel: "custom-native-id"\n'
                                'custom: "retained"\n---\n', 1)
                            expected = expected.replace('"search", "execute"', '"search"')
                            expected = expected.replace(
                                "an unknown harness.", "an unknown harness. Custom discovery.", 1)
                            expected += "\nUser-owned instructions.\n"
                            self.assertIn('model: "custom-native-id"', text)
                            self.assertIn('custom: "retained"', text)
                            self.assertIn("Custom discovery.", text)
                            self.assertNotIn('"execute"', text)
                        clean = "".join(line for line in text.splitlines(keepends=True)
                                        if not line.startswith(MARKER))
                        self.assertEqual(clean, expected)
                        if role == "implementer":
                            self.assertIn("## Child bead ownership handoff\n", clean)
                        self.assertNotEqual(hashlib.sha256(clean.encode()).hexdigest(),
                                            marker[role + "_sha256"])
                        self.assertEqual((self.root / STATE / "base" / rel).read_text(),
                                         current[role])
                    renewed = next(line for line in
                                   (self.root / ROLES["implementer"]).read_text().splitlines()
                                   if line.startswith(MARKER))
                    saved = json.loads(renewed[len(MARKER):])
                    for role, rel in ROLES.items():
                        clean = "".join(line for line in (self.root / rel).read_text().splitlines(True)
                                        if not line.startswith(MARKER))
                        self.assertEqual(saved[role + "_sha256"],
                                         hashlib.sha256(clean.encode()).hexdigest())
                    upgraded = snapshot(self.root)
                    self.assertTrue(helper("verify")["confirmed"])
                    self.assertEqual(helper("verify")["selected"], selected)
                    self.install()
                    self.assertEqual(snapshot(self.root), upgraded)

    def test_role_guard_migration_and_current_tampering_refuse_atomically(self):
        parent = self.root
        for mode in ("normal", "guest"):
            for role, rel in ROLES.items():
                for generation in ("old", "current"):
                    kinds = ("removed", "tampered", "quoted", "malformed",
                             "unowned", "tampered-base")
                    if generation == "current":
                        kinds += ("legacy-live-on-delegated-base",)
                    for kind in kinds:
                        for flags in ((), ("--force", "--dry-run")):
                            with self.subTest(mode=mode, role=role, generation=generation,
                                              kind=kind, flags=flags):
                                # Each invocation gets its own real installation:
                                # even an unexpected successful write cannot seed
                                # another role, mutation or flags variant.
                                variant = "force-dry-run" if flags else "normal"
                                self.root = parent / f"{mode}-{role}-{generation}-{kind}-{variant}"
                                self.root.mkdir()
                                self.git("init", "-q")
                                self.install(*(["--guest"] if mode == "guest" else []))
                                path = self.root / rel
                                base = self.root / STATE / "base" / rel
                                current = path.read_text()
                                pristine = base.read_text()
                                self.assertNotIn(MARKER, pristine)
                                legacy = (OLD_ROLES / f"{role}.agent.md").read_text()
                                source = legacy if generation == "old" else current
                                baseline = legacy if generation == "old" else pristine
                                prefix, task = source.split("Delegated role only:", 1)
                                front, guard = prefix.split("\n## Active harness boundary", 1)
                                guard = "\n## Active harness boundary" + guard
                                mutations = {
                                    "removed": front + "Delegated role only:" + task,
                                    "tampered": source.replace("STOP", "CONTINUE", 1),
                                    "quoted": front + "Delegated role only:" + task + "\n```text\n" + guard + "```\n",
                                    "legacy-live-on-delegated-base": legacy,
                                    "malformed": source.replace("---\n", "BROKEN\n", 1),
                                    "unowned": source,
                                    "tampered-base": source,
                                }
                                path.write_text(mutations[kind])
                                # Pristine authority comes only from the actual
                                # installation or the historical fixture, never
                                # from the live implementer's confirmed bytes.
                                base.write_text(baseline)
                                if kind == "unowned":
                                    base.unlink()
                                elif kind == "tampered-base":
                                    base.write_text(baseline.replace("STOP", "CONTINUE", 1))
                                before = snapshot(self.root)
                                directories = {p.relative_to(self.root) for p in self.root.rglob("*")
                                               if p.is_dir()}
                                result = self.install(*flags, ok=False)
                                self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
                                self.assertIn("no project writes", result.stderr.lower())
                                lowered = result.stderr.lower()
                                # Every refusal carries some repair guidance;
                                # the lifecycle preflight must say what is
                                # wrong, what to restore, and which file.
                                self.assertTrue(
                                    any(w in lowered for w in ("repair", "restore", "reconcile")),
                                    result.stderr)
                                if "Model lifecycle refused" in result.stderr:
                                    self.assertIn("missing native body guard", result.stderr)
                                    self.assertIn("restore", lowered)
                                    self.assertIn("reconcile", lowered)
                                    self.assertIn(rel, result.stderr)
                                    if kind == "tampered-base":
                                        self.assertIn(f"./{STATE}/base/{rel}", result.stderr)
                                        self.assertIn("original pristine snapshot", result.stderr)
                                        self.assertIn("not current upstream", result.stderr)
                                        self.assertIn("historical base is merge authority", result.stderr)
                                    else:
                                        self.assertIn("## Active harness boundary (copilot only)", result.stderr)
                                        self.assertIn("start of the role body", result.stderr)
                                self.assertEqual(snapshot(self.root), before)
                                self.assertEqual(directories, {
                                    p.relative_to(self.root) for p in self.root.rglob("*") if p.is_dir()})

    def test_entry_base_with_confirmed_delegated_live_preserves_pair(self):
        # 75b0de3 introduced entry -> delegated migration; da7f4be explicitly
        # accepts delegated live roles over retained entry-era bases after Save.
        # This is not the reverse (legacy live over delegated base) refusal above.
        parent = self.root

        def tree():
            return {
                str(p.relative_to(self.root)): (
                    p.lstat().st_mode, p.lstat().st_mtime_ns, p.lstat().st_ino,
                    os.readlink(p) if p.is_symlink() else p.read_bytes() if p.is_file() else None)
                for p in self.root.rglob("*")
            }

        for mode in ("normal", "guest"):
            for role, rel in ROLES.items():
                for custom in (False, True):
                    for flags in ((), ("--force", "--dry-run")):
                        with self.subTest(mode=mode, role=role, custom=custom, flags=flags):
                            variant = "force-dry-run" if flags else "normal"
                            self.root = parent / f"{mode}-{role}-{custom}-{variant}"
                            self.root.mkdir()
                            self.git("init", "-q")
                            self.install(*(["--guest"] if mode == "guest" else []))
                            pristine = {r: (self.root / STATE / "base" / p).read_bytes()
                                        for r, p in ROLES.items()}
                            models = self.root / ".github/skills/domestique-v2-copilot-models/SKILL.md"
                            bootstrap = models.read_text().split("```python\n", 1)[1].split("\n```", 1)[0]

                            def helper(*args, plan=None):
                                result = subprocess.run(
                                    [sys.executable, "-I", "-B", "-Werror", "-c", bootstrap, *args],
                                    input=json.dumps(plan) if plan is not None else None,
                                    cwd=self.root, text=True, capture_output=True)
                                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                                return json.loads(result.stdout)

                            if custom:
                                path = self.root / rel
                                # Keep the scalar at an unchanged header boundary;
                                # force need not guess its position beside removed metadata.
                                text = path.read_text().replace(
                                    "\nname:", f'\nmodel: "fixture-{role}"\nname:', 1)
                                text = text.replace("\n---\n", '\ncustom: "retained"\n---\n', 1)
                                text = text.replace('"search", "execute"', '"search"')
                                text = text.replace("an unknown harness.",
                                                    "an unknown harness. Local discovery.", 1)
                                path.write_text(text + "\nLocal role instructions.\n")
                                self.assertFalse(helper("verify")["confirmed"])
                                before = tree()
                                review = helper("request", "--confirm")
                                self.assertFalse(review["configured"])
                                self.assertEqual(tree(), before)
                                self.assertTrue(helper(
                                    "apply", review["digest"], plan=review["plan"])["confirmed"])
                            selected = {r: {"model": f"fixture-{r}" if custom and r == role else None,
                                            "effort": None} for r in ROLES}
                            live = {p: (self.root / p).read_bytes() for p in ROLES.values()}
                            base = self.root / STATE / "base" / rel
                            legacy = (OLD_ROLES / f"{role}.agent.md").read_bytes()
                            self.assertIn(b"Before applying ANY instructions below", legacy)
                            self.assertNotIn(MARKER.encode(), legacy)
                            base.write_bytes(legacy)
                            for data in live.values():
                                self.assertIn(DELEGATED.encode(), data)
                                self.assertNotIn(b"Before applying ANY instructions below", data)
                            verified = helper("verify")
                            self.assertTrue(verified["confirmed"])
                            self.assertEqual(verified["selected"], selected)

                            before = tree()
                            result = self.install(*(flags or ("--dry-run",)))
                            self.assertIn("[model pair] copilot: confirmed -> configured locally", result.stdout)
                            for r, choice in selected.items():
                                model = json.dumps(choice["model"]) if choice["model"] else "native inheritance"
                                display = model + "; effort inherited/omitted"
                                self.assertIn(
                                    f"[model selection] copilot:{r}: {display} -> {display} [preserved-existing]",
                                    result.stdout)
                            self.assertNotIn("[model publication]", result.stdout)
                            self.assertEqual(tree(), before)
                            self.assertEqual(helper("verify"), verified)
                            expected = snapshot(self.root)
                            expected[str(base.relative_to(self.root))] = (
                                base.lstat().st_mode, pristine[role])
                            # Publish without force even after a force preview: local
                            # bodies/settings survive, only pristine authority advances.
                            result = self.install()
                            self.assertIn("[model pair] copilot: confirmed -> configured locally", result.stdout)
                            self.assertIn("[model publication] copilot:configured", result.stdout)
                            self.assertEqual(snapshot(self.root), expected)
                            self.assertEqual(live, {p: (self.root / p).read_bytes() for p in ROLES.values()})
                            self.assertEqual(helper("verify"), verified)
                            for r, p in ROLES.items():
                                self.assertEqual((self.root / STATE / "base" / p).read_bytes(), pristine[r])
                            stable = tree()
                            self.install()
                            self.assertEqual(tree(), stable)
                            self.assertEqual(helper("verify"), verified)

    def test_invalid_pristine_role_guard_with_confirmed_current_live(self):
        parent = self.root
        for role, rel in ROLES.items():
            for kind in ("tampered-entry", "missing-delegated"):
                for flags in ((), ("--force", "--dry-run")):
                    with self.subTest(role=role, kind=kind, flags=flags):
                        variant = "force-dry-run" if flags else "normal"
                        self.root = parent / f"{role}-{kind}-{variant}"
                        self.root.mkdir()
                        self.git("init", "-q")
                        self.install()
                        base = self.root / STATE / "base" / rel
                        if kind == "tampered-entry":
                            original = (OLD_ROLES / f"{role}.agent.md").read_text()
                            base.write_text(original.replace("STOP", "CONTINUE", 1))
                        else:
                            original = base.read_text()
                            front = original.split("\n## Active harness boundary", 1)[0]
                            task = original.split("Delegated role only:", 1)[1]
                            base.write_text(front + "\nDelegated role only:" + task)
                        # The live pair still has its valid installed confirmation
                        # and delegated guard; neither authorizes a damaged base.
                        before = snapshot(self.root)
                        directories = {p.relative_to(self.root) for p in self.root.rglob("*")
                                       if p.is_dir()}
                        result = self.install(*flags, ok=False)
                        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
                        self.assertIn("pristine base", result.stderr)
                        self.assertIn(f"{STATE}/base/{rel}", result.stderr)
                        self.assertIn("original pristine snapshot", result.stderr)
                        self.assertIn("no project writes", result.stderr.lower())
                        self.assertEqual(snapshot(self.root), before)
                        self.assertEqual(directories, {
                            p.relative_to(self.root) for p in self.root.rglob("*") if p.is_dir()})

    def test_known_entry_role_base_preserves_confirmation_contract(self):
        parent = self.root
        for mode in ("normal", "guest"):
            for custom in (False, True):
                with self.subTest(mode=mode, custom=custom):
                    self.root = parent / f"{mode}-{custom}"
                    self.root.mkdir()
                    self.git("init", "-q")
                    self.install(*(["--guest"] if mode == "guest" else []))
                    bases = {}
                    for role, rel in ROLES.items():
                        old = (OLD_ROLES / f"{role}.agent.md").read_bytes()
                        bases[role] = old
                        (self.root / STATE / "base" / rel).write_bytes(old)
                        local = old + (b"\nUser-owned instructions.\n" if custom else b"")
                        (self.root / rel).write_bytes(local)
                    before = snapshot(self.root)
                    if custom:
                        self.run_dom_unconfirmed("--platform", "copilot", "--dry-run")
                        self.assertEqual(snapshot(self.root), before)
                        self.run_dom_unconfirmed("--platform", "copilot")
                        # A current-inventory custom pair awaits explicit Save,
                        # rather than gaining confirmation through guard migration.
                        self.assertEqual(snapshot(self.root), before)
                        models = self.root / ".github/skills/domestique-v2-copilot-models/SKILL.md"
                        bootstrap = models.read_text().split("```python\n", 1)[1].split("\n```", 1)[0]

                        def helper(*args, plan=None):
                            result = subprocess.run(
                                [sys.executable, "-I", "-B", "-Werror", "-c", bootstrap, *args],
                                input=json.dumps(plan) if plan is not None else None,
                                cwd=self.root, text=True, capture_output=True)
                            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                            return json.loads(result.stdout)

                        review = helper("request", "--confirm")
                        self.assertFalse(review["configured"])
                        self.assertEqual(snapshot(self.root), before)
                        self.assertTrue(helper(
                            "apply", review["digest"], plan=review["plan"])["confirmed"])
                        for role, rel in ROLES.items():
                            self.assertEqual((self.root / STATE / "base" / rel).read_bytes(), bases[role])
                    before = snapshot(self.root)
                    self.install("--dry-run")
                    self.assertEqual(snapshot(self.root), before)
                    self.install()
                    for role, rel in ROLES.items():
                        text = (self.root / rel).read_text()
                        self.assertIn(DELEGATED, text)
                        self.assertNotIn("Before applying ANY instructions below", text)
                        self.assertEqual("User-owned instructions." in text, custom)
                    if custom:
                        self.assertTrue(helper("verify")["confirmed"])
                        # A retained, intact entry-era base is also legitimate
                        # after migration/Save when the live role is delegated.
                        live = {rel: (self.root / rel).read_bytes() for rel in ROLES.values()}
                        for role, rel in ROLES.items():
                            (self.root / STATE / "base" / rel).write_bytes(bases[role])
                        self.install()
                        self.assertEqual(live, {
                            rel: (self.root / rel).read_bytes() for rel in ROLES.values()})
                        self.assertTrue(helper("verify")["confirmed"])

    def test_rerun_merge_marker_and_modified_removal(self):
        self.install()
        pair = {}
        for role, rel in ROLES.items():
            path = self.root / rel
            text = "".join(line for line in path.read_text().splitlines(True)
                           if not line.startswith(MARKER))
            text = text.replace("\n---\n", '\nmodel: "custom-native-id"\ncustom: "retained"\n---\n', 1)
            line = next(s for s in text.splitlines() if s.startswith("description:"))
            text = text.replace(line, "description: " + json.dumps(
                DESCRIPTION_GUARDS["copilot"] + f" Custom {role} discovery text."))
            text = text.replace('"search", "execute"', '"search"')
            text += "\nUser-owned instructions.\n"
            pair[role] = text.encode()
            path.write_bytes(pair[role])
        marker = dict(v=1, project=str(self.root.resolve()), harness="copilot")
        marker.update({r + "_sha256": hashlib.sha256(data).hexdigest()
                       for r, data in pair.items()})
        path = self.root / ROLES["implementer"]
        path.write_bytes(b"---\n" + (MARKER + json.dumps(marker) + "\n").encode() + pair["implementer"][4:])
        before = {r: (self.root / p).read_bytes() for r, p in ROLES.items()}
        self.install()
        for role, rel in ROLES.items():
            self.assertEqual((self.root / rel).read_bytes(), before[role])
        # A qualified pair's preserving upgrade renews its final-byte marker.
        revised = self.work / "revised-dom.sh"
        revised.write_text(DOM.read_text().replace(
            "Return a terse summary: files changed, actual validation/results, discovered",
            "Return a brief summary: files changed, actual validation/results, discovered"))
        self.install(dom=revised)
        changed = (self.root / ROLES["implementer"]).read_text()
        self.assertIn("Return a brief summary:", changed)
        self.assertIn('custom: "retained"', changed)
        self.assertIn("Custom implementer discovery text.", changed)
        self.assertIn('tools: ["read", "edit", "search"]', changed)
        saved = json.loads(next(line[len(MARKER):] for line in changed.splitlines()
                                if line.startswith(MARKER)))
        clean = "".join(line for line in changed.splitlines(keepends=True)
                        if not line.startswith(MARKER)).encode()
        self.assertNotEqual(hashlib.sha256(clean).hexdigest(), marker["implementer_sha256"])
        self.assertEqual(hashlib.sha256(clean).hexdigest(), saved["implementer_sha256"])
        self.assertEqual(hashlib.sha256((self.root / ROLES["reviewer"]).read_bytes()).hexdigest(),
                         saved["reviewer_sha256"])
        tree = snapshot(self.root)
        self.install("--uninstall", "--dry-run", dom=revised)
        self.assertEqual(snapshot(self.root), tree)
        self.install("--uninstall", dom=revised)
        self.assertFalse((self.root / STATE).exists())
        self.assertFalse((self.root / SHARED).exists())
        for rel in ROLES.values():
            self.assertEqual(len(list((self.root / rel).parent.glob(Path(rel).name + ".uninstalled.*"))), 1)

    def test_guest_repeat_merge_dry_run_and_conversion(self):
        host = self.root / ".github/copilot-instructions.md"
        host.parent.mkdir()
        host.write_text("Tracked host policy\n")
        self.git("add", "--", ".github/copilot-instructions.md")
        before = host.read_bytes()
        self.install("--guest")
        self.assertEqual(host.read_bytes(), before)
        self.assertTrue(self.hidden(SHARED))
        self.assertTrue(self.hidden(ROLES["implementer"]))
        self.assertFalse(self.hidden(".github/issues/host.md"))
        tree = snapshot(self.root)
        self.install()  # Copilot-only idempotency; default-all is covered separately.
        self.assertEqual(snapshot(self.root), tree)
        self.install("--dry-run")
        self.assertEqual(snapshot(self.root), tree)
        self.install("--no-guest")
        self.assertFalse(self.hidden(SHARED))
        self.assertFalse(self.hidden(ROLES["implementer"]))
        self.assertIn("Tracked host policy", host.read_text())
        self.install("--uninstall")
        self.assertEqual(host.read_bytes(), before)

    def test_custom_native_descriptions_and_fields_upgrade_with_guards(self):
        # Real snapshot merges, including selector-less retained Codex checks.
        # Custom discovery text retains its own guard as well as the body guard.
        upstream = DOM.read_text()
        changes = {
            "Return a terse summary: files changed, actual validation/results, discovered":
                "Return a brief summary: files changed, actual validation/results, discovered",
            "- Stay inside the brief. Do not refactor adjacent code or start another bead.":
                "- Stay inside the brief. Do not refactor adjacent code or start another bead. (v2)",
        }
        for old, new in changes.items():
            self.assertEqual(upstream.count(old), 1)
            upstream = upstream.replace(old, new)
        revised = self.work / "custom-descriptions-upgrade.sh"
        revised.write_text(upstream)
        parent = self.root
        for mode in ("normal", "guest"):
            with self.subTest(mode=mode):
                self.root = parent / mode
                self.root.mkdir()
                self.git("init", "-q")
                flags = ("--guest",) if mode == "guest" else ()
                self.run_dom("--platform", "codex", *flags)
                self.install(*flags)
                expected = {}
                for role in ("implementer", "reviewer"):
                    for harness in ("codex", "copilot"):
                        rel = ROLES[role] if harness == "copilot" else f".codex/agents/{role}.toml"
                        path = self.root / rel
                        text = path.read_text()
                        description = (
                            DESCRIPTION_GUARDS[harness] +
                            f" Host-specific {harness} {role} description"
                        )
                        line = next(s for s in text.splitlines() if s.startswith("description"))
                        if harness == "copilot":
                            text = text.replace(line, "description: " + json.dumps(description))
                            text = text.replace('\n---\n', '\nmodel: "fixture-native-id"\ncustom: "keep"\n---\n', 1)
                            text = text.replace('"search", "execute"', '"search"')
                            text += "\nHost role instructions.\n"
                        else:
                            text = text.replace(line, "description = " + json.dumps(description))
                            line = next(s for s in text.splitlines() if s.startswith("model = "))
                            text = text.replace(line, 'model = "fixture-native-id"')
                            text += '\n[fixture]\nkeep = "host metadata"\n'
                            self.assertEqual(tomllib.loads(text)["description"], description)
                        path.write_text(text)
                        expected[rel] = text
                self.run_dom_unconfirmed()
                for rel, text in expected.items():
                    self.assertEqual((self.root / rel).read_text(), text)
                # Customized roles are custom-unconfirmed: model plans only merge
                # qualified/historical pairs (domestique.sh Model setup prepare,
                # 3d1a3d3 hq-c6o.4; install-upgrade-design "Preserving upgrades"),
                # so an upstream body revision must leave every custom byte
                # untouched until dom-models --confirm, not merge or conflict.
                before_revised = snapshot(self.root)
                self.run_dom_unconfirmed(dom=revised)
                self.assertEqual(snapshot(self.root), before_revised)
                for rel, text in expected.items():
                    self.assertEqual((self.root / rel).read_text(), text)
                    for new in changes.values():
                        self.assertNotIn(new, text)
                # Even with a customized description, removing the body boundary
                # must refuse before changing any file/mode/base/exclusion.
                for rel, guard in (
                    (ROLES["implementer"], "An explicit foreign-harness invocation must STOP"),
                    (".codex/agents/implementer.toml",
                     "ambiguous callers stop without work. Installed directories do not identify it."),
                ):
                    path = self.root / rel
                    original = path.read_text()
                    self.assertIn(guard, original)
                    path.write_text(original.replace(guard, "REMOVED CALLER BOUNDARY"))
                    before = snapshot(self.root)
                    refused = self.run_dom(dom=revised, ok=False)
                    # Not the generic reconfirmation exit: the missing caller
                    # boundary itself must be named as the refusal.
                    self.assertIn("Model lifecycle refused", refused.stderr)
                    self.assertIn("body guard", refused.stderr)
                    self.assertEqual(snapshot(self.root), before)
                    path.write_text(original)

    def test_native_discovery_description_refuses_without_writes(self):
        # Direct installer regression: body guards are intact throughout.
        # Check the entire project, including .git/info/exclude and snapshots,
        # not just the customized role. Force cannot authorize guard repair.
        parent = self.root
        for mode in ("normal", "guest"):
            self.root = parent / mode
            self.root.mkdir()
            self.git("init", "-q")
            flags = ("--guest",) if mode == "guest" else ()
            self.run_dom("--platform", "codex", *flags)
            self.install(*flags)
            for harness in ("codex", "copilot"):
                for role in ("implementer", "reviewer"):
                    rel = ROLES[role] if harness == "copilot" else f".codex/agents/{role}.toml"
                    path = self.root / rel
                    original = path.read_text()
                    line = next(s for s in original.splitlines() if s.startswith("description"))
                    for description in (
                        "Use only in Claude",
                        "Use Codex for this Copilot role" if harness == "copilot"
                        else "Use Copilot for this Codex role",
                        f"Host-specific {role} description",
                        f"{harness.title()} only; custom text without the full boundary.",
                        "Custom text before " + DESCRIPTION_GUARDS[harness],
                        "",
                    ):
                        field = "description: " if harness == "copilot" else "description = "
                        path.write_text(original.replace(line, field + json.dumps(description)))
                        before = snapshot(self.root)
                        directories = {p.relative_to(self.root) for p in self.root.rglob("*") if p.is_dir()}
                        for flags in ((), ("--force",), ("--dry-run",),
                                      ("--force", "--dry-run"), ("--no-guest",),
                                      ("--platform", harness)):
                            with self.subTest(mode=mode, harness=harness, role=role,
                                              description=description, flags=flags):
                                result = self.run_dom(*flags, ok=False)
                                self.assertEqual(result.returncode, 3)
                                self.assertIn("discovery description", result.stderr)
                                self.assertIn(DESCRIPTION_GUARDS[harness], result.stderr)
                                self.assertIn(rel, result.stderr)
                                self.assertIn("no project writes", result.stderr.lower())
                                self.assertRegex(result.stderr, r"must start with|starts with")
                                self.assertIn("restore", result.stderr.lower())
                                self.assertIn("reconcile", result.stderr.lower())
                                self.assertEqual(snapshot(self.root), before)
                                self.assertEqual(
                                    {p.relative_to(self.root) for p in self.root.rglob("*") if p.is_dir()},
                                    directories)
                        path.write_text(original)

    def test_guarded_description_merge_conflicts_refuse_without_writes(self):
        parent = self.root
        for harness in ("codex", "copilot"):
            for role in ("implementer", "reviewer"):
                rel = ROLES[role] if harness == "copilot" else f".codex/agents/{role}.toml"
                for kind in ("conflict", "invalid-upstream"):
                    variants = ((), ("--force",), ("--dry-run",))
                    if kind == "conflict":
                        variants += (("--no-guest",),)
                    for index, flags in enumerate(variants):
                        with self.subTest(harness=harness, role=role, kind=kind, flags=flags):
                            # Real independent installations prevent unexpected
                            # publication from contaminating subsequent cases.
                            name = f"{harness}-{role}-{kind}-{index}"
                            self.root = parent / name
                            self.root.mkdir()
                            self.git("init", "-q")
                            self.run_dom("--platform", "codex", "--guest")
                            self.install("--guest")
                            path = self.root / rel
                            original = path.read_text()
                            line = next(s for s in original.splitlines() if s.startswith("description"))
                            field = "description: " if harness == "copilot" else "description = "
                            if kind == "conflict":
                                local = field + json.dumps(
                                    DESCRIPTION_GUARDS[harness] + " Custom local remainder.")
                                upstream = field + json.dumps(
                                    DESCRIPTION_GUARDS[harness] + " New upstream remainder.")
                                path.write_text(original.replace(line, local))
                                # Customization invalidates pair confirmation.
                                # Review/Save through the installed authority
                                # bootstrap, never synthesize marker hashes or
                                # replace pristine bases with customized bytes.
                                models = (
                                    ".github/skills/domestique-v2-copilot-models/SKILL.md"
                                    if harness == "copilot"
                                    else ".agents/skills/domestique-models/SKILL.md")
                                bootstrap = (self.root / models).read_text()
                                bootstrap = bootstrap.split("```python\n", 1)[1].split("\n```", 1)[0]

                                def helper(*args, plan=None):
                                    result = subprocess.run(
                                        [sys.executable, "-I", "-B", "-Werror", "-c", bootstrap, *args],
                                        input=json.dumps(plan) if plan is not None else None,
                                        cwd=self.root, text=True, capture_output=True)
                                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                                    return json.loads(result.stdout)

                                state = STATE if harness == "copilot" else ".codex/.domestique"
                                bases = snapshot(self.root / state / "base")
                                before_review = snapshot(self.root)
                                review = helper("request", "--confirm")
                                self.assertFalse(review["configured"])
                                self.assertEqual(review["chosen"], review["current"])
                                self.assertEqual(snapshot(self.root), before_review)
                                self.assertTrue(helper(
                                    "apply", review["digest"], plan=review["plan"])["confirmed"])
                                self.assertTrue(helper("verify")["confirmed"])
                                self.assertEqual(snapshot(self.root / state / "base"), bases)
                                self.assertIn(local, path.read_text())
                                self.assertIn(line, (self.root / state / "base" / rel).read_text())
                            else:
                                # Also validate the merged description: an
                                # upstream edit cannot drop the boundary.
                                upstream = field + '"Use only in Claude"'
                            source = DOM.read_text()
                            self.assertEqual(source.count(line), 1)
                            revised = self.work / f"{name}.sh"
                            revised.write_text(source.replace(line, upstream))
                            before = snapshot(self.root)
                            result = self.run_dom(*flags, dom=revised, ok=False)
                            self.assertEqual(result.returncode, 3)
                            self.assertIn("no project writes", result.stderr.lower())
                            self.assertIn("reconcile", result.stderr.lower())
                            if kind == "conflict":
                                self.assertIn("conflict", result.stderr)
                                self.assertIn(rel, result.stderr)
                                self.assertIn(f"./{state}/base/{rel}", result.stderr)
                                self.assertIn("keep the pristine base unchanged", result.stderr)
                                self.assertIn("retry --dry-run", result.stderr)
                            else:
                                self.assertIn("discovery description", result.stderr)
                                self.assertIn(DESCRIPTION_GUARDS[harness], result.stderr)
                                self.assertIn("must start with", result.stderr)
                                self.assertIn("restore", result.stderr.lower())
                                self.assertIn(rel, result.stderr)
                            self.assertEqual(snapshot(self.root), before)

    def test_shared_consumers_and_scoped_removal(self):
        for provider in ("codex", "claude"):
            self.run_dom("--platform", provider, "--guest")
        self.install("--guest")
        shared = (self.root / SHARED).read_bytes()
        self.run_dom("--uninstall", "--platform", "claude")
        self.assertTrue(self.hidden(SHARED))
        self.run_dom("--uninstall", "--platform", "codex")
        self.assertEqual((self.root / SHARED).read_bytes(), shared)
        self.assertTrue(self.hidden(ROLES["implementer"]))
        self.assertEqual((self.root / STATE / "platforms").read_text(), "copilot\n")
        self.install("--uninstall")
        self.assertFalse((self.root / ".agents/.domestique").exists())
        self.assertFalse((self.root / SHARED).exists())
        self.assertNotIn("# BEGIN domestique", (self.root / ".git/info/exclude").read_text())

    def test_source_free_stdin_normal_repeat_and_isolation(self):
        result = subprocess.run(["bash", "-s", "--", str(self.root),
                                 "--platform", "copilot"], input=DOM.read_text(),
                                capture_output=True, text=True, cwd=self.work)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.install()
        before = snapshot(self.root)
        self.install()
        self.assertEqual(snapshot(self.root), before)
        self.install("--dry-run")
        self.assertEqual(snapshot(self.root), before)
        self.run_dom("--platform", "both")
        for rel, scope in (
            (".claude/commands/goal.md", "Claude Code only;"),
            (".claude/agents/implementer.md", "Claude Code only;"),
            (".codex/agents/reviewer.toml", "Codex only;"),
            (".agents/skills/domestique/SKILL.md", "Codex only;"),
            (".github/skills/domestique-v2-copilot/SKILL.md", "Copilot only;"),
        ):
            self.assertIn(scope, (self.root / rel).read_text())
        self.install("--uninstall")
        self.assertTrue((self.root / SHARED).exists())
        self.assertTrue((self.root / ".codex/agents/reviewer.toml").exists())
        self.run_dom("--platform", "codex", "--uninstall")
        self.assertFalse((self.root / SHARED).exists())

    def test_sticky_guest_unrelated_normal_and_explicit_mixed_resolution(self):
        self.install("--guest")
        before = snapshot(self.root / ".github")
        self.run_dom("--platform", "claude", "--no-guest")
        self.assertEqual(snapshot(self.root / ".github"), before)
        self.assertTrue(self.hidden(SHARED))
        self.assertTrue(self.hidden(ROLES["reviewer"]))
        self.assertFalse(self.hidden(".claude/commands/dom-goal.md"))
        tree = snapshot(self.root)
        self.run_dom(ok=False)  # missing Codex plus mixed installed modes
        self.assertEqual(snapshot(self.root), tree)
        self.install("--no-guest")
        self.assertFalse(self.hidden(SHARED))
        self.assertFalse(self.hidden(ROLES["reviewer"]))

    def test_wholly_guest_addition_stays_private(self):
        self.run_dom("--platform", "codex", "--guest")
        self.install()
        self.assertTrue(self.hidden(SHARED))
        self.assertTrue(self.hidden(ROLES["reviewer"]))
        self.assertFalse((self.root / ".github/copilot-instructions.md").exists())

    def test_malformed_roles_refuse_before_writes(self):
        self.install("--guest")
        role = self.root / ROLES["reviewer"]
        original = role.read_bytes()
        for malformed in (
            b"not YAML\n", original.replace(b"---\n", b"---\nmodel: a\nmodel: b\n", 1),
            original.replace(b"---\n", b"---\nmodel: null\n", 1),
            original.replace(b"---\n", b"---\n" + MARKER.encode() + b"{}\n", 1),
            original.replace(b"name: domestique-v2-copilot-reviewer", b"name: wrong-role"),
        ):
            role.write_bytes(malformed)
            before = snapshot(self.root)
            for flags in (("--no-guest",), ("--dry-run",), ("--force",)):
                self.install(*flags, ok=False)
                self.assertEqual(snapshot(self.root), before)
        role.write_bytes(original)

    def test_unsafe_unknown_and_conflicting_paths_refuse(self):
        self.install("--guest")
        path = self.root / ROLES["implementer"]
        original = path.read_bytes()
        path.unlink()
        outside = self.work / "outside-role"
        outside.write_bytes(original)
        path.symlink_to(outside)
        tree = snapshot(self.root)
        result = self.install("--no-guest", ok=False)
        self.assertEqual(result.returncode, 3)
        self.assertIn("unsafe", result.stderr)
        self.assertIn(ROLES["implementer"], result.stderr)
        self.assertIn("no project writes", result.stderr.lower())
        self.assertNotIn("reconfirmation-required", result.stdout)
        self.assertEqual(snapshot(self.root), tree)
        self.assertEqual(path.readlink(), outside)
        self.assertEqual(outside.read_bytes(), original)
        path.unlink()
        path.write_bytes(original)
        (self.root / STATE / "unknown-authority").write_text("unknown\n")
        tree = snapshot(self.root)
        result = self.install("--force", ok=False)
        self.assertEqual(result.returncode, 3)
        self.assertIn("unknown state file unknown-authority", result.stderr)
        self.assertIn("no project writes", result.stderr.lower())
        self.assertNotIn("reconfirmation-required", result.stdout)
        self.assertEqual(snapshot(self.root), tree)
        (self.root / STATE / "unknown-authority").unlink()
        # An edited pair is stale/unconfirmed, not eligible for a merge conflict.
        # Preserve every role/base byte until review/Save, even when upstream
        # changes the same line. Genuine confirmed conflicts are tested above.
        pair = {}
        for role, rel in ROLES.items():
            path = self.root / rel
            text = path.read_bytes().replace(
                b"\n---\n", b'\nmodel: "custom-native-id"\ncustom: "retained"\n---\n', 1)
            text = text.replace(b"Return a terse summary:", b"Return my special summary:")
            text += b"\nUser-owned instructions.\n"
            path.write_bytes(text)
            pair[role] = text
        revised = self.work / "conflict-dom.sh"
        revised.write_text(DOM.read_text().replace("Return a terse summary:", "Return a brief summary:"))
        tree = snapshot(self.root)
        # Actual --no-guest may publish mode changes despite exit 3; preview it
        # without writes, then rerun in the retained guest mode for preservation.
        for flags in (("--no-guest", "--dry-run"), ()):
            with self.subTest(unconfirmed_flags=flags):
                result = self.run_dom_unconfirmed("--platform", "copilot", *flags, dom=revised)
                self.assertNotIn("Model lifecycle refused", result.stderr)
                self.assertEqual(snapshot(self.root), tree)
                for role, rel in ROLES.items():
                    text = (self.root / rel).read_bytes()
                    self.assertEqual(text, pair[role])
                    self.assertIn(b'model: "custom-native-id"', text)
                    self.assertIn(b'custom: "retained"', text)
                    self.assertIn(b"User-owned instructions.", text)
                    # Copilot has no supported effort field; do not introduce one.
                    self.assertNotIn(b"\neffort:", text)
                    self.assertNotIn(b"\nmodel_reasoning_effort:", text)
                    self.assertNotIn(b"Return a brief summary:", text)
                self.assertIn(b"Return my special summary:",
                              (self.root / ROLES["implementer"]).read_bytes())

    def test_preview_competing_authority_is_not_adopted(self):
        receipt = self.root / ".domestique-private/copilot-preview.json"
        receipt.parent.mkdir()
        receipt.write_text("{}\n")
        before = snapshot(self.root)
        self.install("--force", ok=False)
        self.assertEqual(snapshot(self.root), before)

    def test_default_and_all_select_three(self):
        self.run_dom()
        self.assertTrue((self.root / ".claude").exists())
        self.assertTrue((self.root / ".codex").exists())
        self.assertTrue((self.root / ".github").exists())
        before = snapshot(self.root)
        self.run_dom("--platform", "all")
        self.assertEqual(snapshot(self.root), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
