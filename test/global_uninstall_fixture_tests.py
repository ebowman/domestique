"""Fast stdlib regressions; no production commands, native clients or network."""
import ast
from contextlib import redirect_stdout, redirect_stderr
import io
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import types
import unittest
import sys
from unittest.mock import patch

from global_uninstall_fixture import SyntheticTree


def discard_test_tree(root):
    """Explicit observed synthetic leaves only; also handles refused test states."""
    if root.is_symlink() or not root.is_dir():
        root.unlink(missing_ok=True)
        return
    root.chmod(0o700)
    for child in root.iterdir():
        discard_test_tree(child)
    root.rmdir()


def fault_namespace():
    # Exercise the actual suite context manager without running top-level cold
    # cases or parsing CLI args recursively. Only setup is synthetic in units.
    path = Path(__file__).with_name("global-uninstall.py")
    source = ast.parse(path.read_text())
    names = {"check", "snapshot", "clean", "fixture", "FaultFixture"}
    nodes = [n for n in source.body if isinstance(n, (ast.Import, ast.ImportFrom)) or
             isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    ns = {"__file__": str(path), "COUNT": 0, "EXECUTED": [],
          "SETUP_COMMANDS": {"global_install": 0, "local_install": 0, "git_init": 0},
          "ARGS": types.SimpleNamespace(fixture_mode="reuse")}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), ns)
    return ns


