"""Historical inventory unit and isolated execution tests (stdlib only)."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
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


class EmbeddedIdentities(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / "tools/historical-identities.json").read_text())
        cls.source = (ROOT / "domestique.sh").read_text()
        cls.block = HISTORY.embedded_block(cls.source)
        cls.library = cls.block.split("cat <<'PY'\n", 1)[1].split("\nPY\n}", 1)[0]
        cls.namespace = {}
        exec(compile(cls.library, "embedded-identities", "exec"), cls.namespace)
        # Fresh all-provider emissions can exceed 60s under qualification load.
        cls.current = HISTORY.current_projection(cls.source, 300)

    def test_exact_drift_from_history_and_explicit_working_tree_source(self):
        self.assertEqual(self.block, HISTORY.lookup_block(self.data, self.current))

    def test_working_tree_and_head_current_emission_membership(self):
        lookup = self.namespace["installer_identity"]
        head = HISTORY.current_projection(HISTORY.git("show", "HEAD:domestique.sh"), 300)
        for name, identities in (("HEAD", head), ("working tree", self.current)):
            self.assertTrue(identities)
            for identity in identities:
                with self.subTest(source=name, identity=identity):
                    self.assertTrue(lookup(*identity))
            for provider in ("claude", "codex", "copilot"):
                self.assertTrue(any(i[0] == provider and
                                    ("/agents/implementer" in i[1] or
                                     "copilot-implementer" in i[1])
                                    for i in identities))
            self.assertFalse(any("model-setup.py" in i[1] or "/.domestique/" in i[1]
                                 for i in identities))

    def test_every_proven_raw_historical_identity_retained(self):
        lookup = self.namespace["installer_identity"]
        for item in self.data["identities"]:
            if HISTORY.authority_artifact(item):
                self.assertTrue(lookup(item["provider"], item["path"],
                                       item["mode"], item["sha256"]), item)

    def test_legacy_predicate_is_exactly_the_old_allowlist(self):
        self.assertEqual(HISTORY.allowlist(self.source), self.data["allowlist"])
        lookup = self.namespace["legacy_policy_identity"]
        for owner in ("claude", "codex", "copilot", "unknown"):
            for item in self.data["identities"]:
                self.assertEqual(lookup(owner, item["sha256"]),
                                 item["sha256"] in self.data["allowlist"].get(owner, ()))
            self.assertFalse(lookup(owner, "0" * 64))

    def test_missing_legacy_hash_aborts_instead_of_silently_dropping(self):
        data = copy.deepcopy(self.data)
        data["allowlist"]["claude"].append("0" * 64)
        with self.assertRaisesRegex(ValueError, "unreproduced legacy hashes"):
            HISTORY.lookup_block(data, self.current)

    def test_provider_path_mode_and_raw_normalized_boundaries(self):
        lookup = self.namespace["installer_identity"]
        identity = next(i for i in self.current if i[1] == "CLAUDE.local.md")
        self.assertTrue(lookup(*identity))
        owner, path, mode, digest = identity
        for wrong in (("codex", path, mode, digest),
                      (owner, "CLAUDE.md", mode, digest),
                      (owner, path, "normal", digest),
                      (owner, path, mode, "0" * 64)):
            self.assertFalse(lookup(*wrong), wrong)
        normalized = [i for i in self.data["identities"] if i["normalization"]]
        self.assertTrue(normalized)
        for item in normalized:
            self.assertFalse(lookup(item["provider"], item["path"],
                                    item["mode"], item["sha256"]), item)

    def test_failed_partial_and_unreferenced_sets_contribute_no_authority(self):
        data = copy.deepcopy(self.data)
        artifact = {"provider": "claude", "path": ".claude/commands/goal.md",
                    "kind": "file", "normalization": None, "sha256": "0" * 64}
        set_id = HISTORY.sha(HISTORY.encoded([artifact]))
        data["output_sets"][set_id] = [artifact]
        for status in ("failure", "unsupported"):
            data["runs"].append({"status": status, "mode": "normal",
                                 "partial_artifacts": [artifact], "output_set": set_id})
        data["identities"].append(artifact)
        self.assertEqual(HISTORY.historical_projection(data),
                         HISTORY.historical_projection(self.data))

    def test_policy_wrapper_hashes_exact_file_bytes(self):
        # Exercise the actual shell wrapper with a tiny injected shared library:
        # no text decoding, trimming, marker stripping or newline normalization.
        raw = b"raw policy\r\n\n"
        function = "policy_legacy_base() {" + self.source.split(
            "policy_legacy_base() {", 1)[1].split("\n}\n", 1)[0] + "\n}\n"
        library = ("emit_historical_identity_library() { cat <<'PY'\n"
                   "def legacy_policy_identity(provider, digest):\n"
                   f"    return provider == 'claude' and digest == '{HISTORY.sha(raw)}'\n"
                   "PY\n}\n")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "base"
            for content, owner, accepted in ((raw, "claude", True),
                                             (raw, "codex", False),
                                             (raw.rstrip(), "claude", False),
                                             (raw.replace(b"\r", b""), "claude", False)):
                path.write_bytes(content)
                result = subprocess.run(
                    ["bash", "-s", "--", owner, str(path)],
                    input=library + function + 'policy_legacy_base "$1" "$2"\n',
                    text=True, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0 if accepted else 1, result.stderr)


if __name__ == "__main__":
    unittest.main()
