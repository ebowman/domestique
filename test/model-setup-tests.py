"""Installed shared emitter: filesystem guarantees, never native qualification."""
import copy
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
        return root

    def helper(self, root, provider):
        return root / PROVIDERS[provider] / "domestique-model-setup.py"

    def roles(self, root, provider):
        impl = dict(zip(PROVIDERS, CURRENT.ROLES))[provider]
        return {r: root / impl.replace("implementer", r) for r in ("implementer", "reviewer")}

    def bootstrap(self, root, provider):
        rel = {"claude": ".claude/commands/dom-decompose.md",
               "codex": ".agents/skills/domestique-decompose/SKILL.md",
               "copilot": ".github/skills/domestique-v2-copilot-decompose/SKILL.md"}[provider]
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

    def prepare(self, root, provider, inherit=False):
        return self.call(root, provider, "prepare", self.choices(provider, inherit))

    def apply(self, root, provider, prepared, ok=True):
        return self.call(root, provider, "apply", prepared["digest"], prepared["plan"], ok=ok)

    def namespace(self, root, provider):
        helper = self.helper(root, provider)
        namespace = {"__file__": str(helper), "__name__": "tested_helper"}
        exec(compile(helper.read_bytes(), str(helper), "exec"), namespace)
        return namespace

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
                        text = text.replace('model = "gpt-5.6-terra"', 'model = "old"  # retained model')
                        text = text.replace('model = "gpt-5.6"', 'model = "old"  # retained model')
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
            ownership = root / directory / ".domestique/guest-excludes"
            if ownership.exists():
                ownership.write_text(ownership.read_text().replace(relative + "\n", ""))
            role = self.roles(root, provider)["reviewer"]
            role.write_bytes(role.read_bytes() + b"\n# customized body\n")
        self.fixture.run_dom(root, "--guest")
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
