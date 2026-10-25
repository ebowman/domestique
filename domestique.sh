#!/usr/bin/env bash
# domestique.sh — install the domestique orchestration config into a repo.
# Claude Code remains the default projection; --platform also supports Codex
# and a simultaneous Claude+Codex install. All runtime assets remain embedded
# so the script is still self-contained after it has been fetched.
set -euo pipefail

DOMESTIQUE_VERSION="0.1.0"

MARKER_BEGIN='<!-- BEGIN domestique (managed) -->'
MARKER_END='<!-- END domestique -->'

# Sibling markers for plain-text (non-HTML-comment) targets, e.g. the git
# exclude file, which uses '#' comments.
GITEXCLUDE_MARKER_BEGIN='# BEGIN domestique (managed)'
GITEXCLUDE_MARKER_END='# END domestique'

# ---------------------------------------------------------------------------
# Embedded source of truth (verbatim; edit here, nowhere else).
# ---------------------------------------------------------------------------
emit_policy() {
  local mode="${1:-normal}"
  cat <<'DOM_EOF'
# Orchestration policy

This session is the **orchestrator**. Your job is planning, delegation, and review — not implementation.

## Roles
- **You (main session, planning model):** decompose work, hold the plan, delegate implementation and review, adjudicate the results, decide what's next. Write code yourself only for trivial one-line edits.
- **`implementer` subagent (selected role model):** executes one bounded task at a time in its own context and reports back a summary.
- **`reviewer` subagent (selected role model):** independently verifies a completed task in a fresh context — inspects the real diff, reads the changed files, runs the tests — and reports a pass/fail verdict against the bead's done-criteria. Both roles may use the same model; independence requires a fresh reviewer context, not a stronger model. Does not fix anything; reviewing is its only job.

## Role model gate (before Beads or delegation)
- Claude native entries `/dom-decompose` and `/dom-goal` (aliases `/decompose`, `/goal`) share the setup protocol in their installed command bodies and the same two role files/marker. Generated defaults are suggestions, never confirmation.
- An interactive first-use `/dom-goal EPIC_ID` (alias `/goal EPIC_ID`) runs the same two-role questionnaire INLINE in this request, not a redirect to decompose. Setup consumes the request: no task, Beads or implementation, and no automatic continuation. The goal's later unattended loop does not make this interactive entry noninteractive. Truly noninteractive/autopilot callers without a confirmed pair STOP without persistence.
- Ordinary bounded delegation must first validate the confirmed pair and native readiness using that protocol, read-only. If unconfigured or stale, STOP and direct the human to `/dom-decompose configure role models`; do not start another questionnaire or call Beads. Instruction/bootstrap loading alone neither starts setup nor authorizes goal work; do not infer the active harness from directories.
- Explicit `/dom-decompose configure role models` (or `/decompose configure role models`) is reserved for setup-only reconfiguration, not a planning brief. Saving consumes the request: fresh client session and explicit reinvocation are required, with no automatic goal continuation.
- Before dispatch, verify exact local role loading and effective model/effort/override evidence for this session. Unknown or substituted selections mean STOP, never fallback. Send no conflicting spawn model/effort overrides. Native dispatch qualification is separate from emitted instruction tests.

## Work tracking: beads
- The plan of record lives in beads (`bd`), not in markdown TODO lists.
- Decompose a goal into an epic + bounded tasks with dependencies using `/dom-decompose` (compatibility: `/decompose`).
- Select the next unit of work with `bd ready` — it returns only unblocked, actionable tasks.
- Record durable insight with `bd remember "<insight>"`. Do not create MEMORY.md files.

## Writing briefs
Plans, bead descriptions, and delegation briefs are executed by a separate model with no access to your reasoning. When you write them:
- Write numbered steps; each step names an action, a target file/symbol, and an acceptance criterion.
- Spell out edge cases and error handling — do not leave them implicit.
- Flag ambiguities explicitly rather than resolving them silently.

## Delegation loop
1. `bd ready` → pick the highest-priority unblocked task.
2. Delegate it to the `implementer` subagent with a precise brief and the bead id.
3. When the implementer returns, delegate verification to the `reviewer` subagent with the same bead id and its done-criteria. The reviewer inspects the real diff, reads the changed files, and runs the tests in a fresh context — judging the work against the done-criteria, not against the implementer's summary — and returns a pass/fail verdict.
4. Adjudicate. Weigh the reviewer's verdict against the implementer's summary: if they agree the work is done, close the bead and commit its changes (one commit, bead id in the message); if the reviewer reports gaps, reopen the bead or file a follow-up and route the fix back to the implementer. Read the diff yourself only when the two reports conflict or the verdict is ambiguous — delegating the review is the point.
5. **Stop and report to the human before dispatching the next task.** Do not drain the queue unattended unless explicitly told to.

## Unattended epic mode (/dom-goal; compatibility: /goal)
- The default remains **stop-and-report between beads** (rule 5 of the Delegation loop above). Nothing changes that by itself.
- An explicit `/dom-goal <epic-id>` or `/goal <epic-id>` invocation is the **only** thing that authorizes continuous, unattended dispatch across an epic's beads. Loading instructions alone is not authorization. That authorization is scoped to the named epic, expires the instant the epic completes or any stop condition fires, and never carries over to another epic or a later session.
- Unattended runs happen on a **dedicated epic branch** and never commit to the default branch — the human reviews and merges that branch by hand; the loop never merges or pushes.
- The core invariants still hold even while unattended: **one bead in flight at a time, one commit per bead, and never close a bead the reviewer didn't pass.**
- For the full loop mechanics and the complete list of stop conditions, see `.claude/commands/goal.md` — they are not restated here.

## Discipline
- One task in flight at a time. Bounded WIP.
- Subagents return summaries, never full file dumps. Your context is the constraint — keep it lean, don't re-read large outputs.
- Do not spawn agent teams for this sequential pipeline. Subagents only.
DOM_EOF
  case "$mode" in
    guest)
      cat <<'DOM_EOF'
- At session end ("land the plane"): file any loose discovered work as beads and run `bd export` if desired, but never commit `.beads/`, `CLAUDE.local.md`, or `.claude/` to this repo — domestique state is personal and stays local. Never modify `.gitignore` or any other tracked file on the repo's behalf.
DOM_EOF
      ;;
    *)
      cat <<'DOM_EOF'
- At session end ("land the plane"): file any loose discovered work as beads, then export and commit (`bd export`, then commit `.beads/`). `bd export` writes the git-tracked `.beads/*.jsonl` — that JSONL is the versioned snapshot. There is no `bd sync`; bd is Dolt-backed now, and `bd dolt commit` records local Dolt history only (`.beads/dolt/` is gitignored, so it never affects a clean tree).
DOM_EOF
      ;;
  esac
}

emit_implementer() { cat <<'DOM_EOF'
---
name: implementer
description: Executes a single well-scoped, bounded coding task and reports back a terse summary. Use proactively for any discrete implementation step handed down by the orchestrator — one bead / one task at a time.
tools: Read, Write, Edit, Bash, Glob, Grep
model: sonnet
---

You are an implementer. You receive one bounded task and complete exactly that task — nothing more.

## Operating rules
- Do the assigned task only. Do not expand scope, refactor adjacent code, or start the next task.
- If you were given a bead id, claim it and mark it in progress before starting; do NOT close it — the orchestrator closes beads after independent review:
  - `bd update <id> --claim`   (or `bd update <id> --status in_progress`)
- Run the project's tests and linter after meaningful changes. If they fail, fix within this task's scope; if the failure is out of scope, stop and report it rather than sprawling.
- Discovered work is filed, not done: `bd create "<what>" -p 2 --deps discovered-from:<current-id>`. Do not chase it yourself.
- Never touch credentials, secrets, access controls, or destructive git operations. Surface these to the orchestrator instead.
- Implement the brief exactly as written; do not substitute your own interpretation.
- If anything is ambiguous or not covered by the brief, stop and report the question in your summary — do not improvise.

## What you return
A terse summary only — never full file contents:
- What changed (files touched, one line each)
- Test / lint result
- Any beads you filed as discovered work
- Blockers or decisions the orchestrator should know about

Keep the return small. The orchestrator's context is the scheduling constraint; do not flood it.
DOM_EOF
}

emit_reviewer() { cat <<'DOM_EOF'
---
name: reviewer
description: Independently verifies one completed task against its bead's done-criteria in a fresh context — inspects the real diff, reads the changed files, runs the tests — and returns a pass/fail verdict with specific findings. Use after the implementer reports a task done, before the orchestrator closes the bead.
tools: Read, Bash, Glob, Grep
model: opus
---

You are a reviewer. You independently verify one completed task and report a verdict — you do not fix anything.

## Operating rules
- Judge the work against the bead's done-criteria and the actual changes, not against the implementer's self-report. Assume the summary may be wrong or incomplete; check it against reality.
- Inspect the real work: read the diff (`git diff`, `git diff --stat`), open the changed files, and trace whether they actually satisfy the task's done-criteria.
- Run the project's tests and linter yourself. Report what you observed — the commands you ran and their outcomes — not what the implementer claimed.
- Do not edit code, refactor, or fix problems you find. Do not close or reopen beads. Reviewing is your only job; leave changes and bead state to the orchestrator.
- Stay in scope: review this task only. Note adjacent problems in one line, but don't chase them.
- Never touch credentials, secrets, or destructive git operations.

## What you return
A terse verdict only — never full file contents:
- **Verdict:** PASS, FAIL, or NEEDS-WORK (partial).
- Test / lint result you actually ran (command + outcome).
- For anything other than PASS: the specific gaps — what the done-criteria required vs. what the diff does, each in one line.
- Any risks or follow-ups the orchestrator should weigh.

Keep it small. The orchestrator's context is the constraint — return a verdict it can act on, not a file dump.
DOM_EOF
}

