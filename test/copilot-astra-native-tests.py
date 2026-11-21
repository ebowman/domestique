"""Deterministic harness checks only: no model calls and no native PASS claims."""
import argparse
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


GRAPH = ".beads/fixture-graph.json"
SKILL = ".github/skills/domestique-v2-copilot-{}/SKILL.md"
BRANCH = "fixture/handoff"


def handoff_case(out, case, cli=None):
    """Real installed instructions and Git. Graph, planner and gate inputs are simulations."""
    out.mkdir()
    home = out / "home"
    home.mkdir()
    env, overrides = native.environment(home / "copilot")
    (home / "copilot").mkdir()
    env["HOME"] = overrides["HOME"] = str(home)
    root = out / "project"
    root.mkdir()

    def git(*args):
        return native.git(root, env, *args)

    graph = root / GRAPH
    guest = case == "guest"
    git("init", "-q", "-b", BRANCH if case == "ready" else "main")
    # Pre-existing personal Beads exclusion, NOT installer ownership of host state.
    if guest:
        with (root / ".git/info/exclude").open("a") as f:
            f.write("\n.beads/\n")
    bindir = out / "bin"
    bindir.mkdir()
    (bindir / "python3").symlink_to(sys.executable)
    subprocess.run(["bash", str(native.SOURCE), str(root), "--platform", "copilot",
                    *(["--guest"] if guest else [])], cwd=root,
                   env=dict(env, PATH=f"{bindir}:/usr/bin:/bin:/usr/sbin:/sbin"),
                   check=True, capture_output=True, timeout=180)
    plan_path = root / SKILL.format("decompose")
    goal_path = root / SKILL.format("goal")
    plan = plan_path.read_text().split("## Workspace readiness handoff\n", 1)[1].split(
        "must recheck the actual checkout rather than replay the plan.", 1)[0]
    plan += "must recheck the actual checkout rather than replay the plan."
    assert plan in plan_path.read_text()
    completion = native.contract_bytes(native.SOURCE.read_bytes()).decode()
    assert completion.rstrip() in goal_path.read_text()
    graph.parent.mkdir(exist_ok=True)
    outside = {"id": "other", "parent": None, "needs": []}
    native.write_json(graph, [outside])
    for path in native.FILES:
        (root / path).write_text("base\n")
    git("add", ".")  # synthetic clean seed only
    git("commit", "-qm", "synthetic installed baseline")
    if guest:
        for path in (GRAPH, SKILL.format("goal")):
            assert git("check-ignore", path).strip() == path
            assert not git("ls-files", "--", path)
    if case not in ("ready", "stale-collision", "stale-disjoint"):
        (root / "staged.txt").write_text("unrelated staged\n")
        git("add", "--", "staged.txt")
        (root / "unstaged.txt").write_text("unrelated unstaged\n")
        (root / "notes.txt").write_text("unrelated untracked\n")
    target = "new.txt" if case in ("collision", "stale-collision") else "owned.txt"
    if case in ("overlap", "collision"):
        (root / target).write_text("user edit\n")
        if case == "overlap":
            git("add", "--", target)
            (root / target).write_text("later user edit\n")

    def observe(label):
        snap = native.snapshot(root, env, include_local_config=True)
        snap.update(branch=git("branch", "--show-current").strip(),
                    graph=json.loads(graph.read_text()), exclude=(root / ".git/info/exclude").read_text(),
                    tree={str(p.relative_to(root)): native.digest(p.read_bytes())
                          for p in root.rglob("*")
                          if ".git" not in p.relative_to(root).parts and p.is_file()})
        native.write_json(out / (label + ".json"), snap)
        return snap

    def decision():
        # Controlled path-based reference decision; NOT a native planner.
        return "ask:" + target if git("status", "--porcelain=v1", "-uall", "--", target) else "proceed"

    before = observe("before-plan")
    planned = decision()
    nodes = [outside, {"id": "epic", "parent": None, "needs": [], "decision": planned,
                       "branch": before["branch"], "head": before["head"].strip()},
             {"id": "fixture-1", "parent": "epic", "needs": [], "write": target},
             {"id": "verify", "parent": "epic", "needs": ["fixture-1"]}]
    native.write_json(graph, nodes)
    post = observe("after-plan")
    assert before["graph"] == [outside] and post["graph"] == nodes
    scope = [n for n in post["graph"] if n["parent"] == "epic"]
    assert [n["id"] for n in scope if not n["needs"]] == ["fixture-1"]
    assert [(n["id"], n["needs"]) for n in scope if n["needs"]] == [("verify", ["fixture-1"])]
    assert all(before[k] == post[k] for k in ("branch", "head", "index", "exclude"))
    assert {p for p in before["tree"] if before["tree"][p] != post["tree"][p]} == {GRAPH}
    assert before["tree"].keys() == post["tree"].keys()
    if case == "stale-collision":
        (root / target).write_text("new user collision\n")
    if case == "stale-disjoint":
        (root / "notes.txt").write_text("after planning\n")
    current = decision()
    if case == "native":
        # Simulated pending, reviewed change, not a tool action by the model.
        (root / target).write_text("reviewed\n")
    start = observe("before-goal")
    if case == "native":
        prompt = (native.PREAMBLE + "\nInstalled planning handoff:\n" + plan +
                  "\nInstalled goal contract:\n" + completion +
                  "\nControlled scoped resume: apply the workspace gate for fixture-1. "
                  "Scope resolution, role checks and independent PASS are simulated. "
                  "See .beads/fixture-graph.json for the simulated plan (only its change "
                  "from the seed is attributed to planning; do not commit it). "
                  "You are authorized to start on dedicated fixture/handoff at current HEAD "
                  "if safe, verify startup preservation, then finalize pending reviewed "
                  "work locally. " + native.OWNERSHIP + native.FIXTURE_READ_INSTRUCTIONS +
                  "\nAdditionally authorized: git switch only to create fixture/handoff "
                  "at current HEAD in this fixture. No other branch changes or Beads writes. "
                  "Inspect Git directly in cwd; no compound shell helpers. Report actual outcome.")
        usage = out / "usage.json"
        argv = native.argv_for(cli, "A", root, usage, prompt, allow_local_config_read=True,
                               allow_fixture_inspection=True)
        argv[-2:-2] = ["shell(git switch)", "--deny-tool", "shell(git push)", "shell(git merge)"]
        version = subprocess.check_output([cli, "--version"], env=env, cwd=root, timeout=30)
        native.write_json(out / "invocation.json", dict(argv=argv, cwd=str(root), overrides=overrides,
                          version=version.decode(), installer=native.digest(native.SOURCE.read_bytes()),
                          skills={p.name + "/" + p.parent.name: native.digest(p.read_bytes())
                                  for p in (plan_path, goal_path)}))
        result, stdout, stderr = native.execute(argv, root, env)
        (out / "stdout.jsonl").write_bytes(stdout)
        (out / "stderr.txt").write_bytes(stderr)
        end = observe("after-goal")
        checks = native.artifact_checks("A", root, env, start, end)
        checks.update(branch=end["branch"] == BRANCH, plan_preserved=end["graph"] == nodes,
                      other_bytes=start["tree"] == end["tree"], usage=usage.is_file(),
                      original_head=git("rev-parse", "main") == start["head"],
                      scoped_index=git("diff", "--cached", "--name-only").splitlines() == ["staged.txt"])
        metrics = json.loads(usage.read_text()).get("modelMetrics", {}) if usage.is_file() else {}
        status = ("INCONCLUSIVE" if result["timed_out"] else "UNQUALIFIED" if result["exit"]
                  or not metrics else "ARTIFACT FAILURE" if not all(checks.values())
                  else "REVIEW TRANSCRIPT AND MODEL")
        native.write_json(out / "result.json", dict(process=result, checks=checks, status=status,
                                                   reported_models=list(metrics)))
        if result["exit"] or not metrics:
            raise SystemExit(f"{status}: inspect retained stderr and usage; no retry")
        assert not result["exit"] and not result["timed_out"] and all(checks.values()), checks
        return  # transcript and usage review required; never auto-certify native behavior

    assert planned == ("ask:" + target if case in ("overlap", "collision") else "proceed")
    blocked = case in ("overlap", "collision", "stale-collision")
    assert current == ("ask:" + target if blocked else "proceed")
    native.write_json(out / "simulated-decisions.json", {"plan": planned, "live": current})
    if blocked:
        assert observe("after-goal") == start
        return
    if start["branch"] != BRANCH:
        git("switch", "-qc", BRANCH)
    started = observe("after-start")
    assert started == dict(start, branch=BRANCH)
    (root / target).write_text("reviewed\n")
    git("commit", "-qm", "fixture-1", "--only", "--", target)
    end = observe("after-goal")
    assert end["tree"] == dict(start["tree"], **{target: native.digest(b"reviewed\n")})
    assert end["graph"] == nodes and end["branch"] == BRANCH and end["exclude"] == start["exclude"]
    assert git("diff", "--name-only", start["head"].strip(), "HEAD").splitlines() == [target]
    assert git("show", "HEAD:" + target) == "reviewed\n"
    assert [l for l in end["index"].splitlines() if not l.endswith("\t" + target)] == [
        l for l in start["index"].splitlines() if not l.endswith("\t" + target)]


if __name__ == "__main__":
    if "--handoff" in sys.argv:
        parser = argparse.ArgumentParser()
        parser.add_argument("--handoff", type=Path, required=True, help="existing evidence parent")
        parser.add_argument("--native-cli", type=Path, help="one actual session instead of Git simulations")
        args = parser.parse_args()
        output = Path(tempfile.mkdtemp(prefix="hq-ha2.4-", dir=args.handoff)).resolve()
        print(output, flush=True)
        cases = (["native"] if args.native_cli else
                 ["dirty", "guest", "overlap", "collision", "stale-collision", "stale-disjoint", "ready"])
        for name in cases:
            handoff_case(output / name, name, args.native_cli)
            print(name, "artifact checks passed", flush=True)
    else:
        unittest.main()
