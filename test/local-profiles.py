"""Current private local CLI, editable native metadata and executable routing.

All hashes/pins/test fingerprints are in memory. Native trust is a prompt
obligation tested as such, never simulated as native discovery success.
"""
import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parent.parent
DOM = ROOT / "domestique.sh"
UP = ROOT / "update.sh"
COUNT = 0


def check(condition, label):
    global COUNT
    assert condition, label
    COUNT += 1


def run(*args, cwd=None, ok=True, env=None):
    result = subprocess.run([str(a) for a in args], cwd=cwd or W,
                            env=env or ENV, capture_output=True, text=True)
    if ok:
        check(result.returncode == 0, (args, result.stderr, result.stdout))
    return result


def install(repo, *args, ok=True):
    return run("bash", DOM, "--local", repo, *args, ok=ok)


def tree(root):
    # Tests fingerprint in memory only; the product never snapshots live data.
    result = []
    for p in sorted(root.rglob("*")):
        stat = p.lstat()
        data = os.readlink(p) if p.is_symlink() else p.read_bytes() if p.is_file() else None
        result.append((str(p.relative_to(root)), stat.st_mode,
                       stat.st_mtime_ns if p.is_file() else None, data))
    return result


def repo(name):
    p = W / name
    p.mkdir()
    run("git", "init", "-q", p)
    return p


def refuse(*args, roots=(), cwd=None, env=None):
    before = [tree(p) for p in roots]
    result = run(*args, cwd=cwd, env=env, ok=False)
    check(result.returncode != 0, ("expected refusal", args, result.stdout))
    check(before == [tree(p) for p in roots], ("refusal wrote files", args))
    check("SECRET" not in result.stdout + result.stderr, "no secret diagnostics")
    return result


def route(p, provider, role, intent="default", pin=None, ok=True):
    args = ["bash", CORE / "bin/resolve-core", "route", CORE, p, provider,
            role, RELEASE, intent]
    if pin is not None:
        args.append(pin)
    return run(*args, ok=ok)


def native(p, provider, role):
    prefix, ext = {"claude": (".claude", "md"), "codex": (".codex", "toml"),
                   "copilot": (".github", "agent.md")}[provider]
    return p / prefix / "agents" / f"domestique-{provider}-local-{role}.{ext}"


def body(p, codex=False):
    text = p.read_text()
    return tomllib.loads(text)["developer_instructions"] if codex else text


def fences(text):
    blocks = re.findall(r"^```bash\n(.*?)^```$", text, re.M | re.S)
    check(len(blocks) == 2, "two executable core/routing fences")
    return blocks


