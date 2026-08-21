# SPARC: Native Codex support

## S — Specification

Implement the approved PRD in `docs/prd/codex-support.md`. Preserve the no-option Claude behavior while adding explicit/persisted `claude`, `codex`, and `both` platform sets. Codex normal mode uses native AGENTS/custom-agent/skill surfaces; Codex guest mode is skills-only and must preserve host instructions and clean git state.

Success is automated: current suites pass; new tests cover fresh/idempotent/dry-run installs, guest round trips, merge/adopt/conflict, model/skill schema, persisted platforms, both-provider coexistence, Beads recipe routing, update forwarding, and scoped/full uninstall.

## P — Pseudocode

```text
parse_cli():
    validate --platform claude|codex|both
    if explicit: requested = value
    else if domestique provider state persists platforms: requested = persisted set
    else: requested = claude
    on install, union explicit request with persisted set
    on scoped uninstall, remove requested providers from persisted set

install_provider(provider):
    configure provider inventory, policy destination, snapshot root, emitters
    resolve sticky guest state for that provider
    if codex guest: do not install a root policy
    else: install/merge active policy managed block
    install/merge every owned plain file and snapshot pristine emit
    write provider manifest and platform-set state only after clean ownership changes

install_guest_exclude():
    retain Claude compatibility entries; compute exact Codex owned leaves
    preserve pre-install visibility for unrelated/pre-existing Codex paths
    replace only domestique's managed info/exclude block

setup_beads():
    if bd absent: warn/skip
    probe bd init help for --skip-agents/--skip-hooks and guest --stealth
    if any required safe flag is absent: warn/skip initialization and setup
    if guest and no workspace: bd init --stealth --skip-agents --skip-hooks --non-interactive
    if guest: skip all setup recipes
    else if no workspace: bd init --skip-agents --skip-hooks --non-interactive
    for selected provider: bd setup provider

uninstall_provider(provider):
    require provider state or a managed policy marker as ownership evidence
    inspect fixed owned inventory plus all possible policy destinations
    compare plain files to provider base/pristine emit
    remove exact matches; rename modified files unless --force
    strip sound policy managed blocks; refuse malformed markers
    remove only provider snapshot state and prune only empty owned directories
    update persisted provider set and regenerate shared guest excludes
```

Reviewer protocol embedded in policy/skills:

```text
before reviewer dispatch:
    fingerprint git diff, git diff --cached, and bead state
spawn reviewer and wait
after reviewer returns:
    fingerprint again
    if tracked/staged diff or bead state changed: FAIL and stop
    report new visible untracked files; ignored test artifacts are allowed
```

## A — Architecture

```text
domestique.sh
  provider selection/state
      ├── Claude projection (existing emitters and .claude state)
      └── Codex projection
           ├── active AGENTS managed block (normal only)
           ├── .codex/agents/*.toml
           ├── .agents/skills/domestique*/SKILL.md
           └── .codex/.domestique/{manifest,base,mode,platforms,guest-excludes,beads-owned}

shared services
  install_plain / install_policy_block / snapshot / merge
  guest info/exclude compatibility + exact Codex ownership union
  provider-aware Beads routing
  provider-aware uninstall
```

Files:

- Modify `domestique.sh`, `update.sh`, `README.md`, and `docs/install-upgrade-design.md`.
- Add `test/codex.sh`; extend existing tests only where cross-provider behavior requires it.
- Keep all runtime templates embedded in `domestique.sh`.

## R — Refinement

Edge cases:

- Legacy Claude state has no platform-set marker: treat it as persisted Claude.
- Conflicting provider-state markers: warn and take their union; never drop a managed provider silently.
- Existing active `AGENTS.override.md`: manage it in normal mode; detect older managed blocks in either root AGENTS file during uninstall.
- Codex guest with any root AGENTS file: leave it byte-untouched.
- Goal metadata is a first-class managed file for snapshots, manifest, conflicts, excludes, and uninstall.
- Existing untracked owned paths are adopted but not newly hidden unless domestique created them.
- Guest Beads setup never installs editor integrations or hooks.
- Both providers share `.agents`; uninstall removes only domestique skill leaves and empty parents.
- Model unavailable: surface role/model and recovery, never fallback silently.
- Review test artifacts may be ignored; tracked/staged/bead changes are forbidden.

Testing layers:

1. Shell syntax for all scripts.
2. Existing Claude regression suites.
3. Codex installer scenarios with temporary Git repositories.
4. Static TOML/YAML/frontmatter assertions and Claude-term absence checks.
5. Fake-`bd` routing tests for exact init/setup calls.
6. Installed Codex smoke check when available, without making it a portability requirement.

## C — Completion

1. Add provider selection, state persistence, Codex emitters, and normal/guest installation.
2. Generalize snapshot/manifest/merge and exact Codex guest ownership while preserving Claude compatibility.
3. Generalize full/scoped uninstall and Beads routing.
4. Add Codex and cross-provider tests; fix regressions until all pass.
5. Update README/help/design documentation and run final syntax/full-suite/diff review.

Definition of done: every PRD P0 acceptance criterion is represented in implementation and tests; all feature beads are closed; no unintended worktree changes remain.

## Four-dimensional evaluation

- **Usability:** explicit platform selector, unchanged default, exact summaries, namespaced `$` workflows, clear guest bootstrap.
- **Value:** provides native Codex support while retaining Claude and guest safety.
- **Feasibility:** reuses the proven merge/snapshot engine and current documented Codex surfaces; Bash 3.2-compatible data structures only.
- **Viability:** provider inventories isolate future format changes; local edits survive upgrades; no deprecated prompt surface or home-directory writes.
