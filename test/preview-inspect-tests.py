"""Serial read-only installed fixtures; fake executable and mock I/O proof only."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "preview"))
import footprint as F
import machine as M
from native import LEAVES
from project_data import RECEIPT

spec = importlib.util.spec_from_file_location("project_fixtures", ROOT / "test/preview-project-tests.py")
PF = importlib.util.module_from_spec(spec)
spec.loader.exec_module(PF)


class PreviewInspectTests(unittest.TestCase):
    run_raw = classmethod(PF.PreviewProjectTests.run_raw.__func__)
    git = classmethod(PF.PreviewProjectTests.git.__func__)
    repo = classmethod(PF.PreviewProjectTests.repo.__func__)
    setUp = PF.PreviewProjectTests.setUp
    command = PF.PreviewProjectTests.command

    @classmethod
    def setUpClass(cls):
        PF.PreviewProjectTests.setUpClass.__func__(cls)
        cls.bin = cls.base / "isolated-bin"
        cls.bin.mkdir()
        for tool in ("python3", "bash", "git", "dirname"):
            (cls.bin / tool).symlink_to(shutil.which(tool))
        cls.log = cls.base / "FORBIDDEN-CALL"
        for tool in ("bd", "copilot", "claude", "codex", "mcp"):
            fake = cls.bin / tool
            fake.write_text("#!" + sys.executable + "\nimport os\nfrom pathlib import Path\n"
                            "Path(os.environ['INSPECT_CALL_LOG']).write_text('forbidden')\n"
                            "raise SystemExit(99)\n")
            fake.chmod(0o700)
        cls.env.update(PATH=str(cls.bin), INSPECT_CALL_LOG=str(cls.log))

    def tearDown(self):
        self.assertFalse(self.log.exists(), "inspect invoked a native/model/Beads executable")
        self.assertEqual(PF.snapshot(self.source), self.protected_source)
        self.assertEqual(PF.snapshot(self.b), self.untouched_b)

    def inspect(self, *args, code=0, cwd=None):
        before = PF.snapshot(self.base)
        result = self.command(*args, code=code, cwd=cwd)
        after = PF.snapshot(self.base)
        self.assertEqual(after, before, "read-only call changed fixture bytes/modes/paths")
        print("INSPECT_SNAPSHOT " + json.dumps({
            "before": PF.fingerprint(before), "after": PF.fingerprint(after)}), flush=True)
        return result

    def test_absent_aliases_and_exact_grammar(self):
        for form in ("inspect", "--inspect"):
            for args in ((form,), (form, self.a)):
                output = self.inspect(*args)
                self.assertIn("Preview activation: absent", output)
                self.assertIn("Selected shared revision (current):", output)
                self.assertIn("Workflow readiness: NOT CHECKED", output)
                self.assertEqual(output.count("absent (not owned)"), 7)
            for tail in (("",), ("--dry-run",), (self.a, "extra"), (self.a, "--ready")):
                self.inspect(form, *tail, code=2)
        before = PF.snapshot(self.base)
        output = self.run_raw([sys.executable, "-I", "-S", "-B",
                               self.source / "preview/cli.py", "inspect", self.a], self.a, 1)
        self.assertIn("Source checkout is not installation", output)
        self.assertEqual(PF.snapshot(self.base), before)

    def test_active_edited_role_and_creation_hashes_across_update(self):
        self.command("enable")
        record = (self.a / RECEIPT).read_bytes()
        output = self.inspect("inspect")
        self.assertIn("Preview activation: active", output)
        self.assertEqual(output.count(": unchanged"), 7)
        # Inspection requires reads, not lifecycle write permission.
        readonly = (self.a, self.a / ".github/agents", self.a / ".git/info/exclude")
        modes = {path: path.stat().st_mode & 0o777 for path in readonly}
        for path, mode in modes.items():
            path.chmod(mode & ~0o222)
        try:
            self.assertIn("Preview activation: active", self.inspect("--inspect"))
        finally:
            for path, mode in modes.items():
                path.chmod(mode)
        role = self.a / LEAVES["implementer"]
        role.write_bytes(b"---\nmodel: [OPAQUE-METADATA-DO-NOT-DUMP\n---\ncustom body\xff")
        output = self.inspect("--inspect", self.a)
        self.assertIn(f'{F.display(LEAVES["implementer"])}: customized', output)
        self.assertNotIn("OPAQUE-METADATA", output)
        self.command("update", "--ref", self.second)
        output = self.inspect("inspect", self.a)
        self.assertIn(self.second, output)
        self.assertEqual(output.count(": unchanged"), 6)
        self.assertIn(": customized", output)
        self.assertEqual((self.a / RECEIPT).read_bytes(), record)
        # Even a retained old CLI reports machine/current, not its own source as current.
        before = PF.snapshot(self.base)
        old = self.machine_root / "releases" / self.first / "preview/cli.py"
        output = self.run_raw([sys.executable, "-I", "-S", "-B", old, "--inspect", self.a], self.a)
        self.assertIn(self.second, output)
        self.assertEqual(PF.snapshot(self.base), before)

    def test_missing_owned_file(self):
        self.command("enable")
        (self.a / LEAVES["reviewer"]).unlink()
        output = self.inspect("--inspect", code=1)
        self.assertIn(f'{F.display(LEAVES["reviewer"])}: missing', output)
        self.assertIn("Preview activation: partial/unknown", output)
        self.assertNotIn("Preview activation: active", output)

    def test_setup_confirmation_separate_from_creation(self):
        self.command("enable")
        output = self.inspect("inspect")
        self.assertIn("Role model setup: unconfirmed", output)
        PF.setup_models(self)
        output = self.inspect("inspect")
        self.assertEqual(output.count(": customized"), 2)
        self.assertIn("Role model setup: confirmed file pair/receipt (not native evidence)", output)
        role = self.a / LEAVES["reviewer"]
        role.write_bytes(role.read_bytes() + b"\nUser edits stay owned.\n")
        output = self.inspect("inspect")
        self.assertIn("Role model setup: unconfirmed", output)
        self.assertIn("Preview activation: active", output)
        PF.setup_models(self)
        record = json.loads((self.a / RECEIPT).read_bytes())
        self.assertFalse(record["files"][LEAVES["reviewer"]]["model_setup"]["removable"])
        self.assertIn("confirmed file pair", self.inspect("inspect"))

    def test_legacy_and_ambiguous_evidence(self):
        (self.a / ".domestique-private/v2").mkdir(parents=True)
        (self.a / ".claude").mkdir()
        (self.a / ".codex").mkdir()
        policy = self.a / "CLAUDE.md"
        policy.write_text("# Domestique legacy reference\nPRIVATE-POLICY-NOT-OUTPUT\n")
        self.git(self.a, "add", "--", "CLAUDE.md")
        (self.a / ".github/skills/domestique").mkdir(parents=True)
        output = self.inspect("inspect")
        self.assertIn("legacy/experimental named footprint; generation unknown", output)
        self.assertIn("mode: tracked evidence", output)
        self.assertIn('".codex": provider container only', output)
        self.assertIn("untracked is not proof of guest", output)
        self.assertNotIn("PRIVATE-POLICY", output)
        self.assertIn("Preview activation: absent", output)
        # A receipt from another generation is not an active preview.
        (self.a / RECEIPT).write_text('{"kind": "old-ABI", "metadata": "PRIVATE-RECEIPT"}')
        output = self.inspect("--inspect", code=1)
        self.assertIn("incompatible or foreign receipt", output)
        self.assertNotIn("PRIVATE-RECEIPT", output)

    def test_partial_corrupt_missing_receipt_and_exclusion(self):
        self.command("enable")
        path = self.a / RECEIPT
        original = path.read_bytes()
        for content in (b"{PRIVATE-RECEIPT", b"[]",
                        original.replace(b'"active"', b'"partial-enable"'),
                        original.replace(b'"active"', b'"disabled"')):
            path.write_bytes(content)
            output = self.inspect("inspect", code=1)
            self.assertIn("Preview activation: partial/unknown", output)
            self.assertNotIn("PRIVATE-RECEIPT", output)
        path.write_bytes(original)
        exclude = self.a / ".git/info/exclude"
        original_exclude = exclude.read_bytes()
        exclude.write_bytes(b"# edited prefix\n" + original_exclude)
        self.assertIn("Git-common exclusion: unknown", self.inspect("--inspect", code=1))
        exclude.write_bytes(original_exclude)
        path.unlink()
        output = self.inspect("inspect", code=1)
        self.assertIn("unknown (unowned file)", output)
        self.assertIn("Preview activation: partial/unknown", output)

    def test_receipt_missing_required_nullable_fields(self):
        self.command("enable")
        path = self.a / RECEIPT
        original = path.read_bytes()
        # Nullable values are allowed in partial receipts; missing keys are not.
        # Both fields otherwise pass get(...)-based validation before indexing.
        for section, field in (("files", "sha256"), ("exclusion", "identity")):
            record = json.loads(original)
            record["metadata"] = "PRIVATE-RECEIPT-NOT-OUTPUT"
            item = (next(iter(record["files"].values())) if section == "files"
                    else record["exclusion"])
            del item[field]
            path.write_text(json.dumps(record))
            for form in ("inspect", "--inspect"):
                with self.subTest(section=section, field=field, form=form):
                    output = self.inspect(form, self.a, code=1)
                    self.assertIn("Selected shared revision (current):", output)
                    self.assertIn("Receipt " + F.display(RECEIPT) + ": unknown", output)
                    self.assertIn("Preview activation: partial/unknown", output)
                    self.assertIn("Workflow readiness: NOT CHECKED", output)
                    self.assertNotIn("Preview activation: active", output)
                    self.assertNotIn("Traceback", output)
                    self.assertNotIn("KeyError", output)
                    self.assertNotIn("PRIVATE-RECEIPT", output)

    def test_closed_inventory_discriminator(self):
        self.command("enable")
        path = self.a / RECEIPT
        original = path.read_bytes()
        for layout in (None, "unknown", "missing"):
            record = json.loads(original)
            if layout == "missing":
                del record["inventory"]  # Cannot relabel seven files as legacy five.
            else:
                record["inventory"] = layout
            path.write_text(json.dumps(record))
            output = self.inspect("inspect", code=1)
            self.assertIn("Receipt " + F.display(RECEIPT) + ": unknown", output)
            for args in (("enable",), ("disable",),
                         ("workflow", "goal", "--project", self.a)):
                before = PF.snapshot(self.base)
                self.command(*args, code=1)
                self.assertEqual(PF.snapshot(self.base), before)

    def test_unavailable_unsafe_and_unreadable_targets(self):
        sub = self.a / "sub"
        sub.mkdir()
        nongit = self.area / "non-git"
        nongit.mkdir()
        alias = self.area / "alias"
        alias.symlink_to(self.a, target_is_directory=True)
        for target in (self.area / "missing", self.a / "host.txt", sub, nongit, alias):
            output = self.inspect("inspect", target, code=1)
            self.assertIn("Target: refused", output)
            self.assertNotIn("Preview activation: absent", output)
        self.inspect("--inspect", code=1, cwd=sub)
        before = PF.snapshot(self.base)
        original_mode = self.a.stat().st_mode & 0o777
        self.a.chmod(0o300)
        try:
            # Actual mode gate; snapshot before/after with owner access restored.
            output = self.command("inspect", self.a, code=1)
            self.assertIn("unreadable", output)
        finally:
            self.a.chmod(original_mode)
        self.assertEqual(PF.snapshot(self.base), before)
        # Deterministic PermissionError, not a claim about privileged OS enforcement.
        before = PF.snapshot(self.base)
        with patch.dict(os.environ, self.env, clear=True):
            source = M.resolve_source(self.machine_root)
            receipt = M.check_install(self.machine_root, source)
            with patch.object(F, "target_identity", side_effect=PermissionError("PRIVATE-ERROR")):
                code, output = F.report(self.a, self.machine_root, receipt)
            self.assertEqual(code, 1)
            self.assertIn("unavailable/unreadable", output)
            self.assertNotIn("PRIVATE-ERROR", output)
        self.assertEqual(PF.snapshot(self.base), before)
        self.command("enable")
        before = PF.snapshot(self.base)
        read = F.read_bytes
        def denied(path, *args):
            if path == self.a / LEAVES["implementer"]:
                raise PermissionError("PRIVATE-METADATA")
            return read(path, *args)
        with patch.dict(os.environ, self.env, clear=True), patch.object(F, "read_bytes", side_effect=denied):
            code, output = F.report(self.a, self.machine_root, receipt)
        self.assertEqual(code, 1)
        self.assertIn("unknown (unsafe/unreadable file)", output)
        self.assertNotIn("PRIVATE-METADATA", output)
        self.assertEqual(PF.snapshot(self.base), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
