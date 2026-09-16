"""Source-qualified, OFFLINE inspection fixtures; not an inspector.

The immutable matrix is an independent *projection* oracle: scopes/providers
are exact, files are required witnesses (an inspector may report more files).
Tokens in paths/ref are bound by Case.expected(), never by parsing an inspector
or comparing against today's emitters. No public JSON API is implied.

Six cold installer calls per session: historical normal/all, guest/both,
pre-snapshot, real adoption of that older tree, current global/all, local/all.
Other cases mutate/reuse owned trees. No native database is initialized,
copied, or treated as readiness. Failures retain the owned session as evidence.
Python 3.9+ stdlib only. Run test/inspect-fixture-tests.py for the complete scope.
"""
import ast
from collections import Counter
from dataclasses import dataclass, replace
from functools import wraps
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
from typing import Literal, Optional, Tuple
import unittest
import importlib.util


ROOT = Path(__file__).resolve().parent.parent
# This module is also loaded by absolute path in isolated acceptance probes,
# where test/ is intentionally not added to sys.path. Load the exact helper;
# never resolve an ambient/foreign module or alter the caller's import path.
_preview_spec = importlib.util.spec_from_file_location(
    "_domestique_retained_preview", ROOT / "test/preview_fixture.py")
preview_fixture = importlib.util.module_from_spec(_preview_spec)
_preview_spec.loader.exec_module(preview_fixture)
HISTORICAL_PIN = "b60feef4d0d41b8d99b7afec68dd5e6ef648b027"
PRE_SNAPSHOT_PIN = "69f39c468b65335d05260b8c5bc4653a7cf3c9f3"
FORBIDDEN = ("bd", "beads", "claude", "codex", "copilot", "curl", "wget")
PROVIDERS = ("claude", "codex", "copilot")
MAX_INPUT_BYTES = 1024 * 1024
SESSION_SECONDS = 900
COMMAND_SECONDS = 120
INSTALL_SECONDS = 300
INSTALL_PHASES = ("historical_normal", "historical_guest", "pre_snapshot",
                  "historical_adoption", "current_global", "current_local")
INSTALL_TIMING_PREFIX = "INSPECTION_INSTALL_PHASE="
SECRET = "INSPECT_FIXTURE_PRIVATE_VALUE_7c193"
BEGIN = b"<!-- BEGIN domestique (managed) -->"
END = b"<!-- END domestique -->"

Installation = Literal["absent", "installed", "partial", "mixed", "unknown"]
Mode = Literal["normal", "guest", "mixed", "unknown"]
Customization = Literal["unchanged", "customized", "unknown", "not-applicable"]
Comparison = Literal["same", "different", "unknown", "not-applicable"]
REASONS = frozenset((
    "no-domestique-evidence", "unrelated-native-files", "installed-baseline",
    "old-baseline-unavailable", "baseline-missing", "baseline-corrupt",
    "baseline-not-ownership", "created-record", "metadata-changed",
    "instructions-changed", "file-changed", "digest-only-baseline",
    "host-text-excluded", "mixed-provider-modes", "mixed-mode-markers",
    "partial-policy-markers", "multiple-generations", "managed-file-missing",
    "manifest-missing", "manifest-corrupt", "core-inconsistent",
    "invalid-encoding", "input-too-large", "crlf-difference",
    "unsafe-symlink", "unsafe-hardlink", "unsafe-directory", "unsafe-fifo",
    "unsafe-socket", "unreadable-file", "escaped-path", "invalid-target",
    "cli-misuse", "synthetic-beads-metadata-only", "unsupported-metadata",
))


@dataclass(frozen=True)
class Baseline:
    # A merge base/digest identifies comparison bytes, NOT creation authority.
    kind: Literal["snapshot", "digest", "none"]
    status: Literal["valid", "unavailable", "corrupt"]
    path: Optional[str] = None


@dataclass(frozen=True)
class FileEvidence:
    path: str
    status: Literal["readable", "missing", "unsafe", "unreadable", "corrupt"]
    baseline: Baseline
    ownership: Literal["unknown", "created-record"]
    comparison: Comparison
    metadata: Comparison = "unknown"
    instructions: Comparison = "unknown"
    # Field NAMES only, and only with a valid installed textual baseline and
    # supported structure. Never values, effective permissions, or native trust.
    permission_fields: Tuple[str, ...] = ()
    reasons: Tuple[str, ...] = ()


@dataclass(frozen=True)
class GenerationEvidence:
    generation: Literal["legacy-pre-snapshot", "v1-snapshot-1",
                        "historical-draft-copilot", "private-preview-api-1"]
    evidence: Tuple[str, ...]
    reported_version: Optional[str]
    reported_ref: Optional[str]


@dataclass(frozen=True)
class ProviderRecord:
    provider: str
    generations: Tuple[GenerationEvidence, ...]
    installation: Installation
    mode: Mode
    customization: Customization
    files: Tuple[FileEvidence, ...]
    reasons: Tuple[str, ...]


@dataclass(frozen=True)
class ScopeRecord:
    scope: Literal["global", "project"]
    directory: str
    installation: Installation
    mode: Mode
    customization: Customization
    providers: Tuple[ProviderRecord, ...]
    reasons: Tuple[str, ...] = ()
    beads: Literal["absent", "synthetic-metadata-presence-only"] = "absent"


@dataclass(frozen=True)
class InspectionRecord:
    requested_directory: Optional[str]
    resolved_directory: Optional[str]
    context: Literal["git-root", "git-subdirectory", "linked-worktree",
                     "non-git", "invalid-target", "cli-misuse"]
    # CLI misuse has no inspection scopes. Invalid targets still have global
    # evidence independently available; no guessed project root.
    scopes: Tuple[ScopeRecord, ...]
    result: Literal["completed", "incomplete", "misuse"]
    exit_code: Literal[0, 1, 2]
    reasons: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Preservation:
    bytes: bool = True
    modes: bool = True
    mtimes_ns: bool = True
    directory_membership: bool = True
    symlink_targets: bool = True
    no_forbidden_calls: bool = True
    no_private_output: bool = True


@dataclass(frozen=True)
class Scenario:
    name: str
    cohort: str
    mutation: str
    record: InspectionRecord
    argv: Tuple[str, ...] = ("--inspect", "{requested}")
    preservation: Preservation = Preservation()


def absent_provider(provider, reason="no-domestique-evidence"):
    return ProviderRecord(provider, (), "absent", "unknown", "not-applicable",
                          (), (reason,))


def absent_scope(scope):
    return ScopeRecord(scope, "{home}" if scope == "global" else "{project}",
                       "absent", "unknown", "not-applicable",
                       tuple(absent_provider(p) for p in PROVIDERS))


def legacy(provider, mode="normal", *, old=False):
    prefix, leaf, policy = {
        "claude": (".claude", ".claude/agents/implementer.md", "CLAUDE.md"),
        "codex": (".codex", ".codex/agents/implementer.toml", "AGENTS.md"),
        "copilot": (".github", ".github/agents/domestique-implementer.agent.md",
                    ".github/copilot-instructions.md"),
    }[provider]
    state = "{project}/" + prefix + "/.domestique"
    generation = ("legacy-pre-snapshot" if old else
                  "historical-draft-copilot" if provider == "copilot" else
                  "v1-snapshot-1")
    reason = "old-baseline-unavailable" if old else "installed-baseline"
    # Claude's historical snapshots never assert creation. Draft Copilot's
    # created-files and Codex guest-excludes can assert exact created leaves.
    ownership = ("created-record" if provider == "copilot" or
                 provider == "codex" and mode == "guest" else "unknown")
    base = Baseline("none", "unavailable") if old else Baseline(
        "snapshot", "valid", state + "/base/" + leaf)
    file = FileEvidence("{project}/" + leaf, "readable", base, ownership,
                        "unknown" if old else "same",
                        "unknown" if old else "same",
                        "unknown" if old else "same", reasons=(reason,))
    evidence = ("{project}/" + policy,) if old else (state + "/manifest",)
    return ProviderRecord(
        provider, (GenerationEvidence(generation, evidence,
                                      None if old else "0.1.0",
                                      None if old else "unknown"),),
        "installed", mode, "unknown" if old else "unchanged",
        (file,), (reason,))


