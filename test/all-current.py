"""Current standalone all-provider contract. Offline, no native clients."""
import itertools
import os
from pathlib import Path
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


def snapshot(root):
    return {
        str(p.relative_to(root)): (
            p.lstat().st_mode, p.lstat().st_mtime_ns,
            os.readlink(p) if p.is_symlink() else p.read_bytes() if p.is_file() else None,
        )
        for p in root.rglob("*")
    }


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

    def test_fresh_stdin_default_all_and_rerun(self):
        root = self.root("fresh")
        before = snapshot(root)
        self.run_dom(root, "--dry-run")
        self.assertEqual(before, snapshot(root))
        self.run_dom(root)
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
        self.run_dom(root)
        self.assertEqual(before, snapshot(root))
        self.run_dom(root, "--platform=all")
        self.assertEqual(before, snapshot(root))

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
            self.run_dom(root, f"--platform={selector}")
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
            root = self.root(provider)
            self.run_dom(root, "--platform", provider, script=old)
            (root / STATES[provider] / "platforms").unlink()
            self.run_dom(root)
            self.assertEqual(self.installed(root), set(STATES))
            self.assertTrue((root / ".agents/.domestique/manifest").is_file())
            self.assertFalse((root / ".codex/.domestique/base" / SHARED).exists())

    def test_wholly_guest_missing_providers_inherit(self):
        for missing in STATES:
            root = self.root(missing)
            self.seed(root, [p for p in STATES if p != missing], "--guest")
            before = snapshot(root)
            self.run_dom(root, "--dry-run")
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
                self.assertEqual(before, snapshot(root))
            self.run_dom(root, flag)
            for state in (*STATES.values(), ".agents/.domestique"):
                self.assertEqual((root / state / "mode").exists(), flag == "--guest")

    def test_existing_mixed_modes_preserved_when_none_missing(self):
        root = self.root("mixed")
        self.run_dom(root)
        # Represent a persisted per-provider mixed mode, independent of the
        # explicit CLI's established additive conversion semantics.
        (root / STATES["claude"] / "mode").write_text("guest\n")
        before = {state: (root / state / "mode").exists() for state in STATES.values()}
        self.run_dom(root)
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
        self.assertTrue((root / ROLES[0]).is_file())
        self.assertFalse((root / ROLES[2]).exists())

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
