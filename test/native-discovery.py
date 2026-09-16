"""Opt-in, offline native metadata probes; never an execution acceptance test.

Exit 0: all requested discovery observed; 1: assertion/harness failure;
2: at least one BLOCKED component (other observations remain valid).
Without --run, emits STATIC_ONLY and exits 2 without invoking any client.
Only Python stdlib and already installed tools are used.
"""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
CLIENTS = ("claude", "codex", "copilot")
TIMEOUT = 30
RELOAD_MARKER = "Fixture metadata reload hq-b3q.13."

# Path-based loading supports standalone, importlib and runpy callers without
# changing sys.path. The runner imports no native fixture: no dependency cycle.
_SPEC = importlib.util.spec_from_file_location(
    "_domestique_test_supervision", Path(__file__).with_name("acceptance.py"))
if _SPEC.name not in sys.modules:
    S = importlib.util.module_from_spec(_SPEC)
    sys.modules[_SPEC.name] = S
    _SPEC.loader.exec_module(S)
S = sys.modules[_SPEC.name]
SupervisionError = S.SupervisionError
FAILURES = (AssertionError, OSError, ValueError, KeyError, TypeError,
            subprocess.SubprocessError, SupervisionError)
BLOCKER_KINDS = {"absent-tool", "unsupported-interface", "denied-approval"}


class Blocked(Exception):
    def __init__(self, diagnostic, *, kind="unsupported-interface"):
        assert kind in BLOCKER_KINDS, "invalid native blocker kind"
        self.kind = kind
        super().__init__(diagnostic)


def failure_fields(exc):
    fields = {"failure_kind": S.failure_status(exc)["failure_kind"],
              "diagnostic": getattr(exc, "fixture_diagnostic", str(exc))}
    if hasattr(exc, "fixture_installation"):
        fields["fixture_installation"] = exc.fixture_installation
    if getattr(exc, "returncode", None) is not None:
        fields["exit"] = exc.returncode
    primary = getattr(exc, "primary_failure", None)
    if primary is not None:
        fields["primary_failure"] = failure_fields(primary)
    return fields


def shaped(value, kind, context):
    assert type(value) is kind, f"{context}: expected {kind.__name__}"
    return value


def decode(text, context):
    try:
        return json.loads(text)
    except ValueError as exc:
        raise AssertionError(f"{context}: malformed JSON") from exc


def run(argv, cwd, env, timeout=TIMEOUT, input_text=None):
    """Bound the entire process group, including descendants on normal exit."""
    out, err, rc = S.execute([str(a) for a in argv], env, timeout,
                             cwd=cwd, input_text=input_text)
    return subprocess.CompletedProcess(argv, rc, out, err)


def resolve_tools():
    # Resolve symlinks while the real PATH is available; never read client config.
    tools = {name: Path(shutil.which(name)).resolve() if shutil.which(name) else None
             for name in (*CLIENTS, "node", "git", "sandbox-exec")}
    if tools["git"] == Path("/usr/bin/git"):
        # Apple's launcher can invoke Xcode setup; prefer its installed Git.
        for path in ("/Library/Developer/CommandLineTools/usr/bin/git",
                     "/Applications/Xcode.app/Contents/Developer/usr/bin/git"):
            if os.access(path, os.X_OK):
                tools["git"] = Path(path).resolve()
                break
    return tools


def isolated_env(work, tools):
    home = work / "home"
    paths = {
        "HOME": home, "XDG_CONFIG_HOME": home / ".config",
        "XDG_STATE_HOME": home / ".local/state",
        "XDG_CACHE_HOME": home / ".cache", "CODEX_HOME": home / ".codex",
        "TMPDIR": work / "tmp", "DOMESTIQUE_HOME": work / "core",
    }
    for key, path in paths.items():
        if key != "DOMESTIQUE_HOME":
            path.mkdir(parents=True, exist_ok=True)
    for name in (".claude", ".copilot", ".agents"):
        (home / name).mkdir()
    empty = work / "empty"
    empty.mkdir()
    bin_dir = work / "bin"
    bin_dir.mkdir()
    for name in ("node", "git"):
        if tools[name]:
            (bin_dir / name).symlink_to(tools[name])
    # No inherited auth, provider, proxy, shell startup, Git or telemetry env.
    return {
        **{key: str(value) for key, value in paths.items()},
        "PATH": f"{bin_dir}:/usr/bin:/bin:/usr/sbin:/sbin",
        "LANG": "en_US.UTF-8", "LC_ALL": "en_US.UTF-8", "TERM": "dumb",
        "NO_COLOR": "1", "PYTHONDONTWRITEBYTECODE": "1",
        "OPENSSL_CONF": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.hooksPath",
        "GIT_CONFIG_VALUE_0": str(empty), "GIT_TEMPLATE_DIR": str(empty),
    }


