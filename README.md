# domestique

Project configuration for a **multi-model orchestration workflow** in Claude
Code, Codex and GitHub Copilot: an **orchestrator** designs and adjudicates,
an **implementer** executes, and a fresh **reviewer** independently verifies.
The plan of record lives in [Beads](https://github.com/steveyegge/beads).
Delegating implementation and verification keeps the orchestrator's context
lean; “done, tests pass” is checked, not trusted.

## v0.6.2 release candidate: replacing an unmatched Claude or Codex role pair

When neither normal-mode role in a Claude or Codex pair has a matching ancestor, `dom` can
offer a **replacement, not a merge**, after both searches finish. Review
the two backup paths and the model/effort choices. Return keeps everything
as-is; `APPLY` approves the **whole plan**, including backing up both
originals (0600) before replacing **everything except the displayed model and
effort choices**, including custom instructions. Without terminal or file-bound
approval there are no writes.

Read the final status: `PREVIEW ONLY` and `NOT INSTALLED by this run` do not
mean an install happened. `INSTALLED — pending Save` means configuration is
already on disk; review each unconfirmed pair with `dom-models --confirm` in
its native client, then Save. Re-running the installer is not a Save.
See [patch checks and limits](docs/install-upgrade-design.md#v062-candidate-checks-and-limits).

### Retained v0.6.0: dirty-start goals and preserving upgrades

**Starting work:** `dom-decompose` plans; it does not authorize execution.
A later `dom-goal` rechecks the checkout before claiming work. Separable edits
can stay in place; an overlap needs a decision about the affected paths, not
a clean-tree ritual. Native dirty-start execution remains unqualified.

**Upgrading configuration:** preview with `dom --dry-run`. Edited historical
roles need evidence at their own paths; ownership of another role or provider
does not count. Eligible synthetic projects exercised one approval for the
complete plan with either a saved installer or a piped installer at a terminal.
This is not a full migration of a real project or a native readiness check.
See [how to review the plan](#reviewing-historical-native-roles).

### From a dirty checkout to a named goal

In Claude or Copilot, for example, run `/dom-decompose Add a CSV header check`.
Read the returned epic, dependencies and workspace handoff. **Planning stops
there.** When ready, run `/dom-goal <returned-epic-id>` (use `$dom-decompose`
and `$dom-goal` in Codex). An unrelated staged README edit can stay staged:
execution rechecks the target paths and preserves both index and file contents
when starting the dedicated branch and committing reviewed work. If your edit
overlaps the CSV code, identify which change belongs to whom or defer that
path; don't stash everything just to start.

If planning reports no handoff or execution demands a clean tree,
[check the installed instructions and active session](docs/install-upgrade-design.md#workspace-handoff-from-decompose-to-goal)
before changing the checkout.

### Retained v0.5.0: scoped completion

**Independent final release and root acceptance passed.** Authorized managed work includes
in-scope corrections, validation, local scoped commits and task bookkeeping.
Independent fresh reviewer PASS still precedes commit/closure; PASS may carry
advisory notes without requiring another cycle. Ownership-aware handling
preserves unrelated staged/unstaged work instead of demanding a globally clean
tree. Progressing corrections have no arbitrary second-review cap; finite
nonprogress recovery and actual user/runtime budgets still bind.
Ordinary next-ready work remains one task; no automatic push or merge.

Predecessor implementation, regression and controlled Copilot/Astra probes
passed independent review (hq-6f1.1–.3). The native evidence includes one actual
scoped commit, ownership and permission-denial boundaries, and decision-only
progress/advisory probes—not a full registered-role/Beads lifecycle or
comprehensive native unattended execution, which remain **UNQUALIFIED**.
See [release evidence and limits](docs/install-upgrade-design.md#v050-local-candidate-status-and-limits)
for exact provenance and final-candidate checks. Historical v0.4.4 counts below
are not fresh v0.5.0 qualification. Final independent validation passed all
**25 fresh tests** plus syntax/lint/diff checks (hq-6f1.4 and root hq-6f1).
Acceptance and publication are separate.

### Retained v0.4.4 release history: proof-based upgrades and preserving recovery

v0.4.4 strengthens upgrade ownership checks with finite historical byte
identities and pristine manifestless adoption, without blessing unknown or
edited roles. Retained custom policies and completely removed providers stay
retained; guest operations refuse tracked policy writes with recovery guidance.
Unconfirmed model pairs receive actionable review/Save instructions rather than
silent confirmation. The installer remains standalone, including `curl | bash`.

**v0.4.4 offline qualification and independent final release review passed.**
That candidate had **359/359 baseline checks across 13 groups**, by composite
coverage of completed methods/scenarios and reviewed focused fixes—not one
uninterrupted run—and **3/3 working-candidate published-upgrade smoke cases**.
Earlier **74 published-tag cases and seven reported checks** remain separate
reviewed provenance, not fresh executions of v0.5.0. Exhaustive
intermediate-history coverage is deferred; universal automatic migration is not
claimed. Unproven native files, including edited roles without ownership
evidence, require explicit backup/reconciliation; tracked guest policy writes
require reviewed recovery. No native
paid/account/model-readiness qualification is claimed.
See [test gates, provenance and limits](docs/install-upgrade-design.md#v044-release-status-and-limits).

### Retained release behavior

An explicit unrelated-provider install, such as `dom --platform copilot`, no
longer reactivates completely removed Claude/Codex projections merely because
owned metadata remains. v0.4.3 preserves that metadata, pristine bases, host
policy bytes and inactive guest Beads markers. This requires actual safe
absence: surviving partial, unowned, guard-tampered or unsafe files still undergo
validation. Explicitly selecting a damaged pair still refuses; `--force` does
not bypass these checks. Legacy Codex canonical shared ownership still refuses
reassignment.
After publication to `main`, optionally preview with
`dom --platform copilot --dry-run`, then run `dom --platform copilot`.
The covered case needs neither `--force` nor manual metadata repair.
See [evidence and limits](docs/install-upgrade-design.md#v043-release-status-and-limits).

The v0.4.2 fix remains: recognition of five verified historical policy-base identities omitted by
v0.4.1, including the public `99e6274` Claude base. Unknown or modified bases,
current-guard tampering and selected-policy conflicts still refuse; `--force`
does not bypass these checks. v0.4.4 also recognizes the exact pristine early
`ff41544` inventory through a separate proof path, not a blanket missing-base exception.

The v0.4.1 fix remains: custom workflows in unselected or inactive retained
policies are preserved instead of attempting an unrelated full workflow upgrade. Known-owned legacy
policies receive only harness isolation, with independent pristine bases;
explicitly selected active policies still refuse genuine merge conflicts.

<a id="v040-complete-named-goals"></a>

v0.4.0 introduced [named goals](#complete-named-goals) that complete the full nested epic
or exactly the named task, with continuing progress reports every 15 closures.
Reviewed implementation and bounded offline qualification passed; **native
coverage remains BLOCKED by missing user authorization, not authentication**.
Publication does not fully qualify hq-xc2. See [evidence and limits](docs/install-upgrade-design.md#v040-release-status-and-limits).

<a id="v031-explicit-parent-git-approval"></a>

v0.3.1 introduced recognition of explicit parent Git approval, including “go ahead”
for a concrete proposal, without a Beads/model gate. Normal native permissions,
scope and guest privacy remain intact; no automatic drain, push or merge authority.
v0.3.0 introduced ready-to-use defaults and optional model commands.
Implementation reviews hq-c6o.2–.6 passed, but **native qualification hq-c6o.8
remains UNQUALIFIED pending user authorization for fixture/model usage**. Publication was authorized with
that limitation disclosed; this is not native PASS or epic completion.
Earlier [native evidence and two unresolved investigations](docs/install-upgrade-design.md#qualification-and-known-issues)
are history, not qualification of these changes.

### What's new

- One standalone `domestique.sh`, through the existing `dom` command. No
  `dom2`, project enable step, source checkout or global runtime.
- Selector-less fresh installs **and reruns select all three clients**.
  Explicit `--platform claude`, `codex`, `copilot`, `both` or `all` remain;
  **`both` means Claude+Codex**, not Copilot.
- Valid installed defaults need **no model questionnaire**. Optional installer
  overrides and native `dom-models` inspection/changes replace mandatory setup.
  Preserving reruns retain existing choices, including older defaults.
- Shared Codex/Copilot planning and goal skills, sticky normal/guest modes,
  scoped removal, and bounded migration of supported Copilot preview projects.

## Remote install and upgrade

Run from the intended project root. Installation needs Bash, Git and Python
3.11+ for the all-three path. It installs **configuration**, not clients, models,
credentials or Beads itself. Native clients and usable models are prerequisites
for workflow execution, not configuration installation.

After v0.6.2 is published to `main`, the existing alias fetches it on its next
invocation; no alias change is needed:

```sh
alias dom='curl -fsSL https://raw.githubusercontent.com/ebowman/domestique/main/domestique.sh | bash -s --'
dom --dry-run
dom
# Explicit selection; both does not add Copilot:
dom --platform both --dry-run
dom --platform both
```

Equivalent direct transport:

```sh
curl -fsSL https://raw.githubusercontent.com/ebowman/domestique/main/domestique.sh | bash -s -- --dry-run
curl -fsSL https://raw.githubusercontent.com/ebowman/domestique/main/domestique.sh | bash -s --
```

`main` is a **moving channel**: its next invocation downloads whatever is
published there. There is no background auto-update; a tag alone does not update
main or an alias. Canonical workflow emitters ship in the installer; changing a
source checkout does not update installed policies or already-loaded native
instructions. Apply a reviewed preserving upgrade in the intended project,
then reload stale instructions/registrations as appropriate for the client
(a fresh invocation may be required; Codex conversation roles may be immutable).
Compare the installer plan/version, installed projections and effective native
roles when diagnosing drift; a manifest version alone does not prove loaded
instructions. No user configuration or ignored local policy is auto-refreshed
by release preparation.
For repeatable dry-run/apply, replace `main` in **both** commands with the same
full reviewed published commit SHA. Pinning script bytes does not reverse
migrated project state.

### Optional source installation

A source checkout is optional; v0.6.2's changes are included in remote
`dom` after publication to `main`. To inspect reviewed source locally, run from
that checkout against a disposable Git project:

```sh
TARGET=$(mktemp -d)
git -C "$TARGET" init -q
bash ./domestique.sh "$TARGET" --dry-run
# Optional per-harness overrides; separated and equals forms:
bash ./domestique.sh "$TARGET" --platform claude --model claude:implementer=opus --dry-run
bash ./domestique.sh "$TARGET" --platform codex --model=codex:reviewer=inherit --dry-run
bash ./domestique.sh "$TARGET" --platform copilot --model copilot:implementer=inherit --dry-run
```

After reviewing a plan, repeat that command without `--dry-run` to install.
No native client, catalog lookup or authentication is required for installation.

Read the version-labelled target/provider/mode plan before applying.
There are no installer stdin prompts. Explicit selections are **additive**:
live persisted Claude/Codex may also be selected; unselected Copilot is retained.
Stale history alone does not resurrect completely removed providers. This does
not change the selector-less default of all three providers.
Use scoped uninstall, not an install selector, to remove a provider.

### Reviewing historical native roles

If the default `--dry-run` finds edited roles without installer snapshots, look
for an exact-path historical ancestor, each proposed model choice, provider
modes, and any blockers. A proposed adoption is **not approval**. If any path
is blocked, nothing is published. Keep local state or resolve the specific
conflict and preview again; don't use `--force` or change guest visibility just
to pass the check.

Guest neighbors do not prove that an edited manifestless role was installed
in guest mode. If neither mode has a matching ancestor, the review reports
**unknown** rather than recommending a conversion. If installed providers
already mix guest and normal and a selected provider lacks state, the default
can refuse before producing any plan.
Conversely, if only normal Copilot state is present, the absence of Claude and
Codex snapshots is **not** evidence that their files are absent or safe to
replace. Inspect the proposed adoptions and creations separately. If **both**
normal-mode role searches for the same provider (Claude or Codex) finish with `no-match`, plain `dom` can instead
offer to back up both originals and replace the pair. This is **not a merge**:
only the displayed `model` and `effort` (Claude frontmatter) or `model` and
`model_reasoning_effort` (Codex TOML) carry over.
The plan identifies the owner-only `.bak.<timestamp>` files; do not stage or
share those backups. Press Return to decline the whole plan without writes.
An ordinary main checkout can declare `extensions.worktreeConfig` without an
override file. That declaration alone does not block historical review. The
installer checks the exact role path across all reachable merge parents and
reuses unchanged trees, so unrelated commits need not block adoption. An actual
per-worktree config or an incomplete or over-budget search still prevents proof.
Don't change repository config or history to force eligibility.

With a complete plan, a foreground run can request **one `APPLY` on the
controlling terminal**, not installer stdin. For automation use the same saved
candidate, `--review-file` then `--apply-file sha256:TOKEN`; streamed previews
do not issue tokens. After publication the historical role pair still needs
`dom-models --confirm` review/Save (exit `3` is not a readiness signal).
See [approval, recovery and history limits](docs/install-upgrade-design.md#historical-native-role-reconciliation).

### Defaults and preserving overrides

| Harness | Implementer model / effort | Reviewer model / effort |
| --- | --- | --- |
| Claude Code | `sonnet` / inherit | `opus` / inherit |
| Codex | `gpt-5.6-sol` / `medium` | `gpt-5.6-terra` / `high` |
| GitHub Copilot | native inheritance / no effort field | native inheritance / no effort field |

These are chosen IDs, **not a promise of account entitlement or universal catalog
availability**. Using the same model for both roles is allowed; review still
needs a fresh independent context.

Repeat `--model harness:role=id-or-inherit` (or `--model=harness:role=value`)
for individual roles. For example, preview then apply from your project root:

```sh
dom --platform both --model claude:implementer=opus --model=codex:reviewer=inherit --dry-run
dom --platform both --model claude:implementer=opus --model=codex:reviewer=inherit
```

Only `claude|codex|copilot` and `implementer|reviewer`
are accepted; no aliases, wildcards or comma lists. Quote literal IDs as one shell
argument. Identical repeated assignments are allowed; conflicting repeats,
empty/malformed assignments and overrides outside the requested platform selection
refuse before writes. `--platform both` excludes Copilot; retained additive
providers are not extra override targets. With no selector, all three are targets.
`--model` cannot combine with `--force`, `--uninstall` or `--purge-beads`.

Reruns preserve existing models **and effort**, even old shipped defaults.
An explicit override changes only the named model, preserving its effort and
partner. Newly added providers get fresh defaults. On a **fresh** role, an
override equal to its shipped model keeps shipped effort; a different model
(including `inherit`) omits effort. The installer has no effort flag; change
effort later with `dom-models`. See [legacy/recovery rules](docs/install-upgrade-design.md#preserving-upgrades-and-mode-conversion).
Unconfirmed legacy custom-role migration preserves choices and returns `3`
until you review the current pair with `dom-models --confirm` (or
`--configure`) and Save; reruns never approve custom bytes.

## First use and the workflow

| Native client | Inspect saved choices |
| --- | --- |
| Claude Code | `/dom-models` |
| Codex | `$dom-models` |
| GitHub Copilot | `/dom-models` |

Use `/dom-decompose BRIEF` (Claude/Copilot) or `$dom-decompose BRIEF` (Codex)
to plan an epic and bounded tasks. Codex also offers `/skills`. Loading a skill alone
never authorizes goal work. Managed work requires fresh independent reviewer
**PASS before task commit or closure**.
Planning never requires model setup, helper verification, loaded roles or a
restart—even with missing/unconfirmed/manually edited roles—and never delegates
or executes tasks. Named goals now use the target scope and continuation below;
ordinary next-ready work still defaults to **one reviewed bead**.

1. Install and review Git changes. Valid configured pairs enter the existing
   execution gate without a questionnaire, Save or restart merely because fresh.
2. Before managed-bead execution, establish native role registration, effective choices,
   precedence and availability. Saved configuration is **not loaded native choice**.
   Reload only if current registrations are actually stale/unknown. Baseline
   HEAD, tracked/untracked edits and index ownership before work or branch changes.
   Preserve separable unrelated changes exactly; overlapping edits, collisions
   or uncertain ownership need narrow clarification, not blanket cleanup.
3. Unconfirmed/stale pairs stop with `dom-models --confirm` (review current bytes)
   or `--configure` (change choices). Missing/unsafe state needs preserving
   installer repair. Unavailable/mismatched choices stop execution, not planning:
   fix through `--configure`, Save and reload if needed, never automatic substitution.

<a id="upcoming-named-goals-reviewed-candidate"></a>

### Complete named goals

v0.5.0 retains v0.4.0 named scope and adds the scoped completion
contract below. Focused offline and controlled native evidence does not qualify
full native unattended execution.

Use these in the native client with a real project Beads ID:

| Client | Goal command |
| --- | --- |
| Claude Code / GitHub Copilot | `/dom-goal ID` |
| Codex | `$dom-goal ID` |

The actual bead type determines scope: an **epic** runs all unfinished transitive
parent-child descendants, including nested epics and descendants behind closed
intermediate nodes. A **non-epic** runs exactly that bead, even if it has children;
it never selects siblings or external prerequisites. Verified already-closed
targets are no-ops only when their scope is complete.

Clear current user execution requests or native named objectives also qualify:
“Complete epic EPIC_ID”, or “do it” referring to the current concrete named plan.
Native goal/autopilot with that named execution objective is accepted; a bare
mode toggle, quoted examples, loading/matching a skill, planning or model Save
is not execution authority. Ambiguous targets require a narrow question.
For explicitly bounded work, say “Execute only this bead BEAD_ID”,
“Execute one next bead in EPIC_ID”, or “Execute at most 3 beads in EPIC_ID”.
These are natural-language limits, not new command flags. An ordinary next-ready
request still means one bead. Compatibility commands remain Claude `/goal`,
Codex `$domestique-goal`, and Copilot `/domestique-v2-copilot-goal`.

**15 is a soft progress interval, not a stop, permission renewal or expiry.**
After every 15 successful closures, report progress and continue to bead 16,
31 and beyond while healthy. Explicit current user count/time/cost limits and
actual runtime/session budgets still bind; this does not bypass provider limits
or carry authority into another session. Cancellation/objective change and
material scope/ownership/criteria ambiguity stop affected work. Actual permission
denial, unavailable native roles or required model/configuration changes need
narrow operator disposition, never alternate-tool/model bypass.

Record concrete acceptance blockers after each independent review. In-scope
corrections and task-caused regressions may proceed to fresh review while
specific blockers decrease, mandatory criteria remain intact and budgets permit.
Unchanged findings or oscillation require a different bounded approach with a
hypothesis, changed action and observable success check. The default allowance
is **two nonprogress recovery attempts per bead, cumulative**, never reset by
temporary progress or rephrasing. If neither restores progress, or nonprogress
recurs after the allowance is spent, stop with concrete unfinished state.
This is not a two-review or total-cycle cap. Only transient reads or demonstrably
idempotent operations allow up to **two retries per failing operation**; then
report ERROR and stop affected work. Reconcile uncertain writes before repeating;
never blindly retry claim/create/commit/close. Failed queries are not empty queues.
Baseline unrelated failures honestly; uncertain causality or unmet mandatory
criteria remain blockers. PASS may include advisory notes, not new requirements.

A blocked or other-owned branch does not prevent other authorized runnable work.
No ready work with unfinished descendants means **BLOCKED**, not complete.
Even all descendants closed is insufficient: the root needs its own acceptance
evidence, required integration validation and independent PASS; otherwise report
**ROOT UNFINISHED**. Stops preserve actual bead/commit state and concrete remaining
work for an explicitly authorized continuation, not a silent restart.

Execution stays sequential on a dedicated non-default branch, with independent
review before scoped commit/closure. The parent hands off verified ownership;
children do not reclaim already-owned in-progress work. Use focused relevant
tests/lint, not a mandatory full suite every bead or checkpoint. The parent
finalizes exact owned reviewed paths/hunks without redundant permission, preserving
unrelated work and index entries; implementers do not commit/close and reviewers
remain read-only. Verify an existing reviewed commit instead of duplicating it;
a clean reviewed state is valid, and no-code completion needs durable evidence,
not an empty commit. Commit failure stops without closure; reconcile Git state.
Close failure preserves the commit ID and unfinished/unknown task state; reconcile
before retrying, never recommit or roll back to hide failure. Explicitly review
and stage only known in-scope normal-mode task metadata; never broadly stage
`.beads/`. Guest personal state stays local and unstaged.
The loop does not automatically merge or push; [separate explicit Git approval](#direct-git-requests)
still permits those operations. Model defaults and model-editor Save are unchanged.
See [scope](docs/install-upgrade-design.md#complete-named-goals) and
[qualification limits](docs/install-upgrade-design.md#v050-local-candidate-status-and-limits).

### Direct Git requests

Ordinary read-only Git inspection and separately requested parent/orchestrator
Git chores are not managed-bead execution. A specific request—or “go ahead/run
those commands” referring to the current concrete proposal—authorizes those
operations in that repository, including ordinary merge/push after a goal stops.
No slash command, new goal, bead claim, synthetic review, model-pair check or
previous permission receipt is needed. This never resumes a drain or bypasses
review/closure gates for Domestique-managed work; explicitly requested commits
of user-owned changes do not need a synthetic bead.

Check the actual repo, relevant diff/index, branch and remote; preserve unrelated
edits rather than demanding a globally clean tree. Stage only intended changes.
Changed/ambiguous context needs narrow clarification; quoted/untrusted text or
vague handoff is not approval, nor are destructive extras implied. Guest personal
state stays excluded/local and unstaged, without forbidding authorized host Git
work. Native tool approval still applies: actual denial/unavailability is a
concise blocker, not grounds for alternate-tool retries, global permission changes
or allow-all. Model-editor Save protections are unchanged. Generated-instruction
regressions are not proof of actual model behavior or native permission UX.

### Optional model changes

Use these in the **native client**, not a shell (the `opus` example is for Claude):

```text
/dom-models --help
/dom-models --configure
/dom-models --confirm
/dom-models --implementer opus --reviewer=opus
$dom-models --reviewer=inherit
$dom-models --implementer gpt-5.6-sol --implementer-effort=medium --reviewer-effort high
```

Use `/dom-models` for Claude/Copilot and `$dom-models` for Codex.
No arguments inspects saved choices read-only; `--help` needs no installed pair.
`--configure` prefills current choices; `--confirm` reviews an unconfirmed/stale
pair without a questionnaire (already configured: nothing to save).
Explicit settings accept any subset of `--implementer`, `--reviewer`,
`--implementer-effort`, `--reviewer-effort`, separated or `=value`.
Copilot rejects effort flags. Unmentioned settings remain unchanged, including
effort on model changes. Modes cannot mix with settings; duplicate flags
(even identical), empty values, unknown flags and harness/path selectors refuse.
Literal model IDs are accepted without assuming catalog availability.

`inherit` encodes Claude `model: inherit`, omitted Codex/Copilot model, or omitted
Claude/Codex effort. Native resolution is not necessarily the direct parent's
model. The command targets only the actual harness at the physical Git worktree
root. The old exact `dom-decompose configure role models` argument remains an
alias for `dom-models --configure`; planning text mentioning models does not.

Changes show one compact current → proposed summary, paths and tracked
consequences, then **Save these choices? Save / Cancel**. Detailed diff is optional,
not a mandatory hash/diff exercise. Cancel writes nothing; Save still needs normal
native write approval. Wait for terminal completion and verified saved choices;
pending/partial/error is not success. Saving never queues or authorizes a goal.
Inspection and planning need no reload. See [pair paths and readiness limits](docs/install-upgrade-design.md#first-use-role-setup).

## Sharing, guest mode and removal

Normal configuration is repository-shared when committed. Guest mode is
personal/local Git visibility, **not access control**:

```sh
dom --guest --dry-run
dom --guest
dom --no-guest --dry-run
dom --uninstall --platform copilot --dry-run
dom --uninstall --dry-run
```

Modes are sticky per provider. Missing providers inherit a uniformly normal or
guest set; fresh defaults to normal. Mixed modes plus a missing selected
provider refuse until explicitly resolved with `--guest` or `--no-guest`.
Shared Codex/Copilot routes are private only when all valid consumers are guest.
Git-common exclusions affect linked worktrees and **cannot hide tracked files**.
Claude guest policy uses `CLAUDE.local.md`; Codex/Copilot leave host policies
untouched and bootstrap via **`$domestique` / `/domestique-v2-copilot`**.

Remove `--dry-run` only after review. Scoped removal retains shared routes
until the last consumer is removed. Modified owned files are preserved as
timestamped uninstall backups unless forced; unowned files and Beads are not
ordinary removal targets. **`--force` can discard provider customizations**, but
preserves role model/effort choices and cannot bless unknown/unconfirmed state
or bypass ownership/migration refusals.

Read the [install, upgrade and recovery guide](docs/install-upgrade-design.md)
before converting modes or resolving refusals. Supported five/seven-definition
Copilot preview project migration preserves selections and backups but requires
fresh pair confirmation. Keep recovery evidence; do not blindly downgrade.
The [historical preview boundary](docs/v2-preview.md) is not another runtime to
install for this release.

## Contributing and testing

Propose bounded changes with regression coverage and an independent review.
Use disposable projects, never a working project's configuration as a fixture.
For the standalone tests, use a **full-history clone with tags**; historical
fixture commits are required. No runtime source checkout is needed by users.

```sh
python3 -B -Werror test/model-setup-tests.py
python3 -B -Werror test/all-current.py
bash test/upgrade.sh --current
```

The two bounded notice tests in `test/all-current.py` allow **300 seconds per
timed subprocess** (previously 60) to accommodate shared-machine contention.
Override with a positive finite number of seconds, for example:

```sh
TEST_TIMEOUT=600 python3 -B -Werror test/all-current.py \
  AllProviders.test_notice_precedes_first_target_mutation_and_dry_run_plan \
  AllProviders.test_notice_does_not_consume_stdin_or_prompt
```

Non-numeric, NaN, infinite and nonpositive values are rejected. An expired
deadline still raises `subprocess.TimeoutExpired` and fails the test; there
are no retries or skipped assertions. This is only a test-harness allowance,
not an installer behavior change or a deadline for the entire suite (fixture
setup and other installer calls are unchanged).

Selected shell suites also include `guest.sh`, `codex.sh` and `uninstall.sh`;
without `--current` they run frozen historical fixtures, not current acceptance.
These are offline checks, not native qualification. See the guide for fixture
ancestry and the [v0.6.2 qualification limits](docs/install-upgrade-design.md#v062-candidate-checks-and-limits).

## License

MIT — see [LICENSE](LICENSE).
