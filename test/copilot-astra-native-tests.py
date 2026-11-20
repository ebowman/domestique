"""Deterministic harness checks only: no model calls and no native PASS claims."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "native", Path(__file__).with_name("copilot-astra-native.py"))
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


class Harness(unittest.TestCase):
    def test_contract_matches_emission(self):
        contract = native.contract_bytes(native.SOURCE.read_bytes())
        body = b"emit_completion_contract() { cat <<'DOM_EOF'\n" + contract
        body += b"DOM_EOF\n}\nemit_completion_contract\n"
        self.assertEqual(contract, subprocess.check_output(["bash"], input=body))
        with self.assertRaises(ValueError):
            native.contract_bytes(b"not a contract")

    def test_tool_scope(self):
        for case in "ABCDE":
            args = native.argv_for(Path("/cli"), case, Path("/case"), Path("/usage"), "prompt")
            self.assertNotIn("--allow-all", args)
            self.assertIn("--no-custom-instructions", args)
            self.assertIn("--disable-builtin-mcps", args)
            self.assertEqual("bash" in args, case in "ADE")
            self.assertEqual("--deny-tool" in args, case == "E")
            if case in "BC":
                self.assertFalse(any(arg.startswith("shell(") for arg in args))
            self.assertIn("read(/case/**)", args)

    def test_explicit_a_config_grant_only(self):
        fixed = (Path("/cli"), "A", Path("/case"), Path("/usage"), "prompt")
        default = native.argv_for(*fixed)
        approved = native.argv_for(*fixed, allow_local_config_read=True)
        self.assertNotIn("shell(git config)", default)
        self.assertEqual(approved.count("shell(git config)"), 1)
        self.assertEqual([a for a in approved if a != "shell(git config)"], default)
        self.assertIn("`git config --local --list`", native.LOCAL_CONFIG_READ)
        self.assertIn("Do not read other configuration scopes or change any configuration",
                      native.LOCAL_CONFIG_READ)
        expected_e = default.copy()
        expected_e[-2:-2] = ["--deny-tool", "shell(git commit)"]
        self.assertEqual(native.argv_for(Path("/cli"), "E", Path("/case"),
                                        Path("/usage"), "prompt"), expected_e)
        for case in "BCDE":
            with self.assertRaises(ValueError):
                native.argv_for(Path("/cli"), case, Path("/case"), Path("/usage"),
                                "prompt", allow_local_config_read=True)

    def test_approved_run_executes_only_a_and_records_provenance(self):
        # Stub model execution only; all fixture/Git/evidence operations are real.
        with tempfile.TemporaryDirectory() as directory:
            cli = Path(directory) / "fake-cli"
            cli.write_text("synthetic runtime entry, not executable\n")
            real_run = subprocess.run

            def version_or_git(args, **kwargs):
                if args == [str(cli), "--version"]:
                    return subprocess.CompletedProcess(args, 0, b"GitHub Copilot CLI 1.0.114.\n", b"")
                return real_run(args, **kwargs)

            with patch.object(native.subprocess, "run", side_effect=version_or_git), \
                    patch.object(native, "execute", return_value=(
                        {"exit": 0, "timed_out": False, "duration_seconds": 0}, b"", b"")) as execute, \
                    patch.object(native.tempfile, "mkdtemp", side_effect=[
                        str(Path(directory) / "evidence"), str(Path(directory) / "fixture")]):
                (Path(directory) / "evidence").mkdir()
                (Path(directory) / "fixture").mkdir()
                output = native.run(cli, Path(directory), approved_a_read_only_inspection="Synthetic approval")
            execute.assert_called_once()
            self.assertIn("shell(git config)", execute.call_args.args[0])
            self.assertIn("shell(git hash-object)", execute.call_args.args[0])
            self.assertIn(native.FIXTURE_READ_INSTRUCTIONS, execute.call_args.args[0][-1])
            report = json.loads((output / "report.json").read_text())
            self.assertEqual(report["operator_approval"]["provenance"], "Synthetic approval")
            for case in "BCDE":
                self.assertEqual(report["scenarios"][case]["status"], "NOT RUN")
                self.assertFalse((output / case).exists())
            with self.assertRaises(ValueError):
                native.run(cli, Path(directory), approved_a_local_config_read=" ")

    def test_finite_read_grants_preserve_default_and_e(self):
        fixed = (Path("/cli"), "A", Path("/case"), Path("/usage"), "prompt")
        local = native.argv_for(*fixed, allow_local_config_read=True)
        expanded = native.argv_for(*fixed, allow_local_config_read=True,
                                   allow_fixture_inspection=True)
        expected = {
            "shell(git " + sub + ")" for sub in (
                "hash-object", "cat-file", "ls-tree", "diff-tree", "diff-index",
                "diff-files", "rev-list", "branch", "for-each-ref", "show-ref",
            )
        }
        self.assertEqual(set(expanded) - set(local), expected)
        self.assertEqual([arg for arg in expanded if arg not in expected], local)
        self.assertNotIn("shell(git:*)", expanded)
        self.assertNotIn("shell", expanded)
        self.assertNotIn("--allow-all", expanded)
        self.assertIn("hash-object WITHOUT -w", native.FIXTURE_READ_INSTRUCTIONS)
        self.assertIn("Configuration inspection remains ONLY `git config --local --list`",
                      native.FIXTURE_READ_INSTRUCTIONS)
        for case in "BCDE":
            with self.assertRaises(ValueError):
                native.argv_for(Path("/cli"), case, Path("/case"), Path("/usage"),
                                "prompt", allow_local_config_read=True,
                                allow_fixture_inspection=True)
        e = native.argv_for(Path("/cli"), "E", Path("/case"), Path("/usage"), "prompt")
        self.assertFalse(expected.intersection(e))
        self.assertEqual(e[e.index("--deny-tool") + 1], "shell(git commit)")
        with self.assertRaises(ValueError):
            native.argv_for(*fixed, allow_fixture_inspection=True)

    def test_fixture_and_artifact_verifier(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            env, overrides = native.environment(base / "home")
            self.assertEqual(overrides["GIT_CONFIG_GLOBAL"], "/dev/null")
            root = base / "repo"
            native.setup(root, env)
            before = native.snapshot(root, env, include_local_config=True)
            self.assertTrue(all(native.artifact_checks("D", root, env, before, before).values()))
            self.assertFalse(all(native.artifact_checks("A", root, env, before, before).values()))
            # Harness-generated synthetic commit, NOT native action evidence.
            native.git(root, env, "add", "--", "owned.txt")
            native.git(root, env, "commit", "-q", "--only", "-m", "fixture-1", "--", "owned.txt")
            after = native.snapshot(root, env, include_local_config=True)
            self.assertTrue(all(native.artifact_checks("A", root, env, before, after).values()))
            self.assertFalse(all(native.artifact_checks("D", root, env, before, after).values()))
            self.assertFalse(native.artifact_checks("E", root, env, before, after)["head_unchanged"])
            (root / "unstaged.txt").write_text("corrupted\n")
            damaged = native.snapshot(root, env, include_local_config=True)
            self.assertFalse(native.artifact_checks("A", root, env, before, damaged)["unrelated_files_preserved"])
            damaged["index_files"]["staged.txt"] = b"corrupted\n".hex()
            damaged["local_config"] += "00"
            checks = native.artifact_checks("A", root, env, before, damaged)
            self.assertFalse(checks["unrelated_index_bytes_preserved"])
            self.assertFalse(checks["local_config_unchanged"])

    def test_capture_and_timeout(self):
        with tempfile.TemporaryDirectory() as directory:
            env, _ = native.environment(Path(directory) / "home")
            result, out, err = native.execute(
                [sys.executable, "-c", "print('captured')"], directory, env, deadline=5)
            self.assertEqual(result["exit"], 0)
            self.assertEqual(out, b"captured\n")
            self.assertEqual(err, b"")
            result, out, _ = native.execute(
                [sys.executable, "-u", "-c", "import time; print('partial'); time.sleep(10)"],
                directory, env, deadline=0.2)
            self.assertTrue(result["timed_out"])
            self.assertNotEqual(result["exit"], 0)
            self.assertEqual(out, b"partial\n")
            native.write_json(Path(directory) / "result.json", result)
            self.assertEqual(json.loads((Path(directory) / "result.json").read_text()), result)


if __name__ == "__main__":
    unittest.main()