def sandbox_profile(work, tools, installer=False):
    # Default deny also withholds Keychain IPC (no mach-lookup grant).
    # System runtime reads do not include /Library/Keychains or the real HOME.
    reads = [work, Path("/System"), Path("/usr/bin"), Path("/usr/lib"),
             Path("/usr/libexec"), Path("/usr/share"), Path("/usr/sbin"),
             Path("/bin"), Path("/sbin"), Path("/dev"),
             Path("/opt/homebrew/Cellar"), Path("/opt/homebrew/lib"),
             Path("/Applications/Xcode.app/Contents/Developer"),
             Path("/Library/Developer"), Path("/private/etc/localtime"),
             Path("/private/etc/passwd"),
             Path("/private/var/db/dyld")]
    if installer:
        reads.append(ROOT)
    for name in (*CLIENTS, "node"):
        path = tools[name]
        if path:
            if name in ("codex", "copilot") and "node_modules" in path.parts:
                # Include optional platform package siblings under this vendor.
                index = path.parts.index("node_modules")
                reads.append(Path(*path.parts[:index + 2]))
            else:
                reads.append(path)
    lines = [
        "(version 1)", "(deny default)",
        "(allow process-exec process-fork signal sysctl-read)",
        "(allow file-read-metadata)",
        '(allow file-read* (literal "/"))',
    ]
    for path in reads:
        kind = "subpath" if path.is_dir() else "literal"
        lines.append(f"(allow file-read* ({kind} {json.dumps(str(path))}))")
    # Only the context harness supplies this already digest-qualified executable.
    # Never grant its private parent directory (which can be outside Cellar).
    if tools.get("beads"):
        lines.append(f"(allow file-read* (literal {json.dumps(str(tools['beads']))}))")
    lines += [f"(allow file-write* (subpath {json.dumps(str(work))}))",
              '(allow file-write-data (literal "/dev/null"))']
    return "\n".join(lines)


def snapshot(root):
    result = {}
    for path in sorted(root.rglob("*")):
        info = path.lstat()
        value = (os.readlink(path) if path.is_symlink() else
                 hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None)
        result[str(path.relative_to(root))] = (
            info.st_mode, info.st_mtime_ns if path.is_file() else None, value)
    return result


def differences(before, after):
    return sorted(key for key in before.keys() | after.keys()
                  if before.get(key) != after.get(key))