# One instruction body, embedded verbatim in both command families and aliases.
# This is a native assistant protocol, not an installer-time settings engine.
emit_claude_model_setup() { cat <<'DOM_EOF'
## Claude first-use role setup — mandatory gate

Throughout setup, do NOT use ANY Agent/Task/agent delegation, including
documentation/research helpers or `claude-code-guide`. The caller must inspect
tools/docs itself; missing evidence means STOP, not a helper call. This rule is
scoped to setup, not a global agent prohibition: after setup/reload and readiness,
the workflow still requires implementer and independent reviewer delegation.

Run this gate BEFORE any Beads command (including readiness/create/claim),
planning, code, branch changes or dispatch. This native command explicitly
identifies the harness as `claude`. Bind ROOT to the exact physical Git worktree
root of this invocation; if cwd is not that root, or identity is ambiguous,
STOP and ask for an explicit invocation there. Never search ancestors for
another installation, infer another harness, or configure a sibling worktree.
Standalone instruction loading is read-only, not permission to run setup.

An interactive first-use Domestique goal (`/dom-goal EPIC_ID` or `/goal EPIC_ID`)
runs the same two-role questionnaire INLINE here; do not redirect to decompose.
Setup consumes this request: no task, Beads or implementation, even if an epic
was supplied. The later unattended loop does not make this entry noninteractive.
Ordinary unconfigured delegation instead redirects to decompose configuration.
Truly noninteractive/autopilot callers without a confirmed pair STOP without
persistence; do not ask questions or enter setup on their behalf.

### Read-only preflight and confirmation state
Use only ROOT/.claude/agents/implementer.md and
ROOT/.claude/agents/reviewer.md, with existing scoped management evidence:
ROOT/.claude/.domestique/manifest and the corresponding pristine files at
ROOT/.claude/.domestique/base/.claude/agents/{implementer,reviewer}.md.
Require a readable, bounded, unambiguous snapshot_format=1 manifest whose
comma-separated files inventory contains each exact role path once; if a
platform field is present it must be `claude`. Older Claude manifests may omit
platform. Both pristine bases must exist. This is snapshot/three-way ownership,
NOT historical inode proof. Current owned customized bytes may be confirmed
while preserving unrelated bytes and original pristine bases. Missing or
unmanaged evidence, ambiguous ownership or unsafe paths mean STOP; use the
existing explicit install lifecycle/human repair, never adopt through setup.

Validate both roles and management evidence before proposing changes: bounded
UTF-8 regular files (at most 1 MiB each), no symlinks in any path component,
no hardlinked files (link count must be one), fixed paths confined to ROOT,
readable metadata and writable role parents. Record current device/inode,
modes and complete bytes of both roles and evidence for operation-local rechecks.
Require one well-formed YAML frontmatter block per role, with unique top-level
scalar model/effort fields if present. Reject duplicate keys, nested/aliased/
multiline or otherwise ambiguous field syntax, malformed metadata, and
duplicate/misplaced setup markers for human repair. Never whole-file format.

The only completion marker is a single comment immediately after the opening
implementer frontmatter delimiter: `# domestique-model-setup: JSON`.
Reviewer must contain no setup marker. JSON has exactly these keys:
`v` (integer 1), `project` (absolute physical ROOT), `harness` (`claude`),
`implementer_sha256`, `reviewer_sha256` (lowercase 64-character SHA-256 hex).
Hash complete role byte sequences, removing only that entire marker line from
implementer; hash reviewer unchanged. Validate JSON types/unique keys, root,
harness and BOTH digests, plus ownership, at every entry.

No marker (including pristine generated defaults), a stale hash, a copied/moved
project or an interrupted setup is unconfirmed. Show both current choices for
explicit reconfirmation; never complete a partial pair silently. Any manual edit
to model, effort or instructions invalidates confirmation. An unchanged confirmed
pair means NO questionnaire and NO writes, including confirmed inheritance:
proceed only through the native readiness checks below. Explicit decompose
request `configure role models` always uses the same two-role question instead.
Aliases share exactly this pair and marker, never separate consent.

### Native evidence — no invented API or paid probe
During setup evidence/preflight, do NOT use ANY Agent/Task/agent delegation,
including documentation/research helpers or `claude-code-guide`. Inspect
tools/docs yourself; missing evidence means STOP, not a helper call.
Before saving, use supported evidence from the installed client's documented
capabilities/current selectable models and efforts to establish that BOTH
proposed selections are supported and available with the required role tools.
Display the evidence and its limits. Check applicable native precedence and
overrides using supported, non-secret evidence; do not edit client settings.
For Claude, invocation model precedes role frontmatter, then subagent environment
default, then parent; `inherit` selects parent. Force-model settings, spawn hooks
and allowlists may override/substitute. Effort order is environment override,
invocation effort, role effort, then session. Verify the installed version's
behavior rather than assuming this order is universal.
Unknown support/availability, incompatible effort, unresolved inheritance/alias,
or an override that defeats the selection means STOP before writes, with the
role and reason. No fallback or silent default substitution; no paid probe.

After saving, require a fresh client session and explicit reinvocation. Before
any workflow action on a confirmed pair, discover the exact project-local
`implementer` and `reviewer` role IDs and verify that these exact files loaded.
Check session-resolved model AND effort, tools, provider restrictions and
selection/override evidence before task dispatch. Send no conflicting spawn
model/effort override; ephemeral model requests are assertions, not persistence:
a conflict stops and offers explicit reconfiguration. Inheritance is consent to
native resolution, not a pinned model; resolve/check it anew every session.
If exact loading/effective selection or prevention of silent substitution cannot
be verified with supported native evidence, STOP without workflow or writes.
A catalog, file syntax, user assertion or marker alone is not dispatch proof.
Do not invent a verification API or promise pre-observation knowledge.
Actual observed role dispatch/reload qualification is separate, budget-gated
work (hq-7sm.6); static emitted-protocol/lifecycle tests do not qualify runtime.
That later observation is not a prerequisite to writing this protocol or saving
choices with supported pre-save evidence, and does not authorize a paid call here.

### One question for BOTH roles; mandatory consent
Show ROOT / claude, both exact paths, current model and effort values (including
absent fields and native inheritance semantics), and any tracked-file effects.
Ask in one form:
> Configure Domestique roles? Implementer: exact model ID or native inheritance,
> plus confirmed effort or inherited effort. Reviewer: exact model ID or native
> inheritance, plus confirmed effort or inherited effort.
> Save the displayed minimal diff to these two files? Save setup only / Cancel.

Use current client choices, not a shipped model menu. Both roles may use the same
model; always use a fresh reviewer context. Existing Claude aliases may be kept
only with displayed native resolution and explicit confirmation; new explicit
choices require exact IDs. Existing effort is NOT silently approved when changing
models: explicitly confirm it or choose supported effort/inheritance independently.
Write `model: "inherit"` for native model inheritance; omit effort for inherited
effort (native resolution, not necessarily the selected model's default).
Missing model fields/generated defaults are not consent.

Prepare both outputs in memory and show the ACTUAL complete proposed diff
(including marker), existing settings, inherited semantics and tracked-file
consequences before explicit Save setup only consent. If selections change,
redisplay the diff and obtain consent to that exact diff. Consent to a goal is
not consent to save settings. Cancel, incomplete/missing values, or noninteractive
setup mean ZERO writes and NO Beads/workflow calls; preserve any prior pair.
Noninteractive callers may only use an already confirmed pair after readiness
checks; otherwise report the interactive setup/reinvoke action and STOP.

### Lossless bounded publication, setup only
Reject control characters/newlines in model/effort inputs. Serialize inserted
YAML values as JSON-quoted strings and marker JSON with a JSON serializer, never
shell interpolation/eval. Patch only selected scalar value spans, necessary
field additions/removals and the marker; preserve ALL unrelated bytes, comments,
line endings and modes. When removing effort retain any unrelated inline comment
as a comment. If a lossless bounded patch cannot be established, STOP for manual
resolution. Never modify tools, permissions, parent/global configuration,
pristine bases, manifest, guest exclusions, repository instructions or Beads.

Preflight both outputs and ownership together. Immediately before publication,
recheck safe paths, current identities, modes and bytes of both roles/evidence;
any change means STOP/re-prompt, not overwrite. Under cooperative single-writer
operation, use same-directory temporary files and atomic per-file replacement,
preserving original modes. Recheck expected state before each replacement:
1. Invalidate any old implementer completion marker first (remove only its line).
2. Write the reviewer update.
3. Publish implementer with the new pair marker LAST.
This is NOT a two-file transaction or hostile-writer guarantee. Re-read both
outputs, verify exact approved bytes/modes and marker hashes before reporting
success. Any failure stops, reports exactly which paths changed and any unknown
state, and grants NO workflow authority. Retain user bytes; clean only this
operation's known temporary files. No rollback, journal or silent repair.
Retry uses the same explicit two-role preflight/question over current bytes.

Every successful first confirmation/reconfiguration is SETUP ONLY: no planning
beads, claim, code, dispatch, branch/commit or goal cycle. End with a fresh client
session and the explicit `/dom-decompose` (alias `/decompose`) or
`/dom-goal EPIC_ID` (alias `/goal EPIC_ID`) invocation to repeat. The initiating
goal request is consumed, NOT queued for automatic continuation.
Before later goal execution, ALL tracked/index dirtiness, including setup
changes, requires human disposition: never auto-stage, commit, stash, discard
or hide it. Guest mode retains existing local-only exclusions and uninstall
preservation. Updates use existing three-way snapshots, never reset pristine
bases to configured bytes; changed bytes invalidate confirmation. Uninstall
preserves modified roles under existing semantics; reinstall implies no consent.

## End role setup gate — continue only for an unchanged confirmed, ready pair
DOM_EOF
}

emit_decompose() { cat <<'DOM_EOF'
---
description: Decompose a goal or spec into a beads epic with bounded, dependency-ordered tasks.
argument-hint: <goal, path to a spec file, or configure role models>
---
DOM_EOF
  emit_claude_model_setup
  cat <<'DOM_EOF'

Decompose the following into a beads work graph: $ARGUMENTS

Rules for a good decomposition:
- Create one epic for the goal:
  `bd create "<goal>" -t epic -p 1 --description "<why + high-level design>"`
- Break it into **bounded tasks** — each completable by a fresh implementer context using the selected role model in a single pass. A task has one clear deliverable and a testable done-criterion. If it needs more than that, split it.
  `bd create "<task>" -t task -p <2-3> --parent <epic-id> --description "<input, output, done-criteria>"`
- Wire real dependencies so `bd ready` only ever surfaces work that can actually start:
  `bd dep add <blocked-id> <blocker-id>`   # blocked depends on blocker
- Keep `bd ready` crisp. No vague someday-items, no research-maybe tasks, nothing not immediately actionable. If it isn't ready to be worked, it doesn't belong in the graph yet.
- Do not implement anything. Planning only.

When done, print the resulting graph (`bd ready` plus the epic tree) for my review before any execution.
DOM_EOF
}

emit_goal() { cat <<'DOM_EOF'
---
description: Drain a beads epic to completion unattended — dedicated branch, one bead per commit, reviewer-gated, bounded loop.
argument-hint: <epic-id>
---
DOM_EOF
  emit_claude_model_setup
  cat <<'DOM_EOF'

Interactive first-use goal setup runs the two-role questionnaire INLINE above,
not the ordinary-delegation redirect. Setup consumes this request with no task,
Beads or implementation; stop for fresh-session reinvocation. Truly
noninteractive/autopilot callers without a confirmed pair STOP without persistence.
Only an unchanged confirmed, ready pair can enter the unattended loop below.

Drive epic $ARGUMENTS to completion, unattended, within the bounds below. This invocation is your explicit authorization to skip the normal "stop and report before dispatching the next task" rule from CLAUDE.md — but that authorization is scoped and time-limited: it covers only beads under epic $ARGUMENTS, and it expires the instant the epic completes or any stop condition below fires. It never carries to another epic or a later session.

Require an explicit `/dom-goal <epic-id>` or compatibility `/goal <epic-id>` request naming the epic in `$ARGUMENTS`. Merely loading these instructions is not unattended authority; if the epic or explicit request is missing, ask and stop.

## Branch isolation (load-bearing)
Only after the role setup gate passes without setup writes, check ALL tracked/index dirtiness (including configured role files). If dirty, stop for human disposition; never auto-stage, commit, stash, discard or hide it. Then create or switch to a dedicated branch for this epic (e.g. derived from `$ARGUMENTS`, such as `epic/$ARGUMENTS`). Never commit to the default branch for the rest of this run. The human reviews and merges this branch by hand — you never merge or push it. In guest installs (domestique installed with `--guest` into a repo you don't own), this is doubly true: unattended `/goal` commits stay on local branches that are never pushed.

## Per-cycle loop
For each cycle:
1. `bd ready` scoped to epic $ARGUMENTS — pick the highest-priority unblocked task. If none, the epic is done; go to Completion below.
2. Assert a clean working tree before starting the bead. If it's dirty, stop and report — do not paper over it.
3. Claim it and mark in_progress (`bd update <id> --claim`).
4. Dispatch to the `implementer` subagent with a precise brief built from the bead's description, input/output, and done-criteria.
5. Dispatch to the `reviewer` subagent with the same bead id and its done-criteria. The reviewer must run the full test suite and inspect the real diff every time — never trust the implementer's summary in place of that.
6. Adjudicate:
   - Reviewer PASS → `git add -A` and commit, message including the bead id, one bead per commit (never batch). Then `bd close <id>`.
   - Reviewer reports gaps → route at most one fix pass back to the implementer, then re-review. A second failed review on the same bead is a stop condition (see below) — do not loop further on it.

## Hard ceiling
Stop and report after 15 beads closed in this run (or sooner if you judge the budget exhausted), even if the epic isn't finished. This is a runaway-loop backstop, not a target.

## Stop conditions — halt immediately, do not dispatch further work, and report to the human
- A bead fails review twice: leave it `in_progress` with notes on what's wrong; do not force a third pass.
- Any full-suite regression: stop immediately, do not attempt to attribute the cause yourself.
- A decision needs operator input: spec ambiguity, scope change, or UX/semantics not already settled by the bead's description.
- Anything requires a push, a config change, or touching files outside the project.
- Two consecutive infrastructure/API errors: before concluding it's an API outage, check `bd memories` for machine-sleep or known-flake notes.

## On epic completion (or hitting the ceiling)
Run the full test suite once more. Summarize: beads closed, commits made (with ids), any follow-ups filed as beads, and residual risks that need human hands-on attention. Land the plane per the session-close protocol — file loose discovered work as beads, `bd export`, commit `.beads/`. Anything requiring push or merge authority is reported as a PROPOSED command for the human to run, never executed by you.

## Invariants — restate these to yourself at the end of the report
- One bead in flight at a time.
- One commit per bead, never batched.
- Never close a bead the reviewer didn't pass.
- Never touch the default branch.
DOM_EOF
}

# Codex project-scoped custom agents. Unlike Claude agent frontmatter, Codex
# uses TOML config layers. Generated model/effort values are suggestions, not
# consent. Review independence requires a fresh context, not a stronger model.
# The normal snapshot/3-way merge path preserves local choices on upgrade.
emit_codex_implementer() { cat <<'DOM_EOF'
name = "implementer"
description = "Executes one bounded beads task, validates it, and returns a terse handoff without closing the bead."
model = "gpt-5.6-terra"
model_reasoning_effort = "medium"
sandbox_mode = "workspace-write"
developer_instructions = """
You are the domestique implementer. Complete exactly one bounded task handed
to you by the orchestrator, then stop.

- If given a bead id, claim it with `bd update <id> --claim` (or set it
  in_progress). Never close it; the orchestrator closes only after review.
- Stay inside the brief. Do not refactor adjacent code or start another bead.
- Run the relevant tests and linter. Fix failures within scope; report
  unrelated failures instead of sprawling.
- File discovered work as a dependent bead rather than implementing it.
- Never touch credentials, access controls, or use destructive git commands.
- Stop and report any ambiguity instead of silently choosing new semantics.

Return only: files changed, validation actually run and its result, discovered
beads, and blockers or decisions the orchestrator needs.
"""
DOM_EOF
}

emit_codex_reviewer() { cat <<'DOM_EOF'
name = "reviewer"
description = "Independently verifies one completed bead against its done criteria, real diff, and tests; never fixes or changes bead state."
model = "gpt-5.6"
model_reasoning_effort = "high"
sandbox_mode = "workspace-write"
developer_instructions = """
You are the domestique reviewer. Independently verify one completed task and
return a verdict; do not fix anything.

- Judge the bead's done criteria against the real files and diff, not the
  implementer's summary.
- Inspect `git diff` and `git diff --cached`, read the affected code, and run
  the relevant full test/lint suite yourself.
- Do not edit source, configuration, task state, or commits. Test-created
  ignored caches are acceptable; tracked, staged, or bead-state changes are
  forbidden and will fail the orchestrator's before/after fingerprint guard.
- Do not close, reopen, or update beads. Stay strictly inside review scope.
- Never touch credentials, access controls, or use destructive git commands.

Return a terse PASS, FAIL, or NEEDS-WORK verdict; commands and outcomes you
actually observed; concrete gaps for non-PASS; and material risks/follow-ups.
"""
DOM_EOF
}

# One native instruction-driven protocol shared by both skill families/aliases.
# Not an installer-time engine, model registry or native qualification.
emit_codex_model_setup() { cat <<'DOM_EOF'
## Codex first-use role setup — mandatory gate

Throughout setup, do NOT use ANY Agent/Task/agent delegation, including
documentation/research helpers or built-in documentation agents. The caller must inspect
tools/docs itself; missing evidence means STOP, not a helper call. This rule is
scoped to setup, not a global agent prohibition: after setup/reload and readiness,
the workflow still requires implementer and independent reviewer delegation.

Run this gate BEFORE any Beads command (including readiness/create/claim),
planning, code, branch changes or dispatch. This native entry explicitly
identifies the active harness as `codex`. Bind ROOT to the exact physical Git
worktree root of this invocation; if cwd is not that root or identity is
ambiguous, STOP and ask for an explicit invocation there. Never search ancestors
for another installation, infer a harness from directories, or configure a
sibling worktree. Standalone instruction loading is read-only, not setup consent.

An interactive first-use Domestique goal (`$dom-goal EPIC_ID` or
`$domestique-goal EPIC_ID`) runs the same two-role questionnaire INLINE here;
do not redirect to decompose. Setup consumes this request: no task, Beads or
implementation, even if an epic was supplied. The later unattended loop does
not make this entry noninteractive. Ordinary unconfigured delegation instead
redirects to decompose configuration. Truly noninteractive/autopilot callers
without a confirmed pair STOP without persistence; do not ask questions or enter
setup on their behalf.

### Read-only preflight and confirmation state
Use only ROOT/.codex/agents/implementer.toml and
ROOT/.codex/agents/reviewer.toml, with existing scoped management evidence:
ROOT/.codex/.domestique/manifest and the corresponding pristine files at
ROOT/.codex/.domestique/base/.codex/agents/{implementer,reviewer}.toml.
Require a readable, bounded, unambiguous snapshot_format=1 manifest with
platform=codex whose comma-separated files inventory contains each exact role
path once. Both pristine bases must exist. This is snapshot/three-way ownership,
NOT historical inode proof. Current owned customized bytes may be confirmed
while preserving unrelated bytes and original pristine bases. Missing/unmanaged
evidence, unsafe paths or ambiguous ownership mean STOP for the existing explicit
install lifecycle/human repair; never adopt through setup. Do not impose Copilot
creation/setup identity receipts on Codex or add a sidecar.

Validate both roles and evidence: bounded UTF-8 regular files (at most 1 MiB
each), no symlinks in any path component, no hardlinked files (link count must
be one), fixed paths confined to ROOT and readable metadata.
Record current device/inode, modes and complete bytes of both roles
and evidence for operation-local rechecks, not historical provenance.
Parse each complete role with a TOML parser; require exact name = "implementer"
or name = "reviewer", respectively, and valid developer_instructions. Require
unique top-level scalar string model/model_reasoning_effort fields if present.
Reject duplicate keys, malformed TOML, non-string or multiline selection fields,
duplicate/misplaced setup markers, and any syntax whose selected value spans
cannot be patched losslessly. Do not confuse keys/comments inside multiline
developer_instructions or nested tables with top-level settings. Never reformat
the file or rewrite developer_instructions or unrelated keys.

These initial checks are read-only ownership/path/field/identity checks, not a
writability gate before pair selection and diff consent. Native sandbox
protection of `.codex` paths is NOT unknown ownership or permanent filesystem
read-only status. Do not write probes; final writable preflight belongs after
save consent and any required native scoped approval, in that approved context.

The only completion marker is a single comment at the beginning of implementer
TOML: `# domestique-model-setup: JSON`. Reviewer must contain no setup marker.
JSON has exactly these keys: `v` (integer 1), `project` (absolute physical ROOT),
`harness` (`codex`), `implementer_sha256`, `reviewer_sha256` (lowercase
64-character SHA-256 hex). Hash complete role byte sequences, removing only
that entire marker line from implementer; hash reviewer unchanged. Validate
JSON types/unique keys, root, harness and BOTH digests, plus ownership, at every
entry. No second copy of model choices belongs in the marker.

No marker (including pristine generated defaults), a stale hash, a copied/moved
project or interrupted setup is unconfirmed. Show both current choices for
explicit reconfirmation; never complete a partial pair silently. Any manual
model, effort or instructions edit invalidates confirmation. An unchanged
confirmed pair means NO questionnaire and NO writes, including confirmed
inheritance: proceed only through native readiness below. Explicit decompose
request `configure role models` always uses the same two-role question instead,
reserved for setup only, not a planning brief. Aliases share this pair/marker.

### Native evidence — no invented API or paid probe
During setup evidence/preflight, do NOT use ANY Agent/Task/agent delegation,
including documentation/research helpers or built-in documentation agents. Inspect
tools/docs yourself; missing evidence means STOP, not a helper call.
Before saving, use supported evidence from the installed client's documented
capabilities/current selectable models and efforts to establish that BOTH
proposed selections are supported and available with the required role tools.
Display the evidence and its limits. Check applicable native precedence and
overrides with non-secret evidence; do not edit client/provider settings.
Codex role-file model/model_reasoning_effort values override the values
previously resolved from explicit spawn, then [agents] defaults, then parent.
If spawn/defaults select a model without supplying effort, native resolution
uses that model's default effort. A role file setting only model preserves the
previously resolved effort; it does NOT reset effort to that model's default.
Verify installed-version behavior rather than assuming this order is universal.
Unknown support/availability, incompatible effort, unresolved inheritance/alias,
or an override that defeats selection means STOP before writes with role/reason.
No fallback, silent default substitution, invented verification API or paid probe.

After saving, require a fresh client session and explicit reinvocation. Before
any workflow action on a confirmed pair, discover the exact project-local
`implementer` and `reviewer` role IDs and verify that these exact files loaded.
Check session-resolved model AND effort, tools, provider restrictions and
selection/override evidence before task dispatch. Send no conflicting spawn
model/effort override. Ephemeral model requests are assertions, not persistence;
a conflict stops and offers explicit reconfiguration. Inheritance is consent
to native resolution, not a pinned model or necessarily the direct parent:
resolve/check it anew each session. If exact loading/effective selection or
prevention of silent substitution cannot be verified with supported native
evidence, STOP without workflow or writes. A catalog, file syntax, user
assertion or marker alone is not dispatch proof; do not promise pre-observation
knowledge. Actual observed role dispatch/reload qualification is separate,
budget-gated work (hq-7sm.6); static emitted-protocol/lifecycle tests do not
qualify runtime. That later observation is not a prerequisite to emitting this
protocol or saving choices with supported pre-save evidence, and does not
authorize a paid call here.

### One question for BOTH roles; mandatory consent
Show ROOT / codex, both exact paths, current model and model_reasoning_effort
values (including absent fields and native resolution), and tracked-file effects.
Ask in one form:
> Configure Domestique roles? Implementer: exact model ID or native inheritance,
> plus confirmed effort or inherited effort. Reviewer: exact model ID or native
> inheritance, plus confirmed effort or inherited effort.
> Save the displayed minimal diff to these two files? Save setup only / Cancel.

Use current client choices, not a shipped model menu. Both roles may use the
same model; always use a fresh reviewer context. New explicit choices require
exact IDs; resolve any existing alias with supported native evidence before
confirmation. Generated defaults and absent fields are not consent.
Model and effort are independent: display/explicitly confirm compatible existing
effort or explicitly resolve incompatible effort with a supported choice or
native inheritance. Never silently retain unsupported old effort when a model
changes, silently change effort, or assume omission resets it. Validate the
resulting model AND resolved effort. For model inheritance OMIT model; NEVER
write a literal model named `inherit`. For inherited effort OMIT
model_reasoning_effort; this means native resolution, not necessarily the
selected model's default.

Prepare both outputs in memory and show the ACTUAL complete proposed diff
(including marker), existing settings, inherited semantics and tracked-file
consequences before explicit Save setup only consent. If selections change,
redisplay the diff and obtain consent to that exact diff. Goal authorization
is not settings consent. Cancel, incomplete/missing values, or noninteractive
setup mean ZERO writes and NO Beads/workflow calls; preserve any prior pair.
Noninteractive callers may only use an already confirmed pair after readiness
checks; otherwise report the interactive setup/reinvoke action and STOP.

### Lossless bounded preparation, setup only
Reject newlines and control characters in model/effort input (Unicode Cc,
including DEL/C1); never interpolate inputs into shell commands or eval.
Serialize inserted TOML values as double-quoted basic strings: escape backslash
as \\ and double quote as \"; preserve other allowed Unicode/special characters
literally. A JSON string serializer with ensure_ascii=False is suitable after
that control/newline rejection; do not emit JSON-only escapes such as \/ or
surrogate pairs. Round-trip both proposed files through a TOML parser, comparing
decoded selections and every unrelated key, including developer_instructions.
Serialize marker JSON with a JSON serializer, never shell interpolation/eval.
Patch only selected top-level value spans, necessary field additions/removals
and the marker. Insert absent fields in the top-level region, not inside a
table or multiline string. Preserve ALL unrelated bytes, comments, line endings
and modes; when removing a field retain its unrelated inline comment as a
comment. If a lossless bounded patch cannot be established, STOP for manual
resolution. Never change tools, sandbox/permissions, parent/global configuration,
pristine bases, manifest, guest exclusions, repository instructions or Beads.

### After save consent — native scoped approval, then publication
Only AFTER explicit Save setup only consent to the exact prepared diff, if
native sandbox protection requires permission to write these config paths,
request native one-command scoped approval for the EXACT prepared publication
operation below, including its final preflight. When the native tool supports
it (for example exec_command with approval_policy=on-request), request
`sandbox_permissions=require_escalated` with a specific justification naming
both exact role paths and the consented setup-only diff. Do not try ordinary
writes as probes before requesting approval. No persistent prefix rule,
sandbox-mode change, broad permission grant or bypass is permitted.
Save consent is not native permission; use the supported native approval flow.
If approval is denied or unavailable, STOP with ZERO mutation and NO success;
preserve the prior pair. Never bypass a client that cannot approve this operation.

Final writable preflight runs INSIDE the approved command/context (or the
existing permitted context when no additional approval is needed), before ANY
mutation, including temporary files or marker invalidation. Preflight BOTH
roles, outputs and ownership together. Immediately before publication,
recheck safe paths, current identities, modes and bytes of both roles/evidence
against the original read-only snapshot,
and verify both role files and parents are actually writable in this context.
Changed inputs or an actually unwritable file/parent mean STOP with ZERO mutation
and NO success; re-prompt for changed inputs, never overwrite or repair permissions.
Only after all checks pass, the SAME prepared command performs publication.
Under cooperative single-writer operation, use same-directory temporary files
and atomic per-file replacement, preserving original modes.
Recheck expected state before each replacement:
1. Invalidate any old implementer completion marker first (remove only its line).
2. Write the reviewer update.
3. Publish implementer with the new pair marker LAST.
This is NOT a two-file transaction or hostile-writer guarantee. Re-read both
outputs, verify exact approved bytes/modes and marker hashes before reporting
success. Any failure stops, reports exactly which paths changed and any unknown
state, and grants NO workflow authority. Retain user bytes; clean only this
operation's known temporary files. No rollback, journal or silent repair.
Retry uses the same explicit two-role preflight/question over current bytes.

Every successful first confirmation/reconfiguration is SETUP ONLY: no planning
beads, claim, code, dispatch, branch/commit or goal cycle. End with a fresh client
session and explicit `$dom-decompose` (alias `$domestique-decompose`) or
`$dom-goal EPIC_ID` (alias `$domestique-goal EPIC_ID`) invocation to repeat.
The initiating goal request is consumed, NOT queued for automatic continuation.
Missing setup during truly noninteractive/autopilot goal execution means STOP,
not permission to write settings; interactive first-use goal entry asks INLINE
as above. Confirmed setup alone grants no goal authority.
Before later goal execution, ALL tracked/index dirtiness, including setup
changes, requires human disposition: never auto-stage, commit, stash, discard
or hide it. Guest mode retains existing local-only exclusions and uninstall
preservation. Updates use existing three-way snapshots, never reset pristine
bases to configured bytes; changed bytes invalidate confirmation. Uninstall
preserves modified roles under existing semantics; reinstall implies no consent.

## End role setup gate — continue only for an unchanged confirmed, ready pair
DOM_EOF
}

emit_codex_role_gate() { cat <<'DOM_EOF'
## Role model gate (before Beads or delegation)
An interactive first-use `$dom-goal EPIC_ID` (alias `$domestique-goal EPIC_ID`)
runs the same two-role questionnaire INLINE in its installed goal body, not a
redirect to decompose. Setup consumes the request: no task, Beads or
implementation, and no automatic continuation. The later unattended loop does
not make this entry noninteractive. Truly noninteractive/autopilot callers
without a confirmed pair STOP without persistence.
Ordinary bounded delegation must first validate the confirmed pair and native
readiness, read-only, using the shared Codex setup protocol in the installed
`$dom-decompose` / `$domestique-decompose` skill body. If unconfigured or stale,
STOP and direct the human to `$dom-decompose configure role models` (alias
`$domestique-decompose configure role models`); do not start another questionnaire
or call Beads. Do not infer the active harness from directories.
Instruction/bootstrap loading alone neither starts setup nor grants goal
authority. Generated defaults are suggestions, never confirmation. A configured
pair still requires exact local `implementer` / `reviewer` loading and current
native model/effort/override checks before dispatch, with no conflicting spawn
override and no fallback for unknown or substituted selections. Explicit
reconfiguration uses that same two-role gate and ends setup-only, with a fresh
session/reinvocation and no automatic goal continuation.
DOM_EOF
}

# The base skill is both the explicit guest-mode bootstrap (`$domestique`) and
# the implicit match for the ordinary dispatch/landing prompts. It deliberately
# does not authorize unattended epic draining; only an explicit named goal does.
emit_codex_skill() { cat <<'DOM_EOF'
---
name: domestique
description: Orchestrate a beads-backed implementer then independent reviewer workflow. Use when the user says "dispatch next ready bead", asks to dispatch or review a bead, says "land the plane", or explicitly invokes $domestique to bootstrap a guest session. Never use this skill alone to drain an epic unattended.
---

# Domestique orchestration

DOM_EOF
  emit_codex_role_gate
  cat <<'DOM_EOF'

Act as the orchestrator: plan, delegate, wait, independently review, and
adjudicate. Do not implement except for genuinely trivial one-line edits.

For each requested bead:

1. Use `bd ready`, choose one highest-priority unblocked task, and claim it.
2. Spawn exactly one `implementer` agent with the bead id, numbered brief,
   affected files, edge cases, and done criteria. Wait for it to finish.
3. Fingerprint `git diff`, `git diff --cached`, and relevant bead state.
4. Spawn exactly one fresh `reviewer` agent with the same bead and criteria.
   Wait for it to finish. Do not run implementer and reviewer concurrently.
5. Fingerprint tracked/staged diffs and bead state again. Any reviewer-caused
   delta is FAIL and an immediate stop. Report new visible untracked files;
   ignored test artifacts are allowed.
6. PASS with unchanged fingerprints: close the bead and perform only git
   actions currently authorized. Otherwise route at most the requested fix
   work back to the implementer or stop for the operator.
7. Stop and report before dispatching another bead. Only an explicit
   `$dom-goal <epic-id>` or `$domestique-goal <epic-id>` invocation lifts this rule.

In guest installs, never commit domestique state or push host-repository work.
When asked to "land the plane", file loose follow-up beads, run the final
quality gates, report status and proposed handoff commands, and obey the active
repository/user authority for commit, Dolt sync, and push.
DOM_EOF
}

emit_codex_decompose_skill() { cat <<'DOM_EOF'
---
name: domestique-decompose
description: Decompose a goal or specification into a dependency-ordered beads epic with bounded tasks. Use when explicitly invoked as $dom-decompose or $domestique-decompose or when the user asks for domestique/beads decomposition; planning only, never implementation.
---
DOM_EOF
  emit_codex_model_setup
  cat <<'DOM_EOF'

# Decompose into beads

Use the goal or specification in the invoking prompt.

1. Create one epic describing why the work exists and its high-level design.
2. Create bounded child tasks, each completable by a fresh implementer context
   in one pass and carrying explicit inputs, outputs, edge cases, and testable
   done criteria.
3. Add real dependencies so `bd ready` exposes only actionable tasks.
4. Do not implement anything.
5. Print `bd ready` plus the epic tree for human review.
DOM_EOF
}

emit_codex_goal_skill() { cat <<'DOM_EOF'
---
name: domestique-goal
description: Explicitly drain one named beads epic using domestique's bounded implementer-reviewer loop on an isolated branch. Use only when the user explicitly invokes $dom-goal or $domestique-goal with an epic id; never infer this unattended authorization.
---
DOM_EOF
  emit_codex_model_setup
  cat <<'DOM_EOF'

# Unattended epic execution

Interactive first-use goal setup runs the two-role questionnaire INLINE above,
not the ordinary-delegation redirect. Setup consumes this request with no task,
Beads or implementation; stop for fresh-session reinvocation. Truly
noninteractive/autopilot callers without a confirmed pair STOP without persistence.
Only an unchanged confirmed, ready pair can enter the unattended loop below.

An explicit `$dom-goal <epic-id>` or `$domestique-goal <epic-id>` invocation is the sole authorization
to continue between beads. It applies only to that epic and expires on
completion, a stop condition, or after 15 closed beads.
Merely loading or implicitly matching this skill is not unattended authority.

Only after the role setup gate passes without setup writes, require an explicit
epic request and check ALL tracked/index dirtiness (including configured role
files). If dirty, stop for human disposition; never auto-stage, commit, stash,
discard or hide it. Then create/switch to a dedicated epic branch.
Never work on the default branch, merge, or push. Then repeat the sequential
`$domestique` loop: one implementer, wait, fingerprint, one fresh reviewer,
wait, fingerprint, adjudicate. One passing bead per commit; never close a bead
the reviewer did not pass.

Stop immediately for: two failed reviews of one bead, any full-suite
regression, an operator decision, a required push/config/out-of-project write,
two consecutive infrastructure failures, a reviewer-caused tracked/staged or
bead-state delta, a dirty tree before a bead, or the 15-bead ceiling.

On stop or completion, run the full suite, summarize beads and commits, file
loose follow-ups, and report proposed merge/push commands without executing
them. In guest mode, local epic branches are never pushed.
DOM_EOF
}

emit_codex_goal_metadata() { cat <<'DOM_EOF'
interface:
  display_name: "Domestique Goal"
  short_description: "Drain one beads epic with gated review"
  default_prompt: "Use $domestique-goal with an explicit epic id."
policy:
  allow_implicit_invocation: false
DOM_EOF
}

# Public names reuse the same workflow bodies and native invocation policy.
emit_codex_dom_decompose_skill() {
  emit_codex_decompose_skill | sed 's/^name: domestique-decompose$/name: dom-decompose/'
}
emit_codex_dom_goal_skill() {
  emit_codex_goal_skill | sed 's/^name: domestique-goal$/name: dom-goal/'
}
emit_codex_dom_goal_metadata() {
  emit_codex_goal_metadata | sed 's/[$]domestique-goal/$dom-goal/'
}

# Normal Codex sessions receive this as a managed root AGENTS policy block.
# Guest Codex deliberately installs no root policy and instead bootstraps via
# the self-contained $domestique skill, leaving host AGENTS files untouched.
emit_codex_policy() { cat <<'DOM_EOF'
# Domestique orchestration policy (Codex)

DOM_EOF
  emit_codex_role_gate
  cat <<'DOM_EOF'

This session is the orchestrator. Use `$dom-decompose` (compatibility: `$domestique-decompose`) for planning,
then follow the `$domestique` sequential implementer → wait → reviewer → wait
loop for each bead. Stop and report between beads.

Only an explicit `$dom-goal <epic-id>` or `$domestique-goal <epic-id>` invocation authorizes unattended
epic execution. Codex's built-in `/goal` is a different product feature and
does not grant domestique's branch/commit authority by itself.
Merely loading or implicitly matching a skill is not unattended authority.

Use beads as the durable plan of record (`bd ready`, `bd remember`), write
precise numbered briefs, keep one bead in flight, and keep subagent returns
terse. Before and after review, fingerprint tracked/staged diffs and bead state;
reviewer-caused changes fail the review and stop the loop.
DOM_EOF
}

# ---------------------------------------------------------------------------
usage() {
  cat <<'EOF'
Usage: domestique.sh [TARGET_DIR] [options]

Installs domestique orchestration config into TARGET_DIR (default: current
directory). Claude is the compatibility default; Codex uses native surfaces:
  CLAUDE.md                        orchestration policy (in a managed block)
  .claude/agents/implementer.md    implementer subagent
  .claude/agents/reviewer.md       reviewer subagent
  .claude/commands/dom-decompose.md /dom-decompose (also /decompose)
  .claude/commands/dom-goal.md      /dom-goal EPIC_ID (also /goal EPIC_ID)
  AGENTS.md or AGENTS.override.md  Codex policy (normal mode, managed block)
  .codex/agents/*.toml             Codex implementer and reviewer
  .agents/skills/dom-*/            Codex $dom-decompose / $dom-goal EPIC_ID
  .agents/skills/domestique*/      Codex bootstrap and compatibility skills

Options:
  --platform <p> Select claude, codex, or both. A fresh selector-less install
                 remains Claude-only. Explicit installs add to the persisted
                 provider set; later selector-less runs update that set.
  --dry-run      Print planned changes; touch nothing.
  --with-beads   If `bd` is on PATH, initialize with safe skip flags when
                 needed. Normal mode runs setup only for selected providers;
                 guest mode uses --stealth and never runs provider setup.
  --force        Overwrite differing provider files without a .bak backup.
                 Managed policy files are always backed up before change.
  --guest        Use personal/guest mode. Claude routes policy to
                 CLAUDE.local.md; Codex leaves both root AGENTS files
                 untouched and bootstraps through `$domestique` skills.
  --no-guest     Convert an existing guest install back to normal: removes
                 the sticky guest-mode marker and prints by-hand conversion
                 guidance where needed, removes stale guest excludes, and
                 installs the normal policy destination. A no-op note if the
                 target isn't a guest install. Mutually exclusive with
                 --guest (passing both is a usage error).
  --uninstall    Remove everything domestique installed from TARGET_DIR, and
                 only that. With --platform it removes only the selected
                 projection; without it, it scans both. Modified owned files
                 are kept as <file>.uninstalled.<timestamp> unless --force.
                 Managed policy/exclude blocks and provider state are removed,
                 and only empty owned directories are pruned. Never touches
                 .beads/ (see --purge-beads). Combinable only with
                 --platform, --dry-run, --force, --purge-beads, and TARGET_DIR;
                 combining with --guest, --no-guest, or --with-beads is a
                 usage error.
  --purge-beads  Only valid with --uninstall: also `rm -rf` TARGET_DIR/.beads.
                 Without --uninstall this is a usage error.
  --help, -h     Show this help.

Behavior:
  * Existing provider files that differ are backed up to <file>.bak.<timestamp>
    before overwriting (unless --force). Identical files are left untouched.
  * CLAUDE.md: created if absent; if it has the managed markers only the
    content between them is replaced; otherwise the block is appended and all
    existing content is preserved verbatim. Always backed up before change.
  * --guest: for installing into a repo you don't own, for personal use only.
    The managed policy block is written to CLAUDE.local.md instead of
    CLAUDE.md. A tracked CLAUDE.md is never read, modified, or backed up in
    this mode. If CLAUDE.md already carries a non-guest domestique install,
    a warning is printed and CLAUDE.md is left untouched. Everything guest
    mode creates is also kept out of `git status`: a managed block is added
    to <git-common-dir>/info/exclude (resolved via `git rev-parse
    --git-common-dir`, so this works correctly from a worktree too) listing
    provider-local entries. Claude keeps its legacy `CLAUDE.local.md` and
    broad `.claude/` entries; Codex lists only exact domestique-owned leaves
    and state. `.beads/` is added only when domestique's safe guest
    initialization created it; broad backup and `.new` suffix patterns
    are never added. Pre-existing visible Codex paths remain visible across
    reruns and scoped uninstall. If an owned path is already tracked, a
    warning is printed (an exclude can't hide it). `.gitignore` itself
    is never read, written, or otherwise touched by guest mode. A non-git target
    directory prints a warning and skips the exclude step entirely (guest
    install of the rest still proceeds). Net effect: a --guest install
    followed by --uninstall returns the host repo to byte-for-byte clean
    git status, provided nothing installed was modified by hand (modified
    files are preserved as <file>.uninstalled.<timestamp> and show up as
    untracked) and no preserved `.beads/` workspace remains (use
    --purge-beads to remove one).
  * Guest mode is sticky per provider: a guest install writes a mode marker
    in that provider's domestique state. A later plain re-run detects it and
    stays in guest mode instead of silently un-guesting the install; pass
    --no-guest to convert
    back to normal on purpose.
  * Running twice in a row makes no changes on the second run.
  * Pre-existing install with no provider snapshot yet
    and a differing file: ADOPTED, not overwritten — local edits are left in
    place and the base snapshot is seeded from the pristine emitted content
    (not the edited file) so the next run 3-way-merges in upstream changes
    while keeping the edits. Use --force to overwrite verbatim instead.

Periodic updates:
  Use update.sh to fetch the latest domestique.sh from GitHub and re-run it
  against a target directory via this same merge path (see
  docs/install-upgrade-design.md §5). Run `./update.sh --help` for details.
EOF
}

TARGET_DIR=""
PLATFORM_ARG=""
PLATFORM_EXPLICIT=0
DRY_RUN=0
WITH_BEADS=0
FORCE=0
GUEST=0
GUEST_EXPLICIT=0
NO_GUEST=0
UNINSTALL=0
PURGE_BEADS=0

while [ $# -gt 0 ]; do
  case "$1" in
    --platform)
      [ "$#" -ge 2 ] || { echo "Missing argument for --platform" >&2; exit 2; }
      PLATFORM_ARG="$2"; PLATFORM_EXPLICIT=1; shift ;;
    --platform=*)
      PLATFORM_ARG="${1#--platform=}"; PLATFORM_EXPLICIT=1 ;;
    --dry-run)      DRY_RUN=1 ;;
    --with-beads)   WITH_BEADS=1 ;;
    --force)        FORCE=1 ;;
    --guest)        GUEST=1; GUEST_EXPLICIT=1 ;;
    --no-guest)     NO_GUEST=1 ;;
    --uninstall)    UNINSTALL=1 ;;
    --purge-beads)  PURGE_BEADS=1 ;;
    -h|--help)      usage; exit 0 ;;
    --) shift; break ;;
    -*) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    *)
      if [ -z "$TARGET_DIR" ]; then TARGET_DIR="$1"
      else echo "Unexpected argument: $1" >&2; exit 2; fi
      ;;
  esac
  shift
