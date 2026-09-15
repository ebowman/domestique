"""Focused fixture/contract/oracle qualification, NOT runtime --inspect tests."""
from collections import Counter
from contextlib import redirect_stdout
from dataclasses import asdict
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import unittest
from unittest.mock import Mock, patch

import inspect_fixture as F


class ContractTests(unittest.TestCase):
    def assert_safe_failure(self, action, outcome, exception=F.FixtureOperationError):
        try:
            action()
        except exception as error:
            rendered = "".join(traceback.format_exception(type(error), error, error.__traceback__))
            self.assertFalse(F.SECRET in rendered, "private canary escaped into diagnostic traceback")
            self.assertIn(outcome, str(error))
            self.assertLess(len(str(error)), 180)
            self.assertIsNone(error.__cause__)
        else:
            self.fail("failure was swallowed")

    @staticmethod
    def mock_session():
        session = object.__new__(F.FixtureSession)
        session.root = Path("/synthetic-owned-evidence")
        session.deadline = time.monotonic() + 120
        session.env = {}
        session.commands = []
        session.counts = Counter()
        return session

    def test_install_and_ordinary_caps_clip_original_session_including_launch(self):
        self.assertEqual((F.SESSION_SECONDS, F.INSTALL_SECONDS, F.COMMAND_SECONDS),
                         (900, 300, 120))
        for operation in F.OPERATIONS:
            cap = 300 if operation == "install" else 120
            for remaining, launch_seconds in ((900, 0), (200, 0), (75, 10), (0.25, 0),
                                               (1, 2)):
                with self.subTest(operation=operation, remaining=remaining, launch=launch_seconds):
                    session = self.mock_session()
                    session.deadline = 100 + remaining
                    process = Mock(returncode=0)
                    process.communicate.return_value = (b"", b"")
                    with patch.object(F.time, "monotonic", return_value=100) as clock:
                        def launch(*args, **kwargs):
                            clock.return_value = 100 + launch_seconds
                            return process
                        with patch.object(F.subprocess, "Popen", side_effect=launch):
                            session.run(["synthetic"], operation=operation)
                    process.communicate.assert_called_once_with(
                        timeout=min(cap, max(0, remaining - launch_seconds)))
                    self.assertEqual(session.deadline, 100 + remaining)
                    self.assertEqual(session.commands, [(operation, 0, launch_seconds)])

    def test_invalid_and_expired_session_deadlines_fail_before_launch(self):
        for deadline in (float("nan"), float("inf"), float("-inf"), None, True,
                         F.SECRET, -1, 0, 100):
            outcome = ("budget-exhausted" if type(deadline) is int else "invalid-deadline")
            for operation in ("command", "install"):
                with self.subTest(deadline_type=type(deadline).__name__, operation=operation):
                    session = self.mock_session()
                    session.deadline = deadline
                    output = io.StringIO()
                    with patch.object(F.time, "monotonic", return_value=100), \
                            patch.object(F.subprocess, "Popen") as launch, redirect_stdout(output):
                        self.assert_safe_failure(
                            lambda: session.run([F.SECRET], operation=operation,
                                install_phase="current_local" if operation == "install" else None),
                            outcome)
                        launch.assert_not_called()
                    self.assertNotIn(F.SECRET, output.getvalue())
                    if operation == "install":
                        row = json.loads(output.getvalue().removeprefix(F.INSTALL_TIMING_PREFIX))
                        self.assertEqual(row, dict(phase="current_local", limit_seconds=0,
                            elapsed_seconds=0, outcome=outcome, returncode=None))
                    else:
                        self.assertEqual(output.getvalue(), "")

    def test_install_phase_events_are_known_safe_and_leave_provenance_unchanged(self):
        for label in F.INSTALL_PHASES:
            for returncode in (0, 128):
                with self.subTest(label=label, returncode=returncode):
                    session = self.mock_session()
                    session.deadline = 1000
                    process = Mock(returncode=returncode)
                    output = io.StringIO()
                    with patch.object(F.time, "monotonic", return_value=100) as clock:
                        def communicate(**kwargs):
                            clock.return_value = 231.5
                            return F.SECRET.encode(), F.SECRET.encode()
                        process.communicate.side_effect = communicate
                        with patch.object(F.subprocess, "Popen", return_value=process), \
                                patch.object(session, "assert_no_calls") as no_calls, \
                                redirect_stdout(output):
                            if returncode:
                                self.assert_safe_failure(
                                    lambda: session.install(label, F.SECRET, F.SECRET), "nonzero-exit")
                                no_calls.assert_not_called()
                            else:
                                session.install(label, F.SECRET, F.SECRET)
                                no_calls.assert_called_once_with()
                    row = json.loads(output.getvalue().removeprefix(F.INSTALL_TIMING_PREFIX))
                    self.assertEqual(row, dict(phase=label, limit_seconds=300,
                        elapsed_seconds=131.5, outcome="nonzero-exit" if returncode else "returned",
                        returncode=returncode))
                    self.assertNotIn(F.SECRET, output.getvalue())
                    self.assertEqual(session.commands, [("install", returncode, 131.5)])
                    self.assertEqual(session.counts, {label: 1})
        session = self.mock_session()
        with patch.object(session, "run") as run, redirect_stdout(io.StringIO()) as output:
            self.assert_safe_failure(lambda: session.install(F.SECRET, F.SECRET),
                                     "invalid-install-phase")
            run.assert_not_called()
            self.assertEqual(output.getvalue(), "")
        self.assertEqual(session.counts, {})

    def test_named_matrix_and_exit_contract(self):
        self.assertEqual(len(F.MATRIX), len({r.name for r in F.MATRIX}))
        self.assertGreaterEqual(len(F.MATRIX), 50)
        self.assertTrue({"committed-customization", "committed-permissions-customization"}
                        <= {r.name for r in F.MATRIX})

        def walk(value):
            if isinstance(value, dict):
                if "reasons" in value:
                    self.assertTrue(set(value["reasons"]) <= F.REASONS)
                for child in value.values():
                    walk(child)
            elif isinstance(value, (tuple, list)):
                for child in value:
                    walk(child)

        for row in F.MATRIX:
            with self.subTest(row=row.name):
                record = row.record
                walk(asdict(record))
                self.assertEqual(record.exit_code,
                                 {"completed": 0, "incomplete": 1, "misuse": 2}[record.result])
                self.assertTrue(all(asdict(row.preservation).values()))
                self.assertNotIn(F.SECRET, json.dumps(asdict(record)))
                if record.context != "cli-misuse":
                    self.assertEqual(record.scopes[0].scope, "global")
                for scope in record.scopes:
                    self.assertEqual(tuple(p.provider for p in scope.providers), F.PROVIDERS)
                    for provider in scope.providers:
                        for file in provider.files:
                            if file.permission_fields:
                                self.assertEqual(file.baseline.kind, "snapshot")
                                self.assertEqual(file.baseline.status, "valid")
                                self.assertEqual(file.metadata, "different")
                if record.exit_code == 1:
                    self.assertTrue(record.reasons)

    def test_generations_and_creation_are_not_guessed(self):
        row = next(r for r in F.MATRIX if r.name == "multiple-generations-one-provider")
        self.assertEqual(len(row.record.scopes[1].providers[0].generations), 2)
        self.assertEqual(F.NORMAL.providers[0].files[0].ownership, "unknown")
        self.assertEqual(F.NORMAL.providers[2].generations[0].generation,
                         "historical-draft-copilot")
        self.assertIsNone(F.OLD.providers[0].generations[0].reported_version)
        for provider in F.PRIVATE_LOCAL.providers:
            self.assertEqual(provider.files[0].baseline.kind, "digest")
            self.assertEqual(provider.files[0].metadata, "unknown")
            self.assertIsNone(provider.generations[0].reported_version)

    def test_missing_source_and_operational_failure_are_distinct(self):
        # No real installer/source attempts for this fault injection.
        session = self.mock_session()
        for stderr, exception in (
                (b"fatal: Not a valid object name missing:domestique.sh", F.SourceUnavailable),
                (b"fatal: permission denied", F.FixtureOperationError)):
            with self.subTest(classification=exception.__name__):
                with patch.object(session, "run", return_value=subprocess.CompletedProcess(
                        (), 128, F.SECRET.encode(), stderr + F.SECRET.encode())):
                    self.assert_safe_failure(
                        lambda: session.source("missing", F.SECRET), "source-probe", exception)

    def test_subprocess_diagnostics_are_safe_at_origin(self):
        for fault, expected in (
                ("exit", "nonzero-exit; returncode=128"),
                ("launch", "launch-failure"), ("arguments", "launch-failure"),
                ("communicate", "communication-failure"),
                ("timeout", "timeout"), ("exit-race", "timeout"),
                ("termination", "timeout; termination-failure"),
                ("drain-timeout", "timeout; drain-failure"),
                ("drain-io", "timeout; drain-failure"),
                ("pipe-close", "pipe-close-failure")):
            with self.subTest(fault=fault):
                session = self.mock_session()
                process = Mock(pid=12345, returncode=128)
                timeout = subprocess.TimeoutExpired(
                    [F.SECRET], 999999, output=F.SECRET.encode(), stderr=F.SECRET.encode())
                io_error = OSError(13, F.SECRET, F.SECRET)
                result = (F.SECRET.encode(), F.SECRET.encode())
                process.communicate.return_value = result
                if fault == "communicate":
                    process.communicate.side_effect = [io_error, result]
                elif fault in ("timeout", "exit-race", "termination", "drain-timeout", "drain-io"):
                    process.communicate.side_effect = [
                        timeout, timeout if fault == "drain-timeout" else
                        io_error if fault == "drain-io" else result]
                elif fault == "pipe-close":
                    process.stdout.close.side_effect = io_error
                output = io.StringIO()
                with patch.object(F.subprocess, "Popen", return_value=process) as launch, \
                        patch.object(F.os, "killpg") as kill, redirect_stdout(output):
                    if fault in ("launch", "arguments"):
                        launch.side_effect = io_error if fault == "launch" else ValueError(F.SECRET)
                    if fault == "termination":
                        kill.side_effect = io_error
                    elif fault == "exit-race":
                        kill.side_effect = ProcessLookupError(F.SECRET)
                    self.assert_safe_failure(
                        lambda: session.run(["untrusted-command", F.SECRET], operation="install",
                                            install_phase="historical_normal"),
                        "install: " + expected)
                    if process.communicate.call_count == 2:
                        kill.assert_called_once_with(12345, F.signal.SIGKILL)
                        self.assertEqual(process.communicate.call_args.kwargs["timeout"], 10)
                self.assertFalse(F.SECRET in repr(session.commands))
                self.assertNotIn(F.SECRET, output.getvalue())
                row = json.loads(output.getvalue().removeprefix(F.INSTALL_TIMING_PREFIX))
                self.assertEqual(set(row), {"phase", "limit_seconds", "elapsed_seconds",
                                            "outcome", "returncode"})
                self.assertEqual(row["phase"], "historical_normal")
                self.assertEqual(row["outcome"], expected.split("; returncode=")[0])
                self.assertGreater(row["limit_seconds"], 0)
                self.assertLessEqual(row["limit_seconds"], 120)
                self.assertGreaterEqual(row["elapsed_seconds"], 0)

    def test_budget_setup_and_success_output_failures_do_not_leak(self):
        session = self.mock_session()
        session.deadline = 0
        with patch.object(F.subprocess, "Popen") as launch:
            self.assert_safe_failure(lambda: session.run([F.SECRET]), "budget-exhausted")
            self.assert_safe_failure(lambda: session.run([], operation=F.SECRET), "invalid-operation")
            launch.assert_not_called()
        # Source file I/O errors may carry private path names; no side logs.
        with patch.object(session, "run", return_value=subprocess.CompletedProcess(
                (), 0, F.SECRET.encode(), b"")), \
                patch.object(Path, "write_bytes", side_effect=OSError(13, F.SECRET, F.SECRET)):
            self.assert_safe_failure(lambda: session.source("mock", "0" * 40),
                                     "setup: io-or-format-failure")
        # Even rc=0 is not sufficient evidence of a valid Git revision.
        with patch.object(session, "source", return_value=Path("/synthetic-source")), \
                patch.object(Path, "read_bytes", return_value=b"synthetic older source"), \
                patch.object(session, "run", return_value=subprocess.CompletedProcess(
                    (), 0, F.SECRET.encode(), b"")):
            self.assert_safe_failure(session.setup, "source-revision: invalid-output")

    def test_privacy_representations_without_installers(self):
        root = Path("/synthetic-owned-evidence")
        entries = {}
        payloads = (
            # Actual historical pinned Copilot implementer order, NOT reviewer.
            ("copilot", 'tools: ["read", "edit", "search", "execute"]'),
            ("claude", "tools: Read, Write, Edit, Bash, Glob, Grep"),
            ("codex", 'sandbox_mode = "workspace-write"'),
        )
        for provider, metadata in payloads:
            text = (metadata + '\ndeveloper_instructions = """\n' if provider == "codex"
                    else "---\n" + metadata + "\n---\n")
            text += "Provider: claude\nScope: global\nYou are an implementer. " + F.SECRET
            ext = ".toml" if provider == "codex" else ".md"
            entries[f"{provider}/agents/implementer{ext}"] = F.Entry(
                F.stat.S_IFREG | 0o600, 0, (0, 0, 1), text.encode())
        case = Mock(project=root / "project", requested=root / "project", before=entries)
        case.session.root = root
        case.session.pristine = entries
        for payload in (
                *(metadata for _, metadata in payloads),
                '["read", "edit", "search", "execute"]',
                "tools:\n  - read\n  - edit\n  - search\n  - execute",
                "tools = ['read', 'edit', 'search', 'execute']",
                'tools: ["Read","Write","Edit","Bash","Glob","Grep"]',
                "sandbox_mode: 'workspace-write'", "workspace-write",
                "You   are\nan implementer.", F.SECRET,
                # JSON string escaping must not hide fixture values/prompts.
                json.dumps({"detail": 'tools: ["read", "edit", "search", "execute"]'}),
                json.dumps(F.SECRET).replace("I", r"\u0049"),
                json.dumps("You are an implementer.").replace("Y", r"\u0059")):
            for channel in ("stdout", "stderr"):
                with self.subTest(channel=channel):
                    with self.assertRaises(AssertionError):
                        F.assert_private_output(case, **{channel: payload.encode()},
                                                **{("stderr" if channel == "stdout" else "stdout"): b""})
        for safe in (
                b"", b"claude: installed customized; metadata-changed; tools",
                b"Provider: claude\nScope: global\ninstalled\n",
                json.dumps({"path": str(root / "claude/agents/implementer.md"),
                            "metadata": "different", "instructions": "same",
                            "permission_fields": ["tools"]}).encode()):
            F.assert_private_output(case, safe, b"")
        self.assert_safe_failure(
            lambda: F.assert_private_output(case, b"\xff" + F.SECRET.encode(), b""),
            "invalid report encoding", AssertionError)


class RealFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.started = time.monotonic()
        cls.completed = set()
        cls.session = F.FixtureSession()
        print("inspect fixture evidence root:", cls.session.root, flush=True)
        cls.session.setup()
        print(F.provenance_summary(cls.session), flush=True)

    @classmethod
    def tearDownClass(cls):
        cohort = F.qualified_cohort(cls.session)
        F.QUALIFIED_COHORTS.append(cohort)
        # Never clean an active/unasserted case or a changed session.
        if cls.completed != set(range(1, 9)):
            print("inspect fixture assertion failed; retained:", cls.session.root, flush=True)
            return
        cls.session.clean()
        cohort["cleaned"] = True
        print(f"inspect fixtures: cleaned; {time.monotonic() - cls.started:.3f}s", flush=True)

    def assert_baseline_witnesses(self, case, observed=None):
        s = case.session
        observed = case.before if observed is None else observed
        mutation = case.scenario.mutation

        def entry(path):
            rel = Path(path).relative_to(s.root)
            for parent in rel.parents:
                self.assertTrue(F.stat.S_ISDIR(observed[str(parent)].mode),
                                "baseline ancestor must be a real directory")
            value = observed[str(rel)]
            self.assertTrue(F.stat.S_ISREG(value.mode), "baseline must be regular")
            self.assertEqual(value.identity[2], 1, "baseline must be single-linked")
            self.assertTrue(value.mode & 0o444, "baseline must be readable")
            return value

        def unchanged_text(path, source=None):
            value = entry(path)
            self.assertLessEqual(len(value.data), F.MAX_INPUT_BYTES)
            self.assertTrue(b"\0" not in value.data, "baseline must be text")
            try:
                value.data.decode("utf-8")
            except UnicodeDecodeError:
                self.fail("baseline must be UTF-8")
            original = s.pristine[str(Path(source or path).relative_to(s.root))]
            self.assertTrue(value.data == original.data, "baseline bytes changed")
            if source is None:
                self.assertTrue(value == original, "baseline structure changed")

        for scope in case.expected().scopes:
            for provider in scope.providers:
                prefix = {"claude": ".claude", "codex": ".codex",
                          "copilot": ".github"}[provider.provider]
                for file in provider.files:
                    baseline = file.baseline
                    if baseline.status == "valid":
                        self.assertIn(baseline.kind, ("snapshot", "digest"))
                        self.assertIsNotNone(baseline.path)
                        source = None
                        if baseline.kind == "snapshot":
                            if mutation == "mixed-providers" and provider.provider == "codex":
                                source = s.projects["guest"] / Path(
                                    baseline.path).relative_to(case.project)
                            elif mutation == "generations":
                                source = s.projects["normal"] / Path(
                                    baseline.path).relative_to(case.project)
                        unchanged_text(baseline.path, source)
                    elif baseline.status == "corrupt":
                        self.assertEqual(mutation, "corrupt-base")
                        self.assertEqual(baseline.kind, "snapshot")
                        self.assertTrue(entry(baseline.path).data == b"\xff\x00invalid baseline\n",
                                        "corrupt baseline witness changed")
                    else:
                        self.assertEqual(baseline, F.Baseline("none", "unavailable"))
                        state = case.project / prefix / ".domestique"
                        physical_base = state / "base" / Path(file.path).relative_to(case.project)
                        if case.scenario.cohort == "old":
                            self.assertNotIn(str(state.relative_to(s.root)), observed)
                        elif mutation == "missing-base":
                            self.assertNotIn(str(physical_base.relative_to(s.root)), observed)
                        else:
                            self.assertIn(mutation, ("missing-manifest", "corrupt-manifest"))
                            manifest = (case.project / ".domestique-private/manifest"
                                        if case.scenario.cohort == "private" else state / "manifest")
                            if mutation == "missing-manifest":
                                self.assertNotIn(str(manifest.relative_to(s.root)), observed)
                            else:
                                self.assertTrue(entry(manifest).data ==
                                                b"format=\x00\n" + F.SECRET.encode(),
                                                "corrupt manifest witness changed")
                            if case.scenario.cohort != "private":
                                # Intact bytes without a usable manifest are not authority.
                                unchanged_text(physical_base)

    def test_01_source_provenance_and_bounded_setup(self):
        s = self.session
        self.assertEqual(s.counts, {
            "git_init": 5, "worktree_add": 1, "historical_normal": 1,
            "historical_guest": 1, "pre_snapshot": 1, "historical_adoption": 1,
            "current_global": 1, "current_local": 1})
        self.assertEqual(s.origins["historical"].revision, F.HISTORICAL_PIN)
        self.assertEqual(s.origins["pre-snapshot"].revision, F.PRE_SNAPSHOT_PIN)
        for origin in s.origins.values():
            self.assertEqual(F.hashlib.sha256(Path(origin.installer).read_bytes()).hexdigest(),
                             origin.sha256)
        self.assertNotIn("BD_PATH", s.env)
        self.assertNotIn("PYTHONPATH", s.env)
        self.assertNotIn("GIT_DIR", s.env)
        self.assertNotIn("HTTPS_PROXY", s.env)
        self.assertFalse((s.projects["old"] / ".claude/.domestique").exists())
        self.assertFalse((s.projects["old"] / ".git").exists())
        self.assertTrue((s.projects["linked"] / ".git").is_file())
        s.assert_no_calls()
        self.completed.add(1)

    def test_02_actual_formats_and_independent_baselines(self):
        s = self.session
        p = s.projects["normal"]
        for provider, prefix in (("claude", ".claude"), ("codex", ".codex"),
                                 ("copilot", ".github")):
            manifest = (p / prefix / ".domestique/manifest").read_text()
            self.assertIn("snapshot_format=1\nplatform=" + provider + "\n", manifest)
            self.assertIn("installed_ref=unknown\n", manifest)
            self.assertIn("script_sha256=" + s.origins["historical"].sha256, manifest)
            record = next(r for r in F.NORMAL.providers if r.provider == provider)
            file = F.bind(record.files[0], {"project": str(p)})
            self.assertEqual(Path(file.path).read_bytes(), Path(file.baseline.path).read_bytes())
        self.assertTrue((p / ".github/.domestique/created-files").is_file())
        for provider in ("claude", "codex"):
            self.assertEqual((s.projects["guest"] / f".{provider}/.domestique/mode").read_bytes(),
                             b"guest\n")
        adopted = s.projects["adopted"]
        leaf = adopted / ".claude/agents/implementer.md"
        base = adopted / ".claude/.domestique/base/.claude/agents/implementer.md"
        self.assertIn(F.SECRET.encode(), leaf.read_bytes())
        self.assertNotIn(F.SECRET.encode(), base.read_bytes())
        for scope, manifest in (
                ("global", s.root / "global/core/state/global-manifest"),
                ("local", s.projects["private"] / ".domestique-private/manifest")):
            text = manifest.read_text()
            self.assertTrue(text.startswith(f"format=1\nscope={scope}\n"))
            self.assertIn("providers=all\n", text)
            self.assertIn("created=claude:", text)
            self.assertIn("baseline=claude:", text)
        self.assertFalse(any(p.name in (".beads", ".dolt") for p in s.root.rglob("*")))
        self.completed.add(2)

    def test_03_every_scenario_builds_and_is_read_only_with_noop_consumer(self):
        # This does NOT claim an inspector passed. It proves every declared
        # fixture is buildable and every preservation oracle is exercised.
        s = self.session
        before_counts = s.counts.copy()
        for row in F.MATRIX:
            with self.subTest(row=row.name):
                case = s.begin(row.name)
                record = case.expected()
                self.assert_baseline_witnesses(case)
                self.assertEqual(record.exit_code, row.record.exit_code)
                self.assertNotIn("{project}", json.dumps(asdict(record)))
                self.assertNotIn("{release}", json.dumps(asdict(record)))
                if row.mutation == "unrelated":
                    for leaf, state in (
                            (".claude/agents/implementer.md", ".claude/.domestique"),
                            (".codex/agents/implementer.toml", ".codex/.domestique"),
                            (".github/agents/domestique-implementer.agent.md",
                             ".github/.domestique")):
                        self.assertTrue((case.project / leaf).read_bytes() ==
                                        (F.SECRET + "\n").encode(),
                                        "unrelated native witness must not be Domestique")
                        self.assertFalse((case.project / state).exists())
                    self.assertTrue(all(p.installation == "absent" and not p.files
                                        and p.reasons == ("unrelated-native-files",)
                                        for p in record.scopes[1].providers))
                if record.context not in ("invalid-target", "cli-misuse"):
                    self.assertEqual(record.resolved_directory, str(case.project))
                elif record.context == "invalid-target":
                    if row.mutation == "target-symlink":
                        self.assertTrue(case.requested.is_symlink())
                    self.assertFalse(case.requested.is_dir(),
                                     "invalid target must not be a supported directory alias")
                argv, cwd, wanted = case.cli_invocation()
                self.assertTrue(cwd.is_dir(), "CLI launch must use an executable cwd")
                self.assertEqual(argv, ("/bin/bash", str(F.ROOT / "domestique.sh"), *case.argv()))
                self.assertEqual(wanted, record)
                # Every error fixture retains an independent readable provider
                # witness, except absent/CLI/invalid-target which have none.
                for scope in record.scopes:
                    for provider in scope.providers:
                        for file in provider.files:
                            if file.status == "readable":
                                self.assertTrue(Path(file.path).is_file(), file.path)
                if row.name.startswith("unsafe-"):
                    file = record.scopes[1].providers[0].files[0]
                    live = case.before[str(Path(file.path).relative_to(s.root))]
                    kind = {"symlink": F.stat.S_ISLNK, "hardlink": F.stat.S_ISREG,
                            "directory": F.stat.S_ISDIR, "fifo": F.stat.S_ISFIFO,
                            "socket": F.stat.S_ISSOCK, "unreadable": F.stat.S_ISREG}
                    self.assertTrue(kind[row.mutation](live.mode))
                    if row.mutation == "hardlink":
                        peer = case.project / "hardlink-peer.md"
                        peer_rel = str(peer.relative_to(s.root))
                        self.assertNotIn(peer_rel, s.pristine)
                        self.assertEqual(live.identity[2], 2)
                        self.assertEqual(live.identity, case.before[peer_rel].identity)
                        self.assertTrue(live.data == case.before[peer_rel].data)
                        base = case.before[str(Path(file.baseline.path).relative_to(s.root))]
                        self.assertNotEqual(live.identity[:2], base.identity[:2])
                    elif row.mutation == "unreadable":
                        self.assertEqual(live.mode & 0o444, 0)
                if row.mutation in ("committed", "committed-metadata"):
                    result = s.run(["git", "-C", case.project, "status", "--porcelain"])
                    self.assertEqual(result.stdout, b"")
                    file = record.scopes[1].providers[0].files[0]
                    metadata_edit = row.mutation == "committed-metadata"
                    self.assertEqual(record.scopes[1].customization, "customized")
                    self.assertEqual(record.scopes[1].providers[0].customization, "customized")
                    self.assertEqual(file.comparison, "different")
                    self.assertEqual(file.metadata, "different" if metadata_edit else "same")
                    self.assertEqual(file.instructions, "same" if metadata_edit else "different")
                    self.assertEqual(file.permission_fields, ("tools",) if metadata_edit else ())
                    self.assertEqual(file.reasons, (
                        "metadata-changed" if metadata_edit else "instructions-changed",))
                    committed = s.run(["git", "-C", case.project, "show",
                                       "HEAD:.claude/agents/implementer.md"]).stdout
                    self.assertEqual(committed, Path(file.path).read_bytes())
                    self.assertNotEqual(committed, Path(file.baseline.path).read_bytes())
                if row.name == "private-synthetic-beads-presence":
                    self.assertEqual(record.scopes[1].beads, "synthetic-metadata-presence-only")
                if row.mutation.startswith("edit:") or row.mutation in (
                        "private-metadata", "private-body", "private-both",
                        "committed", "committed-metadata"):
                    provider = (row.mutation.split(":")[1] if ":" in row.mutation else "claude")
                    edit = ("body" if row.mutation == "committed" else "metadata"
                            if row.mutation == "committed-metadata" else
                            row.mutation.split(":")[-1].removeprefix("private-"))
                    file = next(r for r in record.scopes[1].providers
                                if r.provider == provider).files[0]
                    leaf = Path(file.path)
                    pristine = s.pristine[str(leaf.relative_to(s.root))].data
                    mutated = leaf.read_bytes()
                    # Structural fixture checks only, not a runtime classifier:
                    # the expected statuses above are fixed declarations.
                    separator = b'developer_instructions = """\n' if provider == "codex" else b"\n---\n"
                    self.assertEqual(pristine.count(separator), 1)
                    self.assertEqual(mutated.count(separator), 1)
                    before_metadata, before_body = pristine.split(separator)
                    after_metadata, after_body = mutated.split(separator)
                    self.assertEqual(before_metadata == after_metadata, edit == "body")
                    self.assertEqual(before_body == after_body, edit == "metadata")
                    if row.mutation == "committed-metadata":
                        self.assertIn(b"tools: Read, Write, Edit, Bash, Glob, Grep\n",
                                      before_metadata)
                        self.assertIn(b"tools: Read, Bash, Glob, Grep\n", after_metadata)
                        self.assertNotIn(F.SECRET.encode(), mutated)
                    else:
                        self.assertIn(F.SECRET.encode(), mutated)
                    base = Path(file.baseline.path)
                    self.assertEqual(base.read_bytes(),
                                     s.pristine[str(base.relative_to(s.root))].data)
                if row.name == "crlf":
                    leaf = Path(record.scopes[1].providers[0].files[0].path)
                    self.assertEqual(leaf.read_bytes().replace(b"\r\n", b"\n"),
                                     s.pristine[str(leaf.relative_to(s.root))].data)
                if row.name == "host-text-outside-policy":
                    policy = case.project / "CLAUDE.md"
                    host = F.SECRET.encode() + b"\n"
                    self.assertEqual(policy.read_bytes(), host +
                                     s.pristine[str(policy.relative_to(s.root))].data +
                                     b"\n" + host)
                self.assertTrue(case.argv()[0] == "--inspect")
                # Status/reason/field-name/escaped-path reports remain valid,
                # including missing witnesses and all generation identities.
                case.accept(json.dumps(asdict(record)).encode())
                F.COMPLETED_MATRIX.append(row.name)
                print("fixture oracle accepted:", row.name, flush=True)
        self.assertEqual(s.counts, before_counts)
        self.assertLess(time.monotonic() - self.started, F.SESSION_SECONDS)
        self.completed.add(3)

    def test_04_all_seven_stubs_leave_markers_even_when_exit_is_swallowed(self):
        s = self.session
        case = s.begin("absent")
        for name in F.FORBIDDEN:
            # Stub markers must work even if a faulty consumer scrubs all env.
            result = s.run(["/bin/sh", "-c", '"$1" ignored-private-argument || :',
                            "_", s.root / "bin" / name], env={"PATH": "/usr/bin:/bin"})
            self.assertEqual(result.returncode, 0)
            self.assertTrue((s.root / "calls" / name).is_file())
        with self.assertRaisesRegex(AssertionError, "forbidden command marker"):
            case.accept()
        with self.assertRaisesRegex(RuntimeError, "retained"):
            s.clean()
        # Explicit fault-test recovery after proving retention, not a finally
        # block or acceptance of a failed consumer.
        s.restore(s.snapshot())
        self.completed.add(4)

    def test_05_oracle_detects_bytes_modes_mtime_membership_and_link_changes(self):
        s = self.session
        for change in ("bytes", "mode", "mtime", "membership", "link"):
            with self.subTest(change=change):
                case = s.begin("absent")
                if change == "bytes":
                    path = s.root / "git-template/info/exclude"
                    prior = path.stat()
                    path.write_bytes(path.read_bytes().replace(b"Synthetic", b"SYNTHETIC"))
                    os.utime(path, ns=(prior.st_atime_ns, prior.st_mtime_ns))
                elif change == "mode":
                    case.project.chmod(0o700 if case.project.stat().st_mode & 0o077 else 0o755)
                elif change == "mtime":
                    os.utime(case.project, ns=(1, 1))
                elif change == "membership":
                    (case.project / "unexpected").mkdir()
                else:
                    (case.project / "unexpected-link").symlink_to(s.root / "home")
                with self.assertRaisesRegex(AssertionError, "changed owned tree"):
                    case.accept()
                with self.assertRaisesRegex(RuntimeError, "retained"):
                    s.clean()
                s.restore(s.snapshot())
        self.completed.add(5)

    def test_06_privacy_oracle_and_safe_escaped_paths(self):
        s = self.session
        case = s.begin("path-with-control-characters")
        payloads = [F.SECRET, "You are an implementer.",
                    "Read, Write, Edit, Bash"]
        with self.assertRaises(AssertionError):
            case.accept(str(case.project).encode())
        # Read the ACTUAL qualified sources' native values and prompts, not
        # just literals chosen to match the oracle. Cover every provider in
        # historical and current global/local cohorts.
        for scope, project, home in (
                (F.NORMAL, s.projects["normal"], s.root / "empty-home"),
                (F.PRIVATE_LOCAL, s.projects["private"], s.root / "home"),
                (F.PRIVATE_GLOBAL, s.projects["private"], s.root / "home")):
            for provider in scope.providers:
                path = Path(F.bind(provider.files[0].path,
                                   {"project": str(project), "home": str(home)}))
                raw = path.read_text()
                if path.suffix == ".toml":
                    metadata, body = raw.split('developer_instructions = """\n')
                    field = next(line for line in metadata.splitlines()
                                 if line.startswith("sandbox_mode ="))
                    value = field.split("=", 1)[1].strip()
                else:
                    metadata, body = raw.split("\n---\n")
                    field = next(line for line in metadata.splitlines()
                                 if line.startswith("tools:"))
                    value = field.split(":", 1)[1].strip()
                if scope is F.NORMAL and provider.provider == "copilot":
                    self.assertEqual(field, 'tools: ["read", "edit", "search", "execute"]')
                # Private adapters begin with safe provider/scope labels, not
                # instructions. Test their actual guard prompt, not those
                # intended status-only report words.
                prompt = (body.strip().splitlines()[0] if scope is F.NORMAL else
                          next(line for line in body.splitlines()
                               if line.startswith("Runtime guard:")))
                payloads.extend((field, value, prompt, raw))
        for index, raw in enumerate(payloads):
            for encoded in (raw.encode(), json.dumps({"detail": raw}).encode()):
                for channel in ("stdout", "stderr"):
                    # Stop immediately if accepted: accept() restores the tree,
                    # so continuing would no longer exercise an active case.
                    with self.assertRaises(AssertionError, msg=f"payload {index} {channel}"):
                        case.accept(**{channel: encoded})
        F.assert_private_output(case, b"Provider: claude\nScope: global\ninstalled\n", b"")
        case.accept(json.dumps(str(case.project)).encode())
        self.completed.add(6)

    def test_07_adopted_git_root_and_nongit_cohorts_match_frozen_contexts(self):
        s = self.session
        before_counts = s.counts.copy()
        for name in ("adopted-baseline-not-ownership", "pre-snapshot-no-git",
                     "v1-no-git", "absent", "path-with-spaces",
                     "path-with-control-characters"):
            with self.subTest(row=name):
                case = s.begin(name)
                expected = case.expected()
                adopted = name == "adopted-baseline-not-ownership"
                self.assertEqual(expected.context, "git-root" if adopted else "non-git")
                result = s.run(["git", "-C", case.requested, "rev-parse",
                                "--show-toplevel", "--is-inside-work-tree"], check=False)
                if adopted:
                    self.assertTrue((case.project / ".git").is_dir())
                    self.assertEqual(result.returncode, 0)
                    self.assertEqual(result.stdout,
                                     (expected.resolved_directory + "\ntrue\n").encode())
                else:
                    self.assertFalse((case.project / ".git").exists())
                    self.assertEqual(result.returncode, 128)
                    self.assertEqual(result.stdout, b"")
                case.accept()
        self.assertEqual(s.counts, before_counts)
        self.completed.add(7)

    def test_08_baseline_assertions_reject_misconstructed_witnesses(self):
        s = self.session
        before_counts = s.counts.copy()
        for name in ("unsafe-hardlink", "corrupt-baseline", "missing-baseline",
                     "normal-missing-manifest", "normal-corrupt-manifest",
                     "private-missing-manifest", "private-corrupt-manifest"):
            with self.subTest(row=name):
                case = s.begin(name)
                self.assert_baseline_witnesses(case)
                base = case.project / ".claude/.domestique/base/.claude/agents/implementer.md"
                if name == "unsafe-hardlink":
                    leaf = case.project / ".claude/agents/implementer.md"
                    leaf.unlink()
                    # Reproduce the former live/base alias, not an external link.
                    os.link(base, leaf)
                else:
                    path = (case.project / (".domestique-private/manifest"
                                           if name.startswith("private-") else
                                           ".claude/.domestique/manifest")
                            if "manifest" in name else base)
                    path.write_bytes(s.pristine[str(path.relative_to(s.root))].data)
                with self.assertRaises(AssertionError):
                    self.assert_baseline_witnesses(case, s.snapshot())
                # Explicit recovery after the fault assertion, never acceptance.
                s.restore(s.snapshot())
        self.assertEqual(s.counts, before_counts)
        self.completed.add(8)


if __name__ == "__main__":
    sys.exit(F.qualification_main("inspect-fixture-tests.py"))
