"""Source-qualified V1/public and V2/refusal regressions; no native/network/DB.

Uses existing owned FixtureSession trees and unittest, not a new runner.
The retained preview's failed-apply test is engine history, not V2 publication.
"""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import shlex
import unittest

import inspect_fixture as F
import preview_fixture as P

V1_PIN = "4de726c2e38e731c67f5f37d4a16206d7b3d99af"
PREVIEW_PIN = "58732cc"
URL = "https://raw.githubusercontent.com/ebowman/domestique/main/domestique.sh"


@contextmanager
def fixture():
    session = F.FixtureSession()
    print("VERSION_BOUNDARY_FIXTURE=" + str(session.root), flush=True)
    try:
        yield session
        session.assert_no_calls()
        session.pristine = session.snapshot()
        session.clean()
        print("VERSION_BOUNDARY_CLEANED=" + str(session.root), flush=True)
    except BaseException:
        print("VERSION_BOUNDARY_RETAINED=" + str(session.root), flush=True)
        raise


def protected(session):
    # Include bytes, modes, mtimes, identities, membership and link targets.
    return {p: e for p, e in session.snapshot().items()
            if Path(p).parts and Path(p).parts[0] in ("home", "global", "cohorts", "tmp")}


def run(session, script, *args, **kwargs):
    return session.run(["/bin/bash", script, *args], check=False, **kwargs)


