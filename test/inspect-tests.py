"""hq-ln2.2-.7: collection, scanners, comparison and complete public CLI matrix.

One qualified fixture session (six offline installer calls), plus small owned
fault fixtures. Failures retain evidence; success removes only owned fixtures.
CLI cases run the actual script; library cases execute the extractable payload.
"""
import ast
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import FrozenInstanceError, asdict, fields, replace
from functools import lru_cache
import io
import json
import os
from pathlib import Path
import re
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


@lru_cache(maxsize=128)
def comparison_projection(oracle, *, private=False):
    """Own ALL .5 fields and reasons; expand frozen witnesses independently.

    Detection projections retain their strong stage-specific oracles. Here no
    comparison field/reason is filtered: frozen witnesses are restored, extra
    pinned native files are unchanged, and applicable reasons are cumulative.
    baseline-not-ownership applies to EVERY changed unknown-authority snapshot,
    not to inferred adoption. No directory/scenario name selects that reason.
    """
    structural = (private_detection_projection(oracle) if private else
                  legacy_detection_projection(oracle))
    providers = []
    for observed, declared in zip(structural.providers, oracle.providers):
        witnesses = {f.path: f for f in declared.files}
        files = []
        for file in observed.files:
            witness = witnesses.get(file.path)
            policy = "host-text-excluded" in file.reasons
            if witness is not None:
                file = replace(file, comparison=witness.comparison, metadata=witness.metadata,
                               instructions=witness.instructions,
                               permission_fields=witness.permission_fields,
                               reasons=tuple(sorted(set(file.reasons) | set(witness.reasons))))
            elif file.baseline.status == "valid" and file.status == "readable":
                digest = file.baseline.kind == "digest"
                plain = file.path.endswith("/openai.yaml") or policy
                file = replace(file, comparison="same",
                               metadata="unknown" if digest else
                               "not-applicable" if plain else "same",
                               instructions="unknown" if digest else "same")
            elif policy:
                file = replace(file, metadata="not-applicable")
            why = set(file.reasons)
            for field, reason in (("metadata", "metadata-changed"),
                                  ("instructions", "instructions-changed")):
                if getattr(file, field) == "different":
                    why.add(reason)
            if (file.comparison == "different" and file.baseline.kind == "snapshot" and
                    file.ownership == "unknown"):
                why.add("baseline-not-ownership")
            files.append(replace(file, reasons=tuple(sorted(why))))
        reasons = set(observed.reasons) | set(declared.reasons)
        reasons.update(r for f in files for r in f.reasons if r != "digest-only-baseline")
        providers.append(replace(observed, files=tuple(files),
                                 customization=declared.customization,
                                 reasons=tuple(sorted(reasons))))
    return replace(structural, customization=oracle.customization, providers=tuple(providers))


@lru_cache(maxsize=512)
def comparison_key(record):
    """Every dataclass field, with only file/reason ORDER normalized.

    Memoize immutable subrecords for mutation tests; duplicates and all extra
    records remain significant. This is not a selected-field projection.
    """
    if isinstance(record, tuple):
        return tuple(comparison_key(item) for item in record)
    if not hasattr(record, "__dataclass_fields__"):
        return record
    result = []
    for field in fields(record):
        value = getattr(record, field.name)
        if field.name == "reasons":
            value = tuple(sorted(value))
        elif field.name == "files":
            value = tuple(sorted(value, key=lambda f: f.path))
        result.append((field.name, comparison_key(value)))
    return tuple(result)


def assert_comparison_projection(test, actual, oracle, *, private=False):
    test.assertTrue(comparison_key(actual) ==
                    comparison_key(comparison_projection(oracle, private=private)),
                    "complete comparison record mismatch")


def adopted_comparison_oracle(oracle):
    # Additional witness, not a change to frozen .1 user-level status semantics.
    # b60feef4 lines 3206-3215 snapshot the new policy but retain the old live
    # block. Physical cohort evidence: 69f39c4 body SHA256 1496c0b3... (3029 B),
    # recorded b60feef4 body 86a12823... (4524 B). Both are legitimately compared.
    policy = F.FileEvidence(
        oracle.directory + "/CLAUDE.md", "readable",
        F.Baseline("snapshot", "valid",
                   oracle.directory + "/.claude/.domestique/base/CLAUDE.md.block"),
        "unknown", "different", "not-applicable", "different",
        reasons=("host-text-excluded", "installed-baseline", "instructions-changed",
                 "baseline-not-ownership"))
    return replace(oracle, providers=tuple(
        replace(p, files=(*p.files, policy)) if p.provider == "claude" else p
        for p in oracle.providers))


class ComparisonProjectionTests(unittest.TestCase):
    def test_payload_python39_syntax_and_stdlib_contract(self):
        tree = ast.parse(PAYLOAD, feature_version=(3, 9))
        modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        modules.update(alias.name for node in ast.walk(tree) if isinstance(node, ast.Import)
                       for alias in node.names)
        self.assertLessEqual(modules, {"sys", "dataclasses", "errno", "hashlib", "json",
                                      "os", "pathlib", "re", "selectors", "shutil", "stat",
                                      "subprocess", "time", "typing"})
        self.assertNotIn("tomllib", PAYLOAD)
        self.assertNotIn("match case", PAYLOAD)

    def test_all_now_owned_fields_reasons_and_extra_records_are_load_bearing(self):
        count = 0
        for row in F.MATRIX:
            if row.name.startswith(("cli-", "invalid-target-")):
                continue
            bound = F.bind(row.record, {"requested": "/project", "project": "/project",
                                       "home": "/home", "core": "/core",
                                       "release": "r-" + "a" * 64})
            for oracle in bound.scopes:
                if row.cohort == "adopted" and oracle.scope == "project":
                    oracle = adopted_comparison_oracle(oracle)
                private = row.cohort == "private"
                expected = comparison_projection(oracle, private=private)
                assert_comparison_projection(self, expected, oracle, private=private)
                mutations = [replace(expected, customization="wrong"),
                             replace(expected, reasons=(*expected.reasons, "invented"))]
                for pi, provider in enumerate(expected.providers):
                    altered = [replace(provider, customization="wrong"),
                               replace(provider, reasons=(*provider.reasons, "invented"))]
                    altered += [replace(provider, reasons=tuple(
                        r for r in provider.reasons if r != reason)) for reason in provider.reasons]
                    if provider.files:
                        altered.append(replace(provider, files=(*provider.files, provider.files[0])))
                    for fi, file in enumerate(provider.files):
                        changed = [replace(file, **{k: v}) for k, v in (
                            ("comparison", "wrong"), ("metadata", "wrong"),
                            ("instructions", "wrong"), ("permission_fields", ("invented",)),
                            ("ownership", "wrong"), ("status", "wrong"),
                            ("reasons", (*file.reasons, "invented")))]
                        changed += [replace(file, reasons=tuple(r for r in file.reasons if r != why))
                                    for why in file.reasons]
                        changed += [replace(file, baseline=replace(file.baseline, **{k: v}))
                                    for k, v in (("kind", "wrong"), ("status", "wrong"),
                                                 ("path", "/wrong"))]
                        altered += [replace(provider, files=tuple(
                            value if i == fi else f for i, f in enumerate(provider.files)))
                                    for value in changed]
                    mutations += [replace(expected, providers=tuple(
                        value if i == pi else p for i, p in enumerate(expected.providers)))
                                  for value in altered]
                for actual in mutations:
                    with self.assertRaises(AssertionError):
                        assert_comparison_projection(self, actual, oracle, private=private)
                    count += 1
        print(f"comparison oracle: {count} full-field/reason/extra-record mutations rejected",
              flush=True)


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

    def test_safe_public_dispatch_and_noninspection_python_dependency(self):
        self.assertEqual(SOURCE.count('\ninspect_main() {'), 1)
        result = self.guarded(lambda: subprocess.run(
            ["/bin/bash", str(F.ROOT / "domestique.sh"), "--inspect", str(self.project)],
            env=self.session.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10))
        self.assertEqual(result.returncode, 0)
        self.assertIn(b"Project-local providers and generations", result.stdout)
        self.assertFalse(result.stderr)
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


def cli_sections(test, result, code):
    """Parse stdout only: an error message is never an inspection report."""
    test.assertEqual(result.returncode, code)
    test.assertEqual(result.stderr, b"")
    text = result.stdout.decode("utf-8")
    test.assertTrue(text.startswith("Domestique inspection - "))
    test.assertTrue(text.endswith(
        f"Result: {'completed' if code == 0 else 'incomplete'}; exit={code}\n"))
    test.assertNotRegex(text, r"[\x00-\x09\x0b-\x1f\x7f]")
    _, global_text = text.split(
        "\nGlobal preview availability (NOT project-local installation)\n", 1)
    global_text, project_text = global_text.split(
        "\nProject-local providers and generations\n", 1)
    project_text, _ = project_text.split("\nAttention:\n", 1)
    return global_text, project_text


