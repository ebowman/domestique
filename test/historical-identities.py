"""Historical inventory unit and isolated execution tests (stdlib only)."""
import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "historical_identities", ROOT / "tools/historical-identities.py")
HISTORY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HISTORY)


class HistoricalIdentities(unittest.TestCase):
    def test_policy_body_matches_installer_awk_bytes(self):
        body = b"\n# policy\r\nmodel: opus\n\n"
        data = b"host prefix\n" + HISTORY.BEGIN + b"\n" + body + HISTORY.END + b"\nhost tail\n"
        actual = subprocess.run(
            ["awk", "-v", "beginm=" + HISTORY.BEGIN.decode(),
             "-v", "endm=" + HISTORY.END.decode(),
             "$0 == beginm && !seen { seen=1; inblock=1; next } "
             "inblock && $0 == endm { inblock=0; next } inblock { print }"],
            input=data, capture_output=True, check=True, timeout=10).stdout
        self.assertEqual(HISTORY.policy_body(data), actual)
        self.assertEqual(actual, body)

    def test_rejects_ambiguous_policy_markers(self):
        for data in (b"", HISTORY.BEGIN, HISTORY.END + b"\n" + HISTORY.BEGIN,
                     HISTORY.BEGIN + b"\n" + HISTORY.BEGIN + b"\n" + HISTORY.END,
                     HISTORY.BEGIN + b"\r\nx\n" + HISTORY.END):
            with self.subTest(data=data), self.assertRaises(ValueError):
                HISTORY.policy_body(data)

    def test_only_explicit_capability_rejection_is_unsupported(self):
        for message in ("Unknown option: --guest", "Unknown option: --platform",
                        "Error: --platform must be one of: claude, codex, both",
                        "Invalid --platform"):
            result = dict(returncode=2, stdout="", stderr=message, timeout=False)
            self.assertEqual(HISTORY.outcome(result), "unsupported")
            result["returncode"] = 1
            self.assertEqual(HISTORY.outcome(result), "failure")
        for code, text, timeout in ((2, "private local: global runtime missing", False),
                                    (97, "blocked dependency", False),
                                    (None, "Unknown option: --guest", True)):
            self.assertEqual(HISTORY.outcome(dict(returncode=code, stdout=text,
                                                 stderr="", timeout=timeout)), "failure")

    def test_normalization_is_exact_and_preserves_models(self):
        path = ".claude/.domestique/manifest"
        data = b"installed_at=2026-11-07T21:00:00Z\nmodel=opus\nscript_sha256=abc\n"
        self.assertEqual(HISTORY.normalize(path, data),
                         b"installed_at=<UTC-INSTALL-TIME>\nmodel=opus\nscript_sha256=abc\n")
        self.assertEqual(HISTORY.normalize(".claude/agents/implementer.md", data), data)
        with self.assertRaises(ValueError):
            HISTORY.normalize(path, b"installed_at=unknown\n")
        with self.assertRaises(ValueError):
            HISTORY.normalize(path, data + data)

    def test_project_normalization_requires_exact_attested_marker(self):
        path = ".claude/agents/implementer.md"
        reviewer = b"---\nmodel: opus\n---\nreview\n"
        role = b"---\nmodel: sonnet\n---\nimplement\n"

        def marked(root, body=role):
            marker = {"v": 1, "project": str(root), "harness": "claude",
                      "implementer_sha256": HISTORY.sha(body),
                      "reviewer_sha256": HISTORY.sha(reviewer)}
            line = (b"# domestique-model-setup: " +
                    json.dumps(marker, sort_keys=True, separators=(",", ":")).encode() + b"\n")
            return body[:4] + line + body[4:]

        files = {path.replace("implementer", "reviewer"): (reviewer, 0o644)}
        first = HISTORY.normalize(path, marked("/first"), Path("/first"), files)
        second = HISTORY.normalize(path, marked("/second"), Path("/second"), files)
        self.assertEqual(first, second)
        self.assertIn(b"model: sonnet\n", first)
        self.assertIn(HISTORY.sha(role).encode(), first)
        self.assertIn(HISTORY.sha(reviewer).encode(), first)
        with self.assertRaises(ValueError):
            HISTORY.normalize(path, marked("/first"), Path("/second"), files)
        with self.assertRaises(ValueError):
            HISTORY.normalize(path, marked("/first").replace(b"model: sonnet", b"model: opus"),
                              Path("/first"), files)
        with self.assertRaises(ValueError):
            HISTORY.normalize(path, marked("/first"), Path("/first"), {})
        changed = HISTORY.normalize(path, marked("/first", role.replace(b"sonnet", b"opus")),
                                    Path("/first"), files)
        self.assertNotEqual(first, changed)

    def test_actual_execution_isolation_and_metadata_separation(self):
        script = """set -eu
test "$HOME" != /root
test -z "$(git config --global --list)"
mkdir -p .claude/agents .claude/.domestique
printf 'model: opus\\n' > .claude/agents/implementer.md
printf 'installed_at=2026-11-07T21:00:00Z\\n' > .claude/.domestique/manifest
"""
        with patch.dict("os.environ", {"BASH_ENV": "/does/not/exist", "GIT_DIR": "/invalid"}):
            record, artifacts = HISTORY.replay(script, "default", "normal", 10)
        self.assertEqual(record["status"], "success", record)
        self.assertEqual(len(artifacts), 2)
        metadata, role = artifacts
        self.assertEqual(metadata["kind"], "metadata")
        self.assertIsNone(metadata["sha256"])
        self.assertEqual(role["sha256"], HISTORY.sha(b"model: opus\n"))
        self.assertFalse(any(item["path"].startswith(".git/") for item in artifacts))

    def test_stub_invocation_cannot_report_success(self):
        record, _ = HISTORY.replay(
            "curl https://example.invalid || true\n"
            "mkdir -p .claude/agents\nprintf x > .claude/agents/implementer.md\n",
            "default", "normal", 10)
        self.assertEqual(record["status"], "failure")
        self.assertIn("blocked dependency invocation", record["errors"][0])
        self.assertNotIn("output_set", record)

    def test_unknown_output_is_a_failure(self):
        record, _ = HISTORY.replay("printf x > surprise.txt", "default", "normal", 10)
        self.assertEqual(record["status"], "failure")
        self.assertIn("unclassified installer output: surprise.txt", record["errors"])

    def test_timeouts_are_failures(self):
        record, _ = HISTORY.replay("while :; do :; done", "default", "normal", 1)
        self.assertEqual(record["status"], "failure")
        self.assertTrue(record["result"]["timeout"])

    def test_all_commit_provenance_retained_for_deduplicated_blobs(self):
        def fake_git(*args):
            if args[0] == "rev-parse":
                return (hashlib.sha1(b"blob 6\0script").hexdigest()
                        if args[-1].endswith(":domestique.sh")
                        else "pinned") + "\n"
            if args[0] == "log":
                return "first\nmiddle\nlast\n"
            if args[0] == "show":
                return "script"
            self.fail(args)

        artifact = {"provider": "claude", "path": "CLAUDE.md", "kind": "policy-body",
                    "sha256": HISTORY.REQUIRED, "output_sha256": "whole",
                    "permissions": 0o644, "normalization": None}

        def fake_replay(script, selector, mode, timeout):
            return {"selector": selector, "mode": mode, "status": "success"}, [artifact]

        with patch.object(HISTORY, "git", side_effect=fake_git), \
                patch.object(HISTORY, "allowlist", return_value={"claude": [HISTORY.REQUIRED]}), \
                patch.object(HISTORY, "replay", side_effect=fake_replay) as replay:
            data = HISTORY.generate("main", "HEAD", 10)
        self.assertEqual(replay.call_count, 12)
        self.assertEqual(data["dimensions"]["commits"], 3)
        for item in data["identities"]:
            self.assertEqual(item["first_commit"], "first")
            self.assertEqual(item["last_commit"], "last")
            self.assertEqual(item["commits"], ["first", "middle", "last"])
        self.assertTrue(data["required_policy_present"])
        self.assertEqual(data["unreproduced_allowlist"], {"claude": []})

    def test_checked_in_history_and_authority_are_complete(self):
        data = json.loads((ROOT / "tools/historical-identities.json").read_text())
        commits = HISTORY.git("log", "--full-history", "--topo-order", "--reverse",
                              "--format=%H", data["history_ref"], "--",
                              "domestique.sh").splitlines()
        self.assertEqual([item["commit"] for item in data["history"]], commits)
        self.assertEqual({c for run in data["runs"] for c in run["commits"]}, set(commits))
        self.assertEqual(data["allowlist"], HISTORY.allowlist(
            HISTORY.git("show", data["allowlist_ref"] + ":domestique.sh")))
        self.assertTrue(data["required_policy_present"])
        for run in data["runs"]:
            if run["status"] == "success":
                artifacts = data["output_sets"][run["output_set"]]
                self.assertEqual(HISTORY.sha(HISTORY.encoded(artifacts)), run["output_set"])
            else:
                self.assertNotIn("output_set", run)


if __name__ == "__main__":
    unittest.main()