with tempfile.TemporaryDirectory() as temp:
    W = Path(temp).resolve()
    HOME = W / "home"
    HOME.mkdir()
    CORE = W / "core"
    tmp = W / "tmp"
    tmp.mkdir()
    forbidden = W / "forbidden"
    forbidden.mkdir()
    for cmd in ("curl", "wget", "bd", "claude", "codex", "copilot"):
        f = forbidden / cmd
        f.write_text("#!/bin/bash\nprintf 'FORBIDDEN-CALL\\n' >&2\nexit 99\n")
        f.chmod(0o700)
    ENV = dict(os.environ, HOME=str(HOME), DOMESTIQUE_HOME=str(CORE),
               TMPDIR=str(tmp), PATH=f"{forbidden}:{os.environ['PATH']}",
               PYTHONDONTWRITEBYTECODE="1")
    ENV.pop("XDG_STATE_HOME", None)
    empty = repo("global-only")
    untouched = tree(empty)
    run("bash", DOM, "--global", "--platform", "all")
    check(tree(empty) == untouched, "global install zero local writes")
    RELEASE = (CORE / "active").read_text().strip().split("=")[1]
    global_before = tree(CORE), tree(HOME)
    for provider in ("claude", "codex", "copilot"):
        for role in ("implementer", "reviewer"):
            check(route(empty, provider, role).stdout.strip() ==
                  f"global-only:domestique-{provider}-{role}", "zero-local default")
            check(route(empty, provider, role, "local-required", ok=False).returncode != 0,
                  "explicit local cannot fall back")
            ext = {"claude": "md", "codex": "toml", "copilot": "agent.md"}[provider]
            agent = HOME / f".{provider}" / "agents" / f"domestique-{provider}-{role}.{ext}"
            text = body(agent, provider == "codex")
            load, recheck = fences(text)
            run("bash", "-c", load, "--", RELEASE, cwd=empty)
            run("bash", "-c", recheck, "--", RELEASE, f"global-only:domestique-{provider}-{role}", cwd=empty)
            check(not re.search(r"^model\s*[:=]", agent.read_text(), re.M), "no installed model pins")
    check(tree(empty) == untouched, "runtime zero local writes")

    # Missing working copies must not erase index-only local evidence. Include
    # deleted symlink/gitlink ancestors of native, receipt and manifest paths.
    indexed_paths = (
        ".codex/agents/domestique-codex-local-reviewer.toml",
        ".codex/agents", ".codex",
        ".domestique-private/routing/codex.receipt",
        ".domestique-private/routing", ".domestique-private/manifest",
        ".domestique-private",
    )
    for mode in ("100644", "120000", "160000"):
        for rel in indexed_paths:
            p = repo(f"index-only-{mode}-{indexed_paths.index(rel)}")
            if mode == "160000":
                # A real local commit object, no remote or submodule client.
                run("git", "-C", p, "-c", "user.name=Test",
                    "-c", "user.email=test@example.invalid", "commit",
                    "--allow-empty", "-qm", "fixture")
                oid = run("git", "-C", p, "rev-parse", "HEAD").stdout.strip()
            else:
                leaf = p / rel
                leaf.parent.mkdir(parents=True, exist_ok=True)
                if mode == "120000":
                    leaf.symlink_to(W / "absent-index-target")
                else:
                    leaf.write_text("indexed local evidence\n")
                run("git", "-C", p, "add", "--", f":(literal){rel}")
                oid = run("git", "-C", p, "rev-parse", f":{rel}").stdout.strip()
                leaf.unlink()
                # Reproduce absence of the whole private/provider tree too.
                parent = leaf.parent
                while parent != p:
                    parent.rmdir()
                    parent = parent.parent
            run("git", "-C", p, "update-index", "--add", "--cacheinfo",
                f"{mode},{oid},{rel}")
            result = refuse("bash", CORE / "bin/resolve-core", "route",
                            CORE, p, "codex", "reviewer", RELEASE, "default",
                            roots=(p, CORE, HOME))
            check("tracked/indexed" in result.stderr, "indexed evidence diagnostic")
            check(route(p, "codex", "reviewer", "global-only").stdout.strip() ==
                  "global-only:domestique-codex-reviewer", "deliberate index bypass")
            refuse("bash", DOM, "--local", p, "--platform", "codex",
                   roots=(p, CORE, HOME))

    host = repo("unrelated-indexed-host")
    for rel in (".codex/agents/host[reviewer]*.toml", ".codex/settings.toml"):
        leaf = host / rel
        leaf.parent.mkdir(parents=True, exist_ok=True)
        leaf.write_text("unrelated host content\n")
        run("git", "-C", host, "add", "--", f":(literal){rel}")
    check(route(host, "codex", "reviewer").stdout.strip() ==
          "global-only:domestique-codex-reviewer", "tracked host siblings are not local evidence")

    # All seven provider sets, actual private path/inventory and no-op/dry-run.
    sets = {"claude": ["claude"], "codex": ["codex"], "copilot": ["copilot"],
            "both": ["claude", "codex"], "claude-copilot": ["claude", "copilot"],
            "codex-copilot": ["codex", "copilot"], "all": ["claude", "codex", "copilot"]}
    projects = {}
    for selection, providers in sets.items():
        p = projects[selection] = repo(selection)
        before = tree(p)
        install(p, "--platform", selection, "--dry-run")
        check(tree(p) == before, "dry-run zero writes")
        install(p, "--platform", selection)
        expected = {str(native(p, prov, role).relative_to(p))
                    for prov in providers for role in ("implementer", "reviewer")}
        actual = {str(f.relative_to(p)) for f in p.rglob("*") if f.is_file()
                  and not str(f.relative_to(p)).startswith((".git/", ".domestique-private/"))}
        check(actual == expected, ("only native roles", actual, expected))
        for leaf in expected:
            run("git", "-C", p, "check-ignore", "-q", leaf)
        check(run("git", "-C", p, "status", "--porcelain").stdout == "", "private status")
        before = tree(p)
        run("bash", DOM, cwd=p)  # bare must preserve provider union
        check(tree(p) == before, "idempotence includes file mtimes")
    check((tree(CORE), tree(HOME)) == global_before, "local never writes global")
    p = projects["claude"]
    install(p, "--platform", "codex-copilot")
    check("providers=all\n" in (p / ".domestique-private/manifest").read_text(),
          "additive union")
    fresh = repo("default")
    run("bash", DOM, fresh, "--guest")
    check(native(fresh, "claude", "reviewer").exists(), "positional default Claude")
    check(not (fresh / "CLAUDE.local.md").exists(), "guest is no-op")
    v3 = W / "native-refresh.sh"
    v3.write_text(DOM.read_text().replace(
        "description: Provider-qualified Domestique $scope $role adapter.",
        "description: Provider-qualified Domestique $scope $role refreshed adapter."))
    old_records = (fresh / ".domestique-private/manifest").read_text().splitlines()
    run("bash", v3, "--local", fresh)
    new_records = (fresh / ".domestique-private/manifest").read_text().splitlines()
    check([x for x in old_records if x.startswith("created=")] ==
          [x for x in new_records if x.startswith("created=")], "refresh retains original creation provenance")
    check([x for x in old_records if x.startswith("baseline=")] !=
          [x for x in new_records if x.startswith("baseline=")], "refresh updates generated baselines")
    before = tree(fresh)
    run("bash", v3, fresh)
    check(tree(fresh) == before, "refreshed native no-op")

    historical = W / "historical.sh"
    historical.write_text(run("git", "-C", ROOT, "show", "b60feef:domestique.sh").stdout)
    migrate = repo("explicit-migration")
    run("bash", historical, "--platform", "codex", "--guest", migrate)
    install(migrate, "--platform", "codex")
    check(not (migrate / ".codex/agents/implementer.toml").exists() and
          native(migrate, "codex", "implementer").exists(), "public setup migrates positive unchanged legacy")
    check((migrate / ".codex/.domestique/guest-excludes").exists(), "migration retains legacy provenance")
    oldhome, oldcore = W / "old-home", W / "old-core"
    oldhome.mkdir()
    oldenv = dict(ENV, HOME=str(oldhome), DOMESTIQUE_HOME=str(oldcore))
    run("bash", historical, "--global", env=oldenv)
    oldtarget = repo("old-helper")
    result = refuse("bash", DOM, "--local", oldtarget, roots=(oldhome, oldcore, oldtarget), env=oldenv)
    check("bash domestique.sh --global" in result.stderr, "owned old helper actionable compatibility refusal")

    # Valid retained none and valid single-role records, not a new public flag.
    none = repo("none")
    state = none / ".domestique-private"
    state.mkdir()
    (state / "manifest").write_text(
        f"format=1\nscope=local\nworktree_root={none}\ncore_root={CORE}\ncore_api=1\nproviders=none\n")
    before = tree(none)
    run("bash", DOM, cwd=none)
    check(tree(none) == before, "none bare creates nothing")
    single = projects["copilot"]
    manifest = single / ".domestique-private/manifest"
    manifest.write_text("".join(line for line in manifest.read_text().splitlines(True)
                                if "-reviewer." not in line))
    receipt = single / ".domestique-private/routing/copilot.receipt"
    receipt.write_text(receipt.read_text().replace("role=domestique-copilot-local-reviewer\n", ""))
    native(single, "copilot", "reviewer").unlink()
    check(route(single, "copilot", "reviewer").stdout.startswith("global-only:"),
          "valid single-role other role global")
    check(route(single, "copilot", "implementer").stdout.startswith("local-required:"),
          "valid single role local")
    missing = native(single, "copilot", "reviewer")
    missing.write_text("indexed missing role\n")
    run("git", "-C", single, "add", "-f", "--", f":(literal){missing.relative_to(single)}")
    missing.unlink()
    check(route(single, "copilot", "reviewer", ok=False).returncode != 0,
          "other-role receipt cannot mask requested index-only evidence")
    run("git", "-C", single, "rm", "--cached", "-q", "--",
        f":(literal){missing.relative_to(single)}")
    check(route(single, "copilot", "reviewer").stdout.startswith("global-only:"),
          "other-role receipt still permits absent unindexed role")

    # Two projects with different native tool/MCP metadata. No universal parser.
    edited = [projects["all"], p]
    pins = {}
    for n, project in enumerate(edited):
        for provider in ("claude", "codex", "copilot"):
            path = native(project, provider, "implementer")
            text = path.read_text()
            if provider == "codex":
                text += f'\n[mcp_servers.project{n}]\nurl = "https://example.invalid/SECRET{n}"\nenabled_tools = ["lookup{n}"]\n'
            else:
                key = "mcpServers" if provider == "claude" else "mcp-servers"
                text = text.replace("\n---\n\n", f'\n{key}:\n  project{n}:\n    url: https://example.invalid/SECRET{n}\n---\n\n', 1)
                if provider == "claude":
                    text = text.replace("tools: Read, Write, Edit, Bash, Glob, Grep",
                                        f"tools: Read, Bash, Glob, Grep, mcp__project{n}__lookup")
                else:
                    text = text.replace('tools: ["read", "search", "execute", "edit"]',
                                        f'tools: ["read", "search", "execute", "project{n}/lookup"]')
            path.write_text(text)
            pins[project, provider] = route(project, provider, "implementer").stdout.strip()
            check(pins[project, provider].startswith("local-required:"), "edited metadata routes")
        refuse("bash", DOM, "--local", project, "--force", roots=(project, CORE, HOME))
        refuse("bash", DOM, "--local", project, "--dry-run", roots=(project, CORE, HOME))
        check(not any(f.suffix in (".new", ".bak") for f in project.rglob("*")), "no live backups")
        check(not any(b"SECRET" in f.read_bytes() for f in (project / ".domestique-private").rglob("*")
                      if f.is_file()), "no secret in private metadata")

    # A genuine global source update retains edited local metadata and old release.
    v2 = W / "v2.sh"
    v2.write_text(DOM.read_text().replace("# Domestique private core: reviewer",
                                        "# Domestique private core: reviewer v2"))
    local_before = [tree(p) for p in edited]
    run("bash", v2, "--global", "--platform", "all")
    check([tree(p) for p in edited] == local_before, "global update preserves both projects")
    check((CORE / "active").read_text().strip() != f"release={RELEASE}", "new release really active")

    # Execute the emitted fences, including parsed Codex developer_instructions.
    for provider in ("claude", "codex", "copilot"):
        project = edited[0]
        skillroot = ".agents" if provider == "codex" else "." + provider
        skill = HOME / skillroot / "skills" / f"domestique-{provider}" / "SKILL.md"
        for suffix in ("", "-decompose", "-goal"):
            skill = HOME / skillroot / "skills" / f"domestique-{provider}{suffix}" / "SKILL.md"
            coreblock, mapblock = fences(body(skill))
            run("bash", "-c", coreblock, "--", RELEASE, cwd=project)
            mapped = run("bash", "-c", mapblock, "--", RELEASE, cwd=project)
            mapping = dict(line.split("=", 1) for line in mapped.stdout.splitlines())
            for role in ("implementer", "reviewer"):
                token = mapping[f"DOMESTIQUE_ROUTE_{role}"]
                path = native(project, provider, role)
                text = body(path, provider == "codex")
                load, recheck = fences(text)
                run("bash", "-c", load, "--", RELEASE, cwd=project)
                run("bash", "-c", recheck, "--", RELEASE, token, cwd=project)
                check(run("bash", "-c", recheck, "--", RELEASE, cwd=project, ok=False).returncode != 0,
                      "delegate missing route pin stops")
                check("MUST independently confirm through native" in text and
                      "If any cannot be confirmed STOP" in text, "untrusted native prompt stop")
                check("full\nprompt forks are user-maintained" in text, "fork upgrade limitation")
            run("bash", "-c", mapblock, "--", RELEASE, "default", "default",
                mapping["DOMESTIQUE_ROUTE_implementer"], mapping["DOMESTIQUE_ROUTE_reviewer"], cwd=project)

    project = edited[0]
    pin = pins[project, "codex"]
    path = native(project, "codex", "implementer")
    original = path.read_bytes()
    path.write_bytes(original + b"\n# changed after binding\n")
    check(route(project, "codex", "implementer", pin=pin, ok=False).returncode != 0,
          "changed bound role stops")
    path.unlink()
    check(route(project, "codex", "implementer", pin=pin, ok=False).returncode != 0,
          "removed bound role stops")
    path.write_bytes(original)
    receipt = project / ".domestique-private/routing/codex.receipt"
    original = receipt.read_bytes()
    receipt.unlink()
    check(route(project, "codex", "implementer", pin=pin, ok=False).returncode != 0,
          "removed bound receipt stops")
    check(route(project, "codex", "implementer", "global-only").stdout.startswith("global-only:"),
          "explicit deliberate global only")
    receipt.write_bytes(original)
    for bad in (original + b"\0", original.replace(b"core_api=1", b"core_api=2"),
                original.replace(b"provider=codex", b"provider=claude")):
        receipt.write_bytes(bad)
        check(route(project, "codex", "reviewer", ok=False).returncode != 0, "bad receipt stops")
    receipt.write_bytes(original)
    manifest = project / ".domestique-private/manifest"
    original = manifest.read_bytes()
    for bad in (original + b"\0", original.replace(b".codex/agents/", b"../agents/")):
        manifest.write_bytes(bad)
        check(route(project, "codex", "reviewer", ok=False).returncode != 0, "bad manifest stops")
    manifest.write_bytes(original)
    path = native(project, "codex", "reviewer")
    path.chmod(0o400)
    route(project, "codex", "reviewer")  # readable is enough at runtime
    path.chmod(0o000)
    check(route(project, "codex", "reviewer", ok=False).returncode != 0, "unreadable native role stops")
    path.chmod(0o600)
    run("git", "-C", project, "add", "-f", str(path))
    check(route(project, "codex", "reviewer", ok=False).returncode != 0, "indexed runtime role stops")
    run("git", "-C", project, "rm", "--cached", "-q", str(path))
    receipt.rename(receipt.with_suffix(".saved"))
    receipt.symlink_to(receipt.with_suffix(".saved"))
    check(route(project, "codex", "reviewer", ok=False).returncode != 0, "symlink receipt stops")
    receipt.unlink()
    receipt.with_suffix(".saved").rename(receipt)

    # Missing/old helper and incompatible core never install globally implicitly.
    target = repo("missing-core")
    helper = CORE / "bin/resolve-core"
    helper_bytes = helper.read_bytes()
    helper.unlink()
    refuse("bash", DOM, "--local", target, roots=(target, CORE, HOME))
    helper.write_bytes(b"#!/bin/bash\nexit 0\n")
    refuse("bash", DOM, "--local", target, roots=(target, CORE, HOME))
    helper.write_bytes(helper_bytes)
    api = CORE / "releases" / RELEASE / "API"
    data = api.read_bytes()
    api.write_bytes(data.replace(b"core_api=1", b"core_api=2"))
    check(route(project, "codex", "reviewer", ok=False).returncode != 0, "incompatible required release")
    api.write_bytes(data)

    # CLI usage failures before even consulting a nonexistent fetch source.
    for script in (DOM, UP):
        extra = ["--source", str(W / "never-fetch")] if script == UP else []
        for args in (["--global", "--local", target], ["--global", target],
                     ["--local"], ["--local", target, target], ["--platform="],
                     ["--platform", "unknown"], ["--model", "x"], ["--tools", "x"],
                     ["--mcp", "x"], [""], ["--no-guest"], ["--with-beads"],
                     ["--state-only"], ["--uninstall"], ["--purge-beads"]):
            result = refuse("bash", script, *args, *extra, roots=(target, CORE, HOME))
            check(result.returncode == 2 and "source =" not in result.stdout, "usage before fetch")
    for args in (["--source="], ["--source", "--dry-run"], ["--source", ""]):
        result = refuse("bash", UP, *args, roots=(target, CORE, HOME))
        check(result.returncode == 2 and "source =" not in result.stdout, "malformed source before fetch")
    # Updater forwards explicit target and provider set; failed preview no apply.
    update_repo = repo("updater")
    run("bash", UP, "--local", update_repo, "--platform", "codex-copilot", "--source", DOM)
    check("providers=codex-copilot" in (update_repo / ".domestique-private/manifest").read_text(),
          "updater scope and set forwarded")
    before = tree(update_repo)
    run("bash", UP, update_repo, "--source", DOM, "--dry-run")
    check(tree(update_repo) == before, "updater dry-run no apply")
    fake = W / "preview-fails.sh"
    fake.write_text('#!/bin/bash\ncase " $* " in *" --dry-run "*) printf "PREVIEW-TRIGGERED\\n"; exit 7;; esac\nprintf "APPLY-TRIGGERED\\n"; exit 98\n')
    for scope in (["--local", update_repo], ["--global"]):
        result = run("bash", UP, *scope, "--source", fake, ok=False)
        check(result.returncode == 7 and "PREVIEW-TRIGGERED" in result.stdout and
              "APPLY-TRIGGERED" not in result.stdout, "failed preview never applies")

    # Real publication failure: intercept the current generated-leaf writer,
    # and require the marker so a primitive change cannot silently skip it.
    injected = W / "injected"
    injected.mkdir()
    shim = injected / "cat"
    shim.write_text('''#!/bin/bash
case "$1" in */.claude/agents/domestique-claude-local-implementer.md)
  printf "PUBLICATION-INJECTION-TRIGGERED\\n" >&2; exit 87;;
esac
exec /bin/cat "$@"
''')
    shim.chmod(0o700)
    failed = repo("partial")
    result = run("bash", DOM, "--local", failed, ok=False,
                 env=dict(ENV, PATH=f"{injected}:{ENV['PATH']}"))
    check(result.returncode != 0 and "PUBLICATION-INJECTION-TRIGGERED" in result.stderr and
          "PARTIAL" in result.stderr, "failure injection actually triggered")
    check((failed / ".domestique-private/pending").exists(), "retained pending recovery")
    check((failed / ".domestique-private/published").read_text() == "format=1\n",
          "failed writer has no positive creation record")
    refuse("bash", DOM, "--local", failed, roots=(failed, CORE, HOME))
    check(route(failed, "claude", "implementer", ok=False).returncode != 0,
          "partial publication cannot become global fallback")

    # DEBUG runs BEFORE redirection (a cat wrapper runs too late). Instrument
    # the real CLI's exact publication commands without changing the source.
    # Trigger assertions below make changed/unreached commands a test failure.
    hook = W / "publication-debug.sh"
    hook.write_text('''set -T
trap 'case "$BASH_COMMAND" in
  '\\''cat "$source" > "$dest"'\\''|'\\''mv "$source" "${dest%/*}"'\\'')
    if [ "${dest:-}" = "$COLLISION_PATH" ] && [ ! -e "$COLLISION_TRIGGER" ]; then
      COLLISION_SOURCE="$source" python3 "$COLLISION_INJECTOR"
    fi;;
esac' DEBUG
''')
    injector = W / "collision.py"
    injector.write_text('''import os
from pathlib import Path
p = Path(os.environ["COLLISION_PATH"])
kind = os.environ["COLLISION_KIND"]
if kind == "wrong-bytes":
    # Command will succeed, but publish bytes different from the digest it
    # just validated. Only generated staging is modified, never copied live.
    Path(os.environ["COLLISION_SOURCE"]).write_text("GENERATED-INJECTION\\n")
elif p.exists() or p.is_symlink():
    p.unlink()
if kind == "directory":
    p.mkdir()
elif kind == "file":
    p.write_text("UNKNOWN-COLLISION\\n")
elif kind == "dangling":
    p.symlink_to(Path(os.environ["COLLISION_OUTSIDE"]) / "absent")
elif kind == "symlink-directory":
    p.symlink_to(os.environ["COLLISION_OUTSIDE"])
Path(os.environ["COLLISION_TRIGGER"]).write_text(kind)
print("COLLISION-TRIGGERED", flush=True)
''')
    protected = [CORE, HOME, *edited]
    protected_before = [tree(p) for p in protected]
    for phase in ("new-native", "new-receipt", "new-manifest",
                  "refresh-native", "refresh-receipt", "refresh-manifest"):
        # Regular-file replacement is deliberately not concurrency-exclusive.
        # Test directory refusal for refresh, all unknown types for creation.
        kinds = ("directory", "wrong-bytes") if phase.startswith("refresh") else (
            "directory", "file", "dangling", "symlink-directory", "wrong-bytes")
        for kind in kinds:
            p = repo(f"collision-{phase}-{kind}")
            if phase.startswith("refresh"):
                install(p)
            collision = (native(p, "claude", "implementer") if phase.endswith("native")
                         else p / ".domestique-private" /
                         ("routing/claude.receipt" if phase.endswith("receipt") else "manifest"))
            sibling = native(p, "claude", "reviewer")
            sibling_before = sibling.read_bytes() if sibling.exists() else None
            outside = W / f"outside-{phase}-{kind}"
            outside.mkdir()
            (outside / "protected").write_text("SECRET-PROTECTED\n")
            outside_before = tree(outside)
            trigger = W / f"trigger-{phase}-{kind}"
            result = run("/bin/bash", v3 if phase.startswith("refresh") else DOM,
                         "--local", p, ok=False,
                         env=dict(ENV, BASH_ENV=str(hook), COLLISION_PATH=str(collision),
                                  COLLISION_KIND=kind, COLLISION_TRIGGER=str(trigger),
                                  COLLISION_INJECTOR=str(injector), COLLISION_OUTSIDE=str(outside)))
            check(trigger.is_file() and trigger.read_text() == kind and
                  "COLLISION-TRIGGERED" in result.stdout, "collision actually triggered")
            check(result.returncode != 0 and "PARTIAL" in result.stderr and
                  "installed providers=" not in result.stdout, "collision is not published success")
            state = p / ".domestique-private"
            check((state / "pending").is_file(), "collision retains prospective metadata")
            log = (state / "published").read_text()
            if phase.endswith("native"):
                check(log == "format=1\n", "no false created/refreshed exact-leaf record")
                check((sibling.read_bytes() if sibling.exists() else None) == sibling_before,
                      "failed first native publication leaves other role unchanged")
            if kind == "directory":
                check(collision.is_dir() and not list(collision.iterdir()), "no nested staged file")
            elif kind == "file":
                check(collision.read_text() == "UNKNOWN-COLLISION\n", "unknown file not overwritten/adopted")
            elif kind == "wrong-bytes":
                check(collision.read_text() == "GENERATED-INJECTION\n" and
                      "unverified published leaf:" in result.stderr,
                      "successful command with wrong generated bytes never recorded")
            else:
                check(collision.is_symlink(), "unknown symlink not replaced")
            check(tree(outside) == outside_before, "no dangling/symlink escape")
            check([tree(root) for root in protected] == protected_before,
                  "old bound projects/home/core unchanged")
            check(not any(b"SECRET" in f.read_bytes() for f in state.rglob("*")
                          if f.is_file() and not f.is_symlink()), "recovery contains no live secrets")
            refuse("bash", DOM, "--local", p, roots=(p, CORE, HOME))
            check(route(p, "claude", "implementer", ok=False).returncode != 0,
                  "wrong/partial manifest never usable")
    check(not any(p.name == "__pycache__" for p in ROOT.rglob("__pycache__")),
          "no bytecode junk")

print(f"local-profiles current production: {COUNT} passed")
