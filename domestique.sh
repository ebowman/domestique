#!/usr/bin/env bash
# domestique.sh — install the domestique orchestration config into a repo.
# No selector installs Claude+Codex+Copilot; explicit both means Claude+Codex.
# Runtime assets remain embedded
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
  emit_harness_guard claude policy
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
- Before dispatch, apply the supported pre-dispatch minimum in that protocol: active native client and registered intended role IDs; verified stored pair/ownership/root/hashes and required reload; matching declared/resolved model/effort and tools; documented project discovery/precedence with competing definitions and known overrides checked; available non-secret provider/model compatibility evidence. Missing optional exact-origin/loaded-byte APIs or future child telemetry alone do not block explicitly authorized work once this minimum passes. Missing/ambiguous registration, actual mismatch, unresolved inheritance, known defeating override or unavailability means STOP, never fallback. Send no conflicting spawn model/effort overrides. Check available child telemetry during/after each authorized assignment before accepting work; selection failure/mismatch stops. Native dispatch qualification remains separate.

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

emit_harness_guard() {
  local harness="$1" surface="${2:-entry}"
  printf '\n## Active harness boundary (%s only)\n\n' "$harness"
  cat <<'DOM_EOF'
Before applying ANY instructions below, identify the ACTUAL native caller from
the client's available session context and native tools. Installed directories,
file names, skill matching/loading and this text are NOT caller identity.
There is no required identity API; if available context/tools do not establish
the client unambiguously, STOP and ask the human. Do not guess.
DOM_EOF
  printf 'These instructions apply only to the native `%s` client.\n' "$harness"
  if [ "$surface" = policy ]; then
    cat <<'DOM_EOF'
Other harnesses must ignore this entire owned policy block, including its role,
setup, Beads and dispatch instructions. Unrelated host instructions still apply.
DOM_EOF
  else
    cat <<'DOM_EOF'
An explicit foreign-harness invocation must STOP without setup, Beads, task,
branch or dispatch writes. Report the mismatch; suggest the shared project-local
dom-decompose/dom-goal entry for Codex/Copilot or Claude's /dom-decompose
and /dom-goal commands, but do not invoke them automatically.
DOM_EOF
  fi
}

emit_implementer() { cat <<'DOM_EOF'
---
name: implementer
description: Claude Code only; never match in another harness. Executes a single well-scoped, bounded coding task and reports back a terse summary — one bead / one task at a time.
tools: Read, Write, Edit, Bash, Glob, Grep
model: sonnet
---
DOM_EOF
  emit_harness_guard claude
  cat <<'DOM_EOF'

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
description: Claude Code only; never match in another harness. Independently verifies one completed task against its bead's done-criteria in a fresh context and returns a pass/fail verdict with specific findings.
tools: Read, Bash, Glob, Grep
model: opus
---
DOM_EOF
  emit_harness_guard claude
  cat <<'DOM_EOF'

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
planning, code, branch changes or dispatch. Establish the actual native
harness as `claude` using available client context/tools, not this command's name.
Bind ROOT to the exact physical Git worktree
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
Include available non-secret provider/model compatibility evidence (supported
current session/provider status, restrictions and selectable model/effort data).
State what each source establishes and what remains unobserved: a catalog is
selection/support evidence, not execution proof or guaranteed future entitlement.
A doctor subprocess describes its own provider/session, not automatically the
active thread; establish applicability before using it as active-session evidence.
For Claude, invocation model precedes role frontmatter, then subagent environment
default, then parent; `inherit` selects parent. Force-model settings, spawn hooks
and allowlists may override/substitute. Effort order is environment override,
invocation effort, role effort, then session. Verify the installed version's
behavior rather than assuming this order is universal.
Unknown support/availability, incompatible effort, unresolved inheritance/alias,
or an override that defeats the selection means STOP before writes, with the
role and reason. No fallback or silent default substitution; no paid probe.

After saving, require a fresh client session and explicit reinvocation. Before
any workflow action on a confirmed pair, establish this supported pre-dispatch
minimum, read-only:
- Identify the active native client and its registered intended `implementer`
  and `reviewer` role IDs; registration must be present and unambiguous.
- Verify the stored pair, ownership, physical ROOT, BOTH marker hashes and
  required fresh-session reload using the checks above.
- Match declared model AND effort and required tools to supported native
  registration/session evidence of their resolution. Explicit non-overridable
  registered selections plus documented native resolution are sufficient;
  resolve inherited values/aliases anew, not by guessing.
- Verify installed-version documented project-local discovery and precedence;
  check competing project/ancestor/global definitions and known invocation,
  environment, hook or client overrides that could defeat these roles.
- Establish current provider/model compatibility with available non-secret
  native evidence, including restrictions and known availability failures;
  report the evidence and its limits, not a future entitlement/runtime guarantee.

Use native source provenance when exposed. Otherwise use documented discovery,
precedence and the checked on-disk pair with matching registered selections;
do not invent exact-origin or loaded-byte attestation. Missing optional
exact-origin/loaded-byte APIs or not-yet-existent child telemetry alone do not
block ordinary explicitly authorized work when this minimum is established.
Missing/ambiguous registration, actual mismatch, unresolved inheritance or a
known defeating override/unavailability means STOP without workflow or writes.
A catalog, file syntax, user assertion or marker alone is not dispatch proof.
Send no conflicting spawn
model/effort override; ephemeral model requests are assertions, not persistence:
a conflict stops and offers explicit reconfiguration. Inheritance is consent to
native resolution, not a pinned model; resolve/check it anew every session.
During/after each authorized assignment, check actual available child telemetry
for role/model/effort and selection errors before accepting work. Observed
selection failure/mismatch means STOP; never silently fall back. Report what
was observed and any telemetry limits; declared selections are not execution
proof. Do not invent a verification API, require an unavailable telemetry API
or demand a separate paid probe to establish readiness.
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
description: Claude Code only; never match in another harness. Decompose a goal or spec into a beads epic with bounded, dependency-ordered tasks.
argument-hint: <goal, path to a spec file, or configure role models>
---
DOM_EOF
  emit_harness_guard claude
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
description: Claude Code only; never match in another harness. Explicitly drain a named beads epic — dedicated branch, one bead per commit, reviewer-gated, bounded loop.
argument-hint: <epic-id>
---
DOM_EOF
  emit_harness_guard claude
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
description = "Codex only; never match in another harness. Executes one bounded beads task, validates it, and returns a terse handoff without closing the bead."
model = "gpt-5.6-terra"
model_reasoning_effort = "medium"
sandbox_mode = "workspace-write"
developer_instructions = """
You are the domestique implementer. Complete exactly one bounded task handed
to you by the orchestrator, then stop.
These instructions apply only in the actual native Codex client; foreign or
ambiguous callers stop without work. Installed directories do not identify it.

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
description = "Codex only; never match in another harness. Independently verifies one completed bead against its done criteria, real diff, and tests; never fixes or changes bead state."
model = "gpt-5.6"
model_reasoning_effort = "high"
sandbox_mode = "workspace-write"
developer_instructions = """
You are the domestique reviewer. Independently verify one completed task and
return a verdict; do not fix anything.
These instructions apply only in the actual native Codex client; foreign or
ambiguous callers stop without work. Installed directories do not identify it.

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
planning, code, branch changes or dispatch. Establish the active harness as `codex`
from actual client context/tools, not this entry's name. Bind ROOT to the exact physical Git
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
Include available non-secret provider/model compatibility evidence (supported
current session/provider status, restrictions and selectable model/effort data).
State what each source establishes and what remains unobserved: a catalog is
selection/support evidence, not execution proof or guaranteed future entitlement.
A doctor subprocess describes its own provider/session, not automatically the
active thread; establish applicability before using it as active-session evidence.
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
any workflow action on a confirmed pair, establish this supported pre-dispatch
minimum, read-only:
- Identify the active native client and its registered intended `implementer`
  and `reviewer` role IDs; registration must be present and unambiguous.
- Verify the stored pair, ownership, physical ROOT, BOTH marker hashes and
  required fresh-session reload using the checks above.
- Match declared model AND effort and required tools to supported native
  registration/session evidence of their resolution. Explicit non-overridable
  registered selections plus documented native resolution are sufficient;
  resolve inherited values/aliases anew, not by guessing.
- Verify installed-version documented project-local discovery and precedence;
  check competing project/ancestor/global definitions and known invocation,
  environment, hook or client overrides that could defeat these roles.
- Establish current provider/model compatibility with available non-secret
  native evidence, including restrictions and known availability failures;
  report the evidence and its limits, not a future entitlement/runtime guarantee.

Use native source provenance when exposed. Otherwise use documented discovery,
precedence and the checked on-disk pair with matching registered selections;
do not invent exact-origin or loaded-byte attestation. Missing optional
exact-origin/loaded-byte APIs or not-yet-existent child telemetry alone do not
block ordinary explicitly authorized work when this minimum is established.
Missing/ambiguous registration, actual mismatch, unresolved inheritance or a
known defeating override/unavailability means STOP without workflow or writes.
A catalog, file syntax, user assertion or marker alone is not dispatch proof.
Send no conflicting spawn
model/effort override. Ephemeral model requests are assertions, not persistence;
a conflict stops and offers explicit reconfiguration. Inheritance is consent
to native resolution, not a pinned model or necessarily the direct parent:
resolve/check it anew each session.
During/after each authorized assignment, check actual available child telemetry
for role/model/effort and selection errors before accepting work. Observed
selection failure/mismatch means STOP; never silently fall back. Report what
was observed and any telemetry limits; declared selections are not execution
proof. Do not invent a verification API, require an unavailable telemetry API
or demand a separate paid probe to establish readiness.
Actual observed role dispatch/reload qualification is separate, budget-gated
work (hq-7sm.6); static emitted-protocol/lifecycle tests do not qualify runtime.
That later observation is not a prerequisite to emitting this
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
authority. Generated defaults are suggestions, never confirmation.
Before dispatch, apply the supported pre-dispatch minimum in that protocol:
active native client and registered intended role IDs; verified stored
pair/ownership/root/hashes and required reload; matching declared/resolved
model/effort and tools; documented project discovery/precedence with competing
definitions and known overrides checked; available non-secret provider/model
compatibility evidence. Missing optional exact-origin/loaded-byte APIs or future
child telemetry alone do not block explicitly authorized work once this minimum
passes. Missing/ambiguous registration, actual mismatch, unresolved inheritance,
known defeating override or unavailability means STOP, never fallback.
Send no conflicting spawn model/effort overrides. Check available child telemetry
during/after each authorized assignment before accepting work; selection
failure/mismatch stops. Native dispatch qualification remains separate. Explicit
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
description: Codex only; never match in Copilot, Claude or an unknown harness. Orchestrate a beads-backed implementer then independent reviewer workflow. In Codex use when the user says "dispatch next ready bead", asks to dispatch or review a bead, says "land the plane", or explicitly invokes $domestique to bootstrap a guest session. Never use this skill alone to drain an epic unattended.
---

# Domestique orchestration

DOM_EOF
  emit_harness_guard codex
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
description: Codex only; never match in Copilot, Claude or an unknown harness. Decompose a goal or specification into a dependency-ordered beads epic with bounded tasks. In Codex use when explicitly invoked as $dom-decompose or $domestique-decompose or when the user asks for domestique/beads decomposition; planning only, never implementation.
---
DOM_EOF
  emit_harness_guard codex
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
description: Codex only; never match in Copilot, Claude or an unknown harness. Explicitly drain one named beads epic using domestique's bounded implementer-reviewer loop on an isolated branch. Use only when the user explicitly invokes $dom-goal or $domestique-goal with an epic id; never infer this unattended authorization.
---
DOM_EOF
  emit_harness_guard codex
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
  short_description: "Codex only: drain one explicit epic with gated review"
  default_prompt: "Use $domestique-goal with an explicit epic id."
policy:
  allow_implicit_invocation: false
DOM_EOF
}

emit_copilot_implementer() { cat <<'DOM_EOF'
---
name: domestique-v2-copilot-implementer
description: Copilot only; never match in Claude, Codex or an unknown harness. Complete exactly one caller-assigned bounded Domestique task.
tools: ["read", "edit", "search", "execute"]
---
DOM_EOF
  emit_harness_guard copilot
  cat <<'DOM_EOF'
Delegated role only: await an explicit bounded brief from the caller, with
physical project root, bead ID, scope and done criteria. Never start setup or
an autonomous workflow. Claim a supplied bead, but never close it or commit.
Complete exactly the assigned task. Run relevant tests and lint; fix only
in-scope failures. File discovered work using
`bd create "<what>" -p 2 --deps discovered-from:<current-id>`; do not chase it.
Never touch credentials, access controls or destructive Git operations.
Stop for ambiguity, scope growth or unavailable native selection; no fallback.
Return a terse summary: files changed, actual validation/results, discovered
beads and blockers. No file dumps.
DOM_EOF
}

emit_copilot_reviewer() { cat <<'DOM_EOF'
---
name: domestique-v2-copilot-reviewer
description: Copilot only; never match in Claude, Codex or an unknown harness. Independently verify one caller-assigned bounded Domestique task in a fresh context.
tools: ["read", "search", "execute"]
---
DOM_EOF
  emit_harness_guard copilot
  cat <<'DOM_EOF'
Delegated role only: await the caller's explicit bounded brief, project root,
bead ID and done criteria. Never start setup or an autonomous workflow.
Inspect actual tracked/staged diffs and affected files, not the implementer's
summary. Run relevant tests and lint yourself. Do not edit code/configuration,
fix findings, change bead state or commit. Ignored test caches are acceptable;
tracked/staged or bead-state changes fail review. Never touch credentials,
access controls or destructive Git operations. Stay within this task's scope.
Return only PASS, FAIL or NEEDS-WORK, actual validation/results, concrete gaps
and material risks. No file dumps.
DOM_EOF
}