def private(provider, scope):
    prefix = {"claude": ".claude", "codex": ".codex",
              "copilot": ".copilot" if scope == "global" else ".github"}[provider]
    ext = {"claude": "md", "codex": "toml", "copilot": "agent.md"}[provider]
    local = "" if scope == "global" else "-local"
    root = "{home}" if scope == "global" else "{project}"
    manifest = ("{core}/state/global-manifest" if scope == "global" else
                "{project}/.domestique-private/manifest")
    file = FileEvidence(
        f"{root}/{prefix}/agents/domestique-{provider}{local}-implementer.{ext}",
        "readable", Baseline("digest", "valid", manifest), "created-record",
        "same", reasons=("installed-baseline", "digest-only-baseline"))
    return ProviderRecord(provider, (GenerationEvidence(
        "private-preview-api-1", (manifest, "{core}/active"), None, "{release}"),),
        "installed", "normal", "unchanged", (file,), ("installed-baseline",))


def scope(providers, kind="project", **changes):
    return replace(ScopeRecord(kind, "{home}" if kind == "global" else "{project}",
                               "installed", "normal", "unchanged",
                               tuple(providers)), **changes)


NORMAL = scope([legacy(p) for p in PROVIDERS])
GUEST = scope([legacy("claude", "guest"), legacy("codex", "guest"),
               absent_provider("copilot")], mode="guest")
OLD = scope([legacy("claude", old=True), absent_provider("codex"),
             absent_provider("copilot")], customization="unknown")
PRIVATE_GLOBAL = scope([private(p, "global") for p in PROVIDERS], "global")
PRIVATE_LOCAL = scope([private(p, "project") for p in PROVIDERS])


def change_provider(original, provider="claude", *, file_changes=None, **changes):
    records = []
    for p in original.providers:
        if p.provider == provider:
            if file_changes is not None:
                p = replace(p, files=(replace(p.files[0], **file_changes), *p.files[1:]))
            p = replace(p, **changes)
        records.append(p)
    return replace(original, providers=tuple(records))


def scenario(name, cohort="normal", mutation="none", project=NORMAL, *,
             global_scope=None, context="git-root", code=0, reasons=(), argv=None):
    record = InspectionRecord(
        "{requested}", "{project}", context,
        (global_scope or absent_scope("global"), project),
        "completed" if code == 0 else "incomplete", code, reasons)
    return Scenario(name, cohort, mutation, record,
                    argv or ("--inspect", "{requested}"))


def file_case(name, mutation, reason, *, provider="claude", cohort="normal",
              original=NORMAL, code=0, installation="installed",
              customization="customized", **file_changes):
    changed = change_provider(
        original, provider, installation=installation,
        customization=customization, reasons=(reason,),
        file_changes=dict(reasons=(reason,), **file_changes))
    changed = replace(changed, installation=installation, customization=customization)
    return scenario(name, cohort, mutation, changed, code=code, reasons=(reason,),
                    global_scope=PRIVATE_GLOBAL if cohort == "private" else None)