class ResetTests(unittest.TestCase):
    def setUp(self):
        self.roots = []
        self.root = self.new_root()
        (self.root / "dir").mkdir()
        self.leaf = self.root / "dir/leaf"
        self.leaf.write_bytes(b"pristine synthetic bytes\n")
        self.leaf.chmod(0o640)
        (self.root / "link").symlink_to("dir/leaf")

    def new_root(self):
        root = Path(tempfile.mkdtemp(prefix=SyntheticTree.PREFIX)).resolve()
        self.roots.append(root)
        return root

    def tearDown(self):
        for root in reversed(self.roots):
            if root.exists() or root.is_symlink():
                discard_test_tree(root)

    def test_mutation_isolation_metadata_and_root_identity(self):
        for p in (self.leaf, self.root / "link", self.root / "dir", self.root):
            os.utime(p, ns=(1_700_000_000_123456789,) * 2, follow_symlinks=False)
        tree = SyntheticTree(self.root)
        identity = self.root.stat().st_ino
        directory_identity = (self.root / "dir").stat().st_ino
        with self.assertRaises(TypeError):
            tree.pristine[Path("new")] = None
        for _ in range(2):
            tree.begin()
            self.leaf.write_bytes(b"changed")
            self.leaf.chmod(0o600)
            (self.root / "extra").mkdir()
            (self.root / "extra/file").write_text("synthetic evidence")
            (self.root / "link").unlink()
            tree.accept()
            tree.restore()
            self.assertEqual(tree._scan(payload=True), tree.pristine)
            self.assertEqual(self.root.stat().st_ino, identity)
            self.assertEqual((self.root / "dir").stat().st_ino, directory_identity)
            self.assertFalse((self.root / "extra").exists())

    def test_missing_paths_and_file_directory_symlink_type_changes(self):
        tree = SyntheticTree(self.root)
        self.leaf.unlink()
        self.leaf.mkdir()
        (self.leaf / "child").write_bytes(b"mutation")
        (self.root / "link").unlink()
        (self.root / "link").mkdir()
        tree.accept()
        tree.restore()
        self.assertEqual(self.leaf.read_bytes(), b"pristine synthetic bytes\n")
        self.assertTrue((self.root / "link").is_symlink())
        self.leaf.unlink()
        (self.root / "dir").rmdir()
        tree.accept()
        tree.restore()
        self.assertTrue(self.leaf.is_file())

    def test_external_symlink_never_followed(self):
        external = self.new_root() / "sentinel"
        external.write_bytes(b"outside synthetic sentinel")
        tree = SyntheticTree(self.root)
        self.leaf.unlink()
        self.leaf.symlink_to(external)
        tree.accept()
        tree.restore()
        self.assertEqual(external.read_bytes(), b"outside synthetic sentinel")
        self.assertFalse(self.leaf.is_symlink())

    def test_dangling_pristine_symlink_metadata(self):
        (self.root / "dangling").symlink_to("absent")
        tree = SyntheticTree(self.root)
        (self.root / "dangling").unlink()
        tree.accept()
        tree.restore()
        self.assertEqual(tree._scan(payload=True), tree.pristine)

    def test_unasserted_case_never_restored_or_cleaned(self):
        tree = SyntheticTree(self.root)
        self.leaf.write_bytes(b"failed-case-evidence")
        for operation in (tree.restore, tree.clean):
            with self.assertRaisesRegex(RuntimeError, "evidence retained"):
                operation()
            self.assertEqual(self.leaf.read_bytes(), b"failed-case-evidence")

    def test_post_assertion_change_refuses_before_any_deletion(self):
        for change in ("extra", "missing", "content", "mode"):
            with self.subTest(change=change):
                tree = SyntheticTree(self.root)
                tree.accept()
                if change == "extra":
                    (self.root / "extra").write_bytes(b"new")
                elif change == "missing":
                    self.leaf.unlink()
                elif change == "content":
                    self.leaf.write_bytes(b"new content")
                else:
                    self.leaf.chmod(0o600)
                with self.assertRaisesRegex(ValueError, "after case assertions"):
                    tree.restore()
                self.assertTrue((self.root / "link").is_symlink())
                (self.root / "extra").unlink(missing_ok=True)
                self.leaf.write_bytes(b"pristine synthetic bytes\n")
                self.leaf.chmod(0o640)

    def test_db_and_hardlinks_refused_at_capture_and_accept(self):
        for name in (".beads", ".dolt", "state.db", "state.sqlite3", "state.db-wal"):
            with self.subTest(name=name):
                tree = SyntheticTree(self.root)
                path = self.root / name
                path.mkdir()
                with self.assertRaisesRegex(ValueError, "database"):
                    SyntheticTree(self.root)
                with self.assertRaisesRegex(ValueError, "database"):
                    tree.accept()
                path.rmdir()
        tree = SyntheticTree(self.root)
        os.link(self.leaf, self.root / "hardlink")
        for operation in (lambda: SyntheticTree(self.root), tree.accept):
            with self.assertRaisesRegex(ValueError, "hardlinked"):
                operation()

    def test_unknown_kind_and_permission_refusal(self):
        tree = SyntheticTree(self.root)
        fifo = self.root / "fifo"
        os.mkfifo(fifo)
        for operation in (lambda: SyntheticTree(self.root), tree.accept):
            with self.assertRaisesRegex(ValueError, "unknown fixture file kind"):
                operation()
        fifo.unlink()
        for path in (self.leaf, self.root / "dir"):
            mode = stat.S_IMODE(path.stat().st_mode)
            path.chmod(0)
            with self.assertRaises(PermissionError):
                tree.accept()
            path.chmod(mode)

    def test_unsafe_roots_refused(self):
        for root in (Path("/"), Path.home(), self.root / "dir",
                     Path(os.path.relpath(self.root))):
            with self.subTest(root=root), self.assertRaises(ValueError):
                SyntheticTree(root)
        alias = self.new_root() / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            SyntheticTree(alias)
        self.root.chmod(0o755)
        with self.assertRaises(ValueError):
            SyntheticTree(self.root)

    def test_root_swap_and_symlink_refuse_without_touching_target(self):
        tree = SyntheticTree(self.root)
        tree.accept()
        moved = self.root.with_name(self.root.name + "-saved")
        self.root.rename(moved)
        self.roots.append(moved)
        self.root.mkdir(mode=0o700)
        with self.assertRaisesRegex(ValueError, "root changed"):
            tree.restore()
        self.root.rmdir()
        self.root.symlink_to(moved, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "root changed"):
            tree.restore()
        self.assertTrue((moved / "dir/leaf").is_file())

    def test_pinned_home_core_project_root_generation_is_required(self):
        tree = SyntheticTree(self.root, roots=("dir",))
        tree.accept()
        (self.root / "dir").rename(self.root / "saved")
        with self.assertRaises(FileNotFoundError):
            tree.restore()
        (self.root / "dir").mkdir()
        with self.assertRaisesRegex(ValueError, "pinned fixture root changed"):
            tree.restore()
        self.assertEqual((self.root / "saved/leaf").read_bytes(), b"pristine synthetic bytes\n")

    def test_restore_unlink_write_and_metadata_errors_propagate(self):
        for method in ("unlink", "open", "utime"):
            with self.subTest(method=method):
                tree = SyntheticTree(self.root)
                tree.accept()
                if method == "utime":
                    target = patch("global_uninstall_fixture.os.utime",
                                   side_effect=PermissionError("injected"))
                elif method == "open":
                    original = Path.open

                    def failing_open(path, mode="r", *args, **kwargs):
                        if mode == "xb":
                            raise PermissionError("injected")
                        return original(path, mode, *args, **kwargs)

                    target = patch.object(Path, "open", failing_open)
                else:
                    target = patch.object(Path, method, side_effect=PermissionError("injected"))
                with target, self.assertRaisesRegex(PermissionError, "injected"):
                    tree.restore()
                # Explicit test reconciliation only AFTER error assertions.
                (self.root / "dir").mkdir(exist_ok=True)
                self.leaf.write_bytes(b"pristine synthetic bytes\n")
                if not (self.root / "link").is_symlink():
                    (self.root / "link").symlink_to("dir/leaf")

    def test_cleanup_requires_success_and_retains_external_target(self):
        external = self.new_root() / "sentinel"
        external.write_text("outside")
        (self.root / "outside-link").symlink_to(external)
        tree = SyntheticTree(self.root)
        tree.accept()
        tree.clean()
        self.assertFalse(self.root.exists())
        self.assertEqual(external.read_text(), "outside")

    def pool(self):
        ns = fault_namespace()
        pool = ns["FaultFixture"]()

        def setup(group):
            root = ns["W"]
            self.roots.append(root)
            (root / "synthetic").write_bytes(b"pristine")
            pool.protected = ([root / "synthetic"], [ns["snapshot"](root / "synthetic")])
            pool.tree = SyntheticTree(root)

        pool.setup = setup
        return ns, pool

    def test_actual_case_context_failure_does_not_restore(self):
        ns, pool = self.pool()
        with self.assertRaisesRegex(AssertionError, "case assertion"):
            with pool.case("journal", "synthetic"):
                (ns["W"] / "synthetic").write_bytes(b"evidence")
                raise AssertionError("case assertion")
        with self.assertRaisesRegex(RuntimeError, "evidence retained"):
            pool.close()
        self.assertEqual((ns["W"] / "synthetic").read_bytes(), b"evidence")

    def test_forbidden_call_marker_refuses_before_reset(self):
        ns, pool = self.pool()
        with self.assertRaisesRegex(AssertionError, "zero native/network/Beads"):
            with pool.case("journal", "synthetic"):
                ns["LOG"].write_text("called")
        with self.assertRaisesRegex(RuntimeError, "evidence retained"):
            pool.tree.restore()
        self.assertEqual(ns["LOG"].read_text(), "called")
        # Finish suspended fixture context while asserting its independent guard.
        with self.assertRaises(AssertionError):
            pool.context.__exit__(None, None, None)

    def test_every_forbidden_stub_blocks_actual_case_under_curated_environment(self):
        import acceptance
        outer = self.new_root()
        env = acceptance.environment(outer, native=False)
        forbidden = ("bd", "beads", "claude", "codex", "copilot", "curl", "wget")
        self.assertEqual({p.name for p in (outer / "forbidden").iterdir()}, set(forbidden))
        for mode in ("fresh", "reuse"):
            for command in forbidden:
                with self.subTest(mode=mode, command=command), \
                        patch.dict(os.environ, env, clear=True):
                    ns, pool = self.pool()
                    ns["ARGS"].fixture_mode = mode
                    with self.assertRaisesRegex(
                            AssertionError, "case made zero native/network/Beads calls before reset"):
                        with pool.case("journal", f"synthetic-{command}"):
                            stub = ns["W"] / "forbidden" / command
                            self.assertEqual(shutil.which(command, path=ns["ENV"]["PATH"]),
                                             str(stub))
                            self.assertEqual(
                                ns["ENV"]["PATH"].split(os.pathsep)[:2],
                                [str(stub.parent), str(outer / "forbidden")])
                            result = subprocess.run(
                                [command, "synthetic-payload-must-not-be-logged"],
                                env=ns["ENV"], cwd=ns["W"], capture_output=True,
                                text=True, timeout=10)
                            self.assertEqual(result.returncode, 99)
                            self.assertEqual(result.stdout + result.stderr, "")
                            self.assertTrue(ns["LOG"].is_file())
                            self.assertEqual(ns["LOG"].read_text(), "called")
                    self.assertEqual(ns["EXECUTED"], [])
                    self.assertEqual(pool.samples, [])
                    self.assertIsNone(pool.tree.observed)
                    for operation in (pool.tree.restore, pool.tree.clean):
                        with self.assertRaisesRegex(RuntimeError, "evidence retained"):
                            operation()
                        self.assertEqual(ns["LOG"].read_text(), "called")
                    # The outer fixture's independent marker gate also propagates;
                    # only tearDown reconciles evidence after all refusal checks.
                    with self.assertRaisesRegex(AssertionError, "zero native/network/Beads"):
                        pool.context.__exit__(None, None, None)
                    self.assertEqual(ns["LOG"].read_text(), "called")

    def test_actual_case_context_reuses_only_after_assertions(self):
        ns, pool = self.pool()
        with pool.case("core", "synthetic-first"):
            root = ns["W"]
            inode = root.stat().st_ino
            (root / "synthetic").write_bytes(b"changed")
        with pool.case("core", "synthetic-second"):
            self.assertEqual(root, ns["W"])
            self.assertEqual(root.stat().st_ino, inode)
            self.assertEqual((root / "synthetic").read_bytes(), b"pristine")
        pool.close()
        self.assertFalse(root.exists())
        self.assertEqual(len(pool.samples), 2)

    def test_fresh_case_context_repeats_setup_at_distinct_roots(self):
        ns, pool = self.pool()
        ns["ARGS"].fixture_mode = "fresh"
        with pool.case("core", "synthetic-first"):
            first = ns["W"]
        self.assertFalse(first.exists())
        with pool.case("core", "synthetic-second"):
            self.assertNotEqual(first, ns["W"])
        self.assertIsNone(pool.tree)

    def test_cli_inventory_selection_and_refusal_before_fixtures(self):
        path = Path(__file__).with_name("global-uninstall.py")
        nodes = []
        for node in ast.parse(path.read_text()).body:
            if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and
                    isinstance(node.value.func, ast.Name) and node.value.func.id == "self_tests"):
                break
            nodes.append(node)
        preamble = compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec")

        def cli(args, status=None):
            ns = {"__file__": str(path)}
            with patch.object(sys, "argv", [str(path), *args]), \
                    patch("tempfile.mkdtemp", side_effect=AssertionError("fixture before selection")), \
                    redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()):
                if status is None:
                    exec(preamble, ns)
                else:
                    with self.assertRaises(SystemExit) as result:
                        exec(preamble, ns)
                    self.assertEqual(result.exception.code, status)
            return ns, out.getvalue()

        ns, listing = cli(["--list"], 0)
        self.assertEqual(len(ns["IDS"]), 67)
        self.assertEqual(len(set(ns["IDS"])), 67)
        self.assertEqual(len(ns["core_faults"]), 24)
        self.assertEqual(len(ns["journal_faults"]), 15)
        self.assertIn("PARTIAL", listing)
        cases = ["core:native:current/API:edit", "core:previous:old/API:edit"]
        for mode in ("fresh", "reuse"):
            ns, _ = cli(["--fixture-mode", mode, "--case", cases[0], "--case", cases[1]])
            self.assertEqual(ns["SELECTED"], set(cases))
            self.assertEqual(ns["ARGS"].fixture_mode, mode)
        for args in (["--case", "unknown"], ["--case", cases[0], "--case", cases[0]],
                     ["--self-test", "--case", cases[0]], ["--list", "--self-test"],
                     ["--fixture-mode", "unknown"]):
            cli(args, 2)
        ns, _ = cli([])
        self.assertEqual(ns["SELECTED"], set(ns["IDS"]))
        self.assertEqual(ns["ARGS"].fixture_mode, "reuse")

    def test_unchanged_acceptance_rejects_every_partial_summary(self):
        import acceptance
        for summary in (
            "global-uninstall PARTIAL: inventory only (67 cases); no execution\n",
            "global-uninstall PARTIAL: synthetic self-tests only; no production cases\n",
            "global-uninstall PARTIAL: 100 checks passed; selected cases only\n",
        ):
            with self.assertRaises(ValueError):
                acceptance.offline_report("global-uninstall.py", summary, "", 0)
        self.assertEqual(acceptance.offline_report(
            "global-uninstall.py",
            "global-uninstall: 100 checks passed (current source; isolated, no native clients)\n",
            "", 0)["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
