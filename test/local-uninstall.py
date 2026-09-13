"""Current profile-only removal, real linked Git worktrees, isolated HOME.

All live-byte fingerprints are test-only/in-memory. No clients or Beads probes.
Faults modify a private copy of the self-contained installer, with mandatory
trigger evidence so primitive changes cannot silently disable coverage.
"""
import ast
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
DOM = ROOT / "domestique.sh"
SETS = {"claude": {"claude"}, "codex": {"codex"}, "copilot": {"copilot"},
        "both": {"claude", "codex"}, "claude-copilot": {"claude", "copilot"},
        "codex-copilot": {"codex", "copilot"}, "all": {"claude", "codex", "copilot"}}
COUNT = 0


def check(value, label):
    global COUNT
    assert value, label
    COUNT += 1


def snapshot(root):
    h = hashlib.sha256()
    for p in [root, *sorted(root.rglob("*"))]:
        if not p.exists() and not p.is_symlink():
            h.update(b"absent")
            continue
        s = p.lstat()
        h.update(repr((str(p.relative_to(root)), s.st_mode)).encode())
        if p.is_symlink():
            h.update(os.readlink(p).encode())
        elif p.is_file():
            h.update(str(s.st_mtime_ns).encode())
            try:
                h.update(p.read_bytes())
            except PermissionError:
                h.update(b"unreadable")
    return h.hexdigest()


def run(*args, cwd=None, env=None):
    return subprocess.run([str(a) for a in args], cwd=cwd or W, env=env or ENV,
                          capture_output=True, text=True)


def success(*args, **kwargs):
    p = run(*args, **kwargs)
    check(p.returncode == 0, (args, p.returncode, p.stdout, p.stderr))
    return p


def repo(name, selection="all"):
    p = W / name
    p.mkdir()
    success("git", "init", "-q", p)
    if selection:
        success("/bin/bash", DOM, "--local", p, "--platform", selection)
    return p


def remove(p, *args, status=0, script=None, spelling="explicit", **kwargs):
    scope = ["--local", p] if spelling == "explicit" else [p] if spelling == "positional" else []
    result = run("/bin/bash", script or DOM, "--uninstall", *scope, *args,
                 cwd=p if spelling == "bare" else W, **kwargs)
    check(result.returncode == status,
          (p.name, args, result.returncode, result.stdout, result.stderr))
    check("SECRET" not in result.stdout + result.stderr, "no secret diagnostics")
    check(not list(p.rglob(".domestique-local-recovery.*")), "no Git-metadata recovery sidecars")
    return result


def refuse(p, *args, status=1, reason=None, **kwargs):
    before = snapshot(W)
    result = remove(p, *args, status=status, **kwargs)
    check(snapshot(W) == before, ("preflight wrote", result.stderr))
    if reason:
        check(reason in result.stderr, ("wrong refusal phase", reason, result.stderr))
    return result


def native(p, provider, role="implementer"):
    prefix, ext = {"claude": (".claude", "md"), "codex": (".codex", "toml"),
                   "copilot": (".github", "agent.md")}[provider]
    return p / prefix / "agents" / f"domestique-{provider}-local-{role}.{ext}"


def records(p):
    lines = (p / ".domestique-private/manifest").read_text().splitlines()
    return {line.removeprefix("created=").rsplit(":", 1)[0]:
            (line, lines[i + 1]) for i, line in enumerate(lines) if line.startswith("created=")}


def ignored(p, path):
    result = run("git", "-C", p, "check-ignore", "-q", "--", path)
    check(result.returncode in (0, 1), "check-ignore operational")
    return result.returncode == 0


def retained_none(p, original):
    state = p / ".domestique-private"
    expected = "\n".join(original.splitlines()[:5]) + "\nproviders=none\n"
    check((state / "manifest").read_text() == expected, "exact format-1 none identity, zero native records")
    check({f.relative_to(state).as_posix() for f in state.rglob("*")} == {"manifest", "routing"},
          "only retained manifest and existing empty routing container; no receipts/journals")
    check(ignored(p, ".domestique-private/manifest") and ignored(p, ".domestique-private/pending"),
          "retained attachment and possible pending remain privately excluded")
    check(all(not native(p, provider, role).exists() for provider in SETS["all"]
              for role in ("implementer", "reviewer")), "no remaining adapters")


def fault_script(name, anchor, insertion, after=True):
    source = DOM.read_text()
    start = source.index("local_uninstall() (")
    end = source.index("\nlocal_install() (", start)
    body = source[start:end]
    check(body.count(anchor) == 1, ("unique actual fault anchor", name, anchor))
    fault = '\n  printf "triggered\\n" > "$FAULT_MARK"\n' + insertion + "\n"
    body = body.replace(anchor, anchor + fault if after else fault + anchor)
    script = W / f"fault-{name}.sh"
    script.write_text(source[:start] + body + source[end:])
    return script