def expected_matrix():
    """Declarations only: NEVER inspect filesystem/production to derive statuses."""
    rows = [
        scenario("absent", "empty", project=absent_scope("project"), context="non-git"),
        scenario("unrelated-native-agents", "empty", "unrelated",
                 replace(absent_scope("project"), providers=tuple(
                     absent_provider(p, "unrelated-native-files") for p in PROVIDERS)),
                 context="non-git"),
        scenario("v1-normal-all-including-draft-copilot"),
        scenario("v1-guest-claude-codex", "guest", project=GUEST),
        scenario("v1-mixed-provider-modes", "normal", "mixed-providers",
                 scope([legacy("claude"), legacy("codex", "guest"), legacy("copilot")],
                       mode="mixed", reasons=("mixed-provider-modes",)), code=1,
                 reasons=("mixed-provider-modes",)),
        scenario("pre-snapshot-no-git", "old", project=OLD, context="non-git",
                 reasons=("old-baseline-unavailable",)),
        scenario("v1-no-git", "nongit", context="non-git"),
        scenario("default-current-directory", argv=("--inspect",)),
        scenario("v1-subdirectory", mutation="subdirectory", context="git-subdirectory"),
        scenario("v1-linked-worktree", "linked", context="linked-worktree"),
        scenario("path-with-spaces", "spaces", context="non-git"),
        scenario("path-with-control-characters", "control", context="non-git",
                 reasons=("escaped-path",)),
        scenario("private-global-and-local", "private", project=PRIVATE_LOCAL,
                 global_scope=PRIVATE_GLOBAL),
        scenario("private-global-only", "private", "global-only",
                 absent_scope("project"), global_scope=PRIVATE_GLOBAL),
        scenario("private-synthetic-beads-presence", "private", "beads",
                 replace(PRIVATE_LOCAL, beads="synthetic-metadata-presence-only",
                         reasons=("synthetic-beads-metadata-only",)),
                 global_scope=PRIVATE_GLOBAL),
    ]
    mixed = change_provider(
        PRIVATE_LOCAL, generations=PRIVATE_LOCAL.providers[0].generations +
        NORMAL.providers[0].generations, installation="mixed", customization="unknown",
        files=PRIVATE_LOCAL.providers[0].files + NORMAL.providers[0].files,
        reasons=("multiple-generations",))
    rows.append(scenario("multiple-generations-one-provider", "private", "generations",
                         replace(mixed, installation="mixed", customization="unknown"),
                         global_scope=PRIVATE_GLOBAL, code=1,
                         reasons=("multiple-generations",)))
    for provider, field in (("claude", "tools"), ("codex", "sandbox_mode"),
                            ("copilot", "tools")):
        for edit in ("metadata", "body", "both"):
            reasons = (("metadata-changed", "instructions-changed") if edit == "both"
                       else ("metadata-changed" if edit == "metadata" else
                             "instructions-changed",))
            row = file_case(
                f"{provider}-{edit}-edit", f"edit:{provider}:{edit}", reasons[0],
                provider=provider, comparison="different",
                metadata="different" if edit != "body" else "same",
                instructions="different" if edit != "metadata" else "same",
                permission_fields=(field,) if edit != "body" else ())
            if edit == "both":
                p = change_provider(row.record.scopes[1], provider, reasons=reasons,
                                    file_changes={"reasons": reasons})
                row = replace(row, record=replace(row.record,
                              scopes=(row.record.scopes[0], p), reasons=reasons))
            rows.append(row)
    rows.extend([
        file_case("committed-customization", "committed", "instructions-changed",
                  comparison="different", metadata="same", instructions="different"),
        file_case("committed-permissions-customization", "committed-metadata",
                  "metadata-changed", comparison="different", metadata="different",
                  instructions="same", permission_fields=("tools",)),
        file_case("adopted-baseline-not-ownership", "none", "baseline-not-ownership",
                  cohort="adopted", original=scope(
                      [legacy("claude"), absent_provider("codex"), absent_provider("copilot")]),
                  comparison="different", metadata="same", instructions="different"),
        file_case("missing-baseline", "missing-base", "baseline-missing",
                  customization="unknown", comparison="unknown",
                  baseline=Baseline("none", "unavailable"),
                  metadata="unknown", instructions="unknown"),
        file_case("corrupt-baseline", "corrupt-base", "baseline-corrupt", code=1,
                  installation="partial", customization="unknown", comparison="unknown",
                  baseline=replace(NORMAL.providers[0].files[0].baseline, status="corrupt"),
                  metadata="unknown", instructions="unknown"),
        file_case("managed-file-missing", "missing-file", "managed-file-missing",
                  code=1, installation="partial", customization="unknown",
                  status="missing", comparison="unknown",
                  metadata="unknown", instructions="unknown"),
        file_case("crlf", "crlf", "crlf-difference", comparison="different",
                  metadata="same", instructions="same"),
        file_case("invalid-encoding", "invalid-encoding", "invalid-encoding",
                  code=1, installation="partial", customization="unknown",
                  status="corrupt", comparison="unknown", metadata="unknown",
                  instructions="unknown"),
        file_case("oversized-input", "oversized", "input-too-large", code=1,
                  installation="partial", customization="unknown", status="unreadable",
                  comparison="unknown", metadata="unknown", instructions="unknown"),
        file_case("unsupported-metadata", "unsupported-metadata", "unsupported-metadata",
                  comparison="different", metadata="unknown", instructions="unknown"),
        # Private manifests store digests, not original native field values.
        # Even though the mutation is known to us, the report cannot classify it.
        file_case("private-metadata-digest-only", "private-metadata", "file-changed",
                  cohort="private", original=PRIVATE_LOCAL, comparison="different"),
        file_case("private-body-digest-only", "private-body", "file-changed",
                  cohort="private", original=PRIVATE_LOCAL, comparison="different"),
        file_case("private-both-digest-only", "private-both", "file-changed",
                  cohort="private", original=PRIVATE_LOCAL, comparison="different"),
    ])
    policy = FileEvidence(
        "{project}/CLAUDE.md", "readable",
        Baseline("snapshot", "valid", "{project}/.claude/.domestique/base/CLAUDE.md.block"),
        "unknown", "same", "not-applicable", "same",
        reasons=("host-text-excluded",))
    host = change_provider(NORMAL, files=(*NORMAL.providers[0].files, policy))
    rows.append(scenario("host-text-outside-policy", mutation="host-text", project=host))
    for mutation, reason in (("partial-markers", "partial-policy-markers"),
                             ("mixed-markers", "mixed-mode-markers")):
        p = change_provider(
            NORMAL, installation="partial" if mutation == "partial-markers" else "mixed",
            mode="unknown" if mutation == "partial-markers" else "mixed",
            customization="unknown", reasons=(reason,),
            files=(*NORMAL.providers[0].files,
                   replace(policy, comparison="unknown", instructions="unknown",
                           status="corrupt", reasons=(reason,))))
        p = replace(p, installation=p.providers[0].installation,
                    mode=p.providers[0].mode, customization="unknown")
        rows.append(scenario(mutation, mutation=mutation, project=p, code=1,
                             reasons=(reason,)))
    for kind in ("symlink", "hardlink", "directory", "fifo", "socket", "unreadable"):
        reason = "unreadable-file" if kind == "unreadable" else "unsafe-" + kind
        rows.append(file_case(
            "unsafe-" + kind, kind, reason, code=1, installation="partial",
            customization="unknown", status="unreadable" if kind == "unreadable" else "unsafe",
            comparison="unknown", metadata="unknown", instructions="unknown"))
    for cohort, original, glob in (("normal", NORMAL, absent_scope("global")),
                                   ("private", PRIVATE_LOCAL, PRIVATE_GLOBAL)):
        for mutation, reason in (("missing-manifest", "manifest-missing"),
                                 ("corrupt-manifest", "manifest-corrupt")):
            providers = ("claude",) if cohort == "normal" else PROVIDERS
            p = original
            for provider in providers:
                prior = next(r for r in p.providers if r.provider == provider)
                generations = tuple(replace(g, evidence=(prior.files[0].path,),
                                             reported_version=None,
                                             reported_ref=None)
                                    for g in prior.generations)
                p = change_provider(p, provider, installation="partial",
                                    customization="unknown", reasons=(reason,),
                                    generations=generations,
                                    file_changes={
                                        "baseline": Baseline("none", "unavailable"),
                                        "ownership": "unknown", "comparison": "unknown",
                                        "metadata": "unknown", "instructions": "unknown",
                                        "reasons": (reason,)})
            rows.append(scenario(
                f"{cohort}-{mutation}", cohort, mutation,
                replace(p, installation="partial", customization="unknown"),
                global_scope=glob, code=1, reasons=(reason,)))
    broken_global = replace(PRIVATE_GLOBAL, installation="partial",
                            customization="unknown", reasons=("core-inconsistent",))
    rows.append(scenario("private-inconsistent-core", "private", "core",
                         PRIVATE_LOCAL, global_scope=broken_global, code=1,
                         reasons=("core-inconsistent",)))
    for kind in ("missing", "file", "symlink"):
        record = InspectionRecord("{requested}", None, "invalid-target",
                                  (absent_scope("global"),), "incomplete", 1,
                                  ("invalid-target",))
        rows.append(Scenario("invalid-target-" + kind, "empty", "target-" + kind, record))
    for name, argv in (
            ("conflicting-install", ("--inspect", "--global")),
            ("conflicting-local", ("--inspect", "--local", "{project}")),
            ("conflicting-beads", ("--inspect", "--with-beads")),
            ("conflicting-uninstall", ("--inspect", "--uninstall")),
            ("extra-target", ("--inspect", "{project}", "{project}")),
            ("unknown-option", ("--inspect", "--not-an-option"))):
        rows.append(Scenario("cli-" + name, "empty", "none",
                    InspectionRecord(None, None, "cli-misuse", (), "misuse", 2,
                                     ("cli-misuse",)), argv))
    return tuple(rows)


MATRIX = expected_matrix()
CLI_EXTRA_CASES = ("independent-invalid-core", "independent-corrupt-global",
                   "independent-missing-core", "legacy-manifest-traversal",
                   "private-manifest-traversal")
QUALIFICATION_PREFIX = "INSPECTION_QUALIFICATION="
QUALIFICATION_SUITES = {
    "inspect-tests.py": "public-cli-and-engine",
    "inspect-fixture-tests.py": "fixture-oracles-not-runtime",
}
QUALIFICATION_LIMITS = (
    "CLI inventory names the qualified cohort; supplemental controls are in unittest IDs; "
    "offline owned fixtures; no native/readiness, atime or hostile-writer atomicity proof")
SETUP_COUNTS = dict(git_init=5, worktree_add=1, historical_normal=1, historical_guest=1,
                    pre_snapshot=1, historical_adoption=1, current_global=1, current_local=1)
COMPLETED_MATRIX = []
COMPLETED_CLI = []
QUALIFIED_COHORTS = []