def cli_path_fields(test, output, requested, project, home):
    """Independent exact path/location witnesses; never call the renderer."""
    text = output.decode("utf-8")
    lines = text.split("\n")
    test.assertNotIn("path-sha256:", text)
    witnesses = []

    def directory(index, prefix, path):
        expected = "unavailable" if path is None else json.dumps(str(path), ensure_ascii=True)
        test.assertEqual(lines[index], prefix + expected)
        if path is not None:
            witnesses.append((index, prefix, str(path)))

    directory(1, "Requested directory: ", requested)
    directory(2, "Physical project scope: ", project)
    global_start = lines.index("Global preview availability (NOT project-local installation)")
    project_start = lines.index("Project-local providers and generations")
    attention = lines.index("Attention:")
    for kind, root, start, end in (
            ("global", home, global_start, project_start),
            ("project", project, project_start, attention)):
        if root is None:
            test.assertEqual(lines[start + 1], "  Scope unavailable; no absence conclusion.")
            continue
        directory(start + 1, "  Directory: ", root)
        paths = {p for provider in F.PROVIDERS for p in PRIVATE_PATHS[kind, provider]}
        if kind == "project":
            paths.update(p for paths in LEGACY_PATHS.values() for p in paths)
            paths.update(("CLAUDE.md", "CLAUDE.local.md", "AGENTS.md", "AGENTS.override.md",
                          ".github/copilot-instructions.md"))
        anchored = {"<" + kind + ">/" + p: p for p in paths}
        for index in range(start + 2, end):
            if not lines[index].startswith("    File: "):
                continue
            path, offset = json.JSONDecoder().raw_decode(lines[index][10:])
            test.assertIn(path, anchored)
            test.assertEqual(lines[index][10:10 + offset], json.dumps(path, ensure_ascii=True))
            test.assertTrue(lines[index][10 + offset:].startswith("; status="))
            # Every anchor identifies an actual fixture leaf (or its missing
            # location), under the independently asserted readable scope root.
            absolute = Path(root) / anchored[path]
            test.assertEqual(str(absolute), str(root) + "/" + anchored[path])
            if "; status=readable;" in lines[index]:
                test.assertTrue(absolute.is_file())
            witnesses.append((index, "    File: ", path))
    return tuple(witnesses)


CLI_MISUSE_STDERR = {
    **{name: b"domestique inspect: conflicts with installation/removal options\n"
       for name in ("cli-conflicting-install", "cli-conflicting-local",
                    "cli-conflicting-beads", "cli-conflicting-uninstall")},
    "cli-extra-target": b"domestique inspect: requires at most one nonempty target\n",
    "cli-unknown-option": b"domestique inspect: invalid option; use --inspect [TARGET]\n",
}


def matrix_cli_scopes(case, expected):
    scopes = []
    for scope in expected.scopes:
        if case.scenario.cohort == "adopted" and scope.scope == "project":
            scope = adopted_comparison_oracle(scope)
        scopes.append(comparison_projection(scope, private=case.scenario.cohort == "private"))
    return tuple(scopes)


def cli_scope_lines(scope):
    """Public grammar expected from independent complete .1/.3/.4/.5 records."""
    def reasons(values):
        return ", ".join(sorted(values)) or "none"

    def states(record):
        return "; ".join(key + "=" + getattr(record, key)
                         for key in ("installation", "mode", "customization"))

    lines = ["  Directory: " + json.dumps(scope.directory),
             "  Summary: " + states(scope), "  Reasons: " + reasons(scope.reasons)]
    for provider in scope.providers:
        generations = sorted(g.generation for g in provider.generations) or ["none"]
        lines.extend("  Provider: " + provider.provider + "; generation=" + g +
                     "; " + states(provider) +
                     (" (combined provider state)" if len(generations) > 1 else "")
                     for g in generations)
        lines.append("    Reasons: " + reasons(provider.reasons))
        for file in sorted(provider.files, key=lambda f: f.path):
            path = "<" + scope.scope + ">" + file.path[len(scope.directory):]
            lines.append("    File: " + json.dumps(path) + "; status=" + file.status +
                         "; baseline=" + file.baseline.kind + "/" + file.baseline.status +
                         "; comparison=" + file.comparison + "; metadata=" + file.metadata +
                         "; instructions=" + file.instructions + "; permission-fields=" +
                         (",".join(file.permission_fields) or "none"))
            lines.append("      Reasons: " + reasons(file.reasons))
    return lines


def matrix_cli_environment(case, expected):
    private = case.scenario.cohort == "private"
    core_status = ("partial" if case.scenario.mutation == "core" else
                   "available" if private else "absent")
    core_reasons = (("core-content-edited", "core-selector-corrupt")
                    if case.scenario.mutation == "core" else () if private else ("core-missing",))
    attention = {("core", reason) for reason in core_reasons}
    if expected.context == "invalid-target":
        attention.add(("project", "invalid-target"))
    if private and case.scenario.mutation in ("missing-manifest", "corrupt-manifest"):
        attention.add(("project", "manifest-" + case.scenario.mutation.split("-")[0]))
    if case.scenario.mutation == "beads":
        attention.add(("project", "synthetic-beads-metadata-only"))
    fault = {"corrupt-base": "invalid-encoding", "invalid-encoding": "invalid-encoding",
             "oversized": "input-too-large", "unreadable": "unreadable-file"}
    fault.update({kind: "unsafe-" + kind
                  for kind in ("symlink", "hardlink", "directory", "fifo", "socket")})
    if case.scenario.mutation in fault:
        attention.add(("inspection", fault[case.scenario.mutation]))
    return core_status, core_reasons, attention


def assert_matrix_cli(test, case, result, expected):
    if expected.context == "cli-misuse":
        test.assertEqual((expected.exit_code, expected.scopes), (2, ()))
        test.assertEqual((result.returncode, result.stdout, result.stderr),
                         (2, b"", CLI_MISUSE_STDERR[case.scenario.name]))
        return ()
    sections = cli_sections(test, result, expected.exit_code)
    text = result.stdout.decode()
    context_scope = ("unresolved" if expected.context == "invalid-target" else
                     "directory-only" if expected.context == "non-git" else "worktree")
    test.assertEqual(text.splitlines()[3],
                     "Context: " + expected.context + "; scope=" + context_scope)
    path_fields = cli_path_fields(test, result.stdout, expected.requested_directory,
                                  expected.resolved_directory, expected.scopes[0].directory)
    core_status, core_reasons, attention = matrix_cli_environment(case, expected)
    scopes = matrix_cli_scopes(case, expected)
    test.assertEqual(len(scopes), 1 if expected.context == "invalid-target" else 2)
    for index, section in enumerate(sections):
        if index == len(scopes):
            test.assertEqual(section.strip("\n"), "  Scope unavailable; no absence conclusion.")
            continue
        wanted = cli_scope_lines(scopes[index])
        if index == 0:
            wanted += ["  Core evidence: " + core_status,
                       "  Core reasons: " + (", ".join(core_reasons) or "none")]
        else:
            synthetic = case.scenario.mutation == "beads"
            wanted += ["  Beads: " + ("metadata present" if synthetic else "no metadata observed") +
                       "; database contents unopened; readiness not assessed",
                       "  Beads reasons: " + ("beads-metadata-only, synthetic-beads-metadata-only"
                                              if synthetic else "none")]
        test.assertEqual(section.strip("\n").splitlines(), wanted)
    actual_attention = text.split("\nAttention:\n", 1)[1].split("\nResult:", 1)[0].splitlines()
    test.assertEqual(actual_attention, ["  " + scope + ": " + reason
                                       for scope, reason in sorted(attention)] or ["  none"])
    return path_fields


