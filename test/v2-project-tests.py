"""Actual installed internal activation/helper cohort; never native enable evidence."""
from contextlib import contextmanager, ExitStack, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import socket
import shutil
import stat
import sys
import unittest
from unittest.mock import patch

import inspect_fixture as F
sys.path.insert(0, str(F.ROOT))
spec = importlib.util.spec_from_file_location("v2_publisher_fixtures",
                                            F.ROOT / "test/v2-publisher-tests.py")
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
from v2.admission import admit
from v2.build import package_data
from v2.guards import guarded_start, guarded_bound, verified_helper
from v2.project_identity import project_identity
from v2.project_preflight import project_preflight, POLICY_LEAVES, LEGACY_COMMANDS
from v2.project_publication import ActivationPublication
from v2.project_publication import (project_pending_read, project_previous_read,
    project_facts_read, project_facts_prefix)
from v2.project_records import (STATE, binding_read, binding_bytes, native_inventory,
    patterns, project_manifest_read, project_manifest_bytes, receipt_bytes,
    receipt_read, skill_ids, generation, exclusion_block)
from v2.records import parse_record, record
from v2.records import published_header, fact_bytes
from v2.safe import Refusal, MAX_NUMBER, sha
import v2.guard_core as C
import v2.guards as G
import v2.safe as S
import v2.project_publication as Pub

# Execute the EXACT generated installed Python closure with an OS-open audit
# witness. No instrumentation changes its bytes/provenance or lookup decisions.
# Separate tests also execute its actual Bash entrypoint without instrumentation.
AUDIT = r'''
import os, sys
from pathlib import Path
helper = sys.argv[1]
raw = Path(helper).read_text()
program = raw.split("<<'DOMESTIQUE_V2_TRUSTED_PY'\n", 1)[1].rsplit(
    "\nDOMESTIQUE_V2_TRUSTED_PY\n", 1)[0]
sys.argv = ["-", *sys.argv[1:]]
def witness(event, args):
    if event == "open" and isinstance(args[0], str):
        if "/roles/" in args[0] and args[0].endswith(".md"):
            os.write(2, b"BODY_OPEN\n")
        if args[0].endswith("/active"):
            os.write(2, b"ACTIVE_OPEN\n")
sys.addaudithook(witness)
exec(compile(program, helper, "exec"), {"__name__": "__main__"})
'''


class RecordAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.data = package_data("2.0.0")
        self.templates = {p: {k: v.encode() for k, v in
                             json.loads(self.data["adapters/" + p + ".templates"]).items()}
                          for p in F.PROVIDERS}

    def test_exact_admission_all_fields_shapes(self):
        metadata = {
            "claude": [
                b'model: "opaque"\n',
                b'tools: ["Read", "Bash"]\ndisallowedTools: \'Write, Edit\'\n',
                b'mcpServers:\n  - configured\n  - local:\n      type: stdio\n'
                b'      command: "inert"\n      args: []\n      env:\n        EXAMPLE: "literal"\n'],
            "codex": [
                b'model = "opaque"\nmodel_reasoning_effort = "ultra"\nsandbox_mode = "read-only"\n',
                b'[mcp_servers.local]\ncommand = "inert"\nargs = []\ncwd = "/unused"\n'
                b'env_vars = ["EXAMPLE"]\nenabled = false\nrequired = true\n'
                b'enabled_tools = []\ndisabled_tools = ["example"]\nstartup_timeout_sec = 1\n'
                b'tool_timeout_sec = 3600\n[mcp_servers.local.env]\nEXAMPLE = "literal"\n',
                b'[mcp_servers.remote]\nurl = "https://invalid.example"\nenabled = false\n'],
            "copilot": [
                b'model: "opaque"\ntools: "read, shell"\n',
                b'mcp-servers:\n  local:\n    type: local\n    command: "inert"\n'
                b'    tools: []\n    args: []\n    env:\n      EXAMPLE: "literal"\n',
                b'mcp-servers:\n  local:\n    type: stdio\n    command: "inert"\n    tools: []\n']}
        checks = 0
        for p, leaves in self.templates.items():
            for leaf, base in leaves.items():
                self.assertEqual(admit(p, leaf, base, base), ())
                if leaf.endswith("openai.yaml"):
                    edits = [b'interface:\n  display_name: "Visible"\n  short_description: \'Hint\'\n']
                elif "/agents/domestique-" in leaf:
                    edits = metadata[p]
                elif p == "claude":
                    edits = [b'model: "opaque"\nallowed-tools: []\n']
                elif p == "copilot":
                    edits = [b'allowed-tools: ["read"]\n']
                else:
                    edits = []
                for edit in edits:
                    live = self.edit(leaf, base, edit)
                    self.assertTrue(admit(p, leaf, live, base))
                    checks += 1
        print("ADMISSION_VALID_SHAPES=" + str(checks), flush=True)

    @staticmethod
    def edit(leaf, base, metadata):
        if leaf.endswith((".toml", "openai.yaml")):
            # MCP TOML tables must follow the protected top-level loader.
            return base + metadata if metadata.startswith(b"[") else metadata + base
        return b"---\n" + metadata + base[4:]

    def test_admission_negative_syntax_and_protected_each_leaf(self):
        invalid = {
            "claude": [b"model: true\n", b"model: .5\n", b"model: 0o7\n", b"model: 0b10\n",
                b"model: value # inline\n", b'model: "x"\nmodel: "x"\n', b"model: &a x\n",
                b"tools: [Read, Read]\n", b"tools: [Read,]\n", b"tools: 'Read,,Write'\n",
                b"mcpServers:\n  x:\n    command: inert\n",
                b"mcpServers:\n  - x\n  - x\n",
                b"mcpServers:\n  - x:\n      url: remote\n",
                b"mcpServers:\n  - x:\n      command: inert\n      env:\n        2BAD: x\n"],
            "codex": [b"model = 'single'\n", b'model = "bad\\n"\n', b"model = true\n",
                b'model_reasoning_effort = "unknown"\n', b'sandbox_mode = "unknown"\n',
                b'model = "x"\nmodel = "x"\n', b'[mcp_servers.x]\nurl = "x"\ncommand = "y"\n',
                b'[mcp_servers.x]\nurl = "x"\nargs = []\n',
                b'[mcp_servers.x]\ncommand = "x"\nstartup_timeout_sec = 3601\n',
                b'[mcp_servers.x]\ncommand = "x"\ntool_timeout_sec = 01\n',
                b'[mcp_servers.x]\ncommand = "x"\nenv_vars = ["NOT-ENV"]\n',
                b'[mcp_servers.x]\nurl = "x"\n[mcp_servers.x.env]\nEXAMPLE = "x"\n',
                b'[mcp_servers.x]\nurl = "x"\n[mcp_servers.x]\nurl = "x"\n'],
            "copilot": [b"model: false\n", b"tools: [read, read]\n",
                b"mcp-servers:\n  - server\n", b"mcp-servers:\n  x:\n    type: remote\n"
                b"    command: inert\n    tools: []\n",
                b"mcp-servers:\n  x:\n    type: local\n    command: inert\n",
                b"mcp-servers:\n  x:\n    type: local\n    command: inert\n    tools: []\n"
                b"    env:\n      EXAMPLE: x\n      EXAMPLE: y\n"]}
        count = 0
        for p, leaves in self.templates.items():
            for leaf, base in leaves.items():
                edits = [base + b"extra body\n", base.replace(b"domestique-v2-", b"fork-v2-"),
                         b"\xef\xbb\xbf" + base, base[:-1], base + b"\t\n",
                         base + b"x" * 8192 + b"\n"]
                if leaf.endswith("openai.yaml"):
                    edits[1] = base.replace(b"false", b"true")
                    edits += [self.edit(leaf, base, b"interface:\n  default_prompt: x\n"),
                              self.edit(leaf, base, b"interface:\n  display_name: true\n")]
                else:
                    edits += [self.edit(leaf, base, line + sep) for line, sep in
                              ((b"context: fork", b"\n"), (b"agent: fork", b"\n"),
                               (b"hooks: fork", b"\n"), (b"models: fork", b"\n"))]
                    if b"disable-model-invocation: true" in base:
                        edits.append(base.replace(b"disable-model-invocation: true",
                                                  b"disable-model-invocation: false"))
                    if "/agents/domestique-" in leaf:
                        edits += [self.edit(leaf, base, edit) for edit in invalid[p]]
                for live in edits:
                    with self.subTest(provider=p, leaf=leaf, case=count):
                        with self.assertRaises(Refusal):
                            admit(p, leaf, live, base)
                        count += 1
        print("ADMISSION_REFUSAL_CASES=" + str(count), flush=True)

    def test_record_grammar_and_whole_provider_inventory(self):
        from v2.project_records import I_KEYS
        i = dict(zip(I_KEYS, ["/w", "/w/.git", "/w/.git", *("1" for _ in range(7))]))
        for p, leaves in self.templates.items():
            hashes = {k: (sha(v), "0644") for k, v in leaves.items()}
            block = dict(status="enabled", generation=1, template_release="r-" + "a"*64,
                         created=hashes, baseline=hashes)
            raw = project_manifest_bytes(i, "/g", {p: block}, {})
            receipt = receipt_bytes(i, "/g", p, block)
            binding = binding_bytes(i, "/g", p, (1, 2), 1, sha(receipt), "r-" + "a"*64,
                                    skill_ids(p)[0], hashes)
            for data, parser in ((raw, project_manifest_read), (binding, binding_read),
                    (receipt, lambda b: receipt_read(b, i, "/g", p, block))):
                parser(data)
                rows = parse_record(data)
                for n in range(len(rows)):
                    variants = [rows[:n] + rows[n+1:], rows[:n] + [rows[n]] + rows[n:],
                                rows[:n] + [("unknown", "x")] + rows[n+1:]]
                    if n + 1 < len(rows):
                        variants.append(rows[:n] + [rows[n+1], rows[n]] + rows[n+2:])
                    for variant in variants:
                        with self.assertRaises(Refusal):
                            parser(record(variant))
                for bad in (data[:-1], b"\xef\xbb\xbf" + data, data.replace(b"\n", b"\r\n"),
                            data + b"x", data.replace(b"format=2", b"format=3"),
                            b"x" * 1048577):
                    with self.assertRaises(Refusal):
                        parser(bad)
            for field in ("adapters",):
                parsed = binding_read(binding)
                for leaf in hashes:
                    smaller = dict(parsed[field])
                    smaller.pop(leaf)
                    with self.assertRaises(Refusal):
                        binding_bytes(i, "/g", p, (1, 2), 1, sha(receipt), "r-" + "a"*64,
                                      skill_ids(p)[0], smaller)
        self.assertEqual(generation(None), 1)
        self.assertEqual(generation({"status": "enabled", "generation": MAX_NUMBER}), MAX_NUMBER)
        self.assertEqual(generation({"status": "disabled", "generation": 1}), 2)
        for n in (0, -1, MAX_NUMBER, MAX_NUMBER + 1):
            with self.assertRaises(Refusal):
                generation({"status": "disabled", "generation": n})

    def test_current_registration_and_metadata_limits(self):
        import acceptance as A
        self.assertEqual(A.CURRENT.count("v2-project-tests.py"), 1)
        self.assertNotIn("v2-project-tests.py", A.RETAINED_PREVIEW)
        self.assertIn("test/v2-project-tests.py", A.provenance(A.Control(30))["source_sha256"])
        p = "claude"
        leaf = native_inventory(p)[0]
        base = self.templates[p][leaf]
        for edit in (b'model: "' + b"x"*4097 + b'"\n',
                     b"tools: [" + b", ".join(b'"t%d"' % n for n in range(65)) + b"]\n",
                     b"mcpServers:\n" + b"".join(b"  - s%d\n" % n for n in range(33)),
                     b"model: x\n" + b"# comment\n"*16384):
            with self.assertRaises(Refusal):
                admit(p, leaf, self.edit(leaf, base, edit), base)

    def scalar_fields(self):
        """Every S consumer/location, including nested arrays, maps and enums."""
        fields = []
        for p, leaves in self.templates.items():
            for leaf in leaves:
                def add(label, template, shape="text", array=False):
                    fields.append((p, leaf, label, template, shape, array))
                if leaf.endswith("openai.yaml"):
                    for key in ("display_name", "short_description"):
                        add(key, "interface:\n  " + key + ": {s}\n")
                elif leaf.endswith(".toml"):
                    for key, shape in (("model", "model"), ("model_reasoning_effort", "reason"),
                                       ("sandbox_mode", "sandbox")):
                        add(key, key + " = {s}\n", shape)
                    for key in ("command", "cwd", "args", "env_vars",
                                "enabled_tools", "disabled_tools"):
                        head = "[mcp_servers.local]\n"
                        if key != "command":
                            head += 'command = "inert"\n'
                        is_array = key in ("args", "env_vars", "enabled_tools", "disabled_tools")
                        add(key, head + key + " = " + ("[{s}]" if is_array else "{s}") + "\n",
                            "env" if key == "env_vars" else "text", is_array)
                    add("url", "[mcp_servers.remote]\nurl = {s}\n")
                    add("env", '[mcp_servers.local]\ncommand = "inert"\n'
                        '[mcp_servers.local.env]\nEXAMPLE = {s}\n')
                elif p != "codex":
                    role = "/agents/domestique-" in leaf
                    if role or p == "claude":
                        add("model", "model: {s}\n", "model")
                    keys = (("tools", "disallowedTools") if p == "claude" else ("tools",)) \
                        if role else ("allowed-tools",)
                    for key in keys:
                        add(key, key + ": [{s}]\n", "tool", True)
                        add(key + "-comma", key + ": {s}\n", "comma")
                    if role:
                        if p == "claude":
                            add("reference", "mcpServers:\n  - {s}\n", "name")
                            head, indent = "mcpServers:\n  - local:\n", "      "
                        else:
                            head, indent = "mcp-servers:\n  local:\n    type: local\n", "    "
                        for key in (("command", "args", "env") if p == "claude"
                                    else ("command", "args", "env", "tools")):
                            text = head
                            if key != "command":
                                text += indent + 'command: "inert"\n'
                            if p == "copilot" and key != "tools":
                                text += indent + "tools: []\n"
                            is_array = key in ("args", "tools")
                            text += indent + key + ": " + ("[{s}]" if is_array else "{s}") + "\n"
                            if key == "env":
                                text = text.replace("env: {s}", "env:\n" + indent + "  EXAMPLE: {s}")
                            add("mcp-" + key, text, "text", is_array)
        return fields

    def test_scalar_grammar_matrix(self):
        # Expected grammar is independent of the production classifier. Quoting
        # fixes scalar syntax, never the separate tool/name/enum/location rules.
        plain = ("opaque", "sonnet", "inherit", "default", "gpt-4.1",
                 "claude-sonnet-4-20250514", "openai/gpt-5", "provider/model:latest",
                 "o3", "4o", "123-model", "0xmodel", "EXAMPLE", "Read", "Bash:*",
                 "vendor/*", "-flag", "--flag", ".hidden", "_1", "a@b", "a+b",
                 "---suffix", "...suffix", "x*y", "minimal", "read-only",
                 "1.2.3", "1.2.3-rc.1", "1.2.3+build.7", "1-2", "1e", "1e+",
                 "1e-", "+1e", "1+2", "1..2", "1:60", "1:2:60", "0:20",
                 "1_0:2_0.5", "1_0e-2", "1.2e_3", "1.2e+3_", "1e2e3",
                 "0XCA_FE", "-0O7_7", "+0B1_0", "0x", "0xG", "0b102", "0o8",
                 "08_", ".", "+.", "-.", "+.nan",
                 "2001-1-2", "2001-12-15-preview", "2025-09-model",
                 "2001-12-15T02:59:43Z-model")
        nonstring = ("*model_alias", "*tool_alias", "*", "&anchor", "&anchor value",
                     "!str", "!!str value", "!<tag:example> value", "%YAML 1.2",
                     "%TAG !x! tag:example", "---", "...", "-", "?", "[value]",
                     "{key: value}", "|", ">", "value # inline", "value: other",
                     "@name", "value:", "Bash:",
                     "true", "False", "TRUE", "null", "Null", "~", "yes", "NO",
                     "on", "Off", "y", "N", ".nan", ".NaN", ".inf", "+.Inf", "-.INF",
                     "0", "01", "08", "-1", "+1", "1_000", "1.2", "1_0.2_0",
                     "1e3", "1e+3", ".5", ".5_0", "-.5_0",
                     "0x1_f", "+0x1_f", "0o7_7", "-0o7_7",
                     "0b1_0", "+0b1_0", "012_345", "1:20", "1_0:20.5",
                     "2001-12-15", "2001-12-15T02:59:43.1Z",
                     "2001-12-15t2:59:43-05:00", "1_", "0x_1",
                     # These resolve as typed numeric syntax too, not strings;
                     # no value conversion is attempted by this classifier.
                     "0x_", "0b_", "0o_", "._")
        # Independent construction from explicit numeric families, NOT NUMBER
        # or a production/parser-generated oracle. Each genuine number also has
        # an opaque "-model" near-neighbor that is positively a plain string.
        families = {
            "decimal": [sign + n for sign in ("", "+", "-")
                        for n in ("0", "00", "08", "42", "1_000", "12__3_")],
            "bases": [sign + prefix + digits for sign in ("", "+", "-")
                      for prefix, digits in (("0", "12_345"), ("0b", "10_01"),
                                             ("0o", "7_7"), ("0x", "CA_FE"),
                                             ("0x", "_1"), ("0b", "1__0_"))],
            "point": [sign + n for sign in ("", "+", "-")
                      for n in ("1.", "0.0", ".5", ".5_0", "1_0.2_0", "1_0.2e-3")],
            "exponent": [sign + mantissa + e + esign + exponent
                         for sign in ("", "+", "-") for mantissa in ("1", "1.25", ".5")
                         for e in ("e", "E") for esign in ("", "+", "-")
                         for exponent in ("0", "12")],
            "sexagesimal": [sign + n for sign in ("", "+", "-")
                            for n in ("1:00", "1:2:59", "1_0:20", "1:20.",
                                      "0:20.5", "1:2:59.5_0")],
        }
        numeric = tuple(dict.fromkeys(n for values in families.values() for n in values))
        plain += tuple(n + "-model" for n in numeric)
        nonstring = tuple(dict.fromkeys((*nonstring, *numeric)))
        # Exhaust EVERY case permutation, with every sign, against a literal
        # expected set transcribed from YAML 1.1/1.2 type productions. No
        # production constant/regex, lower(), or parser supplies expectations.
        from itertools import product
        from v2.admission import string, array
        typed_cases = {
            "y", "Y", "n", "N",
            "yes", "Yes", "YES", "no", "No", "NO",
            "true", "True", "TRUE", "false", "False", "FALSE",
            "on", "On", "ON", "off", "Off", "OFF",
            "null", "Null", "NULL",
            ".inf", ".Inf", ".INF", "+.inf", "+.Inf", "+.INF",
            "-.inf", "-.Inf", "-.INF", ".nan", ".NaN", ".NAN",
        }
        case_table = {
            sign + ("." if word in ("inf", "nan") else "") + "".join(letters):
                sign + ("." if word in ("inf", "nan") else "") + "".join(letters)
                not in typed_cases
            for word in ("true", "false", "null", "yes", "no", "on", "off",
                         "y", "n", "inf", "nan")
            for letters in product(*[(c, c.upper()) for c in word])
            for sign in ("", "+", "-")
        }
        self.assertEqual(len(case_table), 324)
        self.assertEqual({t for t, allowed in case_table.items() if not allowed}, typed_cases)
        self.assertEqual(len(typed_cases), 37)
        direct_checks = 0
        for token, allowed in case_table.items():
            for quote in ("", '"', "'"):
                form = quote + token + quote
                # Singleton and each item position, not just an entire scalar.
                values = ((form, token),
                          ("[" + form + "]", [token]),
                          ("[" + form + ", sentinel]", [token, "sentinel"]),
                          ("[sentinel, " + form + "]", ["sentinel", token]),
                          ("[first, " + form + ", last]", ["first", token, "last"]))
                for source, decoded in values:
                    fn = array if isinstance(decoded, list) else string
                    with self.subTest(case_token=token, source=source):
                        if allowed or quote:
                            self.assertEqual(fn(source), decoded)
                        else:
                            with self.assertRaises(Refusal):
                                fn(source)
                    direct_checks += 1
        # Related case boundaries: base prefixes are lowercase only; hex
        # digits and exponent E/e accept both. T/t is allowed, zone is Z only.
        # Signed modern octal/underscores remain the explicit R4 contract case.
        case_boundaries = [
            (sign + prefix + digits, allowed)
            for sign in ("", "+", "-")
            for prefix, digits, allowed in (
                ("0b", "1_0", False), ("0B", "1_0", True),
                ("0o", "7_7", False), ("0O", "7_7", True),
                ("0x", "Ca_fE", False), ("0X", "Ca_fE", True))]
        case_boundaries += [
            ("2001-12-15" + sep + "02:59:43" + zone, allowed)
            for sep in ("T", "t")
            for zone, allowed in (("", False), ("Z", False), ("z", True),
                                  ("+05:00", False), ("-05:00", False))]
        case_boundaries += [(value, allowed) for value, allowed in (
            ("1e3", False), ("1E3", False), ("1_0.2e-3", False),
            ("1_0.2E-3", False), ("1_0.2e3", True), ("1_0.2E3", True),
            ("1e", True), ("1E", True), ("1e+", True), ("1E+", True))]
        additions = (*case_table.items(), *case_boundaries)
        # Correct the recent matrices rather than preserving casefold bugs.
        plain = tuple(dict.fromkeys((*plain, *(t for t, ok in additions if ok))))
        nonstring = tuple(dict.fromkeys((*nonstring, *(t for t, ok in additions if not ok))))
        print("INDEPENDENT_CASE_TABLE=" + json.dumps(
            dict(expected_nonstrings=sorted(typed_cases), cases=case_table,
                 tokens=324, bare_nonstrings=37, bare_strings=287,
                 direct_checks=direct_checks, boundaries=case_boundaries)), flush=True)
        self.assertFalse(set(plain) & set(nonstring))
        print("INDEPENDENT_GRAMMAR_TABLES=" + json.dumps(
            dict(accepted_plain=plain, refused_bare=nonstring, numeric_families=families)),
            flush=True)
        counts = dict(accepted=0, refused=0, fields=len(self.scalar_fields()),
                      tokens=len(plain + nonstring) + 1, forms=3)
        for p, leaf, label, template, shape, _ in self.scalar_fields():
            base = self.templates[p][leaf]
            toml = leaf.endswith(".toml")
            for token in (*plain, *nonstring, ""):
                fits = {
                    "text": True, "model": bool(token),
                    "tool": bool(re.fullmatch(r"[A-Za-z0-9_./*:-]{1,256}", token)),
                    "comma": bool(re.fullmatch(r"[A-Za-z0-9_./*:-]{1,256}", token)),
                    "name": bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,63}", token)),
                    "env": bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", token)),
                    "reason": token in ("minimal", "low", "medium", "high", "xhigh", "max", "ultra"),
                    "sandbox": token in ("read-only", "workspace-write", "danger-full-access")
                }[shape]
                for quote in ("", '"', "'"):
                    form = quote + token + quote
                    expected = fits and (quote == '"' or (quote == "'" and not toml) or
                                         (not quote and not toml and token in plain and
                                          shape != "comma"))
                    # Empty brackets are a valid empty array, not an empty S.
                    if not form and "[{s}]" in template:
                        expected = True
                    if shape == "comma" and not quote and token == "[value]":
                        expected = True  # Tool fields also accept the array shape.
                    live = self.edit(leaf, base, template.replace("{s}", form).encode())
                    with self.subTest(provider=p, leaf=leaf, field=label, token=token, quote=quote):
                        if expected:
                            self.assertTrue(admit(p, leaf, live, base))
                            counts["accepted"] += 1
                        else:
                            with self.assertRaises(Refusal):
                                admit(p, leaf, live, base)
                            counts["refused"] += 1
        print("SCALAR_GRAMMAR_MATRIX=" + json.dumps(counts), flush=True)

    def test_array_grammar_and_literal_decoding_matrix(self):
        from v2.admission import string, array
        arrays = ("[]", '["Read"]', "[Read]", "['Read']", '["*tool_alias"]',
                  "[*tool_alias]", '["Read", *tool_alias]', '[*tool_alias, "Read"]',
                  '["Read", *tool_alias, "Write"]', "[&anchor Read]", "[!!str Read]",
                  "[0x1_f]", "[0o7_7]", "[.5_0]", "[true]", "[%YAML 1.2]",
                  "[---]", "[...]", "[[Read]]", "[{key: Read}]", "[Read,]",
                  '["Read",]', '[,"Read"]', '["Read" "Write"]', '["Read",, "Write"]',
                  '["Read", "Read"]', '["Read", Read]', '["Read", \'Read\']',
                  '["Read"] # inline', '["Read", "Write"]')
        checks = 0
        fields = [f for f in self.scalar_fields() if f[-1]]
        for p, leaf, label, template, shape, _ in fields:
            for value in arrays:
                expected = value in ("[]", '["Read"]', '["Read", "Write"]')
                expected |= value in ("[Read]", "['Read']") and not leaf.endswith(".toml")
                expected |= value == '["*tool_alias"]' and shape != "env"
                live = self.edit(leaf, self.templates[p][leaf],
                                 template.replace("[{s}]", value).encode())
                with self.subTest(provider=p, leaf=leaf, field=label, array=value):
                    if expected:
                        self.assertTrue(admit(p, leaf, live, self.templates[p][leaf]))
                    else:
                        with self.assertRaises(Refusal):
                            admit(p, leaf, live, self.templates[p][leaf])
                checks += 1
        literals = ((r'"*name"', "*name"), ("'*name'", "*name"),
                    (r'"0x1_f"', "0x1_f"), ("'it''s literal'", "it's literal"),
                    (r'"quote\"slash\\"', 'quote"slash\\'), ('""', ""),
                    ("1.2.3", "1.2.3"), ('"1.2.3"', "1.2.3"), ("'1.2.3'", "1.2.3"),
                    ("1e", "1e"), ('"1e"', "1e"), ("'1e'", "1e"),
                    ("1-2", "1-2"), ('"1-2"', "1-2"), ("'1-2'", "1-2"))
        for source, decoded in literals:
            self.assertEqual(string(source), decoded)
            self.assertEqual(array("[" + source + "]"), [decoded])
            if source.startswith('"'):
                self.assertEqual(string(source, toml=True), decoded)
                self.assertEqual(array("[" + source + "]", toml=True), [decoded])
        print("ARRAY_GRAMMAR_MATRIX=" + json.dumps(
            dict(fields=len(fields), forms=len(arrays), cases=checks, literals=len(literals))),
            flush=True)


