#!/usr/bin/env python3
"""Fresh actual Git index differential tests; faults are SYNTHETIC protocol only."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import local_index_baseline as oracle

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("acceptance", ROOT / "test/acceptance.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class Index(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Include the actual-Git diagnostic matrix and emitted-resolver replay.
        cls.control = runner.Control(240)
        cls.temp = tempfile.TemporaryDirectory(prefix="dom-index-")
        cls.work = Path(cls.temp.name).resolve()
        cls.env = runner.environment(cls.work)
        cls.current = runner.preview_fixture.source().decode()
        cls.sources = []
        for label, source in (("old", oracle.baseline(cls.current)), ("new", cls.current)):
            path = cls.work / (label + ".sh")
            path.write_text(source.split("\nusage()", 1)[0])
            cls.sources.append(path)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.repo = self.work / self._testMethodName
        self.repo.mkdir()
        self.git("init", "-q")
        blob = self.work / "blob"
        blob.write_text("fixture\n")
        self.oid = self.git("hash-object", "-w", str(blob)).strip()

    def git(self, *args):
        out, err, rc = runner.execute(
            ["git", "-C", str(self.repo), *args], self.env, 8, self.control)
        self.assertEqual(rc, 0, (out, err))
        return out

    def indexed(self, name, mode="100644"):
        # Index-only objects, deliberately absent from the worktree. Gitlinks
        # record opaque commit IDs; no commit/client/DB/network is needed.
        oid = "1" * 40 if mode == "160000" else self.oid
        self.git("update-index", "--add", "--cacheinfo", f"{mode},{oid},{name}")

    def guard(self, candidate="a/b/c", source=None, hook="", tail="", env=None):
        return runner.execute(
            ["/bin/bash", "-c", 'source "$1"\n' + hook +
             '\nlocal_untracked "$2" "$3"\n' + tail, "_",
             str(source or self.sources[1]), str(self.repo), candidate],
            env or self.env, 8, self.control)

    def compare(self, expected, candidate="a/b/c", diagnostic=None, sources=None, **kwargs):
        for source in sources or self.sources:
            with self.subTest(source=source.name, candidate=candidate, **kwargs):
                out, err, rc = self.guard(candidate, source=source, **kwargs)
                self.assertEqual(rc == 0, expected, (out, err))
                prefix = "domestique local: tracked/indexed destination or ancestor: "
                collisions = [line for line in err.splitlines() if line.startswith(prefix)]
                if diagnostic is not None:
                    self.assertEqual(collisions, [
                        f"{prefix}{self.repo}/{diagnostic}; stop other writers and resolve "
                        "this path manually before retrying (no force/adoption)."])
                elif expected:
                    self.assertEqual((out, err), ("", ""))

    def test_destination_descendants_and_every_exact_ancestor(self):
        for name in ("a", "a/b", "a/b/c", "a/b/c/child"):
            for mode in ("100644", "120000", "160000"):
                with self.subTest(name=name, mode=mode):
                    self.git("read-tree", "--empty")
                    self.indexed(name, mode)
                    self.compare(False, diagnostic=name if name in ("a", "a/b") else "a/b/c")

    def test_unrelated_siblings_and_prefixes(self):
        for name in ("a/sibling", "a/b/sibling", "a/b/cousin", "ab/c", "other"):
            self.indexed(name)
        self.compare(True)
        self.compare(False, "a", diagnostic="a")
        self.compare(False, "a/b", diagnostic="a/b")

    def test_literal_names(self):
        for outer in ("literal[ab]", "star*?", " space ", "back\\slash",
                      ":(glob)magic", "-dash", "quote'\""):
            candidate = outer + "/mid [x]/leaf\\*?"
            self.git("read-tree", "--empty")
            self.indexed(outer + "/mid [x]/sibling")
            self.compare(True, candidate)
            self.indexed(candidate)
            self.compare(False, candidate, diagnostic=candidate)
            self.git("read-tree", "--empty")
            self.indexed(outer + "/mid [x]", "120000")
            self.compare(False, candidate, diagnostic=outer + "/mid [x]")

    def test_opaque_unrelated_index_bytes(self):
        # execute decodes stdout, so only the guard reads these raw Git records.
        for name in ("a/new\nline", "a/b/tab\tname", "a/b/\udcff",
                     "a/b/雪", "a/b/back\\slash", "elsewhere/\udcfe\n"):
            self.indexed(name)
        self.compare(True)
        self.indexed("a/b/c")
        self.compare(False, diagnostic="a/b/c")

    def test_opaque_destination_descendants_report_only_destination(self):
        for name in ("new\nline", "tab\tname", "\udcff", "雪", "back\\slash", "\x7f"):
            for mode in ("100644", "120000", "160000"):
                with self.subTest(name=name, mode=mode):
                    self.git("read-tree", "--empty")
                    self.indexed("a/b/c/" + name, mode)
                    self.compare(False, diagnostic="a/b/c")

    def test_deleted_worktree_path_still_collides(self):
        leaf = self.repo / "a/b/c"
        leaf.parent.mkdir(parents=True)
        leaf.write_text("tracked")
        self.git("add", "--", "a/b/c")
        leaf.unlink()
        self.compare(False, diagnostic="a/b/c")

    def test_fresh_empty_changed_empty_consecutive_calls(self):
        hook = 'set +e\ngit() { printf "QUERY\\n" >&2; command git "$@"; }'
        tail = '''
first=$?
command git -C "$2" update-index --add --cacheinfo "100644,$OID,$3" || exit 9
local_untracked "$2" "$3"; second=$?
command git -C "$2" read-tree --empty || exit 9
local_untracked "$2" "$3"; third=$?
printf '%s %s %s\\n' "$first" "$second" "$third"
'''
        for source, count in zip(self.sources, (7, 3)):
            self.git("read-tree", "--empty")
            out, err, rc = self.guard(source=source, hook=hook, tail=tail,
                                      env=dict(self.env, OID=self.oid))
            self.assertEqual((out, rc), ("0 1 0\n", 0), err)
            self.assertEqual(err.count("QUERY\n"), count)

    def test_routing_overrides_even_empty(self):
        for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE"):
            for value in ("", "/nonexistent"):
                self.compare(False, env=dict(self.env, **{key: value}),
                             hook='git() { echo unexpected-query; return 0; }')
                self.assertEqual(self.guard(env=dict(self.env, **{key: value}))[0], "")

    def test_pathspec_overrides_and_case(self):
        for key in ("GIT_LITERAL_PATHSPECS", "GIT_GLOB_PATHSPECS",
                    "GIT_NOGLOB_PATHSPECS", "GIT_ICASE_PATHSPECS"):
            for value in ("", "0", "1"):
                out, err, rc = self.guard(env=dict(self.env, **{key: value}),
                                          hook='git() { echo unexpected-query; return 0; }')
                self.assertNotEqual(rc, 0, err)
                self.assertEqual(out, "")
        self.git("config", "core.ignorecase", "true")
        self.indexed("a/B/c")
        self.compare(True)  # Literal Git matching is byte-exact even on Darwin.
        self.indexed("a/b/c")
        self.compare(False, diagnostic="a/b/c")
        self.assertNotEqual(self.guard(hook="shopt -s nocasematch")[2], 0)

    def test_noncanonical_internal_inputs_refuse_before_query(self):
        for candidate in ("", "/a", "a/", "a//b", ".", "..", "./a", "../a",
                          "a/./b", "a/../b", "a/.", "a/..", "a\nb", "a\tb",
                          "a/\x7f", "a/é", "a/e\u0301", "a/\udcff"):
            out, err, rc = self.guard(candidate, hook="git() { echo unexpected-query; }")
            self.assertNotEqual(rc, 0, (candidate, err))
            self.assertEqual(out, "")

    def test_synthetic_protocol_failures(self):
        # Not native evidence: explicitly injected Git protocol corruption.
        for body in ("return 1", 'printf "a/b/sibling\\0"; return 1',
                     'printf "\\0"', 'printf "a/b/sibling"',
                     'printf "a/b/sibling\\0tail"', 'printf "a/b/sibling\\0\\0"',
                     'printf "outside\\0"', 'printf "a/../sibling\\0"',
                     'printf "/a/sibling\\0"', 'printf "a//sibling\\0"',
                     'printf "a/sibling/\\0"', 'printf "a/./sibling\\0"'):
            with self.subTest(body=body):
                out, err, rc = self.guard(hook="git() { " + body + "; }")
                self.assertNotEqual(rc, 0, (out, err))
                self.assertIn("index validation failed", err)
        for body in ("return 0", 'printf "a/b/sibling\\0"'):
            self.assertEqual(self.guard(hook="git() { " + body + "; }")[2], 0)

    def test_immutable_baseline_integrity_and_index_only_delta(self):
        old = oracle.baseline(self.current)
        self.assertEqual(old[:old.index(oracle.START)],
                         self.current[:self.current.index(oracle.START)])
        self.assertEqual(old[old.index(oracle.END):],
                         self.current[self.current.index(oracle.END):])
        fixture = oracle.FIXTURE.read_text()
        for bad in ("", fixture.replace("exact=0", "exact=1")):
            with mock.patch.object(Path, "read_text", return_value=bad):
                with self.assertRaises(ValueError):
                    oracle.baseline(self.current)
        with mock.patch.object(Path, "read_text", side_effect=FileNotFoundError):
            with self.assertRaises(FileNotFoundError):
                oracle.baseline(self.current)
        with self.assertRaises(ValueError):
            oracle.baseline(self.current.replace(oracle.END, "missing"))

    def test_standalone_resolver_emits_identical_guard(self):
        out, err, rc = runner.execute(
            ["/bin/bash", "-c", 'source "$1"; emit_private_core_resolver',
             "_", str(self.sources[1])], self.env, 8, self.control)
        self.assertEqual(rc, 0, err)
        resolver = self.work / "resolver.sh"
        resolver.write_text(out)
        self.assertEqual(out.count("local_untracked ()"), 1)
        # Source function definitions only, not the standalone CLI dispatcher.
        definitions = self.work / "resolver-definitions.sh"
        definitions.write_text(out[:out.index('\ncase "${1:-}"')])
        sources = [*self.sources, definitions]
        self.indexed("a/b/sibling")
        self.compare(True, sources=sources)
        for name in ("a", "a/b", "a/b/c", "a/b/c/child", "a/b/c/opaque\udcff\n\t"):
            for mode in ("100644", "120000", "160000"):
                with self.subTest(name=name, mode=mode):
                    self.git("read-tree", "--empty")
                    self.indexed(name, mode)
                    self.compare(False, diagnostic=name if name in ("a", "a/b") else "a/b/c",
                                 sources=sources)


if __name__ == "__main__":
    unittest.main()
