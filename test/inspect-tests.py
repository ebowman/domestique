"""hq-ln2.2/.3: collection/context and legacy detection; no comparator/CLI.

One qualified fixture session (six offline installer calls), plus small owned
fault fixtures. Failures retain evidence; success removes only owned fixtures.
All reads execute the extractable payload, never source installer callbacks.
"""
import ast
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import FrozenInstanceError, asdict, replace
import io
import json
import os
from pathlib import Path
import shlex
import stat
import subprocess
import sys
import time
import types
import unittest
from unittest.mock import patch

import inspect_fixture as F


SOURCE = (F.ROOT / "domestique.sh").read_text()
PAYLOAD = SOURCE.split("<<'DOM_INSPECT_PY' || inspect_rc=$?\n", 1)[1].split(
    "\nDOM_INSPECT_PY", 1)[0]
WRAPPER = "inspect_main() {" + SOURCE.split("\ninspect_main() {", 1)[1].split(
    "\n}\n", 1)[0] + "\n}\n"
I = types.ModuleType("inspection_boundary")
sys.modules[I.__name__] = I
exec(compile(PAYLOAD, "<embedded-inspection>", "exec"), I.__dict__)
LEAF = ".claude/agents/implementer.md"
BASE = ".claude/.domestique/base/" + LEAF
MANIFEST = ".claude/.domestique/manifest"


def codes(value):
    return {d.code for d in value.diagnostics}


def collect(root, paths, **kwargs):
    reader = I.Collector(str(root), paths, **kwargs)
    for path in paths:
        reader.read(path)
    return reader.finish()


# .3 projects only these .5 comparison conclusions out of the frozen oracle.
# baseline-not-ownership needs a live/base difference (adoption is not recorded);
# ownership itself, baseline availability, and every detection reason stay exact.
DEFERRED_COMPARISON_REASONS = frozenset((
    "metadata-changed", "instructions-changed", "file-changed",
    "crlf-difference", "unsupported-metadata", "baseline-not-ownership",
))


def legacy_detection_projection(oracle):
    """Explicit .3 oracle, independent of scanner output and current emitters.

    .1 files are required witnesses, not an exhaustive file list. Generation
    evidence is checked in full: the two damaged-manifest rows declare the
    implementer witness; the pinned Claude layout also corroborates it with
    reviewer/decompose/goal. No other extra generation paths are permitted.

    Only customization/comparison/metadata/instructions/permission_fields and
    the named comparison reasons above are deferred to .5. Structural reasons
    supplement (never replace) frozen reasons: usable baselines survive live
    edits, host policy text is excluded, and provider reasons aggregate the
    whole inventory, including files outside the frozen witness projection.
    """
    providers = []
    for provider in oracle.providers:
        if provider.installation == "absent":
            providers.append(provider)
            continue
        reasons = set(provider.reasons) - DEFERRED_COMPARISON_REASONS
        damaged = reasons & {"manifest-missing", "manifest-corrupt"}
        old = any(g.generation == "legacy-pre-snapshot" for g in provider.generations)
        reasons.add("baseline-unavailable" if damaged else
                    "old-baseline-unavailable" if old else "installed-baseline")
        if not (provider.provider == "codex" and provider.mode == "guest"):
            reasons.add("host-text-excluded")
        if "baseline-corrupt" in reasons:
            # The frozen corrupt-base mutation is invalid UTF-8, not missing.
            reasons.add("invalid-encoding")
        if "mixed-mode-markers" in reasons:
            # The additional guest policy is not listed in the normal manifest.
            reasons.add("baseline-unavailable")
        if not old and not damaged and provider.mode == "unknown":
            # A valid manifest does not repair the damaged policy's mode.
            reasons.add("mode-unavailable")
        generations = provider.generations
        if damaged:
            assert provider.provider == "claude", "only legacy damaged-manifest rows"
            generations = tuple(replace(g, evidence=g.evidence + tuple(
                oracle.directory + "/" + path for path in (
                    ".claude/agents/reviewer.md", ".claude/commands/decompose.md",
                    ".claude/commands/goal.md"))) for g in generations)
        files = []
        for file in provider.files:
            why = set(file.reasons) - DEFERRED_COMPARISON_REASONS
            if file.baseline.status == "valid":
                why.add("installed-baseline")
            elif file.baseline.status == "corrupt":
                why.add("baseline-corrupt")
            elif damaged:
                why.add("baseline-unavailable")
            if file.path.endswith(("/CLAUDE.md", "/CLAUDE.local.md", "/AGENTS.md",
                                   "/AGENTS.override.md", "/copilot-instructions.md")):
                why.add("host-text-excluded")
            files.append(replace(file, comparison="unknown", metadata="unknown",
                                 instructions="unknown", permission_fields=(),
                                 reasons=tuple(sorted(why))))
        providers.append(replace(provider, generations=generations,
                                 customization="unknown", files=tuple(files),
                                 reasons=tuple(sorted(reasons))))
    return replace(oracle, providers=tuple(providers),
                   customization="not-applicable" if oracle.installation == "absent"
                   else "unknown")


def assert_legacy_projection(test, actual, oracle):
    wanted = legacy_detection_projection(oracle)
    test.assertEqual(tuple(p.provider for p in actual.providers),
                     tuple(p.provider for p in wanted.providers))
    providers = []
    for record, expected in zip(actual.providers, wanted.providers):
        files = {file.path: file for file in record.files}
        test.assertEqual(len(files), len(record.files), "duplicate file evidence")
        if not expected.files:
            test.assertEqual(record.files, ())
        test.assertTrue({file.path for file in expected.files} <= files.keys(),
                        "missing frozen file witness")
        witnesses = []
        for file in expected.files:
            observed = files[file.path]
            test.assertEqual(len(observed.reasons), len(set(observed.reasons)))
            witnesses.append(replace(observed, reasons=tuple(sorted(observed.reasons))))
        test.assertEqual(len(record.reasons), len(set(record.reasons)))
        providers.append(replace(record, files=tuple(witnesses),
                                 reasons=tuple(sorted(record.reasons))))
    # Compare all record fields, not a hand-picked subset. Only the .1-declared
    # additional-file allowance and reason ordering are normalized on actual.
    test.assertEqual(asdict(replace(actual, providers=tuple(providers))), asdict(wanted))