class MatrixCLIAssemblyTests(unittest.TestCase):
    @staticmethod
    def model_case(row):
        projects = {row.cohort: Path("/owned/cohorts") / row.cohort for row in F.MATRIX}
        session = types.SimpleNamespace(
            root=Path("/owned"), projects=projects,
            env={"HOME": "/owned/home", "DOMESTIQUE_HOME": "/owned/core"},
            pristine={"global/core/active": F.Entry(
                stat.S_IFREG | 0o600, 0, (1, 2, 1), b"release=r-" + b"a" * 64 + b"\n")})
        case = F.Case(session, row)
        if row.record.context == "invalid-target":
            case.requested = case.project / "invalid target"
        elif row.record.context == "git-subdirectory":
            case.requested = case.project / "sub/deeper"
        return case

    def test_every_frozen_row_has_executable_spec_and_independent_complete_oracle(self):
        seen = []
        misuse = []
        for row in F.MATRIX:
            with self.subTest(scenario=row.name):
                case = self.model_case(row)
                argv, cwd, expected = case.cli_invocation()
                self.assertEqual(argv[:2], ("/bin/bash", str(F.ROOT / "domestique.sh")))
                self.assertEqual(argv[2:], F.bind(row.argv, {
                    "project": str(case.project), "requested": str(case.requested)}))
                self.assertEqual(expected, F.bind(row.record, {
                    "project": str(case.project), "requested": str(case.requested),
                    "home": case.env["HOME"], "core": case.env["DOMESTIQUE_HOME"],
                    "release": "r-" + "a" * 64}))
                invalid = row.record.context in ("invalid-target", "cli-misuse")
                self.assertEqual(cwd, case.project if invalid else case.requested)
                if row.record.context == "cli-misuse":
                    misuse.append(row.name)
                    good = subprocess.CompletedProcess(argv, 2, b"", CLI_MISUSE_STDERR[row.name])
                    self.assertEqual(assert_matrix_cli(self, case, good, expected), ())
                    with self.assertRaises(AssertionError):
                        assert_matrix_cli(self, case, subprocess.CompletedProcess(
                            argv, 0, good.stdout, good.stderr), expected)
                else:
                    scopes = matrix_cli_scopes(case, expected)
                    self.assertEqual(len(scopes), len(expected.scopes))
                    for actual, frozen in zip(scopes, expected.scopes):
                        self.assertEqual(tuple(p.provider for p in actual.providers), F.PROVIDERS)
                        self.assertEqual(actual.installation, frozen.installation)
                        lines = cli_scope_lines(actual)
                        self.assertEqual(sum(line.startswith("    File: ") for line in lines),
                                         sum(len(p.files) for p in actual.providers))
                        for p, witness in zip(actual.providers, frozen.providers):
                            self.assertEqual(p.installation, witness.installation)
                            files = {f.path: f for f in p.files}
                            for file in witness.files:
                                observed = files[file.path]
                                for key in ("status", "baseline", "comparison", "metadata",
                                            "instructions", "permission_fields", "ownership"):
                                    self.assertEqual(getattr(observed, key), getattr(file, key))
                                self.assertLessEqual(set(file.reasons), set(observed.reasons))
                seen.append(row.name)
        self.assertEqual(seen, [row.name for row in F.MATRIX])
        self.assertEqual(set(misuse), set(CLI_MISUSE_STDERR))

    def test_public_oracle_rejects_extra_records_reasons_fields_and_wrong_status(self):
        # Renderer-only synthetic records, never counted as completed CLI cases.
        count = 0
        for row in F.MATRIX:
            with self.subTest(scenario=row.name):
                case = self.model_case(row)
                argv, _, expected = case.cli_invocation()
                if expected.context == "cli-misuse":
                    text, err = "", CLI_MISUSE_STDERR[row.name]
                else:
                    status, reasons, attention = matrix_cli_environment(case, expected)
                    synthetic = row.mutation == "beads"
                    scan = types.SimpleNamespace(
                        scopes=matrix_cli_scopes(case, expected),
                        core=types.SimpleNamespace(status=status, reasons=reasons),
                        beads=(None if expected.resolved_directory is None else
                               types.SimpleNamespace(
                                   presence=(types.SimpleNamespace(
                                       status="directory" if synthetic else "missing"),),
                                   reasons=("beads-metadata-only", "synthetic-beads-metadata-only")
                                   if synthetic else ())),
                        diagnostics=tuple(I.Diagnostic(scope, why) for scope, why in attention),
                        exit_code=expected.exit_code)
                    context = I.Context(expected.requested_directory, expected.resolved_directory,
                                        expected.context, "unresolved" if
                                        expected.resolved_directory is None else "directory-only"
                                        if expected.context == "non-git" else "worktree")
                    text, err = I.inspect_render(context, scan), b""
                good = subprocess.CompletedProcess(argv, expected.exit_code, text.encode(), err)
                with patch.object(Path, "is_file", return_value=True):
                    assert_matrix_cli(self, case, good, expected)
                    with self.assertRaises(AssertionError):
                        assert_matrix_cli(self, case, subprocess.CompletedProcess(
                            argv, (expected.exit_code + 1) % 3, good.stdout, err), expected)
                    count += 1
                    if expected.context == "cli-misuse":
                        continue
                    provider = next(line for line in text.splitlines()
                                    if line.startswith("  Provider: "))
                    damaged = [text.replace(provider, provider + "\n" + provider, 1),
                               text.replace("    Reasons: ", "    Reasons: invented, ", 1),
                               text.replace("  Reasons: ", "  Reasons: invented, ", 1)]
                    files = [line for line in text.splitlines() if line.startswith("    File: ")]
                    if files:
                        damaged += [text.replace(files[0], files[0] + "\n" + files[0], 1),
                                    text.replace(files[0], "", 1),
                                    text.replace("; comparison=", "; extra=wrong; comparison=", 1),
                                    text.replace("      Reasons: ", "      Reasons: invented, ", 1)]
                    for output in damaged:
                        with self.assertRaises(AssertionError):
                            assert_matrix_cli(self, case, subprocess.CompletedProcess(
                                argv, expected.exit_code, output.encode(), err), expected)
                        count += 1
        print(f"CLI matrix model: {count} result/extra-record/reason/field mutations rejected; "
              "no CLI completion evidence", flush=True)

    def test_actual_unittest_result_and_explicit_selection_control_completion(self):
        # A reporting regression only: no setup, fixture or CLI evidence is
        # manufactured. The complete synthetic lists cannot bless a selector.
        expected = F.test_inventory("inspect-tests.py")
        result = F.QualificationResult(io.StringIO(), True, 1)
        result.testsRun = len(expected)
        result.started_ids = expected.copy()
        result.successful_ids = expected.copy()
        program = types.SimpleNamespace(result=result, testNames=None, testNamePatterns=None)
        source = F.qualification_sources()
        matrix = [row.name for row in F.MATRIX]
        with patch.object(F, "COMPLETED_MATRIX", matrix), \
                patch.object(F, "COMPLETED_CLI", matrix + list(F.CLI_EXTRA_CASES)), \
                patch.object(F, "QUALIFIED_COHORTS", [{"cleaned": True}]):
            def report():
                return F.qualification_report("inspect-tests.py", program, source, time.monotonic())
            self.assertEqual(report()["coverage"], "COMPLETE_INSPECTION_SCOPE")
            for names, patterns in ((expected, None), (None, ["*"])):
                program.testNames, program.testNamePatterns = names, patterns
                self.assertEqual(report()["coverage"], "PARTIAL_INSPECTION_SCOPE")
            program.testNames = program.testNamePatterns = None
            result.successful_ids.pop()
            self.assertEqual(report()["coverage"], "INCOMPLETE_INSPECTION_SCOPE")
            result.successful_ids.append(expected[-1])
            result.skipped.append((self, "synthetic"))
            self.assertEqual(report()["coverage"], "INCOMPLETE_INSPECTION_SCOPE")
            result.skipped.clear()
            source["domestique.sh"] = "0" * 64
            self.assertEqual(report()["coverage"], "INCOMPLETE_INSPECTION_SCOPE")