emit_copilot_model_setup() { cat <<'DOM_EOF'
## Copilot first-use role setup — mandatory gate

No setup delegation of ANY kind, including documentation/research helpers.
Inspect supported native tools/docs yourself; missing evidence means STOP.
Before Beads, planning, code, branch changes or dispatch, establish the actual
native caller as copilot from session context/tools, never installed directories.
Bind ROOT to this invocation's exact physical Git worktree root. Ambiguous
identity or cwd outside that root means STOP; never search ancestors or another
checkout. Loading instructions alone is read-only, not setup consent.

Interactive first-use /dom-goal EPIC_ID (or /domestique-v2-copilot-goal EPIC_ID)
runs this two-role questionnaire INLINE. Setup consumes the request, even with
an epic: no automatic continuation. The later unattended loop does not make
this entry noninteractive. Truly noninteractive/autopilot callers without a
confirmed pair STOP without persistence. Ordinary unconfigured delegation
redirects to /dom-decompose configure role models, without a questionnaire.
The exact decompose request `configure role models` is reserved for setup-only
reconfiguration, not planning, even for an already confirmed pair.

### Read-only ownership and confirmation
Use only ROOT/.github/agents/domestique-v2-copilot-implementer.agent.md and
ROOT/.github/agents/domestique-v2-copilot-reviewer.agent.md. Require the existing
ROOT/.github/.domestique/manifest with snapshot_format=1, platform=copilot and
each exact role path once in its comma-separated files inventory, plus both
pristine bases at ROOT/.github/.domestique/base/.github/agents/.
This is snapshot/three-way ownership, not historical inode proof. No preview
receipt, second writer/authority, global settings or machine runtime is needed.
Missing/unmanaged evidence, unsafe paths or ambiguous ownership means STOP for
explicit lifecycle/human repair; never adopt through setup.

Validate bounded UTF-8 regular roles/evidence (at most 1 MiB each), no symlink
in any component, no hardlinks, paths confined to ROOT. Record current complete
bytes, modes and device/inode identities for operation-local rechecks.
Require one well-formed YAML frontmatter block and exact names
`domestique-v2-copilot-implementer` / `domestique-v2-copilot-reviewer`.
Reject duplicate keys, malformed metadata, nested/aliased/multiline selection
syntax, non-string models and duplicate/misplaced markers for human repair.
Retain native tools arrays and all other metadata/body bytes. No Copilot effort
field is invented; effort/model_reasoning_effort fields require human repair.
Never whole-file format or silently repair ambiguous native YAML.

The only completion marker is one comment immediately after the opening
implementer delimiter: `# domestique-model-setup: JSON`. Reviewer has none.
JSON has exactly keys `v` (integer 1), `project` (absolute physical ROOT),
`harness` (`copilot`), `implementer_sha256`, `reviewer_sha256` (lowercase
64-character SHA-256 hex). Validate unique keys/types/root/harness and BOTH
digests at every entry. Hash full file bytes, excluding only the entire
implementer marker line; hash reviewer unchanged. No model copies in the marker.
No marker, stale hash, moved/copied project or partial setup is unconfirmed.
ANY edit to model, tools, metadata or body invalidates confirmation. Show both
current selections for explicit reconfirmation; never silently reapprove.
An unchanged confirmed pair, including inheritance, has NO questionnaire and
NO writes, but still requires native readiness. Aliases share this same pair.

### Supported native evidence, not a paid probe
Before saving establish BOTH selections' support/availability and required
role/tools compatibility using the installed client's documented capabilities,
current selectable models and applicable non-secret session/provider evidence.
Show sources and limits: a catalog is selection evidence, not execution proof
or future entitlement. A subprocess's provider/session is not automatically
the active thread. Verify applicability. Respect explicit provider constraints
using actual native evidence; do not infer provider from spelling or hardcode a
provider switch. Examples such as Sol/Luna/Opus/Sonnet are not selected values.
Unknown/unavailable/unsupported selection, unresolved inheritance or defeating
override means STOP without writes. No fallback, fake paid probe, invented API
or caller-assertion CLI flag substitutes for evidence.

After a save require a fresh Copilot invocation/reload and explicit reinvocation.
Before any dispatch on a confirmed pair, establish read-only:
- Actual native client and present, unambiguous registered intended role IDs.
- Stored pair/ownership/physical ROOT/BOTH hashes and required fresh reload.
- Matching declared/resolved model and required tools, using supported native
  registration/session evidence. Explicit non-overridable registered selections
  plus documented resolution suffice; resolve aliases/inheritance each session.
- Installed-version project discovery/precedence, competing project/ancestor/
  global definitions and known invocation/environment/hook/client overrides.
- Available non-secret provider/model compatibility and restrictions.
Use native source provenance when exposed; otherwise documented discovery,
precedence and the checked pair with matching registered selections suffice.
Optional exact-origin/loaded-file attestation and unavailable future child
telemetry are NOT prerequisites. Actual observed mismatch/unavailability,
ambiguous registration, unresolved inheritance or defeating overrides STOP.
Marker, syntax, catalog and user assertion alone are not dispatch proof.
Send no conflicting spawn model override. Ephemeral requests are assertions,
not persistence or precedence overrides; conflicts require reconfiguration.
Check available child role/model telemetry and selection errors during/after
each authorized assignment before accepting work. Observed mismatch/failure
stops without fallback. Report telemetry limits honestly. No paid probe needed.
Native dispatch/reload qualification remains separate budget-gated work.

### BOTH roles, actual diff and explicit consent
Show ROOT / copilot, exact role paths, current selections (including absent
model/native inheritance), evidence and tracked-file consequences. Ask BOTH:
> Implementer: exact native model ID or native inheritance?
> Reviewer: exact native model ID or native inheritance?
Both may use the same model; independent review means a fresh context.
Use current native choices, not a shipped menu. Resolve existing aliases with
native evidence before confirmation. Generated defaults/unset fields are not
consent. Inheritance removes the model field and follows native resolution,
not necessarily the direct parent; resolve it anew each session.

Prepare both outputs in memory. Patch only model value spans/addition/removal
and the implementer marker, preserving unrelated fields, tools, comments,
body, modes and line endings. Preserve an inline comment when removing model.
Reject control characters/newlines in input; serialize inserted values as
JSON-quoted YAML strings and marker JSON with a serializer, never shell/eval.
If lossless patching is uncertain, STOP. Show the ACTUAL complete proposed diff
(including marker) and require explicit `Save setup only` consent to that diff.
Changed selections require a new diff/consent. Goal consent is not save consent.
Cancel, partial/missing input or noninteractive setup means ZERO writes and
NO workflow. No global/provider/auth/trust/tool/MCP/settings changes.

After consent preflight both outputs and writable parents together; recheck
safe paths, identities, modes and complete bytes of roles AND evidence.
Any concurrent change means STOP/re-prompt, never overwrite. Under cooperative
single-writer operation use same-directory temporary files and atomic per-file
replacement, retaining modes: invalidate old implementer marker first, publish
reviewer next, publish implementer with new pair marker LAST. Recheck expected
state before each replacement. This is not a two-file transaction or hostile-
writer guarantee. Re-read exact approved bytes/modes and verify both hashes.
Failure reports changed paths/unknown state, grants no workflow authority and
retains user bytes for explicit retry; clean only operation-owned temporaries.
Never update pristine snapshots/manifest/excludes or add receipts/journals.

Every successful confirmation/reconfiguration is SETUP ONLY: no Beads, planning,
code, branch/commit or dispatch. End with fresh Copilot invocation/reload and
explicit /dom-decompose or /dom-goal EPIC_ID (legacy names also work).
The initiating goal is consumed, not queued. Before later goal work, ALL
tracked/index dirtiness, including setup edits, requires human disposition:
never auto-stage, commit, stash, discard or hide it. Existing snapshot upgrades
preserve customizations; changed bytes invalidate consent, never silently renew
it. Uninstall preserves modified roles; reinstall implies no confirmation.

## End setup gate — continue only for an unchanged confirmed, ready pair
DOM_EOF
}

emit_copilot_role_gate() { cat <<'DOM_EOF'
## Read-only role gate
Before Beads/delegation validate the confirmed pair and supported pre-dispatch
readiness using `.github/skills/domestique-v2-copilot-decompose/SKILL.md`.
Read that gate as a protocol, not a new invocation or setup authorization.
If unconfigured/stale, STOP and direct the human to
`/dom-decompose configure role models`; no ordinary/bootstrap questionnaire.
Loading/matching alone authorizes neither setup nor an epic. Actual mismatches,
unavailable/ambiguous roles, unresolved inheritance or defeating overrides STOP;
optional loaded-file attestation/future telemetry is not a prerequisite.
Goal first-use runs the same questionnaire inline in its own body, setup only.
DOM_EOF
}

emit_copilot_loop() { cat <<'DOM_EOF'
## Bounded native cycle
Use the existing user's `bd` in the exact physical project root. Require actual
command success and usable scoped output; errors are never an empty queue.
Missing prerequisites mean STOP, not install/init/repair. Treat brief/model
data literally, never eval. No credentials, settings, push or merge changes.
Before code require a clean tracked tree/index and a dedicated non-default
task/epic branch. Dirty/uncertain state requires human disposition, not hiding.
One task in flight: verify its real bead, scope and done criteria, claim it,
then delegate exactly one bounded brief to `domestique-v2-copilot-implementer`.
Wait. Fingerprint tracked/staged diffs and bead state. Delegate independent
verification to a fresh `domestique-v2-copilot-reviewer` with the same criteria.
Reviewer runs relevant tests/lint and inspects real work. Fingerprint again;
reviewer-caused tracked/staged/bead changes FAIL and stop. Ignored caches are OK.
At most one corrective pass plus fresh review. Second non-PASS, full-suite
regression, ambiguity/scope growth, model/role/tools failure, infrastructure
failure or exhausted session budget means STOP, leave unpassed work in_progress.
Only after PASS stage exact reviewed paths with literal Git pathspecs, verify
the staged diff, make one authorized local commit including bead ID, then close
the bead. Never broad-stage or close unpassed work. Commit/close failure stops.
Do not guess/stage database paths. Beads-induced dirtiness requires disposition.
File adjacent work as discovered-from beads, never implement it opportunistically.
Report changed paths, actual validations, review, commit/bead state and blockers.
Stop after one bead unless an explicit named Domestique goal authorizes more.
Guest state remains local-only; never commit it or push host-repository work.
DOM_EOF
}

emit_copilot_skill() { cat <<'DOM_EOF'
---
name: domestique-v2-copilot
description: Copilot only; never match in Claude, Codex or an unknown harness. Bootstrap Domestique or perform one explicitly assigned bounded bead with independent review; never authorize an epic by matching.
---
DOM_EOF
  emit_harness_guard copilot
  emit_copilot_role_gate
  emit_copilot_loop
  cat <<'DOM_EOF'
Ordinary entry is read-only guidance until an explicit task/brief/action request.
Missing task/brief: ask and stop, never invent one. Land-the-plane requests mean
validation/status/handoff, not autonomous queue draining, push or merge.
DOM_EOF
}

emit_copilot_decompose_skill() { cat <<'DOM_EOF'
---
name: domestique-v2-copilot-decompose
description: Copilot only; never match in Claude, Codex or an unknown harness. Handle an explicit /dom-decompose or /domestique-v2-copilot-decompose request; planning or role setup only.
---
DOM_EOF
  emit_harness_guard copilot
  emit_copilot_model_setup
  cat <<'DOM_EOF'
After the gate and explicit planning request, create one epic and bounded child
tasks using the existing project-scoped bd. Each task has one deliverable,
inputs/outputs, edge cases and testable done criteria. Wire real dependencies.
Check every result and retain actual IDs; errors are not successful creation.
Show scoped ready work and the epic tree for human review. No implementation,
delegation, claims, close, staging or commits. Planning never grants execution.
DOM_EOF
}

emit_copilot_goal_skill() { cat <<'DOM_EOF'
---
name: domestique-v2-copilot-goal
description: Copilot only; never match in Claude, Codex or an unknown harness. Run one explicitly named epic only on /dom-goal EPIC_ID or /domestique-v2-copilot-goal EPIC_ID; matching/loading and native goal/autopilot are not authorization.
---
DOM_EOF
  emit_harness_guard copilot
  emit_copilot_model_setup
  emit_copilot_loop
  cat <<'DOM_EOF'
Preserve the original explicit /dom-goal EPIC_ID or
/domestique-v2-copilot-goal EPIC_ID request and its literal epic argument.
Missing explicit request/epic means STOP; native /goal or /autopilot is not
Domestique authorization. Setup consumes goal-first requests without work.
Only after unchanged confirmation/readiness, require human disposition of ALL
tracked/index dirtiness (including setup changes), then use a dedicated epic
branch. Never auto-stage/commit/stash/discard/hide setup changes.
Verify epic type and descendant membership from successful scoped Beads queries.
Select highest-priority ready unfinished task inside that epic only, serially.
Default bound is ONE reviewed bead; the human may explicitly request more,
at most 15 per session. Every next bead needs a clean branch again.
Authority expires on completion, a stop condition, bound, budget or session end;
never carry it to another epic/session. Never merge or push.
If no scoped ready tasks exist, inspect ALL unfinished descendants, including
nested epics. Unfinished blocked work means BLOCKED, not complete. Errors or
empty/unverified output cannot prove completion; never auto-close the epic.
Report review/commits/bead states and remaining work, without queue draining.
DOM_EOF
}

emit_copilot_policy() {
  emit_harness_guard copilot policy
  emit_copilot_role_gate
  emit_copilot_loop
}

# One physical public entry, with no native workflow/setup duplicated here.
emit_shared_skill() {
  local kind="$1"
  printf '%s\n' '---' "name: dom-$kind"
  printf 'description: Codex or Copilot only. Route an explicit dom-%s request to that actual native caller'\''s project-local workflow; loading is not setup or unattended authorization.\n' "$kind"
  printf '%s\n' '---'
  cat <<'DOM_EOF'

## Shared native routing — read-only boundary

Identify the ACTUAL native caller using the client's available session context
and native tools. There is no required identity API. Installed directories,
file names, skill matching/loading and this text do NOT identify the client.
Unknown, ambiguous, or unsupported callers STOP explicitly, without setup,
Beads, task, branch or dispatch writes. Claude must use its /dom-decompose or
/dom-goal command in Claude Code instead; do not auto-invoke another entry.

Bind ROOT to this invocation's physical Git worktree root. Read only the body
for the established native caller below, relative to ROOT; never search another
checkout/ancestor, invoke a global/machine launcher, or fall back across harnesses.
Missing, unreadable or foreign native bodies mean STOP and report that this
project lacks the required native projection. Installation/discovery alone
does not establish native readiness.

Preserve the ORIGINAL user request verbatim, including explicit epic arguments
and its authorization provenance, when reading the body. Never synthesize a new
user invocation. Merely loading or implicitly matching this skill is not
unattended authority and must not start setup. Goal requires an original explicit
dom-goal invocation naming the epic (Codex $dom-goal; Copilot /dom-goal);
loading the routed body cannot grant it. Native compatibility invocations retain
their own explicit authority, never an inferred request. Setup consumes that
request; fresh-session explicit reinvocation is required, not automatic continuation.
DOM_EOF
  printf '\n- Codex: `.agents/skills/domestique-%s/SKILL.md` (compatibility `$domestique-%s`); ordinary loop `.agents/skills/domestique/SKILL.md`, native roles `implementer` / `reviewer`.\n' "$kind" "$kind"
  printf -- '- Copilot: `.github/skills/domestique-v2-copilot-%s/SKILL.md`; ordinary loop `.github/skills/domestique-v2-copilot/SKILL.md`, native roles `domestique-v2-copilot-implementer` / `domestique-v2-copilot-reviewer`.\n' "$kind"
  printf '\nFor this entry preserve the explicit `%s` request and all its arguments.\n' "\$dom-$kind"
}
emit_codex_dom_decompose_skill() {
  emit_shared_skill decompose
}
emit_codex_dom_goal_skill() {
  emit_shared_skill goal
}
emit_codex_dom_goal_metadata() {
  emit_codex_goal_metadata | sed \
    -e 's/[$]domestique-goal/$dom-goal/' \
    -e 's/Codex only: drain one explicit epic with gated review/Route one explicit epic to the actual native caller/'
}

# Normal Codex sessions receive this as a managed root AGENTS policy block.
# Guest Codex deliberately installs no root policy and instead bootstraps via
# the self-contained $domestique skill, leaving host AGENTS files untouched.
emit_codex_policy() { cat <<'DOM_EOF'
# Domestique orchestration policy (Codex)

DOM_EOF
  emit_harness_guard codex policy
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
directory). Without a selector, installs all three native projections:
  CLAUDE.md                        orchestration policy (in a managed block)
  .claude/agents/implementer.md    implementer subagent
  .claude/agents/reviewer.md       reviewer subagent
  .claude/commands/dom-decompose.md /dom-decompose (also /decompose)
  .claude/commands/dom-goal.md      /dom-goal EPIC_ID (also /goal EPIC_ID)
  AGENTS.md or AGENTS.override.md  Codex policy (normal mode, managed block)
  .codex/agents/*.toml             Codex implementer and reviewer
  .agents/skills/dom-*/            Codex $dom-decompose / $dom-goal EPIC_ID
  .agents/skills/domestique*/      Codex bootstrap and compatibility skills
  .github/agents/domestique-v2-copilot-*.agent.md  Copilot native roles
  .github/skills/domestique-v2-copilot*/           Copilot local workflows
  .github/copilot-instructions.md Copilot policy (normal only)

Options:
  --platform <p> Select claude, codex, both, copilot, or all. Both means only
                 Claude+Codex. No selector (fresh or rerun) selects all three.
                 Explicit installs add to the persisted provider set.
  --dry-run      Print planned changes; touch nothing.
  --with-beads   If `bd` is on PATH, initialize with safe skip flags when
                 needed. Normal mode runs setup only for selected providers;
                 guest mode uses --stealth and never runs provider setup.
  --force        Overwrite differing provider files without a .bak backup.
                 Managed policy files are always backed up before change.
  --guest        Use personal/guest mode. Claude routes policy to
                 CLAUDE.local.md; Codex leaves both root AGENTS files
                 untouched and bootstraps through `$domestique` skills.
                 Copilot leaves host policies untouched and bootstraps via
                 /domestique-v2-copilot. Exclusions use exact owned paths.
  --no-guest     Convert an existing guest install back to normal: removes
                 the sticky guest-mode marker and prints by-hand conversion
                 guidance where needed, removes stale guest excludes, and
                 installs the normal policy destination. A no-op note if the
                 target isn't a guest install. Mutually exclusive with
                 --guest (passing both is a usage error).
  --uninstall    Remove everything domestique installed from TARGET_DIR, and
                 only that. With --platform it removes only the selected
                 projection; without it, it scans all three. Modified owned files
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
  * All retained owned CLAUDE/AGENTS root blocks are checked before writes,
    even inactive blocks behind an override or mode conversion. Normal-mode
    isolation upgrades preserve custom text via existing snapshot merges and
    always back up changed policies, including with --force. Missing ownership
    proof or conflicts refuse before writes. Retained CLAUDE.local.md keeps
    personal guest wording; --no-guest removes its guest exclusion, not content.
  * --guest: for installing into a repo you don't own, for personal use only.
    The managed policy block is written to CLAUDE.local.md instead of
    CLAUDE.md. Host root policies are inspected read-only for owned harness
    guards, never modified or backed up in this mode. An old unguarded owned
    block refuses before writes: upgrade it in normal mode (--no-guest) or
    explicitly reconcile it first. Guarded host blocks stay untouched. Everything guest
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
    back to normal on purpose. Missing providers inherit a wholly guest or
    wholly normal installed set (fresh is normal). Mixed modes with a missing
    selected provider refuse before writes; choose --guest or --no-guest.
  * Requires local Git and Python (3.11+ with tomllib when selecting Codex).
    Native clients are optional for configuration installation, not readiness.
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