class Rpc:
    """Finite newline-JSON app-server dialogue, not a session/model client."""
    METHODS = {"initialize", "skills/list", "config/read"}

    def __init__(self, argv, cwd, env, timeout=TIMEOUT):
        self.argv, self.timeout = argv, timeout
        self.owner = S.supervised_process(
            [str(a) for a in argv], env, timeout + 5, cwd=cwd, stdin=True,
            binary=True, max_output=4 * 1024 * 1024)
        self.session = self.owner.__enter__()
        self.proc = self.session.proc
        try:
            self.session.check()
        except Exception:
            self.owner.__exit__(*sys.exc_info())
            raise
        self.deadline = time.monotonic() + timeout
        self.pending, self.stderr, self.size, self.next_id = b"", b"", 0, 0
        self.stdout = b""
        self.closed = False
        self.failure = None

    def close(self):
        if self.closed:
            return
        self.closed = True
        exc = self.failure
        # Carry protocol failure into cleanup, but never mistake our own
        # TERM/KILL result for a child that failed before cleanup signaling.
        cleanup_failure = None
        try:
            self.owner.__exit__(type(exc) if exc else None, exc,
                                exc.__traceback__ if exc else None)
        except Exception as raised:
            if raised is not exc:
                cleanup_failure = raised
        rc = self.session.completed_returncode
        out, err = (prefix + bytes(chunk) for prefix, chunk in
                    zip((self.stdout, self.stderr), self.session.drain.chunks))
        out, err = out.decode("utf-8", "replace"), err.decode("utf-8", "replace")
        if cleanup_failure is not None:
            failure = cleanup_failure
        elif rc not in (None, 0):
            failure = subprocess.CalledProcessError(rc, self.argv)
            failure.primary_failure = exc
        else:
            failure = exc
        if failure is not None:
            failure.output, failure.stderr = out, err
            primary = getattr(failure, "primary_failure", None)
            if primary is not None:
                primary.output, primary.stderr = out, err
            if rc is not None:
                failure.returncode = rc
            self.failure = failure
        if cleanup_failure is not None or rc not in (None, 0):
            raise failure

    def send(self, payload):
        try:
            data = (json.dumps(payload) + "\n").encode()
            assert len(data) <= 4 * 1024 * 1024, "RPC input exceeded bounded metadata limit"
            self.session.drain.send(data)
            while self.session.drain.pending_input:
                self.check_deadline()
                self.session.step(min(.02, max(0, self.deadline - time.monotonic())))
            if self.proc.stdin.closed:
                raise BrokenPipeError("app-server stdin closed")
        except BrokenPipeError as exc:
            raise AssertionError("app-server closed stdin before protocol completion") from exc

    def check_deadline(self):
        if time.monotonic() >= self.deadline:
            raise subprocess.TimeoutExpired("app-server protocol", self.timeout)

    def request(self, method, params):
        try:
            return self._request(method, params)
        except Exception as exc:
            self.failure = exc
            raise

    def _request(self, method, params):
        assert method in self.METHODS, "non-introspection RPC forbidden"
        self.next_id += 1
        request_id = self.next_id
        self.send({"id": request_id, "method": method, "params": params})
        while True:
            while b"\n" in self.pending:
                line, self.pending = self.pending.split(b"\n", 1)
                message = shaped(decode(line, f"app-server {method}"), dict,
                                 f"app-server {method} response")
                if "id" in message and "method" in message:
                    # Only documented approval requests justify a blocker.
                    if message["method"] in (
                            "item/commandExecution/requestApproval",
                            "item/fileChange/requestApproval"):
                        raise Blocked("server requested tool approval; no response sent",
                                      kind="denied-approval")
                    raise AssertionError("unexpected server request; no response sent")
                if "id" not in message:
                    shaped(message.get("method"), str, f"app-server {method} notification.method")
                    if "params" in message:
                        assert type(message["params"]) in (dict, list), \
                            f"app-server {method} notification.params: expected dict/list"
                    # Unknown notification names are valid; only check the envelope.
                    continue
                if "id" in message:
                    shaped(message["id"], int, f"app-server {method} response id")
                if message.get("id") == request_id:
                    assert not ("error" in message and "result" in message), \
                        f"app-server {method}: response has both result and error"
                    if "error" in message:
                        error = shaped(message["error"], dict, f"app-server {method} error")
                        code = shaped(error.get("code"), int, f"app-server {method} error.code")
                        shaped(error.get("message"), str, f"app-server {method} error.message")
                        if code == -32601:  # JSON-RPC Method not found.
                            raise Blocked(f"app-server {method}: native RPC error code {code}")
                        raise AssertionError(f"app-server {method}: native RPC error code {code}")
                    assert "result" in message, f"app-server {method}: RPC response missing result/error"
                    return shaped(message["result"], dict, f"app-server {method} result")
            self.check_deadline()
            drain = self.session.drain
            if drain.streams[0] not in drain.selector.get_map() and not drain.chunks[0]:
                raise AssertionError(f"app-server {method}: EOF before response")
            self.session.step(min(.02, max(0, self.deadline - time.monotonic())))
            self.stdout += bytes(drain.chunks[0])
            self.pending += bytes(drain.chunks[0])
            self.stderr += bytes(drain.chunks[1])
            for chunk in drain.chunks:
                chunk.clear()

    def initialize(self, expected_home):
        response = self.request("initialize", {
            "clientInfo": {"name": "domestique_native_discovery", "version": "1"},
        })
        assert response.get("codexHome") == expected_home, "app-server escaped fixture CODEX_HOME"
        self.send({"method": "initialized"})
        return response


