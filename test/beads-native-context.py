"""TEST ONLY: opt-in Beads 1.1.2 private-context experiment, never a user initializer.

No --run: no native commands or fixtures. Exit 0 requires every proof; 2 means
BLOCKED/unexecuted, 1 means FAILED. Only disposable fixture data is reported.
"""
import argparse
import datetime
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import uuid

sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location(
    "native_discovery", Path(__file__).with_name("native-discovery.py"))
N = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(N)
PIN = "20e493e569c922d1253bdeff068c5e56c94957fb"
BINARY = Path("/opt/homebrew/Cellar/beads/1.1.2/bin/beads")
PROOFS = ("sandbox", "native-init", "readiness", "required-operations",
          "separation", "IDENTITY_BINDING", "database-uuid-query", "host-privacy", "cleanup")
SECTION = ("\n# Beads / Dolt files (added by bd init)\n"
           ".dolt/\n*.db\n.beads-credential-key\n.beads/proxieddb/\n")
DENIAL = re.compile(r"operation not permitted|permission denied|sandbox.*denied", re.I)
KNOWN_WARNINGS = {
    "Warning: could not compute repository ID: not a git repository",
    "Warning: could not compute clone ID: not a git repository: not a git repository: exit status 128",
    "warning: beads.role not configured (GH#2950).",
    "⚠️  Git hooks not installed (5 missing)",
}
COMMANDS = {"--help", "--version", "init", "create", "dep", "ready", "show",
            "update", "close", "remember", "export", "context", "sql", "ping", "where",
            "info", "list"}


def exit_code(proofs):
    if "FAILED" in proofs.values():
        return 1
    return 0 if all(proofs.get(key) == "PASS" for key in PROOFS) else 2


def warnings(text):
    observed = [line.strip() for line in text.splitlines()
                if re.match(r"\s*(?:warning:|⚠)", line, re.I)]
    unknown = set(observed) - KNOWN_WARNINGS
    if unknown:
        raise N.Blocked(f"unreviewed native warnings: {sorted(unknown)}")
    return observed


def check_ping(value):
    assert type(value) is dict and value.get("status") == "ok", "ping query not ok"
    for field in ("resolve_ms", "store_ms", "query_ms", "total_ms"):
        assert type(value.get(field)) is int and value[field] >= 0, f"ping {field}"


def check_identity_refusal(result, original, replacement):
    """Pinned main.go:1439-1474 fields; arbitrary nonzero is never identity proof."""
    assert str(uuid.UUID(original)) == original
    assert str(uuid.UUID(replacement)) == replacement and replacement != original
    assert result.returncode > 0, "identity control write did not refuse normally"
    assert not result.stdout.strip(), "unexpected identity control stdout"
    lines = result.stderr.splitlines()
    for expected in (
        "Error: workspace identity mismatch detected",
        f"  metadata.json project_id: {replacement}",
        f"  database _project_id:     {original}",
    ):
        assert lines.count(expected) == 1, "missing/ambiguous pinned identity diagnostic field"
    warnings(result.stderr)
    return {"diagnostic": "workspace identity mismatch detected",
            "metadata_project_id": replacement, "database_project_id": original}


def check_unchanged_issues(queued, ids, rejected_title):
    assert type(queued) is list and len(queued) == len(ids) == 3, "identity control issue count"
    assert {x["id"] for x in queued} == set(ids), "identity control changed issue IDs"
    assert all(x["title"] != rejected_title for x in queued), "rejected issue persisted"


def export_records(text):
    records = [json.loads(line) for line in text.splitlines()]
    issues, memories = {}, {}
    for record in records:
        assert type(record) is dict, "export record must be object"
        if record.get("_type") == "issue":
            assert record["id"] not in issues, "duplicate issue"
            issues[record["id"]] = record
        elif record.get("_type") == "memory":
            assert record["key"] not in memories, "duplicate memory"
            memories[record["key"]] = record["value"]
        else:
            raise AssertionError("unknown export record type")
    return issues, memories


