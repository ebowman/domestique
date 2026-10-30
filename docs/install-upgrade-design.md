# Install/upgrade design: current private preview and historical contracts

## Reading this document

### Deterministic native model setup (hq-7sm.22)

The same standalone installer now installs a harness-bound
`domestique-model-setup.py` in `.claude`, `.codex`, or `.github`. It uses existing
Python (3.11+ for Codex TOML), without packages, native clients, a model registry,
service or second installer. Old provider inventories remain upgrade inputs;
the preserving lifecycle adds the helper and its pristine base. Modified or
unowned helpers refuse rather than being adopted or merged. Customized native
role bodies remain supported under existing ownership guards. Guest visibility,
preview migration and scoped removal use the existing provider state.

Native UX is still two-phase: establish the ACTUAL caller, ask BOTH role choices
inline, check supported persistent native selections, then prepare and display
the actual minimal diff. Preparation and filesystem verification write nothing.
Explicit human save consent and normal native protected-write approval precede
apply. The independently retained displayed-plan digest binds integrity, not
consent. Apply accepts no replacement body, destination or model overrides.
Read-only preparation/verification accept safe readable roles and parents
without requiring write access. Apply checks writable roles/parents only in the
approved execution context; filesystem modes remain stale/race evidence,
distinct from the current native sandbox's write permission.
Native instructions externally verify helper ownership/path and equality to its
pristine snapshot and execute those same verified bytes, not a later path read.

The shared emitter patches only model/effort scalars and the existing marker,
preserving unrelated metadata, comments, body, line endings and modes. Full
role/base/manifest/helper and parent snapshots are rechecked before publication.
Live roles and pristine bases are validated separately for exact native names,
nonempty string descriptions and native prompt content (including a nonempty
string `developer_instructions` for Codex), without replacing customized bodies.
The old marker is invalidated first when present; reviewer is published before
the new implementer marker. Failure is nonzero with partial-state recovery
information, never blind rollback or inferred approval. Only operation-owned
temporaries are cleaned; unknown leftovers remain for explicit reconciliation.
The native files, pair marker and existing snapshots remain the sole authority.

After saving, STOP for a fresh native invocation; no queued goal or Beads work.
On fresh goals, helper JSON is **filesystem-only**, not native readiness or
qualification. The assistant still checks actual roles, discovery/precedence,
overrides, resolved inheritance, availability and available telemetry. Existing
native hooks are not controlled; no zero-external-hook-read claim is made.
Manual body edits invalidate confirmation and require an actual diff and new
explicit consent. Native effectiveness remains the separate hq-7sm.6 gate.
Historical validation tables below describe their pinned inputs, not this change.

### Integrated offline gate for native handoff (hq-7sm.14, 2026-10-29)

Candidate: `f928cb270613f32d378b196854fa3ecf93b686da`, with only the bounded
`test/all-current.py` extension and this evidence update uncommitted. Product
bytes are unchanged. SHA-256 pins:

| Input | SHA-256 |
| --- | --- |
| `domestique.sh` | `d3c317aae01929a9aac858e37deec95ae60f4e30203ff9affe997ea76f927a93` |
| `domestique2.sh` | `0fb14c892e67fe062a6611139deefe355c402eed4a693ca08a522ee60be1b16b` |
| `test/all-current.py` | `76fffb01ae2ea03256ccc37c0f215a6667e1640ef10fdd2ab44f086f3023899e` |
| `test/acceptance.py` | `3153af110c5d5863e5e79a1da1bf839f5ed8839f3d6a3f6bcb59b98cd030a8c8` |

The combined fixture uses source-free stdin in independent normal/guest Git
projects. Six independently customized native-format roles carry synthetic
pair confirmations, distinct model strings and retained tools/metadata.
Sequential single-harness body upgrades preserve exact unrelated bytes and
markers: only the changed role's hash becomes stale; other pairs remain valid
until their own update. These are **hash-contract checks, not native consent**.
Reruns preserve bytes/modes; configured three-way merges may refresh mtimes.
The first targeted attempt incorrectly demanded mtime stability on those real
merges; that test assertion was narrowed, without a product change. Dry-runs
still require full filesystem/mode/mtime, index and exclusion invariance.

Static enumeration checks eight physical skill entries, with exactly one
canonical `dom-goal` and one `dom-decompose`, plus all four Claude command names.
Actual ordinary/bootstrap, compatibility, canonical, role and policy contents
are checked for caller boundaries and explicit-authority requirements.
This is **static inventory/isolation evidence, not native discovery**.
The same configured fixture exercises full removal on a copy and scoped
Codex → Claude → Copilot removal, remaining shared ownership, exact private
exclude unions, modified-role preservation, unchanged index/isolated HOME,
and no implicit Beads/dependency installation.

Existing suites were reused rather than duplicated: platformless Claude
`v0.1.0`/`415fb69` ownership/recovery; `64f4e09` Claude/Codex upgrades (now both
normal and guest through stdin); five/seven preview creation and preserving
cutover; retained policies; invalid options; conflict, symlink, no-clobber and
pre-write refusals. The hq-7sm.19 private corpus was **not rerun or copied into
tests**; its separately qualified aggregate and limitations below still apply.

Full actual-current results, with frozen product/test inputs and no full-suite
retries or 600-second suite cutoff:

| Invocation (`python3 -B -Werror` for Python suites) | Result |
| --- | --- |
| `test/all-current.py` | 33/33 (3304.865 s) |
| `bash test/copilot.sh --current` | 15/15 + 8/8 migration (2128.510 + 492.726 s) |
| `bash test/guest.sh --current` | 16/16 |
| `bash test/codex.sh --current` | 30/30 |
| `bash test/upgrade.sh --current` | 13/13 |
| `bash test/uninstall.sh --current` | 24/24, including purge reporting and END-only refusal |
| `test/preview-project-tests.py` | 15/15 |
| `test/preview-workflow-tests.py` | 12/12 |
| `test/preview-inspect-tests.py` | 9/9 |
| `test/preview-machine-tests.py` | 4/4 |
| `test/acceptance-tests.py` | 107/107 |

The actual static runner scope is
`python3 -B -Werror test/acceptance.py --exhaustive --total-seconds 4200 --suite-seconds 3600 --suite CURRENT:syntax-lint-ast-diff`.
It **passed**: 18 shell files, 5 emitted helpers, 73 Python files, 2 embedded
Python payloads, and zero warning-level ShellCheck exceptions; the current thin
bootstrap is checked explicitly. This selected scope is not the runner's
exhaustive full-offline manifest.

**Remaining gates:** hq-7sm.17's historical END-only cause remains unproven;
this current pass does not close it or claim a fix. Existing diagnostics and
the separately reported 100 current/30 baseline focused passes remain historical
evidence, not new runs here. hq-7sm.6 requires separate operator-approved native
budgets, an isolated all-installed project, actual client discovery/precedence
and role registration, independently consented pairs with available native
model/tool evidence, fresh reload/reinvocation, and observed bounded
implementer/reviewer dispatch with no cross-harness fallback. No installed
native versions, model availability, user acceptance or publication are claimed.
No native clients, paid PTYs, live projects or real Beads initialization were
used by this offline gate.

### Remote install and upgrade

The standalone candidate's selector-less **fresh install and rerun select all
three**: Claude Code, Codex and GitHub Copilot. The `VERSION` notice uses the
script's actual version (currently `0.1.0`, not a new release announcement) and
shows the physical target and actual selected normal/guest modes after safe
preflight, before the first target mutation. Dry-run prints the same plan without
target writes; preflight failures instead give preserving diagnostics. There is
no installer stdin questionnaire or stored consent state.

Run from the intended project root; an explicit target can also follow `--`:

```sh
curl -fsSL https://raw.githubusercontent.com/ebowman/domestique/main/domestique.sh | bash -s -- --dry-run
curl -fsSL https://raw.githubusercontent.com/ebowman/domestique/main/domestique.sh | bash -s --
# Preview any explicit selection before applying it without --dry-run:
curl -fsSL https://raw.githubusercontent.com/ebowman/domestique/main/domestique.sh | bash -s -- --platform claude --dry-run
curl -fsSL https://raw.githubusercontent.com/ebowman/domestique/main/domestique.sh | bash -s -- --platform codex --dry-run
curl -fsSL https://raw.githubusercontent.com/ebowman/domestique/main/domestique.sh | bash -s -- --platform copilot --dry-run
curl -fsSL https://raw.githubusercontent.com/ebowman/domestique/main/domestique.sh | bash -s -- --platform both --dry-run
curl -fsSL https://raw.githubusercontent.com/ebowman/domestique/main/domestique.sh | bash -s -- --platform all --dry-run
```

**`both` means Claude+Codex, not Copilot.** Explicit installs are additive, not a
way to remove existing providers: persisted Claude/Codex may also be selected;
an existing unselected Copilot is retained unchanged. Read the actual selection
in the notice. `--uninstall --platform copilot` removes only Copilot's owned
projection; selector-less uninstall scans all three.

**Moving URL:** pushing `main` changes what existing remote commands/aliases
receive on their **next execution**. Nothing updates installed projects in the
background. A release tag alone does not change main or rewrite an alias.
Two main downloads can differ between preview and apply. Pin both to the same
full reviewed commit SHA by replacing `/main/` with `/<FULL_COMMIT_SHA>/`
(substitute the actual published SHA, not the placeholder). An explicit
published-version URL is:

```sh
curl -fsSL https://raw.githubusercontent.com/ebowman/domestique/v0.1.0/domestique.sh | bash -s -- --dry-run
```

That tag contains historical code, not this candidate's all-three/migration
contract; consult the selected revision's help. Pinning selects script bytes,
not a rollback of project state. The candidate still reports `0.1.0`; version
text alone does not identify a commit. No publication/version bump happens here.
Native qualification (hq-7sm.6) precedes final release handoff (hq-7sm.7);
offline tests/install success do not establish native support or user acceptance.
For acceptance against actively used repositories, compare installer-relevant files, Git indexes and exclusions immediately before and after each operation; retain later drift separately rather than claiming whole-session immutability. In one candidate dry-run, the index remained byte-identical through the post-copy check, then changed more than thirteen minutes later in entries outside installer-managed paths. The writer is unknown: this establishes the operation-window result, not a general attribution or permission to reset the user's index.

**Existing-install qualification (hq-7sm.19, 2026-10-29).** Product bytes remain
the tested `5b8f3a9`; `e6e9eba` changes documentation only. All **159** inventoried
locations are accounted for: **157** original dry-runs and isolated-copy
lifecycles, **2** inventory-only exclusions. The active candidate is an additional
supplemental exclusion, not part of 159. Original dry-runs yielded **34 accepted,
123 preserving refusals**: 106 retained-projection conflicts, 14 unknown retained
ownership, 2 policy-merge conflicts and 1 missing policy base. These are not 157
upgrade passes or automatically bugs; actionable per-project diagnostics remain
private. Copy install/rerun outcomes matched those categories; scoped and unified
removal each succeeded on all **157 copies**. Original installer modifications
attempted: **0**. No live upgrades, force/recovery writes or native-client
qualification occurred.

All **157** immediate post-operation and post-copy original comparisons preserved
the observed file hashes/modes, indexes, config and exclusions. Fresh read-only
accounting at **19:12:08–19:12:27 UTC** found **154 exact matches**, **4 later
index-drift items** and **1 inventory-only directory-metadata drift**. The four
items involve three indexes: two have logical changes outside the observed
installer surfaces; two items share the third, whose path/stage/mode/blob entries
are unchanged despite different raw bytes. Writers remain **unknown**; neither
stat-cache attribution nor installer mutation is inferred. Relevant surface
bytes/modes, config/excludes and tracked/ignored query results still match for
all 159, with no observed managed-surface loss. The supplemental candidate's
index change corresponds to the intervening documentation revision. Earlier
drift artifacts, operation timestamps and new per-item observations are retained
privately for review; this is operation-window preservation, not perpetual
directory immutability or permission to disregard index writes.

Copy checks covered byte/mode-faithful relevant surfaces, tracked presence,
effective queried ignores, preservation on refusal, rerun stability, removal
backups and unowned exclusion bytes. Copies contain relevant surfaces only:
controlled Git models do **not** reproduce staged bytes, history, shared-worktree
effects or inherited-policy fidelity. Symlink targets and pruned directories are
inventory gaps. Final accounting reused the unchanged product's retained runs,
not new installer executions. Wrapper (.16), unknown-marker (.17) and native
qualification (.6) remain separate.

**Configuration, not software installation:** no native client/model software is
installed. Project role files are `.claude/agents/{implementer,reviewer}.md`,
`.codex/agents/{implementer,reviewer}.toml`, and
`.github/agents/domestique-v2-copilot-{implementer,reviewer}.agent.md`.
Commands/workflows live under `.claude/commands`, `.agents/skills` and
`.github/skills`; provider snapshots live under `.claude/.domestique`,
`.codex/.domestique`, `.github/.domestique`, with shared routes owned by
`.agents/.domestique`. Normal policies are managed blocks in `CLAUDE.md`,
`AGENTS.md` (or an existing `AGENTS.override.md`) and
`.github/copilot-instructions.md`.

Preserving snapshot merges retain existing model choices/customizations;
`--force` can replace provider files and is not a migration/refusal bypass.
There is **no global model override registry**. Each harness independently
requires explicit first-use confirmation of its implementer/reviewer pair using
native availability evidence, then reload/fresh invocation before work. Generated
defaults are suggestions, not consent; changed role bytes invalidate confirmation.
Use `/dom-decompose configure role models` in Claude/Copilot or
`$dom-decompose configure role models` in Codex. Installation is not readiness.

Codex setup distinguishes **pre-save persistent role-file support** from
**post-save fresh-session registration readiness**. Immutable roles loaded in
the current conversation need not match the proposed pair: that mismatch alone
does not prohibit a supported persistent edit. Verify installed role-file
semantics and provider/tool compatibility; a model catalog alone is insufficient.
Show the actual diff, obtain setup-only consent and required native scoped
protected-write approval, save only, and stop for fresh reload/reinvocation.
No in-session Task/spawn override or old-default fallback is permitted.
Fresh registrations must match the chosen/native-effective pair before dispatch;
genuine capability, inheritance, tool or permission restrictions still stop.
This instruction clarification is not native qualification; effectiveness
requires new, separately authorized native evidence after reload.