def test_inventory(name):
    """Static inventory only; importing a suite must never start its fixtures."""
    if name not in QUALIFICATION_SUITES:
        raise ValueError("unknown inspection qualification suite")
    tree = ast.parse((ROOT / "test" / name).read_text())
    return sorted(cls.name + "." + method.name for cls in tree.body
                  if isinstance(cls, ast.ClassDef)
                  for method in cls.body if isinstance(method, ast.FunctionDef)
                  and method.name.startswith("test_"))


def qualification_sources():
    paths = ("domestique2.sh", "update2.sh", "README.md", "test/preview_fixture.py", "test/inspect_fixture.py",
             "test/inspect-tests.py", "test/inspect-fixture-tests.py",
             "test/acceptance.py", "test/acceptance-tests.py")
    return {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths}


class QualificationResult(unittest.TextTestResult):
    """Observe the ordinary unittest result; do not replace test execution."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.started_ids = []
        self.successful_ids = []

    def startTest(self, test):
        self.started_ids.append(".".join(test.id().split(".")[-2:]))
        super().startTest(test)

    def addSuccess(self, test):
        self.successful_ids.append(".".join(test.id().split(".")[-2:]))
        super().addSuccess(test)


class QualificationRunner(unittest.TextTestRunner):
    resultclass = QualificationResult


def qualification_report(name, program, before, started):
    result = program.result
    selected = program.testNames is not None or bool(program.testNamePatterns)
    expected = test_inventory(name)
    cli = ([row.name for row in MATRIX] + list(CLI_EXTRA_CASES)
           if name == "inspect-tests.py" else [])
    sources = qualification_sources()
    complete = (not selected and result.wasSuccessful() and not result.skipped
                and not result.expectedFailures
                and result.testsRun == len(expected)
                and sorted(result.started_ids) == expected
                and sorted(result.successful_ids) == expected
                and sorted(COMPLETED_MATRIX) == sorted(row.name for row in MATRIX)
                and sorted(COMPLETED_CLI) == sorted(cli)
                and len(QUALIFIED_COHORTS) == 1
                and QUALIFIED_COHORTS[0]["cleaned"]
                and sources == before)
    return {
        "suite": name, "scope": QUALIFICATION_SUITES[name],
        "coverage": ("COMPLETE_INSPECTION_SCOPE" if complete else
                     "PARTIAL_INSPECTION_SCOPE" if selected and result.wasSuccessful()
                     else "INCOMPLETE_INSPECTION_SCOPE"),
        "explicit_selection": selected,
        "unittest": {
            "run": result.testsRun, "started": result.started_ids,
            "successful": result.successful_ids, "failures": len(result.failures),
            "errors": len(result.errors), "skips": len(result.skipped),
            "expected_failures": len(result.expectedFailures),
            "unexpected_successes": len(result.unexpectedSuccesses),
        },
        "matrix_completed": COMPLETED_MATRIX, "matrix_count": len(COMPLETED_MATRIX),
        "cli_completed": COMPLETED_CLI, "cli_count": len(COMPLETED_CLI),
        "qualified_cohorts": QUALIFIED_COHORTS,
        "source_sha256": sources, "source_unchanged": sources == before,
        "runtime": {"python": platform.python_version(), "system": sys.platform,
                    "machine": platform.machine()},
        "elapsed_seconds": time.monotonic() - started,
        "limits": QUALIFICATION_LIMITS,
    }


def qualification_main(name, *, verbosity=1):
    before, started = qualification_sources(), time.monotonic()
    program = unittest.main(exit=False, verbosity=verbosity, testRunner=QualificationRunner)
    report = qualification_report(name, program, before, started)
    print(QUALIFICATION_PREFIX + json.dumps(report, sort_keys=True), flush=True)
    return (0 if program.result.wasSuccessful() and
            report["coverage"] != "INCOMPLETE_INSPECTION_SCOPE" else 1)


class SourceUnavailable(RuntimeError):
    """Required local Git object missing; never fetch or substitute a source."""


class FixtureOperationError(RuntimeError):
    """Operational failure, not a qualified historical/native limitation."""


OPERATIONS = frozenset(("command", "setup", "source-probe", "source-read",
                        "source-revision", "git-init", "git-stage", "git-commit",
                        "git-worktree", "install"))


def operation_error(operation, outcome, returncode=None):
    # Only caller-owned vocabulary and numeric process facts. Never render a
    # child exception, argv, output, or arbitrary caller-supplied operation.
    if operation not in OPERATIONS:
        operation = "command"
    code = f"; returncode={returncode}" if type(returncode) is int else ""
    return FixtureOperationError(f"fixture {operation}: {outcome}{code}; evidence retained")


def install_timing(label, limit, started, outcome, returncode=None):
    # Supplemental stdout event only: keep the strict qualification/provenance
    # schema unchanged. All labels/outcomes originate in this fixture, not argv
    # or exception/child text. A returned installer alone is not qualification.
    if label is not None:
        print(INSTALL_TIMING_PREFIX + json.dumps({
            "phase": label, "limit_seconds": limit,
            "elapsed_seconds": time.monotonic() - started,
            "outcome": outcome,
            "returncode": returncode if type(returncode) is int else None,
        }, sort_keys=True), flush=True)


def setup_errors(function):
    """Contain setup I/O/decoding exceptions too, without leaking their context."""
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (OSError, ValueError, subprocess.SubprocessError):
            raise operation_error("setup", "io-or-format-failure") from None
    return wrapped


@dataclass(frozen=True)
class Origin:
    label: str
    revision: str
    sha256: str
    installer: str


@dataclass(frozen=True)
class Entry:
    mode: int
    mtime_ns: int
    identity: Tuple[int, int, int]
    data: Optional[bytes]


def bind(value, tokens):
    """Bind only fixture-declared tokens, preserving arbitrary path characters."""
    if isinstance(value, str):
        return re.sub(r"\{(requested|project|home|core|release)\}",
                      lambda m: tokens[m[1]], value)
    if isinstance(value, tuple):
        return tuple(bind(v, tokens) for v in value)
    if hasattr(value, "__dataclass_fields__"):
        return replace(value, **{k: bind(getattr(value, k), tokens)
                                 for k in value.__dataclass_fields__})
    return value


def unescape_report(text):
    # One JSON escaping layer (including Unicode escapes) plus YAML/TOML/plain
    # punctuation is enough for the supported report representations tested
    # here. This is not a decoder for arbitrary encodings or obfuscation.
    return re.sub(r'\\(?:u[0-9a-fA-F]{4}|["\\/bfnrt])',
                  lambda m: json.loads('"' + m[0] + '"'), text)


def words(text):
    return tuple(re.findall(r"\w+", text.casefold()))


def private_fragments(entries):
    """Fixture-derived negative witnesses, not a universal secrecy proof.

    Examine owned Markdown/TOML payloads, including installed baselines, NOT
    installer source or Git objects. Four-word prompt excerpts and native
    metadata values are independent of quote/list/whitespace representation.
    Short native values and individual tool names also count, but field names
    alone (e.g. permission_fields=['tools']) do not. No runtime classification
    or expected status is inferred from this corpus.
    """
    forbidden = {(SECRET.casefold(),)}
    payloads = {(Path(rel).suffix, "/agents/" in "/" + rel, entry.data)
                for rel, entry in entries.items()
                if Path(rel).suffix in (".md", ".toml") and entry.data is not None
                and stat.S_ISREG(entry.mode) and len(entry.data) <= MAX_INPUT_BYTES}
    for suffix, agent, raw in payloads:
        # Invalid-input cases are intentional; replacement retains readable
        # fragments, while the independent pristine corpus remains included.
        text = unescape_report(raw.decode("utf-8", errors="replace"))
        # Do not manufacture a private phrase by joining separate public
        # adapter labels such as "Provider: claude" and "Scope: global".
        for line in text.splitlines():
            tokens = words(line)
            forbidden.update(tokens[i:i + 4] for i in range(len(tokens) - 3))
        if not agent:
            continue
        if suffix == ".toml":
            metadata = text.split('developer_instructions = """', 1)[0]
        elif text.startswith("---\n") and "\n---\n" in text:
            metadata = text.split("\n---\n", 1)[0]
        else:
            continue  # Deliberately corrupt/unsupported fixture, not a baseline.
        for field, value in re.findall(r"(?m)^([\w-]+)\s*[:=]\s*(.+)$", metadata):
            values = value.strip("[]").split(",") if field == "tools" else (value,)
            for part in values:
                tokens = words(part)
                if 0 < len(tokens) <= 4:
                    forbidden.add(tokens)
    return forbidden


