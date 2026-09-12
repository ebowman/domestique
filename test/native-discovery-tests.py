"""OFFLINE harness regressions with synthetic protocol responses, NOT native proof."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location(
    "native_discovery", Path(__file__).with_name("native-discovery.py"))
N = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(N)
NON_OBJECTS = (True, False, None, 7, "private-payload", [])


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="domestique-protocol-test-")
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name).resolve()
        self.tools = {key: None for key in (*N.CLIENTS, "node", "git", "sandbox-exec")}
        self.h = N.Harness(self.work, self.tools)
        self.h.versions["codex"] = "synthetic-test-only"

    def rpc(self, script, timeout=2):
        rpc = N.Rpc([sys.executable, "-u", "-c", script],
                    self.work, self.h.env, timeout=timeout)
        self.addCleanup(rpc.close)
        return rpc

    def response_rpc(self, response):
        return self.rpc("import sys,json\n"
                        "request=json.loads(sys.stdin.readline())\n"
                        f"print(json.dumps({response!r}),flush=True)\n")

    def skills(self):
        return [{"name": f"domestique-codex{suffix}", "enabled": True, "scope": "user",
                 "description": N.RELOAD_MARKER,
                 "path": str(Path(self.h.env["HOME"]) / ".agents/skills" /
                             f"domestique-codex{suffix}/SKILL.md")}
                for suffix in ("", "-decompose", "-goal")]

    def check_skills(self, skills, stage="global-only"):
        self.h.check_skills("codex", stage, self.work / "A", skills)

    def repos(self, harness=None):
        harness = harness or self.h
        harness.repos = [harness.work / name for name in ("A", "B")]
        for repo in harness.repos:
            repo.mkdir(exist_ok=True)

    def copilot_skills(self):
        return [{"name": f"domestique-{provider}{suffix}", "enabled": True,
                 "description": N.RELOAD_MARKER,
                 "source": f"personal-{source}",
                 "path": str(Path(self.h.env["HOME"]) / prefix / "skills" /
                             f"domestique-{provider}{suffix}")}
                for provider, source, prefix in (("codex", "agents", ".agents"),
                                                ("copilot", "copilot", ".copilot"))
                for suffix in ("", "-decompose", "-goal")]

    def failed_step(self, component, callback, diagnostic):
        self.repos()
        self.h.results.clear()
        self.h.observed_step(component, callback)
        self.assertEqual(self.h.results[0]["component"], component)
        self.assertEqual(self.h.results[0]["status"], "ASSERTION_FAILURE")
        self.assertIn(diagnostic, self.h.results[0]["diagnostic"])
        self.assertNotIn("private-payload", self.h.results[0]["diagnostic"])
        self.assertEqual(self.h.results[1]["changes"], {"A": [], "B": []})
        self.assertEqual(N.exit_code(self.h.results), 1)
        self.assertNotIn("NATIVE_DISCOVERY_OBSERVED", [r["status"] for r in self.h.results])

    def cli_report(self, probe):
        # Exercise real main/report/exit, substituting only the offline probe
        # boundary. No synthetic result is native evidence.
        with mock.patch.object(sys, "argv", ["native-discovery.py", "--run"]), \
                mock.patch.object(N, "resolve_tools", return_value=self.tools), \
                mock.patch.object(N.Harness, "probe", probe), \
                mock.patch("builtins.print") as output:
            code = N.main()
        report = json.loads(output.call_args.args[0])
        return code, report

    def test_no_opt_in_never_resolves_or_runs_clients(self):
        with mock.patch.object(sys, "argv", ["native-discovery.py"]), \
                mock.patch.object(N, "resolve_tools", side_effect=AssertionError("must not resolve")), \
                mock.patch("builtins.print") as output:
            self.assertEqual(N.main(), 2)
            self.assertEqual(json.loads(output.call_args.args[0])["status"], "STATIC_ONLY")

    def test_environment_is_constructed_not_copied(self):
        extra = self.work / "env"
        extra.mkdir()
        with mock.patch.dict(os.environ, {"UNRELATED_ENV": "fixture", "HTTP_PROXY": "fixture",
                                          "BASH_ENV": "fixture", "GIT_CONFIG_COUNT": "99"}):
            env = N.isolated_env(extra, self.tools)
        for key in ("UNRELATED_ENV", "HTTP_PROXY", "BASH_ENV"):
            self.assertNotIn(key, env)
        self.assertEqual(env["GIT_CONFIG_COUNT"], "1")
        self.assertEqual(env["GIT_CONFIG_GLOBAL"], "/dev/null")
        self.assertEqual(env["OPENSSL_CONF"], "/dev/null")
        self.assertFalse(Path(env["DOMESTIQUE_HOME"]).exists())
        for key in ("HOME", "XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME", "CODEX_HOME"):
            self.assertTrue(Path(env[key]).is_relative_to(extra))

    def test_sandbox_has_no_network_or_keychain_ipc_grant(self):
        profile = self.h.profile
        self.assertIn("(deny default)", profile)
        self.assertNotIn("(allow network", profile)
        self.assertNotIn("mach-lookup", profile)
        self.assertNotIn(str(N.ROOT), profile)
        self.assertIn(str(N.ROOT), N.sandbox_profile(self.work, self.tools, installer=True))
        self.assertEqual(profile.count("(allow file-write*"), 1)

    def test_missing_sandbox_stops_before_process(self):
        with mock.patch.object(N, "run", side_effect=AssertionError("must not run")):
            with self.assertRaisesRegex(N.Blocked, "sandbox-exec unavailable"):
                self.h.safe(["unused"])

    def test_missing_client_is_explicit_blocker(self):
        with self.assertRaisesRegex(N.Blocked, "executable unavailable"):
            self.h.inspect("copilot")

    def test_exit_codes_do_not_promote_blockers(self):
        self.assertEqual(N.exit_code([{"status": "NATIVE_DISCOVERY_OBSERVED"}]), 0)
        self.assertEqual(N.exit_code([{"status": "BLOCKED"}]), 2)
        self.assertEqual(N.exit_code([{"status": "BLOCKED"}, {"status": "ASSERTION_FAILURE"}]), 1)
        self.assertEqual(N.exit_code([{"status": "STATIC_ONLY"}]), 2)

    def test_snapshots_report_changes(self):
        repo = self.work / "A"
        repo.mkdir()
        before = N.snapshot(repo)
        (repo / "native-cache").write_text("fixture")
        self.assertEqual(N.differences(before, N.snapshot(repo)), ["native-cache"])
        before = N.snapshot(repo)
        (repo / "native-cache").write_text("modified")
        self.assertEqual(N.differences(before, N.snapshot(repo)), ["native-cache"])

    def test_synthetic_skill_response_classification_only(self):
        self.check_skills(self.skills())
        self.assertEqual(self.h.results[-1]["status"], "NATIVE_DISCOVERY_OBSERVED")
        # This unit test exercises the classifier; it is never native evidence.

    def test_missing_skill_is_assertion_failure(self):
        with self.assertRaisesRegex(AssertionError, "missing"):
            self.check_skills(self.skills()[:-1])

    def test_duplicate_skill_is_assertion_failure(self):
        skills = self.skills()
        with self.assertRaisesRegex(AssertionError, "duplicate"):
            self.check_skills(skills + [skills[0]])

    def test_wrong_source_path_is_assertion_failure(self):
        skills = self.skills()
        skills[0]["path"] = "/not-the-fixture"
        with self.assertRaisesRegex(AssertionError, "wrong source"):
            self.check_skills(skills)

    def test_disabled_skill_is_assertion_failure(self):
        skills = self.skills()
        skills[0]["enabled"] = False
        with self.assertRaisesRegex(AssertionError, "disabled"):
            self.check_skills(skills)

    def test_enabled_requires_actual_boolean_for_each_provider(self):
        for provider, factory in (("codex", self.skills), ("copilot", self.copilot_skills)):
            for enabled in ("false", "true", "", 0, 1, None, {}, []):
                with self.subTest(provider=provider, enabled=enabled):
                    skills = factory()
                    skills[0]["enabled"] = enabled
                    self.failed_step(provider + "-synthetic", lambda: self.h.check_skills(
                        provider, "global-only", self.work / "A", skills), "skill.enabled: expected bool")

    def test_missing_enabled_matches_supported_provider_grammars(self):
        # Installed Codex schema requires boolean; installed Copilot list
        # serializer unconditionally emits a boolean (not an optional field).
        for provider, factory in (("codex", self.skills), ("copilot", self.copilot_skills)):
            with self.subTest(provider=provider):
                skills = factory()
                del skills[0]["enabled"]
                self.failed_step(provider, lambda: self.h.check_skills(
                    provider, "global-only", self.work / "A", skills), "skill.enabled")

    def test_copilot_disabled_and_optional_description(self):
        skills = self.copilot_skills()
        del skills[0]["description"]  # Optional outside the qualified reload check.
        self.h.versions["copilot"] = "synthetic-test-only"
        self.h.check_skills("copilot", "global-only", self.work / "A", skills)
        self.assertEqual(self.h.results[-1]["status"], "NATIVE_DISCOVERY_OBSERVED")
        skills[0]["enabled"] = False
        self.failed_step("copilot", lambda: self.h.check_skills(
            "copilot", "global-only", self.work / "A", skills), "disabled")

    def test_copilot_qualified_metadata_reload(self):
        self.h.versions["copilot"] = "synthetic-test-only"
        skills = self.copilot_skills()
        self.h.check_skills("copilot", "metadata-reload", self.work / "A", skills)
        self.assertEqual(len(self.h.results[-1]["skills"]), 6)
        self.assertEqual(sum("description" in s for s in self.h.results[-1]["skills"]), 2)
        for index in (0, 3):
            with self.subTest(index=index):
                stale = self.copilot_skills()
                stale[index]["description"] = "stale"
                self.failed_step("copilot-reload", lambda: self.h.check_skills(
                    "copilot", "metadata-reload", self.work / "A", stale), "missed metadata")

    def test_skill_list_and_rows_have_typed_shapes(self):
        for provider in ("codex", "copilot"):
            for value in (*NON_OBJECTS[:-1], {}, [True], [None], [7], ["private-payload"], [[]],
                          [{"name": None}]):
                with self.subTest(provider=provider, value=value):
                    self.failed_step(provider, lambda: self.h.check_skills(
                        provider, "global-only", self.work / "A", value), "expected")

    def test_wrong_scope_is_assertion_failure(self):
        skills = self.skills()
        skills[0]["scope"] = "repo"
        with self.assertRaisesRegex(AssertionError, "source scope"):
            self.check_skills(skills)

    def test_reload_requires_observed_description(self):
        skills = self.skills()
        self.check_skills(skills, "metadata-reload")
        skills[0]["description"] = "stale"
        with self.assertRaisesRegex(AssertionError, "missed metadata"):
            self.check_skills(skills, "metadata-reload")

    def test_initialized_and_list_responses_required(self):
        rpc = self.rpc(
            "import sys,json\n"
            "for line in sys.stdin:\n"
            " r=json.loads(line)\n"
            " if r['method']=='initialized': continue\n"
            f" result={{'codexHome':{self.h.env['CODEX_HOME']!r}}} "
            "if r['method']=='initialize' else {'data':[]}\n"
            " print(json.dumps({'id':r['id'],'result':result}),flush=True)\n")
        rpc.initialize(self.h.env["CODEX_HOME"])
        self.assertEqual(rpc.request("skills/list", {"cwds": []}), {"data": []})

    def test_initialize_wrong_home_is_assertion_failure(self):
        rpc = self.response_rpc({"id": 1, "result": {"codexHome": "/wrong-home"}})
        with self.assertRaisesRegex(AssertionError, "escaped"):
            rpc.initialize(self.h.env["CODEX_HOME"])

    def test_alive_server_without_protocol_is_blocked_and_reaped(self):
        rpc = self.rpc("import time; time.sleep(30)", timeout=0.1)
        with self.assertRaisesRegex(N.Blocked, "protocol timeout"):
            rpc.request("skills/list", {})
        rpc.close()
        self.assertIsNotNone(rpc.proc.poll())

    def test_native_error_is_blocked_not_discovered(self):
        rpc = self.response_rpc({"id": 1, "error": {"code": -32601, "message": "unsupported"}})
        with self.assertRaisesRegex(N.Blocked, "native RPC error code -32601"):
            rpc.request("skills/list", {})

    def test_eof_is_blocked_not_discovered(self):
        rpc = self.rpc("import sys; sys.stdin.readline()")
        with self.assertRaisesRegex(N.Blocked, "EOF"):
            rpc.request("skills/list", {})

    def test_malformed_json_is_assertion_failure(self):
        rpc = self.rpc("import sys; sys.stdin.readline(); print('not-json',flush=True)")
        with self.assertRaisesRegex(AssertionError, "malformed JSON"):
            rpc.request("skills/list", {})

    def test_rpc_non_object_envelopes_and_results_fail_structurally(self):
        for method in sorted(N.Rpc.METHODS):
            for value in NON_OBJECTS:
                for payload in (value, {"id": 1, "result": value}):
                    with self.subTest(method=method, payload=payload):
                        rpc = self.response_rpc(payload)
                        self.failed_step("codex-" + method,
                                         lambda: rpc.request(method, {}), "expected dict")
                        rpc.close()
                        self.assertIsNotNone(rpc.proc.poll())

    def test_rpc_malformed_errors_and_ambiguous_response_fail(self):
        errors = (*NON_OBJECTS, {}, {"code": True, "message": "private-payload"},
                  {"code": -1, "message": None}, {"code": "private-payload", "message": "error"})
        for method in sorted(N.Rpc.METHODS):
            for error in errors:
                with self.subTest(method=method, error=error):
                    rpc = self.response_rpc({"id": 1, "error": error})
                    self.failed_step("codex-" + method, lambda: rpc.request(method, {}), "error")
                    rpc.close()
            rpc = self.response_rpc({"id": 1, "result": {},
                                     "error": {"code": -1, "message": "private-payload"}})
            self.failed_step("codex-" + method, lambda: rpc.request(method, {}), "both result and error")
            rpc.close()

    def test_rpc_invalid_response_id_is_not_boolean_equal_success(self):
        for value in (True, None, "1", [], {}):
            with self.subTest(value=value):
                rpc = self.response_rpc({"id": value, "result": {}})
                self.failed_step("codex-initialize", lambda: rpc.initialize(
                    self.h.env["CODEX_HOME"]), "response id: expected int")
                rpc.close()

    def dialogue(self, harness, method, result, notification=None):
        """Real stdio framing with only one response replaced by malformed data."""
        repo = harness.repos[0]
        valid = {
            "initialize": {"codexHome": harness.env["CODEX_HOME"]},
            "skills/list": {"data": [{"cwd": str(repo), "errors": [], "skills": self.skills()}]},
            "config/read": {"config": {"agents": None}},
        }
        valid[method] = result
        return ("import sys,json\n"
                f"responses={valid!r}\n"
                "for line in sys.stdin:\n"
                " r=json.loads(line)\n"
                " if r['method']=='initialized': continue\n"
                f" if r['method']=={method!r} and {notification is not None!r}:\n"
                f"  print(json.dumps({notification!r}),flush=True)\n"
                " print(json.dumps({'id':r['id'],'result':responses[r['method']]}),flush=True)\n")

    def test_invalid_notification_method_before_valid_reply_fails(self):
        self.repos()
        self.h.codex_role_limit = "synthetic schema has no role-list method"
        for method, result in (
            ("initialize", {"codexHome": self.h.env["CODEX_HOME"]}),
            ("skills/list", {"data": [{"cwd": str(self.h.repos[0]),
                                      "errors": [], "skills": self.skills()}]}),
            ("config/read", {"config": {"agents": None}}),
        ):
            for value in ([], ["private-payload"], None, {"private-payload": 1},
                          True, False, 7, 1.5):
                with self.subTest(method=method, value=value):
                    rpc = self.rpc(self.dialogue(
                        self.h, method, result,
                        {"method": value, "params": {"private-payload": "private-payload"}}))
                    with mock.patch.object(N, "Rpc", return_value=rpc):
                        self.failed_step("codex-global-only-A", lambda: self.h.discover_codex(
                            "global-only", self.h.repos[0]),
                            f"app-server {method} notification.method: expected str")
                    self.assertIsNotNone(rpc.proc.poll())

    def test_invalid_notification_params_before_valid_reply_fails(self):
        self.repos()
        self.h.codex_role_limit = "synthetic schema has no role-list method"
        for value in (None, True, False, 7, 1.5, "private-payload"):
            with self.subTest(value=value):
                rpc = self.rpc(self.dialogue(
                    self.h, "initialize", {"codexHome": self.h.env["CODEX_HOME"]},
                    {"method": "private-payload", "params": value}))
                with mock.patch.object(N, "Rpc", return_value=rpc):
                    self.failed_step("codex-global-only-A", lambda: self.h.discover_codex(
                        "global-only", self.h.repos[0]),
                        "app-server initialize notification.params: expected dict/list")
                self.assertIsNotNone(rpc.proc.poll())

    def test_valid_unknown_notification_before_valid_reply_is_ignored(self):
        self.repos()
        self.h.codex_role_limit = "synthetic schema has no role-list method"
        for fields in ({}, {"params": {}}, {"params": ["private-payload"]},
                       {"jsonrpc": "2.0", "params": {"private-payload": True}}):
            with self.subTest(fields=fields):
                self.h.results.clear()
                rpc = self.rpc(self.dialogue(
                    self.h, "initialize", {"codexHome": self.h.env["CODEX_HOME"]},
                    {"method": "unknown/future-event", **fields}))
                with mock.patch.object(N, "Rpc", return_value=rpc):
                    self.h.observed_step("codex-global-only-A", lambda: self.h.discover_codex(
                        "global-only", self.h.repos[0]))
                self.assertEqual([r["status"] for r in self.h.results],
                                 ["NATIVE_DISCOVERY_OBSERVED", "BLOCKED", "STATIC_ONLY"])
                self.assertEqual(N.exit_code(self.h.results), 2)
                self.assertIsNotNone(rpc.proc.poll())

    def test_codex_nested_result_shapes_fail_before_observation(self):
        self.repos()
        cases = [("initialize", {}), ("initialize", {"codexHome": []})]
        for value in NON_OBJECTS:
            cases += [("skills/list", {"data": value}),
                      ("skills/list", {"data": [value]}),
                      ("skills/list", {"data": [{"cwd": str(self.h.repos[0]),
                                               "errors": value, "skills": []}]}),
                      ("config/read", {"config": value})]
        cases += [("skills/list", {}), ("config/read", {}),
                  ("skills/list", {"data": [{"cwd": str(self.h.repos[0]), "errors": []}]}),
                  ("config/read", {"config": {"agents": []}})]
        for method, result in cases:
            with self.subTest(method=method, result=result):
                rpc = self.rpc(self.dialogue(self.h, method, result))
                with mock.patch.object(N, "Rpc", return_value=rpc):
                    self.failed_step("codex-global-only-A", lambda: self.h.discover_codex(
                        "global-only", self.h.repos[0]), "codex" if method != "initialize" else "fixture")
                self.assertIsNotNone(rpc.proc.poll())

    def test_cli_rpc_failure_report_and_exit(self):
        def probe(harness):
            self.repos(harness)
            rpc = self.response_rpc([])
            with mock.patch.object(N, "Rpc", return_value=rpc):
                harness.observed_step("codex-global-only-A", lambda: harness.discover_codex(
                    "global-only", harness.repos[0]))
            self.assertIsNotNone(rpc.proc.poll())

        code, report = self.cli_report(probe)
        self.assertEqual(code, 1)
        self.assertEqual(report["counts"], {"NATIVE_DISCOVERY_OBSERVED": 0, "BLOCKED": 0,
                                           "ASSERTION_FAILURE": 1, "STATIC_ONLY": 1})
        self.assertEqual(report["results"][0], {
            "component": "codex-global-only-A", "status": "ASSERTION_FAILURE",
            "diagnostic": "app-server initialize response: expected dict"})

    def test_cli_malformed_enabled_is_failure_not_native_proof(self):
        def probe(harness):
            self.repos(harness)
            skills = self.copilot_skills()
            skills[0]["enabled"] = "false"
            with mock.patch.object(harness, "command", return_value=json.dumps(skills)):
                harness.observed_step("copilot-global-only-A", lambda: harness.discover_copilot(
                    "global-only", harness.repos[0]))

        code, report = self.cli_report(probe)
        self.assertEqual(code, 1)
        self.assertEqual(report["counts"]["NATIVE_DISCOVERY_OBSERVED"], 0)
        self.assertEqual(report["counts"]["ASSERTION_FAILURE"], 1)
        self.assertEqual(report["results"][0], {
            "component": "copilot-global-only-A", "status": "ASSERTION_FAILURE",
            "diagnostic": "copilot skill.enabled: expected bool"})

    def test_copilot_json_entrypoint_rejects_non_list_and_malformed_json(self):
        for text in ("not-json-private-payload", *(json.dumps(v) for v in NON_OBJECTS), "{}"):
            with self.subTest(text=text):
                with mock.patch.object(self.h, "command", return_value=text):
                    self.failed_step("copilot-global-only-A", lambda: self.h.discover_copilot(
                        "global-only", self.work / "A"), "copilot")

    def test_valid_config_never_proves_role_discovery(self):
        self.repos()
        self.h.codex_role_limit = "synthetic schema has no role-list method"
        for agents in (None, {"reviewer": {"description": "synthetic only"}}):
            with self.subTest(agents=agents):
                self.h.results.clear()
                rpc = self.rpc(self.dialogue(self.h, "config/read", {"config": {"agents": agents}}))
                with mock.patch.object(N, "Rpc", return_value=rpc):
                    self.h.observed_step("codex-global-only-A", lambda: self.h.discover_codex(
                        "global-only", self.h.repos[0]))
                self.assertEqual([(r["component"], r["status"]) for r in self.h.results], [
                    ("codex-skills", "NATIVE_DISCOVERY_OBSERVED"), ("codex-roles", "BLOCKED"),
                    ("codex-global-only-A-project-writes", "STATIC_ONLY")])
                self.assertEqual(N.exit_code(self.h.results), 2)
                self.assertIsNotNone(rpc.proc.poll())

    def test_cli_empty_version_failure_report_and_exit(self):
        for provider in N.CLIENTS:
            for stdout in ("", " \n\t "):
                with self.subTest(provider=provider, stdout=stdout):
                    def probe(harness):
                        self.repos(harness)
                        harness.tools[provider] = Path("/synthetic-client")
                        result = subprocess.CompletedProcess([], 0, stdout, "private-payload")
                        with mock.patch.object(harness, "safe", return_value=result) as safe:
                            harness.observed_step(provider + "-interface",
                                                  lambda: harness.inspect(provider))
                        self.assertEqual(safe.call_count, 1)
                        self.assertNotIn(provider, harness.versions)

                    code, report = self.cli_report(probe)
                    self.assertEqual(code, 1)
                    self.assertEqual(report["counts"]["NATIVE_DISCOVERY_OBSERVED"], 0)
                    self.assertEqual(report["counts"]["ASSERTION_FAILURE"], 1)
                    self.assertEqual(report["results"][0], {
                        "component": provider + "-interface", "status": "ASSERTION_FAILURE",
                        "diagnostic": provider + " --version: empty output"})

    def test_well_formed_version_is_unchanged(self):
        for provider in N.CLIENTS:
            with self.subTest(provider=provider):
                self.h.tools[provider] = Path("/synthetic-client")
                with mock.patch.object(self.h, "safe", side_effect=[
                    subprocess.CompletedProcess([], 0, " client 1.2.3 \nextra\n", ""),
                    subprocess.CompletedProcess([], 0, "help", ""),
                ]):
                    self.assertEqual(self.h.inspect(provider), "help")
                self.assertEqual(self.h.versions[provider], "client 1.2.3 ")
                self.assertEqual(self.h.results[-1]["status"], "STATIC_ONLY")

    def test_malformed_rpc_reaps_exact_process_group_including_child(self):
        self.check_rpc_process_group_reaped([[]], "response: expected dict")

    def test_malformed_notification_before_valid_reply_reaps_child(self):
        self.check_rpc_process_group_reaped([
            {"method": ["private-payload"], "params": {}},
            {"id": 1, "result": {"codexHome": self.h.env["CODEX_HOME"]}},
        ], "notification.method: expected str")

    def check_rpc_process_group_reaped(self, messages, diagnostic):
        pidfile = self.work / "child-pid"
        script = ("import sys,subprocess,pathlib,time,json\n"
                  "sys.stdin.readline()\n"
                  "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])\n"
                  f"pathlib.Path({str(pidfile)!r}).write_text(str(child.pid))\n"
                  f"for message in {messages!r}: print(json.dumps(message),flush=True)\n"
                  "time.sleep(30)\n")
        rpc = self.rpc(script)
        self.failed_step("codex-initialize", lambda: rpc.initialize(
            self.h.env["CODEX_HOME"]), diagnostic)
        with mock.patch.object(N.os, "killpg", wraps=os.killpg) as kill:
            rpc.close()
        kill.assert_called_once_with(rpc.proc.pid, N.signal.SIGKILL)
        self.assertIsNotNone(rpc.proc.poll())
        child = subprocess.run(["/bin/ps", "-p", pidfile.read_text(), "-o", "stat="],
                               capture_output=True, text=True, timeout=5)
        self.assertTrue(not child.stdout.strip() or child.stdout.strip().startswith("Z"),
                        "synthetic stdio descendant is still running")

    def test_missing_result_is_assertion_failure(self):
        rpc = self.response_rpc({"id": 1})
        with self.assertRaisesRegex(AssertionError, "missing result"):
            rpc.request("skills/list", {})

    def test_unexpected_server_request_never_approved(self):
        rpc = self.response_rpc({"id": 999, "method": "unexpected"})
        with self.assertRaisesRegex(N.Blocked, "unexpected server request"):
            rpc.request("skills/list", {})

    def test_non_introspection_request_is_rejected(self):
        rpc = self.rpc("import time; time.sleep(30)")
        with self.assertRaisesRegex(AssertionError, "forbidden"):
            rpc.request("turn/start", {})

    def test_command_timeout_is_blocked_and_group_reaped(self):
        pidfile = self.work / "pid"
        script = f"import os,time,pathlib; pathlib.Path({str(pidfile)!r}).write_text(str(os.getpid())); time.sleep(30)"
        with self.assertRaisesRegex(N.Blocked, "timeout"):
            N.run([sys.executable, "-c", script], self.work, self.h.env, timeout=0.5)
        with self.assertRaises(ProcessLookupError):
            os.kill(int(pidfile.read_text()), 0)

    def test_failed_probe_still_reports_project_writes(self):
        self.h.repos = [self.work / "A", self.work / "B"]
        for repo in self.h.repos:
            repo.mkdir()

        def fail():
            (self.h.repos[0] / "cache").write_text("fixture")
            raise N.Blocked("synthetic runtime refusal")

        self.h.observed_step("synthetic", fail)
        self.assertEqual(self.h.results[-2]["status"], "BLOCKED")
        self.assertEqual(self.h.results[-1]["changes"], {"A": ["cache"], "B": []})


if __name__ == "__main__":
    unittest.main()
