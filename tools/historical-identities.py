#!/usr/bin/env python3
"""Replay historical installers offline; see historical-identities.md."""
import argparse
import ast
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time


REPO = Path(__file__).resolve().parents[1]
BEGIN = b"<!-- BEGIN domestique (managed) -->"
END = b"<!-- END domestique -->"
REQUIRED = "5211df2a6c2c03d7ec6d385a0c204ea2e79fc9aaa2855406ec8bd0cf791bac5d"
SELECTORS = ("default", "claude", "codex", "copilot", "both", "all")
POLICIES = {
    "CLAUDE.md": "claude", "CLAUDE.local.md": "claude",
    "AGENTS.md": "codex", "AGENTS.override.md": "codex",
    ".github/copilot-instructions.md": "copilot",
}
# An explicit executable allowlist, not the user's PATH. No native client,
# package manager, network tool, or credential helper can fall through it.
UTILITIES = (
    "bash sh git awk sed grep find wc cut paste head tail cmp cp mkdir rm mv "
    "rmdir touch date mktemp cat dirname tr sort stat uname readlink chmod "
    "basename diff uniq xargs printf shasum perl env id od ln"
).split()
BLOCKED = "bd claude codex copilot gh curl wget brew npm npx node ssh sudo".split()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode()


def run(argv, *, cwd, env, timeout=60):
    """Bound the entire process group, including shell grandchildren."""
    with subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          start_new_session=True, umask=0o022) as proc:
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            out, err = proc.communicate()
            return {"returncode": None, "stdout": out.decode(errors="replace"),
                    "stderr": err.decode(errors="replace"), "timeout": True}
        except BaseException:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate()
            raise
        return {"returncode": proc.returncode, "stdout": out.decode(errors="replace"),
                "stderr": err.decode(errors="replace"), "timeout": False}


def git(*args):
    env = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0"}
    result = run(["/usr/bin/git", "--no-pager", *args], cwd=REPO, env=env)
    if result["returncode"] != 0:
        raise ValueError(f"git {args}: {result}")
    return result["stdout"]


def policy_body(data):
    """Installer awk semantics: whole-line markers, print each body line + LF.

    Reject anything the installer's markers_sane would reject. CR is not
    stripped: awk's record separator is LF, not Python's splitlines().
    """
    lines = data.split(b"\n")
    if lines.count(BEGIN) != 1 or lines.count(END) != 1:
        raise ValueError("missing or duplicate policy markers")
    first, last = lines.index(BEGIN), lines.index(END)
    if first >= last:
        raise ValueError("inverted policy markers")
    return b"".join(line + b"\n" for line in lines[first + 1:last])


def outcome(result):
    """Only explicit CLI rejection is 'unsupported'; all other errors fail."""
    if result["timeout"]:
        return "failure"
    if result["returncode"] == 0:
        return "success"
    text = result["stdout"] + result["stderr"]
    if result["returncode"] == 2 and re.search(
        r"Unknown option: --(?:platform|guest)\b|"
        r"Error: --platform must be one of:|Invalid --platform\b", text
    ):
        return "unsupported"
    return "failure"


def allowlist(source):
    if LOOKUP_BEGIN in source:
        body = embedded_block(source).split("cat <<'PY'\n", 1)[1].split("\nPY\n}", 1)[0]
        tree = ast.parse(body)
        table = next(node.value for node in tree.body if isinstance(node, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == "_INSTALLER_IDENTITIES"
                             for t in node.targets))
        known = {}
        for key_node, value_node in zip(table.keys, table.values):
            owner, path, mode = ast.literal_eval(key_node)
            if path == LEGACY_PATH and mode == "*":
                if (not isinstance(value_node, ast.Call) or
                        not isinstance(value_node.func, ast.Name) or
                        value_node.func.id != "frozenset" or len(value_node.args) != 1 or
                        value_node.keywords):
                    raise ValueError("invalid generated legacy hashes")
                known[owner] = sorted(ast.literal_eval(value_node.args[0]))
        return known
    body = source.split("policy_legacy_base() {", 1)[1].split("\nPY\n}", 1)[0]
    tree = ast.parse(body.split("<<'PY'\n", 1)[1])
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "known" for target in node.targets
        ):
            return {key: sorted(value) for key, value in ast.literal_eval(node.value).items()}
    raise ValueError("policy_legacy_base known literal not found")