def assert_private_output(case, stdout, stderr, *, path_fields=None):
    if len(stdout) + len(stderr) > MAX_INPUT_BYTES:
        raise AssertionError("report exceeds privacy oracle bound")
    try:
        out = stdout.decode("utf-8", errors="strict")
        err = stderr.decode("utf-8", errors="strict")
    except UnicodeError:
        raise AssertionError("invalid report encoding") from None
    output = out + err
    if any(ord(c) < 32 and c not in "\n\t" or ord(c) == 127 for c in output):
        raise AssertionError("unescaped report control character")
    if str(case.project) in output and any(ord(c) < 32 for c in str(case.project)):
        raise AssertionError("raw control-character path exposed")
    if path_fields is not None:
        # CLI callers supply independent (line index, exact prefix, known path)
        # witnesses. Exempt only that JSON token, never its suffix or stderr.
        lines = out.split("\n")
        seen = set()
        for index, prefix, path in path_fields:
            if (index in seen or not 0 <= index < len(lines) or prefix not in (
                    "Requested directory: ", "Physical project scope: ",
                    "  Directory: ", "    File: ")):
                raise AssertionError("invalid expected path field location")
            seen.add(index)
            token = prefix + json.dumps(str(path), ensure_ascii=True)
            line = lines[index]
            if (not line.startswith(token) or
                    (not line[len(token):].startswith("; ") if prefix == "    File: "
                     else line != token)):
                raise AssertionError("expected escaped path field mismatch")
            lines[index] = prefix + '"<authorized-path>"' + line[len(token):]
        output = "\n".join(lines) + err
    output = unescape_report(output)
    if SECRET.casefold() in output.casefold():
        raise AssertionError("private fixture value exposed")
    # Only actual fixture paths may carry otherwise-private native name atoms.
    # Do not exempt arbitrary path-shaped strings or private canaries in paths.
    snapshots = (case.session.pristine, case.before)
    paths = {str(case.session.root / rel) for snapshot in snapshots for rel in snapshot}
    paths.update((str(case.project), str(case.requested)))
    if path_fields is None:
        for path in sorted(paths, key=len, reverse=True):
            output = output.replace(path, " ")
    forbidden = set().union(*(private_fragments(snapshot) for snapshot in snapshots))
    tokens = words(output)
    observed = {tokens[i:i + size] for size in range(1, 5)
                for i in range(len(tokens) - size + 1)}
    if forbidden & observed or re.search(r"\bdeveloper_instructions\s*=", output):
        raise AssertionError("raw installed prompt/native value exposed")


