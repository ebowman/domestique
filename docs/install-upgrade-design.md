# Standalone 0.2.0: install, upgrade and recovery

This is the publication guide for the **v0.2.0 preparation tree**, not an
announcement that main or the tag has been published. The current product is
one standalone `domestique.sh`; no global runtime, source checkout, `dom2` or
project enable step is required. See the [README](../README.md) for the workflow.

## Remote install and upgrade

Existing `dom` aliases that fetch `main/domestique.sh` receive new bytes on their
next invocation **after main is published**. Nothing updates in the background,
and publishing only a tag does not change those aliases.
Run from the intended project root; the optional positional argument is the
target directory. Bash, Git and Python 3.11+ cover the all-three path.
Native clients/model software are not installed.

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

The `v0.2.0` tag may replace `REV` only after publication. Until then, test the
reviewed local file in a disposable project. Historical `v0.1.0` is neither this
release's behavior nor a safe downgrade of migrated state.

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
| `--force` | Replace differing provider files without `.bak`; managed policy files still receive backups. Can discard customizations; not an ownership or migration bypass. |
| `--with-beads` | If `bd` is available, initialize when needed using safe skip flags. Normal mode sets up selected providers; guest uses stealth and no provider setup. Does not install Beads. |
| `--uninstall` | Remove owned configuration; optional `--platform` scopes removal, otherwise scans all three. |
| `--purge-beads` | Only with uninstall; explicitly deletes the target's `.beads`. Omit to preserve task data. |
| `--help`, `-h` | Show the selected script's full contract. |

Uninstall combines only with target, platform, dry-run, force and purge-beads,
not with guest/no-guest/with-beads.

## First-use role setup

Setup is independent **per physical project and per harness**. There is no
global model override registry.

| Harness | Implementer / reviewer paths | Deterministic helper |
| --- | --- | --- |
| Claude | `.claude/agents/implementer.md` / `.claude/agents/reviewer.md` | `.claude/domestique-model-setup.py` |
| Codex | `.codex/agents/implementer.toml` / `.codex/agents/reviewer.toml` | `.codex/domestique-model-setup.py` |
| Copilot | `.github/agents/domestique-v2-copilot-implementer.agent.md` / `.github/agents/domestique-v2-copilot-reviewer.agent.md` | `.github/domestique-model-setup.py` |

Use `/dom-decompose configure role models` in Claude/Copilot or
`$dom-decompose configure role models` in Codex. First interactive goal also
requires setup if the pair is not confirmed. Ordinary planning skips setup and
all helper/role readiness checks, even with missing/unconfirmed/manually edited
pairs. Only the entire explicit `configure role models` argument selects setup;
planning text mentioning models does not. Reuse saved native selections.
Ask missing/unconfirmed choices together, including supported effort, explaining
local persistence and when they apply; check native availability and persistent role support.
Explicit inheritance is a choice: Claude uses `model: inherit`; Codex/Copilot
omit model. Copilot does not support persisted effort through this helper.
Generated defaults and missing fields are not user consent.

The installed protocol verifies helper ownership and pristine-byte equality,
then executes the verified bytes. Prepare/verify are **read-only**, with no
scratch or staged plan. Summarize project/harness, current → chosen model/effort,
exact role files, scalar/marker-only change scope, preserved tools/prompts and
tracked consequences. Offer detailed diff on request; do not require raw diff,
marker JSON, hashes or verbose evidence output. Retain the digest independently.
Ask **Save these choices?** after preparation, then obtain any ordinary scoped
native write approval and apply only that exact plan. Initial choices are not
save consent; changes require reprepare, new summary and renewed consent.
Cancel means zero writes. The digest binds integrity, not consent.
The helper edits model/effort scalars and the pair marker while preserving
unrelated metadata, comments, body, line endings and modes.
Changed snapshots/roles/parents cause refusal rather than a stale apply.

Wait for terminal completion, including any background result, check the helper
result and verify the saved pair before claiming success. Nonzero/partial or
unverifiable results are failures, not pending success.
After save, no queued goal or task work. Respond with terse saved choices and
only the necessary next step. Explicit planning may proceed without reload or
repeating an already supplied brief; it never delegates, claims or executes tasks.
Before execution, supported reload/fresh native invocation is required when
registrations are stale/unknown. Verify registrations, precedence, inheritance, effective
choices and availability. Explicitly review/dispose of tracked setup changes
before a fresh goal; do not auto-stage, stash or hide them.
Codex's current immutable conversation roles need not match a proposed persistent
edit, but fresh registrations must match before dispatch. A model catalog alone
does not prove persistent role support. No in-session override or fallback to
old defaults substitutes for a supported saved pair and reload.

The implementer file's `# domestique-model-setup: JSON` marker binds the physical
project, harness and both role hashes. Manual body/model edits invalidate it.
Unchanged confirmed pairs survive reruns without prompts; changed bytes need a
new prepared summary/consent. Helper schema, serialization and pair hashes are unchanged.
Modified or unowned helpers refuse rather than being adopted or merged.
Filesystem verification is **not native attestation**: the assistant still
checks actual discovery, role support, availability and available telemetry.
Existing native hooks are not controlled. Unavailable/mismatched models mean
STOP, not fallback. Partial apply returns recovery information; preserve and
reconcile it rather than inferring approval or blindly rolling back.

### Native entries and ownership

Claude uses `/dom-decompose` and `/dom-goal EPIC_ID`, stored under
`.claude/commands`. Codex uses `$dom-decompose` and `$dom-goal EPIC_ID`;
Copilot uses `/dom-decompose` and `/dom-goal EPIC_ID`. Codex also supports
`/skills`. Codex/Copilot share the canonical
`.agents/skills/dom-decompose/SKILL.md` and `.agents/skills/dom-goal/SKILL.md`.
Routing follows actual native context, not which other clients' files exist.

Compatibility entries remain: Claude `/decompose`, `/goal`; Codex
`$domestique-decompose`, `$domestique-goal`; Copilot
`/domestique-v2-copilot-decompose`, `/domestique-v2-copilot-goal`.
They retain the same explicit config-vs-plan routing and execution gate.
Loading an entry alone never authorizes work;
a goal needs a fresh explicit request naming the epic.

Provider snapshots live in `.claude/.domestique`, `.codex/.domestique` and
`.github/.domestique`; shared routes are owned by `.agents/.domestique`.
The flat `snapshot_format=1` manifests and pristine `base/` files remain the
authority, alongside mode/selection/exclusion records. Normal policy blocks
live in `CLAUDE.md`, `AGENTS.md` (or existing `AGENTS.override.md`) and
`.github/copilot-instructions.md`.

## Preserving upgrades and mode conversion

Compatible snapshot upgrades retain model choices and customizations using
three-way merges. A plain-file conflict leaves the live file unchanged, writes
the proposed merge to `.new`, preserves a `.bak.<timestamp>` and exits `3`.
Inspect and resolve explicitly; do not replace the live file blindly.
Legacy differing provider files without snapshots may be adopted unchanged,
with pristine emitted bases seeded for a subsequent merge. Adoption is not a
general exception to ownership checks: unknown ownership, missing policy bases,
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
selection rules apply: **selector-less 0.2.0 updates add all three**, even to
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

Independent final native review passed for the standalone logic at
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

### Release selection and fixture portability

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
