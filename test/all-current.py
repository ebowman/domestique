"""Current standalone all-provider contract. Offline, no native clients."""
import itertools
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "domestique.sh"
SCRIPT = SOURCE.read_text()
STATES = {
    "claude": ".claude/.domestique",
    "codex": ".codex/.domestique",
    "copilot": ".github/.domestique",
}
ROLES = (
    ".claude/agents/implementer.md",
    ".codex/agents/implementer.toml",
    ".github/agents/domestique-v2-copilot-implementer.agent.md",
)
SHARED = ".agents/skills/dom-goal/SKILL.md"
POLICY_ANCHOR = "loop for each bead. Stop and report between beads."
VERSION = re.search(r'^DOMESTIQUE_VERSION="([^"]+)"', SCRIPT, re.M).group(1)
GUIDE = ("https://github.com/ebowman/domestique/blob/main/"
         "docs/install-upgrade-design.md#remote-install-and-upgrade")
LABELS = {"claude": "Claude Code", "codex": "Codex", "copilot": "GitHub Copilot"}


def snapshot(root):
    return {
        str(p.relative_to(root)): (
            p.lstat().st_mode, p.lstat().st_mtime_ns,
            os.readlink(p) if p.is_symlink() else p.read_bytes() if p.is_file() else None,
        )
        for p in root.rglob("*")
    }


def byte_snapshot(root):
    # Customized three-way merges may republish unchanged bytes. The rerun
    # contract is byte/mode stability; dry-run still checks mtimes above.
    return {rel: (mode, data) for rel, (mode, _mtime, data) in snapshot(root).items()}