class FixtureSession:
    """One positively-owned session, serial cases, no silent fallback/cleanup.

    begin(name) -> Case; assert the eventual report against case.expected()
    and call case.accept(stdout, stderr) ONLY after all report assertions pass.
    accept enforces application read-only/privacy/stub oracles then restores
    pristine synthetic state. clean() refuses an unaccepted or failed case.
    """
    @setup_errors
    def __init__(self):
        self.root = Path(tempfile.mkdtemp(prefix="inspect-fixture-", dir=ROOT / "test"))
        self.identity = self.root.stat().st_dev, self.root.stat().st_ino
        self.deadline = time.monotonic() + SESSION_SECONDS
        self.counts = Counter()
        self.origins = {}
        self.commands = []
        self.active = None
        self.pristine = None
        self.held = {}
        self.sockets = []
        for name in ("home", "tmp", "bin", "calls", "sources", "cohorts", "global",
                     "git-template"):
            (self.root / name).mkdir()
        # Reproduce the ordinary Git template's info/exclude structure without
        # inheriting user templates or hooks. Current local publication expects
        # that standard directory to exist.
        (self.root / "git-template/info").mkdir()
        (self.root / "git-template/info/exclude").write_text("# Synthetic fixture exclusions\n")
        for name in FORBIDDEN:
            p = self.root / "bin" / name
            # Redirection belongs to the stub, not to a tool invocation.
            # No arguments/values are logged; a marker survives swallowed rc=99.
            # A literal owned destination also survives a child's scrubbed env.
            p.write_text('#!/bin/sh\n'
                         f': > {shlex.quote(str(self.root / "calls" / name))}\nexit 99\n')
            p.chmod(0o700)
        # Allowlist, not inherited tool config. Git config/attributes/hooks,
        # client homes, Python startup, proxy/credential and Beads env scrubbed.
        self.env = {
            "PATH": str(self.root / "bin") + os.pathsep +
                    os.pathsep.join(dict.fromkeys((
                        str(Path(shutil.which("python3")).parent),
                        "/usr/bin", "/bin", "/usr/sbin", "/sbin"))),
            "HOME": str(self.root / "home"),
            "TMPDIR": str(self.root / "tmp"),
            # Keep the absent core's nearest existing parent BELOW the ceiling.
            # Git invoked AT a ceiling still searches its parents.
            "DOMESTIQUE_HOME": str(self.root / "global/core"),
            "XDG_CONFIG_HOME": str(self.root / "home/xdg-config"),
            "XDG_STATE_HOME": str(self.root / "home/xdg-state"),
            "XDG_DATA_HOME": str(self.root / "home/xdg-data"),
            "XDG_CACHE_HOME": str(self.root / "home/xdg-cache"),
            "CLAUDE_CONFIG_DIR": str(self.root / "home/.claude"),
            "CODEX_HOME": str(self.root / "home/.codex"),
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_ATTR_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.hooksPath",
            "GIT_CONFIG_VALUE_0": os.devnull,
            "GIT_TEMPLATE_DIR": str(self.root / "git-template"),
            "GIT_CEILING_DIRECTORIES": str(self.root),
            "GIT_AUTHOR_NAME": "Inspection fixture",
            "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
            "GIT_COMMITTER_NAME": "Inspection fixture",
            "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
            "GIT_OPTIONAL_LOCKS": "0", "GIT_PAGER": "cat", "PAGER": "cat",
            "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1",
            "LC_ALL": "C", "BD_DISABLE_METRICS": "1",
        }

    def run(self, args, *, cwd=None, env=None, check=True, operation="command",
            install_phase=None):
        if operation not in OPERATIONS:
            raise operation_error("command", "invalid-operation")
        if install_phase is not None and (
                operation != "install" or install_phase not in INSTALL_PHASES):
            raise operation_error(operation, "invalid-install-phase")
        start = time.monotonic()
        if type(self.deadline) not in (int, float) or not math.isfinite(self.deadline):
            install_timing(install_phase, 0, start, "invalid-deadline")
            raise operation_error(operation, "invalid-deadline")
        remaining = self.deadline - start
        if remaining <= 0:
            install_timing(install_phase, 0, start, "budget-exhausted")
            raise operation_error(operation, "budget-exhausted")
        cap = INSTALL_SECONDS if operation == "install" else COMMAND_SECONDS
        limit = min(cap, remaining)
        phase, process, failure = "launch-failure", None, None
        try:
            process = subprocess.Popen([str(a) for a in args], cwd=cwd or self.root,
                                       env=env or self.env, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, start_new_session=True)
            phase = "communication-failure"
            limit = min(cap, max(0, self.deadline - time.monotonic()))
            stdout, stderr = process.communicate(timeout=limit)
        except subprocess.TimeoutExpired:
            failure = "timeout"
        except (OSError, ValueError, subprocess.SubprocessError):
            failure = phase
        if failure and process is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass  # Exit race; draining and failure reporting are still required.
            except OSError:
                failure += "; termination-failure"
            try:
                process.communicate(timeout=10)
            except (OSError, ValueError, subprocess.SubprocessError):
                failure += "; drain-failure"
        if process is not None:
            # Popen.__exit__ can wait without a bound after a failed drain.
            # Close pipes explicitly instead; communicate owns bounded reaping.
            for pipe in (process.stdout, process.stderr):
                if pipe is not None:
                    try:
                        pipe.close()
                    except OSError:
                        failure = (failure + "; " if failure else "") + "pipe-close-failure"
        if failure:
            install_timing(install_phase, limit, start, failure,
                           process.returncode if process is not None else None)
            raise operation_error(operation, failure) from None
        result = subprocess.CompletedProcess(args, process.returncode, stdout, stderr)
        self.commands.append((operation, result.returncode,
                              round(time.monotonic() - start, 3)))
        install_timing(install_phase, limit, start,
                       "nonzero-exit" if result.returncode else "returned", result.returncode)
        if check and result.returncode:
            raise operation_error(operation, "nonzero-exit", result.returncode)
        return result

    @setup_errors
    def source(self, label, revision):
        found = self.run(["git", "-C", ROOT, "cat-file", "-e",
                          revision + ":domestique.sh"], check=False, operation="source-probe")
        if found.returncode:
            # Only a genuine absent object is a source dependency failure.
            detail = found.stderr.decode("utf-8", errors="backslashreplace")
            if any(s in detail for s in ("Not a valid object name", "invalid object name",
                                        "does not exist", "not a valid object name")):
                raise SourceUnavailable("fixture source-probe: local source unavailable; "
                                        f"returncode={found.returncode}; no fetch; evidence retained")
            raise operation_error("source-probe", "nonzero-exit", found.returncode)
        raw = self.run(["git", "-C", ROOT, "show",
                        revision + ":domestique.sh"], operation="source-read").stdout
        path = self.root / "sources" / (label + ".sh")
        path.write_bytes(raw)
        self.origins[label] = Origin(label, revision, hashlib.sha256(raw).hexdigest(), str(path))
        return path

    def project(self, name, git=False):
        path = self.root / "cohorts" / name
        path.mkdir()
        if git:
            self.run(["git", "init", "-q", path], operation="git-init")
            self.counts["git_init"] += 1
        return path

    def install(self, label, script, *args):
        if label not in INSTALL_PHASES:
            raise operation_error("install", "invalid-install-phase")
        self.counts[label] += 1
        self.run(["bash", script, *args], operation="install", install_phase=label)
        self.assert_no_calls()

    def copy_text(self, source, destination):
        """Only owned UTF-8 installer payloads; never Git/native DB copying."""
        self.owned_path(source)
        self.owned_path(destination)
        for path in sorted(source.rglob("*")):
            rel = path.relative_to(source)
            if ".git" in rel.parts:
                continue
            if any(p in {".beads", ".dolt", "dolt"} or
                   p.endswith((".db", ".sqlite", ".sqlite3")) for p in rel.parts):
                raise ValueError("database copying forbidden")
            s = path.lstat()
            dest = destination / rel
            if stat.S_ISDIR(s.st_mode):
                dest.mkdir(exist_ok=True, parents=True)
            elif stat.S_ISREG(s.st_mode) and s.st_nlink == 1:
                raw = path.read_bytes()
                raw.decode("utf-8")  # Fail explicitly: textual installer artifacts only.
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(raw)
            else:
                raise ValueError("unsafe source for textual reuse")

    def owned_path(self, path):
        rel = path.relative_to(self.root)
        if ".." in rel.parts or self.root.resolve() != self.root:
            raise ValueError("path outside owned fixture")
        current = self.root
        for part in rel.parts:
            current = current / part
            if current.is_symlink():
                raise ValueError("symlink in textual fixture path")

    @setup_errors
    def setup(self):
        historical = self.source("historical", HISTORICAL_PIN)
        older = self.source("pre-snapshot", PRE_SNAPSHOT_PIN)
        # Assert the local older source truly predates stored baseline machinery.
        raw = older.read_bytes()
        if b"snapshot_format" in raw or b"SNAPSHOT_BASE" in raw:
            raise FixtureOperationError("pinned older source is not pre-snapshot")
        # Format-1 fixtures from the retained source, never a V2 installation.
        current = preview_fixture.materialize(self.root / "sources")
        revision = self.run(["git", "-C", ROOT, "rev-parse", "HEAD"],
                            operation="source-revision").stdout
        if re.fullmatch(rb"[0-9a-f]{40}\n?", revision) is None:
            raise operation_error("source-revision", "invalid-output")
        revision = revision.decode("ascii").strip()
        self.origins["current"] = Origin("retained-private-preview", revision,
                                        hashlib.sha256(current.read_bytes()).hexdigest(),
                                        str(current))
        self.projects = {name: self.project(name, git=name in (
            "normal", "guest", "adopted", "private", "global-only"))
                         for name in ("normal", "guest", "old", "adopted", "empty",
                                      "nongit", "spaces here", "control\n\t\x1bhere",
                                      "private", "global-only")}
        self.projects["spaces"] = self.projects.pop("spaces here")
        self.projects["control"] = self.projects.pop("control\n\t\x1bhere")
        self.install("historical_normal", historical, "--platform", "all",
                     self.projects["normal"])
        self.install("historical_guest", historical, "--platform", "both", "--guest",
                     self.projects["guest"])
        self.install("pre_snapshot", older, self.projects["old"])
        self.copy_text(self.projects["old"], self.projects["adopted"])
        self._edit(self.projects["adopted"] / ".claude/agents/implementer.md", "body")
        self.install("historical_adoption", historical, self.projects["adopted"])
        for name in ("nongit", "spaces", "control"):
            self.copy_text(self.projects["normal"], self.projects[name])
        normal = self.projects["normal"]
        self.run(["git", "-C", normal, "add", "."], operation="git-stage")
        self.run(["git", "-C", normal, "commit", "-qm", "Synthetic installed fixture"],
                 operation="git-commit")
        linked = self.root / "cohorts/linked"
        self.run(["git", "-C", normal, "worktree", "add", "-q", "--detach", linked],
                 operation="git-worktree")
        self.counts["worktree_add"] += 1
        self.projects["linked"] = linked
        self.install("current_global", current, "--global", "--platform", "all")
        self.install("current_local", current, "--local", self.projects["private"],
                     "--platform", "all")
        # Empty isolated global scope for historical cases; installed HOME/core
        # remain covered by the whole-session preservation oracle in every case.
        (self.root / "empty-home").mkdir()
        self.pristine = self.snapshot()
        return self

    def assert_no_calls(self):
        if tuple((self.root / "calls").iterdir()):
            raise AssertionError(f"forbidden command marker; retained {self.root}")

    def snapshot(self):
        """Owned-tree oracle, NOT evidence classification. Never follows links.

        Regular payloads here were created by this fixture. Synthetic Beads
        sentinels are the sole allowed .beads contents. Held pre-denial fds let
        the oracle compare unreadable-file bytes without chmod/read repair.
        """
        root_stat = self.root.lstat()
        if (self.root.resolve() != self.root or
                (root_stat.st_dev, root_stat.st_ino) != self.identity):
            raise ValueError("owned session root changed")
        entries = {}

        def visit(path):
            s = path.lstat()
            rel = str(path.relative_to(self.root))
            if s.st_uid != os.getuid() or s.st_dev != self.identity[0]:
                raise ValueError("foreign fixture state")
            data = None
            if stat.S_ISREG(s.st_mode):
                parts = path.relative_to(self.root).parts
                db_path = any(part.lower() in {".beads", ".dolt", "dolt", "beads.db"} or
                              part.lower().endswith((".db", ".sqlite", ".sqlite3",
                                                     ".db-wal", ".db-shm"))
                              for part in parts)
                synthetic = parts == ("cohorts", "private", ".beads", "SYNTHETIC")
                if db_path and not synthetic:
                    raise ValueError("native database state forbidden")
                held = self.held.get(path)
                if held is not None:
                    if os.fstat(held).st_ino != s.st_ino:
                        raise ValueError("held unreadable fixture changed")
                    data = os.pread(held, s.st_size + 1, 0)
                else:
                    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
                    with os.fdopen(fd, "rb") as f:
                        if os.fstat(f.fileno()).st_ino != s.st_ino:
                            raise ValueError("fixture changed during capture")
                        data = f.read()
            elif stat.S_ISLNK(s.st_mode):
                data = os.fsencode(os.readlink(path))
            elif not (stat.S_ISDIR(s.st_mode) or stat.S_ISFIFO(s.st_mode) or
                      stat.S_ISSOCK(s.st_mode)):
                raise ValueError("unsupported oracle fixture kind")
            entries[rel] = Entry(s.st_mode, s.st_mtime_ns,
                                 (s.st_dev, s.st_ino, s.st_nlink), data)
            if stat.S_ISDIR(s.st_mode):
                for child in sorted(path.iterdir()):
                    visit(child)
        visit(self.root)
        return entries

    def begin(self, name):
        if self.active is not None or self.pristine is None:
            raise RuntimeError("setup required or unaccepted case: evidence retained")
        if self.snapshot() != self.pristine:
            raise ValueError("pristine session changed")
        selected = next(row for row in MATRIX if row.name == name)
        self.active = Case(self, selected)
        self.active.prepare()
        self.active.before = self.snapshot()
        return self.active

    def restore(self, observed):
        if self.snapshot() != observed:
            raise ValueError("changed after assertions; evidence retained")
        for fd in self.held.values():
            os.close(fd)
        self.held.clear()
        for sock in self.sockets:
            sock.close()
        self.sockets.clear()
        # Remove only explicitly observed entries; retain pristine directories.
        for rel, entry in sorted(observed.items(), key=lambda x: len(Path(x[0]).parts),
                                 reverse=True):
            if rel == ".":
                continue
            wanted = self.pristine.get(rel)
            p = self.root / rel
            if stat.S_ISDIR(entry.mode):
                if wanted is None or not stat.S_ISDIR(wanted.mode):
                    p.rmdir()
            elif wanted != entry:
                p.unlink()
        for rel, entry in self.pristine.items():
            p = self.root / rel
            if stat.S_ISDIR(entry.mode):
                p.mkdir(exist_ok=True)
            elif not p.exists():
                # Pristine fixtures have only regular owned files; no databases,
                # hardlinks or symlinks. Git object bytes never leave this root.
                p.write_bytes(entry.data)
            os.chmod(p, stat.S_IMODE(entry.mode))
        for rel, entry in reversed(tuple(self.pristine.items())):
            os.utime(self.root / rel, ns=(entry.mtime_ns, entry.mtime_ns))
        restored = self.snapshot()
        if {k: replace(v, identity=(0, 0, 0)) for k, v in restored.items()} != {
                k: replace(v, identity=(0, 0, 0)) for k, v in self.pristine.items()}:
            raise ValueError("fixture restoration mismatch")
        self.pristine = restored
        self.active = None

    def clean(self):
        if self.active is not None or self.pristine is None:
            raise RuntimeError(f"failed/unaccepted fixture: retained {self.root}")
        self.assert_no_calls()
        observed = self.snapshot()
        if observed != self.pristine:
            raise ValueError("unasserted state; evidence retained")
        for rel, entry in sorted(observed.items(), key=lambda x: len(Path(x[0]).parts),
                                 reverse=True):
            path = self.root / rel
            if stat.S_ISDIR(entry.mode):
                path.rmdir()
            else:
                path.unlink()

    @staticmethod
    def _edit(path, edit):
        raw = path.read_bytes()
        if edit in ("metadata", "both"):
            pattern = (rb"(?m)^sandbox_mode = .+$" if path.suffix == ".toml" else
                       rb"(?m)^tools: .+$")
            replacement = (f'sandbox_mode = "{SECRET}"' if path.suffix == ".toml"
                           else f"tools: [{SECRET}]").encode()
            raw, count = re.subn(pattern, replacement, raw)
            if count != 1:
                raise FixtureOperationError("fixture metadata edit anchor changed")
        if edit in ("body", "both"):
            # For Codex put text INSIDE the installed multiline instructions.
            if path.suffix == ".toml":
                anchor = b'developer_instructions = """\n'
                if raw.count(anchor) != 1:
                    raise FixtureOperationError("fixture body edit anchor changed")
                raw = raw.replace(anchor, anchor + SECRET.encode() + b"\n")
            else:
                raw += b"\n" + SECRET.encode() + b"\n"
        path.write_bytes(raw)