done
TARGET_DIR="${TARGET_DIR:-.}"

case "${PLATFORM_ARG:-claude}" in
  claude|codex|both) ;;
  *)
    echo "Error: --platform must be one of: claude, codex, both (got '$PLATFORM_ARG')." >&2
    usage >&2
    exit 2
    ;;
esac

if [ "$GUEST_EXPLICIT" -eq 1 ] && [ "$NO_GUEST" -eq 1 ]; then
  echo "Error: --guest and --no-guest are mutually exclusive." >&2
  usage >&2
  exit 2
fi

if [ "$PURGE_BEADS" -eq 1 ] && [ "$UNINSTALL" -eq 0 ]; then
  echo "Error: --purge-beads is only valid together with --uninstall." >&2
  usage >&2
  exit 2
fi

# configure_provider <claude|codex> — select one provider's inventory and
# snapshot namespace. Policy destination is finalized after sticky guest mode
# is resolved for that provider.
configure_provider() {
  CURRENT_PROVIDER="$1"
  SNAPSHOT_TOUCHED=0
  POLICY_DEST=""
  case "$CURRENT_PROVIDER" in
    claude)
      SNAPSHOT_DIR="$TARGET_DIR/.claude/.domestique"
      POLICY_EMITTER="emit_policy"
      POLICY_LABEL="CLAUDE.md"
      POLICY_CANDIDATES="CLAUDE.md CLAUDE.local.md"
      MANAGED_PLAIN_FILES=".claude/agents/implementer.md,.claude/agents/reviewer.md,.claude/commands/decompose.md,.claude/commands/goal.md,.claude/commands/dom-decompose.md,.claude/commands/dom-goal.md"
      ;;
    codex)
      SNAPSHOT_DIR="$TARGET_DIR/.codex/.domestique"
      POLICY_EMITTER="emit_codex_policy"
      POLICY_LABEL="AGENTS.md"
      POLICY_CANDIDATES="AGENTS.md AGENTS.override.md"
      MANAGED_PLAIN_FILES=".codex/agents/implementer.toml,.codex/agents/reviewer.toml,.agents/skills/domestique/SKILL.md,.agents/skills/domestique-decompose/SKILL.md,.agents/skills/domestique-goal/SKILL.md,.agents/skills/domestique-goal/agents/openai.yaml,.agents/skills/dom-decompose/SKILL.md,.agents/skills/dom-goal/SKILL.md,.agents/skills/dom-goal/agents/openai.yaml"
      ;;
  esac
  SNAPSHOT_BASE="$SNAPSHOT_DIR/base"
  MODE_MARKER="$SNAPSHOT_DIR/mode"
}