class LegacyProjectionTests(unittest.TestCase):
    def test_structural_projection_requires_unavailable_mode_reason(self):
        row = next(row for row in F.MATRIX if row.name == "partial-markers")
        oracle = F.bind(row.record.scopes[1], {"project": "/synthetic-project"})
        projected = legacy_detection_projection(oracle)
        assert_legacy_projection(self, projected, oracle)
        provider = projected.providers[0]
        self.assertIn("mode-unavailable", provider.reasons)
        damaged = replace(provider, reasons=tuple(
            reason for reason in provider.reasons if reason != "mode-unavailable"))
        with self.assertRaises(AssertionError):
            assert_legacy_projection(self, replace(
                projected, providers=(damaged, *projected.providers[1:])), oracle)

    def test_projection_rejects_dropped_or_invented_detection_fields(self):
        count = 0
        for name in ("normal-missing-manifest", "normal-corrupt-manifest"):
            row = next(row for row in F.MATRIX if row.name == name)
            oracle = F.bind(row.record.scopes[1], {"project": "/synthetic-project"})
            projected = legacy_detection_projection(oracle)
            assert_legacy_projection(self, projected, oracle)
            provider = projected.providers[0]
            file = provider.files[0]
            generation = provider.generations[0]
            reason = "manifest-missing" if name.endswith("missing-manifest") else "manifest-corrupt"
            mutations = [
                replace(projected, **{key: value}) for key, value in (
                    ("scope", "global"), ("directory", "/wrong"),
                    ("installation", "installed"), ("mode", "guest"),
                    ("customization", "unchanged"), ("reasons", ("invented",)),
                    ("beads", "synthetic-metadata-presence-only"))]
            provider_mutations = [
                replace(provider, **{key: value}) for key, value in (
                    ("provider", "wrong"), ("installation", "installed"),
                    ("mode", "guest"), ("customization", "unchanged"),
                    ("reasons", tuple(r for r in provider.reasons if r != reason)),
                    ("reasons", provider.reasons + ("invented",)),
                    ("files", ()), ("generations", ()))]
            for key, value in (("generation", "legacy-pre-snapshot"),
                               ("evidence", ()), ("evidence", ("/wrong",)),
                               ("reported_version", "0.1.0"), ("reported_ref", "unknown")):
                provider_mutations.append(replace(
                    provider, generations=(replace(generation, **{key: value}),)))
            file_mutations = [
                replace(file, **{key: value}) for key, value in (
                    ("path", "/wrong"), ("status", "missing"),
                    ("ownership", "created-record"), ("comparison", "same"),
                    ("metadata", "same"), ("instructions", "same"),
                    ("permission_fields", ("tools",)),
                    ("reasons", tuple(r for r in file.reasons if r != reason)),
                    ("reasons", file.reasons + ("invented",)))]
            for key, value in (("kind", "snapshot"), ("status", "valid"), ("path", "/wrong")):
                file_mutations.append(replace(file, baseline=replace(
                    file.baseline, **{key: value})))
            provider_mutations.extend(replace(provider, files=(file,)) for file in file_mutations)
            mutations.extend(replace(projected, providers=(p, *projected.providers[1:]))
                             for p in provider_mutations)
            for index, actual in enumerate(mutations):
                with self.subTest(row=name, mutation=index):
                    with self.assertRaises(AssertionError):
                        assert_legacy_projection(self, actual, oracle)
                    count += 1
        print(f"legacy projection: {count} dropped/invented-field mutations rejected", flush=True)

    def test_in_memory_collections_preserve_manifest_failure_on_every_affected_file(self):
        count = 0
        for layout in I.LEGACY_LAYOUTS:
            provider, prefix, native, policies, _ = layout
            for status, reason in (("missing", "manifest-missing"), ("readable", "manifest-corrupt")):
                with self.subTest(provider=provider, reason=reason):
                    manifest = prefix + "/.domestique/manifest"
                    leaf = native[0]
                    text = {
                        "claude": "\nname: implementer\nYou are an implementer. "
                                  "You receive one bounded task",
                        "codex": 'name = "implementer"\nYou are the domestique implementer.',
                        "copilot": "\nname: domestique-implementer\n"
                                   "You are the Domestique implementer.",
                    }[provider]
                    observations = (
                        I.Observation(manifest, status, data=b"not-a-manifest\n"
                                      if status == "readable" else None),
                        I.Observation(leaf, "readable", data=text.encode()),
                        I.Observation(prefix + "/.domestique/base/" + leaf,
                                      "readable", data=b"intact baseline, not authority\n"),
                        I.Observation(policies[0], "readable",
                                      data=(F.BEGIN + b"\nowned\n" + F.END + b"\n")),
                    )
                    by_path = {o.path: o for o in observations}

                    def collector(root, allowed, **kwargs):
                        collection = I.Collection(root, tuple(
                            by_path.get(path, I.Observation(path, "missing")) for path in allowed),
                            (), True)
                        reader = unittest.mock.Mock()
                        reader.finish.return_value = collection
                        return reader

                    with patch.object(I, "Collector", side_effect=collector):
                        record, collection = I.legacy_provider(
                            "/synthetic-project", layout, I.Limits(), None)
                    self.assertTrue(collection.consistent)
                    self.assertEqual(record.installation, "partial")
                    self.assertIn(reason, record.reasons)
                    self.assertEqual(len(record.files), 2)
                    self.assertEqual(len(record.generations), 1)
                    for file in record.files:
                        self.assertIn(reason, file.reasons)
                        self.assertNotIn("old-baseline-unavailable", file.reasons)
                        self.assertEqual(file.baseline, I.Baseline("none", "unavailable"))
                        self.assertEqual(file.ownership, "unknown")
                        self.assertEqual((file.comparison, file.metadata, file.instructions,
                                          file.permission_fields),
                                         ("unknown", "unknown", "unknown", ()))
                    for generation in record.generations:
                        self.assertEqual(generation.evidence, ("/synthetic-project/" + leaf,))
                        self.assertIsNone(generation.reported_version)
                        self.assertIsNone(generation.reported_ref)
                    count += 1
        print(f"legacy manifest propagation: {count} in-memory provider/case probes", flush=True)


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.session = F.FixtureSession()
        self.root = self.session.root
        self.project = self.session.project("boundary")
        self.leaf = self.project / LEAF
        self.leaf.parent.mkdir(parents=True)
        self.leaf.write_bytes(F.SECRET.encode())
        self.env_patch = patch.dict(os.environ, self.session.env, clear=True)
        self.env_patch.start()

    def tearDown(self):
        self.env_patch.stop()
        result = self._outcome.result
        if any(test is self for test, _ in result.failures + result.errors):
            print("inspection boundary failed; retained:", self.root, flush=True)
            return
        self.session.assert_no_calls()
        self.session.pristine = self.session.snapshot()
        self.session.clean()

    def guarded(self, action):
        before = self.session.snapshot()
        result = action()
        self.assertTrue(before == self.session.snapshot(), "owned state changed")
        self.session.assert_no_calls()
        self.assertNotIn(F.SECRET, repr(result), "private bytes in representation")
        return result

    def test_default_nongit_alias_and_escaped_display(self):
        with patch.object(I.os, "getcwd", return_value=str(self.project)), \
                patch.object(I, "git_root") as git:
            context = self.guarded(lambda: I.resolve_context())
            git.assert_not_called()
        self.assertEqual(context.context, "non-git")
        self.assertEqual(context.scope, "directory-only")
        self.assertEqual(context.resolved_directory, str(self.project))
        alias = self.root / "alias"
        alias.symlink_to(self.project)
        context = self.guarded(lambda: I.resolve_context(alias))
        self.assertEqual(context.resolved_directory, str(self.project))
        weird = self.root / "cohorts" / "space\n\t\x1bname"
        weird.mkdir()
        result = self.guarded(lambda: I.resolve_context(weird))
        shown = I.display(result.resolved_directory)
        self.assertNotIn("\n", shown)
        self.assertIn("\\n", shown)

    def test_invalid_targets_never_claim_nongit_or_absence(self):
        denied = self.project / "denied"
        denied.mkdir()
        denied.chmod(0)
        try:
            for target in (self.root / "missing", self.leaf, denied, "", "\0"):
                result = I.resolve_context(target)
                self.assertEqual(result.context, "invalid-target")
                self.assertEqual(result.scope, "unresolved")
                self.assertIn("invalid-target", codes(result))
        finally:
            denied.chmod(0o700)
        with patch.object(I.os, "getcwd", side_effect=OSError(F.SECRET)):
            self.assertIn("invalid-target", codes(I.resolve_context()))

    def test_real_git_root_subdirectory_and_linked_worktree(self):
        s = self.session
        s.run(["git", "init", "-q", self.project], operation="git-init")
        s.run(["git", "-C", self.project, "commit", "--allow-empty", "-qm", "boundary"],
              operation="git-commit")
        subdir = self.project / "subdir"
        subdir.mkdir()
        linked = self.root / "cohorts/linked"
        s.run(["git", "-C", self.project, "worktree", "add", "-q", "--detach", linked],
              operation="git-worktree")
        for requested, expected, physical in (
                (self.project, "git-root", self.project),
                (subdir, "git-subdirectory", self.project),
                (linked, "linked-worktree", linked)):
            result = self.guarded(lambda: I.resolve_context(requested))
            self.assertEqual(result.context, expected)
            self.assertEqual(result.resolved_directory, str(physical))
            self.assertTrue(result.unchanged())

    def test_git_environment_and_executable_integrations_are_disabled(self):
        self.session.run(["git", "init", "-q", self.project], operation="git-init")
        config = self.project / ".git/config"
        with config.open("a") as stream:
            stream.write("\n[core]\nfsmonitor = bd\nhooksPath = /not-used\n"
                         "[credential]\nhelper = !beads\n"
                         "[diff]\nexternal = claude\n")
        overrides = {
            "GIT_DIR": F.SECRET, "GIT_WORK_TREE": F.SECRET,
            "GIT_CONFIG_GLOBAL": F.SECRET, "GIT_CONFIG_SYSTEM": F.SECRET,
            "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.worktree",
            "GIT_CONFIG_VALUE_0": F.SECRET, "GIT_EXEC_PATH": F.SECRET,
            "GIT_TRACE": str(self.root / "trace-must-not-exist"),
            "GIT_SSH_COMMAND": "codex", "LD_PRELOAD": F.SECRET,
        }
        real_popen = I.subprocess.Popen
        with patch.dict(os.environ, overrides), \
                patch.object(I.subprocess, "Popen", wraps=real_popen) as launch:
            context = self.guarded(lambda: I.resolve_context(self.project))
            self.assertEqual(context.context, "git-root")
            args = launch.call_args
            env = args.kwargs["env"]
            self.assertFalse(set(overrides) & set(env) -
                             {"GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM"})
            self.assertEqual(env["GIT_OPTIONAL_LOCKS"], "0")
            self.assertEqual(env["GIT_CONFIG_GLOBAL"], os.devnull)
            self.assertEqual(args.args[0][-3:],
                             ["rev-parse", "--show-toplevel", "--is-inside-work-tree"])
            self.assertEqual(launch.call_count, 1)

    def test_uncertain_git_and_discovery_limits(self):
        with patch.object(I, "MAX_ANCESTORS", 1):
            result = self.guarded(lambda: I.resolve_context(self.project))
            self.assertIn("root-discovery-limit", codes(result))
        marker = self.project / ".git"
        marker.symlink_to(self.root)
        with patch.object(I, "git_root") as git:
            result = self.guarded(lambda: I.resolve_context(self.project))
            self.assertIn("unsafe-git-marker", codes(result))
            git.assert_not_called()
        marker.unlink()
        os.mkfifo(marker)
        result = self.guarded(lambda: I.resolve_context(self.project))
        self.assertIn("unsafe-git-marker", codes(result))
        marker.unlink()
        marker.mkdir()
        with patch.object(I.shutil, "which", return_value=None):
            result = self.guarded(lambda: I.resolve_context(self.project))
            self.assertIn("root-discovery-unavailable", codes(result))
        with patch.object(I, "stamp", side_effect=PermissionError(F.SECRET)):
            self.assertIn("root-discovery-unavailable", codes(I.resolve_context(self.project)))
        with patch.object(I, "git_root", return_value=True):
            # A changed candidate invalidates the otherwise successful result.
            with patch.object(I.Context, "unchanged", return_value=False):
                self.assertIn("inconsistent-evidence", codes(I.resolve_context(self.project)))

    def test_git_failure_output_deadline_and_output_cap(self):
        (self.project / ".git").mkdir()
        git = self.root / "bin/git"
        for body in (
                f"printf '%s' {shlex.quote(F.SECRET)}; "
                f"printf '%s' {shlex.quote(F.SECRET)} >&2; exit 1",
                "while :; do printf 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'; done",
                "exec /bin/sleep 5"):
            git.write_text("#!/bin/sh\n" + body + "\n")
            git.chmod(0o700)
            started = time.monotonic()
            with patch.object(I, "GIT_SECONDS", 0.15):
                result = self.guarded(lambda: I.resolve_context(self.project))
            self.assertLess(time.monotonic() - started, 3)
            self.assertIn("root-discovery-unavailable", codes(result))
        with patch.object(I.subprocess, "Popen", side_effect=OSError(F.SECRET)):
            self.assertFalse(I.git_root(self.project))

    def test_safe_read_immutable_and_sealed_no_enumeration(self):
        def action():
            with patch.object(I.os, "scandir", side_effect=AssertionError("enumeration")), \
                    patch.object(I.os, "listdir", side_effect=AssertionError("enumeration")):
                reader = I.Collector(str(self.project), (LEAF,))
                provisional = reader.read(LEAF)
                self.assertTrue(provisional.data == F.SECRET.encode(), "wrong private bytes")
                self.assertTrue(provisional.text() == F.SECRET, "wrong private text")
                result = reader.finish()
                self.assertIs(result, reader.finish())
                self.assertIn("collection-sealed", codes(reader.read(LEAF)))
                with self.assertRaises(FrozenInstanceError):
                    result.consistent = False
                with self.assertRaises(FrozenInstanceError):
                    provisional.data = b"replacement"
                return result
        result = self.guarded(action)
        self.assertTrue(result.consistent)
        self.assertFalse(result.diagnostics)

    def test_unread_required_inventory_is_not_silently_certified(self):
        other = '.claude/agents/review"er.md'
        paths = (LEAF, other)
        for missing in (False, True):
            if not missing:
                (self.project / other).write_bytes(b"other")
            else:
                (self.project / other).unlink()
            for read_paths in ((), (LEAF,)):
                with self.subTest(missing=missing, read_paths=read_paths):
                    def action():
                        reader = I.Collector(str(self.project), paths, scope="global")
                        for path in read_paths:
                            reader.read(path)
                        with patch.object(reader, "_observe", wraps=reader._observe) as observe:
                            result = reader.finish()
                        # Finishing revalidates only attempted reads, never
                        # manufactures observations for omitted inventory.
                        self.assertTrue(all(call.args[0] is None or
                                            call.args[0] in read_paths
                                            for call in observe.call_args_list))
                        self.assertEqual(reader._allowed, set(paths))
                        self.assertEqual(tuple(o.path for o in result.observations), read_paths)
                        self.assertEqual(result.diagnostics, tuple(
                            I.Diagnostic("global", "unread-required-input", I.display(path))
                            for path in sorted(set(paths) - set(read_paths))))
                        self.assertFalse(result.consistent)
                        self.assertTrue(all(o.data is None for o in result.observations))
                        self.assertIs(result, reader.finish())
                        self.assertIn("collection-sealed", codes(reader.read(other)))
                        return result
                    self.guarded(action)

    def test_explicit_empty_and_complete_required_inventory(self):
        other = ".claude/agents/reviewer.md"
        (self.project / other).write_bytes(b"other")
        for paths in ((), (LEAF, other), (LEAF, LEAF, other)):
            result = self.guarded(lambda: collect(self.project, paths))
            self.assertTrue(result.consistent)
            self.assertFalse(result.diagnostics)
            self.assertEqual({o.path for o in result.observations}, set(paths))
            self.assertTrue(all(o.status == "readable" for o in result.observations))
        # A missing record is accounted for only by an actual read attempt.
        (self.project / other).unlink()
        result = self.guarded(lambda: collect(self.project, (LEAF, other)))
        self.assertTrue(result.consistent)
        self.assertFalse(result.diagnostics)
        self.assertEqual(tuple(o.status for o in result.observations), ("readable", "missing"))
        result = self.guarded(lambda: collect(self.root / "missing", ()))
        self.assertFalse(result.consistent)
        self.assertIn("invalid-target", codes(result))

    def test_unread_inventory_survives_collector_failures_and_limits(self):
        other = ".claude/agents/reviewer.md"
        third = ".claude/agents/third.md"
        paths = (LEAF, other, third)
        for path in paths:
            (self.project / path).write_bytes(b"xxxx")
        for failure in ("not-allowlisted", "entry-limit", "byte-limit"):
            with self.subTest(failure=failure):
                def action():
                    limits = I.Limits(total_bytes=2) if failure == "byte-limit" else I.Limits(entries=3)
                    reader = I.Collector(str(self.project), paths, limits=limits)
                    reader.read(LEAF)
                    if failure == "not-allowlisted":
                        reader.read("unknown.md")
                    elif failure == "entry-limit":
                        for _ in range(3):
                            reader.read(LEAF)
                    # Calling read after the boundary breaks does not account
                    # for a path that was never actually observed.
                    reader.read(other)
                    result = reader.finish()
                    self.assertFalse(result.consistent)
                    self.assertIn(failure, codes(result))
                    self.assertEqual({d.path for d in result.diagnostics
                                      if d.code == "unread-required-input"},
                                     {I.display(other), I.display(third)})
                    self.assertEqual(tuple(o.path for o in result.observations), (LEAF,))
                    self.assertTrue(all(o.data is None for o in result.observations))
                    return result
                self.guarded(action)
        # Invalid/over-limit declarations are never reinterpreted as empty or
        # as just the accepted prefix of the requested inventory.
        for limits in (I.Limits(entries=2), I.Limits(entries=0)):
            result = self.guarded(lambda: I.Collector(
                str(self.project), paths, limits=limits).finish())
            self.assertFalse(result.consistent)
            self.assertTrue(codes(result) & {"entry-limit", "invalid-limits"})

    def test_unread_inventory_preserves_read_failure_and_race_diagnostics(self):
        other = ".claude/agents/missing.md"
        for failure in ("unreadable-file", "invalid-encoding", "inconsistent-evidence"):
            with self.subTest(failure=failure):
                self.leaf.write_bytes(b"\xff" if failure == "invalid-encoding" else b"xxxx")
                reader = I.Collector(str(self.project), (LEAF, other))
                if failure == "unreadable-file":
                    with patch.object(I.os, "read", side_effect=PermissionError(13, F.SECRET)):
                        reader.read(LEAF)
                        result = reader.finish()
                else:
                    reader.read(LEAF)
                    if failure == "inconsistent-evidence":
                        self.leaf.write_bytes(b"changed")
                    result = reader.finish()
                self.assertFalse(result.consistent)
                self.assertEqual(codes(result), {failure, "unread-required-input"})
                self.assertTrue(all(o.data is None for o in result.observations))
                self.assertNotIn(F.SECRET, repr(result))

    def test_absolute_traversal_unknown_and_engine_paths(self):
        for path in ("/etc/passwd", "../outside", ".claude/../outside",
                     ".claude//agents/a", "./CLAUDE.md", "C:/outside", "a\\b",
                     "", None, "x\nvalue", "x\0value", "a/" * 17 + "b",
                     ".beads/config.yaml", ".beads/dolt/db", "x.sqlite",
                     "a/.dolt/config", "a/beads.db-wal"):
            with self.subTest(path=repr(path)):
                result = self.guarded(lambda: collect(self.project, (path,)))
                self.assertTrue(result.diagnostics)
                self.assertFalse(result.observations)
        reader = I.Collector(str(self.project), (MANIFEST,))
        result = self.guarded(lambda: reader.read(LEAF))
        self.assertIn("not-allowlisted", codes(result))
        self.assertNotIn(LEAF, repr(result))

    def test_symlink_hardlink_fifo_directory_unreadable_without_leaf_open(self):
        self.leaf.unlink()
        outside = self.root / "outside"
        outside.write_bytes(F.SECRET.encode())
        for kind in ("symlink", "hardlink", "fifo", "directory", "unreadable"):
            if kind == "symlink":
                self.leaf.symlink_to(outside)
            elif kind == "hardlink":
                os.link(outside, self.leaf)
            elif kind == "fifo":
                os.mkfifo(self.leaf)
            elif kind == "directory":
                self.leaf.mkdir()
            else:
                self.leaf.write_bytes(F.SECRET.encode())
                self.session.held[self.leaf] = os.open(self.leaf, os.O_RDONLY)
                self.leaf.chmod(0)
            real_open = I.os.open

            def checked_open(path, *args, **kwargs):
                self.assertNotEqual(path, self.leaf.name, "unsafe leaf opened")
                return real_open(path, *args, **kwargs)

            with patch.object(I.os, "open", side_effect=checked_open):
                # The preservation oracle owns its own safe absolute-path reads.
                result = self.guarded(lambda: collect(self.project, (LEAF,)))
            expected = "unreadable-file" if kind == "unreadable" else "unsafe-" + kind
            self.assertIn(expected, codes(result))
            if kind == "directory":
                self.leaf.rmdir()
            else:
                self.leaf.unlink()
            if kind == "unreadable":
                os.close(self.session.held.pop(self.leaf))

    def test_parent_and_root_alias_not_followed_by_collector(self):
        alias = self.root / "alias"
        alias.symlink_to(self.project)
        result = self.guarded(lambda: collect(alias, (LEAF,)))
        self.assertIn("invalid-target", codes(result))
        self.leaf.unlink()
        self.leaf.parent.rmdir()
        self.leaf.parent.symlink_to(self.root)
        result = self.guarded(lambda: collect(self.project, (LEAF,)))
        self.assertIn("unsafe-symlink", codes(result))
        missing = self.guarded(lambda: collect(self.root / "absent-root", ()))
        self.assertIn("invalid-target", codes(missing))

    def test_device_metadata_is_rejected_without_open(self):
        real_stat = I.os.stat
        real_open = I.os.open

        def device_stat(path, *args, **kwargs):
            original = real_stat(path, *args, **kwargs)
            if path == self.leaf.name:
                fields = list(original)
                fields[0] = stat.S_IFCHR | 0o600
                return os.stat_result(fields)
            return original

        def checked_open(path, *args, **kwargs):
            self.assertNotEqual(path, self.leaf.name, "device opened")
            return real_open(path, *args, **kwargs)

        with patch.object(I.os, "stat", side_effect=device_stat), \
                patch.object(I.os, "open", side_effect=checked_open):
            result = collect(self.project, (LEAF,))
        self.assertIn("unsafe-nonregular", codes(result))

    def test_file_entry_depth_and_aggregate_budgets(self):
        self.leaf.write_bytes(b"x" * I.MAX_BYTES)
        result = self.guarded(lambda: collect(self.project, (LEAF,)))
        self.assertEqual(result.observations[0].status, "readable")
        self.leaf.write_bytes(b"x" * (I.MAX_BYTES + 1))
        result = self.guarded(lambda: collect(self.project, (LEAF,)))
        self.assertIn("input-too-large", codes(result))
        self.assertIsNone(result.observations[0].data)
        yielded = []

        def endless():
            while True:
                yielded.append(1)
                yield LEAF
        reader = I.Collector(str(self.project), endless(), limits=I.Limits(entries=2))
        self.assertEqual(len(yielded), 3)
        self.assertIn("entry-limit", codes(reader.finish()))
        for limits in (I.Limits(depth=1), I.Limits(entries=0), I.Limits(file_bytes="bad")):
            result = self.guarded(lambda: collect(self.project, (LEAF,), limits=limits))
            self.assertTrue(result.diagnostics)
        self.leaf.write_bytes(b"xxxx")
        other = ".claude/agents/reviewer.md"
        (self.project / other).write_bytes(b"yyyy")
        result = self.guarded(lambda: collect(
            self.project, (LEAF, other), limits=I.Limits(total_bytes=6)))
        self.assertIn("byte-limit", codes(result))
        self.assertTrue(all(o.data is None for o in result.observations))
        # Invalid UTF-8 still consumes the aggregate read budget.
        self.leaf.write_bytes(b"\xffxxx")
        result = self.guarded(lambda: collect(
            self.project, (LEAF, other), limits=I.Limits(total_bytes=6)))
        self.assertIn("byte-limit", codes(result))
        # Bytes consumed before an I/O error count as well, even though no
        # payload survives. Revalidation has the same independent total cap.
        self.leaf.write_bytes(b"xxxx")
        real_read = I.os.read
        calls = 0

        def partial_error(fd, size):
            nonlocal calls
            calls += 1
            if calls % 2 == 0:
                raise OSError(5, F.SECRET)
            return real_read(fd, size)

        with patch.object(I.os, "read", side_effect=partial_error):
            result = collect(self.project, (LEAF, other), limits=I.Limits(total_bytes=6))
        self.assertIn("byte-limit", codes(result))
        self.assertNotIn(F.SECRET, repr(result))
        reader = I.Collector(str(self.project), (LEAF,), limits=I.Limits(entries=1))
        reader.read(LEAF)
        reader.read(LEAF)
        self.assertIn("entry-limit", codes(reader.finish()))

    def test_encoding_and_io_diagnostics_never_include_native_content(self):
        self.leaf.write_bytes(b"\xff" + F.SECRET.encode())
        result = self.guarded(lambda: collect(self.project, (LEAF,)))
        self.assertIn("invalid-encoding", codes(result))
        self.assertEqual(result.observations[0].status, "corrupt")
        self.assertIsNone(result.observations[0].text())
        for failure in (PermissionError(13, F.SECRET, F.SECRET), OSError(5, F.SECRET)):
            with patch.object(I.os, "read", side_effect=failure):
                result = collect(self.project, (LEAF,))
            self.assertIn("unreadable-file", codes(result))
            self.assertNotIn(F.SECRET, repr(result))

    def test_observable_content_identity_membership_and_missing_races(self):
        for mutation in ("content", "replace", "parent", "missing", "root"):
            reader = I.Collector(str(self.project), (LEAF,))
            reader.read(LEAF)
            if mutation == "content":
                s = self.leaf.stat()
                self.leaf.write_bytes(b"x" * s.st_size)
                os.utime(self.leaf, ns=(s.st_atime_ns, s.st_mtime_ns))
            elif mutation == "replace":
                temporary = self.leaf.with_suffix(".new")
                temporary.write_bytes(self.leaf.read_bytes())
                temporary.replace(self.leaf)
            elif mutation == "parent":
                (self.leaf.parent / "appeared").write_bytes(b"")
            elif mutation == "missing":
                self.leaf.unlink()
            else:
                moved = self.project.with_name("moved")
                self.project.rename(moved)
                self.project.symlink_to(moved)
            result = reader.finish()
            self.assertIn("inconsistent-evidence", codes(result))
            self.assertFalse(result.consistent)
            self.assertTrue(all(o.data is None for o in result.observations))
            if mutation == "missing":
                self.leaf.write_bytes(b"restored")
        self.project.unlink()
        moved.rename(self.project)
        self.leaf.unlink()
        reader = I.Collector(str(self.project), (LEAF,))
        self.assertEqual(reader.read(LEAF).status, "missing")
        self.leaf.write_bytes(b"appeared")
        self.assertIn("inconsistent-evidence", codes(reader.finish()))

    def test_during_read_race_and_context_generation(self):
        real_read = I.os.read
        mutated = False

        def racing_read(fd, size):
            nonlocal mutated
            data = real_read(fd, size)
            if not mutated:
                mutated = True
                self.leaf.write_bytes(b"changed")
            return data
        reader = I.Collector(str(self.project), (LEAF,))
        with patch.object(I.os, "read", side_effect=racing_read):
            provisional = reader.read(LEAF)
        self.assertIn("inconsistent-evidence", codes(provisional))
        self.assertIn("inconsistent-evidence", codes(reader.finish()))
        context = I.resolve_context(self.project)
        reader = I.Collector(str(self.project), (LEAF,), context=context)
        reader.read(LEAF)
        (self.project / ".git").mkdir()
        self.assertIn("inconsistent-evidence", codes(reader.finish()))

    def test_expected_context_and_collector_faults_are_sanitized_at_source(self):
        loop = self.root / "resolution-loop"
        loop.symlink_to(loop.name)
        result = self.guarded(lambda: I.resolve_context(loop))
        self.assertIn("invalid-target", codes(result))
        # Compatibility: pre-3.13 pathlib uses RuntimeError for resolution loops.
        with patch.object(I.Path, "resolve", side_effect=RuntimeError(F.SECRET)):
            result = I.resolve_context(self.project)
        self.assertIn("invalid-target", codes(result))
        self.assertNotIn(F.SECRET, repr(result))
        with patch.object(I.os, "open", side_effect=PermissionError(13, F.SECRET)):
            result = I.Collector(str(self.project), (LEAF,)).finish()
        self.assertFalse(result.consistent)
        self.assertEqual(codes(result), {"invalid-target", "unread-required-input"})
        self.assertNotIn(F.SECRET, repr(result))
        for code, expected in ((I.errno.ELOOP, "unsafe"), (I.errno.ENOTDIR, "inconsistent"),
                               (I.errno.EIO, "unreadable")):
            reader = I.Collector(str(self.project), (LEAF,))
            with patch.object(I.os, "read", side_effect=OSError(code, F.SECRET)):
                observation = reader.read(LEAF)
                result = reader.finish()
            self.assertTrue(observation.diagnostics)
            self.assertEqual(observation.status, expected)
            self.assertEqual(result.consistent, code != I.errno.ENOTDIR)
            self.assertNotIn("unread-required-input", codes(result))
            self.assertNotIn(F.SECRET, repr(result))
        # Discovery launch/deadline errors remain expected, without stderr.
        for fault in (OSError(I.errno.EIO, F.SECRET),
                      subprocess.TimeoutExpired(F.SECRET, 1, output=F.SECRET)):
            with patch.object(I.subprocess, "Popen", side_effect=fault):
                self.assertFalse(I.git_root(self.project))

    def test_unexpected_library_faults_propagate_without_printing(self):
        marker = self.project / ".git"
        marker.mkdir()
        for kind in (RuntimeError, ValueError, AssertionError, TypeError):
            for boundary in ("context", "git", "collector", "read", "finish", "main"):
                with self.subTest(kind=kind.__name__, boundary=boundary):
                    reader = I.Collector(str(self.project), (LEAF,))
                    owner, name, action = {
                        "context": (I, "stamp", lambda: I.resolve_context(self.project)),
                        "git": (I.subprocess, "Popen", lambda: I.git_root(self.project)),
                        "collector": (I.os, "open", lambda: I.Collector(
                            str(self.project), (LEAF,))),
                        "read": (I.os, "read", lambda: reader.read(LEAF)),
                        "finish": (reader, "_observe", reader.finish),
                        "main": (I, "resolve_context", lambda: I.boundary_main([str(self.project)])),
                    }[boundary]
                    fault = kind(F.SECRET)
                    output, errors = io.StringIO(), io.StringIO()
                    with redirect_stdout(output), redirect_stderr(errors), \
                            patch.object(owner, name, side_effect=fault):
                        with self.assertRaises(kind) as raised:
                            action()
                    self.assertIs(raised.exception, fault)
                    self.assertEqual(output.getvalue() + errors.getvalue(), "")
                    self.assertIsNone(reader._sealed)
                    self.assertFalse(reader._observed)

    def test_unexpected_main_fault_is_nonzero_without_raw_exception_chain(self):
        # Exercise the actual __main__ dispatch, not just boundary_main as a
        # library. Inject a chained bug before dispatch and use the real shell
        # privacy boundary; do not install a catch or exception hook in the test.
        injection = (
            "def boundary_main(args):\n"
            f"    value = Path({LEAF!r}).read_text()\n"
            "    try:\n"
            "        raise ValueError(value)\n"
            "    except ValueError as cause:\n"
            "        raise RuntimeError(value) from cause\n\n")
        wrapper = WRAPPER.replace('if __name__ == "__main__":',
                                  injection + 'if __name__ == "__main__":')
        result = self.guarded(lambda: self.shell(wrapper=wrapper))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(result.stderr, b"domestique inspect: runtime-or-collection-failure\n")
        # Also prohibit restoring a broad catch anywhere in the payload.
        for node in ast.walk(ast.parse(PAYLOAD)):
            if isinstance(node, ast.ExceptHandler):
                self.assertIsNotNone(node.type)
                self.assertFalse(any(isinstance(part, ast.Name) and
                                     part.id in ("Exception", "BaseException")
                                     for part in ast.walk(node.type)))

    def shell(self, args=(), env=None, wrapper=WRAPPER):
        return subprocess.run(
            ["/bin/bash", "-c", wrapper + '\ninspect_main "$@"', "inspection", *map(str, args)],
            env=env or self.session.env, cwd=self.project, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=10)

    def test_isolated_runtime_no_repository_user_startup_or_bytecode(self):
        malicious = ("from pathlib import Path\n"
                     f"Path({str(self.root / 'calls/bd')!r}).write_text('startup')\n")
        for name in ("sitecustomize.py", "usercustomize.py", "json.py"):
            (self.project / name).write_text(malicious)
        env = dict(self.session.env, PYTHONPATH=str(self.project),
                   PYTHONHOME=str(self.project), PYTHONSTARTUP=str(self.project / "json.py"))
        result = self.guarded(lambda: self.shell(env=env))
        self.assertEqual(result.returncode, 0)
        self.assertIn(b"scope=directory-only", result.stdout)
        self.assertFalse(result.stderr)
        self.assertIn("python3 -I -S -B -", WRAPPER)
        ast.parse(PAYLOAD, feature_version=(3, 9))

    def test_missing_old_and_failed_runtime_are_explicit_and_sanitized(self):
        env = dict(self.session.env, PATH=str(self.root / "bin"))
        result = self.guarded(lambda: self.shell(env=env))
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"Python 3.9+ runtime unavailable", result.stderr)
        python = self.root / "bin/python3"
        for code in (69, 126):
            python.write_text("#!/bin/sh\nprintf '%s' " + shlex.quote(F.SECRET) +
                              f" >&2\nexit {code}\n")
            python.chmod(0o700)
            result = self.guarded(lambda: self.shell(env=env))
            self.assertEqual(result.returncode, 1)
            self.assertNotIn(F.SECRET.encode(), result.stderr)
        check_old = ("import sys\nsys.version_info = (3, 8)\n" + PAYLOAD)
        result = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", check_old],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        self.assertEqual(result.returncode, 69)
        self.assertFalse(result.stdout + result.stderr)
        python.unlink()
        result = self.guarded(lambda: self.shell((self.root / "missing",)))
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"invalid-target", result.stdout)
        self.assertNotIn(b"installing", result.stdout)

    def test_no_public_dispatch_or_noninspection_python_dependency(self):
        self.assertEqual(SOURCE.count('\ninspect_main() {'), 1)
        self.assertNotIn("--inspect", SOURCE.replace(WRAPPER, ""))
        # Preserve existing shell dependencies while making Python unusable.
        python = self.root / "bin/python3"
        python.write_text("#!/bin/sh\n: > " + shlex.quote(str(self.root / "calls/bd")) +
                          "\nexit 99\n")
        python.chmod(0o700)
        env = self.session.env
        result = self.guarded(lambda: subprocess.run(
            ["/bin/bash", str(F.ROOT / "domestique.sh"), "--help"], env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10))
        self.assertEqual(result.returncode, 0)
        self.assertFalse(result.stderr)


class QualifiedFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.started = time.monotonic()
        cls.complete = False
        cls.session = F.FixtureSession()
        print("inspection collection evidence:", cls.session.root, flush=True)
        cls.session.setup()
        print(F.provenance_summary(cls.session), flush=True)

    @classmethod
    def tearDownClass(cls):
        if not cls.complete:
            print("collection fixture failed; retained:", cls.session.root, flush=True)
            return
        cls.session.clean()
        print(f"collection fixtures: cleaned; {time.monotonic() - cls.started:.3f}s", flush=True)

    def test_qualified_contexts_and_boundary_projection(self):
        names = (
            "absent", "v1-normal-all-including-draft-copilot", "v1-guest-claude-codex",
            "pre-snapshot-no-git", "v1-no-git", "default-current-directory",
            "v1-subdirectory", "v1-linked-worktree", "path-with-spaces",
            "path-with-control-characters", "private-global-and-local",
            "private-synthetic-beads-presence", "invalid-encoding", "oversized-input",
            "unsafe-symlink", "unsafe-hardlink", "unsafe-directory", "unsafe-fifo",
            "unsafe-socket", "unsafe-unreadable", "managed-file-missing",
        )
        for name in names:
            with self.subTest(scenario=name):
                case = self.session.begin(name)
                expected = case.expected()
                with patch.dict(os.environ, case.env, clear=True):
                    context = I.resolve_context(case.requested)
                    self.assertEqual(context.context, expected.context)
                    self.assertEqual(context.resolved_directory, expected.resolved_directory)
                    paths = [LEAF, BASE, MANIFEST]
                    if case.scenario.cohort == "private":
                        paths = [".domestique-private/manifest",
                                 ".claude/agents/domestique-claude-local-implementer.md"]
                    result = collect(context.resolved_directory, paths, context=context)
                    if case.scenario.cohort == "private":
                        global_native = collect(
                            case.env["HOME"],
                            (".claude/agents/domestique-claude-implementer.md",),
                            scope="global")
                        global_records = collect(
                            case.env["DOMESTIQUE_HOME"], ("active", "state/global-manifest"),
                            scope="global")
                        for observed in (global_native, global_records):
                            self.assertTrue(observed.consistent)
                            self.assertTrue(all(o.status == "readable"
                                                for o in observed.observations))
                            self.assertNotIn(F.SECRET, repr(observed))
                    if name.startswith("unsafe-") or name in ("invalid-encoding", "oversized-input"):
                        oracle = expected.scopes[1].providers[0].files[0]
                        self.assertEqual(result.observations[0].status, oracle.status)
                        self.assertTrue(set(oracle.reasons) <= codes(result))
                    elif name == "managed-file-missing":
                        self.assertEqual(result.observations[0].status, "missing")
                    self.assertTrue(result.consistent)
                    # The oracle exempts actual absolute fixture paths, not
                    # relative/missing native names (e.g. "implementer" is also
                    # a private native metadata value). No report API yet:
                    # exercise scoped statuses/codes, never dump objects.
                    self.assertNotIn(F.SECRET, repr(result))
                    output = (I.display(context.resolved_directory) + "\n" +
                              "\n".join(o.status for o in result.observations) + "\n" +
                              "\n".join(sorted(codes(result)))).encode()
                    case.accept(output, b"")
            if self.session.active is not None:
                return  # Keep the first failed case; no cascading fixture use.
        type(self).complete = True


    def test_z_legacy_source_qualified_projection(self):
        # Reuse the SAME six cold installs as the boundary projection. The .1
        # declarations stay frozen; only the documented .5 comparison fields
        # and reasons are projected by legacy_detection_projection().
        type(self).complete = False
        selected = [row for row in F.MATRIX if row.cohort not in ("private", "empty")
                    and not row.name.startswith("cli-")]
        selected += [row for row in F.MATRIX
                     if row.name in ("absent", "unrelated-native-agents")]
        for row in selected:
            with self.subTest(scenario=row.name):
                case = self.session.begin(row.name)
                expected = case.expected()
                with patch.dict(os.environ, case.env, clear=True):
                    context = I.resolve_context(case.requested)
                    result = I.inspect_scan_legacy(context)
                oracle = expected.scopes[1]
                self.assertEqual(context.context, expected.context)
                self.assertEqual(context.resolved_directory, expected.resolved_directory)
                self.assertEqual(result.exit_code, expected.exit_code)
                assert_legacy_projection(self, result.scope, oracle)
                self.assertTrue(all(c.consistent for c in result.collections))
                self.assertNotIn("unread-required-input", codes(result))
                case.accept(json.dumps(asdict(result.scope), ensure_ascii=True).encode(), b"")
                print("legacy oracle accepted:", row.name, flush=True)
            if self.session.active is not None:
                return
        print(f"legacy oracle: {len(selected)} source-qualified cases; no comparison claims",
              flush=True)
        # Coexistence is a legacy-only projection, NOT guessing preview bytes
        # into a snapshot version; .4/.5 combine distinct generation records.
        case = self.session.begin("multiple-generations-one-provider")
        with patch.dict(os.environ, case.env, clear=True):
            result = I.inspect_scan_legacy(I.resolve_context(case.requested))
        # The coexistence mutation copies only historical Claude into preview.
        oracle = F.bind(F.scope((F.NORMAL.providers[0], F.absent_provider("codex"),
                                 F.absent_provider("copilot"))),
                        {"project": str(case.project)})
        assert_legacy_projection(self, result.scope, oracle)
        self.assertEqual(result.exit_code, 0)
        case.accept(json.dumps(asdict(result.scope), ensure_ascii=True).encode(), b"")
        print("legacy oracle accepted: multiple-generations-one-provider (legacy only)",
              flush=True)
        type(self).complete = True


