"""Installed shared emitter: filesystem guarantees, never native qualification."""
import copy
from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("current_fixture", Path(__file__).with_name("all-current.py"))
CURRENT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CURRENT)
PROVIDERS = {"claude": ".claude", "codex": ".codex", "copilot": ".github"}
DECOMPOSE = {
    "claude": ".claude/commands/dom-decompose.md",
    "codex": ".agents/skills/domestique-decompose/SKILL.md",
    "copilot": ".github/skills/domestique-v2-copilot-decompose/SKILL.md",
}
MODELS = {
    "claude": ".claude/commands/dom-models.md",
    "codex": ".agents/skills/domestique-models/SKILL.md",
    "copilot": ".github/skills/domestique-v2-copilot-models/SKILL.md",
}

def check_execution_protocol(root, provider):
    """Inspect installed instructions/execute their verify, NOT native UX proof."""
    root = Path(root)
    decompose = (root / DECOMPOSE[provider]).read_text()
    goal = (root / DECOMPOSE[provider].replace("decompose", "goal")).read_text()
    start = f"## {provider} read-only execution gate"
    end = "## End execution gate"
    gate = decompose.split(start, 1)[1].split(end, 1)[0]
    assert gate == goal.split(start, 1)[1].split(end, 1)[0]
    flat = " ".join(gate.split())
    for phrase in (
        "BEFORE any Beads command", "exact physical Git worktree root",
        "pristine helper bootstrap below with `verify`",
        "installer-owned manifest/pristine bases", "BOTH marker hashes",
        "NOT native attestation", "including fresh defaults",
        "saved custom/inherited pair needs NO questionnaire and NO writes",
        "requires no Save, setup-only detour, restart or new goal invocation",
        "Visible default values without a valid marker are NOT confirmation",
        "never silently repair files or bless bodies", "dom-models --confirm",
        "dom-models --configure", "no embedded wizard",
        "present, unambiguous registered intended role IDs",
        "documented project discovery/precedence", "known competing definitions",
        "available non-secret model/effort support evidence",
        "do not repeatedly list catalogs/config",
        "documented native discovery and inheritance resolution",
        "absent counterevidence, suffice",
        "independent inherited-model attestation or future child telemetry alone MUST NOT block",
        "Genuinely unknown required registration/discovery",
        "known unavailable/unsupported selection",
        "STOP before workflow writes or dispatch",
        "Report only the affected role, precise reason",
        "Never substitute another model or send a conflicting spawn model/effort override",
        "Helper `confirmed` alone never means native Ready",
        "not a freshly installed role already registered",
        "No invented hot-reload API or permission bypass",
        "check available child role/model/effort telemetry",
        "Static instruction/helper tests are not native UX/dispatch qualification",
    ):
        assert phrase in flat, (provider, phrase)
    for text in (decompose, goal):
        assert text.index("Active harness boundary") < text.index(start)
        assert "questionnaire INLINE" not in text
        assert "Save these choices?" not in text
        assert "Pass `verify`" in text
        assert "pass `prepare`" not in text
    assert decompose.index("SKIP the entire role setup section") < decompose.index(start)
    assert decompose.index(end) < decompose.index("\n# Decompose into beads\n")
    assert "ALL tracked/index dirtiness" in goal
    assert "fresh independent reviewer context" in goal
    prefix = "$" if provider == "codex" else "/"
    # Native explicit goal at its CURRENT authorization level, not xc2.
    assert f"{prefix}dom-goal" in goal
    if provider == "copilot":
        assert "Default bound is ONE reviewed bead" in goal
        assert "native /goal or /autopilot is not" in goal
        assert "Fresh defaults omit model in BOTH roles" in gate
        assert "not necessarily the direct parent's model" in gate
    else:
        assert "15" in goal
        assert "explicit" in goal
    bootstrap = gate.split("```python\n", 1)[1].split("\n```", 1)[0]
    result = subprocess.run([sys.executable, "-I", "-B", "-Werror", "-c", bootstrap, "verify"],
                            cwd=root, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    verified = json.loads(result.stdout)
    assert verified["scope"] == "filesystem-only"
    return verified


class ModelSetup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = CURRENT.AllProviders()
        cls.fixture.setUp()
        cls.addClassCleanup(cls.fixture.doCleanups)
        cls.seed = cls.fixture.root("seed")
        cls.fixture.run_dom(cls.seed)
        cls.env = cls.fixture.env

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=self.fixture.work)
        self.addCleanup(self.tmp.cleanup)
        self.area = Path(self.tmp.name)
        self.sequence = 0

    def project(self):
        self.sequence += 1
        root = self.area / str(self.sequence)
        shutil.copytree(self.seed, root)
        # Most helper tests deliberately start with an owned, unconfirmed pair.
        for provider in PROVIDERS:
            module = self.namespace(self.seed, provider)
            impl = self.roles(root, provider)["implementer"]
            impl.write_bytes(module["split_marker"](impl.read_bytes(), "implementer")[0].encode())
        return root

    def helper(self, root, provider):
        return root / PROVIDERS[provider] / "domestique-model-setup.py"

    def roles(self, root, provider):
        impl = dict(zip(PROVIDERS, CURRENT.ROLES))[provider]
        return {r: root / impl.replace("implementer", r) for r in ("implementer", "reviewer")}

    def bootstrap(self, root, provider):
        rel = DECOMPOSE[provider]
        text = (root / rel).read_text()
        return text.split("```python\n", 1)[1].split("\n```", 1)[0]

    def call(self, root, provider, action, value=None, plan=None, ok=True, cwd=None,
             deny_write_access=False):
        bootstrap = self.bootstrap(root, provider)
        if deny_write_access:
            # Model a read-only execution context without changing tracked modes.
            # This is an installed-helper subprocess probe, not native qualification.
            bootstrap = ("import os\noriginal_access = os.access\n"
                         "os.access = lambda path, mode: False if mode & os.W_OK "
                         "else original_access(path, mode)\n") + bootstrap
        args = [sys.executable, "-I", "-B", "-Werror", "-c", bootstrap, action]
        if value is not None:
            args.append(value if isinstance(value, str) else json.dumps(value))
        result = subprocess.run(args, input=json.dumps(plan) if plan is not None else None,
                                cwd=cwd or root, env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return json.loads(result.stdout) if ok else result

    def choices(self, provider, inherit=False):
        return {r: {"model": None if inherit else 'model/α-"quoted"\\exact',
                    "effort": None if inherit or provider == "copilot" else "high"}
                for r in ("implementer", "reviewer")}

    def native(self, root, provider, *args, text=False, ok=True):
        body = (root / MODELS[provider]).read_text()
        bootstrap = body.split("```python\n", 1)[1].split("\n```", 1)[0]
        result = subprocess.run(
            [sys.executable, "-I", "-B", "-Werror", "-c", bootstrap,
             "request-text" if text else "request", *args],
            cwd=root, env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return json.loads(result.stdout) if ok else result

    def test_dom_models_native_grammar_inspection_and_cancel(self):
        for provider in PROVIDERS:
            root = self.project()
            # A byte-identical copied install is not confirmed for its new root.
            self.roles(root, provider)["implementer"].write_bytes(
                self.roles(self.seed, provider)["implementer"].read_bytes())
            before = CURRENT.snapshot(root)
            inspected = self.native(root, provider)
            self.assertEqual(inspected["mode"], "inspect")
            self.assertFalse(inspected["configured"])
            self.assertTrue(any("Copied/moved root" in w for w in inspected["warnings"]))
            self.assertEqual(inspected["native_readiness"], "not established")
            self.assertNotIn("plan", inspected)
            self.assertEqual(self.native(root, provider, "--configure")["current"],
                             inspected["current"])
            self.assertIn("usage", self.native(root, provider, "--help"))
            invalid = [
                ("--implementer=x", "--implementer=x"),
                ("--reviewer", "x", "--reviewer=y"),
                ("--implementer=",), ("--reviewer", ""),
                ("--implementer",), ("--reviewer", "--confirm"),
                ("--configure", "--implementer=x"), ("--confirm", "--reviewer=x"),
                ("--help", "--configure"), ("--configure", "--confirm"),
                ("--harness=codex",), ("--path=.",), ("--unknown",),
                ("--implementer-effort=high", "--implementer-effort=high"),
                ("--reviewer=x\nbad",), ("--reviewer= trailing",),
            ]
            if provider == "copilot":
                invalid += [("--reviewer-effort=inherit",), ("--implementer-effort", "high")]
            for argv in invalid:
                with self.subTest(provider=provider, argv=argv):
                    self.native(root, provider, *argv, ok=False)
            self.native(root, provider, "'unterminated", text=True, ok=False)
            # Preparing is not consent. Simulated cancellation calls no writer.
            prepared = self.native(root, provider, "--confirm")
            self.assertIn("digest", prepared)
            self.assertEqual(prepared["chosen"], inspected["current"])
            self.assertEqual(before, CURRENT.snapshot(root))
            self.apply(root, provider, prepared)
            confirmed = self.native(root, provider)
            self.assertTrue(confirmed["configured"])
            before = CURRENT.snapshot(root)
            self.assertNotIn("plan", self.native(root, provider, "--confirm"))
            self.assertEqual(before, CURRENT.snapshot(root))
            self.roles(root, provider)["reviewer"].unlink()
            before = CURRENT.snapshot(root)
            self.assertIn("not installed/unconfigured", self.native(root, provider)["status"])
            self.assertIn("usage", self.native(root, provider, "--help"))
            self.native(root, provider, "--confirm", ok=False)
            self.assertEqual(before, CURRENT.snapshot(root))

    def test_dom_models_literal_override_preserves_partner_effort_and_bodies(self):
        import shlex
        for provider in PROVIDERS:
            root = self.project()
            # Explicit non-null efforts must survive model-only changes.
            self.apply(root, provider, self.prepare(root, provider))
            roles = self.roles(root, provider)
            roles["reviewer"].write_bytes(roles["reviewer"].read_bytes() + b"\n# current custom body\n")
            before = {r: p.read_bytes() for r, p in roles.items()}
            current = self.native(root, provider)["current"]
            literal = 'model/alpha-"quoted"\\exact=a:b $(never-execute)'
            argv = ["--implementer", literal]
            a = self.native(root, provider, *argv)
            b = self.native(root, provider, shlex.join(argv), text=True)
            self.assertEqual(a, b)
            self.assertEqual(a["chosen"]["implementer"]["effort"], current["implementer"]["effort"])
            self.assertTrue(any("body differs" in w for w in a["warnings"]))
            self.apply(root, provider, a)
            self.assertEqual(roles["reviewer"].read_bytes(), before["reviewer"])
            self.assertEqual(self.native(root, provider)["current"]["implementer"]["model"], literal)
            bare_before = self.namespace(root, provider)["split_marker"](
                roles["implementer"].read_bytes(), "implementer")[0]
            a = self.native(root, provider, "--reviewer=inherit")
            self.apply(root, provider, a)
            state = self.native(root, provider)["current"]
            self.assertEqual(state["reviewer"]["model"], "inherit" if provider == "claude" else None)
            self.assertEqual(state["reviewer"]["effort"], current["reviewer"]["effort"])
            self.assertEqual(self.namespace(root, provider)["split_marker"](
                roles["implementer"].read_bytes(), "implementer")[0], bare_before)
            if provider != "copilot":
                a = self.native(root, provider, "--implementer-effort=inherit")
                self.apply(root, provider, a)
                state = self.native(root, provider)["current"]
                self.assertIsNone(state["implementer"]["effort"])
                self.assertEqual(state["implementer"]["model"], literal)
            # Current-body edits are acknowledged without rewriting body or base.
            before = {r: self.namespace(root, provider)["split_marker"](p.read_bytes(), r)[0]
                      for r, p in roles.items()}
            roles["reviewer"].write_bytes(roles["reviewer"].read_bytes() + b"# stale\n")
            before["reviewer"] += "# stale\n"
            a = self.native(root, provider, "--confirm")
            self.apply(root, provider, a)
            for r, p in roles.items():
                self.assertEqual(self.namespace(root, provider)["split_marker"](p.read_bytes(), r)[0],
                                 before[r])

    def test_dom_models_emitted_routes_and_native_api_boundary(self):
        shared = (self.seed / ".agents/skills/dom-models/SKILL.md").read_text()
        for text in ("ACTUAL native caller", "Unknown, ambiguous", "Missing/unreadable/foreign",
                     "ORIGINAL explicit request", "No arguments means read-only inspection"):
            self.assertIn(text, shared)
        for provider, rel in MODELS.items():
            body = (self.seed / rel).read_text()
            for text in ("Active harness boundary", "request-text", "Save / Cancel",
                         "Cancelled; nothing saved", "Await terminal completion",
                         "No installer API", "current -> chosen", "detailed",
                         "Saved configuration is not proof"):
                self.assertIn(text, body)
            self.assertIn(rel, (self.seed / DECOMPOSE[provider]).read_text())
            if provider != "claude":
                self.assertIn(rel, shared)
            root = self.project()
            before = CURRENT.snapshot(root)
            for action in ("installer", "installer-apply", "installer_request"):
                self.call(root, provider, action, ok=False)
            self.native(root, provider, "--installer", ok=False)
            self.assertEqual(before, CURRENT.snapshot(root))

    def test_dom_models_effort_only_preserves_omitted_claude_model(self):
        root = self.project()
        roles = self.roles(root, "claude")
        impl = roles["implementer"]
        impl.write_bytes(re.sub(rb"(?m)^model:.*\n", b"", impl.read_bytes()))
        reviewer = roles["reviewer"].read_bytes()
        prepared = self.native(root, "claude", "--implementer-effort", "high")
        self.apply(root, "claude", prepared)
        self.assertNotIn(b"\nmodel:", impl.read_bytes())
        self.assertEqual(roles["reviewer"].read_bytes(), reviewer)
        prepared = self.native(root, "claude", "--implementer=inherit")
        self.apply(root, "claude", prepared)
        self.assertIn(b'\nmodel: "inherit"\n', impl.read_bytes())
        self.assertEqual(self.native(root, "claude")["current"]["implementer"]["effort"], "high")

    def prepare(self, root, provider, inherit=False):
        return self.call(root, provider, "prepare", self.choices(provider, inherit))

    def apply(self, root, provider, prepared, ok=True):
        return self.call(root, provider, "apply", prepared["digest"], prepared["plan"], ok=ok)

    def namespace(self, root, provider):
        helper = self.helper(root, provider)
        namespace = {"__file__": str(helper), "__name__": "tested_helper"}
        exec(compile(helper.read_bytes(), str(helper), "exec"), namespace)
        return namespace

    @contextmanager
    def installer(self, root, provider, upgrade=None):
        # Load trusted emitted code from the installer fixture, NOT target code.
        module = self.namespace(self.seed, provider)
        cwd = Path.cwd()
        os.chdir(root)
        try:
            layout = module["Pair"](installed=False)
            pristine = {p: (self.seed / p).read_bytes() for p in layout.files}
            for rel in layout.paths.values():
                pristine[rel] = pristine[f"{layout.state}/base/{rel}"]
            manifest = module["Pair"].inventory(layout, pristine[layout.manifest])
            old_files = manifest["files"].replace("," + layout.helper, "")
            recognized = {(manifest["domestique_version"], files)
                          for files in (manifest["files"], old_files)}
            if upgrade:
                for role, rel in layout.paths.items():
                    pristine[rel] = upgrade(module, role, pristine[rel])
                    pristine[f"{layout.state}/base/{rel}"] = pristine[rel]

            def merge(local, base, upstream):
                # Exercise real preserving diff3 in external operation scratch.
                with tempfile.TemporaryDirectory(dir=self.area) as scratch:
                    paths = [Path(scratch) / name for name in ("local", "base", "upstream")]
                    for path, data in zip(paths, (local, base, upstream)):
                        path.write_bytes(data)
                    result = subprocess.run(["git", "merge-file", "-p", "--diff3", *map(str, paths)],
                                            capture_output=True, env=self.env)
                    if result.returncode:
                        raise ValueError("native preserving merge conflict")
                    return result.stdout

            def validate(role, base, live, candidate):
                # Real native parsing and guard checks; .4 supplies its existing
                # full guard/migration validation, not a success-shaped stub.
                for data in (base, live, candidate):
                    _, fields, _ = module["parse"](data, role)
                    body = (fields["developer_instructions"] if provider == "codex"
                            else module["split_marker"](data, role)[0].split("---", 2)[2])
                    required = (("These instructions apply only in the actual native Codex client; foreign or",
                                 "ambiguous callers stop without work. Installed directories do not identify it.")
                                if provider == "codex" else
                                (f"## Active harness boundary ({provider} only)",
                                 f"These instructions apply only to the native `{provider}` client.",
                                 "An explicit foreign-harness invocation must STOP"))
                    if not all(text in body for text in required):
                        raise ValueError("unsafe native guard")
            yield module, module["InstallerPair"](pristine, recognized, merge, validate)
        finally:
            os.chdir(cwd)

    def test_installer_fresh_defaults_inheritance_and_absent_binding(self):
        defaults = {
            "claude": ("sonnet", "opus"), "codex": ("gpt-5.6-sol", "gpt-5.6-terra"),
            "copilot": (None, None),
        }
        for provider in PROVIDERS:
            for override in ({}, {"reviewer": None}, {"implementer": 'model/α-"quoted"\\exact=a:b'}):
                with self.subTest(provider=provider, override=override):
                    root = self.project()
                    shutil.rmtree(root / PROVIDERS[provider])
                    with self.installer(root, provider) as (module, pair):
                        before = CURRENT.snapshot(root)
                        prepared = pair.prepare(override)
                        self.assertEqual(before, CURRENT.snapshot(root))
                        self.assertEqual(prepared["plan"]["eligibility"], "fresh")
                        self.assertTrue(all(v is None for v in prepared["plan"]["snapshot"]["files"].values()))
                        result = pair.apply(**prepared)
                        self.assertEqual(result["publication_snapshot"], pair.snapshot()[0])
                        self.assertTrue(result["configured"])
                        self.assertFalse(result["native_ready"])
                        for role, model in zip(("implementer", "reviewer"), defaults[provider]):
                            wanted = override.get(role, model)
                            if provider == "claude" and wanted is None:
                                wanted = "inherit"
                            self.assertEqual(result["selected"][role]["model"], wanted)
                            effort = ({"implementer": "medium", "reviewer": "high"}[role]
                                      if provider == "codex" and role not in override else None)
                            self.assertEqual(result["selected"][role]["effort"], effort)
                        # Final pair really verifies using the installed helper.
                        installed_module = self.namespace(root, provider)
                        installed = installed_module["Pair"]()
                        _, contents = installed.snapshot()
                        self.assertTrue(installed_module["verify"](installed, contents)["confirmed"])
                    with self.installer(root, provider) as (_, pair):
                        before = CURRENT.snapshot(root)
                        inodes = {r: p.stat().st_ino for r, p in self.roles(root, provider).items()}
                        result = pair.apply(**pair.prepare({}))
                        self.assertEqual(result["published"], [])
                        self.assertEqual(before, CURRENT.snapshot(root))
                        self.assertEqual(inodes, {r: p.stat().st_ino for r, p in self.roles(root, provider).items()})

    def test_installer_confirmed_exact_partial_override_and_upstream_defaults(self):
        for provider in PROVIDERS:
            root = self.project()
            roles = self.roles(root, provider)
            # Keep local==old pristine settings; even these are pinned on upgrade.
            with self.installer(root, provider) as (_, pair):
                self.assertEqual(pair.prepare({})["plan"]["eligibility"], "legacy")
                pair.apply(**pair.prepare({}))
            old = self.call(root, provider, "verify")["selected"]

            def upgrade(module, role, data):
                data = module["patch"](data, role, {"model": "new-upstream", "effort": None})
                return data + b"\n# reviewed upstream addition\n"

            with self.installer(root, provider, upgrade) as (module, pair):
                result = pair.apply(**pair.prepare({}))
                self.assertEqual(result["selected"], old)
                for role, path in roles.items():
                    self.assertIn(b"# reviewed upstream addition", path.read_bytes())
                    base = root / f"{pair.state}/base/{pair.paths[role]}"
                    self.assertEqual(module["parse"](base.read_bytes(), role)[1]["model"], "new-upstream")
                    self.assertNotIn(module["MARKER"].encode(), base.read_bytes())
                before = CURRENT.snapshot(root)
                self.assertEqual(pair.apply(**pair.prepare({}))["published"], [])
                self.assertEqual(before, CURRENT.snapshot(root))
            # A later native Save can confirm custom bodies and exact scalar spelling.
            data = roles["implementer"].read_bytes()
            module = self.namespace(root, provider)
            bare = module["split_marker"](data, "implementer")[0]
            if provider == "codex":
                bare = bare.replace('model_reasoning_effort = "medium"',
                                    "model_reasoning_effort = 'medium'  # pinned effort")
            elif provider == "claude":
                bare = bare.replace("model: sonnet", "model: 'sonnet'  # pinned model")
                bare = bare.replace("---\n", "---\neffort: 'high'  # pinned effort\n", 1)
            roles["implementer"].write_bytes(bare.replace("\n", "\r\n").encode())
            roles["reviewer"].write_bytes(roles["reviewer"].read_bytes() + b"\n# approved custom body\n")
            current = self.call(root, provider, "verify")["selected"]
            self.apply(root, provider, self.call(root, provider, "prepare", current))
            with self.installer(root, provider, upgrade) as (module, pair):
                original = {r: p.read_bytes() for r, p in roles.items()}
                inodes = {r: p.stat().st_ino for r, p in roles.items()}
                same = current["implementer"]["model"]
                if same == "inherit":
                    same = None
                pair.apply(**pair.prepare({"implementer": same}))
                self.assertEqual(original, {r: p.read_bytes() for r, p in roles.items()})
                self.assertEqual(inodes, {r: p.stat().st_ino for r, p in roles.items()})
                result = pair.apply(**pair.prepare({"implementer": "different"}))
                self.assertEqual(result["selected"]["implementer"]["effort"], current["implementer"]["effort"])
                self.assertEqual(roles["reviewer"].read_bytes(), original["reviewer"])
                self.assertEqual(roles["reviewer"].stat().st_ino, inodes["reviewer"])
                expected = module["patch"](original["implementer"], "implementer",
                                           {"model": "different"}, model_only=True)
                self.assertEqual(module["split_marker"](roles["implementer"].read_bytes(), "implementer")[0].encode(),
                                 expected)
                inherited = pair.apply(**pair.prepare({"implementer": None}))
                self.assertEqual(inherited["selected"]["implementer"]["effort"],
                                 current["implementer"]["effort"])

    def test_installer_legacy_inventory_vs_damaged_authority(self):
        for provider in PROVIDERS:
            for defect in ("legacy", "legacy-custom", "claimed-helper", "base", "unknown",
                           "symlink", "malformed-helper", "guard"):
                with self.subTest(provider=provider, defect=defect):
                    root = self.project()
                    with self.installer(root, provider) as (module, pair):
                        if defect.startswith("legacy"):
                            (root / pair.helper).unlink()
                            (root / f"{pair.state}/base/{pair.helper}").unlink()
                            manifest = root / pair.manifest
                            manifest.write_text(manifest.read_text().replace("," + pair.helper, ""))
                            role = root / pair.paths["implementer"]
                            role.write_bytes(module["patch"](role.read_bytes(), "implementer",
                                             {"model": "legacy-choice", "effort": None}))
                            if defect == "legacy-custom":
                                role.write_bytes(role.read_bytes() + b"\n# custom body\n")
                        elif defect == "claimed-helper":
                            (root / pair.helper).unlink()
                        elif defect == "base":
                            (root / f"{pair.state}/base/{pair.paths['reviewer']}").unlink()
                        elif defect == "unknown":
                            path = root / pair.manifest
                            path.write_text(path.read_text().replace("domestique_version=", "unknown_version="))
                        elif defect == "symlink":
                            path = root / pair.paths["reviewer"]
                            path.unlink()
                            path.symlink_to(root / pair.paths["implementer"])
                        elif defect == "malformed-helper":
                            for rel in (pair.helper, f"{pair.state}/base/{pair.helper}"):
                                (root / rel).write_bytes(b"invalid python !\n")
                        else:
                            path = root / pair.paths["reviewer"]
                            guard = (b"These instructions apply only in the actual native Codex client"
                                     if provider == "codex" else b"An explicit foreign-harness")
                            path.write_bytes(path.read_bytes().replace(guard, b"Removed"))
                        before = CURRENT.snapshot(root)
                        if not defect.startswith("legacy"):
                            with self.assertRaises(ValueError):
                                pair.prepare({})
                            self.assertEqual(before, CURRENT.snapshot(root))
                        else:
                            prepared = pair.prepare({})
                            self.assertEqual(before, CURRENT.snapshot(root))
                            result = pair.apply(**prepared)
                            self.assertEqual(result["configured"], defect == "legacy")
                            self.assertEqual(result["selected"]["implementer"]["model"], "legacy-choice")
                            if defect == "legacy-custom":
                                self.assertEqual(result["outcome"], "reconfirmation-required")
                                self.assertIn(b"# custom body", (root / pair.paths["implementer"]).read_bytes())

    def test_installer_stale_copied_and_partial_never_approve(self):
        for provider in PROVIDERS:
            for defect in ("body", "model", "copied", "partial"):
                with self.subTest(provider=provider, defect=defect):
                    root = self.project()
                    with self.installer(root, provider) as (_, pair):
                        pair.apply(**pair.prepare({}))
                    if defect == "copied":
                        destination = self.area / f"copy-{provider}"
                        shutil.copytree(root, destination)
                        root = destination
                    else:
                        path = self.roles(root, provider)["reviewer"]
                        if defect == "partial":
                            path.unlink()
                        elif defect == "body":
                            path.write_bytes(path.read_bytes() + b"\n# unreviewed edit\n")
                        else:
                            module = self.namespace(root, provider)
                            path.write_bytes(module["patch"](path.read_bytes(), "reviewer",
                                                            {"model": "manual"}, model_only=True))
                    with self.installer(root, provider) as (_, pair):
                        before = CURRENT.snapshot(root)
                        with self.assertRaisesRegex(ValueError, "partial owned pair" if defect == "partial"
                                                    else "unconfirmed pair"):
                            pair.prepare({"implementer": "new"})
                        self.assertEqual(before, CURRENT.snapshot(root))
                        if defect == "partial":
                            with self.assertRaises(ValueError) as raised:
                                pair.prepare({})
                            result = json.loads(str(raised.exception))
                            self.assertFalse(result["configured"])
                            self.assertEqual(result["outcome"], "repair-required")
                            self.assertEqual(before, CURRENT.snapshot(root))
                            continue
                        prepared = pair.prepare({})
                        self.assertEqual(prepared["plan"]["eligibility"], "stale")
                        result = pair.apply(**prepared)
                        self.assertFalse(result["configured"])
                        if defect != "partial":
                            self.assertEqual(before, CURRENT.snapshot(root))
                    self.assertFalse(self.call(root, provider, "verify")["confirmed"])

    def test_installer_unreviewed_body_cannot_become_pristine_on_rerun(self):
        for provider in PROVIDERS:
            for historical in (False, True):
                with self.subTest(provider=provider, historical=historical):
                    root = self.project()
                    roles = self.roles(root, provider)
                    for path in roles.values():
                        path.write_bytes(path.read_bytes() + b"\n# future upstream body\n")

                    def upgrade(module, role, data):
                        return data + b"\n# future upstream body\n"

                    with self.installer(root, provider, upgrade) as (_, pair):
                        if historical:
                            (root / pair.helper).unlink()
                            (root / f"{pair.state}/base/{pair.helper}").unlink()
                            manifest = root / pair.manifest
                            manifest.write_text(manifest.read_text().replace("," + pair.helper, ""))
                        bases = {p: (root / p).read_bytes() for p in pair.files
                                 if "/base/" in p and (root / p).exists()}
                        for attempt in range(2):
                            prepared = pair.prepare({}, force=True)
                            self.assertEqual(prepared["plan"]["eligibility"], "custom-unconfirmed")
                            self.assertEqual(prepared["plan"]["historical_migration"],
                                             historical and attempt == 0)
                            self.assertFalse(pair.apply(**prepared)["configured"])
                        for path, data in bases.items():
                            self.assertEqual((root / path).read_bytes(), data)

    def test_installer_tamper_races_and_partial_publication(self):
        for provider in PROVIDERS:
            for defect in ("plan", "absent", "parent", "reviewer", "marker", "temporary"):
                with self.subTest(provider=provider, defect=defect):
                    root = self.project()
                    if defect in ("absent", "parent"):
                        shutil.rmtree(root / PROVIDERS[provider])
                    with self.installer(root, provider) as (_, pair):
                        prepared = pair.prepare({"reviewer": "installed-choice"})
                        if defect == "plan":
                            prepared["plan"]["outputs"][pair.paths["reviewer"]] = "0" * 64
                            # Recomputed digest does NOT authorize a body substitution.
                            prepared["digest"] = __import__("hashlib").sha256(
                                json.dumps(prepared["plan"], sort_keys=True, ensure_ascii=False,
                                           separators=(",", ":")).encode()).hexdigest()
                        elif defect in ("absent", "parent"):
                            directory = root / PROVIDERS[provider]
                            directory.mkdir()
                            if defect == "absent":
                                directory.joinpath("agents").mkdir()
                                (root / pair.paths["reviewer"]).write_bytes(b"unowned competing file\n")
                        real_replace, real_mkstemp = os.replace, tempfile.mkstemp
                        replaced = []

                        def replace(src, dest):
                            target = pair.paths["reviewer" if defect == "reviewer" else "implementer"]
                            if defect in ("reviewer", "marker") and str(dest) == str(root / target):
                                raise OSError("injected installer publication failure")
                            replaced.append(str(dest))
                            return real_replace(src, dest)

                        def mkstemp(*args, **kwargs):
                            fd, name = real_mkstemp(*args, **kwargs)
                            if defect == "temporary":
                                path = root / pair.paths["reviewer"]
                                path.write_bytes(path.read_bytes() + b"\n# competing write\n")
                            return fd, name

                        before = CURRENT.snapshot(root)
                        with patch.object(os, "replace", replace), patch.object(tempfile, "mkstemp", mkstemp):
                            with self.assertRaises(ValueError) as raised:
                                pair.apply(**prepared)
                        if defect in ("plan", "absent", "parent"):
                            self.assertEqual(before, CURRENT.snapshot(root))
                        else:
                            error = json.loads(str(raised.exception))
                            self.assertEqual(error["published"], [str(Path(p).relative_to(root)) for p in replaced])
                            self.assertFalse(error["workflow_authorized"])
                            self.assertFalse(self.call(root, provider, "verify")["confirmed"])
                        self.assertFalse(list(root.rglob(".domestique-model-setup-*")))

    def test_installer_plan_cannot_enter_native_apply(self):
        for provider in PROVIDERS:
            root = self.project()
            with self.installer(root, provider) as (_, pair):
                prepared = pair.prepare({})
            before = CURRENT.snapshot(root)
            self.apply(root, provider, prepared, ok=False)
            self.call(root, provider, "installer-apply", prepared["digest"], prepared["plan"], ok=False)
            self.assertEqual(before, CURRENT.snapshot(root))

    def test_installer_invalidation_precedes_dependency_and_pair_changes(self):
        for provider in PROVIDERS:
            for failure in ("base", "reviewer", "marker"):
                with self.subTest(provider=provider, failure=failure):
                    root = self.project()
                    with self.installer(root, provider) as (_, pair):
                        pair.apply(**pair.prepare({}))

                    def upgrade(module, role, data):
                        return data + b"\n# reviewed body upgrade\n"

                    with self.installer(root, provider, upgrade) as (module, pair):
                        prepared = pair.prepare({})
                        original_replace, stages = os.replace, []

                        def replace(src, dest):
                            rel = str(Path(dest).relative_to(root))
                            data = Path(src).read_bytes()
                            if (failure == "base" and "/base/" in rel or
                                    failure == "reviewer" and rel == pair.paths["reviewer"] or
                                    failure == "marker" and module["MARKER"].encode() in data):
                                raise OSError("injected failure after marker invalidation")
                            stages.append((rel, data))
                            return original_replace(src, dest)

                        with patch.object(os, "replace", replace):
                            with self.assertRaises(ValueError) as raised:
                                pair.apply(**prepared)
                        error = json.loads(str(raised.exception))
                        self.assertTrue(error["partial"])
                        self.assertEqual(stages[0][0], pair.paths["implementer"])
                        self.assertNotIn(module["MARKER"].encode(), stages[0][1])
                        self.assertFalse(self.call(root, provider, "verify")["confirmed"])
                        with self.assertRaisesRegex(ValueError, "must prepare"):
                            pair.apply(**prepared)
                        self.assertFalse(list(root.rglob(".domestique-model-setup-*")))

    def test_planning_routes_bypass_setup_at_every_entry_layer(self):
        # Emitted protocol checks, not a simulation of native assistant behavior.
        for guest in (False, True):
            root = self.project() if not guest else self.fixture.root("planning-guest")
            if guest:
                self.fixture.run_dom(root, "--guest")
            for provider, rel in DECOMPOSE.items():
                with self.subTest(provider=provider, guest=guest):
                    text = (root / rel).read_text()
                    boundary, routed = text.split("## Explicit config-vs-plan routing", 1)
                    route, rest = routed.split(f"## {provider} read-only execution gate", 1)
                    setup, plan = rest.split("\n# Decompose into beads\n", 1)
                    self.assertIn("Active harness boundary", boundary)
                    for required in (
                        "Only the entire explicit argument `configure role models`",
                        "Task text mentioning models", "NOT configuration intent",
                        "SKIP the entire role setup section", "No model configuration/questions",
                        "helper\nverify, loaded-role check or reload",
                        "missing, unconfirmed or manually edited",
                        "Do not read role files", "explicit planning request",
                        "never falls through", "Planning never delegates",
                        "claims/closes beads", "stages or commits",
                    ):
                        self.assertIn(required, route)
                    self.assertIn("Ordinary planning-only decompose skips this entire gate", setup)
                    self.assertIn("exec(compile(code", setup)  # execution verify remains functional
                    for forbidden in ("emit_", "After the gate", "helper", "reload",
                                      "confirmed pair", "questionnaire"):
                        self.assertNotIn(forbidden, plan)
                    self.assertIn("epic", plan)
                    self.assertIn("bounded", plan)
                    self.assertIn("dependencies", plan)
                    self.assertRegex(plan, r"(?i)(do not.*delegate|no implementation,\ndelegation)")
            self.assertEqual((root / DECOMPOSE["claude"]).read_bytes(),
                             (root / ".claude/commands/decompose.md").read_bytes())
            layers = [
                ".agents/skills/dom-decompose/SKILL.md",
                ".agents/skills/dom-goal/SKILL.md",
                ".agents/skills/domestique/SKILL.md",
                ".github/skills/domestique-v2-copilot/SKILL.md",
                "CLAUDE.local.md" if guest else "CLAUDE.md",
            ]
            if not guest:
                layers += ["AGENTS.md", ".github/copilot-instructions.md"]
            for rel in layers:
                text = (root / rel).read_text()
                flat = " ".join(text.split())
                self.assertIn("Planning-only decompose bypasses", text, rel)
                self.assertIn("helper verify", flat, rel)
                self.assertIn("loaded-role checks or reload", flat, rel)
                self.assertIn("configure role models", text, rel)
                self.assertNotIn("gate (before Beads or delegation)", text, rel)
                self.assertNotIn("Before Beads/delegation", text, rel)
            for rel in (".github/skills/domestique-v2-copilot/SKILL.md",
                        *([] if guest else [".github/copilot-instructions.md"])):
                self.assertIn("Its Beads/readiness/branch gates do not apply to planning",
                              (root / rel).read_text())

    def test_concise_exact_plan_consent_and_terminal_save_protocol(self):
        for provider, rel in MODELS.items():
            text = (self.seed / rel).read_text()
            for entry in (text,):
                flat = " ".join(entry.split())
                for required in (
                    "prefilled with current saved models/efforts",
                    "project/harness, each current -> chosen model/effort",
                    "both exact role paths", "preserved tools/prompts",
                    "tracked-file consequences", "complete detailed diff on request",
                    "do not print raw diffs, marker JSON",
                    "Retain its digest independently",
                    "Save these choices? Save / Cancel",
                    "Initial model selection before prepare is NOT save consent",
                    "prepare/new summary/new explicit human save consent",
                    "ZERO target writes", "ONLY the exact plan JSON",
                    "Setup cancelled; nothing saved",
                    "Do not report success or resume the initiating goal",
                    "normal native one-command protected-write approval",
                    "Run apply synchronously", "background notification",
                    "until terminal completion; pending is NOT saved",
                    "Check exit status and helper JSON", "read-only `verify`",
                    "check both hashes/choices against apply",
                    "is explicit FAILURE, never success-shaped",
                    "Only after verified completion",
                    "including one already supplied",
                    "stale/unknown registrations require a supported reload",
                    "Do not invent in-session refresh",
                    "fresh explicit execution authorization",
                    "the initiating goal is consumed, not queued",
                ):
                    self.assertIn(required, flat, provider)
                for forbidden in ("Display the plan's ACTUAL complete diff",
                                  "show the ACTUAL complete proposed diff",
                                  "displayed digest", "Save setup only / Cancel",
                                  "Before Beads, planning", "any workflow action",
                                  "stop for fresh-session reinvocation"):
                    self.assertNotIn(forbidden, entry, provider)
                self.assertLess(entry.index("It returns `plan` and `digest`"),
                                entry.index("Ask once: `Save these choices?"))
                self.assertLess(entry.index("Ask once: `Save these choices?"),
                                entry.index("Only after explicit consent AND"))
            for rel in (DECOMPOSE[provider], DECOMPOSE[provider].replace("decompose", "goal")):
                execution = (self.seed / rel).read_text()
                self.assertNotIn("Save these choices?", execution)
                self.assertNotIn("pass `prepare`", execution)

    def test_fresh_configured_defaults_across_execution_layers(self):
        # Actual fresh installer confirmation at its original physical root.
        # Text routing/read-only helper checks do not emulate native dispatch.
        expected = {
            "claude": (("sonnet", None), ("opus", None)),
            "codex": (("gpt-5.6-sol", "medium"), ("gpt-5.6-terra", "high")),
            "copilot": ((None, None), (None, None)),
        }
        before = CURRENT.snapshot(self.seed)
        for provider in PROVIDERS:
            result = check_execution_protocol(self.seed, provider)
            self.assertTrue(result["confirmed"])
            self.assertEqual(tuple((c["model"], c["effort"]) for c in result["selected"].values()),
                             expected[provider])
            if provider == "copilot":
                for role in self.roles(self.seed, provider).values():
                    self.assertNotIn("\nmodel:", role.read_text())
        # Root/bootstrap, shared public, and native command/skill layers agree.
        layers = [
            "CLAUDE.md", "AGENTS.md", ".github/copilot-instructions.md",
            ".agents/skills/domestique/SKILL.md",
            ".github/skills/domestique-v2-copilot/SKILL.md",
            ".agents/skills/dom-goal/SKILL.md", ".agents/skills/dom-decompose/SKILL.md",
        ]
        for rel in layers:
            text = " ".join((self.seed / rel).read_text().split())
            with self.subTest(layer=rel):
                for required in ("installer-configured defaults", "custom/inherited pairs",
                                 "dom-models --confirm", "dom-models --configure",
                                 "independent inherited-model", "counterevidence",
                                 "stale/unknown current registrations"):
                    self.assertIn(required, text)
                self.assertNotIn("questionnaire INLINE", text)
                self.assertNotIn("Generated defaults are suggestions, never confirmation", text)
                self.assertNotIn("Save these choices?", text)
        self.assertEqual(before, CURRENT.snapshot(self.seed))

    def test_saved_pair_and_known_unavailable_route_never_fallback(self):
        for provider in PROVIDERS:
            root = self.project()
            # A literal offline selection is saved, not native availability proof.
            self.apply(root, provider, self.prepare(root, provider))
            before = CURRENT.snapshot(root)
            result = check_execution_protocol(root, provider)
            self.assertTrue(result["confirmed"])
            self.assertEqual(result["selected"], self.native(root, provider)["current"])
            self.assertEqual(before, CURRENT.snapshot(root))
            # Known unavailability is a native evidence branch documented in the
            # installed gate, not something filesystem verify can discover.
            goal = (root / DECOMPOSE[provider].replace("decompose", "goal")).read_text()
            stop = " ".join(goal.split("Genuinely unknown required registration/discovery", 1)[1]
                            .split("Helper `confirmed`", 1)[0].split())
            for phrase in ("known unavailable/unsupported selection",
                           "STOP before workflow writes or dispatch",
                           "Report only the affected role, precise reason",
                           "dom-models --configure", "Never substitute another model",
                           "conflicting spawn model/effort override"):
                self.assertIn(phrase, stop)
            self.assertNotIn("Save these choices?", stop)
            self.apply(root, provider, self.prepare(root, provider, inherit=True))
            before = CURRENT.snapshot(root)
            inherited = check_execution_protocol(root, provider)
            self.assertTrue(inherited["confirmed"])
            for choice in inherited["selected"].values():
                self.assertEqual(choice["model"], "inherit" if provider == "claude" else None)
                self.assertIsNone(choice["effort"])
            self.assertEqual(before, CURRENT.snapshot(root))

    def test_unconfirmed_execution_never_autoblesses_current_bodies(self):
        for provider in PROVIDERS:
            root = self.project()
            before = CURRENT.snapshot(root)
            self.assertFalse(check_execution_protocol(root, provider)["confirmed"])
            self.assertEqual(before, CURRENT.snapshot(root))
            self.apply(root, provider, self.native(root, provider, "--confirm"))
            reviewer = self.roles(root, provider)["reviewer"]
            reviewer.write_bytes(reviewer.read_bytes() + b"\n# unreviewed body\n")
            before = CURRENT.snapshot(root)
            self.assertFalse(check_execution_protocol(root, provider)["confirmed"])
            self.assertEqual(before, CURRENT.snapshot(root))

    def test_published_confirmed_pair_compatibility(self):
        # Released 0.2.2 choices equal its old bases; they must still stay pinned.
        published = subprocess.check_output(
            ["git", "show", "337ccf0dce0c466d53ffce695dfd84f817f82719:domestique.sh"],
            cwd=CURRENT.SOURCE.parent, text=True)
        root = self.fixture.root("published-confirmed")
        self.fixture.run_dom(root, script=published)
        selected = {}
        for provider in PROVIDERS:
            reviewer = self.roles(root, provider)["reviewer"]
            reviewer.write_bytes(reviewer.read_bytes().replace(b"Read, Bash, Glob, Grep", b"Read, Grep")
                                 .replace(b'"search", "execute"', b'"search"'))
            selected[provider] = self.call(root, provider, "verify")["selected"]
            self.apply(root, provider, self.call(root, provider, "prepare", selected[provider]))
        before = {str(p): p.read_bytes() for provider in PROVIDERS
                  for p in self.roles(root, provider).values()}
        self.fixture.run_dom(root)
        for provider in PROVIDERS:
            state = self.call(root, provider, "verify")
            self.assertTrue(state["confirmed"])
            self.assertEqual(state["selected"], selected[provider])
            for p in self.roles(root, provider).values():
                self.assertEqual(before[str(p)], p.read_bytes())
        stable = CURRENT.snapshot(root)
        for provider in PROVIDERS:
            self.assertTrue(self.call(root, provider, "verify")["confirmed"])
        self.assertEqual(stable, CURRENT.snapshot(root))
        for provider in PROVIDERS:
            path = self.roles(root, provider)["reviewer"]
            path.write_bytes(path.read_bytes() + b"\n# manual edit\n")
            self.assertFalse(self.call(root, provider, "verify")["confirmed"])

    def test_actual_installer_defaults_override_inherit_and_exact_rerun(self):
        root = self.area / "fresh"
        root.mkdir()
        subprocess.run(["git", "init", "-q", str(root)], env=self.env, check=True)
        self.fixture.run_dom(root)
        defaults = {
            "claude": (("sonnet", None), ("opus", None)),
            "codex": (("gpt-5.6-sol", "medium"), ("gpt-5.6-terra", "high")),
            "copilot": ((None, None), (None, None)),
        }
        for provider in PROVIDERS:
            state = self.call(root, provider, "verify")
            self.assertTrue(state["confirmed"])
            self.assertEqual(state["selected"], {
                role: dict(zip(("model", "effort"), value))
                for role, value in zip(("implementer", "reviewer"), defaults[provider])})
            for role, path in self.roles(root, provider).items():
                base = root / PROVIDERS[provider] / ".domestique/base" / path.relative_to(root)
                self.assertNotIn(b"# domestique-model-setup:", base.read_bytes())
        stable = CURRENT.snapshot(root)
        inodes = {p: p.stat().st_ino for p in root.rglob("*") if p.is_file()}
        self.fixture.run_dom(root)
        self.assertEqual(stable, CURRENT.snapshot(root))
        self.assertEqual(inodes, {p: p.stat().st_ino for p in inodes})
        for provider in PROVIDERS:
            module = self.namespace(self.seed, provider)
            roles = self.roles(root, provider)
            impl = roles["implementer"]
            original = self.call(root, provider, "verify")["selected"]
            choice = dict(original["implementer"], effort=None if provider == "copilot" else "high")
            data = module["patch"](impl.read_bytes(), "implementer", choice)
            data += b"\n# confirmed custom prompt\n"
            data = data.replace(b"effort: \"high\"", b'effort: "high" # keep exact effort')
            data = data.replace(b'model_reasoning_effort = "high"',
                                b'model_reasoning_effort = "high" # keep exact effort')
            impl.write_bytes(data)
            original["implementer"] = choice
            self.apply(root, provider, self.call(root, provider, "prepare", original))
            for value in ('literal/model-"quoted"\\exact=a:b', "inherit"):
                before = {p: p.read_bytes() for h in PROVIDERS for p in self.roles(root, h).values()}
                all_before = CURRENT.snapshot(root)
                args = ("--platform", provider, "--model", f"{provider}:implementer={value}")
                self.fixture.run_dom(root, "--dry-run", *args)
                self.assertEqual(all_before, CURRENT.snapshot(root))
                self.fixture.run_dom(root, *args)
                expected = module["patch"](before[impl], "implementer",
                                           {"model": None if value == "inherit" else value},
                                           model_only=True)
                self.assertEqual(module["split_marker"](impl.read_bytes(), "implementer")[0].encode(),
                                 expected)
                for path, old in before.items():
                    if path != impl:
                        self.assertEqual(old, path.read_bytes())
                state = self.call(root, provider, "verify")
                self.assertTrue(state["confirmed"])
                self.assertEqual(state["selected"]["implementer"]["effort"], choice["effort"])
                base = root / PROVIDERS[provider] / ".domestique/base" / impl.relative_to(root)
                self.assertNotIn(b"literal/model", base.read_bytes())
                self.assertNotIn(b"confirmed custom prompt", base.read_bytes())
            before = self.call(root, provider, "verify")["selected"]
            self.fixture.run_dom(root, "--platform", provider, "--force")
            state = self.call(root, provider, "verify")
            self.assertTrue(state["confirmed"])
            self.assertEqual(before, state["selected"])
            self.assertNotIn(b"confirmed custom prompt", impl.read_bytes())
            if provider != "copilot":
                self.assertIn(b"# keep exact effort", impl.read_bytes())

    def test_actual_installer_unconfirmed_unknown_and_partial_refuse(self):
        for kind in ("stale", "custom", "partial", "unknown", "missing-helper",
                     "custom-inventory", "current-without-helper-inventory"):
            with self.subTest(kind=kind):
                root = self.project()
                roles = self.roles(root, "codex")
                if kind == "stale":
                    self.apply(root, "codex", self.prepare(root, "codex"))
                    roles["reviewer"].write_bytes(roles["reviewer"].read_bytes() + b"\n# manual\n")
                elif kind == "custom":
                    roles["reviewer"].write_bytes(roles["reviewer"].read_bytes() + b"\n# legacy custom\n")
                elif kind == "partial":
                    roles["reviewer"].unlink()
                elif kind == "unknown":
                    manifest = root / ".codex/.domestique/manifest"
                    manifest.write_text(manifest.read_text().replace("domestique_version=0.2.2",
                                                                    "domestique_version=unknown"))
                elif kind in ("custom-inventory", "current-without-helper-inventory"):
                    manifest = root / ".codex/.domestique/manifest"
                    remove = (",.agents/skills/domestique/SKILL.md"
                              if kind == "custom-inventory" else
                              ",.codex/domestique-model-setup.py")
                    manifest.write_text(manifest.read_text().replace(remove, ""))
                    if kind == "current-without-helper-inventory":
                        self.helper(root, "codex").unlink()
                        (root / ".codex/.domestique/base/.codex/domestique-model-setup.py").unlink()
                else:
                    self.helper(root, "codex").unlink()
                    (root / ".codex/.domestique/base/.codex/domestique-model-setup.py").unlink()
                before = CURRENT.snapshot(root)
                for dry in (("--dry-run",), ()):
                    result = self.fixture.run_dom(root, *dry, "--model=codex:implementer=new", ok=False)
                    if kind in ("unknown", "custom-inventory", "current-without-helper-inventory"):
                        self.assertIn("unknown inventory generation", result.stderr)
                    elif kind == "missing-helper":
                        self.assertIn("missing claimed helper", result.stderr)
                    self.assertEqual(before, CURRENT.snapshot(root))
                if kind in ("stale", "custom"):
                    old = {p: p.read_bytes() for p in roles.values()}
                    self.fixture.run_dom(root, "--platform", "codex", ok=False)
                    self.assertEqual(old, {p: p.read_bytes() for p in roles.values()})
                    self.assertFalse(self.call(root, "codex", "verify")["confirmed"])
                else:
                    self.fixture.run_dom(root, ok=False)
                    self.assertEqual(before, CURRENT.snapshot(root))

    def test_actual_installer_partial_publication_never_marks_failed_pair(self):
        root = self.area / "failure"
        root.mkdir()
        subprocess.run(["git", "init", "-q", str(root)], env=self.env, check=True)
        source = CURRENT.SCRIPT.replace(
            "            os.replace(temp, path)",
            "            if HARNESS == 'codex' and rel == pair.paths['reviewer']:\n"
            "                raise OSError('injected reviewer publication failure')\n"
            "            os.replace(temp, path)")
        self.assertNotEqual(source, CURRENT.SCRIPT)
        result = self.fixture.run_dom(root, script=source, ok=False)
        self.assertIn("injected reviewer publication failure", result.stderr)
        self.assertIn("claude:configured", result.stderr)
        self.assertIn('"partial": true', result.stderr)
        state = subprocess.run([sys.executable, "-I", "-B", str(self.helper(root, "claude")), "verify"],
                               cwd=root, env=self.env, capture_output=True, text=True, check=True)
        self.assertTrue(json.loads(state.stdout)["confirmed"])
        self.assertFalse(self.roles(root, "codex")["implementer"].exists())
        self.assertFalse(self.roles(root, "copilot")["implementer"].exists())

    def test_actual_v010_upgrade_preserves_models_and_configures_defaults(self):
        root, _ = self.fixture.legacy_claude("model-v010", ref="v0.1.0")
        lib = self.namespace(self.seed, "claude")
        expected = {r: lib["parse"](p.read_bytes(), r)[1]["model"]
                    for r, p in self.roles(root, "claude").items()}
        before = CURRENT.snapshot(root)
        result = self.fixture.run_dom(root, "--dry-run")
        self.assertIn("claude: legacy -> configured locally", result.stdout)
        self.assertEqual(before, CURRENT.snapshot(root))
        self.fixture.run_dom(root)
        for provider in PROVIDERS:
            state = self.call(root, provider, "verify")
            self.assertTrue(state["confirmed"])
            if provider == "claude":
                self.assertEqual(expected, {r: c["model"] for r, c in state["selected"].items()})
                for path in self.roles(root, provider).values():
                    self.assertIn("## Active harness boundary (claude only)", path.read_text())
                    self.assertIn("description: Claude Code only;", path.read_text())
            elif provider == "codex":
                self.assertEqual(state["selected"], {
                    "implementer": {"model": "gpt-5.6-sol", "effort": "medium"},
                    "reviewer": {"model": "gpt-5.6-terra", "effort": "high"}})
            else:
                self.assertEqual(state["selected"], {
                    r: {"model": None, "effort": None} for r in ("implementer", "reviewer")})

    def test_actual_v010_custom_tools_preserves_partner_until_save(self):
        root, _ = self.fixture.legacy_claude("model-v010-tools", ref="v0.1.0")
        roles = self.roles(root, "claude")
        lib = self.namespace(self.seed, "claude")
        old = {r: p.read_bytes() for r, p in roles.items()}
        text = old["implementer"].replace(b"tools: ", b"tools: mcp__example__search, ", 1)
        roles["implementer"].write_bytes(text)
        before = CURRENT.snapshot(root)
        self.fixture.run_dom(root, "--platform", "claude", "--dry-run", "--force", ok=False)
        self.assertEqual(before, CURRENT.snapshot(root))
        self.fixture.run_dom(root, "--platform", "claude", "--force", ok=False)
        state = self.call(root, "claude", "verify")
        self.assertFalse(state["confirmed"])
        for role, path in roles.items():
            self.assertEqual(state["selected"][role]["model"], lib["parse"](old[role], role)[1]["model"])
            base = root / ".claude/.domestique/base" / path.relative_to(root)
            self.assertEqual(base.read_bytes(), old[role])
            self.assertTrue(path.read_bytes().endswith(old[role].split(b"\n---\n", 1)[1]))
        self.assertIn(b"tools: mcp__example__search, ", roles["implementer"].read_bytes())
        self.assertNotIn(b"mcp__example__search", roles["reviewer"].read_bytes())
        migrated = {r: p.read_bytes() for r, p in roles.items()}
        self.fixture.run_dom(root, "--platform", "claude", "--force", ok=False)
        self.assertEqual(migrated, {r: p.read_bytes() for r, p in roles.items()})
        before = CURRENT.snapshot(root)
        review = self.native(root, "claude", "--confirm")
        self.assertEqual(review["chosen"], state["selected"])
        self.assertEqual(before, CURRENT.snapshot(root))
        self.assertTrue(self.apply(root, "claude", review)["confirmed"])
        self.fixture.run_dom(root, "--platform", "claude")
        self.assertTrue(self.call(root, "claude", "verify")["confirmed"])
        self.assertEqual(roles["reviewer"].read_bytes(), migrated["reviewer"])
        for role, path in roles.items():
            self.assertEqual(lib["split_marker"](path.read_bytes(), role)[0].encode(), migrated[role])

    def test_historical_inventory_table_matches_repository_sources(self):
        # Read actual source, never project-supplied inventory authority. Exercise
        # the production finite-set builder without installing a version matrix.
        block = CURRENT.SCRIPT.split("    historical = {\n", 1)[1]
        block = "historical = {\n" + block.split("\n    def merge_for", 1)[0]
        block = block.replace("\n    ", "\n")
        import itertools
        from types import SimpleNamespace
        for provider in PROVIDERS:
            helper = f"{PROVIDERS[provider]}/domestique-model-setup.py"
            policies = {"claude": ["CLAUDE.md", "CLAUDE.local.md"],
                        "codex": ["AGENTS.md", "AGENTS.override.md"],
                        "copilot": [".github/copilot-instructions.md"]}[provider]
            manifest = self.seed / PROVIDERS[provider] / ".domestique/manifest"
            files = next(line[6:] for line in manifest.read_text().splitlines()
                         if line.startswith("files="))
            files = ",".join(p for p in files.split(",") if p not in policies)
            namespace = dict(provider=provider, policies=policies, itertools=itertools, files=files,
                             layout=SimpleNamespace(helper=helper))
            exec(compile(block, "<installer inventory builder>", "exec"), namespace)
            recognized = namespace["recognized"]
            observed = set()
            refs = ("v0.1.0", "76d217f", "6158d35", "8cb30cb", "4dc26fd",
                    "9f33930", "v0.2.0", "v0.2.1", "v0.2.2")
            for ref in refs:
                source = subprocess.check_output(
                    ["git", "-C", str(CURRENT.SOURCE.parent), "show", ref + ":domestique.sh"],
                    text=True)
                version = re.search(r'^DOMESTIQUE_VERSION="([^"]+)"', source, re.M)[1]
                inventories = re.findall(r'^\s*MANAGED_PLAIN_FILES="([^"$]+)"', source, re.M)
                if provider == "claude" and ref == "v0.1.0":
                    inventory = re.search(r'^MANAGED_FILES="([^"]+)"', source, re.M)[1]
                    self.assertIn((version, inventory), recognized)
                    continue
                if provider == "copilot":
                    if "COPILOT_ENTRIES='" not in source:
                        continue
                    entries = source.split("COPILOT_ENTRIES='", 1)[1].split("'", 1)[0]
                    inventory = ",".join(line.split("|")[0] for line in entries.splitlines())
                    if 'COPILOT_FILES="$COPILOT_OLD_FILES,.github/domestique-model-setup.py"' in source:
                        inventory += "," + helper
                else:
                    inventory = next((i for i in inventories
                                      if i.startswith(PROVIDERS[provider])), None)
                    if inventory is None:  # This historical source predates the provider.
                        continue
                for count in range(len(policies) + 1):
                    for subset in itertools.combinations(policies, count):
                        observed.add((version, inventory + "".join("," + p for p in subset)))
            for count in range(len(policies) + 1):
                for subset in itertools.combinations(policies, count):
                    observed.add(("0.2.2", files + "".join("," + p for p in subset)))
            self.assertEqual(recognized, observed)

    def test_actual_installer_helper_return_race_refuses_final_success(self):
        # Deterministic fault at the exact apply-return/caller handoff, not an
        # environment hook or a timing race. Only this disposable script changes.
        anchor = "            outcome = pair.apply(**result)\n"
        self.assertEqual(CURRENT.SCRIPT.count(anchor), 1)
        for kind in ("hash", "inode"):
            with self.subTest(kind=kind):
                root = self.project()
                injection = (
                    "            for rel in (pair.helper, f'{pair.state}/base/{pair.helper}'):\n"
                    "                path = root / rel\n"
                    "                data = path.read_bytes()\n"
                    + ("                path.write_bytes(data + b'\\n# concurrent fixture edit\\n')\n"
                       if kind == "hash" else
                       "                temporary = path.with_name(path.name + '.fixture')\n"
                       "                temporary.write_bytes(data)\n"
                       "                os.replace(temporary, path)\n"))
                source = CURRENT.SCRIPT.replace(anchor, anchor + injection)
                result = self.fixture.run_dom(root, "--platform", "claude", script=source, ok=False)
                self.assertEqual(result.returncode, 3)
                self.assertIn("Final model verification: claude: state changed after pair publication",
                              result.stderr)
                # The v1 marker binds roles, not dependencies. Its continuing
                # validity must NOT be mistaken for lifecycle success.
                state = self.call(root, "claude", "verify")
                self.assertTrue(state["confirmed"])
                self.assertEqual(self.helper(root, "claude").read_bytes(),
                                 (root / ".claude/.domestique/base/.claude/domestique-model-setup.py")
                                 .read_bytes())

    def test_prepare_verify_cancel_denied_zero_writes_all_formats(self):
        for provider in PROVIDERS:
            with self.subTest(provider=provider):
                root = self.project()
                before = CURRENT.snapshot(root)
                status = self.call(root, provider, "verify")
                self.assertEqual(status["scope"], "filesystem-only")
                self.assertFalse(status["confirmed"])
                prepared = self.prepare(root, provider)
                self.assertEqual(prepared, self.prepare(root, provider))
                self.assertIn("--- a/", prepared["plan"]["diff"])
                self.assertEqual(len(prepared["plan"]["snapshot"]["files"]), 7)
                # Cancel / denied write approval have no apply call or staging.
                self.assertEqual(before, CURRENT.snapshot(root))
                self.assertFalse(list(root.rglob(".domestique-model-setup-*")))

    def test_exact_preservation_inheritance_manual_reconfirmation(self):
        for provider in PROVIDERS:
            with self.subTest(provider=provider):
                root = self.project()
                roles = self.roles(root, provider)
                original = {}
                for role, path in roles.items():
                    text = path.read_text()
                    if provider == "codex":
                        text = text.replace('developer_instructions = """\n',
                                            'developer_instructions = """\nCustom native prompt preface.\n')
                        text = re.sub(r'(?m)^model = "[^"]*"$',
                                      'model = "old"  # retained model', text)
                        text = text.replace('model_reasoning_effort = "medium"',
                                            'model_reasoning_effort = "medium"  # retained effort')
                        text = text.replace('model_reasoning_effort = "high"',
                                            'model_reasoning_effort = "high"  # retained effort')
                        text += '\n[extra]\nmodel = "table-model"\n'
                    else:
                        if provider == "claude":
                            text = text.replace("model: sonnet", 'model: "old"  # retained model')
                            text = text.replace("model: opus", 'model: "old"  # retained model')
                        else:
                            text = text.replace("---\n", '---\nmodel: "old"  # retained model\n', 1)
                        text += "\nCustom role body without final newline"
                    text = text.replace("\n", "\r\n")
                    path.write_bytes(text.encode())
                    path.chmod(0o640)
                    original[role] = path.read_bytes()
                plan = self.prepare(root, provider)
                self.assertTrue(self.apply(root, provider, plan)["confirmed"])
                module = self.namespace(root, provider)
                for role, path in roles.items():
                    bare, _ = module["split_marker"](path.read_bytes(), role)
                    expected = module["patch"](original[role], role, self.choices(provider)[role])
                    self.assertEqual(bare.encode(), expected)
                    self.assertEqual(path.stat().st_mode & 0o777, 0o640)
                    self.assertIn(b"  # retained model\r\n", path.read_bytes())
                    self.assertNotIn(b"\n", path.read_bytes().replace(b"\r\n", b""))
                    if provider == "codex":
                        self.assertTrue(path.read_bytes().endswith(b'[extra]\r\nmodel = "table-model"\r\n'))
                        self.assertEqual(tomllib.loads(path.read_text())["developer_instructions"],
                                         tomllib.loads(original[role].decode())["developer_instructions"])
                    else:
                        self.assertTrue(path.read_bytes().endswith(b"Custom role body without final newline"))
                        self.assertEqual(path.read_bytes().split(b"---\r\n", 2)[2],
                                         original[role].split(b"---\r\n", 2)[2])
                inherited = self.prepare(root, provider, True)
                self.assertTrue(self.apply(root, provider, inherited)["confirmed"])
                for path in roles.values():
                    self.assertIn(b"  # retained model\r\n", path.read_bytes())
                # Valid custom instructions invalidate hashes, not ownership.
                path = roles["reviewer"]
                path.write_bytes(path.read_bytes() + (b"# manual\r\n" if provider == "codex" else b"\r\nmanual"))
                self.assertFalse(self.call(root, provider, "verify")["confirmed"])
                reconfirm = self.prepare(root, provider, True)
                self.assertIn("domestique-model-setup:", reconfirm["plan"]["diff"])
                self.assertTrue(self.apply(root, provider, reconfirm)["confirmed"])

    def test_readonly_prepare_verify_and_apply_permissions(self):
        for provider in PROVIDERS:
            for kind in ("roles", "parents", "both"):
                with self.subTest(provider=provider, kind=kind):
                    root = self.project()
                    roles = self.roles(root, provider)
                    # Start confirmed so read-only verification must validate hashes too.
                    self.apply(root, provider, self.prepare(root, provider))
                    paths = list(roles.values()) if kind in ("roles", "both") else []
                    if kind in ("parents", "both"):
                        paths += sorted((p for p in (root / PROVIDERS[provider]).rglob("*")
                                         if p.is_dir()),
                                        key=lambda p: len(p.parts), reverse=True)
                        paths += [root / PROVIDERS[provider], root]
                    modes = {p: p.stat().st_mode & 0o777 for p in paths}
                    for path, mode in modes.items():
                        path.chmod(mode & ~0o222)
                        self.addCleanup(path.chmod, mode)
                    before = CURRENT.snapshot(root)
                    prepared = self.prepare(root, provider, True)
                    self.assertTrue(self.call(root, provider, "verify")["confirmed"])
                    result = self.apply(root, provider, prepared, ok=False)
                    self.assertIn("not writable", result.stderr)
                    self.assertEqual(before, CURRENT.snapshot(root))
                    self.assertFalse(list(root.rglob(".domestique-model-setup-*")))
                    for path, mode in reversed(list(modes.items())):
                        path.chmod(mode)
                    # A filesystem mode change is stale evidence, not sandbox approval.
                    before = CURRENT.snapshot(root)
                    result = self.apply(root, provider, prepared, ok=False)
                    self.assertIn("stale/tampered plan", result.stderr)
                    self.assertEqual(before, CURRENT.snapshot(root))
                    self.assertTrue(self.apply(root, provider, self.prepare(root, provider, True))["confirmed"])

    def test_execution_write_permission_is_not_snapshot_state(self):
        for provider in PROVIDERS:
            with self.subTest(provider=provider):
                root = self.project()
                before = CURRENT.snapshot(root)
                prepared = self.call(root, provider, "prepare", self.choices(provider),
                                     deny_write_access=True)
                self.assertEqual(prepared, self.prepare(root, provider))
                self.assertFalse(self.call(root, provider, "verify",
                                           deny_write_access=True)["confirmed"])
                result = self.call(root, provider, "apply", prepared["digest"], prepared["plan"],
                                   ok=False, deny_write_access=True)
                self.assertIn("not writable", result.stderr)
                self.assertEqual(before, CURRENT.snapshot(root))
                self.assertFalse(list(root.rglob(".domestique-model-setup-*")))
                self.assertTrue(self.apply(root, provider, prepared)["confirmed"])

    def test_native_structure_live_and_pristine_zero_write_refusal(self):
        for provider in PROVIDERS:
            root = self.project()
            prepared = self.prepare(root, provider)
            for role, live in self.roles(root, provider).items():
                base = root / PROVIDERS[provider] / ".domestique/base" / live.relative_to(root)
                for authority, path in (("live", live), ("base", base)):
                    original = path.read_text()
                    separator = " = " if provider == "codex" else ": "
                    invalid = {
                        "wrong-name": re.sub(r"(?m)^name.*$", 'name' + separator + '"wrong-role"', original),
                        "missing-name": re.sub(r"(?m)^name.*\n", "", original),
                        "non-string-name": re.sub(r"(?m)^name.*$", "name" + separator + "false", original),
                        "missing-description": re.sub(r"(?m)^description.*\n", "", original),
                        "empty-description": re.sub(r"(?m)^description.*$", 'description' + separator + '""', original),
                        "non-string-description": re.sub(r"(?m)^description.*$", "description" + separator + "42", original),
                    }
                    if provider == "codex":
                        prefix = original.split("developer_instructions =", 1)[0]
                        invalid.update({
                            "missing-prompt": prefix,
                            "empty-prompt": prefix + 'developer_instructions = "  "\n',
                            "non-string-prompt": prefix + 'developer_instructions = ["prompt"]\n',
                            "table-prompt": prefix + '[developer_instructions]\nbody = "prompt"\n',
                        })
                    else:
                        front = original.split("---\n", 2)
                        invalid["missing-prompt"] = "---\n" + front[1] + "---\n"
                        invalid["empty-prompt"] = invalid["missing-prompt"] + " \n\t\n"
                    for defect, text in invalid.items():
                        with self.subTest(provider=provider, role=role, authority=authority, defect=defect):
                            try:
                                path.write_text(text)
                                before = CURRENT.snapshot(root)
                                self.call(root, provider, "prepare", self.choices(provider), ok=False)
                                self.call(root, provider, "verify", ok=False)
                                self.apply(root, provider, prepared, ok=False)
                                self.assertEqual(before, CURRENT.snapshot(root))
                                self.assertFalse(list(root.rglob(".domestique-model-setup-*")))
                            finally:
                                path.write_text(original)

    def test_tampered_digest_choices_body_path_root_and_replay(self):
        for provider in PROVIDERS:
            root = self.project()
            prepared = self.prepare(root, provider)
            for mutation in ("digest", "choices", "body", "path", "root", "diff"):
                with self.subTest(provider=provider, mutation=mutation):
                    altered = copy.deepcopy(prepared)
                    if mutation == "digest":
                        altered["digest"] = "0" * 64
                    elif mutation == "choices":
                        altered["plan"]["choices"]["reviewer"]["model"] = "different"
                    elif mutation == "root":
                        altered["plan"]["root"] = str(self.seed)
                    elif mutation == "diff":
                        altered["plan"]["diff"] += "unapproved"
                    else:
                        altered["plan"][mutation] = "unapproved override"
                    before = CURRENT.snapshot(root)
                    self.apply(root, provider, altered, ok=False)
                    self.assertEqual(before, CURRENT.snapshot(root))
            self.apply(root, provider, prepared)
            before = CURRENT.snapshot(root)
            self.apply(root, provider, prepared, ok=False)
            self.assertEqual(before, CURRENT.snapshot(root))

    def test_stale_every_file_and_parent_identity(self):
        for provider in PROVIDERS:
            for kind in range(8):
                with self.subTest(provider=provider, kind=kind):
                    root = self.project()
                    prepared = self.prepare(root, provider)
                    paths = list(prepared["plan"]["snapshot"]["files"])
                    path = root / paths[kind] if kind < 7 else self.roles(root, provider)["reviewer"].parent
                    moved = path.with_name(path.name + ".moved")
                    path.rename(moved)
                    if kind < 7:
                        shutil.copy2(moved, path)
                    else:
                        shutil.copytree(moved, path)
                    before = CURRENT.snapshot(root)
                    self.apply(root, provider, prepared, ok=False)
                    self.assertEqual(before, CURRENT.snapshot(root))

    def test_unsafe_files_and_writability(self):
        for provider in PROVIDERS:
            for kind in ("symlink", "hardlink", "directory", "fifo", "mode", "parent-mode"):
                with self.subTest(provider=provider, kind=kind):
                    root = self.project()
                    path = self.roles(root, provider)["reviewer"]
                    data = path.read_bytes()
                    if kind == "parent-mode":
                        path.parent.chmod(0o777)
                        self.addCleanup(path.parent.chmod, 0o700)
                    elif kind == "mode":
                        path.chmod(0o666)
                    else:
                        path.unlink()
                        if kind == "symlink":
                            path.symlink_to(self.roles(root, provider)["implementer"])
                        elif kind == "hardlink":
                            os.link(self.roles(root, provider)["implementer"], path)
                        elif kind == "directory":
                            path.mkdir()
                        else:
                            os.mkfifo(path)
                    # Avoid a generic snapshot trying to read a FIFO.
                    result = self.call(root, provider, "prepare", self.choices(provider), ok=False)
                    self.assertTrue(result.stderr)
                    self.assertFalse(list(root.rglob(".domestique-model-setup-*")))
                    if kind in ("mode", "parent-mode"):
                        self.assertEqual(data, path.read_bytes())

    def test_external_modified_helper_unowned_and_wrong_root(self):
        for provider in PROVIDERS:
            root = self.project()
            helper = self.helper(root, provider)
            helper.write_bytes(b'raise RuntimeError("UNTRUSTED EXECUTED")\n')
            result = self.call(root, provider, "verify", ok=False)
            self.assertNotIn("RuntimeError: UNTRUSTED EXECUTED", result.stderr)
            self.assertIn("Modified helper", result.stderr)
            root = self.project()
            manifest = root / PROVIDERS[provider] / ".domestique/manifest"
            manifest.write_text(manifest.read_text().replace("," + str(self.helper(root, provider).relative_to(root)), ""))
            self.call(root, provider, "verify", ok=False)
            root = self.project()
            child = root / "child"
            child.mkdir()
            self.call(root, provider, "verify", cwd=child, ok=False)
            prepared = self.prepare(root, provider)
            other = self.project()
            self.call(other, provider, "apply", prepared["digest"], prepared["plan"], ok=False)

    def test_controls_duplicate_inputs_and_unsupported_effort(self):
        for provider in PROVIDERS:
            root = self.project()
            for control in ("\n", "\x7f", "\x85", "\ud800", "\u2028", "\u2029"):
                value = self.choices(provider)
                value["reviewer"]["model"] += control
                self.call(root, provider, "prepare", value, ok=False)
            self.call(root, provider, "prepare", '{"implementer":null,"implementer":null}', ok=False)
            roles = self.roles(root, provider)
            path = roles["reviewer"]
            prefix = b'model = "duplicate"\n' if provider == "codex" else b'model: "one"\nmodel: "two"\n'
            if provider == "codex":
                path.write_bytes(prefix + path.read_bytes())
            else:
                path.write_bytes(path.read_bytes().replace(b"---\n", b"---\n" + prefix, 1))
            self.call(root, provider, "verify", ok=False)
        root = self.project()
        value = self.choices("copilot")
        value["implementer"]["effort"] = "high"
        self.call(root, "copilot", "prepare", value, ok=False)

    def test_prepublication_race_and_failed_second_publish(self):
        for provider in PROVIDERS:
            for failure in ("preflight", "before-replace", "second-publish", "unknown-temp", "edited-temp"):
                with self.subTest(provider=provider, failure=failure):
                    root = self.project()
                    self.apply(root, provider, self.prepare(root, provider))
                    prepared = self.prepare(root, provider, True)
                    module = self.namespace(root, provider)
                    cwd = Path.cwd()
                    os.chdir(root)
                    try:
                        pair = module["Pair"]()
                        real_snapshot, real_replace = pair.snapshot, os.replace
                        real_mkstemp = tempfile.mkstemp
                        calls = 0
                        replaced = []
                        initial = {r: p.read_bytes() for r, p in self.roles(root, provider).items()}
                        def snapshot():
                            nonlocal calls
                            calls += 1
                            if failure == "preflight" and calls == 2:
                                p = self.roles(root, provider)["reviewer"]
                                p.write_bytes(p.read_bytes() + b"\n# concurrent\n")
                            if failure == "edited-temp" and calls == 3:
                                for temporary in root.rglob(".domestique-model-setup-*"):
                                    temporary.write_bytes(b"unknown leftover")
                            return real_snapshot()
                        def replace(src, dest):
                            if failure == "second-publish" and len(replaced) == 1:
                                raise OSError("injected second publication failure")
                            replaced.append(str(dest))
                            return real_replace(src, dest)
                        def mkstemp(*args, **kwargs):
                            fd, name = real_mkstemp(*args, **kwargs)
                            if failure in ("before-replace", "unknown-temp"):
                                p = self.roles(root, provider)["reviewer"]
                                p.write_bytes(p.read_bytes() + b"\n# concurrent\n")
                            if failure == "unknown-temp":
                                os.unlink(name)
                                Path(name).write_bytes(b"unknown leftover")
                            return fd, name
                        with patch.object(pair, "snapshot", snapshot), patch.object(os, "replace", replace), \
                                patch.object(tempfile, "mkstemp", mkstemp):
                            with self.assertRaises(ValueError):
                                module["publish"](pair, prepared["plan"], prepared["digest"])
                        roles = self.roles(root, provider)
                        if failure == "second-publish":
                            self.assertEqual(roles["reviewer"].read_bytes(), initial["reviewer"])
                            self.assertNotIn(b"# domestique-model-setup:", roles["implementer"].read_bytes())
                        else:
                            self.assertEqual(roles["implementer"].read_bytes(), initial["implementer"])
                        leftovers = list(root.rglob(".domestique-model-setup-*"))
                        self.assertEqual(len(leftovers), 1 if failure in ("unknown-temp", "edited-temp") else 0)
                        if leftovers:
                            self.assertEqual(leftovers[0].read_bytes(), b"unknown leftover")
                    finally:
                        os.chdir(cwd)
                    self.assertEqual(self.call(root, provider, "verify")["confirmed"], failure == "edited-temp")

    def test_old_inventory_upgrade_guest_privacy_and_scoped_uninstall(self):
        root = self.project()
        for provider, directory in PROVIDERS.items():
            helper = self.helper(root, provider)
            relative = str(helper.relative_to(root))
            helper.unlink()
            (root / directory / ".domestique/base" / relative).unlink()
            manifest = root / directory / ".domestique/manifest"
            manifest.write_text(manifest.read_text().replace("," + relative, ""))
            # The recognized pre-helper generation also predates dom-models.
            model_path = MODELS[provider]
            (root / model_path).unlink()
            (root / directory / ".domestique/base" / model_path).unlink()
            manifest.write_text(manifest.read_text().replace("," + model_path, ""))
            manifest.write_text(manifest.read_text().replace("domestique_version=0.2.2",
                                                            "domestique_version=0.1.0"))
            ownership = root / directory / ".domestique/guest-excludes"
            if ownership.exists():
                ownership.write_text(ownership.read_text().replace(relative + "\n", "")
                                     .replace(model_path + "\n", ""))
            role = self.roles(root, provider)["reviewer"]
            role.write_bytes(role.read_bytes() + b"\n# customized body\n")
        self.fixture.run_dom(root, "--guest", ok=False)
        for provider in PROVIDERS:
            self.assertTrue(self.helper(root, provider).is_file())
            self.assertIn(b"# customized body", self.roles(root, provider)["reviewer"].read_bytes())
            result = subprocess.run(["git", "check-ignore", "-q", str(self.helper(root, provider))],
                                    cwd=root, env=self.env)
            self.assertEqual(result.returncode, 0)
            self.assertFalse(self.call(root, provider, "verify")["confirmed"])
        self.fixture.run_dom(root, "--platform", "codex", "--uninstall")
        self.assertFalse(self.helper(root, "codex").exists())
        self.assertTrue(self.helper(root, "claude").exists())
        self.assertTrue(self.helper(root, "copilot").exists())
        self.assertTrue((root / CURRENT.SHARED).exists())

    def test_installer_refuses_modified_unowned_helper_without_merge(self):
        for provider, directory in PROVIDERS.items():
            for kind in ("modified", "unowned"):
                with self.subTest(provider=provider, kind=kind):
                    root = self.project()
                    helper = self.helper(root, provider)
                    if kind == "modified":
                        helper.write_bytes(helper.read_bytes() + b"\n# custom executable\n")
                    else:
                        (root / directory / ".domestique/base" / helper.relative_to(root)).unlink()
                    before = CURRENT.snapshot(root)
                    self.fixture.run_dom(root, "--platform", provider, ok=False)
                    self.assertEqual(before, CURRENT.snapshot(root))


if __name__ == "__main__":
    unittest.main(verbosity=2)