# resolve_provider_mode — apply explicit guest/no-guest selection or the
# provider's own sticky marker. Different installed providers may therefore
# retain different guest modes on the same selector-less rerun.
resolve_provider_mode() {
  local marker_content=""
  GUEST="$REQUESTED_GUEST"
  if [ -e "$MODE_MARKER" ]; then
    marker_content="$(cat "$MODE_MARKER" 2>/dev/null || true)"
    case "$marker_content" in
      guest)
        if [ "$NO_GUEST" -eq 1 ]; then
          if [ "$DRY_RUN" -eq 1 ]; then
            note_dry "remove mode marker $MODE_MARKER (--no-guest)"
          else
            rm -f "$MODE_MARKER"
          fi
          echo "domestique: converting guest install for $CURRENT_PROVIDER in $TARGET_DIR to normal mode." >&2
          if [ "$CURRENT_PROVIDER" = "claude" ]; then
            echo "  CLAUDE.local.md is left in place; fold any customizations into CLAUDE.md or remove it by hand." >&2
          else
            echo '  Skills and agents are retained; normal mode now adds the active root AGENTS policy block.' >&2
          fi
          GUEST=0
        elif [ "$GUEST_EXPLICIT" -eq 0 ]; then
          GUEST=1
          echo "Note: existing $CURRENT_PROVIDER guest install detected in $TARGET_DIR — staying in guest mode. Pass --no-guest to convert." >&2
        fi
        ;;
      *)
        echo "Warning: $MODE_MARKER has unexpected content '$marker_content' (expected 'guest') — treating $CURRENT_PROVIDER as normal." >&2
        GUEST=0
        ;;
    esac
  elif [ "$NO_GUEST" -eq 1 ]; then
    echo "Note: --no-guest passed but no $CURRENT_PROVIDER guest marker was found — proceeding normally." >&2
    GUEST=0
  fi

  case "$CURRENT_PROVIDER:$GUEST" in
    claude:1)
      POLICY_DEST="CLAUDE.local.md"
      POLICY_LABEL="$POLICY_DEST"
      if [ -e "$TARGET_DIR/CLAUDE.md" ] && grep -qxF "$MARKER_BEGIN" "$TARGET_DIR/CLAUDE.md" 2>/dev/null; then
        echo "Warning: a normal domestique install exists in $TARGET_DIR/CLAUDE.md — left untouched; guest policy goes to $TARGET_DIR/$POLICY_DEST." >&2
      fi
      ;;
    claude:0)
      POLICY_DEST="CLAUDE.md"
      POLICY_LABEL="$POLICY_DEST"
      ;;
    codex:1)
      # No additive root instruction file exists in Codex. Skills-only guest
      # mode is intentional and leaves both host AGENTS files byte-untouched.
      POLICY_DEST=""
      POLICY_LABEL="skills-only"
      ;;
    codex:0)
      if [ -e "$TARGET_DIR/AGENTS.override.md" ]; then
        POLICY_DEST="AGENTS.override.md"
      else
        POLICY_DEST="AGENTS.md"
      fi
      POLICY_LABEL="$POLICY_DEST"
      ;;
  esac

  if [ -n "$POLICY_DEST" ]; then
    POLICY_SNAPSHOT="$SNAPSHOT_BASE/$POLICY_DEST.block"
  else
    POLICY_SNAPSHOT=""
  fi
}