def publish(plan):
    """Only actual successful internal effects mint prerequisite ownership."""
    tx = ActivationPublication(plan)
    if tx.begin():
        while tx.count < len(tx.items):
            tx.apply_next()
        tx.finish()
    return tx


class ScalarInstalledTests(unittest.TestCase):
    def test_installed_scalar_gate_and_quoted_fresh_entry(self):
        # One genuine installed cohort for the R4/R5/R6 matrix, not one install
        # per scalar. Public enable/factory STOP and native qualification unchanged.
        report = dict(negative=[], positive=[], machine_installs=1)
        watching, body_opens = False, []
        def witness(event, args):
            if watching and event == "open" and isinstance(args[0], str):
                if "/roles/" in args[0] and args[0].endswith(".md"):
                    body_opens.append(args[0])
        sys.addaudithook(witness)
        with fixtures.fixture() as s:
            report["fixture"] = dict(root=str(s.root), identity=s.identity)
            root = fixtures.root(s)
            release = fixtures.publish_local(fixtures.source(s), s.env)["runtime"]
            helper = root / "releases" / release / "bin/resolve-core"
            report.update(release=release, helper_sha256=sha(helper.read_bytes()))
            w = s.project("scalar-admission", git=True)
            tx = publish(project_preflight(w, root, ("claude", "copilot")))
            report["creation_effects"] = len(tx.items)
            def invoke(provider, op, binding=None, audit=True):
                role = skill_ids(provider)[0] if op == "start" else (
                    "orchestrator" if op == "read" else "implementer")
                argv = (["python3", "-I", "-S", "-B", "-Werror", "-c", AUDIT] if audit else []) + [
                    helper, op, root, w, provider, role]
                if binding is not None:
                    argv.append(binding.decode())
                return s.run(argv, check=False)
            def refused(out):
                self.assertEqual(out.returncode, 1, out.stderr)
                self.assertEqual(out.stdout, b"")
                self.assertNotIn(b"BODY_OPEN", out.stderr)
                return dict(exit=out.returncode, stdout_bytes=len(out.stdout),
                            body_opens=out.stderr.count(b"BODY_OPEN"))
            bindings = {}
            for provider in ("claude", "copilot"):
                result = invoke(provider, "start", audit=False)
                self.assertEqual(result.returncode, 0, result.stderr)
                bindings[provider] = result.stdout
            role = ".claude/agents/domestique-v2-claude-implementer.md"
            skill = ".github/skills/domestique-v2-copilot/SKILL.md"
            cases = [
                ("claude", role, b"model: *model_alias\n"),
                ("claude", role, b"tools: [*tool_alias]\n"),
                ("copilot", skill, b"allowed-tools: [*tool_alias]\n"),
                ("claude", role, b"model: 0x1_f\n"),
                ("claude", role, b"model: 0o7_7\n"),
                ("claude", role, b"mcpServers:\n  - local:\n      command: inert\n"
                 b"      args: [1.2e+3]\n"),
                ("claude", role, b'mcpServers:\n  - local:\n      command: "inert"\n'
                 b'      args: ["first", *tool_alias]\n'),
                ("copilot", ".github/agents/domestique-v2-copilot-implementer.agent.md",
                 b'mcp-servers:\n  local:\n    type: local\n    command: "inert"\n'
                 b'    tools: []\n    env:\n      EXAMPLE: *model_alias\n'),
                ("claude", role, b"model: True\n"),
                ("claude", role, b"mcpServers:\n  - local:\n      command: inert\n"
                 b"      args: [.Inf]\n"),
                ("claude", role, b"mcpServers:\n  - local:\n      command: inert\n"
                 b"      args: [.NaN]\n"),
                ("copilot", ".github/agents/domestique-v2-copilot-implementer.agent.md",
                 b"mcp-servers:\n  local:\n    type: local\n    command: inert\n"
                 b"    tools: []\n    env:\n      EXAMPLE: Null\n"),
                ("copilot", skill, b"allowed-tools: [OFF]\n"),
                ("claude", role, b"model: 2001-12-15t02:59:43Z\n")]
            for provider, leaf, edit in cases:
                with self.subTest(provider=provider, leaf=leaf, edit=edit):
                    path = w / leaf
                    base = path.read_bytes()
                    live = RecordAdmissionTests.edit(leaf, base, edit)
                    path.write_bytes(live)
                    before = s.snapshot()
                    with self.assertRaises(Refusal):
                        admit(provider, leaf, live, base)
                    stdout = io.StringIO()
                    body_opens.clear()
                    watching = True
                    try:
                        with redirect_stdout(stdout), self.assertRaises(Refusal):
                            project_preflight(w, root, (provider,))
                    finally:
                        watching = False
                    self.assertEqual(stdout.getvalue(), "")
                    self.assertEqual(body_opens, [])
                    # A matching caller-carried binding deliberately removes
                    # staleness as a reason: read/route must themselves classify.
                    # This is NOT represented as a token minted by fresh start.
                    parsed = binding_read(bindings[provider])
                    parsed["adapters"][leaf] = (sha(live), "0644")
                    matching = binding_bytes(**parsed)
                    case = dict(provider=provider, leaf=leaf, edit=edit.decode(),
                                preflight=dict(refused=True, stdout_bytes=0, body_opens=0),
                                start=refused(invoke(provider, "start")),
                                old_read=refused(invoke(provider, "read", bindings[provider])),
                                matching_read=refused(invoke(provider, "read", matching)),
                                matching_route=refused(invoke(provider, "route", matching)))
                    self.assertEqual(before, s.snapshot())
                    self.assertFalse((w / STATE / "pending").exists())
                    case.update(readonly=True, pending_absent=True)
                    report["negative"].append(case)
                    path.write_bytes(base)
            for provider, leaf, edit in (
                    ("claude", role, b'model: "*model_alias"\n'),
                    ("claude", role, b"tools: ['*tool_alias']\n"),
                    ("copilot", skill, b'allowed-tools: ["*tool_alias"]\n'),
                    ("claude", role, b'model: "0x1_f"\n'),
                    # Exact installed R5 edits and quoted counterparts.
                    *((p, leaf, edit.replace(b"{s}", value))
                      for p, leaf, edit in (
                          ("claude", role, b"mcpServers:\n  - local:\n"
                           b"      command: inert\n      args: [{s}]\n"),
                          ("copilot", ".github/agents/domestique-v2-copilot-implementer.agent.md",
                           b"mcp-servers:\n  local:\n    type: local\n"
                           b"    command: inert\n    tools: []\n    env:\n      VERSION: {s}\n"))
                      for value in (b"1.2.3", b'"1.2.3"')),
                    # Numeric-looking values in all applicable S positions,
                    # including models, command, args, env and tool strings.
                    ("claude", role, b"model: 1.2.3\n"
                     b"tools: [1-2, 1e, 1.2.3]\ndisallowedTools: [1:60]\n"
                     b"mcpServers:\n  - local:\n      command: 1e+\n"
                     b"      args: [1-2, 1e, 1e+, 1.2.3-rc.1]\n"
                     b"      env:\n        VERSION: 1.2.3\n"),
                    ("copilot", ".github/agents/domestique-v2-copilot-implementer.agent.md",
                     b"model: 1.2.3-rc.1\ntools: [1.2.3, 1-2]\n"
                     b"mcp-servers:\n  local:\n    type: local\n"
                     b"    command: 1e\n    tools: [1.2.3, 1e+]\n"
                     b"    args: [1-2, 1e+]\n    env:\n      VERSION: 1.2.3\n"),
                    # Exact R6 witness and both unchanged quoted spellings.
                    *(("claude", role, b"mcpServers:\n  - local:\n"
                       b"      command: inert\n      args: [" + value + b"]\n")
                      for value in (b".iNf", b'".iNf"', b"'.iNf'")),
                    ("claude", role, b"model: trUe\ntools: [.iNf, .nAn, oFF]\n"
                     b"disallowedTools: [nUlL]\nmcpServers:\n  - trUe\n  - local:\n"
                     b"      command: nUlL\n      args: [.iNf, +.iNf, -.nAn, +.NaN]\n"
                     b"      env:\n        EXAMPLE: .nAn\n"),
                    ("copilot", ".github/agents/domestique-v2-copilot-implementer.agent.md",
                     b"model: nUlL\ntools: [trUe, .iNf]\n"
                     b"mcp-servers:\n  local:\n    type: local\n"
                     b"    command: oFF\n    tools: [.nAn, +.NaN]\n"
                     b"    args: [.iNf, -.INF-model, -.NaN]\n"
                     b"    env:\n      EXAMPLE: +.iNf\n"),
                    ("claude", role, b"model: 2001-12-15t02:59:43z\n"),
                    ("claude", role, b'model: "2001-12-15t02:59:43Z"\n')):
                path = w / leaf
                base = path.read_bytes()
                live = RecordAdmissionTests.edit(leaf, base, edit)
                path.write_bytes(live)
                before = s.snapshot()
                self.assertEqual(ActivationPublication(project_preflight(w, root, (provider,))).items, [])
                case = dict(provider=provider, leaf=leaf, edit=edit.decode())
                for op in ("read", "route"):
                    case["old_" + op] = refused(invoke(provider, op, bindings[provider]))
                # Actual standalone Bash entrypoint, without the audit harness.
                fresh = invoke(provider, "start", audit=False)
                self.assertEqual(fresh.returncode, 0, fresh.stderr)
                self.assertEqual(binding_read(fresh.stdout)["adapters"][leaf][0], sha(live))
                for op in ("read", "route"):
                    out = invoke(provider, op, fresh.stdout, audit=False)
                    self.assertEqual(out.returncode, 0, out.stderr)
                    expected = (root / "releases" / release / "roles/orchestrator.md").read_bytes() \
                        if op == "read" else (
                            "domestique-v2-" + provider + "-implementer:" +
                            binding_read(fresh.stdout)["adapters"][
                                native_inventory(provider)[0]][0] + "\n").encode()
                    self.assertEqual(out.stdout, expected)
                    case[op] = dict(exit=out.returncode, stdout_bytes=len(out.stdout), exact=True)
                self.assertEqual(before, s.snapshot())
                case.update(fresh_start=0, binding_covers_live_edit=True, readonly=True)
                report["positive"].append(case)
                path.write_bytes(base)
            s.assert_no_calls()
            report["forbidden_calls"] = False
        self.assertFalse(Path(report["fixture"]["root"]).exists())
        report["fixture_cleaned"] = True
        print("INSTALLED_SCALAR_MATRIX=" + json.dumps(report), flush=True)


class ProjectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = fixtures.fixture()
        cls.s = cls.context.__enter__()
        cls.addClassCleanup(cls.context.__exit__, None, None, None)
        cls.root = fixtures.root(cls.s)
        cls.source = fixtures.source(cls.s)
        cls.release = fixtures.publish_local(cls.source, cls.s.env)["runtime"]
        cls.w = cls.s.project("private", git=True)
        (cls.w / ".beads").mkdir()
        (cls.w / ".beads/SYNTHETIC").write_text("inert preservation sentinel\n")
        cls.b = cls.s.project("B", git=True)
        cls.tx = publish(project_preflight(cls.w, cls.root, F.PROVIDERS))
        cls.helper = cls.root / "releases" / cls.release / "bin/resolve-core"
        # A second genuinely published immutable release, same helper ABI.
        second = fixtures.source(cls.s, "2.0.1", "second")
        cls.release2 = fixtures.publish_local(second, cls.s.env)["runtime"]
        cls.helper2 = cls.root / "releases" / cls.release2 / "bin/resolve-core"
        # Select retained R1 by the real publisher, not a hand-written pointer.
        fixtures.publish_local(cls.source, cls.s.env)
        cls.s.pristine = cls.s.snapshot()
        print("PROJECT_COHORT=" + json.dumps({"release": cls.release,
            "helper_sha256": sha(cls.helper.read_bytes()), "projects": [str(cls.w), str(cls.b)],
            "facts": len(cls.tx.items), "machine_installs": 2}), flush=True)

    def tearDown(self):
        self.s.assert_no_calls()
        self.s.restore(self.s.snapshot())

    def invoke(self, op, provider="claude", role=None, binding=None, target=None, helper=None):
        role = role or (skill_ids(provider)[0] if op == "start" else "implementer")
        args = [helper or self.helper, op, self.root, target or self.w, provider, role]
        if binding is not None:
            args.append(binding.decode())
        return self.s.run(args, check=False)

    def audited(self, op, provider="claude", role=None, binding=None, target=None, helper=None):
        role = role or (skill_ids(provider)[0] if op == "start" else "implementer")
        args = ["python3", "-I", "-S", "-B", "-c", AUDIT, helper or self.helper, op,
                self.root, target or self.w, provider, role]
        if binding is not None:
            args.append(binding.decode())
        return self.s.run(args, check=False)

    def refused(self, out, body_free=True):
        self.assertNotEqual(out.returncode, 0)
        self.assertEqual(out.stdout, b"")
        if body_free:
            self.assertNotIn(b"BODY_OPEN", out.stderr)

    def reset(self):
        self.s.restore(self.s.snapshot())

    def start(self, provider="claude", entry=None):
        out = self.invoke("start", provider, entry)
        self.assertEqual(out.returncode, 0, out.stderr)
        binding_read(out.stdout)
        return out.stdout

    @contextmanager
    def unchanged(self):
        before = self.s.snapshot()
        yield
        self.assertEqual(before, self.s.snapshot())

    def test_installed_positive_all_providers_and_noop(self):
        with self.unchanged():
            tx = publish(project_preflight(self.w, self.root, F.PROVIDERS))
            self.assertEqual(tx.items, [])
            for provider in F.PROVIDERS:
                binding = self.start(provider)
                self.assertEqual(len(binding_read(binding)["adapters"]),
                                 6 if provider == "codex" else 5)
                for role in ("orchestrator", "implementer", "reviewer"):
                    out = self.invoke("read", provider, role, binding)
                    self.assertEqual(out.returncode, 0, out.stderr)
                    self.assertEqual(out.stdout, (self.root / "releases" / self.release /
                                                 ("roles/" + role + ".md")).read_bytes())
                for role in ("implementer", "reviewer"):
                    out = self.invoke("route", provider, role, binding)
                    self.assertEqual(out.returncode, 0, out.stderr)
                    self.assertIn(("domestique-v2-" + provider + "-" + role).encode(), out.stdout)

    def test_all_bound_leaves_stale_and_fresh_metadata(self):
        for p in F.PROVIDERS:
            binding = self.start(p)
            templates = json.loads((self.root / "releases" / self.release /
                                    ("adapters/" + p + ".templates")).read_bytes())
            for leaf in native_inventory(p):
                with self.subTest(provider=p, leaf=leaf):
                    path = self.w / leaf
                    base = templates[leaf].encode()
                    if leaf.endswith("openai.yaml"):
                        edit = b'interface:\n  display_name: "Fixture"\n'
                    elif p == "codex" and leaf.endswith("SKILL.md"):
                        edit = b"model: forbidden\n"
                    elif p == "codex":
                        edit = b'model = "fixture"\n'
                    else:
                        edit = b'tools: []\n' if "/agents/" in leaf else b'allowed-tools: []\n'
                    path.write_bytes(RecordAdmissionTests.edit(leaf, base, edit))
                    with self.unchanged():
                        self.refused(self.audited("read", p, binding=binding))
                        fresh = self.audited("start", p)
                        if p == "codex" and leaf.endswith("SKILL.md"):
                            self.refused(fresh)
                        else:
                            self.assertEqual(fresh.returncode, 0, fresh.stderr)
                            self.assertNotEqual(binding_read(fresh.stdout)["adapters"],
                                                binding_read(binding)["adapters"])
                    self.reset()

    def test_absent_disabled_pending_corrupt_and_provider_mismatch(self):
        binding = self.start()
        manifest = self.w / STATE / "manifest"
        receipt = self.w / STATE / "routing/claude.receipt"
        cases = [
            ("absent", lambda: manifest.unlink()),
            ("corrupt", lambda: manifest.write_bytes(manifest.read_bytes() + b"x")),
            ("receipt-corrupt", lambda: receipt.write_bytes(receipt.read_bytes() + b"x")),
            ("receipt-provider", lambda: receipt.write_bytes(
                (self.w / STATE / "routing/codex.receipt").read_bytes())),
            ("receipt-mode", lambda: receipt.chmod(0o644)),
            ("private-mode", lambda: (self.w / STATE).chmod(0o755)),
        ]
        cases += [(name, lambda name=name: (self.w / STATE / name).write_text("partial\n"))
                  for name in ("pending", "previous", "published", "exclude-afterimage")]
        def disabled():
            i, root, providers, exclusions = project_manifest_read(manifest.read_bytes())
            providers["claude"]["status"] = "disabled"
            manifest.write_bytes(project_manifest_bytes(i, root, providers, exclusions))
            receipt.unlink()
        cases += [("disabled", disabled)]
        for name, mutate in cases:
            with self.subTest(state=name):
                mutate()
                with self.unchanged():
                    self.refused(self.audited("read", binding=binding))
                    self.refused(self.audited("start"))
                self.reset()
        with self.unchanged():
            self.refused(self.audited("start", target=self.b))
            self.refused(self.audited("read", "codex", binding=binding))
            self.refused(self.audited("read", binding=binding, target=self.b))
            self.refused(self.invoke("route", role="orchestrator", binding=binding))
            self.refused(self.invoke("read", role="unknown", binding=binding))

    def test_goal_only_entry_and_exact_argv(self):
        ordinary = self.start()
        with self.unchanged():
            self.refused(self.audited("read", role="goal", binding=ordinary))
            goal = self.start(entry="/domestique-v2-claude-goal")
            result = self.invoke("read", role="goal", binding=goal)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(b"one literal epic", result.stdout.lower())
            for args in ([], ["start"], ["start", self.root, self.w, "claude", ""],
                         ["start", self.root, self.w, "claude", "orchestrator"],
                         ["start", self.root, self.w, "claude", "/domestique-v2-claude", "extra"]):
                self.refused(self.s.run([self.helper, *args], check=False))
            self.refused(self.s.run([fixtures.launcher(self.s), "enable", self.w], check=False))

    def test_active_start_only_same_release_and_machine_pending(self):
        with self.unchanged():
            start = self.audited("start")
            self.assertEqual(start.returncode, 0, start.stderr)
            self.assertIn(b"ACTIVE_OPEN", start.stderr)
            self.assertIn(b"BODY_OPEN", start.stderr)
        binding = start.stdout
        # Test the only selector function, not repeated integrity snapshot reads.
        with patch.object(G, "sample_active", wraps=G.sample_active) as sample:
            guarded_start(self.root, self.w, "claude", skill_ids("claude")[0])
            self.assertEqual(sample.call_count, 1)
        # Simulate an active switch independently of bound workflow execution.
        (self.root / "active").write_text("release=" + self.release2 + "\n")
        with self.unchanged():
            fresh = self.audited("start")
            self.assertEqual(binding_read(fresh.stdout)["release"], self.release2)
            self.refused(self.audited("read", binding=fresh.stdout))  # T is not same R2.
            result = self.audited("read", binding=fresh.stdout, helper=self.helper2)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn(b"ACTIVE_OPEN", result.stderr)
        (self.root / "active").unlink()
        (self.root / "state/pending").write_text("interrupted machine fixture\n")
        with self.unchanged():
            for op in ("read", "route"):
                result = self.audited(op, binding=binding)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn(b"ACTIVE_OPEN", result.stderr)
                self.assertIn(b"BODY_OPEN", result.stderr)

    def test_original_watch_before_read_and_before_output(self):
        binding = self.start()
        path = self.w / native_inventory("claude")[0]
        guard = G.ActivationGuard(self.root, self.w, "claude")
        path.write_bytes(path.read_bytes() + b"edited\n")
        with patch.object(C, "snapshot", wraps=C.snapshot) as opens:
            with self.assertRaises(Refusal):
                C.guarded_body_read(self.root, self.release, "roles/implementer.md",
                                    guard.index, guard.watch, guard.check)
            self.assertEqual(opens.call_count, 0)
        self.reset()
        original = G.binding_bytes
        def changed_after_body(*args, **kwargs):
            result = original(*args, **kwargs)
            path.write_bytes(path.read_bytes() + b"edited\n")
            return result
        with patch.object(G, "binding_bytes", side_effect=changed_after_body):
            with self.assertRaises(Refusal):
                guarded_start(self.root, self.w, "claude", skill_ids("claude")[0])
        self.reset()
        for leaf in ("bin/resolve-core", "roles/reviewer.md", "PACKAGE"):
            runtime_leaf = self.root / "releases" / self.release / leaf
            runtime_leaf.unlink()
            with self.unchanged():
                if leaf == "bin/resolve-core":
                    with self.assertRaises(Refusal):
                        verified_helper(self.root, self.w, "claude", binding)
                else:
                    self.refused(self.audited("read", binding=binding),
                                 body_free=not leaf.startswith("roles/"))
            self.reset()

    def test_physical_top_subdirectory_nested_move_clone_and_runtime(self):
        sub = self.w / "sub"
        sub.mkdir()
        (sub / "HEAD").write_text("ordinary file, not bare authority\n")
        with self.unchanged():
            with self.assertRaises(Refusal):
                project_preflight(sub, self.root)
            self.assertEqual(project_identity(sub, invocation=True)[0]["worktree_root"], str(self.w))
            out = self.audited("start", target=sub)
            self.assertEqual(out.returncode, 0, out.stderr)
        self.s.run(["git", "init", "-q", sub], operation="git-init")
        with self.unchanged():
            self.refused(self.audited("start", target=sub))
        self.reset()
        movable = self.s.project("movable", git=True)
        publish(project_preflight(movable, self.root))
        for scope in (movable, self.root):
            moved = scope.with_name(scope.name + "-moved")
            scope.rename(moved)
            try:
                if scope == movable:
                    with self.unchanged():
                        self.refused(self.audited("start", target=moved))
                else:
                    with self.unchanged():
                        self.refused(self.s.run([moved / "releases" / self.release / "bin/resolve-core",
                            "start", moved, self.w, "claude", skill_ids("claude")[0]], check=False))
            finally:
                moved.rename(scope)
        gitdir = movable / ".git"
        gitdir.rename(movable / ".git-held")
        shutil.copytree(movable / ".git-held", gitdir)
        with self.unchanged():
            self.refused(self.audited("start", target=movable))
        # Restore the original directory identity, not a byte-equivalent copy.
        copied_git = movable / ".git-copy"
        gitdir.rename(copied_git)
        (movable / ".git-held").rename(gitdir)
        # Recreate the same pathname with copied genuine owned records and Git
        # metadata. Path equality does not preserve worktree or Git-dir inodes.
        held = movable.with_name("held")
        movable.rename(held)
        shutil.copytree(held, movable)
        with self.unchanged():
            self.refused(self.audited("start", target=movable))
        self.reset()
        # Copying genuine records does not create authority at another root.
        other = self.s.project("copied", git=True)
        (other / ".domestique-private").mkdir(mode=0o700)
        (other / STATE).mkdir(mode=0o700)
        (other / STATE / "manifest").write_bytes((self.w / STATE / "manifest").read_bytes())
        (other / STATE / "manifest").chmod(0o600)
        with self.unchanged():
            self.refused(self.audited("start", target=other))
        alias = self.s.root / "alias"
        alias.symlink_to(self.w)
        with self.unchanged():
            with self.assertRaises(Refusal):
                project_identity(alias)
            self.refused(self.audited("start", target=alias))
        non_git = self.s.project("not-git")
        bare = self.s.project("bare")
        self.s.run(["git", "init", "-q", "--bare", bare], operation="git-init")
        with self.unchanged():
            for target in (non_git, bare, non_git / "missing"):
                with self.assertRaises(Refusal):
                    project_preflight(target, self.root)

    def test_unsafe_permissions_boundaries_and_native_missing(self):
        binding = self.start()
        targets = [self.w / STATE / "manifest", self.w / ".git/info",
                   self.w / ".claude/agents", self.w / native_inventory("claude")[0]]
        for target in targets:
            with self.subTest(target=str(target.relative_to(self.w))):
                target.chmod(0o555 if target.is_dir() else 0o000)
                if target.is_file():
                    # The existing oracle's held descriptor records unreadable
                    # fixture bytes; no operation repairs permissions.
                    target.chmod(0o600)
                    fd = os.open(target, os.O_RDONLY)
                    self.s.held[target] = fd
                    target.chmod(0o000)
                with self.unchanged():
                    if target.is_dir():
                        # No namespace effect on these read-only host containers:
                        # genuine no-op and workflow guards need read/search only.
                        self.assertEqual(publish(project_preflight(self.w, self.root)).items, [])
                        out = self.audited("read", binding=binding)
                        self.assertEqual(out.returncode, 0, out.stderr)
                    else:
                        with self.assertRaises(Refusal):
                            project_preflight(self.w, self.root)
                        self.refused(self.audited("read", binding=binding))
                self.reset()
        uid = os.getuid()
        with self.unchanged(), patch.object(os, "getuid", return_value=uid + 1):
            with self.assertRaises(Refusal):
                project_preflight(self.w, self.root)
        for p in F.PROVIDERS:
            binding = self.start(p)
            for leaf in native_inventory(p):
                (self.w / leaf).unlink()
                with self.unchanged():
                    self.refused(self.audited("read", p, binding=binding))
                self.reset()

    def test_preflight_collision_matrix_zero_writes(self):
        leaf = native_inventory("claude")[0]
        dest = self.b / leaf
        dest.parent.mkdir(parents=True)
        template = (self.w / leaf).read_bytes()
        outside = self.b / "other"
        outside.write_bytes(template)
        sock = None
        def socket_leaf():
            nonlocal sock
            sock = socket.socket(socket.AF_UNIX)
            sock.bind(str(dest))
        collisions = [
            ("equal", lambda: dest.write_bytes(template)),
            ("unknown", lambda: dest.write_text("unknown\n")),
            ("symlink", lambda: dest.symlink_to(outside)),
            ("hardlink", lambda: os.link(outside, dest)),
            ("fifo", lambda: os.mkfifo(dest)),
            ("socket", socket_leaf),
            ("directory", lambda: dest.mkdir()),
            ("unsafe-mode", lambda: (dest.write_bytes(template), dest.chmod(0o666))),
        ]
        for name, create in collisions:
            with self.subTest(collision=name):
                create()
                with self.unchanged():
                    with self.assertRaises(Refusal):
                        project_preflight(self.b, self.root)
                if sock:
                    sock.close()
                    sock = None
                if dest.is_dir() and not dest.is_symlink():
                    dest.rmdir()
                else:
                    dest.unlink()
        self.reset()
        for rel in (leaf, ".claude/agents/domestique-old.md",
                    ".domestique-private/manifest", ".claude/agents/implementer.md"):
            path = self.b / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("index-only\n")
            self.s.run(["git", "-C", self.b, "add", "-f", "--", rel])
            path.unlink()
            with self.unchanged():
                with self.assertRaises(Refusal):
                    project_preflight(self.b, self.root)
            self.reset()
        for rel in (".domestique-private/manifest", ".claude/.domestique",
                    ".agents/skills/domestique-fork/SKILL.md", "CLAUDE.md",
                    ".github/copilot-instructions.md"):
            path = self.b / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("domestique old/unknown authority\n")
            with self.unchanged():
                with self.assertRaises(Refusal):
                    project_preflight(self.b, self.root)
            self.reset()
        for rel in (".git/info", ".domestique-private"):
            if rel == ".git/info":
                (self.b / ".git/info/exclude").unlink()
                (self.b / rel).rmdir()
            else:
                (self.b / rel).mkdir(mode=0o700)
            with self.unchanged():
                with self.assertRaises(Refusal):
                    project_preflight(self.b, self.root)
            self.reset()

    def test_exclusions_exact_unowned_edited_shared_and_preexisting(self):
        info = self.b / ".git/info/exclude"
        i = project_identity(self.b)[0]
        block = exclusion_block(i, patterns(("claude",)))
        for data in (block, block + block, block.split(b"# END")[0],
                     block.replace(b"BEGIN", b"UNKNOWN"), block + b"not terminated",
                     block.replace(b"SKILL.md", b"OTHER.md"), b"\xff\n",
                     b"x"*8192 + b"\n"):
            info.write_bytes(data)
            with self.unchanged():
                with self.assertRaises(Refusal):
                    project_preflight(self.b, self.root)
            self.reset()
        # Existing exact outside lines are not adopted into any block.
        info.write_bytes(b"# host line\n" + b"".join((p + "\n").encode()
                                                   for p in patterns(("claude",))))
        with self.unchanged():
            plan = project_preflight(self.b, self.root)
            self.assertIsNone(plan.exclusion["action"])
            self.assertTrue(all(v[0] == "preexisting" for v in plan.exclusion["records"].values()))
            ActivationPublication(plan)  # All encodings/bounds are dry-run, too.
        info.write_bytes(info.read_bytes() + (patterns(("claude",))[0] + "\n").encode())
        with self.unchanged():
            with self.assertRaises(Refusal):
                project_preflight(self.b, self.root)
        self.reset()
        owned = self.w / ".git/info/exclude"
        owned.write_bytes(owned.read_bytes().replace(b"SKILL.md", b"OTHER.md"))
        with self.unchanged():
            with self.assertRaises(Refusal):
                project_preflight(self.w, self.root)

    def test_linked_worktree_isolation_and_shared_exclude_refusal(self):
        # A genuine Git-resolved unborn linked worktree, without any commits.
        linked = self.s.project("linked", git=True)
        common = self.w / ".git"
        admin = common / "worktrees/linked"
        admin.parent.mkdir()
        (linked / ".git").rename(admin)
        (admin / "commondir").write_text("../..\n")
        (admin / "gitdir").write_text(str(linked / ".git") + "\n")
        (linked / ".git").write_text("gitdir: " + str(admin) + "\n")
        with self.unchanged():
            i = project_identity(linked)[0]
            self.assertEqual(i["git_common_dir"], str(common))
            self.assertEqual(i["git_dir"], str(admin))
            self.refused(self.audited("start", target=linked))
            with self.assertRaises(Refusal):
                project_preflight(linked, self.root)

    def test_generation_fixed_template_and_journal_facts(self):
        old_binding = self.start()
        manifest = self.w / STATE / "manifest"
        i, root, providers, exclusions = project_manifest_read(manifest.read_bytes())
        providers["claude"]["status"] = "disabled"
        manifest.write_bytes(project_manifest_bytes(i, root, providers, exclusions))
        (self.w / STATE / "routing/claude.receipt").unlink()
        (self.root / "active").write_text("release=" + self.release2 + "\n")
        plan = project_preflight(self.w, self.root, ("claude",))
        tx = ActivationPublication(plan)
        self.assertEqual(tx.providers["claude"]["generation"], 2)
        self.assertEqual(tx.providers["claude"]["template_release"], self.release)
        project_previous_read(tx.previous, tx.tx, plan, tx.items)
        project_pending_read(tx.pending, tx.tx, plan, tx.previous, tx.items)
        # Metadata only, never native/exclude preimages.
        self.assertNotIn(b"STOP", tx.previous)
        self.assertNotIn(b"configured", tx.previous)
        for data, parser in ((tx.previous, lambda b: project_previous_read(
                b, tx.tx, plan, tx.items)), (tx.pending, lambda b: project_pending_read(
                b, tx.tx, plan, tx.previous, tx.items))):
            rows = parse_record(data)
            for n in range(len(rows)):
                with self.assertRaises(Refusal):
                    parser(record(rows[:n] + rows[n+1:]))
        self.assertTrue(tx.begin())
        while tx.count < len(tx.items):
            tx.apply_next()
            with self.assertRaises(Refusal):
                G.ActivationGuard(self.root, self.w, "claude")
        raw = tx.published
        header = published_header(tx.tx, tx.pending)
        # Every possible prefix of the actual successful facts remains pending.
        for n in range(len(header), len(raw) + 1):
            project_facts_prefix(raw[:n], tx.tx, tx.pending, tx.items)
        for bad in (raw + b"sequence=0", raw + b"\xff", raw + b"x"*8192):
            with self.assertRaises(Refusal):
                project_facts_prefix(bad, tx.tx, tx.pending, tx.items)
        tx.finish()
        parsed = project_manifest_read(manifest.read_bytes())[2]
        self.assertEqual(parsed["claude"]["generation"], 2)
        with self.unchanged():
            self.refused(self.audited("read", binding=old_binding))
            new = self.start()
            self.assertEqual(binding_read(new)["gen"], 2)
        # Overflow refuses before a new journal or receipt.
        parsed["claude"]["status"] = "disabled"
        parsed["claude"]["generation"] = MAX_NUMBER
        manifest.write_bytes(project_manifest_bytes(i, root, parsed, exclusions))
        (self.w / STATE / "routing/claude.receipt").unlink()
        with self.unchanged():
            with self.assertRaises(Refusal):
                project_preflight(self.w, self.root)

    def test_metadata_preserved_no_generation_advance_and_protected_loader(self):
        path = self.w / native_inventory("claude")[0]
        base = path.read_bytes()
        path.write_bytes(RecordAdmissionTests.edit(str(path), base, b'model: "literal"\n'))
        manifest = (self.w / STATE / "manifest").read_bytes()
        with self.unchanged():
            tx = publish(project_preflight(self.w, self.root, ("claude",)))
            self.assertFalse(tx.items)
            self.assertEqual((self.w / STATE / "manifest").read_bytes(), manifest)
        # Unknown/protected loader and name changes cannot acquire fresh bindings.
        for data in (base.replace(b"domestique-v2-claude", b"domestique-v2-codex"),
                     base.replace(b"STOP", b"GO"), base + b"new instructions\n"):
            self.assertNotEqual(base, data)
            path.write_bytes(data)
            with self.unchanged():
                self.refused(self.audited("start"))

    def test_partial_publication_and_creation_races(self):
        plan = project_preflight(self.b, self.root)
        tx = ActivationPublication(plan)
        leaf = self.b / native_inventory("claude")[0]
        leaf.parent.mkdir(parents=True)
        leaf.write_text("racing unowned leaf\n")
        with self.unchanged():
            with self.assertRaises(Refusal):
                tx.begin()
        self.reset()
        tx = ActivationPublication(project_preflight(self.b, self.root))
        tx.begin()
        # First exclusion edit succeeds; no manifest or receipt may certify it.
        tx.apply_next()
        self.assertFalse((self.b / STATE / "manifest").exists())
        with self.unchanged():
            self.refused(self.audited("start", target=self.b))

            with self.assertRaises(Refusal):
                project_preflight(self.b, self.root)
        self.reset()
        tx = ActivationPublication(project_preflight(self.b, self.root))
        tx.begin()
        original = Pub.exclusive
        def race(path, data, mode, *args):
            if path.name == "exclude-afterimage":
                path.write_bytes(data)  # Equality is not this transaction's creation.
            return original(path, data, mode, *args)
        before_exclude = (self.b / ".git/info/exclude").read_bytes()
        with patch.object(Pub, "exclusive", side_effect=race):
            with self.assertRaises((Refusal, OSError)):
                tx.apply_next()
        self.assertEqual((self.b / ".git/info/exclude").read_bytes(), before_exclude)
        self.assertEqual(project_facts_read(tx.published, tx.tx, tx.pending, tx.items)[1], 0)
        self.assertTrue((self.b / STATE / "pending").exists())
        with self.unchanged():
            self.refused(self.audited("start", target=self.b))

    def test_source_relocation_does_not_retarget_runtime_and_late_nested_root(self):
        relocated = self.source.with_name("relocated-source")
        self.source.rename(relocated)
        with self.unchanged():
            self.start()
        self.reset()
        intermediate = self.w / "intermediate"
        sub = intermediate / "sub"
        sub.mkdir(parents=True)
        guard = G.ActivationGuard(self.root, sub, "claude")
        self.s.run(["git", "init", "-q", intermediate], operation="git-init")
        with self.unchanged():
            with self.assertRaises(Refusal):
                guard.check()
            self.refused(self.audited("start", target=sub))