class Harness:
    def __init__(self, work, tools):
        self.work, self.tools = work, tools
        self.env = isolated_env(work, tools)
        self.profile = sandbox_profile(work, tools)
        self.results = []
        self.versions = {}

    def result(self, component, status, **data):
        if status == "BLOCKED":
            assert data.get("blocker_kind") in BLOCKER_KINDS
        self.results.append(dict(component=component, status=status, **data))

    def safe(self, argv, cwd=None, **kwargs):
        if not self.tools["sandbox-exec"]:
            raise Blocked("sandbox-exec unavailable; no native process invoked", kind="absent-tool")
        return run([self.tools["sandbox-exec"], "-p", self.profile, *argv],
                   cwd or self.work, self.env, **kwargs)

    def validate_isolation(self):
        # A sibling sentinel is our own temporary data, never real user data.
        with tempfile.TemporaryDirectory(prefix="domestique-denied-") as outside:
            sentinel = Path(outside).resolve() / "sentinel"
            sentinel.write_text("fixture-only")
            script = (
                "import pathlib,socket,sys\n"
                "pathlib.Path(sys.argv[1]).write_text('allowed')\n"
                "try:\n pathlib.Path(sys.argv[2]).read_text()\n"
                "except PermissionError: pass\n"
                "else: sys.exit(11)\n"
                "try:\n pathlib.Path(sys.argv[2]).write_text('denied')\n"
                "except PermissionError: pass\n"
                "else: sys.exit(12)\n"
                "try:\n socket.socket().bind(('127.0.0.1',0))\n"
                "except PermissionError: pass\n"
                "else: sys.exit(13)\n"
                "try:\n socket.socket().connect(('127.0.0.1',9))\n"
                "except PermissionError: pass\n"
                "else: sys.exit(14)\n"
                "print('write-inside/read-outside/write-outside/network-bind/connect-deny: OK')\n"
            )
            result = self.safe([Path(sys.executable).resolve(), "-c", script,
                                self.work / "allowed", sentinel])
            if result.returncode or sentinel.read_text() != "fixture-only":
                raise AssertionError("sandbox validation failed: " +
                              (result.stderr or result.stdout or str(result.returncode))[:1000])
        self.result("isolation", "STATIC_ONLY", diagnostic=result.stdout.strip(),
                    policy="default deny; no network or mach/Keychain IPC grants")

    def setup(self):
        if not self.tools["git"]:
            raise Blocked("git unavailable; fixtures cannot be prepared", kind="absent-tool")
        self.repos = [self.work / name for name in ("A", "B")]
        for repo in self.repos:
            repo.mkdir()
            result = self.safe([self.tools["git"], "init", "-q", repo])
            if result.returncode:
                raise AssertionError("isolated git init: " + result.stderr[:1000])
            # Empty templates suppress sample hooks AND Git's ordinary info
            # directory. Supply the normal private-exclude container ourselves.
            (repo / ".git/info").mkdir(exist_ok=True)
            (repo / ".git/info/exclude").write_text("")
        before = [snapshot(repo) for repo in self.repos]
        self.install("--global", "--platform", "all")
        assert before == [snapshot(repo) for repo in self.repos], "global install wrote projects"
        self.result("installer-global", "STATIC_ONLY", untouched_repos=["A", "B"])

    def install(self, *args):
        # This harness qualifies the retained preview's global advertisements,
        # never V2/1 project-only discovery. Do not use the public gated writer.
        import preview_fixture
        retained = self.work / "retained-domestique2.sh"
        if not retained.exists():
            retained = preview_fixture.materialize(self.work)
        # Fixture setup is separate from the native metadata-command budget.
        budget = 120
        operation = ("local fixture installation" if "--local" in args else
                     "global fixture installation")
        argv = [self.tools["sandbox-exec"], "-p",
                sandbox_profile(self.work, self.tools, installer=True),
                "/bin/bash", retained, *args]
        started = time.monotonic()
        try:
            result = run(argv, self.work, self.env, timeout=budget)
            if result.returncode:
                error = AssertionError(f"installer exited nonzero: {result.returncode}")
                error.returncode = result.returncode
                error.output, error.stderr = result.stdout, result.stderr
                raise error
        except FAILURES as exc:
            context = {"operation": operation, "budget_seconds": budget,
                       "elapsed_seconds": time.monotonic() - started}
            # Keep exception identity, kind, output and cleanup/primary links.
            # Reports need no sandbox profile, argv or installer output dump.
            failure = exc
            while failure is not None:
                failure.fixture_installation = context
                failure.fixture_diagnostic = str(failure).replace(
                    str(argv), "<fixture installer>").replace(
                    str([str(arg) for arg in argv]), "<fixture installer>")
                failure = getattr(failure, "primary_failure", None)
            raise

    def inspect(self, name):
        path = self.tools[name]
        if not path:
            raise Blocked(f"{name}: executable unavailable; not installed by harness", kind="absent-tool")
        version = self.safe([path, "--version"])
        if version.returncode:
            raise AssertionError(f"{name} --version exit {version.returncode}: {version.stderr[:1000]}")
        lines = version.stdout.strip().splitlines()
        assert lines, f"{name} --version: empty output"
        self.versions[name] = lines[0]
        help_result = self.safe([path, "--help"])
        if help_result.returncode:
            raise AssertionError(f"{name} --help exit {help_result.returncode}: {help_result.stderr[:1000]}")
        text = help_result.stdout + help_result.stderr
        self.result(name + "-interface", "STATIC_ONLY", executable=str(path),
                    version=self.versions[name], commands=["--version", "--help"])
        return text

    def command(self, name, args, cwd=None):
        result = self.safe([self.tools[name], *args], cwd=cwd)
        if result.returncode:
            raise AssertionError(f"{name} {' '.join(args)} exit {result.returncode}: " +
                          (result.stderr or result.stdout)[:1000])
        return result.stdout

    def prepare_claude(self, help_text):
        if not re.search(r"^\s+agents \[", help_text, re.M):
            raise Blocked("claude --help: no supported agents introspection command")
        text = self.command("claude", ["agents", "--help"])
        if "Manage background agents" in text and "Print active sessions" in text:
            raise Blocked("claude agents --help: 'Manage background agents'; --json prints "
                          "active sessions, not configured role IDs. No session view launched. "
                          "Top-level --help offers no non-model skill listing.")
        raise Blocked("claude agents --help: unrecognized metadata interface; not invoked")

    def prepare_copilot(self, help_text):
        if not re.search(r"^\s+skill\s", help_text, re.M):
            raise Blocked("copilot --help: no supported skill subcommand")
        text = self.command("copilot", ["skill", "--help"])
        if not re.search(r"^\s+list ", text, re.M):
            raise Blocked("copilot skill --help: list unavailable")
        text = self.command("copilot", ["skill", "list", "--help"])
        if "--json" not in text or "List all available skills" not in text:
            raise Blocked("copilot skill list --help: unsupported listing format")
        self.result("copilot-roles", "BLOCKED", version=self.versions["copilot"],
                    blocker_kind="unsupported-interface",
                    command="copilot --help",
                    diagnostic="--agent selects a session agent; no non-model role-list "
                    "subcommand advertised. No authenticated startup or ACP invoked.")

    def prepare_codex(self, help_text):
        if "app-server" not in help_text:
            raise Blocked("codex --help: app-server unavailable")
        text = self.command("codex", ["app-server", "--help"])
        if "generate-json-schema" not in text or "stdio://" not in text:
            raise Blocked("codex app-server --help: schema or stdio interface unavailable")
        text = self.command("codex", ["app-server", "generate-json-schema", "--help"])
        if "--out" not in text:
            raise Blocked("codex schema generator: --out unavailable")
        schema = self.work / "schema"
        self.command("codex", ["app-server", "generate-json-schema", "--out", str(schema)])
        if not all((schema / name).is_file()
                   for name in ("ClientRequest.json", "ClientNotification.json")):
            raise Blocked("Codex schema bundle layout changed; adapter not invoked")
        requests = shaped(decode((schema / "ClientRequest.json").read_text(),
                                 "codex ClientRequest schema"), dict, "codex ClientRequest schema")
        methods = set()
        for item in shaped(requests.get("oneOf"), list, "codex schema oneOf"):
            properties = shaped(shaped(item, dict, "codex schema request").get("properties"),
                                dict, "codex schema properties")
            method = shaped(properties.get("method"), dict, "codex schema method")
            for value in shaped(method.get("enum"), list, "codex schema method.enum"):
                methods.add(shaped(value, str, "codex schema method name"))
        candidates = sorted(m for m in methods if re.search(r"(agent|role).*/list$", m, re.I))
        self.codex_role_limit = (
            f"Unhandled schema role-list candidates: {candidates}" if candidates else
            "Generated stable schema has no role-list method")
        if not Rpc.METHODS <= methods:
            raise Blocked("Codex generated schema lacks initialize/skills/list/config/read")
        notifications = shaped(decode((schema / "ClientNotification.json").read_text(),
                                      "codex notification schema"), dict, "codex notification schema")
        if "initialized" not in json.dumps(notifications):
            raise Blocked("Codex generated schema lacks initialized notification")
        for file, fields in (
            ("v1/InitializeParams.json", {"clientInfo"}),
            ("v1/InitializeResponse.json", {"codexHome"}),
            ("v2/SkillsListParams.json", {"cwds", "forceReload"}),
            ("v2/SkillsListResponse.json", {"data"}),
            ("v2/ConfigReadParams.json", {"cwd", "includeLayers"}),
            ("v2/ConfigReadResponse.json", {"config"}),
        ):
            path = schema / file
            if not path.is_file():
                raise Blocked(f"Codex schema changed: {file}; adapter not invoked")
            document = shaped(decode(path.read_text(), f"codex schema {file}"),
                              dict, f"codex schema {file}")
            properties = shaped(document.get("properties"), dict, f"codex schema {file} properties")
            if not fields <= properties.keys():
                raise Blocked(f"Codex schema changed: {file}; adapter not invoked")
        self.result("codex-schema", "STATIC_ONLY", methods=sorted(Rpc.METHODS),
                    diagnostic="generated by installed binary; schema is not discovery proof")

    def check_skills(self, name, stage, repo, skills):
        """Check IDs AND native-returned source paths, never parse emitted files."""
        assert name in ("codex", "copilot"), "unsupported skill response grammar"
        shaped(skills, list, f"{name} skills")
        for item in skills:
            shaped(item, dict, f"{name} skill")
            fields = (("name", "path", "description", "scope") if name == "codex"
                      else ("name", "path", "source"))
            for field in fields:
                shaped(item.get(field), str, f"{name} skill.{field}")
            # Codex 0.154.0 SkillMetadata requires enabled:boolean; Copilot
            # 1.0.83 skill list --json always emits enabled:!isDisabled(...).
            # Do not infer truth from a string, number, or a missing field.
            shaped(item.get("enabled"), bool, f"{name} skill.enabled")
        expected_providers = ("codex", "copilot") if name == "copilot" else ("codex",)
        expected = {f"domestique-{p}{suffix}" for p in expected_providers
                    for suffix in ("", "-decompose", "-goal")}
        rows = [s for s in skills if s["name"].startswith("domestique-")]
        assert {s["name"] for s in rows} == expected, f"{name}: unexpected/missing native skill IDs"
        assert len(rows) == len(expected), f"{name}: duplicate skill IDs"
        summaries = []
        for item in rows:
            provider = "copilot" if item["name"].startswith("domestique-copilot") else "codex"
            prefix = ".copilot" if provider == "copilot" else ".agents"
            path = Path(self.env["HOME"]) / prefix / "skills" / item["name"]
            path = path / "SKILL.md" if name == "codex" else path
            assert item["path"] == str(path) and item["enabled"], f"{name}: wrong source/disabled skill"
            source = item["scope"] if name == "codex" else item["source"]
            expected_source = ("user" if name == "codex" else
                               "personal-copilot" if provider == "copilot" else "personal-agents")
            assert source == expected_source, f"{name}: wrong native source scope"
            summaries.append({"name": item["name"], "source": source})
            if stage == "metadata-reload" and item["name"] in ("domestique-codex", "domestique-copilot"):
                assert item["description"] == RELOAD_MARKER, f"{name}: fresh process missed metadata edit"
                summaries[-1]["description"] = item["description"]
        self.result(name + "-skills", "NATIVE_DISCOVERY_OBSERVED", stage=stage,
                    repo=repo.name, version=self.versions[name], skills=summaries)

    def discover_copilot(self, stage, repo):
        text = self.command("copilot", ["skill", "list", "--json"], cwd=repo)
        self.check_skills("copilot", stage, repo, decode(text, "copilot skill list"))

    def discover_codex(self, stage, repo):
        rpc = Rpc([self.tools["sandbox-exec"], "-p", self.profile, self.tools["codex"],
                   "app-server", "--listen", "stdio://"], repo, self.env)
        try:
            rpc.initialize(self.env["CODEX_HOME"])
            response = rpc.request("skills/list", {"cwds": [str(repo)], "forceReload": True})
            entries = shaped(response.get("data"), list, "codex skills/list data")
            assert len(entries) == 1, "codex skills/list: wrong skills cwd count"
            entry = shaped(entries[0], dict, "codex skills/list entry")
            assert entry.get("cwd") == str(repo), "codex skills/list: wrong skills cwd"
            errors = shaped(entry.get("errors"), list, "codex skills/list errors")
            assert errors == [], "codex skills/list: native skill parse errors"
            response = rpc.request("config/read", {"cwd": str(repo), "includeLayers": True})
            config = shaped(response.get("config"), dict, "codex config/read config")
            agents = config.get("agents")
            assert agents is None or type(agents) is dict, "codex config/read config.agents: expected dict/null"
            self.check_skills("codex", stage, repo, entry.get("skills"))
            # config/read is not a role enumeration API. Even a populated config
            # must not be promoted to runtime .codex/agents discovery.
            self.result("codex-roles", "BLOCKED", stage=stage, repo=repo.name,
                        blocker_kind="unsupported-interface",
                        version=self.versions["codex"],
                        command="app-server: initialize; skills/list; config/read",
                        diagnostic="config/read is not agent enumeration; "
                        + ("config.agents=null" if agents is None else "config.agents is present")
                        + ". " + self.codex_role_limit + "; no thread launched.")
        finally:
            rpc.close()

    def observed_step(self, component, callback):
        before = [snapshot(repo) for repo in self.repos]
        try:
            callback()
        except Blocked as exc:
            self.result(component, "BLOCKED", diagnostic=str(exc), blocker_kind=exc.kind)
        except FAILURES as exc:
            self.result(component, "ASSERTION_FAILURE", **failure_fields(exc))
        finally:
            self.result(component + "-project-writes", "STATIC_ONLY",
                        changes={repo.name: differences(old, snapshot(repo))
                                 for repo, old in zip(self.repos, before)})

    def probe(self):
        self.validate_isolation()
        self.setup()
        ready = []
        for name in CLIENTS:
            before = [snapshot(repo) for repo in self.repos]
            try:
                text = self.inspect(name)
                getattr(self, "prepare_" + name)(text)
                ready.append(name)
            except Blocked as exc:
                self.result(name + "-discovery", "BLOCKED",
                            blocker_kind=exc.kind,
                            version=self.versions.get(name, "unavailable"), diagnostic=str(exc))
            except FAILURES as exc:
                self.result(name + "-discovery", "ASSERTION_FAILURE", **failure_fields(exc))
            finally:
                self.result(name + "-help-schema-project-writes", "STATIC_ONLY",
                            changes={repo.name: differences(old, snapshot(repo))
                                     for repo, old in zip(self.repos, before)})
        for stage in ("global-only", "after-local-A-fresh-process", "metadata-reload"):
            if stage == "after-local-A-fresh-process":
                before_b = snapshot(self.repos[1])
                before_global = snapshot(Path(self.env["DOMESTIQUE_HOME"])), snapshot(Path(self.env["HOME"]))
                self.install("--local", self.repos[0], "--platform", "all")
                assert snapshot(self.repos[1]) == before_b, "local A installer changed B"
                assert before_global == (snapshot(Path(self.env["DOMESTIQUE_HOME"])),
                                         snapshot(Path(self.env["HOME"]))), "local A installer changed global state"
                local_ids = []
                for provider, prefix, suffix in (("claude", ".claude", "md"),
                                                  ("codex", ".codex", "toml"),
                                                  ("copilot", ".github", "agent.md")):
                    for role in ("implementer", "reviewer"):
                        name = f"domestique-{provider}-local-{role}"
                        leaf = Path(prefix) / "agents" / f"{name}.{suffix}"
                        assert (self.repos[0] / leaf).is_file(), "local fixture adapter missing"
                        assert not (self.repos[1] / leaf).exists(), "local adapter leaked to B"
                        local_ids.append(name)
                self.result("installer-local-A", "STATIC_ONLY",
                            filesystem_role_ids={"A": local_ids, "B": []},
                            diagnostic="all three providers; profile-only; B unchanged; no Beads")
            if stage == "metadata-reload":
                for provider, directory in (("codex", ".agents"), ("copilot", ".copilot")):
                    path = Path(self.env["HOME"]) / directory / "skills" / f"domestique-{provider}/SKILL.md"
                    text = path.read_text()
                    old = "description: Provider-qualified Domestique ordinary workflow."
                    assert text.count(old) == 1, "fixture skill description format changed"
                    path.write_text(text.replace(old, "description: " + RELOAD_MARKER))
            for name in ready:
                for repo in self.repos:
                    self.observed_step(f"{name}-{stage}-{repo.name}",
                                       lambda n=name, r=repo: getattr(self, "discover_" + n)(stage, r))


