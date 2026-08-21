# PRD: Native Codex support

**Status:** Approved (5-0 specialist consensus)
**Date:** 2026-08-21
**Origin:** “This directory holds an open source project I created called domestique, which currently works in guest & non-guest mode with Claude Code. I would like you to extend it to work with Codex.”

## Problem statement

Domestique currently projects its orchestration workflow exclusively onto Claude Code surfaces: `CLAUDE.md`, `.claude/agents/*.md`, `.claude/commands/*.md`, and `bd setup claude`. Codex uses different native surfaces and has no additive equivalent of `CLAUDE.local.md`. Users need the same orchestrator → bounded implementer → independent reviewer workflow in Codex without changing the existing Claude default or weakening guest-mode isolation.

## Proposed solution

Add `--platform claude|codex|both`; a first install without the option remains Claude-only. Persist the selected platform set in domestique-owned provider state so later selector-less upgrades update the installed set. Explicit installs add to that set; scoped uninstall removes from it.

Codex normal mode installs:

- a managed policy block in an existing active root `AGENTS.override.md`, or `AGENTS.md` otherwise;
- `.codex/agents/implementer.toml` using `gpt-5.6-terra` at medium effort;
- `.codex/agents/reviewer.toml` using `gpt-5.6` at high effort;
- repo skills `.agents/skills/domestique*/SKILL.md`, including decomposition, dispatch/landing policy, and explicit unattended goal execution;
- `.agents/skills/domestique-goal/agents/openai.yaml` with `allow_implicit_invocation: false`.

Codex guest mode never creates or modifies `AGENTS.md` or `AGENTS.override.md`, because an override shadows host instructions rather than layering with them. It installs path-specifically excluded Codex agents, skills, and `.codex/.domestique` state. The user invokes `$domestique` once per new session; every operational skill remains self-contained, and the base skill implicitly matches “dispatch next ready bead” and “land the plane.” This is functional guest support but intentionally not claimed as automatic startup-policy parity.

Claude state stays under `.claude/.domestique`; Codex state uses `.codex/.domestique`. Both use the existing adopt/three-way-merge/conflict invariant.

## P0 user stories and acceptance criteria

| ID | Story | Acceptance criteria |
|---|---|---|
| US-1 | Existing Claude user upgrades safely | Bare install remains Claude-only; current Claude output and all existing tests remain compatible. |
| US-2 | User installs Codex only or both clients | `--platform codex` creates no Claude artifacts; `both` creates both projections; selector is forwarded by `update.sh` and persisted for later bare reruns. |
| US-3 | Codex runs the domestique loop | Native custom agents implement bounded implementation and independent review; policy enforces implementer → wait → reviewer → wait and stop-between-beads. |
| US-4 | Codex has reusable workflows | Namespaced `$domestique`, `$domestique-decompose`, and `$domestique-goal` skills are discoverable; goal is explicit-only and is the sole unattended authorization boundary. |
| US-5 | Guest use respects the host | Codex guest leaves both root AGENTS files byte-untouched, uses precise local excludes, preserves pre-existing untracked visibility, and leaves a previously clean worktree clean. |
| US-6 | Beads uses the right integration | Normal installs use `bd init --skip-agents --skip-hooks --non-interactive` when needed, then `bd setup` only for selected providers. Guest uses `bd init --stealth --skip-agents --skip-hooks --non-interactive` and never runs provider setup; if safe flags are unavailable, it skips with a warning. |
| US-7 | Local customization survives | Codex policy, TOML, skill, and skill-metadata changes adopt/merge like Claude files; conflicts preserve live files, emit `.new`/`.bak`, retain old bases, and exit 3. |
| US-8 | Uninstall is ownership-safe | Bare uninstall scans both providers; scoped uninstall removes only the selected projection, updates the persisted platform set and shared exclude union, preserves modified/user files, and prunes only empty directories. |
| US-9 | Reviewer independence is verifiable | Orchestrator fingerprints tracked/staged diffs immediately before and after review; any reviewer-introduced tracked or bead-state delta is FAIL/stop. Ignored test artifacts may change and new visible untracked artifacts are reported. |
| US-10 | Model failures are recoverable | Failure identifies the role and configured model; docs explain editing the TOML or removing model settings to inherit the parent. No silent substitution. |

## Design and UX considerations

- Print selected platform(s), guest status, and policy destination or “skills-only” before writes.
- Use `$` skill syntax prominently; do not imply repository `/goal` or custom-prompt support.
- Keep `domestique.sh` self-contained so curl-pipe and clone-once installation still work.
- Guest exclusions name only domestique-owned files/directories rather than hiding whole `.agents/` or `.codex/` trees.
- Normal mode preserves all content outside managed markers and manages the actually active root instruction file.

## Technical and domain considerations

- Codex project agents are TOML files requiring `name`, `description`, and `developer_instructions`.
- Repo skills live under `.agents/skills`; custom prompts are deprecated and user-global, so they are out of scope.
- Reviewer uses inherited/workspace-write permissions because tests commonly write caches/build output. Non-editing is enforced by instructions plus the tracked/staged diff guard.
- Persisted platform selection is domestique state, not inference from installed binaries or arbitrary project files.
- Manifests enumerate the real managed inventory, including goal metadata and mixed root policy destinations.

## Success metrics

- All existing 49 Claude scenarios remain green.
- New Codex normal, guest, upgrade/conflict, mixed-platform, Beads routing, and uninstall scenarios pass.
- Fresh Codex guest install/uninstall preserves exact clean `git status`.
- Shell syntax and emitted TOML/skill frontmatter validate.
- No generated Codex content refers to Claude paths, Sonnet/Opus, or deprecated custom prompts.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Guest has no additive root policy file | Skills-only guest mode; explicit `$domestique` bootstrap; self-contained operational skills; honest documentation. |
| Codex agent schema/model IDs evolve | Keep emitted TOML locally editable and three-way merged; document parent-model inheritance recovery. |
| Reviewer modifies work while testing | Pre/post tracked/staged and bead-state fingerprints; fail and stop without auto-cleanup. |
| Mixed-provider uninstall removes host files | Fixed owned inventory, base comparison, exact-path pruning, scoped platform state, precise exclude union. |
| `bd init` mutates unrelated integrations/hooks | Use `--skip-agents --skip-hooks`; guest additionally uses `--stealth` and skips all setup recipes. |

## Out of scope

- Deprecated/global Codex custom prompts or writes to `~/.codex`.
- Plugin/global distribution, model benchmarking, Windows-native installer, or providers beyond Claude and Codex.
- Automatic push/merge or broad recursive deletion.
- Modifying Beads itself.
- Claiming byte-identical prompts or identical startup behavior across providers.

## Open questions

None blocking implementation.