class CLITests(unittest.TestCase):
    # Small owned fault fixtures, NOT another cold installation cohort.
    setUp = BoundaryTests.setUp
    tearDown = BoundaryTests.tearDown

    def cli(self, args, *, env=None, script=None, cwd=None):
        before = self.session.snapshot()
        result = subprocess.run(
            ["/bin/bash", str(script or F.ROOT / "domestique.sh"), *map(str, args)],
            cwd=cwd or self.project, env=env or self.session.env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        self.assertEqual(before, self.session.snapshot(), "owned state changed")
        self.session.assert_no_calls()
        if result.stdout.startswith(b"Domestique inspection - "):
            target = next((str(a) for a in args if not str(a).startswith("--")),
                          str(Path(cwd or self.project).resolve()))
            resolved = Path(cwd or self.project) / target
            project = str(resolved.resolve()) if resolved.is_dir() else None
            fields = cli_path_fields(
                self, result.stdout, target, project, (env or self.session.env)["HOME"])
            case = types.SimpleNamespace(session=self.session, before=before,
                                         project=project, requested=target)
            self.session.pristine = before
            F.assert_private_output(case, result.stdout, result.stderr, path_fields=fields)
        else:
            self.assertNotIn(F.SECRET.encode(), result.stdout + result.stderr)
        return result

    def misuse(self, args, env=None):
        result = self.cli(args, env=env)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")
        self.assertTrue(result.stderr.startswith(b"domestique inspect: "))
        self.assertNotIn(F.SECRET.encode(), result.stderr)
        self.assertNotIn(b"Provider:", result.stderr)

    def test_every_explicit_conflict_both_orders_and_values(self):
        conflicts = [(flag,) for flag in (
            "--global", "--local", "--platform", "--dry-run", "--force", "--guest",
            "--no-guest", "--with-beads", "--state-only", "--uninstall", "--purge-beads")]
        conflicts += [("--local", str(self.project)), ("--local", ""),
                      ("--platform", "claude"), ("--platform", ""), ("--platform", F.SECRET),
                      ("--platform=",), ("--platform=all",), ("--platform=" + F.SECRET,)]
        # No interpreter is available even for errors. This also catches
        # --platform consuming --inspect as a value in the legacy parser.
        env = dict(self.session.env, PATH=str(self.root / "bin"))
        for conflict in conflicts:
            for args in (("--inspect", *conflict), (*conflict, "--inspect"),
                         (str(self.project), *conflict, "--inspect")):
                with self.subTest(args=tuple(a if F.SECRET not in a else "<private>"
                                             for a in args)):
                    self.misuse(args, env)
        self.misuse(("--platform", "--inspect", "--platform=claude"), env)
        self.misuse(("--guest", "--no-guest", "--inspect"), env)
        print(f"CLI conflicts: {len(conflicts) * 3 + 2} cases; all seven stubs guarded",
              flush=True)

    def test_malformed_arguments_and_invalid_targets(self):
        malformed = [
            ("--inspect", ""), ("", "--inspect"), ("--inspect", ".", "."),
            (".", ".", "--inspect"), ("--inspect=" + F.SECRET,), ("--inspect=",),
            ("--inspect", "--inspect"), ("--inspect", "--not-" + F.SECRET),
            ("--not-" + F.SECRET, "--inspect"), ("--inspect", "--", "."),
            ("--", "--inspect"), ("--inspect", "--", "--"), ("--inspect", "-"),
        ]
        for args in malformed:
            with self.subTest(case=malformed.index(args)):
                self.misuse(args)
        for target in (self.root / F.SECRET, self.leaf):
            result = self.cli(("--inspect", target))
            global_text, project_text = cli_sections(self, result, 1)
            self.assertIn("installation=absent", global_text)
            self.assertIn("Scope unavailable; no absence conclusion.", project_text)
            self.assertIn(b"invalid-target", result.stdout)
        print(f"CLI malformed: {len(malformed)} misuse + 2 invalid filesystem targets", flush=True)

    def test_help_wins_without_runtime_or_mutation(self):
        env = dict(self.session.env, PATH=str(self.root / "bin"))
        # Help uses the original cat dependency, not Python or preflight.
        (self.root / "bin/cat").symlink_to("/bin/cat")
        for args in (("--inspect", "--help"), ("-h", "--inspect"),
                     ("--inspect", "--global", "-h"), ("--help", "--inspect=" + F.SECRET)):
            result = self.cli(args, env=env)
            self.assertEqual(result.returncode, 0)
            self.assertFalse(result.stderr)
            self.assertIn(b"dom2 --inspect", result.stdout)
            self.assertNotIn(b"Provider:", result.stdout)

    def test_absent_default_orders_alias_and_secret_control_paths(self):
        weird = self.project / (F.SECRET + "\n\t\x1b[31mquote\"\nRequested directory: spoof")
        weird.mkdir()
        spaces = self.project / "ordinary project with spaces"
        spaces.mkdir()
        alias = self.project / "alias"
        alias.symlink_to(weird)
        count = 0
        for target in (self.project, spaces, weird, alias):
            for args in (("--inspect", target), (target, "--inspect"),
                         ("--inspect",), ("--inspect", ".")):
                result = self.cli(args, cwd=target)
                global_text, project_text = cli_sections(self, result, 0)
                self.assertIn("scope=directory-only", result.stdout.decode())
                for section in (global_text, project_text):
                    self.assertEqual(section.count("generation=none; installation=absent"), 3)
                count += 1
        for target in ("ordinary project with spaces", "./ordinary project with spaces",
                       "alias", "./alias", weird.name):
            self.cli(("--inspect", target))
            count += 1
        trailing = self.cli(("--inspect", "--"))
        cli_sections(self, trailing, 0)
        first = self.cli(("--inspect", self.project))
        second = self.cli(("--inspect", self.project))
        self.assertEqual(first.stdout, second.stdout)
        print(f"CLI readable paths: {count + 3} cwd/dot/absolute/relative/alias/control cases", flush=True)

    def test_duplicate_policy_blocks_actual_cli(self):
        block = F.BEGIN + b"\n" + F.SECRET.encode() + b"\n" + F.END + b"\n"
        (self.project / "CLAUDE.md").write_bytes(block + block)
        result = self.cli(("--inspect", self.project))
        _, project = cli_sections(self, result, 1)
        self.assertIn('File: "<project>/CLAUDE.md"; status=corrupt;', project)
        self.assertIn("multiple-policy-blocks (more than one managed block; "
                      "inspect the reported policy file)", project)
        self.assertNotIn("unrecognized-evidence", result.stdout.decode())
        self.assertNotIn(F.SECRET.encode(), result.stdout)

    def test_unrelated_legacy_native_evidence_survives_public_combination(self):
        # No installers: the existing owned fixture already has an unrelated
        # historical-name agent. Its reason must survive the preview merger.
        for leaf in (".codex/agents/implementer.toml",
                     ".github/agents/domestique-implementer.agent.md"):
            path = self.project / leaf
            path.parent.mkdir(parents=True)
            path.write_text(F.SECRET)
        result = self.cli(("--inspect", self.project))
        row = next(row for row in F.MATRIX if row.name == "unrelated-native-agents")
        case = types.SimpleNamespace(scenario=row)
        expected = F.bind(row.record, {
            "requested": str(self.project), "project": str(self.project),
            "home": self.session.env["HOME"]})
        assert_matrix_cli(self, case, result, expected)

    def test_missing_unsupported_and_unexpected_runtime_actual_script(self):
        env = dict(self.session.env, PATH=str(self.root / "bin"))
        missing = self.cli(("--inspect",), env=env)
        self.assertEqual((missing.returncode, missing.stdout, missing.stderr),
                         (1, b"", b"domestique inspect: Python 3.9+ runtime unavailable\n"))
        python = self.root / "bin/python3"
        for code in (69, 1, 126):
            python.write_text("#!/bin/sh\nprintf '%s' " + shlex.quote(F.SECRET) +
                              f" >&2\nexit {code}\n")
            python.chmod(0o700)
            result = self.cli(("--inspect",), env=env)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, b"")
            self.assertIn(b"runtime unavailable" if code == 69 else
                          b"runtime-or-collection-failure", result.stderr)
        python.unlink()
        # Fault injection in a copy of the complete current shell artifact.
        script = self.root / "sources/injected.sh"
        for injection, expected in (
                ("sys.version_info = (3, 8)\n", b"Python 3.9+ runtime unavailable"),
                (f"raise RuntimeError({F.SECRET!r})\n", b"runtime-or-collection-failure")):
            script.write_text(SOURCE.replace("import sys\n", "import sys\n" + injection, 1))
            result = self.cli(("--inspect",), script=script)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, b"")
            self.assertIn(expected, result.stderr)

    def test_original_parser_controls_without_install_or_python(self):
        baseline = self.session.source(
            "parser-baseline", "096c72f10a3b5d60d5a4afe4f4c3a6cfd38819a2")
        python = self.root / "bin/python3"
        python.write_text("#!/bin/sh\n: > " + shlex.quote(str(self.root / "calls/bd")) +
                          "\nexit 99\n")
        python.chmod(0o700)
        controls = [
            ("--dry-run",), ("--dry-run", "--"), ("--dry-run", "--", "."),
            (".", "--dry-run"), ("--local", ".", "--dry-run"),
            ("--local",), ("--local", ""), ("",), (".", "."),
            ("--platform",), ("--platform=",), ("--platform", "invalid"),
            ("--global", "."), ("--no-guest",), ("--with-beads",),
            ("--state-only",), ("--purge-beads",),
            ("--uninstall", "--with-beads"), ("--guest", "--dry-run"),
            ("--global", "--uninstall", "--dry-run"),
        ]
        controls += [("--global", "--uninstall", "--dry-run", "--platform=" + p)
                     for p in ("claude", "codex", "copilot", "both",
                               "claude-copilot", "codex-copilot", "all")]
        for args in controls:
            with self.subTest(args=args):
                before = self.cli(args, script=baseline)
                after = self.cli(args)
                self.assertEqual((after.returncode, after.stdout, after.stderr),
                                 (before.returncode, before.stdout, before.stderr))
        print(f"Original parser: {len(controls)} byte-identical result controls; no Python", flush=True)