# Record the exact Codex paths that domestique may hide in guest mode.  The
# file is written for normal installs too, so a later normal -> guest
# conversion can distinguish domestique-created files from host files that
# merely happened to exist before installation.  Older managed exclude blocks
# are accepted as a one-time migration source.
codex_exclude_was_owned() {
  local rel="$1" ownership="$TARGET_DIR/.codex/.domestique/guest-excludes"
  if [ -e "$ownership" ] && grep -qxF "$rel" "$ownership" 2>/dev/null; then
    return 0
  fi

  local common_dir="" exclude_file
  if command -v git >/dev/null 2>&1; then
    common_dir="$(git -C "$TARGET_DIR" rev-parse --git-common-dir 2>/dev/null)" || common_dir=""
    if [ -n "$common_dir" ]; then
      case "$common_dir" in /*) : ;; *) common_dir="$TARGET_DIR/$common_dir" ;; esac
    fi
  fi
  [ -z "$common_dir" ] && [ -d "$TARGET_DIR/.git" ] && common_dir="$TARGET_DIR/.git"
  [ -n "$common_dir" ] || return 1
  exclude_file="$common_dir/info/exclude"
  [ -e "$exclude_file" ] || return 1
  awk -v beginm="$GITEXCLUDE_MARKER_BEGIN" -v endm="$GITEXCLUDE_MARKER_END" -v wanted="$rel" '
    $0 == beginm && !seen { seen=1; inblock=1; next }
    inblock && $0 == endm { exit found ? 0 : 1 }
    inblock && $0 == wanted { found=1 }
    END { exit found ? 0 : 1 }
  ' "$exclude_file"
}

write_codex_guest_ownership() {
  local ownership="$TARGET_DIR/.codex/.domestique/guest-excludes"
  local staged="$TMPDIR_WORK/codex_guest_excludes"
  {
    [ "${CODEX_PREEXIST_IMPL:-0}" -eq 1 ] || printf '.codex/agents/implementer.toml\n'
    [ "${CODEX_PREEXIST_REVIEWER:-0}" -eq 1 ] || printf '.codex/agents/reviewer.toml\n'
    printf '.codex/.domestique/\n'
    [ "${CODEX_PREEXIST_BASE_SKILL:-0}" -eq 1 ] || printf '.agents/skills/domestique/SKILL.md\n'
    [ "${CODEX_PREEXIST_DECOMPOSE_SKILL:-0}" -eq 1 ] || printf '.agents/skills/domestique-decompose/SKILL.md\n'
    [ "${CODEX_PREEXIST_GOAL_SKILL:-0}" -eq 1 ] || printf '.agents/skills/domestique-goal/SKILL.md\n'
    [ "${CODEX_PREEXIST_GOAL_META:-0}" -eq 1 ] || printf '.agents/skills/domestique-goal/agents/openai.yaml\n'
    [ "${CODEX_PREEXIST_DOM_DECOMPOSE_SKILL:-0}" -eq 1 ] || printf '.agents/skills/dom-decompose/SKILL.md\n'
    [ "${CODEX_PREEXIST_DOM_GOAL_SKILL:-0}" -eq 1 ] || printf '.agents/skills/dom-goal/SKILL.md\n'
    [ "${CODEX_PREEXIST_DOM_GOAL_META:-0}" -eq 1 ] || printf '.agents/skills/dom-goal/agents/openai.yaml\n'
  } > "$staged"
  if [ "$DRY_RUN" -eq 1 ]; then
    note_dry "record exact Codex guest ownership -> $ownership"
  else
    mkdir -p "$(dirname "$ownership")"
    [ -e "$ownership" ] && cmp -s "$staged" "$ownership" || cp "$staged" "$ownership"
  fi
}

write_provider_manifest() {
  [ "$SNAPSHOT_TOUCHED" -eq 1 ] || return 0
  if [ "$DRY_RUN" -eq 1 ]; then
    note_dry "write/update manifest -> $SNAPSHOT_DIR/manifest"
  else
    mkdir -p "$SNAPSHOT_DIR"
    write_manifest
  fi
}

install_current_provider() {
  echo "domestique: platform=$CURRENT_PROVIDER mode=$([ "$GUEST" -eq 1 ] && printf guest || printf normal) policy=${POLICY_DEST:-skills-only}"

  if [ -n "$POLICY_DEST" ]; then
    install_claude_md "$TARGET_DIR/$POLICY_DEST" "$([ "$GUEST" -eq 1 ] && printf guest || printf normal)" "$POLICY_EMITTER"
  fi

  case "$CURRENT_PROVIDER" in
    claude)
      install_plain "$TARGET_DIR/.claude/agents/implementer.md" emit_implementer
      install_plain "$TARGET_DIR/.claude/agents/reviewer.md" emit_reviewer
      install_plain "$TARGET_DIR/.claude/commands/decompose.md" emit_decompose
      install_plain "$TARGET_DIR/.claude/commands/goal.md" emit_goal
      install_plain "$TARGET_DIR/.claude/commands/dom-decompose.md" emit_decompose
      install_plain "$TARGET_DIR/.claude/commands/dom-goal.md" emit_goal
      ;;
    codex)
      install_plain "$TARGET_DIR/.codex/agents/implementer.toml" emit_codex_implementer
      install_plain "$TARGET_DIR/.codex/agents/reviewer.toml" emit_codex_reviewer
      install_plain "$TARGET_DIR/.agents/skills/domestique/SKILL.md" emit_codex_skill
      install_plain "$TARGET_DIR/.agents/skills/domestique-decompose/SKILL.md" emit_codex_decompose_skill
      install_plain "$TARGET_DIR/.agents/skills/domestique-goal/SKILL.md" emit_codex_goal_skill
      install_plain "$TARGET_DIR/.agents/skills/domestique-goal/agents/openai.yaml" emit_codex_goal_metadata
      install_plain "$TARGET_DIR/.agents/skills/dom-decompose/SKILL.md" emit_codex_dom_decompose_skill
      install_plain "$TARGET_DIR/.agents/skills/dom-goal/SKILL.md" emit_codex_dom_goal_skill
      install_plain "$TARGET_DIR/.agents/skills/dom-goal/agents/openai.yaml" emit_codex_dom_goal_metadata
      write_codex_guest_ownership
      ;;
  esac

  if [ "$GUEST" -eq 1 ]; then
    if [ "$DRY_RUN" -eq 1 ]; then
      note_dry "write mode marker -> $MODE_MARKER (guest)"
    else
      mkdir -p "$(dirname "$MODE_MARKER")"
      printf 'guest\n' > "$MODE_MARKER"
    fi
  fi
  write_provider_manifest
}

persist_platform_set() {
  local state_dir state_file old
  [ "$CONFLICT_OCCURRED" -eq 0 ] || return 0
  for state_dir in "$TARGET_DIR/.claude/.domestique" "$TARGET_DIR/.codex/.domestique"; do
    case "$state_dir" in
      "$TARGET_DIR/.claude/.domestique") [ "$SELECT_CLAUDE" -eq 1 ] || continue ;;
      "$TARGET_DIR/.codex/.domestique") [ "$SELECT_CODEX" -eq 1 ] || continue ;;
    esac
    state_file="$state_dir/platforms"
    old="$(cat "$state_file" 2>/dev/null || true)"
    [ "$old" = "$PLATFORM_SET" ] && continue
    if [ "$DRY_RUN" -eq 1 ]; then
      note_dry "persist platform set '$PLATFORM_SET' -> $state_file"
    else
      mkdir -p "$state_dir"
      printf '%s\n' "$PLATFORM_SET" > "$state_file"
    fi
  done
}

if [ "$UNINSTALL" -eq 1 ]; then
  if [ "$GUEST_EXPLICIT" -eq 1 ] || [ "$NO_GUEST" -eq 1 ] || [ "$WITH_BEADS" -eq 1 ]; then
    echo "Error: --uninstall is only combinable with --platform, --dry-run, --force, --purge-beads, and TARGET_DIR." >&2
    usage >&2
    exit 2
  fi
fi

if [ ! -d "$TARGET_DIR" ]; then
  echo "Target directory does not exist: $TARGET_DIR" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Platform selection. Provider-owned `platforms` files all carry the same
# canonical installed set. Explicit installs add to that set; selector-less
# reruns use it. A legacy Claude state dir without a platforms file counts as
# Claude, while a genuinely fresh selector-less install remains Claude-only.
# ---------------------------------------------------------------------------
SELECT_CLAUDE=0
SELECT_CODEX=0
PERSISTED_CLAUDE=0
PERSISTED_CODEX=0

read_platform_state() {
  local statefile="$1" value
  [ -e "$statefile" ] || return 0
  value="$(cat "$statefile" 2>/dev/null || true)"
  case "$value" in
    claude) PERSISTED_CLAUDE=1 ;;
    codex) PERSISTED_CODEX=1 ;;
    both) PERSISTED_CLAUDE=1; PERSISTED_CODEX=1 ;;
    *) echo "Warning: ignoring invalid domestique platform state '$value' in $statefile." >&2 ;;
  esac
}

read_platform_state "$TARGET_DIR/.claude/.domestique/platforms"
read_platform_state "$TARGET_DIR/.codex/.domestique/platforms"

# Backfill provider state that predates the platforms marker.
if [ "$PERSISTED_CLAUDE" -eq 0 ] && [ -d "$TARGET_DIR/.claude/.domestique" ]; then
  PERSISTED_CLAUDE=1
fi
if [ "$PERSISTED_CODEX" -eq 0 ] && [ -d "$TARGET_DIR/.codex/.domestique" ]; then
  PERSISTED_CODEX=1
fi

if [ "$PLATFORM_EXPLICIT" -eq 1 ]; then
  SELECT_CLAUDE="$PERSISTED_CLAUDE"
  SELECT_CODEX="$PERSISTED_CODEX"
  case "$PLATFORM_ARG" in
    claude) SELECT_CLAUDE=1 ;;
    codex) SELECT_CODEX=1 ;;
    both) SELECT_CLAUDE=1; SELECT_CODEX=1 ;;
  esac
elif [ "$PERSISTED_CLAUDE" -eq 1 ] || [ "$PERSISTED_CODEX" -eq 1 ]; then
  SELECT_CLAUDE="$PERSISTED_CLAUDE"
  SELECT_CODEX="$PERSISTED_CODEX"
else
  SELECT_CLAUDE=1
fi

if [ "$SELECT_CLAUDE" -eq 1 ] && [ "$SELECT_CODEX" -eq 1 ]; then
  PLATFORM_SET="both"
elif [ "$SELECT_CODEX" -eq 1 ]; then
  PLATFORM_SET="codex"
else
  PLATFORM_SET="claude"
fi

REQUESTED_GUEST="$GUEST"

TS="$(date +%Y%m%d%H%M%S)"
TMPDIR_WORK="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_WORK"' EXIT

# Summary accumulators.
SUM_CREATED=()
SUM_UPDATED=()
SUM_BACKEDUP=()
SUM_SKIPPED=()
SUM_MERGED=()
SUM_CONFLICT=()
SUM_ADOPTED=()
# --uninstall-only accumulators.
SUM_REMOVED=()
SUM_KEPT=()

# Set to 1 if any file ended in a merge conflict or hard merge error this run;
# drives the final non-zero exit (see docs/install-upgrade-design.md §4).
CONFLICT_OCCURRED=0

note_dry() { [ "$DRY_RUN" -eq 1 ] && echo "  [dry-run] $*"; return 0; }

# print_group <label> <item...> — used by both the install and uninstall
# summary printers. Hoisted here (from its original position just above the
# install summary) so do_uninstall() can call it too.
print_group() {
  local label="$1"; shift
  [ "$#" -eq 0 ] && return 0
  echo "  $label:"
  local item
  for item in "$@"; do echo "    - $item"; done
}

# Provider configuration is swapped before each install projection. Initialize
# with Claude values for compatibility; configure_provider replaces them before
# every selected provider is installed.
CURRENT_PROVIDER="claude"
POLICY_DEST="CLAUDE.md"
POLICY_EMITTER="emit_policy"
POLICY_LABEL="CLAUDE.md"
POLICY_CANDIDATES="CLAUDE.md CLAUDE.local.md"
MANAGED_PLAIN_FILES=".claude/agents/implementer.md,.claude/agents/reviewer.md,.claude/commands/decompose.md,.claude/commands/goal.md,.claude/commands/dom-decompose.md,.claude/commands/dom-goal.md"

# ---------------------------------------------------------------------------
# Base snapshot / manifest. The existing merge implementation is provider
# neutral once these paths and inventory values are configured.
# ---------------------------------------------------------------------------
SNAPSHOT_DIR="$TARGET_DIR/.claude/.domestique"
SNAPSHOT_BASE="$SNAPSHOT_DIR/base"
# Policy managed-block snapshot is keyed by destination filename (CLAUDE.md
# vs CLAUDE.local.md under --guest) so a --guest run never reads or rewrites
# the plain run's merge base, and vice versa. See docs/install-upgrade-design.md.
POLICY_SNAPSHOT="$SNAPSHOT_BASE/$POLICY_DEST.block"
SNAPSHOT_TOUCHED=0

# rel_to_base <dest> -> absolute path under SNAPSHOT_BASE mirroring <dest>'s
# path relative to TARGET_DIR, 1:1 (including the .claude/ prefix — no
# managed file lives under .claude/.domestique/, so this never recurses).
rel_to_base() {
  local dest="$1"
  printf '%s' "$SNAPSHOT_BASE/${dest#"$TARGET_DIR"/}"
}

# snapshot_plain <dest> <content-file>
# Record the pristine emitted content as the future merge base. Call only
# after <dest> was actually created/overwritten with <content-file>'s bytes
# (never on an identical-skip — the snapshot is already correct there).
snapshot_plain() {
  local dest="$1" content="$2" basepath
  basepath="$(rel_to_base "$dest")"
  SNAPSHOT_TOUCHED=1
  if [ "$DRY_RUN" -eq 1 ]; then
    note_dry "snapshot base -> $basepath"
    return 0
  fi
  mkdir -p "$(dirname "$basepath")"
  cp "$content" "$basepath"
}

# snapshot_claude_block <content-file>
# Record the managed block BODY (no marker lines) as the future merge base
# for the policy file at $POLICY_DEST (CLAUDE.md, or CLAUDE.local.md under
# --guest). Call only after $POLICY_DEST was actually created/updated.
snapshot_claude_block() {
  local content="$1" basepath="$POLICY_SNAPSHOT"
  SNAPSHOT_TOUCHED=1
  if [ "$DRY_RUN" -eq 1 ]; then
    note_dry "snapshot base -> $basepath"
    return 0
  fi
  mkdir -p "$(dirname "$basepath")"
  cp "$content" "$basepath"
}

# managed_files_list — provider inventory plus every sound managed policy
# destination still on disk. The current policy destination is included under
# dry-run even before it exists.
managed_files_list() {
  local out="$MANAGED_PLAIN_FILES" policyfile include
  for policyfile in $POLICY_CANDIDATES; do
    include=0
    if [ -n "$POLICY_DEST" ] && [ "$policyfile" = "$POLICY_DEST" ]; then
      include=1
    elif [ -e "$TARGET_DIR/$policyfile" ] && grep -qxF "$MARKER_BEGIN" "$TARGET_DIR/$policyfile" 2>/dev/null; then
      include=1
    fi
    [ "$include" -eq 1 ] && out="$out,$policyfile"
  done
  printf '%s' "$out"
}

# write_manifest — flat key=value manifest describing the snapshot.
write_manifest() {
  local manifest="$SNAPSHOT_DIR/manifest" ref sha
  ref="$(git -C "$(dirname "$0")" rev-parse --short HEAD 2>/dev/null)" || ref="unknown"
  [ -z "$ref" ] && ref="unknown"
  if command -v sha256sum >/dev/null 2>&1; then
    sha="$(sha256sum "$0" 2>/dev/null | awk '{print $1}')" || sha=""
  elif command -v shasum >/dev/null 2>&1; then
    sha="$(shasum -a 256 "$0" 2>/dev/null | awk '{print $1}')" || sha=""
  else
    sha=""
  fi
  [ -z "$sha" ] && sha="unavailable"
  {
    printf 'snapshot_format=1\n'
    printf 'platform=%s\n' "$CURRENT_PROVIDER"
    printf 'domestique_version=%s\n' "$DOMESTIQUE_VERSION"
    printf 'installed_ref=%s\n' "$ref"
    printf 'installed_at=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'script_sha256=%s\n' "$sha"
    printf 'files=%s\n' "$(managed_files_list)"
  } > "$manifest"
}

# install_plain <dest> <emitter-fn>
# Missing -> write. Identical -> skip. --force -> overwrite verbatim, no merge.
# Differs (no --force):
#   - base snapshot exists -> 3-way merge (git merge-file); clean merge
#     overwrites dest and advances the snapshot; conflict/error leaves dest
#     untouched, writes dest.new + a .bak, and does not advance the snapshot.
#   - no base snapshot (legacy/pre-snapshot install) -> ADOPT: seed the base
#     snapshot from the PRISTINE freshly-emitted content (not the edited
#     on-disk file), leave the live file unchanged (no .bak, no overwrite).
#     This preserves any local edits now, and sets up the NEXT run to
#     3-way-merge against a vanilla base, so upstream gets applied and
#     local edits are preserved from then on. (Seeding base from the
#     current/edited content instead would make ours == base whenever no
#     further edit is made, causing the next merge to silently drop it.)
# See docs/install-upgrade-design.md §2.
install_plain() {
  local dest="$1" emitter="$2" staged
  staged="$TMPDIR_WORK/staged"
  "$emitter" > "$staged"

  if [ ! -e "$dest" ]; then
    if [ "$DRY_RUN" -eq 1 ]; then
      note_dry "create $dest"
    else
      mkdir -p "$(dirname "$dest")"
      cp "$staged" "$dest"
    fi
    SUM_CREATED+=("$dest")
    snapshot_plain "$dest" "$staged"
    return 0
  fi

  if cmp -s "$staged" "$dest"; then
    # Identical to the fresh emit — no change needed, but if there's no base
    # snapshot yet (legacy install), seed it now so future runs have a base
    # to merge against.
    local ident_basepath
    ident_basepath="$(rel_to_base "$dest")"
    if [ ! -e "$ident_basepath" ]; then
      snapshot_plain "$dest" "$staged"
    fi
    SUM_SKIPPED+=("$dest (identical)")
    return 0
  fi

  # Differs.
  if [ "$FORCE" -eq 1 ]; then
    if [ "$DRY_RUN" -eq 1 ]; then
      note_dry "overwrite $dest (--force, no backup)"
    else
      cp "$staged" "$dest"
    fi
    SUM_UPDATED+=("$dest (forced)")
    snapshot_plain "$dest" "$staged"
    return 0
  fi

  local basepath
  basepath="$(rel_to_base "$dest")"

  if [ ! -e "$basepath" ]; then
    # Legacy fallback: no prior snapshot to merge against. ADOPT rather than
    # clobber — leave the live file untouched (no overwrite, no .bak) and
    # seed the base snapshot from the freshly emitted (pristine, un-edited)
    # content, NOT the current on-disk content. This matters: base must
    # represent the *vanilla* baseline so that on the next run,
    # diff(base, ours) reveals the user's local edits (preserved) and
    # diff(base, theirs) reveals the real upstream change (applied). Seeding
    # base from the edited on-disk content instead would make ours == base
    # whenever no further edit has been made, causing git merge-file to
    # take theirs wholesale and silently drop the very edit we're trying
    # to save.
    note_dry "adopt $dest (no base snapshot; seed base from pristine emit, leave file unchanged; re-run to merge upstream)"
    snapshot_plain "$dest" "$staged"
    SUM_ADOPTED+=("$dest (local edits preserved; re-run to merge upstream)")
    return 0
  fi

  # 3-way merge: ours=$dest, base=$basepath, theirs=$staged.
  local merged rc=0
  merged="$TMPDIR_WORK/merged"
  git merge-file -p --diff3 \
    -L "yours (local edits)" -L "base (last installed)" -L "upstream (new domestique)" \
    "$dest" "$basepath" "$staged" > "$merged" || rc=$?

  if [ "$rc" -eq 0 ]; then
    if [ "$DRY_RUN" -eq 1 ]; then
      note_dry "merge $dest (clean)"
    else
      cp "$merged" "$dest"
    fi
    SUM_MERGED+=("$dest")
    snapshot_plain "$dest" "$staged"
    return 0
  fi

  # Conflict (rc = number of conflicted hunks, 1..127) or hard error (rc>=128).
  # Either way: leave the live file untouched, do not advance the snapshot,
  # and force a non-zero exit for the whole run.
  CONFLICT_OCCURRED=1
  local newfile="$dest.new" backup="$dest.bak.$TS" kind="conflict"
  if [ "$rc" -ge 128 ]; then
    kind="error"
    echo "Error: git merge-file failed unexpectedly for $dest (exit $rc)." >&2
  else
    echo "Warning: merge conflict in $dest ($rc hunk(s)) — see $newfile" >&2
  fi
  if [ "$DRY_RUN" -eq 1 ]; then
    note_dry "merge $dest ($kind) — would write $newfile, back up $dest -> $backup, leave $dest untouched"
  else
    cp "$merged" "$newfile"
    cp "$dest" "$backup"
    SUM_BACKEDUP+=("$backup")
  fi
  SUM_CONFLICT+=("$dest ($kind; see $newfile)")
}

# markers_sane <file>
# Checks the domestique managed-block markers (MARKER_BEGIN/MARKER_END) in
# <file> for structural soundness before install/uninstall trust them to
# delimit a single well-formed block. Prints "<status> <begin-count>
# <end-count>" to stdout; status is one of:
#   none       - neither marker present
#   ok         - exactly one of each, BEGIN before END
#   half       - exactly one marker present, its pair missing
#   dup_begin  - BEGIN appears more than once
#   dup_end    - END appears more than once
#   inverted   - one of each present, but END appears before BEGIN
# Any status other than none/ok means the naive BEGIN..END awk strip/splice
# would silently touch the wrong span (data loss) - callers must refuse.
markers_sane() {
  local file="$1" bc ec bl el
  bc=$(grep -cxF "$MARKER_BEGIN" "$file" 2>/dev/null || true)
  ec=$(grep -cxF "$MARKER_END" "$file" 2>/dev/null || true)
  bc="${bc:-0}"; ec="${ec:-0}"
  if [ "$bc" -eq 0 ] && [ "$ec" -eq 0 ]; then
    echo "none $bc $ec"; return 0
  fi
  if [ "$bc" -gt 1 ]; then
    echo "dup_begin $bc $ec"; return 0
  fi
  if [ "$ec" -gt 1 ]; then
    echo "dup_end $bc $ec"; return 0
  fi
  if [ "$bc" -eq 0 ] || [ "$ec" -eq 0 ]; then
    echo "half $bc $ec"; return 0
  fi
  bl=$(grep -nxF "$MARKER_BEGIN" "$file" | head -1 | cut -d: -f1)
  el=$(grep -nxF "$MARKER_END" "$file" | head -1 | cut -d: -f1)
  if [ "$bl" -gt "$el" ]; then
    echo "inverted $bc $ec"; return 0
  fi
  echo "ok $bc $ec"
}

# install_claude_md <dest>
# Missing/no-markers/half-marker -> unchanged from before (create, append,
# refuse). Has both markers, block differs:
#   - --force -> replace block wholesale, no merge, advance snapshot.
#   - base block snapshot exists -> 3-way merge the BLOCK BODY (git
#     merge-file); clean merge splices the merged body back between fresh
#     markers, preserving everything outside the markers byte-for-byte, and
#     advances the snapshot; conflict/error leaves dest untouched, writes
#     dest.new (full file, conflict-marked block spliced in) + a .bak, and
#     does not advance the snapshot.
#   - no base snapshot (legacy/pre-snapshot install) -> ADOPT: seed the
#     block snapshot from the PRISTINE emitted policy body (not the
#     current/edited on-disk block), leave the file unchanged (no
#     overwrite, no .bak); re-run to merge upstream.
# See docs/install-upgrade-design.md §3.
install_claude_md() {
  local dest="$1" mode="${2:-normal}" emitter="${3:-emit_policy}"
  local blk="$TMPDIR_WORK/block" result="$TMPDIR_WORK/claude_result"
  local policybody="$TMPDIR_WORK/policybody"

  "$emitter" "$mode" > "$policybody"

  # Build the managed block: BEGIN marker + verbatim policy + END marker.
  {
    printf '%s\n' "$MARKER_BEGIN"
    cat "$policybody"
    printf '%s\n' "$MARKER_END"
  } > "$blk"

  # Case A: no CLAUDE.md -> create it as just the managed block.
  if [ ! -e "$dest" ]; then
    if [ "$DRY_RUN" -eq 1 ]; then
      note_dry "create $dest (managed block only)"
    else
      cp "$blk" "$dest"
    fi
    SUM_CREATED+=("$dest")
    snapshot_claude_block "$policybody"
    return 0
  fi

  # Refuse to guess on a structurally unsound managed-block file: a
  # half-marked file (one marker without its pair), duplicate BEGIN/END
  # markers, or END appearing before BEGIN would all make the extract/splice
  # below act on the wrong span - swallowing or misplacing user content is
  # data loss. Leave it untouched and bail.
  local marker_status marker_bc marker_ec
  read -r marker_status marker_bc marker_ec < <(markers_sane "$dest")
  case "$marker_status" in
    none|ok) ;;
    half)
      if [ "$marker_bc" -eq 0 ]; then
        echo "Error: $dest has a '$MARKER_END' marker but no matching '$MARKER_BEGIN'." >&2
      else
        echo "Error: $dest has a '$MARKER_BEGIN' marker but no matching '$MARKER_END'." >&2
      fi
      echo "       Refusing to edit a half-marked file. Fix it by hand and re-run." >&2
      exit 1
      ;;
    dup_begin)
      echo "Error: $dest has more than one '$MARKER_BEGIN' marker ($marker_bc occurrences)." >&2
      echo "       Refusing to edit a file with duplicate markers. Fix it by hand and re-run." >&2
      exit 1
      ;;
    dup_end)
      echo "Error: $dest has more than one '$MARKER_END' marker ($marker_ec occurrences)." >&2
      echo "       Refusing to edit a file with duplicate markers. Fix it by hand and re-run." >&2
      exit 1
      ;;
    inverted)
      echo "Error: $dest has a '$MARKER_END' marker appearing before its '$MARKER_BEGIN' marker." >&2
      echo "       Refusing to edit a file with markers in the wrong order. Fix it by hand and re-run." >&2
      exit 1
      ;;
  esac

  # Case B: has both markers -> replace only the region between them, verbatim rest.
  # marker_status is already known-"ok" here (none/half/dup_*/inverted all
  # exited above), so dispatch on it rather than re-testing with a substring
  # grep that could disagree with markers_sane's whole-line semantics.
  if [ "$marker_status" = "ok" ]; then
    # Extract the current on-disk block body (ours-block) for a potential
    # 3-way merge, and build the wholesale-replace result (today's behavior)
    # for the no-merge-needed / legacy / --force paths.
    local oursblock="$TMPDIR_WORK/oursblock"
    awk -v beginm="$MARKER_BEGIN" -v endm="$MARKER_END" '
      $0 == beginm && !seen { seen=1; inblock=1; next }
      inblock && $0 == endm { inblock=0; next }
      inblock { print }
    ' "$dest" > "$oursblock"

    awk -v beginm="$MARKER_BEGIN" -v endm="$MARKER_END" -v blockfile="$blk" '
      BEGIN { while ((getline line < blockfile) > 0) block = block line ORS }
      $0 == beginm && !seen { seen=1; inblock=1; printf "%s", block; next }
      inblock && $0 == endm { inblock=0; next }
      inblock { next }
      { print }
    ' "$dest" > "$result"

    # If the block body is already current (no user edit, or already up to
    # date), the wholesale-replace result is byte-identical to $dest already
    # — no merge needed. Fall through to the idempotency guard below.
    if ! cmp -s "$oursblock" "$policybody"; then
      if [ "$FORCE" -eq 1 ]; then
        : # wholesale replace (already computed in $result above), no merge.
      else
        local basepath="$POLICY_SNAPSHOT"
        if [ -e "$basepath" ]; then
          # 3-way merge the block body: ours=$oursblock, base=$basepath,
          # theirs=$policybody.
          local mergedblock rc=0
          mergedblock="$TMPDIR_WORK/mergedblock"
          git merge-file -p --diff3 \
            -L "yours (local edits)" -L "base (last installed)" -L "upstream (new domestique)" \
            "$oursblock" "$basepath" "$policybody" > "$mergedblock" || rc=$?

          if [ "$rc" -eq 0 ]; then
            # Clean merge: splice the merged block body back between fresh
            # markers, preserving everything outside the markers verbatim.
            awk -v beginm="$MARKER_BEGIN" -v endm="$MARKER_END" -v blockfile="$mergedblock" '
              BEGIN { while ((getline line < blockfile) > 0) block = block line ORS }
              $0 == beginm && !seen { seen=1; inblock=1; print beginm; printf "%s", block; next }
              inblock && $0 == endm { inblock=0; print endm; next }
              inblock { next }
              { print }
            ' "$dest" > "$result"

            if cmp -s "$result" "$dest"; then
              SUM_SKIPPED+=("$dest (managed block already current)")
              return 0
            fi

            local backup="$dest.bak.$TS"
            if [ "$DRY_RUN" -eq 1 ]; then
              note_dry "backup $dest -> $backup, then merge managed block (clean)"
            else
              cp "$dest" "$backup"
              cp "$result" "$dest"
            fi
            SUM_BACKEDUP+=("$backup")
            SUM_MERGED+=("$dest ($POLICY_LABEL block)")
            snapshot_claude_block "$policybody"
            return 0
          fi

          # Conflict (rc = number of conflicted hunks, 1..127) or hard error
          # (rc>=128): leave the live file untouched, do not advance the
          # snapshot, write the conflict-marked full file to dest.new, back
          # up the current live file, force a non-zero exit for the run.
          CONFLICT_OCCURRED=1
          local newfile="$dest.new" backup2="$dest.bak.$TS" kind="conflict"
          if [ "$rc" -ge 128 ]; then
            kind="error"
            echo "Error: git merge-file failed unexpectedly for $dest block (exit $rc)." >&2
          else
            echo "Warning: merge conflict in $dest managed block ($rc hunk(s)) — see $newfile" >&2
          fi

          local conflictresult="$TMPDIR_WORK/conflict_result"
          awk -v beginm="$MARKER_BEGIN" -v endm="$MARKER_END" -v blockfile="$mergedblock" '
            BEGIN { while ((getline line < blockfile) > 0) block = block line ORS }
            $0 == beginm && !seen { seen=1; inblock=1; print beginm; printf "%s", block; next }
            inblock && $0 == endm { inblock=0; print endm; next }
            inblock { next }
            { print }
          ' "$dest" > "$conflictresult"

          if [ "$DRY_RUN" -eq 1 ]; then
            note_dry "merge $dest block ($kind) — would write $newfile, back up $dest -> $backup2, leave $dest untouched"
          else
            cp "$conflictresult" "$newfile"
            cp "$dest" "$backup2"
            SUM_BACKEDUP+=("$backup2")
          fi
          SUM_CONFLICT+=("$dest ($kind; see $newfile)")
          return 0
        fi
        # else: no base snapshot -> ADOPT (same rationale as install_plain):
        # seed CLAUDE.md.block from the PRISTINE emitted policy body (not
        # the current on-disk block, which carries the user's edit), and
        # leave the live file unchanged (no overwrite, no .bak). Base must
        # be the vanilla baseline so the next run's merge sees the local
        # edit as ours-vs-base (preserved) and any real upstream change as
        # theirs-vs-base (applied) — seeding from the edited block instead
        # would make ours == base and cause the next merge to silently
        # discard the edit.
        note_dry "adopt $dest (no base snapshot for managed block; seed base from pristine emit, leave file unchanged; re-run to merge upstream)"
        snapshot_claude_block "$policybody"
        SUM_ADOPTED+=("$dest (local edits preserved; re-run to merge upstream)")
        return 0
      fi
    fi
  else
    # Case C: no markers -> append the block, preserving existing bytes verbatim.
    # Add a single newline first only if the file does not already end in one,
    # so the BEGIN marker starts on its own line.
    cp "$dest" "$result"
    if [ -s "$result" ] && [ "$(tail -c 1 "$result" | wc -l)" -eq 0 ]; then
      printf '\n' >> "$result"
    fi
    cat "$blk" >> "$result"
  fi

  # Idempotency guard: if nothing would change, skip (no backup, no write).
  if cmp -s "$result" "$dest"; then
    # Already current — but if there's no block base snapshot yet (legacy
    # install), seed it now so future runs have a base to merge against.
    if [ ! -e "$POLICY_SNAPSHOT" ]; then
      snapshot_claude_block "$policybody"
    fi
    SUM_SKIPPED+=("$dest (managed block already current)")
    return 0
  fi

  local backup="$dest.bak.$TS"
  if [ "$DRY_RUN" -eq 1 ]; then
    note_dry "backup $dest -> $backup, then update managed block"
  else
    cp "$dest" "$backup"        # CLAUDE.md is ALWAYS backed up before change.
    cp "$result" "$dest"
  fi
  SUM_BACKEDUP+=("$backup")
  SUM_UPDATED+=("$dest (managed block)")
  snapshot_claude_block "$policybody"
}