MODEL_ROLES = {
    ".claude/agents/implementer.md": "claude",
    ".codex/agents/implementer.toml": "codex",
    ".github/agents/domestique-v2-copilot-implementer.agent.md": "copilot",
}


def normalize(path, data, root=None, files=None):
    """Normalize only validated timestamp / attested model-marker project."""
    if path.endswith("/.domestique/manifest"):
        data, count = re.subn(
            rb"(?m)^installed_at=\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$",
            b"installed_at=<UTC-INSTALL-TIME>", data)
        if count != 1:
            raise ValueError(f"{path}: expected exactly one installed_at field")
    marker = b"# domestique-model-setup:"
    if path in MODEL_ROLES and marker in data:
        owner = MODEL_ROLES[path]
        lines = data.splitlines(keepends=True)
        position = 0 if owner == "codex" else 1
        if (sum(marker in line for line in lines) != 1 or len(lines) <= position or
                not lines[position].startswith(marker + b" ")):
            raise ValueError(f"{path}: ambiguous model marker")
        raw = lines[position][len(marker) + 1:]
        newline = b"\r\n" if raw.endswith(b"\r\n") else b"\n"
        value = json.loads(raw)

        def canonical(item):
            return json.dumps(item, sort_keys=True, ensure_ascii=False,
                              separators=(",", ":"), allow_nan=False).encode()

        if (type(value) is not dict or set(value) != {
                "v", "project", "harness", "implementer_sha256", "reviewer_sha256"} or
                type(value["v"]) is not int or value["v"] != 1 or
                value["harness"] != owner or root is None or
                value["project"] != str(root) or raw != canonical(value) + newline):
            raise ValueError(f"{path}: invalid model marker")
        rest = b"".join(lines[:position] + lines[position + 1:])
        reviewer = path.replace("implementer", "reviewer")
        if (files is None or reviewer not in files or
                value["implementer_sha256"] != sha(rest) or
                value["reviewer_sha256"] != sha(files[reviewer][0])):
            raise ValueError(f"{path}: model marker does not attest role pair")
        # Do not strip the marker, hashes, harness, model fields, or role body.
        value["project"] = "<PHYSICAL-PROJECT-ROOT>"
        lines[position] = marker + b" " + canonical(value) + newline
        data = b"".join(lines)
    return data


def provider(path):
    if path in POLICIES:
        return POLICIES[path]
    for prefix, name in ((".claude/", "claude"), (".codex/", "codex"),
                         (".github/", "copilot"), (".agents/", "shared")):
        if path.startswith(prefix):
            # The original domestique* skills are Codex-owned, not shared.
            if path.startswith(".agents/skills/domestique"):
                return "codex"
            return name
    if path == ".git/info/exclude":
        return "shared"
    raise ValueError(f"unclassified installer output: {path}")


def snapshot(root):
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"unexpected symlink: {path}")
        if path.is_file():
            result[path.relative_to(root).as_posix()] = (
                path.read_bytes(), path.stat().st_mode & 0o777)
    return result


def isolated(work):
    bindir = work / "bin"
    bindir.mkdir()
    for name in UTILITIES:
        real = shutil.which(name, path="/usr/bin:/bin:/usr/sbin:/sbin")
        if real is None:
            raise ValueError(f"missing system utility: {name}")
        (bindir / name).symlink_to(real)
    (bindir / "python3").symlink_to(sys.executable)
    for name in BLOCKED:
        stub = bindir / name
        stub.write_text(
            "#!/bin/sh\n"
            'printf "%s\\n" "$0 $*" >> "$DEPENDENCY_LOG"\n'
            'printf "blocked dependency: %s\\n" "$0" >&2\nexit 97\n')
        stub.chmod(0o755)
    for name in ("home", "config", "cache", "data", "state", "tmp", "repo", "template"):
        (work / name).mkdir()
    return {
        "PATH": str(bindir), "HOME": str(work / "home"), "LC_ALL": "C",
        "LANG": "C", "TZ": "UTC", "TMPDIR": str(work / "tmp"),
        "XDG_CONFIG_HOME": str(work / "config"), "XDG_CACHE_HOME": str(work / "cache"),
        "XDG_DATA_HOME": str(work / "data"), "XDG_STATE_HOME": str(work / "state"),
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_COUNT": "0",
        "DEPENDENCY_LOG": str(work / "dependency.log"),
        "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1",
    }


