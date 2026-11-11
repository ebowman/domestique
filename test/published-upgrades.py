#!/usr/bin/env python3
"""Opt-in, offline published-release gate; not an every-commit guarantee."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import time


REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("history", REPO / "tools/historical-identities.py")
history = importlib.util.module_from_spec(spec)
spec.loader.exec_module(history)
TAGS = ("v0.1.0", "v0.2.0", "v0.2.1", "v0.2.2", "v0.3.0",
        "v0.3.1", "v0.4.0", "v0.4.1", "v0.4.2", "v0.4.3")
STATES = {"claude": ".claude/.domestique", "codex": ".codex/.domestique",
          "copilot": ".github/.domestique"}
PREFIX = b"Public release-gate host prefix\r\n\n"
SUFFIX = b"\nPublic release-gate host suffix without newline"
MARKER = b"# domestique-model-setup:"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def write_json(path, value):
    # Evidence is append-only by filename: never silently replace a prior run.
    with path.open("xb") as stream:
        stream.write(history.encoded(value))


def capabilities(tag, source):
    """Audit the actual fixed published parsers, not a guessed ancestry date."""
    if tag == "v0.1.0":
        require("--platform)" not in source and "--guest)" not in source,
                "v0.1.0 capabilities changed")
        require('install_claude_md "$TARGET_DIR/CLAUDE.md"' in source,
                "missing original Claude installer")
        return ("claude",), ("normal",)
    require('case "${PLATFORM_ARG:-all}" in' in source and
            "claude|codex|both|copilot|all)" in source and "--guest)" in source,
            f"{tag}: unrecognized published capabilities; do not skip")
    return tuple(STATES), ("normal", "guest")


def plan():
    cases = []
    for tag in TAGS:
        revision = history.git("rev-parse", tag + "^{commit}").strip()
        source = history.git("show", revision + ":domestique.sh")
        providers, modes = capabilities(tag, source)
        for mode in modes:
            for provider in providers:
                cases.append(dict(id=f"{tag}-{mode}-{provider}", tag=tag, revision=revision,
                                  mode=mode, install="default" if tag == "v0.1.0" else provider,
                                  upgrade=provider, expected="success"))
            cases.append(dict(id=f"{tag}-{mode}-default-all", tag=tag, revision=revision,
                              mode=mode, install="default", upgrade="all", expected="success"))
    return cases


def tree(root, *, mtimes=True):
    result = {}
    for path in sorted(root.rglob("*")):
        st = path.lstat()
        require(not path.is_symlink(), f"unexpected symlink: {path}")
        data = path.read_bytes() if path.is_file() else None
        result[path.relative_to(root).as_posix()] = (
            st.st_mode, st.st_mtime_ns if mtimes else None,
            history.sha(data) if data is not None else None)
    return result


def unchanged(before, after, label):
    changed = [p for p in before.keys() | after.keys() if before.get(p) != after.get(p)]
    require(not changed, f"{label}: changed paths: {sorted(changed)}")


def export(revision, destination):
    """Replay the installer AND its same-revision tools, including private cores."""
    destination.mkdir()
    paths = ["domestique.sh"]
    if history.git("ls-tree", "--name-only", revision, "tools").strip():
        paths.append("tools")
    env = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0"}
    result = subprocess.run(["/usr/bin/git", "archive", revision, *paths],
                            cwd=REPO, env=env, capture_output=True, timeout=120, check=True)
    with tarfile.open(fileobj=io.BytesIO(result.stdout)) as archive:
        for member in archive:
            path = destination / member.name
            require(not Path(member.name).is_absolute() and ".." not in Path(member.name).parts,
                    "unsafe archive path")
            require(member.isfile() or member.isdir(), "nonregular historical support file")
            if member.isdir():
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(archive.extractfile(member).read())
                path.chmod(member.mode)
    return history.sha(result.stdout)


def library(source, provider):
    body = source.split("emit_model_setup_helper() {", 1)[1]
    body = body.split("cat <<'PY'\n", 1)[1].split("\nPY\n}", 1)[0]
    namespace = {"HARNESS": provider, "__name__": "published_gate"}
    exec(compile(body, "<candidate-model-parser>", "exec"), namespace)
    return namespace


def roles(files, source):
    values = {}
    for implementer, provider in history.MODEL_ROLES.items():
        lib = library(source, provider)
        for role in ("implementer", "reviewer"):
            path = implementer.replace("implementer", role)
            if path in files:
                fields = lib["parse"](files[path][0], role)[1]
                values[path] = (fields.get("model"), fields.get(
                    "model_reasoning_effort" if provider == "codex" else "effort"))
    return values


def role_body(path, data, source):
    """Comparison only: separately assert selections and validate raw attestation."""
    provider = history.provider(path)
    role = "implementer" if "implementer" in Path(path).name else "reviewer"
    parsed, _fields, _marker = library(source, provider)["parse"](data, role)
    lines, _newline, _insertion, spans = parsed
    selection_lines = {span[0] for span in spans.values()}
    return "".join(line for i, line in enumerate(lines)
                   if i not in selection_lines and not line.startswith(MARKER.decode())).encode()


def check_manifest(path, actual, fresh, old):
    data, mode = actual
    expected = dict(line.split("=", 1) for line in fresh[0].decode().splitlines())
    got = dict(line.split("=", 1) for line in data.decode().splitlines())
    history.normalize(path, data)
    require(mode == fresh[1], f"manifest mode differs: {path}")
    if actual == old:
        # write_provider_manifest only writes when SNAPSHOT_TOUCHED. Require
        # exact old provenance, NOT arbitrary old versions/hashes, and require
        # current inventory. All current bases are checked separately.
        require(got.keys() == expected.keys() and
                all(got[key] == expected[key] for key in ("snapshot_format", "platform", "files")),
                f"retained manifest inventory differs: {path}")
    else:
        require({k: v for k, v in got.items() if k != "installed_at"} ==
                {k: v for k, v in expected.items() if k != "installed_at"},
                f"current manifest differs: {path}")


def compare_contract(root, reference, old, source, policies, *, guest=False):
    actual, fresh = history.snapshot(root), history.snapshot(reference)
    old_choices, new_choices = roles(old, source), roles(actual, source)
    for path, choice in old_choices.items():
        require(new_choices.get(path) == choice, f"model/effort changed: {path}")
    expected_roles = roles(fresh, source)
    for path, choice in expected_roles.items():
        if path not in old_choices:
            require(new_choices.get(path) == choice, f"fresh model/effort wrong: {path}")
    # A fresh reference is authority only for selected current projections and
    # pristine bases, NOT ownership ledgers, retained workflows or backup sets.
    for path, (data, mode) in fresh.items():
        if path.startswith(".git/") or "/.domestique/" in path:
            continue
        require(path in actual, f"missing current projection: {path}")
        got, got_mode = actual[path]
        require(got_mode == mode, f"projection mode differs: {path}")
        if path in policies:
            require(got.startswith(PREFIX) and got.endswith(SUFFIX), f"host text lost: {path}")
            got = got[len(PREFIX):-len(SUFFIX)]
        if path in expected_roles:
            # Validate the unnormalized marker against the physical root and
            # BOTH live hashes before removing it for body comparison.
            if path in history.MODEL_ROLES:
                history.normalize(path, actual[path][0], root, actual)
                require((MARKER in actual[path][0]) == (MARKER in data),
                        f"missing current ownership attestation: {path}")
            got, data = role_body(path, got, source), role_body(path, data, source)
        require(got == data, f"current projection differs: {path}")
    for path, (data, mode) in fresh.items():
        if "/.domestique/base/" in path:
            require(actual.get(path) == (data, mode), f"current pristine base differs: {path}")
        elif path.endswith("/.domestique/manifest"):
            check_manifest(path, actual[path], (data, mode), old.get(path))
        elif path.endswith(("/.domestique/mode", "/.domestique/platforms")):
            require(actual.get(path) == (data, mode), f"current state differs: {path}")
        elif "/.domestique/" in path and not path.endswith("/.domestique/guest-excludes"):
            require(actual.get(path) == (data, mode), f"unclassified state differs: {path}")
    # Every old backup survives exactly. Every new backup must be an actual
    # pre-upgrade file, never a reconstructed/normalized identity.
    for path, value in old.items():
        if ".bak." in path or path == "host.txt":
            require(actual.get(path) == value, f"existing host/backup lost: {path}")
    for path, value in actual.items():
        if ".bak." in path and path not in old:
            original = path.split(".bak.", 1)[0]
            require(old.get(original) == value, f"backup not exact original: {path}")
        if path.startswith(".git/") or path in fresh or path in old or ".bak." in path:
            continue
        raise AssertionError(f"unexpected new file: {path}")
    owned_native = set()
    for state in STATES.values():
        manifest = old.get(state + "/manifest")
        if manifest:
            fields = dict(line.split("=", 1) for line in manifest[0].decode().splitlines())
            owned_native.update(fields["files"].split(","))
    for path, value in old.items():
        if path.startswith(".git/") or ".bak." in path or path in fresh:
            continue
        # Only duplicated provider copies of a CURRENT shared base may retire.
        # A directory-name match alone must not hide lost unknown state/data.
        shared_copy = any(
            path.startswith(state + "/base/.agents/skills/") and
            ".agents/.domestique/base/" + path[len(state + "/base/"):] in fresh
            for state in STATES.values())
        if shared_copy:
            require(path not in actual or actual[path] == value,
                    f"retired shared base changed: {path}")
        elif path in owned_native:
            require(path not in actual, f"retired native projection still live: {path}")
        else:
            require(actual.get(path) == value, f"unclassified old file changed/lost: {path}")
    # Ledger differences encode legitimate ownership provenance (especially
    # historical .beads); no fresh-equality comparison and no identity stripping.
    exclude = actual[".git/info/exclude"][0]
    require(exclude.startswith(b"# release-gate host exclusion\nhost-private.txt\n"),
            "host excludes changed")
    for path, (data, _mode) in actual.items():
        if path.endswith("/.domestique/guest-excludes"):
            lines = data.decode().splitlines()
            require(len(lines) == len(set(lines)), f"duplicate guest ledger entry: {path}")
            for line in lines:
                require(line and (not guest or line.encode() in exclude.splitlines()),
                        f"guest ledger entry lacks exclusion: {path}: {line}")


def execute(case, candidate, released, output, timeout, setup_timeout):
    started = time.monotonic()
    directory = output / case["id"]
    directory.mkdir()
    work = directory / "work"
    work.mkdir()
    env = history.isolated(work)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    root = work / "repo"
    record = dict(case, commands=[], status="FAIL")

    def command(label, argv, cwd=root, budget=timeout, expected=0):
        begin = time.monotonic()
        result = history.run(argv, cwd=cwd, env=env, timeout=budget)
        evidence = dict(label=label, argv=list(map(str, argv)), cwd=str(cwd),
                        budget_seconds=budget, seconds=time.monotonic() - begin,
                        expected_returncode=expected, **result)
        record["commands"].append(evidence)
        write_json(directory / f"command-{len(record['commands']):03d}.json", evidence)
        require(not result["timeout"], f"{label}: timeout/inconclusive")
        require(result["returncode"] == expected,
                f"{label}: expected {expected}, got {result['returncode']}; "
                f"{result['stderr'][-3000:]}")
        return result

    def install(label, script, selector, target=root, preview=False):
        args = [] if selector == "default" else ["--platform", selector]
        if case["mode"] == "guest":
            args.append("--guest")
        if preview:
            args.append("--dry-run")
        return command(label, ["bash", str(script), *args], cwd=target)

    def status(target=root):
        return command("git-status", ["git", "--no-optional-locks", "status",
                                      "--porcelain=v1", "--untracked-files=all"],
                       cwd=target, budget=setup_timeout)["stdout"]

    try:
        command("setup", ["git", "init", "-q", "--template=" + str(work / "template")],
                budget=setup_timeout)
        (root / ".git/info").mkdir(exist_ok=True)
        (root / ".git/info/exclude").write_bytes(
            b"# release-gate host exclusion\nhost-private.txt\n")
        (root / "host.txt").write_bytes(b"unrelated user bytes\n")
        command("stage-host", ["git", "add", "host.txt"], budget=setup_timeout)
        install("released-install", released / "domestique.sh", case["install"])
        policies = [p for p in history.POLICIES if (root / p).is_file()]
        for path in policies:
            target = root / path
            target.write_bytes(PREFIX + target.read_bytes() + SUFFIX)
            Path(str(target) + ".bak.20000101000000").write_bytes(b"older user backup\n")
        old = history.snapshot(root)
        before_status = status()
        before = tree(root)
        write_json(directory / "before.json", before)
        install("preview", candidate / "domestique.sh", case["upgrade"], preview=True)
        unchanged(before, tree(root), "preview bytes/modes/mtimes/index/excludes")
        require(status() == before_status, "preview changed Git status")
        install("apply", candidate / "domestique.sh", case["upgrade"])
        require((root / ".git/index").read_bytes() == old[".git/index"][0], "apply changed index")
        after = tree(root, mtimes=False)
        write_json(directory / "after.json", after)
        after_status = status()
        install("rerun", candidate / "domestique.sh", case["upgrade"])
        unchanged(after, tree(root, mtimes=False), "rerun bytes/modes/no new backups")
        require(status() == after_status, "rerun changed Git status")
        reference = work / "reference"
        reference.mkdir()
        command("reference-setup", ["git", "init", "-q", "--template=" + str(work / "template")],
                cwd=reference, budget=setup_timeout)
        install("current-reference", candidate / "domestique.sh", case["upgrade"], reference)
        compare_contract(root, reference, old, (candidate / "domestique.sh").read_text(), policies,
                         guest=case["mode"] == "guest")
        if case["mode"] == "guest":
            current = history.snapshot(reference)
            for path in current:
                if path.startswith(".git/") or "/.domestique/" in path:
                    continue
                command("guest-hidden", ["git", "check-ignore", "-q", "--", path],
                        budget=setup_timeout)
        record["status"] = "PASS"
    except Exception as exc:
        record["failure"] = f"{type(exc).__name__}: {exc}"
    finally:
        isolation_errors = []
        if (work / "dependency.log").exists():
            isolation_errors.append((work / "dependency.log").read_text())
        for name in ("home", "config", "cache", "data", "state"):
            if history.snapshot(work / name):
                isolation_errors.append(f"unexpected {name} writes")
        if isolation_errors:
            record.update(status="FAIL", isolation_errors=isolation_errors)
        record["seconds"] = time.monotonic() - started
        write_json(directory / "result.json", record)
    return record


def positive(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be positive and finite")
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", default="HEAD")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--filter", action="append", default=[],
                        help="case ID substring; repeat for union of impacted cases")
    parser.add_argument("--workers", type=int, choices=(1, 2), default=2)
    parser.add_argument("--timeout", type=positive, default=900, help="seconds per installer attempt")
    parser.add_argument("--setup-timeout", type=positive, default=120)
    args = parser.parse_args()
    cases = [case for case in plan() if not args.filter or
             any(value in case["id"] for value in args.filter)]
    if not cases:
        parser.error("filter selected no cases")
    revision = history.git("rev-parse", args.revision + "^{commit}").strip()
    manifest = dict(revision=revision, cases=cases, count=len(cases), workers=args.workers,
                    installer_timeout=args.timeout, setup_timeout=args.setup_timeout,
                    harness_sha256=history.sha(Path(__file__).read_bytes()),
                    isolation_sha256=history.sha((REPO / "tools/historical-identities.py").read_bytes()),
                    scope="10 published tags; single providers plus default/all; no native qualification")
    print(json.dumps(manifest, indent=2), flush=True)
    if args.list:
        return 0
    if args.output is None:
        parser.error("--output is required for execution (must not already exist)")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "plan.json", manifest)  # Before any installer execution.
    with (output / "executed-harness.py").open("xb") as stream:
        stream.write(Path(__file__).read_bytes())
    sources = output / "sources"
    sources.mkdir()
    revisions = {revision} | {case["revision"] for case in cases}
    try:
        archives = {ref: export(ref, sources / ref) for ref in sorted(revisions)}
    except Exception as exc:
        write_json(output / "setup-failure.json",
                   dict(status="FAIL", failure=f"{type(exc).__name__}: {exc}"))
        raise
    write_json(output / "sources.json", archives)
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(execute, case, sources / revision, sources / case["revision"],
                               output, args.timeout, args.setup_timeout) for case in cases]
        records = []
        for future in futures:
            record = future.result()
            records.append(record)
            print(f"{record['status']} {record['id']} {record['seconds']:.1f}s "
                  f"{record.get('failure', '')}", flush=True)
    summary = dict(count=len(records), passed=sum(r["status"] == "PASS" for r in records),
                   failed=sum(r["status"] != "PASS" for r in records),
                   seconds=time.monotonic() - started,
                   results={r["id"]: history.sha((output / r["id"] / "result.json").read_bytes())
                            for r in records})
    write_json(output / "summary.json", summary)
    print(json.dumps(summary, indent=2), flush=True)
    return int(summary["failed"] != 0)


if __name__ == "__main__":
    sys.exit(main())
