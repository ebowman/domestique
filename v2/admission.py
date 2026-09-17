"""Appendix F bounded in-memory classifier, shared with the future native writer.

Returns field names only. No values, parser excerpts, rendering, native calls,
metadata copies or secret evaluation. Protected bytes always compare against T.
"""
import re
from .safe import need, text_bounds
from .project_records import native_inventory, role_leaf

NAME = r"[A-Za-z_][A-Za-z0-9_-]{0,63}"
ENV = r"[A-Za-z_][A-Za-z0-9_]{0,63}"
TOOL = r"[A-Za-z0-9_./*:-]{1,256}"
PLAIN = r"[A-Za-z0-9_./*+@-][A-Za-z0-9_./*+@:-]*"
QUOTED = r'"(?:[^"\\\n]|\\["\\])*"'
SINGLE = r"'(?:[^'\n]|'')*'"
# PLAIN is only F's lexical envelope, not proof of a YAML string. In particular
# its '*' can start an alias, '@' is reserved at the start, a final ':' is a
# mapping indicator, and '-' / '---' / '...' are YAML indicators.
# Whole-token grammars, never a numeric-looking prefix/character heuristic.
# YAML 1.1 decimal/legacy octal, lowercase bases with underscores (including
# modern 0o), decimal-point floats and sexagesimal; YAML 1.2 decimal/exponents.
# Do not decode numbers. Uppercase base prefixes, incomplete exponents, semver
# and opaque IDs remain strings. Special inf/nan spellings are checked below.
# Exact YAML 1.1/1.2 type productions, not case-insensitive keywords. Only
# infinity permits a sign; signed NaN and mixed-case near-misses are strings
# when they fit PLAIN. YAML 1.1's single-letter booleans are included.
NONSTRING = frozenset((
    "true", "True", "TRUE", "false", "False", "FALSE",
    "yes", "Yes", "YES", "no", "No", "NO",
    "on", "On", "ON", "off", "Off", "OFF", "y", "Y", "n", "N",
    "null", "Null", "NULL", "~",
    ".inf", ".Inf", ".INF", "+.inf", "+.Inf", "+.INF", "-.inf", "-.Inf", "-.INF",
    ".nan", ".NaN", ".NAN",
))
NUMBER = (r"[-+]?(?:[0-9]+|[1-9][0-9_]*|0[0-7_]+|"
          r"0b[01_]+|0o[0-7_]+|0x[0-9a-fA-F_]+|"
          r"(?:[0-9][0-9_]*\.[0-9_]*|\.[0-9_]+)"
          r"(?:[eE][-+][0-9]+)?|"
          r"(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)[eE][-+]?[0-9]+|"
          r"[1-9][0-9_]*(?::[0-5]?[0-9])+|"
          r"[0-9][0-9_]*(?::[0-5]?[0-9])+\.[0-9_]*)")
# Timestamp syntax remains unsupported, including the date-only YAML form;
# unrelated date-like IDs must not be swept up by NUMBER. YAML permits T/t
# between date and time, but only uppercase Z for the UTC zone.
TIMESTAMP = (r"[0-9]{4}-[0-9]{2}-[0-9]{2}|"
             r"[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}[Tt][0-9]{1,2}:"
             r"[0-9]{2}:[0-9]{2}(?:\.[0-9]*)?(?:Z|[-+][0-9]{1,2}"
             r"(?::[0-9]{2})?)?")


def string(value, toml=False, nonempty=False):
    need(type(value) is str, "metadata-string-type")
    if re.fullmatch(QUOTED, value):
        decoded = re.sub(r'\\(["\\])', r"\1", value[1:-1])
    elif not toml and re.fullmatch(SINGLE, value):
        decoded = value[1:-1].replace("''", "'")
    else:
        need(not toml and re.fullmatch(PLAIN, value), "metadata-string")
        need(not value.startswith(("*", "@")) and not value.endswith(":") and
             value not in ("-", "---", "..."),
             "metadata-string-syntax")
        need(value not in NONSTRING and
             not re.fullmatch(NUMBER, value) and not re.fullmatch(TIMESTAMP, value),
             "metadata-string-token")
        decoded = value
    need(len(decoded.encode()) <= 4096 and (decoded or not nonempty), "metadata-string-bounds")
    return decoded


def array(value, toml=False, names=None):
    need(type(value) is str, "metadata-array-type")
    need(value.startswith("[") and value.endswith("]"), "metadata-array")
    rest = value[1:-1].strip(" ")
    result = []
    token = re.compile(QUOTED + ("" if toml else "|" + SINGLE + "|" + PLAIN))
    while rest:
        match = token.match(rest)
        need(match is not None, "metadata-array-string")
        result.append(string(match[0], toml))
        rest = rest[match.end():].lstrip(" ")
        if rest:
            need(rest.startswith(",") and rest[1:].strip(" "), "metadata-array-separator")
            rest = rest[1:].lstrip(" ")
    need(len(result) <= 64 and len(set(result)) == len(result), "metadata-array-bounds")
    if names:
        need(all(re.fullmatch(names, v) for v in result), "metadata-array-names")
    return result