class RendererTests(unittest.TestCase):
    def test_explicit_fields_and_known_permission_names_only(self):
        secret = F.SECRET + "\n\x1b"
        file = I.FileEvidence("/project/" + secret, "readable",
                              I.Baseline("snapshot", "valid", secret), "created-record",
                              "different", "different", "same",
                              ("tools", "model", secret), ("metadata-changed", secret))
        generations = tuple(I.GenerationEvidence(g, (secret,), secret, secret) for g in (
            "v1-snapshot-1", "private-preview-api-1"))
        provider = I.ProviderRecord("claude", generations, "mixed", "mixed", "unknown",
                                    (file,), ("multiple-generations", secret))
        project = I.ScopeRecord("project", "/project", "mixed", "mixed", "unknown",
                                (provider,))
        core = I.CoreEvidence(secret, secret, "unknown", secret, (secret,), (secret,))
        context = I.Context(secret, "/project", "non-git", "directory-only")
        # These private objects must never be traversed or serialized.
        private = object()
        scan = I.PrivateScan((project,), core, None, (I.Diagnostic(secret, secret, secret),),
                             1, private, private, context)
        text = I.inspect_render(context, scan)
        expected_file = ('    File: ' + json.dumps("/project/" + secret) +
                         '; status=readable; baseline=snapshot/valid; comparison=different; '
                         'metadata=different; instructions=same; permission-fields=tools')
        self.assertIn(expected_file, text.split("\n"))
        case = types.SimpleNamespace(
            project="/project", requested=secret, before={},
            session=types.SimpleNamespace(root=Path("/fixture"), pristine={}))
        F.assert_private_output(case, text.encode(), b"", path_fields=(
            (1, "Requested directory: ", secret),
            (text.split("\n").index(expected_file), "    File: ", "/project/" + secret)))
        self.assertNotIn("object at", text)
        self.assertNotIn("model", text)
        self.assertIn("permission-fields=tools", text)
        self.assertEqual(text.count("(combined provider state)"), 2)
        self.assertEqual(text.count("installation=mixed; mode=mixed; customization=unknown"), 3)
        self.assertIn("unrecognized-evidence", text)
        self.assertNotRegex(text, r"[\x00-\x09\x0b-\x1f\x7f]")
        self.assertEqual(text, I.inspect_render(context, scan))

    def test_report_reason_mapping_covers_engine_diagnostics(self):
        # Audit actual engine vocabulary, including rare failure branches, not
        # just fixture REASONS. Explicit exclusions are non-reason tokens or
        # propagated programming errors, not an open-ended suffix heuristic.
        engine = ast.parse(PAYLOAD.split("\nREPORT_REASONS =", 1)[0])
        literals = {n.value for n in ast.walk(engine) if isinstance(n, ast.Constant)
                    and isinstance(n.value, str)
                    and re.fullmatch(r"[a-z]+(?:-[a-z]+)+", n.value)}
        non_reasons = {
            "argument-hint", "claude-copilot", "codex-copilot", "created-files",
            "declared-owned", "declared-ready", "directory-only",
            "disable-model-invocation", "dolt-embedded-cgo", "git-root",
            "git-subdirectory", "guest-excludes", "historical-draft-copilot",
            "last-touched", "legacy-policy", "legacy-pre-snapshot",
            "legacy-scope-mismatch", "linked-worktree", "metadata-presence-only",
            "non-git", "not-applicable", "not-assessed", "private-native",
            "rev-parse", "synthetic-metadata-presence-only",
            "unsupported-comparison-input", "user-invocable",
        }
        self.assertLessEqual(non_reasons, literals)
        engine_reasons = literals - non_reasons
        self.assertLessEqual(engine_reasons, I.REPORT_REASONS)
        self.assertLessEqual(F.REASONS - {"cli-misuse"}, I.REPORT_REASONS)
        self.assertEqual(I.report_reasons((F.SECRET,)), "unrecognized-evidence")
        self.assertEqual(I.report_reasons(("future-reason\n" + F.SECRET,)),
                         "unrecognized-evidence")
        for reason in engine_reasons:
            self.assertIn(reason, I.report_reasons((reason,)))
        print(f"Renderer reasons: {len(engine_reasons)} engine literals audited; "
              f"{len(non_reasons)} explicit non-reason exclusions", flush=True)

    def test_exact_path_escaping_without_renderer_derived_expectations(self):
        for path, expected in (
                (".", '"."'), ("../ordinary project", '"../ordinary project"'),
                ("/ordinary project", '"/ordinary project"'),
                ('/space\n\t\x1b[31m"\\\r\x7f\u202e',
                 r'"/space\n\t\u001b[31m\"\\\r\u007f\u202e"')):
            with self.subTest(expected=expected):
                self.assertEqual(I.report_path(path), expected)
        self.assertEqual(I.report_path(None), "unavailable")