# install_git_exclude <target-dir>
# Guest-mode only: hide everything domestique creates from git via a managed
# block in the target repo's git exclude file (.git/info/exclude — a
# local-only ignore file, unlike .gitignore, so it is never committed).
# Resolves the exclude file via `git -C <target> rev-parse --git-common-dir`
# so worktrees/submodules land in the shared common git dir; falls back to
# <target>/.git/info/exclude if git isn't on PATH but .git is a real dir;
# warns and skips (without failing) if the target isn't a git repo at all.
install_git_exclude() {
  local target="$1" common_dir="" exclude_file
  local block="$TMPDIR_WORK/exclude_block" result="$TMPDIR_WORK/exclude_result"

  if command -v git >/dev/null 2>&1; then
    common_dir="$(git -C "$target" rev-parse --git-common-dir 2>/dev/null)" || common_dir=""
    if [ -n "$common_dir" ]; then
      case "$common_dir" in
        /*) : ;;
        *) common_dir="$target/$common_dir" ;;
      esac
    fi
  fi
  if [ -z "$common_dir" ] && [ -d "$target/.git" ]; then
    common_dir="$target/.git"
  fi

  if [ -z "$common_dir" ]; then
    echo "Warning: $target does not look like a git repository — skipping the .git/info/exclude managed block (guest mode)." >&2
    SUM_SKIPPED+=(".git/info/exclude (not a git repository)")
    return 0
  fi

  exclude_file="$common_dir/info/exclude"

  # Warn (never fail) if a guest-managed path is already tracked in the
  # target repo — an exclude entry cannot hide an already-tracked path.
  if command -v git >/dev/null 2>&1; then
    local trackme tracked_paths=".beads"
    [ "${CLAUDE_GUEST_SELECTED:-0}" -eq 1 ] && tracked_paths="CLAUDE.local.md .claude $tracked_paths"
    [ "${CODEX_GUEST_SELECTED:-0}" -eq 1 ] && tracked_paths=".codex/agents/implementer.toml .codex/agents/reviewer.toml .codex/.domestique .agents/skills/domestique .agents/skills/domestique-decompose .agents/skills/domestique-goal .agents/skills/dom-decompose .agents/skills/dom-goal $tracked_paths"
    for trackme in $tracked_paths; do
      if git -C "$target" ls-files --error-unmatch "$trackme" >/dev/null 2>&1; then
        echo "Warning: $trackme is already tracked in $target — a git exclude entry cannot hide a tracked path. Run 'git rm --cached -r $trackme' if you want it hidden." >&2
      fi
    done
  fi

  {
    printf '%s\n' "$GITEXCLUDE_MARKER_BEGIN"
    if [ "${CLAUDE_GUEST_SELECTED:-0}" -eq 1 ]; then
      printf 'CLAUDE.local.md\n'
      printf '.claude/\n'
    fi
    if [ "${CODEX_GUEST_SELECTED:-0}" -eq 1 ]; then
      local codex_ownership="$target/.codex/.domestique/guest-excludes"
      if [ -e "$codex_ownership" ]; then
        cat "$codex_ownership"
      else
        # Dry-run and legacy-state fallback.  Fresh real installs persist the
        # exact list before this block is reconciled.
        [ "${CODEX_PREEXIST_IMPL:-0}" -eq 1 ] || printf '.codex/agents/implementer.toml\n'
        [ "${CODEX_PREEXIST_REVIEWER:-0}" -eq 1 ] || printf '.codex/agents/reviewer.toml\n'
        printf '.codex/.domestique/\n'
        [ "${CODEX_PREEXIST_BASE_SKILL:-0}" -eq 1 ] || printf '.agents/skills/domestique/SKILL.md\n'
        [ "${CODEX_PREEXIST_DECOMPOSE_SKILL:-0}" -eq 1 ] || printf '.agents/skills/domestique-decompose/SKILL.md\n'
        [ "${CODEX_PREEXIST_GOAL_SKILL:-0}" -eq 1 ] || printf '.agents/skills/domestique-goal/SKILL.md\n'
        [ "${CODEX_PREEXIST_GOAL_META:-0}" -eq 1 ] || printf '.agents/skills/domestique-goal/agents/openai.yaml\n'
        [ "${CODEX_PREEXIST_DOM_DECOMPOSE_SKILL:-0}" -eq 1 ] || printf '.agents/skills/dom-decompose/SKILL.md\n'
        [ "${CODEX_PREEXIST_DOM_GOAL_SKILL:-0}" -eq 1 ] || printf '.agents/skills/dom-goal/SKILL.md\n'
        [ "${CODEX_PREEXIST_DOM_GOAL_META:-0}" -eq 1 ] || printf '.agents/skills/dom-goal/agents/openai.yaml\n'
      fi
    fi
    if { [ "${CLAUDE_GUEST_SELECTED:-0}" -eq 1 ] && [ -e "$target/.claude/.domestique/beads-owned" ]; } ||
       { [ "${CODEX_GUEST_SELECTED:-0}" -eq 1 ] && [ -e "$target/.codex/.domestique/beads-owned" ]; }; then
      printf '.beads/\n'
    fi
    printf '%s\n' "$GITEXCLUDE_MARKER_END"
  } > "$block"

  if [ -e "$exclude_file" ]; then
    if grep -qF "$GITEXCLUDE_MARKER_BEGIN" "$exclude_file" && ! grep -qF "$GITEXCLUDE_MARKER_END" "$exclude_file"; then
      echo "Error: $exclude_file has a '$GITEXCLUDE_MARKER_BEGIN' marker but no matching '$GITEXCLUDE_MARKER_END'." >&2
      echo "       Refusing to edit a half-marked file. Fix it by hand and re-run." >&2
      exit 1
    fi

    if grep -qF "$GITEXCLUDE_MARKER_BEGIN" "$exclude_file"; then
      awk -v beginm="$GITEXCLUDE_MARKER_BEGIN" -v endm="$GITEXCLUDE_MARKER_END" -v blockfile="$block" '
        BEGIN { while ((getline line < blockfile) > 0) blk = blk line ORS }
        $0 == beginm && !seen { seen=1; inblock=1; printf "%s", blk; next }
        inblock && $0 == endm { inblock=0; next }
        inblock { next }
        { print }
      ' "$exclude_file" > "$result"
    else
      cp "$exclude_file" "$result"
      if [ -s "$result" ] && [ "$(tail -c 1 "$result" | wc -l)" -eq 0 ]; then
        printf '\n' >> "$result"
      fi
      cat "$block" >> "$result"
    fi
  else
    cp "$block" "$result"
  fi

  if [ -e "$exclude_file" ] && cmp -s "$result" "$exclude_file"; then
    SUM_SKIPPED+=("$exclude_file (managed block already current)")
    return 0
  fi

  if [ "$DRY_RUN" -eq 1 ]; then
    if [ -e "$exclude_file" ]; then
      note_dry "update $exclude_file (managed block)"
      SUM_UPDATED+=("$exclude_file")
    else
      note_dry "create $exclude_file (managed block only)"
      SUM_CREATED+=("$exclude_file")
    fi
    return 0
  fi

  mkdir -p "$(dirname "$exclude_file")"
  if [ -e "$exclude_file" ]; then
    cp "$result" "$exclude_file"
    SUM_UPDATED+=("$exclude_file (managed block)")
  else
    cp "$result" "$exclude_file"
    SUM_CREATED+=("$exclude_file")
  fi
}

# Remove only domestique's managed ignore block.  This is also run after a
# guest -> normal conversion so stale ignores cannot keep normal assets hidden.
remove_git_exclude() {
  local target="$1" common_dir="" exclude_file result="$TMPDIR_WORK/exclude_remove_result"
  if command -v git >/dev/null 2>&1; then
    common_dir="$(git -C "$target" rev-parse --git-common-dir 2>/dev/null)" || common_dir=""
    if [ -n "$common_dir" ]; then
      case "$common_dir" in /*) : ;; *) common_dir="$target/$common_dir" ;; esac
    fi
  fi
  [ -z "$common_dir" ] && [ -d "$target/.git" ] && common_dir="$target/.git"
  [ -n "$common_dir" ] || return 0
  exclude_file="$common_dir/info/exclude"
  [ -e "$exclude_file" ] || return 0
  grep -qF "$GITEXCLUDE_MARKER_BEGIN" "$exclude_file" 2>/dev/null || return 0
  if ! grep -qF "$GITEXCLUDE_MARKER_END" "$exclude_file" 2>/dev/null; then
    echo "Error: $exclude_file has a '$GITEXCLUDE_MARKER_BEGIN' marker but no matching '$GITEXCLUDE_MARKER_END'." >&2
    echo "       Refusing to edit a half-marked file. Fix it by hand and re-run." >&2
    exit 1
  fi
  awk -v beginm="$GITEXCLUDE_MARKER_BEGIN" -v endm="$GITEXCLUDE_MARKER_END" '
    $0 == beginm && !seen { seen=1; inblock=1; next }
    inblock && $0 == endm { inblock=0; next }
    inblock { next }
    { print }
  ' "$exclude_file" > "$result"
  if [ "$DRY_RUN" -eq 1 ]; then
    note_dry "strip domestique block from $exclude_file"
  else
    cp "$result" "$exclude_file"
  fi
  SUM_UPDATED+=("$exclude_file (removed stale guest block)")
}

# `.beads/` is shared across providers. If one domestique guest projection
# created it, every subsequently active guest provider must carry that fact so
# a scoped uninstall of the original owner cannot make the workspace visible.
sync_guest_beads_ownership() {
  local claude_marker="$TARGET_DIR/.claude/.domestique/beads-owned"
  local codex_marker="$TARGET_DIR/.codex/.domestique/beads-owned"
  if [ ! -d "$TARGET_DIR/.beads" ]; then
    if [ "$DRY_RUN" -eq 0 ]; then
      rm -f "$claude_marker" "$codex_marker"
    fi
    return 0
  fi
  [ "${ANY_GUEST:-0}" -eq 1 ] || return 0
  if [ ! -e "$claude_marker" ] && [ ! -e "$codex_marker" ]; then
    return 0
  fi
  if [ "$DRY_RUN" -eq 1 ]; then
    note_dry "propagate shared .beads ownership across active guest providers"
    return 0
  fi
  if [ "${CLAUDE_GUEST_SELECTED:-0}" -eq 1 ]; then
    mkdir -p "$(dirname "$claude_marker")"
    : > "$claude_marker"
  fi
  if [ "${CODEX_GUEST_SELECTED:-0}" -eq 1 ]; then
    mkdir -p "$(dirname "$codex_marker")"
    : > "$codex_marker"
  fi
}

# do_uninstall <target-dir>
# Remove everything domestique installed into <target-dir>, and only that.
# See usage() --uninstall for the summary of what is (and is not) removed.
do_uninstall() {
  local target="$1"
  local anything_done=0

  # Fixed path inventories are not ownership proof by themselves. Require a
  # provider state tree or one of our managed policy markers before touching
  # plain projection files; this keeps a never-installed host file safe even
  # if its bytes happen to match a domestique template exactly.
  local claude_evidence=0 codex_evidence=0 evidence_file
  [ -d "$target/.claude/.domestique" ] && claude_evidence=1
  [ -d "$target/.codex/.domestique" ] && codex_evidence=1
  for evidence_file in "$target/CLAUDE.md" "$target/CLAUDE.local.md"; do
    [ -e "$evidence_file" ] && grep -qxF "$MARKER_BEGIN" "$evidence_file" 2>/dev/null && claude_evidence=1
  done
  for evidence_file in "$target/AGENTS.md" "$target/AGENTS.override.md"; do
    [ -e "$evidence_file" ] && grep -qxF "$MARKER_BEGIN" "$evidence_file" 2>/dev/null && codex_evidence=1
  done

  # --- 1. provider-owned plain files, safety-compared ----------------------
  local provider state_rel rel emitter dest staged basepath reference
  while IFS='|' read -r provider state_rel rel emitter; do
    [ -z "$rel" ] && continue
    [ "$provider" = "claude" ] && [ "$UNINSTALL_CLAUDE" -eq 0 ] && continue
    [ "$provider" = "codex" ] && [ "$UNINSTALL_CODEX" -eq 0 ] && continue
    [ "$provider" = "claude" ] && [ "$claude_evidence" -eq 0 ] && continue
    [ "$provider" = "codex" ] && [ "$codex_evidence" -eq 0 ] && continue
    dest="$target/$rel"
    [ -e "$dest" ] || continue
    if [ "$provider" = "codex" ] && [ -e "$target/.codex/.domestique/guest-excludes" ] &&
       ! grep -qxF "$rel" "$target/.codex/.domestique/guest-excludes" 2>/dev/null; then
      SUM_KEPT+=("$dest (pre-existing; never domestique-owned)")
      continue
    fi
    staged="$TMPDIR_WORK/uninstall_staged"
    "$emitter" > "$staged"
    basepath="$target/$state_rel/base/$rel"
    reference="$basepath"
    [ -e "$reference" ] || reference="$staged"

    if cmp -s "$dest" "$reference"; then
      anything_done=1
      if [ "$DRY_RUN" -eq 1 ]; then
        note_dry "remove $dest"
      else
        rm -f "$dest"
      fi
      SUM_REMOVED+=("$dest")
    elif [ "$FORCE" -eq 1 ]; then
      anything_done=1
      if [ "$DRY_RUN" -eq 1 ]; then
        note_dry "remove $dest (modified, --force)"
      else
        rm -f "$dest"
      fi
      SUM_REMOVED+=("$dest (modified, --force)")
    else
      anything_done=1
      local kept="$dest.uninstalled.$TS"
      if [ "$DRY_RUN" -eq 1 ]; then
        note_dry "keep $dest (modified) -> would rename to $kept"
      else
        mv "$dest" "$kept"
      fi
      SUM_KEPT+=("$kept")
    fi
  done <<UNINSTALL_FILES
claude|.claude/.domestique|.claude/agents/implementer.md|emit_implementer
claude|.claude/.domestique|.claude/agents/reviewer.md|emit_reviewer
claude|.claude/.domestique|.claude/commands/decompose.md|emit_decompose
claude|.claude/.domestique|.claude/commands/goal.md|emit_goal
claude|.claude/.domestique|.claude/commands/dom-decompose.md|emit_decompose
claude|.claude/.domestique|.claude/commands/dom-goal.md|emit_goal
codex|.codex/.domestique|.codex/agents/implementer.toml|emit_codex_implementer
codex|.codex/.domestique|.codex/agents/reviewer.toml|emit_codex_reviewer
codex|.codex/.domestique|.agents/skills/domestique/SKILL.md|emit_codex_skill
codex|.codex/.domestique|.agents/skills/domestique-decompose/SKILL.md|emit_codex_decompose_skill
codex|.codex/.domestique|.agents/skills/domestique-goal/SKILL.md|emit_codex_goal_skill
codex|.codex/.domestique|.agents/skills/domestique-goal/agents/openai.yaml|emit_codex_goal_metadata
codex|.codex/.domestique|.agents/skills/dom-decompose/SKILL.md|emit_codex_dom_decompose_skill
codex|.codex/.domestique|.agents/skills/dom-goal/SKILL.md|emit_codex_dom_goal_skill
codex|.codex/.domestique|.agents/skills/dom-goal/agents/openai.yaml|emit_codex_dom_goal_metadata
UNINSTALL_FILES

  # --- 2. managed policy blocks for selected providers --------------------
  local policyfile policymode policyemitter policybase
  while IFS='|' read -r provider policyfile policymode policyemitter policybase; do
    [ "$provider" = "claude" ] && [ "$UNINSTALL_CLAUDE" -eq 0 ] && continue
    [ "$provider" = "codex" ] && [ "$UNINSTALL_CODEX" -eq 0 ] && continue
    dest="$target/$policyfile"
    [ -e "$dest" ] || continue

    local marker_status marker_bc marker_ec
    read -r marker_status marker_bc marker_ec < <(markers_sane "$dest")
    [ "$marker_status" = "none" ] && continue

    # Refuse to guess on a structurally unsound managed-block file: one
    # marker present without its pair, duplicate BEGIN/END markers, or END
    # appearing before BEGIN would all make the strip below act on the wrong
    # span (data loss). Leave it byte-untouched and mark the run conflicted,
    # mirroring install's guard, but without aborting the whole run — other
    # files still get uninstalled.
    if [ "$marker_status" != "ok" ]; then
      anything_done=1
      CONFLICT_OCCURRED=1
      local marker_problem=""
      case "$marker_status" in
        half)
          if [ "$marker_bc" -eq 0 ]; then
            echo "Error: $dest has a '$MARKER_END' marker but no matching '$MARKER_BEGIN'." >&2
          else
            echo "Error: $dest has a '$MARKER_BEGIN' marker but no matching '$MARKER_END'." >&2
          fi
          echo "       Refusing to edit a half-marked file. Fix it by hand and re-run." >&2
          marker_problem="half-marked managed block"
          ;;
        dup_begin)
          echo "Error: $dest has more than one '$MARKER_BEGIN' marker ($marker_bc occurrences)." >&2
          echo "       Refusing to edit a file with duplicate markers. Fix it by hand and re-run." >&2
          marker_problem="duplicate BEGIN marker"
          ;;
        dup_end)
          echo "Error: $dest has more than one '$MARKER_END' marker ($marker_ec occurrences)." >&2
          echo "       Refusing to edit a file with duplicate markers. Fix it by hand and re-run." >&2
          marker_problem="duplicate END marker"
          ;;
        inverted)
          echo "Error: $dest has a '$MARKER_END' marker appearing before its '$MARKER_BEGIN' marker." >&2
          echo "       Refusing to edit a file with markers in the wrong order. Fix it by hand and re-run." >&2
          marker_problem="markers in wrong order (END before BEGIN)"
          ;;
      esac
      note_dry "ERROR: $dest has $marker_problem — leaving it untouched, not uninstalling"
      SUM_CONFLICT+=("$dest ($marker_problem)")
      continue
    fi

    anything_done=1

    local oursblock pristine refblock modified=0
    oursblock="$TMPDIR_WORK/uninstall_oursblock"
    awk -v beginm="$MARKER_BEGIN" -v endm="$MARKER_END" '
      $0 == beginm && !seen { seen=1; inblock=1; next }
      inblock && $0 == endm { inblock=0; next }
      inblock { print }
    ' "$dest" > "$oursblock"

    pristine="$TMPDIR_WORK/uninstall_pristine"
    "$policyemitter" "$policymode" > "$pristine"
    refblock="$target/$policybase/base/$policyfile.block"
    [ -e "$refblock" ] || refblock="$pristine"
    cmp -s "$oursblock" "$refblock" || modified=1

    # Strip the block (including markers), preserving everything else
    # verbatim. Back the file up first ONLY when the block was user-modified
    # relative to its base/pristine content — an exact-inverse strip needs no
    # backup and must not leave a stray .bak behind (round-trip byte-parity
    # with the pre-install tree, verified by scenario a/b).
    local result backup
    result="$TMPDIR_WORK/uninstall_result"
    awk -v beginm="$MARKER_BEGIN" -v endm="$MARKER_END" '
      $0 == beginm && !seen { seen=1; inblock=1; next }
      inblock && $0 == endm { inblock=0; next }
      inblock { next }
      { print }
    ' "$dest" > "$result"

    if [ "$modified" -eq 1 ]; then
      backup="$dest.bak.$TS"
      if [ "$DRY_RUN" -eq 1 ]; then
        note_dry "backup $dest -> $backup (managed block was modified)"
      else
        cp "$dest" "$backup"
      fi
      SUM_BACKEDUP+=("$backup")
    fi

    if grep -q '[^[:space:]]' "$result" 2>/dev/null; then
      if [ "$DRY_RUN" -eq 1 ]; then
        note_dry "strip managed block from $dest, leaving the rest of the file intact"
      else
        cp "$result" "$dest"
      fi
      SUM_REMOVED+=("$dest (managed block)")
    else
      if [ "$DRY_RUN" -eq 1 ]; then
        note_dry "remove $dest (empty after stripping managed block)"
      else
        rm -f "$dest"
      fi
      SUM_REMOVED+=("$dest")
    fi
  done <<UNINSTALL_POLICIES
claude|CLAUDE.md|normal|emit_policy|.claude/.domestique
claude|CLAUDE.local.md|guest|emit_policy|.claude/.domestique
codex|AGENTS.md|normal|emit_codex_policy|.codex/.domestique
codex|AGENTS.override.md|normal|emit_codex_policy|.codex/.domestique
UNINSTALL_POLICIES

  # --- 3. managed block in <git-common-dir>/info/exclude ------------------
  # A scoped uninstall retains an exact union for any other provider that is
  # still guest-installed. Only the final guest-provider removal strips it.
  local keep_claude_guest=0 keep_codex_guest=0
  if [ "$UNINSTALL_CLAUDE" -eq 0 ] && [ "$(cat "$target/.claude/.domestique/mode" 2>/dev/null || true)" = "guest" ]; then
    keep_claude_guest=1
  fi
  if [ "$UNINSTALL_CODEX" -eq 0 ] && [ "$(cat "$target/.codex/.domestique/mode" 2>/dev/null || true)" = "guest" ]; then
    keep_codex_guest=1
  fi

  if [ "$keep_claude_guest" -eq 1 ] || [ "$keep_codex_guest" -eq 1 ]; then
    CLAUDE_GUEST_SELECTED="$keep_claude_guest"
    CODEX_GUEST_SELECTED="$keep_codex_guest"
    install_git_exclude "$target"
    anything_done=1
  else
  local common_dir="" exclude_file
  if command -v git >/dev/null 2>&1; then
    common_dir="$(git -C "$target" rev-parse --git-common-dir 2>/dev/null)" || common_dir=""
    if [ -n "$common_dir" ]; then
      case "$common_dir" in
        /*) : ;;
        *) common_dir="$target/$common_dir" ;;
      esac
    fi
  fi
  if [ -z "$common_dir" ] && [ -d "$target/.git" ]; then
    common_dir="$target/.git"
  fi

  if [ -n "$common_dir" ]; then
    exclude_file="$common_dir/info/exclude"
    if [ -e "$exclude_file" ] && grep -qF "$GITEXCLUDE_MARKER_BEGIN" "$exclude_file" 2>/dev/null; then
      anything_done=1
      local exresult
      exresult="$TMPDIR_WORK/uninstall_exclude_result"
      awk -v beginm="$GITEXCLUDE_MARKER_BEGIN" -v endm="$GITEXCLUDE_MARKER_END" '
        $0 == beginm && !seen { seen=1; inblock=1; next }
        inblock && $0 == endm { inblock=0; next }
        inblock { next }
        { print }
      ' "$exclude_file" > "$exresult"
      if [ "$DRY_RUN" -eq 1 ]; then
        note_dry "strip domestique block from $exclude_file (preserving everything else)"
      else
        cp "$exresult" "$exclude_file"
      fi
      SUM_REMOVED+=("$exclude_file (managed block)")
    fi
  fi
  # Non-git target: nothing was installed there — skip silently.
  fi

  # --- 4. selected provider state (do this after snapshot comparisons) -----
  local snapshot_dir
  for snapshot_dir in "$target/.claude/.domestique" "$target/.codex/.domestique"; do
    case "$snapshot_dir" in
      "$target/.claude/.domestique") [ "$UNINSTALL_CLAUDE" -eq 1 ] || continue ;;
      "$target/.codex/.domestique") [ "$UNINSTALL_CODEX" -eq 1 ] || continue ;;
    esac
    [ -e "$snapshot_dir" ] || continue
    anything_done=1
    if [ "$DRY_RUN" -eq 1 ]; then
      note_dry "remove $snapshot_dir (snapshots, manifest, mode marker)"
    else
      rm -rf "$snapshot_dir"
    fi
    SUM_REMOVED+=("$snapshot_dir")
  done

  # Keep the surviving provider's persisted set authoritative.
  local remaining_state="" remaining_value=""
  if [ "$UNINSTALL_CLAUDE" -eq 1 ] && [ "$UNINSTALL_CODEX" -eq 0 ] && [ -d "$target/.codex/.domestique" ]; then
    remaining_state="$target/.codex/.domestique/platforms"; remaining_value="codex"
  elif [ "$UNINSTALL_CODEX" -eq 1 ] && [ "$UNINSTALL_CLAUDE" -eq 0 ] && [ -d "$target/.claude/.domestique" ]; then
    remaining_state="$target/.claude/.domestique/platforms"; remaining_value="claude"
  fi
  if [ -n "$remaining_state" ]; then
    if [ "$DRY_RUN" -eq 1 ]; then
      note_dry "persist platform set '$remaining_value' -> $remaining_state"
    else
      printf '%s\n' "$remaining_value" > "$remaining_state"
    fi
  fi

  # Prune now-empty dirs, never one that still has user content.
  if [ "$DRY_RUN" -eq 1 ]; then
    note_dry "prune selected provider directories if left empty"
  else
    if [ "$UNINSTALL_CLAUDE" -eq 1 ]; then
      rmdir "$target/.claude/agents" 2>/dev/null || true
      rmdir "$target/.claude/commands" 2>/dev/null || true
      rmdir "$target/.claude" 2>/dev/null || true
    fi
    if [ "$UNINSTALL_CODEX" -eq 1 ]; then
      rmdir "$target/.codex/agents" 2>/dev/null || true
      rmdir "$target/.codex" 2>/dev/null || true
      rmdir "$target/.agents/skills/domestique-goal/agents" 2>/dev/null || true
      rmdir "$target/.agents/skills/domestique-goal" 2>/dev/null || true
      rmdir "$target/.agents/skills/domestique-decompose" 2>/dev/null || true
      rmdir "$target/.agents/skills/dom-goal/agents" 2>/dev/null || true
      rmdir "$target/.agents/skills/dom-goal" 2>/dev/null || true
      rmdir "$target/.agents/skills/dom-decompose" 2>/dev/null || true
      rmdir "$target/.agents/skills/domestique" 2>/dev/null || true
      rmdir "$target/.agents/skills" 2>/dev/null || true
      rmdir "$target/.agents" 2>/dev/null || true
    fi
  fi

  # --- 7. .beads/ — never touched by default -------------------------------
  if [ -d "$target/.beads" ]; then
    if [ "$PURGE_BEADS" -eq 1 ]; then
      anything_done=1
      if [ "$DRY_RUN" -eq 1 ]; then
        note_dry "remove $target/.beads (--purge-beads)"
      else
        rm -rf "$target/.beads"
      fi
      SUM_REMOVED+=("$target/.beads (--purge-beads)")
    else
      echo "Note: $target/.beads left in place (domestique never removes it by default) — pass --purge-beads, or remove it by hand: rm -rf $target/.beads" >&2
    fi
  fi

  echo
  if [ "$anything_done" -eq 0 ]; then
    echo "domestique: nothing to remove in $target — no domestique install detected."
    return 0
  fi

  if [ "$DRY_RUN" -eq 1 ]; then echo "Summary (planned uninstall):"; else echo "Summary (uninstall):"; fi
  [ "${#SUM_REMOVED[@]}"   -gt 0 ] && print_group "Removed"         "${SUM_REMOVED[@]}"
  [ "${#SUM_KEPT[@]}"      -gt 0 ] && print_group "Kept (modified)" "${SUM_KEPT[@]}"
  [ "${#SUM_BACKEDUP[@]}"  -gt 0 ] && print_group "Backed up"       "${SUM_BACKEDUP[@]}"
  [ "${#SUM_SKIPPED[@]}"   -gt 0 ] && print_group "Skipped"         "${SUM_SKIPPED[@]}"
  [ "${#SUM_CONFLICT[@]}"  -gt 0 ] && print_group "Conflicted"      "${SUM_CONFLICT[@]}"
  [ "$DRY_RUN" -eq 1 ] && echo "  (dry run: nothing was actually changed)"

  if [ "$CONFLICT_OCCURRED" -eq 1 ]; then
    echo
    echo "One or more files ended in conflict/error — see 'Conflicted' above." >&2
    return 3
  fi
  echo "Done."
}

if [ "$UNINSTALL" -eq 1 ]; then
  UNINSTALL_CLAUDE=1
  UNINSTALL_CODEX=1
  if [ "$PLATFORM_EXPLICIT" -eq 1 ]; then
    UNINSTALL_CLAUDE=0
    UNINSTALL_CODEX=0
    case "$PLATFORM_ARG" in
      claude) UNINSTALL_CLAUDE=1 ;;
      codex) UNINSTALL_CODEX=1 ;;
      both) UNINSTALL_CLAUDE=1; UNINSTALL_CODEX=1 ;;
    esac
  fi
  echo "domestique: uninstalling from $TARGET_DIR (platform=${PLATFORM_ARG:-all})"
  [ "$DRY_RUN" -eq 1 ] && echo "(dry run — no files will be modified)"
  do_uninstall "$TARGET_DIR"
  exit $?
fi

# ---------------------------------------------------------------------------
echo "domestique: installing into $TARGET_DIR (platforms=$PLATFORM_SET)"
[ "$DRY_RUN" -eq 1 ] && echo "(dry run — no files will be modified)"

ANY_GUEST=0
CLAUDE_GUEST_SELECTED=0
CODEX_GUEST_SELECTED=0
# Preserve the pre-install visibility of existing untracked Codex-owned
# paths: guest exclude hides only files domestique is creating itself.
CODEX_PREEXIST_IMPL=0
CODEX_PREEXIST_REVIEWER=0
CODEX_PREEXIST_BASE_SKILL=0
CODEX_PREEXIST_DECOMPOSE_SKILL=0
CODEX_PREEXIST_GOAL_SKILL=0
CODEX_PREEXIST_GOAL_META=0
CODEX_PREEXIST_DOM_DECOMPOSE_SKILL=0
CODEX_PREEXIST_DOM_GOAL_SKILL=0
CODEX_PREEXIST_DOM_GOAL_META=0
[ -e "$TARGET_DIR/.codex/agents/implementer.toml" ] && ! codex_exclude_was_owned '.codex/agents/implementer.toml' && CODEX_PREEXIST_IMPL=1
[ -e "$TARGET_DIR/.codex/agents/reviewer.toml" ] && ! codex_exclude_was_owned '.codex/agents/reviewer.toml' && CODEX_PREEXIST_REVIEWER=1
[ -e "$TARGET_DIR/.agents/skills/domestique/SKILL.md" ] && ! codex_exclude_was_owned '.agents/skills/domestique/SKILL.md' && CODEX_PREEXIST_BASE_SKILL=1
[ -e "$TARGET_DIR/.agents/skills/domestique-decompose/SKILL.md" ] && ! codex_exclude_was_owned '.agents/skills/domestique-decompose/SKILL.md' && CODEX_PREEXIST_DECOMPOSE_SKILL=1
[ -e "$TARGET_DIR/.agents/skills/domestique-goal/SKILL.md" ] && ! codex_exclude_was_owned '.agents/skills/domestique-goal/SKILL.md' && CODEX_PREEXIST_GOAL_SKILL=1
[ -e "$TARGET_DIR/.agents/skills/domestique-goal/agents/openai.yaml" ] && ! codex_exclude_was_owned '.agents/skills/domestique-goal/agents/openai.yaml' && CODEX_PREEXIST_GOAL_META=1
[ -e "$TARGET_DIR/.agents/skills/dom-decompose/SKILL.md" ] && ! codex_exclude_was_owned '.agents/skills/dom-decompose/SKILL.md' && CODEX_PREEXIST_DOM_DECOMPOSE_SKILL=1
[ -e "$TARGET_DIR/.agents/skills/dom-goal/SKILL.md" ] && ! codex_exclude_was_owned '.agents/skills/dom-goal/SKILL.md' && CODEX_PREEXIST_DOM_GOAL_SKILL=1
[ -e "$TARGET_DIR/.agents/skills/dom-goal/agents/openai.yaml" ] && ! codex_exclude_was_owned '.agents/skills/dom-goal/agents/openai.yaml' && CODEX_PREEXIST_DOM_GOAL_META=1
if [ "$SELECT_CLAUDE" -eq 1 ]; then
  configure_provider claude
  resolve_provider_mode
  if [ "$GUEST" -eq 1 ]; then
    ANY_GUEST=1
    CLAUDE_GUEST_SELECTED=1
  fi
  install_current_provider
fi
if [ "$SELECT_CODEX" -eq 1 ]; then
  configure_provider codex
  resolve_provider_mode
  if [ "$GUEST" -eq 1 ]; then
    ANY_GUEST=1
    CODEX_GUEST_SELECTED=1
    printf '%s\n' "Note: Codex guest mode is skills-only; start each new session with \`\$domestique\`." >&2
  fi
  install_current_provider
fi

persist_platform_set

# --- beads (opt-in) --------------------------------------------------------
if [ "$WITH_BEADS" -eq 1 ]; then
  if command -v bd >/dev/null 2>&1; then
    BD_READY_FOR_SETUP=0
    if [ -d "$TARGET_DIR/.beads" ]; then
      SUM_SKIPPED+=("bd init (.beads/ already present)")
      BD_READY_FOR_SETUP=1
    else
      BD_INIT_SAFE=1
      if [ "$DRY_RUN" -eq 0 ]; then
        BD_INIT_HELP="$(bd init --help 2>&1 || true)"
        case "$BD_INIT_HELP" in
          *--skip-agents*--skip-hooks*) : ;;
          *) BD_INIT_SAFE=0 ;;
        esac
        if [ "$ANY_GUEST" -eq 1 ]; then
          case "$BD_INIT_HELP" in *--stealth*) : ;; *) BD_INIT_SAFE=0 ;; esac
        fi
      fi
      if [ "$BD_INIT_SAFE" -eq 0 ]; then
        echo "Warning: installed bd lacks the safe init flags required by domestique; skipping --with-beads initialization." >&2
        SUM_SKIPPED+=("beads init (safe --skip-agents/--skip-hooks flags unavailable)")
      elif [ "$DRY_RUN" -eq 1 ]; then
        if [ "$ANY_GUEST" -eq 1 ]; then
          note_dry "run: bd init --stealth --skip-agents --skip-hooks --non-interactive (in $TARGET_DIR)"
        else
          note_dry "run: bd init --skip-agents --skip-hooks --non-interactive (in $TARGET_DIR)"
        fi
      else
        if [ "$ANY_GUEST" -eq 1 ]; then
          ( cd "$TARGET_DIR" && bd init --stealth --skip-agents --skip-hooks --non-interactive )
          if [ "$CLAUDE_GUEST_SELECTED" -eq 1 ]; then
            mkdir -p "$TARGET_DIR/.claude/.domestique"
            : > "$TARGET_DIR/.claude/.domestique/beads-owned"
          fi
          if [ "$CODEX_GUEST_SELECTED" -eq 1 ]; then
            mkdir -p "$TARGET_DIR/.codex/.domestique"
            : > "$TARGET_DIR/.codex/.domestique/beads-owned"
          fi
        else
          ( cd "$TARGET_DIR" && bd init --skip-agents --skip-hooks --non-interactive )
        fi
      fi
      [ "$BD_INIT_SAFE" -eq 1 ] && SUM_CREATED+=(".beads/ (bd init)")
      [ "$BD_INIT_SAFE" -eq 1 ] && BD_READY_FOR_SETUP=1
    fi

    if [ "$ANY_GUEST" -eq 1 ]; then
      echo "Note: guest mode intentionally skips bd setup provider recipes to preserve host instructions and hooks." >&2
      SUM_SKIPPED+=("bd setup (guest isolation)")
    elif [ "$BD_READY_FOR_SETUP" -eq 1 ]; then
      if [ "$SELECT_CLAUDE" -eq 1 ]; then
        if [ "$DRY_RUN" -eq 1 ]; then note_dry "run: bd setup claude (in $TARGET_DIR)"
        else ( cd "$TARGET_DIR" && bd setup claude ); fi
        SUM_UPDATED+=("bd setup claude")
      fi
      if [ "$SELECT_CODEX" -eq 1 ]; then
        if [ "$DRY_RUN" -eq 1 ]; then note_dry "run: bd setup codex (in $TARGET_DIR)"
        else ( cd "$TARGET_DIR" && bd setup codex ); fi
        SUM_UPDATED+=("bd setup codex")
      fi
    else
      SUM_SKIPPED+=("bd setup (beads workspace unavailable)")
    fi
  else
    SUM_SKIPPED+=("beads: 'bd' not found on PATH — skipped (install not required)")
  fi
fi

sync_guest_beads_ownership
if [ "$ANY_GUEST" -eq 1 ]; then
  install_git_exclude "$TARGET_DIR"
else
  remove_git_exclude "$TARGET_DIR"
fi

# --- summary ---------------------------------------------------------------
echo
if [ "$DRY_RUN" -eq 1 ]; then echo "Summary (planned):"; else echo "Summary:"; fi
[ "${#SUM_CREATED[@]}"  -gt 0 ] && print_group "Created"    "${SUM_CREATED[@]}"
[ "${#SUM_UPDATED[@]}"  -gt 0 ] && print_group "Updated"    "${SUM_UPDATED[@]}"
[ "${#SUM_MERGED[@]}"   -gt 0 ] && print_group "Merged"     "${SUM_MERGED[@]}"
[ "${#SUM_ADOPTED[@]}"  -gt 0 ] && print_group "Adopted"    "${SUM_ADOPTED[@]}"
[ "${#SUM_BACKEDUP[@]}" -gt 0 ] && print_group "Backed up"  "${SUM_BACKEDUP[@]}"
[ "${#SUM_SKIPPED[@]}"  -gt 0 ] && print_group "Skipped"    "${SUM_SKIPPED[@]}"
[ "${#SUM_CONFLICT[@]}" -gt 0 ] && print_group "Conflicted" "${SUM_CONFLICT[@]}"
[ "$DRY_RUN" -eq 1 ] && echo "  (dry run: nothing was actually changed)"

if [ "$CONFLICT_OCCURRED" -eq 1 ]; then
  echo
  echo "One or more files ended in conflict/error — see 'Conflicted' above and the .new/.bak files for each." >&2
  exit 3
fi
echo "Done."