class AllProviders(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="domestique-all-")
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name).resolve()
        self.bin = self.work / "bin"
        self.bin.mkdir()
        (self.bin / "python3").symlink_to(sys.executable)
        self.env = dict(os.environ, HOME=str(self.work / "home"),
                        PATH=f"{self.bin}:/usr/bin:/bin:/usr/sbin:/sbin")
        for key in ("BASH_ENV", "ENV", "CDPATH", "PYTHONPATH"):
            self.env.pop(key, None)
        for client in ("claude", "codex", "copilot", "domestique2", "bd"):
            self.assertIsNone(shutil.which(client, path=self.env["PATH"]))

    def root(self, name):
        root = self.work / name
        root.mkdir()
        subprocess.run(["git", "init", "-q", str(root)], check=True, env=self.env)
        return root

    def run_dom(self, root, *args, ok=True, script=SCRIPT, env=None):
        # No path to the source, launcher or even a target argument: cwd is an
        # independent temp project. All installed bytes must come from stdin.
        result = subprocess.run(["bash", "-s", "--", *args], cwd=root,
                                input=script, text=True, capture_output=True,
                                env=env or self.env)
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn("\nDone.\n", result.stdout)
        return result

    def installed(self, root):
        return {p for p, state in STATES.items() if (root / state).exists()}

    def seed(self, root, providers, *flags):
        for provider in providers:
            self.run_dom(root, "--platform", provider, *flags)
        self.assertEqual(self.installed(root), set(providers))

    def assert_notice(self, result, root, modes, *, explicit=False, dry=False):
        output = result.stdout
        self.assertIn(f"VERSION {VERSION}", output)
        self.assertIn(f"Target: {root}", output)
        selection = next(line for line in output.splitlines() if line.startswith("Selected:"))
        for provider, label in LABELS.items():
            if provider in modes:
                self.assertIn(f"{label} ({modes[provider]})", selection)
            else:
                self.assertNotIn(label, selection)
        self.assertEqual("No --platform:" in output, not explicit)
        if not explicit:
            self.assertIn("fresh installs AND reruns", output)
            self.assertIn("ALL Claude Code, Codex and GitHub Copilot", output)
        self.assertIn("both remains Claude+Codex", output)
        self.assertIn("Project config only", output)
        self.assertIn("not native clients/model software", output)
        self.assertIn("retain model choices", output)
        self.assertIn("--force can replace", output)
        self.assertIn("independently in each harness", output)
        self.assertIn("reload/start a fresh invocation", output)
        self.assertIn("not native readiness", output)
        self.assertIn("| bash -s -- --dry-run", output)
        self.assertIn("| bash -s -- --platform claude", output)
        self.assertIn("migration, refusals and recovery", output)
        self.assertIn(GUIDE, output)
        self.assertEqual("(dry-run; no target changes)" in output, dry)
        self.assertLess(output.index(GUIDE), output.index("Summary"))

    def test_fresh_stdin_default_all_and_rerun(self):
        root = self.root("fresh")
        before = snapshot(root)
        modes = dict.fromkeys(STATES, "normal")
        self.assert_notice(self.run_dom(root, "--dry-run"), root, modes, dry=True)
        self.assertEqual(before, snapshot(root))
        self.assert_notice(self.run_dom(root), root, modes)
        self.assertEqual(self.installed(root), set(STATES))
        for role in ROLES:
            self.assertTrue((root / role).is_file())
        for path in root.rglob("*.md"):
            if ".git" not in path.parts:
                body = path.read_text()
                self.assertNotIn(str(SOURCE.parent), body)
                self.assertNotIn("preview/launcher", body)
                self.assertNotIn("current/bin", body)
        self.assertFalse((root / ".beads").exists())
        before = snapshot(root)
        self.assert_notice(self.run_dom(root), root, modes)
        self.assertEqual(before, snapshot(root))
        self.assert_notice(self.run_dom(root, "--platform=all"), root, modes, explicit=True)
        self.assertEqual(before, snapshot(root))

    def assert_static_inventory(self, root):
        """Physical discovery surfaces, NOT observed native discovery/dispatch."""
        inventory = {}
        for directory in (".agents/skills", ".github/skills", ".claude/skills"):
            for path in (root / directory).glob("*/SKILL.md"):
                name = re.search(r"(?m)^name: (.+)$", path.read_text()).group(1)
                inventory.setdefault(name, []).append(path)
        expected = {
            "dom-goal", "dom-decompose", "domestique", "domestique-goal",
            "domestique-decompose", "domestique-v2-copilot",
            "domestique-v2-copilot-goal", "domestique-v2-copilot-decompose",
        }
        self.assertEqual(set(inventory), expected)
        for name, paths in inventory.items():
            self.assertEqual(len(paths), 1, name)
            self.assertFalse(paths[0].is_symlink())
            body = paths[0].read_text()
            if name in ("dom-goal", "dom-decompose"):
                self.assertEqual(paths[0], root / f".agents/skills/{name}/SKILL.md")
                for text in ("description: Codex or Copilot only.",
                             "Unknown, ambiguous, or unsupported callers STOP",
                             "Merely loading or implicitly matching this skill is not",
                             "loading the routed body cannot grant it.",
                             "Preserve the ORIGINAL user request verbatim"):
                    self.assertIn(text, body)
                for rel in (f".agents/skills/domestique-{name[4:]}/SKILL.md",
                            f".github/skills/domestique-v2-copilot-{name[4:]}/SKILL.md"):
                    self.assertIn(rel, body)
                    self.assertTrue((root / rel).is_file())
            else:
                harness = "copilot" if "copilot" in name else "codex"
                self.assertIn(f"description: {harness.capitalize()} only;", body)
                self.assertIn(f"These instructions apply only to the native `{harness}` client.", body)
                self.assertIn("An explicit foreign-harness invocation must STOP without setup", body)
                self.assertIn("skill matching/loading and this text are NOT caller identity.", body)
                # Boundary precedes the real ordinary/bootstrap or setup gate.
                gate = ({"domestique": "## Role model gate",
                         "domestique-v2-copilot": "## Read-only role gate"}.get(
                             name, f"## {harness.capitalize()} first-use role setup"))
                after_guard = body.index("and /dom-goal commands, but do not invoke them automatically.")
                self.assertIn(gate, body[after_guard:])
                if name == "domestique":
                    self.assertIn("Instruction/bootstrap loading alone neither starts setup nor grants goal",
                                  body)
                    self.assertIn("do not start another questionnaire", body)
                elif name == "domestique-v2-copilot":
                    self.assertIn("no ordinary/bootstrap questionnaire", body)
                    self.assertIn("never authorize an epic by matching", body)
        for provider, impl in zip(STATES, ROLES):
            for role in ("implementer", "reviewer"):
                body = (root / impl.replace("implementer", role)).read_text()
                label = "Claude Code" if provider == "claude" else provider.capitalize()
                self.assertRegex(body, rf'description[:= ]+"?{label} only;')
                if provider == "codex":
                    self.assertIn("ambiguous callers stop without work. Installed directories do not identify it.",
                                  body)
                else:
                    self.assertIn("An explicit foreign-harness invocation must STOP without setup", body)
        commands = list((root / ".claude/commands").glob("*.md"))
        self.assertEqual({p.stem for p in commands},
                         {"dom-goal", "dom-decompose", "goal", "decompose"})
        for path in commands:
            body = path.read_text()
            self.assertIn("description: Claude Code only;", body)
            self.assertIn("These instructions apply only to the native `claude` client.", body)
            self.assertIn("An explicit foreign-harness invocation must STOP without setup", body)
        for rel, harness in (("CLAUDE.md", "claude"), ("CLAUDE.local.md", "claude"),
                             ("AGENTS.md", "codex"),
                             (".github/copilot-instructions.md", "copilot")):
            path = root / rel
            if path.exists() and "<!-- BEGIN domestique" in path.read_text():
                self.assertIn(f"These instructions apply only to the native `{harness}` client.",
                              path.read_text())
                self.assertIn("Other harnesses must ignore this entire owned policy block",
                              path.read_text())

    def assert_private_union(self, root, guest, remaining, host_exclude):
        exclude = (root / ".git/info/exclude").read_text()
        self.assertTrue(exclude.startswith(host_exclude))
        expected = set()
        if guest:
            if "claude" in remaining:
                expected.update(("CLAUDE.local.md", ".claude/"))
            for provider in ("codex", "copilot"):
                if provider in remaining:
                    expected.update((root / STATES[provider] / "guest-excludes").read_text().splitlines())
            if remaining & {"codex", "copilot"}:
                expected.add(".agents/.domestique/")
                expected.update((root / ".agents/.domestique/guest-excludes").read_text().splitlines())
        if expected:
            block = exclude.split("# BEGIN domestique (managed)\n", 1)[1].split("# END domestique", 1)[0]
            lines = block.splitlines()
            self.assertEqual(set(lines), expected)
            self.assertEqual(len(lines), len(expected))
        else:
            self.assertNotIn("# BEGIN domestique (managed)", exclude)

    def test_combined_confirmed_pair_update_and_complete_lifecycle(self):
        # Synthetic confirmations test the emitted hash contract, not consent
        # or native model availability. Each harness has a distinct pair.
        marker_prefix = "# domestique-model-setup: "
        changes = {
            "claude": ("Keep the return small.", "Keep the return concise."),
            "codex": ("- Stay inside the brief. Do not refactor adjacent code or start another bead.",
                      "- Stay inside the brief. Do not refactor adjacent code or start another bead. (updated)"),
            "copilot": ("Return a terse summary: files changed, actual validation/results, discovered",
                        "Return a brief summary: files changed, actual validation/results, discovered"),
        }
        for guest in (False, True):
            with self.subTest(guest=guest):
                root = self.root(f"combined-{guest}")
                home = Path(self.env["HOME"])
                home.mkdir(exist_ok=True)
                (home / ".gitconfig").write_text("# isolated host configuration\n")
                host_home = snapshot(home)
                (root / "host.txt").write_text("tracked host bytes\n")
                subprocess.run(["git", "-C", str(root), "add", "host.txt"],
                               env=self.env, check=True)
                index = (root / ".git/index").read_bytes()
                exclude = root / ".git/info/exclude"
                host_exclude = exclude.read_text() + "\n# host exclusion\nhost-private/\n"
                exclude.write_text(host_exclude)
                flags = ("--guest",) if guest else ()
                before = snapshot(self.work)
                self.run_dom(root, *flags, "--dry-run")
                self.assertEqual(before, snapshot(self.work))
                self.run_dom(root, *flags)
                self.assert_static_inventory(root)
                self.assert_private_union(root, guest, set(STATES), host_exclude)
                before = byte_snapshot(root)
                self.run_dom(root)
                self.assertEqual(before, byte_snapshot(root))
                pairs, markers = {}, {}
                for provider, impl in zip(STATES, ROLES):
                    pair = {}
                    for role in ("implementer", "reviewer"):
                        path = root / impl.replace("implementer", role)
                        text = path.read_text()
                        model = f"fixture-{provider}-{role}"
                        if provider == "codex":
                            text = re.sub(r'(?m)^model = .+$', f'model = "{model}"', text)
                            text += f'\n[fixture]\nmetadata = "{provider}-{role}"\n'
                        else:
                            text = re.sub(r"(?m)^model: .+\n", "", text)
                            text = text.replace("\n---\n",
                                                f'\nmodel: "{model}"\nfixture: "{provider}-{role}"\n---\n', 1)
                            # Independently preserve actual native tools fields.
                            text = text.replace("Read, Write, Edit, Bash, Glob, Grep",
                                                "Read, Edit, Bash, Grep")
                            text = text.replace('"search", "execute"', '"search"')
                        pair[role] = text.encode()
                    marker = dict(v=1, project=str(root.resolve()), harness=provider)
                    marker.update({r + "_sha256": hashlib.sha256(data).hexdigest()
                                   for r, data in pair.items()})
                    line = (marker_prefix + json.dumps(marker) + "\n").encode()
                    data = pair["implementer"]
                    pair["implementer"] = (line + data if provider == "codex"
                                           else data[:4] + line + data[4:])
                    for role, data in pair.items():
                        (root / impl.replace("implementer", role)).write_bytes(data)
                    pairs[provider], markers[provider] = pair, line
                before = byte_snapshot(root)
                self.run_dom(root)
                self.assertEqual(before, byte_snapshot(root))
                upstream = SCRIPT
                for changed, (old, new) in changes.items():
                    self.assertEqual(upstream.count(old), 1)
                    upstream = upstream.replace(old, new)
                    before = snapshot(self.work)
                    self.run_dom(root, "--dry-run", script=upstream)
                    self.assertEqual(before, snapshot(self.work))
                    self.run_dom(root, script=upstream)
                    pairs[changed]["implementer"] = pairs[changed]["implementer"].replace(
                        old.encode(), new.encode())
                    for provider, impl in zip(STATES, ROLES):
                        marker = json.loads(markers[provider].decode()[len(marker_prefix):])
                        for role, expected in pairs[provider].items():
                            data = (root / impl.replace("implementer", role)).read_bytes()
                            self.assertEqual(data, expected)  # tools, metadata, marker, body
                            clean = data.replace(markers[provider], b"")
                            valid = hashlib.sha256(clean).hexdigest() == marker[role + "_sha256"]
                            updated = list(changes).index(provider) <= list(changes).index(changed)
                            self.assertEqual(valid, role == "reviewer" or not updated)
                    before = byte_snapshot(root)
                    self.run_dom(root, script=upstream)
                    self.assertEqual(before, byte_snapshot(root))
                self.assert_static_inventory(root)
                # Branch the SAME configured fixture for full versus scoped removal.
                full = self.work / f"full-{guest}"
                shutil.copytree(root, full)
                for target, selections in ((full, (None,)), (root, ("codex", "claude", "copilot"))):
                    remaining = set(STATES)
                    for selected in selections:
                        args = ("--uninstall",) + (("--platform", selected) if selected else ())
                        before = snapshot(self.work)
                        self.run_dom(target, *args, "--dry-run", script=upstream)
                        self.assertEqual(before, snapshot(self.work))
                        self.run_dom(target, *args, script=upstream)
                        removed = {selected} if selected else set(STATES)
                        remaining -= removed
                        self.assertEqual(self.installed(target), remaining)
                        self.assertEqual((target / SHARED).exists(),
                                         bool(remaining & {"codex", "copilot"}))
                        self.assert_private_union(target, guest, remaining, host_exclude)
                        for provider, impl in zip(STATES, ROLES):
                            for role, data in pairs[provider].items():
                                path = target / impl.replace("implementer", role)
                                if provider in remaining:
                                    self.assertEqual(path.read_bytes(), data)
                                elif provider in removed:
                                    kept = list(path.parent.glob(path.name + ".uninstalled.*"))
                                    self.assertEqual(len(kept), 1)
                                    self.assertEqual(kept[0].read_bytes(), data)
                        self.assertEqual((target / ".git/index").read_bytes(), index)
                        self.assertFalse((target / ".beads").exists())
                self.assertEqual(host_home, snapshot(home))

    def test_absolute_target_system_ancestor_alias(self):
        root = self.root("absolute-target")
        # Do not resolve the tempfile spelling: macOS supplies /var/... while
        # the physical project lives under /private/var/....
        target = str(Path(self.tmp.name) / root.name)
        (root / "AGENTS.md").write_text("host instructions\n")
        self.run_dom(root, target)
        self.assertEqual(self.installed(root), set(STATES))
        self.assertEqual(len(list(root.glob("AGENTS.md.bak.*"))), 1)
        before = snapshot(root)
        self.run_dom(root, target)
        self.assertEqual(before, snapshot(root))

    def test_all_seven_persisted_subsets(self):
        for count in (1, 2, 3):
            for providers in itertools.combinations(STATES, count):
                with self.subTest(providers=providers):
                    root = self.root("-".join(providers))
                    self.seed(root, providers)
                    # State membership, not exact canonical string equality.
                    value = ",".join(reversed(providers)) + "\n"
                    for provider in providers:
                        (root / STATES[provider] / "platforms").write_text(value)
                    self.run_dom(root)
                    self.assertEqual(self.installed(root), set(STATES))
                    for state in STATES.values():
                        self.assertEqual((root / state / "platforms").read_text(),
                                         "claude,codex,copilot\n")
                    before = snapshot(root)
                    self.run_dom(root)
                    self.assertEqual(before, snapshot(root))

    def test_explicit_selectors_additive_and_both_not_copilot(self):
        for selector, expected in (
            ("claude", {"claude"}), ("codex", {"codex"}),
            ("copilot", {"copilot"}), ("both", {"claude", "codex"}),
            ("all", set(STATES)),
        ):
            root = self.root(selector)
            self.assert_notice(self.run_dom(root, f"--platform={selector}"), root,
                               dict.fromkeys(expected, "normal"), explicit=True)
            self.assertEqual(self.installed(root), expected)
            self.run_dom(root, "--platform", "both")
            self.assertEqual(self.installed(root), expected | {"claude", "codex"})
        root = self.work / "both"
        self.assertEqual((root / ".claude/commands/dom-goal.md").read_bytes(),
                         (root / ".claude/commands/goal.md").read_bytes())
        self.assertTrue((root / ".agents/skills/domestique-goal/SKILL.md").is_file())

    def test_legacy_claude_codex_upgrade_without_platform_markers(self):
        old = subprocess.check_output(
            ["git", "-C", str(SOURCE.parent), "show", "64f4e09:domestique.sh"],
            text=True,
        )
        for provider in ("claude", "codex"):
            for guest in (False, True):
                with self.subTest(provider=provider, guest=guest):
                    root = self.root(f"{provider}-{guest}")
                    self.run_dom(root, "--platform", provider,
                                 *(("--guest",) if guest else ()), script=old)
                    (root / STATES[provider] / "platforms").unlink()
                    before = snapshot(self.work)
                    self.run_dom(root, "--dry-run")
                    self.assertEqual(before, snapshot(self.work))
                    self.run_dom(root)
                    self.assertEqual(self.installed(root), set(STATES))
                    self.assertTrue((root / ".agents/.domestique/manifest").is_file())
                    self.assertFalse((root / ".codex/.domestique/base" / SHARED).exists())
                    for state in STATES.values():
                        self.assertEqual((root / state / "mode").exists(), guest)

    def legacy_claude(self, name, *, guest=False, ref="415fb69"):
        # Public Git objects only: v0.1.0 is the released normal installer;
        # 415fb69 is the last Claude-only installer, including sticky guest.
        old = subprocess.check_output(
            ["git", "-C", str(SOURCE.parent), "show", f"{ref}:domestique.sh"],
            text=True,
        )
        root = self.root(name)
        # Normal recovery adds host text after removing the old managed region.
        # Avoid an unrelated same-second backup from the initial old install.
        if guest:
            (root / "CLAUDE.md").write_bytes(b"# Host instructions\nKeep host bytes.\n")
        self.run_dom(root, *(("--guest",) if guest else ()), script=old)
        state = root / STATES["claude"]
        manifest = (state / "manifest").read_text()
        rel = "CLAUDE.local.md" if guest else "CLAUDE.md"
        self.assertIn("snapshot_format=1\n", manifest)
        self.assertNotIn("platform=", manifest)
        self.assertIn(rel, next(line for line in manifest.splitlines()
                               if line.startswith("files=")).split("=", 1)[1].split(","))
        self.assertTrue((state / f"base/{rel}.block").is_file())
        return root, rel

    def test_platformless_legacy_claude_policy_recovery(self):
        for ref, guest in (("v0.1.0", False), ("415fb69", False), ("415fb69", True)):
            for missing in (False, True):
                with self.subTest(ref=ref, guest=guest, missing=missing):
                    root, rel = self.legacy_claude(
                        f"legacy-{ref}-{guest}-{missing}", guest=guest, ref=ref)
                    policy = root / rel
                    host = b"# Host instructions\nKeep host bytes.\n"
                    # The legitimate old base remains after the owner removes
                    # the managed region, or removes the live policy entirely.
                    if missing:
                        policy.unlink()
                    else:
                        policy.write_bytes(host)
                        policy.chmod(0o600)
                    private = [root / STATES["claude"], root / ".claude/agents"]
                    for directory in private:
                        directory.chmod(0o700)
                    for evidence in ("manifest", f"base/{rel}.block"):
                        path = root / STATES["claude"] / evidence
                        path.chmod(0o600)
                        private.append(path)
                    for role, model in (("implementer", "opus"), ("reviewer", "sonnet")):
                        path = root / f".claude/agents/{role}.md"
                        body = re.sub(r"(?m)^model: .+$", f"model: {model}",
                                      path.read_text())
                        path.write_text(body + "\nPublic fixture role customization.\n")
                        path.chmod(0o600)
                        private.append(path)
                    modes = {p: p.stat().st_mode for p in private}
                    old_backups = {p: p.read_bytes() for p in root.glob(f"{rel}.bak.*")}
                    before = snapshot(root)
                    self.run_dom(root, "--dry-run")
                    self.assertEqual(before, snapshot(root))
                    self.run_dom(root)
                    self.assertEqual(self.installed(root), set(STATES))
                    self.assertEqual(modes, {p: p.stat().st_mode for p in private})
                    if not missing:
                        self.assertTrue(policy.read_bytes().startswith(host))
                        self.assertEqual(policy.stat().st_mode & 0o777, 0o600)
                        backups = [p for p in root.glob(f"{rel}.bak.*") if p not in old_backups]
                        self.assertEqual(len(backups), 1)
                        self.assertEqual(backups[0].read_bytes(), host)
                        self.assertEqual(backups[0].stat().st_mode & 0o777, 0o600)
                    else:
                        self.assertEqual(set(root.glob(f"{rel}.bak.*")), set(old_backups))
                    self.assertEqual(old_backups, {p: p.read_bytes() for p in old_backups})
                    if guest:
                        self.assertEqual((root / "CLAUDE.md").read_bytes(), host)
                        for state in STATES.values():
                            self.assertEqual((root / state / "mode").read_text(), "guest\n")
                    for role, model in (("implementer", "opus"), ("reviewer", "sonnet")):
                        body = (root / f".claude/agents/{role}.md").read_text()
                        self.assertIn(f"\nmodel: {model}\n", body)
                        self.assertIn("Public fixture role customization.", body)
                        self.assertNotIn("# domestique-model-setup:", body)
                    self.assertIn("platform=claude\n",
                                  (root / STATES["claude"] / "manifest").read_text())

    def test_platformless_legacy_claude_invalid_ownership_zero_writes(self):
        for guest in (False, True):
            root, rel = self.legacy_claude(f"invalid-{guest}", guest=guest)
            (root / rel).write_text("# Host policy without managed markers\n")
            manifest = root / STATES["claude"] / "manifest"
            original = manifest.read_text()
            invalid = {
                "foreign": original + "platform=codex\n",
                "empty": original + "platform=\n",
                "duplicate-platform": original + "platform=claude\nplatform=claude\n",
                "ambiguous-platform": original + "platform=\nplatform=claude\n",
                "unsupported-schema": original.replace("snapshot_format=1", "snapshot_format=2"),
                "missing-schema": original.replace("snapshot_format=1\n", ""),
                "duplicate-schema": original + "snapshot_format=1\n",
                "malformed": original + "not-a-field\n",
                "extra-equals": original + "platform=claude=other\n",
                "duplicate-inventory": original + f"files={rel}\n",
                "duplicate-file": re.sub(r"(?m)^(files=.*)$", rf"\1,{rel}", original),
                "unowned-base": re.sub(r"(?m)^files=.*$", "files=.claude/agents/implementer.md",
                                       original),
            }
            for kind, body in invalid.items():
                with self.subTest(guest=guest, kind=kind):
                    manifest.write_text(body)
                    before = snapshot(root)
                    for flags in (("--dry-run",), (), ("--force",)):
                        result = self.run_dom(root, *flags, ok=False)
                        self.assertIn("unowned policy base collision", result.stderr)
                        self.assertIn("No project writes", result.stderr)
                        self.assertEqual(before, snapshot(root))
            manifest.unlink()
            before = snapshot(root)
            self.run_dom(root, ok=False)
            self.assertEqual(before, snapshot(root))

    def test_platformless_legacy_claude_unsafe_evidence_zero_writes(self):
        for evidence in ("manifest", "base/CLAUDE.md.block"):
            for kind in ("symlink", "hardlink", "directory", "parent-symlink"):
                with self.subTest(evidence=evidence, kind=kind):
                    root, rel = self.legacy_claude(f"unsafe-{kind}-{evidence.replace('/', '-')}")
                    (root / rel).unlink()
                    path = root / STATES["claude"] / evidence
                    outside = self.work / f"outside-{root.name}"
                    if kind == "parent-symlink":
                        path.parent.rename(outside)
                        path.parent.symlink_to(outside, target_is_directory=True)
                    else:
                        path.rename(outside)
                        if kind == "symlink":
                            path.symlink_to(outside)
                        elif kind == "hardlink":
                            os.link(outside, path)
                        else:
                            path.mkdir()
                    before = snapshot(self.work)
                    for flags in (("--dry-run",), (), ("--force",)):
                        result = self.run_dom(root, *flags, ok=False)
                        self.assertIn("unsafe", result.stderr)
                        self.assertEqual(before, snapshot(self.work))

    def test_platformless_ownership_exception_exact_state_and_provider(self):
        # Exercise the actual helper in isolation as well as policy_preflight:
        # absence must not become generic provider/shared-state ownership.
        helpers = "\n".join(
            f"{name}() {{" + SCRIPT.split(f"{name}() {{", 1)[1].split("\n}\n", 1)[0] + "\n}\n"
            for name in ("shared_safe_path", "snapshot_has_file")
        )
        root, rel = self.legacy_claude("helper")
        for state, provider, valid in (
            (STATES["claude"], "claude", True),
            (STATES["claude"], "codex", False),
            (STATES["codex"], "claude", False),
            (STATES["codex"], "codex", False),
            (STATES["copilot"], "copilot", False),
            (".agents/.domestique", "shared", False),
        ):
            with self.subTest(state=state, provider=provider):
                if state != STATES["claude"]:
                    shutil.copytree(root / STATES["claude"], root / state, dirs_exist_ok=True)
                before = snapshot(root)
                result = subprocess.run(
                    ["bash", "-s", "--", str(root), state, provider, rel],
                    input=helpers + '\nTARGET_DIR="$1"\nsnapshot_has_file "$2" "$3" "$4" .block\n',
                    text=True, capture_output=True, env=self.env)
                self.assertEqual(result.returncode, 0 if valid else 1, result.stderr)
                self.assertEqual(before, snapshot(root))

    def test_wholly_guest_missing_providers_inherit(self):
        for missing in STATES:
            root = self.root(missing)
            self.seed(root, [p for p in STATES if p != missing], "--guest")
            before = snapshot(root)
            self.assert_notice(self.run_dom(root, "--dry-run"), root,
                               dict.fromkeys(STATES, "guest"), dry=True)
            self.assertEqual(before, snapshot(root))
            self.run_dom(root)
            for state in (*STATES.values(), ".agents/.domestique"):
                self.assertEqual((root / state / "mode").read_text(), "guest\n")
            self.assertFalse((root / "CLAUDE.md").exists())
            self.assertFalse((root / "AGENTS.md").exists())
            self.assertFalse((root / ".github/copilot-instructions.md").exists())
            result = subprocess.check_output(
                ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=all"],
                env=self.env, text=True)
            self.assertEqual(result, "")

    def test_mixed_missing_zero_write_refusal_and_explicit_resolution(self):
        for flag in ("--guest", "--no-guest"):
            root = self.root(flag)
            self.seed(root, ["copilot"], "--guest")
            self.run_dom(root, "--platform", "claude", "--no-guest")
            before = snapshot(root)
            for args in ((), ("--dry-run",), ("--force",), ("--platform", "all")):
                result = self.run_dom(root, *args, ok=False)
                self.assertIn("mixed-mode ambiguity", result.stderr)
                self.assertIn("--guest or --no-guest", result.stderr)
                self.assertNotIn("install plan", result.stdout)
                self.assertNotIn("Selected:", result.stdout)
                self.assertEqual(before, snapshot(root))
            self.assert_notice(self.run_dom(root, flag), root,
                               dict.fromkeys(STATES, "guest" if flag == "--guest" else "normal"))
            for state in (*STATES.values(), ".agents/.domestique"):
                self.assertEqual((root / state / "mode").exists(), flag == "--guest")

    def test_existing_mixed_modes_preserved_when_none_missing(self):
        root = self.root("mixed")
        self.run_dom(root)
        # Represent a persisted per-provider mixed mode, independent of the
        # explicit CLI's established additive conversion semantics.
        (root / STATES["claude"] / "mode").write_text("guest\n")
        before = {state: (root / state / "mode").exists() for state in STATES.values()}
        self.assert_notice(self.run_dom(root), root,
                           {"claude": "guest", "codex": "normal", "copilot": "normal"})
        self.assertEqual(before, {s: (root / s / "mode").exists() for s in STATES.values()})
        self.assertFalse(subprocess.run(
            ["git", "-C", str(root), "check-ignore", "-q", SHARED], env=self.env
        ).returncode == 0)

    def test_scoped_uninstall_retains_shared_until_last(self):
        for mode in ("normal", "guest"):
            root = self.root(mode)
            self.run_dom(root, *(["--guest"] if mode == "guest" else []))
            before = snapshot(root)
            self.run_dom(root, "--uninstall", "--platform", "both", "--dry-run")
            self.assertEqual(before, snapshot(root))
            shared = (root / SHARED).read_bytes()
            self.run_dom(root, "--uninstall", "--platform", "both")
            self.assertEqual(self.installed(root), {"copilot"})
            self.assertEqual((root / SHARED).read_bytes(), shared)
            self.run_dom(root, "--uninstall",
                         *(["--platform", "all"] if mode == "guest" else []))
            self.assertEqual(self.installed(root), set())
            self.assertFalse((root / SHARED).exists())

    def test_all_paths_and_parser_preflight_before_writes(self):
        for rel in (".claude/commands/dom-goal.md", ".codex/agents/reviewer.toml",
                    ".github/agents/domestique-v2-copilot-reviewer.agent.md",
                    ".agents/skills/dom-goal/SKILL.md", "AGENTS.md"):
            root = self.root(str(len(list(self.work.iterdir()))))
            path = root / rel
            path.mkdir(parents=True)  # directory is not an output file
            before = snapshot(root)
            self.run_dom(root, ok=False)
            self.assertEqual(before, snapshot(root))
        root = self.root("parser")
        # Stand in for a local Python lacking the required format parser,
        # without installing software or relying on the host Python version.
        (self.bin / "python3").unlink()
        (self.bin / "python3").write_text("#!/bin/sh\nexit 1\n")
        (self.bin / "python3").chmod(0o755)
        before = snapshot(root)
        result = self.run_dom(root, ok=False)
        self.assertIn("tomllib", result.stderr)
        self.assertEqual(before, snapshot(root))

    def test_operational_failure_discloses_partial_result(self):
        root = self.root("partial")
        cp = self.bin / "cp"
        cp.write_text(
            '#!/bin/sh\ncase "$2" in\n'
            '  */.github/agents/*) exit 17 ;;\n'
            'esac\nexec /bin/cp "$@"\n'
        )
        cp.chmod(0o755)
        result = self.run_dom(root, ok=False)
        self.assertEqual(result.returncode, 17)
        self.assertIn("partial results may remain", result.stderr)
        self.assertIn(f"VERSION {VERSION}", result.stdout)
        self.assertIn("install plan", result.stdout)
        self.assertNotIn("\nDone.", result.stdout)
        self.assertTrue((root / ROLES[0]).is_file())
        self.assertFalse((root / ROLES[2]).exists())

    def test_notice_precedes_first_target_mutation_and_dry_run_plan(self):
        # Combined xtrace/output observes real execution order, including mode
        # removal before provider writes and policy backups before role creation.
        for scenario in ("fresh", "host-policy", "conversion", "dry-run"):
            with self.subTest(scenario=scenario):
                root = self.root(scenario)
                args = []
                if scenario == "host-policy":
                    (root / "CLAUDE.md").write_text("host policy\n")
                elif scenario == "conversion":
                    self.run_dom(root, "--guest")
                    args = ["--no-guest"]
                elif scenario == "dry-run":
                    args = ["--dry-run"]
                before = snapshot(root)
                result = subprocess.run(
                    ["bash", "-x", "-s", "--", str(root), *args], cwd=root, input=SCRIPT,
                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    env=self.env, timeout=60)
                self.assertEqual(result.returncode, 0, result.stdout)
                lines = result.stdout.splitlines()
                notice_end = next(i for i, line in enumerate(lines)
                                  if not line.startswith("+") and GUIDE in line)
                writes = []
                for i, line in enumerate(lines):
                    if not re.match(r"^\++ (mkdir|cp|rm|mv|policy_copy) ", line):
                        continue
                    words = shlex.split(line.lstrip("+ "))
                    # Preflight may copy FROM the project into temp staging.
                    # Only destinations count for copy; mv also mutates source.
                    targets = (words[-1:] if words[0] == "cp" else
                               words[2:3] if words[0] == "policy_copy" else words[1:])
                    if any(p == str(root) or p.startswith(str(root) + "/") for p in targets):
                        writes.append(i)
                if scenario == "dry-run":
                    self.assertFalse(writes)
                    self.assertEqual(before, snapshot(root))
                    first_plan = next(i for i, line in enumerate(lines)
                                      if line.startswith("  [dry-run]"))
                    self.assertLess(notice_end, first_plan)
                else:
                    self.assertTrue(writes, result.stdout)
                    self.assertLess(notice_end, min(writes))
                    self.assertNotEqual(before, snapshot(root))
                # The read-only notice resolver must not run a real conversion.
                self.assertFalse(any("converting guest install" in line
                                     and not line.startswith("+")
                                     for line in lines[:notice_end]))

    def test_notice_does_not_consume_stdin_or_prompt(self):
        for args in ((), ("--platform", "claude"), ("--dry-run",)):
            root = self.root(f"stdin-{len(list(self.work.iterdir()))}")
            # Pipe transport: a trailing shell command must still execute.
            result = self.run_dom(root, *args, script=SCRIPT + "\nprintf 'PIPE-END\\n'\n")
            self.assertTrue(result.stdout.endswith("PIPE-END\n"))
            # Script supplied separately: arbitrary stdin remains for the caller.
            result = subprocess.run(
                ["bash", "-c", 'bash "$@" || exit $?\nIFS= read -r remaining\n'
                 'printf "UNCONSUMED:%s\\n" "$remaining"\n',
                 "stdin-check", str(SOURCE), *args],
                cwd=root, input="caller-owned stdin\n", text=True, capture_output=True,
                env=self.env, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(result.stdout.endswith("UNCONSUMED:caller-owned stdin\n"))

    def test_notice_absent_on_help_errors_and_scoped_uninstall(self):
        root = self.root("non-install")
        before = snapshot(root)
        help_result = self.run_dom(root, "--help")
        self.assertIn(f"VERSION {VERSION}", help_result.stdout)
        self.assertIn("fresh installs AND reruns", help_result.stdout)
        self.assertIn(GUIDE, help_result.stdout)
        results = [help_result]
        for args in (("--platform", "invalid"), ("--guest", "--no-guest"),
                     ("missing-target",)):
            results.append(self.run_dom(root, *args, ok=False))
        (root / ".github/agents").mkdir(parents=True)
        (root / ROLES[2]).mkdir()
        obstructed = snapshot(root)
        refusal = self.run_dom(root, ok=False)
        self.assertIn("No project writes", refusal.stderr)
        self.assertIn("repair", refusal.stderr)
        self.assertEqual(obstructed, snapshot(root))
        results.append(refusal)
        shutil.rmtree(root / ".github")
        # Ignore parent-directory mtime changed by this fixture's obstruction.
        self.assertEqual(before, snapshot(root))
        self.run_dom(root)
        for flags in (("--dry-run",), ()):
            removal = self.run_dom(root, "--uninstall", "--platform", "copilot", *flags)
            self.assertIn("uninstalling", removal.stdout)
            self.assertIn("platform=copilot", removal.stdout)
            results.append(removal)
        self.assertEqual(self.installed(root), {"claude", "codex"})
        for result in results:
            self.assertNotIn("install plan", result.stdout + result.stderr)
            self.assertNotIn("Selected:", result.stdout + result.stderr)
            self.assertNotIn("No --platform:", result.stdout + result.stderr)

    def test_explicit_notice_reports_additive_selection_not_retained_copilot(self):
        root = self.root("additive")
        self.run_dom(root, "--guest")
        # Existing Claude/Codex remain additive; unselected Copilot stays guest
        # and must not be announced as selected or converted.
        result = self.run_dom(root, "--platform", "claude", "--no-guest")
        self.assert_notice(result, root, {"claude": "normal", "codex": "normal"},
                           explicit=True)
        self.assertEqual((root / STATES["copilot"] / "mode").read_text(), "guest\n")
        before = snapshot(root)
        self.assert_notice(self.run_dom(root, "--platform", "claude", "--dry-run"),
                           root, {"claude": "normal", "codex": "normal"},
                           explicit=True, dry=True)
        self.assertEqual(before, snapshot(root))

    def test_policy_backup_collision_zero_writes_including_outside_victim(self):
        fixed = SCRIPT.replace('TS="$(date +%Y%m%d%H%M%S)"', 'TS="20990101000000"')
        for kind in ("symlink", "directory", "file", "hardlink"):
            with self.subTest(kind=kind):
                root = self.root(kind)
                (root / "AGENTS.md").write_text("host instructions\n")
                victim = self.work / f"outside-{kind}"
                victim.write_bytes(b"OUTSIDE must survive\n")
                backup = root / "AGENTS.md.bak.20990101000000"
                if kind == "symlink":
                    backup.symlink_to(victim)
                elif kind == "directory":
                    backup.mkdir()
                elif kind == "hardlink":
                    os.link(victim, backup)
                else:
                    backup.write_bytes(b"unrelated existing backup\n")
                before = snapshot(self.work)
                for flags in ((), ("--dry-run",), ("--force",)):
                    result = self.run_dom(root, *flags, script=fixed, ok=False)
                    self.assertIn("policy", result.stderr)
                    self.assertEqual(before, snapshot(self.work))

    def test_modified_policy_uninstall_same_timestamp_preserves_install_backup(self):
        clock = 'TS="$(date +%Y%m%d%H%M%S)"'
        self.assertEqual(SCRIPT.count(clock), 1)
        fixed = SCRIPT.replace(clock, 'TS="20990101000000"')
        root = self.root("uninstall-backup-collision")
        policy = root / "CLAUDE.md"
        original = b"# Host policy\n\nOutside text.\n"
        policy.write_bytes(original)
        self.run_dom(root, "--platform", "claude", script=fixed)
        backup = root / "CLAUDE.md.bak.20990101000000"
        self.assertEqual(backup.read_bytes(), original)
        anchor = "The plan of record lives in beads (`bd`), not in markdown TODO lists."
        self.assertEqual(policy.read_text().count(anchor), 1)
        policy.write_text(policy.read_text().replace(anchor, anchor + " (user-edit)"))
        before = snapshot(self.work)
        for flags in ((), ("--dry-run",), ("--force",)):
            with self.subTest(flags=flags):
                result = self.run_dom(root, "--uninstall", "--platform", "claude",
                                      *flags, script=fixed, ok=False)
                self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
                self.assertIn("unsafe or occupied policy backup CLAUDE.md.bak.20990101000000",
                              result.stderr)
                self.assertIn("No project writes", result.stderr)
                self.assertEqual(backup.read_bytes(), original)
                # Includes modified policy, roles, snapshots, modes, excludes,
                # directory layout, bytes and mtimes: refusal precedes removal.
                self.assertEqual(before, snapshot(self.work))

    def preservation_script(self):
        clock = 'TS="$(date +%Y%m%d%H%M%S)"'
        self.assertEqual(SCRIPT.count(clock), 1)
        return SCRIPT.replace(clock, 'TS="20990101000000"')

    def test_modified_plain_preservation_collisions_preflight_entire_inventory(self):
        fixed = self.preservation_script()
        # Roles, Claude commands, provider skills, shared skills and metadata;
        # late inventory entries must refuse before earlier roles are removed.
        cases = (
            ("claude", ".claude/agents/reviewer.md"),
            ("claude", ".claude/commands/dom-goal.md"),
            ("codex", ".codex/agents/reviewer.toml"),
            ("codex", ".agents/skills/domestique-goal/SKILL.md"),
            ("codex", ".agents/skills/domestique-goal/agents/openai.yaml"),
            ("copilot", ".github/agents/domestique-v2-copilot-reviewer.agent.md"),
            ("copilot", ".github/skills/domestique-v2-copilot-goal/SKILL.md"),
            ("all", SHARED),
            ("all", ".agents/skills/dom-decompose/SKILL.md"),
            ("all", ".agents/skills/dom-goal/agents/openai.yaml"),
        )
        for guest in (False, True):
            root = self.root(f"preservation-{guest}")
            self.run_dom(root, *(("--guest",) if guest else ()), script=fixed)
            for provider, rel in cases:
                with self.subTest(guest=guest, rel=rel):
                    source = root / rel
                    original = source.read_bytes()
                    modified = original + b"\n# user customization\n"
                    source.write_bytes(modified)
                    kept = root / f"{rel}.uninstalled.20990101000000"
                    kept.write_bytes(b"unrelated preservation must survive\n")
                    before = snapshot(self.work)
                    for flags in ((), ("--dry-run",)):
                        result = self.run_dom(
                            root, "--uninstall", "--platform", provider, *flags,
                            script=fixed, ok=False)
                        self.assertEqual(result.returncode, 3, result.stderr)
                        self.assertIn(f"occupied uninstall preservation {rel}", result.stderr)
                        self.assertIn("No project writes", result.stderr)
                        self.assertEqual(before, snapshot(self.work))
                        self.assertEqual(source.read_bytes(), modified)
                    kept.unlink()
                    source.write_bytes(original)

    def test_unsafe_preservation_destinations_protect_target_and_outside(self):
        fixed = self.preservation_script()
        for rel in (".claude/agents/reviewer.md", SHARED):
            for kind in ("symlink", "dangling", "directory", "hardlink",
                         "parent-symlink", "parent-file"):
                with self.subTest(rel=rel, kind=kind):
                    root = self.root(f"unsafe-{len(list(self.work.iterdir()))}")
                    self.run_dom(root, "--guest", script=fixed)
                    source = root / rel
                    source.write_bytes(source.read_bytes() + b"\n# modified\n")
                    kept = root / f"{rel}.uninstalled.20990101000000"
                    victim = self.work / f"victim-{root.name}"
                    victim.write_bytes(b"outside bytes must survive\n")
                    if kind == "symlink":
                        kept.symlink_to(victim)
                    elif kind == "dangling":
                        kept.symlink_to(self.work / "absent-outside")
                    elif kind == "directory":
                        kept.mkdir()
                        (kept / "unrelated").write_bytes(b"directory contents\n")
                    elif kind == "hardlink":
                        os.link(victim, kept)
                    else:
                        moved = self.work / f"moved-{root.name}"
                        source.parent.rename(moved)
                        if kind == "parent-symlink":
                            source.parent.symlink_to(moved, target_is_directory=True)
                        else:
                            source.parent.write_bytes(b"not a directory\n")
                    before = snapshot(self.work)
                    for flags in ((), ("--dry-run",), ("--force",)):
                        result = self.run_dom(root, "--uninstall", *flags,
                                              script=fixed, ok=False)
                        self.assertEqual(result.returncode, 3, result.stderr)
                        self.assertIn("unsafe", result.stderr)
                        self.assertEqual(before, snapshot(self.work))

    def test_preservation_success_scoped_repeat_and_last_owner(self):
        fixed = self.preservation_script()
        for guest in (False, True):
            root = self.root(f"success-{guest}")
            self.run_dom(root, *(("--guest",) if guest else ()), script=fixed)
            modified = {}
            for rel in (*ROLES, SHARED):
                path = root / rel
                modified[rel] = path.read_bytes() + b"\n# user customization\n"
                path.write_bytes(modified[rel])
            # A shared collision is irrelevant until the last consumer leaves.
            shared_kept = root / f"{SHARED}.uninstalled.20990101000000"
            shared_kept.write_bytes(b"unrelated shared preservation\n")
            for provider, rel in zip(STATES, ROLES):
                if provider == "copilot":
                    before = snapshot(self.work)
                    self.run_dom(root, "--uninstall", "--platform", provider,
                                 script=fixed, ok=False)
                    self.assertEqual(before, snapshot(self.work))
                    shared_kept.unlink()
                before = snapshot(self.work)
                self.run_dom(root, "--uninstall", "--platform", provider,
                             "--dry-run", script=fixed)
                self.assertEqual(before, snapshot(self.work))
                self.run_dom(root, "--uninstall", "--platform", provider, script=fixed)
                self.assertFalse((root / rel).exists())
                self.assertEqual((root / f"{rel}.uninstalled.20990101000000").read_bytes(),
                                 modified[rel])
                self.assertFalse((root / STATES[provider]).exists())
                if provider != "copilot":
                    self.assertEqual((root / SHARED).read_bytes(), modified[SHARED])
                    self.assertTrue((root / ".agents/.domestique").exists())
                before = snapshot(self.work)
                self.run_dom(root, "--uninstall", "--platform", provider, script=fixed)
                self.assertEqual(before, snapshot(self.work))
            self.assertEqual(shared_kept.read_bytes(), modified[SHARED])
            self.assertFalse((root / SHARED).exists())
            self.assertFalse((root / ".agents/.domestique").exists())

    def test_force_deletes_modified_sources_without_touching_occupied_preservations(self):
        fixed = self.preservation_script()
        for provider, guest in (("claude", False), ("codex", True),
                                ("copilot", True), ("both", False), ("all", True)):
            with self.subTest(provider=provider, guest=guest):
                root = self.root(f"force-{provider}")
                self.run_dom(root, "--platform", provider,
                             *(("--guest",) if guest else ()), script=fixed)
                sources = [root / rel for rel in (*ROLES, SHARED) if (root / rel).exists()]
                for source in sources:
                    source.write_bytes(source.read_bytes() + b"\n# modified\n")
                    Path(f"{source}.uninstalled.20990101000000").write_bytes(b"occupied\n")
                before = snapshot(self.work)
                self.run_dom(root, "--uninstall", "--platform", provider,
                             "--force", "--dry-run", script=fixed)
                self.assertEqual(before, snapshot(self.work))
                self.run_dom(root, "--uninstall", "--platform", provider,
                             "--force", script=fixed)
                for source in sources:
                    self.assertFalse(source.exists())
                    self.assertEqual(Path(f"{source}.uninstalled.20990101000000").read_bytes(),
                                     b"occupied\n")
                self.assertEqual(self.installed(root), set())
                self.assertFalse((root / ".agents/.domestique").exists())

    def test_preservation_publication_race_refuses_without_clobber(self):
        fixed = self.preservation_script()
        for kind in ("file", "symlink"):
            with self.subTest(kind=kind):
                root = self.root(f"race-{kind}")
                self.run_dom(root, "--platform", "claude", script=fixed)
                source = root / ROLES[0]  # first removal: no prior target mutations
                modified = source.read_bytes() + b"\n# user customization\n"
                source.write_bytes(modified)
                state = root / STATES["claude"]
                before = snapshot(state)
                victim = self.work / f"race-victim-{kind}"
                victim.write_bytes(b"racing destination must survive\n")
                kept = Path(f"{source}.uninstalled.20990101000000")
                # Introduce a collision only at the real safe-copy invocation,
                # after all preflights. No timing, retries or product stubbing.
                wrapper = self.bin / "python3"
                wrapper.unlink()
                wrapper.write_text(
                    '#!/bin/sh\ncase "$3" in\n'
                    '  *.uninstalled.20990101000000)\n'
                    f'    /bin/{"cp" if kind == "file" else "ln -s"} '
                    '"$COLLISION_VICTIM" "$3" ;;\n'
                    'esac\nexec "$REAL_PYTHON" "$@"\n')
                wrapper.chmod(0o755)
                env = dict(self.env, COLLISION_VICTIM=str(victim), REAL_PYTHON=sys.executable)
                result = self.run_dom(root, "--uninstall", "--platform", "claude",
                                      script=fixed, env=env, ok=False)
                self.assertIn("FileExistsError", result.stderr)
                self.assertIn("partial results may remain", result.stderr)
                self.assertEqual(source.read_bytes(), modified)
                self.assertEqual(before, snapshot(state))
                self.assertEqual(kept.read_bytes(), b"racing destination must survive\n")
                self.assertEqual(victim.read_bytes(), b"racing destination must survive\n")
                if kind == "symlink":
                    self.assertTrue(kept.is_symlink())
                    self.assertEqual(os.readlink(kept), str(victim))
                wrapper.unlink()
                wrapper.symlink_to(sys.executable)

    def test_guarded_policy_conflict_preflights_all_project_writes(self):
        for inactive in (False, True):
            with self.subTest(inactive=inactive):
                root = self.root(f"conflict-{inactive}")
                self.seed(root, ["codex"])
                policy = root / "AGENTS.md"
                policy.write_text("host prefix\n" + policy.read_text().replace(
                    POLICY_ANCHOR, "local conflicting bead rule.") + "host suffix")
                if inactive:
                    (root / "AGENTS.override.md").write_text("host override\n")
                upstream = SCRIPT.replace(POLICY_ANCHOR, "upstream changed bead rule.")
                before = snapshot(self.work)
                for flags in ((), ("--dry-run",), ("--force",)):
                    result = self.run_dom(root, *flags, script=upstream, ok=False)
                    self.assertEqual(result.returncode, 3, result.stderr)
                    self.assertIn("policy merge conflict", result.stderr)
                    self.assertEqual(before, snapshot(self.work))

    def assert_shared_visibility(self, root, guest):
        self.assertEqual((root / ".agents/.domestique/mode").exists(), guest)
        for rel in (SHARED, ".agents/skills/dom-decompose/SKILL.md",
                    ".agents/skills/dom-goal/agents/openai.yaml"):
            ignored = subprocess.run(
                ["git", "-C", str(root), "check-ignore", "-q", rel], env=self.env)
            self.assertEqual(ignored.returncode, 0 if guest else 1, rel)

    def test_codex_copilot_mixed_sticky_transitions_and_scoped_uninstall(self):
        for normal, guest in (("codex", "copilot"), ("copilot", "codex")):
            for removed in (normal, guest):
                with self.subTest(normal=normal, removed=removed):
                    root = self.root(f"{normal}-{removed}")
                    self.run_dom(root)
                    # Persisted mixed state, all providers present.
                    (root / STATES[guest] / "mode").write_text("guest\n")
                    self.run_dom(root)
                    self.assert_shared_visibility(root, False)
                    self.assertTrue((root / STATES[guest] / "mode").exists())
                    before = snapshot(root)
                    self.run_dom(root, "--dry-run")
                    self.assertEqual(before, snapshot(root))
                    self.run_dom(root, "--platform", normal, "--guest")
                    self.assert_shared_visibility(root, True)
                    self.run_dom(root)  # sticky, both guests
                    self.assert_shared_visibility(root, True)
                    self.run_dom(root, "--platform", normal, "--no-guest")
                    self.assert_shared_visibility(root, False)
                    if normal == "copilot":
                        # Explicit install remains additive for persisted
                        # Claude/Codex: --no-guest converts them too.
                        self.assertFalse((root / STATES[guest] / "mode").exists())
                        (root / STATES[guest] / "mode").write_text("guest\n")
                        self.run_dom(root)
                        self.assert_shared_visibility(root, False)
                    self.run_dom(root, "--uninstall", "--platform", removed)
                    remaining = guest if removed == normal else normal
                    self.assert_shared_visibility(root, remaining == guest)
                    role = ROLES[1] if remaining == "codex" else ROLES[2]
                    ignored = subprocess.run(
                        ["git", "-C", str(root), "check-ignore", "-q", role],
                        env=self.env)
                    self.assertEqual(ignored.returncode, 0 if remaining == guest else 1)
                    self.run_dom(root, "--uninstall", "--platform", remaining)
                    self.assertFalse((root / SHARED).exists())

    def test_compatible_policy_merge_preserves_host_customization_and_backup(self):
        root = self.root("compatible")
        self.seed(root, ["codex"])
        policy = root / "AGENTS.md"
        body = policy.read_text().replace(
            "precise numbered briefs", "precise custom numbered briefs")
        policy.write_text("host prefix\n" + body + "host suffix")
        original = policy.read_bytes()
        upstream = SCRIPT.replace(POLICY_ANCHOR, "upstream changed bead rule.")
        self.run_dom(root, script=upstream)
        self.assertIn(b"precise custom numbered briefs", policy.read_bytes())
        self.assertIn(b"upstream changed bead rule.", policy.read_bytes())
        self.assertTrue(policy.read_bytes().startswith(b"host prefix\n"))
        self.assertTrue(policy.read_bytes().endswith(b"host suffix"))
        backups = list(root.glob("AGENTS.md.bak.*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), original)

    def test_all_owned_policy_uninstall_backup_collisions(self):
        fixed = SCRIPT.replace('TS="$(date +%Y%m%d%H%M%S)"', 'TS="20990101000000"')
        root = self.root("owned-backups")
        self.run_dom(root)
        for source, rel, state in (
            ("CLAUDE.md", "CLAUDE.local.md", STATES["claude"]),
            ("AGENTS.md", "AGENTS.override.md", STATES["codex"]),
        ):
            shutil.copyfile(root / source, root / rel)
            shutil.copyfile(root / state / "base" / f"{source}.block",
                            root / state / "base" / f"{rel}.block")
        for rel in ("CLAUDE.md", "CLAUDE.local.md", "AGENTS.md",
                    "AGENTS.override.md", ".github/copilot-instructions.md"):
            with self.subTest(rel=rel):
                policy = root / rel
                original = policy.read_bytes()
                policy.write_bytes(original.replace(b"<!-- END domestique -->",
                                                     b"custom text\n<!-- END domestique -->"))
                backup = root / f"{rel}.bak.20990101000000"
                backup.write_bytes(b"existing backup must survive")
                before = snapshot(self.work)
                for flags in ((), ("--dry-run",), ("--force",)):
                    self.run_dom(root, "--uninstall", *flags, script=fixed, ok=False)
                    self.assertEqual(before, snapshot(self.work))
                backup.unlink()
                policy.write_bytes(original)

    def test_inactive_legacy_backup_and_policy_conflict_destinations(self):
        old = subprocess.check_output(
            ["git", "-C", str(SOURCE.parent), "show", "64f4e09:domestique.sh"],
            text=True)
        root = self.root("inactive-backup")
        self.run_dom(root, "--platform", "codex", script=old)
        (root / "AGENTS.override.md").write_text("host override\n")
        (root / "AGENTS.md.bak.20990101000000").write_bytes(b"old backup\n")
        fixed = SCRIPT.replace('TS="$(date +%Y%m%d%H%M%S)"', 'TS="20990101000000"')
        before = snapshot(self.work)
        for flags in ((), ("--force",), ("--dry-run",)):
            self.run_dom(root, *flags, script=fixed, ok=False)
            self.assertEqual(before, snapshot(self.work))
        for kind in ("symlink", "directory", "file"):
            root = self.root(f"conflict-output-{kind}")
            self.seed(root, ["codex"])
            policy = root / "AGENTS.md"
            policy.write_text(policy.read_text().replace(POLICY_ANCHOR, "local conflict"))
            artifact = root / "AGENTS.md.new"
            victim = self.work / f"artifact-victim-{kind}"
            victim.write_bytes(b"outside artifact victim")
            if kind == "symlink":
                artifact.symlink_to(victim)
            elif kind == "directory":
                artifact.mkdir()
            else:
                artifact.write_bytes(b"unrelated artifact")
            before = snapshot(self.work)
            upstream = SCRIPT.replace(POLICY_ANCHOR, "upstream conflict")
            for flags in ((), ("--force",), ("--dry-run",)):
                self.run_dom(root, *flags, script=upstream, ok=False)
                self.assertEqual(before, snapshot(self.work))

    def test_unowned_policy_base_not_overwritten(self):
        root = self.root("unowned-policy-base")
        base = root / STATES["codex"] / "base/AGENTS.md.block"
        base.parent.mkdir(parents=True)
        base.write_bytes(b"unrelated file at predictable snapshot path")
        before = snapshot(self.work)
        for flags in ((), ("--force",), ("--dry-run",)):
            self.run_dom(root, *flags, ok=False)
            self.assertEqual(before, snapshot(self.work))


if __name__ == "__main__":
    unittest.main(verbosity=2)