def tools(value):
    if value.startswith("["):
        return array(value, names=TOOL)
    need(value.startswith(('"', "'")), "metadata-tool-list")
    result = [s.strip(" ") for s in string(value).split(",")]
    need(len(result) <= 64 and len(set(result)) == len(result) and
         all(re.fullmatch(TOOL, s) for s in result), "metadata-tools")
    return result


def bool_value(value):
    need(value in ("true", "false"), "metadata-bool")


def integer_value(value):
    need(re.fullmatch(r"[1-9][0-9]{0,3}", value) and int(value) <= 3600, "metadata-integer")


def significant(lines):
    return [line for line in lines if line.strip(" \n") and
            not line.lstrip(" ").startswith("#")]


def yaml_map(lines, indent, depth=1):
    need(depth <= 5, "metadata-depth")
    lines = significant(lines)
    result, pos = {}, 0
    while pos < len(lines):
        match = re.fullmatch(" " * indent + r"([A-Za-z_][A-Za-z0-9_-]*):(?: (.*))?\n",
                             lines[pos])
        need(match is not None and re.fullmatch(NAME, match[1]) and match[1] not in result,
             "metadata-map-field")
        key, value = match[1], match[2]
        pos += 1
        end = pos
        while end < len(lines) and len(lines[end]) - len(lines[end].lstrip(" ")) > indent:
            end += 1
        if value is None:
            need(end > pos, "metadata-empty-map")
            result[key] = yaml_map(lines[pos:end], indent + 2, depth + 1)
        else:
            need(value and value == value.strip(" ") and end == pos, "metadata-map-scalar")
            result[key] = value
        pos = end
    need(len(result) <= 64, "metadata-map-bounds")
    return result


def environment(values, toml=False):
    need(type(values) is dict and len(values) <= 64, "metadata-env")
    for key, value in values.items():
        need(re.fullmatch(ENV, key) and type(value) is str, "metadata-env-field")
        string(value, toml)


def server(values, kind):
    need(type(values) is dict, "metadata-server")
    if kind == "claude":
        need("command" in values and set(values) <= {"command", "type", "args", "env"},
             "metadata-server-fields")
        if "type" in values:
            need(values["type"] == "stdio", "metadata-server-type")
    else:
        need({"type", "command", "tools"} <= set(values) <=
             {"type", "command", "tools", "args", "env"}, "metadata-server-fields")
        need(values["type"] in ("local", "stdio"), "metadata-server-type")
        array(values["tools"])
    string(values["command"])
    if "args" in values:
        array(values["args"])
    if "env" in values:
        environment(values["env"])


def claude_mcp(lines):
    lines = significant(lines)
    names, pos = set(), 0
    while pos < len(lines):
        match = re.fullmatch(r"  - (.+)\n", lines[pos])
        need(match is not None, "metadata-mcp-list")
        value = match[1]
        end = pos + 1
        while end < len(lines) and not lines[end].startswith("  - "):
            end += 1
        if value.endswith(":"):
            name = value[:-1]
            need(re.fullmatch(NAME, name), "metadata-server-name")
            server(yaml_map(lines[pos + 1:end], 6, 3), "claude")
        else:
            name = string(value)
            need(re.fullmatch(NAME, name) and end == pos + 1, "metadata-server-reference")
        need(name not in names and len(names) < 32, "metadata-mcp-bounds")
        names.add(name)
        pos = end
    need(names, "metadata-empty-mcp-list")


def yaml_mutable(key, lines, provider, role, sidecar):
    first = re.fullmatch(r"[^:]+:(?: (.*))?\n", lines[0])
    need(first is not None, "metadata-field")
    value = first[1]
    if key == "model":
        need(value is not None and not significant(lines[1:]), "metadata-model")
        string(value, nonempty=True)
    elif key in ("tools", "disallowedTools", "allowed-tools"):
        need(value is not None and not significant(lines[1:]), "metadata-tools-shape")
        tools(value)
    elif key == "mcpServers":
        need(value is None, "metadata-mcp-shape")
        claude_mcp(lines[1:])
    elif key == "mcp-servers":
        need(value is None, "metadata-mcp-shape")
        servers = yaml_map(lines[1:], 2, 2)
        need(0 < len(servers) <= 32, "metadata-mcp-bounds")
        for values in servers.values():
            server(values, "copilot")
    elif key == "interface":
        need(sidecar and value is None, "metadata-interface")
        fields = yaml_map(lines[1:], 2, 2)
        need(fields and set(fields) <= {"display_name", "short_description"},
             "metadata-interface-fields")
        for v in fields.values():
            string(v)
    else:
        need(False, "metadata-unsupported-field")