def native_profile(work, tools, private, beads):
    """Reuse runtime read policy, replace its broad fixture write grant."""
    original = f"(allow file-write* (subpath {json.dumps(str(work))}))"
    profile = N.sandbox_profile(work, tools)
    assert profile.count(original) == 1
    grants = "\n".join(f"(allow file-write* (subpath {json.dumps(str(p))}))"
                       for p in (private, beads))
    # No external Dolt executable, even if one becomes available on PATH.
    return profile.replace(original, grants) + '\n(deny process-exec (regex #"/dolt$"))'


def private_env(private, repo, tools):
    env = N.isolated_env(private, tools)
    env.update({
        "BEADS_DIR": str(repo / ".beads"),
        "GIT_CEILING_DIRECTORIES": str(private),
        "BD_DISABLE_METRICS": "1", "BD_DOLT_MODE": "embedded",
        "BD_DOLT_SHARED_SERVER": "false", "BD_BACKUP_ENABLED": "false",
        "BD_EXPORT_AUTO": "false", "BD_NO_HOOKS": "1",
    })
    return env


def protected_snapshot(work, allowed):
    # Prune engine directories rather than opening all Dolt files for hashing.
    result = {}
    for base, dirs, files in os.walk(work, followlinks=False):
        base = Path(base)
        dirs[:] = [d for d in dirs if base / d not in allowed]
        for name in sorted(dirs + files):
            path = base / name
            info = path.lstat()
            result[str(path.relative_to(work))] = (
                info.st_mode,
                info.st_mtime_ns if path.is_file() else None,
                os.readlink(path) if path.is_symlink() else
                N.hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None)
    return result