case "${PLATFORM_ARG:-all}" in
  claude|codex|both|copilot|all) ;;
  *)
    echo "Error: --platform must be one of: claude, codex, both, copilot, all (got '$PLATFORM_ARG')." >&2
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

# Check even the tools used to construct inventories and temporary staging
# before using them. These are local prerequisites, never installed for users.
for dependency in git python3 awk sed grep find wc cut paste head tail cmp cp mkdir rm mv rmdir touch date mktemp cat dirname tr sort; do
  command -v "$dependency" >/dev/null 2>&1 || {
    echo "Error: required local dependency '$dependency' is unavailable. No project writes." >&2
    exit 3
  }
done

COPILOT_ENTRIES='.github/agents/domestique-v2-copilot-implementer.agent.md|emit_copilot_implementer
.github/agents/domestique-v2-copilot-reviewer.agent.md|emit_copilot_reviewer
.github/skills/domestique-v2-copilot/SKILL.md|emit_copilot_skill
.github/skills/domestique-v2-copilot-decompose/SKILL.md|emit_copilot_decompose_skill
.github/skills/domestique-v2-copilot-goal/SKILL.md|emit_copilot_goal_skill'
COPILOT_FILES="$(printf '%s\n' "$COPILOT_ENTRIES" | cut -d'|' -f1 | paste -sd, -)"

# configure_provider <claude|codex|copilot|shared> — select inventory and
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
      MANAGED_PLAIN_FILES=".codex/agents/implementer.toml,.codex/agents/reviewer.toml,.agents/skills/domestique/SKILL.md,.agents/skills/domestique-decompose/SKILL.md,.agents/skills/domestique-goal/SKILL.md,.agents/skills/domestique-goal/agents/openai.yaml"
      ;;
    copilot)
      SNAPSHOT_DIR="$TARGET_DIR/.github/.domestique"
      POLICY_EMITTER="emit_copilot_policy"
      POLICY_LABEL=".github/copilot-instructions.md"
      POLICY_CANDIDATES=".github/copilot-instructions.md"
      MANAGED_PLAIN_FILES="$COPILOT_FILES"
      ;;
    shared)
      SNAPSHOT_DIR="$TARGET_DIR/.agents/.domestique"
      POLICY_CANDIDATES=""
      MANAGED_PLAIN_FILES="$SHARED_FILES"
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
  if [ "$CURRENT_PROVIDER" = copilot ] && [ "${PREVIEW_MIGRATE:-0}" -eq 1 ] &&
     [ "$NO_GUEST" -eq 0 ]; then GUEST=1; fi
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
            echo "  CLAUDE.local.md is retained and its owned block harness-scoped, preserving personal guest instructions/customizations; reconcile it with CLAUDE.md explicitly if desired. It is no longer hidden by the Claude guest exclude." >&2
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
    codex:1|copilot:1)
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
    copilot:0)
      POLICY_DEST=".github/copilot-instructions.md"
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
    [ "$DRY_RUN" -eq 1 ] || mkdir -p "$(dirname "$TARGET_DIR/$POLICY_DEST")"
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
      write_codex_guest_ownership
      ;;
    copilot)
      local rel emitter
      while IFS='|' read -r rel emitter; do
        install_plain "$TARGET_DIR/$rel" "$emitter"
      done <<< "$COPILOT_ENTRIES"
      if [ "$DRY_RUN" -eq 0 ]; then
        cmp -s "$TMPDIR_WORK/copilot-excludes" "$SNAPSHOT_DIR/guest-excludes" ||
          cp "$TMPDIR_WORK/copilot-excludes" "$SNAPSHOT_DIR/guest-excludes"
      fi
      echo "Copilot configuration installed; native readiness is NOT established. Use a fresh native invocation and the role setup gate."
      ;;
  esac

  if [ "$GUEST" -eq 1 ]; then
    if [ "$DRY_RUN" -eq 1 ]; then
      note_dry "write mode marker -> $MODE_MARKER (guest)"
    else
      mkdir -p "$(dirname "$MODE_MARKER")"
      [ "$(cat "$MODE_MARKER" 2>/dev/null || true)" = guest ] ||
        printf 'guest\n' > "$MODE_MARKER"
    fi
  fi
  write_provider_manifest
}

persist_platform_set() {
  local state_dir state_file old
  [ "$CONFLICT_OCCURRED" -eq 0 ] || return 0
  for state_dir in "$TARGET_DIR/.claude/.domestique" "$TARGET_DIR/.codex/.domestique" "$TARGET_DIR/.github/.domestique"; do
    case "$state_dir" in
      "$TARGET_DIR/.claude/.domestique") [ "$SELECT_CLAUDE" -eq 1 ] || continue ;;
      "$TARGET_DIR/.codex/.domestique") [ "$SELECT_CODEX" -eq 1 ] || continue ;;
      "$TARGET_DIR/.github/.domestique") [ "$SELECT_COPILOT" -eq 1 ] || continue ;;
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
# reruns select all three. Legacy state directories count as installed too.
# ---------------------------------------------------------------------------
SELECT_CLAUDE=0
SELECT_CODEX=0
SELECT_COPILOT=0
PERSISTED_CLAUDE=0
PERSISTED_CODEX=0
PERSISTED_COPILOT=0

read_platform_state() {
  local statefile="$1" value provider
  local members
  [ -e "$statefile" ] || return 0
  value="$(cat "$statefile" 2>/dev/null || true)"
  case "$value" in
    both) value=claude,codex ;;
    all) value=claude,codex,copilot ;;
  esac
  case "$value" in
    ""|,*|*,|*,,*|*$'\n'*)
      echo "Error: invalid domestique platform state in $statefile. No project writes." >&2
      exit 3 ;;
  esac
  IFS=, read -r -a members <<< "$value"
  for provider in "${members[@]}"; do
    case "$provider" in
      claude) PERSISTED_CLAUDE=1 ;;
      codex) PERSISTED_CODEX=1 ;;
      copilot) PERSISTED_COPILOT=1 ;;
      *) echo "Error: invalid domestique platform state in $statefile. No project writes." >&2; exit 3 ;;
    esac
  done
}

read_platform_state "$TARGET_DIR/.claude/.domestique/platforms"
read_platform_state "$TARGET_DIR/.codex/.domestique/platforms"
read_platform_state "$TARGET_DIR/.github/.domestique/platforms"

# Backfill provider state that predates the platforms marker.
if [ "$PERSISTED_CLAUDE" -eq 0 ] && [ -d "$TARGET_DIR/.claude/.domestique" ]; then
  PERSISTED_CLAUDE=1
fi
if [ "$PERSISTED_CODEX" -eq 0 ] && [ -d "$TARGET_DIR/.codex/.domestique" ]; then
  PERSISTED_CODEX=1
fi
if [ -d "$TARGET_DIR/.github/.domestique" ]; then
  PERSISTED_COPILOT=1
fi

if [ "$PLATFORM_EXPLICIT" -eq 1 ]; then
  if [ "$UNINSTALL" -eq 0 ]; then
    SELECT_CLAUDE="$PERSISTED_CLAUDE"
    SELECT_CODEX="$PERSISTED_CODEX"
  fi
  # An explicit unrelated provider operation retains Copilot unchanged.
  # In particular it must not convert/hide normal assets or expose guest ones.
  SELECT_COPILOT=0
  case "$PLATFORM_ARG" in
    claude) SELECT_CLAUDE=1 ;;
    codex) SELECT_CODEX=1 ;;
    both) SELECT_CLAUDE=1; SELECT_CODEX=1 ;;
    copilot) SELECT_COPILOT=1 ;;
    all) SELECT_CLAUDE=1; SELECT_CODEX=1; SELECT_COPILOT=1 ;;
  esac
else
  SELECT_CLAUDE=1
  SELECT_CODEX=1
  SELECT_COPILOT=1
fi

platform_set() {
if [ "$SELECT_CLAUDE" -eq 1 ] && [ "$SELECT_CODEX" -eq 1 ]; then
  PLATFORM_SET="both"
elif [ "$SELECT_CODEX" -eq 1 ]; then
  PLATFORM_SET="codex"
elif [ "$SELECT_CLAUDE" -eq 1 ]; then
  PLATFORM_SET="claude"
else
  PLATFORM_SET=""
fi
if [ "$SELECT_COPILOT" -eq 1 ] ||
   { [ "$UNINSTALL" -eq 0 ] && [ "$PERSISTED_COPILOT" -eq 1 ]; }; then
  [ "$PLATFORM_SET" != both ] || PLATFORM_SET="claude,codex"
  PLATFORM_SET="${PLATFORM_SET:+$PLATFORM_SET,}copilot"
fi
}
platform_set

REQUESTED_GUEST="$GUEST"

TS="$(date +%Y%m%d%H%M%S)"
TMPDIR_WORK="$(mktemp -d)"
MUTATION_STARTED=0
trap 'rc=$?; if [ "$rc" -ne 0 ] && [ "$MUTATION_STARTED" -eq 1 ]; then echo "Error: lifecycle interrupted (exit $rc); partial results may remain. Inspect the target before retrying." >&2; fi; rm -rf "$TMPDIR_WORK"; exit "$rc"' EXIT

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

# Shared canonical assets use the same snapshots, not a provider registry.
# Copilot's consumer contract is a snapshot_format=1/platform=copilot
# .github/.domestique manifest inventorying BOTH namespaced roles with bases.
SHARED_ENTRIES='.agents/skills/dom-decompose/SKILL.md|emit_codex_dom_decompose_skill
.agents/skills/dom-goal/SKILL.md|emit_codex_dom_goal_skill
.agents/skills/dom-goal/agents/openai.yaml|emit_codex_dom_goal_metadata'
SHARED_FILES=".agents/skills/dom-decompose/SKILL.md,.agents/skills/dom-goal/SKILL.md,.agents/skills/dom-goal/agents/openai.yaml"
SHARED_MIGRATE=0
SHARED_PRESENT=0
SHARED_CODEX=0
SHARED_COPILOT=0
SHARED_REMOVE=0
SHARED_GUEST=0
PREVIEW_MIGRATE=0

# Supported project-only preview cutover. This deliberately embeds the small
# old locator/receipt contract: installed scripts never import preview sources
# or inspect the machine installation. The durable directory is a bounded
# source backup, not a second provider authority.
preview_migration() {
  python3 - "$TARGET_DIR" "$TMPDIR_WORK" "$1" "$NO_GUEST" "$COPILOT_FILES" <<'PY'
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys
import tempfile

root = Path(sys.argv[1]).resolve()
work, action, normal, files_arg = Path(sys.argv[2]).resolve(), sys.argv[3], sys.argv[4], sys.argv[5]
receipt = ".domestique-private/copilot-preview.json"
archive = ".domestique-private/copilot-preview-migration"
state = ".github/.domestique"
roles = ("implementer", "reviewer")
definitions = {
    "ordinary": ("domestique-v2-copilot", "Load the shared Domestique Copilot instructions."),
    "decompose": ("domestique-v2-copilot-decompose", "Load Domestique planning instructions without coding."),
    "goal": ("domestique-v2-copilot-goal", "Load an explicitly requested Domestique epic workflow."),
    "implementer": ("domestique-v2-copilot-implementer", "Implement one caller-assigned Domestique task."),
    "reviewer": ("domestique-v2-copilot-reviewer", "Independently review one caller-assigned Domestique task."),
}
entries = {**definitions, **{f"dom-{k}": (f"dom-{k}", definitions[k][1])
                            for k in ("decompose", "goal")}}
leaves = {k: (f".github/agents/{v[0]}.agent.md" if k in roles else
              f".github/skills/{v[0]}/SKILL.md") for k, v in entries.items()}
marker = "# domestique-model-setup:"
guard = "Copilot only; never match in Claude, Codex or an unknown harness."

def need(condition, message):
    if not condition:
        raise ValueError(message)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def ident(path):
    info = path.stat()
    return [info.st_dev, info.st_ino]

def identity(value):
    return type(value) is list and len(value) == 2 and all(type(n) is int and n >= 0 for n in value)

def digest(value):
    return type(value) is str and re.fullmatch("[0-9a-f]{64}", value)

def safe(path):
    for p in (*reversed(path.parents), path):
        need(not p.is_symlink(), f"symlink: {p}")
        if p.exists():
            info = p.stat()
            need(stat.S_ISDIR(info.st_mode) or (p == path and stat.S_ISREG(info.st_mode)
                 and info.st_nlink == 1), f"unsafe path: {p}")

def read(path, limit=1048576):
    safe(path)
    need(path.is_file() and path.stat().st_size <= limit and path.stat().st_mode & 0o400,
         f"missing/oversize/unreadable file: {path}")
    return path.read_bytes()

def unique(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, "duplicate JSON key")
        result[key] = value
    return result

def load(data):
    return json.loads(data, object_pairs_hook=unique)

def git(*args):
    return subprocess.check_output(["git", "-C", str(root), *args]).decode().rstrip("\n")

def scalar(value):
    value = value.strip()
    need(bool(value), "empty scalar")
    if value.startswith('"'):
        item, end = json.JSONDecoder().raw_decode(value)
        need(type(item) is str and (not value[end:].strip() or
             value[end:].startswith((" #", "\t#"))), "invalid scalar suffix")
        return item
    if value.startswith("'"):
        match = re.fullmatch(r"'((?:[^']|'')*)'(?:[ \t]+#.*)?", value)
        need(match is not None, "invalid single-quoted scalar")
        return match[1].replace("''", "'")
    need(not any(c in value for c in "[]{}&*!|>'\"`%@") and
         not value.startswith(("-", "?", ":", "#")) and ": " not in value and
         not re.search(r":\s*$", value), "unsupported complex/invalid scalar")
    return re.split(r"[ \t]+#", value, maxsplit=1)[0].rstrip()

def parse(data, kind, source=True):
    text = data.decode("utf-8")
    need("\r" not in text and not any(ord(c) < 32 and c not in "\n\t" for c in text),
         "unsupported controls/line endings")
    lines = text.splitlines(keepends=True)
    need(lines and lines[0] == "---\n", "missing frontmatter")
    end = lines.index("---\n", 1)
    # Generated workflow bodies document the marker protocol literally; only
    # source role markers are approval evidence, never those examples.
    markers = [i for i, line in enumerate(lines if source else lines[:end]) if marker in line]
    if markers:
        need(kind == "implementer" and markers == [1] and lines[1].startswith(marker + " "),
             "misplaced setup marker")
        value = load(lines[1][len(marker):])
        need(type(value) is dict and set(value) == {
            "v", "project", "harness", "implementer_sha256", "reviewer_sha256"} and
            type(value["v"]) is int and value["v"] == 1 and value["project"] == str(root) and
            value["harness"] == "copilot" and all(digest(value[r + "_sha256"]) for r in roles),
            "invalid setup marker")
    fields = {}
    for i, line in enumerate(lines[1:end], 1):
        if not line.strip() or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_-]*):[ \t]*(.*?)\n", line)
        need(match is not None and match[1] not in fields, "complex/duplicate YAML field")
        key, value = match.groups()
        if key == "tools" and value.startswith("["):
            item = load(value)
            need(type(item) is list and all(type(t) is str for t in item), "invalid tools")
        else:
            item = scalar(value)
        if key == "model":
            need(type(item) is str and 0 < len(item) <= 512 and item == item.strip() and
                 all(c.isprintable() for c in item), "invalid model selection")
            need(value.startswith(("'", '"')) or
                 (item.lower() not in ("null", "~", "true", "false", "yes", "no", "on", "off") and
                  not re.match(r"^[+\-0-9.]", item)), "ambiguous model scalar")
        fields[key] = (i, item)
    need("effort" not in fields and "model_reasoning_effort" not in fields,
         "Copilot effort is unsupported; preserve and explicitly repair")
    need(fields.get("name", (None, None))[1] == entries[kind][0], "wrong native identity/name")
    return lines, end, fields, markers

def original(kind, launcher, harness=True):
    name, description = entries[kind]
    actual = kind.removeprefix("dom-")
    text = f"---\nname: {name}\ndescription: {description}\n---\n\n"
    command = shlex.join([launcher, "workflow", actual, "--project", str(root)] +
                        (["--harness", "copilot"] if harness else []))
    if kind in roles:
        text += ("Delegated role only: await the caller's explicit bounded task and retained\n"
                 "shared-source instructions/context. Do not start a workflow, resolve the\n"
                 "current revision independently, or run this locator autonomously.\n"
                 "The caller's shared role-definition locator is:\n\n")
    else:
        if actual == "goal":
            text += ("Use only for an explicit Domestique goal request naming an epic.\n"
                     "Native goal/autopilot and ordinary planning are not authorization.\n\n")
        text += ("Load instructions from the shared preview command for this explicit project;\n"
                 "follow the returned instructions, not a copied local workflow engine:\n\n")
    return (text + f"```sh\n{command}\n```\n\n"
            "If loading fails, report that failure; do not invent a local fallback.\n"
            "Definition discovery alone does not establish operational workflow readiness.\n").encode()