class Case:
    def __init__(self, session, scenario):
        self.session = session
        self.scenario = scenario
        self.project = session.projects[scenario.cohort]
        self.requested = self.project
        self.env = dict(session.env)
        if scenario.cohort != "private":
            self.env.update(HOME=str(session.root / "empty-home"),
                            DOMESTIQUE_HOME=str(session.root / "absent-core"),
                            CLAUDE_CONFIG_DIR=str(session.root / "empty-home/.claude"),
                            CODEX_HOME=str(session.root / "empty-home/.codex"))
        self.before = None

    def expected(self):
        release = "unavailable"
        if self.scenario.cohort == "private":
            # Binding a recorded identity is not inferring a generation/status.
            # Use PRISTINE bytes even when the active record is corrupt now.
            release = self.session.pristine["global/core/active"].data.decode().strip().split("=")[1]
        return bind(self.scenario.record, {
            "requested": str(self.requested), "project": str(self.project),
            "home": self.env["HOME"], "core": self.env["DOMESTIQUE_HOME"],
            "release": release})

    def argv(self):
        return bind(self.scenario.argv, {"requested": str(self.requested),
                                        "project": str(self.project)})

    def cli_invocation(self):
        # Invalid targets are argv, never the subprocess working directory.
        expected = self.expected()
        cwd = (self.project if expected.context in ("invalid-target", "cli-misuse")
               else self.requested)
        return (("/bin/bash", str(ROOT / "domestique2.sh"), *self.argv()), cwd, expected)

    def prepare(self):
        s, p, mutation = self.session, self.project, self.scenario.mutation
        leaf = p / ".claude/agents/implementer.md"
        base = p / ".claude/.domestique/base/.claude/agents/implementer.md"
        if mutation == "none":
            return
        if mutation.startswith("edit:"):
            _, provider, edit = mutation.split(":")
            file = next(r for r in NORMAL.providers if r.provider == provider).files[0]
            s._edit(Path(bind(file.path, {"project": str(p)})), edit)
        elif mutation == "unrelated":
            # Include bounded historical native paths, but no Domestique content
            # or state. Arbitrary host names alone are outside that inventory.
            for rel in (".claude/agents/host.md", ".codex/agents/host.toml",
                        ".github/agents/host.agent.md",
                        ".claude/agents/implementer.md", ".codex/agents/implementer.toml",
                        ".github/agents/domestique-implementer.agent.md"):
                dest = p / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(SECRET + "\n")
        elif mutation == "subdirectory":
            self.requested = p / "sub/deeper"
            self.requested.mkdir(parents=True)
        elif mutation == "mixed-providers":
            self._remove(p / ".codex")
            (p / "AGENTS.md").unlink()
            s.copy_text(s.projects["guest"] / ".codex", p / ".codex")
        elif mutation == "generations":
            s.copy_text(s.projects["normal"] / ".claude", p / ".claude")
            (p / "CLAUDE.md").write_bytes((s.projects["normal"] / "CLAUDE.md").read_bytes())
        elif mutation == "global-only":
            self.project = self.requested = s.projects["global-only"]
        elif mutation == "beads":
            (p / ".beads/dolt").mkdir(parents=True)
            (p / ".beads/SYNTHETIC").write_text(
                "SYNTHETIC metadata-presence ONLY; no database or readiness\n")
        elif mutation in ("committed", "committed-metadata"):
            if mutation == "committed":
                s._edit(leaf, "body")
            else:
                # A real native tools reduction, not a Git-mode change or a
                # body canary masquerading as committed permissions coverage.
                raw, count = re.subn(
                    rb"(?m)^tools: Read, Write, Edit, Bash, Glob, Grep$",
                    b"tools: Read, Bash, Glob, Grep", leaf.read_bytes())
                if count != 1:
                    raise FixtureOperationError("committed tools edit anchor changed")
                leaf.write_bytes(raw)
            s.run(["git", "-C", p, "add", "."], operation="git-stage")
            s.run(["git", "-C", p, "commit", "-qm", "Synthetic committed customization"],
                  operation="git-commit")
        elif mutation == "missing-base":
            base.unlink()
        elif mutation == "corrupt-base":
            base.write_bytes(b"\xff\x00invalid baseline\n")
        elif mutation == "missing-file":
            leaf.unlink()
        elif mutation == "crlf":
            leaf.write_bytes(leaf.read_bytes().replace(b"\n", b"\r\n"))
        elif mutation == "invalid-encoding":
            leaf.write_bytes(b"\xff" + SECRET.encode())
        elif mutation == "oversized":
            leaf.write_bytes(b"x" * (MAX_INPUT_BYTES + 1))
        elif mutation == "unsupported-metadata":
            raw = leaf.read_bytes()
            leaf.write_bytes(raw.replace(b"tools: ", b"tools: &unsupported ", 1))
        elif mutation.startswith("private-"):
            dest = p / ".claude/agents/domestique-claude-local-implementer.md"
            s._edit(dest, mutation.removeprefix("private-"))
        elif mutation == "host-text":
            dest = p / "CLAUDE.md"
            dest.write_bytes(SECRET.encode() + b"\n" + dest.read_bytes() +
                             b"\n" + SECRET.encode() + b"\n")
        elif mutation == "partial-markers":
            dest = p / "CLAUDE.md"
            dest.write_bytes(dest.read_bytes().replace(END, b""))
        elif mutation == "mixed-markers":
            dest = p / "CLAUDE.local.md"
            dest.write_bytes((s.projects["guest"] / "CLAUDE.local.md").read_bytes())
        elif mutation == "hardlink":
            peer = p / "hardlink-peer.md"
            s.owned_path(leaf)
            s.owned_path(peer)
            # Only the live inode becomes unsafe; the installed baseline stays intact.
            os.link(leaf, peer)
        elif mutation in ("symlink", "directory", "fifo", "socket"):
            leaf.unlink()
            if mutation == "symlink":
                leaf.symlink_to(base)  # Safe referent but unsafe managed path.
            elif mutation == "directory":
                leaf.mkdir()
            elif mutation == "fifo":
                os.mkfifo(leaf)
            else:
                sock = socket.socket(socket.AF_UNIX)
                # macOS sockaddr_un path limit: bind relative to owned project.
                previous = Path.cwd()
                try:
                    os.chdir(p)
                    sock.bind(".claude/agents/implementer.md")
                finally:
                    os.chdir(previous)
                s.sockets.append(sock)
        elif mutation == "unreadable":
            s.held[leaf] = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW)
            leaf.chmod(0)
        elif mutation in ("missing-manifest", "corrupt-manifest"):
            dest = p / (".domestique-private/manifest" if self.scenario.cohort == "private"
                        else ".claude/.domestique/manifest")
            if mutation == "missing-manifest":
                dest.unlink()
            else:
                dest.write_bytes(b"format=\x00\n" + SECRET.encode())
        elif mutation == "core":
            (s.root / "global/core/active").write_bytes(b"release=invalid\n")
        elif mutation.startswith("target-"):
            self.requested = p / "invalid target"
            if mutation == "target-file":
                self.requested.write_text(SECRET)
            elif mutation == "target-symlink":
                # A readable directory alias is supported. This frozen INVALID
                # target row needs a dangling link, not a valid alias to p.
                self.requested.symlink_to(p / "missing-referent")
        else:
            raise ValueError("undeclared fixture mutation: " + mutation)

    def _remove(self, path):
        # Only builder-known disposable textual subtrees, never follow links.
        self.session.owned_path(path)
        if path.is_dir() and not path.is_symlink():
            for child in path.iterdir():
                self._remove(child)
            path.rmdir()
        else:
            path.unlink()

    def accept(self, stdout=b"", stderr=b"", *, path_fields=None):
        assert_private_output(self, stdout, stderr, path_fields=path_fields)
        self.session.assert_no_calls()
        observed = self.session.snapshot()
        if observed != self.before:
            raise AssertionError(f"inspection changed owned tree; retained {self.session.root}")
        self.session.restore(observed)


def provenance_summary(session):
    return json.dumps({"origins": {k: vars(v) for k, v in session.origins.items()},
                       "setup_counts": dict(session.counts),
                       "installer_seconds": sum(c[2] for c in session.commands
                                                if c[0] == "install"),
                       "declared_matrix_cases": len(MATRIX), "root": str(session.root),
                       "root_identity": session.identity,
                       "native_calls": 0, "beads": "synthetic metadata only"},
                      sort_keys=True)


def qualified_cohort(session):
    tools = {}
    for name, path in (("python3", shutil.which("python3", path=session.env["PATH"])),
                       ("bash", "/bin/bash"),
                       ("git", shutil.which("git", path=session.env["PATH"]))):
        tools[name] = {"path": path, "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()}
    return {**json.loads(provenance_summary(session)),
            "commands": dict(Counter(c[0] for c in session.commands)),
            "command_seconds": sum(c[2] for c in session.commands),
            "forbidden_stubs": list(FORBIDDEN), "tools": tools, "cleaned": False}
