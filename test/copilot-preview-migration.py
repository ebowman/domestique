"""Real five/seven preview creation -> standalone cutover; offline only."""
import importlib.util
import io
import json
from pathlib import Path
import shlex
import subprocess
import sys
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("preview_project_fixture", ROOT / "test/preview-project-tests.py")
F = importlib.util.module_from_spec(spec)
spec.loader.exec_module(F)
DOM = ROOT / "domestique.sh"
ARCHIVE = ".domestique-private/copilot-preview-migration"
STATE = ".github/.domestique"
SHARED = ".agents/skills/dom-goal/SKILL.md"


def timeout_output(output):
    """Retain bounded head/tail progress from these generated fixture logs."""
    if output is None:
        return "<no output captured>"
    if isinstance(output, bytes):
        output = output.decode("utf-8", errors="replace")
    if not output:
        return "<empty output>"
    if len(output) > 4096:
        return (output[:2048] + f"\n<{len(output) - 4096} characters omitted>\n"
                + output[-2048:])
    return output


class Migration(F.PreviewProjectTests):
    def enable(self, root=None, five=False):
        root = root or self.a
        if five:
            self.command("update", "--ref", self.legacy)
        self.command("enable", root)
        if five:
            self.command("update", "--ref", self.first)
            self.host = F.snapshot(self.home)
        record = self.receipt(root)
        self.assertEqual(len(record["files"]), 5 if five else 7)
        return record

    def dom(self, *flags, root=None, script=None, stdin=False, ok=True):
        root = root or self.a
        argv = ["bash", "-s", "--"] if stdin else ["bash", str(script or DOM)]
        command = [*argv, str(root), *flags]
        started = time.monotonic()
        try:
            result = subprocess.run(command, cwd=self.area, env=self.env,
                                    input=DOM.read_text() if stdin else None,
                                    capture_output=True, text=True, timeout=60)
        except subprocess.TimeoutExpired as exc:
            raise AssertionError(
                f"Installer timeout: scenario={self.id()}\n"
                f"command={shlex.join(command)}\n"
                f"timeout={exc.timeout}s elapsed={time.monotonic() - started:.3f}s\n"
                f"stdout:\n{timeout_output(exc.stdout)}\n"
                f"stderr:\n{timeout_output(exc.stderr)}"
            ) from exc
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertRegex(result.stderr, "REFUSED/PARTIAL|preflight|interrupted")
        return result

    def assert_cutover(self, root, source):
        self.assertFalse((root / F.RECEIPT).exists())
        self.assertTrue((root / STATE / "manifest").is_file())
        self.assertTrue((root / ARCHIVE / "complete").is_file())
        for rel, data in source.items():
            self.assertEqual((root / ARCHIVE / "source" / rel).read_bytes(), data)
        for kind in ("dom-goal", "dom-decompose"):
            self.assertFalse((root / ".github/skills" / kind).exists())
        for rel in F.LEAVES.values():
            path = root / rel
            if path.exists():
                data = path.read_bytes()
                self.assertNotIn(str(self.launcher).encode(), data)
                if rel.startswith(".github/agents/"):
                    self.assertNotIn(b"# domestique-model-setup:", data)
                self.assertIn(b"Copilot only;", data)
        self.assertTrue((root / SHARED).is_file())
        exclude = (root / ".git/info/exclude").read_bytes()
        self.assertNotIn(b"# domestique-copilot-preview ", exclude)
        self.assertNotIn(b"/.github/skills/dom-goal/", exclude)
        self.assertNotIn(b"/.domestique-private/copilot-preview.json", exclude)
        self.assertIn(("/" + ARCHIVE + "/\n").encode(), exclude)

    def test_migration_pristine_five_and_seven(self):
        for five in (True, False):
            root = self.area / ("five" if five else "seven")
            self.repo(root)
            record = self.enable(root, five)
            source = {rel: (root / rel).read_bytes() for rel in (*record["files"], F.RECEIPT)}
            before = F.snapshot(root)
            preview = self.dom("--dry-run", root=root)
            self.assertEqual(F.snapshot(root), before)
            self.assertIn(f"{len(record['files'])} definitions", preview.stdout)
            self.assertIn("pair UNCONFIRMED", preview.stdout)
            self.dom(root=root)
            self.assert_cutover(root, source)
            self.assertEqual((root / STATE / "mode").read_bytes(), b"guest\n")
            before = F.snapshot(root)
            self.dom(root=root)
            self.assertEqual(F.snapshot(root), before)

    def test_migration_configured_metadata_normal_and_guest(self):
        for five, normal in ((True, True), (False, False)):
            root = self.area / ("normal-five" if five else "guest-seven")
            self.repo(root)
            record = self.enable(root, five)
            host = root / ".github/copilot-instructions.md"
            host.write_bytes(b"Host instructions; no Domestique ownership.\n")
            self.git(root, "add", ".github/copilot-instructions.md")
            expected = {}
            for role in F.S.ROLES:
                path = root / F.LEAVES[role]
                text = path.read_text()
                description = ("Copilot only; never match in Claude, Codex or an unknown harness. "
                               "Host-specific review discovery.")
                if role == "reviewer":
                    line = next(line for line in text.splitlines() if line.startswith("description:"))
                    text = text.replace(line, "description: " + json.dumps(description) + " # description note")
                extra = ("# native metadata comment\n"
                         "custom_native_scalar: 'keep exact ''quoting''' # inline\n"
                         'tools: ["read", "search"]\n'
                         "another-native-field: plain value # untouched\n")
                path.write_text(text.replace("\n---\n", "\n" + extra + "---\n", 1))
                expected[role] = extra.encode()
            F.setup_models(self, root, implementer="fixture-native-selected", reviewer="inherit")
            source = {rel: (root / rel).read_bytes() for rel in (*record["files"], F.RECEIPT)}
            flags = ("--platform", "copilot", "--no-guest") if normal else ("--platform", "copilot", "--guest")
            before = F.snapshot(root)
            self.dom(*flags, "--dry-run", root=root)
            self.assertEqual(F.snapshot(root), before)
            self.dom(*flags, "--force", root=root)
            self.assert_cutover(root, source)
            for role in F.S.ROLES:
                path = root / F.LEAVES[role]
                data = path.read_bytes()
                self.assertIn(expected[role], data)
                if role == "implementer":
                    self.assertIn(b'model: "fixture-native-selected"\n', data)
                else:
                    self.assertNotIn(b"\nmodel:", data)
                    self.assertIn(b"# description note\n", data)
                pristine = (root / STATE / "base" / F.LEAVES[role]).read_bytes()
                self.assertNotIn(b"fixture-native-selected", pristine)
                self.assertNotIn(expected[role], pristine)
            if normal:
                self.assertTrue(host.read_bytes().startswith(b"Host instructions; no Domestique ownership.\n"))
            else:
                self.assertEqual(host.read_bytes(), b"Host instructions; no Domestique ownership.\n")
            self.assertEqual(self.git(root, "check-ignore", ARCHIVE + "/plan.json").strip(),
                             ARCHIVE + "/plan.json")

    def test_migration_unsupported_states_refuse_before_all_writes(self):
        cases = ("malformed", "unknown", "duplicate", "wrong-project", "copied-receipt",
                 "body", "role-name", "description", "complex", "effort", "duplicate-field",
                 "invalid-scalar", "reasoning-effort", "wrong-path", "tools-complex",
                 "shared", "shared-directory", "legacy", "alias-extra", "alias-edit",
                 "symlink", "native-temp", "exclude-temp", "shared-exclude", "END-only")
        for case in cases:
            with self.subTest(case=case):
                root = self.area / case
                self.repo(root)
                self.enable(root)
                receipt = root / F.RECEIPT
                role = root / F.LEAVES["implementer"]
                if case == "malformed":
                    receipt.write_bytes(b"{")
                elif case in ("unknown", "wrong-project", "wrong-path"):
                    record = self.receipt(root)
                    if case == "unknown":
                        record["inventory"] = "experimental"
                    elif case == "wrong-project":
                        record["project"]["root"] = str(self.b)
                    else:
                        record["files"]["../wrong"] = next(iter(record["files"].values()))
                    receipt.write_text(json.dumps(record))
                elif case == "duplicate":
                    receipt.write_text(receipt.read_text().replace('"kind":', '"kind": "duplicate", "kind":'))
                elif case == "copied-receipt":
                    data = receipt.read_bytes()
                    receipt.rename(receipt.with_suffix(".original"))
                    receipt.write_bytes(data)
                    # Keep the original outside the authority directory.
                    receipt.with_suffix(".original").rename(root / "saved-receipt")
                elif case == "body":
                    role.write_bytes(role.read_bytes() + b"\nIntentional custom prompt.\n")
                elif case == "role-name":
                    role.write_text(role.read_text().replace("name: domestique-v2-copilot-implementer", "name: custom"))
                elif case == "description":
                    role.write_text(role.read_text().replace(
                        "Implement one caller-assigned Domestique task.", "Unscoped custom description."))
                elif case in ("complex", "effort", "duplicate-field", "invalid-scalar",
                              "reasoning-effort", "tools-complex"):
                    extra = {"complex": "custom: {nested: value}\n", "effort": "effort: high\n",
                             "reasoning-effort": "model_reasoning_effort: high\n",
                             "tools-complex": 'tools: [["nested"]]\n',
                             "duplicate-field": "model: a\nmodel: b\n",
                             "invalid-scalar": "custom: value:\n"}[case]
                    role.write_text(role.read_text().replace("\n---\n", "\n" + extra + "---\n", 1))
                elif case in ("shared", "shared-directory"):
                    path = root / SHARED
                    path.parent.mkdir(parents=True)
                    if case == "shared":
                        path.write_bytes(b"unowned shared skill\n")
                elif case == "legacy":
                    (root / ".domestique-private/v2").mkdir()
                elif case == "alias-extra":
                    (root / ".github/skills/dom-goal/custom.md").write_text("Keep me\n")
                elif case == "alias-edit":
                    path = root / ".github/skills/dom-goal/SKILL.md"
                    path.write_bytes(path.read_bytes() + b"\nCustom alias.\n")
                elif case == "symlink":
                    original = role.read_bytes()
                    role.unlink()
                    (root / "role-source").write_bytes(original)
                    role.symlink_to(root / "role-source")
                elif case in ("native-temp", "exclude-temp"):
                    directory = role.parent if case == "native-temp" else root / ".git/info"
                    (directory / ".copilot-migration-interrupted").write_bytes(b"retain staging bytes\n")
                else:
                    exclude = root / ".git/info/exclude"
                    extra = (b"# END domestique\n" if case == "END-only" else
                             b"# domestique-copilot-preview BEGIN foreign\n")
                    exclude.write_bytes(exclude.read_bytes() + extra)
                before = F.snapshot(root)
                for flags in (("--dry-run",), (), ("--force",)):
                    self.dom(*flags, root=root, ok=False)
                    self.assertEqual(F.snapshot(root), before, case)

    def test_migration_source_independent_stdin(self):
        self.enable()
        source = {rel: (self.a / rel).read_bytes() for rel in (*self.receipt()["files"], F.RECEIPT)}
        absent = []
        try:
            for path in (self.machine_root, self.source):
                moved = path.with_name(path.name + "-unavailable")
                path.rename(moved)
                absent.append((path, moved))
            self.dom("--platform", "copilot", stdin=True)
        finally:
            for path, moved in reversed(absent):
                moved.rename(path)
        self.assert_cutover(self.a, source)

    def test_migration_exact_exclude_union_and_other_providers(self):
        self.enable()
        self.dom("--platform", "both", "--guest")
        # An existing ownership marker, not a real Beads invocation.
        (self.a / ".claude/.domestique/beads-owned").write_bytes(b"")
        exclude = self.a / ".git/info/exclude"
        exclude.write_bytes(exclude.read_bytes() + b"# host suffix\nhost-unrelated/\n")
        providers = {rel: F.snapshot(self.a / rel) for rel in (".claude", ".codex", ".beads")}
        self.dom("--platform", "copilot")
        for rel, before in providers.items():
            # Existing additive selection records the new provider set and
            # synchronizes Beads ownership; all other provider bytes stay put.
            after = F.snapshot(self.a / rel)
            if rel == ".codex":
                after.pop(".domestique/beads-owned", None)
            if rel != ".beads":
                self.assertEqual((self.a / rel / ".domestique/platforms").read_bytes(),
                                 b"claude,codex,copilot\n")
                after.pop(".domestique/platforms")
                before.pop(".domestique/platforms")
            self.assertEqual(set(after), set(before), rel)
            for path, value in before.items():
                self.assertEqual(after[path], value, f"{rel}/{path}")
        data = exclude.read_text()
        self.assertTrue(data.startswith("# host excludes\n"))
        self.assertIn("# host suffix\nhost-unrelated/\n", data)
        body = data.split("# BEGIN domestique (managed)\n")[1].split("# END domestique\n")[0]
        expected = {"CLAUDE.local.md", ".claude/", ".beads/", ".agents/.domestique/"}
        expected.update((self.a / ".codex/.domestique/guest-excludes").read_text().splitlines())
        expected.update((self.a / STATE / "guest-excludes").read_text().splitlines())
        expected.update((self.a / ".agents/.domestique/guest-excludes").read_text().splitlines())
        self.assertEqual(set(body.splitlines()), expected)
        self.assertEqual(len(body.splitlines()), len(expected), "no duplicate excludes")

    def test_migration_failed_and_interrupted_cutover_resumes(self):
        for failure in ("receipt-revoked", "role-published", "interrupted"):
            root = self.area / failure
            self.repo(root)
            record = self.enable(root)
            source = {rel: (root / rel).read_bytes() for rel in (*record["files"], F.RECEIPT)}
            script = self.area / (failure + ".sh")
            text = DOM.read_text()
            if failure == "receipt-revoked":
                anchor = '        # Publish only after project receipt revocation.'
                injection = '        raise OSError("fixture cutover failure after revocation")\n'
            else:
                anchor = '                atomic(root / rel, data, plan["output"][rel]["mode"])'
                injection = ("\n                os._exit(19)" if failure == "interrupted" else
                             '\n                raise OSError("fixture cutover failure after role")')
            self.assertEqual(text.count(anchor), 1)
            text = text.replace(anchor, injection + anchor if failure == "receipt-revoked" else anchor + injection)
            script.write_text(text)
            result = self.dom("--platform", "copilot", root=root, script=script, ok=False)
            self.assertIn("partial", result.stderr.lower())
            self.assertFalse((root / F.RECEIPT).exists())
            self.assertTrue((root / ARCHIVE / "plan.json").is_file())
            self.assertEqual(self.git(root, "check-ignore", ARCHIVE + "/plan.json").strip(),
                             ARCHIVE + "/plan.json")
            for kind in ("dom-decompose", "dom-goal"):
                rel = F.LEAVES[kind]
                if (root / rel).exists():
                    self.assertEqual(self.git(root, "check-ignore", rel).strip(), rel)
            before = F.snapshot(root)
            self.dom("--platform", "copilot", "--dry-run", root=root)
            self.assertEqual(F.snapshot(root), before)
            self.dom("--platform", "copilot", root=root)
            self.assert_cutover(root, source)

    def test_migration_partial_customization_is_not_overwritten(self):
        self.enable()
        script = self.area / "fails.sh"
        anchor = '        # Publish only after project receipt revocation.'
        script.write_text(DOM.read_text().replace(anchor, '        raise OSError("fixture stop")\n' + anchor))
        self.dom("--platform", "copilot", script=script, ok=False)
        self.assertFalse((self.a / F.RECEIPT).exists())
        self.assertTrue((self.a / ARCHIVE / "plan.json").is_file())
        path = self.a / F.LEAVES["reviewer"]
        path.write_bytes(path.read_bytes() + b"\nIntentional edit during recovery.\n")
        before = F.snapshot(self.a)
        self.dom("--platform", "copilot", ok=False)
        self.assertEqual(F.snapshot(self.a), before)
        path.write_bytes((self.a / ARCHIVE / "source" / F.LEAVES["reviewer"]).read_bytes())
        (self.a / ARCHIVE / "unknown-leftover").write_bytes(b"must remain\n")
        before = F.snapshot(self.a)
        self.dom("--platform", "copilot", "--dry-run", ok=False)
        self.assertEqual(F.snapshot(self.a), before)

    def test_migration_partial_snapshot_directory_ownership(self):
        script = self.area / "receipt-revoked.sh"
        anchor = '        # Publish only after project receipt revocation.'
        text = DOM.read_text()
        self.assertEqual(text.count(anchor), 1)
        script.write_text(text.replace(anchor, '        os._exit(19)\n' + anchor))
        cases = ("empty", "nonempty", "nested", "unknown-symlink",
                 "expected-symlink", "wrong-ancestor", "wrong-leaf", "valid-ancestry")
        for case in cases:
            with self.subTest(case=case):
                root = self.area / case
                self.repo(root)
                record = self.enable(root)
                source = {rel: (root / rel).read_bytes() for rel in (*record["files"], F.RECEIPT)}
                self.dom("--platform", "copilot", root=root, script=script, ok=False)
                self.assertFalse((root / F.RECEIPT).exists())
                self.assertTrue((root / ARCHIVE / "plan.json").is_file())
                self.assertFalse((root / ARCHIVE / "complete").exists())

                outside = self.area / (case + "-outside")
                outside.mkdir()
                (outside / "victim").write_bytes(b"outside bytes must remain\n")
                ancestor = root / STATE / "base/.github/agents"
                if case in ("empty", "nonempty"):
                    unknown = root / STATE / "unknown-custom-directory"
                    unknown.mkdir(parents=True)
                    if case == "nonempty":
                        (unknown / "custom.txt").write_bytes(b"retain custom contents\n")
                elif case == "nested":
                    unknown = ancestor / "unknown/nested"
                    unknown.mkdir(parents=True)
                elif case == "unknown-symlink":
                    ancestor.mkdir(parents=True)
                    (ancestor / "unknown").symlink_to(outside, target_is_directory=True)
                elif case == "expected-symlink":
                    ancestor.parent.mkdir(parents=True)
                    ancestor.symlink_to(outside, target_is_directory=True)
                elif case == "wrong-ancestor":
                    ancestor.parent.mkdir(parents=True)
                    ancestor.write_bytes(b"directory ancestry is not a file\n")
                elif case == "wrong-leaf":
                    (root / STATE / "base" / F.LEAVES["implementer"]).mkdir(parents=True)
                else:
                    # Empty expected ancestry is a legitimate interrupted stage,
                    # not a reason to require every future snapshot file now.
                    for rel in record["files"]:
                        if "/dom-" not in rel:
                            (root / STATE / "base" / rel).parent.mkdir(parents=True, exist_ok=True)

                def evidence():
                    return F.snapshot(self.area), {
                        str(path.relative_to(self.area)): (
                            path.lstat().st_dev, path.lstat().st_ino,
                            path.lstat().st_mode, path.lstat().st_mtime_ns)
                        for path in self.area.rglob("*")
                    }

                before = evidence()
                self.dom("--platform", "copilot", "--dry-run", root=root,
                         ok=case == "valid-ancestry")
                self.assertEqual(evidence(), before, "dry-run changed project or outside victim")
                self.assertFalse((root / ARCHIVE / "complete").exists())
                self.dom("--platform", "copilot", root=root, ok=case == "valid-ancestry")
                if case == "valid-ancestry":
                    self.assert_cutover(root, source)
                    self.assertEqual((outside / "victim").read_bytes(), b"outside bytes must remain\n")
                else:
                    self.assertEqual(evidence(), before, "refusal changed project or outside victim")
                    self.assertFalse((root / ARCHIVE / "complete").exists())