def transfer(data, kind, launcher, upstream):
    lines, end, fields, markers = parse(data, kind)
    old = original(kind, launcher)
    bodies = [old.split(b"---\n", 2)[2]]
    if "inventory" not in record:
        # Original five-definition source (6544140) predates --harness.
        bodies.append(original(kind, launcher, False).split(b"---\n", 2)[2])
    need(data.split(b"---\n", 2)[2] in bodies,
         f"custom prompt fork: {leaves[kind]}; retain source and explicitly reconcile it")
    new_lines, new_end, new_fields, _ = parse(upstream, kind, source=False)
    need("description" in fields, "missing description")
    index, description = fields["description"]
    if description == entries[kind][1]:
        # Replace only the known generated value, retaining inline comments.
        raw = lines[index].split(":", 1)[1].strip()
        if raw.startswith('"'):
            _, stop = json.JSONDecoder().raw_decode(raw)
            suffix = raw[stop:]
        elif raw.startswith("'"):
            suffix = raw[re.match(r"'(?:[^']|'')*'", raw).end():]
        else:
            comment = re.search(r"[ \t]+#", raw)
            suffix = raw[comment.start():] if comment else ""
        lines[index] = new_lines[new_fields["description"][0]].rstrip("\n") + suffix + "\n"
    else:
        need(description == guard or description.startswith(guard + " "),
             f"custom description lacks exact harness boundary: {leaves[kind]}")
    # Preserve every accepted field and comment, not an arbitrary allowlist.
    return ("".join(line for i, line in enumerate(lines[:end]) if i not in markers) +
            "".join(new_lines[new_end:])).encode()

def atomic(path, data, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    safe(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".copilot-migration-", delete=False) as out:
            temporary = Path(out.name)
            os.fchmod(out.fileno(), mode)
            out.write(data)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()

try:
    safe(root / receipt)
    safe(root / archive)
    private = root / ".domestique-private"
    if private.exists():
        need(all(p.name in ("copilot-preview.json", "copilot-preview-migration")
                 for p in private.iterdir()), "unknown experimental/private authority or staging leftover")
    for base in (".github", ".copilot"):
        need(not os.path.lexists(root / base / ".domestique") or base == ".github",
             "unknown experimental authority")
    for rel in (".github/skills/domestique", ".github/skills/domestique-decompose",
                ".github/skills/domestique-goal", ".github/agents/domestique-implementer.agent.md",
                ".github/agents/domestique-reviewer.agent.md"):
        need(not os.path.lexists(root / rel), f"unknown legacy authority: {rel}")
    if (root / archive / "complete").exists():
        need(read(root / archive / "complete") == b"source backup only; snapshot authority\n" and
             not (root / receipt).exists(), "conflicting completed migration/preview authority")
        sys.exit(0)
    if not (root / receipt).exists() and not (root / archive).exists():
        sys.exit(0)
    need(Path(os.path.abspath(sys.argv[1])) == root, "symlink/aliased project root")
    need(git("rev-parse", "--show-toplevel") == str(root), "exact physical Git project root required")
    git_dir = Path(git("rev-parse", "--absolute-git-dir"))
    common = Path(os.path.abspath(root / git("rev-parse", "--git-common-dir")))
    project = {"root": str(root), "root_identity": ident(root),
               "git_dir": str(git_dir), "git_identity": ident(git_dir),
               "common_dir": str(common), "common_identity": ident(common)}
    exclude = common / "info/exclude"
    safe(exclude)
    pending = (root / archive).exists()
    if pending:
        plan = load(read(root / archive / "plan.json", 65536))
        need(type(plan) is dict and set(plan) == {"v", "project", "normal", "source", "output"} and
             plan["v"] == 1 and plan["project"] == project and plan["normal"] == normal,
             "invalid migration backup or changed mode; retry with the original flags")
        need(type(plan["source"]) is dict and set(plan["source"]) <= {receipt, "exclude", *leaves.values()}
             and receipt in plan["source"] and type(plan["output"]) is dict,
             "invalid migration source inventory")
        source = {rel: read(root / archive / "source" / rel) for rel in plan["source"]}
        # Receipt and output schema are independently rederived below.
        record_data = source[receipt]
    else:
        need(not (root / state).exists(), "dual preview/snapshot authority")
        record_data = read(root / receipt, 65536)
        source = {receipt: record_data}
    record = load(record_data)
    need(type(record) is dict and set(record) in (
        {"kind", "state", "project", "installation", "native_ids", "token", "files",
         "directories", "exclusion", "receipt_identity"},
        {"kind", "state", "project", "installation", "native_ids", "token", "files",
         "directories", "exclusion", "receipt_identity", "inventory"}), "unknown/malformed preview receipt")
    need(record["kind"] == "domestique-copilot-preview" and record["state"] == "active" and
         record["project"] == project, "unsupported/foreign/partial preview receipt")
    need(record.get("inventory", "original-five") in ("original-five", "public-names") and
         ("inventory" not in record or record["inventory"] == "public-names"), "unknown inventory")
    selected = leaves if "inventory" in record else {k: leaves[k] for k in definitions}
    need(record["native_ids"] == {k: v[0] for k, v in definitions.items()}, "unknown native IDs")
    installation = record["installation"]
    need(type(installation) is dict and set(installation) == {
        "root", "root_identity", "launcher", "launcher_identity", "launcher_sha256"} and
        all(type(installation[k]) is str and Path(installation[k]).is_absolute() and
            os.path.normpath(installation[k]) == installation[k] for k in ("root", "launcher")) and
        all(identity(installation[k]) for k in ("root_identity", "launcher_identity")) and
        digest(installation["launcher_sha256"]), "invalid installed identity")
    need(identity(record["receipt_identity"]) and (pending or ident(root / receipt) ==
         record["receipt_identity"]), "copied/replaced receipt identity")
    need(type(record["token"]) is str and re.fullmatch("[0-9a-f]{32}", record["token"]),
         "invalid exclusion token")
    facts = record["files"]
    need(type(facts) is dict and set(facts) == set(selected.values()), "unknown/incomplete owned paths")
    parents = {str(p) for rel in (*selected.values(), receipt) for p in Path(rel).parents if str(p) != "."}
    directories = record["directories"]
    need(type(directories) is dict and directories.keys() <= parents and
         all(identity(v) for v in directories.values()), "invalid directory ownership")
    for rel, value in directories.items():
        if not pending:
            safe(root / rel)
            need(ident(root / rel) == value, f"replaced owned directory: {rel}")
    output = {}
    for kind, rel in selected.items():
        value = facts[rel]
        need(type(value) is dict and {"identity", "sha256"} <= set(value) and
             set(value) <= {"identity", "sha256", "model_setup"} and
             identity(value["identity"]) and digest(value["sha256"]), "invalid creation facts")
        setup = value.get("model_setup")
        if setup is not None:
            need(kind in roles and type(setup) is dict and {"identity", "sha256", "removable"} <= set(setup)
                 and set(setup) <= {"identity", "sha256", "removable", "confirmed"} and
                 identity(setup["identity"]) and digest(setup["sha256"]) and
                 type(setup["removable"]) is bool and type(setup.get("confirmed", True)) is bool,
                 "invalid model setup facts")
        if not pending:
            source[rel] = read(root / rel)
            need(ident(root / rel) in (value["identity"], (setup or {}).get("identity")),
                 f"replaced native ownership: {rel}")
        # A known source body, not approval hashes, bounds prompt provenance.
        if kind in definitions:
            output[rel] = transfer(source[rel], kind, installation["launcher"],
                                   read(work / "preview-upstream" / rel))
        else:
            need(sha(source[rel]) == value["sha256"] and source[rel] ==
                 original(kind, installation["launcher"]), f"edited obsolete alias: {rel}")
    for kind in set(leaves) - set(selected):
        need(not os.path.lexists(root / leaves[kind]), "unowned public alias collision")
    # Reject leftovers in obsolete directories, even if the owned leaf agrees.
    for kind in ("dom-decompose", "dom-goal"):
        directory = root / Path(leaves[kind]).parent
        safe(directory)
        if directory.exists():
            need(all(p.name == "SKILL.md" for p in directory.iterdir()), "custom obsolete alias leftover")
    exclusion = record["exclusion"]
    token = record["token"]
    block = (f"# domestique-copilot-preview BEGIN {token}\n" +
             "".join(f"/{rel}\n" for rel in (*selected.values(), receipt)) +
             f"# domestique-copilot-preview END {token}\n").encode()
    need(type(exclusion) is dict and set(exclusion) == {
        "state", "identity", "prefix_size", "prefix_sha256", "separator", "block"} and
        exclusion["state"] == "present" and identity(exclusion["identity"]) and
        type(exclusion["prefix_size"]) is int and 0 <= exclusion["prefix_size"] <= 1048576 and
        digest(exclusion["prefix_sha256"]) and exclusion["separator"] in ("", "\n") and
        exclusion["block"] == block.decode(), "invalid exclusion receipt")
    if not pending:
        source["exclude"] = read(exclude)
        need(ident(exclude) == exclusion["identity"], "replaced Git-common exclude")
    before = source["exclude"]
    offset = exclusion["prefix_size"]
    contribution = exclusion["separator"].encode() + block
    need(before.count(b"# domestique-copilot-preview ") == 2 and
         sha(before[:offset]) == exclusion["prefix_sha256"] and
         before[offset:offset + len(contribution)] == contribution,
         "edited/foreign/shared preview exclusion contribution")
    remainder = before[:offset] + before[offset + len(contribution):]
    need(("/" + archive).encode() not in remainder, "unowned migration exclusion collision")
    begin, end = b"# BEGIN domestique (managed)", b"# END domestique"
    need(remainder.count(begin) == remainder.count(end) and remainder.count(begin) <= 1 and
         (begin not in remainder or remainder.index(begin) < remainder.index(end)),
         "malformed existing managed exclusion")
    # Preserve the host bytes and existing provider contribution. The main
    # installer subsequently reconciles this block using its exact union.
    output["exclude"] = remainder + (b"\n" if remainder and not remainder.endswith(b"\n") else b"")
    output["exclude"] += ("/" + archive + "/\n").encode()
    for rel in files_arg.split(","):
        output[f"{state}/base/{rel}"] = read(work / "preview-upstream" / rel)
    output[f"{state}/guest-excludes"] = (state + "/\n" + "\n".join(files_arg.split(",")) + "\n").encode()
    if normal == "0":
        output[f"{state}/mode"] = b"guest\n"
        begin, end = b"# BEGIN domestique (managed)\n", b"# END domestique\n"
        data = output["exclude"]
        need(data.count(begin) == data.count(end) and data.count(begin) <= 1,
             "malformed existing managed exclusion")
        extra = (state + "/\n" + "\n".join(files_arg.split(",")) + "\n").encode()
        if begin in data:
            need(data.index(begin) < data.index(end), "reversed managed exclusion")
            output["exclude"] = data.replace(end, extra + end)
        else:
            output["exclude"] += begin + extra + end
    output[f"{state}/manifest"] = (
        "snapshot_format=1\nplatform=copilot\ndomestique_version=preview-migration\n"
        "installed_ref=unknown\nfiles=" + files_arg + "\n").encode()
    # Keep the old exact exclusions until their aliases are gone. During a
    # partial cutover neither source backups nor new snapshots become visible.
    output["exclude-pending"] = before + (b"\n" if before and not before.endswith(b"\n") else b"")
    output["exclude-pending"] += ("/" + archive + "/\n/" + state + "/\n").encode()
    source_keys = {receipt, "exclude", *selected.values()}
    need(set(source) == source_keys, "unknown migration source paths")
    if pending:
        expected = {archive + "/plan.json", *(archive + "/source/" + p for p in source),
                    *(archive + "/output/" + p for p in output)}
        parents = {str(p) for rel in expected for p in Path(rel).parents}
        for path in (root / archive).rglob("*"):
            safe(path)
            need(str(path.relative_to(root)) in expected | parents, "unknown migration backup leftover")
        actual = {str(p.relative_to(root)) for p in (root / archive).rglob("*") if not p.is_dir()}
        need(actual == expected, "unknown/incomplete migration backup")
        for category, values in (("source", source), ("output", output)):
            need(set(plan[category]) == set(values), "invalid migration inventory")
            for rel, data in values.items():
                item = plan[category][rel]
                need(type(item) is dict and set(item) == {"sha256", "mode"} and
                     item["sha256"] == sha(data) and type(item["mode"]) is int and
                     0 <= item["mode"] <= 0o777 and
                     read(root / archive / category / rel) == data, "changed migration source/output")
    else:
        plan = {"v": 1, "project": project, "normal": normal, "source": {}, "output": {}}
        for category, values in (("source", source), ("output", output)):
            for rel, data in values.items():
                path = exclude if rel.startswith("exclude") else root / rel
                mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
                need(mode <= 0o777, f"unsupported special mode: {rel}")
                plan[category][rel] = {"sha256": sha(data), "mode": mode}
    # Every live cutover path must be an exact old or planned afterimage.
    # Metadata edited since an interruption is NOT silently reinterpreted.
    for rel in (source_keys | set(output)) - {"exclude-pending"}:
        path = exclude if rel == "exclude" else root / rel
        safe(path)
        need(not any(path.parent.glob(".copilot-migration-*")),
             f"unresolved cutover staging leftover in {path.parent}; preserve and reconcile it")
        if path.exists():
            observed = read(path)
            candidates = [v[rel] for v in (source, output) if rel in v]
            if rel == "exclude":
                candidates.append(output["exclude-pending"])
            need(observed in candidates,
                 f"changed migration path: {rel}; preserve backup and reconcile explicitly")
        else:
            removable = {receipt, leaves["dom-decompose"], leaves["dom-goal"]}
            need(rel not in source or (pending and rel in removable), f"missing source: {rel}")
    # Unknown snapshot or alias leftovers cannot hide behind resumable state.
    if (root / state).exists():
        need(pending, "dual authority")
        need((root / state).is_dir(), "wrong partial snapshot root type")
        expected_files = {rel for rel in output if rel.startswith(state + "/")}
        expected_directories = {str(parent) for rel in expected_files
                                for parent in Path(rel).parents
                                if str(parent).startswith(state + "/")}
        for path in (root / state).rglob("*"):
            safe(path)
            expected = expected_directories if path.is_dir() else expected_files
            need(str(path.relative_to(root)) in expected, "unknown partial snapshot leftover")
    tracked = git("ls-files", "--cached", "-z").split("\0")
    for rel in (source_keys | set(output) | {archive}) - {"exclude", "exclude-pending"}:
        need(not any(p and (p == rel or p.startswith(rel + "/") or rel.startswith(p + "/"))
                     for p in tracked), f"tracked migration path: {rel}")
    # Expose only a temporary projection to the existing read-only preflights.
    for rel, data in output.items():
        if not rel.startswith("exclude"):
            path = work / "preview-root" / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            os.chmod(path, plan[category][rel]["mode"])
    (work / "preview-active").write_text("pending\n")
    print(f"Copilot preview migration: {len(selected)} definitions; byte-preserving source backup "
          f"{archive}; replace five native workflows, retire proven public aliases/receipt, "
          "seed pristine snapshots; selected metadata retained, pair UNCONFIRMED.")
    if action == "apply":
        if not pending:
            # Publish the complete bounded backup before changing any authority.
            temporary = Path(tempfile.mkdtemp(prefix=".copilot-migration-", dir=private))
            for category, values in (("source", source), ("output", output)):
                for rel, data in values.items():
                    path = temporary / category / rel
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
            (temporary / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
            os.rename(temporary, root / archive)
        atomic(exclude, output["exclude-pending"], plan["output"]["exclude-pending"]["mode"])
        # Revoke the old project receipt, never the machine installation.
        # All replacement bytes and their preserving plan have been validated.
        path = root / receipt
        if path.exists():
            path.unlink()
        # Publish only after project receipt revocation.
        for rel, data in output.items():
            if not rel.startswith("exclude"):
                atomic(root / rel, data, plan["output"][rel]["mode"])
        for kind in ("dom-decompose", "dom-goal"):
            if kind in selected:
                path = root / leaves[kind]
                if path.exists():
                    path.unlink()
                if path.parent.exists():
                    path.parent.rmdir()
        atomic(exclude, output["exclude"], plan["output"]["exclude"]["mode"])
        atomic(root / archive / "complete", b"source backup only; snapshot authority\n")
        print("Copilot preview cutover complete; backup retained; fresh pair confirmation required.")
except (OSError, ValueError, TypeError, KeyError, RecursionError, subprocess.CalledProcessError) as exc:
    print(f"Copilot preview migration REFUSED/PARTIAL: {exc}. No source is discarded; "
          f"retain {archive} and all custom files. Retry the same installer/flags for "
          "verified partial afterimages; unknown state requires explicit preserving reconciliation.",
          file=sys.stderr)
    sys.exit(3)
PY
}

preview_preflight() {
  [ "$SELECT_COPILOT" -eq 1 ] || return 0
  local path rel emitter
  for path in .domestique-private/copilot-preview.json .domestique-private/copilot-preview-migration; do
    if [ -e "$TARGET_DIR/$path" ] || [ -L "$TARGET_DIR/$path" ]; then
      [ "$UNINSTALL" -eq 0 ] || [ -f "$TARGET_DIR/.domestique-private/copilot-preview-migration/complete" ] ||
        shared_refuse "preview migration requires install, not uninstall; preserve source"
    fi
  done
  while IFS='|' read -r rel emitter; do
    mkdir -p "$TMPDIR_WORK/preview-upstream/$(dirname "$rel")"
    "$emitter" > "$TMPDIR_WORK/preview-upstream/$rel"
  done <<< "$COPILOT_ENTRIES"
  preview_migration plan || exit $?
  [ -f "$TMPDIR_WORK/preview-active" ] || return 0
  PREVIEW_MIGRATE=1
  # Do not adopt identical unowned shared files during this migration.
  while IFS='|' read -r rel emitter; do
    if [ -e "$TARGET_DIR/$rel" ] || [ -L "$TARGET_DIR/$rel" ] ||
       [ -d "$TARGET_DIR/$(dirname "$rel")" ]; then
      snapshot_has_file .agents/.domestique shared "$rel" ||
        snapshot_has_file .codex/.domestique codex "$rel" ||
        shared_refuse "unowned shared collision during preview migration: $rel"
    fi
  done <<< "$SHARED_ENTRIES"
}

shared_refuse() {
  echo "Error: shared skills preflight: $*. No project writes; repair ownership/merge by hand and retry (including with --force)." >&2
  exit 3
}

# Fixed, project-relative paths only. Do not follow symlinks or hardlinks when
# reading management evidence. Missing leaf paths are allowed for creation.
shared_safe_path() {
  local rel="$1" kind="${2:-file}" part path="$TARGET_DIR" remaining="$1"
  local parts
  IFS='/' read -r -a parts <<< "$rel"
  for part in "${parts[@]}"; do
    path="$path/$part"
    remaining="${remaining#"$part"}"
    remaining="${remaining#/}"
    [ ! -L "$path" ] || return 1
    [ -e "$path" ] || continue
    if [ -n "$remaining" ] || [ "$kind" = directory ]; then
      [ -d "$path" ] || return 1
    else
      [ -f "$path" ] && [ -r "$path" ] || return 1
      [ "$(find "$path" -prune -links +1 -print)" = "" ] || return 1
      [ "$(wc -c < "$path")" -le 1048576 ] || return 1
    fi
  done
}

# Backups are new evidence, never an overwrite target (even a regular file).
policy_backup_preflight() {
  local rel="$1.bak.$TS"
  shared_safe_path "$rel" && [ ! -e "$TARGET_DIR/$rel" ] ||
    shared_refuse "unsafe or occupied policy backup $rel; preserve it and retry with a new timestamp"
}

# Pin destination directories and refuse links/collisions again at publication.
# Used for policy backups and uninstall preservation: neither may follow links
# or overwrite an occupied destination when publishing new evidence.
policy_copy() {
  python3 - "$1" "$2" "${3:-replace}" "$TARGET_DIR" <<'PY'
import os
from pathlib import Path
import shutil
import stat
import sys

source, destination, action, root = sys.argv[1:]
# Preflight permits system aliases above the physical project root (e.g.
# macOS /var). Pin that root, then disallow symlinks in every project component.
path = Path(os.path.relpath(destination, root))
if ".." in path.parts:
    raise ValueError(f"policy destination outside project: {destination}")
directory = os.open(str(Path(root).resolve()), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
try:
    for part in path.parts[:-1]:
        child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                        dir_fd=directory)
        os.close(directory)
        directory = child
    with os.fdopen(os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as incoming:
        source_info = os.fstat(incoming.fileno())
        if not stat.S_ISREG(source_info.st_mode) or source_info.st_nlink != 1:
            raise ValueError(f"unsafe policy source: {source}")
        mode = stat.S_IMODE(os.fstat(incoming.fileno()).st_mode)
        flags = os.O_WRONLY | os.O_NOFOLLOW | os.O_NONBLOCK
        try:
            fd = os.open(path.name, flags | os.O_CREAT | os.O_EXCL, mode,
                         dir_fd=directory)
        except FileExistsError:
            if action == "new":
                raise
            fd = os.open(path.name, flags, dir_fd=directory)
        with os.fdopen(fd, "wb") as outgoing:
            info = os.fstat(outgoing.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError(f"unsafe policy destination: {destination}")
            os.ftruncate(outgoing.fileno(), 0)
            shutil.copyfileobj(incoming, outgoing)
finally:
    os.close(directory)
PY
}

snapshot_has_file() {
  local state="$1" platform="$2" rel="$3" manifest="$TARGET_DIR/$1/manifest"
  shared_safe_path "$state/manifest" && [ -f "$manifest" ] || return 1
  awk -F= -v platform="$platform" -v wanted="$rel" '
    NF != 2 || seen[$1]++ { bad=1 }
    $1 == "snapshot_format" { format=$2 }
    $1 == "platform" { provider=$2 }
    $1 == "files" {
      n=split($2, paths, ",")
      for (i=1; i<=n; i++) {
        if (paths[i] == wanted) found++
        if (files[paths[i]]++) bad=1
      }
    }
    END { exit bad || format != "1" || provider != platform || found != 1 }
  ' "$manifest" || return 1
  shared_safe_path "$state/base/$rel${4:-}" && [ -f "$TARGET_DIR/$state/base/$rel${4:-}" ]
}

shared_consumer_valid() {
  local provider="$1" state role
  case "$provider" in
    codex) state=".codex/.domestique" ;;
    copilot) state=".github/.domestique" ;;
  esac
  for role in implementer reviewer; do
    case "$provider" in
      codex) snapshot_has_file "$state" "$provider" ".codex/agents/$role.toml" || return 1 ;;
      copilot) snapshot_has_file "$state" "$provider" ".github/agents/domestique-v2-copilot-$role.agent.md" || return 1 ;;
    esac
  done
  shared_safe_path "$state/mode" || return 1
  [ ! -e "$TARGET_DIR/$state/mode" ] || [ "$(cat "$TARGET_DIR/$state/mode")" = guest ]
}

