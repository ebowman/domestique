# Standalone: install, upgrade and recovery

This is the **v0.6.2 release candidate guide**. The backed-up replacement
offered for an unmatched Codex pair is now available for a normal-mode Claude
pair. Replacing role content does not confirm a model or authorize a workflow.

- **Goal startup:** planning records a [workspace handoff](#workspace-handoff-from-decompose-to-goal).
  Execution rechecks the live checkout. Preserve disjoint staged and unstaged
  changes; ask before touching overlapping work. A handoff does not authorize a goal.
- **Installer upgrades:** [review the complete plan](#historical-native-role-reconciliation)
  before adopting edited legacy roles. Each role needs its own exact-path
  ancestor evidence. An unmatched role blocks adoption; its neighbors cannot
  establish ownership. A normal-mode Claude or Codex pair with two completed `no-match`
  searches can instead be backed up and **replaced by explicit choice**.
  One approval publishes a complete eligible plan, not a
  partial migration, model confirmation or readiness certificate.

See [candidate checks and limits](#v062-candidate-checks-and-limits).

Retained v0.4.4 safe-upgrade behavior: finite historical ownership proof and
pristine manifestless adoption support bounded preserving upgrades. Unknown
converted roles require explicit backup migration, not fabricated pristine
bases or automatic overwrite. Tracked guest policy writes refuse with recovery
guidance; unconfirmed model pairs receive actionable reconfirmation instructions.
Retained custom policies keep their workflows.

The v0.4.3 behavior remains: explicit unrelated-provider installs retain
completely removed Claude/Codex projections as inactive when actual safe absence
is established, rather than reactivating them from leftover owned metadata.
Metadata, pristine bases, host policy bytes and inactive guest Beads markers are
preserved. Surviving partial, unowned, guard-tampered or unsafe files still undergo
validation; explicitly selecting a damaged pair still refuses, even with `--force`.
Live-provider additive behavior and the selector-less all-provider default are
unchanged; stale history alone does not resurrect completely removed providers.
Legacy Codex canonical shared ownership still refuses reassignment.
The v0.4.2 fix still recognizes five verified historical
policy-base identities omitted by v0.4.1, without relaxing inventory authority
or conflict checks. The v0.4.1 fix still preserves customized retained policies,
adding only harness isolation to known-owned legacy blocks instead of upgrading
unrelated workflows. Independent pristine bases and genuine-conflict refusal for
explicitly selected active policies remain intact.
v0.4.0 introduced complete nested-epic or exact-task goals and soft progress
checkpoints. Explicit parent Git approval, introduced in v0.3.1,
bypasses Beads/model gates, not native permissions, scope or guest privacy.
It grants no automatic drain, push or merge authority. Model defaults and
optional setup were introduced in v0.3.0.
Implementation reviews hq-c6o.2–.6 passed; native qualification hq-c6o.8
remains **UNQUALIFIED pending user authorization for fixture/model usage**. Publication was authorized
with this limitation disclosed, not with native PASS or epic completion.
Those historical validations are instruction-level/filesystem-only, not new native UX qualification.
Historical native evidence below does not qualify v0.3.1–v0.4.4.
hq-xc2's reviewed implementation and bounded offline checks passed, but
[native coverage remains BLOCKED](#v040-release-status-and-limits);
publication does not fully qualify the epic.
The [v0.4.4 evidence and limits](#v044-release-status-and-limits) remain history,
not fresh v0.6.2 qualification.
The product is one standalone `domestique.sh`; no global runtime, `dom2` or
project enable step. See the [README](../README.md) for the workflow.

## Remote install and upgrade

After v0.6.2 is published to `main`, existing `dom` aliases that fetch
`main/domestique.sh` receive its workflow and installer changes on their next invocation,
without an alias change.
For the covered completely removed Claude/Codex case, optionally preview with
`dom --platform copilot --dry-run`, then run `dom --platform copilot`.
Neither `--force` nor manual metadata repair is needed.
For the covered historical Claude base, preview with
`dom --platform claude --dry-run`, then run `dom --platform claude`.
Hash recognition needs no `--force`.
For the covered unselected/inactive retained-policy case, ordinary
`dom --platform=copilot` needs neither `--force` nor manual repair.
Preview with `dom --dry-run`, then run `dom`. Nothing
updates in the background; publishing only a tag does not change those aliases.
Run from the intended project root; the optional positional argument is the
target directory. Bash, Git and Python 3.11+ cover the all-three path.
Native clients/model software are not installed or required for offline
configuration installation; native availability matters before execution.

```sh
curl -fsSL https://raw.githubusercontent.com/ebowman/domestique/main/domestique.sh | bash -s -- --dry-run
curl -fsSL https://raw.githubusercontent.com/ebowman/domestique/main/domestique.sh | bash -s --
curl -fsSL https://raw.githubusercontent.com/ebowman/domestique/main/domestique.sh | bash -s -- --platform copilot --dry-run
```

For repeatable preview/apply, set `REV` to the same full reviewed **published**
commit SHA for both commands (replace the placeholder before running):

```sh
REV=FULL_REVIEWED_PUBLISHED_COMMIT_SHA
curl -fsSL "https://raw.githubusercontent.com/ebowman/domestique/$REV/domestique.sh" | bash -s -- --dry-run
curl -fsSL "https://raw.githubusercontent.com/ebowman/domestique/$REV/domestique.sh" | bash -s --
```

A source checkout is optional; v0.6.2's changes are included in remote
`dom` after publication to `main`. To inspect source locally, use the selected checkout:

```sh
TARGET=$(mktemp -d)
git -C "$TARGET" init -q
bash ./domestique.sh "$TARGET" --dry-run
# Choose one preview; remove --dry-run only after reviewing it:
bash ./domestique.sh "$TARGET" --platform claude --model claude:implementer=opus --dry-run
bash ./domestique.sh "$TARGET" --platform codex --model=codex:reviewer=inherit --dry-run
bash ./domestique.sh "$TARGET" --platform copilot --model copilot:implementer=inherit --dry-run
bash ./domestique.sh "$TARGET" --platform both --model claude:implementer=opus --model=codex:reviewer=inherit --dry-run
```

The same model options work with `dom` from the target project root:

```sh
dom --platform both --model claude:implementer=opus --model=codex:reviewer=inherit --dry-run
dom --platform both --model claude:implementer=opus --model=codex:reviewer=inherit
```

Review the preview before applying. Pinning older script bytes does not reverse
migrated project state.

The version-labelled plan shows the physical target, selected providers and
normal/guest modes before target writes. Dry-run performs no target writes;
unsafe preflight instead produces preserving diagnostics. There is no installer
stdin questionnaire, so `curl | bash` works.

### Selectors and options

| Option | Meaning |
| --- | --- |
| No selector | **All Claude Code, Codex and Copilot on fresh installs and reruns.** |
| `--platform claude`, `codex`, `copilot`, `both`, `all` | Explicit selection; **both = Claude+Codex**. Installs are additive: live persisted Claude/Codex may also be selected; unselected Copilot remains. Stale history alone does not resurrect completely removed providers. Read the actual plan. |
| `--dry-run` | Preview without target changes. |
| `--guest` / `--no-guest` | Explicit mode/conversion; mutually exclusive. |
| `--model harness:role=id-or-inherit` | Repeatable per-role model override; also `--model=harness:role=value`. Rules below. |
| `--force` | Regenerate qualified role bodies while preserving model/effort choices; other differing provider files replaced without `.bak`. Managed policies still backed up. Can discard customizations, never bless unconfirmed state or bypass ownership/migration checks. |
| `--with-beads` | If `bd` is available, initialize when needed using safe skip flags. Normal mode sets up selected providers; guest uses stealth and no provider setup. Does not install Beads. |
| `--uninstall` | Remove owned configuration; optional `--platform` scopes removal, otherwise scans all three. |
| `--purge-beads` | Only with uninstall; explicitly deletes the target's `.beads`. Omit to preserve task data. |
| `--help`, `-h` | Show the selected script's full contract. |

Uninstall combines only with target, platform, dry-run, force and purge-beads,
not with guest/no-guest/with-beads/model.

### Model defaults and override precedence

| Harness | Implementer model / effort | Reviewer model / effort |
| --- | --- | --- |
| Claude | `sonnet` / inherit | `opus` / inherit |
| Codex | `gpt-5.6-sol` / `medium` | `gpt-5.6-terra` / `high` |
| Copilot | native inheritance / no effort field | native inheritance / no effort field |

These chosen IDs do not establish account entitlement or universal catalog
availability. Same-model implementer/reviewer pairs are allowed; review always
uses a fresh independent context. No installer catalog/auth lookup is required.

- Fresh providers get these defaults, configured after successful verification
  at a physical Git worktree root. No model questionnaire or Save is needed.
- Reruns preserve existing model/effort choices, **including old pristine
  defaults**. Newly added providers get fresh defaults.
- An explicit override changes only the named model, preserving existing
  effort and the partner. There is no installer effort flag. On a **fresh** role,
  selecting its shipped model retains shipped effort; any other model,
  including `inherit`, omits effort. Later `dom-models` model changes preserve effort.
- Harness is exactly `claude|codex|copilot`; role is `implementer|reviewer`.
  No aliases, wildcards or comma lists. IDs are literal, nonempty bounded strings
  (up to 512 characters), without edge whitespace/control characters; quote as
  one shell argument. Identical repeated assignments are idempotent; conflicting
  repeats and malformed/unknown assignments refuse before writes.
- Overrides must target the **requested** platform selection, not merely a
  provider retained by additive installation. No selector permits all three;
  `both` permits only Claude+Codex. `--model` is incompatible with `--force`,
  `--uninstall` and `--purge-beads`.

## First-use role setup

Valid installer-configured defaults and saved custom/inherited pairs need
**no questionnaire, Save or restart merely because fresh**. Configuration is
per physical Git worktree root and per harness; there is no global model registry.
Targets outside any Git worktree, and targets inside a worktree but not at
its root, skip model-pair setup entirely: roles and policy install as before,
exactly one informational line is printed ("Model setup skipped: requires a Git
repository" or "Model setup skipped: run dom at the repository root (<root>)
to configure role models"), and the install exits 0 with no unconfirmed-pair
state (`--model` there still refuses with exit 3). Only git's "not a git
repository" error (matched under `LC_ALL=C`) counts as non-Git; any other git
failure (dubious ownership / `safe.directory`, git missing, permission errors)
is not skipped silently: the install stays unconfirmed (exit 3) and git's own
error text is shown.

| Harness | Implementer / reviewer paths | Deterministic helper |
| --- | --- | --- |
| Claude | `.claude/agents/implementer.md` / `.claude/agents/reviewer.md` | `.claude/domestique-model-setup.py` |
| Codex | `.codex/agents/implementer.toml` / `.codex/agents/reviewer.toml` | `.codex/domestique-model-setup.py` |
| Copilot | `.github/agents/domestique-v2-copilot-implementer.agent.md` / `.github/agents/domestique-v2-copilot-reviewer.agent.md` | `.github/domestique-model-setup.py` |

### Inspect or change later

Use `/dom-models` in Claude/Copilot, `$dom-models` in Codex, in the native client
(the `opus` example is for Claude):

```text
/dom-models
/dom-models --help
/dom-models --configure
/dom-models --confirm
/dom-models --implementer opus --reviewer=opus
$dom-models
$dom-models --reviewer=inherit
$dom-models --implementer gpt-5.6-sol --implementer-effort=medium --reviewer-effort high
```

No arguments inspects saved choices read-only, not a catalog or authentication
check. `--help` works without an installed pair. `--configure` prefills current
choices; `--confirm` prepares the current unconfirmed/stale pair for review
without questions (already configured: nothing to save). Explicit settings accept
any subset of `--implementer MODEL`, `--reviewer MODEL`,
`--implementer-effort LEVEL`, `--reviewer-effort LEVEL`, separated or `=value`.
Copilot rejects effort flags. Unmentioned model/effort/partner stays unchanged.
Modes cannot mix with each other or settings. Duplicate flags (even identical),
empty values, unknown flags and harness/path selectors refuse without writes.
Literal model IDs are accepted without assuming catalog availability.
Only the actual native caller's harness and physical Git root are targeted.

`inherit` means Claude `model: inherit`, omitted Codex/Copilot model, or omitted
Claude/Codex effort. Native resolution need not equal the direct parent's model.
Use effort levels supported by the chosen native model; unsupported combinations
stop at execution, not by silently clearing effort. The exact old
`dom-decompose configure role models` argument aliases `dom-models --configure`;
ordinary planning text mentioning models does not select configuration.

The pristine installed helper prepares read-only. Review one compact summary of
project/harness, current → chosen settings, paths, scalar/pair-marker scope,
tracked consequences and relevant stale/body/copied-root warnings, then
**Save these choices? Save / Cancel**. Detailed diff is available on request;
raw hashes/diffs are not mandatory. Selection or `--confirm` is not Save consent.
Cancel writes nothing. Save needs ordinary scoped native write approval;
changed plans need renewed consent. Bodies, tools and unrelated metadata are
preserved. Wait for terminal completion and pair verification before reporting
saved; pending, partial or nonzero results are not success. Preserve recovery
information on failure; do not blindly roll back.

### First execution checklist

1. Planning (`dom-decompose BRIEF`) bypasses all setup/helper/readiness checks,
   even with missing, unconfirmed or manually edited roles. It never delegates
   or executes tasks; no reload or repeated brief is needed.
2. For managed-bead execution, verify the configured pair and actual native role discovery,
   registration, precedence, effective choices and available support evidence.
   The marker binds the physical root, harness and both role hashes, **not
   loaded native choices**. A catalog alone is not persistent role support.
   Missing optional loaded-byte/child telemetry alone is not a blocker absent
   counterevidence and with documented native resolution.
3. Reload/start a fresh native invocation only if required registrations are
   stale/unknown, not merely because files are fresh. Codex conversation roles
   may be immutable; saved edits do not change them in place.
4. Stale/unconfirmed pairs stop with `dom-models --confirm` or `--configure`;
   missing/unsafe authority needs explicit preserving installer repair.
   Unavailable models, unsupported effort or known mismatches stop with the
   affected role/reason and `--configure` route, never automatic substitution.
5. Baseline HEAD, tracked/untracked edits and index ownership before work or
   branch changes; preserve separable unrelated changes exactly. Overlap,
   collisions, uncertain ownership or an unsafe branch switch need narrow
   clarification, not blanket cleanup. Installation/Save never queues or authorizes
   a goal. After a configuration detour, give a fresh explicit goal naming the
   intended target; a fresh valid install alone needs no renewed authorization.

   #### Workspace handoff from decompose to goal

   The handoff is new in v0.6.0.
   For example, `/dom-decompose Add a CSV header check` returns a graph and
   handoff; a separate `/dom-goal <returned-epic-id>` authorizes execution.
   Codex uses `$dom-decompose` and `$dom-goal`. If the client still says to
   clean the index first, inspect the **installed native bodies**, not just the
   version string: look for `Workspace readiness handoff` in decompose and
   `Named goal workspace readiness` in goal. For Copilot these are
   `.github/skills/domestique-v2-copilot-{decompose,goal}/SKILL.md`.
   If missing, preview `bash /path/to/candidate/domestique.sh "$TARGET"
   --platform copilot --dry-run` (retain `--guest` for a guest install);
   review the preview before applying without `--dry-run`. Do not force over
   local policy. If disk is current but the loaded instructions are stale,
   refresh the native session and issue a fresh explicit named goal. A real
   overlap still needs a decision on the affected path, not a different prompt.

   Within the active harness, an explicit planning request still
   authorizes only the Beads plan (epic, bounded children, real dependencies and
   graph report). No role inspection/setup, delegation, claim, closure, source
   edit, branch change, staging or commit is part of planning.

   **Read-only observation.** Before plan writes, identify the physical worktree
   root, HEAD commit and branch (or detached state), and any in-progress Git
   operation. Compare each child's intended write paths with the index relative
   to HEAD, worktree relative to the index, and untracked paths that could collide.
   Report the baseline and the effects of actual planning writes with the plan:
   use paths/status or fingerprints, not diffs, private file contents or secrets.
   Distinguish pre-existing changes from metadata attributable to specific
   successful Beads operations and their returned IDs. A changed path after a
   write is not by itself proof of authorship. Mark unknown paths, attribution or
   branch suitability explicitly; neither a directory name nor a role filename
   establishes ownership.

   **Decision at execution.** The handoff is evidence, not authority. On a named,
   authorized goal, resolve scope/closed no-ops and apply the existing read-only
   role gate. Before any execution write, claim or dispatch, observe the actual
   checkout again, including metadata changed by planning. Reclassify against the
   current target; recheck before branch changes, each bead and finalization.
   Never treat a failed read as a clean result.

   | Decision | When and what to do |
   | --- | --- |
   | Proceed as-is | Reuse a suitable dedicated non-default branch. If a new dedicated local branch at the current HEAD would preserve the index and all worktree bytes, create it at goal startup, not as a preparation bead. |
   | Bounded preparation | Plan a prerequisite only for a specific necessary, in-scope action with known ownership, a safe starting state and a verifiable result. Name the dependent work and what makes it ready; do not make the prerequisite itself depend on that result. Execute it only under the ordinary goal gates. |
   | Ask about overlap | If a collision, uncertain ownership, unsafe switch, foreign merge/rebase or unresolved user choice prevents safe progress, identify the affected operation/paths and ask for the missing decision. Do not assign a cleanup bead, finish or abort someone else's operation, stash, reset, discard or broadly stage. |

   **Fixture acceptance.** Compare branch/HEAD, staged entries, worktree bytes
   and actual Beads state before planning, after planning and at goal startup.
   Only the requested graph changes during planning; the following are execution
   outcomes, not a global cleanliness test:

   | Fixture | Observable result |
   | --- | --- |
   | Clean | No prep child. Reuse the suitable branch or create the dedicated branch at the same HEAD; index and files unchanged by branch setup. Only then claim the authorized ready task (do not reclaim an already-owned assignment). |
   | Separable staged, unstaged and untracked changes | No cleanup, prep child or redundant permission. Start the scoped task as above; unrelated staged entries and worktree bytes survive startup and the reviewed task commit unchanged and excluded from that commit. |
   | Overlapping staged/unstaged edit or untracked destination | Ask narrowly before affected branch/index/file changes, claim, dispatch or closure. Keep the plan and user's edits intact; independently safe authorized work need not wait. |
   | Changed since plan | Recompute, don't replay: a newly separable change survives; a new collision stops affected work before mutation or claim. Recheck planning-induced metadata too: attributable bookkeeping alone does not block; mixed or unknown changes cannot be adopted as plan output. |
   | Guest | Permit the same safe host task/branch and local Beads lifecycle. Personal Beads and harness state stay local, never staged or committed; no tracked ignore edits to hide them. In normal mode only reviewed, known in-scope project metadata may enter a scoped commit. |

   **Qualification boundary (hq-ha2.4).** Run
   `python3 -B test/copilot-astra-native-tests.py --handoff /tmp` for the
   controlled fixtures. Each installs the candidate in a fresh Git root and
   retains its graph, branch/HEAD, index, diffs and file fingerprints before
   planning, after planning and across goal startup. The graph is synthetic
   JSON, not a live Beads database. Decisions, planning writes, branch setup
   and task commits in these seven cases are **fixture operations**, not actions
   observed from a planner or goal agent. Guest tests use a pre-existing local
   Beads exclusion and the installer's guest harness exclusions.
   **7/7 fixture cases passed** (dirty, guest, tracked overlap, untracked
   collision, stale collision, stale disjoint, already-ready branch). Evidence:
   `/tmp/hq-ha2.4-wyfs68uc/`. For example, the dirty fixture's scoped commit
   `04076cb` changed only `owned.txt`; `staged.txt` remained pre-staged and the
   tracked synthetic graph remained unstaged. Two installed planning/goal
   projection tests across the three providers and seven runner unit tests
   also passed; those are offline checks.

   The separate opt-in `--native-cli /absolute/path/to/copilot` runs only one
   action probe (180-second session deadline). It supplies installed contract
   text, simulated scope/role checks and a simulated independent PASS; only
   the client may start the branch and finalize the reviewed change. Inspect
   the transcript, usage and Git snapshots, not just exit status. On `2ee8b83`,
   Copilot CLI **1.0.114** exited 1: `No authentication information found.`
   Requested `gpt-6-astra`; **actual model: none** (zero requests, empty
   `modelMetrics`). No tool action, branch switch or commit; the disjoint
   staged entry remained intact. Evidence: `/tmp/hq-ha2.4-psx7w4iz/native/`.
   No credential lookup or retry by the harness. **Native dirty-start
   continuation is unqualified**; neither this probe nor the Git simulations
   establish actual Beads lifecycle, role dispatch or independent review.

<a id="upcoming-named-goals-reviewed-candidate"></a>

### Complete named goals

v0.5.0 retains v0.4.0 named scope and adds scoped completion.
Use remote (after publication) or local preview/apply above; preserving reruns retain
model/effort choices. Refresh stale native instructions as needed. Defaults,
optional model setup and explicit model-editor Save are unchanged.

In Claude/Copilot use `/dom-goal ID`; in Codex use `$dom-goal ID`.
Resolve the real Beads type before execution: an epic includes **all unfinished
transitive parent-child descendants**, including nested epics and traversal
through closed intermediate nodes. A non-epic selects **only itself**, even
when it has children. Siblings, external prerequisites and discovered-from links
do not expand scope. Verified closed non-epics or fully closed epic scopes are
no-ops; a closed epic with unfinished descendants is an inconsistency, not completion.

Clear current user/native named execution objectives also authorize work,
including “do it” referring to the current concrete named plan. A native
goal/autopilot objective naming the target qualifies; a bare toggle, quoted text,
skill loading/matching, planning or Save does not. Ambiguous scope needs clarification.
For smaller runs say “Execute only this bead BEAD_ID”, “Execute one next bead in
EPIC_ID”, or “Execute at most 3 beads in EPIC_ID”; these are user bounds, not CLI
flags. Ordinary next-ready requests remain one bead.

Every **15 successful closures is a soft progress checkpoint**: report and
continue to 16, 31 and beyond without a pause, renewed permission or expiry.
Current user count/time/cost limits and actual runtime/session budgets bind.
Cancellation/objective change and material ambiguity stop affected execution.
Use the progress/recovery rules below for review gaps, task-caused regressions
and recoverable errors. No provider/session-limit bypass or automatic cross-session
resumption is promised. Preserve concrete unfinished IDs, reasons and commit state.
Blocked/deferred/other-owned branches do not stop other runnable authorized branches;
no runnable work with unfinished scope is **BLOCKED**, not COMPLETE.
Root and nested-epic acceptance require their own evidence, required integration
validation and independent PASS, not just closed children; missing root evidence
is **ROOT UNFINISHED**.

Keep one task in flight on a dedicated non-default branch, fresh independent
review before scoped commit/closure, and focused relevant validation rather than
a full suite per bead/checkpoint. The parent hands off verified claim state;
an already-owned in-progress assignment is not reclaimed. No automatic
merge/push occurs in the loop; separately explicit parent Git approval below
remains valid.

#### Scoped completion, review and recovery

- Authorization covers necessary in-scope fixes, validation, local commits and
  bookkeeping without redundant permission, unless the user restricts it.
  The parent owns commit/closure; implementers stay within their brief and never
  commit/close, and reviewers remain read-only in a fresh independent context.
- Baseline and recheck HEAD, tracked/untracked edits and the index, including
  role configuration. Global cleanliness is not required. Preserve unrelated
  edits and staged entries exactly; never adopt user edits implicitly. Overlap,
  untracked collisions, uncertain ownership or unsafe branch switches stop only
  affected work for clarification. Never stash, discard, hide or broadly stage.
- Independent fresh PASS on the exact owned changes precedes finalization.
  Stage only reviewed paths/hunks with literal pathspecs, inspect the staged
  diff and exclude unrelated pre-staged changes while preserving their index.
  If safe isolation is impossible, ask narrowly. Keep one scoped commit per
  changed bead. Verify an existing accepted commit rather than duplicate it.
  A clean reviewed state is valid; a no-code decision needs durable review
  evidence, not an empty commit. Close and verify actual state.
- Commit failure stops without closure; reconcile Git state before safe retry.
  Close failure preserves the commit ID and actual unfinished/unknown state;
  reconcile before retry, never recommit or roll back to hide failure.
  Normal-mode metadata is explicitly reviewed/exported/staged only at known
  in-scope paths after checking configuration and diff, never broad `.beads/`
  staging. Guest personal state remains local and unstaged. Bookkeeping
  dirtiness alone is not a blocker; unknown ownership is.
- Record acceptance blockers and evidence after every fresh review. Correct
  in-scope gaps and task-caused regressions, then obtain fresh review. Continue
  while specific blockers decrease, required criteria remain intact and actual
  budgets permit; there is no arbitrary second-review or total-cycle cap.
- Unchanged findings or oscillation require a materially different bounded
  hypothesis, action and observable success check. Default: **at most two
  nonprogress recovery attempts per bead, cumulative**, never reset by temporary
  progress or rephrasing. If neither restores measurable progress, or nonprogress
  recurs after the allowance is spent, stop with concrete blockers. Report the
  allowance/consumption; do not invent time/credit ceilings.
- Only transient reads or demonstrably idempotent operations permit **at most
  two retries per failing operation**, then ERROR and stop affected work.
  Reconcile uncertain writes before repetition; no blind claim/create/commit/close
  retries. Failed/unusable queries never mean empty, complete or successful;
  suspend dependent dispatch until valid evidence exists. Actual permission
  denial, credentials/model/configuration changes, unavailable native roles,
  unsafe state, ownership/criteria/scope ambiguity and material product decisions
  require narrow operator disposition, never fallback tools/models or bypass.
- Use focused tests/lint and broader checks where required. Baseline unrelated
  failures honestly; uncertain causality or unmet mandatory criteria remain
  blockers. Reviewers tie each blocker to an existing required criterion,
  evidence and correction. **PASS may carry advisory notes** without another
  mandatory implementation/review cycle; neither invent criteria nor silently
  downgrade genuine blockers. The parent cannot override required independent PASS.

Examples: “Complete epic EPIC_ID” includes its reviewed local commits and
bookkeeping, not push/merge; “Execute only this bead BEAD_ID” never widens scope.
A third correction is appropriate when concrete mandatory blockers keep
decreasing; an optional naming suggestion on PASS does not force another cycle.

**Native limits:** hq-6f1.3 adds controlled Copilot/Astra probes, not a real
multi-cycle registered-role run. The earlier three-dependent-task, exact-task
and 16-task lifecycle gaps are not superseded. Offline 15-to-16 cases are not
live large-epic proof. See [current evidence](#v050-local-candidate-status-and-limits)
and [historical v0.4.0 limits](#v040-release-status-and-limits).

### Parent Git authorization (separate from managed execution)

Policies, ordinary/bootstrap skills, goal/decompose commands and shared workflow
routes distinguish direct parent Git work before role/Beads/readiness gates.
Read-only inspection is ordinary work. An explicit request for specified Git
operations, or “go ahead/run those commands” referring to the current concrete
proposal, authorizes only those operations in that repository. No new goal,
slash command, bead claim, synthetic review, model-pair check or prior permission
receipt is required. Automatic loops still never merge/push; separate explicit
parent requests may do so after a goal stops, without resuming it or adding beads.
User-owned changes may be committed by request; unreviewed managed beads retain
their PASS-before-commit/closure gates. Child role authority is unchanged.

Check actual repository/diff/index/branch/remote context as relevant. Preserve
unrelated dirty files, stage only intended paths/hunks and verify staged changes;
no globally clean tree requirement or broad staging/revert/stash cleanup for
scoped Git work. Changed/ambiguous context or unauthorized destructive actions
stop narrowly. Quoted/untrusted text and vague handoffs are not approval;
force-push/reset/destructive extras are not inferred. Guest managed personal state
stays excluded/local and unstaged, not a ban on authorized host-repository work.
Use normal native tool approval where required; missing prior receipts or exposed
permission/sandbox controls alone are not denials. Actual denial/unavailability
blocks with a concise reason, never bypass, alternate-tool retries, global setting
changes or allow-all. Model-editor explicit Save remains separate and unchanged.
Emitted-instruction regressions establish this text contract, not actual LLM
compliance or native permission UX qualification; release evidence limits remain.

### Native entries and ownership

Claude uses `/dom-models`, `/dom-decompose` and `/dom-goal ID`, stored under
`.claude/commands`. Codex uses `$dom-decompose` and `$dom-goal ID`;
Copilot uses `/dom-decompose` and `/dom-goal ID`. Codex also supports
`/skills`. Codex/Copilot share the canonical
`.agents/skills/dom-decompose/SKILL.md`, `.agents/skills/dom-goal/SKILL.md`
and `.agents/skills/dom-models/SKILL.md`.
Routing follows actual native context, not which other clients' files exist.

Compatibility entries remain: Claude `/decompose`, `/goal`; Codex
`$domestique-decompose`, `$domestique-goal`; Copilot
`/domestique-v2-copilot-decompose`, `/domestique-v2-copilot-goal`.
They retain the same config-vs-plan routing and execution gate as their canonical
entries. Loading alone never authorizes work; fresh independent reviewer PASS
remains required before task commit/closure. [Complete named goals](#complete-named-goals)
use epic/non-epic scope, with no default one-bead cap for named epics.
Ordinary next-ready requests still mean one reviewed bead.

Provider snapshots live in `.claude/.domestique`, `.codex/.domestique` and
`.github/.domestique`; shared routes are owned by `.agents/.domestique`.
The flat `snapshot_format=1` manifests and pristine `base/` files remain the
authority, alongside mode/selection/exclusion records. Normal policy blocks
live in `CLAUDE.md`, `AGENTS.md` (or existing `AGENTS.override.md`) and
`.github/copilot-instructions.md`.

## Preserving upgrades and mode conversion

Canonical emitters ship in `domestique.sh`; a source version bump or download
does not refresh installed policies, native registrations or cached instructions.
Apply the reviewed installer to the intended project after previewing the same
source/flags. Reload stale instructions/registrations according to the native
client, starting a fresh invocation when needed (Codex conversation roles may
be immutable). Verify effective roles and current projections, not just a
manifest version: untouched snapshots may retain exact historical provenance.
No automatic refresh of ignored `CLAUDE.md`, `CLAUDE.local.md` or `.claude/`
in this source checkout, and no user configuration changes, accompany release
preparation. Release bytes reach `main` through a separate publication step,
not through local version changes.

Compatible snapshot upgrades preserve model/effort scalars even when they equal
older shipped defaults; other compatible customizations use three-way merges.

| Existing role state | Preserving rerun |
| --- | --- |
| Valid configured pair | Preserve choices; safely merge qualified bodies and refresh verification. No questionnaire. |
| Recognized owned legacy, no marker, bodies/metadata pristine apart from model/effort scalars | Preserve choices, upgrade and configure automatically. |
| Legacy custom body/tools/metadata, stale/body-edited marker, copied/moved root | Preserve roles unconfirmed; review current bytes with `dom-models --confirm` or change via `--configure`. Model overrides wait for review/Save. |
| Recognized pre-helper inventory with required safe role bases | Install helper through preserving migration, then apply the legacy rules above. |
| Missing partner, manifest/base, helper claimed by a current inventory, modified/unowned helper, unknown authority or unsafe path | Refuse for preserving repair; neither rerun nor `--force` blesses it. |

For recognized pre-helper custom roles, a conflict-free preserving migration
upgrades old guards and helper authority but leaves the pair unconfirmed and
retains its old pristine role bases. The installer reports completed migration
and exits `3` for review/Save; repeated runs do not approve the custom bytes.
Use `dom-models --confirm` to review the migrated current pair, then Save.
Dry-run reports the same confirmation requirement without project writes.

`--force` may regenerate **qualified** role bodies but never resets saved
model/effort or confirms unreviewed state. Default-looking values alone are not
confirmation. Keep diagnostics, live files, pristine bases and backups; reconcile
the stated ownership/conflict problem, preview the same candidate and flags,
then review/Save if required. Do not delete evidence to force eligibility.
Publication is sequential across providers, not one all-provider transaction:
after interruption a completed provider may remain configured while another
failed. Nonzero/partial output is not overall success; retain recovery details.

Read the final installer status, not just the exit code:

| Status | What to do |
| --- | --- |
| `PREVIEW ONLY` | No install performed. Review the plan or resolve blockers. |
| `NOT INSTALLED by this run` | The run refused or approval was declined; an earlier install may still exist. |
| `INSTALLED` | The selected configuration was installed. This does not attest to native registration or model availability. |
| `INSTALLED — pending Save` | Publication completed. Exit `3` means review each unconfirmed pair with `dom-models --confirm` in its native client, then Save; don't reinstall to confirm. |
| `lifecycle interrupted` | Partial results may remain. Inspect the target and backups before retrying. |

A generic plain-file conflict leaves the live file unchanged, writes
the proposed merge to `.new`, preserves a `.bak.<timestamp>` and exits `3`.
Inspect and resolve explicitly; do not replace the live file blindly.
Legacy differing provider files without snapshots may be adopted unchanged,
with pristine emitted bases seeded for a subsequent merge; this is **not a role
pair ownership exception**. Unknown ownership, missing policy bases,
unsafe paths or incompatible retained policy blocks can refuse before writes.

### Historical native-role reconciliation

Without a selector, preview **all three providers together**. An edited
manifestless role may have a provable ancestor even though its current bytes
are not an installer identity. `--dry-run` reports the path, private inspection
command, changed line ranges, old/proposed choices and output digest for an
eligible proposal. Read the modes, other provider/shared effects, exclusions
and blockers too. A candidate for one path is not authority to publish a
partial plan. In particular, if any provider stays guest, a planned tracked
rewrite can veto the entire plan. Do not untrack files or convert modes as a
shortcut. A normal-mode conversion changes visibility and needs its own review.

* **Preview or decline:** `bash ./domestique.sh "$TARGET" --dry-run` or the
  equivalent `bash -s -- "$TARGET" --dry-run` stream does not change the
  project. Preview may materialize local inputs and proposed merges in scratch
  outside the target: use a trusted private location, not a shared log or a
  system that forbids even temporary copies. `--keep-local` declines adoption.
* **Approve once:** rerun without `--dry-run` in a foreground terminal. Read
  the complete plan, then type `APPLY` on `/dev/tty` or press Return to decline.
  Installer stdin is never the approval channel. Without a controlling terminal,
  save and verify the installer **outside** the target and use:

  ```sh
  bash ./domestique.sh --review-file "$TARGET"
  # Only for a complete, reviewed plan; paste the exact sha256:... printed above:
  bash ./domestique.sh --apply-file sha256:TOKEN "$TARGET"
  ```

  These transport switches must be first. Repeat the same selection and mode
  options. A token binds the saved bytes and target plan; ordinary streamed
  previews cannot issue one. Changed inputs (including index state), installer
  or proposed effects require fresh review, not reuse of an old token.
* **Conflict or refusal:** retain live files, inventory, pristine bases, index
  and existing backups. Inspect ancestor/local/upstream privately (generate
  upstream in an empty disposable directory). Resolve competing edits by hand
  and preview again, or explicitly preview `--use-upstream=PATH` for a
  history-proven conflict: this proposes backing up local bytes and taking
  upstream while preserving role model/effort. Repeat the option on approval.
  Neither it nor `--force` establishes missing ownership. After an interrupted
  publication inspect reported completed writes and backups; there is no
  blanket rollback. After successful publication, exit `3` with **review/Save
  required** means the adopted roles are still unconfirmed; review the pair in
  `dom-models --confirm` and Save. Rerunning does not approve the models.

History proof uses raw regular-file blobs at the exact path from the actual
local `HEAD` ancestry, matched to a finite installer identity for that provider,
path and mode. Renames, backups, other refs or a similar-looking policy are
not proof. Two distinct recognized bases are ambiguous. Shallow, linked-worktree, alternate or
promisor storage and unsafe/unsupported evidence cannot establish this proof.
In a physical main checkout, a single valid boolean `extensions.worktreeConfig`
declaration in `.git/config` is supported **only when `.git/config.worktree`
is absent**. Even an empty override, dangling symlink, duplicate declaration,
other extension or included config is not qualified. The probe parses verified
local config bytes without includes, limiting expanded key output to 64 KiB
before parsing. Git replacement objects are disabled and Git must report
`/dev/null` as its graft source. An existing `.git/info/grafts` (even a dangling
link) still refuses. The reviewed evidence binds the config digest, file and
directory identities/change times, the graft parent and absence of both overrides;
changes require a fresh preview. Don't edit repo config to obtain a token.

The probe inventories every reachable commit and root tree, including every
merge parent. It walks each exact path component once per distinct tree at
that depth, so unrelated commits can share evidence. A deletion means the
path was absent in that tree; it does not erase the earlier evidence. A
historical symlink or other nonregular path component is not evidence for a
regular role. The per-path limits are 65,536 commits, 8,192 component trees,
32 distinct role blobs, 1 MiB per tree/blob, 64 MiB total tree/blob content,
32,768 Git metadata entries and 20 seconds. The probe requires local Git
support for `cat-file --batch-command`; missing objects, unsupported plumbing
or an exhausted budget never certify a prefix. Keep live files and index
intact; compare ancestor/local/upstream privately rather than rewriting history.
If history is needed to distinguish a manifestless provider's mode from its
neighbors' guest setting and the evidence is inconclusive, **unknown** is a
refusal, not a guest conversion. A completed search with no matching ancestor
in either mode is not positive evidence for guest. On macOS the history probe
uses the system `/usr/bin/git` launcher, not a discovered toolchain executable;
launcher time counts toward the same deadline. Keep the current files; for a time limit,
retry the same preview when the machine is less busy. For unavailable history,
review trusted provenance separately rather than forcing a visibility change.
No fetching, native model execution or universal historical coverage is implied.

The focused cases in `test/all-current.py` distinguish these synthetic layouts.
All start with edited historical Claude roles and no Claude snapshot:

| Existing Codex / Copilot | Claude paths in the index | Selector-less outcome |
| --- | --- | --- |
| Neither installed | Tracked | A completed `no-match` at both normal Claude role paths permits a replacement offer. Only validated frontmatter `model` and `effort` choices carry over. `APPLY` backs up `.claude/agents/implementer.md` and `.claude/agents/reviewer.md` beside the originals (0600) before replacing their content and installing the other providers. Return keeps all files as they were. |
| No snapshot / normal | Tracked | Representative state layout. With no conflicting Codex native files in the fixture, preview creates Codex roles, retains the independent private Codex config and preserves the configured Copilot choices. |
| No snapshot, **live Codex roles** / normal | Tracked | Proven edited Codex roles are proposed for adoption. If both exact-path searches complete with `no-match`, the installer can instead propose replacing both role bodies, backing up their complete original bytes first (0600, beside each role). No ancestor or merge is claimed. Only the displayed top-level TOML model/effort settings survive replacement. Keep these backups out of Git. |
| Guest / normal | Tracked | Separate negative control: mixed persisted modes and missing Claude state. Refuses before approval without converting or untracking anything. |
| Normal / normal | Tracked | With proven history and a complete plan, one approval can migrate the roles without changing the index. |
| Guest / guest | Tracked | Refuses a planned tracked rewrite even when it can identify the Claude ancestor. |
| Guest / guest | Not indexed; still in history | Eligible sibling exercises one approval while retaining guest privacy. |

These are disposable projects with synthetic roles, Git ancestry, settings
and host configuration. Missing state directories do not establish that native
files are absent, owned or safe to replace.

The eligible controls compare saved and piped previews and exercise either a
saved-file approval token or one `APPLY` on the controlling terminal with a
piped installer. The unmatched-pair controls run the ordinary file and pipe
commands on a controlling terminal, decline, then approve and inspect written
roles and originals. Both preserve role choices and unrelated staged/unstaged data
and rerun without another reconciliation. None establishes eligibility for a
particular consumer checkout; do not remove files from the index to mimic a
control.

Normal mode shares configuration when committed. Modes are sticky **per
provider**. Missing providers inherit a wholly normal or guest set; fresh
defaults to normal. Mixed modes with a missing selected provider refuse until
explicitly resolved using `--guest` or `--no-guest`.

Guest mode:

- Claude uses `CLAUDE.local.md`; Codex/Copilot leave host policies untouched and
  bootstrap through **`$domestique` / `/domestique-v2-copilot`**.
- Local Git-common exclusions affect linked worktrees. They **cannot hide
  tracked files** and are Git visibility, not access control. Review warnings.
  Non-Git targets cannot receive those exclusions.
- Shared routes are visible if any valid Codex/Copilot consumer is normal;
  they are private only if all consumers are guest. Guest mode does not promise
  to hide arbitrary host files, existing visible paths or recovery artifacts.
- Converting an uncommitted normal install leaves its owned root policies
  (`CLAUDE.md`, `AGENTS.md`/`AGENTS.override.md`, and
  `.github/copilot-instructions.md`) byte-untouched. Guest install and dry-run
  warn and list the owned untracked policies still visible to Git, including
  mixed host/managed files; unrelated host-only policies are not remnants.
  They may stay visible, but do not commit them unintentionally. For cleanup,
  review `dom --uninstall --platform all --dry-run`, explicitly repeat without
  `--dry-run` only after review, then review `dom --guest --dry-run` before
  `dom --guest`. Uninstall removes owned blocks, not outside host text.
  Never blindly delete whole host files or pristine base/state directories.
- If guest installation would rewrite tracked files (including selected
  provider state, manifests or shared routes), it refuses **before any project
  writes**, lists the exact paths, and does so even with `--force` or
  `--dry-run`. Use `--no-guest` to remain normal, or explicitly review/uninstall
  the normal installation as above and review the Git changes before retrying.
  Unrelated tracked files and genuinely unchanged tracked policies do not
  cause refusal; exclusions still cannot hide them.
  In particular, tracked `CLAUDE.local.md` containing only personal notes
  refuses: appending the managed block would rewrite a tracked file. An
  already-owned, valid guarded guest policy can instead be retained unchanged,
  with an `already tracked` warning. `test/guest.sh --current` checks both
  cases; the no-argument suite runs frozen `b60feef`, whose warning-only
  personal-notes behavior is historical coverage, not the current contract.
- Shared Git-common exclude path/type and marker structure are checked before
  any guest model, policy or state publication, even for a single provider and
  with `--force` or `--dry-run`. Repair unsafe paths or malformed markers by hand
  before retrying; a missing exclude is still created when needed.
- All retained owned root policy blocks are checked, including inactive ones.
  An old unguarded owned host block refuses in guest mode; upgrade it in normal
  mode (`--no-guest`) or explicitly reconcile first. Guest mode does not rewrite
  host policies to manufacture isolation.
- `--no-guest` removes stale guest exclusions and installs normal policy.
  Retained `CLAUDE.local.md` content is not deleted automatically; follow the
  printed by-hand conversion guidance and review visibility before committing.

## Removal

With the existing alias:

```sh
dom --uninstall --platform copilot --dry-run
dom --uninstall --dry-run
```

After review, repeat without `--dry-run`. Scoped removal preserves shared
routes while another valid consumer remains. Modified owned files are kept as
`<file>.uninstalled.<timestamp>` unless forced; policy/exclusion blocks and
provider state are removed, and only empty owned directories are pruned.
Unowned content and Beads remain. `--purge-beads` is a separate destructive
choice, not ordinary cleanup. Preserved backups may be visible in Git status.

## 5. Updating with update.sh

The unchanged public-base `update.sh` fetches one source, previews it, then
applies that same downloaded script through the merge path. It supports
`--source <path|url>` and `DOMESTIQUE_UPDATE_SOURCE`; default source is main.
Consult `./update.sh --help` for wrapper options. The downloaded installer's
selection rules apply: **selector-less updates add all three**, even to
an existing subset. Use explicit selectors and inspect the plan; this is not a
recommendation for unattended mode conversion.

## Supported Copilot preview project migration

Only supported active **project** receipts migrate: original five-definition
and seven-definition (`public-names`) layouts. The physical Git root,
Git/common identities, native names, created identities and exact exclusions
must match `.domestique-private/copilot-preview.json`.
No preview machine/source directory is opened, executed or required.
`--platform copilot` scopes selection; default selects all three.
Copilot remains guest/private unless `--no-guest` is explicit.

Before any selected-provider writes, migration validates receipt, source bytes,
metadata, shared ownership and replacement workflows, plus ordinary lifecycle
preflights. Dry-run uses the same candidates without project writes.
Malformed, foreign, copied, disabled/partial or unknown receipts, experimental
authority, unsafe links, tracked migration paths, unowned shared collisions,
custom alias leftovers and prompt-body forks **refuse preserving state**.
`--force` cannot bypass these checks.

Compatible scalar native metadata, comments and flat JSON string arrays for
`tools` survive. Complex YAML, duplicate/invalid scalars and Copilot
`effort`/`model_reasoning_effort` refuse. Names must remain exact; custom
descriptions need the current harness boundary. Only recognized locator bodies
become standalone workflows. Model/tools selections survive, but the old pair
marker is removed: changed workflows require fresh confirmation and reload.

### Recovery

A bounded source/output backup is staged at
`.domestique-private/copilot-preview-migration/` before cutover. It retains
receipt, native files, exclusion bytes and modes, and stays locally excluded
even after normal conversion. The old project receipt is revoked before
snapshot authority is published. Only unchanged proven obsolete aliases are
removed. Machine preview installations, source, `dom2` and Beads are untouched.

On failure/interruption, preserve that backup and every custom file; retain the
diagnostics. Preview/retry the **same installer and mode flags**. Recovery
accepts only old bytes, planned afterimages or bounded removals, never overwriting
new edits. Unknown/incomplete staging, changed output, custom leftovers or
different installer outputs need explicit preserving reconciliation; do not
delete evidence just to pass installation. A `complete` file denotes an inert
backup, not another native authority. This is cooperative single-writer
recovery, not an adversarial transaction service.

Do **not** blindly run an older installer as rollback: selecting older bytes
cannot reverse migrated ownership/workflows. See the concise
[historical boundary](v2-preview.md).

## Qualification and known issues

### v0.6.2 candidate checks and limits

Installer SHA-256:
`92d6f286b74d967e80787f01abc73fc35fc976f20ca851dfc47c9d288a65cf4a`.

The control is a disposable normal Git project with two tracked, customized
Claude roles, no recognized role ancestors and no Codex or Copilot install.
On both plain default transports, v0.6.1 blocked both paths without writes.
An earlier candidate also blocked valid punctuation in discarded metadata as
`ambiguous YAML scalar`. The replacement check now reads identity and choices
from a conservative flat frontmatter subset. Ordinary description punctuation
and comma-separated tool names are not model choices. Neither those fields
nor the old instructions are copied into the new role; its emitted discovery
and role guards still undergo normal validation. In retained choices, a
leading comma requires quotes: `model: ,local` or `effort: ,custom` blocks
the whole plan without a token; `model: ",local"` is a string, not a syntax
error. Accepting a string does not establish native model or effort support.

| Candidate check | Observed |
| --- | --- |
| Saved script and script piped to Bash, no flags | No terminal or Return left the tree unchanged. One terminal `APPLY` installed all three providers, preserved the index and both roles' model/effort, and left two byte-exact 0600 backups. The historical pair had no confirmation marker. Exit `3` reported `INSTALLED — pending Save`; a second default run changed no bytes or modes and added no backups. |
| Refusal controls | Duplicate, malformed or ambiguous frontmatter, wrong role name, invalid confirmation marker, executable, symlink and partial pair refused. Neither an unowned helper nor an unmatched command was swept into role replacement. Changing a role after review invalidated approval before publication. |
| Existing normal Codex replacement and v0.6.1 upgrade | Saved and piped Codex replacement controls passed. A configured v0.6.1 install upgraded without reconciliation, retaining six model choices, pristine bases, host edits and index. Its second run was byte/mode stable. |

The patch adds v0.6.2 to the two finite generation lists; it does not change
the historical identities or installed role/helper emitters. These are focused
offline checks, not the full upgrade matrix, a consumer migration, or native
client/Save qualification.

### v0.6.1 candidate checks and limits

Installer SHA-256:
`609d769525863c3ddb7eb63b1f5dd4d5975546b3fb4fa568986fd5dd43b6ccc4`.
Relative to the reviewed repair (`d6bdb2d`), the only installer changes are
the version and the two finite generation lists. The historical identity data
is unchanged. Checks use disposable Git repositories, not consumer data,
native clients or a model Save.

| Input | Observed on the versioned installer |
| --- | --- |
| Tracked Claude roles with proven ancestors, unmatched Codex pair, configured normal Copilot | Saved and piped default commands showed the same proposed effects. Return wrote nothing. One terminal `APPLY` published the plan, kept the index and unrelated edits, and left each exact Codex original in a 0600 sibling backup. Exit `3` said `INSTALLED — pending Save`; reruns neither changed bytes/modes nor added backups. |
| Same no-match history, release control | Published v0.6.0 refused both paths without writes. v0.6.1 offered replacement, but refused an executable input without issuing an approval token. |
| Empty project / existing normal v0.6.0 install (`41c201c`) | Fresh default install and reruns passed. The upgrade preserved six configured role choices, host policy text, pristine bases, staged index and unstaged data. Preview wrote nothing; the installed rerun was byte/mode stable. |
| Previous repair installed by `d6bdb2d` | Upgrade retained both backups, installed roles and pending-Save state. No new reconciliation or backups on apply or rerun. |
| Outcome ordering | Unsafe scratch refused before target writes. An injected copy failure exited `17` and reported partial results. A piped clean install printed its one final status **before** a caller command that exited `47`. |

Ten focused `AllProviders` tests passed, as did the finite-inventory test,
13 published-upgrade **harness** tests, Bash syntax and warning-level
ShellCheck. These are not a full historical matrix or native readiness
qualification. The v0.6.0 refusal above is a negative control, not a failed
candidate check; [historical baseline results](#offline-baseline-release-gate)
were not rerun or reclassified for this patch.

### v0.6.0 candidate checks and limits

The installer SHA-256 is
`e1febd15f496ad25e9609cff9797a716e248842e13ff76fa407bf3e80849bd06`.
Relative to `ed41c44`, only the emitted version and the two finite generation
lists (current inventory and policy-only state) changed in the installer. No
historical role or policy identity was added for the version bump.

Focused offline checks on these installer bytes:

| Disposable Git project | Observed result |
| --- | --- |
| Empty, default selection | Streamed no-write preview, all-three install and stable reruns passed. |
| Published `v0.5.0` (`72cbd5eef6926a806a4f63ce758af3d33de3709e`), normal default selection | Preview made no changes. Apply retained role choices, host policy text, index and backups; projections and pristine bases matched a fresh v0.6.0 reference. Rerun changed no bytes or modes and added no backups. |
| Synthetic edited Claude and Codex roles with proven ancestors, plus configured Copilot | Saved-file and piped runs showed the same planned effects. Each published once (saved token or terminal `APPLY`), preserved choices and the index, and reran without another reconciliation or byte changes. Exit `3` still required review/Save. |

Dirty-start evidence comes from installed instructions and disposable Git
fixtures, not a successful native dirty-start lifecycle. Reconciliation
evidence covers filesystem effects, including refusals, not a full migration
of a real project. A no-write preview cannot establish that such a migration
was applied or that a native client loaded and confirmed the resulting roles.
Review, publication and native qualification are separate.

<a id="v050-local-candidate-status-and-limits"></a>

### v0.5.0 release status and limits

**Independent final release and root acceptance passed** for hq-6f1.4 and
root hq-6f1, with no blockers. The final independent reviewer passed **25 fresh
tests**: three AllProviders selectors plus two normal/guest preserving-upgrade
selectors (**5** total, the five selectors documented below), the native harness
(**7**) and the published-upgrade harness (**13**). Bash syntax, warning-level
shellcheck and diff checks also passed. The canonical completion contract hash
remains unchanged. These results are independent final validation, separate
from the preparation and predecessor observations retained below.

Acceptance does not itself publish the release. Commit, merge, push, tag and
GitHub release are separate publication operations; installed-policy refresh
remains a reviewed user upgrade.
Full registered-role/Beads lifecycle and comprehensive native unattended
execution remain **UNQUALIFIED**. No new full historical matrix was run;
v0.4.4's 359/359 composite qualification is retained history, not fresh v0.5.0
results.

#### Independently reviewed predecessor evidence

These are predecessor results reported by the independent reviewers, not reruns
performed during final version preparation:

- hq-6f1.1 (`5632965`): policy reviewer ran **8 relevant AllProviders tests**,
  plus syntax and lint; PASS for the scoped completion implementation.
- hq-6f1.2 (`de0f71f`): regression reviewer ran
  `python3 test/all-current.py CompletionQualification` — **5 PASS**, including
  actual published v0.4.4 → candidate normal and guest all-provider upgrades
  and **19 contradiction controls**; and
  `python3 test/published-upgrades-tests.py` — **13 PASS**, plus syntax/lint.
  These are installed-instruction/filesystem checks, not model behavior.
- hq-6f1.3 (`6de7dd6`): native reviewer ran
  `python3 -B test/copilot-astra-native-tests.py` — **7 PASS**, relevant
  syntax/lint, and independently inspected actual retained fixture artifacts
  and logs. The deterministic seven tests qualify the harness, not native
  behavior by themselves.

The separately observed controlled native probes used **Copilot CLI 1.0.114**,
with native usage confirming **gpt-6-astra/main**. Reproduction and isolation
protocol: [`test/copilot-astra-native.md`](../test/copilot-astra-native.md);
opt-in runner: [`test/copilot-astra-native.py`](../test/copilot-astra-native.py).
Review histories supplied to the probes were explicitly simulated:

| Probe | Reviewed observation | Boundary |
| --- | --- | --- |
| A, final approved fixture | PASS: actual local commit `dc6c1cf` changed only `owned.txt`; unrelated staged/unstaged files, index entries/blob bytes and local configuration preserved | Real scoped commit, not registered-role dispatch or Beads closure |
| B | PASS: permitted third progressing corrective cycle and fresh review | Decision only; no actual multi-cycle native execution |
| C | PASS: advisory/no-code completion without mandatory extra cycle or empty commit | Decision only; no actual closure |
| D | PASS: uncertain ownership stopped without mutation | Narrow ownership boundary |
| E | PASS: actual Git-commit permission denial, no retry/bypass or completion claim | Deliberate denial boundary, not a workflow failure |

Two earlier A attempts were **INCONCLUSIVE because of test allowlist omissions**,
not policy failures. Each fresh grant followed explicit user approval; those
attempts and their logs remain evidence, not erased or silently retried.
Personal session paths, account details and verbose transcripts are not published
here; hq-6f1.3 retains the evidence references. These limited observations do not
supersede historical native lifecycle gaps or qualify automatic unattended work.

#### Final version-preparation checks

The final installer changes `DOMESTIQUE_VERSION` from 0.4.4 to 0.5.0 and adds
0.5.0 to the existing current-inventory and policy-only generation allowlists
relative to `6de7dd6`; inventory shape, ownership and safety checks are unchanged.
Its SHA-256 is
`71b4ca27d66ff08294c1e981e0f1807d23559485800c5ece886084a2eeb28746`
(predecessor source:
`a92e56a8e250f6e3f442dbf7bf213d733eab34f8afef7f19da44a7e0908c977c`).
The literal canonical completion contract, including its emitted final newline,
is byte-identical in both, SHA-256
`8af5a3e3b2b964d4880f3259be836cfe8f0df300a3d7817a11248c9dbdb54221`.
This supports retaining the reviewed native observations without another paid
run; it does not turn them into fresh v0.5.0 native executions.

Fresh final-candidate checks (separate from predecessor evidence):

The first four-test projection/version/upgrade run completed **2 PASS, 2 FAIL**
in 1031.317 seconds. Both upgrades passed preview/apply and preservation checks,
then refused the stable rerun with `unknown inventory generation`: the initial
version-only bump wrote 0.5.0 manifests not recognized by the old allowlists.
The directly coupled correction adds only 0.5.0 to the two finite current
generation lists. That failed attempt is not counted as qualification.

After correction, this exact final-candidate command completed **4 PASS** in
1684.285 seconds:

```sh
python3 -B test/all-current.py \
  AllProviders.test_reviewed_transaction_across_entry_layers \
  AllProviders.test_notice_absent_on_help_errors_and_scoped_uninstall \
  CompletionQualification.test_published_v044_preserving_upgrade_normal_all \
  CompletionQualification.test_published_v044_preserving_upgrade_guest_all
```

The two upgrade smokes used actual v0.4.4
(`98bdea04732c4862d45ddae6eed25436e09182d9`) installers and the final candidate
in normal/guest default-all mode across Claude, Codex and Copilot. Both
preview/apply/rerun sequences passed, preserving six custom role choices,
host configuration/policies, pristine bases, unrelated index/backups and guest
privacy while checking current projections. This is bounded filesystem evidence,
not a repeated full qualification suite or native workflow run.

- `bash -n domestique.sh` — PASS.
- `shellcheck --severity=warning domestique.sh` — PASS.
- `git diff --check` — PASS.
- `python3 -B test/all-current.py AllProviders.test_presnapshot_pristine_policy_copilot_upgrade`
  — **1 PASS** (336.403 seconds): current-version policy-only preservation and
  stable preview/rerun after the generation-list correction.
- `python3 -B test/published-upgrades-tests.py` — **13 PASS** (gate unit
  controls, not the 74-case historical installer matrix).
- `python3 -B test/copilot-astra-native-tests.py` — **7 PASS** (deterministic
  harness checks only; no paid/native CLI invocation).

### v0.4.4 release status and limits

- **Offline qualification and independent final release review passed.**
  Qualification completed on 2026-11-12 using a working-tree candidate based on `0574c0c`,
  installer SHA-256
  `12374816427c11db455d52b1b6b767d8f14d3d803c2aab8b6101b78f598d99f1`.
  Complete required coverage is **359/359 baseline checks across 13 groups**:
  **205 unittest methods and 154 shell scenarios**, with no skips, unknown
  inventory entries or unresolved failures. This is a **composite** of completed
  methods/scenarios and independently reviewed focused fixes, not one
  uninterrupted baseline or thirteen newly successful full-suite invocations.
  Source hashes and exact method/scenario inventories establish which earlier
  passes remain applicable; focused duplicates are not counted twice.
- The final group counts and provenance are:

  | Group | Covered | Evidence composition |
  | --- | ---: | --- |
  | All-current | 111/111 | 100 completed methods + 11 fresh shards |
  | Copilot-current | 21/21 | 14 completed methods + 7 fresh shards |
  | Model setup | 41/41 | 40 completed methods + reviewed changed-method pass |
  | Upgrade current | 13/13 | 10 completed scenarios + 3 reviewed replacements |
  | Uninstall current | 29/29 | Completed full command |
  | Guest current | 17/17 | Completed full command |
  | Codex current | 30/30 | 28 completed scenarios + 2 reviewed replacements |
  | Upgrade historical | 12/12 | Full command; 3 affected scenarios rechecked |
  | Uninstall historical | 23/23 | Completed full command |
  | Guest historical | 14/14 | Completed full command |
  | Codex historical | 16/16 | Full command; affected visibility scenario rechecked |
  | Historical identities | 19/19 | Retained completed command |
  | Published-gate units | 13/13 | Completed full command |

  Shell coverage is **89/89 current + 65/65 frozen historical = 154/154**.
  Frozen `b60feef` fixtures preserve historical adoption behavior; they are not
  current-candidate CLI acceptance. The reviewed shell corrections verify
  **17 exit-3 zero-write refusals** for unproven native files, with exact
  diagnostics and snapshots checked first. They do not restore automatic
  adoption of edited roles or weaken ownership checks.
- Original identity failures, the 28,800-second all-current/Copilot
  interruptions, model/shell assertion failures and the interrupted initial
  focused selector remain immutable non-PASS attempts. Identity coverage
  completed 19/19 in 307.800 seconds after fresh-emission fixture budgets changed
  from 60 to a finite 300 seconds; production logic and the intentional
  one-second timeout negative control were unchanged. A timeout is never PASS.
- **3/3 focused published-upgrade smoke cases** passed against the actual
  working installer above: v0.1.0 normal default/all, and v0.4.3 normal and guest
  default/all, in 649.128 seconds. A session-only source adapter supplied the
  working bytes to the existing harness, retaining its assertions and isolation;
  it did not pretend that `--revision HEAD` selected the uncommitted candidate.
  These three cases are separate from the 359 baseline checks.
- The final session evidence is indexed by
  `release044-final-qualified-coverage.json` (exact names, source hashes,
  commands, durations, logs and scenario renames) and
  `release044-final-review-manifest.json` (final five-file hashes and scoped
  diff). It references the unchanged original attempts and the reviewed
  `hq-dds30-review.json` / `hq-dds30-artifacts.json` focused evidence.
  Recorded Bash syntax, warning-level ShellCheck, Python AST and diff checks
  passed. Final documentation completion checks consistency and diff only;
  it does not rerun qualification suites or change installer/test code.
- The [bounded published-upgrade gate](#bounded-published-upgrade-gate)
  qualifies **74 published-tag cases plus seven reported checks**, with the
  exact earlier revisions, installer fingerprint and evidence recorded below.
  These are not new executions of the release candidate.
  **Exhaustive intermediate-history/mutation coverage remains deferred**;
  there is no universal automatic-migration guarantee.
- Ownership requires finite historical byte proof and safe inventories.
  Exact pristine manifestless policies/native roles and the early Claude
  inventory have bounded adoption paths. Unproven native files, including
  edited or unknown converted roles without ownership evidence, require
  explicit backup/reconciliation; do not delete evidence or use `--force`
  to manufacture ownership.
- Retained custom policies and removed-provider metadata remain preserved.
  Guest writes to tracked policies refuse with recovery guidance; review
  `--no-guest` or explicit uninstall/backup recovery rather than expecting
  exclusions to hide tracked files. Unconfirmed pairs require review and Save.
- **No native paid/account/readiness qualification:** offline configuration
  evidence does not establish client loading, model availability or native
  dispatch. Network delivery and consumer projects were not tested.
  Historical unresolved investigations remain recorded below.

### Offline baseline release gate

The historical hq-dds.3 baseline, recorded on **2026-11-07**, targets installer
revision `7abd9b72338f72485bb573ce8f9e3f5d902a24d0`; it was not rerun by the
bounded published-upgrade gate below. Its reproduction commands are the following complete suites
from that full-history, tag-enabled checkout, without changing installer or test
bytes between runs. Use disposable fixtures, a fresh temporary `HOME` and
`TMPDIR` per suite, no consumer configuration, and a tool-only `PATH` containing
Python 3.11+, Bash and Git but no native clients or real Beads executable.
Disable inherited Git configuration with `GIT_CONFIG_NOSYSTEM=1` and
`GIT_CONFIG_GLOBAL=/dev/null`; do not change global configuration.
`COPILOT_WORKROOT` must name a newly created empty temporary directory.

```sh
python3 -B -Werror test/all-current.py
python3 -B -Werror test/copilot-current.py ./domestique.sh "$COPILOT_WORKROOT"
python3 -B -Werror test/model-setup-tests.py
bash test/upgrade.sh --current
bash test/uninstall.sh --current
bash test/guest.sh --current
bash test/codex.sh --current
bash test/upgrade.sh
bash test/uninstall.sh
bash test/guest.sh
bash test/codex.sh
```

Copilot's installer and workroot arguments precede any optional unittest
selectors; the baseline uses no selectors. Shell `--current` runs exercise the
candidate; the four unflagged runs exercise frozen `b60feef` fixtures, not the
candidate CLI. Keep at most two suite processes concurrent. The baseline uses
finite outer deadlines of 24 hours per Python suite and 4 hours per shell suite;
the notice tests retain their default 300-second subprocess deadline.
Preserve separate stdout/stderr and command, revision, exit, duration, count,
skip and failure evidence. A timeout/interruption is incomplete, never PASS;
nonzero results require individually tracked release blockers, not silent
acceptance. This command list alone is not a green qualification claim.

At the recorded revision, all eleven runs completed without test skips or
interruptions; ten exited zero. Current guest completed **15/16**, failing
`tracked CLAUDE.local.md warning` (expected zero exit and warning assertions).
Its captured installer diagnostics were not emitted by the harness; cause and
regression status remain unknown. The baseline is **not green**; release
acceptance requires the parent to track this failure as a blocker.

These are offline filesystem, generated-instruction and helper checks only.
They do not qualify native clients, model/account availability, consumer
repositories, or comprehensive ancestor upgrades. The generated ancestor matrix
is a separate future gate; neither historical passes nor this baseline replace
it or the native qualification gaps below.

### v0.4.3 release status and limits

- The removed-provider fix (hq-owe, `29fdc40`, against published v0.4.2)
  independently passed source review and **14 focused offline tests**, Bash
  syntax, warning-level ShellCheck, Python AST and diff checks before release
  preparation. This is not a full matrix or native qualification.
- Actual historical installers in generic disposable fixtures reproduce the
  failure on published v0.4.2 and verify the fix. Explicit unrelated-provider
  installs preserve inactive metadata/bases, host policies and guest Beads
  markers without reviving completely removed Claude/Codex projections.
  Safe absence is required, not blanket exemption for unselected providers:
  surviving partial, unowned, guard-tampered or unsafe files remain validated.
  Explicitly selected damaged pairs still refuse, including with `--force`;
  legacy Codex canonical shared ownership still refuses reassignment.
- Live-provider additive selection and default-all behavior are unchanged.
  Stale provider history alone does not resurrect completely removed providers.
  The reported consumer state was externally cleaned up before the final real
  check; an upgrade of its original old state was **not verified**.
- **Native coverage remains unqualified:** authorization for new paid
  fixtures/model usage remains pending, not authentication. Prior historical
  uninstall, migration-timeout, unterminated-host-suffix and recovery
  qualification limitations remain; see the retained
  [v0.4.2](#v042-release-status-and-limits) and
  [v0.4.1 limits](#v041-release-status-and-limits).

### v0.4.2 release status and limits

- The historical-policy fix (hq-qmf, `28ddf41`, against published v0.4.1
  `9841ab9`) independently passed source review. An audit of 74 public commits
  and actual old installers verified five omitted policy-base identities,
  including `99e6274` with SHA-256
  `378081109234078c13371c06ffd3d7e787d7d325fc384abb30b25721b9faee7c`.
- Recognition is finite: unknown or modified bases, current-guard tampering
  and selected-policy conflicts still refuse, including with `--force`.
  Very early `ff41544` lacks the complete inventory and still refuses
  independently. Not every historical installation is supported.
  The v0.4.1 retained-policy preservation fix remains intact.
- Independent review passed **12 focused tests**, Bash syntax,
  warning-level ShellCheck, Python AST and diff checks. Published v0.4.1
  rejects the matching fixture as a negative control; the candidate passes
  ordinary/force selected-Claude dry-runs and preserving upgrades, plus
  retained-Copilot guard migration. These are local offline fixtures.
  The reported actual base hash matched known public source, but the complete
  actual remote project was not verified and no upgrade was applied there.
- **Native coverage remains unqualified:** authorization for new paid
  fixtures/model usage was unavailable, not authentication. Historical
  malformed-marker uninstall (hq-7sm.17), migration timeout (hq-6pf) and
  unterminated-host-suffix uninstall newline behavior (hq-6yh) remain unresolved.
  See the retained [v0.4.1 limits](#v041-release-status-and-limits) below.

### v0.4.1 release status and limits

- The retained-policy fix (hq-pu1, `ae02624`, against published v0.4.0
  `67195ab`) independently passed source review. Unselected/inactive retained
  policies preserve custom workflows; known-owned legacy blocks receive only
  harness isolation. Already guarded retained workflows stay unchanged.
  Pristine bases remain independent of custom live text, and explicitly selected
  active providers still refuse real workflow conflicts.
- Implementation validation passed **7 policy tests and 2 Codex scenarios**;
  independent review passed **9 relevant tests, 2 Codex scenarios and provider
  probes**. Independent consumer normal/force dry-runs both exited `0`, changing
  none of 79 scoped records or Git status. These are bounded offline results,
  not a universal clean test matrix or live native proof.
- Supplementary legacy-recovery failures reproduced unchanged on the baseline;
  they are not fixed here. Historical malformed-marker uninstall (hq-7sm.17)
  and migration-timeout (hq-6pf) investigations remain unresolved. The
  pre-existing unterminated-host-suffix uninstall newline behavior (hq-6yh)
  is also not fixed.
- **Native defaults/goal coverage remains unqualified:** authorization for new
  paid fixtures/model usage was unavailable, not authentication. hq-c6o.8
  remains UNQUALIFIED and hq-xc2 native coverage remains BLOCKED; prior evidence
  below is not new native qualification.

### v0.4.0 release status and limits

- hq-xc2.1–.5 were reviewed; final hq-xc2.6 offline checks at `e5dba79`
  passed **8/8 selected tests** and **5/5 syntax/lint/diff command groups**.
  Evidence includes actual published v0.3.1 (`18f09ac`) negative controls and
  confirmed model/effort/custom-tools preserving upgrades across all three harnesses.
  Prior reviewed matrices were reused, not all rerun for release preparation.
- **NATIVE GAP — BLOCKED by authorization, not authentication:** the user was
  unavailable to authorize new paid fixtures/model usage. No native three-task
  epic, exact single-task or 16-task run occurred; runtime adherence is unproved.
  Offline PASS is not native PASS, and hq-xc2 is **not fully qualified** despite
  publication of its implementation. hq-c6o.8 also remains UNQUALIFIED.
- No functional publication blocker was found in the bounded offline review.
  Publication was authorized with this native gap disclosed; historical
  hq-7sm.17 and hq-6pf risks below remain unresolved, not fixed by this release.

### Historical native evidence (not hq-c6o qualification)

Independent final native review passed for the earlier standalone logic at
`75b0de30b7da5153b7f2fe68f52619bbd724380d`, unchanged in the documentation/test
handoff `8cac49bbe94ea0604f47ce40cc107e98fadca240`. All three actual clients
used the same all-installed disposable project with independent setup, changed
pairs, reload, dirty-tree refusal, invalid-model preservation and cross-harness
isolation. Saved-default implementation and fresh review passed before task
commit/closure. These bounded results are not universal client/model support.

**Initial native attempts were not flawless.** Claude initially staged scratch
before consent, violating read-only preparation. A declined reconfiguration
preserved the pair; a new request later completed compliant read-only
preparation, inline plan, fresh consent, apply and reload. That success does not
erase the earlier deviations. Copilot's parent-facing tool returns exposed no
child model/effort; independent review found no ignored mandatory telemetry.
Native events corroborated selections, but later controller labels are not
preacceptance proof. Optional loaded-byte attestation was not required.
A correct foreign-parent refusal demonstrates a boundary STOP, not foreign
child execution. Do not bypass boundaries to manufacture evidence.

Two unresolved historical failures remain open; their residual risk was
explicitly accepted for 0.2.0 preparation, **not fixed**:

- **hq-7sm.17:** END-only uninstall assertions failed for exit `3`, the
  `CLAUDE.md` Conflicted bucket and snapshot-directory removal. Original
  per-scenario return code/stderr was not retained; cause remains unknown.
  Better diagnostics and subsequent focused/full passes do not establish a fix.
- **hq-6pf:** the seven-definition preview migration rerun exceeded its
  60-second timeout. Original progress evidence is missing; cause is unknown,
  **not proven contention**. Later fast candidate/baseline probes and a full
  Copilot pass do not establish a fix or justify increasing the timeout.

Retain diagnostics on a new occurrence; no blind repeat loops. Configuration
installation, helper checks and offline tests do not attest native readiness.

### Bounded published-upgrade gate

`test/published-upgrades.py` is an opt-in, stdlib-only offline gate, not a
universal every-commit upgrade guarantee. This is candidate evidence for the
**v0.4.4 safe-upgrade scope with explicit preserving recovery**, not a promise
of universal automatic migration. Its exact published set is
`v0.1.0`, `v0.2.0`, `v0.2.1`, `v0.2.2`, `v0.3.0`, `v0.3.1`, `v0.4.0`,
`v0.4.1`, `v0.4.2`, `v0.4.3`. Local tag objects and historical support files
are required; it never fetches missing history or substitutes a newer core.

The finite plan has **74 cases**: v0.1.0's Claude-only normal installation
upgraded to Claude or all; for each later tag, Claude, Codex and Copilot
same-provider upgrades plus default-to-all, each in normal and guest mode.
Equivalent default/all aliases are not multiplied, and combined-provider
permutations and arbitrary ancestry commits are not exhaustively qualified.

```sh
python3 test/published-upgrades.py --list --revision HEAD
python3 test/published-upgrades-tests.py -v
python3 test/published-upgrades.py --revision FULL_CANDIDATE_SHA --workers 2 \
  --output /tmp/published-upgrades-unique-run
# Narrow reproduction, always to a NEW output directory:
python3 test/published-upgrades.py --revision FULL_CANDIDATE_SHA \
  --filter v0.2.0-guest-codex --output /tmp/published-upgrades-repro
```

The plan/count and resolved revisions are emitted before execution. Per-attempt
commands, return codes, expected outcomes, stdout/stderr and timings, source
archive hashes, tree fingerprints and retained isolated fixtures are evidence;
existing output directories are refused. Default budgets are 900 seconds per
installer attempt and 120 seconds for Git setup, with at most two workers.
Timeouts and any unexpected exit (including exit 3) fail; failed published
installs are never relabelled unsupported. Full runs may take hours under load.

Each release case checks preview bytes/modes/mtimes (including Git index and
excludes), applies, then checks byte/mode/status-stable rerun with no new backups.
It preserves policy host text, existing backups and model/effort selections;
selected native bodies, pristine bases and manifest inventories must match the
current contract. Comparison omits only validated installation timestamps and,
for role-body comparison, separately checked model/effort lines and a marker
whose **raw** root and both live hashes have first been validated. Normalized
bytes never confer ownership. Guest ownership ledgers are not fresh-equality
objects: historical `.beads` provenance is legitimate, and retired provider
copies of shared bases need not survive when the current shared base exists.
Unknown old files, including unclassified metadata, must remain byte/mode exact;
unknown new files are rejected, not normalized away. Active guest projections must remain
Git-excluded; unrelated host exclusions remain intact.
An untouched snapshot may retain its **exact original** manifest provenance
because manifests are written only when their snapshots change; its inventory
and pristine bases must still match current upstream. Arbitrary stale or altered
manifest metadata is not accepted. Repeated `--filter` selects the union of
impacted cases without rerunning the whole gate.

`python3 test/published-upgrades-tests.py --reported` separately selects seven
reported-risk checks using existing current-test helpers: retained custom Claude
under Copilot-only selection, known-old-base proof, removed-provider projections,
tracked guest publication, staged pre-snapshot adoption, tracked old policy
refusal plus `--no-guest` recovery, and custom unowned converted-role refusal
plus an explicitly backed-up fresh installation. These are not added Cartesian
provider permutations. The staged pre-snapshot fixture avoids commits; it does
not claim the committed/worktree variants of the broader existing suite.
The reported checks run serially, each with a separate 7,200-second test budget
and 1,800-second piped-installer budget. They retain the reviewed real-pipe
`run_stdin` helper (independent feeder and owned-group cleanup), not file-route
substitution. A test deadline unwinds that cleanup; the outer process has a
further 60-second safety margin. Every completed case records command, source
hashes, stdout/stderr, exit and duration before the next case starts. A failure
stops the batch for diagnosis; timeout is never PASS. For a selected case:

```sh
python3 -B -Werror test/published-upgrades-tests.py --reported \
  --case test_historical_claude_retained_guard_only \
  --timeout 7200 --installer-timeout 1800 \
  --output /tmp/published-reported-unique-run
```

Omit `--case` for all seven; repeat it for a selected subset. Omit `--output`
for a new temporary evidence directory; an existing output directory is refused.

Recovery checks require specific diagnostics and zero writes, not arbitrary
exit-3 acceptance. Guest mode cannot rewrite tracked host policies to create
privacy. `--no-guest` exercises normal-mode recovery, not a guarantee of later
guest conversion. Unknown/tampered/custom unowned roles are never overwritten
or assigned fabricated pristine bases: the fixture owner explicitly moves its
pair to a separate backup before fresh installation. That is not automatic
migration or proof that arbitrary custom prompts have been reconciled.
Retained unselected workflows are checked for preservation by the reported
regressions, not against fresh defaults.

These are local configuration tests only: no accounts, native clients, catalogs
or real consumer projects. They do not establish native loading/model readiness,
replace the final post-version-bump baseline, or supersede deferred exhaustive
mutation/ancestry qualification.

**Bounded qualification completed 2026-11-11 at `463dc94`: 74 published cases
and seven reported risks have PASS evidence.** The 74 file-execution results
remain the **2026-11-10** run at `202bfe9`: 48 initial passes plus 26 targeted
replays after correcting unchanged-manifest comparison. They were digest-checked,
not rerun. That earlier gate used installer SHA-256
`ee3efc9dccecbc81d429216e731412f9515a051567b9709f90cd01f248f67324`.
The original digest index is `/tmp/dds28-final-evidence/evidence.json`; its
historical BLOCKED status is superseded only for these reported checks.

All seven were executed once serially with the hq-dds.29 helper at `463dc94`,
exiting zero without skips: retained custom policy (170s), known old base
(149s), removed provider (207s), tracked guest writes (451s), pre-snapshot
adoption (85s), tracked old-policy recovery (71s), and unowned converted-role
refusal/explicit-backup recovery (110s). Per-case commands, source hashes and
logs are under `/tmp/dds28-reported-463dc94-final/`; `summary.json` indexes them.
Executed harness bytes are retained there under `executed-sources/`. Subsequent
comparator-only unknown-file controls do not change these reported checks.

The original 3,600-second suite timeout (first case incomplete, six unrun) and
900-second stdin probe remain historical failures, not successes. hq-dds.29
addressed the intermittent host subprocess input/output stall in the test
transport; no installer product change or deterministic root-cause claim is
implied. The completed checks above use actual piped stdin. This bounded result
does not qualify network delivery, native clients/accounts, consumer projects,
all guest conversions or exhaustive ancestry. At that checkpoint, parent review
and the final post-version-bump baseline were still required. The later
[v0.4.4 composite baseline](#v044-release-status-and-limits) records completed
offline coverage and passed independent final release review.

### Historical 0.2.0 release selection and fixture portability

The 0.2.0 preparation changes **only the version line** in the qualified
installer and selects three publication documents plus thirteen source/test
paths. It reuses the identical logic's full-matrix/native qualification, with
bounded syntax, lint, helper and historical-upgrade checks on the preparation
tree; it does not claim another full/native run. Independent release review
still precedes commit/publication.

The publication tip excludes experimental runtime and framework files, while
retaining **all candidate ancestry**, explicitly accepted for this preparation.
Do not squash/rebase away fixture history on publication. Local privacy
screening was completed; retained history remains part of publication review.
Full-history, tag-enabled clones are required for tests, not shallow clones or
source archives:

| Fixture ref | Required historical files |
| --- | --- |
| `v0.1.0` (`4aa67aef5fdfecd1442a983e1dd500473ef6e955`) | `domestique.sh` |
| `415fb697e542b2ca8600affd8d0238adce1bfe83` | `domestique.sh` |
| `64f4e093df67e0db6d5aa89c681c3cd0e3986e6c` | `domestique.sh` |
| `654414025554defe9eeef50c39b14a87326088b8` | `domestique.sh` |
| `b60feef4d0d41b8d99b7afec68dd5e6ef648b027` | `domestique.sh`, `update.sh` |

Copilot role fixtures from ancestor `9f339305a4f900176b647248f68907499dcc0620`
are vendored in `test/fixtures/copilot-9f33930/`; current tests read those files.
The candidate's coupled `test/copilot.sh --current` migration coverage depends
on retained preview sources and is **not a standalone publication-tree runner**.
That prior coverage is reused, not silently replaced by the selected
`test/copilot-current.py`. Historical shell runners without `--current` exercise
frozen fixtures only. Do not confuse those passes with current/native acceptance.

### v0.3.0 release status and limits

- v0.3.0 is a feature minor release: configured defaults, repeatable per-role
  installer overrides, preserving reruns and optional native `dom-models`.
  Existing choices, including released v0.2.2 defaults, remain pinned.
- hq-c6o.8 remains **UNQUALIFIED pending user authorization for fixture/model usage** for native first use
  and preserving upgrades. Offline checks and the historical `75b0de3` PASS
  do **not** establish native v0.3.0 PASS or epic completion. Configuration,
  actual native loading and model availability remain distinct.
- Publication was authorized after explicit disclosure of that native-validation
  limitation. Independent release review still precedes publication.
  hq-7sm.17 and hq-6pf remain unresolved. At that release, hq-xc2 was
  unimplemented and epic-drain/one-reviewed-bead bounds were unchanged;
  v0.4.0's goal changes above are separate, not retroactive qualification.
- After publication to main, the existing remote alias fetches these features.
  Preview and pin the same bytes for apply; local source installation remains
  an option, not a requirement.
