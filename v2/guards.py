"""Internal Appendix C helper. No public loaders, delegation, native or Beads calls."""
import os
from pathlib import Path
import stat
import sys
from .safe import Refusal, need, physical, read, sha, re
from .package import PROVIDERS
from .project_records import (STATE, binding_bytes, binding_read, native_inventory,
                              patterns, receipt_read, role_id, role_leaf, skill_ids)
from .project_identity import project_identity, identity_guard, index_untracked
from .project_preflight import (state_read, native_boundaries, exclusions_plan,
                                no_project_pending, ignore_preflight)
from .guard_core import (core_index, helper_provenance, template_inventory,
                         guarded_body_read, release_validate)
from .admission import admit


class ActivationGuard:
    def __init__(self, root, target, provider):
        need(provider in PROVIDERS, "provider")
        self.i, self.watch = project_identity(target, invocation=True)
        self.worktree, self.root = Path(self.i["worktree_root"]), physical(root)
        self.provider = provider
        # Authenticate the project before even inspecting candidate execution data.
        self.providers, exclusions = state_read(self.i, self.root, self.watch)
        need(provider in self.providers and self.providers[provider]["status"] == "enabled",
             "activation absent/disabled")
        self.block = self.providers[provider]
        native_boundaries(self.i, self.providers, (provider,), self.watch)
        self.index, self.core = core_index(self.root, self.watch)
        t = self.block["template_release"]
        helper_provenance(self.root, t, self.index, self.watch)
        templates = template_inventory(self.root, t, provider, self.index, self.watch)
        self.adapters = {}
        for leaf, template in templates.items():
            need(self.block["baseline"][leaf] == (sha(template), "0644"), "pristine T baseline")
            snap = self.watch.paths[self.worktree / leaf]
            need(snap is not None and snap[1] is not None, "missing native leaf")
            admit(provider, leaf, snap[1], template)
            self.adapters[leaf] = (sha(snap[1]), f"{stat.S_IMODE(snap[0][3]):04o}")
        self.receipt = receipt_read(
            read(self.worktree / STATE / "routing" / (provider + ".receipt"), mode=0o600),
            self.i, self.root, provider, self.block)
        exclusion = exclusions_plan(self.i, patterns((provider,)), exclusions, self.watch)
        need(exclusion["action"] is None and exclusion["records"] == exclusions,
             "missing/stale exclusions")
        ignore_preflight(self.i, patterns((provider,)), self.watch)
        self.check()

    def check(self):
        # This is before EVERY shared-body open and immediately before output.
        no_project_pending(self.worktree, self.watch)
        identity_guard(self.i, self.watch)
        index_untracked(self.i, [STATE, *native_inventory(self.provider)])
        self.watch.check()
        no_project_pending(self.worktree, self.watch)

    def helper(self, release, executing=None):
        path, data = helper_provenance(self.root, release, self.index, self.watch)
        if executing is not None:
            need(str(path) == executing, "wrong release helper")
        self.check()
        return path, data

    def match(self, binding):
        need(binding["i"] == self.i and binding["root"] == str(self.root) and
             binding["provider"] == self.provider and binding["core"] == self.core and
             binding["gen"] == self.block["generation"] and binding["receipt"] == self.receipt
             and binding["adapters"] == self.adapters, "stale/foreign binding")
        self.check()


def sample_active(guard):
    """The only selector read. Subsequent checks compare this witness, not select."""
    guard.check()
    snap = guard.watch.add(guard.root / "active")
    need(snap is not None and snap[1] is not None and
         stat.S_IMODE(snap[0][3]) == 0o600 and
         re.fullmatch(rb"release=r-[0-9a-f]{64}\n", snap[1]), "invalid active")
    selected = snap[1][8:-1].decode()
    need(selected in guard.index, "unlisted active")
    return selected


def guarded_start(root, target, provider, entry, executing=None):
    need(entry in skill_ids(provider), "entry skill")
    guard = ActivationGuard(root, target, provider)
    # Loader verifies T before exec; helper checks that the executing path is T.
    guard.helper(guard.block["template_release"], executing)
    selected = sample_active(guard)
    guard.helper(selected)
    bodies = release_validate(guard.root, selected, guard.index, guard.watch, guard.check)
    result = binding_bytes(guard.i, guard.root, provider, guard.core,
                           guard.block["generation"], guard.receipt, selected, entry,
                           guard.adapters)
    for leaf, original in bodies.items():
        guarded_body_read(guard.root, selected, leaf, guard.index, guard.watch, guard.check, original)
    guard.check()
    return result, guard


def guarded_bound(operation, root, target, provider, role, raw, executing=None):
    need(operation in ("read", "route") and role in
         (("implementer", "reviewer") if operation == "route" else
          ("orchestrator", "goal", "implementer", "reviewer")), "bound role")
    binding = binding_read(raw)
    need(binding["provider"] == provider, "binding provider")
    if role == "goal":
        need(binding["entry"] == skill_ids(provider)[-1], "explicit goal entry required")
    guard = ActivationGuard(root, target, provider)
    guard.match(binding)
    r = binding["release"]
    # Deliberately NOT runtime_read/management_read: no active or machine journal.
    guard.helper(r, executing)
    bodies = release_validate(guard.root, r, guard.index, guard.watch, guard.check)
    if operation == "route":
        result = (role_id(provider, role) + ":" +
                  binding["adapters"][role_leaf(provider, role)][0] + "\n").encode()
    else:
        leaf = "roles/" + role + ".md"
        snap = guarded_body_read(guard.root, r, leaf, guard.index, guard.watch, guard.check,
                                 bodies[leaf])
        result = snap[1]
        guarded_body_read(guard.root, r, leaf, guard.index, guard.watch, guard.check, snap)
    guard.match(binding)
    return result, guard


def verified_helper(root, target, provider, binding=None):
    """Body-free loader handoff API: verify T or explicitly bound R BEFORE exec.

    Caller executes only returned immutable path/bytes after watch.check; public
    native serialization/delegation is deliberately not supplied here.
    """
    guard = ActivationGuard(root, target, provider)
    release = guard.block["template_release"]
    if binding is not None:
        parsed = binding_read(binding)
        guard.match(parsed)
        release = parsed["release"]
    path, data = guard.helper(release)
    guard.check()
    return path, data, guard


def helper_main(argv, executing):
    try:
        need(argv and all(type(v) is str and v for v in argv), "empty helper argument")
        operation = argv[0]
        need((operation == "start" and len(argv) == 5) or
             (operation in ("read", "route") and len(argv) == 6), "helper argv")
        _, root, target, provider, role = argv[:5]
        if operation == "start":
            result, guard = guarded_start(root, target, provider, role, executing)
        else:
            result, guard = guarded_bound(operation, root, target, provider, role,
                                          argv[5].encode("utf-8"), executing)
        guard.check()
        sys.stdout.buffer.write(result)
        return 0
    except (Refusal, OSError, ValueError, IndexError, KeyError, TypeError, StopIteration):
        print("domestique2: guarded workflow refused; no fallback", file=sys.stderr)
        return 1