class Experiment:
    def __init__(self, work, tools):
        assert work.parent == Path("/private/tmp") and work.name.startswith(
            "domestique-beads-context-"), "requires known disposable fixture path"
        assert work.is_dir() and work.resolve() == work and not any(work.iterdir()), (
            "fixture must be fresh, empty, physical")
        self.work, self.tools = work, tools
        self.deadline = time.monotonic() + 480
        self.report = {
            "scope": "TEST ONLY; disposable fixtures; production .6 remains blocked",
            "source_pin": PIN, "binary": str(BINARY), "commands": [],
            "proofs": {key: "BLOCKED" for key in PROOFS}, "contexts": [],
            "limits": [
                "macOS and installed 1.1.2 only; no portable/version certification",
                "stderr denials and protected snapshots checked; no kernel denial audit",
                "--sandbox is auto-push control, not OS isolation",
            ],
            "process_policy": "60s/process, 480s/native phase; helper reaps/kills exact child "
                              "process group on normal exit/timeout; no detached/external Dolt",
            "proof_definitions": {
                "readiness": "real ping query, persisted CRUD, physical embedded files, metadata UUIDs",
                "IDENTITY_BINDING": "three disposable metadata-only UUID negative controls; "
                                    "native refusal reports original DB UUID; no issue inserted",
                "database-uuid-query": "optional direct DB _project_id SELECT; unsupported SQL "
                                       "is not a feasibility blocker",
            },
        }
        self.contexts = []
        self.before = None
        self.allowed = []

    def safe(self, argv, cwd, env, profile):
        if not self.tools["sandbox-exec"]:
            raise N.Blocked("sandbox-exec unavailable; no native invocation")
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise N.Blocked("480s experiment deadline exceeded")
        return N.run([self.tools["sandbox-exec"], "-p", profile, *argv],
                     cwd, env, timeout=min(60, remaining))

    def checked(self, argv, cwd, env, profile):
        result = self.safe(argv, cwd, env, profile)
        if result.returncode:
            raise N.Blocked(f"{list(map(str, argv))}: exit {result.returncode}: "
                            f"{result.stderr or result.stdout}")
        return result

    def validate(self, context):
        repo, private, env, profile = context
        # Outside fixture read/write sentinel: our own disposable data, never real HOME.
        with tempfile.TemporaryDirectory(prefix="domestique-beads-denied-") as temp:
            outside = Path(temp).resolve() / "sentinel"
            outside.write_text("outside-fixture")
            targets = [outside, repo / ".gitignore",
                       self.work / "A/.git/config", self.work / "A/.git/index",
                       self.work / "A/.git/info/exclude", self.work / "A/.git/hooks/sentinel",
                       self.work / "host-home/sentinel"]
            if repo.name == "W":
                admin = Path((repo / ".git").read_text().strip().removeprefix("gitdir: "))
                assert admin.is_relative_to(self.work / "A/.git/worktrees")
                targets.extend((repo / ".git", admin / "index", admin / "HEAD"))
            script = (
                "import pathlib,socket,sys,json\n"
                "pathlib.Path(sys.argv[1]).write_text('allowed')\n"
                "for target in sys.argv[2:]:\n"
                " try:\n  with open(target,'a') as f: f.write('FORBIDDEN')\n"
                " except PermissionError: pass\n"
                " else: raise AssertionError('write was not permission denied: '+target)\n"
                "try: pathlib.Path(sys.argv[2]).read_text()\n"
                "except PermissionError: pass\n"
                "else: raise AssertionError('outside read allowed')\n"
                "for operation in ('bind','connect'):\n"
                " with socket.socket() as s:\n"
                "  try: getattr(s,operation)(('127.0.0.1',9 if operation=='connect' else 0))\n"
                "  except PermissionError: pass\n"
                "  else: raise AssertionError('network not permission denied')\n"
                "print('POSITIVE_WRITE_AND_PERMISSION_DENIALS_OK')\n"
            )
            result = self.checked(
                [Path(sys.executable).resolve(), "-c", script, private / "probe", *targets],
                private / "run", env, profile)
            assert result.stdout.strip() == "POSITIVE_WRITE_AND_PERMISSION_DENIALS_OK"
            assert outside.read_text() == "outside-fixture"
            assert (private / "probe").read_text() == "allowed"
        self.report.setdefault("sandbox_probes", []).append(repo.name)

    def setup(self):
        if sys.platform != "darwin" or not self.tools["sandbox-exec"]:
            raise N.Blocked("requires verified macOS sandbox-exec")
        if not BINARY.is_file() or Path("/opt/homebrew/bin/bd").resolve() != BINARY:
            raise N.Blocked("installed Beads path differs from experiment pin")
        # All setup state is already under the first project's private context.
        first = self.work / "A"
        private = first / ".domestique-private/beads-context"
        private.mkdir(parents=True)
        setup_env = private_env(private, first, self.tools)
        setup_profile = N.sandbox_profile(self.work, self.tools)
        (self.work / "host-home").mkdir()
        (self.work / "host-home/sentinel").write_text("fixture HOME, not native HOME\n")
        # Verify generic setup sandbox before even Git fixture setup.
        h = N.Harness.__new__(N.Harness)
        h.work, h.tools, h.env, h.profile, h.results = (
            self.work, self.tools, setup_env, setup_profile, [])
        h.validate_isolation()
        git = self.tools["git"]
        if git is None:
            raise N.Blocked("Git unavailable")
        for name in ("A", "B"):
            repo = self.work / name
            repo.mkdir(exist_ok=True)
            self.checked([git, "init", "-q", repo], self.work, setup_env, setup_profile)
        linked = self.work / "W"
        self.checked([git, "-C", first, "worktree", "add", "--orphan", "-b",
                      "fixture-linked", linked], self.work, setup_env, setup_profile)
        for name in ("A", "B", "W"):
            repo = self.work / name
            (repo / ".gitignore").write_text("# host policy\n" + (SECTION if name == "A" else ""))
            (repo / "unknown.db").write_text("unrelated fixture data\n")
            (repo / ".claude").mkdir()
            (repo / ".claude/settings.local.json").write_text('{"fixture":true}\n')
            (repo / "CLAUDE.md").write_text("host policy sentinel\n")
            (repo / "AGENTS.md").write_text("host policy sentinel\n")
            if name != "W":
                (repo / ".git/info").mkdir(exist_ok=True)
                (repo / ".git/info/exclude").write_text("# host excludes\n")
                (repo / ".git/hooks").mkdir(exist_ok=True)
                (repo / ".git/hooks/sentinel").write_text("never execute\n")
            self.checked([git, "-C", repo, "add", ".gitignore"], self.work,
                         setup_env, setup_profile)
            private = repo / ".domestique-private/beads-context"
            if name == "A":
                env = setup_env
            else:
                private.mkdir(parents=True)
                env = private_env(private, repo, self.tools)
            (private / "run").mkdir()
            profile = native_profile(self.work, self.tools, private, repo / ".beads")
            self.contexts.append((repo, private, env, profile))
            self.allowed.extend((private, repo / ".beads"))
        self.before = protected_snapshot(self.work, self.allowed)
        self.ignore_before = self.ignores()
        assert self.ignore_before == {"A": [0, 1], "B": [1, 1], "W": [1, 1]}
        for context in self.contexts:
            self.validate(context)
            repo, private, env, profile = context
            discovery = self.safe([git, "rev-parse", "--show-toplevel"],
                                  private / "run", env, profile)
            assert discovery.returncode == 128 and "not a git repository" in discovery.stderr
            host = self.checked([git, "rev-parse", "--show-toplevel"], repo, env, profile)
            assert Path(host.stdout.strip()).resolve() == repo
            self.report["contexts"].append({
                "repo": str(repo), "cwd": str(private / "run"), "env": env,
                "git_discovery": {"private_exit": discovery.returncode,
                                  "private_stderr": discovery.stderr, "host_root": host.stdout.strip()},
            })
        self.report["proofs"]["sandbox"] = "PASS"

    def ignores(self):
        values = {}
        for repo, private, env, profile in self.contexts:
            values[repo.name] = []
            for path in ("unknown.db", ".claude/settings.local.json"):
                result = self.safe([self.tools["git"], "check-ignore", "-q", "--", path],
                                   repo, env, profile)
                assert result.returncode in (0, 1), result.stderr
                values[repo.name].append(result.returncode)
        return values

    def bd(self, context, *args, json_output=False, expected_error=None,
           identity_expectation=None):
        assert self.report["proofs"]["sandbox"] == "PASS", "native requires verified sandbox"
        assert context in self.contexts, "unknown native context"
        assert args and args[0] in COMMANDS, "non-experiment native command"
        repo, private, env, profile = context
        assert private == repo / ".domestique-private/beads-context"
        assert env["BEADS_DIR"] == str(repo / ".beads")
        if args[0] == "init" and "--help" not in args:
            assert not (repo / ".beads").exists(), "init is fresh-final-path only"
        argv = [BINARY, "--sandbox", *args]
        if json_output:
            argv.append("--json")
        item = {"repo": repo.name, "cwd": str(private / "run"),
                "argv": list(map(str, argv)), "exit": None}
        self.report["commands"].append(item)
        try:
            result = self.safe(argv, private / "run", env, profile)
        except N.Blocked as exc:
            item["classification"] = "BLOCKED"
            item["diagnostic"] = str(exc)
            raise
        item["exit"] = result.returncode
        if identity_expectation is not None:
            assert args[0] == "create" and expected_error is None
            # Report only controlled fields, not raw native recovery advice/config.
            item["classification"] = "FAILED"
            evidence = check_identity_refusal(result, *identity_expectation)
            if DENIAL.search(result.stdout + result.stderr):
                raise N.Blocked("identity control permission denial")
            item.update(classification="PASS: identity refusal", **evidence)
            return evidence
        item.update(stdout=result.stdout, stderr=result.stderr)
        if DENIAL.search(result.stdout + result.stderr):
            raise N.Blocked(f"native permission denial: {item}")
        if expected_error is not None:
            assert result.returncode == 1 and expected_error in result.stderr, item
            item["classification"] = "BLOCKED: source-reviewed unsupported diagnostic"
            return result.stderr
        if result.returncode:
            raise N.Blocked(f"native command failed: {item}")
        if "--help" in args:
            item["stdout"] = "(help inspected; omitted)"
        else:
            item["warnings"] = warnings(result.stdout + result.stderr)
        return N.decode(result.stdout, str(args)) if json_output else result.stdout

    def initialize(self, context):
        repo, private, env, profile = context
        prefix = "fx" + repo.name.lower()
        assert not (repo / ".beads").exists(), "final database must be initially missing"
        self.bd(context, "init", "--stealth", "--skip-agents", "--skip-hooks",
                "--non-interactive", "--prefix", prefix, "--remote=")
        metadata = json.loads((repo / ".beads/metadata.json").read_text())
        self.report.setdefault("metadata", {})[repo.name] = metadata
        assert metadata.get("backend") == "dolt" and metadata.get("dolt_mode") == "embedded"
        uuid.UUID(metadata["project_id"])
        assert metadata.get("dolt_database") == prefix
        assert not (repo / ".beads/redirect").exists()
        assert not (repo / ".beads/dolt").exists(), "unexpected server-mode directory"
        assert not any((repo / ".beads").glob("dolt-server*")), "unexpected server artifacts"
        assert not list(private.rglob(".git")), "unexpected Git initialization in private context"
        engine = repo / ".beads/embeddeddolt"
        assert engine.is_dir() and engine.resolve() == engine
        files = [str(p.relative_to(repo / ".beads")) for p in engine.rglob("*") if p.is_file()]
        assert any("/.dolt/" in p for p in files), "missing physical embedded Dolt database"
        self.report.setdefault("engine_files", {})[repo.name] = files
        check_ping(self.bd(context, "ping", json_output=True))
        where = self.bd(context, "where", json_output=True)
        assert where["path"] == str(repo / ".beads") and where["database_path"] == str(engine)
        assert where["prefix"] == prefix
        # Installed 1.1.2 prints text for info --json in this context. It is
        # diagnostic only, NOT the readiness/engine/identity protocol.
        info = self.bd(context, "info", "--json")
        assert f"Database: {engine}\nMode: direct\n" in info
        self.report.setdefault("info_protocol", {})[repo.name] = "text despite --json; diagnostic only"
        self.report.setdefault("initialized", []).append(repo.name)

    def operations(self, context):
        repo, private, env, profile = context
        epic = self.bd(context, "create", f"Fixture {repo.name} epic", "--type", "epic",
                       "--description", "Disposable native experiment", json_output=True)
        first = self.bd(context, "create", f"Fixture {repo.name} first", "--parent", epic["id"],
                        "--description", "Disposable bounded task", json_output=True)
        second = self.bd(context, "create", f"Fixture {repo.name} second", "--parent", epic["id"],
                         "--deps", first["id"], "--description", "Disposable dependent task",
                         json_output=True)
        ids = [epic["id"], first["id"], second["id"]]
        assert all(i.startswith("fx" + repo.name.lower() + "-") for i in ids)
        shown = self.bd(context, "show", second["id"], json_output=True)
        assert len(shown) == 1 and shown[0]["parent"] == epic["id"]
        dependencies = {(d["id"], d["dependency_type"]) for d in shown[0]["dependencies"]}
        assert (epic["id"], "parent-child") in dependencies
        assert (first["id"], "blocks") in dependencies
        self.report.setdefault("operation_queries", {})[repo.name] = {"second": shown}
        ready = self.bd(context, "ready", json_output=True)
        assert first["id"] in {x["id"] for x in ready}
        assert second["id"] not in {x["id"] for x in ready}
        self.bd(context, "update", first["id"], "--status", "in_progress", json_output=True)
        progressing = self.bd(context, "show", first["id"], json_output=True)
        assert len(progressing) == 1 and progressing[0]["status"] == "in_progress"
        self.bd(context, "close", first["id"], "--reason", "Fixture complete", json_output=True)
        ready = self.bd(context, "ready", json_output=True)
        assert second["id"] in {x["id"] for x in ready}
        self.bd(context, "remember", f"Disposable fixture memory {repo.name}", "--key",
                "fixture-memory")
        output = private / "fixture-export.jsonl"
        self.bd(context, "export", "--include-memories", "--output", str(output))
        issues, memories = export_records(output.read_text())
        assert set(ids) == issues.keys()
        assert issues[first["id"]]["status"] == "closed"
        assert memories == {"fixture-memory": f"Disposable fixture memory {repo.name}"}
        self.report.setdefault("exports", {})[repo.name] = {
            "issues": issues, "memories": memories, "path": str(output),
        }
        check_ping(self.bd(context, "ping", json_output=True))
        self.report.setdefault("operations_completed", []).append(repo.name)
        return ids

    def identity_binding(self, context, ids):
        """DISPOSABLE TEST ONLY. Never mutate an existing user's identity."""
        repo = context[0]
        control = {"status": "BLOCKED"}
        self.report.setdefault("identity_controls", {})[repo.name] = control
        try:
            assert context in self.contexts and repo.is_relative_to(self.work)
            assert repo.name in self.report["initialized"]
            assert repo.name in self.report["operations_completed"]
            path = repo / ".beads/metadata.json"
            assert path.is_file() and not path.is_symlink()
            original_bytes = path.read_bytes()  # Known generated metadata, not a DB copy.
            metadata = json.loads(original_bytes)
            assert metadata == self.report["metadata"][repo.name], "generated metadata drift"
            original = metadata["project_id"]
            replacement = str(uuid.uuid4())
            assert replacement != original
            title = f"Rejected fixture {repo.name} identity control {replacement}"
            metadata["project_id"] = replacement
            try:
                path.write_text(json.dumps(metadata) + "\n")
                control["refusal"] = self.bd(
                    context, "create", title, "--description", "Disposable negative control",
                    json_output=True, identity_expectation=(original, replacement))
            except Exception as exc:
                # A later verification outage must not downgrade a failed write control.
                control["status"] = "BLOCKED" if isinstance(exc, N.Blocked) else "FAILED"
                self.report["proofs"]["IDENTITY_BINDING"] = control["status"]
                raise
            finally:
                path.write_bytes(original_bytes)
                assert path.read_bytes() == original_bytes, "metadata restoration failed"
                control["metadata_restored"] = True
                # Fresh native query even after a failed/blocked write classification.
                queued = self.bd(context, "list", "--all", json_output=True)
                check_unchanged_issues(queued, ids, title)
                control["unchanged_ids"] = sorted(ids)
                control["rejected_issue_absent"] = True
        except N.Blocked:
            self.report["proofs"]["IDENTITY_BINDING"] = control["status"]
            raise
        except Exception:
            control["status"] = "FAILED"
            self.report["proofs"]["IDENTITY_BINDING"] = "FAILED"
            raise
        control["status"] = "PASS"

    def probe(self):
        self.setup()
        version = self.bd(self.contexts[0], "--version")
        self.report["version"] = version.strip()
        self.report["binary_sha256"] = N.hashlib.sha256(BINARY.read_bytes()).hexdigest()
        assert re.search(r"\b1\.1\.2\b", version), "version differs from pin"
        self.bd(self.contexts[0], "--help")
        for command in ("init", "create", "dep", "ready", "show", "update",
                        "close", "remember", "export", "context", "sql"):
            help_text = self.bd(self.contexts[0], command, "--help")
            if command == "init":
                for flag in ("--stealth", "--skip-agents", "--skip-hooks", "--non-interactive",
                             "--prefix", "--remote", "--sandbox"):
                    assert flag in help_text, f"missing native init flag {flag}"
        for context in self.contexts:
            self.initialize(context)
        self.report["proofs"]["native-init"] = "PASS"
        ids = {}
        for context in self.contexts:
            ids[context[0].name] = self.operations(context)
        self.report["proofs"]["required-operations"] = "PASS"
        assert len({m["project_id"] for m in self.report["metadata"].values()}) == 3
        for context in self.contexts:
            name = context[0].name
            queued = self.bd(context, "list", "--all", json_output=True)
            actual_ids = {x["id"] for x in queued}
            assert set(ids[name]) <= actual_ids
            assert not any(set(other) & actual_ids for key, other in ids.items() if key != name)
        self.report["proofs"]["separation"] = "PASS"
        self.report["proofs"]["readiness"] = "PASS"
        for context in self.contexts:
            self.identity_binding(context, ids[context[0].name])
        assert len(self.report["identity_controls"]) == 3
        assert all(c["status"] == "PASS" for c in self.report["identity_controls"].values())
        self.report["proofs"]["IDENTITY_BINDING"] = "PASS"
        # Source sql.go explicitly refuses embedded mode. Execute that SELECT
        # once to record the real limitation, not pretend context/where queries
        # read _project_id. No server/alternate engine fallback is permitted.
        diagnostic = self.bd(
            self.contexts[0], "sql", "SELECT value FROM metadata WHERE `key` = '_project_id'",
            "--json", expected_error="'bd sql' is not yet supported in embedded mode")
        self.report["database_uuid_limit"] = diagnostic
        self.report["limits"].append(
            "DB binding proven by disposable negative controls, not direct SQL; missing DB "
            "_project_id can skip native checks and must FAIL the control; production needs "
            "known init/version/pinned target and approved commands, never routine UUID mutation")

    def privacy(self):
        if self.before is None:
            return
        changes = N.differences(self.before, protected_snapshot(self.work, self.allowed))
        ignores = self.ignores()
        self.report["protected"] = {
            "entries": len(self.before), "changes": changes,
            "check_ignore_before": self.ignore_before, "check_ignore_after": ignores,
            "includes": "host files/modes, Git index/config/excludes/hooks/common-admin, HOME sentinel",
        }
        self.report["proofs"]["host-privacy"] = (
            "FAILED" if changes or ignores != self.ignore_before else "PASS")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if sys.flags.optimize:
        print(json.dumps({"status": "FAILED", "diagnostic": "run without -O/-OO"}))
        return 1
    if not args.run:
        print(json.dumps({"status": "STATIC_ONLY", "diagnostic": "requires --run; no native init"}))
        return 2
    # Absolute temp parent, never inherited TMPDIR, repo, HOME or user configuration.
    temp = tempfile.TemporaryDirectory(prefix="domestique-beads-context-", dir="/private/tmp")
    work = Path(temp.name).resolve()
    tools = N.resolve_tools()
    # Reuse the Git launcher handling, but do not grant client runtime reads or
    # put Node/AI client symlinks on the fixture PATH.
    for name in (*N.CLIENTS, "node"):
        tools[name] = None
    experiment = Experiment(work, tools)
    try:
        experiment.probe()
    except N.Blocked as exc:
        experiment.report["blocker"] = str(exc)
    except (AssertionError, OSError, ValueError, KeyError, TypeError,
            subprocess.TimeoutExpired) as exc:
        experiment.report["failure"] = str(exc)
        experiment.report["proofs"]["experiment"] = "FAILED"
    finally:
        try:
            experiment.privacy()
        except (AssertionError, OSError, N.Blocked) as exc:
            experiment.report["proofs"]["host-privacy"] = "FAILED"
            experiment.report["privacy_error"] = str(exc)
        try:
            temp.cleanup()
            assert not work.exists()
            experiment.report["proofs"]["cleanup"] = "PASS"
        except (OSError, AssertionError) as exc:
            experiment.report["proofs"]["cleanup"] = "FAILED"
            experiment.report["orphan"] = {"path": str(work), "error": str(exc)}
    experiment.report["date"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    experiment.report["counts"] = {
        status: sum(value == status for value in experiment.report["proofs"].values())
        for status in ("PASS", "BLOCKED", "FAILED")
    }
    experiment.report["status"] = (
        "FAILED" if exit_code(experiment.report["proofs"]) == 1 else
        "BLOCKED" if exit_code(experiment.report["proofs"]) == 2 else "PASS")
    print(json.dumps(experiment.report, indent=2))
    return exit_code(experiment.report["proofs"])


if __name__ == "__main__":
    sys.exit(main())