def replay(script, selector, mode, timeout, *, pristine_roles=False):
    """Apply timeout to the installer; setup uses run's finite 60-second default."""
    with tempfile.TemporaryDirectory(prefix="domestique-history-") as directory:
        work = Path(directory).resolve()
        env = isolated(work)
        root = work / "repo"
        init = run(["git", "init", "-q", "--template=" + str(work / "template"), "."],
                   cwd=root, env=env)
        if init["returncode"] != 0:
            raise ValueError(f"isolated git init failed: {init}")
        before = snapshot(root)
        installer = work / "domestique.sh"
        installer.write_bytes(script.encode("utf-8"))
        args = ([] if selector == "default" else ["--platform", selector])
        if mode == "guest":
            args.append("--guest")
        result = run(["bash", str(installer), *args], cwd=root, env=env, timeout=timeout)
        status = outcome(result)
        for key in ("stdout", "stderr"):
            result[key] = result[key].replace(str(work), "<SANDBOX>")
        errors = []
        if (work / "dependency.log").exists():
            errors.append("blocked dependency invocation: " +
                          (work / "dependency.log").read_text().replace(str(work), "<SANDBOX>"))
        for name in ("home", "config", "cache", "data", "state"):
            if snapshot(work / name):
                errors.append(f"unexpected writes in isolated {name}")
        after = snapshot(root)
        artifacts = []
        for path in sorted(before.keys() | after.keys()):
            if before.get(path) == after.get(path):
                continue
            try:
                if path not in after:
                    raise ValueError(f"installer deleted initial file: {path}")
                data, permissions = after[path]
                owner = provider(path)
                normalized = normalize(path, data, root, after)
                if pristine_roles and path in MODEL_ROLES:
                    # The installer already stores the unmarked pristine role.
                    # Do not synthesize authority by stripping a live marker.
                    state = {"claude": ".claude", "codex": ".codex",
                             "copilot": ".github"}[owner]
                    data = after[f"{state}/.domestique/base/{path}"][0]
                    normalized = normalize(path, data, root, after)
                    if normalized != data or b"# domestique-model-setup:" in data:
                        raise ValueError(f"{path}: marked pristine role")
                kind = ("policy-body" if path in POLICIES else
                        "metadata" if "/.domestique/" in path or path.startswith(".git/")
                        else "file")
                identity = policy_body(data) if kind == "policy-body" else normalized
                artifacts.append({
                    "path": path, "provider": owner, "kind": kind,
                    "sha256": sha(identity) if kind != "metadata" else None,
                    "output_sha256": sha(normalized), "permissions": permissions,
                    "normalization": (
                        "model_marker_project" if path in MODEL_ROLES else "installed_at"
                    ) if normalized != data else None,
                })
            except ValueError as exc:
                errors.append(str(exc))
        if status == "success" and not artifacts:
            errors.append("installer reported success without artifacts")
        if errors:
            status = "failure"
        record = {"selector": selector, "mode": mode, "args": args, "status": status}
        if status != "success":
            record["result"] = result
            record["errors"] = errors
            # Partial output is evidence, never authority.
            record["partial_artifacts"] = artifacts
        elif result["stderr"]:
            record["diagnostics"] = result["stderr"]
        return record, artifacts


