"""Offline current-candidate projection tests; never native qualification."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
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
        self.root = WORK / self._testMethodName
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

    def install(self, *flags, **kwargs):
        return self.run_dom("--platform", "copilot", *flags, **kwargs)

    def hidden(self, path):
        return self.git("check-ignore", "-q", path).returncode == 0

    def test_install_native_contents_and_routing(self):
        # A restricted PATH proves missing Copilot does not block installation.
        bindir = WORK / "bin"
        bindir.mkdir(exist_ok=True)
        python = bindir / "python3"
        if not python.exists():
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
                "No setup delegation of ANY kind", "two-role questionnaire INLINE",
                "exact physical Git worktree root", "snapshot_format=1",
                "platform=copilot", "implementer_sha256", "reviewer_sha256",
                "excluding only the entire", "ANY edit", "stale hash",
                "Reviewer: exact native model ID or native inheritance",
                "Inheritance removes the model field", "complete detailed diff on request",
                "Save these choices?", "ZERO target writes", "marker LAST",
                "exec(compile(code", "assert code == read(base)",
                "Prepare is READ-ONLY", "independently retained",
                "fresh Copilot invocation/reload", "human disposition",
                "Optional exact-origin/loaded-file attestation", "NOT prerequisites",
                "competing project/ancestor/", "Actual observed mismatch/unavailability",
                "Send no conflicting spawn model override", "No fallback",
            ):
                self.assertIn(required, text)
        ordinary = (self.root / ".github/skills/domestique-v2-copilot/SKILL.md").read_text()
        self.assertIn("no ordinary/bootstrap questionnaire", ordinary)
        self.assertIn("one explicitly assigned bounded bead", ordinary)

    def test_old_role_guard_upgrade_preserves_custom_pair(self):
        # Bounded pristine role bytes from 9f339305a4f900176b647248f68907499dcc0620.
        # Seed only the two owned role snapshots, as in old-inventory helper tests.
        # Synthetic confirmation tests hash invalidation, NOT native consent.
        parent = self.root
        for mode in ("normal", "guest"):
            for custom in (False, True):
                with self.subTest(mode=mode, custom=custom):
                    self.root = parent / f"{mode}-{custom}"
                    self.root.mkdir()
                    self.git("init", "-q")
                    self.install(*(["--guest"] if mode == "guest" else []))
                    current = {r: (self.root / rel).read_text() for r, rel in ROLES.items()}
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
                    marker = dict(v=1, project=str(self.root.resolve()), harness="copilot")
                    marker.update({r + "_sha256": hashlib.sha256(text.encode()).hexdigest()
                                   for r, text in pair.items()})
                    marker_line = MARKER + json.dumps(marker) + "\n"
                    for role, rel in ROLES.items():
                        text = pair[role]
                        if role == "implementer":
                            text = text[:4] + marker_line + text[4:]
                        (self.root / rel).write_text(text)
                    before = snapshot(self.root)
                    self.install("--dry-run")
                    self.assertEqual(snapshot(self.root), before)
                    self.install()
                    for role, rel in ROLES.items():
                        path = self.root / rel
                        text = path.read_text()
                        self.assertIn(DELEGATED, text)
                        self.assertNotIn("Before applying ANY instructions below", text)
                        old_body = pair[role].split("Delegated role only:", 1)[1]
                        self.assertEqual(text.split("Delegated role only:", 1)[1], old_body)
                        if custom:
                            self.assertIn('model: "custom-native-id"', text)
                            self.assertIn('custom: "retained"', text)
                            self.assertIn("Custom discovery.", text)
                            self.assertNotIn('"execute"', text)
                        clean = "".join(line for line in text.splitlines(keepends=True)
                                        if not line.startswith(MARKER))
                        self.assertNotEqual(hashlib.sha256(clean.encode()).hexdigest(),
                                            marker[role + "_sha256"])
                        self.assertEqual((self.root / STATE / "base" / rel).read_text(),
                                         current[role])
                    self.assertIn(marker_line, (self.root / ROLES["implementer"]).read_text())
                    upgraded = snapshot(self.root)
                    self.install()
                    self.assertEqual(snapshot(self.root), upgraded)

    def test_role_guard_migration_and_current_tampering_refuse_atomically(self):
        parent = self.root
        for mode in ("normal", "guest"):
            self.root = parent / mode
            self.root.mkdir()
            self.git("init", "-q")
            self.install(*(["--guest"] if mode == "guest" else []))
            for role, rel in ROLES.items():
                path = self.root / rel
                base = self.root / STATE / "base" / rel
                current = path.read_text()
                legacy = (OLD_ROLES / f"{role}.agent.md").read_text()
                for generation, source in (("old", legacy), ("current", current)):
                    base.write_text(source)
                    prefix, task = source.split("Delegated role only:", 1)
                    front, guard = prefix.split("\n## Active harness boundary", 1)
                    guard = "\n## Active harness boundary" + guard
                    mutations = {
                        "removed": front + "Delegated role only:" + task,
                        "tampered": source.replace("STOP", "CONTINUE", 1),
                        "quoted": front + "Delegated role only:" + task + "\n```text\n" + guard + "```\n",
                        "wrong-surface": legacy if generation == "current" else current,
                        "malformed": source.replace("---\n", "BROKEN\n", 1),
                        "unowned": source,
                        "tampered-base": source,
                    }
                    for kind, changed in mutations.items():
                        with self.subTest(mode=mode, role=role, generation=generation, kind=kind):
                            path.write_text(changed)
                            base.write_text(source)
                            if kind == "unowned":
                                base.unlink()
                            elif kind == "tampered-base":
                                base.write_text(source.replace("STOP", "CONTINUE", 1))
                            before = snapshot(self.root)
                            directories = {p.relative_to(self.root) for p in self.root.rglob("*")
                                           if p.is_dir()}
                            for flags in ((), ("--force", "--dry-run")):
                                result = self.install(*flags, ok=False)
                                self.assertEqual(result.returncode, 3)
                                self.assertIn("No project writes", result.stderr)
                                self.assertEqual(snapshot(self.root), before)
                                self.assertEqual(directories, {
                                    p.relative_to(self.root) for p in self.root.rglob("*") if p.is_dir()})
                            base.write_text(source)
                path.write_text(current)
                base.write_text(current)

    def test_rerun_merge_marker_and_modified_removal(self):
        self.install()
        pair = {}
        for role, rel in ROLES.items():
            path = self.root / rel
            text = path.read_text().replace("\n---\n", '\nmodel: "custom-native-id"\ncustom: "retained"\n---\n', 1)
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
        # A real three-way upgrade retains metadata and marker, never reapproves.
        revised = WORK / "revised-dom.sh"
        revised.write_text(DOM.read_text().replace(
            "Return a terse summary: files changed, actual validation/results, discovered",
            "Return a brief summary: files changed, actual validation/results, discovered"))
        self.install(dom=revised)
        changed = (self.root / ROLES["implementer"]).read_text()
        self.assertIn("Return a brief summary:", changed)
        self.assertIn('custom: "retained"', changed)
        self.assertIn("Custom implementer discovery text.", changed)
        self.assertIn('tools: ["read", "edit", "search"]', changed)
        self.assertIn(MARKER + json.dumps(marker), changed)
        clean = "".join(line for line in changed.splitlines(keepends=True)
                        if not line.startswith(MARKER)).encode()
        self.assertNotEqual(hashlib.sha256(clean).hexdigest(), marker["implementer_sha256"])
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
        revised = WORK / "custom-descriptions-upgrade.sh"
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
                self.run_dom()
                for rel, text in expected.items():
                    self.assertEqual((self.root / rel).read_text(), text)
                self.run_dom(dom=revised)
                for rel, text in expected.items():
                    for old, new in changes.items():
                        text = text.replace(old, new)
                    self.assertEqual((self.root / rel).read_text(), text)
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
                    self.run_dom(dom=revised, ok=False)
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
                                self.assertIn("No project writes", result.stderr)
                                self.assertEqual(snapshot(self.root), before)
                                self.assertEqual(
                                    {p.relative_to(self.root) for p in self.root.rglob("*") if p.is_dir()},
                                    directories)
                        path.write_text(original)

    def test_guarded_description_merge_conflicts_refuse_without_writes(self):
        self.run_dom("--platform", "codex", "--guest")
        self.install("--guest")
        for harness in ("codex", "copilot"):
            for role in ("implementer", "reviewer"):
                rel = ROLES[role] if harness == "copilot" else f".codex/agents/{role}.toml"
                path = self.root / rel
                original = path.read_text()
                line = next(s for s in original.splitlines() if s.startswith("description"))
                field = "description: " if harness == "copilot" else "description = "
                local = field + json.dumps(DESCRIPTION_GUARDS[harness] + " Custom local remainder.")
                upstream = field + json.dumps(DESCRIPTION_GUARDS[harness] + " New upstream remainder.")
                path.write_text(original.replace(line, local))
                source = DOM.read_text()
                self.assertEqual(source.count(line), 1)
                revised = WORK / f"conflict-{harness}-{role}.sh"
                revised.write_text(source.replace(line, upstream))
                before = snapshot(self.root)
                for flags in ((), ("--force",), ("--dry-run",), ("--no-guest",)):
                    with self.subTest(harness=harness, role=role, flags=flags):
                        result = self.run_dom(*flags, dom=revised, ok=False)
                        self.assertEqual(result.returncode, 3)
                        self.assertIn("conflict", result.stderr)
                        self.assertIn(rel, result.stderr)
                        self.assertEqual(snapshot(self.root), before)
                # Also validate the *merged* description, not merely the live
                # role: an upstream edit cannot drop the discovery boundary.
                path.write_text(original)
                revised.write_text(source.replace(line, field + '"Use only in Claude"'))
                before = snapshot(self.root)
                for flags in ((), ("--force",), ("--dry-run",)):
                    result = self.run_dom(*flags, dom=revised, ok=False)
                    self.assertIn("discovery description", result.stderr)
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
                                capture_output=True, text=True, cwd=WORK)
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
        outside = WORK / "outside-role"
        outside.write_bytes(original)
        path.symlink_to(outside)
        tree = snapshot(self.root)
        self.install("--no-guest", ok=False)
        self.assertEqual(snapshot(self.root), tree)
        self.assertEqual(outside.read_bytes(), original)
        path.unlink()
        path.write_bytes(original)
        (self.root / STATE / "unknown-authority").write_text("unknown\n")
        tree = snapshot(self.root)
        self.install("--force", ok=False)
        self.assertEqual(snapshot(self.root), tree)
        (self.root / STATE / "unknown-authority").unlink()
        # User and upstream change the same owned line: refuse before mode writes.
        path.write_bytes(original.replace(b"Return a terse summary:", b"Return my special summary:"))
        revised = WORK / "conflict-dom.sh"
        revised.write_text(DOM.read_text().replace("Return a terse summary:", "Return a brief summary:"))
        tree = snapshot(self.root)
        self.install("--no-guest", dom=revised, ok=False)
        self.assertEqual(snapshot(self.root), tree)

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
