"""hq-ln2.2/.3/.4: collection, legacy and private preview; no comparator/CLI.

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
WRAPPER = SOURCE[SOURCE.index("\ninspect_main() {") + 1:SOURCE.index(
    "\n}\n", SOURCE.index("\nDOM_INSPECT_PY\n")) + 3] + "\n"
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

# Exact b60feef4 native inventory; 69f39c4 predates Claude's goal command.
# Policy destinations are selected below from the frozen mode/marker scenario,
# never from a scanner collection or a filesystem-derived allowlist.
LEGACY_PATHS = {
    "claude": (".claude/agents/implementer.md", ".claude/agents/reviewer.md",
               ".claude/commands/decompose.md", ".claude/commands/goal.md"),
    "codex": (".codex/agents/implementer.toml", ".codex/agents/reviewer.toml",
              ".agents/skills/domestique/SKILL.md",
              ".agents/skills/domestique-decompose/SKILL.md",
              ".agents/skills/domestique-goal/SKILL.md",
              ".agents/skills/domestique-goal/agents/openai.yaml"),
    "copilot": (".github/agents/domestique-implementer.agent.md",
                ".github/agents/domestique-reviewer.agent.md",
                ".github/skills/domestique/SKILL.md",
                ".github/skills/domestique-decompose/SKILL.md",
                ".github/skills/domestique-goal/SKILL.md"),
}


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
        witnesses = {f.path: f for f in files}
        paths = LEGACY_PATHS[provider.provider]
        if old:
            paths = paths[:3]
        policies = (("CLAUDE.local.md" if provider.mode == "guest" else "CLAUDE.md",)
                    if provider.provider == "claude" else
                    () if provider.provider == "codex" and provider.mode == "guest" else
                    ("AGENTS.md",) if provider.provider == "codex" else
                    (".github/copilot-instructions.md",))
        if "mixed-mode-markers" in provider.reasons:
            policies += ("CLAUDE.local.md",)
        inventory = []
        prefix = {"claude": ".claude", "codex": ".codex", "copilot": ".github"}[provider.provider]
        for path in paths + policies:
            absolute = oracle.directory + "/" + path
            if absolute in witnesses:
                inventory.append(witnesses.pop(absolute))
                continue
            policy = path in policies
            missing_base = damaged or old or path == "CLAUDE.local.md" and provider.mode == "mixed"
            base = F.Baseline("none", "unavailable") if missing_base else F.Baseline(
                "snapshot", "valid", oracle.directory + "/" + prefix +
                "/.domestique/base/" + path + (".block" if policy else ""))
            why = set(damaged) | {
                "old-baseline-unavailable" if old else
                "baseline-unavailable" if missing_base else "installed-baseline"}
            if policy:
                why.add("host-text-excluded")
            mixed_policy = policy and provider.mode == "mixed"
            if mixed_policy:
                why.add("mixed-mode-markers")
            inventory.append(F.FileEvidence(
                absolute, "corrupt" if mixed_policy else "readable", base,
                "unknown" if damaged or old else
                "created-record" if provider.provider == "copilot" or
                provider.provider == "codex" and provider.mode == "guest" else "unknown",
                "unknown", reasons=tuple(sorted(why))))
        assert not witnesses, "frozen witness outside pinned source inventory"
        providers.append(replace(provider, generations=generations,
                                 customization="unknown", files=tuple(inventory),
                                 reasons=tuple(sorted(reasons))))
    return replace(oracle, providers=tuple(providers),
                   customization="not-applicable" if oracle.installation == "absent"
                   else "unknown")


def assert_legacy_projection(test, actual, oracle):
    wanted = legacy_detection_projection(oracle)
    assert_detection_projection(test, actual, wanted)


def assert_detection_projection(test, actual, wanted):
    test.assertEqual(tuple(p.provider for p in actual.providers),
                     tuple(p.provider for p in wanted.providers))
    providers = []
    for record, expected in zip(actual.providers, wanted.providers):
        files = {file.path: file for file in record.files}
        test.assertEqual(len(files), len(record.files), "duplicate file evidence")
        test.assertEqual(set(files), {file.path for file in expected.files},
                         "complete source-qualified file inventory")
        witnesses = []
        for file in expected.files:
            observed = files[file.path]
            test.assertEqual(len(observed.reasons), len(set(observed.reasons)))
            witnesses.append(replace(observed, reasons=tuple(sorted(observed.reasons))))
        test.assertEqual(len(record.reasons), len(set(record.reasons)))
        providers.append(replace(record, files=tuple(witnesses),
                                 reasons=tuple(sorted(record.reasons))))
    # All actual records are checked, including independently expanded .1
    # witnesses. Only file ordering and reason ordering are normalized.
    test.assertEqual(asdict(replace(actual, providers=tuple(providers))), asdict(wanted))


# Production-format references, independent of the scanner's inventory.
PRIVATE_PATHS = {}
for kind in ("global", "project"):
    for name, prefix, ext in (("claude", ".claude", "md"), ("codex", ".codex", "toml"),
                              ("copilot", ".copilot" if kind == "global" else ".github",
                               "agent.md")):
        qualifier = "" if kind == "global" else "-local"
        leaves = tuple(f"{prefix}/agents/domestique-{name}{qualifier}-{role}.{ext}"
                       for role in ("implementer", "reviewer"))
        if kind == "global":
            skills = ".agents" if name == "codex" else prefix
            leaves = tuple(f"{skills}/skills/domestique-{name}{suffix}/SKILL.md"
                           for suffix in ("", "-decompose", "-goal")) + leaves
            if name == "codex":
                leaves += (".agents/skills/domestique-codex-goal/agents/openai.yaml",)
        PRIVATE_PATHS[kind, name] = leaves


def private_detection_projection(oracle):
    """All .4 fields, not a shape/status filter.

    Only .5 comparison/customization conclusions are deferred. Expand the .1
    implementer witness to the complete production native inventory. Damaged
    manifests have both corroborating local roles, never a fabricated ref.
    Explicitly supplement scope manifest failures and legacy host exclusions;
    do not discard unknown structural reasons.
    """
    providers = []
    for provider in oracle.providers:
        if provider.installation == "absent":
            providers.append(provider)
            continue
        damaged = set(provider.reasons) & {"manifest-missing", "manifest-corrupt"}
        mixed = len(provider.generations) > 1
        reasons = set(provider.reasons) - DEFERRED_COMPARISON_REASONS
        reasons.add("baseline-unavailable" if damaged else "installed-baseline")
        generations = provider.generations
        if damaged:
            generations = tuple(replace(g, evidence=tuple(
                oracle.directory + "/" + p for p in PRIVATE_PATHS["project", provider.provider]))
                                for g in generations)
        file = provider.files[0]
        why = set(file.reasons) - DEFERRED_COMPARISON_REASONS
        why.update(("baseline-unavailable",) if damaged else
                   ("installed-baseline", "digest-only-baseline"))
        files = tuple(replace(file, path=oracle.directory + "/" + path,
                              comparison="unknown", metadata="unknown", instructions="unknown",
                              permission_fields=(), reasons=tuple(sorted(why)))
                      for path in PRIVATE_PATHS[oracle.scope, provider.provider])
        if mixed:
            old_scope = F.ScopeRecord("project", oracle.directory, "installed", "normal",
                                     "unchanged", (F.NORMAL.providers[0],))
            old_scope = F.bind(old_scope, {"project": oracle.directory})
            old = legacy_detection_projection(old_scope).providers[0]
            reasons.update(old.reasons)
            files += old.files
        providers.append(replace(provider, generations=generations, customization="unknown",
                                 files=files, reasons=tuple(sorted(reasons))))
    reasons = set(oracle.reasons)
    if oracle.scope == "project":
        reasons.update(reason for p in providers for reason in p.reasons
                       if reason in ("manifest-missing", "manifest-corrupt"))
    return replace(oracle, providers=tuple(providers), reasons=tuple(sorted(reasons)),
                   customization="not-applicable" if oracle.installation == "absent"
                   else "unknown")


def assert_private_projection(test, actual, oracle):
    wanted = private_detection_projection(oracle)
    assert_detection_projection(test, actual, wanted)


def without_core_selection(provider):
    return replace(provider, generations=tuple(
        replace(g, evidence=g.evidence[:1], reported_ref=None)
        if g.generation == "private-preview-api-1" and g.reported_ref is not None else g
        for g in provider.generations))


def assert_stale_combination(test, result, before):
    test.assertEqual(result.exit_code, 1)
    test.assertEqual(result.scopes[0], before.scopes[0])
    test.assertEqual(result.core, before.core)
    test.assertEqual(result.scopes[1].installation, "unknown")
    test.assertIn("inconsistent-evidence", result.scopes[1].reasons)
    test.assertIn("inconsistent-evidence", codes(result))
    for actual, observed in zip(result.scopes[1].providers, before.scopes[1].providers):
        test.assertEqual(actual.installation, "unknown")
        test.assertEqual(actual.generations, observed.generations,
                         "observed generation/provenance was lost or replaced")
        test.assertEqual(tuple(f.path for f in actual.files), tuple(f.path for f in observed.files))
        test.assertTrue(set(observed.reasons) <= set(actual.reasons))
        for file in actual.files:
            test.assertEqual(file.status, "unknown")
            test.assertEqual(file.baseline.status, "unavailable")
            test.assertIn("inconsistent-evidence", file.reasons)
    test.assertEqual(result.digests, ())
    test.assertTrue(all(not c.consistent for c in result.collections))
    test.assertTrue(all(o.data is None for c in result.collections for o in c.observations))


class PrivateProjectionTests(unittest.TestCase):
    def test_complete_oracles_reject_extra_duplicate_and_misattributed_records(self):
        count = 0
        for oracle, projection, assertion in (
                (F.PRIVATE_GLOBAL, private_detection_projection, assert_private_projection),
                (F.PRIVATE_LOCAL, private_detection_projection, assert_private_projection),
                (F.NORMAL, legacy_detection_projection, assert_legacy_projection),
                (F.GUEST, legacy_detection_projection, assert_legacy_projection),
                (F.OLD, legacy_detection_projection, assert_legacy_projection)):
            oracle = F.bind(oracle, {"project": "/project", "home": "/home", "core": "/core",
                                     "release": "r-" + "a" * 64})
            expected = projection(oracle)
            for index, provider in enumerate(expected.providers):
                witness = expected.providers[0].files[0]
                extras = (
                    replace(witness, path="/invented-extra-private-file"),
                    replace(witness, path=oracle.directory + "/unlisted/agent.md"),
                    replace(witness, path=oracle.directory + "/../outside.md"),
                    replace(witness, path=oracle.directory +
                            "/.claude/agents/domestique-claude-invented.md"),
                    replace(witness, path="/core/active"),
                    replace(witness, path="/core/releases/r-" + "a" * 64 + "/roles/reviewer.md"),
                    witness,
                )
                for extra in extras:
                    actual = replace(expected, providers=tuple(
                        replace(p, files=(*p.files, extra)) if i == index else p
                        for i, p in enumerate(expected.providers)))
                    with self.assertRaises(AssertionError):
                        assertion(self, actual, oracle)
                    count += 1
                for file in provider.files[1:]:
                    for field, value in (("status", "missing"), ("ownership", "invented"),
                                         ("reasons", ("invented",))):
                        actual = replace(expected, providers=tuple(
                            replace(p, files=tuple(
                                replace(f, **{field: value}) if f == file else f for f in p.files))
                            if i == index else p for i, p in enumerate(expected.providers)))
                        with self.assertRaises(AssertionError):
                            assertion(self, actual, oracle)
                        count += 1
            if all(p.files for p in expected.providers):
                first, second, *rest = expected.providers
                swapped = replace(expected, providers=(
                    replace(first, files=(second.files[0], *first.files[1:])),
                    replace(second, files=(first.files[0], *second.files[1:])), *rest))
                with self.assertRaises(AssertionError):
                    assertion(self, swapped, oracle)
                count += 1
        print(f"complete inventory oracle: {count} extra/duplicate/ownership/field mutations rejected",
              flush=True)

    def test_every_private_field_and_reason_is_load_bearing(self):
        count = 0
        for row in F.MATRIX:
            if row.cohort != "private":
                continue
            for oracle in F.bind(row.record, {"requested": "/project", "project": "/project",
                                             "home": "/home",
                                             "core": "/core", "release": "r-" + "a" * 64}).scopes:
                expected = private_detection_projection(oracle)
                assert_private_projection(self, expected, oracle)
                mutations = [replace(expected, **{k: v}) for k, v in (
                    ("scope", "wrong"), ("directory", "/wrong"), ("installation", "wrong"),
                    ("mode", "wrong"), ("customization", "wrong"), ("reasons", ("invented",)),
                    ("beads", "wrong"), ("providers", ()))]
                for index, provider in enumerate(expected.providers):
                    damaged = [replace(provider, **{k: v}) for k, v in (
                        ("provider", "wrong"), ("generations", ()), ("installation", "wrong"),
                        ("mode", "wrong"), ("customization", "wrong"), ("files", ()),
                        ("reasons", ("invented",)))]
                    damaged += [replace(provider, reasons=tuple(
                        r for r in provider.reasons if r != reason)) for reason in provider.reasons]
                    for gi, generation in enumerate(provider.generations):
                        for key, value in (("generation", "wrong"), ("evidence", ()),
                                           ("reported_version", "2.0.0"),
                                           ("reported_ref", "wrong")):
                            damaged.append(replace(provider, generations=tuple(
                                replace(g, **{key: value}) if j == gi else g
                                for j, g in enumerate(provider.generations))))
                        for path in generation.evidence:
                            damaged.append(replace(provider, generations=tuple(
                                replace(g, evidence=tuple(p for p in g.evidence if p != path))
                                if j == gi else g for j, g in enumerate(provider.generations))))
                    for fi, file in enumerate(provider.files):
                        altered = [replace(file, **{k: v}) for k, v in (
                            ("path", "/wrong"), ("status", "wrong"), ("ownership", "wrong"),
                            ("comparison", "wrong"), ("metadata", "wrong"),
                            ("instructions", "wrong"), ("permission_fields", ("tools",)),
                            ("reasons", ("invented",)))]
                        altered += [replace(file, reasons=tuple(
                            r for r in file.reasons if r != reason)) for reason in file.reasons]
                        altered += [replace(file, baseline=replace(file.baseline, **{k: v}))
                                    for k, v in (("kind", "wrong"), ("status", "wrong"),
                                                 ("path", "/wrong"))]
                        damaged += [replace(provider, files=tuple(
                            f if j != fi else change for j, f in enumerate(provider.files)))
                                    for change in altered]
                    mutations += [replace(expected, providers=tuple(
                        change if j == index else p for j, p in enumerate(expected.providers)))
                                  for change in damaged if change != provider]
                for actual in mutations:
                    if actual == expected:
                        continue
                    with self.assertRaises(AssertionError):
                        assert_private_projection(self, actual, oracle)
                    count += 1
        print(f"private projection: {count} dropped/invented-field mutations rejected", flush=True)


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


    def private_scan(self, case, *, with_legacy=False):
        with patch.dict(os.environ, case.env, clear=True):
            context = I.resolve_context(case.requested)
            legacy = I.inspect_scan_legacy(context) if with_legacy else None
            real_open = I.os.open

            def guarded_open(path, *args, **kwargs):
                self.assertNotIn(path, ("SYNTHETIC", "metadata.json", "config.yaml",
                                        ".local_version", "embeddeddolt", "dolt"),
                                 "opened Beads metadata/engine leaf")
                return real_open(path, *args, **kwargs)

            with patch.object(I.os, "open", side_effect=guarded_open), \
                    patch.object(I, "Collector", wraps=I.Collector) as readers, \
                    patch.object(I.os, "scandir", side_effect=AssertionError("enumeration")), \
                    patch.object(I.os, "listdir", side_effect=AssertionError("enumeration")), \
                    patch.object(I.Path, "read_bytes", side_effect=AssertionError("raw read")), \
                    patch.object(I.Path, "read_text", side_effect=AssertionError("raw read")), \
                    patch.object(I.subprocess, "Popen", side_effect=AssertionError("execution")):
                result = I.inspect_scan_private(context, legacy=legacy)
            self.assertTrue({call.args[0] for call in readers.call_args_list} <=
                            {case.env["HOME"], case.env["DOMESTIQUE_HOME"], str(case.project)},
                            "a persisted foreign binding authorized a read")
        self.assertNotIn(F.SECRET, repr(result))
        self.assertTrue(all(c.consistent for c in result.collections))
        self.assertNotIn("unread-required-input", codes(result))
        self.assertEqual(result.core.label, "PRIVATE PREVIEW")
        self.assertEqual(result.beads.readiness, "not-assessed")
        return result

    def assert_private_inputs(self, case, result, skip_scope=None):
        # Verify actual baseline fingerprints from installed records, NOT from
        # current emitters or customized native leaves. Never echo private bytes.
        expected = {}
        for root, manifest in ((Path(case.env["HOME"]), Path(case.env["DOMESTIQUE_HOME"]) /
                                "state/global-manifest"),
                               (case.project, case.project / ".domestique-private/manifest")):
            if skip_scope == ("project" if root == case.project else "global"):
                continue
            entry = case.before.get(str(manifest.relative_to(self.session.root)))
            if entry is None or not entry.data.startswith(b"format=1\n"):
                continue
            for line in entry.data.decode().splitlines():
                if line.startswith("baseline=") and not line.startswith("baseline=core:"):
                    path, digest = line[len("baseline="):].split(":", 1)[1].rsplit(":", 1)
                    expected[str(root / path)] = (str(manifest), digest, False)
        actual = {d.path: (d.baseline_path, d.sha256, d.content_available) for d in result.digests}
        self.assertEqual(len(actual), len(result.digests))
        self.assertTrue(actual == expected, "installed digest/content availability mismatch")
        for collection in result.collections:
            for observed in collection.observations:
                if observed.data is not None and not any(
                        observed.path in p for p in PRIVATE_PATHS.values()):
                    # The coexistence scanner retains its legacy snapshots.
                    self.assertEqual(case.scenario.mutation, "generations")
        return len(actual)

    def accept_private(self, case, result, *, observed_before=None):
        public = {"scopes": tuple(asdict(s) for s in result.scopes),
                  "core": asdict(result.core), "beads": asdict(result.beads),
                  "diagnostics": tuple(asdict(d) for d in result.diagnostics),
                  "exit_code": result.exit_code}
        output = json.dumps(public, ensure_ascii=True).encode()
        if observed_before is not None:
            # Coexistence is staged after pristine capture. A deleted legacy
            # witness still has an actual, pre-mutation path and private corpus.
            # Qualify the FULL report against those captured bytes too, never
            # against scanner-derived paths or a prefix/name exemption.
            privacy_case = types.SimpleNamespace(
                project=case.project, requested=case.requested, before=case.before,
                session=types.SimpleNamespace(
                    root=self.session.root,
                    pristine={**observed_before, **self.session.pristine}))
            F.assert_private_output(privacy_case, output, b"")
            # The unchanged fixture accept() still enforces all preservation,
            # stub and restoration checks on the post-mutation snapshot.
            output = json.dumps({"exit_code": result.exit_code,
                                 "scopes": tuple(s.installation for s in result.scopes)}).encode()
        case.accept(output, b"")

    def test_zz_private_source_qualified_projection(self):
        type(self).complete = False
        selected = [row for row in F.MATRIX if row.cohort == "private"]
        counts = {}
        for row in selected:
            with self.subTest(scenario=row.name):
                case = self.session.begin(row.name)
                expected = case.expected()
                result = self.private_scan(case, with_legacy=row.mutation == "generations")
                self.assertEqual(result.exit_code, expected.exit_code)
                for actual, oracle in zip(result.scopes, expected.scopes):
                    if row.mutation == "core":
                        wanted = private_detection_projection(oracle)
                        wanted = replace(wanted, providers=tuple(
                            without_core_selection(p) for p in wanted.providers))
                        assert_detection_projection(self, actual, wanted)
                    else:
                        assert_private_projection(self, actual, oracle)
                release = expected.scopes[0].providers[0].generations[0].reported_ref
                core = case.env["DOMESTIQUE_HOME"]
                core_paths = ("state/global-manifest", "active", "bin/resolve-core",
                              "releases/" + release + "/API",
                              "releases/" + release + "/SHA256SUMS") + tuple(
                                  "releases/" + release + "/roles/" + r + ".md"
                                  for r in ("goal", "implementer", "orchestrator", "reviewer"))
                self.assertEqual(asdict(result.core), dict(
                    directory=core, selector="DOMESTIQUE_HOME",
                    status="partial" if row.mutation == "core" else "available",
                    release=release, evidence=tuple(core + "/" + p for p in core_paths),
                    reasons=("core-selector-corrupt", "core-content-edited")
                    if row.mutation == "core" else (), label="PRIVATE PREVIEW"))
                self.assertEqual((result.beads.path, result.beads.ownership, result.beads.state),
                                 (str(case.project / ".beads"),
                                  "unknown" if row.mutation == "corrupt-manifest" else "unowned",
                                  "unattached" if row.mutation == "beads" else "absent"))
                self.assertEqual(result.beads.reasons,
                                 ("beads-metadata-only", "synthetic-beads-metadata-only")
                                 if row.mutation == "beads" else ())
                statuses = {p.path: p.status for p in result.beads.presence}
                known = (
                    ".beads", ".beads/SYNTHETIC", ".beads/metadata.json", ".beads/config.yaml",
                    ".beads/.local_version", ".beads/embeddeddolt", ".beads/dolt",
                    ".domestique-private/beads-context", ".domestique-private/exports",
                    ".domestique-private/beads-attempt")
                self.assertEqual(statuses, {str(case.project / path): (
                    "regular" if path == ".beads/SYNTHETIC" else "directory")
                    if row.mutation == "beads" and path in
                    (".beads", ".beads/SYNTHETIC", ".beads/dolt") else "missing" for path in known})
                self.assertTrue(all(not p.reasons for p in result.beads.presence))
                # A corrupt manifest makes unattached Beads ownership unknown,
                # but cannot change the observed absence or readiness.
                counts[row.name] = self.assert_private_inputs(case, result)
                self.accept_private(case, result)
                print("private oracle accepted:", row.name, "digests=" + str(counts[row.name]),
                      flush=True)
            if self.session.active is not None:
                return
        print(f"private oracle: {len(selected)} source-qualified cases; "
              f"{sum(counts.values())} genuine digest witnesses", flush=True)
        type(self).complete = True

    def test_zzz_private_structural_mutations(self):
        type(self).complete = False
        # All mutations start from the same genuine global/local cohort. No
        # extra installer calls, current-emitter baselines, native clients or DB.
        names = (
            "local-profile-missing", "local-profile-symlink", "local-profile-hardlink",
            "receipt-missing", "receipt-corrupt", "receipt-symlink", "receipt-foreign-core",
            "project-binding", "local-core-binding", "local-core-missing", "local-core-corrupt",
            "local-schema", "local-inventory",
            "local-pending", "providers-none", "local-subset", "beads-owned",
            "beads-retained", "beads-unknown-schema", "beads-pending",
            "global-manifest-missing", "global-manifest-corrupt", "global-schema",
            "global-binding", "global-inventory", "global-pending",
            "global-native-missing", "global-native-symlink", "global-native-hardlink",
            "core-api", "core-role-edited", "core-helper-missing", "core-helper-edited",
            "core-selector-symlink", "core-selector-missing", "core-sums-corrupt",
        )
        for name in names:
            with self.subTest(mutation=name):
                case = self.session.begin("private-global-and-local")
                root, core = case.project, Path(case.env["DOMESTIQUE_HOME"])
                local = root / ".domestique-private/manifest"
                global_manifest = core / "state/global-manifest"
                local_text, global_text = local.read_text(), global_manifest.read_text()
                release = (core / "active").read_text().split("=")[1].strip()
                local_leaf = root / PRIVATE_PATHS["project", "claude"][0]
                global_leaf = Path(case.env["HOME"]) / PRIVATE_PATHS["global", "claude"][3]
                receipt = root / ".domestique-private/routing/claude.receipt"
                leaf = global_leaf if name.startswith("global-native") else local_leaf
                if name in ("local-profile-missing", "global-native-missing"):
                    leaf.unlink()
                elif name in ("local-profile-symlink", "global-native-symlink"):
                    leaf.unlink()
                    leaf.symlink_to(core / "active")
                elif name in ("local-profile-hardlink", "global-native-hardlink"):
                    os.link(leaf, root / "live-only-hardlink-peer")
                elif name.startswith("receipt-"):
                    if name == "receipt-corrupt":
                        receipt.write_text(receipt.read_text().replace(
                            "provider=claude", "provider=codex"))
                    elif name == "receipt-foreign-core":
                        receipt.write_text(receipt.read_text().replace(
                            "core_root=" + str(core), "core_root=/unobserved-foreign-core"))
                    else:
                        receipt.unlink()
                        if name == "receipt-symlink":
                            receipt.symlink_to(core / "active")
                elif name == "project-binding":
                    local.write_text(local_text.replace(
                        "worktree_root=" + str(root), "worktree_root=/wrong"))
                elif name == "local-core-binding":
                    local.write_text(local_text.replace("core_root=" + str(core), "core_root=/wrong"))
                    for provider in F.PROVIDERS:
                        path = root / f".domestique-private/routing/{provider}.receipt"
                        path.write_text(path.read_text().replace(
                            "core_root=" + str(core), "core_root=/wrong"))
                elif name in ("local-core-missing", "local-core-corrupt"):
                    local.write_text(local_text.replace("core_root=" + str(core) + "\n",
                                                       "" if name == "local-core-missing" else
                                                       "core_root=relative-core\n"))
                elif name == "local-schema":
                    local.write_text(local_text.replace("format=1", "format=99", 1))
                elif name == "local-inventory":
                    local.write_text(local_text.replace(
                        "claude:.claude/agents/domestique-claude-local-implementer.md",
                        "claude:../" + F.SECRET))
                elif name == "local-pending":
                    (root / ".domestique-private/pending").write_text(F.SECRET)
                elif name in ("providers-none", "local-subset"):
                    lines = local_text.splitlines(keepends=True)
                    header = "".join(lines[:6])
                    if name == "providers-none":
                        local.write_text(header.replace("providers=all", "providers=none"))
                        for provider in F.PROVIDERS:
                            for path in PRIVATE_PATHS["project", provider]:
                                (root / path).unlink()
                            (root / f".domestique-private/routing/{provider}.receipt").unlink()
                    else:
                        # local_manifest_read explicitly accepts role subsets
                        # and receipt role order follows the paired inventory.
                        local.write_text(header + "".join(
                            line for line in lines[6:] if "claude-local-reviewer" not in line))
                        (root / PRIVATE_PATHS["project", "claude"][1]).unlink()
                        receipt.write_text(receipt.read_text().replace(
                            "role=domestique-claude-local-reviewer\n", ""))
                elif name.startswith("beads-"):
                    # Structural metadata only, no engine/native initialization.
                    # A different installed version and fingerprint are allowed
                    # declarations, not a requirement to load a pinned runtime.
                    fields = (
                        ("beads_path", ".beads"), ("beads_path_created", "by-init:" + "a" * 32),
                        ("beads_status", "retained" if name == "beads-retained" else "ready"),
                        ("beads_executable", "/nonexistent/bd"), ("beads_sha256", "b" * 64),
                        ("beads_version", "99.1.2"), ("beads_platform", "Darwin-arm64"),
                        ("beads_backend", "dolt-embedded-cgo"),
                        ("beads_context", ".domestique-private/beads-context"),
                        ("beads_prefix", "dm" + "a" * 12),
                        ("beads_uuid", "00000000-0000-0000-0000-000000000000"),
                        ("beads_readiness", "init-ping-where-v1"),
                        ("beads_selectors_sha256", "c" * 64), ("beads_git", "/nonexistent/git"),
                        ("beads_git_sha256", "d" * 64))
                    declaration = "".join(k + "=" + v + "\n" for k, v in fields)
                    declared_paths = tuple(".beads/" + p for p in (
                        ".gitignore", ".local_version", "README.md", "config.yaml",
                        "embeddeddolt", "interactions.jsonl", "last-touched", "metadata.json"
                    )) + (".domestique-private/beads-context", ".domestique-private/exports")
                    declaration += "".join("beads_created=" + p + ":" + "e" * 64 + "\n"
                                           for p in declared_paths)
                    if name == "beads-unknown-schema":
                        declaration = declaration.replace("beads_backend=", "unknown_backend=")
                    local.write_text(local_text + declaration)
                    if name == "beads-pending":
                        (root / ".domestique-private/beads-attempt").write_text(F.SECRET)
                elif name == "global-manifest-missing":
                    global_manifest.unlink()
                elif name == "global-manifest-corrupt":
                    global_manifest.write_text("format=\0\n" + F.SECRET)
                elif name == "global-schema":
                    global_manifest.write_text(global_text.replace("format=1", "format=99", 1))
                elif name == "global-binding":
                    global_manifest.write_text(global_text.replace(
                        "core_root=" + str(core), "core_root=/wrong"))
                elif name == "global-inventory":
                    global_manifest.write_text(global_text.replace(
                        "claude:.claude/skills/domestique-claude/SKILL.md",
                        "claude:../" + F.SECRET))
                elif name == "global-pending":
                    (core / "state/pending").write_text(F.SECRET)
                elif name == "core-api":
                    (core / f"releases/{release}/API").write_text(
                        f"format=1\ncore_api=99\nrelease={release}\n")
                elif name == "core-role-edited":
                    path = core / f"releases/{release}/roles/implementer.md"
                    path.write_text(path.read_text() + F.SECRET)
                elif name == "core-helper-missing":
                    (core / "bin/resolve-core").unlink()
                elif name == "core-helper-edited":
                    path = core / "bin/resolve-core"
                    path.write_text(path.read_text() + "\n" + F.SECRET)
                elif name.startswith("core-selector"):
                    (core / "active").unlink()
                    if name == "core-selector-symlink":
                        (core / "active").symlink_to(core / "state/global-manifest")
                elif name == "core-sums-corrupt":
                    (core / f"releases/{release}/SHA256SUMS").write_text(F.SECRET)
                else:
                    self.fail("undeclared private mutation")
                case.before = self.session.snapshot()
                result = self.private_scan(case)
                self.assert_private_mutation(case, result, name, release)
                self.accept_private(case, result)
                print("private structural accepted:", name, flush=True)
            if self.session.active is not None:
                return
        print(f"private structural: {len(names)} production-format mutations; six-install reuse",
              flush=True)
        type(self).complete = True

    def assert_private_mutation(self, case, result, name, release):
        global_scope, project = result.scopes
        expected_global, expected_project = tuple(
            private_detection_projection(s) for s in case.expected().scopes)
        expected_core_reasons = {
            "global-manifest-missing": ("manifest-missing",),
            "global-manifest-corrupt": ("manifest-corrupt",),
            "global-schema": ("manifest-schema-unsupported",),
            "global-binding": ("core-binding-mismatch",),
            "global-inventory": ("manifest-inventory-corrupt",),
            "global-pending": ("global-publication-pending",),
            "core-api": ("core-api-unsupported", "core-content-edited"),
            "core-role-edited": ("core-content-edited",),
            "core-helper-missing": ("core-resource-unavailable",),
            "core-helper-edited": ("core-content-edited",),
            "core-selector-symlink": ("core-selector-corrupt", "core-resource-unavailable"),
            "core-selector-missing": ("core-selector-missing", "core-resource-unavailable"),
            "core-sums-corrupt": ("core-content-edited",),
        }.get(name, ())
        self.assertEqual(result.core.reasons, expected_core_reasons)
        self.assertEqual(result.core.status, "partial" if expected_core_reasons else "available")
        self.assertEqual(result.core.release, None if name in (
            "core-api", "core-role-edited", "core-sums-corrupt") else release)
        self.assertEqual(result.core.directory, case.env["DOMESTIQUE_HOME"])
        self.assertEqual(result.core.selector, "DOMESTIQUE_HOME")
        core = case.env["DOMESTIQUE_HOME"]
        paths = ["state/global-manifest", "active", "bin/resolve-core",
                 f"releases/{release}/API", f"releases/{release}/SHA256SUMS"]
        paths += [f"releases/{release}/roles/{r}.md"
                  for r in ("goal", "implementer", "orchestrator", "reviewer")]
        omitted = {"global-manifest-missing": "state/global-manifest",
                   "core-selector-missing": "active", "core-helper-missing": "bin/resolve-core"}
        if name in omitted:
            paths.remove(omitted[name])
        if name == "global-pending":
            paths.insert(3, "state/pending")
        self.assertEqual(result.core.evidence, tuple(core + "/" + p for p in paths))
        if expected_core_reasons:
            expected_global = replace(expected_global, installation="partial",
                                      reasons=("core-inconsistent",))
        if name in ("core-api", "core-role-edited", "core-sums-corrupt",
                    "core-selector-missing", "core-selector-symlink"):
            def unbound(scope):
                return replace(scope, providers=tuple(
                    without_core_selection(p) for p in scope.providers))
            expected_global, expected_project = unbound(expected_global), unbound(expected_project)
        bad_manifest = {
            "project-binding": "project-binding-mismatch",
            "local-schema": "manifest-schema-unsupported",
            "local-inventory": "manifest-inventory-corrupt",
            "local-core-missing": "manifest-corrupt",
            "local-core-corrupt": "manifest-corrupt",
            "global-manifest-missing": "manifest-missing",
            "global-manifest-corrupt": "manifest-corrupt",
            "global-schema": "manifest-schema-unsupported",
            "global-binding": "core-binding-mismatch",
            "global-inventory": "manifest-inventory-corrupt",
        }.get(name)
        if bad_manifest:
            scope = expected_global if name.startswith("global-") else expected_project
            records = []
            for p in scope.providers:
                # openai.yaml alone has no provider-qualified body; every other
                # genuine global file and both local roles corroborate preview.
                files = tuple(replace(f, baseline=F.Baseline("none", "unavailable"),
                                      ownership="unknown",
                                      reasons=tuple(sorted((bad_manifest, "baseline-unavailable"))))
                              for f in p.files if not f.path.endswith("/openai.yaml"))
                records.append(replace(
                    p, installation="partial", files=files,
                    reasons=tuple(sorted((bad_manifest, "baseline-unavailable"))),
                    generations=(F.GenerationEvidence(
                        "private-preview-api-1", tuple(f.path for f in files), None, None),)))
            scope = replace(scope, installation="partial", providers=tuple(records),
                            reasons=scope.reasons if name.startswith("global-")
                            else (bad_manifest,))
            if name.startswith("global-"):
                expected_global = scope
            else:
                expected_project = scope
        file_reason = {
            "local-profile-missing": "managed-file-missing",
            "global-native-missing": "managed-file-missing",
            "local-profile-symlink": "unsafe-symlink",
            "global-native-symlink": "unsafe-symlink",
            "local-profile-hardlink": "unsafe-hardlink",
            "global-native-hardlink": "unsafe-hardlink",
        }.get(name)
        if file_reason:
            scope = expected_global if name.startswith("global") else expected_project
            provider = scope.providers[0]
            files = tuple(replace(f, status="missing" if name.endswith("missing") else "unsafe",
                                  reasons=tuple(sorted((*f.reasons, file_reason))))
                          if "-implementer." in f.path else f for f in provider.files)
            provider = replace(provider, installation="partial", files=files,
                               reasons=tuple(sorted((*provider.reasons, file_reason))))
            scope = replace(scope, installation="partial", providers=(provider, *scope.providers[1:]))
            if name.startswith("global"):
                expected_global = scope
            else:
                expected_project = scope
        if name.startswith("receipt-"):
            reasons = ("receipt-missing",) if name == "receipt-missing" else (
                ("receipt-corrupt", "unsafe-symlink") if name == "receipt-symlink"
                else ("receipt-corrupt",))
            p = expected_project.providers[0]
            expected_project = replace(expected_project, installation="partial", providers=(
                replace(without_core_selection(p), installation="partial",
                        reasons=tuple(sorted((*p.reasons, *reasons)))),
                *expected_project.providers[1:]))
        if name in ("local-core-binding", "local-pending"):
            expected_project = replace(expected_project, installation="partial",
                                       reasons=("core-binding-mismatch" if name == "local-core-binding"
                                                else "local-publication-pending",))
            if name == "local-core-binding":
                expected_project = replace(expected_project, providers=tuple(
                    replace(without_core_selection(p), installation="partial",
                            reasons=tuple(sorted((*p.reasons, "core-binding-mismatch"))))
                    for p in expected_project.providers))
        if name == "providers-none":
            expected_project = F.bind(F.absent_scope("project"), {"project": str(case.project)})
            expected_project = replace(expected_project, reasons=("providers-none-retained",))
        if name == "local-subset":
            p = expected_project.providers[0]
            expected_project = replace(expected_project, providers=(
                replace(p, files=p.files[:1]), *expected_project.providers[1:]))
        if name.startswith("beads-"):
            problem = name == "beads-unknown-schema"
            pending = name == "beads-pending"
            expected_project = replace(expected_project, beads="absent" if problem else
                                       "metadata-presence-only", installation="partial"
                                       if problem or pending else "installed",
                                       reasons=("beads-schema-unsupported",) if problem else
                                       ("beads-attachment-pending",) if pending else ())
            self.assertEqual((result.beads.ownership, result.beads.state, result.beads.reasons),
                             ("unknown", "unknown", ("beads-schema-unsupported",)) if problem else
                             ("declared-owned", "pending" if pending else "retained"
                              if name == "beads-retained" else "declared-ready",
                              ("beads-metadata-only",)))
        else:
            self.assertEqual(result.beads.reasons, ())
            self.assertEqual(result.beads.ownership,
                             "unknown" if bad_manifest and not name.startswith("global") else "unowned")
            self.assertEqual(result.beads.state, "pending" if name == "local-pending" else "absent")
        self.assertEqual(result.beads.path, str(case.project / ".beads"))
        for p in result.beads.presence:
            self.assertEqual(p.status, "regular" if name == "beads-pending" and
                             p.path.endswith("/beads-attempt") else "missing")
            self.assertEqual(p.reasons, ())
        assert_detection_projection(self, global_scope, expected_global)
        assert_detection_projection(self, project, expected_project)
        self.assertEqual(tuple(len(p.files) for p in global_scope.providers),
                         tuple(len(p.files) for p in expected_global.providers))
        self.assertEqual(tuple(len(p.files) for p in project.providers),
                         tuple(len(p.files) for p in expected_project.providers))
        self.assertEqual(result.exit_code, 0 if name in (
            "providers-none", "local-subset", "beads-owned", "beads-retained") else 1)
        self.assert_private_inputs(case, result, skip_scope=(
            "global" if name.startswith("global") else "project") if bad_manifest else None)

    def test_zzzz_supplied_legacy_generation_is_revalidated_in_same_cohort(self):
        type(self).complete = False
        names = ("stable", "file-content", "file-identity", "file-deletion",
                 "manifest-format", "manifest-ref", "policy-identity", "context-identity")
        for name in names:
            with self.subTest(mutation=name):
                case = self.session.begin("multiple-generations-one-provider")
                observed_before = case.before
                with patch.dict(os.environ, case.env, clear=True):
                    context = I.resolve_context(case.requested)
                    legacy = I.inspect_scan_legacy(context)
                    before = I.inspect_scan_private(context, legacy=legacy)
                    target = case.project / (
                        MANIFEST if name.startswith("manifest-") else
                        "CLAUDE.md" if name == "policy-identity" else LEAF)
                    if name == "file-content":
                        target.write_bytes(target.read_bytes() + b"\nchanged owned body\n")
                    elif name in ("file-identity", "policy-identity"):
                        replacement = target.with_name(target.name + ".replacement")
                        replacement.write_bytes(target.read_bytes())
                        os.replace(replacement, target)
                    elif name == "file-deletion":
                        target.unlink()
                    elif name == "manifest-format":
                        target.write_text(target.read_text().replace("snapshot_format=1",
                                                                     "snapshot_format=99"))
                    elif name == "manifest-ref":
                        target.write_text(target.read_text().replace("installed_ref=unknown",
                                                                     "installed_ref=abc123"))
                    elif name == "context-identity":
                        marker = case.project / ".git"
                        marker.chmod(stat.S_IMODE(marker.stat().st_mode) ^ 0o010)
                    case.before = self.session.snapshot()
                    # A new context must not launder the original context proof.
                    result = I.inspect_scan_private(I.resolve_context(case.requested), legacy=legacy)
                    if name == "stable":
                        self.assertEqual(result, before)
                        self.assertEqual(result.collections[-3:], legacy.collections)
                        self.assertTrue(any(o.data is not None for c in legacy.collections
                                            for o in c.observations))
                    else:
                        assert_stale_combination(self, result, before)
                        if name == "manifest-format":
                            fresh = I.inspect_scan_legacy(I.resolve_context(case.requested))
                            self.assertEqual(fresh.scope.installation, "partial")
                            self.assertEqual(fresh.exit_code, 1)
                    self.accept_private(case, result, observed_before=observed_before)
                    print("supplied legacy source-qualified:", name, flush=True)
            if self.session.active is not None:
                return
        print(f"supplied legacy: {len(names)} cases; same six-install cohort", flush=True)
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


class PrivateBoundaryTests(unittest.TestCase):
    setUp = BoundaryTests.setUp
    tearDown = BoundaryTests.tearDown
    guarded = BoundaryTests.guarded

    def scan(self, **kwargs):
        context = I.resolve_context(self.project)
        return self.guarded(lambda: I.inspect_scan_private(context, **kwargs))

    def seed_legacy(self, state):
        if state == "absent":
            return
        for provider in F.PROVIDERS:
            for path in LEGACY_PATHS[provider]:
                LegacyFailureTests.write(self, path, "owned fixture native\n")
            prefix = {"claude": ".claude", "codex": ".codex", "copilot": ".github"}[provider]
            policy = {"claude": "CLAUDE.md", "codex": "AGENTS.md",
                      "copilot": ".github/copilot-instructions.md"}[provider]
            manifest = ("snapshot_format=1\nplatform=" + provider +
                        "\ndomestique_version=0.1.0\ninstalled_ref=abc123\n"
                        "installed_at=2026-01-01T00:00:00Z\nscript_sha256=unavailable\nfiles=" +
                        ",".join((*LEGACY_PATHS[provider], policy)) + "\n")
            LegacyFailureTests.write(self, prefix + "/.domestique/manifest", manifest)
            LegacyFailureTests.write(self, policy, F.BEGIN + b"\nowned\n" + F.END + b"\n")
            if state == "partial":
                LegacyFailureTests.write(self, LEGACY_PATHS[provider][0], b"\xff")

    def test_private_failure_survives_every_legacy_combination(self):
        pristine = self.session.snapshot()
        real_read = I.Collector.read
        for private_state in ("pending", "corrupt", "unknown"):
            for legacy_state in ("absent", "installed", "partial"):
                with self.subTest(private=private_state, legacy=legacy_state):
                    self.seed_legacy(legacy_state)
                    if private_state == "pending":
                        LegacyFailureTests.write(self, ".domestique-private/pending", "pending\n")
                    elif private_state == "corrupt":
                        LegacyFailureTests.write(self, ".domestique-private/manifest", "format=99\n")

                    def read(reader, path):
                        if private_state == "unknown" and reader.scope.startswith("project:") and \
                                path.endswith(".receipt"):
                            return None  # Deliberately omit a required boundary observation.
                        return real_read(reader, path)

                    context = I.resolve_context(self.project)
                    legacy = self.guarded(lambda: I.inspect_scan_legacy(context))
                    self.assertEqual(legacy.scope.installation, legacy_state)
                    with patch.object(I.Collector, "read", new=read):
                        preview = self.scan()
                        combined = self.scan(legacy=legacy)
                    self.assertEqual(preview.exit_code, 1)
                    self.assertEqual(combined.exit_code, 1)
                    expected_state = "partial" if private_state != "unknown" or \
                        legacy_state == "partial" else "unknown"
                    self.assertEqual(combined.scopes[1].installation, expected_state)
                    self.assertTrue(set(preview.scopes[1].reasons) <= set(combined.scopes[1].reasons))
                    self.assertEqual(combined.scopes[0], preview.scopes[0])
                    self.assertEqual(combined.collections[-3:], legacy.collections)
                    for p, old, local in zip(combined.scopes[1].providers, legacy.scope.providers,
                                             preview.scopes[1].providers):
                        self.assertEqual(p.generations, old.generations)
                        self.assertEqual(p.files, old.files)
                        self.assertEqual(p.installation, (
                            "partial" if legacy_state == "partial" else "unknown")
                            if private_state == "unknown" else old.installation)
                        self.assertNotIn("multiple-generations", p.reasons)
                        if private_state == "unknown":
                            self.assertTrue(set(local.reasons) <= set(p.reasons))
                    self.session.pristine = pristine
                    self.session.restore(self.session.snapshot())
                    pristine = self.session.pristine
        print("private failure merge: 9 combinations, 27 provider records", flush=True)

    def test_supplied_legacy_real_file_changes_cannot_be_laundered(self):
        self.seed_legacy("installed")
        pristine = self.session.snapshot()
        for mutation in ("stable", "file-content", "file-identity", "file-deletion",
                         "manifest-format", "manifest-ref", "policy-identity"):
            with self.subTest(mutation=mutation):
                context = I.resolve_context(self.project)
                legacy = I.inspect_scan_legacy(context)
                before = self.scan(legacy=legacy)
                self.assertEqual(before.exit_code, 0)
                target = self.project / (MANIFEST if mutation.startswith("manifest-") else
                                         "CLAUDE.md" if mutation == "policy-identity" else LEAF)
                if mutation == "file-content":
                    target.write_bytes(target.read_bytes() + b"changed\n")
                elif mutation in ("file-identity", "policy-identity"):
                    replacement = target.with_name(target.name + ".replacement")
                    replacement.write_bytes(target.read_bytes())
                    os.replace(replacement, target)
                elif mutation == "file-deletion":
                    target.unlink()
                elif mutation == "manifest-format":
                    target.write_text(target.read_text().replace("snapshot_format=1",
                                                                 "snapshot_format=99"))
                elif mutation == "manifest-ref":
                    target.write_text(target.read_text().replace("installed_ref=abc123",
                                                                 "installed_ref=def456"))
                result = self.scan(legacy=legacy)
                if mutation == "stable":
                    self.assertEqual(result, before)
                    self.assertEqual(result.collections[-3:], legacy.collections)
                else:
                    assert_stale_combination(self, result, before)
                self.session.pristine = pristine
                self.session.restore(self.session.snapshot())
                pristine = self.session.pristine

    def test_local_declared_binding_does_not_invent_unobserved_core_evidence(self):
        core = self.session.env["DOMESTIQUE_HOME"]
        path = PRIVATE_PATHS["project", "claude"][0]
        text = ("Provider: claude\nScope: local\ncore_api=1\n"
                "Stable loader: domestique-core-api-1; router-api-1;\n")
        LegacyFailureTests.write(self, path, text)
        digest = I.hashlib.sha256(text.encode()).hexdigest()
        for binding in (core, "/unobserved-foreign-core", "relative-core"):
            manifest = (f"format=1\nscope=local\nworktree_root={self.project}\n"
                        f"core_root={binding}\ncore_api=1\nproviders=claude\n" +
                        "".join(f"{key}=claude:{path}:{digest}\n"
                                for key in ("created", "baseline")))
            LegacyFailureTests.write(self, ".domestique-private/manifest", manifest)
            LegacyFailureTests.write(
                self, ".domestique-private/routing/claude.receipt",
                f"format=1\nworktree_root={self.project}\nprovider=claude\ncore_root={binding}\n"
                "core_api=1\nrole=domestique-claude-local-implementer\n")
            with patch.object(I, "Collector", wraps=I.Collector) as readers:
                result = self.scan()
            self.assertTrue({call.args[0] for call in readers.call_args_list} <=
                            {core, self.session.env["HOME"], str(self.project)})
            provider = result.scopes[1].providers[0]
            self.assertEqual(provider.installation, "installed" if binding == core else "partial")
            self.assertEqual(provider.generations[0].reported_ref, None)
            self.assertEqual(provider.generations[0].evidence, (
                str(self.project / (path if binding == "relative-core"
                                    else ".domestique-private/manifest")),))
            self.assertEqual(provider.files[0].path, str(self.project / path))
            if binding == "/unobserved-foreign-core":
                self.assertIn("core-binding-mismatch", provider.reasons)
            self.assertEqual(result.core.status, "absent")

    def test_beads_metadata_exception_cannot_bypass_forbidden_ancestors(self):
        forbidden = (
            ".git/.beads/metadata.json", ".dolt/.beads/config.yaml",
            "engine.sqlite/.beads/config.yaml", "db.sqlite3/.beads/config.yaml",
            "db.db/.beads/config.yaml", "db.db-wal/.beads/config.yaml",
            "db.db-shm/.beads/config.yaml", "nested/.beads/metadata.json",
            ".beads/.beads/metadata.json", ".beads/dolt/.beads/config.yaml",
            ".beads/metadata.json/child", ".beads/metadata.json.bak",
            ".beads/Metadata.json", ".BEADS/metadata.json",
            ".beads/config.yml", ".beads//metadata.json", "./.beads/metadata.json",
            ".git/../.beads/metadata.json", ".beads/../.beads/metadata.json",
            ".beads/dolt/data", ".beads/embeddeddolt/data",
        )
        for path in forbidden:
            with self.subTest(path=path), patch.object(
                    I.os, "open", side_effect=AssertionError("forbidden path opened")):
                result = collect(self.project, (path,), metadata={path: "file"})
                self.assertFalse(result.consistent)
                self.assertFalse(result.observations)
                self.assertTrue(codes(result) & {"escaped-path", "unsupported-input"})
        beads = self.project / ".beads"
        beads.mkdir()
        (beads / "embeddeddolt").mkdir()
        (beads / "dolt").mkdir()
        metadata = {p: kind for p, kind in I.BEADS_METADATA.items() if p.startswith(".beads")}
        result = self.guarded(lambda: collect(self.project, metadata, metadata=metadata))
        self.assertTrue(result.consistent)
        self.assertEqual(tuple(o.status for o in result.observations),
                         ("directory", "missing", "missing", "missing", "missing",
                          "directory", "directory"))
        self.assertTrue(all(o.data is None and o._bytes_read == 0 for o in result.observations))
        alias = self.project / "nested"
        alias.symlink_to(self.project)
        result = self.guarded(lambda: collect(
            self.project, ("nested/.beads/metadata.json",),
            metadata={"nested/.beads/metadata.json": "file"}))
        self.assertFalse(result.consistent)
        (beads / "metadata.json").symlink_to(self.leaf)
        result = self.guarded(lambda: collect(
            self.project, (".beads/metadata.json",), metadata={".beads/metadata.json": "file"}))
        self.assertEqual(result.observations[0].status, "unsafe")
        self.assertIn("unsafe-symlink", codes(result))

    def test_declared_environment_precedence_and_absent_scopes(self):
        for env, directory, selector in (
                ({"DOMESTIQUE_HOME": str(self.root / "chosen"),
                  "XDG_STATE_HOME": str(self.root / "other")},
                 self.root / "chosen", "DOMESTIQUE_HOME"),
                ({"DOMESTIQUE_HOME": "", "XDG_STATE_HOME": str(self.root / "state")},
                 self.root / "state/domestique", "XDG_STATE_HOME"),
                ({"DOMESTIQUE_HOME": "", "XDG_STATE_HOME": ""},
                 self.root / "home/.local/state/domestique", "HOME")):
            with patch.dict(os.environ, env):
                result = self.scan()
            self.assertEqual(asdict(result.core), dict(
                directory=str(directory), selector=selector, status="absent", release=None,
                evidence=(), reasons=("core-missing",), label="PRIVATE PREVIEW"))
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(tuple(s.installation for s in result.scopes), ("absent", "absent"))
            self.assertEqual(tuple(s.directory for s in result.scopes),
                             (str(self.root / "home"), str(self.project)))
            self.assertEqual(result.digests, ())
        with patch.dict(os.environ, HOME="", DOMESTIQUE_HOME="", XDG_STATE_HOME=""):
            with patch.object(I, "Collector", wraps=I.Collector) as collectors:
                result = self.scan()
            self.assertTrue(all(call.args[0] == str(self.project)
                                for call in collectors.call_args_list),
                            "missing HOME invented a global filesystem scope")
        self.assertEqual(asdict(result.core), dict(
            directory="", selector="HOME", status="unknown", release=None,
            evidence=(), reasons=("invalid-core-scope",), label="PRIVATE PREVIEW"))
        self.assertEqual(result.exit_code, 1)

    def test_invalid_or_symlink_core_never_blocks_independent_legacy(self):
        state = self.project / ".claude/.domestique"
        state.mkdir()
        (state / "manifest").write_text(LegacyFailureTests.manifest(self))
        (self.project / "CLAUDE.md").write_bytes(F.BEGIN + b"\nowned\n" + F.END + b"\n")
        alias = self.root / "alias-core"
        alias.symlink_to(self.project)
        for value in ("relative/" + F.SECRET, str(alias)):
            with patch.dict(os.environ, DOMESTIQUE_HOME=value):
                context = I.resolve_context(self.project)
                legacy = I.inspect_scan_legacy(context)
                result = self.guarded(lambda: I.inspect_scan_private(context, legacy=legacy))
            self.assertEqual(asdict(result.scopes[1]), asdict(legacy.scope))
            self.assertEqual(result.core.status, "unknown")
            self.assertEqual(result.exit_code, 1)
            self.assertIsNone(result.core.release)
            self.assertEqual(result.scopes[0].reasons, ("core-inconsistent",))
        with patch.dict(os.environ, DOMESTIQUE_HOME=str(alias)):
            self.assertIn("unsafe-symlink", codes(self.scan()))

    def test_metadata_collector_never_opens_even_oversized_journals(self):
        private = self.project / ".domestique-private"
        private.mkdir()
        journal = private / "pending"
        journal.write_bytes(b"x" * (I.MAX_BYTES + 1))
        allowed = (".domestique-private", ".domestique-private/pending")
        kinds = dict(zip(allowed, ("directory", "file")))
        real_open = I.os.open

        def opened(path, *args, **kwargs):
            self.assertNotEqual(path, "pending", "journal contents opened")
            return real_open(path, *args, **kwargs)

        with patch.object(I.os, "open", side_effect=opened):
            result = self.guarded(lambda: collect(self.project, allowed, metadata=kinds))
        self.assertTrue(result.consistent)
        self.assertEqual(tuple(o.status for o in result.observations), ("directory", "regular"))
        self.assertTrue(all(o.data is None and o._bytes_read == 0 for o in result.observations))
        reader = I.Collector(str(self.project), allowed, metadata=kinds)
        reader.read(allowed[0])
        self.assertIn("unread-required-input", codes(reader.finish()))
        result = self.scan()
        self.assertEqual(result.scopes[1].installation, "partial")
        self.assertEqual(result.scopes[1].reasons, ("manifest-missing", "local-publication-pending"))
        self.assertEqual(result.beads.state, "pending")
        self.assertEqual(result.beads.readiness, "not-assessed")

    def test_beads_unsafe_metadata_and_forbidden_engine_paths(self):
        beads = self.project / ".beads"
        beads.mkdir()
        (beads / "metadata.json").symlink_to(self.leaf)
        result = self.scan()
        self.assertEqual(result.beads.ownership, "unknown")
        self.assertEqual(result.beads.state, "unknown")
        self.assertEqual(result.beads.reasons, (
            "beads-metadata-only", "beads-evidence-unavailable", "unsafe-symlink"))
        self.assertEqual(result.scopes[1].reasons, ("beads-evidence-unavailable",))
        self.assertEqual(result.exit_code, 1)
        observed = next(p for p in result.beads.presence if p.path.endswith("/metadata.json"))
        self.assertEqual(asdict(observed), dict(path=str(beads / "metadata.json"),
                                               status="unsafe", reasons=("unsafe-symlink",)))
        for path in (".beads/embeddeddolt/db", ".beads/dolt/db", ".beads/config.yaml/child",
                     ".beads/../host", ".git/config", ".dolt/config"):
            result = self.guarded(lambda: collect(self.project, (path,), metadata={path: "file"}))
            self.assertFalse(result.consistent)
            self.assertFalse(result.observations)
        # Declaring metadata does not authorize a normal textual read.
        result = self.guarded(lambda: collect(self.project, (".beads/metadata.json",)))
        self.assertFalse(result.consistent)
        self.assertIn("unsupported-input", codes(result))

    def test_cross_stage_mutation_revokes_records_and_baselines(self):
        private = self.project / ".domestique-private"
        private.mkdir()
        manifest = private / "manifest"
        text = (f"format=1\nscope=local\nworktree_root={self.project}\n"
                f"core_root={self.session.env['DOMESTIQUE_HOME']}\ncore_api=1\nproviders=none\n")
        manifest.write_text(text)
        original = I.Collector.finish
        changed = False

        def finish(reader):
            nonlocal changed
            result = original(reader)
            if reader.scope == "project:claude" and not changed:
                manifest.write_text(text.replace("core_api=1", "core_api=99"))
                changed = True
            return result

        before = self.session.snapshot()
        with patch.object(I.Collector, "finish", new=finish):
            result = I.inspect_scan_private(I.resolve_context(self.project))
        # The sole writer is this explicit fault injection; restore the owned
        # bytes/mtime via the existing preservation fixture, not a scanner repair.
        self.assertTrue(changed)
        self.assertEqual(result.scopes[1].installation, "unknown")
        self.assertIn("inconsistent-evidence", result.scopes[1].reasons)
        self.assertEqual(result.digests, ())
        self.assertEqual((result.beads.ownership, result.beads.state), ("unknown", "unknown"))
        self.assertTrue(all(o.data is None for c in result.collections for o in c.observations))
        self.session.pristine = before
        self.session.restore(self.session.snapshot())
        self.session.assert_no_calls()

    def test_manifest_grammars_reject_ambiguity_without_arbitrary_references(self):
        core = self.session.env["DOMESTIQUE_HOME"]
        prefix = (f"format=1\nscope=local\nworktree_root={self.project}\n"
                  f"core_root={core}\ncore_api=1\nproviders=claude\n")
        key = "claude:" + PRIVATE_PATHS["project", "claude"][0]
        pair = "created=" + key + ":" + "a" * 64 + "\nbaseline=" + key + ":" + "b" * 64 + "\n"
        valid = prefix + pair
        parsed, reasons = I.private_manifest(valid, "project", str(self.project), core)
        self.assertEqual(reasons, ())
        self.assertEqual(parsed.pairs, ((key, "a" * 64, "b" * 64),))
        for mutation in (valid[:-1], valid.replace("\n", "\r\n"), valid + pair,
                         valid.replace("baseline=", "unknown="),
                         valid.replace("providers=claude", "providers=none"),
                         valid.replace(key, "claude:../" + F.SECRET),
                         valid.replace("a" * 64, "bad"),
                         valid.replace("format=1", "format=1\nformat=1"),
                         valid + "unknown=" + F.SECRET + "\n"):
            parsed, reasons = I.private_manifest(mutation, "project", str(self.project), core)
            self.assertIsNone(parsed)
            self.assertTrue(reasons)
            self.assertNotIn(F.SECRET, repr(reasons))
        for status in ("ready", "retained"):
            # An incomplete declaration cannot borrow native readiness from a
            # status field, directory presence, version, or generated sentinel.
            declaration, problem = I.private_beads_declaration(
                ["beads_path=.beads", "beads_status=" + status])
            self.assertEqual((declaration, problem), ((), "beads-schema-unsupported"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