**Guest/private scope:** modes are sticky per provider; missing providers inherit
a wholly guest or normal installed set (fresh is normal). Mixed modes with a
missing selected provider refuse until explicitly resolved with `--guest` or
`--no-guest`. Claude guest policy is personal `CLAUDE.local.md`; Codex/Copilot
leave host policies untouched and bootstrap via `$domestique` /
`/domestique-v2-copilot`. Local Git-common exclusions hide owned guest paths, not
tracked files or arbitrary host content; linked worktrees share those ignore
effects. Shared routes are private only when all valid Codex/Copilot consumers
are guest. This is Git visibility, not access control. Old unguarded owned host
policies refuse in guest mode; see [preserving policy conversion](#single-script-shared-skill-foundation-hq-7sm10).

**Preview migration/recovery:** supported original five-definition and
seven-definition (`public-names`) Copilot project receipts migrate without the
machine preview/source. Copilot stays private unless `--no-guest` is explicit.
Compatible model metadata is preserved, but new workflows need fresh pair
confirmation. Unknown ownership, unsupported metadata/body forks, unsafe paths
and merge conflicts refuse rather than discarding edits. See the
[exact supported layouts, refusals and backup recovery](#supported-copilot-preview-project-migration-hq-7sm13)
below. Keep `.domestique-private/copilot-preview-migration/` and all custom files;
after interruption preview/retry the **same installer and flags**, reconciling
unknown afterimages explicitly. Do not blindly reinstall an older script as a
downgrade: it cannot reverse migrated ownership/workflows. Preserve backups and
review the complete project state before any manual recovery.

### Supported Copilot preview project migration (hq-7sm.13)

Run the same standalone `bash domestique.sh ROOT --dry-run`, inspect its plan,
then rerun without `--dry-run`. `--platform copilot` scopes the selection;
the default selects all three providers. The exact physical Git root must match
the active `.domestique-private/copilot-preview.json` receipt, its Git/common
identities, native names, created path identities and exact exclusion contribution.
Supported inventories are the original five (absent inventory discriminator)
and seven (`public-names`). Original five-definition locators without `--harness`
and the subsequent explicit-harness locators are recognized from their source
templates. No machine/source directory is opened, executed or required.

Before **any selected-provider writes**, the bounded embedded helper validates
source bytes, metadata, shared ownership and replacement workflows; the existing
snapshot, policy, merge and lifecycle preflights validate the rest of the plan.
Dry-run uses the same candidates and performs no project writes. Malformed,
foreign, copied, disabled/partial or unknown receipts, experimental authority,
symlinks/hardlinks, tracked paths, unowned shared collisions (even identical),
custom alias leftovers and prompt-body forks refuse with preserving diagnostics.
`--force` cannot bypass these checks or discard the metadata transfer.

Every accepted scalar native frontmatter field, comment and unaffected byte is
retained, plus flat JSON string arrays for `tools`; unknown scalar keys acquire
no invented semantics. Complex YAML, duplicates, invalid scalars and Copilot
`effort`/`model_reasoning_effort` are unsupported and refuse. Names remain exact.
Only the known generated description is replaced with the generated guarded
description. A custom description must already start with the exact current
Copilot harness boundary, or the human must reconcile it explicitly. No prose
classifier or metadata allowlist substitutes for the existing scalar contract.
Known locator bodies become standalone workflows; any other body refuses.
Model examples are not selections. Selected model/tools/metadata survive, but
the old pair marker is removed: new workflow bytes require fresh explicit
confirmation and native readiness checks, never automatic approval.

A complete bounded source/output backup is staged before cutover at
`.domestique-private/copilot-preview-migration/`. It retains original receipt,
native files, exclusion bytes and file modes; its exact directory is locally
excluded even after normal conversion. The old project receipt is revoked before
publishing snapshot authority. Only unchanged proven obsolete `.github` public
aliases are removed; canonical entries live under `.agents`. Pristine generated
bases, not configured files, seed the normal snapshot merge contract.
Copilot remains guest/private unless `--no-guest` is explicit. The Git-common
exclude union retains host lines, other-provider privacy and existing Beads
ownership. Neither the preview machine install, original source, `dom2`, nor
Beads data is migrated or removed.

Failures/interruption return nonzero and disclose partial results. Retain the
backup and rerun the **same installer and mode flags**, first with `--dry-run`.
Pending recovery verifies the fixed source/output inventory and accepts only
old bytes, planned afterimages, or removals bounded by that plan. It never
overwrites edits made during recovery. Unknown/incomplete backup staging,
changed files, custom leftovers or changed installer outputs require explicit
preserving reconciliation; do not delete them merely to make installation pass.
The `complete` file marks an inert source backup, not another native authority;
later runs use ordinary snapshots. This is cooperative single-writer recovery
using staging/atomic file replacement, not an adversarial transaction service.

`bash test/copilot.sh --current` includes real five/seven creation, model writer,
refusal, source-independent stdin, exclusion preservation and interrupted-cutover
fixtures. Historical shell mode is unchanged. These are offline lifecycle
checks, **not native qualification** of the migrated workflows; that remains
pending separately.

### Single-script shared skill foundation (hq-7sm.10)

This candidate's source-free `domestique.sh` installs Claude, Codex and Copilot
on both fresh and repeat selector-less runs (hq-7sm.12). `--platform all` selects
the same three; `both` remains Claude+Codex only. Explicit selections add to the
persisted subset, never silently remove another provider. Uninstall without a
selector scans all three; explicit uninstall removes only that selection.
The self-contained Copilot projection supports the bounded preview project
migration below (.13). Native qualification .6 and publication remain pending.
Installed provider modes stay sticky; missing providers inherit wholly guest or
wholly normal installations (fresh is normal). With mixed installed modes and
a missing selected provider, preflight refuses without changing provider, shared,
policy or exclude state. Explicit `--guest`/`--no-guest` provide intentional
resolution using the established additive selection semantics.
Required local dependencies and all selected target/state paths are checked
before writes, including Git-common exclusions and Python's Codex TOML parser.
The all-provider install requires Git and Python 3.11+; native clients remain
optional for config installation and are never installed by this script.
Operational failures return nonzero and disclose possible partial results,
not three-client readiness. No machine launcher, source reference or separate
runtime is required by the installed workflows.
The two canonical `.agents/skills/dom-{decompose,goal}/SKILL.md`
entries route by actual native client context/tools, never installed directories.
Codex bodies remain `.agents/skills/domestique{,-decompose,-goal}/SKILL.md`;
Copilot bodies are
`.github/skills/domestique-v2-copilot{,-decompose,-goal}/SKILL.md`, using
`domestique-v2-copilot-{implementer,reviewer}` agent IDs. Missing/ambiguous
native bodies stop, without cross-harness fallback. Original explicit goal
authorization and epic arguments must survive routing; loading is not consent.
Descriptions, bootstrap/legacy bodies, and owned root policies are scoped too,
because Copilot can discover `.agents/skills` and read CLAUDE/AGENTS instructions.
Host instructions outside owned policy blocks remain untouched.
Only the two Copilot delegated roles inherit the actual native parent's guarded
routing when the runtime delivers the exact registered profile as the child's
controlling role. The parent checks native identity and the existing confirmed
pair/root/readiness/model/precedence/override gates before dispatch; the child
does not independently authenticate this chain or rediscover product identity.
Plain parent assertions, paths/model/tool aliases and read/quoted/pasted profiles
are not authority. Unknown parent context or unavailable/ambiguous selection
stops before dispatch; foreign or contradictory native context overrides routing
and stops without writes or fallback. This is behavioral parent/runtime trust,
not cryptographic provenance; entry/shared/policy guards are unchanged.
Owned old entry guards at those two role boundaries migrate through the existing
three-way merge to the exact delegated guard. Compatible custom bodies and
metadata/tools survive; malformed, unowned or tampered boundaries refuse before
project writes. Changed role bytes invalidate existing confirmation, never renew
consent automatically. Offline lifecycle/text tests do not qualify native child
behavior.
Guest upgrades inspect host root policies read-only: an old owned block without
the harness guard refuses before any project writes (also with `--force` or
`--dry-run`). First upgrade the policy in normal mode (`--no-guest`), or
explicitly reconcile the reported owned block, then retry guest mode. This
also applies to sticky guest reruns and inactive owned AGENTS root policies.
Already-guarded host policies and unrelated host instructions remain
byte-preserved; guest mode never rewrites or backs up these host files.

Isolation preflight covers **all retained owned root candidates**, not just
the new active destination or selected provider: `CLAUDE.md`, `CLAUDE.local.md`,
`AGENTS.md`, `AGENTS.override.md`, and `.github/copilot-instructions.md`.
Every owned block with a pristine base, even an already-guarded inactive block,
undergoes the preserving merge preflight. In normal mode, an unguarded block is
three-way merged against its existing per-file pristine block snapshot and the
current harness-scoped policy. This also scopes the inactive `AGENTS.md` when
a host adds an override after installation. Unrelated host prefixes/suffixes
(including missing final newlines) and cleanly mergeable custom owned text are
preserved; every changed policy gets a new `.bak.<timestamp>` backup.
Policy destinations, bases, backups and conflict paths are checked before
selected writes; symlinks, hardlinks and wrong types refuse. An occupied backup
name refuses when a backup is needed, preserving earlier backups and unrelated
files. Backup creation is exclusive and policy publication refuses symlink
destinations again, including under `--force` and `--dry-run`.
`--force` does not bypass this preserving isolation merge. Missing/unsafe bases,
conflicts, malformed markers, or a merged block without the guard refuse before
provider, shared, mode or exclusion writes, including dry-run. Restore the
reported pristine snapshot or explicitly reconcile the reported block without
discarding custom text. Already-scoped inactive blocks stay byte-unchanged after
preflight. Active owned policies use the same preserving merge even with
`--force`; policy conflicts leave the entire project unchanged, without `.new`
or backup artifacts. Guarded pre-snapshot policies retain adoption semantics.

`--no-guest` allows this preserving normal conversion; it does not delete
`CLAUDE.local.md` or change its personal guest wording into normal commit
instructions. That retained owned block is scoped using the guest emitter and
its own snapshot. The normal `CLAUDE.md` is added/updated separately; reconcile
the retained local policy with it explicitly if desired. The Claude guest
exclusion is removed, so the retained local file and backups may become visible.
In guest mode only the selected Claude provider's **untracked personal**
`CLAUDE.local.md` can undergo this isolation upgrade; an unsafe owned tracked
local policy refuses with normal-mode recovery guidance too. An already-scoped
tracked local block is left byte-unchanged in guest mode, including `--force`.

Shared state uses the existing flat manifest/base pattern at
`.agents/.domestique`, `snapshot_format=1`, `platform=shared`. Its exact inventory
is the two canonical skills plus `dom-goal/agents/openai.yaml`; only this state
holds their pristine bases. `guest-excludes` records the owned canonical leaves;
`mode=guest` (the contents of the optional `mode` file) keeps them and the shared
state private. No general registry or daemon is involved.

Consumers are derived read-only from valid native manifest inventories and both
role bases: Codex's `.codex/.domestique`, or
`.github/.domestique` with `platform=copilot` and the two
`.github/agents/domestique-v2-copilot-{implementer,reviewer}.agent.md` paths.
Current tests install both real projections; these offline checks are not
native execution qualification. Scoped Codex/Copilot
removal retains shared files/bases while that valid consumer remains. The last
valid consumer's removal uses existing unchanged/remove, modified/rename rules.
Shared canonical routes are visible whenever **any valid Codex or Copilot
consumer is normal**, in either mixed-mode permutation. They remain private
when all valid consumers are guest, including during a normal Claude install.
Sticky reruns, explicit selected conversions and scoped removal recompute this
rule; remaining guest providers retain their own exact asset exclusions.
Invalid surviving consumer evidence refuses instead of authorizing deletion
or exposure. Existing host canonical leaves remain
visible and survive removal under the existing ownership bookkeeping.

Copilot's five native files have their own manifest/pristine snapshots and exact
guest exclusions, never broad `.github` exclusions or duplicate canonical
`.github/skills/dom-*` entries. Normal policy is a managed block; guest bootstrap
is `/domestique-v2-copilot` with no host-policy writes. Explicit unrelated
provider operations retain Copilot visibility. Copilot setup asks both roles
and stores only the existing full-byte confirmed-pair marker in implementer
frontmatter after explicit diff consent. No model defaults are confirmations;
native inheritance removes `model`. Existing custom metadata/tools/body survive
three-way upgrades; changed bytes invalidate confirmation without reapproval.
Native role discovery descriptions must independently retain these exact
decoded prefixes (not merely a guard somewhere in the role body):

- Copilot: `Copilot only; never match in Claude, Codex or an unknown harness.`
- Codex: `Codex only; never match in another harness.`

The prefix is the non-overridable scope of the entire description; append a
space and compatible custom remainder. Validation checks this explicit format,
not natural-language intent or keywords in arbitrary custom prose. Quoted
single-line Copilot scalars and native TOML descriptions are decoded before
checking; Codex validation requires Python 3.11+ `tomllib`. Copilot preflight
checks both native roles and selected retained Codex roles, including explicit
Codex operations while Copilot is installed. It checks the normal three-way
merge candidate before provider/shared/state/exclusion writes, independently
of body validation. If that preserving merge cannot establish the boundary,
missing/changed prefixes or conflicts refuse in ordinary, guest, `--force`,
and `--dry-run` runs. Restore the reported exact prefix and explicitly reconcile
custom text against its scope before retrying. The installer does not classify
foreign prose, silently prepend guards, overwrite custom descriptions to repair
them, or refresh confirmed-pair hashes. Compatible description/model/tools/
metadata/body edits retain the normal merge lifecycle and full-byte consent
invalidation; unrelated retained Copilot files remain untouched.
Setup ends before Beads/work, requires fresh native invocation/reload and human
disposition of tracked setup edits. Missing Copilot does not prevent installation
but installation never claims readiness. Preview receipts/competing canonical
paths, unknown ownership, malformed roles, unsafe paths and conflicts refuse;
preview migration and native qualification remain separate work.

Before **any project writes**, unknown/incomplete state in the new shared
namespace refuses, even with identical bytes, dry-run, or `--force`. Existing
canonical and shared state paths must have directory ancestors and regular
file leaves (or be absent for creation). Links, directory leaves and other
obstructions refuse in both install and uninstall before any mutation;
`--force` never bypasses this safety check. Existing
Codex canonical bases are checked and used for three-way merging before they
are retired from Codex's inventory/base tree. Clean merges preserve custom
bytes and store only the new pristine shared base; conflicts refuse without
`.new`, backup, mode, policy, or other project writes. Resolve the reported
canonical path against its reported old base by hand and retry. Shared and
legacy duplicate bases refuse rather than choosing an authority. Reruns do not
churn unchanged pristine bases/manifests for preserved custom plain bodies.
Other provider file conflicts retain their existing lifecycle.

Coverage is shell lifecycle tests and assertions over actual installed text,
not native discovery, dispatch, or runtime qualification. Pre-dispatch readiness
and post-assignment observation remain distinct requirements.

**Source split checkpoint (hq-5jc.3):** public `domestique.sh`/`update.sh` now
preserve verified released v1. The reviewed preview body and inspector live in
[`domestique2.sh`](../domestique2.sh); its mutating dispatch is gated.
[`update2.sh`](../update2.sh) also refuses publication/candidate execution.
Below, preview commands and diagnostics naming the old scripts are historical
at `020c05c`/`58732cc`, **not instructions for today's public v1 files**.
See [current source status](v2-source-boundary.md) and [README](../README.md).
No runtime/project/native namespace migration is implemented by the split.

**Proposed next interface:** [V2 install/activation contract V2/1](v2-install-contract.md)
freezes hq-1t9's inert machine install, required private project activation,
whole-runtime workflow binding and named acceptance matrix. It is documentation
only: no `install-v2.sh`/installed `domestique2` interface or published V2 URL is
claimed. It does not change the current checkout `dom2` alias or the v1 channel.
Use that contract for future hq-1t9 work; the implemented preview and historical
boundaries below remain unchanged until their owning implementation tasks land.

**Current authority is the implemented private preview on `epic/hq-b3q`,
not the historical normal/guest installer.** The original Problem, sections
1–7 and their residual-risk notes below describe historical three-way merge,
normal/guest and purge behavior. They are retained for design/migration
reference, **not current setup, force, initialization or removal instructions**.
Historical PRDs likewise remain historical. Start with the
[README](../README.md) for current usage and the
[private contract](#current-private-globallocal-contract-hq-b3q-implemented-preview-with-blocked-work)
for exact formats/recovery. `main` and draft PR #11 do not contain this preview.

| Area | Current authority / status |
| --- | --- |
| Shared core and global definitions | .2/.3 implemented: immutable six-file Core API 1 releases and standalone helper; global-first, no project writes |
| Private local safety/profiles | .4/.5 implemented: physical Git root, exact ownership/exclusions, qualified roles/receipts, runtime routing separate from database eligibility |
| Beads operations | .6 qualified Darwin arm64 / observed 1.1.2 CGO private initializer and controlled dispatcher implemented; unowned/failed/unsupported cases stop. .10's always-refusing status is superseded |
| Removal | .11 global, .12 local profiles and .7 Beads retention/unchanged-only purge implemented; valid providers=none attachment retained for reuse |
| Native evidence | .8 final acceptance below separates actual production init/wrapper/cleanup from .14 historical context controls and .13 skill discovery. Direct SQL UUID queries, Claude skills and all native roles remain scoped runtime limitations, not invented passes |
| Documentation | Qualified preview, not a release-complete or all-runtimes claim; final acceptance does not replace independent review |
| Old plans | Parent-reconciled **deferred**, not completed/closed/reparented; see final disposition table |

Within the private section, checkpoint accounts record what existed **at that
checkpoint**. Their older “future” statements are superseded by this table and
later implemented checkpoints, not competing active instructions. Historical proposed
Beads formats are not authority for the current parsers; use .6/.7's implemented
formats and lifecycle. Only .6's exact pinned engine qualification is claimed, not general
backend certification or end-to-end native workflow acceptance. .14's database
operations remain distinct historical disposable-test evidence.

## Historical problem (normal/guest installer)

`install_plain` today: missing → write; differs → backup `.bak.<ts>` + overwrite
(unless `--force`); identical → skip. `install_claude_md` today: managed-block
replace between markers, always backs up, refuses half-marked files, idempotent.

Both "differs → overwrite" paths silently discard a user's local edits (e.g.
MCP tools hand-added to an agent's frontmatter) on the next install/upgrade.
We want a 3-way merge (base = what we last installed, ours = on-disk with the
user's edits, theirs = what the current `domestique.sh` would emit now) so
local edits survive while upstream changes still apply.

Because the Claude and Codex emitters live inside the script itself, an upgraded `domestique.sh`
cannot reconstruct what an *older* version of itself emitted. The merge base
must therefore be snapshotted to disk at install time, not recomputed.

**Correctness invariant (the crux of this whole design): the snapshot base
advances only on a clean apply, never on conflict.** Clean merge/write →
overwrite the live file AND advance the snapshot to the freshly-emitted
`theirs`. Conflict → live file is left untouched AND the snapshot stays at
its old value. Advancing the snapshot on a conflicted file would make the
conflict un-re-mergeable on the next run (the next run's "base" would no
longer reflect what the user actually last saw).

Correctness of the merge comes entirely from the byte-for-byte content of the
snapshotted base files, not from `DOMESTIQUE_VERSION`. The manifest's
version/ref fields are diagnostic only; they are never a merge base or an
ownership decision.

---

## 1. Provider snapshots, manifests, and selection

State is provider-specific: `.claude/.domestique/` for Claude and
`.codex/.domestique/` for Codex. A Codex-only install therefore creates no
`.claude/` bookkeeping. Each installed provider records the selected
platform set so a later selector-less run can recover it without inspecting
installed binaries or arbitrary project files. A provider state tree without
a platform record implies that provider.

```
.claude/.domestique/
  mode                                   # sticky guest-mode marker (see §6); absent on normal installs
  platforms                              # persisted provider union
  beads-owned                            # optional shared-workspace ownership marker
  manifest                              # small key:value file, shell-parseable
  base/
    CLAUDE.md.block                     # last-installed managed-block BODY (no markers) — normal-mode installs
    CLAUDE.local.md.block               # same, but for the guest-mode destination — see §6
    .claude/agents/implementer.md
    .claude/agents/reviewer.md
    .claude/commands/decompose.md
    .claude/commands/goal.md

.codex/.domestique/
  mode                                   # guest marker; absent in normal mode
  platforms                              # persisted union: claude, codex, or both
  guest-excludes                         # exact Codex leaves that guest mode may hide
  beads-owned                            # optional shared-workspace ownership marker
  manifest
  base/
    AGENTS.md.block                      # normal mode, when AGENTS.md is active
    AGENTS.override.md.block             # normal mode, when the override is active
    .codex/agents/implementer.toml
    .codex/agents/reviewer.toml
    .agents/skills/domestique/SKILL.md
    .agents/skills/domestique-decompose/SKILL.md
    .agents/skills/domestique-goal/SKILL.md
    .agents/skills/domestique-goal/agents/openai.yaml
```

The `base/` tree mirrors each managed file's path under the target repo
verbatim (e.g. `.claude/agents/implementer.md` is snapshotted at
`base/.claude/agents/implementer.md`), one pristine copy per managed file,
**except** for the policy destination (`CLAUDE.md`, or `CLAUDE.local.md`
under `--guest` — see §6), where we snapshot only the managed block's *body*
(the content between the markers, not the markers themselves and not the
surrounding user content) — see §3. Note `base/` holds up to two separate
policy-block snapshots (`CLAUDE.md.block` and `CLAUDE.local.md.block`),
keyed by destination filename, because a target directory can see both a
plain install and a `--guest` install over its lifetime (see §6) — each
mode's merge base is independent of the other's.

The same path-mirroring rule applies to both providers. Policy destinations
are snapshotted as block bodies; plain agent, command, skill, and skill
metadata files are snapshotted verbatim. Codex guest mode has no root policy
snapshot because it never reads or writes either AGENTS file.

**Manifest format:** flat `key=value` lines, one per line, no nesting — avoids
a `jq`/`yq` dependency in a `bash + git + coreutils` script.

```
snapshot_format=1
domestique_version=<DOMESTIQUE_VERSION, e.g. 0.1.0>
installed_ref=<git describe/short-sha of domestique.sh's own repo, or "unknown">
installed_at=<ISO8601 timestamp>
script_sha256=<sha256 of domestique.sh, or "unavailable">
platform=claude
files=.claude/agents/implementer.md,.claude/agents/reviewer.md,.claude/commands/decompose.md,.claude/commands/goal.md,CLAUDE.md
```

A Codex manifest uses `platform=codex` and lists the actual TOML, skill,
metadata, and active policy destinations. Manifests are inventories, not
assumptions: mixed policy history can leave managed blocks in more than one
possible policy destination, and uninstall must inspect them all.

For Claude, `files=` is **not** simply "this run's policy destination plus
the four fixed `.claude/` files" — it is computed from actual on-disk state at manifest-write
time (`managed_files_list`), because a target directory can be in a mixed
state: a prior plain install left a managed block in `CLAUDE.md`, and a later
`--guest` run (or vice versa) writes into `CLAUDE.local.md` without touching
`CLAUDE.md`. Both policy files are still domestique-managed in that
directory, so `files=` lists whichever of `CLAUDE.md` / `CLAUDE.local.md`
actually carry the managed-block markers on disk — this run's destination is
always included (it was just written), plus the *other* policy file if it
independently carries the markers too. In a mixed-mode directory, `files=`
can therefore list **both** `CLAUDE.md,CLAUDE.local.md`, not just one. Codex
uses the same inventory rule across its two possible normal policy
destinations and fixed TOML/skill leaves.

**When it's written:**
- **At install** (first time, no provider state present): after each
  file is successfully written (create or clean overwrite), write/refresh its
  base snapshot and update the manifest.
- **After each successful apply on upgrade**: same rule — a file's base
  snapshot advances *only* when that file's live copy was just brought to
  exactly the freshly-emitted content (clean install, clean merge, or
  `--force` overwrite). A conflicted file's base snapshot is left untouched.

**Gitignore:** design intent, not implemented behavior — a case could be made
for the installer to append provider state to the target repo's
`.gitignore` if one exists (or note it in the summary if none exists). As
shipped, the installer does not print any such recommendation or touch
`.gitignore` at all (see the Open Questions entry below); users who want it
ignored add it by hand. Rationale for wanting this: it is
per-working-copy merge state, not a shareable artifact, and different clones
of the same repo could each have their own locally-edited files with
independently-advancing bases. Tension: a fresh clone (or a clone that never
ran domestique with this feature) has no provider state at all, so on
that first run it ADOPTS — seeds the base from the pristine freshly-emitted
content (not the current/edited file) and leaves the live file unchanged
(see §2/§3) — rather than overwriting, then merges upstream in on the
*next* run.

---

## 2. Plain-file merge (`install_plain`)

**Tool: `git merge-file`.** Chosen over `diff3 -m` because it (a) works
without the target being a git repo — it's a plumbing command, not
repo-dependent, (b) supports `-p`/`--stdout` so we don't have to mutate a
working file in place before deciding whether to accept the result, and (c)
gives unambiguous exit-code semantics we can branch on (see below). `diff3`'s
output format is also less conventional for tooling to parse/store as a
conflict artifact than git's standard `<<<<<<< / ======= / >>>>>>>` markers,
which many editors and future tooling already understand.

**Invocation:**

```
git merge-file -p --diff3 \
  -L "yours (local edits)" -L "base (last installed)" -L "upstream (new domestique)" \
  <ours> <base> <theirs>   > <staged-result>
rc=$?
```

- `ours`   = current on-disk file.
- `base`   = `<provider-state>/base/<relpath>` (the pristine snapshot).
- `theirs` = freshly emitted content from the current script's `emit_*` function.

**Exit code handling — conflict and error are distinct buckets, not one:**
- `rc == 0`: clean merge. Write `<staged-result>` over the live file. Advance
  the base snapshot for this file to `theirs`. Report as **merged** (or
  **updated**, if `ours` was already identical to `base`, i.e. no local
  edits existed — still counts as a normal upstream update).
- `rc` in `1..127`: conflict (rc = number of conflicted hunks per git's
  convention). Do **not** touch the live file. Write the conflicted result
  (containing `<<<<<<<`/`|||||||`/`=======`/`>>>>>>>` markers) to
  `<dest>.new` alongside the live file. Also back up the live file to
  `<dest>.bak.<ts>` (so the pre-conflict state is preserved even though it
  wasn't overwritten — this matches "always have a timestamped safety copy"
  and gives the user a clean diff target). Print a warning naming the file
  and the `.new` artifact. Do **not** advance the base snapshot. Set the
  script's overall exit code to non-zero (see §4).
- `rc >= 128` (or any unexpected/non-numeric failure): treat as a hard error
  for that file — same non-destructive handling as conflict (leave `ours`
  untouched, no snapshot advance) but reported distinctly as **error**, not
  **conflict**, since it likely indicates a bad snapshot or environment
  problem worth surfacing differently.

**No snapshot present for this file (legacy install, or file predates this
feature) — ADOPT, don't clobber:**
- **Identical file:** no change needed; seed the base snapshot from the
  current (== freshly emitted) content so future runs have a base. Same as
  today.
- **Differs:** do **not** back up or overwrite. Seed the base snapshot from
  the **pristine, freshly-emitted content** (the same bytes `install_plain`
  would write if the file were missing) — **not** the current on-disk
  content — and leave the live file byte-unchanged. Report it as **adopted**
  (`Adopted <dest> (local edits preserved; re-run to merge upstream)`).
  Rationale: base must be the *vanilla* baseline. With base = pristine emit,
  the *next* run's 3-way merge — `ours` = current file (with the local
  edit, plus any further edits made since), `base` = the pristine snapshot
  just seeded, `theirs` = the (possibly newer) emit — sees the edit as
  `ours != base` (preserved) and any real upstream change as
  `theirs != base` (applied), with no data loss on the very first upgrade
  after adopting this feature. **Seeding base from the current/edited
  content instead is a bug, not a variant**: it makes `ours == base`
  whenever no *further* edit is made since adoption, so `git merge-file`
  takes `theirs` wholesale on the next run and silently drops the very edit
  this design exists to protect — confirmed empirically while implementing
  this. `--force` still bypasses adopt and overwrites verbatim, as usual.
- **Missing file:** unchanged from the general missing-file case — create +
  snapshot.

**File deleted by the user:** treated as "missing" exactly as today —
`install_plain`'s missing-file branch fires (write theirs fresh), and the
base snapshot is (re)written. No merge is attempted since there is no `ours`
to merge.

**Identical case:** if `ours` == `base` == `theirs` (nothing changed on
either side), or `ours` == `theirs` (independently converged), skip as
today — no write, no backup, snapshot may still be refreshed defensively
though it's already correct.

---

## 3. Managed policy-block merge

The 3-way merge applies **only to the block body** (the content strictly
between `MARKER_BEGIN` and `MARKER_END`), never to the surrounding user
content, which is preserved byte-for-byte exactly as today.

Claude normal and guest policy destinations remain `CLAUDE.md` and
`CLAUDE.local.md`. Codex normal mode manages the active root instruction
file: an existing `AGENTS.override.md`, otherwise `AGENTS.md`. Codex guest
mode bypasses this function entirely and leaves both files byte-untouched.
The algorithm below uses `CLAUDE.md` as the original concrete example; the
destination and provider snapshot root are parameters.

**Extraction:** given the on-disk `CLAUDE.md`, extract the current block body
as `ours-block` (using the same awk logic already used to *replace* the
block, adapted to *capture* it instead). `base-block` is
`.claude/.domestique/base/CLAUDE.md.block` from the last snapshot.
`theirs-block` is the current `emit_policy` output.

**Merge:** `git merge-file -p --diff3 <ours-block> <base-block> <theirs-block>`
→ same exit-code buckets as §2 (0 = clean, 1-127 = conflict, ≥128 = error).

**Outcomes:**
- **Clean:** splice the merged block body back between fresh
  `MARKER_BEGIN`/`MARKER_END` markers into the file, preserving everything
  outside the markers exactly as `install_claude_md` does today (same awk
  splice, just with the merged body instead of the raw `emit_policy` output).
  Always back up `CLAUDE.md` first, as today. Advance
  `CLAUDE.md.block` snapshot to `theirs-block`. Idempotency guard (skip if
  result == current file) still applies before deciding to write/backup.
- **Conflict:** leave `CLAUDE.md` untouched (still back it up regardless,
  matching "CLAUDE.md is ALWAYS backed up before modification" — here
  "modification" is attempted, so back up defensively even though the live
  file ends up unchanged, so the user has a timestamped reference point).
  Write the full file with the conflicted block spliced in (markers +
  conflict-marker'd body + preserved surrounding content) to
  `CLAUDE.md.new`. Warn, don't advance the snapshot, set non-zero exit.
- **No markers yet (Case C, first-time install of the block into an existing
  file) or no file at all (Case A):** unchanged from today — no merge is
  possible or needed since there's no prior `ours-block`; write/append as
  today, then write the initial `CLAUDE.md.block` snapshot.
- **Half-marker file:** unchanged — still refuse and exit 1 before any
  merge logic runs.
- **No snapshot present (legacy):** same ADOPT behavior as §2 — if the block
  body is identical to the fresh emit, just seed `CLAUDE.md.block` (no
  change). If it differs, do **not** back up or overwrite; seed
  `CLAUDE.md.block` from the **pristine `emit_policy` output** (not the
  current/edited on-disk block body), leave `CLAUDE.md` byte-unchanged, and
  report **adopted**. The next run 3-way merges the block body against that
  pristine base, applying upstream while preserving the local edit — seeding
  from the edited block body instead would make `ours == base` and cause the
  next merge to drop the edit.

---

## 4. CLI / UX

- **`--platform claude|codex|both`:** an explicit install adds the selected
  projection(s) to the persisted set. A new selector-less install defaults
  to Claude; later selector-less runs use persisted state. Never infer the
  user's desired client from executables or files. Print selected platforms,
  guest status, and the policy destination (or `skills-only`) before writes.
- **Codex invocation:** normal and guest installs expose namespaced
  `$domestique`, `$domestique-decompose`, and `$domestique-goal` repo skills.
  Goal metadata disables implicit invocation; only an explicit goal skill is
  unattended authorization. Codex custom agents are project TOML, not
  deprecated user-global custom prompts.
- **Codex models and review isolation:** the implementer TOML pins
  `gpt-5.6-terra` at medium effort; the reviewer pins `gpt-5.6` at high
  effort. An unavailable pin is reported with the role and model; recovery is
  to edit the TOML or remove both model keys to inherit the parent, never a
  silent substitution. The reviewer inherits workspace-write so generic test
  suites may create caches/build output, but its instructions forbid edits.
  The orchestrator fingerprints tracked diff, staged diff, and bead state
  immediately before and after review. Any delta is FAIL/stop; ignored test
  artifacts are allowed and new visible untracked artifacts are reported.
- **Normal `--with-beads`:** if needed, initialize with
  `bd init --skip-agents --skip-hooks --non-interactive`, then run `bd setup claude`,
  `bd setup codex`, or both recipes according to the selected platforms.
  Missing `bd`, or a version without both safe skip flags, warns and skips.
  Guest behavior is stricter in §6.

- **`--dry-run`:** performs the merge computation (runs `git merge-file`) but
  writes nothing — no live file changes, no `.new`/`.bak` artifacts, no
  snapshot writes. Reports what *would* happen: `[dry-run] merge <dest>
  (clean)` or `[dry-run] merge <dest> (would conflict — see N hunks)`.
- **`--force`:** redefined to mean **discard local edits, take upstream
  verbatim, no merge attempted** — i.e. today's exact `--force` behavior
  (overwrite, no backup) is preserved unchanged, just now explicitly
  documented as bypassing the merge path entirely. This is the escape hatch
  for "I don't want my edits, just give me latest." (Alternative reading —
  "force a merge attempt even in some other edge case" — is rejected; there's
  no scenario in this design where merging is blocked but forceable. See Open
  Questions if this reading turns out to be needed later.) `--force` still
  advances the snapshot (theirs was just written verbatim).
- **Summary sections:** extend today's `Created / Updated / Backed up /
  Skipped` groups with two more:
  - `Merged` — clean 3-way merges (local edits preserved + upstream applied).
  - `Conflicted` — files where a `.new` artifact was written; live file left
    untouched. Each line names both the live file and its `.new` sibling.
  - `Adopted` — legacy (no-snapshot) install where the on-disk file differed
    from the fresh emit: base snapshot seeded from the pristine emit, live
    file left unchanged, local edits preserved; re-run to merge upstream.
  - (`Error` cases fold into `Conflicted` in the printed summary but are
    logged distinctly to stderr with the underlying reason.)
- **Exit codes** (matching the script's *existing* mapping, not inventing a
  new one — confirmed against the current script: unknown/unexpected CLI
  args already exit `2`; missing target dir and half-marker refusal already
  exit `1`):
  - `0`: everything applied cleanly (creates, updates, clean merges, skips).
  - `1`: unchanged from today — operational refusals: missing target dir,
    half-marker policy file.
  - `2`: unchanged from today — CLI misuse: unknown option, unexpected
    argument.
  - `3` (new): one or more files ended in **conflict** or **error** during
    merge. All non-conflicted files still get applied normally; this is a
    partial-success code, not an abort — the script does not stop processing
    other files when one conflicts. The summary always lists exactly which
    files conflicted so the exit code alone is enough for a CI/script caller
    to distinguish "bad invocation" (2) from "ran, but a file needs human
    attention" (3).

---

## 5. Periodic updater interaction

The "fetch latest `domestique.sh` from GitHub and re-run" updater is a thin
wrapper around this same mechanism and needs no separate merge logic: it
downloads the new script, runs it against the target directory exactly as a
manual upgrade would, and the existing provider snapshot (written by
whichever run last succeeded — manual or automated) is the base
for the 3-way merge regardless of how the new script arrived. The only thing
the updater adds on top is deciding *when* to trigger a run (e.g. on a
schedule, or on detecting a newer upstream ref) and where to surface
conflicts for human attention (e.g. failing a CI job or opening an issue) —
it should treat exit code `3` (conflicts) as "applied partially, needs a
human," not as a hard failure of the updater itself, and exit codes `1`/`2`
as script/invocation bugs worth escalating differently.

`update.sh` forwards an explicit `--platform`. Without one, it lets the
installer resolve the persisted platform set. It also forwards guest
conversion flags; platform and guest state are orthogonal, and neither is
re-detected heuristically.

---

## 6. Guest mode (`--guest`)

**Purpose.** Install into a repo you don't own for personal use without
changing tracked host files or adding domestique noise to `git status`.

**Claude policy destination.** Under Claude `--guest`, `POLICY_DEST` is `CLAUDE.local.md`
instead of `CLAUDE.md`; every place in §1–§3 that reads/writes "the policy
file" or "`CLAUDE.md`" targets whatever `POLICY_DEST` resolves to for this
run. This is why `base/` can hold both `CLAUDE.md.block` and
`CLAUDE.local.md.block` (see §1) — each mode's merge base is snapshotted
under its own destination filename, so a `--guest` run never reads or
advances the plain run's merge base, and vice versa. If a tracked `CLAUDE.md`
already carries a non-guest domestique install, the guest run warns and
leaves `CLAUDE.md` untouched entirely (never read, merged, or backed up).

**Guest policy content is a variant, not a different file.** `emit_policy`
takes a `mode` argument (`normal` or `guest`); the shared prose is identical,
but the guest variant's final bullet replaces the "export and commit
`.beads/`" session-end guidance with guidance to never commit `.beads/`,
`CLAUDE.local.md`, or `.claude/` to the host repo, and to never modify
`.gitignore` or any other tracked file on the repo's behalf. `emit_goal`'s
body is mode-invariant but carries a self-scoping caveat noting that in guest
installs, unattended `/goal` commits stay on local branches that are never
pushed — doubling down on the same never-touch-the-host-repo guarantee.
Because the merge/snapshot machinery in §2/§3 operates on whatever
`emit_policy "$mode"` currently emits, upgrading a guest install re-merges
against the guest variant's snapshot, not the normal variant's — the two
never cross-contaminate.

**Codex policy is skills-only.** Codex has no additive equivalent of
`CLAUDE.local.md`; at one directory level `AGENTS.override.md` shadows rather
than layers over `AGENTS.md`. A Codex guest install therefore never creates,
reads, merges, backs up, or modifies either root AGENTS file. It installs
project custom-agent TOML and the three namespaced skills only. The user runs
`$domestique` once in each new session. Every operational skill repeats the
invariants it needs, the base skill can implicitly match ordinary dispatch
and landing prompts, and the goal skill remains explicit-only. This provides
the workflow without claiming automatic startup-policy parity.

**Exclude-block management (`install_git_exclude`).** Guest mode replaces one
managed `#`-comment block in `<git-common-dir>/info/exclude`. Claude retains
the legacy `CLAUDE.local.md` and broad `.claude/` entries, which may hide
pre-existing untracked content below `.claude/`.
Codex entries name the two agent TOMLs, three skill leaves and goal metadata,
and `.codex/.domestique`. No broad conflict/backup suffix patterns are added,
so unrelated host artifacts remain visible. Shared `.beads/` is included
when domestique created it; that shared ownership marker is propagated to
guest providers added later so scoped uninstall cannot expose it. Never
exclude whole `.agents/` or `.codex/`
trees. Codex never newly hides an exact managed path that was already visibly
untracked before installation. A tracked owned-path collision is reported because excludes
cannot hide it. The common directory is resolved with `git rev-parse` so the
block works in worktrees. Non-Git targets warn and skip exclusion. Content
outside the managed block is always preserved.

**Sticky mode marker.** Each guest provider writes `mode=guest` in its own
state tree. Selector-less reruns take the union of persisted providers and
retain their guest mode, including through `update.sh`. `--no-guest`
converts deliberately: Claude prints manual guidance for local-policy
customizations; Codex begins managing the active AGENTS destination. Passing
`--guest` and `--no-guest` is rejected before file I/O. Conflicting provider
state is resolved conservatively by union so a managed projection is never
silently dropped.

**Beads in guest mode.** If requested and `.beads/` is absent, run
`bd init --stealth --skip-agents --skip-hooks --non-interactive`. Never run a provider `bd
setup` recipe in guest mode: those recipes may write host instructions,
hooks, or tracked configuration. If the installed `bd` lacks the safe flags,
skip initialization with a warning. This keeps the worktree clean after a
guest `--with-beads` install; uninstall still preserves
`.beads/` unless `--purge-beads` is explicit.

---

## 7. Uninstall (`--uninstall`, `--purge-beads`)

**Scope.** Bare `--uninstall` scans and removes all domestique-managed
provider projections. `--uninstall --platform claude|codex|both` is scoped to the
selected projection, removes it from persisted platform state, and rebuilds
the shared guest-exclude union for providers that remain. Claude inventory is
the existing four `.claude` projection files and policy destinations. Codex
inventory is the two agent TOMLs, three skill leaves plus goal metadata, and
managed blocks in either possible normal AGENTS destination. Each provider's
state tree is owned separately. `.beads/` remains unless `--purge-beads` is
explicit.

Only known leaves are removed. `.claude/agents`, `.claude/commands`,
`.codex/agents`, `.agents/skills`, and their parents are pruned only when
empty; an entire user-owned `.codex/` or `.agents/` tree is never a deletion
target. Install-only flags remain invalid with uninstall, while `--platform`
is valid for scoped removal.

**Snapshot-compare safety (mirrors §2's ADOPT reasoning in reverse).** Each
provider must first have ownership evidence: its state tree or a managed
policy marker. Fixed inventory paths alone are never treated as proof, so a
never-installed matching host file is untouched. Each managed plain file is compared against its provider's recorded base
snapshot (falling back to the pristine freshly-emitted content if no
snapshot exists — e.g. a legacy install that predates the snapshot feature).
An exact match means the file was never modified after install, so it's
deleted outright with no backup. A mismatch means the user edited it: it's
kept, renamed to `<file>.uninstalled.<timestamp>`, unless `--force` is
passed, in which case it's removed anyway (noted as "modified, --force" in
the summary). The same compare-then-decide logic governs the policy files'
managed blocks: the on-disk block body is diffed against
the matching policy-block snapshot (or the pristine provider policy
output for the matching mode, if no snapshot exists); an unmodified block is
stripped with no backup, and the file is deleted entirely if stripping
leaves nothing but whitespace behind, while a modified block is backed up to
`<file>.bak.<timestamp>` before stripping.

**Marker-sanity refusals.** Before stripping a policy file's managed block,
`--uninstall` runs the same `markers_sane` check §3 uses for install: a
result other than `none`/`ok` (i.e. `half`, `dup_begin`, `dup_end`, or
`inverted` — a half-marked file, duplicate BEGIN/END markers, or END
appearing before BEGIN) means the naive strip would act on the wrong span,
so that file is left byte-untouched, reported under `Conflicted`, and the
overall run exits `3` — but processing continues for every other file
(unlike install's half-marker refusal, which aborts the whole run; uninstall
treats a corrupt marker in one file as a partial failure, not a hard stop,
since other installed files are still safe to remove).

**No-op behavior.** If nothing domestique installed is found in the target
(`anything_done` stays `0` across every step), `--uninstall` prints a note
and exits `0` — it's a clean no-op, not an error.

**`--dry-run`.** Performs every comparison and decision above but writes,
deletes, and renames nothing — it prints exactly what would happen (create/
remove/keep/backup) for every step, matching the real run's summary
structure (`Removed` / `Kept (modified)` / `Backed up` / `Skipped` /
`Conflicted`).

**Round-trip guarantee.** For the common case — a `--guest` install into an
otherwise-clean host repo, immediately followed by `--uninstall` — every
installed file is deleted outright (nothing was ever modified), the exclude
block is fully stripped or reduced to the remaining provider union, provider
state is removed, and empty owned parents are pruned, leaving byte-for-byte
clean `git status`. This applies to Claude, Codex, both, and safe guest
installs without Beads. For `--with-beads`, pass `--purge-beads` on uninstall
to remove the deliberately preserved `.beads/` workspace too. Guest never
runs `bd setup`. A scoped uninstall preserves the other projection and only
its exact exclude entries.

---

## Historical residual risks and resolved decisions

- `--force` remains discard-local-and-take-upstream; there is no separate
  force-merge mode.
- Domestique never edits `.gitignore`. Codex guest uses precise local leaves;
  Claude guest retains its legacy `.claude/` compatibility entry. Normal-mode
  provider state follows the project's normal tracking policy.
- Snapshot corruption is not authenticated. A missing base falls back to
  ADOPT; a corrupt base may produce a merge conflict or bad merge and remains
  a known limitation.
- Concurrent installers can race on provider state. No locking is included.
- First adoption seeds a missing base from the pristine emitter and leaves a
  differing live file untouched. Seeding from the edited live file is
  forbidden because it makes `ours == base` and can drop the local edit on
  the next merge.
- Codex agent schemas and model availability can evolve. Locally edited TOML
  is merge-preserved, and unavailable-model recovery is explicit rather than
  silently substituting a role or model.

---

## Current private global/local contract (hq-b3q; implemented preview with blocked work)

**Status and boundary.** The private-only replacement is implemented in this
checkout for core/global/local profile lifecycle, with the blocked/open
boundaries in the authority table above. It builds on `58f4d29` (including
reviewed Copilot payload commit `2896937`). `main` and draft PR #11 do not
contain these changes; neither is merged/pushed or rewritten here. “Private”
is the sole ownership mode: global and local are distribution scopes, not
normal versus guest modes. The old dual-mode prescriptions are retired.

**Historical hq-b3q.3 CLI checkpoint (superseded by .5/.10/.11 below):**
only explicit `--global` install/update was
implemented from this contract. Legacy bare/positional installs and the legacy
updater remain project operations, unchanged; they are **not yet** the private
local operation specified below. `--local`, state-only, migration, and global
uninstall remain future work and are refused. Global accepts all seven sets
below, including the two composite spellings; legacy selection is unchanged.
The updater validates global scope/options before fetching, forwards no `.`
target, and does not apply after a failed global preview.

#### hq-b3q.6 qualified private initialization and controlled operations (current)

This implementation supersedes the always-refusing **production** status in
.10 and the later historical checkpoints below. It does not change .14's
historical experiment results, certify other native versions, or complete .8
role/model/MCP execution. All code remains embedded in `domestique.sh`;
`bin/resolve-core` embeds its own bridge and imports no checkout/test files.
Core API 1 and the six-file immutable role release inventory remain intact.
The helper capability marker is now `beads_guard_api=2`.

**Qualification and dependencies.** Only observed Darwin arm64 / Beads 1.1.2
CGO embedded is enabled, with exact binary SHA-256
`cb77069648d90fef8876f775d647997beb7bb0ab5461509394c29d5bf14b7c42`.
The source pin remains `gastownhall/beads@20e493e569c922d1253bdeff068c5e56c94957fb`.
Installed Python 3.9+ stdlib and `/usr/bin/sandbox-exec` are required for Beads
only; ordinary core/profile loads have no Python dependency. Apple's Python/Git
setup launchers are not an installer fallback. No package installation occurs.
Python uses `-I -S -B` to disable site startup hooks and bytecode-cache writes.
Python 3.9+ is necessary but not sufficient: working
`os.waitid(P_PID, WEXITED|WNOHANG|WNOWAIT)`, nonblocking POSIX pipes and sessions
are required, with default SIGCHLD and single-threaded exclusive child ownership.
Darwin additionally requires stdlib ctypes and working `proc_listpids` in the
system `/usr/lib/libproc.dylib`.
Missing Darwin interpreter/kernel support refuses before child creation and
qualification/claim/init writes; ordinary non-Beads core loading is unchanged.
The embedded `execute_child` retains the direct session leader until its last
group signal and only then reaps. Fair selector reads retain UTF-8 boundaries
and universal newlines, with 60 seconds execution plus one shared five-second
cleanup deadline. Synthetic integration reuses the extracted primitive with
600 seconds plus five; there is no production import from tests or host-wide
process-table polling. No post-reap group fallback or detached-descendant
containment is claimed. A surviving native leader retains inherited FD8.
Timeout/cleanup failures retain private output/status while public diagnostics
omit argv and payload. Leader completion alone cannot excuse EPERM. The sole
exception is a completed, exclusively unreaped leader revalidated on both sides
of one exact-group PID enumeration that returns empty or only that leader.
Any other PID (including another zombie), full/truncated buffer, malformed length
or PID, nonzero errno/error, unsupported API, ownership change/loss or exhausted
original five-second cleanup budget keeps explicit cleanup failure. A still-live
leader never uses this exception. No signal follows reap.
`test/beads-execution-tests.py` now has 27 synthetic/harmless tests, requiring
actual Darwin natural zero/nonzero success, UTF-8/newline and dual-pipe output,
own-group cleanup and FD8 inheritance; native qualification success is **not**
established for this changed bridge.

**Narrow Darwin API evidence.** Installed SDK `libproc.h` declares
`int proc_listpids(uint32_t, uint32_t, void *, int)`; `sys/proc_info.h` defines
`PROC_PGRP_ONLY` as 2. The buffer contains int-sized PIDs; the result is **bytes**,
not a PID count. Apple's released
[`xnu-12377.1.9` kernel implementation](https://github.com/apple-oss-distributions/xnu/blob/xnu-12377.1.9/bsd/kern/proc_info.c#L359-L485)
holds `proc_list_lock` throughout both `allproc` and `zombproc`, filtering
`p_pgrpid` directly. There is no later per-PID state lookup or exit-state elision.
[`kern_proc.c`](https://github.com/apple-oss-distributions/xnu/blob/xnu-12377.1.9/bsd/kern/kern_proc.c)
protects group changes and process-list insertion with that lock;
[`kern_exit.c`](https://github.com/apple-oss-distributions/xnu/blob/xnu-12377.1.9/bsd/kern/kern_exit.c)
moves processes between the two lists under that lock. Exec shadows are duplicate
proc objects, not omitted independent PIDs:
[`kern_exec.c`](https://github.com/apple-oss-distributions/xnu/blob/xnu-12377.1.9/bsd/kern/kern_exec.c#L5241-L5261)
transfers the shadow flag and PID identity under the same lock.
The [libproc wrapper](https://github.com/apple-oss-distributions/xnu/blob/xnu-12377.1.9/libsyscall/wrappers/libproc/libproc.c#L45-L59)
maps syscall -1 to zero **with errno**. ctypes uses `use_errno=True`, clears errno
immediately before the call and captures it immediately afterward; only a zero
result with zero errno is empty success. The fixed non-NULL two-int buffer never
uses the NULL sizing mode, which is a host-count estimate rather than membership.
Full buffers refuse, without retries, growth, per-member state reads or `ps`.
A cached runtime capability check binds this one symbol and verifies the
zero-size/non-NULL call's expected zero/ENOMEM before mutation or child creation;
that probe fails before process enumeration. Harmless disposable retained-child
tests verify actual own-group pair/full, running-singleton and completed
membership behavior on Darwin. This proves no live members at the locked
observation, not future/detached containment or a solution to `ps` latency.

This production change invalidates prior whole-file source fingerprints and
requires independent reassessment of initializer, bridge, synthetic integration,
native production/cleanup and runner coverage; it does not complete .8.
The exact observed user-owned Homebrew Cellar parent mode 0775 is accepted for
the digest-pinned executable; other unsafe writable ancestors refuse. This
retains the existing no-hostile-writer/concurrency guarantee boundary.
Fresh qualification uses only private temporary staging, OS positive-write and
outside-read/write/network denial probes, and native help/version. It records
canonical executable and Git paths/digests; later invocations require those
same bytes, not PATH replacement or automatic requalification.

**CLI and publication.** Explicit `--local TARGET --with-beads --state-only`
creates no providers on a fresh attachment. Existing provider records,
receipts and edited profiles remain wholly untouched. Explicit combined
Beads/profile requests preflight target, core/helper, ownership, all selected
profiles, legacy authority and all actual linked-worktree exclusion collisions
before writes. Existing host `.beads` refuses, including empty or byte-identical
directories; no native query is used to decide adoption. An existing Git info
directory is required for Beads publication. Invalid flag combinations and
global/non-uninstall purge refuse before writes; the updater rejects all cleanup
requests before fetch, forwards valid update requests and does
not apply any failed preview. Dry-run has no project/global/index/exclude writes
and no native DB calls.
State-only and unselected providers in combined requests preserve valid original
native-record/receipt ordering, creation hashes and baseline hashes. The exact
projected manifest and generated-or-retained receipt set is validated before
initialization; only legitimately refreshed providers get generated ordering.
State-only
uses legacy **check**, not migration: it refuses active legacy authority
without deleting even otherwise-eligible legacy profiles. Colon-bearing Beads
roots (Git ceiling delimiter) and Git executable directories (PATH delimiter)
refuse rather than misrouting discovery.

After preflight, the controller exclusively claims any new private state root
and the empty final `.beads` directory (no `exist_ok`). Process-local device/inode
proof plus empty-directory checks distinguish these reservations from adoption.
It revalidates every actual shared worktree and exact proposed exclusion, then
protects the owned private tree and only the known native artifact paths/subtree,
before writing any journals/context or executing native init. New selected
provider files are not prematurely hidden. Existing host `.beads`, late claim
collisions and newly populated reservations refuse without covering foreign
paths. No invalid placeholder metadata is precreated.

The protected `published` journal records the actual checked exclusion path/hash
and completed directory reservations. `beads-attempt` is failed-by-default:
`format=1`, `beads_status=failed`, `attempt=<hex>`,
`beads_reservation=.beads:<device>:<inode>`. Neither reservation is successful
native creation, readiness or future purge authority. The bridge rechecks the
exact empty DB reservation, creates the private context, initializes directly at the final
DB path, verifies metadata/schema/physical engine, then queries ping and where.
Only after those proofs are successful is the full ready suffix emitted and
published in the local manifest. Zero-exit bad metadata, partial init or bad
readiness leaves nonzero failed attempt/journal evidence, no ready manifest or
successful `beads_created` records. No DB copies, rollback, automatic purge,
reinit or post-hoc directory ownership inference occurs. Partial known native
artifacts and attempt/context/journals remain protected even on init/readiness
failure. Unknown unallowlisted native artifacts gain neither ownership nor new
exclusions; manual reconciliation and avoiding commits remain necessary. An
interruption before protection may leave only empty claimed directories; an
interrupted exclusion write requires checking the exact actual exclusion bytes.
Stop writers; never infer successful creation from a protective reservation.

**Process boundary.** Native CWD is exactly
`<physical-project>/.domestique-private/beads-context/run`, Git ceiling is its
parent, and absolute `BEADS_DIR` is `<physical-project>/.beads`. HOME, XDG
config/state/cache, tmp and empty Git hooks/templates are context-owned.
Both Git config selectors point to a generated empty `beads-context/gitconfig`,
never to real HOME configuration.
The allowlist environment and pinned init flags reuse .14's source-verified
semantics (including explicit empty remote and `no-git-ops: true`).
There are no inherited tokens, Git selectors, alternate DB/config selectors,
proxies, OTel endpoints, real HOME config or credentials. Native `--sandbox`
is auto-push control only. Actual default-deny OS policy permits runtime reads
and DB/context reads/writes, no network or Keychain/mach IPC, no external Dolt,
and only the dedicated export directory when export was requested. Native has
no write grant to installer journals, manifests, routing, index, host policies,
global installation or common excludes. Processes/groups are bounded and
reaped, including after timeout. Native's mode-0777 `.dolt` JSON selectors are
accepted only inside owned mode-0700 enclosing private trees, with their exact
safe schemas and immutable fingerprints checked; no permissions are repaired.

**Bounded local format 1 extension.** The original six headers and native
created/baseline pairs stay ordered. Optional Beads records follow them, in
this exact order (no unknown-key escape):

```
beads_path=.beads
beads_path_created=by-init:<32 lowercase hex attempt>
beads_status=ready
beads_executable=<canonical qualified path>
beads_sha256=<64 lowercase hex>
beads_version=1.1.2
beads_platform=Darwin-arm64
beads_backend=dolt-embedded-cgo
beads_context=.domestique-private/beads-context
beads_prefix=dm<12 lowercase hex>
beads_uuid=<canonical UUID>
beads_readiness=init-ping-where-v1
beads_selectors_sha256=<64 lowercase hex>
beads_git=<canonical installed Git path>
beads_git_sha256=<64 lowercase hex>
beads_created=<known relative leaf/subtree>:<initial SHA-256>
```

`beads_created` repeats exactly in this order: `.beads/.gitignore`,
`.beads/.local_version`, `.beads/README.md`, `.beads/config.yaml`,
`.beads/embeddeddolt`, `.beads/interactions.jsonl`, `.beads/last-touched`,
`.beads/metadata.json`, `.domestique-private/beads-context`,
`.domestique-private/exports`. File hashes are SHA-256 of bytes; subtree hashes
use sorted relative names, NUL framing, `d` directory or `f` plus binary file
digest. These are initial unchanged-only purge baselines (.7), not runtime DB
freshness. Pinned `last_touched.go` reads empty as no default and writes the
explicit issue ID; its leaf is exclusively precreated before publishing ready,
never inferred from a later unknown artifact. `retained` uses the same ownership
fields; .7 emits it after last-provider removal, not as a fresh readiness claim.
`failed` is explicit
in the attempt journal and never eligible for runtime/rerun. Duplicate, missing,
NUL, unknown, unordered or unsupported state refuses in every consumer.

Metadata is exactly the pinned five-field embedded schema. Engine root contains
the stable prefix database and `.lock`; required physical `.dolt/noms/manifest`
exists. Engine config is empty and repo_state is main with empty remotes,
backups and branches. Private Dolt global config is empty. Immutable selector
fingerprinting includes metadata, config, local version, README/gitignore,
engine config/repo_state and private Dolt config. Context routing directories
remain empty; generated empty Git config is fingerprinted too.
Unexpected configs/redirects/.env/server paths, symlinks,
hardlinks, foreign ownership and indexed paths refuse before invocation.
All normal operations preserve original Beads manifest records. Readiness is
native ping query + canonical where, **not** info's human-text “direct” line or
an invented SQL/UUID protocol. Native identity mismatch refusal is the pinned
write guard proven by .14; routine code never mutates a user's UUID to test it.

**Installed operation API.** `beads-guard CORE PHYSICAL_PROJECT LITERAL_RELEASE`
is structural/read-only (including dependency fingerprints), not a native
query. `beads CORE PHYSICAL_PROJECT LITERAL_RELEASE COMMAND [ARGV...]` validates
the grammar before native readiness and executes only approved ready/show/list,
epic/task create, update/claim, close, dep add/remove, remember and fixed-path
export. No raw bd/global discovery fallback, shell eval, arbitrary global flags,
path/config override, SQL/auth/remote/setup/doctor/import/server or exec exists.
Option values are individual argv data, including flag-looking descriptions;
`--` permits flag-looking positional titles at the wrapper boundary. Pinned
`create.go:98` rejects such native positional titles even after `--`, so the
bridge sends the validated title as one literal `--title=<value>` argv element.
This was verified against the actual production wrapper with a title containing
both `--db` and “permission denied”; no option/path interpretation or false
denial classification occurs. Export writes only
`.domestique-private/exports/issues.jsonl` (optional include-memories), including
its native atomic temporary write, never source/global files. All native
provider fences and shared workflow roles require this dispatcher and literal
retained binding for every operation in every fresh shell. Definitions and
native profile routing remain read-only and independent of mutable DB hashes.
Native role discovery, reload/trust, tool capability and model/MCP acceptance
remain separate unverified gates.
Native stdout is operation data, not a denial-substring blacklist: issue text
such as “permission denied” is valid. Native stderr denials still stop.
For Beads attachments, final journal removals revalidate exact effective
exclusion bytes as well as paths/types/hashes; loss retains pending recovery,
not an eligible ready attachment. Later publication failure does not erase
already-proven DB creation; creation provenance and attachment completion
remain separate.

**Removal boundary (superseded by implemented .7 below).** Beads attachments
support retention and unchanged-only purge; ordinary profile-only .12 behavior
is unchanged. Global uninstall never writes projects; removing the
core makes its dispatcher unavailable and database use stops. Changed binary,
context, identity, unsupported version or failed state requires manual review/
requalification, never editing selectors to bypass a guard.

**Validation entry points:** `test/beads-private.py` is explicitly synthetic;
it substitutes a fake binary digest only into a disposable installer, with no
production environment bypass. `test/beads-production.py --run` executes the
actual new production initializer and installed dispatcher in fresh temporary
HOME/core/A/B/linked-W fixtures with the installed qualified binary, plus a
mixed-provider ordering fixture C. Each native process uses production's OS sandbox.
Setup Git uses the test sandbox; installer/dispatcher controllers use the
allowlisted temporary environment. Darwin refuses nested default-deny sandbox
application, so the test does not weaken it or pretend nested execution passed.
The native production run including .7 cleanup passed **85 checked controller commands**:
fresh state-only init and read-only dry-run/rerun in A, B and linked W; epic/task
creation (including the explicit-title case), dependency add/remove and ready
unblocking, update/claim, show/list, close, remember, fixed-path export, and
pre-invocation UUID-mismatch refusal with no rejected issue, plus used-DB
retention, purge refusal and qualified reactivation without rebaselining.
All **121 protected
entries** (including 15 host-policy/settings/data leaves, HOME/core, indexes,
Git configs and linked admin files) remained unchanged. Only the expected
managed exact exclusions changed; unrelated visibility and each exclusion's
host prefix remained unchanged. All three queues persisted independently.
C reversed both valid Claude role pairs and receipt roles, then passed combined
Copilot+Beads dry-run and actual initialization while preserving Claude files,
receipt bytes, creation/baseline history and global state.
These are controller-command counts, not a fabricated native subprocess count.
The .14 71-call native identity controls remain distinct historical evidence.

The historical .6 validation checkpoint recorded **790** synthetic Beads protocol/lifecycle checks, including
partial init, readiness failure, zero-exit invalid metadata, exclusive/late
claim collisions, protected callback failure, actual Git visibility for every
produced attempt/context/native file, and failed linked-worktree protection;
core **117**, global install **316**, local profiles **1134**, local
preflight **366**, updated missing/unowned Beads guards **1697**, local removal
**1364**, global removal **3173**. Offline native-context **31** and
native-discovery **45** remain prior evidence, not current rerun counts; their
shared harness was unchanged. Source and emitted helper pass Bash 3.2
syntax and warning-level ShellCheck; Python AST and `git diff --check` pass.
Use `python3 -I -B` for isolated test invocations: `-I` alone ignores
`PYTHONDONTWRITEBYTECODE`. No bytecode artifacts remain.
No real project Beads operations, tool installation, commits/pushes, or native
role/model/auth/MCP workloads were performed.

#### hq-b3q.10 Beads operation boundary checkpoint (historical; superseded by .6 above)

This checkpoint supersedes `.5`'s generic Beads CLI refusal, **not** its
profile installation/routing contract. Both the actual installer and updater
accept `--local TARGET --with-beads`, optionally with `--state-only`.
State-only requires both explicit flags and conflicts with `--platform`.
Bare/positional `--with-beads`, global initialization, state-only without
local/Beads, and initialization/uninstall combinations are usage errors
(exit 2). Valid initialization grammar returns **operational exit 1** before
any writes, bd execution, source fetch/copy, preview/apply or profile
installation, including dry-run and combined profile requests. No
`providers=none`, failed/ready record or path-creation claim is fabricated.
Ordinary private profile/global installation and updater behavior is unchanged.

**Verified upstream blocker:** installed Homebrew Beads 1.1.2's archived source
hash matched `gastownhall/beads` tag commit
`20e493e569c922d1253bdeff068c5e56c94957fb`. At that pinned source:

* [`init_stealth.go:48–90`](https://github.com/gastownhall/beads/blob/20e493e569c922d1253bdeff068c5e56c94957fb/cmd/bd/init_stealth.go#L48-L90)
  unconditionally adds broad common-dir excludes, including `.beads/`,
  `.claude/settings.local.json`, `.dolt/`, `*.db`,
  `.beads-credential-key`, and `.beads/proxieddb/`.
* [`init_stealth.go:170–223`](https://github.com/gastownhall/beads/blob/20e493e569c922d1253bdeff068c5e56c94957fb/cmd/bd/init_stealth.go#L170-L223)
  can rewrite/delete root `.gitignore`, without a tracked-file guard.
* [`init.go:681–708`](https://github.com/gastownhall/beads/blob/20e493e569c922d1253bdeff068c5e56c94957fb/cmd/bd/init.go#L681-L708)
  and [`init.go:1484–1536`](https://github.com/gastownhall/beads/blob/20e493e569c922d1253bdeff068c5e56c94957fb/cmd/bd/init.go#L1484-L1536)
  cover initialization/setup behavior: `--skip-agents` now suppresses all
  provider setup, but does not suppress stealth Git policy. Git `beads.role`
  and metrics/home writes are additional concerns.

There is no supported skip-Git-policy switch and **no currently certified
private backend/version**. Installing bd, detecting four flags, or inventing
a version threshold does not solve this. `.6` remains blocked on a real
supported backend preserving exact ownership/privacy, without run/rollback
or HOME/Git shims. No native client or real bd initialization was run for
this checkpoint. Even `where`, `ping`, `info` or engine startup can write
metrics, migrations or database state; pure loading/preflight never calls bd.

The standalone installed resolver adds the internal read-only API:

```
resolve-core beads-guard CORE PHYSICAL_WORKTREE REQUIRED_RELEASE
```

Its capability declaration is the exact line
`# beads_guard_api=1 (metadata-only eligibility; no certified backend)`.
Wrappers check it before invoking the operation; missing/old helper stops
with an explicit `bash update.sh --global` diagnostic using the same
`DOMESTIQUE_HOME`, then reload. **For this unpublished preview, use
`bash ./update.sh --source ./domestique.sh --global` from this checkout**:
the updater's default remote source is main, not this preview. The diagnostic
does not silently update anything.
The guard receives the parent's **literal release**, never samples `active`,
validates the bound release and exact physical Git root, checks state paths
and index-only objects/ancestors, and uses the existing strict private
format-1 ownership parser in runtime mode (native customization is allowed).
No `.beads` content is read and no bd command, lock, staging or repair runs.
All current cases refuse with empty stdout: `missing`, `host-unowned`,
`unsafe-path`, `tracked-index`, `invalid-private`, `invalid-core`, or
`invalid-project` (exit 1); wrong action/arity is exit 2.
Failed, partial, malformed and unknown/fake Beads records are rejected as
`invalid-private`, not parsed into invented readiness. Valid `providers=none`
or normal native-profile manifests without Beads are still `missing`.
Existing `.beads` is not ownership, including beside a valid private manifest.
Every guard refusal includes metadata-only manual guidance and the unsupported
backend limitation; it never instructs the user to probe/init Beads.

Each provider's actual emitted adapter now has three separately executable
fences: **core load**, **native role routing**, **project database guard**
(Codex fences are inside parsed `developer_instructions` TOML). Bind/read
remain usable without a project database. `.5` role maps and deliberate
global-only routing remain independent; neither bypasses database eligibility.
Shared core instructions require the guard at actual workflow startup,
including decompose-only planning, and before later database operations
(claim, discovered work, remember, land/export). Implementers guard database
operations, not source-only edits. Reviewers do not run bd at all, even for
reads; the parent supplies review criteria/evidence. No role may improvise
setup/init or apparent read-only bd probes. This is an instruction/executable
boundary, not OS sandbox enforcement of arbitrary user-written prompts.

Future `.6` hook points are `local_beads_guard` and the strict private ownership
parser plus explicit local CLI initialization branches. Only after a real
certified backend exists may `.6` extend ownership/readiness formats and
add a successful guard route; none exists now. The lifecycle text below is
**future acceptance**, not a claim that four flags are sufficient today.
Focused executable coverage is `PYTHONDONTWRITEBYTECODE=1 python3
test/beads-guard.py`, alongside all four current suites and the clearly
historical offline fixtures.

#### hq-b3q.7 implemented Beads retention and unchanged-only purge

The public local uninstall path accepts all seven provider sets, force and
dry-run. Bare/positional removal has the same local semantics. Initialization
flags, global purge and purge without uninstall are usage errors before writes;
the updater stays update-only. The embedded filesystem schema/hash validator
does not qualify or execute `bd`, nor read an unavailable global core.

Retention preserves every original Beads record, digest, attempt identity and
ordering plus all DB/context/export bytes. Mutable legitimate engine changes
are not initial-hash failures. Selected edited providers remain whole with
nonzero status, including force; unselected bytes stay untouched. After the last
profile, `ready` becomes `retained`, including already-none attachments.
Retained reruns are idempotent. Ordinary profile updates preserve retained
status. Explicit `--with-beads` reactivation runs the .6 qualified ping/where
before publishing ready; initial creation hashes are never recomputed.

Purge first proves successful ready/retained ownership and exact initial hashes
for all eight `.beads` artifacts plus context and exports. Reservations, failed
attempts, presence and equal unowned bytes are not authority. Unknown/missing
paths, changed hashes, NUL/duplicate/corrupt records, unsupported types, links,
foreign owners, tracked state and index ancestors refuse even with force, before
any provider removal. Any remaining unselected or edited provider refuses
shared-DB purge. No `bd` query, qualification or database-opening helper decides
purge: query startup can mutate the very baseline being checked.

Current wrapped operations and lifecycle changes use cooperative exclusive
nonblocking `fcntl.flock` on the existing owned metadata.json. A shell parent
retains fixed fd 8's open description while Python locks it; fd/path generation,
regular single-link ownership and the no-follow reopened inode must agree.
After acquisition manifest/pending/selectors are reread. The descriptor remains
held through native child reaping or actual metadata-last deletion. A stale
descriptor cannot approve replacement metadata. There is no new lockfile or
manifest field. New initialization instead uses .6 exclusive empty claims and
pending while metadata does not yet exist.
Coordinated native children also inherit fd 8, so an abruptly killed wrapper
cannot release the cooperative gate while its native leader survives.
Qualification staging uses the caller's TMPDIR (or current directory), never
an unconditional system temporary path. A generated `no-git-ops: true` config
binds its disposable no-DB target. After checking a new empty DB claim, init
exclusively creates that same fixed config before native init. This is necessary
because pinned native discovery ignores an empty explicit BEADS_DIR and can
otherwise select an ancestor database; the OS sandbox correctly denies that
attempt. No database contents are copied, no Git sentinel is forged, and the
pinned binary, clean native environment and OS sandbox are unchanged.

**Operator precondition: stop raw/older writers.** This is our cooperative lock,
not a native Beads writer lock. Pinned upstream
[`store.go:96–102`](https://github.com/gastownhall/beads/blob/20e493e569c922d1253bdeff068c5e56c94957fb/internal/storage/embeddeddolt/store.go#L96-L102)
uses native.lock only around initialization. No absolute process census,
hostile-writer protection, power-loss durability or cross-root atomicity is
claimed. Pure structural guards and qualification without a DB need no gate.

Deletion inventories complete recorded subtrees before the first removal,
rechecks type/generation/hash at each bottom-up exact path, journals actual
removals, and removes metadata last while its descriptor is held. Only the
by-init-proven empty `.beads` root is rmdir'd. No root/provider glob, recursive
root deletion, directory move, native data copy, host rollback, Git-sidecar or
out-of-root recovery journal exists. Beads fields persist until every recorded
path is gone. Reappeared/changed/unknown paths interrupt cleanup with original
baselines and private pending evidence, never invented success.

Shared common-dir exclusions are planned before writes against every actual
linked worktree and retained native/DB path. Only owned no-longer-needed rules
are removed. Final success rechecks remaining manifest/receipts/exclusions and
each journal immediately before unlink. Successful purge retains a valid private
providers=none manifest and its owned private-tree rule for reuse. Final deletion
of this reusable attachment is not part of .7.

`test/beads-cleanup.py` exercises synthetic public CLI, inherited-fd exclusion
and failure injection; `--native` separately opts into actual pinned .6
production initialization/CRUD/reactivation and cleanup with native-call
instrumentation. Both require project-local private TMPDIR and isolated HOME,
and neither implies .8 native role/tool/MCP acceptance.

The historical .7 implementation verification checkpoint (**2026-09-13,
commit `20b6fe8`**, superseded by the complete final matrix below) observed
**204 synthetic cleanup checks**
and **84 pinned-native cleanup checks** (107 and 56 instrumented bridge process
calls, respectively, including qualification probes). Final-source focused
checks passed **28 native checks / 15 real bd calls** and **27 synthetic checks /
15 fake bd calls**; both used 21 bridge processes and **zero bd calls during
cleanup**. Native production integration passed 85 controller commands.
Core (117), guard (1697), profiles (1134), preflight (366), global install (316)
and global removal (3173) matrices passed; the synthetic bridge suite passed
817 checks and updated focused schema/descriptor units passed 132. Local
removal's selection/preflight/shared-worktree sections passed, followed by all
478 remaining transaction/late-fault checks after updating their unique
injection anchors. That suite now freezes the source at startup: modifying a
live Bash script can otherwise splice changed byte offsets into an invocation.
Source/emitted Bash 3.2, warning-level ShellCheck and Python AST checks passed.

#### hq-b3q.11 explicit global removal checkpoint

Historical checkpoint account of the implemented global removal feature;
its then-future local removal statements are superseded by .12.

`bash domestique.sh --uninstall --global [--platform P] [--dry-run] [--force]`
now removes only positively owned global native leaves, plus shared core
leaves when the last eligible provider is removed. The seven provider sets
are unchanged; no selector means the **persisted owned union**, not discovery.
At the .11 checkpoint only explicit `--global` enabled removal (superseded for
local profiles by .12 below). Bare/positional/`--local` uninstall
still refuses as future `.7` work, as does purge. Targets, initialization,
state-only, `--no-guest`, and unsupported modifiers are usage errors (exit 2)
before writes. `--guest` remains a warning-only deprecated no-op. `update.sh`
is still only an updater; it does not accept/forward uninstall.

`global_uninstall` reuses `global_read_manifest`, `global_manifest`,
`global_inventory`, `global_check_core_tree`, physical `global_path` checks,
and the trusted embedded API-1 resolver. Raw manifest bytes must be NUL-free
and LF-terminated before parsing (also enforced on ordinary global install).
Every retained historical release needs all six valid recorded leaves.
Unknown entries anywhere under the core, malformed/missing state, missing
recorded leaves, changed core bytes, symlinks, unsafe ancestors or worktree
destinations refuse the entire operation before writes (exit 1), even forced.
Removal's `global_remove_path` checks bounded literal index leaf/ancestor
objects via `local_untracked` when an exact destination is now in a worktree;
it never scans projects, a registry or native profile directories. No bd,
native client, network/API request, or project write is part of removal.

Creation provenance and generated baselines remain distinct. A matching
unowned file is never adopted, including when all state is missing. Absence
of owned state, whether destinations exist or everything is absent, is an
explicit non-success: nothing was adopted or removed. A selector containing
no owned providers is a successful no-op only with otherwise valid state.
Customized **selected** native metadata retains its whole provider, all its
original valid records and assets, and required shared core. Other clean
selected providers can be removed; retained edits cause exit 1 with a clear
notice, also for a dry-run (“would retain WHOLE”). Unselected edited providers
stay byte-identical, without copy, rebaseline or renderer refresh. No `--force`
escape, backups, snapshots, content diagnostics or partial-provider format
exists. Full user-maintained forks and host config files remain untouched.

Dry-run performs the same full preflight without staging, journal creation or
destination writes. A successful scoped removal changes only eligible native
leaves and the canonical manifest/provider union; required shared core and
other provider bytes remain unchanged. Global format 1 never writes
`providers=none`: last-provider removal unlinks verified native assets,
helper, active pointer, **all** owned release history and the manifest. It
warns that project-local profiles stay in their projects and stop at required
core checks until global core is explicitly restored. There is no registry,
local repair, implicit reinstall or legacy fallback.

**Containers and reinstall.** Format 1 does not persist directory creation
provenance. Consequently no preexisting directory is deleted, including empty
skill, role, release, bin, state and core containers. Descendant file ownership
is not directory ownership. Only the new removal transaction's own temporary
manifest directory is `rmdir`ed after becoming empty. No recursive root
deletion is used. After complete removal, an ordinary install still refuses
the empty unproven core root rather than adopting it. Stop writers, manually
inspect and `rmdir` only the exact now-empty core containers bottom-up, then
explicitly reinstall with the same `DOMESTIQUE_HOME`/HOME. Leave native and host
configuration containers in place: a fresh install can create absent native
leaves there, but will still refuse collisions. Restoring the same global root
lets unchanged local loaders work again without project edits.

**Interruption and metadata-only recovery.** All preflight precedes writes;
each actual unlink revalidates physical ancestors, index status, regular-file
type and baseline hash. `unlink` receives a single exact file, not a root or
glob. Exclusive no-clobber creation publishes these reserved journals:

* `state/pending`: format 1, `operation=global-uninstall`, core root, previous
  manifest digest, remaining provider set (or `absent`, **not** a global
  manifest provider value), ordered `remove=<key>:<baseline>` intentions and
  a final manifest `remove` or `replace` intention.
* `state/previous`: the old canonical manifest re-emitted from validated
  metadata, never copied live native content.
* `state/published`: initially empty, then `removed=<key>:<baseline>` only
  after each successful exact unlink and absence check; the final manifest
  removal is recorded likewise. A retained manifest uses
  `replaced=core:state/global-manifest:<digest>` only after validating the
  actual exact replacement file/type/hash, never merely `mv` success.

Journal bytes/types/hashes are revalidated before append and immediately before
each journal unlink against generated or previously validated in-memory metadata,
never newly sampled live bytes. Changed or reappearing journals are left untouched
with the remaining recovery markers; pending clears last. All required retained
core leaves (helper, active, and every historical release's API/checksums/roles)
must still match their API-validated provenance before manifest replacement,
before journal cleanup, and again before clearing pending. Last-provider removal
has no retained core to check. The last manifest is also checked before cleanup.
Publication never moves a directory into a racing destination. A failed
command reports nonzero `PARTIAL removal`; remaining manifest/previous records
and journals are retained, not falsely presented as a fresh installation.
Ordinary install and uninstall reruns with pending state fail closed.
Stop all writers and manually compare exact leaf presence/digests with
previous, planned and completed records; an intent is not a completed
deletion or creation. Never recover an unknown destination merely because it
matches generated bytes. Do not copy edited metadata into recovery files.
An interruption between unlink and logging can leave an unrecorded completed
deletion; damaged or incomplete journals require manual reconciliation, not
inference or automated retry. Reconcile the exact transaction before removing
its artifacts. This is bounded checked shell publication, **not** cross-root
atomicity, power-loss durability, or a hostile-same-user-writer lock promise.

Focused current-source coverage: `PYTHONDONTWRITEBYTECODE=1 python3
test/global-uninstall.py`. Fixtures use physical temporary HOME/core and real
local project attachments, actual helper/fence execution, whole-tree identity
hashes and command-level failure/race injection; no native runtime acceptance
is claimed. `.6` Beads initialization remains blocked; `.7` local uninstall/
purge, `.8` live acceptance and `.9` full README remain future work.

#### hq-b3q.12 local profile-only removal checkpoint (historical boundaries)

The following describes the .12 checkpoint. Its Beads refusal boundary is
superseded by .6 initialization and .7 cleanup, not an active purge restriction.

`bash domestique.sh --uninstall --local TARGET [--platform P] [--dry-run]
[--force]` removes only positively owned, unchanged local native roles and their
validated routing receipts. Bare `--uninstall` and positional TARGET are this
same local operation, never implicit global installation/removal or the retired
normal/guest engine. All seven provider selectors work; selectorless removal
uses the persisted union. `--guest` remains a deprecated warning-only alias;
`--no-guest`, purge, and initialization/state-only combinations refuse before
writes. `update.sh` remains update-only. The .10 unsupported initialization
boundary is unchanged.

**No global dependency.** `local_uninstall` uses the embedded strict local
ownership reader, physical Git top-level/path/index checks and common-dir
exclusion planner. The persisted canonical `core_root` is identity metadata:
removal neither reads nor executes global assets and does not require a usable
core, helper, active release, or Beads backend. Missing/incompatible global
installations can be repaired separately. Removal never writes HOME, a global
registry, the index, root policy, hooks, settings or `.gitignore`.

**Retention is whole-provider.** Any selected customized native role retains
that provider's entire role set, receipt, original created/baseline records and
exclusions, with nonzero status even under force/dry-run. Eligible other
providers can still be removed. Unselected customized metadata is usable but
never becomes a new saved baseline. Comparisons use ephemeral hashes; live
native contents are never copied into a backup, temporary file or journal.
Unknown or byte-identical unowned leaves are not adopted. Tracked/index-only
ancestor objects, symlinks, NUL/corrupt records, missing receipts, unknown
private state, active legacy policy and ambiguous exclusion ownership refuse
before writes. Unrelated files in native parent directories remain untouched.

**Shared privacy and containers.** The .4 planner validates existing rules
against the before-inventory, then derives the removal union from remaining
current roles and all actual linked worktree owners. Other owners keep their
exact native rule; same-path host collisions and unreadable/broken worktree
state refuse. Missing/unknown/duplicate managed rules are not silently repaired.
No `.domestique-private` or native parent directory has positive directory
creation provenance for pruning. Native containers therefore remain untouched;
no new directory ownership is recorded. The existing positively owned private
attachment remains in place, with its already-proven private-tree exclusion.
Linked worktrees can independently remove their last profiles: exact native
patterns remain only while another worktree or retained provider needs them.

Successful last-profile removal publishes a valid format-1 local manifest with
`providers=none`, zero native `created`/`baseline` entries, and the same physical
worktree, `core_root`, and Core API metadata. No adapters, receipts or journals
remain. This is retained-after-removal attachment metadata, not Beads readiness,
initialization or database ownership. Success reports **profiles removed;
private attachment metadata retained** only after all selected eligible profiles
are gone and retained state validates; a selected customized provider still
causes nonzero status. No private-state tree or private-tree exclusion is
automatically destroyed by .12; explicit integrated final-state cleanup belongs
to .7. Do not manually remove this valid attachment as a normal reinstall step.

A bare local install rerun with `providers=none` creates no agents. Repeated
local uninstall validates the attachment and reports no owned profiles without
changing metadata, even with a missing global core. Explicit provider reinstall
reuses the valid attachment and requires a compatible global core, as before.
An unknown preexisting `.domestique-private` is still never adopted.

**Interruption is not successful removal.** All preflight precedes writes.
Exact leaves are revalidated immediately before `unlink`; a metadata-only
`pending` intent contains original manifest records and intended path/digest
removals. `published` records actual completed unlinks/manifest creation, not
planned deletion. Manifest replacement is a checked unlink plus exclusive
creation, not a directory-interpreting move. The implementation rechecks all
remaining native/receipt/manifest hashes, bounded private inventories, index
objects, linked-worktree enumeration/common-directory identity and actual Git
ignore effectiveness (including late host-policy changes) before state commit and
before clearing each journal. Late changes preserve unknown bytes and fail
partial. Each journal is independently revalidated immediately before unlink.
Last-profile publication follows the same retained-manifest path as partial
removal, never a zero-state/drop-exclusion phase. The original `pending` stays
in the existing private root throughout manifest and exclusion publication and
all risky validation. `published` is cleared only after retained
manifest/receipts/exclusions validate; those checks run again before the exact
last-minute validation and final unlink of `pending`. No after-the-fact pending
recreation or exclusion-repair engine is needed. All local records, including
original intent, previous provenance and completed-operation journals, live
only in `<repo>/.domestique-private/`, never Git metadata or HOME.

This is bounded revalidation, not an OS-atomic transaction or writer lock.
Detected late changes fail nonzero with the existing in-root pending evidence;
unknown bytes and changed shared excludes are never overwritten to repair them.
An outside writer that destroys the original private exclusion (or a failed
exclude write) can expose already-existing state. There is no promise of privacy
against that concurrent destruction, no authorization to clobber foreign rules,
and no out-of-root fallback storage. Stop writers and manually reconcile.

Stop writers, retain available pending/published records, and compare original
provenance, actual exact leaves and shared exclusions manually before retry.
Never adopt a reappeared identical leaf, copy edited metadata into recovery, or
discard unexplained recovery records. During interrupted publication, pending
state makes install/default routing fail closed instead of silently choosing
global routing.

**Beads is not implemented by this checkpoint.** An unrelated host `.beads`
database and its preexisting visibility are untouched; no database inspection,
probe, initialization, retention ownership or purge is inferred. Unknown future
Beads fields/recovery formats refuse cleanup pending .7. A valid
`providers=none` state reports no owned profiles, not invented readiness or
database ownership. .6 remains blocked, .7 retention/purge and .8 live native
acceptance remain future work; .9 full documentation is separate.

Current executable coverage adds `PYTHONDONTWRITEBYTECODE=1 python3
test/local-uninstall.py`, including linked-worktree `check-ignore` visibility
and explicitly triggered partial-unlink/journal/retained-state mutations.
Fixtures isolate HOME/core and fake all native/Beads/network commands.

#### hq-b3q.13 isolated native discovery checkpoint (bounded part of .8)

**Observed 2026-09-12 on macOS arm64; not native execution acceptance.**
`test/native-discovery.py` uses the current installer, not historical fixtures
or mocked clients. Reproduce from the repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 test/native-discovery.py --run
PYTHONDONTWRITEBYTECODE=1 python3 -W error test/native-discovery-tests.py
```

The first command emits JSON: `NATIVE_DISCOVERY_OBSERVED` means an actual
native metadata response with checked IDs, enabled state and source paths;
`BLOCKED` names a typed absent tool, source-backed unsupported interface or
documented denied tool approval, never an arbitrary runtime refusal;
`ASSERTION_FAILURE` is a regression or malformed response; `STATIC_ONLY`
is installer/filesystem/schema/isolation evidence, **not** native discovery.
Exit **0** means no blocked or failed discovery components, **1** means
assertion/harness failure, **2** means blocked/incomplete native coverage.
Malformed RPC envelopes/results or skill field types, and successful but
empty/whitespace-only `--version` output, produce component-labelled
`ASSERTION_FAILURE` records and exit 1, not tracebacks or discovery success.
RPC diagnostics name the method/shape or native error code without echoing
raw response/error-message/stderr contents; malformed stdio paths retain
bounded process-group cleanup.
Without `--run`, nothing native runs: `STATIC_ONLY`, exit 2. Missing clients
are never installed, and missing/failed isolation stops before native startup.

**Isolation.** Executable symlinks are resolved before replacing HOME.
Physical temporary HOME, XDG config/state/cache, CODEX_HOME, native directories,
private core and independent Git top-level fixtures A/B are disposed at exit.
The environment is constructed from an allowlist, not copied: no inherited
tokens, provider settings, proxies or shell startup variables; PATH contains
system tools and isolated links to the resolved Node/Git. Git uses no global
or system config, no host templates/hooks; OpenSSL uses `/dev/null` rather
than host configuration. The macOS-only `sandbox-exec` policy defaults to deny,
grants no network or Mach/Keychain IPC, and permits file-content reads only
for fixtures and specified installed runtimes/packages (plus source reads
for the installer alone). File metadata reads are permitted. Writes are
confined to fixtures, with `/dev/null` as the only sink exception.
Before native calls, a harmless probe verifies an inside write, denied
outside-sentinel read/write, and denied loopback bind/connect. No auth,
inference, MCP, trust/registration, ACP startup, Beads or model prompts are
invoked. All commands have 30-second deadlines (installer: 120 seconds);
finite stdio servers must answer initialize/list, then their exact process
groups are killed/reaped, including on errors (cleanup deadline: 5 seconds).

Actual installed entrypoints below use `$ORIGINAL_HOME` for the pre-isolation
home; these are executable locations, not configuration read locations:

| Client/version | Resolved entrypoint | Native result / precise limit |
| --- | --- | --- |
| Claude Code **2.1.268** | `$ORIGINAL_HOME/.local/share/claude/versions/2.1.268` | **BLOCKED** roles and skills. `--help` then `agents --help` describes **“Manage background agents”**; `--json` prints active sessions, not configured roles. No non-model skill listing advertised. The session view was not launched; older assumptions about `claude agents` do not apply to this installation. |
| Codex CLI **0.154.0** | `$ORIGINAL_HOME/.nvm/versions/node/v22.22.0/lib/node_modules/@openai/codex/bin/codex.js` (resolved from `/opt/homebrew/bin/codex`) | **OBSERVED** skills via `app-server --listen stdio://`: real `initialize`, `initialized`, `skills/list` (`cwds`, `forceReload=true`), and `config/read`. `app-server --help` and `generate-json-schema --help/--out` were inspected first; generated schemas gate the adapter. **BLOCKED** roles: stable schema has no role-list method; `config/read` returns `config.agents=null` in A and B, before and after local setup. This is not evidence that `.codex/agents` is unsupported or ignored by a model session. |
| GitHub Copilot CLI **1.0.83** | `$ORIGINAL_HOME/.nvm/versions/node/v22.22.0/lib/node_modules/@github/copilot/npm-loader.js` | **OBSERVED** skills via `skill list --json`, after inspecting `skill --help` and `skill list --help`; no authenticated startup required. **BLOCKED** roles: top-level help offers `--agent` selection, not a non-model role-list command. ACP initialization would not establish discovery and was not attempted. |

The JavaScript launchers used resolved Node
`/opt/homebrew/Cellar/node/26.7.0/bin/node`. Native help/version also ran only
inside the fixtures/sandbox. Copilot's unpacked builtin cache and Codex's
system-skill sources were under temporary HOME, never the real session store.

These versions are observations, not minimum support requirements or evidence
that the products lack roles. The blocked classifications concern only the
safe non-model interfaces available to this harness.

**A/B and reload evidence.** Current `--global --platform all` leaves both
initial Git snapshots unchanged. Codex natively lists `domestique-codex`,
`domestique-codex-decompose`, `domestique-codex-goal`, scope `user`, from
`$HOME/.agents/skills/<ID>/SKILL.md` in both repos. Copilot lists all three
`domestique-copilot{,-decompose,-goal}` from `personal-copilot` and all three
Codex-qualified skills from `personal-agents`, without duplicate names.
After `--local A --platform all`, fresh processes in both repos still list
those global skills. All six qualified local role files exist only in A
(`STATIC_ONLY`); **native local-role visibility in A, absence in B and global
role coexistence remain BLOCKED for all three clients**, not inferred from
files, routing receipts, config nulls or skill discovery.

A final fixture-only edit changes the ordinary Codex/Copilot skill descriptions
to `Fixture metadata reload hq-b3q.13.`. Fresh native processes report exactly
that description in both repos. This proves skill-metadata reload, not live
shared-core updates or role capability reload. Before/after project snapshots
cover help/schema and every discovery invocation, including failures; this
run recorded **no native project writes** in A or B, and local installation
left B unchanged. Future native cache differences are returned as explicit
relative paths, not silently excluded.

Final run: **12 native skill observations, 8 blocked records, 0 assertion
failures, 22 static-only records; exit 2**. Blocked records are Claude
roles/skills, Copilot roles, and six Codex role checks across A/B and three
stages. **45 offline harness tests passed** (synthetic protocol/classification,
timeouts, EOF/errors, cleanup, environment and source checks; not native
proof). Python AST, Bash 3.2 syntax and warning-level installer ShellCheck
passed. No renderer changes or full product-suite rerun were needed.

The executable guard/resolver tests remain **OFFLINE**, separate from these
native metadata observations. Nothing here verifies role execution, tool/MCP
access or enforcement, explicit-goal/model-session rules, live core updates,
or actual Beads goal/decompose work. .6 private Beads initialization remains
blocked by upstream privacy, .7 database retention/purge remains future work,
and those execution/trust criteria of .8 remain open.

#### hq-b3q.14 native Beads private-context experiment (TEST ONLY; .6 blocked)

**Current .8 test-only selection checkpoint (2026-09-14).** Historical observations
below are unchanged. `test/beads_fixture.py` is an independent stdlib resolver
shared by context, production, native cleanup and the acceptance controller.
Default remains `/opt/homebrew/Cellar/beads/1.1.2/bin/beads`; explicit
`DOMESTIQUE_TEST_BEADS_BINARY` accepts a manually provisioned absolute private
path only after physical-path, regular/readable/executable and exact SHA-256
validation:
`cb77069648d90fef8876f775d647997beb7bb0ab5461509394c29d5bf14b7c42`.
No downloads, registry, cache, system downgrade/link change, production PIN
change or alternative release-build acceptance is involved. An invalid explicit
selection is a failure, never a missing-tool blocker or fallback. Only an absent
default retains the context harness's missing-tool blocker.

Selection occurs only after native opt-in. Default/synthetic cleanup does not
even import the resolver. Acceptance forwards the setting solely to the three
native Beads scopes, including empty values so they fail rather than disappear;
offline, historical and AI discovery scopes receive none. Spawned product/native
commands retain their allowlisted environments without this variable. The context
profile uses the existing tools/profile mechanism for one extra **literal**
selected-executable read; no HOME/parent, network or mach grants. It no longer
depends on the global `bd` link. Production and cleanup retain the initializer's
own sandbox, not a nested test sandbox. Native platform/ABI and live validation
are unchanged.

Context records `binary`/`binary_sha256`; production records `native_fixture`;
cleanup emits `NATIVE_FIXTURE=` JSON before its unchanged completion line.
Acceptance validates this grammar, records each selected actual path/digest as
per-scope `native_fixture` under the source-bound report, and compares selection
again after execution. Private reports retain the actual private path.
`beads-fixture-tests.py` is in QUICK and CURRENT; validation/provenance globbing
includes it and the resolver. Newly affected dependencies are acceptance and
its units, the three native Beads harnesses, the shared discovery profile
(hence discovery/context/native-supervision units), the new selector units,
syntax/AST/lint and these usage docs. No prior native-discovery evidence is
replaced. The missing-qualified-dependency failure in `s86mqfvk` is not product
fallback evidence; its 12 discovery observations / 8 legitimate blockers remain
separate. This checkpoint is not native lifecycle requalification or completion
of .8: fresh remaining native/current/historical coverage and independent review
are still required.

Checkpoint validation: selector/wiring **17**, acceptance runner **99**, context
**31**, discovery protocol **48**, and native-supervision **26** synthetic unit
tests passed sequentially. Existing selected syntax validation passed (14 shell
files, emitted resolver, 24 Python ASTs, embedded Python, warning-level
ShellCheck with zero exceptions, `git diff --check`). Exactly one isolated
qualified-path `--sandbox --version` smoke returned `bd version 1.1.2 (Homebrew)`,
exit 0, empty stderr, with the exact digest above and fixture cleanup verified.
No native init/CRUD, lifecycle/context/discovery suite or matrix was run at this
checkpoint; the system `bd` link remained on 1.2.2.

**Executed on macOS, 2026-09-12; not a user initialization recipe.**
`test/beads-native-context.py` imports the existing native-discovery stdlib
environment, sandbox runtime-read policy, bounded process-group runner and
isolation probes without modifying that helper. No agents, models, auth, MCP,
installer, real-project Beads commands, Git commits, pushes, or external Dolt
servers were invoked. Production `.10` guard/initializer refusal is unchanged.
The script defaults to `STATIC_ONLY`/exit 2 without native execution or fixtures.

Reproduction commands (only the harness creates/addresses disposable fixtures):

```
PYTHONDONTWRITEBYTECODE=1 python3 test/beads-native-context.py --run
PYTHONDONTWRITEBYTECODE=1 python3 test/beads-native-context-tests.py
PYTHONDONTWRITEBYTECODE=1 python3 test/native-discovery-tests.py
```

**Observed pin and mechanism.** Installed `/opt/homebrew/bin/bd` resolves to
`/opt/homebrew/Cellar/beads/1.1.2/bin/beads`, reporting
`bd version 1.1.2 (Homebrew)`. Reports include binary SHA-256 (not a claim
of reproducible binary/source equivalence); the final 07:21:50 UTC trial
recorded `cb77069648d90fef8876f775d647997beb7bb0ab5461509394c29d5bf14b7c42`.
Public read-only source reviewed:
`gastownhall/beads@20e493e569c922d1253bdeff068c5e56c94957fb`,
especially `cmd/bd/init.go` (559–583, 681–737, 1114–1223),
`init_stealth.go`, `doctor/gitignore.go`, `ping.go`, `info.go`,
`context_cmd.go`, `export.go`, `sql.go`, and `main.go` (1439–1474).

Each fresh physical fixture repo **R** has its own
`P=R/.domestique-private/beads-context`, `CWD=P/run`,
`BEADS_DIR=R/.beads` (initially absent), and
`GIT_CEILING_DIRECTORIES=P`. Real Git returns exit 128 / “not a git repository”
from each private CWD and correctly discovers R from each host root.
Two independent repos A/B and W, an orphan linked worktree of A, are prepared
with sanitized Git configs/empty templates/hooks, without a commit.
Every actual native command, including version/help, runs from the private
non-Git CWD; **no mixed-context recovery was needed for the required operations**.
This does not certify unexecuted commands such as `context` (help only).

The native init argv is exactly the pinned executable plus:
`--sandbox init --stealth --skip-agents --skip-hooks --non-interactive
--prefix fx{a,b,w} --remote=`.
The explicit empty remote opts out of Git-origin remote inference in the
pinned source. Native `--sandbox` disables auto-push; it is **not OS security**.
The database is created directly at its final fixture path, without a
Git shim, temporary database relocation, copy, rollback, or lock deletion.

Environment is constructed, not inherited: HOME, XDG config/state/cache,
TMPDIR, empty Git hooks/templates and a bin containing only resolved tool
symlinks are inside P. Runtime PATH adds only system executable directories.
The reused helper also sets fixture CODEX_HOME/DOMESTIQUE_HOME, locale/terminal,
no-color/no-bytecode and `OPENSSL_CONF=/dev/null`. Git uses
`GIT_CONFIG_NOSYSTEM=1`, GLOBAL/SYSTEM `/dev/null`, no terminal prompts and
one process-only `core.hooksPath` override. Beads controls are:
`BD_DISABLE_METRICS=1`, `BD_DOLT_MODE=embedded`,
`BD_DOLT_SHARED_SERVER=false`, `BD_BACKUP_ENABLED=false`,
`BD_EXPORT_AUTO=false`, `BD_NO_HOOKS=1`.
No inherited auth, telemetry, proxy, BEADS_DB/BD_DB or Git directory overrides
are passed; no user configuration is copied. In particular, the external-server
forcing BEADS_DOLT_SHARED_SERVER/SERVER_MODE variables and OTel export variables
are absent. No reliance on `OTEL_SDK_DISABLED`.

**OS isolation and privacy evidence.** Default-deny macOS sandbox-exec allows
runtime reads and fixture reads, no network or mach/Keychain IPC grants.
Native writes are limited to that repo's P and `.beads` (plus `/dev/null`);
the generic helper's broad fixture-write grant is replaced, not retained.
External `/dolt` execution is explicitly denied. Before any native bd call,
positive private writes and negative outside-fixture read/write, host Git
config/index/exclude/hooks/policy/HOME-sentinel writes, and network bind/connect
probes actually run. Only **PermissionError**, not arbitrary process failure or
connection refusal, satisfies a negative probe. W additionally probes its
`.git` pointer and A's linked-worktree admin index/HEAD.
Git writes are allowed only during fixture setup; subsequent host Git probes
use the narrow native sandbox. Every child is bounded to 60 seconds, the native
phase to 480 seconds, with exact child process-group kill/reap on exit/timeout.
Only known fixture trees are cleaned; orphan cleanup errors fail the report.

Before/after snapshots cover **69 protected entries**, file bytes, modes,
index/config/info-exclude/hooks and linked common/admin paths, root policies
and a fake external HOME sentinel. A's `.gitignore` includes the exact
`# Beads / Dolt files (added by bd init)` section the pinned initializer would
otherwise remove. It remained byte-identical. `git check-ignore` for
`unknown.db` / `.claude/settings.local.json` stayed `[0,1]` in A and `[1,1]`
in B/W (0=ignored, 1=visible). **No protected changes** were observed.
No exclusions were installed: native's “invisible”/“exclude configured”
success prose is misleading after its explicit non-Git skip.

**Actual outcomes:** the completed trial ran **71 native Beads processes**:
67 exit 0, three expected identity refusals exit 1, and one expected unsupported
SQL diagnostic exit 1. Structured proof counts are **8 PASS, 1 BLOCKED,
0 FAILED; overall exit 2**. SQL introspection remains honestly BLOCKED but is
**no longer a feasibility blocker**; this is still not production acceptance.

* PASS native init, readiness (as narrowly defined in the report), required
  operations, separation, **IDENTITY_BINDING**, host privacy, sandbox, cleanup.
* All three real metadata files say `backend=dolt`, `dolt_mode=embedded`,
  database names `fxa/fxb/fxw`, and distinct valid `project_id` UUIDs.
  Physical `.beads/embeddeddolt/<database>/.dolt/{config.json,repo_state.json,
  noms/manifest,...}` files exist; no redirect or server-mode directory/artifacts.
  Metadata's legacy `database: "dolt"` is **not** the physical engine path.
  `where --json` confirms the physical `.beads`/embedded path and explicit prefix.
* Six `ping --json` invocations actually query the stores, before and after
  operations in separate fresh processes. Ping is status/timings, **not identity**.
  Per repo, actual create produces an epic and two bounded tasks; show verifies
  parent-child/blocking edges, ready excludes then includes the dependent task,
  update/show verifies in_progress, and close persists. Remember persists one
  dummy memory. Explicit private JSONL exports contain exactly three issue
  records and one `_type: "memory"` record each. Final fresh `list --all --json`
  queries find each repo's own three IDs and none from the other two queues,
  including W versus its common-dir owner A.
* **PASS IDENTITY_BINDING, independently repeatable in A/B/W:** after normal
  init/CRUD/export, the harness preserves each known generated `metadata.json`'s
  bytes in memory and changes **only `project_id`** to a different valid UUID.
  One uniquely titled disposable `create` per fixture, through the same verified
  sandbox/controller/environment, returns nonzero with the pinned
  `main.go:1439–1474` diagnostic: `Error: workspace identity mismatch detected`,
  `metadata.json project_id: <replacement>`, and
  `database _project_id: <original>`. The last field reports the original UUID
  despite the changed metadata field, proving database binding beyond distinct
  metadata UUIDs. Arbitrary nonzero, an unrelated version/mode error, missing or
  wrong original UUID, or a successful write cannot pass. Reports retain only
  controlled refusal fields, not raw recovery advice. Original metadata bytes
  are restored in `finally`, even on failure; a fresh native `list --all --json`
  must then contain exactly the expected three IDs and no rejected title.
  All three actual controls passed restoration and absence checks.
* **BLOCKED optional direct database UUID query:** actual
  `--sandbox sql "SELECT value FROM metadata WHERE \`key\` = '_project_id'" --json`
  returns exit 1, empty stdout, and
  `Error: 'bd sql' is not yet supported in embedded mode`.
  This is explicitly refused by pinned `sql.go`, not a GetRepoContext/CWD error;
  no host-root/server fallback was attempted. There is **no direct SQL result**;
  database identity binding is instead proven by the negative controls above.
  Direct `config get _project_id` returned empty in the earlier independent
  review and is not identity evidence (not added to this harness). Pinned
  main.go can skip native validation when the DB key is missing; such a skipped
  check/successful write **fails** this control, never counts as identity proof.

Warnings retained: missing repository/clone fingerprints, unconfigured
`beads.role`, and five missing Git hooks. No suggested Git config/hook/setup
repair was run. Unknown warnings and any surfaced permission denial block.
`info --json` actually emits human text (“Mode: direct”) here despite its
help/source JSON branch; the harness records this diagnostic-only protocol
limitation rather than interpreting it as engine/identity proof. Early harness
trials failed on that JSON assumption and on treating exported memory records
as issues; both parsers were corrected against actual output/pinned types, not
by accepting arbitrary process failure. Kernel denial audit logs are **not**
collected: silent attempted denials are not disproved by unchanged snapshots.

**Review gate for .6:** this establishes feasibility of the bounded non-Git
context for tested init/CRUD, not a certified initializer. A future wrapper
still needs independent review, exact executable/platform/version certification,
owned physical private-context paths and process-only environment, explicit
stable prefix/audit identity policy, no host config/role fixes, strict readiness
and DB-identity evidence under known initialization, a pinned target and approved
commands, partial-init failure handling without destructive
rollback, and exact exclusion/manifest ownership (including context artifacts).
UUID mutation here is a **disposable-test negative control only**, never a
routine identity check or recovery recipe for an existing user database.
It must not reuse stealth's broad ignores or treat help flags/exit 0/direct mode
as readiness. No production ownership/readiness format was added here.
Production `.6` stays disabled until its own implementation and independent
review; its parent adjudicates this evidence after independent review.
Other platforms/versions, existing databases, concurrency, production removal,
and role/model/MCP workflows remain unexecuted and uncertified.

Validation: **31 pure offline guard/protocol tests (the original 16 unchanged,
plus 15 classification/restoration/failure/cleanup tests) and the unchanged
helper's 45 tests pass**. Synthetic helper tests are not native identity proof.
Python AST/syntax and `git diff --check` pass. No new framework,
package/tool installation, production edits, or full installer-suite run.

#### hq-b3q.5 public private-profile checkpoint (historical status; feature implemented)

This checkpoint supersedes the older CLI-status statements in `.3`/`.4`
below. `--local TARGET`, old positional `TARGET`, and bare `.` now all use
the private local operation, never the legacy engine. Both scopes accept all
seven provider sets. Selection adds to the recorded union; a bare rerun uses
it, fresh state defaults to Claude, and retained `providers=none` creates
nothing. `--guest` only warns; `--no-guest`, unsupported model/MCP/tool flags,
malformed scope/target combinations and local uninstall/purge
refuse before writes (updater: before fetch). `.6`/`.7` own those unfinished
lifecycle operations; `.10` above defines the current Beads refusal grammar.
`.11` above supersedes this checkpoint's earlier global-uninstall refusal;
`.12` supersedes its local profile-uninstall refusal, not Beads purge.
No implicit global installation or update occurs.
Missing/old router helper requires an explicit `bash domestique.sh --global`
with the same private-root environment.

Local setup uses `.4` preflight/migration/exclusion accounting, publishes
only exact provider-qualified native role leaves (both roles for requested
providers), and records generated baseline digests and creation provenance
in `.domestique-private/manifest`. Receipts live only in its `routing/`.
No local skills, root policies, core body copies, settings, `.gitignore`,
index, hooks, Beads, home registry or global writes are part of local setup.
An unknown identical leaf is not adopted. Pristine owned files can refresh;
edited files refuse the entire refresh untouched even with force, before
rendering or copying any live native content. Full prompt forks are never
relinked and cannot claim shared-core compatibility.

The standalone installed `bin/resolve-core` adds `router-api` (prints
`router_api=1`) and:

```
route CORE PHYSICAL_WORKTREE PROVIDER ROLE REQUIRED_RELEASE INTENT [PIN]
```

`ROLE` is implementer/reviewer. `INTENT` is default, global-only or
local-required. The required release is always the literal parent binding;
route never samples active. Successful output is exactly one ephemeral token:
`global-only:<exact-ID>` or
`local-required:<exact-ID>:<manifest-sha256>:<receipt-sha256>:<current-leaf-sha256>`.
Supply that same token to every subsequent check. A changed/missing bound
local profile/receipt fails without fallback. Explicit global-only deliberately
bypasses local evidence; default fails on invalid local evidence, including
indexed native leaves or indexed path ancestors without working copies.
Literal Git pathspecs check only the requested leaf/subtree and exact ancestor
objects, not unrelated tracked host files in provider directories. Private
manifest/receipt paths and their indexed ancestors are checked as well. A valid
receipt listing only the other role permits a global requested role only
when the requested adapter is absent. The two roles bind independently.
Tokens and hashes of live native content must never be saved to files,
preferences, Beads or memory.

The resolver reuses `local_manifest_read ROOT runtime`, separating structural
and creation/path provenance from the install-only pristine baseline check.
Readable owned untracked nonsymlink regular native roles may have edited
native tools/MCP metadata at runtime. This is not native schema validation,
trust proof, authentication, or proof that required tools/core protocol are
available. Wrappers contain executable core and routing fences (Codex:
`developer_instructions`), plus a stable loader declaration. Orchestrators
must use native discovery to independently confirm exact ID/no collision,
reload after edits, trust, read/shell capability and the active required core
protocol before delegating. Failure to confirm stops; edited tools never
waive guardrails. Native registration/auth remain separate user actions.
No actual native client/server calls are made by setup or these tests.
Core API 1 and each immutable release's six-file inventory are unchanged.

Publication exclusively claims a private `pending` prospective manifest and
records successful native creation/refresh digests in `published`. New native
leaves and new receipts/manifest use exclusive noclobber redirection from
generated staging (also used for release population). Files, directories and
dangling symlinks at the final leaf refuse, never become target containers.
Replacements move a same-basename generated file to the parent directory,
not to the final leaf as a possible container. Every publication verifies
the exact final path, regular-file type and generated digest before recording
creation/refresh or proceeding with receipts/manifest. Replacement is not
exclusive against concurrent regular-file writers; these checks do not
promise concurrency isolation. Receipts/manifest publish before the `.4`
shared exclusion apply/revalidation, and journals clear last. An interrupted
operation reports `PARTIAL`; normal reruns and routing refuse retained
journals. Retain them and reconcile exact creation/publication metadata
manually, never infer creation from the pending intent or byte equality.
No live metadata is copied into logs/backups/recovery. Only generated source
is staged. A failure can leave partial native/private files before exclusion
publication; it is not a successful private installation and must not be
committed. Cooperating-writer/revalidation limits from `.4` still apply:
stop other writers; this is not hostile same-user race or power-loss atomicity.

Current production coverage: `beads-guard.py`, `global-uninstall.py`,
`local-uninstall.py`, `local-profiles.sh`, `local-preflight.sh`, `global.sh`,
`private-core.sh`; `native-discovery-tests.py` adds 45 offline harness tests.
Retired normal/guest/merge/uninstall behavior
is retained as explicitly labelled offline `b60feef` fixture coverage in
`codex.sh`, `copilot.sh`, `guest.sh`, `upgrade.sh`, `uninstall.sh`, not claimed
as successful production CLI acceptance. `.4` migration fixtures also use
that historical installer. .9 now documents this implemented preview; .13
records limited native-version evidence, not full .8 execution acceptance.

#### hq-b3q.4 internal local safety checkpoint (historical pre-.5 status)

`domestique.sh` now embeds the following ordinary Bash functions **before
`usage()`**, so the existing extract-before-usage test/consumer pattern can
load them without running main. No successful `--local` operation, dummy
role, new default behavior, or compatibility CLI switch is introduced.
Legacy normal/guest execution, including its historical limitations, remains
unchanged. The new fail-closed rules apply to these internal APIs only.

* `local_preflight TARGET PROVIDERS [check|migrate]` is entirely read-only.
  It resolves an existing exact physical Git top-level, checks the required
  global core using the embedded trusted API-1 resolver and global ownership
  checks, validates local state and all six reserved native local leaves,
  classifies all three legacy provider inventories, and plans shared excludes.
  `PROVIDERS` accepts the seven canonical sets or `none`; existing native
  ownership is unioned into the requested inventory. `check` is the default
  and refuses active legacy authority. `migrate` only plans positively
  created, unchanged, untracked legacy removals; it does not perform them.
  `FORCE`/`DRY_RUN` environment variables confer no authority.
* Successful preflight returns metadata in `L_ROOT`, `L_CORE`, `L_RELEASE`,
  `L_WANT` (repo-relative native leaves), `L_REMOVE`/`L_REMOVE_HASH`
  (absolute legacy leaves and digests), `L_LEGACY` (provider:normal/guest
  evidence), `L_COMMON`, `L_WORKTREES`, `L_EXCLUDE`, `L_EXCLUDE_BEFORE`
  (digest, or empty for absent), and `L_EXCLUDE_AFTER` (prospective exclude
  bytes). Arrays after a failure are **not a plan**. `M_*` variables are
  scratch manifest results, not target receipts. No live native content is
  placed in a plan, snapshot, backup, conflict file, or diagnostic.
* `local_manifest_read ROOT` validates format-1 state and actual owned
  native bytes; `local_inventory`, `local_selected`, `local_pattern`, and
  `local_exclude_plan` are shared helpers. Call preflight first to initialize
  the inventory and target. A consumer may filter `L_WANT` to a role subset
  and replan, but must repeat all preflight checks before publication.
* `local_migrate TARGET PROVIDERS [DRY]` is the explicit cleanup operation;
  `DRY` is exactly `0` (default) or `1`. It preflights **every** proposed
  change before removal and repeats full preflight before each leaf removal.
  It removes only proven eligible leaves, retaining original legacy
  snapshots, provenance, directories, and exclusion bytes in place.
  Interruption/removal failure reports nonzero `PARTIAL`, never rollback or
  installation success. Stop other writers and inspect the named paths and
  retained metadata manually before retrying. There is no live-content
  recovery copy or inferred ownership of a remaining leaf.
* `local_exclude_apply TARGET PROVIDERS [DRY [check|migrate]]` replans and
  revalidates, then publishes only the exclude file with a same-directory
  private stage and rename. Real apply requires an **already valid owned
  local manifest and all requested actual native leaves**; fresh preflight
  is not an installation and cannot be passed off as one by calling apply.
  A byte-identical exclude is not rewritten. Dry-run does not create a
  stage, lock, state directory, or any other file. This is an existing-owned
  attachment primitive: `.5` still owns fresh adapter/state publication,
  routing receipt emission, role selection, and compatibility CLI wiring.

**Implemented local format 1.** The six singleton LF-terminated header
lines are, in order, `format=1`, `scope=local`,
`worktree_root=<physical-root>`, `core_root=<canonical-absolute-root>`,
`core_api=1`, `providers=<set-or-none>`. Adjacent `created`/`baseline`
pairs follow. As with the implemented global HOME-relative format, local
native record paths include their native prefix, but are **repo-relative**:
for example
`created=codex:.codex/agents/domestique-codex-local-implementer.toml:<sha256>`.
Only the six exact local table leaves are allowed. Either role subset is
valid; every listed provider must have at least one pair. `none` has no
native pairs. Digests are 64 lowercase hex characters, creation digest and
current generated baseline are distinct metadata, and the live leaf must
match its baseline. Byte equality without `created` is not ownership.
Raw-byte validation precedes line parsing (including reused global metadata
parsers), so Bash cannot silently discard NULs into apparent ownership.
Parsing also re-emits and byte-compares the manifest, rejecting truncated
lines, unknown/duplicate keys, unpaired records, paths outside the inventory,
root mismatches, and invalid provider sets.

The state-tree inventory currently allows only `manifest`, optional
`routing/`, and the provider receipts specified below, validated against
the corresponding native records in manifest order. Missing receipts are
not invented: `.5` decides installation/routing completeness. Unknown
private entries (including not-yet-supported Beads or recovery formats)
refuse, even with force. `.6` must extend bounded metadata validation and
exact subtree accounting before its proven-owned `.beads/` subtrees can be
accepted; this checkpoint cannot hide `.beads/` wholesale or treat mere
presence as ownership/readiness.

**Legacy evidence and limits.** Main's snapshot-format-1 manifests and
draft #11's per-provider layout are parsed, not sourced. Claude snapshots
provide no whole-leaf creation authority and therefore cannot authorize
automatic removal. Codex's explicit `guest-excludes` native entries and
Copilot's immutable `created-files` are creation records, separately from
their pristine bases. A mode file, if present, must be exactly `guest\n`.
Absent mode is only a classification of historical normal evidence, never
permission for normal writes. Normal root blocks remain blockers unless
whole-leaf creation is recorded and the **entire leaf** equals its
marker-wrapped baseline. There is no block-stripping authorization for a
file containing host text. Unmarked, unrecorded host policy is not a
collision. Edited, adopted, indexed, symlinked, malformed, or ambiguous
legacy assets require metadata-only manual resolution. The manifest and
creation records are trusted owner-controlled provenance, not a defense
against an owner maliciously forging all their own records.
Legacy manifests, provider/mode records, and creation evidence must be
NUL-free and LF-terminated before parsing. Policy marker inspection also
rejects NULs; an unmarked host policy need not have a final LF.

**Shared exclusion policy.** Git's actual NUL-delimited worktree listing is
read once per plan with checked status; every physical worktree and common
directory is verified. The new block is bounded by
`# BEGIN domestique private (format=1)` / `# END domestique private` and
contains only the union of exact root-anchored native patterns and
`/.domestique-private/`. Ownership comes from current worktree manifests,
not a home registry, lease, or the mere presence of a pattern. Every existing
block pattern needs an actual owning attachment. All candidate patterns
are checked against every worktree: same-path owned attachments are allowed;
an existing/indexed host collision, missing/unreadable/malformed state,
unavailable worktree, or unknown shared block refuses the whole operation.
Index checks include every repo-bounded ancestor object of native, legacy,
and private-state paths, even if a regular file, symlink, or gitlink has
been deleted on disk. Ancestor directory contents are not ancestor objects:
unrelated tracked siblings remain allowed. All index pathspecs are literal.
Other attachments' exact patterns are retained. Literal Git metacharacters
are escaped by `local_pattern`. `local_ignore_effective` checks Git's real
ignore precedence using a read-only synthetic global exclude; conflicting
repository `.gitignore` negations refuse instead of promising privacy that
`info/exclude` cannot provide. Existing info-exclude negations can also cause
a conservative refusal. Relevant ancestor ignore files are checked for
readability and symlink collisions, never edited.

Unknown preexisting rules outside managed blocks stay in place and are never
adopted or deleted. The line-based exclude API refuses NULs or a missing
final LF before any write, rather than lossily reconstructing host text;
other host bytes (including non-UTF8 bytes) are preserved exactly.
Well-formed legacy blocks containing only known exact
native rules (and the old exact Codex metadata tree) are preserved unchanged,
not claimed as new ownership. Broad legacy `.claude/`, `.beads/`, or other
unknown rules **inside legacy blocks refuse**: this checkpoint cannot prove
all retained recovery assets and therefore does not narrow them automatically.
Resolve those old blocks manually only after accounting for retained assets
and every linked worktree. No shared common-dir lock can promise visibility
isolation for future host files at the same relative path. These checks prove
the current inventory only; stop other writers, and rerun accounting after
worktree/state changes. Publication is bounded shell revalidation, not an
atomic transaction against hostile same-user filesystem mutation.

`bash test/local-preflight.sh` exercises these functions in physical temporary
HOME/core/repos, including actual legacy installer fixtures and linked
worktrees. No network, model/native client, real-home install, or successful
local CLI discovery is asserted.

### Scope and command line

* `domestique.sh --global [--platform P]` installs or updates only personal
  defaults and the private core. It writes no repository. `--global` is the
  only spelling that may write a home/config root.
* `domestique.sh --local TARGET [--platform P]` creates or refreshes optional
  private project adapters in `TARGET`; it never installs a missing global
  core. The old `domestique.sh TARGET` spelling is retained as exactly this
  local operation. The old selector-less invocation with no target remains
  local `.` (not global), so old bare and positional invocations can never
  unexpectedly write home.
* For local scope, `.` and relative targets are resolved against the invoking
  directory to one physical (`pwd -P`) directory before preflight; that exact
  directory must be the Git worktree top-level. A missing target, a non-Git
  target, a subdirectory rather than its top-level, or a symlinked
  parent/destination is rejected before writes. There is no repository crawl.
  `--global` takes no target; combining it with `--local` or a positional
  target is a usage error.
* `--platform` has exactly seven canonical provider-set values: `claude`,
  `codex`, `copilot`, `both` (Claude+Codex), `claude-copilot`,
  `codex-copilot`, and `all` (all three). It is available in either scope.
  A fresh selector-less adapter install selects `claude`; a later
  selector-less adapter install uses that scope's persisted provider union.
  Provider selection never comes from scanning arbitrary configuration or
  installed executables.
* `--guest` is accepted only as a deprecated, warning-producing no-op alias
  for this private contract; it does not select a legacy destination or alter
  scope. `--no-guest`, and `--guest --no-guest`, are rejected before any
  filesystem access. There is no guest-to-normal conversion.
* `--local TARGET --with-beads --state-only` is the one recognized
  state-only spelling; it conflicts with `--platform`. All valid explicit
  local initialization requests, with or without state-only, currently
  **exit 1 before any writes**, including dry-run and combined profile setup.
  No attachment or ready/failed record is fabricated. Bare/positional or
  global `--with-beads` is a usage error. No bd command runs. Model, MCP,
  tool, role and profile modifiers are not accepted.
* `--dry-run` performs scope, ownership and core-compatibility preflight
  without destination writes. Current private refresh has **no merge path**.
  `--force` never overrides edits, tracked/unknown ownership, unsafe paths,
  ambiguity or legacy authority. The
  updater accepts and forwards the same explicit scope and selector. An
  updater invocation without a scope remains local compatibility behavior
  (`TARGET`, or `.`), never global.
* `--uninstall --global` removes only positively owned global assets.
  `--uninstall --local TARGET` removes only that worktree’s positively owned
  attachment; old positional/bare uninstall remains local compatibility
  behavior. `--purge-beads` is local-uninstall-only and requires successful
  ownership, initial unchanged DB/context/export hashes and no remaining provider.
  Global
  uninstall never finds, crawls, or deletes local profiles/state.
* The parser rejects, before any write, conflicting scopes/targets,
  `--uninstall --with-beads`, `--purge-beads` without local `--uninstall`, global
  purge, state-only outside `--local TARGET --with-beads`, and all unsupported
  role/profile/model/MCP/tool modifiers.

### Private root, core, and native assets

The canonical private root is
`${DOMESTIQUE_HOME:-${XDG_STATE_HOME:-$HOME/.local/state}/domestique}`.
`DOMESTIQUE_HOME` and `XDG_STATE_HOME`, when supplied, must be absolute,
non-symlinked paths owned/writable by the invoking user; relative values,
unreadable roots, and symlink escapes fail closed. `$HOME` is likewise the
only basis for the native personal paths below (tests set a temporary HOME).
The installer creates no alternate discovery registry and does not depend on
blind symlinks. A relocation is an explicit new root installation; existing
adapters continue to name their old root and stop rather than guessing.

```
<private-root>/
  releases/<release>/API              # format=1, core_api=1, release=<release>
  releases/<release>/SHA256SUMS
  releases/<release>/roles/{orchestrator,implementer,reviewer,goal}.md
  bin/resolve-core                    # API-1 global-core-owned resolver
  active                              # one line: release=<release>
  state/global-manifest               # format=1 ownership record
```

Core API 1 is frozen. `<release>` is exactly
`r-` followed by 64 lower-case hexadecimal characters; it is the SHA-256 of
the exact UTF-8 bytes of `SHA256SUMS`, and is used only as a single path
component. `SHA256SUMS` has exactly four LF-terminated lines, sorted by these
literal relative paths: `roles/goal.md`, `roles/implementer.md`,
`roles/orchestrator.md`, `roles/reviewer.md`. Each line is
`<64-lowercase-hex><two spaces><path>\n`, where the digest is of that
allowlisted file's exact bytes. `API` has exactly the three LF-terminated
lines `format=1`, `core_api=1`, and `release=<release>`, in that order.

Publication first stages a new, private, non-symlinked release directory,
writes and verifies all four role files plus `API` and `SHA256SUMS` (six files
total), then exclusively claims, populates without clobbering, and validates the final release directory.
After preparing compatible native assets and state, it atomically replaces
`active` with a complete temporary file in `<private-root>`. It never promises native
atomicity across the separate provider roots. A failed stage leaves no active
pointer change and is reported for manual inspection; releases are never
silently garbage-collected or deleted while referenced by an active pointer
or manifest. Native adapters are staged and ownership-recorded at their own
root; their commit pointer/manifest write is last, after their core check.
Thus an old API-1 adapter and old active API-1 release may coexist during a
failure. An incompatible API is blocked for an explicit manual migration,
not generalized schema negotiation.

Every adapter body contains the literal shell-quoted absolute core root and
calls `bash <private-root>/bin/resolve-core`, rather than
describing an abstract resolver. This API-1 helper is a global-core-owned
asset outside immutable role releases and is not a selectable provider. Its
core-loading interface is `resolve-core bind ROOT ROLE [RELEASE]`, which writes the
validated release identity alone to stdout, and `resolve-core read ROOT ROLE
RELEASE`, which writes the validated named role bytes alone to stdout. `ROLE`
is allowlisted and `RELEASE`, when supplied, prevents any `active` read.
`bind` without a release reads `active` once; both commands validate the
absolute canonical non-symlinked root, API 1, release identity, ordered
`SHA256SUMS`, and all four role digests before stdout. Failures write only a
diagnostic to stderr and no stdout. The workflow keeps that identity only in
ephemeral context and passes it explicitly to every role load. A goal first
binds then reads both orchestrator and goal with that same release; delegated
implementer/reviewer loads receive the binding and must not resample active.
The exact handoff is a `DOMESTIQUE_BOUND_RELEASE=<verified release identity>`
field in the parent's task brief. Execute the emitted fenced Bash block with
`bash -c`, the block as command, `--` as argument zero, and that literal
field value as argument one. The block creates only an ephemeral shell
parameter from that argument, never an inherited environment default.
Missing/empty/malformed delegated arguments fail before role output; only a
NEW bootstrap skill may omit the argument. Retain its printed binding in
workflow context and supply it to every subsequent skill and delegated load.
All wrappers load orchestrator policy; goal also loads goal at the same binding.
Missing helper, unreadable bound resources, or incompatible helper/role API
stops, never executing arbitrary paths or embedded old policy. `.3` installs
or stages this helper with core compatibility checks, not as a role/provider.
The same helper also provides `.5`'s `router-api`/`route` and `.10`'s
`beads-guard` interfaces specified above; these do not change Core API 1 or
the immutable six-file release inventory.

Global install owns only manifest-listed leaves at these provider-native
locations:

| Provider | Global skills (exact directory/trigger) | Global roles (exact path/ID) |
| --- | --- | --- |
| Claude | `$HOME/.claude/skills/domestique-claude{,-decompose,-goal}/SKILL.md`; `/domestique-claude`, `/domestique-claude-decompose`, `/domestique-claude-goal` | `$HOME/.claude/agents/domestique-claude-{implementer,reviewer}.md`; `domestique-claude-implementer`, `domestique-claude-reviewer` |
| Codex | `$HOME/.agents/skills/domestique-codex{,-decompose,-goal}/SKILL.md`; `$domestique-codex`, `$domestique-codex-decompose`, `$domestique-codex-goal` | `$HOME/.codex/agents/domestique-codex-{implementer,reviewer}.toml`; `domestique-codex-implementer`, `domestique-codex-reviewer` |
| Copilot | `$HOME/.copilot/skills/domestique-copilot{,-decompose,-goal}/SKILL.md`; `/domestique-copilot`, `/domestique-copilot-decompose`, `/domestique-copilot-goal` | `$HOME/.copilot/agents/domestique-copilot-{implementer,reviewer}.agent.md`; `domestique-copilot-implementer`, `domestique-copilot-reviewer` |

The normal-language wording is provider-scoped (“use Claude Domestique”,
“use Codex Domestique”, or “use Copilot Domestique”); a goal workflow is
requested only by its explicit `*-goal` trigger. There is no generic
`domestique` alias in v1. This modest namespace cost is deliberate: Copilot's
project discovery of `.claude/agents` and Codex's discovery of
`$HOME/.agents/skills` cannot collide with a provider-qualified ID. Existing
legacy unqualified names are retained only in an explicitly blocked or
reconciled migration and are never silently shadowed.

The renderers write literal, shell-quoted paths from the resolved roots; they
do not interpolate shell syntax, expand a path embedded in generated content,
or render a user config wholesale. Global install does not modify global
CLAUDE/AGENTS instruction files, runtime settings, MCP registration,
authentication, shell startup, plugins, or project files. It preflights every
parent/leaf, including ownership, symlink, collision, and permissions, before
writing. Created-file provenance is recorded separately from merge bases:
byte-identical pre-existing files are not owned merely because they equal an
emission.

Each local attachment has exactly one state root:
`<repo>/.domestique-private/`. It is an untracked, private, non-symlinked
directory at the validated physical worktree top-level, never a directory
under `<private-root>`. It contains every local manifest, routing receipt,
created-file provenance, Beads record, and recovery diagnostic; there is no
user-root local registry, registration, lease, or local receipt copy. A local
operation may read and validate the global core and its active release, but
never writes `<private-root>` (including `state/global-manifest`). Provider
native adapter paths are fixed, validated repo-relative paths, not discovered
by scanning a provider directory. Local adapter leaves have distinct IDs and
never rely on duplicate-name precedence:

| Provider | Local roles (exact path/ID) | Private receipt |
| --- | --- | --- |
| Claude | `<repo>/.claude/agents/domestique-claude-local-{implementer,reviewer}.md`; `domestique-claude-local-implementer/reviewer` | `<repo>/.domestique-private/routing/claude.receipt` |
| Codex | `<repo>/.codex/agents/domestique-codex-local-{implementer,reviewer}.toml`; `domestique-codex-local-implementer/reviewer` | `<repo>/.domestique-private/routing/codex.receipt` |
| Copilot | `<repo>/.github/agents/domestique-copilot-local-{implementer,reviewer}.agent.md`; `domestique-copilot-local-implementer/reviewer` | `<repo>/.domestique-private/routing/copilot.receipt` |

`state/global-manifest` and
`<repo>/.domestique-private/manifest` are line-oriented format-1 files with
one `key=value` per line, UTF-8 values with no newline or `=`. The global
keys are `format`, `scope=global`,
`core_root` (absolute canonical private-root path), `core_api=1`,
`providers` (one of the seven nonempty canonical sets above), and repeated
`created=<provider>:<native-relative-leaf>:<sha256>` and
`baseline=<provider>:<native-relative-leaf>:<sha256>`. Local keys are
`format`, `scope=local`, `worktree_root` (absolute physical root),
`core_root` (absolute), `core_api=1`, `providers`, repeated `created`, and
repeated `baseline=<provider>:<native-relative-leaf>:<sha256>`; its
`providers` is either one of those seven sets or the literal `none`, which is
currently valid for retained-after-removal state (successful state-only
initialization is blocked). Native
relative leaves are relative only to that provider's bounded native root
shown in the tables; they must be normalized, nonempty, and contain neither
`..` nor a symlink. Root fields (`core_root`, `worktree_root`) are absolute canonical paths; `beads_path` and `beads_created` are project-relative as defined below.
`created` is the sole native-adapter creation provenance; a pristine byte match never
creates ownership. `baseline` describes generated bytes only and is not
ownership evidence.

#### Implemented global format, preflight, and recovery

Global format 1 uses the five singleton header lines above, in that order,
followed by adjacent `created`/`baseline` pairs for each leaf. Digests are
exactly 64 lowercase hexadecimal characters. `created` retains the digest at
successful creation; `baseline` is the current **embedded generated** digest,
not a snapshot of live bytes. A baseline match without a `created` record
never grants ownership. There are no native content snapshots, three-way
merges, backups, conflict files, timestamps, or local registry in this scope.
Edited native leaves refuse the entire install/update, including `--force`,
with path/metadata-only diagnostics; they are neither copied nor overwritten.
Global uninstall instead retains the whole edited provider as described in `.11`.

For global records only, native leaves are HOME-relative with exact prefixes
from the table (`.claude`, `.agents`/`.codex`, `.copilot`); Codex additionally
owns `.agents/skills/domestique-codex-goal/agents/openai.yaml`. Ordering is
Claude, Codex, Copilot; within each, base/decompose/goal skills, implementer/
reviewer agents, then Codex goal metadata. The reserved non-provider `core:`
namespace is relative to `core_root` and allowlists only `bin/resolve-core`,
`active`, and the six leaves of each complete `releases/r-<hash>` release.
Core records follow native records, retaining insertion order across upgrades.
The manifest itself and its recovery journal are reserved state, not recursive
`created` entries. No unknown keys, duplicates, incomplete releases, alternate
paths, extra core entries, malformed newline termination, or root mismatches
are accepted. Existing root without valid state refuses even if empty.
The manifest is trusted invoking-user-owned installation state, not a
cryptographic defense against an owner maliciously rewriting all provenance.
Installed helpers are never executed during preflight: the embedded trusted
helper validates existing and staged API-1 releases.

Paths must be absolute and already canonical (no `.`/`..`, repeated/trailing
slash, symlink component, ASCII control character, or `=`). Spaces, both
quote characters, and backslashes are literal. HOME is the sole native-root
basis; an alternate core cannot equal/contain HOME, enter any of its four
native roots, or enter a Git worktree. Destination ancestors are inspected
by exact path, not by scanning provider directories. Existing destination
roots/leaves must be invoking-user-owned, owner-readable/writable and not
group/world-writable. System ancestors may be root-owned; shared writable
system ancestors must be sticky. Existing permissions are never changed.
New directories/files use a private umask. Temporary rendering is private,
outside HOME/core/worktrees, and contains only embedded generated source.
An exact no-op does not rewrite files or metadata; dry-run performs the real
preflight and staged validation without destination writes.

Publication uses portable Bash, Git and ordinary filesystem utilities, not
runtime Python or an undocumented fsync utility. Its **bounded durability**
is complete checked writes plus same-filesystem renames and a recovery journal,
not a guarantee against power loss or a lying filesystem. Portable shell
cannot promise ordered durable fsyncs across these native roots. A pending
journal is created exclusively by hard link and acts as the cooperating-writer
lock; there is no daemon, timeout takeover, or stale-lock deletion. Paths and
digests are rechecked before publication and before replacement. New leaves
are linked exclusively from same-directory private stages, never overwritten
or adopted if they appear after preflight. This is not protection against
hostile simultaneous filesystem mutation by the same user; stop other writers
before recovery. The core release is rendered and validated in private staging.
Publication exclusively claims the absent final release directory with `mkdir`
(not `mkdir -p` or directory `mv`); an existing/racing directory or symlink is
never reused, populated, or adopted, even if empty or identical. Only the six
fixed allowlisted generated files are populated with no-clobber creation while
the release is still unadvertised. The freshly emitted API-1 helper validates
the final non-symlink release path and a recursive stage comparison checks its
exact inventory, after population, immediately before active replacement, and
before clearing recovery journals. Helper/native assets are prepared before
the manifest, and active switches last. Older immutable releases are retained,
without GC.

On a publication failure the command exits nonzero with `PARTIAL`, not a
successful empty/default state. The old active release remains usable unless
the final active switch already completed, in which case the new compatible
release is usable. Reserved recovery files are:

* `state/pending`: complete prospective format-1 manifest; **intent, not
  proof that an absent leaf was created**.
* `state/previous`: the validated prior manifest re-emitted from metadata, or
  the single line `fresh-install` (never copied live native content).
* `state/published`: LF-terminated `release-claimed=<release>` (exclusive
  directory creation succeeded, population may be incomplete), `release=<release>`
  (population and final-path validation completed), and
  `published=<namespace>:<leaf>:<generated-sha256>` entries, appended only
  after the corresponding publication command succeeds.

A rerun with pending state refuses read-only. Recovery is deliberately manual,
not an automatic merge/adoption path: retain these records; compare only
digests and metadata, never copy edited native content into recovery files.
For an upgrade, restore positively owned changed leaves from the trusted old
installer's emitters **only after** confirming they still match the recorded
published new digest; restore the prior manifest and old active pointer, and
retain complete validated releases with their provenance. Alternatively,
finish the intended installation using its trusted source after checking
every completed leaf against pending/published metadata. For fresh installs,
only completed publication records establish creation; an unrecorded or
divergent destination requires independent human ownership confirmation,
never an equality-based guess. A claimed but incomplete release stays
unadvertised and must be reconciled manually; a failed directory claim records
no ownership of the collision. Remove journal/stage artifacts only after
reconciling that exact transaction, then retry. If a command failed before
the journal was complete, or a crash interrupted command/log ordering, stop
for manual ownership reconciliation rather than inferring success. Unknown
destinations and user edits must remain untouched. The `.3` publication format
has no automated recovery command; `.11` adds global uninstall with separate
removal journals and the fail-closed recovery limits described above.

An explicit install adds its selected providers to that scope's persisted
union; a bare rerun uses that union. Scoped uninstall removes only requested
providers from its own scope, leaving every other provider and the other
scope unaffected. A local `providers=none` bare rerun validates retained
attachment metadata and installs no adapter; it is not Beads initialization.
Missing state defaults only to a fresh requested install
when every destination is absent. Missing, corrupt, conflicting, or
out-of-root state with an existing destination is an error; known legacy
names enter the explicit legacy classification path, and unknown files do
not. Neither case scans executables, guesses provenance, or repairs state.
The installer may add the exact `.domestique-private/` tree and owned native
leaves to the private exclude mechanism only after linked-worktree accounting
proves ownership. Exact positively owned `.beads/` subtree exclusion remains
future blocked work. Neither permits excluding whole provider directories,
`.beads/` wholesale, or any unknown/host state.

### Loading, routing, and local capability metadata

Global skills load common orchestrator policy before choosing native IDs. Routing
is selected separately for the `implementer` and `reviewer` role of each
workflow request/session:

* A user deliberately chooses **global-only** or **local-required** in the
  workflow prompt. Global-only invokes the same-provider global role and is
  not an automatic recovery from any local error.
* A normal request with no explicit choice uses a valid current-worktree
  `<repo>/.domestique-private/routing/<provider>.receipt`, if present, for
  the requested role; if there is no local request or local adapter/receipt
  evidence for that role, it maps that role to global-only. A valid receipt
  listing only implementer does not require reviewer to be local (or vice
  versa). Requested-role adapter evidence makes that role local-required.
  A present broken/unreadable receipt stops rather than broadening to global.
* Local-required validates the matching provider receipt and its
  `role=<exact-local-ID>` for the requested role, then discovers that exact
  native ID after its reload boundary and confirms required read/shell
  capability and native project trust. Missing, unreadable, corrupt,
  untrusted, unavailable, colliding, or incompatible receipt/role stops
  fail-closed; it never selects the global role or broader tools.

A receipt is private, nonsecret, non-symlinked file at exactly
`<physical-worktree-root>/.domestique-private/routing/<provider>.receipt`.
It has exactly these LF-terminated lines, in order: `format=1`,
`worktree_root=<absolute physical root>`, `provider=<provider>`,
`core_root=<absolute canonical private root>`, `core_api=1`, and one
`role=<exact provider-qualified local ID>` for each installed role. The
physical root and provider must match the current worktree/provider; duplicate,
unknown, missing, or mismatched fields stop local-required routing. At
workflow start the orchestrator records the
provider-and-role map for that invocation in its ephemeral session/workflow
context, not in a preference, global registry, native configuration, or new
persistent model. Once a role is bound local-required, a receipt or adapter
disappearing mid-run stops that role; it is not reinterpreted as global.
If all local files and evidence are removed before a new default invocation,
and the user supplies no explicit local choice, that invocation is
indistinguishable from never-installed and may map global-only. No central
registry claims to remember otherwise.

| Provider | Native metadata fields (emitters are minimal) | Core declaration location / source fact | Reload and trust |
| --- | --- | --- | --- |
| Claude | documented agent `name`, `description`, `tools`, `mcpServers`; Markdown body | body instruction declares `core_root`, API, role, and resolver; [subagents](https://code.claude.com/docs/en/sub-agents), [skills](https://code.claude.com/docs/en/skills) | restart/reload as documented; project/server trust must be confirmed |
| Codex | documented agent TOML fields and `mcp_servers` only | `developer_instructions` prompt-body value contains the declaration/resolver, not a new TOML key; [subagents](https://developers.openai.com/codex/subagents/), [skills](https://developers.openai.com/codex/skills/) | start/reload a new session and confirm native trust/capability |
| Copilot | documented agent frontmatter `name`, `description`, `tools`, `mcp-servers`; Markdown body | body instruction declares the protocol; [CLI reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference) | documented reload/discovery plus project/server trust confirmation |

No version threshold is asserted here; .8 final acceptance records limited observed
versions and precise native execution limitations. Domestique emits minimal adapters,
accepts no arbitrary MCP
or secret CLI input, and does not implement a YAML/TOML parser or universal
MCP interface. User edits remain native configuration. An unsupported
scaffold/config request is explicitly unsupported; preflight does not claim
to universally detect a client silently ignoring unknown keys.

The adapter is a complete provider-native role configuration plus an explicit
core-reading instruction; no provider is claimed to merge agent fields.
Deliberate full local prompt forks are user-maintained, non-core-referencing
files outside this automatic upgrade contract. They must be marked as such,
are not refreshed by a core update, and cannot hide that limitation. Shared
guardrails, including explicit goal authorization, sequential fresh-context
review, no push/merge, and private landing, live in the core. “Independent
review” means a fresh, separate reviewer context; it does not promise a
stronger or different model/vendor. Claude retains native Anthropic defaults,
Codex native OpenAI defaults, and Copilot has no Domestique pin. A user may
request a supported role/vendor model for one session only: unavailable
requests stop with no substitution; otherwise native defaults apply only when
no request was made. Nothing persists that request or promises to override
another client's native file/session setting.
Copilot runtime may fall back if a requested model or effort is unavailable;
the stop/no-substitution instruction is not hard vendor or billing enforcement.
Avoid Auto when vendor selection matters.

Local MCP/tool data stays in a complete local native adapter, subject to the
installed client version and its trust UI:

* Claude uses its documented `mcpServers` and `tools` agent fields.
* Codex uses documented TOML `mcp_servers` and the documented parent
  inheritance/override semantics of a complete custom agent; duplicate skills
  are not merged.
* Copilot uses documented `mcp-servers` and `tools` fields. Its provider
  precedence/field inheritance is not assumed portable.

An already authorized project server may be inherited where that native
runtime actually supports it; a project difference alone does not require a
local profile. Server registration/authentication and tool filtering are
separate: a `tools` list cannot make an undeclared or unavailable server
accessible, widen permission, autoapprove trust, execute/install a server, or
authenticate it. Credentials remain in native runtime auth/environment and
are never emitted, snapshotted, logged, or put in Beads. Requests for a field
outside these native fields must be checked against the installed client's
documentation. The installer rejects unsupported CLI modifiers; it does not
detect native versions or parse/validate arbitrary edited YAML/TOML schemas.
Missing native confirmation stops delegation rather than silently broadening
tools. New-scope generated cores and adapters contain no credentials. If an owned
native adapter differs byte-for-byte from its recorded pristine baseline,
Domestique leaves that adapter wholly untouched, including with `--force`,
and stops automatic refresh for it with metadata-only/manual-migration
guidance. It never copies, logs, serializes, backs up, or creates `.bak`/`.new`
artifacts from user-edited native metadata. A compatible global core-only
update may proceed without rewriting those local adapters. This supersedes
the legacy merge/snapshot assumptions above for the new scope; full prompt
forks remain user-maintained and are never silently upgraded.

The documented locations/fields are based on the official provider references
recorded in the epic: [Claude subagents](https://code.claude.com/docs/en/sub-agents),
[Claude skills](https://code.claude.com/docs/en/skills),
[Codex subagents](https://developers.openai.com/codex/subagents/),
[Codex skills](https://developers.openai.com/codex/skills/), and the
[Copilot CLI reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference).
Native schemas, discovery, precedence, and trust behavior remain
version-sensitive; documenting this loader contract is not native runtime
proof.

### Private lifecycle, legacy migration, and Beads

No local operation edits tracked host/root policy, `.gitignore`, index,
hooks, or provider settings, and no force flag takes those over. Preflight
classifies each exact leaf as tracked, owned-created, adopted, unknown,
legacy-normal, legacy-guest/mixed, or malformed. Provenance and a pristine
base have different authority: only positively owned, unchanged, untracked
legacy leaves may be safely cleaned up. Tracked, customized, unknown,
ambiguous, absent-marker, corrupt-marker, or conflicting legacy policy is a
blocker with a manual recovery diagnostic; it is never an adoption fallback.
An active incompatible old normal policy is not reported as “migrated.”
Current removal retains edited providers in place without making backups;
historical recovery evidence must be manually accounted for, never copied or
silently exposed. Removing global core warns that linked local
adapters will stop on their required-core check; it does not repair them by
fallback.

Global definition installation and project Beads initialization are distinct.
Loading a skill creates neither a database nor Git artifact. Current explicit
local `--with-beads` uses .6's qualified initializer and refuses unsupported contexts;
.10's unconditional refusal is historical. The structural runtime guard separately
classifies eligibility without reading database contents or invoking bd. The only
Beads location this contract uses is the literal repo-relative `.beads/`
(`beads_path=.beads` in the local manifest); it does not auto-discover an
arbitrary Beads storage location or assume a resolver/environment route.
Tracked, shared, unknown, symlinked, or otherwise unsafe `.beads/` stops for
an explicit user decision. In particular, an already existing host
`.beads/`, even if it looks initialized, is unowned and is neither hidden nor
adopted.

#### Historical proposed Beads lifecycle acceptance (superseded by .6 and .7)

Everything in this subsection is future acceptance, including state-only
success, Beads manifest fields, retained database ownership and purge. The
current parser rejects these fields; do not create them manually or treat an
existing host database as owned. No eligible private export exists today;
future export still requires explicit authorization and proven eligibility,
never force-adding or committing private/personal state.

**Future `.6` contract, blocked:** for an absent eligible `.beads/`, a
supported backend must first be proven to preserve exact private Git policy,
host files and home state. The originally proposed
`bd init --stealth --skip-agents --skip-hooks --non-interactive` is **not safe
on verified 1.1.2** and is not currently run; see the pinned `.10` blocker
above. Only a genuinely verified supported equivalent may eventually run.
The future local manifest records
the path creation separately from database success as
`beads_path_created=by-init:<attempt-id>`: a successful verified database
initialization writes `beads_status=ready` and repeated
`beads_created=<normalized-relative-subtree>:<sha256>` provenance for only
the initialized, positively owned `.beads/` subtrees. It records the init
command/version and a readiness check sufficient to verify that database,
but never a whole user or project database snapshot. Presence of `.beads/`
alone is never readiness or ownership evidence.

If initialization fails, the private state root records
`beads_status=failed`, that attempt identifier, and a nonsecret recovery
diagnostic, but no `ready` record or successful `beads_created` provenance.
It reports non-success and requires manual recovery/reclassification; a
rerun or purge must not infer ownership merely from the resulting `.beads/`
directory. `ready` means a current verified initialized database; `retained`
means formerly ready, still provenance-protected after the last adapter is
removed, and not a claim that a fresh readiness check succeeded; `failed`
means no successful initialization claim. `bd setup` never runs. Each
project/worktree has its own private state—there is no global queue—and
private state is never staged/committed. A user may authorize source commits;
Domestique never turns that into a push/merge authorization.

State-only initialization creates `<repo>/.domestique-private/manifest` with
`providers=none` and no adapter `created` leaves, then follows the same
Beads rules. A successful state-only rerun verifies its recorded ready
or retained subtrees and writes `ready` only on success; it does not add
adapters. Local uninstall without `--purge-beads` removes only eligible owned
adapters and its matching receipt, while retaining the private manifest,
provenance/recovery evidence, and Beads state; after the last adapter it
records `providers=none` and changes a formerly ready Beads record to
`beads_status=retained`. With
`--purge-beads`, it may remove only recorded, untracked, unchanged
`beads_created` subtrees whose last successful record is `ready` or
`retained`, and then removes their provenance/status record. It refuses purge
for `failed`, missing, modified, or unowned state. If that leaves no adapters,
Beads records, or recovery evidence, it may remove the positively owned
private state tree itself; otherwise it retains it. Thus neither an adapter
removal nor a successful/failed rerun converts existing host `.beads/` into
owned state.

### Acceptance matrix and remaining runtime gates

Using a temporary HOME and two disposable Git repositories (including a linked
worktree fixture where applicable), the contract requires the following. The
final acceptance evidence below distinguishes executable offline coverage from
native observations and blocked runtime gates; this table alone is not a pass:

| Fixture/action | Required observation |
| --- | --- |
| Global install, then two untouched repos | each provider’s documented global skills/agents are discoverable after its documented reload/restart; neither repo gains files |
| Claude and Copilot local discovery, plus Codex user skills | all provider-qualified global/local IDs coexist; Copilot discovery of `.claude/agents` and Codex discovery of `$HOME/.agents/skills` produces no collision or same-name precedence dependency |
| One local role with MCP/tools, one without | only the selected repo routes to its distinct local ID and sees declared native metadata; no cross-contamination |
| Receipt selects reviewer, then implementer | the global provider skill records each role's ephemeral route and routes only to the exact discovered, trusted `domestique-<provider>-local-<role>` ID |
| Local attachment operation | install/rerun/uninstall/receipt/lease activity leaves `<private-root>` byte-identical; all local records are under `<repo>/.domestique-private/` |
| Core-only global update | a newly loaded global and core-referencing local role reads the new compatible core with no local metadata rewrite |
| Core publication interrupted before active-pointer replacement | `active` remains the prior complete release; a staged release is not selected, and recovery reports it without deleting it |
| Missing/incompatible core, denied trust, or required unavailable tool | role stops with a specific diagnostic; no global/broader-role fallback and no server auth/execution |
| Tracked/unknown/corrupt legacy state and two worktrees | preflight/dry-run are byte-identical; malformed state or shared exclude ambiguity fails closed |
| `--local TARGET --with-beads --state-only` | `providers=none`, no adapter leaves, and only verified ready `.beads/` subtrees receive exact provenance; existing unowned/host `.beads/` refuses rather than being hidden or adopted |
| Missing required receipt or local evidence; local receipt/adapter disappears mid-run | required role stops without a global/broader fallback; an explicit global-only prompt remains the only global choice after local failure |
| Owned adapter edited with an inline-secret sentinel | divergence leaves the live adapter byte-identical and emits no backup, conflict, `.new`, log, or serialized copy containing the sentinel |
| Scoped uninstall/purge | only positively owned untracked selected leaves are removed; retained recovery/Beads protections and other scope remain |

This is the retained full contract, **not a native execution checklist marked
complete**. Offline coverage and strictly bounded native observations are recorded
separately in final acceptance. Role execution, MCP/tool/trust, model/goal
sessions and agent-driven database workflows remain unverified. Qualified native
initializer/wrapper/cleanup evidence does not constitute native agent execution.

### Final acceptance (2026-09-13)

**Qualified preview, not production-ready across all runtimes. Final acceptance
is pending after the runner safety checkpoint.** The completed results below
are dated prior evidence from 2026-09-13, using runner SHA256
`4cdcbd5f2e2c9a3eecd6d4d16a76968320da9bd4f60d574b159452818d9f2d45`;
they do not certify the updated runner or complete .8/the epic.
That acceptance used the checkout based on `20b6fe8` on `epic/hq-b3q`; neither `main` nor
draft #11 has been updated. Independent review is a separate required gate:
the implementer does not mark its own work review-PASS or close .8/the epic.
Observed host/toolchain: **macOS 26.6.2 arm64**, `/bin/bash` **3.2.57**,
Python **3.14.6**, Apple Git **2.50.1**, ShellCheck **0.11.0**. Native client and
Beads versions below are observations, not minimum/universal support claims.

For a separately authorized exhaustive run, use
`python3 -B -W error test/acceptance.py --exhaustive --jobs 1 --total-seconds 43200 --suite-seconds 14400`
and, separately,
`python3 -B -W error test/acceptance.py --exhaustive --native-only --jobs 1 --total-seconds 43200 --suite-seconds 14400`
only after explicit non-model native consent. `--native` in place of
`--native-only` combines both groups with that same consent.
Default `python3 -B -W error test/acceptance.py` is labelled **QUICK** and selects
only `private-core.sh`, native-discovery/beads-native-context/acceptance/global-path/
local-index **unit** suites, `native-supervision-tests.py`,
`global-diagnostics-tests.py`, `beads-fixture-tests.py`, and
`beads-execution-tests.py` (synthetic/harmless production ownership probes,
not native qualification). No lifecycle,
historical or native operations run in QUICK. Syntax/lint includes per-file Bash syntax, warning-level ShellCheck
on source/tests/emitted resolver, and Python AST including the embedded
controller. EXHAUSTIVE alone selects the intact CURRENT and five pinned **b60feef**
HISTORICAL lists plus the new diagnostic unit suite and syntax/lint.
Native-only is never labelled complete offline acceptance. Logs/JSON are retained only in the printed private
`SESSION_ARTIFACTS`; disposable fixtures are cleaned up. No additional tools,
framework, CI service, model calls or performance framework are involved.

For an explicitly partial run, repeat `--suite CATEGORY:NAME`, for example:

```sh
python3 -B -W error test/acceptance.py --suite CURRENT:syntax-lint-ast-diff --suite CURRENT:private-core.sh
```

Only exact entries permitted by the existing mode/flags are selectable.
`CURRENT`, `HISTORICAL_FIXTURE` and `NATIVE` are literal categories; there is no
path/glob/regex/shorthand interpretation. Empty, unknown, duplicate, wrong-category
or unavailable-in-mode tokens are rejected before provenance, fixtures or launch.
`CURRENT:local-uninstall.py` needs exhaustive mode and explicit total/per-suite
budgets. `NATIVE:beads-cleanup.py` needs those plus `--native` or `--native-only`
and explicit non-model native consent; it is distinct from offline
`CURRENT:beads-cleanup.py`. Native-only excludes all offline scopes, including
syntax/lint. Exhaustive remains serial regardless of selection. The exact requested
category/name list and submission order follow caller order so cheap scopes can
precede expensive ones; QUICK `--jobs 2` can overlap execution and results may be
in completion order. No-selector manifests and order are unchanged.

Explicit selections always use `SELECTED_SCOPES_NOT_FULL_ACCEPTANCE` with
`full_offline_acceptance: false`, including selected-all and all-native-only runs.
Existing provenance, budgets and per-scope results remain in the report. Exit 0
means only selected work passed, not full acceptance; validated native blocker 2
and failure/incomplete 1 classifications are unchanged. Only the non-selected
`FULL_OFFLINE` / `FULL_OFFLINE_AND_NATIVE` labels can qualify for full offline
acceptance, subject to the existing completeness checks.
There is no automatic trusted reuse, report import/cache/resume trust or
coverage-union generation. Prior failed reports remain unchanged; any eventual
historical-plus-fresh coverage union needs independent attestation of exact runs,
source dependencies and tool-fingerprint limitations, and fresh native evidence.
This checkpoint neither completes .8 nor claims current full acceptance.

QUICK accepts positive finite `--total-seconds` (default/max **1200**) and
`--suite-seconds` (default/max **600**). EXHAUSTIVE requires both explicitly and
rejects `--jobs 2`; native flags require EXHAUSTIVE. Invalid combinations fail
before artifacts. No larger quick budgets silently select exhaustive coverage.
Reports include mode, exact requested coverage, jobs/budgets and progress.
QUICK exit 0 is `QUICK_SUBSET_NOT_FULL_OFFLINE`, `full_offline_acceptance: false`.
The full-offline discriminator requires completed exhaustive current/historical/
syntax coverage, never native-only or partial/duplicate results.
Per-suite execution/validation/shutdown is capped by remaining total time.
Shutdown and final fixture cleanup reserve time **within** the total budget;
deadlines are never silently extended. Quick budgets are not exhaustive defaults.
Full acceptance needs a separately
authorized explicit budget, not smaller sampled coverage or timeout-as-pass.

The serial budget example is based on prior healthy global/preflight/profiles/
global-uninstall/local-uninstall observations of 577/1079/3803/11868/9930 seconds:
over 7.5 hours combined, with a longest suite above 3.2 hours. Twelve hours total
and four hours per suite provide explicit operator-chosen bounded headroom, not
a guarantee, expected current duration or automatic permission to run.
Do not overlap heavyweight suites for the next acceptance gate or automatically
retry/extend these limits. Exhaustive can take hours; no exact current exhaustive
duration is claimed. Timeouts are `INCOMPLETE`, exit 1. Assertion/timeout failure
stops scheduling and cancels remaining work as INCOMPLETE without masking the
original failure as user cancellation. Validated native BLOCKED/exit 2 is distinct
and does not trigger this fail-fast policy.
Inspection is bounded by the original remaining execution/cleanup deadline, with at
most five seconds per attempt. Only `TimeoutExpired` allows one fresh retry, without
sleep or budget extension. Work cancellation/fail-fast prevents reattempt; cleanup
omits those work checks so owned-target cleanup remains best-effort. No partial or
stale snapshot is used; recovery requires complete parsing before the deadline.
Recovery emits the identity-free `PROCESS_INSPECTION_RECOVERED` stderr diagnostic
in shared/native supervision and `process_inspection_recoveries` counts in runner
suite results. Qualified success remains success, never native BLOCKED/2.
Repeated timeouts and non-retriable inspection failures,
including empty/malformed output, and cleanup errors are `INCOMPLETE`/exit 1 with
`failure_kind: supervision`, not test-budget `timeout`, native blockers or passes.
Cleanup continues for observed descendants using a fresh PID/birth snapshot for
each individual signal (best-effort, not atomic; birth timestamps have second
resolution);
isolated error diagnostics retain both cleanup errors and the full primary failure.
State parsing validates Darwin/Linux primary states and suffix flags, with only a
primary `Z` classified as a zombie. Known pre-cleanup child exits remain in suite
results and isolated diagnostics with stdout/stderr; cleanup-induced signal exits
never replace an existing timeout, cancellation or supervision failure.

**Retained-leader supervision requirement (2026-09-14 correction):** group
signals must precede any direct-child reap. The direct `start_new_session`
child reserves the PID/PGID while live **and while retained as a zombie**.
Completion is observed with `waitid(P_PID, WEXITED|WNOHANG|WNOWAIT)`, never
`poll`, `communicate` or `wait` before group cleanup. Selector-based bounded
nonblocking reads drain both pipes; pipe-holding ordinary/background children
cannot postpone group cleanup once leader completion is observed. All group
TERM/KILL attempts and termination verification precede final drain/wait.
There is no group-signal fallback after that irreversible release boundary.
Missing waitid support, non-default SIGCHLD, ECHILD, premature reap and
contradictory leader identity fail closed, permanently disabling group signals.
No global SIGCHLD configuration is changed. The runner must be the sole reaper
of each child it launches; embedding it with a competing reaper is unsupported,
not a safety guarantee against arbitrary concurrent `waitpid` calls.
This retained kernel-leader guarantee is distinct from observed descendant
birth checks: those remain best-effort and detach/reparent between observations
can escape detection. Known surviving owned descendants are cleanup failures.
Regressions use mocked delivery for foreign PID/PGID reuse and lost ownership;
real-child tests cover live/completed leaders, ordinary/closed-pipe/new-session
descendants, large output, exit 7, signal exits and cancellation. This focused
correction and any QUICK result are not full .8 acceptance or independent review.

**Native helper integration (2026-09-14):** the same stdlib
`acceptance.supervised_process` ownership context now serves `execute`,
native-discovery `run`, and interactive `Rpc` startup/close; the Beads context
and production fixtures import that batch helper. No duplicate group cleanup
implementation remains in discovery. Explicit cwd/environment/sandbox argv and
optional stdin text survive the shared boundary. Nonblocking writes avoid pipe
deadlocks; output is bounded to 64 MiB for batch and 4 MiB for RPC metadata.
RPC uses its protocol timeout plus a fixed five-second supervision/cleanup
allowance, still beneath the outer runner's unchanged caps. Path-based loading
has no native/runner dependency cycle and supports standalone/importlib/runpy.
Source provenance automatically hashes this helper and the new small regression
suite, selected once in QUICK and once in the exhaustive CURRENT inventory.

TimeoutExpired and supervision/cleanup errors propagate as typed failures into
exit-1 native reports, including nested fixture error and privacy handlers.
Protocol EOF, unknown RPC errors, generic nonzero exits and unreviewed warnings
are failures, not unsupported-interface evidence. Exit 2 requires a structured
`blocker_kind` (absent-tool, unsupported-interface, denied-approval) with its
diagnostic; optional source-reviewed unsupported embedded SQL remains allowed.
Validators reject structured failure fields anywhere in a report, irrespective
of a BLOCKED label, without guessing from prose. Safe regressions use mocked
foreign targets, real harmless Python pipes, and injected native fixtures only.
The earlier native reports below are previous evidence, not fresh qualification
of this corrected implementation.

The bounded global diagnostic checkpoint ran the complete suite once, alone:
exit 0, 316 assertions, 47 fixtures, 343.74 seconds. The largest gap between
recorded progress events was nine seconds; fixture f8 took about 40 seconds
across additive installation, helper, cross-repository and refresh operations.
There was no observed global hang. The earlier concurrent 599.24-second timeout
is consistent with contention but does not establish its cause. Completion-only
records from this experiment cannot independently attribute time to snapshots,
setup and production operations. They also predate the final diagnostic format;
the ad-hoc driver did not record a source-content pin and used weaker cleanup
than the acceptance runner. This is diagnostic evidence, not full acceptance.

For future authorized diagnostic experiments use the exhaustive offline command
above with `--global-diagnostics`. The report binds source/tool SHA256 (including
the actual helpers and new test), platform/Python identity, diagnostic format,
exact selection/configuration/budgets, command/exit and suite wall times.
`global-progress.tsv` is outside all fixture/snapshot/native roots; fixtures are
cleaned while session evidence survives cancellation and is operator-removed
after review. No long diagnostic run is authorized by this documentation.

The raw `DOM_TEST_DIAG=/absolute/private/path/global.diag bash test/global.sh`
interface alone is not provenance-complete. Its directory must exist outside
fixture roots (including resolved symlinks). Leave the variable unset for ordinary
execution. `global-diag-v1` appends whole-second elapsed time, case id, stable
caller line, fixed operation/phase, and numeric end status. It logs no argv,
payload or arbitrary check-label text. Helper starts/ends pair by case/caller/
operation and chronological order, but nested timings are not additive.
Setup/direct operations/gaps remain unattributed and interrupted starts may
lack ends. Do not invent per-operation attribution from the earlier 343.74s run:
it predates final formatting and is not new-source acceptance.
Open/write errors are explicit failures, including writes inside command
substitutions. Persistent disposable probes extract the actual helper definitions
to test stream/status equivalence, failures, nonleakage, path isolation and
append-only cancellation survival without executing the 316-case suite.
Full .8 requires independently completed current-source `--exhaustive` coverage,
qualified native evidence-or-blockers and independent review; QUICK green is
insufficient. Those gates remain pending.
No production optimization or native gate was exercised by this checkpoint.
The runner uses
checkout CWD, `/dev/null` stdin, private HOME/TMPDIR and no inherited Git policy
or authentication environment. Its Git template provides the ordinary
`.git/info/exclude` container but no user hooks. Discovery and its offline
protocol units are staged outside the checkout, under ordinary OS-private
TMPDIR, rather than bypassing production's global-root guard or weakening
the sandbox-profile unit assertion.
It validates native JSON shapes, proof sets, counts, diagnostics and exit-code
consistency. Missing/malformed reports, timeout, cleanup failure or omitted suite
completion are failures, not legitimate exit-2 blockers.

SIGINT/SIGTERM stop further scheduling; active owned process groups and observed
descendants (including nested new-session children) receive TERM then KILL within
the shutdown reserve. Direct children are reaped; orphan descendants are verified
terminated and left to the OS reaper. Identity-only `ps` snapshots track exact
PIDs/start times, never command names or payloads. This is not kernel containment:
detach/reparent between snapshots can escape observation, and uninterruptible
OS/filesystem operations can delay return. Inspection/termination/fixture-cleanup
failures are explicit failures, not suppressed. One failed termination does not
abort bounded best-effort termination/escalation
of the remaining positively identified owned targets. Collected cleanup errors
still make the run fail even if subsequent KILL succeeds. SIGKILL cannot be intercepted;
external CLI lifecycle events cannot be inferred. An agent cancellation that
sends the runner no signal is bounded only by its own total deadline.

An atomic sanitized incremental JSON report starts `INCOMPLETE`/exit 1 and records
each completed/failing/cancelled task, requested coverage, session timestamps,
source-file hashes including dirty runner/tests, and actual tool binary hashes.
Partial runs finish `INCOMPLETE` or `CANCELLED`, never a full-suite claim.
Final exit/completeness includes cancellation captured through fixture cleanup,
incomplete-report serialization, and handler restoration. Both previous signal
dispositions are restored before the definitive outcome snapshot/completion write;
each restored signal has ordinary native behavior, not a sticky runner flag.
Later native termination can leave the last persisted report intact. Cleanup and
final-report errors remain nonzero; successful suites cannot override them.
Ten-second progress heartbeats expose active/pending counts and remaining budget;
raw diagnostics remain only in the private fixture artifacts. There is no
automatic resume or cached-success path. Native-only still implies no offline
coverage; CURRENT/HISTORICAL/NATIVE and precise blocker distinctions are unchanged.

The safety checkpoint runs only the fast runner units and applicable syntax
checks, not the acceptance matrix or native clients. Prior durations were
global-uninstall **11867.82s**, local-uninstall **9929.61s**, local-profiles
**3802.87s**, native production **1148.45s**, native cleanup **1632.87s**.
Those are observations of the previous runner snapshot, not performance changes
or current acceptance evidence.

The subsequent [bounded path-batching checkpoint](../test/global-path-performance.md)
adds `global-path-tests.py` once to offline `CURRENT`; the multi-minute benchmark
is explicit opt-in only. Both use a checksum-pinned, verbatim helper fixture from
`20b6fe8d924d50c943242dc730725e59ce1ef956`, not mutable HEAD or required Git history.
The fixture is included in syntax/lint and source-provenance capture. BSD
`%Mp%03Lp` now retains special permission bits, allowing root-owned sticky
writable ancestors outside the boundary without allowing user-owned
sticky/writable ancestors or unsafe in-boundary paths. Special-bit-only changes
are detected by metadata stability checks; the oracle retains the legacy bug
and the tests explicitly distinguish the intended correction.
Earlier concurrent bounded attempts: **18 path tests (2 errors)** and **54 runner units
(2 failing subtests, 3 errors)**, not passes; existing process-inspection/cleanup
deadlines blocked validation. Syntax/warning-ShellCheck/diff and fixture integrity
passed. The prior **117** private-core checks were not rerun after this correction.
Earlier batching timings predate the correction; local-preflight's earlier
120-second timeout was not a pass and was not rerun. Full applicable `.8`
acceptance and independent review remain required.

The resumed **index-query-only checkpoint** leaves those path helpers and the
runner's signal/finalization guarantees unchanged. `local_untracked` now issues
one fresh `git ls-files -z` query at the literal outermost candidate component,
matching destination/subtree collisions and exact indexed ancestor objects while
ignoring unrelated indexed siblings. The internal candidate contract is canonical
printable ASCII repo-relative inventory leaves; noncanonical/non-ASCII candidates
and all Git pathspec overrides refuse before querying, avoiding normalization and
case/pathspec rewriting mismatches. Indexed sibling names remain opaque bytes,
including LF and non-UTF8. Git's original literal byte-exact case semantics are
preserved even with `core.ignorecase=true`. Routing overrides, malformed/empty
frames, truncated tails and nonzero commands still refuse. All per-mutation
calls remain fresh; there is no cross-call cache or extra filesystem optimization.

`local-index-tests.py` is included exactly once in `CURRENT`, with strict unittest
completion reporting and source provenance for its immutable helper fixture and
loader. Its baseline is the original helper at
`20b6fe8d924d50c943242dc730725e59ce1ef956`, never mutable HEAD; synthetic corruption
is protocol testing, not native-client or Beads evidence. Sequential checks passed
**12 index tests, 18 unchanged path tests, 55 runner units and 117 private-core
checks**. The opt-in benchmark reuses the existing isolated fixture and supervision:
one global-all and one local-all per source, four successful operations total,
120 seconds/operation and 300 seconds overall. Only the index helper differs.
Local-all measured **73.425 → 54.929 seconds**, saving **18.497 seconds (25.2%)**,
**1.337x** in one sample. Global setup measured 10.148 → 6.556 seconds; do not
attribute that variability to local index querying. Core starts absent below
`work/scope/core`. No native clients, databases, network or full matrices ran.
The parent's complete local-preflight attempt timed out at **599.16 seconds**
without a complete summary; it was not repeated or granted a larger limit here.
Details and initial fixture-validation failures are retained in the
[checkpoint record](../test/global-path-performance.md). Full `.8` acceptance
and independent review remain pending.

**Prior completed CURRENT offline counts:** `private-core.sh` **117**, `global.sh`
**316**, `local-preflight.sh` **366**, `local-profiles.sh` **1134** (wrapper runs
Python once), `global-uninstall.py` **3173**, full `local-uninstall.py` **1365**
(all selection/preflight/shared-worktree/transaction/late-fault phases),
`beads-guard.py` **1697**, synthetic `beads-private.py` **823**, synthetic
`beads-cleanup.py` **212**. Offline protocol units: native discovery **45**,
Beads context **31**; runner classification/isolation/timeout/help units **30**.
These are per-harness check counts, not native operation totals or additional
standalone `private-core-commands.py`/`local-profiles.py` suites.
Synthetic cleanup recorded **71 fake Beads / 107 instrumented process calls**,
with zero calls during cleanup.

The complete stable-source offline runner finished **exit 0** at
**2026-09-13 09:11 UTC**. The separate completed native runner finished **exit 2**
at **03:48 UTC** for only the documented native blockers, with no assertion
failures. No independent-review PASS or bead closure is asserted here.

**HISTORICAL_FIXTURE b60feef counts, separately:** Codex **16**, Copilot **85**,
guest **14**, uninstall **23**, upgrade **12** reported passes. Original pinned
coverage is retained, not repurposed as current installation acceptance.
**Syntax/lint PASS:** all **12** applicable shell files plus the emitted resolver
under Bash 3.2; warning-level ShellCheck on source/tests/helper, **0 new warning
exceptions** (no blanket SC2034 suppression); AST for all **14** Python files
plus the embedded controller, no bytecode caches; `git diff --check`.

**Observed native results (2026-09-13).**

| Scope / harness | Actual result |
| --- | --- |
| `native-discovery.py --run` | 12 native skill observations, 8 blocked records, 22 static-only, 0 assertion failures; exit 2 |
| Historical context `beads-native-context.py --run` | 71 recorded commands; 8 PASS proofs, 1 BLOCKED optional SQL UUID query, 0 failures; exit 2 |
| CURRENT `beads-production.py --run` | 85 checked processes; A/B/linked W queue and storage identity separation, 15 protected host leaves / 121 protected entries; mixed-provider C ordering PASS; exit 0 |
| CURRENT `beads-cleanup.py --native` | 92 checks; 38 native Beads / 56 instrumented process calls, ZERO calls during cleanup; retain/pristine purge/cooperative locks PASS; exit 0 |

Native AI fixtures use the actual current installer. Global setup leaves both
repositories untouched; local setup creates six qualified role files only in A,
leaves B untouched and now explicitly asserts byte/type/mtime identity of the
global core and HOME during that operation. This is filesystem evidence, not
native role enumeration. Skills in A/B are checked before local setup, in fresh
processes after local A setup, and after a skill-description edit/reload.

| Actual client version | Executed bounded interface / precise blocker |
| --- | --- |
| Claude **2.1.269** | `--version`, `--help`, `agents --help`: **“Manage background agents”**, `--json` prints active sessions, not configured role IDs; no non-model skill listing advertised. Session view not launched. The dated .13 observation of 2.1.268 is retained above. |
| Codex **0.154.0** | `app-server --help`, `app-server generate-json-schema --help` then `--out <fixture>`; `app-server --listen stdio://` with `initialize`, `initialized`, `skills/list` (`cwds`, `forceReload=true`) and `config/read`. Skills observed, native-returned source paths checked; `config.agents=null` in A/B at every stage and stable schema has no role-list method. No thread/model session launched. |
| Copilot **1.0.83** | `--help`, `skill --help`, `skill list --help`, `skill list --json` in A/B; skill IDs/source paths observed. `--agent` selects a session agent; help advertises no non-model role-list subcommand. Authenticated startup/ACP not invoked. |

The Beads experiment's exact optional response was
`Error: 'bd sql' is not yet supported in embedded mode` for argv
``["bd", "--sandbox", "sql", "SELECT value FROM metadata WHERE `key` = '_project_id'", "--json"]``
(passed directly, not interpreted by a shell).
Native initialization, CRUD/dependencies/remember/export, readiness, distinct
queues, storage UUID identity negative controls, host privacy and teardown passed.
That TEST ONLY experiment is not the production initializer; the separate CURRENT
fixture uses the actual emitted dispatcher and .6 sandbox, and .7 native cleanup
uses source instrumentation solely to count calls without changing protection.

**Corrections during execution, not suppressed failures.** Initial runner attempts
misplaced discovery under the checkout (global worktree refusal), then under
`/private/tmp` (unsafe writable ancestor refusal). The completed corrected native
run uses ordinary OS-private staging and exits 2 for only the precise native
limitations above. Offline discovery units also require outside-checkout staging
for their sandbox no-source-read assertion; the runner now supplies it. One
global-uninstall attempt was invalidated by editing the live script's help while
Bash was running (changed byte offsets, syntax error after an otherwise successful
operation); complete reruns use stable source. These were runner/execution
corrections, not changes to production ownership, sandbox or locking guards.
Do not edit source during acceptance.

**Coverage interpretation.** Current executable tests cover all seven provider
selectors; qualified IDs and cross-client collision refusal; missing bound
release, corrupt/missing/mid-run receipts and no global fallback; metadata edits,
secret-sentinel non-copying and core-update/local-byte separation; local scope
byte identity; state-only none, successful/failed/unowned Beads; shared-worktree
exclusions; retained and pristine-purge state; publication fault/journal privacy;
force unchanged-only and ambiguous legacy refusal. Native protocol units use
synthetic responses, not native clients. Model defaults, ephemeral choices,
explicit-goal authority, source-commit authorization and no private staging
are prompt/guard assertions, **not executed model-session behavior**.

**Native limitations and manual gates — NOT executed.** Repeat the safe metadata
protocol with `python3 -B test/native-discovery.py --run` before interpreting any
future version. Help, schemas, config reads, skill listings, receipt validation
and inline SDK custom-agent injection cannot prove filesystem role discovery.
The bounded interfaces below do not establish that the products lack roles.
No authentication, model budget, UI trust or MCP/network workload was authorized
for this acceptance; do not weaken the isolation profile to get a green result.

For future separately authorized manual acceptance, recreate two disposable Git
roots A/B and a private HOME/core, using the harness's environment/setup helper.
Run current `domestique.sh --global --platform all`, then
`domestique.sh --local A --platform all`; retain pre/post snapshots of B and
global HOME/core. Start each installed client's **documented interactive role
interface** from A and B (fresh processes, no guessed role-list command).
Use the README's provider-qualified base/decompose/goal invocations and record:

1. The native-returned source path and exact
   `domestique-<provider>-{implementer,reviewer}` global IDs in A/B, plus
   `domestique-<provider>-local-{implementer,reviewer}` only in A; no collisions
   or same-name precedence assumptions. Claude skills also need native proof.
2. A-only supported nonsecret tools/MCP metadata edit, documented reload,
   exact selected native role, source binding and effective capabilities.
   Record trust separately from tool availability. Do not register/authenticate
   or execute a server without new explicit permission.
3. Bind each role independently via its receipt; then remove/corrupt the bound
   receipt/adapter or release in that disposable fixture. The native workflow
   must stop, not delegate to global/broader tools. Restore by a fresh fixture,
   not by fabricating production provenance.
4. Perform a compatible core-only update from an explicitly supplied local
   source; a fresh global/local role must read the new bound core while local
   customized bytes remain identical. Skill-description reload is not this test.
5. Under separately authorized model-session tests, verify native defaults,
   explicit session model choice and unavailable-choice stop without persistence;
   ordinary/base requests must not authorize unattended work. Only same-provider
   explicit goal authority permits sequential implementer/fresh-reviewer work,
   with no private staging, unauthorized source commit, push or merge.

Until those records exist, native role discovery/routing, custom metadata
reload/capability enforcement, live core update in roles, MCP/trust/tool access,
model/goal-session behavior and agent-driven Beads remain **UNVERIFIED**.
The qualified Beads production initializer/dispatcher and guarded cleanup are
separate observations, not substitutes for these gates. Beads qualification is
only Darwin arm64, Python stdlib and `sandbox-exec`, with 1.1.2 CGO embedded SHA-256
`cb77069648d90fef8876f775d647997beb7bb0ab5461509394c29d5bf14b7c42`.
Other versions/platforms/backends refuse. Direct embedded SQL UUID inspection is
optional/unsupported, not a remaining Beads feasibility blocker: native identity
negative controls and actual production queries are distinct proof. Cleanup
never queries Beads. Stop raw/older writers: metadata `flock` coordinates only
the current wrapper/controller/cleanup, not arbitrary writers or a process census.

### Old-plan disposition (parent-approved deferral)

The parent has already reconciled **hq-2su and unfinished .3–.7, hq-e7f and
hq-4oh.15 as DEFERRED**, not completed/closed or reparented. No bead queries or
mutations are part of this documentation change. Completed `hq-2su.1/.2`
remain closed history; commits `2896937`/`58f4d29` are reused. Draft #11 is
untouched, not merged or pushed.

| Deferred historical work | Retained private-plan mapping / current status |
| --- | --- |
| hq-2su.3 guest preflight | hq-b3q.4 done; .6 private Beads initialization implemented for the qualified artifact/platform |
| hq-2su.4 uninstall | .11 global / .12 local profiles / .7 unchanged-only database cleanup implemented; valid none attachment retained |
| hq-2su.5 policy/discovery | .2/.5 done; .13/.8 limited native evidence; role/tool/MCP runtime limitations remain |
| hq-2su.6 acceptance | .8 final evidence above; independent review required, no claim of all old native criteria fulfilled |
| hq-2su.7 documentation | current .9, approved now using implemented preview + .13 evidence |
| hq-e7f missing-mode safety | .4 fail-closed legacy classification; absent/corrupt mode never permits normal writes |
| hq-4oh.15 setup/init | no `bd setup`; .6 uses the qualified private execution context and sandbox, not four flags alone |

Old normal/guest dual-mode prescriptions are retired; do not restore
`--no-guest`, unsafe init/rollback or force-overwrite paths. Approval explicitly
allowed .9 without claiming blocked native execution. Final .8 evidence above
retains those runtime limitations rather than presenting the old plan as ready.
This records disposition, **not fulfillment of all old criteria or release
completion**.