class PermissionTests(unittest.TestCase):
    """Real modes, exact planned parents; one small genuine installed cohort."""
    @classmethod
    def setUpClass(cls):
        cls.context = fixtures.fixture()
        cls.s = cls.context.__enter__()
        cls.addClassCleanup(cls.context.__exit__, None, None, None)
        cls.root = fixtures.root(cls.s)
        cls.release = fixtures.publish_local(fixtures.source(cls.s), cls.s.env)["runtime"]
        cls.helper = cls.root / "releases" / cls.release / "bin/resolve-core"
        cls.w = cls.s.project("private", git=True)
        (cls.w / ".beads").mkdir()
        (cls.w / ".beads/SYNTHETIC").write_text("inert preservation sentinel\n")
        cls.fresh = cls.s.project("fresh", git=True)
        cls.disabled = cls.s.project("disabled", git=True)
        publish(project_preflight(cls.w, cls.root, ("claude",)))
        publish(project_preflight(cls.disabled, cls.root, ("codex",)))
        # Revocation history, not invented creation provenance. This is only a
        # fixture state transition; no public disable/enable API is implied.
        manifest = cls.disabled / STATE / "manifest"
        i, root, providers, exclusions = project_manifest_read(manifest.read_bytes())
        providers["codex"]["status"] = "disabled"
        manifest.write_bytes(project_manifest_bytes(i, root, providers, exclusions))
        (cls.disabled / STATE / "routing/codex.receipt").unlink()
        cls.binding = cls.s.run([cls.helper, "start", cls.root, cls.w, "claude",
                                skill_ids("claude")[0]]).stdout
        cls.s.pristine = cls.s.snapshot()

    def tearDown(self):
        self.reset()

    def reset(self):
        self.s.assert_no_calls()
        self.s.restore(self.s.snapshot())

    @contextmanager
    def mode(self, path, mode):
        self.assertTrue(path.is_relative_to(self.s.root))
        old = stat.S_IMODE(path.stat().st_mode)
        path.chmod(mode)
        try:
            self.assertFalse(os.access(path, os.W_OK), "requires genuine nonwritable fixture")
            yield
        finally:
            path.chmod(old)  # Only this test's own denial, solely for fixture cleanup.

    def claude_usable(self, pending=False):
        for op, role, tail in (("start", skill_ids("claude")[0], []),
                              ("read", "orchestrator", [self.binding.decode()]),
                              ("route", "implementer", [self.binding.decode()])):
            out = self.s.run(["python3", "-I", "-S", "-B", "-c", AUDIT, self.helper,
                              op, self.root, self.w, "claude", role, *tail], check=False)
            if pending:
                self.assertNotEqual(out.returncode, 0)
                self.assertEqual(out.stdout, b"")
                self.assertNotIn(b"BODY_OPEN", out.stderr)
            else:
                self.assertEqual(out.returncode, 0, out.stderr)
                self.assertIn(b"BODY_OPEN", out.stderr)
                if op == "read":
                    self.assertEqual(out.stdout, (self.root / "releases" / self.release /
                                                  "roles/orchestrator.md").read_bytes())

    def test_exact_claude_then_codex_nonwritable_root(self):
        self.assertFalse((self.w / ".agents").exists())
        self.assertTrue(os.access(self.w / STATE, os.W_OK))
        self.assertTrue(os.access(self.w / ".git/info", os.W_OK))
        with self.mode(self.w, 0o555):
            before = self.s.snapshot()
            with self.assertRaisesRegex(Refusal, "planned parent not writable"):
                project_preflight(self.w, self.root, ("codex",))
            self.claude_usable()
            self.assertEqual(before, self.s.snapshot())
            self.assertFalse((self.w / STATE / "pending").exists())
            self.assertFalse((self.w / STATE / "routing/codex.receipt").exists())
        print("PERMISSION_EXACT_ROOT=refused-before-publication; prior-Claude-usable", flush=True)

    def test_planned_parent_permission_matrix(self):
        sidecar = ".agents/skills/domestique-v2-codex-goal/agents/openai.yaml"
        cases = [
            (self.fresh, ("claude",), ".", None),
            (self.fresh, F.PROVIDERS, ".", None),
            (self.fresh, ("claude",), ".claude", None),
            (self.fresh, ("claude",), ".claude/agents", None),
            (self.fresh, ("claude",), ".claude/skills", None),
            (self.fresh, F.PROVIDERS, ".codex/agents", None),
            (self.fresh, ("copilot",), ".github", None),
            (self.fresh, ("copilot",), ".github/skills", None),
            (self.fresh, ("claude",), ".git/info", None),
            (self.fresh, ("claude",), ".git/info", "exclude"),
            (self.fresh, ("claude",), ".git/info/exclude", None),
            (self.w, ("codex",), ".agents", None),
            (self.w, ("codex",), ".agents/skills", None),
            (self.w, ("codex",), ".codex", None),
            (self.w, ("codex",), ".codex/agents", None),
            (self.w, ("codex",), ".domestique-private", None),
            (self.w, ("codex",), STATE, None),
            (self.w, ("codex",), STATE + "/routing", None),
            (self.w, ("codex",), ".git/info", None),
            (self.w, ("codex",), ".git/info/exclude", None),
            (self.disabled, ("codex",), str(Path(sidecar).parent), sidecar),
            (self.disabled, ("codex",), str(Path(sidecar).parent.parent), "agents"),
        ]
        for w, providers, leaf, missing in cases:
            with self.subTest(worktree=w.name, providers=providers, parent=leaf, missing=missing):
                target = w / leaf
                if missing == "exclude":
                    (w / ".git/info/exclude").unlink()
                elif missing:
                    (w / sidecar).unlink()
                    if missing == "agents":
                        (w / sidecar).parent.rmdir()
                if not target.exists():
                    target.mkdir(parents=True)
                mode = 0o444 if target.is_file() else 0o500 if leaf.startswith(
                    ".domestique-private") else 0o555
                with self.mode(target, mode):
                    before = self.s.snapshot()
                    # Both dry-run API and apply entry refuse the same original
                    # state. Neither can publish journals, exclusions or dirs.
                    for apply in (False, True):
                        with self.assertRaises(Refusal):
                            plan = project_preflight(w, self.root, providers)
                            if apply:
                                publish(plan)
                        self.assertEqual(before, self.s.snapshot())
                    if w != self.w or not leaf.startswith(".domestique-private"):
                        self.claude_usable()
                    self.assertEqual(before, self.s.snapshot())
                    self.assertFalse((w / STATE / "pending").exists())
                if w == self.w and leaf.startswith(".domestique-private"):
                    # The denied private mode itself invalidates its frozen
                    # schema. Restoring only our test mode must recover the old
                    # activation, with no journal left behind by the refusal.
                    restored = self.s.snapshot()
                    self.claude_usable()
                    self.assertEqual(restored, self.s.snapshot())
                print("PERMISSION_CASE=" + json.dumps(dict(worktree=str(w), parent=leaf,
                    providers=providers, missing=missing, mode=oct(mode),
                    dry_run_and_apply_refused=True, full_snapshot_preserved=True)), flush=True)
                self.reset()
        self.assertEqual(len(cases), 22)

    def test_late_original_permissions_before_direct_effects(self):
        for stage in ("plan", "prepared", "journal", "exclude"):
            with self.subTest(stage=stage):
                plan = project_preflight(self.w, self.root, ("codex",))
                tx = None if stage == "plan" else ActivationPublication(plan)
                if stage in ("journal", "exclude"):
                    self.assertTrue(tx.begin())
                if stage == "exclude":
                    self.assertEqual(tx.items[0]["phase"], "exclusions")
                    tx.apply_next()
                with self.mode(self.w, 0o555):
                    before = self.s.snapshot()
                    with self.assertRaises(Refusal):
                        if stage == "plan":
                            ActivationPublication(plan)
                        elif stage == "prepared":
                            tx.begin()
                        else:
                            tx.apply_next()
                    self.claude_usable(pending=stage in ("journal", "exclude"))
                    self.assertEqual(before, self.s.snapshot())
                print("PERMISSION_LATE=" + stage + ":zero-further-effects", flush=True)
                self.reset()

    def test_readonly_workflow_noop_and_no_effect_ancestors(self):
        # Required state remains 0700/0600 by frozen schema. Host read/search
        # containers and an unchanged exclusion leaf need not be writable.
        with ExitStack() as stack:
            for path in (self.w, self.w / ".claude", self.w / ".claude/agents",
                         self.w / ".claude/skills", self.w / ".git/info",
                         self.w / ".git/info/exclude"):
                stack.enter_context(self.mode(path, 0o444 if path.is_file() else 0o555))
            before = self.s.snapshot()
            self.assertEqual(publish(project_preflight(self.w, self.root)).items, [])
            self.claude_usable()
            self.assertEqual(before, self.s.snapshot())
        # W is not a destination parent if all required top-level containers
        # already exist. Only lower writable creation parents receive effects.
        for parent in (".agents", ".codex"):
            (self.w / parent).mkdir()
        with self.mode(self.w, 0o555):
            before = self.s.snapshot()
            plan = project_preflight(self.w, self.root, ("codex",))
            self.assertEqual(before, self.s.snapshot())  # successful dry-run
            tx = publish(plan)
            self.assertTrue(tx.items)
            self.assertFalse(any(item["path"].parent == self.w for item in tx.items))
            self.claude_usable()
            out = self.s.run([self.helper, "start", self.root, self.w, "codex",
                              skill_ids("codex")[0]])
            binding_read(out.stdout)
        # A real fresh publication with preexisting exact exclusions need not
        # edit or rename info/exclude; do not impose a fictitious write on it.
        exclude = self.fresh / ".git/info/exclude"
        exclude.write_bytes(b"".join((p + "\n").encode() for p in patterns(("claude",))))
        with self.mode(exclude, 0o444), self.mode(exclude.parent, 0o555):
            before = S.snapshot(exclude)
            tx = publish(project_preflight(self.fresh, self.root))
            self.assertFalse(any(item["phase"] == "exclusions" for item in tx.items))
            self.assertEqual(S.snapshot(exclude), before)
        print("PERMISSION_POSITIVE=readonly-noop-workflow; writable-nearest-ancestor", flush=True)