def yaml_protected(data, provider, role, sidecar):
    text = text_bounds(data)
    if sidecar:
        header, body = text, ""
    else:
        need(text.startswith("---\n") and "\n---\n" in text[3:], "metadata-frontmatter")
        header, body = text[4:].split("---\n", 1)
    allowed = ({"interface"} if sidecar else
               {"model", "tools", "disallowedTools", "mcpServers"} if role and provider == "claude"
               else {"model", "tools", "mcp-servers"} if role and provider == "copilot"
               else {"model", "allowed-tools"} if provider == "claude"
               else {"allowed-tools"} if provider == "copilot" else set())
    lines = header.splitlines(keepends=True)
    kept, admitted, seen, pos = [], set(), set(), 0
    while pos < len(lines):
        match = re.match(r"([A-Za-z_][A-Za-z0-9_-]*):", lines[pos])
        if not match:
            kept.append(lines[pos])
            pos += 1
            continue
        key = match[1]
        need(key not in seen, "metadata-duplicate")
        seen.add(key)
        end = pos + 1
        while end < len(lines) and (lines[end].startswith((" ", "#")) or
                                    lines[end] == "\n"):
            end += 1
        if key in allowed:
            yaml_mutable(key, lines[pos:end], provider, role, sidecar)
            admitted.add(key)
        else:
            kept.extend(lines[pos:end])
        pos = end
    return "".join(kept) + ("\0" + body if not sidecar else ""), admitted


def toml_protected(data, pristine):
    text = text_bounds(data)
    template = text_bounds(pristine)
    # This is the ONLY multiline exception; bind the entire delimiter/value.
    marker = 'developer_instructions = """\n'
    need(template.count(marker) == 1 and text.count(marker) == 1, "metadata-loader")
    value = marker + template.split(marker, 1)[1].split('"""\n', 1)[0] + '"""\n'
    need(text.count(value) == 1, "metadata-protected-loader")
    text = text.replace(value, "\0\n")
    allowed = {"model", "model_reasoning_effort", "sandbox_mode"}
    tables, top_seen, kept, admitted = {}, set(), [], set()
    table = None
    mutable = False
    for line in text.splitlines(keepends=True):
        if not line.strip(" \n") or line.lstrip(" ").startswith("#"):
            if not mutable:
                kept.append(line)
            continue
        if line.startswith("["):
            match = re.fullmatch(r"\[mcp_servers\.(" + NAME + r")(\.env)?\]\n", line)
            need(match is not None, "metadata-table")
            table = (match[1], bool(match[2]))
            need(table not in tables, "metadata-duplicate-table")
            tables[table] = {}
            mutable = True
            admitted.add("mcp_servers")
            continue
        if line == "\0\n":
            need(table is None, "metadata-loader-location")
            kept.append(line)
            mutable = False
            continue
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*) = (.+)\n", line)
        need(match is not None, "metadata-assignment")
        key, value = match[1], match[2]
        if table is not None:
            need(key not in tables[table] and len(tables[table]) < 64, "metadata-map-bounds")
            tables[table][key] = value
            continue
        need(key not in top_seen, "metadata-duplicate")
        top_seen.add(key)
        mutable = key in allowed
        if not mutable:
            kept.append(line)
        else:
            decoded = string(value, toml=True, nonempty=key == "model")
            if key == "model_reasoning_effort":
                need(decoded in ("minimal", "low", "medium", "high", "xhigh", "max", "ultra"),
                     "metadata-reasoning")
            if key == "sandbox_mode":
                need(decoded in ("read-only", "workspace-write", "danger-full-access"),
                     "metadata-sandbox")
            admitted.add(key)
    names = {name for name, _ in tables}
    need(len(names) <= 32, "metadata-mcp-bounds")
    for name in names:
        need((name, False) in tables, "metadata-orphan-env")
        values = tables[name, False]
        stdio = "command" in values
        need(stdio != ("url" in values), "metadata-transport")
        common = {"enabled", "required", "enabled_tools", "disabled_tools",
                  "startup_timeout_sec", "tool_timeout_sec"}
        need(set(values) <= common | ({"command", "args", "env_vars", "cwd"}
                                      if stdio else {"url"}), "metadata-server-fields")
        for key, value in values.items():
            if key in ("enabled", "required"):
                bool_value(value)
            elif key.endswith("_timeout_sec"):
                integer_value(value)
            elif key in ("args", "env_vars", "enabled_tools", "disabled_tools"):
                array(value, toml=True, names=ENV if key == "env_vars" else None)
            else:
                string(value, toml=True)
        if (name, True) in tables:
            need(stdio, "metadata-http-env")
            environment(tables[name, True], toml=True)
    return "".join(kept), admitted


def admit(provider, leaf, live, pristine):
    need(leaf in native_inventory(provider), "metadata-inventory")
    # Bounds precede any parsing/classification of either afterimage.
    text_bounds(live)
    text_bounds(pristine)
    role = leaf in (role_leaf(provider, "implementer"), role_leaf(provider, "reviewer"))
    if provider == "codex" and role:
        protected, fields = toml_protected(live, pristine)
        base, _ = toml_protected(pristine, pristine)
    else:
        sidecar = leaf.endswith("/agents/openai.yaml")
        protected, fields = yaml_protected(live, provider, role, sidecar)
        base, _ = yaml_protected(pristine, provider, role, sidecar)
    need(protected == base, "metadata-protected-bytes")
    return tuple(sorted(fields))