def generate(ref, authority_ref, timeout):
    resolved = git("rev-parse", "--verify", ref + "^{commit}").strip()
    authority = git("rev-parse", "--verify", authority_ref + "^{commit}").strip()
    commits = git("log", "--full-history", "--topo-order", "--reverse",
                  "--format=%H", resolved, "--", "domestique.sh").splitlines()
    histories, blobs = [], {}
    for commit in commits:
        blob = git("rev-parse", commit + ":domestique.sh").strip()
        histories.append({"commit": commit, "blob": blob})
        blobs.setdefault(blob, []).append(commit)
    known = allowlist(git("show", authority + ":domestique.sh"))
    runs, sets, identities = [], {}, {}
    for index, (blob, provenance) in enumerate(blobs.items(), 1):
        script = git("show", blob)
        raw = script.encode("utf-8")
        object_id = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if object_id != blob:
            raise ValueError(f"{blob}: git show did not preserve installer bytes")
        # Additional preview selectors are included when advertised by the
        # parser. They may fail because the historical private runtime is absent.
        selectors = list(SELECTORS)
        if re.search(r"claude\|codex\|copilot\|both\|claude-copilot\|codex-copilot\|all\)", script):
            selectors += ["claude-copilot", "codex-copilot"]
        for selector in selectors:
            for mode in ("normal", "guest"):
                record, artifacts = replay(script, selector, mode, timeout)
                record.update(blob=blob, commits=provenance)
                if record["status"] == "success":
                    set_id = sha(encoded(artifacts))
                    sets.setdefault(set_id, artifacts)
                    record["output_set"] = set_id
                    for artifact in artifacts:
                        if artifact["kind"] == "metadata":
                            continue
                        key = (artifact["provider"], artifact["path"], mode, artifact["sha256"])
                        identities.setdefault(key, set()).update(provenance)
                runs.append(record)
        print(f"blob {index}/{len(blobs)}: {provenance[0]}", file=sys.stderr)
    order = {commit: index for index, commit in enumerate(commits)}
    inventory = []
    for (owner, path, mode, digest), provenance in sorted(identities.items()):
        ordered = sorted(provenance, key=order.__getitem__)
        inventory.append({"provider": owner, "path": path, "mode": mode, "sha256": digest,
                          "first_commit": ordered[0], "last_commit": ordered[-1],
                          "normalization": next(
                              a["normalization"] for artifacts in sets.values()
                              for a in artifacts if a["path"] == path and a["sha256"] == digest),
                          "commits": ordered})
    policies = {}
    for item in inventory:
        if item["path"] in POLICIES:
            policies.setdefault(item["provider"], set()).add(item["sha256"])
    missing = {owner: sorted(set(values) - policies.get(owner, set()))
               for owner, values in known.items()}
    counts = dict(sorted(Counter(record["status"] for record in runs).items()))
    return {
        "schema": 1, "history_ref": resolved, "allowlist_ref": authority,
        "history_command": "git log --full-history --topo-order --reverse --format=%H "
                           + resolved + " -- domestique.sh",
        "platform": sys.platform, "execution": "fresh git repo; default models; no --with-beads",
        "normalization": {
            "*/.domestique/manifest": "installed_at=<UTC-INSTALL-TIME> only",
            "attested model setup marker": "project=<PHYSICAL-PROJECT-ROOT> only",
        },
        "history": histories, "runs": runs, "output_sets": sets, "identities": inventory,
        "allowlist": known, "unreproduced_allowlist": missing,
        "required_policy_present": REQUIRED in policies.get("claude", set()),
        "dimensions": {"commits": len(commits), "installer_blobs": len(blobs),
                       "runs": len(runs), "output_sets": len(sets),
                       "identities": len(inventory), "outcomes": counts},
    }


LOOKUP_BEGIN = "# BEGIN GENERATED HISTORICAL IDENTITIES"
LOOKUP_END = "# END GENERATED HISTORICAL IDENTITIES"
LEGACY_PATH = "@legacy-policy-base"


def authority_artifact(item):
    """Finite adoption payload scope; never helper code or state metadata."""
    path = item["path"]
    return (item.get("normalization") is None and
            (path in POLICIES or
             (path.endswith((".md", ".toml", ".yaml")) and
              any(part in path for part in ("/agents/", "/commands/", "/skills/")))))


def historical_projection(data):
    if data["schema"] != 1:
        raise ValueError("unsupported history schema")
    identities = set()
    # Output sets are authority only through successful runs. Never project
    # partial artifacts or trust the normalized identity grouping index.
    for record in data["runs"]:
        if record["status"] != "success":
            continue
        artifacts = data["output_sets"][record["output_set"]]
        if sha(encoded(artifacts)) != record["output_set"]:
            raise ValueError("output set digest mismatch")
        for item in artifacts:
            if item["kind"] != "metadata" and authority_artifact(item):
                identities.add((item["provider"], item["path"], record["mode"], item["sha256"]))
    for owner, hashes in data["allowlist"].items():
        proven = {digest for provider_, path, mode, digest in identities
                  if provider_ == owner and path in POLICIES}
        missing = set(hashes) - proven
        if missing:
            raise ValueError(f"unreproduced legacy hashes for {owner}: {sorted(missing)}")
        # Preserve the old provider-only predicate exactly. Path/mode and
        # inventory/base proofs remain the responsibility of its existing caller.
        identities.update((owner, LEGACY_PATH, "*", digest) for digest in hashes)
    return identities