class PolicyTests(unittest.TestCase):
    """Retained policy/command inventory against genuinely published prerequisites."""
    invoke = ProjectTests.invoke
    audited = ProjectTests.audited
    refused = ProjectTests.refused
    start = ProjectTests.start
    unchanged = ProjectTests.unchanged
    reset = ProjectTests.reset
    tearDown = ProjectTests.tearDown
    LEGACY = (b"<!-- BEGIN domestique (managed) -->\n# Orchestration policy\n"
              b"<!-- END domestique -->\n")

    @classmethod
    def setUpClass(cls):
        cls.context = fixtures.fixture()
        cls.s = cls.context.__enter__()
        cls.addClassCleanup(cls.context.__exit__, None, None, None)
        cls.root = fixtures.root(cls.s)
        src = fixtures.source(cls.s)
        cls.release = fixtures.publish_local(src, cls.s.env)["runtime"]
        cls.helper = cls.root / "releases" / cls.release / "bin/resolve-core"
        cls.w = cls.s.project("policy-enabled", git=True)
        cls.b = cls.s.project("policy-fresh", git=True)
        tx = publish(project_preflight(cls.w, cls.root, F.PROVIDERS))
        cls.bindings = {}
        for p in F.PROVIDERS:
            cls.bindings[p] = guarded_start(cls.root, cls.w, p, skill_ids(p)[0])[0]
        cls.s.pristine = cls.s.snapshot()
        print("POLICY_COHORT=" + json.dumps(dict(release=cls.release,
            helper_sha256=sha(cls.helper.read_bytes()), facts=len(tx.items),
            root=str(cls.s.root), identity=cls.s.identity)), flush=True)

    @classmethod
    def collisions(cls):
        # Independent literal inventory asserts the emitter/inspector conventions;
        # do not let the production inventory define away an omitted regression.
        policies = ("CLAUDE.md", "CLAUDE.local.md", "AGENTS.md", "AGENTS.override.md",
                    ".github/copilot-instructions.md")
        commands = {
            ".claude/commands/decompose.md":
                b"Decompose the following into a beads work graph:\nbd ready\n",
            ".claude/commands/goal.md":
                b"Drive epic $ARGUMENTS to completion, unattended\nbd ready\n"}
        assert POLICY_LEAVES == policies and set(LEGACY_COMMANDS) == set(commands)
        return [(p, cls.LEGACY) for p in policies] + list(commands.items()) + [
            ("CLAUDE.local.md", b"<!-- BeGiN domestique (broken)\n"),
            (".claude/.domestique/manifest", b"legacy\n"),
            (".codex/.domestique/manifest", b"legacy\n"),
            (".github/.domestique/manifest", b"legacy\n"),
            (".domestique-private/manifest", b"format=1\n"),
            (".claude/commands/domestique-fork.md", b"unknown fork\n")]

    def put(self, worktree, rel, data):
        path = worktree / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def test_fresh_dryrun_inventory_each_provider_zero_writes(self):
        cases = 0
        for rel, data in self.collisions():
            self.put(self.b, rel, data)
            with self.unchanged():
                for p in F.PROVIDERS:
                    with self.subTest(path=rel, provider=p):
                        # Same planner for preview and apply; preparation must
                        # never reach begin, even when no apply was requested.
                        for apply in (False, True):
                            with self.assertRaises(Refusal):
                                tx = ActivationPublication(project_preflight(self.b, self.root, (p,)))
                                if apply:
                                    tx.begin()
                            cases += 1
                        self.refused(self.audited("start", p, target=self.b))
                self.assertFalse((self.b / STATE / "manifest").exists())
            self.reset()
        print("POLICY_FRESH_DRYRUN_REFUSALS=" + str(cases), flush=True)

    def test_late_authority_revokes_each_provider_rerun_and_helper(self):
        cases = 0
        for rel, data in self.collisions():
            self.put(self.w, rel, data)
            with self.unchanged():
                for p in F.PROVIDERS:
                    with self.subTest(path=rel, provider=p):
                        with self.assertRaises(Refusal):
                            publish(project_preflight(self.w, self.root, (p,)))
                        with self.assertRaises(Refusal):
                            verified_helper(self.root, self.w, p, self.bindings[p])
                        for op in ("start", "read", "route"):
                            self.refused(self.audited(op, p, binding=None if op == "start"
                                                     else self.bindings[p]))
                            cases += 1
            self.reset()
        print("POLICY_LATE_INSTALLED_BODY_FREE_REFUSALS=" + str(cases), flush=True)

    def test_ordinary_host_policies_and_commands_preserved_positive(self):
        for w in (self.w, self.b):
            for rel in (*POLICY_LEAVES, *LEGACY_COMMANDS):
                self.put(w, rel, b"# Host instructions\nUse the project's test runner.\n")
        with self.unchanged():
            for p in F.PROVIDERS:
                ActivationPublication(project_preflight(self.b, self.root, (p,)))
                self.assertFalse(publish(project_preflight(self.w, self.root, (p,))).items)
                for op in ("start", "read", "route"):
                    out = self.audited(op, p, binding=None if op == "start" else self.bindings[p])
                    self.assertEqual(out.returncode, 0, out.stderr)
                    self.assertIn(b"BODY_OPEN", out.stderr)
        host = {rel: (self.b / rel).read_bytes() for rel in (*POLICY_LEAVES, *LEGACY_COMMANDS)}
        publish(project_preflight(self.b, self.root, F.PROVIDERS))
        with self.unchanged():
            for rel, data in host.items():
                self.assertEqual((self.b / rel).read_bytes(), data)
            for p in F.PROVIDERS:
                out = self.audited("start", p, target=self.b)
                self.assertEqual(out.returncode, 0, out.stderr)
                self.assertIn(b"BODY_OPEN", out.stderr)
        print("POLICY_HOST_POSITIVE=3 providers; fresh, preview, rerun, start/read/route", flush=True)

    def test_disabled_provider_cannot_reactivate_over_guest_policy(self):
        for p in F.PROVIDERS:
            manifest = self.w / STATE / "manifest"
            i, root, providers, exclusions = project_manifest_read(manifest.read_bytes())
            providers[p]["status"] = "disabled"
            manifest.write_bytes(project_manifest_bytes(i, root, providers, exclusions))
            (self.w / STATE / "routing" / (p + ".receipt")).unlink()
            self.put(self.w, "CLAUDE.local.md", self.LEGACY)
            with self.unchanged():
                with self.assertRaises(Refusal):
                    publish(project_preflight(self.w, self.root, (p,)))
                for op in ("start", "read", "route"):
                    self.refused(self.audited(op, p, binding=None if op == "start"
                                             else self.bindings[p]))
            self.reset()

    def test_original_policy_witness_before_write_body_and_output(self):
        for rel in ("CLAUDE.local.md", ".claude/commands/goal.md"):
            data = self.LEGACY if rel.endswith("local.md") else dict(self.collisions())[rel]
            tx = ActivationPublication(project_preflight(self.b, self.root))
            self.put(self.b, rel, data)
            with self.unchanged():
                with self.assertRaises(Refusal):
                    tx.begin()
            self.reset()
            guard = G.ActivationGuard(self.root, self.w, "claude")
            self.put(self.w, rel, data)
            with self.unchanged(), patch.object(C, "snapshot", wraps=C.snapshot) as opens:
                with self.assertRaises(Refusal):
                    C.guarded_body_read(self.root, self.release, "roles/implementer.md",
                                        guard.index, guard.watch, guard.check)
                self.assertEqual(opens.call_count, 0)
            self.reset()
        # A mutation after body validation still cannot release guarded output.
        original = G.binding_bytes
        def late(*args, **kwargs):
            result = original(*args, **kwargs)
            self.put(self.w, "CLAUDE.local.md", self.LEGACY)
            return result
        with patch.object(G, "binding_bytes", side_effect=late):
            with self.assertRaises(Refusal):
                guarded_start(self.root, self.w, "claude", skill_ids("claude")[0])
        self.reset()
        # Preserve original creation/writer witnesses: inject at the short-write
        # handoff, then require refusal BEFORE the next real os.write.
        tx = ActivationPublication(project_preflight(self.b, self.root))
        tx.begin()
        original_write = Pub.checked_write
        def late_write(fd, path, data, before, guard):
            self.put(self.b, "CLAUDE.local.md", self.LEGACY)
            snapshot = self.s.snapshot()
            with patch.object(S.os, "write", wraps=S.os.write) as writes:
                with self.assertRaises(Refusal):
                    original_write(fd, path, data, before, guard)
                self.assertEqual(writes.call_count, 0)
            self.assertEqual(self.s.snapshot(), snapshot)
            raise Refusal("injected late policy")
        with patch.object(Pub, "checked_write", side_effect=late_write):
            with self.assertRaises(Refusal):
                tx.apply_next()
        self.assertFalse((self.b / STATE / "manifest").exists())
        print("POLICY_ORIGINAL_WITNESSES=pre-begin, pre-body, pre-output, pre-write", flush=True)