# Discovery is a separate boundary from the role body. Validate the decoded
# description's exact, owned prefix, not the apparent meaning of custom prose.
# Check the preserving merge candidate; never insert a guard into user text or
# use --force as permission to repair an unscoped description.
native_role_description_preflight() {
  local provider="$1" candidate="$2" rel="$3"
  python3 - "$provider" "$candidate" <<'PY' ||
import json
import pathlib
import re
import sys

provider, candidate = sys.argv[1:]
prefix = {
    "codex": "Codex only; never match in another harness.",
    "copilot": "Copilot only; never match in Claude, Codex or an unknown harness.",
}[provider]
try:
    text = pathlib.Path(candidate).read_text()
    if provider == "codex":
        try:
            import tomllib
        except ImportError:
            raise ValueError("Python 3.11+ (tomllib) required for Codex role validation") from None
        description = tomllib.loads(text).get("description")
    else:
        lines = text.splitlines()
        if not lines or lines[0] != "---":
            raise ValueError("missing role frontmatter")
        end = lines.index("---", 1)
        values = [line[len("description:"):].strip() for line in lines[1:end]
                  if line.startswith("description:")]
        if len(values) != 1:
            raise ValueError("expected one frontmatter description")
        value = values[0]
        if value.startswith('"'):
            description, end = json.JSONDecoder().raw_decode(value)
            if value[end:].strip() and not value[end:].startswith((" #", "\t#")):
                raise ValueError("invalid description scalar")
        elif value.startswith("'"):
            match = re.fullmatch(r"'((?:[^']|'')*)'(?:[ \t]+#.*)?", value)
            if not match:
                raise ValueError("invalid description scalar")
            description = match[1].replace("''", "'")
        else:
            # Same simple, single-line scalar subset as role syntax preflight.
            if not value or any(c in value for c in "[]{}&*!|>'\"`%@") or ": " in value:
                raise ValueError("unsupported description scalar")
            description = re.split(r"[ \t]+#", value, maxsplit=1)[0].rstrip()
    if not isinstance(description, str) or not (
            description == prefix or description.startswith(prefix + " ")):
        raise ValueError("missing exact discovery description boundary")
except (OSError, ValueError, TypeError) as exc:
    print(f"{provider} role description: {exc}. The decoded description must start "
          f"with {prefix!r}; retain compatible custom text after that prefix, "
          "explicitly reconcile the role and retry. Role body guards are also required.",
          file=sys.stderr)
    sys.exit(1)
PY
    shared_refuse "native role discovery description guard $rel"
}