def exit_code(results):
    if any(r["status"] == "ASSERTION_FAILURE" or "failure_kind" in r for r in results):
        return 1
    if any(r["status"] == "BLOCKED" for r in results):
        return 2
    return 0 if any(r["status"] == "NATIVE_DISCOVERY_OBSERVED" for r in results) else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="opt in to sandboxed offline probes")
    args = parser.parse_args()
    if sys.flags.optimize:
        print(json.dumps({"status": "ASSERTION_FAILURE", "diagnostic": "run without Python -O/-OO"}))
        return 1
    if not args.run:
        print(json.dumps({"status": "STATIC_ONLY", "diagnostic": "opt in with --run; no clients invoked"}))
        return 2
    tools = resolve_tools()
    with tempfile.TemporaryDirectory(prefix="domestique-native-") as temp:
        harness = Harness(Path(temp).resolve(), tools)
        try:
            harness.probe()
        except Blocked as exc:
            harness.result("prerequisite", "BLOCKED", diagnostic=str(exc), blocker_kind=exc.kind)
            for name in CLIENTS:
                harness.result(name + "-discovery", "BLOCKED",
                               blocker_kind=exc.kind,
                               diagnostic="isolation/setup prerequisite failed; no discovery invoked")
        except FAILURES as exc:
            harness.result("harness", "ASSERTION_FAILURE", **failure_fields(exc))
        print(json.dumps({
            "date": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "scope": "native-discovery-only; no auth/inference/MCP/Beads",
            "counts": {status: sum(r["status"] == status for r in harness.results)
                       for status in ("NATIVE_DISCOVERY_OBSERVED", "BLOCKED",
                                      "ASSERTION_FAILURE", "STATIC_ONLY")},
            "results": harness.results,
        }, indent=2))
        return exit_code(harness.results)


if __name__ == "__main__":
    sys.exit(main())