class WriteWitnessTests(unittest.TestCase):
    """Actual prior activation + original transaction and installed-helper guards."""
    audited = ProjectTests.audited
    refused = ProjectTests.refused
    reset = ProjectTests.reset
    tearDown = ProjectTests.tearDown

    @classmethod
    def setUpClass(cls):
        cls.context = fixtures.fixture()
        cls.s = cls.context.__enter__()
        cls.addClassCleanup(cls.context.__exit__, None, None, None)
        cls.root = fixtures.root(cls.s)
        cls.release = fixtures.publish_local(fixtures.source(cls.s), cls.s.env)["runtime"]
        cls.helper = cls.root / "releases" / cls.release / "bin/resolve-core"
        cls.w = cls.s.project("write-witness", git=True)
        initial = publish(project_preflight(cls.w, cls.root, ("claude",)))
        cls.binding = guarded_start(cls.root, cls.w, "claude", skill_ids("claude")[0])[0]
        cls.s.pristine = cls.s.snapshot()
        print("WRITE_COHORT=" + json.dumps(dict(root=str(cls.s.root), identity=cls.s.identity,
            helper_sha256=sha(cls.helper.read_bytes()), prior_facts=len(initial.items))),
            flush=True)

    def test_genuine_prior_and_authorized_partial_effects_complete(self):
        before = self.s.snapshot()
        out = self.audited("read", binding=self.binding, role="orchestrator")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout, (self.root / "releases" / self.release /
                                    "roles/orchestrator.md").read_bytes())
        self.assertNotIn(b"ACTIVE_OPEN", out.stderr)
        self.assertEqual(before, self.s.snapshot())
        tx = ActivationPublication(project_preflight(self.w, self.root, ("codex",)))
        originals = dict(tx.originals)
        real = S.os.write
        events = []
        interrupted = set()
        def partial(fd, data):
            # One EINTR and then genuinely short writes for each opened inode.
            inode = os.fstat(fd).st_ino
            if inode not in interrupted:
                interrupted.add(inode)
                events.append("EINTR")
                raise InterruptedError()
            count = real(fd, data[:max(1, len(data) // 2)])
            events.append(count)
            return count
        with patch.object(S.os, "write", side_effect=partial):
            self.assertTrue(tx.begin())
            while tx.count < len(tx.items):
                tx.apply_next()
            tx.finish()
        self.assertEqual(dict(tx.originals), originals)
        self.assertFalse((self.w / STATE / "pending").exists())
        self.assertFalse(publish(project_preflight(self.w, self.root, ("codex",))).items)
        for p in ("claude", "codex"):
            out = self.audited("start", p)
            self.assertEqual(out.returncode, 0, out.stderr)
        print("WRITE_AUTHORIZED_PARTIAL=" + json.dumps(dict(events=events,
            items=len(tx.items), originals_retained=True, completed=True)), flush=True)

    def run_refusal(self, target, kind="equal", boundary="fact", retry=None):
        """Inject at a real primitive handoff, never replace the original guard.

        Compare the entire owned tree, including inode/mode/link count and exact
        bytes, from the injection onward. Audit actual write/namespace syscalls,
        including accidental cleanup and write-capable opens, not mock intent.
        """
        tx = ActivationPublication(project_preflight(self.w, self.root, ("codex",)))
        originals = dict(tx.originals)
        if boundary not in ("pending", "previous", "published"):
            self.assertTrue(tx.begin())
        if boundary in ("native", "manifest", "receipt"):
            while not (tx.items[tx.count]["phase"] == boundary and
                       tx.items[tx.count]["action"] != "mkdir"):
                tx.apply_next()
        if boundary == "unlink":
            while tx.count < len(tx.items):
                tx.apply_next()
        target = Path(target) if target is not None else None
        evidence, events, before_detection = {}, [], []
        mutated = []
        real_write = S.os.write

        def mutate():
            self.assertFalse(mutated)
            old = target.lstat() if os.path.lexists(target) else None
            data = target.read_bytes() if old and stat.S_ISREG(old.st_mode) else b"late\n"
            mode = stat.S_IMODE(old.st_mode) if old else 0o644
            if kind == "mode":
                target.chmod(0o600 if mode != 0o600 else 0o644)
            elif kind == "directory":
                target.chmod(0o700 if mode != 0o700 else 0o755)
            else:
                candidate = self.s.root / "foreign-afterimage"
                candidate.write_bytes(data + (b"changed\n" if kind == "content" else b""))
                candidate.chmod(mode)
                target.parent.mkdir(parents=True, exist_ok=True)
                if kind in ("symlink", "hardlink"):
                    target.unlink()
                    if kind == "symlink":
                        target.symlink_to(candidate)
                    else:
                        os.link(candidate, target)
                else:
                    os.replace(candidate, target)
            new = target.lstat()
            if kind == "equal" and old:
                self.assertEqual(target.read_bytes(), data)
                self.assertNotEqual(old.st_ino, new.st_ino)
                self.assertEqual(stat.S_IMODE(new.st_mode), mode)
            evidence.update(old_inode=old.st_ino if old else None,
                            new_inode=new.st_ino, mode=stat.S_IMODE(new.st_mode),
                            links=new.st_nlink, sha256=sha(data))
            mutated.append(self.s.snapshot())

        @contextmanager
        def audit():
            with ExitStack() as stack:
                for name in ("open", "write", "mkdir", "replace", "unlink", "fchmod",
                             "ftruncate", "link", "rmdir"):
                    original = getattr(S.os, name)
                    def observed(*args, _name=name, _original=original, **kwargs):
                        writable = _name != "open" or args[1] & (
                            os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
                        # Git's read-only query connects stdin to /dev/null;
                        # that is not a destination creation or publication.
                        writable = writable and not (_name == "open" and args[0] == os.devnull)
                        if mutated and writable:
                            events.append(dict(syscall=_name,
                                destination=str(args[0]),
                                bytes=len(args[1]) if _name == "write" else None))
                        return _original(*args, **kwargs)
                    stack.enter_context(patch.object(S.os, name, side_effect=observed))
                yield

        real_checked = Pub.checked_write
        real_safe_checked = S.checked_write
        fired = []
        def handoff(original, fd, path, data, before, guard):
            nonlocal target
            match = boundary == "fact" and path == self.w / STATE / "published"
            match |= boundary in ("pending", "previous", "published") and path.name == boundary
            match |= boundary == "exclude" and path.name == "exclude-afterimage"
            match |= boundary in ("native", "manifest", "receipt") and path == tx.items[tx.count]["path"]
            if not match or fired:
                return original(fd, path, data, before, guard)
            fired.append(True)
            if target is None:
                target = path
            if retry:
                # Skip write_created's zero-byte pre-chmod validation.
                if not data:
                    fired.clear()
                    return original(fd, path, data, before, guard)
                audited_write = S.os.write
                def short(fd, value):
                    if mutated:
                        return audited_write(fd, value)
                    if retry == "short":
                        count = real_write(fd, value[:7])
                        before_detection.append(dict(bytes=count, path=str(path)))
                        mutate()
                        return count
                    mutate()
                    raise InterruptedError()
                with patch.object(S.os, "write", side_effect=short):
                    return original(fd, path, data, before, guard)
            mutate()
            return original(fd, path, data, before, guard)

        namespace = tx.watch.namespace
        @contextmanager
        def namespace_handoff(parent, entry_delta, directory_delta=0):
            match = boundary == "rename" and entry_delta == -1
            match |= boundary == "mkdir" and directory_delta == 1
            match |= boundary == "unlink" and entry_delta == -1
            if match and not fired:
                fired.append(True)
                mutate()
            with namespace(parent, entry_delta, directory_delta):
                yield

        with audit(), patch.object(Pub, "checked_write",
                side_effect=lambda *a: handoff(real_checked, *a)), patch.object(S, "checked_write",
                side_effect=lambda *a: handoff(real_safe_checked, *a)), patch.object(
                tx.watch, "namespace", side_effect=namespace_handoff):
            with self.assertRaises(Refusal):
                if boundary in ("pending", "previous", "published"):
                    tx.begin()
                elif boundary == "unlink":
                    tx.finish()
                elif boundary == "mkdir":
                    while tx.count < len(tx.items):
                        tx.apply_next()
                else:
                    tx.apply_next()
        self.assertTrue(fired)
        self.assertTrue(mutated)
        self.assertEqual(self.s.snapshot(), mutated[0])
        self.assertEqual(events, [], "post-detection OS effects")
        self.assertEqual(dict(tx.originals), originals)
        self.assertTrue((self.w / STATE / "pending").exists())
        if boundary not in ("receipt", "unlink") and target.name != "codex.receipt":
            self.assertFalse((self.w / STATE / "routing/codex.receipt").exists())
        if boundary == "receipt":
            self.assertEqual((self.w / STATE / "routing/codex.receipt").read_bytes(), b"")
        if boundary == "fact":
            self.assertEqual(project_facts_read(tx.published, tx.tx, tx.pending, tx.items)[1], 0)
        # Pending must refuse before opening even a receipt, not merely a body.
        receipt_audit = AUDIT.replace('if args[0].endswith("/active"):',
            'if "/routing/" in args[0]:\n            os.write(2, b"RECEIPT_OPEN\\n")\n'
            '        if args[0].endswith("/active"):')
        for op in ("start", "read", "route"):
            args = ["python3", "-I", "-S", "-B", "-c", receipt_audit, self.helper, op,
                    self.root, self.w, "claude",
                    skill_ids("claude")[0] if op == "start" else "implementer"]
            if op != "start":
                args.append(self.binding.decode())
            out = self.s.run(args, check=False)
            self.refused(out)
            self.assertNotIn(b"RECEIPT_OPEN", out.stderr)
        self.assertEqual(self.s.snapshot(), mutated[0])
        print("WRITE_REFUSAL=" + json.dumps(dict(target=str(target), kind=kind,
            boundary=boundary, retry=retry, writes_before_detection=before_detection,
            events_after_detection=events, preserved=evidence, pending=True,
            published_bytes=(self.w / STATE / "published").stat().st_size
                if (self.w / STATE / "published").exists() else None,
            helper_body_and_receipt_opens=0, apply_success=False)), flush=True)
        self.reset()

    def test_all_provider_native_originals_before_fact(self):
        for p in F.PROVIDERS:
            for leaf in native_inventory(p):
                with self.subTest(provider=p, leaf=leaf):
                    self.run_refusal(self.w / leaf)

    def test_native_content_mode_and_links_before_fact(self):
        for kind in ("content", "mode", "symlink", "hardlink"):
            with self.subTest(kind=kind):
                self.run_refusal(self.w / native_inventory("claude")[0], kind)

    def test_state_core_index_exclusion_and_journal_witnesses(self):
        targets = [self.w / STATE / p for p in (
            "manifest", "routing/claude.receipt", "routing/copilot.receipt",
            "pending", "previous", "published")]
        targets += [self.w / ".git/info/exclude", self.w / ".git/index",
                    self.root / "state/runtime-manifest", self.root / "active", self.helper]
        for target in targets:
            with self.subTest(target=target):
                self.run_refusal(target)
        self.run_refusal(self.w / ".claude/skills", "directory")
        # Original exclusion preimage, before even writing its staged afterimage.
        self.run_refusal(self.w / ".git/info/exclude", boundary="exclude")

    def test_directly_related_creation_rename_truncate_unlink_handoffs(self):
        for boundary in ("pending", "previous", "published", "exclude", "mkdir",
                         "native", "rename", "manifest", "receipt", "unlink"):
            with self.subTest(boundary=boundary):
                self.run_refusal(self.w / native_inventory("claude")[0], boundary=boundary)

    def test_short_write_and_eintr_repeat_original_checks(self):
        for boundary in ("fact", "exclude", "manifest"):
            for retry in ("short", "eintr"):
                with self.subTest(boundary=boundary, retry=retry):
                    self.run_refusal(self.w / native_inventory("claude")[0],
                                     boundary=boundary, retry=retry)

    def test_inflight_destination_is_checked_by_open_inode_primitive(self):
        # The transaction delegates exactly this destination to checked_write;
        # changing its mode alone does not incidentally change a parent witness.
        for boundary in ("exclude", "native", "manifest", "receipt"):
            with self.subTest(boundary=boundary):
                self.run_refusal(None, "mode", boundary)


class MutationHandoffTests(unittest.TestCase):
    """R7: real open/parent-open handoffs, not a mocked pre-mutation guard."""
    setUpClass = classmethod(WriteWitnessTests.setUpClass.__func__)
    tearDown = ProjectTests.tearDown
    reset = ProjectTests.reset
    audited = ProjectTests.audited
    refused = ProjectTests.refused

    def mutation_case(self, boundary, target_name, kind="equal"):
        tx = ActivationPublication(project_preflight(self.w, self.root, ("codex",)))
        originals = dict(tx.originals)
        if boundary != "create":
            self.assertTrue(tx.begin())
        if boundary == "truncate":
            while tx.items[tx.count]["phase"] != "manifest":
                tx.apply_next()
        if boundary == "mkdir":
            while tx.items[tx.count]["action"] != "mkdir":
                tx.apply_next()
        if boundary == "unlink":
            while tx.count < len(tx.items):
                tx.apply_next()
        stage = self.w / STATE / "exclude-afterimage"
        targets = dict(native=self.w / native_inventory("claude")[0],
                       state=self.w / STATE / "manifest",
                       exclusion=self.w / ".git/info/exclude", stage=stage,
                       parent=self.w / STATE, index=self.w / ".git/index",
                       policy=self.w / "CLAUDE.md")
        target = targets[target_name]
        evidence, injected, events = {}, [], []
        real_open = os.open

        def inject():
            old = target.lstat() if target.exists() else None
            data = target.read_bytes() if old and stat.S_ISREG(old.st_mode) else b"late\n"
            if kind == "mode":
                target.chmod((0o644 if boundary == "chmod" else 0o600)
                             if target == stage else 0o755)
            else:
                candidate = self.s.root / "r7-foreign"
                candidate.write_bytes(data)
                candidate.chmod(stat.S_IMODE(old.st_mode) if old else 0o644)
                os.replace(candidate, target)
                if old:
                    self.assertNotEqual(old.st_ino, target.stat().st_ino)
                    self.assertEqual(target.read_bytes(), data)
            evidence.update(target=str(target), old_inode=old.st_ino if old else None,
                            foreign_inode=target.stat().st_ino,
                            foreign_mode=stat.S_IMODE(target.stat().st_mode))
            # Mark first: snapshot itself opens files and must not reinject.
            injected.append(None)
            injected[0] = self.s.snapshot()

        def opened(path, flags, *args, **kwargs):
            if injected and flags & (os.O_CREAT | os.O_TRUNC):
                events.append(dict(syscall="open", destination=str(path), flags=flags))
            fd = real_open(path, flags, *args, **kwargs)
            p = Path(path)
            match = boundary == "chmod" and p == stage and flags == os.O_RDONLY | os.O_NOFOLLOW
            match |= boundary == "truncate" and p == tx.items[tx.count]["path"] and \
                flags == os.O_WRONLY | os.O_NOFOLLOW
            directory = flags == os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            match |= directory and (
                boundary == "rename" and p == self.w / ".git/info" or
                boundary == "mkdir" and p == tx.items[tx.count]["path"].parent or
                boundary in ("create", "unlink") and p == self.w / STATE)
            if match and not injected:
                if boundary == "chmod":
                    self.assertEqual(stat.S_IMODE(os.fstat(fd).st_mode), 0o600)
                inject()
            return fd

        with ExitStack() as stack:
            stack.enter_context(patch.object(os, "open", side_effect=opened))
            for name in ("write", "fchmod", "ftruncate", "mkdir", "link", "unlink",
                         "replace", "rmdir"):
                original = getattr(os, name)
                def traced(*args, _name=name, _original=original, **kwargs):
                    if injected:
                        events.append(dict(syscall=_name, destination=str(args[0])))
                    result = _original(*args, **kwargs)
                    if not injected and boundary == "mode-result" and _name == "fchmod" and \
                            args[1] == 0o644 and stage.exists() and \
                            os.fstat(args[0]).st_ino == stage.stat().st_ino:
                        inject()
                    return result
                stack.enter_context(patch.object(os, name, side_effect=traced))
            with self.assertRaises(Refusal):
                if boundary == "create":
                    tx.begin()
                elif boundary == "unlink":
                    tx.finish()
                else:
                    tx.apply_next()
        self.assertTrue(injected, (boundary, target_name))
        self.assertEqual(events, [], "no syscall effects after invalid open handoff")
        self.assertEqual(self.s.snapshot(), injected[0])
        self.assertEqual(dict(tx.originals), originals)
        self.assertEqual(target.stat().st_ino, evidence["foreign_inode"])
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), evidence["foreign_mode"])
        if boundary == "create":
            self.assertFalse((self.w / STATE / "pending").exists())
        else:
            self.assertTrue((self.w / STATE / "pending").exists())
        if boundary in ("chmod", "rename", "mode-result"):
            self.assertEqual(project_facts_read(tx.published, tx.tx, tx.pending, tx.items)[1], 0)
            self.assertEqual(stat.S_IMODE(stage.stat().st_mode),
                             evidence["foreign_mode"] if target == stage else
                             0o600 if boundary == "chmod" else 0o644)
        if boundary != "unlink":
            self.assertFalse((self.w / STATE / "routing/codex.receipt").exists())
        if boundary != "create":
            receipt_audit = AUDIT.replace('if args[0].endswith("/active"):',
                'if "/routing/" in args[0]:\n            os.write(2, b"RECEIPT_OPEN\\n")\n'
                '        if args[0].endswith("/active"):')
            for op in ("start", "read", "route"):
                args = ["python3", "-I", "-S", "-B", "-Werror", "-c", receipt_audit,
                        self.helper, op, self.root, self.w, "claude",
                        skill_ids("claude")[0] if op == "start" else "implementer"]
                if op != "start":
                    args.append(self.binding.decode())
                out = self.s.run(args, check=False)
                self.refused(out)
                self.assertNotIn(b"RECEIPT_OPEN", out.stderr)
            self.assertEqual(self.s.snapshot(), injected[0])
        print("MUTATION_HANDOFF=" + json.dumps(dict(boundary=boundary, target=target_name,
            kind=kind, preserved=evidence, events_after_injection=events,
            pending=boundary != "create",
            body_and_receipt_opens=0 if boundary != "create" else None,
            originals_retained=True)), flush=True)
        self.reset()

    def test_exclusion_reopen_original_and_owned_stage_matrix(self):
        for target in ("native", "state", "exclusion", "stage"):
            with self.subTest(target=target):
                self.mutation_case("chmod", target)
        self.mutation_case("chmod", "stage", "mode")
        for target in ("native", "stage"):
            with self.subTest(mode_result=target):
                self.mutation_case("mode-result", target)

    def test_truncate_reopen_original_and_destination_matrix(self):
        for target in ("native", "state", "exclusion"):
            with self.subTest(target=target):
                self.mutation_case("truncate", target)

    def test_namespace_parent_open_matrix(self):
        for boundary, target, kind in (
                ("rename", "native", "equal"), ("rename", "exclusion", "equal"),
                ("rename", "stage", "equal"), ("rename", "stage", "mode"),
                ("rename", "parent", "mode"), ("rename", "index", "equal"),
                ("rename", "policy", "equal"), ("mkdir", "native", "equal"),
                ("create", "native", "equal"), ("unlink", "native", "equal")):
            with self.subTest(boundary=boundary, target=target, kind=kind):
                self.mutation_case(boundary, target, kind)

    def test_normal_exclusion_and_unchanged_noop(self):
        start = self.s.run([self.helper, "start", self.root, self.w, "claude",
                            skill_ids("claude")[0]])
        binding_read(start.stdout)
        out = self.s.run([self.helper, "read", self.root, self.w, "claude",
                          "orchestrator", start.stdout.decode()])
        self.assertEqual(out.stdout, (self.root / "releases" / self.release /
                                     "roles/orchestrator.md").read_bytes())
        tx = publish(project_preflight(self.w, self.root, ("codex",)))
        self.assertEqual(tx.items[0]["action"], "edit-exclude")
        self.assertEqual(stat.S_IMODE((self.w / ".git/info/exclude").stat().st_mode), 0o644)
        self.assertFalse((self.w / STATE / "exclude-afterimage").exists())
        self.assertFalse((self.w / STATE / "pending").exists())
        before = self.s.snapshot()
        self.assertFalse(publish(project_preflight(self.w, self.root, ("codex",))).items)
        self.assertEqual(before, self.s.snapshot())
        for provider in ("claude", "codex"):
            out = self.s.run([self.helper, "start", self.root, self.w, provider,
                              skill_ids(provider)[0]])
            binding_read(out.stdout)
        print("MUTATION_NORMAL=" + json.dumps(dict(effects=len(tx.items),
            stage_absent=True, noop_unchanged=True, genuine_start=True,
            exact_body_bytes=len((self.root / "releases" / self.release /
                                  "roles/orchestrator.md").read_bytes()))), flush=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