# All dependencies, selected inventories and provider modes are checked before
# any provider, shared owner or exclude is changed. No native client is needed.
lifecycle_preflight() {
  local provider state rel selected mode guests=0 normals=0 missing=0
  local paths=""
  if [ "$SELECT_CODEX" -eq 1 ] && [ "$UNINSTALL" -eq 0 ]; then
    python3 -c 'import tomllib' >/dev/null 2>&1 ||
      shared_refuse "Python 3.11+ with tomllib is required for Codex role validation"
  fi
  for provider in claude codex copilot; do
    configure_provider "$provider"
    state="${SNAPSHOT_DIR#"$TARGET_DIR"/}"
    selected=0
    case "$provider" in
      claude) selected="$SELECT_CLAUDE" ;;
      codex) selected="$SELECT_CODEX" ;;
      copilot) selected="$SELECT_COPILOT" ;;
    esac
    shared_safe_path "$state" directory || shared_refuse "unsafe $state"
    for rel in mode platforms manifest guest-excludes beads-owned; do
      shared_safe_path "$state/$rel" || shared_refuse "unsafe $state/$rel"
    done
    if [ -d "$SNAPSHOT_DIR" ]; then
      mode="$(cat "$MODE_MARKER" 2>/dev/null || true)"
      case "$mode" in
        guest) guests=$((guests + 1)) ;;
        "")
          if [ "$SELECT_COPILOT" -eq 1 ] || [ "$provider" = copilot ]; then
            [ ! -e "$MODE_MARKER" ] || shared_refuse "invalid mode $state"
          fi
          normals=$((normals + 1)) ;;
        *)
          [ "$SELECT_COPILOT" -eq 0 ] && [ "$provider" != copilot ] ||
            shared_refuse "invalid mode $state"
          normals=$((normals + 1)) ;;
      esac
    elif [ "$selected" -eq 1 ]; then
      missing=1
    fi
    [ "$selected" -eq 1 ] || continue
    for rel in mode platforms manifest guest-excludes beads-owned; do
      paths="$paths$state/$rel"$'\n'
    done
    local files
    IFS=, read -r -a files <<< "$MANAGED_PLAIN_FILES"
    for rel in "${files[@]}"; do
      shared_safe_path "$rel" && shared_safe_path "$state/base/$rel" &&
        shared_safe_path "$rel.bak.$TS" && shared_safe_path "$rel.new" &&
        shared_safe_path "$rel.uninstalled.$TS" ||
        shared_refuse "unsafe selected $provider path $rel"
      paths="$paths$rel"$'\n'"$state/base/$rel"$'\n'"$rel.bak.$TS"$'\n'"$rel.new"$'\n'"$rel.uninstalled.$TS"$'\n'
    done
  done
  if [ "$UNINSTALL" -eq 0 ] && [ "$missing" -eq 1 ] &&
     [ "$GUEST_EXPLICIT" -eq 0 ] && [ "$NO_GUEST" -eq 0 ]; then
    [ "$guests" -eq 0 ] || [ "$normals" -eq 0 ] ||
      shared_refuse "mixed-mode ambiguity with missing provider; explicitly choose --guest or --no-guest"
    [ "$guests" -eq 0 ] || REQUESTED_GUEST=1
  fi
  for provider in claude codex copilot; do
    configure_provider "$provider"
    for rel in $POLICY_CANDIDATES; do
      shared_safe_path "$rel" && shared_safe_path "${SNAPSHOT_BASE#"$TARGET_DIR"/}/$rel.block" &&
        shared_safe_path "$rel.bak.$TS" && shared_safe_path "$rel.new" ||
        shared_refuse "unsafe policy destination $rel"
      paths="$paths$rel"$'\n'"${SNAPSHOT_BASE#"$TARGET_DIR"/}/$rel.block"$'\n'"$rel.bak.$TS"$'\n'"$rel.new"$'\n'
    done
  done
  if [ "$SELECT_CODEX" -eq 1 ] || [ "$SELECT_COPILOT" -eq 1 ]; then
    local shared_files
    IFS=, read -r -a shared_files <<< "$SHARED_FILES"
    for rel in "${shared_files[@]}" manifest mode guest-excludes; do
      case "$rel" in
        .agents/*)
          shared_safe_path "$rel.bak.$TS" && shared_safe_path "$rel.new" &&
            shared_safe_path "$rel.uninstalled.$TS" || shared_refuse "unsafe shared output $rel"
          paths="$paths$rel"$'\n'".agents/.domestique/base/$rel"$'\n'"$rel.bak.$TS"$'\n'"$rel.new"$'\n'"$rel.uninstalled.$TS"$'\n' ;;
        *) paths="$paths.agents/.domestique/$rel"$'\n' ;;
      esac
    done
  fi
  # Writable ancestors and the Git-common exclude need checking together with
  # prospective leaves. This is a read-only check, not a write probe.
  python3 - "$TARGET_DIR" "$paths" <<'PY' ||
import os
from pathlib import Path
import stat
import subprocess
import sys

root = Path(sys.argv[1]).resolve()
paths = [root / p for p in sys.argv[2].splitlines()]
common = subprocess.run(["git", "-C", str(root), "rev-parse", "--git-common-dir"],
                        capture_output=True, text=True)
if common.returncode == 0:
    directory = Path(common.stdout.strip())
    if not directory.is_absolute():
        directory = root / directory
    paths.append(directory / "info" / "exclude")
try:
    for candidate in paths:
        checked_parent = False
        for item in (candidate, *candidate.parents):
            if item.is_symlink():
                raise ValueError(f"symlink: {item}")
            if not item.exists():
                continue
            info = item.stat()
            if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
                raise ValueError(f"non-file/directory: {item}")
            if item == candidate and item.is_file() and info.st_nlink != 1:
                raise ValueError(f"hardlinked leaf: {item}")
            if not checked_parent:
                if not os.access(item, os.W_OK) or not info.st_mode & 0o222:
                    raise ValueError(f"not writable: {item}")
                checked_parent = item.is_dir()
            if item == root or item == root.parent:
                break
except (OSError, ValueError) as exc:
    print(f"Lifecycle path preflight: {exc}", file=sys.stderr)
    sys.exit(1)
PY
    shared_refuse "unsafe or unwritable lifecycle paths"
}

# Copilot projection preflight reuses snapshot ownership and three-way merge.
# It never writes project state or confirms a model pair.
copilot_preflight() {
  [ "$SELECT_COPILOT" -eq 1 ] || [ -e "$TARGET_DIR/.github/.domestique" ] ||
    [ -L "$TARGET_DIR/.github/.domestique" ] || return 0
  command -v python3 >/dev/null 2>&1 || shared_refuse "python3 required for Copilot preflight"
  local state=".github/.domestique" rel emitter path base rc native_root="$TARGET_DIR"
  if [ "$PREVIEW_MIGRATE" -eq 1 ]; then
    native_root="$TMPDIR_WORK/preview-root"
  else
    for path in .domestique-private/copilot-preview.json .github/skills/dom-decompose .github/skills/dom-goal; do
      if [ -e "$TARGET_DIR/$path" ] || [ -L "$TARGET_DIR/$path" ]; then
        shared_refuse "competing preview ownership/path $path; supported receipt required"
      fi
    done
  fi
  shared_safe_path "$state" directory || shared_refuse "unsafe Copilot state"
  : > "$TMPDIR_WORK/copilot-excludes"
  : > "$TMPDIR_WORK/shared-new-excludes"
  if [ "$PREVIEW_MIGRATE" -eq 1 ]; then
    cp "$native_root/$state/guest-excludes" "$TMPDIR_WORK/copilot-excludes"
  elif [ -d "$TARGET_DIR/$state" ]; then
    shared_consumer_valid copilot || shared_refuse "unknown Copilot authority"
    while IFS='|' read -r rel emitter; do
      snapshot_has_file "$state" copilot "$rel" || shared_refuse "incomplete Copilot inventory: $rel"
    done <<< "$COPILOT_ENTRIES"
    local files
    files="$(sed -n 's/^files=//p' "$TARGET_DIR/$state/manifest")"
    [ "$files" = "$COPILOT_FILES" ] || [ "$files" = "$COPILOT_FILES,.github/copilot-instructions.md" ] ||
      shared_refuse "unknown Copilot inventory"
    while IFS= read -r path; do
      rel="${path#"$TARGET_DIR/$state"/}"
      if [ -d "$path" ] && [ ! -L "$path" ]; then
        shared_safe_path "${path#"$TARGET_DIR"/}" directory || shared_refuse "unsafe state directory"
        case "$COPILOT_FILES,.github/copilot-instructions.md" in *"${rel#base/}/"*) : ;; *)
          [ "$path" = "$TARGET_DIR/$state" ] || [ "$rel" = base ] ||
            shared_refuse "unknown Copilot state directory $rel" ;;
        esac
      else
        shared_safe_path "${path#"$TARGET_DIR"/}" || shared_refuse "unsafe state file $rel"
        case "$rel" in
          manifest|mode|platforms|guest-excludes|beads-owned) ;;
          base/.github/copilot-instructions.md.block) ;;
          base/*) case ",$COPILOT_FILES," in *",${rel#base/},"*) ;; *) shared_refuse "unknown state file $rel" ;; esac ;;
          *) shared_refuse "unknown state file $rel" ;;
        esac
      fi
    done < <(find "$TARGET_DIR/$state" -print)
    [ -f "$TARGET_DIR/$state/guest-excludes" ] || shared_refuse "missing Copilot visibility evidence"
    while IFS= read -r rel; do
      case ",$COPILOT_FILES,.github/.domestique/," in *",$rel,"*) ;; *) shared_refuse "unknown Copilot exclusion $rel" ;; esac
    done < "$TARGET_DIR/$state/guest-excludes"
    cp "$TARGET_DIR/$state/guest-excludes" "$TMPDIR_WORK/copilot-excludes"
  else
    printf '.github/.domestique/\n' > "$TMPDIR_WORK/copilot-excludes"
  fi
  while IFS='|' read -r rel emitter; do
    shared_safe_path "$rel" && shared_safe_path "$state/base/$rel" &&
      shared_safe_path "$rel.bak.$TS" && shared_safe_path "$rel.uninstalled.$TS" ||
      shared_refuse "unsafe Copilot path $rel"
    base="$native_root/$state/base/$rel"
    if [ -e "$native_root/$rel" ] && [ ! -f "$base" ]; then
      shared_refuse "unowned Copilot path $rel; no silent preview adoption"
    fi
    if [ ! -e "$native_root/$rel" ]; then
      printf '%s\n' "$rel" >> "$TMPDIR_WORK/copilot-excludes"
    elif [ "$SELECT_COPILOT" -eq 1 ] && [ "$UNINSTALL" -eq 0 ]; then
      "$emitter" > "$TMPDIR_WORK/copilot-upstream"
      rc=0
      git merge-file -p "$native_root/$rel" "$base" "$TMPDIR_WORK/copilot-upstream" > "$TMPDIR_WORK/copilot-candidate" || rc=$?
      [ "$rc" -eq 0 ] || shared_refuse "Copilot merge conflict $rel"
      native_role_description_preflight copilot "$TMPDIR_WORK/copilot-candidate" "$rel"
      emit_harness_guard copilot > "$TMPDIR_WORK/copilot-guard"
      python3 - "$TMPDIR_WORK/copilot-guard" "$TMPDIR_WORK/copilot-candidate" "$rel" <<'PY' ||
import pathlib
import sys
guard, candidate = (pathlib.Path(p).read_bytes() for p in sys.argv[1:3])
# Decoded descriptions are checked separately for roles and skills; neither
# discovery nor body boundaries can substitute for the other.
sys.exit(guard not in candidate)
PY
        shared_refuse "missing Copilot caller guard $rel"
    fi
  done <<< "$COPILOT_ENTRIES"
  while IFS='|' read -r rel emitter; do
    [ -e "$TARGET_DIR/$rel" ] || printf '%s\n' "$rel" >> "$TMPDIR_WORK/shared-new-excludes"
  done <<< "$SHARED_ENTRIES"
  path=".github/copilot-instructions.md"
  shared_safe_path "$path" && shared_safe_path "$state/base/$path.block" &&
    shared_safe_path "$path.bak.$TS" || shared_refuse "unsafe Copilot policy"
  if [ -f "$TARGET_DIR/$path" ] && grep -qF "$MARKER_BEGIN" "$TARGET_DIR/$path" &&
     [ ! -f "$TARGET_DIR/$state/base/$path.block" ]; then
    shared_refuse "unknown Copilot policy authority"
  fi
  if [ "$SELECT_COPILOT" -eq 1 ] && [ "$UNINSTALL" -eq 0 ] && [ -f "$TARGET_DIR/$state/base/$path.block" ] &&
     [ -f "$TARGET_DIR/$path" ]; then
    awk -v b="$MARKER_BEGIN" -v e="$MARKER_END" '$0==b {on=1;next} $0==e {exit} on' \
      "$TARGET_DIR/$path" > "$TMPDIR_WORK/copilot-policy"
    emit_copilot_policy > "$TMPDIR_WORK/copilot-upstream"
    rc=0
    git merge-file -p "$TMPDIR_WORK/copilot-policy" "$TARGET_DIR/$state/base/$path.block" "$TMPDIR_WORK/copilot-upstream" >/dev/null || rc=$?
    [ "$rc" -eq 0 ] || shared_refuse "Copilot policy conflict"
  fi
  # Validate native syntax without a YAML dependency or any confirmation write.
  command -v python3 >/dev/null 2>&1 || shared_refuse "python3 required for Copilot preflight"
  python3 - "$native_root" <<'PY' || shared_refuse "malformed Copilot role or unsafe exclude path"
import json
import pathlib
import re
import stat
import subprocess
import sys

root = pathlib.Path(sys.argv[1]).resolve()

def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result

def scalar(value):
    if value.startswith('"'):
        item, end = json.JSONDecoder().raw_decode(value)
        if not isinstance(item, str) or (value[end:].strip() and not value[end:].startswith((" #", "\t#"))):
            raise ValueError("invalid string")
        return item
    if value.startswith("'"):
        match = re.fullmatch(r"'((?:[^']|'')*)'(?:[ \t]+#.*)?", value)
        if not match:
            raise ValueError("invalid quoted scalar")
        return match[1].replace("''", "'")
    if not value or any(c in value for c in "[]{}&*!|>'\"`%@") or value.startswith(("-", "?", ":", "#")) or ": " in value:
        raise ValueError("complex YAML; human repair required")
    return re.split(r"[ \t]+#", value, maxsplit=1)[0].rstrip()

try:
    for role in ("implementer", "reviewer"):
        path = root / f".github/agents/domestique-v2-copilot-{role}.agent.md"
        if not path.exists():
            continue
        text = path.read_bytes().decode("utf-8")
        if "\r" in text or any(ord(c) < 32 and c not in "\n\t" for c in text):
            raise ValueError("unsupported role controls/line endings")
        lines = text.splitlines(keepends=True)
        if not lines or lines[0] != "---\n":
            raise ValueError("missing frontmatter")
        end = lines.index("---\n", 1)
        markers = [i for i, line in enumerate(lines) if "# domestique-model-setup:" in line]
        if markers:
            if role != "implementer" or markers != [1] or not lines[1].startswith("# domestique-model-setup: "):
                raise ValueError("duplicate/misplaced marker")
            marker = json.loads(lines[1].split(": ", 1)[1], object_pairs_hook=unique)
            if (not isinstance(marker, dict) or set(marker) != {
                    "v", "project", "harness", "implementer_sha256", "reviewer_sha256"} or
                    type(marker["v"]) is not int or marker["v"] != 1 or
                    not isinstance(marker["project"], str) or not marker["project"].startswith("/") or
                    marker["harness"] != "copilot" or not all(
                        isinstance(marker[r + "_sha256"], str) and
                        re.fullmatch("[0-9a-f]{64}", marker[r + "_sha256"])
                        for r in ("implementer", "reviewer"))):
                raise ValueError("malformed marker")
            # Stale hashes remain unconfirmed, never silently renewed here.
        fields = {}
        for line in lines[1:end]:
            if not line.strip() or line.startswith("#"):
                continue
            match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_-]*):[ \t]*(.*?)\n", line)
            if not match or match[1] in fields:
                raise ValueError("malformed/duplicate YAML field")
            key, value = match.groups()
            if key == "tools" and value.startswith("["):
                tools = json.loads(value)
                if not isinstance(tools, list) or not all(isinstance(t, str) for t in tools):
                    raise ValueError("invalid native tools")
                fields[key] = tools
            else:
                fields[key] = scalar(value)
            if key == "model" and not value.startswith(("'", '"')) and (
                    fields[key].lower() in ("null", "~", "true", "false", "yes", "no", "on", "off") or
                    re.match(r"^[+\-0-9.]", fields[key])):
                raise ValueError("non-string model")
        if fields.get("name") != f"domestique-v2-copilot-{role}" or "effort" in fields or "model_reasoning_effort" in fields:
            raise ValueError("wrong role identity or unsupported effort")
    common = subprocess.run(["git", "-C", str(root), "rev-parse", "--git-common-dir"],
                            capture_output=True, text=True)
    if common.returncode == 0:
        base = pathlib.Path(common.stdout.strip())
        if not base.is_absolute():
            base = root / base
        exclude = (base / "info/exclude").absolute()
        for path in (*reversed(exclude.parents), exclude):
            if path.is_symlink():
                raise ValueError("symlink in exclude path")
            if path.exists():
                info = path.stat()
                if path == exclude:
                    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                        raise ValueError("unsafe exclude leaf")
                    data = path.read_text()
                    b, e = "# BEGIN domestique (managed)", "# END domestique"
                    if data.count(b) != data.count(e) or data.count(b) > 1 or (
                            b in data and data.index(b) > data.index(e)):
                        raise ValueError("malformed exclude block")
                elif not path.is_dir():
                    raise ValueError("unsafe exclude ancestor")
except (OSError, ValueError, TypeError) as exc:
    print(f"Copilot preflight: {exc}", file=sys.stderr)
    sys.exit(1)
PY
  # Copilot enablement must not partially publish before an older selected
  # projection's unsafe path, merge conflict or missing caller guard is found.
  while IFS='|' read -r provider rel emitter; do
    # An unrelated explicit provider operation retains Copilot unchanged.
    # Still enforce discovery isolation on any Codex roles it will rewrite;
    # other retained-projection checks remain scoped to Copilot enablement.
    if [ "$SELECT_COPILOT" -eq 0 ]; then
      case "$provider:$rel" in codex:*.toml) ;; *) continue ;; esac
    fi
    [ "$provider" != claude ] || [ "$SELECT_CLAUDE" -eq 1 ] || continue
    [ "$provider" != codex ] || [ "$SELECT_CODEX" -eq 1 ] || continue
    base=".$provider/.domestique/base/$rel"
    shared_safe_path "$rel" && shared_safe_path "$base" &&
      shared_safe_path "$rel.bak.$TS" && shared_safe_path "$rel.new" ||
      shared_refuse "unsafe retained $provider path $rel"
    [ "$UNINSTALL" -eq 0 ] || continue
    "$emitter" > "$TMPDIR_WORK/legacy-upstream"
    cp "$TMPDIR_WORK/legacy-upstream" "$TMPDIR_WORK/legacy-candidate"
    if [ -f "$TARGET_DIR/$rel" ]; then
      [ -f "$TARGET_DIR/$base" ] || shared_refuse "unknown retained ownership $rel"
      rc=0
      git merge-file -p "$TARGET_DIR/$rel" "$TARGET_DIR/$base" "$TMPDIR_WORK/legacy-upstream" > "$TMPDIR_WORK/legacy-candidate" || rc=$?
      [ "$rc" -eq 0 ] || shared_refuse "retained projection conflict $rel"
    fi
    case "$rel" in
      *.yaml) continue ;;
      *.toml)
        native_role_description_preflight codex "$TMPDIR_WORK/legacy-candidate" "$rel"
        python3 - "$TMPDIR_WORK/legacy-candidate" <<'PY' ||
import pathlib
import sys
guard = (
    "These instructions apply only in the actual native Codex client; foreign or\n"
    "ambiguous callers stop without work. Installed directories do not identify it."
)
# The body boundary is mandatory in addition to the discovery description.
sys.exit(guard not in pathlib.Path(sys.argv[1]).read_text())
PY
          shared_refuse "missing retained role caller guard $rel"
        ;;
      *)
        emit_harness_guard "$provider" > "$TMPDIR_WORK/legacy-guard"
        python3 - "$TMPDIR_WORK/legacy-guard" "$TMPDIR_WORK/legacy-candidate" <<'PY' ||
import pathlib
import sys
sys.exit(pathlib.Path(sys.argv[1]).read_bytes() not in pathlib.Path(sys.argv[2]).read_bytes())
PY
          shared_refuse "missing retained caller guard $rel"
        ;;
    esac
  done <<'ENTRIES'
claude|.claude/agents/implementer.md|emit_implementer
claude|.claude/agents/reviewer.md|emit_reviewer
claude|.claude/commands/decompose.md|emit_decompose
claude|.claude/commands/goal.md|emit_goal
claude|.claude/commands/dom-decompose.md|emit_decompose
claude|.claude/commands/dom-goal.md|emit_goal
codex|.codex/agents/implementer.toml|emit_codex_implementer
codex|.codex/agents/reviewer.toml|emit_codex_reviewer
codex|.agents/skills/domestique/SKILL.md|emit_codex_skill
codex|.agents/skills/domestique-decompose/SKILL.md|emit_codex_decompose_skill
codex|.agents/skills/domestique-goal/SKILL.md|emit_codex_goal_skill
codex|.agents/skills/domestique-goal/agents/openai.yaml|emit_codex_goal_metadata
ENTRIES
}

shared_preflight() {
  local rel emitter base staged rc path
  local state=".agents/.domestique" legacy=".codex/.domestique"
  # Validate prospective paths as well as existing evidence, before *either*
  # lifecycle can touch providers, modes or exclusions. A directory is not a
  # valid file leaf; a file is not a valid ancestor. Never traverse a symlink.
  shared_safe_path "$state" directory || shared_refuse "unsafe $state"
  for path in manifest mode guest-excludes; do
    shared_safe_path "$state/$path" || shared_refuse "unsafe $state/$path"
  done
  shared_safe_path "$legacy/guest-excludes" || shared_refuse "unsafe legacy visibility evidence"
  while IFS='|' read -r rel emitter; do
    shared_safe_path "$rel" || shared_refuse "unsafe canonical path $rel"
    shared_safe_path "$state/base/$rel" || shared_refuse "unsafe shared base for $rel"
    shared_safe_path "$legacy/base/$rel" || shared_refuse "unsafe legacy base for $rel"
  done <<< "$SHARED_ENTRIES"
  shared_consumer_valid codex && SHARED_CODEX=1
  shared_consumer_valid copilot && SHARED_COPILOT=1
  [ "$PREVIEW_MIGRATE" -eq 0 ] || SHARED_COPILOT=1
  if [ -e "$TARGET_DIR/.github/.domestique" ] || [ -L "$TARGET_DIR/.github/.domestique" ]; then
    [ "$SHARED_COPILOT" -eq 1 ] || shared_refuse "uncertain Copilot consumer ownership"
  fi
  if [ -e "$TARGET_DIR/$state" ] || [ -L "$TARGET_DIR/$state" ]; then
    shared_safe_path "$state" directory && [ -d "$TARGET_DIR/$state" ] || shared_refuse "unsafe $state"
    if [ -e "$TARGET_DIR/$legacy" ] || [ -L "$TARGET_DIR/$legacy" ]; then
      [ "$SHARED_CODEX" -eq 1 ] || shared_refuse "uncertain Codex consumer ownership"
    fi
    # This namespace is new: even identical unknown files cannot be adopted.
    while IFS='|' read -r rel emitter; do
      snapshot_has_file "$state" shared "$rel" || shared_refuse "unknown/incomplete $state; expected authoritative shared manifest and bases"
    done <<< "$SHARED_ENTRIES"
    [ "$(sed -n 's/^files=//p' "$TARGET_DIR/$state/manifest")" = "$SHARED_FILES" ] ||
      shared_refuse "unexpected shared inventory"
    while IFS= read -r path; do
      case "$path" in
        "$TARGET_DIR/$state"|"$TARGET_DIR/$state/base"|"$TARGET_DIR/$state/base/.agents"|"$TARGET_DIR/$state/base/.agents/skills"|"$TARGET_DIR/$state/base/.agents/skills/dom-decompose"|"$TARGET_DIR/$state/base/.agents/skills/dom-goal"|"$TARGET_DIR/$state/base/.agents/skills/dom-goal/agents")
          shared_safe_path "${path#"$TARGET_DIR"/}" directory || shared_refuse "unsafe state directory $path"
          continue ;;
        "$TARGET_DIR/$state/manifest"|"$TARGET_DIR/$state/mode"|"$TARGET_DIR/$state/guest-excludes") ;;
        "$TARGET_DIR/$state/base/.agents/skills/dom-decompose/SKILL.md"|"$TARGET_DIR/$state/base/.agents/skills/dom-goal/SKILL.md"|"$TARGET_DIR/$state/base/.agents/skills/dom-goal/agents/openai.yaml") ;;
        *) shared_refuse "unknown state path $path" ;;
      esac
      shared_safe_path "${path#"$TARGET_DIR"/}" || shared_refuse "unsafe state path $path"
    done < <(find "$TARGET_DIR/$state" -print)
    [ -f "$TARGET_DIR/$state/guest-excludes" ] || shared_refuse "missing shared visibility evidence"
    while IFS= read -r rel; do
      case ",$SHARED_FILES," in *",$rel,"*) : ;; *) shared_refuse "unknown shared visibility path $rel" ;; esac
    done < "$TARGET_DIR/$state/guest-excludes"
    [ ! -e "$TARGET_DIR/$state/mode" ] || [ "$(cat "$TARGET_DIR/$state/mode")" = guest ] ||
      shared_refuse "invalid shared mode"
    [ "$SHARED_CODEX" -eq 1 ] || [ "$SHARED_COPILOT" -eq 1 ] ||
      shared_refuse "shared state has no valid native consumer"
    SHARED_PRESENT=1
    [ ! -e "$TARGET_DIR/$state/mode" ] || SHARED_GUEST=1
  fi
  [ "$SELECT_CODEX" -eq 1 ] || [ "$SELECT_COPILOT" -eq 1 ] || return 0
  [ "$UNINSTALL" -eq 0 ] || return 0
  while IFS='|' read -r rel emitter; do
    shared_safe_path "$rel" || shared_refuse "unsafe canonical path $rel"
    base="$TARGET_DIR/$state/base/$rel"
    if [ -e "$TARGET_DIR/$legacy/base/$rel" ]; then
      [ "$SHARED_PRESENT" -eq 0 ] || shared_refuse "duplicate authoritative base for $rel"
      snapshot_has_file "$legacy" codex "$rel" || shared_refuse "invalid legacy ownership for $rel"
      base="$TARGET_DIR/$legacy/base/$rel"
      SHARED_MIGRATE=1
    fi
    [ -f "$base" ] && [ -f "$TARGET_DIR/$rel" ] || continue
    staged="$TMPDIR_WORK/shared-preflight"
    "$emitter" > "$staged"
    rc=0
    git merge-file -p "$TARGET_DIR/$rel" "$base" "$staged" >/dev/null || rc=$?
    [ "$rc" -eq 0 ] || shared_refuse "merge conflict for $rel against $base; preserve custom bytes and resolve explicitly"
  done <<< "$SHARED_ENTRIES"
}

# Shared routes are private only when every surviving valid consumer is guest.
# Selected installs supply their resolved modes; uninstall excludes removed owners.
resolve_shared_visibility() {
  local provider valid selected guest state
  SHARED_GUEST=1
  for provider in codex copilot; do
    case "$provider" in
      codex) valid="$SHARED_CODEX"; selected="$SELECT_CODEX"; guest="${CODEX_GUEST_SELECTED:-0}"; state=.codex ;;
      copilot) valid="$SHARED_COPILOT"; selected="$SELECT_COPILOT"; guest="${COPILOT_GUEST_SELECTED:-0}"; state=.github ;;
    esac
    if [ "$UNINSTALL" -eq 1 ]; then
      [ "$selected" -eq 0 ] && [ "$valid" -eq 1 ] || continue
      guest=0
      [ "$(cat "$TARGET_DIR/$state/.domestique/mode" 2>/dev/null || true)" != guest ] || guest=1
    elif [ "$selected" -eq 0 ]; then
      [ "$valid" -eq 1 ] || continue
      guest=0
      [ "$(cat "$TARGET_DIR/$state/.domestique/mode" 2>/dev/null || true)" != guest ] || guest=1
    fi
    [ "$guest" -eq 1 ] || SHARED_GUEST=0
  done
}

write_shared_mode() {
  [ "$DRY_RUN" -eq 0 ] || return 0
  local marker="$TARGET_DIR/.agents/.domestique/mode"
  if [ "$SHARED_GUEST" -eq 1 ]; then
    [ "$(cat "$marker" 2>/dev/null || true)" = guest ] || printf 'guest\n' > "$marker"
  else
    rm -f "$marker"
  fi
}

install_shared() {
  local rel emitter
  configure_provider shared
  # Visibility follows all consumers, not the last installed provider.
  while IFS='|' read -r rel emitter; do
    install_plain "$TARGET_DIR/$rel" "$emitter"
  done <<< "$SHARED_ENTRIES"
  write_provider_manifest
  resolve_shared_visibility
  if [ "$DRY_RUN" -eq 0 ]; then
    if [ "$SHARED_PRESENT" -eq 0 ]; then
      : > "$SNAPSHOT_DIR/guest-excludes"
      while IFS='|' read -r rel emitter; do
        if codex_exclude_was_owned "$rel" ||
           grep -qxF "$rel" "$TMPDIR_WORK/shared-new-excludes" 2>/dev/null; then
          printf '%s\n' "$rel" >> "$SNAPSHOT_DIR/guest-excludes"
        fi
      done <<< "$SHARED_ENTRIES"
    fi
    write_shared_mode
  fi
  if [ "$SHARED_MIGRATE" -eq 1 ]; then
    configure_provider codex
    while IFS='|' read -r rel emitter; do
      [ "$DRY_RUN" -eq 1 ] || rm -f "$SNAPSHOT_BASE/$rel"
    done <<< "$SHARED_ENTRIES"
    SNAPSHOT_TOUCHED=1
    write_provider_manifest
  fi
  [ "$DRY_RUN" -eq 1 ] || SHARED_PRESENT=1
}

# Every retained owned root block needs a preserving merge preflight, even if
# already guarded or inactive. Guarded inactive blocks are not update targets.
policy_preflight() {
  local provider requested state rel status bc ec block expected base emitter mode merged rc guarded selected active
  for provider in claude codex copilot; do
    configure_provider "$provider"
    selected=0
    case "$provider" in
      claude) selected="$SELECT_CLAUDE" ;;
      codex) selected="$SELECT_CODEX" ;;
      copilot) selected="$SELECT_COPILOT" ;;
    esac
    state=".$provider/.domestique"
    [ "$provider" != copilot ] || state=".github/.domestique"
    shared_safe_path "$state/mode" || shared_refuse "unsafe $state/mode"
    requested="$REQUESTED_GUEST"
    if [ "$provider" = copilot ] && [ "$PREVIEW_MIGRATE" -eq 1 ] &&
       [ "$NO_GUEST" -eq 0 ]; then requested=1; fi
    if [ "$GUEST_EXPLICIT" -eq 0 ] && [ "$NO_GUEST" -eq 0 ] &&
       [ -f "$TARGET_DIR/$state/mode" ] &&
       [ "$(cat "$TARGET_DIR/$state/mode")" = guest ]; then
      requested=1
    fi
    active=""
    if [ "$selected" -eq 1 ]; then
      case "$provider:$requested" in
        claude:0) active=CLAUDE.md ;;
        claude:1) active=CLAUDE.local.md ;;
        codex:0)
          active=AGENTS.md
          [ ! -e "$TARGET_DIR/AGENTS.override.md" ] || active=AGENTS.override.md ;;
        copilot:0) active=.github/copilot-instructions.md ;;
      esac
    fi
    for rel in CLAUDE.md CLAUDE.local.md AGENTS.md AGENTS.override.md .github/copilot-instructions.md; do
      case "$provider:$rel" in claude:AGENTS*|codex:CLAUDE*|claude:.github/*|codex:.github/*|copilot:CLAUDE*|copilot:AGENTS*) continue ;; esac
      shared_safe_path "$rel" || shared_refuse "unsafe root policy $rel"
      base="$state/base/$rel.block"
      shared_safe_path "$base" || shared_refuse "unsafe policy base $base"
      if [ -f "$TARGET_DIR/$base" ] &&
         ! grep -qxF "$MARKER_BEGIN" "$TARGET_DIR/$rel" 2>/dev/null; then
        snapshot_has_file "$state" "$provider" "$rel" .block ||
          shared_refuse "unowned policy base collision $base"
      fi
      [ -f "$TARGET_DIR/$rel" ] || continue
      read -r status bc ec < <(markers_sane "$TARGET_DIR/$rel")
      if [ "$status" = none ]; then
        if [ "$UNINSTALL" -eq 0 ] && [ "$rel" = "$active" ]; then policy_backup_preflight "$rel"; fi
        continue
      fi
      # Uninstall retains its existing malformed-marker diagnostics.
      if [ "$UNINSTALL" -eq 1 ] && { [ "$selected" -eq 0 ] || [ "$status" != ok ]; }; then continue; fi
      [ "$status" = ok ] || {
        echo "Error: malformed owned policy $rel ($status; duplicate, missing or inverted markers). Fix it by hand and re-run. No project writes." >&2
        exit 1
      }
      block="$TMPDIR_WORK/retained-block"
      expected="$TMPDIR_WORK/retained-guard"
      awk -v beginm="$MARKER_BEGIN" -v endm="$MARKER_END" '
        $0 == beginm { inblock=1; next }
        $0 == endm { exit }
        inblock { print }
      ' "$TARGET_DIR/$rel" > "$block"
      emitter="$POLICY_EMITTER"
      mode=normal
      [ "$rel" != CLAUDE.local.md ] || mode=guest
      "$emitter" "$mode" > "$TMPDIR_WORK/retained-upstream"
      if [ "$UNINSTALL" -eq 1 ]; then
        local reference="$TARGET_DIR/$base"
        [ -f "$reference" ] || reference="$TMPDIR_WORK/retained-upstream"
        cmp -s "$block" "$reference" || policy_backup_preflight "$rel"
        continue
      fi
      {
        [ "$provider" != codex ] || printf '# Domestique orchestration policy (Codex)\n\n'
        emit_harness_guard "$provider" policy
      } > "$expected"
      guarded=0
      if head -c "$(wc -c < "$expected")" "$block" | cmp -s "$expected" -; then
        guarded=1
        if [ "$requested" -eq 1 ] && [ "$rel" = CLAUDE.local.md ] &&
           git -C "$TARGET_DIR" ls-files --error-unmatch "$rel" >/dev/null 2>&1; then
          touch "$TMPDIR_WORK/keep-$rel"
        fi
      fi
      if [ "$guarded" -eq 0 ] && [ "$requested" -eq 1 ]; then
        # Only the selected Claude provider's untracked personal root may be
        # upgraded in guest mode. Never silently edit a tracked host root.
        if [ "$rel" != CLAUDE.local.md ] || [ "$SELECT_CLAUDE" -eq 0 ] ||
           git -C "$TARGET_DIR" ls-files --error-unmatch "$rel" >/dev/null 2>&1; then
          shared_refuse "unguarded owned host policy $rel cannot be changed in guest mode; first upgrade in normal mode (--no-guest), or explicitly reconcile the owned block's harness guard, then retry --guest"
        fi
      fi
      # Guarded pre-snapshot policies retain the existing adoption semantics.
      if [ "$guarded" -eq 1 ] && [ ! -f "$TARGET_DIR/$base" ]; then
        mkdir -p "$(dirname "$TMPDIR_WORK/preserve-$rel")"
        touch "$TMPDIR_WORK/preserve-$rel"
        continue
      fi
      shared_safe_path "$base" && [ -f "$TARGET_DIR/$base" ] ||
        shared_refuse "unguarded owned policy $rel lacks a safe base $base; restore its last pristine snapshot or explicitly reconcile its owned harness guard without discarding custom text"
      merged="$TMPDIR_WORK/retained-merged"
      rc=0
      git merge-file -p "$block" "$TARGET_DIR/$base" "$TMPDIR_WORK/retained-upstream" > "$merged" || rc=$?
      [ "$rc" -eq 0 ] ||
        shared_refuse "owned policy merge conflict for $rel against $base; preserve custom text and reconcile the block explicitly before retrying"
      head -c "$(wc -c < "$expected")" "$merged" | cmp -s "$expected" - ||
        shared_refuse "merged owned policy $rel lacks the harness guard; reconcile the block against $base explicitly"
      mkdir -p "$(dirname "$TMPDIR_WORK/preserve-$rel")"
      touch "$TMPDIR_WORK/preserve-$rel"
      if [ "$guarded" -eq 1 ] && { [ "$rel" != "$active" ] || [ -f "$TMPDIR_WORK/keep-$rel" ]; }; then continue; fi
      cmp -s "$merged" "$block" || policy_backup_preflight "$rel"
      [ "$guarded" -eq 0 ] || continue
      # Ephemeral plan only, not another project registry. The existing block
      # installer performs the same preserving merge and documented backup.
      mkdir -p "$(dirname "$TMPDIR_WORK/scope-$rel")"
      touch "$TMPDIR_WORK/scope-$rel"
    done
  done
}

install_retained_policies() {
  local provider rel mode
  for provider in claude codex copilot; do
    configure_provider "$provider"
    for rel in $POLICY_CANDIDATES; do
      [ -f "$TMPDIR_WORK/scope-$rel" ] || continue
      POLICY_DEST="$rel"
      POLICY_LABEL="$rel"
      POLICY_SNAPSHOT="$SNAPSHOT_BASE/$rel.block"
      mode=normal
      [ "$rel" != CLAUDE.local.md ] || mode=guest
      install_claude_md "$TARGET_DIR/$rel" "$mode" "$POLICY_EMITTER"
    done
    write_provider_manifest
  done
}

# rel_to_base <dest> -> absolute path under SNAPSHOT_BASE mirroring <dest>'s
# path relative to TARGET_DIR, 1:1 (including the .claude/ prefix — no
# managed file lives under .claude/.domestique/, so this never recurses).
rel_to_base() {
  local dest="$1"
  if [ "$CURRENT_PROVIDER" = shared ] && [ "$SHARED_PRESENT" -eq 0 ] &&
     [ -f "$TARGET_DIR/.codex/.domestique/base/${dest#"$TARGET_DIR"/}" ]; then
    printf '%s' "$TARGET_DIR/.codex/.domestique/base/${dest#"$TARGET_DIR"/}"
    return
  fi
  printf '%s' "$SNAPSHOT_BASE/${dest#"$TARGET_DIR"/}"
}

# snapshot_plain <dest> <content-file>
# Record the pristine emitted content as the future merge base. Call only
# after <dest> was actually created/overwritten with <content-file>'s bytes
# (never on an identical-skip — the snapshot is already correct there).
snapshot_plain() {
  local dest="$1" content="$2" basepath
  basepath="$SNAPSHOT_BASE/${dest#"$TARGET_DIR"/}"
  # A preserved custom body can merge identically on every rerun. Do not
  # churn its manifest timestamp when the authoritative pristine base agrees.
  if [ -f "$basepath" ] && cmp -s "$content" "$basepath"; then
    return 0
  fi
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
  policy_copy "$content" "$basepath"
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
  # Cutover has already preserved native metadata against pristine snapshots.
  # Force cannot discard that transfer on this same invocation.
  local FORCE="$FORCE"
  if [ "$PREVIEW_MIGRATE" -eq 1 ] && [ "$CURRENT_PROVIDER" = copilot ]; then FORCE=0; fi
  if [ "$PREVIEW_MIGRATE" -eq 1 ] && [ "$CURRENT_PROVIDER" = copilot ] &&
     [ "$DRY_RUN" -eq 1 ]; then
    note_dry "publish validated preview replacement $dest (metadata retained, pristine snapshot)"
    SUM_UPDATED+=("$dest (preview migration)")
    return 0
  fi
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
    if [ ! -e "$ident_basepath" ] || { [ "$CURRENT_PROVIDER" = shared ] && [ "$SHARED_PRESENT" -eq 0 ]; }; then
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

# Splice only the owned body; head/tail preserve host bytes, including a
# suffix without a final newline (awk's print would silently add one).
splice_policy_body() {
  local dest="$1" body="$2" result="$3" begin end
  begin="$(grep -nxF "$MARKER_BEGIN" "$dest" | cut -d: -f1)"
  end="$(grep -nxF "$MARKER_END" "$dest" | cut -d: -f1)"
  {
    head -n "$begin" "$dest"
    cat "$body"
    tail -n "+$end" "$dest"
  } > "$result"
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
  local FORCE="$FORCE"
  if [ -f "$TMPDIR_WORK/keep-${dest##*/}" ]; then
    SUM_SKIPPED+=("$dest (guarded tracked personal policy retained in guest mode)")
    return 0
  fi
  # --force does not discard customized text during an isolation upgrade,
  # including the later active-destination pass in this same invocation.
  [ ! -f "$TMPDIR_WORK/preserve-${dest#"$TARGET_DIR"/}" ] || FORCE=0
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
      policy_copy "$blk" "$dest" new
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

    splice_policy_body "$dest" "$policybody" "$result"

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
            splice_policy_body "$dest" "$mergedblock" "$result"

            if cmp -s "$result" "$dest"; then
              SUM_SKIPPED+=("$dest (managed block already current)")
              return 0
            fi

            local backup="$dest.bak.$TS"
            if [ "$DRY_RUN" -eq 1 ]; then
              note_dry "backup $dest -> $backup, then merge managed block (clean)"
            else
              policy_copy "$dest" "$backup" new
              policy_copy "$result" "$dest"
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
          splice_policy_body "$dest" "$mergedblock" "$conflictresult"

          if [ "$DRY_RUN" -eq 1 ]; then
            note_dry "merge $dest block ($kind) — would write $newfile, back up $dest -> $backup2, leave $dest untouched"
          else
            policy_copy "$conflictresult" "$newfile" new
            policy_copy "$dest" "$backup2" new
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
    policy_copy "$dest" "$backup" new
    policy_copy "$result" "$dest"
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
        # Canonical visibility belongs to the shared state, not this guest.
        grep -vE '^\.agents/skills/dom-(decompose|goal)/' "$codex_ownership" || true
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
      fi
    fi
    if [ "${COPILOT_GUEST_SELECTED:-0}" -eq 1 ]; then
      if [ -f "$target/.github/.domestique/guest-excludes" ]; then
        cat "$target/.github/.domestique/guest-excludes"
      elif [ -f "$TMPDIR_WORK/copilot-excludes" ]; then
        cat "$TMPDIR_WORK/copilot-excludes"
      fi
    fi
    if [ "$SHARED_REMOVE" -eq 0 ]; then
      if [ "$SHARED_GUEST" -eq 1 ] && [ "$SHARED_PRESENT" -eq 1 ]; then
        printf '.agents/.domestique/\n'
        cat "$target/.agents/.domestique/guest-excludes"
      elif [ ! -e "$target/.agents/.domestique" ] && [ "${CODEX_GUEST_SELECTED:-0}" -eq 1 ]; then
        # Dry-run or a legacy uninstall still uses the original owner.
        printf '.agents/.domestique/\n'
        if [ -f "$target/.codex/.domestique/guest-excludes" ]; then
          grep -E '^\.agents/skills/dom-(decompose|goal)/' "$target/.codex/.domestique/guest-excludes" || true
        else
          [ "${CODEX_PREEXIST_DOM_DECOMPOSE_SKILL:-0}" -eq 1 ] || printf '.agents/skills/dom-decompose/SKILL.md\n'
          [ "${CODEX_PREEXIST_DOM_GOAL_SKILL:-0}" -eq 1 ] || printf '.agents/skills/dom-goal/SKILL.md\n'
          [ "${CODEX_PREEXIST_DOM_GOAL_META:-0}" -eq 1 ] || printf '.agents/skills/dom-goal/agents/openai.yaml\n'
        fi
      fi
    fi
    if { [ "${CLAUDE_GUEST_SELECTED:-0}" -eq 1 ] && [ -e "$target/.claude/.domestique/beads-owned" ]; } ||
       { [ "${CODEX_GUEST_SELECTED:-0}" -eq 1 ] && [ -e "$target/.codex/.domestique/beads-owned" ]; } ||
       { [ "${COPILOT_GUEST_SELECTED:-0}" -eq 1 ] && [ -e "$target/.github/.domestique/beads-owned" ]; }; then
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
  local copilot_marker="$TARGET_DIR/.github/.domestique/beads-owned"
  if [ ! -d "$TARGET_DIR/.beads" ]; then
    if [ "$DRY_RUN" -eq 0 ]; then
      rm -f "$claude_marker" "$codex_marker" "$copilot_marker"
    fi
    return 0
  fi
  [ "${ANY_GUEST:-0}" -eq 1 ] || return 0
  if [ ! -e "$claude_marker" ] && [ ! -e "$codex_marker" ] && [ ! -e "$copilot_marker" ]; then
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
  if [ "${COPILOT_GUEST_SELECTED:-0}" -eq 1 ]; then
    mkdir -p "$(dirname "$copilot_marker")"
    : > "$copilot_marker"
  fi
}