class PathPrivacyTests(unittest.TestCase):
    def test_exact_scoped_fields_only_never_native_payloads_or_spoofing(self):
        root = Path("/synthetic-owned-evidence")
        path = str(root / ("ordinary implementer " + F.SECRET + "\n\t\x1b[31m\""))
        native = ('---\nname: implementer\ntools: Read, Write, Edit, Bash\n---\n'
                  'You are an implementer. ' + F.SECRET)
        entries = {"project/agents/implementer.md": F.Entry(
            stat.S_IFREG | 0o600, 0, (0, 0, 1), native.encode())}
        case = types.SimpleNamespace(project=path, requested=path, before=entries,
                                     session=types.SimpleNamespace(root=root, pristine=entries))
        prefix = "Requested directory: "
        line = prefix + json.dumps(path)
        fields = ((0, prefix, path),)
        # Establish the old oracle's false positive on the legitimate field.
        with self.assertRaisesRegex(AssertionError, "private fixture value"):
            F.assert_private_output(case, (line + "\n").encode(), b"")
        F.assert_private_output(case, (line + "\n").encode(), b"", path_fields=fields)
        count = 0
        for payload in (F.SECRET, "implementer", "Read", "You are an implementer.",
                        "tools: Read, Write, Edit, Bash", "developer_instructions =",
                        native, path, json.dumps(path)):
            for stdout, stderr in (
                    (line + "\n" + payload, ""),
                    (line + "\n", payload),
                    (payload + line, ""),
                    (line + payload, ""),
                    (line + "\n" + line, "")):
                with self.assertRaises(AssertionError):
                    F.assert_private_output(case, stdout.encode(), stderr.encode(),
                                            path_fields=fields)
                count += 1
        for spoof in (
                line.replace(F.SECRET, F.SECRET + "suffix"),
                "extra " + line, prefix + path,
                line.replace("Requested directory:", "Physical project scope:")):
            with self.assertRaises(AssertionError):
                F.assert_private_output(case, spoof.encode(), b"", path_fields=fields)
            count += 1
        file_path = "<project>/agents/implementer.md"
        file_line = "    File: " + json.dumps(file_path) + "; status=readable"
        file_fields = ((0, "    File: ", file_path),)
        F.assert_private_output(case, file_line.encode(), b"", path_fields=file_fields)
        for payload in (F.SECRET, "implementer", "tools: Read"):
            with self.assertRaises(AssertionError):
                F.assert_private_output(case, (file_line + "; detail=" + payload).encode(),
                                        b"", path_fields=file_fields)
            count += 1
        print(f"Scoped path privacy: {count} payload/location/prefix/suffix negatives", flush=True)


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
        cohort = F.qualified_cohort(cls.session)
        F.QUALIFIED_COHORTS.append(cohort)
        if not cls.complete:
            print("collection fixture failed; retained:", cls.session.root, flush=True)
            return
        cls.session.clean()
        cohort["cleaned"] = True
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


    def test_y_public_cli_source_qualified_reports(self):
        type(self).complete = False
        for row in F.MATRIX:
            with self.subTest(scenario=row.name):
                case = self.session.begin(row.name)
                argv, cwd, expected = case.cli_invocation()
                if row.mutation in ("committed", "committed-metadata"):
                    status = self.session.run(
                        ["git", "-C", case.project, "status", "--porcelain"],
                        env=case.env, operation="command")
                    self.assertEqual(status.stdout, b"")
                result = self.session.run(argv, cwd=cwd, env=case.env, check=False)
                path_fields = assert_matrix_cli(self, case, result, expected)
                case.accept(result.stdout, result.stderr, path_fields=path_fields)
                F.COMPLETED_MATRIX.append(row.name)
                F.COMPLETED_CLI.append(row.name)
                print("CLI source-qualified:", row.name, flush=True)
            if self.session.active is not None:
                return
        # An independently damaged global scope must not hide legacy project
        # evidence; poison references/paths never become report values.
        for kind in ("invalid-core", "corrupt-global", "missing-core"):
            case = self.session.begin("v1-normal-all-including-draft-copilot")
            if kind == "invalid-core":
                case.env["DOMESTIQUE_HOME"] = "relative/" + F.SECRET + "\x1b"
            elif kind == "corrupt-global":
                case.env.update(HOME=self.session.env["HOME"],
                                DOMESTIQUE_HOME=self.session.env["DOMESTIQUE_HOME"])
                manifest = Path(case.env["DOMESTIQUE_HOME"]) / "state/global-manifest"
                manifest.write_text("core_root=/" + F.SECRET + "\n")
            # missing-core is already the isolated historical scope.
            case.before = self.session.snapshot()
            result = self.session.run(
                ["/bin/bash", F.ROOT / "domestique.sh", case.project, "--inspect"],
                cwd=case.project, env=case.env, check=False)
            _, project = cli_sections(self, result, 0 if kind == "missing-core" else 1)
            self.assertIn("installation=installed; mode=normal; customization=unchanged", project)
            self.assertEqual(project.count("generation="), 3)
            path_fields = cli_path_fields(
                self, result.stdout, str(case.project), str(case.project), case.env["HOME"])
            case.accept(result.stdout, result.stderr, path_fields=path_fields)
            F.COMPLETED_CLI.append("independent-" + kind)
            print("CLI source-qualified:", "independent-" + kind, flush=True)
            print("CLI independent project:", kind, flush=True)
        for kind in ("legacy", "private"):
            case = self.session.begin("private-global-and-local" if kind == "private" else
                                      "v1-normal-all-including-draft-copilot")
            manifest = case.project / (".domestique-private/manifest" if kind == "private"
                                       else MANIFEST)
            original = manifest.read_text()
            anchor = (PRIVATE_PATHS["project", "claude"][0] if kind == "private" else LEAF)
            self.assertIn(anchor, original)
            manifest.write_text(original.replace(anchor, "../" + F.SECRET))
            case.before = self.session.snapshot()
            argv, cwd, expected = case.cli_invocation()
            result = self.session.run(argv, cwd=cwd, env=case.env, check=False)
            global_text, project = cli_sections(self, result, 1)
            self.assertIn("manifest-inventory-corrupt" if kind == "private" else
                          "manifest-corrupt", project)
            self.assertIn("installation=partial", project)
            self.assertIn("installation=installed" if kind == "private" else
                          "installation=absent", global_text)
            fields = cli_path_fields(self, result.stdout, expected.requested_directory,
                                     expected.resolved_directory, expected.scopes[0].directory)
            case.accept(result.stdout, result.stderr, path_fields=fields)
            name = kind + "-manifest-traversal"
            F.COMPLETED_CLI.append(name)
            print("CLI source-qualified:", name, flush=True)
        self.assertEqual(dict(self.session.counts), F.SETUP_COUNTS)
        self.assertEqual(F.COMPLETED_MATRIX, [row.name for row in F.MATRIX])
        self.assertEqual(F.COMPLETED_CLI, F.COMPLETED_MATRIX + list(F.CLI_EXTRA_CASES))
        print(f"CLI reports: {len(F.COMPLETED_CLI)} completed; "
              f"{len(F.COMPLETED_MATRIX)} named matrix cases; same six-install cohort", flush=True)
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
                compared = I.inspect_compare(result)
                complete_oracle = (adopted_comparison_oracle(oracle)
                                   if row.cohort == "adopted" else oracle)
                assert_comparison_projection(self, compared.scope, complete_oracle)
                if row.cohort == "adopted":
                    observed = {o.path: o for c in result.collections for o in c.observations}
                    self.assertEqual(F.hashlib.sha256(observed["CLAUDE.md"].data).hexdigest(),
                                     "1496c0b308110131921a2e7c7e36b10efbdcf411684106aa4d5f234bbab2071e")
                    self.assertEqual(F.hashlib.sha256(
                        observed[".claude/.domestique/base/CLAUDE.md.block"].data).hexdigest(),
                        "86a12823f8f46176d99196080fe624d42ba1dc30852db7cebda5cafcf027d120")
                self.assertEqual(compared.exit_code, result.exit_code)
                self.assertTrue(all(c.consistent for c in result.collections))
                self.assertNotIn("unread-required-input", codes(result))
                case.accept(json.dumps(asdict(compared.scope), ensure_ascii=True).encode(), b"")
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
        assert_comparison_projection(self, I.inspect_compare(result).scope, oracle)
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
                compared = I.inspect_compare(result)
                for actual, oracle in zip(compared.scopes, expected.scopes):
                    wanted = comparison_projection(oracle, private=True)
                    if row.mutation == "core":
                        wanted = replace(wanted, providers=tuple(
                            without_core_selection(p) for p in wanted.providers))
                    assert_detection_projection(self, actual, wanted)
                self.assertEqual(compared.exit_code, result.exit_code)
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
                self.accept_private(case, compared)
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
                        compared = I.inspect_compare(result)
                        self.assertEqual(compared.exit_code, 1)
                        self.assertEqual(compared.scopes[1].customization, "unknown")
                        self.assertTrue(all(f.comparison == "unknown"
                                            for s in compared.scopes for p in s.providers
                                            for f in p.files))
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


    def test_zzzzz_comparison_fresh_scopes_and_template_independence(self):
        type(self).complete = False
        mutations = ("template-drift", "prompt-fork", "unknown-frontmatter",
                     "stale-private-local", "stale-private-core", "digest-input-missing")
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                private = mutation.startswith(("stale-private", "digest-input"))
                case = self.session.begin("private-global-and-local" if private else
                                          "v1-normal-all-including-draft-copilot")
                with patch.dict(os.environ, case.env, clear=True):
                    context = I.resolve_context(case.requested)
                    scan = I.inspect_scan_private(context) if private else I.inspect_scan_legacy(context)
                    if mutation == "template-drift":
                        (case.project / "domestique.sh").write_text(F.SECRET + "\n")
                    elif mutation in ("prompt-fork", "unknown-frontmatter"):
                        leaf = case.project / LEAF
                        raw = leaf.read_bytes()
                        leaf.write_bytes((raw.split(b"\n---\n", 1)[0] + b"\n---\n" +
                                          F.SECRET.encode() + b"\n") if mutation == "prompt-fork"
                                         else raw.replace(b"tools:", b"unknown:"))
                    elif mutation == "stale-private-local":
                        leaf = case.project / PRIVATE_PATHS["project", "claude"][0]
                        leaf.write_bytes(leaf.read_bytes() + F.SECRET.encode())
                    elif mutation == "stale-private-core":
                        active = Path(case.env["DOMESTIQUE_HOME"]) / "active"
                        active.write_text("release=invalid\n")
                    elif mutation == "digest-input-missing":
                        scan = replace(scan, digests=())
                    if not private:
                        scan = I.inspect_scan_legacy(I.resolve_context(case.requested))
                    case.before = self.session.snapshot()
                    with patch.object(I.subprocess, "Popen", side_effect=AssertionError("execution")), \
                            patch.object(I.Path, "read_bytes", side_effect=AssertionError("raw read")), \
                            patch.object(I.Path, "read_text", side_effect=AssertionError("raw read")), \
                            patch.object(I.os, "scandir", side_effect=AssertionError("enumeration")):
                        result = I.inspect_compare(scan)
                if private:
                    project = result.scopes[1]
                    self.assertEqual(project.customization, "unknown")
                    self.assertTrue(all(f.comparison == "unknown" for p in project.providers
                                        for f in p.files))
                    if mutation == "stale-private-local":
                        assert_comparison_projection(self, result.scopes[0],
                                                     case.expected().scopes[0], private=True)
                        self.assertEqual(project.installation, "unknown")
                    elif mutation == "stale-private-core":
                        self.assertEqual(result.core.status, "unknown")
                        self.assertEqual(result.scopes[0].customization, "unknown")
                    else:
                        self.assertTrue(all("baseline-unavailable" in f.reasons
                                            for s in result.scopes for p in s.providers
                                            for f in p.files))
                    self.accept_private(case, result)
                else:
                    if mutation == "template-drift":
                        assert_comparison_projection(self, result.scope, case.expected().scopes[1])
                    else:
                        file = result.scope.providers[0].files[0]
                        self.assertEqual((file.comparison, file.metadata, file.instructions),
                                         ("different", "same", "different")
                                         if mutation == "prompt-fork" else
                                         ("different", "unknown", "unknown"))
                        self.assertEqual(file.permission_fields, ())
                    case.accept(json.dumps(asdict(result.scope), ensure_ascii=True).encode(), b"")
                print("comparison source-qualified:", mutation, flush=True)
            if self.session.active is not None:
                return
        print(f"comparison additional: {len(mutations)} cases; same six-install cohort", flush=True)
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