W = Path(tempfile.mkdtemp(prefix="domestique-local-remove-")).resolve()
try:
    # Bash keeps a byte offset into its script while a long operation runs.
    # Freeze the exact current source so concurrent development cannot splice
    # a later parser/dispatch block into an already-running test invocation.
    source = DOM.read_bytes()
    DOM = W / "domestique.sh"
    DOM.write_bytes(source)
    HOME, CORE, LOG = W / "home", W / "core", W / "forbidden-log"
    for name in ("home", "tmp", "forbidden"):
        (W / name).mkdir()
    for command in ("bd", "claude", "codex", "copilot", "curl", "wget"):
        f = W / "forbidden" / command
        f.write_text('#!/bin/bash\nprintf "called\\n" >> "$FORBIDDEN_LOG"\nexit 99\n')
        f.chmod(0o700)
    ENV = dict(os.environ, HOME=str(HOME), DOMESTIQUE_HOME=str(CORE),
               TMPDIR=str(W / "tmp"), FORBIDDEN_LOG=str(LOG),
               PYTHONDONTWRITEBYTECODE="1", PATH=f"{W / 'forbidden'}:{os.environ['PATH']}")
    ENV.pop("XDG_STATE_HOME", None)
    success("/bin/bash", DOM, "--global", "--platform", "all")
    global_before = snapshot(CORE), snapshot(HOME)

    # All seven installed unions: selectorless read-only dry-run, positional
    # and bare compatibility, absent selector no-op, last-profile reinstall.
    for n, (selection, providers) in enumerate(SETS.items()):
        p = repo(f"union-{selection}", selection)
        owned = records(p)
        original = (p / ".domestique-private/manifest").read_text()
        if selection != "all":
            absent = next(iter(SETS["all"] - providers))
            before = snapshot(p)
            remove(p, "--platform", absent)
            check(snapshot(p) == before, "absent selector no-op")
        before = snapshot(W)
        result = remove(p, "--dry-run", "--force")
        check("would remove" in result.stdout and snapshot(W) == before,
              "read-only preview and complete tree identity")
        if selection == "claude":
            leaves = [f for f in p.rglob("*") if f.is_file() and ".git" not in f.parts]
            for f in leaves:
                f.chmod(0o400)
            before = snapshot(W)
            remove(p, "--dry-run")
            check(snapshot(W) == before, "genuinely read-only native/state preview")
            for f in leaves:
                f.chmod(0o600)
        result = remove(p, "--guest", spelling="bare" if n % 2 else "positional")
        check("profiles removed; private attachment metadata retained" in result.stdout,
              "complete removal reports retained attachment")
        check(all(not (p / key.split(":", 1)[1]).exists() for key in owned),
              "every exact native removed")
        retained_none(p, original)
        before = snapshot(W)
        result = remove(p)
        check("no owned local profiles" in result.stdout and snapshot(W) == before,
              "repeated none removal is a metadata-identical no-op")
        result = success("/bin/bash", DOM, "--local", p)
        check("providers=none retained; no adapters created" in result.stdout and snapshot(W) == before,
              "bare none install is a metadata-identical no-op")
        success("/bin/bash", DOM, "--local", p, "--platform", selection)
        check(set(key.split(":")[0] for key in records(p)) == providers,
              "explicit reinstall reuses retained attachment without manual rmdir")
        remove(p)
        retained_none(p, original)

    # Every subset from all; unrelated host settings, native forks, Beads
    # database and its prior visibility survive without inspection/adoption.
    for selection, removing in SETS.items():
        p = repo(f"subset-{selection}")
        before_records = records(p)
        original = (p / ".domestique-private/manifest").read_text()
        host = p / ".codex/settings.toml"
        host.write_text("SECRET-HOST-MCP\n")
        fork = p / ".claude/agents/my-own-profile.md"
        fork.write_text("SECRET-HOST-TOOLS\n")
        beads = p / ".beads"
        beads.mkdir()
        (beads / "database").write_bytes(b"\x00SECRET-DATABASE\xff")
        policies = [p / "AGENTS.md", p / ".claude/settings.json",
                    p / ".github/copilot-instructions.md"]
        for policy in policies:
            policy.write_text("SECRET-HOST-POLICY\n")
        success("git", "-C", p, "add", "--", "AGENTS.md")
        policies.append(p / ".git/index")
        # Test both previously visible and independently hidden host databases.
        if selection in ("claude", "all"):
            with (p / ".git/info/exclude").open("a") as f:
                f.write("/.beads/\n")
        visibility = ignored(p, ".beads/database")
        protected = [snapshot(x) for x in (host, fork, beads, *policies)]
        kept = {key: snapshot(p / key.split(":", 1)[1]) for key in before_records
                if key.split(":")[0] not in removing}
        remove(p, "--platform", selection)
        check([snapshot(x) for x in (host, fork, beads, *policies)] == protected,
              "host policies/native config/Beads/index bytes and times unchanged")
        check(ignored(p, ".beads/database") == visibility, "host Beads prior visibility unchanged")
        for key in before_records:
            path = p / key.split(":", 1)[1]
            if key in kept:
                check(snapshot(path) == kept[key], "unselected native identity")
                check(records(p)[key] == before_records[key], "original provenance retained")
                check(ignored(p, path.relative_to(p)), "remaining exact native private")
            else:
                check(not path.exists(), "selected native deleted")
                check(not ignored(p, path.relative_to(p)), "removed native rule removed")
        if selection == "all":
            retained_none(p, original)

    # Customized native MCP/tools are valid runtime metadata but whole-provider
    # retention, including force/dry-run; unrelated edited profiles do not block.
    for provider in SETS["all"]:
        p = repo(f"edited-{provider}")
        victim = native(p, provider, "reviewer")
        original = victim.read_text()
        if provider == "codex":
            edited = original + '\n[mcp_servers.local_test]\ncommand = "SECRET-CUSTOM-NATIVE-MCP"\n'
        elif provider == "claude":
            edited = original.replace("tools: ", "tools: SECRET-CUSTOM-NATIVE-MCP, ", 1)
        else:
            edited = original.replace("tools: [", 'tools: ["SECRET-CUSTOM-NATIVE-MCP", ', 1)
        check(edited != original, "native metadata customization actually applied")
        victim.write_text(edited)
        old = records(p)
        keep = {f: snapshot(f) for f in (native(p, provider), victim,
                p / f".domestique-private/routing/{provider}.receipt")}
        refuse(p, "--platform", provider, "--force", "--dry-run", reason="retain WHOLE")
        refuse(p, "--platform", provider, "--force", reason="retain WHOLE")
        remove(p, "--force", status=1)
        check(all(snapshot(f) == h for f, h in keep.items()), "whole customized provider retained")
        check(records(p) == {k: v for k, v in old.items() if k.split(":")[0] == provider},
              "never rehash edited content into saved ownership")
        copies = [f for f in p.rglob("*") if f.is_file() and b"SECRET-CUSTOM" in f.read_bytes()]
        check(copies == [victim], "secret exists only at original native leaf")
        other = next(iter(SETS["all"] - {provider}))
        # A fresh different repo proves selected clean removal succeeds with an
        # unselected edited role, rather than reporting the selected edit case.
        q = repo(f"unselected-edited-{provider}")
        native(q, provider).write_text("SECRET-DIFFERENT-PROFILE\n")
        remove(q, "--platform", other)
        check(native(q, provider).read_text() == "SECRET-DIFFERENT-PROFILE\n",
              "unselected edited role preserved")

    check((snapshot(CORE), snapshot(HOME)) == global_before,
          "all positive subset/retention removals preserve present global/HOME bytes and times")
    # Global assets are neither required nor read for authorization.
    for kind in ("missing", "incompatible", "other-root"):
        p = repo(f"core-{kind}", "codex")
        env = dict(ENV)
        if kind == "missing":
            CORE.rename(W / "saved-core")
            before = snapshot(W / "saved-core"), snapshot(HOME)
        elif kind == "incompatible":
            helper = CORE / "bin/resolve-core"
            original = helper.read_bytes()
            helper.write_text('SECRET-INCOMPATIBLE-HELPER\n')
            before = snapshot(CORE), snapshot(HOME)
        else:
            env["DOMESTIQUE_HOME"] = str(W / "absent-other-core")
            before = snapshot(CORE), snapshot(HOME)
        remove(p, env=env)
        check((snapshot(W / "saved-core" if kind == "missing" else CORE), snapshot(HOME)) == before,
              "missing/incompatible/ambient core independent and untouched")
        if kind == "missing":
            before_none = snapshot(W)
            result = remove(p, env=env)
            check("no owned local profiles" in result.stdout and snapshot(W) == before_none,
                  "none removal does not require missing global core")
            reinstall = run("/bin/bash", DOM, "--local", p, "--platform", "codex", env=env)
            check(reinstall.returncode != 0 and "invalid required global core" in reinstall.stderr and
                  snapshot(W) == before_none, "explicit none reinstall requires compatible core without writes")
            (W / "saved-core").rename(CORE)
        elif kind == "incompatible":
            helper.write_bytes(original)
    # Helper fixture restoration changes its mtime, not product writes.
    global_before = snapshot(CORE), snapshot(HOME)

    pristine = repo("pristine-native-source", "codex")
    pristine_codex = native(pristine, "codex").read_bytes()
    # Literal index objects and ancestors, tracked-now, symlinks, NUL,
    # corrupt/duplicate/unknown state, legacy authority and missing receipts.
    for kind in ("tracked", "index-ancestor", "symlink", "manifest-nul", "native-nul",
                 "duplicate", "unknown-state", "pending", "beads-field", "receipt",
                 "unknown-native", "policy", "marker", "unknown-exclude", "missing-exclude"):
        p = repo(f"refuse-{kind}", "claude")
        state = p / ".domestique-private"
        victim = native(p, "claude")
        manifest = state / "manifest"
        if kind == "tracked":
            success("git", "-C", p, "add", "-f", "--", f":(literal){victim.relative_to(p)}")
        elif kind == "index-ancestor":
            blob = success("git", "-C", p, "hash-object", "-w", victim).stdout.strip()
            success("git", "-C", p, "update-index", "--add", "--cacheinfo", f"120000,{blob},.claude")
        elif kind == "symlink":
            victim.unlink()
            victim.symlink_to(W / "unknown")
        elif kind in ("manifest-nul", "native-nul"):
            f = manifest if kind == "manifest-nul" else victim
            f.write_bytes(f.read_bytes() + b"\x00\n")
        elif kind == "duplicate":
            manifest.write_text(manifest.read_text() + "\n".join(next(iter(records(p).values()))) + "\n")
        elif kind == "unknown-state":
            (state / "unknown").write_text("SECRET-UNKNOWN-RECOVERY\n")
        elif kind == "pending":
            (state / "pending").write_text("format=unknown\n")
        elif kind == "beads-field":
            manifest.write_text(manifest.read_text() + "beads=owned\n")
        elif kind == "receipt":
            (state / "routing/claude.receipt").unlink()
        elif kind == "unknown-native":
            f = native(p, "codex")
            f.parent.mkdir(parents=True)
            # Byte identity is not ownership.
            f.write_bytes(pristine_codex)
        elif kind == "policy":
            (p / "CLAUDE.md").write_text("<!-- BEGIN domestique (managed) -->\nSECRET-POLICY\n<!-- END domestique (managed) -->\n")
        elif kind == "marker":
            (p / "CLAUDE.local.md").write_text("<!-- BEGIN domestique unknown -->\n")
        elif kind == "unknown-exclude":
            f = p / ".git/info/exclude"
            f.write_text(f.read_text().replace("# END domestique private", "/unknown-host/\n# END domestique private"))
        elif kind == "missing-exclude":
            f = p / ".git/info/exclude"
            f.write_text(f.read_text().replace("/.domestique-private/\n", ""))
        refuse(p, "--force")
        refuse(p, "--dry-run")

    # Strict physical target, genuine no ownership, no-profile state, and
    # CLI conflicts remain read-only and never become a legacy engine call.
    empty = repo("empty", None)
    refuse(empty, reason="no owned local profiles")
    legacy = repo("legacy-only", None)
    old_role = legacy / ".claude/agents/implementer.md"
    old_role.parent.mkdir(parents=True)
    old_role.write_text("SECRET-LEGACY-ONLY\n")
    refuse(legacy, "--force", reason="active legacy")
    extra = repo("extra-canonical-receipt")
    (extra / ".domestique-private/routing/unknown.receipt").write_text(
        f"format=1\nworktree_root={extra}\nprovider=unknown\ncore_root={CORE}\ncore_api=1\n")
    refuse(extra, reason="unknown private removal entry")
    sub = empty / "sub"
    sub.mkdir()
    refuse(sub, reason="not the exact Git top-level")
    alias = W / "alias"
    alias.symlink_to(empty, target_is_directory=True)
    refuse(alias, reason="symlink component")
    refuse(empty, "--purge-beads", reason="no owned local profiles")
    for args in (("--with-beads",), ("--state-only",),
                 ("--no-guest",), ("--global",), ("--platform", "none")):
        refuse(empty, *args, status=2)
    state = empty / ".domestique-private"
    state.mkdir()
    refuse(empty, reason="missing local manifest")
    before = snapshot(W)
    result = run("/bin/bash", DOM, "--local", empty, "--platform", "claude")
    check(result.returncode != 0 and "missing local manifest" in result.stderr and snapshot(W) == before,
          "unknown preexisting private root is never adopted")
    (state / "manifest").write_text(
        f"format=1\nscope=local\nworktree_root={empty}\ncore_root={CORE}\ncore_api=1\nproviders=none\n")
    refuse(empty, reason="missing exact shared exclusion provenance")

    # Actual linked worktrees: exact shared native rule remains for its other
    # owner, unrelated host paths stay visible. Both last-profile removals
    # independently retain valid none attachments and their shared private rule.
    main = repo("linked-main")
    success("git", "-C", main, "-c", "user.name=Test", "-c",
            "user.email=test@example.invalid", "commit", "--allow-empty", "-qm", "fixture")
    linked = W / "linked-other"
    success("git", "-C", main, "worktree", "add", "-q", "-b", "other", linked)
    success("/bin/bash", DOM, "--local", linked, "--platform", "all")
    other_before = snapshot(linked)
    remove(main, "--platform", "claude")
    check(snapshot(linked) == other_before, "linked native/state identity")
    rel = native(main, "claude").relative_to(main)
    check(ignored(linked, rel) and ignored(main, rel), "common rule retained for actual other owner")
    protected = [main / ".domestique-private", native(main, "codex"), native(main, "copilot")]
    protected_before = [snapshot(f) for f in protected]
    # The target is NOT first in worktree enumeration. Its private rule must
    # deduplicate against the earlier main worktree, not corrupt the union.
    remove(linked, "--platform", "codex")
    check([snapshot(f) for f in protected] == protected_before, "linked-target removal preserves main attachment")
    exclude = main / ".git/info/exclude"
    check(exclude.read_text().splitlines().count("/.domestique-private/") == 1,
          "one common private rule even when removal target enumerates later")
    check(ignored(main, native(main, "codex").relative_to(main)) and
          ignored(linked, native(linked, "codex").relative_to(linked)),
          "earlier main owner keeps its exact shared leaf exclusion")
    before = snapshot(W)
    success("/bin/bash", DOM, "--local", linked)
    check(snapshot(W) == before, "scoped linked removal leaves valid idempotent installation state")
    host = main / ".claude/agents/unrelated.md"
    host.write_text("SECRET-HOST\n")
    check(not ignored(main, host.relative_to(main)), "host sibling visible")
    collision = native(main, "claude")
    collision.write_text("SECRET-SAME-PATH-HOST\n")
    refuse(main, "--platform", "codex", reason="shared exclude would hide host destination")
    collision.unlink()
    (linked / ".domestique-private/unknown").write_text("SECRET-OTHER-STATE\n")
    refuse(main, "--platform", "codex", reason="unknown private state")
    (linked / ".domestique-private/unknown").unlink()
    linked_manifest = linked / ".domestique-private/manifest"
    linked_manifest_bytes = linked_manifest.read_bytes()
    linked_manifest.chmod(0)
    refuse(main, "--platform", "codex", reason="path")
    linked_manifest.chmod(0o600)
    check(linked_manifest.read_bytes() == linked_manifest_bytes, "unreadable linked metadata bytes preserved")
    main_manifest = (main / ".domestique-private/manifest").read_text()
    other_before = snapshot(linked)
    remove(main)
    retained_none(main, main_manifest)
    check(snapshot(linked) == other_before, "main last-profile removal preserves linked attachment")
    expected_patterns = {"/.domestique-private/"} | {"/" + key.split(":", 1)[1] for key in records(linked)}
    check({line for line in exclude.read_text().splitlines() if line.startswith("/")} == expected_patterns,
          "only other worktree native roles and retained private rule remain")
    main_before = snapshot(main / ".domestique-private"), snapshot(host)
    remove(linked)
    retained_none(linked, linked_manifest_bytes.decode())
    check((snapshot(main / ".domestique-private"), snapshot(host)) == main_before,
          "linked last-profile removal preserves main none attachment and host")
    check([line for line in exclude.read_text().splitlines() if line.startswith("/")] ==
          ["/.domestique-private/"], "no native rules after both worktrees reach none")
    for target in (main, linked):
        before = snapshot(W)
        remove(target)
        success("/bin/bash", DOM, "--local", target)
        check(snapshot(W) == before, "linked none uninstall/bare install are read-only")
        success("/bin/bash", DOM, "--local", target, "--platform", "claude")
        remove(target)
    check(not ignored(main, host.relative_to(main)), "host sibling stays visible after both last removals")

    # Transaction faults: actual unlink failure, late tracked/reappeared leaf,
    # retained role/receipt/manifest changes before commit and EACH cleanup.
    before_manifest = '  local_remove_validate || exit 1\n  if [ "$PURGE_BEADS" = 1 ]; then'
    cases = {
        "unlink-failure": ('  local_remove_new "$U_STATE/pending" "$plan" &&\n    local_remove_new "$U_STATE/published" "" || exit 1',
                           '  unlink() {\n    if [ "$i" = 1 ]; then\n'
                           '      printf "unlink-called\\n" > "$FAULT_UNLINK"\n'
                           '      return 73\n    fi\n    command unlink "$@"\n  }', True),
        "reappear": ('    unlink "${remove_paths[i]}" || exit 1',
                     '  if [ "$i" = 0 ]; then printf "SECRET-REAPPEARED\\n" > "${remove_paths[i]}"; fi', True),
        "tracked-late": ('    unlink "${remove_paths[i]}" || exit 1',
                         '  if [ "$i" = 0 ]; then git -C "$L_ROOT" add -f -- .claude/agents/domestique-claude-local-reviewer.md; fi', True),
        "manifest": (before_manifest,
                     '  printf "SECRET-MANIFEST\\n" >> "$U_STATE/manifest"', False),
        "retained-role": (before_manifest,
                          '  printf "SECRET-RETAINED\\n" >> "$L_ROOT/.codex/agents/domestique-codex-local-reviewer.toml"', False),
        "receipt": (before_manifest,
                    '  printf "SECRET-RECEIPT\\n" >> "$U_STATE/routing/codex.receipt"', False),
        "published": ('  local_remove_check "$U_STATE/published" "$U_LOG_HASH" "$L_ROOT" || exit 1\n  unlink "$U_STATE/published" || exit 1',
                      '  printf "SECRET-JOURNAL\\n" >> "$U_STATE/published"', False),
        "pending": ('  unlink "$U_STATE/published" || exit 1',
                    '  printf "SECRET-JOURNAL\\n" >> "$U_STATE/pending"', True),
        "pending-type": ('  unlink "$U_STATE/published" || exit 1',
                         '  unlink "$U_STATE/pending"\n  mkdir "$U_STATE/pending"\n'
                         '  printf "SECRET-UNKNOWN-TYPE\\n" > "$U_STATE/pending/host"', True),
        "manifest-type": (before_manifest,
                          '  unlink "$U_STATE/manifest"\n  mkdir "$U_STATE/manifest"\n'
                          '  printf "SECRET-UNKNOWN-TYPE\\n" > "$U_STATE/manifest/host"', False),
        "cleanup-retained": ('  unlink "$U_STATE/published" || exit 1',
                             '  printf "SECRET-RETAINED\\n" >> "$L_ROOT/.codex/agents/domestique-codex-local-reviewer.toml"', True),
        "last-pending": ('  U_LOG_HASH=absent',
                         '  printf "SECRET-REAPPEARED\\n" > "$U_STATE/manifest"', True),
        "exclude": ('  local_remove_exclude "$final_exclude" || exit 1',
                    '  printf "# host changed\\n" >> "$L_EXCLUDE"', False),
        "ignore-policy": (before_manifest,
                          '  printf "!/.codex/agents/domestique-codex-local-reviewer.toml\\n" > "$L_ROOT/.gitignore"', False),
    }
    for name, (anchor, insertion, after) in cases.items():
        p = repo(f"fault-project-{name}")
        script = fault_script(name, anchor, insertion, after)
        mark = W / f"trigger-{name}"
        unlink_mark = W / f"unlink-trigger-{name}"
        env = dict(ENV, FAULT_MARK=str(mark), FAULT_UNLINK=str(unlink_mark))
        state = p / ".domestique-private"
        secret_path = None
        secret_expected = None
        if name in ("retained-role", "cleanup-retained"):
            secret_path = native(p, "codex", "reviewer")
            secret_expected = secret_path.read_bytes() + b"SECRET-RETAINED\n"
        elif name == "receipt":
            secret_path = state / "routing/codex.receipt"
            secret_expected = secret_path.read_bytes() + b"SECRET-RECEIPT\n"
        elif name == "manifest":
            secret_path = state / "manifest"
            secret_expected = secret_path.read_bytes() + b"SECRET-MANIFEST\n"
        elif name in ("pending", "published"):
            secret_path = state / name
        elif name in ("pending-type", "manifest-type"):
            secret_path = state / name.removesuffix("-type") / "host"
            secret_expected = b"SECRET-UNKNOWN-TYPE\n"
        elif name in ("reappear", "last-pending"):
            secret_path = native(p, "claude") if name == "reappear" else state / "manifest"
            secret_expected = b"SECRET-REAPPEARED\n"
        result = run("/bin/bash", script, "--uninstall", "--local", p,
                     "--platform", "all" if name == "last-pending" else "claude", env=env)
        check(mark.is_file() and mark.read_text() == "triggered\n", ("fault actually triggered", name))
        check(result.returncode != 0 and "PARTIAL removal" in result.stderr,
              ("fault is partial, not successful/preflight", name, result.stderr))
        if name == "ignore-policy":
            check((p / ".gitignore").read_bytes() ==
                  b"!/.codex/agents/domestique-codex-local-reviewer.toml\n" and
                  "exclusion" in result.stderr, "late conflicting host ignore policy preserved, not rewritten")
        check("SECRET" not in result.stderr + result.stdout, "fault diagnostics hash-only")
        state = p / ".domestique-private"
        check((state / "pending").exists(), ("pending evidence preserved/reestablished", name))
        published = state / "published"
        if published.exists():
            completed = [line.split("=", 1)[1].rsplit(":", 1)[0]
                         for line in published.read_text().splitlines() if line.startswith("removed=")]
            if name == "unlink-failure":
                check(unlink_mark.is_file() and unlink_mark.read_text() == "unlink-called\n",
                      "actual unlink command failure injected")
                check(completed == [str(native(p, "claude").relative_to(p))],
                      "journal contains only actual completed first unlink")
                check(native(p, "claude", "reviewer").is_file(), "failed unlink retained next leaf")
            if name == "reappear":
                check(completed == [str(native(p, "claude").relative_to(p))] and
                      native(p, "claude").read_text() == "SECRET-REAPPEARED\n",
                      "actual unlink recorded despite protected reappearance")
            if name == "tracked-late":
                check(len(completed) == 1 and native(p, "claude", "reviewer").is_file(),
                      "late indexed next path refused before unlink")
        check(ignored(p, ".domestique-private/pending"), "recovery remains private")
        before = snapshot(p)
        rerun = run("/bin/bash", DOM, "--local", p)
        check(rerun.returncode != 0 and snapshot(p) == before, "install rerun fails closed")
        refuse(p)
        release = (CORE / "active").read_text().strip().split("=")[1]
        routed = run("/bin/bash", CORE / "bin/resolve-core", "route", CORE, p,
                     "claude", "implementer", release, "default")
        check(routed.returncode != 0 and not routed.stdout.startswith("global-only:"),
              "pending absent-local-evidence never defaults global")
        secrets = [f for f in p.rglob("*") if f.is_file() and b"SECRET-" in f.read_bytes()]
        check(secrets == ([] if secret_path is None else [secret_path]),
              ("protected secret remains only at its injected exact leaf", name, secrets))
        if secret_expected is not None:
            check(secret_path.read_bytes() == secret_expected, ("protected complete bytes", name))
        elif secret_path is not None:
            check(secret_path.read_bytes().endswith(b"SECRET-JOURNAL\n"), "changed journal bytes preserved")

    # Exercise the real last exclusion publication AND the final risky boundary
    # (published gone, original pending still present, final validation ahead).
    last_exclude = '  local_remove_exclude "$final_exclude" || exit 1'
    last_risk = '  U_LOG_HASH=absent'
    for name in ("last-exclusion", "pending-boundary", "retained-boundary",
                 "foreign-state", "corrupt-shared", "pending-policy", "linked-pending",
                 "destroyed-exclusion", "pending-unlink"):
        p = repo(f"late-{name}")
        state = p / ".domestique-private"
        manifest_before = (state / "manifest").read_bytes()
        exclude = p / ".git/info/exclude"
        host_rules = "/host-hidden\n/.beads/\n"
        with exclude.open("a") as f:
            f.write(host_rules)
        host = p / ".codex/settings.toml"
        host.write_text("SECRET-HOST-SETTINGS\n")
        beads = p / ".beads"
        beads.mkdir()
        (beads / "database").write_bytes(b"SECRET-HOST-DATABASE\x00")
        (p / "host-hidden").write_text("SECRET-HIDDEN-HOST\n")
        (p / "tracked-host").write_text("SECRET-INDEX-HOST\n")
        success("git", "-C", p, "add", "--", "tracked-host")
        linked = None
        if name == "linked-pending":
            success("git", "-C", p, "-c", "user.name=Test", "-c",
                    "user.email=test@example.invalid", "commit", "-qm", "fixture")
            linked = W / "late-linked-other"
            success("git", "-C", p, "worktree", "add", "-q", "-b", "late-other", linked)
        protected = [host, beads, p / "host-hidden", p / "tracked-host", p / ".git/index"]
        if name == "retained-boundary":
            protected += [native(p, provider, role) for provider in ("codex", "copilot")
                          for role in ("implementer", "reviewer")]
            protected += [state / f"routing/{provider}.receipt" for provider in ("codex", "copilot")]
        protected_before = [snapshot(f) for f in protected]
        anchor = last_exclude if name == "last-exclusion" else last_risk
        insertion = '  printf "SECRET-LATE-MANIFEST\\n" >> "$U_STATE/manifest"'
        if name == "foreign-state":
            insertion += '\n  printf "SECRET-FOREIGN-STATE\\n" > "$U_STATE/unknown"'
        elif name == "corrupt-shared":
            insertion += '\n  printf "# BEGIN domestique broken\\n" >> "$L_EXCLUDE"'
        elif name == "pending-policy":
            insertion += '\n  printf "!/.domestique-private/pending\\n" > "$L_ROOT/.gitignore"'
        elif name == "linked-pending":
            insertion += ('\n  mkdir "$FAULT_LINKED/.domestique-private"\n'
                          '  printf "SECRET-FOREIGN-PENDING\\n" > "$FAULT_LINKED/.domestique-private/pending"')
        elif name == "destroyed-exclusion":
            insertion += '\n  printf "/host-hidden\\n/.beads/\\n# SECRET-FOREIGN-RULES\\n" > "$L_EXCLUDE"'
        elif name == "pending-unlink":
            insertion = ('  unlink() {\n'
                         '    printf "unlink-called\\n" > "$FAULT_UNLINK"\n'
                         '    return 73\n  }')
        insertion = ('  [ -f "$U_STATE/pending" ] &&\n'
                     '    [ "$(global_hash < "$U_STATE/pending")" = "$U_PENDING_HASH" ] &&\n'
                     '    git -C "$L_ROOT" check-ignore -q -- .domestique-private/pending || exit 91\n'
                     '  printf "protected-original\\n" > "$FAULT_PRIVATE"\n') + insertion
        script = fault_script(name, anchor, insertion)
        mark = W / f"trigger-late-{name}"
        private_mark = W / f"private-late-{name}"
        unlink_mark = W / f"unlink-late-{name}"
        env = dict(ENV, FAULT_MARK=str(mark), FAULT_LINKED=str(linked or ""),
                   FAULT_PRIVATE=str(private_mark), FAULT_UNLINK=str(unlink_mark))
        result = remove(p, "--platform", "claude" if name == "retained-boundary" else "all",
                        script=script, status=1, env=env)
        check(mark.is_file() and mark.read_text() == "triggered\n", ("actual late boundary triggered", name))
        check(private_mark.is_file() and private_mark.read_text() == "protected-original\n",
              ("original pending still protected AT actual boundary", name))
        check("PARTIAL removal" in result.stderr and "profiles removed;" not in result.stdout,
              ("late failure never reports completion", name))
        expected = b"\n".join(manifest_before.split(b"\n")[:5]) + b"\nproviders=none\n"
        if name == "retained-boundary":
            expected = b"\n".join(line for line in manifest_before.split(b"\n")
                                  if not line.startswith((b"created=claude:", b"baseline=claude:")))
            expected = expected.replace(b"providers=all\n", b"providers=codex-copilot\n")
        if name != "pending-unlink":
            expected += b"SECRET-LATE-MANIFEST\n"
        else:
            check(unlink_mark.is_file() and unlink_mark.read_text() == "unlink-called\n",
                  "actual final pending unlink failure triggered")
        check((state / "manifest").read_bytes() == expected, ("late changed manifest intact", name))
        check([snapshot(f) for f in protected] == protected_before,
              ("host/Beads/index/remaining providers unchanged", name))
        check(not list((p / ".git").rglob(".domestique-local-recovery.*")),
              "no local recovery sidecars anywhere in Git metadata")
        pending = (state / "pending").read_bytes()
        oldhash = hashlib.sha256(manifest_before).hexdigest().encode()
        remaining = expected.removesuffix(b"SECRET-LATE-MANIFEST\n")
        expected_pending = (b"format=1\noperation=local-uninstall\nprevious=" + oldhash +
                            b"\nremaining=" + hashlib.sha256(remaining).hexdigest().encode() +
                            b"\n" + manifest_before)
        for line in manifest_before.splitlines():
            if line.startswith(b"baseline="):
                provider, path_hash = line.removeprefix(b"baseline=").split(b":", 1)
                if name == "retained-boundary" and provider != b"claude":
                    continue
                expected_pending += b"remove=" + path_hash + b"\n"
                if b"-reviewer." in path_hash:
                    receipt = (f"format=1\nworktree_root={p}\nprovider={provider.decode()}\n"
                               f"core_root={CORE}\ncore_api=1\n"
                               f"role=domestique-{provider.decode()}-local-implementer\n"
                               f"role=domestique-{provider.decode()}-local-reviewer\n").encode()
                    expected_pending += (b"remove=.domestique-private/routing/" + provider +
                                         b".receipt:" + hashlib.sha256(receipt).hexdigest().encode() + b"\n")
        check(pending == expected_pending and b"SECRET" not in pending,
              "exact original in-root intent retained, never replaced by edited content")
        check(ignored(p, ".domestique-private/pending") == (name != "destroyed-exclusion"),
              "pending remains private unless outside writer destroys original exclusion")
        status = success("git", "-C", p, "status", "--porcelain", "--untracked-files=all").stdout
        check((".domestique-private/pending" not in status) == (name != "destroyed-exclusion") and
              ".domestique-local-recovery." not in status, "actual Git status matches bounded privacy")
        check(ignored(p, ".beads/database") and ignored(p, "host-hidden") and
              not ignored(p, ".codex/settings.toml"), "original host visibility unchanged")
        rules = exclude.read_text()
        check(host_rules in rules, "unknown exact host exclude rules unchanged")
        if name == "corrupt-shared":
            check(rules.endswith("# BEGIN domestique broken\n"),
                  "corrupt shared exclude not clobbered by recovery")
        elif name == "destroyed-exclusion":
            check(rules == host_rules + "# SECRET-FOREIGN-RULES\n",
                  "outside-writer exclusion destruction is not repaired or clobbered")
        elif name == "pending-policy":
            check((p / ".gitignore").read_bytes() == b"!/.domestique-private/pending\n",
                  "late conflicting ignore policy unchanged")
        elif name == "linked-pending":
            check((linked / ".domestique-private/pending").read_bytes() == b"SECRET-FOREIGN-PENDING\n" and
                  ignored(linked, ".domestique-private/pending"),
                  "late foreign journal unchanged under preexisting shared rule, not adopted")
        if name != "destroyed-exclusion":
            check(rules.splitlines().count("/.domestique-private/") == 1 and
                  ignored(p, ".domestique-private/manifest"),
                  "original private exclusion retained, never removed or recreated")
        if name == "foreign-state":
            check((state / "unknown").read_bytes() == b"SECRET-FOREIGN-STATE\n" and
                  ignored(p, ".domestique-private/unknown"), "late unknown metadata intact under original rule")

    removal_source = DOM.read_text().split("local_remove_check() {", 1)[1].split("\nlocal_install() (", 1)[0]
    check(".domestique-local-recovery." not in removal_source and "mktemp" not in removal_source,
          "actual removal contains no temporary sidecar creation, even on successful paths")
    check(not list(W.rglob(".domestique-local-recovery.*")), "no Git recovery sidecars in any fixture")
    check((snapshot(CORE), snapshot(HOME)) == global_before, "all local operations zero global/HOME writes")
    check(not LOG.exists(), "zero bd/native/network calls")
    ast.parse(Path(__file__).read_text())
    print(f"local-uninstall: {COUNT} checks passed (current source; isolated; no clients)")
finally:
    # Fixture cleanup only: exact observed leaves, no broad recursive deletion.
    for p in sorted(W.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if p.is_symlink() or not p.is_dir():
            p.unlink()
        else:
            p.rmdir()
    W.rmdir()
