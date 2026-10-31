# Standalone: install, upgrade and recovery

Current sections are the **v0.3.0 release guide**.
Implementation reviews hq-c6o.2–.6 passed; native qualification hq-c6o.8
remains **UNQUALIFIED pending user authorization for fixture/model usage**. Publication was authorized
with this limitation disclosed, not with native PASS or epic completion.
Historical evidence below does not qualify v0.3.0.
The product is one standalone `domestique.sh`; no global runtime, `dom2` or
project enable step. See the [README](../README.md) for the workflow.

## Remote install and upgrade

Existing `dom` aliases that fetch `main/domestique.sh` receive v0.3.0's new
defaults, flags and `dom-models` command on their next invocation after release
to main, without an alias change. Nothing
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

A source checkout is optional; the new features are also available through
remote `dom` after release. To inspect reviewed source locally:

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
| `--platform claude`, `codex`, `copilot`, `both`, `all` | Explicit selection; **both = Claude+Codex**. Installs are additive: persisted Claude/Codex may also be selected; unselected Copilot remains. Read the actual plan. |
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
Non-Git/subdirectory installs retain compatibility behavior but cannot claim
helper-configured status outside that root.

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
2. For execution, verify the configured pair and actual native role discovery,
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
5. Explicitly review/dispose of tracked changes before goal work; do not
   auto-stage, stash or hide them. Installation/Save never queues or authorizes
   a goal. After a configuration detour, give a fresh explicit goal naming the
   intended epic; a fresh valid install alone needs no renewed authorization.

### Native entries and ownership

Claude uses `/dom-models`, `/dom-decompose` and `/dom-goal EPIC_ID`, stored under
`.claude/commands`. Codex uses `$dom-decompose` and `$dom-goal EPIC_ID`;
Copilot uses `/dom-decompose` and `/dom-goal EPIC_ID`. Codex also supports
`/skills`. Codex/Copilot share the canonical
`.agents/skills/dom-decompose/SKILL.md`, `.agents/skills/dom-goal/SKILL.md`
and `.agents/skills/dom-models/SKILL.md`.
Routing follows actual native context, not which other clients' files exist.

Compatibility entries remain: Claude `/decompose`, `/goal`; Codex
`$domestique-decompose`, `$domestique-goal`; Copilot
`/domestique-v2-copilot-decompose`, `/domestique-v2-copilot-goal`.
They retain the same explicit config-vs-plan routing and execution gate.
Loading an entry alone never authorizes work;
a goal needs an explicit request naming the epic. Fresh independent reviewer
PASS remains required before task commit/closure. Copilot's default bound remains
**one reviewed bead**; native `/goal` or `/autopilot` is not Domestique
authorization. Broader unattended authorization (hq-xc2) remains unimplemented,
not shipped here. Existing epic-drain bounds are unchanged.

Provider snapshots live in `.claude/.domestique`, `.codex/.domestique` and
`.github/.domestique`; shared routes are owned by `.agents/.domestique`.
The flat `snapshot_format=1` manifests and pristine `base/` files remain the
authority, alongside mode/selection/exclusion records. Normal policy blocks
live in `CLAUDE.md`, `AGENTS.md` (or existing `AGENTS.override.md`) and
`.github/copilot-instructions.md`.

## Preserving upgrades and mode conversion

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

A generic plain-file conflict leaves the live file unchanged, writes
the proposed merge to `.new`, preserves a `.bak.<timestamp>` and exits `3`.
Inspect and resolve explicitly; do not replace the live file blindly.
Legacy differing provider files without snapshots may be adopted unchanged,
with pristine emitted bases seeded for a subsequent merge; this is **not a role
pair ownership exception**. Unknown ownership, missing policy bases,
unsafe paths or incompatible retained policy blocks can refuse before writes.

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
  hq-7sm.17 and hq-6pf remain unresolved; hq-xc2 is unimplemented and existing
  epic-drain/one-reviewed-bead bounds are unchanged.
- After publication to main, the existing remote alias fetches these features.
  Preview and pin the same bytes for apply; local source installation remains
  an option, not a requirement.