def current_projection(source, timeout):
    identities = set()
    for mode in ("normal", "guest"):
        record, artifacts = replay(source, "all", mode, timeout, pristine_roles=True)
        if record["status"] != "success":
            raise ValueError(f"current emission failed: {record}")
        for item in artifacts:
            if item["kind"] != "metadata" and authority_artifact(item):
                identities.add((item["provider"], item["path"], mode, item["sha256"]))
    return identities


def lookup_block(data, current):
    identities = historical_projection(data) | current
    grouped = {}
    for owner, path, mode, digest in sorted(identities):
        if not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ValueError("invalid identity digest")
        grouped.setdefault((owner, path, mode), []).append(digest)
    lines = [
        LOOKUP_BEGIN,
        "# Format 1; raw payload/body SHA-256 only; normalized grouping hashes excluded.",
        "# Regenerate: python3 tools/historical-identities.py --emit-lookup domestique.sh \\",
        "#   --history-data tools/historical-identities.json --current-source domestique.sh",
        "emit_historical_identity_library() {",
        "  cat <<'PY'",
        "# @legacy-policy-base/* preserves the original provider-only policy predicate.",
        "# Other keys are provider/path/install-mode; not yet used for adoption.",
        "_INSTALLER_IDENTITIES = {",
    ]
    for key, hashes in sorted(grouped.items()):
        lines.append(f"    {key!r}: frozenset((")
        lines.extend(f"        {digest!r}," for digest in hashes)
        lines.append("    )),")
    lines += [
        "}",
        "",
        "def installer_identity(provider, path, mode, digest):",
        "    return digest in _INSTALLER_IDENTITIES.get((provider, path, mode), ())",
        "",
        "def legacy_policy_identity(provider, digest):",
        f"    return installer_identity(provider, {LEGACY_PATH!r}, '*', digest)",
        "PY",
        "}",
        LOOKUP_END,
    ]
    return "\n".join(lines) + "\n"


def embedded_block(source):
    if source.count(LOOKUP_BEGIN) != 1 or source.count(LOOKUP_END) != 1:
        raise ValueError("expected exactly one generated lookup block")
    start = source.index(LOOKUP_BEGIN)
    end = source.index(LOOKUP_END, start) + len(LOOKUP_END)
    return source[start:end] + "\n"


def main():
    def interrupted(_signum, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default="main")
    parser.add_argument("--allowlist-ref", default="HEAD")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--emit-lookup", type=Path,
                        help="replace the marked compact lookup block in this installer")
    parser.add_argument("--history-data", type=Path)
    parser.add_argument("--current-source", type=Path,
                        help="explicit installer source for isolated current emissions")
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    if args.emit_lookup:
        if not args.history_data or not args.current_source or args.output:
            parser.error("--emit-lookup requires --history-data and --current-source, not --output")
        source = args.emit_lookup.read_text()
        old = embedded_block(source)
        data = json.loads(args.history_data.read_text())
        block = lookup_block(data, current_projection(args.current_source.read_text(), args.timeout))
        args.emit_lookup.write_text(source.replace(old, block))
        return 0
    if not args.output or args.history_data or args.current_source:
        parser.error("history replay requires --output; projection options require --emit-lookup")
    started = time.monotonic()
    data = generate(args.ref, args.allowlist_ref, args.timeout)
    args.output.write_bytes(encoded(data))
    print(json.dumps({"runtime_seconds": round(time.monotonic() - started, 3),
                      **data["dimensions"], "unreproduced_allowlist": data["unreproduced_allowlist"],
                      "required_policy_present": data["required_policy_present"]},
                     sort_keys=True), file=sys.stderr)
    # Historical failures are retained, but cannot masquerade as a clean run.
    return 1 if data["dimensions"]["outcomes"].get("failure") or not data["required_policy_present"] else 0


if __name__ == "__main__":
    sys.exit(main())