class ComparisonTests(unittest.TestCase):
    setUp = BoundaryTests.setUp
    tearDown = BoundaryTests.tearDown
    guarded = BoundaryTests.guarded
    write = LegacyFailureTests.write

    def evidence(self, baseline, live, *, provider="claude", policy=False):
        path = ("CLAUDE.md" if policy else ".codex/agents/implementer.toml"
                if provider == "codex" else ".github/agents/domestique-implementer.agent.md"
                if provider == "copilot" else LEAF)
        base = ".claude/.domestique/base/" + path + (".block" if policy else "")
        self.write(base, baseline)
        self.write(path, F.BEGIN + b"\n" + live + F.END + b"\n" if policy else live)
        context = I.resolve_context(self.project)
        collection = collect(self.project, (path, base), context=context)
        if policy:
            collection = I.collection_content(collection, "legacy-policy")
        absolute, reference = str(self.project / path), str(self.project / base)
        file = I.FileEvidence(absolute, collection.observations[0].status,
                              I.Baseline("snapshot", "valid", reference), "unknown",
                              reasons=("installed-baseline",) +
                              (("host-text-excluded",) if policy else ()))
        provider = I.ProviderRecord(provider, (), "installed", "normal", "unknown",
                                    (file,), ("installed-baseline",))
        scope = I.ScopeRecord("project", str(self.project), "installed", "normal", "unknown",
                              (provider,))
        return I.LegacyScan(scope, (), 0, (collection,), context)

    def compare(self, evidence):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr), \
                patch.object(I, "inspect_scan_legacy", side_effect=AssertionError("rescan")), \
                patch.object(I, "inspect_scan_private", side_effect=AssertionError("rescan")), \
                patch.object(I.Path, "read_bytes", side_effect=AssertionError("raw read")), \
                patch.object(I.Path, "read_text", side_effect=AssertionError("raw read")), \
                patch.object(I.os, "listdir", side_effect=AssertionError("enumeration")), \
                patch.object(I.subprocess, "Popen", side_effect=AssertionError("execution")):
            result = I.inspect_compare(evidence)
        self.assertEqual(stdout.getvalue() + stderr.getvalue(), "")
        self.assertNotIn(F.SECRET, repr(result))
        return result

    def test_supported_native_metadata_body_both_models_quotes_and_multiline(self):
        cases = (
            ("claude", b"---\nname: implementer\ntools: [Read, Bash]\nmodel: old\n---\nbody\n",
             ((b"[Read, Bash]", b'["Read", "Edit"]', "different", "same", ("tools",)),
              (b"body", b"fork", "same", "different", ()),
              (b"model: old", b"model: new", "different", "same", ()))),
            ("copilot", b"---\nname: 'agent'\ndescription: |\n  one\n  two\ntools: ['read']\n"
             b"---\nbody\n",
             ((b"one", b"changed", "different", "same", ()),
              (b"['read']", b"['edit']", "different", "same", ("tools",)),
              (b"'agent'", b"'agent''s name'", "different", "same", ()))),
            ("codex", b'name = "agent"\nmodel = "old"\nsandbox_mode = "workspace-write"\n'
             b'description = """multi\nline \\"quoted\\""""\n'
             b'developer_instructions = """\nbody\n"""\n',
             ((b"workspace-write", b"read-only", "different", "same", ("sandbox_mode",)),
              (b'body', b'fork', "same", "different", ()),
              (b'model = "old"', b'model = "new"', "different", "same", ()),
              (b'line ', b'new line ', "different", "same", ()))),
        )
        count = 0
        for provider, base, mutations in cases:
            for old, new, metadata, instructions, fields in (
                    (b"absent", b"absent", "same", "same", ()), *mutations):
                for body_change in (False, True):
                    with self.subTest(provider=provider, mutation=count):
                        live = base.replace(old, new)
                        if body_change:
                            live = live.replace(b"body", F.SECRET.encode())
                        evidence = self.evidence(base, live, provider=provider)
                        before = self.session.snapshot()
                        result = self.compare(evidence)
                        file = result.scope.providers[0].files[0]
                        body = "different" if body_change else instructions
                        same = live == base
                        reasons = {"installed-baseline"}
                        if not same:
                            reasons.add("baseline-not-ownership")
                        if metadata == "different":
                            reasons.add("metadata-changed")
                        if body == "different":
                            reasons.add("instructions-changed")
                        wanted = replace(evidence.scope.providers[0].files[0],
                                         comparison="same" if same else "different",
                                         metadata=metadata, instructions=body,
                                         permission_fields=fields, reasons=tuple(sorted(reasons)))
                        self.assertEqual(replace(file, reasons=tuple(sorted(file.reasons))), wanted)
                        self.assertEqual(result.scope.customization,
                                         "unchanged" if same else "customized")
                        self.assertEqual(before, self.session.snapshot())
                        count += 1
        print(f"comparison native subset: {count} exact metadata/body/permission cases", flush=True)

    def test_unsupported_syntax_never_claims_unchanged_instructions_or_fields(self):
        yaml = b"---\nname: agent\ntools: [Read]\n---\nbody\n"
        toml = b'name = "agent"\nsandbox_mode = "read-only"\ndeveloper_instructions = """body"""\n'
        cases = [
            ("claude", yaml, yaml.replace(b"[Read]", value)) for value in (
                b"&anchor [Read]", b"[*alias]", b"{nested: value}", b'"unclosed',
                b'["Read"', b'"multi\nline"', b"|\n  first\n second", b"!tag value",
                b"- invalid sequence", b"? invalid mapping")]
        cases += [("claude", yaml, live) for live in (
            yaml.replace(b"tools:", b"unknown:"),
            yaml.replace(b"name: agent", b"name: agent\nname: duplicate"),
            yaml.replace(b"---\nbody", b"--\nbody"),
            b"entire prompt fork " + F.SECRET.encode(),
            yaml.replace(b"tools:", b" tools:"))]
        cases += [("codex", toml, live) for live in (
            toml.replace(b"sandbox_mode", b"unknown"),
            toml.replace(b'"""body"""', b'"""unterminated'),
            toml.replace(b'"""body"""', b'"""body""""'),
            toml + b"[sandbox_workspace_write]\nnetwork_access = true\n",
            toml.replace(b'name = "agent"', b'name = "agent"\nname = "duplicate"'),
            toml.replace(b'"""body"""', b'"""bad\\qescape"""'))]
        for index, (provider, base, live) in enumerate(cases):
            with self.subTest(case=index):
                result = self.compare(self.evidence(base, live, provider=provider))
                file = result.scope.providers[0].files[0]
                self.assertEqual((file.comparison, file.metadata, file.instructions,
                                  file.permission_fields), ("different", "unknown", "unknown", ()))
                self.assertEqual(set(file.reasons), {"installed-baseline", "unsupported-metadata",
                                                    "baseline-not-ownership"})
        print(f"comparison conservative syntax: {len(cases)} cases", flush=True)

    def test_comments_crlf_and_managed_policy_body_only(self):
        base = b"---\nname: agent\ntools: [Read] # comment\n---\nbody\n"
        for live, metadata, reasons in (
            (base.replace(b"comment", b"changed"), "different", {"metadata-changed"}),
            (base.replace(b"\n", b"\r\n"), "same", {"crlf-difference"})):
            result = self.compare(self.evidence(base, live))
            file = result.scope.providers[0].files[0]
            self.assertEqual((file.metadata, file.instructions, file.permission_fields),
                             (metadata, "same", ()))
            self.assertEqual(set(file.reasons), reasons | {
                "installed-baseline", "baseline-not-ownership"})
        evidence = self.evidence(b"owned\n", b"owned\n", policy=True)
        self.write("CLAUDE.md", F.SECRET.encode() + b"\n" + F.BEGIN + b"\nowned\n" +
                   F.END + b"\n" + F.SECRET.encode())
        evidence = replace(evidence, collections=(I.collection_content(
            collect(self.project, ("CLAUDE.md", ".claude/.domestique/base/CLAUDE.md.block"),
                    context=I.resolve_context(self.project)), "legacy-policy"),),
                           _context=I.resolve_context(self.project))
        result = self.compare(evidence)
        file = result.scope.providers[0].files[0]
        self.assertEqual((file.comparison, file.metadata, file.instructions),
                         ("same", "not-applicable", "same"))
        self.assertNotIn(F.SECRET.encode(), evidence.collections[0].observations[0].data)

    def test_pinned_native_literal_characters_and_comment_context(self):
        source = self.session.source("comment-syntax", F.HISTORICAL_PIN).read_bytes()
        self.assertEqual(F.hashlib.sha256(source).hexdigest(),
                         "2a4fc602e8b8991e5e7d52663993384d7f2ba3bfed6c58aced5cad61195d22a8")
        pinned = (
            ("claude", "emit_implementer",
             "d50fdb9a7bec1d457ea21547038985a46965b02e0b71416fde6969ccfb1e9e8c"),
            ("copilot", "emit_copilot_implementer",
             "75aa888490638d10c4ed482e0be6efe517c344a6a3eac296719785c179486dea"),
            ("codex", "emit_codex_implementer",
             "ad16242a1e34631e728729ad9b4a7da37f02ead712d4b989028b4ceca59332e7"),
        )
        malformed_count, supported_count = 0, 0
        secret = F.SECRET.encode()
        for provider, emitter, digest in pinned:
            anchor = (emitter + "() { cat <<'DOM_EOF'\n").encode()
            self.assertEqual(source.count(anchor), 1)
            base = source.split(anchor, 1)[1].split(b"\nDOM_EOF\n", 1)[0] + b"\n"
            self.assertEqual(F.hashlib.sha256(base).hexdigest(), digest)
            toml = provider == "codex"
            permission = "sandbox_mode" if toml else "tools"

            def field(raw, key, line):
                result, count = F.re.subn(rb"(?m)^" + key.encode() + rb"[:= ].*$",
                                          lambda match: line, raw)
                self.assertEqual(count, 1, "pinned metadata field anchor")
                return result

            changed = field(base, permission, b'sandbox_mode = "read-only"' if toml
                            else b"tools: ['" + secret + b"']")
            self.assertTrue(changed != base, "source-qualified permission witness")
            invalid, positive = [], []
            controls = (0, 1, 8, 11, 12, 14, 31, 127)
            if not toml:
                controls += (0x80, 0x84, 0x86, 0x9f, 0xfffe, 0xffff)
            for point in controls:
                value = secret + chr(point).encode() + b"suffix"
                if toml:
                    invalid.extend((
                        b"# " + value + b"\n" + changed,
                        field(changed, permission, b'sandbox_mode = "read-only" # ' + value),
                        field(changed, "name", b'name = "' + value + b'"'),
                        field(changed, "description", b'description = """\n' + value + b'\n"""'),
                        changed + b"# " + value + b"\n",
                    ))
                else:
                    invalid.extend((
                        changed.replace(b"---\n", b"---\n# " + value + b"\n", 1),
                        field(changed, "tools", b"tools: Read # " + value),
                        field(changed, "tools", b"tools: 'Read' # " + value),
                        field(changed, "tools", b"tools: ['Read'] # " + value),
                        field(changed, "description", b"description: | # " + value + b"\n  text"),
                        field(changed, "description", b"description: |\n  " + value),
                        field(changed, "name", b"name: " + value),
                        field(changed, "name", b'name: "' + value + b'"'),
                    ))
            if toml:
                for comment in (b"# " + secret, b"\t# " + secret,
                                "# \t\u0080\u0085\u009f\u00a0\u2028\U0001f642".encode()):
                    positive.extend((
                        comment + b"\n" + changed,
                        field(changed, permission, b'sandbox_mode = "read-only"' + comment),
                        changed + comment + b"\n",
                    ))
                for value in (b'"quoted#hash"', b"'literal#hash'",
                              b'"escaped\\u0000\\u001f\\t\\n\\"#hash"',
                              b'"""multiline\n# string content\n"""'):
                    positive.append(field(changed, "description", b"description = " + value))
            else:
                for value in (b"'Read'#comment", b"['Read']#comment",
                              b'"Read"#comment', b"|#comment\n  text",
                              "'Read'\u00a0#comment".encode(),
                              "['Read']\u0085#comment".encode()):
                    invalid.append(field(changed, "tools", b"tools: " + value))
                invalid.extend((
                    field(changed, "tools", b"tools:['Read']"),
                    field(changed, "name", b'name:"agent"'),
                    field(changed, "name", b"name:#comment"),
                    changed.replace(b"---\n", "---\n\u00a0# comment\n".encode(), 1),
                ))
                for comment in (b" # " + secret, b"\t# " + secret,
                                " # \t\u0085\u00a0\u2028\U0001f642".encode()):
                    positive.extend((
                        changed.replace(b"---\n", b"---\n" + comment + b"\n", 1),
                        field(changed, "name", b"name: plain" + comment),
                        field(changed, "name", b"name: 'quoted#hash'" + comment),
                        field(changed, "description", b"description: [one, 'two#hash']" + comment),
                        field(changed, "description", b"description: |" + comment + b"\n  text"),
                    ))
                for value in (b"plain#hash", b'"quoted#hash"', b"'quoted#hash'",
                              b'"escaped\\u0000\\u001f\\t\\n\\"#hash"',
                              "'printable\u0085\u00a0\u2028\U0001f642'".encode(),
                              b"|\n  # block content\n  text"):
                    positive.append(field(changed, "description", b"description: " + value))
            for index, malformed in enumerate(invalid):
                for baseline_bad in (False, True):
                    with self.subTest(provider=provider, malformed=index, baseline_bad=baseline_bad):
                        evidence = self.evidence(malformed if baseline_bad else base,
                                                 base if baseline_bad else malformed,
                                                 provider=provider)
                        result = self.guarded(lambda: self.compare(evidence))
                        expected = replace(evidence.scope.providers[0].files[0],
                                           comparison="different", reasons=(
                                               "installed-baseline", "unsupported-metadata",
                                               "baseline-not-ownership"))
                        self.assertEqual(result.scope.providers[0].files[0], expected)
                        self.assertEqual(result.scope.customization, "customized")
                        malformed_count += 1
            for index, live in enumerate((base, changed, *positive)):
                for crlf in (False, True):
                    with self.subTest(provider=provider, supported=index, crlf=crlf):
                        live_bytes = live.replace(b"\n", b"\r\n") if crlf else live
                        evidence = self.evidence(base, live_bytes, provider=provider)
                        result = self.guarded(lambda: self.compare(evidence))
                        reasons = ["installed-baseline"]
                        if index:
                            reasons.append("metadata-changed")
                        elif crlf:
                            reasons.append("crlf-difference")
                        if index or crlf:
                            reasons.append("baseline-not-ownership")
                        expected = replace(
                            evidence.scope.providers[0].files[0],
                            comparison="different" if index or crlf else "same",
                            metadata="different" if index else "same", instructions="same",
                            permission_fields=(permission,) if index else (),
                            reasons=tuple(reasons))
                        self.assertEqual(result.scope.providers[0].files[0], expected)
                        supported_count += 1
            print(f"pinned comment syntax: {provider} baseline SHA256 {digest}", flush=True)
        print(f"pinned comment syntax: {malformed_count} exact conservative cases; "
              f"{supported_count} supported cases; all seven stubs/preservation/privacy guarded; "
              f"owned root {self.root}", flush=True)

    def test_missing_revoked_incomplete_and_stale_evidence_cannot_be_pristine(self):
        base = b"---\nname: agent\ntools: [Read]\n---\nbody\n"
        for mutation in ("edit", "identity", "missing", "baseline", "manifest-proof",
                         "revoked", "unsealed", "incomplete", "absent-collections"):
            with self.subTest(mutation=mutation):
                evidence = self.evidence(base, base)
                c = evidence.collections[0]
                if mutation == "edit":
                    self.write(LEAF, base + b"fork\n")
                elif mutation == "identity":
                    self.write(LEAF + ".replacement", base)
                    os.replace(self.project / (LEAF + ".replacement"), self.project / LEAF)
                elif mutation == "missing":
                    (self.project / LEAF).unlink()
                elif mutation == "baseline":
                    self.write(BASE, base + b"baseline drift\n")
                elif mutation == "manifest-proof":
                    self.write("CLAUDE.md", "new root membership")
                elif mutation == "revoked":
                    c = replace(c, consistent=False)
                elif mutation == "unsealed":
                    c = replace(c, _declaration=())
                elif mutation == "incomplete":
                    c = replace(c, observations=c.observations[:1])
                evidence = replace(evidence, collections=() if mutation == "absent-collections"
                                   else (c,))
                result = self.compare(evidence)
                self.assertEqual((result.exit_code, result.scope.installation,
                                  result.scope.customization), (1, "unknown", "unknown"))
                self.assertEqual(result.scope.providers[0].files[0].comparison, "unknown")
                self.assertIn("inconsistent-evidence", codes(result))
        with self.assertRaisesRegex(TypeError, "^unsupported-comparison-input$"):
            I.inspect_compare(None)

    def test_omitted_generation_collection_is_not_pristine(self):
        base = b"---\nname: agent\ntools: [Read]\n---\nbody\n"
        evidence = self.evidence(base, base)
        receipt = self.project / MANIFEST
        self.write(MANIFEST, "recorded generation\n")
        context = I.resolve_context(self.project)
        native = collect(self.project, (LEAF, BASE), context=context)
        generation = I.GenerationEvidence("v1-snapshot-1", (str(receipt),), "0.1.0", "abc123")
        provider = replace(evidence.scope.providers[0], generations=(generation,))
        evidence = replace(evidence, scope=replace(evidence.scope, providers=(provider,)),
                           collections=(native,), _context=context)
        result = self.compare(evidence)
        self.assertEqual((result.exit_code, result.scope.customization), (1, "unknown"))
        self.assertEqual(result.scope.providers[0].files[0].comparison, "unknown")


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
        parsed, reasons = I.private_manifest(
            valid.replace(key, "claude:../" + F.SECRET), "project", str(self.project), core)
        self.assertIsNone(parsed)
        self.assertEqual(reasons, ("manifest-inventory-corrupt",))
        # Small synthetic fault fixture, not a qualified install/matrix row.
        # Exercise the real CLI and Case.accept privacy/state/stub gates without
        # requiring the complete shared six-install cohort for this regression.
        self.session.projects = {"private": self.project}
        self.session.pristine = self.session.snapshot()
        case = self.session.begin("private-global-and-local")
        LegacyFailureTests.write(
            self, ".domestique-private/manifest",
            valid.replace(key, "claude:../" + F.SECRET))
        case.before = self.session.snapshot()
        result = self.session.run(
            ["/bin/bash", F.ROOT / "domestique.sh", "--inspect", self.project],
            cwd=self.project, env=case.env, check=False)
        global_text, project = cli_sections(self, result, 1)
        self.assertIn("manifest-inventory-corrupt", project)
        self.assertIn("installation=partial", project)
        self.assertIn("installation=absent", global_text)
        path_fields = cli_path_fields(
            self, result.stdout, str(self.project), str(self.project), case.env["HOME"])
        case.accept(result.stdout, result.stderr, path_fields=path_fields)
        self.assertIsNone(self.session.active)
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
    sys.exit(F.qualification_main("inspect-tests.py", verbosity=2))
