"""Opt-in actual production initializer/installed bridge, disposable macOS fixtures.

No --run: no fixtures or native operations. No AI, auth, model or MCP workloads.
Production supplies the native sandbox. Setup Git uses the test sandbox.
Darwin refuses reapplying a sandbox under the test default-deny policy; do not
weaken that policy to enable nesting. Installer/dispatcher controllers therefore
run with the allowlisted fixture environment, as in the ordinary installer tests.
"""
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("native", ROOT / "test/native-discovery.py")
N = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(N)
SPEC = importlib.util.spec_from_file_location("beads_fixture", ROOT / "test/beads_fixture.py")
F = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(F)


def experiment():
    if sys.argv[1:] != ["--run"]:
        print("STATIC ONLY; actual production fixture requires --run")
        return 2
    selected = F.resolve()
    count = 0
    # Existing installer global_path intentionally remains unchanged here;
    # use the ordinary private OS temp parent used by its current suites.
    with tempfile.TemporaryDirectory(prefix="domestique-beads-production-") as temp:
        work = Path(temp).resolve()
        tools = N.resolve_tools()
        env = N.isolated_env(work, tools)
        env["GIT_CEILING_DIRECTORIES"] = str(work.parent)
        (work / "bin/bd").symlink_to(selected["path"])
        (work / "bin/python3").symlink_to(Path(sys.executable).resolve())
        env.update(SECRET="SECRET-ENV", BD_DB="SECRET-ROUTE", BEADS_DB="SECRET-ROUTE",
                   HTTP_PROXY="http://127.0.0.1:9", OTEL_EXPORTER_OTLP_ENDPOINT="http://127.0.0.1:9")
        profile = N.sandbox_profile(work, tools, installer=True)
        calls = []

        def run(argv, cwd=work, ok=True):
            nonlocal count
            command = ([tools["sandbox-exec"], "-p", profile, *argv]
                       if argv[0] == tools["git"] else argv)
            result = N.run(command, cwd, env, timeout=600)
            calls.append((list(map(str, argv)), result.returncode))
            assert (result.returncode == 0) == ok, (
                argv, result.returncode, result.stdout, result.stderr,
                [(str(p.relative_to(work)), oct(p.lstat().st_mode))
                 for p in work.rglob("*") if not p.is_symlink() and p.lstat().st_mode & 0o022],
                [(str(p.relative_to(work)), [x.name for x in p.iterdir()])
                 for p in work.glob("*/.beads")])
            count += 1
            return result

        # Native qualification here belongs to the retained preview, not V2.
        import preview_fixture
        dom = ["bash", str(preview_fixture.materialize(work))]
        run([*dom, "--global", "--platform", "all"])
        core = work / "core"
        helper = core / "bin/resolve-core"
        release = (core / "active").read_text().strip().split("=")[1]
        hosts = []
        for name in ("A", "B"):
            repo = work / name
            repo.mkdir()
            run([tools["git"], "init", "-q", repo])
            (repo / ".git/info").mkdir()
            (repo / ".git/info/exclude").write_text("# fixture host excludes\n")
            hosts.append(repo)
        linked = work / "W"
        run([tools["git"], "-C", hosts[0], "worktree", "add", "--orphan",
             "-b", "fixture-linked", linked])
        hosts.append(linked)
        (work / "home/native-user-config").write_text("SECRET-NATIVE-HOME\n")
        protected = {}
        for repo in hosts:
            (repo / "CLAUDE.md").write_text("SECRET-HOST-POLICY\n")
            (repo / "AGENTS.md").write_text("SECRET-HOST-AGENTS\n")
            section = ("\n# Beads / Dolt files (added by bd init)\n"
                       ".dolt/\n*.db\n.beads-credential-key\n.beads/proxieddb/\n")
            (repo / ".gitignore").write_text("# host only\n" + (section if repo.name == "A" else ""))
            (repo / "unknown.db").write_text("SECRET-HOST-DB\n")
            (repo / ".claude").mkdir()
            (repo / ".claude/settings.local.json").write_text('{"secret":"SECRET-SETTINGS"}\n')
            for p in (repo / "CLAUDE.md", repo / "AGENTS.md", repo / ".gitignore",
                      repo / "unknown.db", repo / ".claude/settings.local.json"):
                protected[p] = p.read_bytes()
            run([tools["git"], "-C", repo, "add", ".gitignore"])
        allowed = {p / rel for p in hosts for rel in (".beads", ".domestique-private")}
        allowed.update({p / ".git/info/exclude" for p in hosts[:2]})

        def protected_snapshot():
            result = {}
            for base, dirs, files in os.walk(work, followlinks=False):
                base = Path(base)
                dirs[:] = [d for d in dirs if base / d not in allowed]
                for name in sorted(dirs + files):
                    path = base / name
                    if path in allowed:
                        continue
                    info = path.lstat()
                    result[str(path.relative_to(work))] = (
                        info.st_mode, info.st_mtime_ns if path.is_file() else None,
                        os.readlink(path) if path.is_symlink() else
                        hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None)
            return result

        protected_before = protected_snapshot()
        queues = {}
        for repo in hosts:
            before = N.snapshot(work)
            run([*dom, "--local", repo, "--with-beads", "--state-only", "--dry-run"])
            assert before == N.snapshot(work), "production dry-run wrote fixture"
            run([*dom, "--local", repo, "--with-beads", "--state-only"])
            manifest = repo / ".domestique-private/manifest"
            text = manifest.read_text()
            assert "providers=none\n" in text and "beads_status=ready\n" in text
            assert not list(repo.glob(".*/*/*implementer*")), "state-only created adapters"
            before = N.snapshot(work)
            run([*dom, "--local", repo, "--with-beads", "--state-only"])
            assert before == N.snapshot(work), "state-only rerun changed files"

            def bd(*args):
                return run(["bash", helper, "beads", core, repo, release, *args], cwd=repo)

            epic = json.loads(bd("create", "Fixture epic", "--type", "epic", "--json").stdout)
            first = json.loads(bd("create", "--parent", epic["id"],
                                  "--description", "--db is literal text; 'quoted'", "--json",
                                  "--", "--db permission denied is literal text").stdout)
            assert first["title"] == "--db permission denied is literal text"
            second = json.loads(bd("create", "Fixture dependent", "--parent", epic["id"],
                                   "--deps", first["id"], "--json").stdout)
            bd("dep", "remove", second["id"], first["id"], "--json")
            bd("dep", "add", second["id"], first["id"], "--json")
            ready = json.loads(bd("ready", "--parent", epic["id"], "--json").stdout)
            assert first["id"] in {x["id"] for x in ready}
            assert second["id"] not in {x["id"] for x in ready}
            bd("update", first["id"], "--claim", "--json")
            bd("show", first["id"], "--json")
            bd("close", first["id"], "--reason", "fixture complete", "--json")
            bd("remember", "Fixture durable insight", "--key", "fixture")
            bd("export", "--include-memories")
            exported = [json.loads(line) for line in
                        (repo / ".domestique-private/exports/issues.jsonl").read_text().splitlines()]
            assert len(exported) == 4
            queues[repo.name] = {x["id"] for x in json.loads(bd("list", "--all", "--json").stdout)}
            assert queues[repo.name] == {epic["id"], first["id"], second["id"]}
            assert manifest.read_text() == text, "DB mutation rewrote provenance baseline"
            run(["bash", helper, "beads-guard", core, repo, release])
            run([*dom, "--uninstall", "--local", repo])
            assert manifest.read_text() == text.replace("beads_status=ready\n", "beads_status=retained\n")
            before = N.snapshot(work)
            run([*dom, "--uninstall", "--local", repo, "--purge-beads", "--force"], ok=False)
            assert before == N.snapshot(work), "used database purge refusal wrote fixture"
            run([*dom, "--local", repo, "--with-beads", "--state-only"])
            assert manifest.read_text() == text, "reactivation changed original provenance"
            metadata = repo / ".beads/metadata.json"
            original = metadata.read_bytes()
            data = json.loads(original)
            data["project_id"] = "11111111-1111-4111-8111-111111111111"
            metadata.write_text(json.dumps(data) + "\n")
            before = N.snapshot(work)
            run(["bash", helper, "beads", core, repo, release,
                 "create", "MUST-NOT-EXIST", "--json"], ok=False)
            assert before == N.snapshot(work), "wrapper identity refusal wrote data"
            metadata.write_bytes(original)
            assert "MUST-NOT-EXIST" not in bd("list", "--all", "--json").stdout
            for p, data in protected.items():
                assert p.read_bytes() == data, f"host privacy: {p.name}"
            run([tools["git"], "-C", repo, "check-ignore", "-q", "unknown.db"], ok=repo.name == "A")
            run([tools["git"], "-C", repo, "check-ignore", "-q",
                 ".claude/settings.local.json"], ok=False)
            run([tools["git"], "-C", repo, "check-ignore", "-q", ".beads/metadata.json"])
        assert not (queues["A"] & queues["B"] or queues["A"] & queues["W"])
        assert protected_snapshot() == protected_before, "protected HOME/core/Git/host changes"
        for repo in hosts[:2]:
            text = (repo / ".git/info/exclude").read_text()
            assert text.startswith("# fixture host excludes\n# BEGIN domestique private (format=1)\n")
            assert text.endswith("# END domestique private\n")
            assert "\n/.beads/\n" not in text
            assert text.count("\n/.beads/metadata.json\n") == 1
        # Actual pinned native mixed-provider ordering regression, independent
        # of the synthetic digest-substitution suite above.
        combined = work / "C"
        combined.mkdir()
        run([tools["git"], "init", "-q", combined])
        (combined / ".git/info").mkdir(exist_ok=True)
        run([*dom, "--local", combined, "--platform", "claude"])
        manifest = combined / ".domestique-private/manifest"
        lines = manifest.read_text().splitlines(keepends=True)
        lines[6] = lines[6].rsplit(":", 1)[0] + ":" + "a" * 64 + "\n"
        manifest.write_text("".join(lines[:6] + lines[8:10] + lines[6:8]))
        pairs = manifest.read_text().splitlines()[6:]
        receipt = combined / ".domestique-private/routing/claude.receipt"
        lines = receipt.read_text().splitlines(keepends=True)
        receipt.write_text("".join(lines[:5] + list(reversed(lines[5:]))))
        unchanged = {p: p.read_bytes() for p in
                     [receipt, *combined.glob(".claude/agents/*")]}
        protected_global = N.snapshot(core), N.snapshot(work / "home")
        before = N.snapshot(work)
        run([*dom, "--local", combined, "--with-beads", "--platform", "copilot", "--dry-run"])
        assert before == N.snapshot(work), "mixed-provider native dry-run wrote files"
        run([*dom, "--local", combined, "--with-beads", "--platform", "copilot"])
        assert manifest.read_text().splitlines()[6:10] == pairs
        assert "beads_status=ready\n" in manifest.read_text()
        assert all(p.read_bytes() == data for p, data in unchanged.items())
        assert protected_global == (N.snapshot(core), N.snapshot(work / "home"))
        run(["bash", helper, "beads-guard", core, combined, release])
        run([tools["git"], "-C", combined, "check-ignore", "-q", ".beads/metadata.json"])
        print(json.dumps({"production": "PASS", "checked_processes": count,
                          "native_fixture": selected,
                          "projects": list(queues), "protected_host_leaves": len(protected),
                          "protected_entries": len(protected_before),
                          "mixed_provider_ordering": "PASS (actual native C)",
                          "native": "Beads 1.1.2 CGO embedded, Darwin arm64",
                          "scope": "actual production initializer and installed wrapper; "
                                   "not role/model/MCP execution"}))
    return 0


def main():
    try:
        return experiment()
    except N.FAILURES as exc:
        print(json.dumps({"production": "FAILED", "status": "ASSERTION_FAILURE",
                          "scope": "production fixture failed; not native qualification",
                          **N.failure_fields(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