class DomDiagnostics(unittest.TestCase):
    def setUp(self):
        # Only exercise dom(); never initialize the real installer fixture.
        self.migration = Migration("test_migration_pristine_five_and_seven")
        self.migration.a = Path("/fixture/seven")
        self.migration.area = Path("/fixture")
        self.migration.env = {"FIXTURE_PRIVATE_SENTINEL": "must-not-appear"}

    def run_timeout(self, stdout, stderr, **flags):
        command = ["bash", str(DOM), "/fixture/seven"]
        timeout = subprocess.TimeoutExpired(command, 60, output=stdout, stderr=stderr)
        caught = []

        def scenario():
            try:
                self.migration.dom(**flags)
            except AssertionError as exc:
                caught.append(exc)
                raise

        stream = io.StringIO()
        with mock.patch.object(subprocess, "run", side_effect=timeout) as run, \
                mock.patch.object(time, "monotonic", side_effect=[100, 160.125]):
            result = unittest.TextTestRunner(stream=stream).run(
                unittest.FunctionTestCase(scenario))
        self.assertFalse(result.wasSuccessful())
        self.assertEqual(len(result.failures), 1)
        self.assertIs(caught[0].__cause__, timeout)
        run.assert_called_once_with(command, cwd=self.migration.area,
                                    env=self.migration.env, input=None,
                                    capture_output=True, text=True, timeout=60)
        diagnostic = stream.getvalue()
        self.assertIn("scenario=" + self.migration.id(), diagnostic)
        self.assertIn("command=" + shlex.join(command), diagnostic)
        self.assertIn("timeout=60s elapsed=60.125s", diagnostic)
        self.assertNotIn("must-not-appear", diagnostic)
        return diagnostic

    def test_timeout_partial_output_is_emitted_and_bounded(self):
        for as_bytes in (True, False):
            with self.subTest(as_bytes=as_bytes):
                stdout = "begin\n" + "x" * 5000 + "\nlast phase"
                stderr = "warning: \ufffd"
                if as_bytes:
                    stdout = stdout.encode()
                    stderr = b"warning: \xff"
                diagnostic = self.run_timeout(stdout, stderr)
                self.assertIn("stdout:\nbegin\n", diagnostic)
                self.assertIn("<921 characters omitted>", diagnostic)
                self.assertIn("\nlast phase\nstderr:\nwarning: \ufffd", diagnostic)
                self.assertNotIn("x" * 2049, diagnostic)
                self.assertLess(len(diagnostic), 8000)

    def test_timeout_without_output_still_fails_even_when_nonzero_expected(self):
        diagnostic = self.run_timeout(None, None, ok=False)
        self.assertIn("stdout:\n<no output captured>", diagnostic)
        self.assertIn("stderr:\n<no output captured>", diagnostic)
        diagnostic = self.run_timeout(b"", "")
        self.assertIn("stdout:\n<empty output>", diagnostic)
        self.assertIn("stderr:\n<empty output>", diagnostic)

    def test_completed_success_and_nonzero_handling_unchanged(self):
        for code, ok, stderr, fails in (
                (0, True, "", False),
                (3, False, "REFUSED/PARTIAL: fixture", False),
                (3, True, "REFUSED/PARTIAL: fixture", True),
                (0, False, "", True),
                (3, False, "unexpected fixture failure", True)):
            with self.subTest(code=code, ok=ok, stderr=stderr):
                completed = subprocess.CompletedProcess([], code, "fixture output", stderr)
                with mock.patch.object(subprocess, "run", return_value=completed) as run:
                    if fails:
                        with self.assertRaises(AssertionError):
                            self.migration.dom(ok=ok)
                    else:
                        self.assertIs(self.migration.dom(ok=ok), completed)
                run.assert_called_once()
                self.assertEqual(run.call_args.kwargs["timeout"], 60)


if __name__ == "__main__":
    suite = unittest.TestSuite(Migration(name) for name in sorted(dir(Migration))
                               if name.startswith("test_migration_"))
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(DomDiagnostics))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(not result.wasSuccessful())