class LegacyFailureTests(unittest.TestCase):
    # Tiny owned fault roots only; no additional cold installer setup.
    setUp = BoundaryTests.setUp
    tearDown = BoundaryTests.tearDown
    guarded = BoundaryTests.guarded

    def write(self, path, value):
        destination = self.project / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(value.encode() if isinstance(value, str) else value)

    def scan(self, **kwargs):
        return self.guarded(lambda: I.inspect_scan_legacy(
            I.resolve_context(self.project), **kwargs))

    def manifest(self, provider="claude"):
        # Fixed historical grammar, independent of detector inventory/output.
        native = {
            "claude": ".claude/agents/implementer.md,.claude/agents/reviewer.md,"
                      ".claude/commands/decompose.md,.claude/commands/goal.md,CLAUDE.md",
            "codex": ".codex/agents/implementer.toml,.codex/agents/reviewer.toml,"
                     ".agents/skills/domestique/SKILL.md,"
                     ".agents/skills/domestique-decompose/SKILL.md,"
                     ".agents/skills/domestique-goal/SKILL.md,"
                     ".agents/skills/domestique-goal/agents/openai.yaml",
        }[provider]
        return ("snapshot_format=1\nplatform=" + provider +
                "\ndomestique_version=0.1.0\ninstalled_ref=b60feef\n"
                "installed_at=2026-01-01T00:00:00Z\nscript_sha256=unavailable\n"
                "files=" + native + "\n")

    def test_generic_known_filenames_and_unowned_policy_are_not_ownership(self):
        self.write("CLAUDE.md", F.SECRET)
        result = self.scan()
        self.assertEqual(result.scope.installation, "absent")
        self.assertEqual(result.scope.providers[0].files, ())
        self.assertEqual(result.scope.providers[0].reasons, ("unrelated-native-files",))
        policy = next(o for o in result.collections[0].observations if o.path == "CLAUDE.md")
        self.assertIsNone(policy.data)

    def test_orphaned_state_markers_and_baselines_are_not_clean_absence(self):
        for path, value in (
                ("CLAUDE.md", F.BEGIN + b"\n" + F.END + b"\n"),
                (MANIFEST, self.manifest()),
                (".claude/.domestique/mode", "guest\n"),
                (BASE, "orphan baseline")):
            with self.subTest(path=path):
                self.write(path, value)
                record = self.scan().scope.providers[0]
                self.assertEqual(record.installation, "partial")
                self.assertTrue(record.reasons)
                if path == "CLAUDE.md":
                    self.assertIn("manifest-missing", record.files[0].reasons)
                    self.assertNotIn("old-baseline-unavailable", record.files[0].reasons)
                (self.project / path).unlink()

    def test_marker_damage_duplicates_crlf_and_host_text_privacy(self):
        block = F.BEGIN + b"\n" + b"owned\n" + F.END + b"\n"
        for value, reason in (
                (block + block, "multiple-policy-blocks"),
                (block.replace(b"\n", b"\r\n"), "partial-policy-markers"),
                (block[:-1], "partial-policy-markers"),
                (F.END + b"\n" + F.BEGIN + b"\n", "partial-policy-markers"),
                (block.replace(b"BEGIN", b"begin"), "partial-policy-markers"),
                (block.replace(F.END, b""), "partial-policy-markers"),
                (b"<!-- BEGIN domestique\n", "partial-policy-markers")):
            with self.subTest(reason=reason, value_size=len(value)):
                self.write("CLAUDE.md", F.SECRET.encode() + b"\n" + value)
                result = self.scan()
                self.assertEqual(result.scope.providers[0].mode, "unknown")
                self.assertEqual(result.exit_code, 1)
                self.assertIn(reason, result.scope.providers[0].reasons)
                self.assertTrue(all(o.data is None for o in result.collections[0].observations
                                    if o.path == "CLAUDE.md"))

    def test_missing_mode_competing_blocks_is_mixed_not_normal(self):
        block = F.BEGIN + b"\nowned\n" + F.END + b"\n"
        for path in ("CLAUDE.md", "CLAUDE.local.md"):
            self.write(path, block)
        result = self.scan()
        self.assertEqual(result.scope.providers[0].mode, "mixed")
        self.assertEqual(result.scope.providers[0].installation, "mixed")
        self.assertIn("mixed-mode-markers", result.scope.providers[0].reasons)
        self.assertTrue(all(f.status == "corrupt" for f in result.scope.providers[0].files
                            if f.path.endswith(("CLAUDE.md", "CLAUDE.local.md"))))

    def test_mixed_provider_modes_preserve_installation_evidence(self):
        block = F.BEGIN + b"\nowned\n" + F.END + b"\n"
        for provider in ("claude", "codex"):
            manifest = self.manifest(provider)
            self.write("." + provider + "/.domestique/manifest", manifest)
            for path in manifest.split("files=", 1)[1].strip().split(","):
                self.write(path, block if path == "CLAUDE.md" else "native\n")
        self.write(".codex/.domestique/mode", "guest\n")
        result = self.scan()
        self.assertEqual((result.scope.installation, result.scope.mode, result.exit_code),
                         ("installed", "mixed", 1))
        self.assertEqual(result.scope.reasons, ("mixed-provider-modes",))
        self.assertEqual(tuple(p.installation for p in result.scope.providers),
                         ("installed", "installed", "absent"))
        (self.project / LEAF).unlink()
        result = self.scan()
        self.assertEqual((result.scope.installation, result.scope.mode, result.exit_code),
                         ("partial", "mixed", 1))
        self.write("CLAUDE.local.md", block)
        result = self.scan()
        self.assertEqual((result.scope.installation, result.scope.mode, result.exit_code),
                         ("mixed", "mixed", 1))

    def test_manifest_poison_never_widens_inventory_or_echoes_values(self):
        original = self.manifest()
        for value in (
                original.replace("0.1.0", F.SECRET),
                original.replace("b60feef", F.SECRET),
                original.replace("CLAUDE.md", "../" + F.SECRET),
                original.replace("CLAUDE.md", ".codex/agents/implementer.toml"),
                original.replace("CLAUDE.md", "CLAUDE.md,CLAUDE.md"),
                original.replace("\n", "\r\n"),
                original[:-1], original + "files=" + F.SECRET + "\n",
                original.replace("platform=claude", "platform=codex")):
            self.write(MANIFEST, value)
            self.write(".codex/.domestique/manifest", self.manifest("codex"))
            result = self.scan()
            claude, codex = result.scope.providers[:2]
            self.assertIn("manifest-corrupt", claude.reasons)
            self.assertFalse(claude.generations)
            self.assertEqual(codex.generations[0].reported_ref, "b60feef")
            self.assertFalse(any(F.SECRET in o.path for c in result.collections
                                 for o in c.observations))

    def test_every_static_input_observed_and_provider_limits_stay_independent(self):
        self.write(MANIFEST, self.manifest())
        self.write(".codex/.domestique/manifest", self.manifest("codex"))
        result = self.scan()
        self.assertTrue(all(c.consistent for c in result.collections))
        self.assertEqual(tuple(len(c.observations) for c in result.collections), (15, 20, 16))
        self.write(LEAF, "x" * 800)
        with patch.object(I.os, "scandir", side_effect=AssertionError("enumeration")), \
                patch.object(I.Path, "read_bytes", side_effect=AssertionError("direct read")), \
                patch.object(I.Path, "read_text", side_effect=AssertionError("direct read")):
            context = I.resolve_context(self.project)
            limited = I.inspect_scan_legacy(context, limits=I.Limits(total_bytes=600))
        # Claude alone exceeds this byte budget; Codex's smaller manifest
        # remains observable (independent collector), never globally suppressed.
        self.assertIn("byte-limit", codes(limited))
        self.assertFalse(limited.collections[0].consistent)
        self.assertTrue(limited.collections[1].consistent)
        self.assertEqual(limited.scope.providers[1].generations[0].reported_ref, "b60feef")
        self.assertEqual(limited.exit_code, 1)

    def test_mode_platform_and_creation_records_are_bounded_not_authority(self):
        self.write(MANIFEST, self.manifest())
        for name, value, code in (
                ("mode", F.SECRET + "\n", "mode-corrupt"),
                ("platforms", "codex\n", "platforms-corrupt"),
                ("platforms", F.SECRET + "\n", "platforms-corrupt")):
            self.write(".claude/.domestique/" + name, value)
            self.assertIn(code, self.scan().scope.providers[0].reasons)
            (self.project / (".claude/.domestique/" + name)).unlink()
        self.write(".codex/.domestique/manifest", self.manifest("codex"))
        self.write(".codex/.domestique/guest-excludes", "../" + F.SECRET + "\n")
        result = self.scan().scope.providers[1]
        self.assertIn("creation-record-corrupt", result.reasons)
        self.assertTrue(all(f.ownership == "unknown" for f in result.files))

    def test_unexpected_detector_fault_surfaces_without_logging(self):
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(I, "legacy_manifest", side_effect=RuntimeError(F.SECRET)), \
                redirect_stdout(output), redirect_stderr(errors):
            with self.assertRaises(RuntimeError):
                I.inspect_scan_legacy(I.resolve_context(self.project))
        self.assertFalse(output.getvalue() + errors.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