# do_uninstall <target-dir>
# Remove everything domestique installed into <target-dir>, and only that.
# See usage() --uninstall for the summary of what is (and is not) removed.
do_uninstall() {
  local target="$1"
  local anything_done=0
  if [ "$SHARED_PRESENT" -eq 1 ] &&
     { [ "$UNINSTALL_CODEX" -eq 1 ] || [ "$SHARED_CODEX" -eq 0 ]; } &&
     { [ "$UNINSTALL_COPILOT" -eq 1 ] || [ "$SHARED_COPILOT" -eq 0 ]; }; then
    SHARED_REMOVE=1
  fi

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
  # Traverse the same ownership/selection inventory twice, so even the last
  # preservation collision refuses before any earlier file/state is removed.
  local provider state_rel rel emitter dest staged basepath reference phase
  for phase in preflight apply; do
    if [ "$phase" = apply ] && [ "$DRY_RUN" -eq 0 ]; then MUTATION_STARTED=1; fi
  while IFS='|' read -r provider state_rel rel emitter; do
    [ -z "$rel" ] && continue
    local ownership="$target/$state_rel/guest-excludes"
    case "$rel" in
      .agents/skills/dom-decompose/*|.agents/skills/dom-goal/*)
        if [ "$SHARED_PRESENT" -eq 1 ]; then
          [ "$SHARED_REMOVE" -eq 1 ] || continue
          provider=shared
          state_rel=".agents/.domestique"
          ownership="$target/$state_rel/guest-excludes"
        elif [ "$SHARED_COPILOT" -eq 1 ]; then
          continue
        fi
        ;;
    esac
    [ "$provider" = "claude" ] && [ "$UNINSTALL_CLAUDE" -eq 0 ] && continue
    [ "$provider" = "codex" ] && [ "$UNINSTALL_CODEX" -eq 0 ] && continue
    [ "$provider" = "copilot" ] && { [ "$UNINSTALL_COPILOT" -eq 0 ] || [ "$SHARED_COPILOT" -eq 0 ]; } && continue
    [ "$provider" = "claude" ] && [ "$claude_evidence" -eq 0 ] && continue
    [ "$provider" = "codex" ] && [ "$codex_evidence" -eq 0 ] && continue
    dest="$target/$rel"
    [ -e "$dest" ] || continue
    if [ "$provider" != "claude" ] && [ -e "$ownership" ] &&
       ! grep -qxF "$rel" "$ownership" 2>/dev/null; then
      [ "$phase" != apply ] || SUM_KEPT+=("$dest (pre-existing; never domestique-owned)")
      continue
    fi
    staged="$TMPDIR_WORK/uninstall_staged"
    "$emitter" > "$staged"
    basepath="$target/$state_rel/base/$rel"
    reference="$basepath"
    [ -e "$reference" ] || reference="$staged"

    if [ "$phase" = preflight ]; then
      if [ "$FORCE" -eq 0 ] && ! cmp -s "$dest" "$reference"; then
        shared_safe_path "$rel.uninstalled.$TS" && [ ! -e "$dest.uninstalled.$TS" ] ||
          shared_refuse "unsafe or occupied uninstall preservation $rel.uninstalled.$TS; preserve it and retry with a new timestamp"
      fi
      continue
    fi

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
        policy_copy "$dest" "$kept" new
        rm -f "$dest"
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
copilot|.github/.domestique|.github/agents/domestique-v2-copilot-implementer.agent.md|emit_copilot_implementer
copilot|.github/.domestique|.github/agents/domestique-v2-copilot-reviewer.agent.md|emit_copilot_reviewer
copilot|.github/.domestique|.github/skills/domestique-v2-copilot/SKILL.md|emit_copilot_skill
copilot|.github/.domestique|.github/skills/domestique-v2-copilot-decompose/SKILL.md|emit_copilot_decompose_skill
copilot|.github/.domestique|.github/skills/domestique-v2-copilot-goal/SKILL.md|emit_copilot_goal_skill
UNINSTALL_FILES
  done

  # --- 2. managed policy blocks for selected providers --------------------
  local policyfile policymode policyemitter policybase
  while IFS='|' read -r provider policyfile policymode policyemitter policybase; do
    [ "$provider" = "claude" ] && [ "$UNINSTALL_CLAUDE" -eq 0 ] && continue
    [ "$provider" = "codex" ] && [ "$UNINSTALL_CODEX" -eq 0 ] && continue
    [ "$provider" = "copilot" ] && [ "$UNINSTALL_COPILOT" -eq 0 ] && continue
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
        policy_copy "$dest" "$backup" new
      fi
      SUM_BACKEDUP+=("$backup")
    fi

    if grep -q '[^[:space:]]' "$result" 2>/dev/null; then
      if [ "$DRY_RUN" -eq 1 ]; then
        note_dry "strip managed block from $dest, leaving the rest of the file intact"
      else
        policy_copy "$result" "$dest"
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
copilot|.github/copilot-instructions.md|normal|emit_copilot_policy|.github/.domestique
UNINSTALL_POLICIES

  # --- 3. managed block in <git-common-dir>/info/exclude ------------------
  # A scoped uninstall retains an exact union for any other provider that is
  # still guest-installed. Only the final guest-provider removal strips it.
  local keep_claude_guest=0 keep_codex_guest=0 keep_copilot_guest=0
  if [ "$UNINSTALL_CLAUDE" -eq 0 ] && [ "$(cat "$target/.claude/.domestique/mode" 2>/dev/null || true)" = "guest" ]; then
    keep_claude_guest=1
  fi
  if [ "$UNINSTALL_CODEX" -eq 0 ] && [ "$(cat "$target/.codex/.domestique/mode" 2>/dev/null || true)" = "guest" ]; then
    keep_codex_guest=1
  fi
  if [ "$UNINSTALL_COPILOT" -eq 0 ] && [ "$(cat "$target/.github/.domestique/mode" 2>/dev/null || true)" = "guest" ]; then
    keep_copilot_guest=1
  fi
  if [ "$SHARED_PRESENT" -eq 1 ] && [ "$SHARED_REMOVE" -eq 0 ]; then
    resolve_shared_visibility
    write_shared_mode
  fi

  if [ "$keep_claude_guest" -eq 1 ] || [ "$keep_codex_guest" -eq 1 ] || [ "$keep_copilot_guest" -eq 1 ] ||
     { [ "$SHARED_REMOVE" -eq 0 ] && [ "$SHARED_GUEST" -eq 1 ]; }; then
    CLAUDE_GUEST_SELECTED="$keep_claude_guest"
    CODEX_GUEST_SELECTED="$keep_codex_guest"
    COPILOT_GUEST_SELECTED="$keep_copilot_guest"
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
  for snapshot_dir in "$target/.claude/.domestique" "$target/.codex/.domestique" "$target/.github/.domestique" "$target/.agents/.domestique"; do
    case "$snapshot_dir" in
      "$target/.claude/.domestique") [ "$UNINSTALL_CLAUDE" -eq 1 ] || continue ;;
      "$target/.codex/.domestique") [ "$UNINSTALL_CODEX" -eq 1 ] || continue ;;
      "$target/.github/.domestique") [ "$UNINSTALL_COPILOT" -eq 1 ] || continue ;;
      "$target/.agents/.domestique") [ "$SHARED_REMOVE" -eq 1 ] || continue ;;
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
  SELECT_CLAUDE=0; SELECT_CODEX=0; SELECT_COPILOT=0
  [ "$UNINSTALL_CLAUDE" -eq 0 ] && [ -d "$target/.claude/.domestique" ] && SELECT_CLAUDE=1
  [ "$UNINSTALL_CODEX" -eq 0 ] && [ -d "$target/.codex/.domestique" ] && SELECT_CODEX=1
  [ "$UNINSTALL_COPILOT" -eq 0 ] && [ -d "$target/.github/.domestique" ] && SELECT_COPILOT=1
  platform_set
  persist_platform_set

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
    if [ "$UNINSTALL_COPILOT" -eq 1 ]; then
      local dir
      for dir in .github/agents .github/skills/domestique-v2-copilot .github/skills/domestique-v2-copilot-decompose .github/skills/domestique-v2-copilot-goal .github/skills .github; do
        rmdir "$target/$dir" 2>/dev/null || true
      done
    fi
    if [ "$SHARED_REMOVE" -eq 1 ]; then
      local shared_dir
      for shared_dir in .agents/skills/dom-goal/agents .agents/skills/dom-goal .agents/skills/dom-decompose .agents/skills .agents; do
        rmdir "$target/$shared_dir" 2>/dev/null || true
      done
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

lifecycle_preflight
preview_preflight
copilot_preflight
shared_preflight
policy_preflight

if [ "$UNINSTALL" -eq 1 ]; then
  UNINSTALL_CLAUDE=1
  UNINSTALL_CODEX=1
  UNINSTALL_COPILOT=1
  if [ "$PLATFORM_EXPLICIT" -eq 1 ]; then
    UNINSTALL_CLAUDE=0
    UNINSTALL_CODEX=0
    UNINSTALL_COPILOT=0
    case "$PLATFORM_ARG" in
      claude) UNINSTALL_CLAUDE=1 ;;
      codex) UNINSTALL_CODEX=1 ;;
      both) UNINSTALL_CLAUDE=1; UNINSTALL_CODEX=1 ;;
      copilot) UNINSTALL_COPILOT=1 ;;
      all) UNINSTALL_CLAUDE=1; UNINSTALL_CODEX=1; UNINSTALL_COPILOT=1 ;;
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
[ "$DRY_RUN" -eq 1 ] || MUTATION_STARTED=1

if [ "$PREVIEW_MIGRATE" -eq 1 ]; then
  if [ "$DRY_RUN" -eq 1 ]; then
    note_dry "validated preview cutover: preserve source, revoke old receipt, publish five replacements and snapshots, remove only unchanged .github public aliases and their exact exclusion contribution"
  else
    preview_migration apply || exit $?
  fi
fi

install_retained_policies

ANY_GUEST=0
CLAUDE_GUEST_SELECTED=0
CODEX_GUEST_SELECTED=0
COPILOT_GUEST_SELECTED=0
if [ "$SELECT_CLAUDE" -eq 0 ] &&
   [ "$(cat "$TARGET_DIR/.claude/.domestique/mode" 2>/dev/null || true)" = guest ]; then
  CLAUDE_GUEST_SELECTED=1
  ANY_GUEST=1
fi
if [ "$SELECT_CODEX" -eq 0 ] &&
   [ "$(cat "$TARGET_DIR/.codex/.domestique/mode" 2>/dev/null || true)" = guest ]; then
  CODEX_GUEST_SELECTED=1
  ANY_GUEST=1
fi
if [ "$SELECT_COPILOT" -eq 0 ] &&
   [ "$(cat "$TARGET_DIR/.github/.domestique/mode" 2>/dev/null || true)" = guest ]; then
  COPILOT_GUEST_SELECTED=1
  ANY_GUEST=1
fi
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
if [ "$SELECT_COPILOT" -eq 1 ]; then
  configure_provider copilot
  resolve_provider_mode
  if [ "$GUEST" -eq 1 ]; then
    ANY_GUEST=1
    COPILOT_GUEST_SELECTED=1
    echo "Note: Copilot guest mode is skills-only; bootstrap with /domestique-v2-copilot." >&2
  fi
  install_current_provider
fi
if [ "$SELECT_CODEX" -eq 1 ] || [ "$SELECT_COPILOT" -eq 1 ]; then
  install_shared
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
        if [ "$ANY_GUEST" -eq 1 ] || [ "$(cat "$TARGET_DIR/.agents/.domestique/mode" 2>/dev/null || true)" = guest ]; then
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
          if [ "$COPILOT_GUEST_SELECTED" -eq 1 ]; then
            mkdir -p "$TARGET_DIR/.github/.domestique"
            : > "$TARGET_DIR/.github/.domestique/beads-owned"
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
if [ "$ANY_GUEST" -eq 1 ] || [ "$SHARED_GUEST" -eq 1 ]; then
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