class VersionBoundaryTests(unittest.TestCase):
    def test_pins_public_bytes_retained_payloads_and_historical_origins(self):
        with fixture() as s:
            rows = {}
            for name in ("domestique.sh", "update.sh"):
                old = s.run(["git", "-C", F.ROOT, "show", V1_PIN + ":" + name]).stdout
                actual = (F.ROOT / name).read_bytes()
                self.assertEqual(actual, old)
                preview = s.run(["git", "-C", F.ROOT, "show", PREVIEW_PIN + ":" + name]).stdout
                artifact = name.replace(".sh", "2.sh")
                self.assertEqual(P.source(artifact), preview)
                rows[name] = hashlib.sha256(actual).hexdigest()
                rows[artifact] = hashlib.sha256((F.ROOT / artifact).read_bytes()).hexdigest()
            self.assertEqual(F.HISTORICAL_PIN, "b60feef4d0d41b8d99b7afec68dd5e6ef648b027")
            self.assertEqual(F.PRE_SNAPSHOT_PIN, "69f39c468b65335d05260b8c5bc4653a7cf3c9f3")
            self.assertIn(URL.encode(), (F.ROOT / "update.sh").read_bytes())
            print("VERSION_BOUNDARY_SOURCE_SHA256=" + json.dumps(rows, sort_keys=True))

    def test_actual_downloaded_v1_updater_normal_guest_both_and_sticky_defaults(self):
        with fixture() as s:
            old = s.root / "sources/downloaded-update.sh"
            old.write_bytes(s.run(["git", "-C", F.ROOT, "show", V1_PIN + ":update.sh"]).stdout)
            for mode in ("normal", "guest"):
                repo = s.project(mode, git=True)
                args = ("--guest",) if mode == "guest" else ()
                result = run(s, old, "--source", F.ROOT / "domestique.sh",
                             "--platform", "both", *args, repo, operation="install")
                self.assertEqual(result.returncode, 0, (result.stdout, result.stderr))
                policy = "CLAUDE.local.md" if mode == "guest" else "CLAUDE.md"
                self.assertIn(F.BEGIN, (repo / policy).read_bytes())
                for leaf in (".claude/agents/implementer.md", ".claude/agents/reviewer.md",
                             ".claude/commands/decompose.md", ".claude/commands/goal.md",
                             ".codex/agents/implementer.toml", ".codex/agents/reviewer.toml",
                             ".agents/skills/domestique/SKILL.md",
                             ".agents/skills/domestique-decompose/SKILL.md",
                             ".agents/skills/domestique-goal/SKILL.md",
                             ".agents/skills/domestique-goal/agents/openai.yaml"):
                    self.assertTrue((repo / leaf).is_file(), leaf)
                for provider in ("claude", "codex"):
                    state = repo / ("." + provider) / ".domestique"
                    if mode == "guest":
                        self.assertEqual((state / "mode").read_text().strip(), mode)
                    else:
                        # Actual v1 records sticky guest only, not normal.
                        self.assertFalse((state / "mode").exists())
                    self.assertEqual((state / "platforms").read_text().strip(), "both")
                    self.assertIn("snapshot_format=1\n", (state / "manifest").read_text())
                self.assertFalse((repo / ".github").exists())
                self.assertFalse((repo / ".domestique-private").exists())
                if mode == "guest":
                    self.assertFalse((repo / "AGENTS.md").exists())
                    self.assertIn(b"CLAUDE.local.md", (repo / ".git/info/exclude").read_bytes())
                else:
                    self.assertTrue((repo / "AGENTS.md").is_file())
                before = protected(s)
                # Omitted provider and mode use actual installed v1 state.
                result = run(s, old, "--source=" + str(F.ROOT / "domestique.sh"),
                             "--dry-run", repo, operation="install")
                self.assertEqual(result.returncode, 0, (result.stdout, result.stderr))
                self.assertEqual(protected(s), before)
                if mode == "guest":
                    # Exercise the legacy conversion flag without applying it.
                    result = run(s, old, "--source", F.ROOT / "domestique.sh",
                                 "--no-guest", "--dry-run", repo, operation="install")
                    self.assertEqual(result.returncode, 0, (result.stdout, result.stderr))
                    self.assertEqual(protected(s), before)

    def test_v1_network_default_and_environment_overrides_are_literal(self):
        with fixture() as s:
            repo = s.project("quotes ' \" $(not-a-command) space", git=True)
            old = s.root / "sources/downloaded-update.sh"
            old.write_bytes(s.run(["git", "-C", F.ROOT, "show", V1_PIN + ":update.sh"]).stdout)
            log = s.root / "sources/fetch-url"
            curl = s.root / "bin/curl"
            # The only network implementation is this disposable stub.
            curl.write_text("#!/bin/sh\n"
                            'test "$1" = -fsSL && test "$3" = -o || exit 99\n'
                            f'printf "%s\\n" "$2" > {shlex.quote(str(log))}\n'
                            f'cp {shlex.quote(str(F.ROOT / "domestique.sh"))} "$4"\n')
            for env_value, explicit, expected in (
                    (None, None, URL), ("", None, URL),
                    ("https://fixture.invalid/v1.sh", None, "https://fixture.invalid/v1.sh"),
                    ("https://fixture.invalid/env.sh", "https://fixture.invalid/explicit.sh",
                     "https://fixture.invalid/explicit.sh"),
                    (str(F.ROOT / "domestique.sh"), None, None),
                    ("https://fixture.invalid/unused.sh", str(F.ROOT / "domestique.sh"), None)):
                with self.subTest(env=env_value, explicit=explicit):
                    if log.exists():
                        log.unlink()
                    env = dict(s.env)
                    if env_value is not None:
                        env["DOMESTIQUE_UPDATE_SOURCE"] = env_value
                    before = protected(s)
                    args = ("--source", explicit) if explicit is not None else ()
                    result = run(s, old, *args, "--dry-run", "--platform", "codex", repo,
                                 env=env, operation="install")
                    self.assertEqual(result.returncode, 0, (result.stdout, result.stderr))
                    self.assertEqual(log.read_text().strip() if log.exists() else None, expected)
                    self.assertEqual(protected(s), before)
            # Existing seven forbidden-call markers stay empty, including curl:
            # only the known stub above was allowed, with exact URL witnesses.

    def test_v1_updater_against_new_artifact_cannot_fall_into_old_writer(self):
        with fixture() as s:
            repo = s.project("old-updater-new-source", git=True)
            before = protected(s)
            # The public updater is byte-identical to the downloaded one.
            result = run(s, F.ROOT / "update.sh", "--source", F.ROOT / "domestique2.sh", repo)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(protected(s), before)
            self.assertNotIn(b"Created:", result.stdout)

    def test_new_updater_rejects_old_empty_malformed_missing_and_spoof_sources(self):
        with fixture() as s:
            old = s.source("verified-public-v1", V1_PIN)
            marker = s.root / "sources/candidate-executed"
            before = s.snapshot()
            result = run(s, F.ROOT / "update2.sh", "--source", old)
            self.assertEqual((result.returncode, result.stdout), (1, b""))
            self.assertEqual(s.snapshot(), before)
            for label, raw in (
                    ("old", old.read_bytes()),
                    ("empty", b""),
                    ("malformed", b"if\n"),
                    ("spoof", b"#!/bin/bash\n# format=2\n# major=2\n"),
                    ("reviewed-preview", P.source())):
                candidate = s.root / "sources" / (label + " ' quote.sh")
                # Nonempty candidates have an execution witness BEFORE their
                # original body, so an early old-script exit cannot hide a call.
                candidate.write_bytes(
                    b"#!/bin/bash\n: > " + shlex.quote(str(marker)).encode() + b"\n" + raw
                    if raw else raw)
                before = s.snapshot()
                for preview in ((), ("--dry-run",)):
                    result = run(s, F.ROOT / "update2.sh", "--source", candidate, *preview)
                    self.assertEqual(result.returncode, 1)
                    self.assertEqual(result.stdout, b"")
                    self.assertEqual(s.snapshot(), before)
                    self.assertFalse(marker.exists(), "candidate execution witness")
            before = s.snapshot()
            result = run(s, F.ROOT / "update2.sh", "--source", s.root / "missing")
            self.assertEqual(result.returncode, 1)
            self.assertEqual(s.snapshot(), before)

    def test_new_update_selectors_offline_packages_and_environment_refuse_without_writes(self):
        with fixture() as s:
            package = s.root / "sources/local package ' \""
            package.mkdir()
            # Even apparent format-2 identity cannot unlock unfinished publication.
            (package / "PACKAGE").write_text("format=2\nproduct=domestique\nmajor=2\n")
            for args in (("--version", "2.0.0"), ("--version=2.0.0", "--dry-run"),
                         ("--source", str(package)), ("--source=" + str(package), "--")):
                before = s.snapshot()
                result = run(s, F.ROOT / "update2.sh", *args)
                self.assertEqual((result.returncode, result.stdout), (1, b""))
                self.assertEqual(s.snapshot(), before)
            for value, expected in (("", 1), (str(F.ROOT / "domestique2.sh"), 2)):
                before = s.snapshot()
                result = run(s, F.ROOT / "update2.sh", "--source", package,
                             env=dict(s.env, DOMESTIQUE_UPDATE_SOURCE=value))
                self.assertEqual((result.returncode, result.stdout), (expected, b""))
                self.assertEqual(s.snapshot(), before)
                if value:
                    self.assertIn(b"DOMESTIQUE_UPDATE_SOURCE", result.stderr)

    def test_new_update_typed_argv_and_quoting_no_calls_or_writes(self):
        invalid = [
            (), ("--source",), ("--source", ""), ("--source=",), ("--version",),
            ("--version=",), ("--version", "1.0.0"), ("--version", "2.01.0"),
            ("--version", "v2.0.0"), ("--version", "main"), ("--version", "2.0.0-rc1"),
            ("--source", "--dry-run"), ("--source", "https://fixture.invalid/a"),
            ("--source", "a", "--source", "b"), ("--source=a", "--version=2.0.0"),
            ("--version=2.0.0", "--dry-run", "--dry-run"), ("--", "--source", "a"),
            ("--version=2.0.0", "--", "extra"), ("--global",), ("--platform=all",),
            ("--guest",), ("--force",), ("--model", "gpt-6-astra"), ("--source=a", "--help"),
        ]
        with fixture() as s:
            for args in invalid:
                with self.subTest(args=args):
                    before = s.snapshot()
                    result = run(s, F.ROOT / "update2.sh", *args)
                    self.assertEqual((result.returncode, result.stdout), (2, b""))
                    self.assertEqual(s.snapshot(), before)
            literal = "./$(touch never) ' \" \\ no-source"
            before = s.snapshot()
            result = run(s, F.ROOT / "update2.sh", "--source", literal)
            self.assertEqual((result.returncode, result.stdout), (1, b""))
            self.assertEqual(s.snapshot(), before)

    def test_new_entrypoint_cannot_adopt_or_overwrite_any_old_namespace(self):
        with fixture() as s:
            repo = s.project("old-input", git=True)
            for parent in (Path(s.env["DOMESTIQUE_HOME"]), repo / ".domestique-private",
                           Path(s.env["HOME"]) / ".claude/agents"):
                parent.mkdir(parents=True, exist_ok=True)
                (parent / "manifest").write_text("format=1\n" + F.SECRET + "\n")
            for args in ((), (str(repo),), ("--global",), ("--local", str(repo)),
                         ("--uninstall", "--global"), ("enable", str(repo)),
                         ("disable", str(repo)), ("install",), ("update",),
                         ("--local", str(repo), "--with-beads"), ("--dry-run",)):
                before = s.snapshot()
                result = run(s, F.ROOT / "domestique2.sh", *args)
                self.assertEqual((result.returncode, result.stdout), (1, b""))
                self.assertNotIn(F.SECRET.encode(), result.stderr)
                self.assertEqual(s.snapshot(), before)

    def test_retained_preview_failed_preview_never_applies(self):
        # This test is explicitly retained format-1 updater behavior, NOT a
        # claim that the public update2 shell now executes candidate previews.
        with fixture() as s:
            updater = P.materialize(s.root / "sources", "update2.sh")
            candidate = s.root / "sources/failed-preview.sh"
            witness = s.root / "sources/preview-only"
            apply = s.root / "sources/applied"
            candidate.write_text("#!/bin/bash\n"
                                 'if [ "$1" = --dry-run ]; then\n'
                                 f': > {shlex.quote(str(witness))}\nexit 7\nfi\n'
                                 f': > {shlex.quote(str(apply))}\n')
            before = protected(s)
            result = run(s, updater, "--source", candidate, "--global")
            self.assertEqual(result.returncode, 7)
            self.assertTrue(witness.exists())
            self.assertFalse(apply.exists())
            self.assertEqual(protected(s), before)
            for raw in (b"", b"if\n"):
                candidate.write_bytes(raw)
                witness.unlink(missing_ok=True)
                result = run(s, F.ROOT / "update2.sh", "--source", candidate)
                self.assertEqual(result.returncode, 1)
                self.assertFalse(witness.exists())
                self.assertFalse(apply.exists())

    def test_branch_source_help_does_not_advertise_working_installation(self):
        with fixture() as s:
            for script in ("domestique2.sh", "update2.sh"):
                before = s.snapshot()
                result = run(s, F.ROOT / script, "--help")
                self.assertEqual(result.returncode, 0)
                self.assertIn(b"SOURCE-ONLY TRANSITION", result.stdout)
                self.assertIn(script.encode(), result.stdout)
                self.assertNotIn(URL.encode(), result.stdout)
                self.assertEqual(s.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
