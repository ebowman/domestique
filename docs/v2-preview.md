# Small Copilot-first preview

**COPILOT/MACOS PREVIEW: RETAINED-CLI WORKFLOW AND SEPARATE GOAL SKILL LOAD DEMONSTRATED.**
The hq-iyu.2–.5 source implements installation, explicit update, offline
version/help, Copilot-only project enable/disable with dry-run, and thin shared
workflow/context loading with an explicit external-Beads readiness step.
Read-only inspection reports the selected revision and target footprint.
The [2026-09-18 native demonstration](#bounded-native-qualification-2026-09-18)
at `ad80706` completed real decompose and a direct retained-CLI one-bead goal
with independent review and Beads closure. Its goal skill invocation failed,
then a separate read-only native probe loaded the corrected project-local goal
skill successfully. The full cycle predates the two-line template visibility
fix; shared workflow instruction bodies are unchanged. This is not a new full-cycle rerun,
all-entry discovery or end-to-end skill-entry qualification.
Documentation, local fixture tests, source checkout, old passing logs and
discoverable metadata alone do not establish a project's workflow readiness.

## Boundary and source

Support the observed macOS environment and Copilot first: install once from a
trusted, explicitly selected Git revision, explicitly enable one project, and
update the shared workflow source once. Released Claude/Codex v1
`domestique.sh` now adds compatible short public names; its existing lifecycle
and `update.sh` transport semantics remain unchanged. No promise of other-platform
or other-provider v2 parity.

This separate branch starts at `19deeab511000ff72322c231d17cb3a8c80d8641`.
Completed history, the historical ABI2 baseline, and existing experimental
modules remain preserved. The old `docs/v2-bootstrap.md`,
`docs/v2-install-contract.md`, `docs/v2-install-interfaces.md` and
`docs/v2-source-boundary.md` describe the earlier framework, not this preview's
runtime contract. Their evidence is neither weakened nor relabeled as preview
acceptance. The uncommitted ABI3 experiment in the original worktree is
**unreviewed/incomplete**; its apparent qualification successes do not replace
the last independent FAIL, which predates those edits.

The runtime is small repository-owned `preview/` source and a thin stable
command. Native project-local adapters are thin loaders; shared workflow
instructions live in `preview/workflows/` (common plus small entry/role sections).
Neither the historical package runtime nor ABI3
payload/transport is on this execution path. `install-v2.sh` has been replaced
for **this preview contract only**; it no longer accepts the historical package
bootstrap grammar and does not migrate its installations.

## Commands and availability

The hq-iyu.2–.5 rows below are implemented. Inspection is read-only, not legacy
fallback or repair. Instruction loading is not native
workflow execution. `REV` must explicitly resolve to a commit in
the trusted source; there is no default branch selection or implicit download.

| Invocation (availability by owning task) | Routine behavior | Owning task |
| --- | --- | --- |
| `install-v2.sh --source CHECKOUT --ref REV` | Install the selected trusted local Git source revision and stable command; no project activation. | hq-iyu.2 |
| `domestique2 update --ref REV` | Prepare a revision from the recorded source, then switch the owned current pointer; no project rewrites. | hq-iyu.2 |
| `domestique2 enable [TARGET] [--dry-run]` | Fresh: install seven local Copilot definitions at the exact physical Git worktree root. Existing five-definition layouts are preserved. Omitted target requires cwd itself to be that root. | hq-iyu.3 + compatible public names |
| `domestique2 disable [TARGET] [--dry-run]` | Revoke the receipt, remove only unchanged owned definitions, retain edits and report partial removal. | hq-iyu.3 |
| `domestique2 workflow TYPE --project ROOT` | Load shared instructions/context without Beads; bare goal/roles give non-authorizing setup guidance. Optional `--ready` explicitly checks existing user Beads. | hq-iyu.4 |
| `domestique2 inspect [TARGET]` | Read-only shared-revision and selected-project ownership report; omitted target requires cwd itself to be the exact physical Git root. | hq-iyu.5 |
| `domestique2 --inspect [TARGET]` | Alias of `inspect [TARGET]`, not an installation or repair operation. | hq-iyu.5 |
| `domestique2 version` / `domestique2 --version` | Report the selected source revision offline. | hq-iyu.2 |
| `domestique2 help` / `domestique2 --help` | Describe only supported commands and prerequisite boundaries. | hq-iyu.2 |

### Install and update the machine source

Provide existing Bash, Git and Python 3.9+ with its standard library. The macOS
developer-tools Python stub is not accepted. If a prerequisite is missing,
provide it separately; the preview never installs tools or opens setup/auth
flows. This is a source entrypoint, not a standalone downloadable installer:

```sh
bash -p ./install-v2.sh --source "/path/to/trusted checkout" --ref REV
"$HOME/.local/bin/domestique2" --version
"$HOME/.local/bin/domestique2" --help
"$HOME/.local/bin/domestique2" update --ref NEXT_REV
```

`CHECKOUT` must be an existing local Git checkout root (linked worktrees are
allowed); its physical path is recorded. Both install options are mandatory,
each exactly once, in either order. Update accepts exactly `--ref REV`.
Install also accepts `help` or `--help` alone; bare installed `domestique2`
prints help. Version/help accept no extra arguments. Enable/disable accept
at most one nonempty literal target followed by optional `--dry-run`, exactly
once and last. There is no `--platform`, force, adoption or migration switch.
`inspect` and `--inspect` accept at most one nonempty literal target, no flags.
Unknown/duplicate/empty options, flags in value positions
and extra arguments are misuse. Quote paths with spaces or shell literals;
arguments and JSON receipts are never evaluated or sourced.

Exit **0** means complete/no-op (including preserved customization on repeat
enable); **1** means refusal, partial disable/installation, unavailable
functionality or an operational/prerequisite error; **2** means argument
misuse, rejected before effects. Dry-run performs the same preflight but makes
no writes; refusal or a predicted partial disable still returns **1**.

Selection uses normal Git commit resolution, not working-tree bytes: the
selected commit must include the new `preview/cli.py`, runtime and matching
launcher source. Preview Python and launcher syntax are checked without
executing candidate setup or hooks. Revisions with symlinks or submodules are
refused; this small implementation requires complete regular-file Git content.
Uncommitted source edits are not installed. Only trusted, runnable source is
supported; syntax checks are not a sandbox or proof of arbitrary program
behavior. Git operations isolate ambient repository/config/template settings
and disable hooks, optional index writes, maintenance and remote protocols.

The install location is
`${XDG_DATA_HOME:-$HOME/.local/share}/domestique-preview`; the stable executable
is `$HOME/.local/bin/domestique2`. Installation writes only owned source
revision directories, small JSON creation receipts, the current pointer and
that command (creating missing owned parents as necessary). No shell startup,
PATH, aliases, default branch, native global definitions or project registry
are changed. Existing `dom`/`dom2` aliases may still invoke older scripts.
Existing legitimate `.local/bin` contents are preserved.

Each `releases/COMMIT` is a standalone shallow Git checkout, with no alternates
or live source dependency. `current` is a relative symlink to a retained
revision; the stable launcher selects it once and dispatches the revision's CLI.
New CLI behavior ships through the Git ref/update, not a regenerated command
dispatcher. Version/help work offline even when the original checkout has moved
or disappeared. Update then reports the missing recorded source and preserves
the selected revision. Restore that source path to update again; source refresh
is user-managed, with no implicit fetch from a remote.

Missing source/ref, dirty or foreign destinations, unsafe paths, an unowned
command collision or incompatible experimental installation cause refusal.
Do not adopt even identical unowned files. No force, automatic migration,
`git pull` merge, auto-update or release download. Prepare before switching;
failure retains the old selection. Retain prior revisions, without garbage
collection. Updates affect the next workflow; running workflows and delegated
roles retain one immutable source revision resolved once at workflow entry.
Revisions are immutable by convention: ordinary Git status/HEAD checks detect
managed edits, and creation receipts distinguish owned paths from identical
unowned files. Do not edit these checkouts. Validation checks the selected and
requested revisions, not every historical checkout on every invocation.
Repeat install of the same source/commit is a no-op; a different installed
selection requires `update --ref`, not a reinstall.

Known collisions and write-permission failures are checked before preparation.
An ordinary preparation failure cleans only this operation's own temporary
files. If preparation completed but the pointer switch failed, the old pointer
remains selected and the prepared owned revision may remain; there is no
automatic recovery, cleanup of unknown leftovers, rollback engine or GC.
Single-writer, non-hostile local operation is required; power-loss durability
and hostile concurrent-owner atomicity are not promised.

For callers outside the installed entry, `preview.machine.resolve_source(root)` is the small
read-only internal API returning one checked absolute revision `Path`. Retain
that path for the whole workflow and delegated roles rather than reading
`current` again. Retained revision CLI help/version also remain callable by
their immutable path; management updates must use the current launcher.

### Bounded local validation

Run only the new scope, not the historical ABI suites:

```sh
python3 -B -Werror test/preview-workflow-tests.py
python3 -B -Werror test/preview-inspect-tests.py
python3 -B -Werror test/preview-project-tests.py
python3 -B -Werror test/preview-machine-tests.py
bash -n install-v2.sh
bash -n preview/launcher.sh
shellcheck --severity=warning install-v2.sh preview/launcher.sh
```

The machine stdlib unittest module uses one tiny local Git cohort (two runnable
commits and one deliberately incomplete commit) and disposable HOME/XDG paths.
It covers offline dispatch, real behavior change, retained old paths, same-ref
no-ops, failed preparation, dirty/foreign collisions, literal arguments and no
source/project/native writes. The project module uses one installed local
runtime cohort and A/B repositories: exact footprint, literal loader commands,
dry-run/no-op, preservation through shared update, partial revocation, ordinary
collisions/permissions/write failure, and linked-common ambiguity.
Run these four modules SERIAL, in owned temporary fixtures (not simultaneous
30-second subprocess cohorts). The workflow module uses installed immutable
revisions, unchanged `.3` locators and a fake `bd` recording exact argv/cwd/exit/
effects. It checks default no-DB loads, explicit intent/readiness, refusal paths,
literal context, customization and retained old role sources after update.
Its scripted claim/role-load/review-label/commit/close transcript is NOT actual
native implementation, review, model dispatch or a real database lifecycle.
The eight-case inspector scope reuses the project cohort and isolated fake
executables: absence/aliases, active/customized across template update, missing
owned file, older/ambiguous evidence, invalid/partial receipts and exclusions,
and refused/unreadable targets. Byte/mode/path snapshots protect fixtures before
and after reads. Deterministic PermissionError tests are mock I/O proof, not
privileged-host filesystem permission or native acceptance proof.
These offline modules make no native/model/network/real-Beads calls or real
HOME installation.
Static emitted-command checks are not native
discovery or workflow proof. Historical ABI/bootstrap/inspector suites are not
part of this qualification stage.

For the additive public-name change, run the related existing runners serially:
`bash test/codex.sh --current` (19 scenarios, including Claude/Codex names),
`bash test/guest.sh --current` (14 scenarios), then
`python3 -B -Werror test/preview-project-tests.py` (7 tests),
`python3 -B -Werror test/preview-workflow-tests.py` (7 tests), and
`python3 -B -Werror test/preview-inspect-tests.py` (8 tests).
The shell runners without `--current` remain historical fixtures.
The prior five-definition lifecycle/block and prior v1 installer are frozen from
`654414025554defe9eeef50c39b14a87326088b8`, not reconstructed from new constants.
This is naming/compatibility evidence only; no native model probe is required.

## Explicit project ownership

Enable/disable require a valid installed machine runtime but do not write it,
update source, or use the historical `v2/` modules. TARGET must name the exact
physical Git worktree root: subdirectories, symlink paths, non-Git directories
and bare repositories refuse, including default cwd if it is a subdirectory.
Managed machine release checkouts cannot be activated.

```sh
"$HOME/.local/bin/domestique2" enable "/physical/project root" --dry-run
"$HOME/.local/bin/domestique2" enable "/physical/project root"
"$HOME/.local/bin/domestique2" inspect "/physical/project root"
"$HOME/.local/bin/domestique2" disable "/physical/project root" --dry-run
"$HOME/.local/bin/domestique2" disable "/physical/project root"
```

Only these seven local Copilot definitions and the single JSON receipt
`.domestique-private/copilot-preview.json` belong to activation:

- `.github/skills/domestique-v2-copilot/SKILL.md`
- `.github/skills/domestique-v2-copilot-decompose/SKILL.md`
- `.github/skills/domestique-v2-copilot-goal/SKILL.md`
- `.github/agents/domestique-v2-copilot-implementer.agent.md`
- `.github/agents/domestique-v2-copilot-reviewer.agent.md`
- `.github/skills/dom-decompose/SKILL.md`
- `.github/skills/dom-goal/SKILL.md`

The last two are thin public wrappers for the same `decompose`/`goal` CLI types,
not new roles or workflows. Original five-definition activations keep their exact
inventory and exclusion contribution until explicit safe disable/re-enable.

#### Shared thin loader commands

Each definition references the absolute stable installed launcher with this
simple command shape (paths are literal shell-quoted, including spaces, quotes
and `$`):

```text
ABSOLUTE_LAUNCHER workflow TYPE --project ABSOLUTE_PHYSICAL_ROOT
```

TYPE is `ordinary`, `decompose`, `goal`, `implementer` or `reviewer`. These
commands validate grammar, machine runtime and active exact project identity,
then return shared instructions or setup guidance; by default they execute no
native or Beads actions. This implements the reserved shape, not a new public
ABI freeze, native runner or workflow engine.
The wrappers request shared instructions and report load errors, rather than
baking a permanent stop prompt into a local file. Existing owned `.3` wrappers
therefore work after a central update without replacement or rebaselining.

Optional flags are ordinary bounded argv data (unknown/duplicate/empty/malformed
arguments return **2**; missing action/role context or prerequisite returns **1**):

| Option | Meaning |
| --- | --- |
| `--ready` | Explicit consent to run existing `bd --version` and `bd -C ROOT status` in ROOT, up to 20 seconds each. No task is automatically executed. |
| `--brief TEXT` | Literal bounded planning/task description, at most 16 KiB characters, newlines preserved. Decompose readiness requires it. |
| `--task ID` | One explicit bounded bead ID for ordinary action or delegated role; ordinary readiness also requires a brief. |
| `--epic ID --domestique-goal` | Goal only: transport the actual user's explicit Domestique goal request plus one epic. Neither flag alone grants loop authority. |
| `--source ABSOLUTE_CLI` | Must equal this invocation's immutable `releases/REV/preview/cli.py` path exactly; mandatory for actual roles. Never a source override. |
| `--role-id EXACT_ID` | Mandatory for actual roles, exactly the selected local implementer/reviewer ID. |
| `--implementer-model ID` / `--reviewer-model ID` | Optional literal ephemeral requested model strings; no persistent settings/capability claim. |
| `--confirm-native` | Caller asserts fresh native exact-ID/capability confirmation of customized files before `--ready`; not automatic metadata admission or native proof. |

Bare goal is SETUP ONLY, not a loop body or Beads readiness. Its rendered
instructions tell the native caller to forward the user's explicit epic through
the retained command, e.g. `python3 -I -S -B ABSOLUTE_IMMUTABLE_CLI workflow goal
--project ROOT --source ABSOLUTE_IMMUTABLE_CLI --epic USER_EPIC --domestique-goal
--ready`. The original `.3` locator need not know newer flags. If the user did
not explicitly request Domestique goal, ask and stop rather than infer intent
from native goal/autopilot or planning. An explicit gated goal load without
`--ready` can read policy, but cannot act before requested readiness.

Bare role locators return ROLE LOCATOR ONLY, with no role body or workflow start.
Actual role loads require caller-supplied `--project`, `--task`, `--brief`,
`--source` and `--role-id`; rendered role commands contain the exact immutable
source/project/role IDs and literal task/brief (or clearly labeled placeholders).
Replace placeholders from the SAME retained assignment, not current. The native
caller/role compares task, project, source and exact ID against that assignment
and stops on mismatch. These plain fields are not authenticated session tokens;
the loader cannot infer a caller's unexpressed intended task. Roles do not
independently sample current or invoke readiness to start a new workflow.
JSON display escapes literal context; shell command examples use literal quoting
and preserve newlines. Never eval them or serialize them into persistent settings.

Frontmatter contains only these exact `name` / `description` pairs:

| Name | Description |
| --- | --- |
| `domestique-v2-copilot` | Load the shared Domestique Copilot instructions. |
| `domestique-v2-copilot-decompose` | Load Domestique planning instructions without coding. |
| `domestique-v2-copilot-goal` | Load an explicitly requested Domestique epic workflow. |
| `domestique-v2-copilot-implementer` | Implement one caller-assigned Domestique task. |
| `domestique-v2-copilot-reviewer` | Independently review one caller-assigned Domestique task. |
| `dom-decompose` | Load Domestique planning instructions without coding. |
| `dom-goal` | Load an explicitly requested Domestique epic workflow. |

Goal is model-loadable, but execution still requires an explicit
Domestique goal request naming an epic, not native goal/autopilot. No model,
tool, MCP defaults or permission grants are emitted. Delegated roles await the
caller's bounded task and retained source context; their locator is for the
caller, not permission to start a workflow or resolve `current` independently.
The loader uses the immutable path already selected once by the launcher; it
never resolves current again. It requires the matching active project receipt,
root/Git/common identities, machine binding, five stable internal native IDs and all
recorded owned files (seven fresh, five legacy) before operational instructions. Missing/revoked/moved/copied/foreign,
nested-root or missing-role contexts refuse without Beads or fallback.
Customized definitions are marked, never parsed or rewritten; fresh native
confirmation is required before action. Edited raw locators are trusted user
code, outside hostile-loader guarantees. Definition installation alone is
**not operational workflow readiness**.

#### Ordinary ownership and removal

The bounded JSON receipt's `kind` is `domestique-copilot-preview`. It records:

- `project`: physical root, independently resolved Git directory and common
  directory, each with device/inode identity (copied/moved/foreign roots refuse).
- `installation`: machine root identity and stable launcher path, identity and
  hash; `native_ids`: the five exact names, independent of selected source ref.
- `inventory`: `public-names` for fresh seven-definition activations; absent for
  the original five-definition layout. No other inventories are accepted, no
  adoption or rebaselining occurs, and internal `native_ids` stay unchanged.
- `files`: only created native relative paths, their creation identities and
  original SHA-256 hashes (`null` only for a known incomplete write).
- `directories`: only created parents and their identities; `receipt_identity`
  identifies this state file, not a foreign identical copy.
- `token`, `exclusion`: exact eight-pattern block (original six for legacy) plus delimiters, original
  prefix length/hash, optional separator newline, exclude identity and
  `planned` / `present` / `removed` state.
- `state`: `partial-enable`, `active` or `disabled`. Only `active` permits
  workflow use; partial disable keeps the disabled receipt and original hashes.

All receipt paths are restricted to the closed native/state leaf and parent
sets and matched to the selected root, never arbitrary paths supplied in JSON.
Receipts are at most 64 KiB; exclusion and known legacy anchor reads are bounded
at 1 MiB. Hash comparisons establish unchanged versus customized bytes, **not**
approval of arbitrary native metadata or effective permissions. Larger owned
native files are retained as customized without parsing.

Fresh enable preflights every required leaf, parent writability, receipt and
exclusion before creating anything. Refuse tracked/index-only, symlinked,
hardlinked, nonregular, unknown or incompatible collisions, unsafe permissions,
and known v1/experimental authority anchors. Even identical unowned files or
preexisting named skill directories are not adopted. Legitimate `.github`
containers and unrelated `.domestique-private` notes can coexist; no private
state or native leaf collision is absorbed. Only exact known legacy
state/command/policy anchors are checked, not the whole machine.

Repeat enable never rewrites wrappers, changes their baselines, parses their
YAML or approves user model fields. It reports `customized` and preserves all
owned local edits byte-for-byte, including bodies and malformed metadata,
across shared source/template updates. Missing owned definitions refuse
repair; use disable. A replaced native inode is retained as customized/replaced,
not newly adopted.

Disable first preflights all leaves/exclusion and revokes the active receipt
**before any eligible deletion**. Only same-identity, unchanged owned files are
deleted. Customized, replaced, tracked, unsafe or unowned leftovers remain;
exit **1 / PARTIAL** lists reasons and retains the disabled receipt with its
original baselines. Repeated partial disable remains honest, never re-enables or
rebaselines. Resolve retained material yourself, then repeat disable; enable
refuses while a partial/revoked receipt exists. Complete cleanup removes the
receipt; repeat disable is a zero-write no-op, and fresh re-enable is
collision-safe. Only proven-created empty directories are removed; unrelated
contents/directories are never recursively deleted.

Never rewrite root instructions, settings, hooks, the index or tracked
`.gitignore`; never initialize, open or hide `.beads`.

The only Git exclusion change is an exact owned contribution to the Git-common
`info/exclude` for exactly the recorded native files and receipt, never entire
containers or `.beads`. An appended block uses
`# domestique-copilot-preview BEGIN TOKEN` / `END TOKEN` delimiters and eight
root-anchored literal patterns (six in legacy receipts). Preserve host bytes and mode, including
preexisting matching lines (unowned). Missing ordinary common `info/` or unsafe/
unwritable exclusions refuse before publication, without Git-admin repair.
An absent `exclude` file may be created; disable never deletes that file.

Removal requires the original file identity, prefix and exact unique block.
Host suffix additions survive; edits to the prefix/block, duplicate/foreign
preview markers or replaced exclude files cause conservative retention. This
may require manual attribution even for a harmless host prefix edit.
Only one preview activation per common repository is supported: another
worktree's block causes enable/refusal, and disable without a local matching
receipt refuses to remove it. Linked root and per-worktree Git identities are
distinct from common identity. Common ignore effects do **not** activate sibling
worktrees. No sibling registry or crawl establishes wider ownership; ambiguous
disable revokes the local receipt, removes eligible files, retains the common
contribution and reports partial.

Ordinary mid-write failure can leave a factual `partial-enable` receipt and
created subset; disable uses only those recorded claims. Small receipt updates
are atomic replacements, not a transactional journal. Interruption between a
file write and recording it can leave an unknown file; partial exclusion writes
can require manual resolution. No automatic reset/adoption, power-loss
durability, perfect race atomicity or concurrent-writer recovery is claimed.

Safety assumes trusted local source and cooperative single-writer operations,
normal Git/filesystem validation and an atomic owned current-pointer switch.
It does **not** promise hostile same-owner/concurrent-writer atomicity, native
sandboxing or invisibility. Existing ancestor/global definitions may still
advertise Domestique; enabling or disabling this preview does not retire them
or erase cached native context. Use fresh clients when qualifying discovery.

## First-use role models — Claude protocol implemented, native unqualified

The accepted contract (hq-7sm.1) below is implemented for Claude as an **emitted
native assistant protocol** in `domestique.sh` (hq-7sm.2), not a standalone
settings engine or native runtime qualification. One shared setup body gates
canonical/legacy decompose and goal; ordinary policy redirects unconfirmed
delegation to setup. Generated Claude model defaults remain suggestions, not
consent. Codex and Copilot setup adapters are still pending:
`domestique.sh` emits Codex model/effort defaults; `preview/native.py` emits no Copilot models.
`preview/workflow.py` transports ephemeral requests, and
`preview/workflows/common.md` forbids persistent settings changes. Those current
instructions remain in force for those pending adapters. No new
installer, model registry, migration engine, or `/drain` entry is proposed.

### One question, two roles, one project and harness

Before the first decompose or goal action, the native entry passes its explicit
`claude`, `codex`, or `copilot` harness identity and exact physical Git worktree
root to setup. Never infer the active harness from directories, search ancestors
for another project, or configure another harness. Existing project activation/
ownership checks still apply. Missing role files require the existing explicit
install/enable lifecycle, not creation by this question.

Use one form/question, not a wizard:

> Configure Domestique roles for **ROOT / HARNESS**?
> Implementer: **exact model ID or native inheritance**; reviewer: **exact model
> ID or native inheritance**. Existing values (including effort) are shown for
> confirmation, not pre-approved. For Claude/Codex, confirm each existing effort
> or choose a supported effort/native inheritance. Save the displayed minimal
> diff to these two role files (and Copilot's existing ownership receipt)?
> **Save setup only / Cancel**. Reload, then invoke your workflow again.

Show paths, inherited semantics, and any tracked-file consequences before
consent. No model menu is shipped: use the client's current supported choices,
not guesses from filenames or a dated list. Both roles may use the same model;
review independence comes from a **fresh reviewer context**, not a vendor or
price tier. A generated default, an empty model field, loading instructions,
and consent to run a goal are all **not consent to save setup**.

| State at entry | Small UX and permitted result |
| --- | --- |
| Unconfigured: no valid completion marker, including pristine generated defaults | Ask once for both roles; show defaults as suggestions only. No workflow until confirmed. |
| Partial: one role chosen/missing, malformed metadata, or interrupted setup | Show both current choices; stop for missing/unsafe files, otherwise explicitly reconfirm the pair. Never complete silently. |
| Confirmed explicit models, unchanged pair | No questionnaire or writes; check current native availability/effective dispatch before acting. |
| Confirmed inheritance, unchanged pair | No questionnaire or writes. Resolve native defaults for this session; inheritance is consent to that policy, not a pinned model. |
| Customized / unowned files | Owned edits: offer existing settings for confirmation and preserve unrelated bytes. Claude/Codex use scoped manifest/pristine snapshot evidence, not historical inode proof. Copilot additionally refuses identities outside its recorded creation/setup ownership. Unowned, unsafe or ambiguous files stop; no adoption through setup. |
| Model/effort unavailable, unsupported, substituted, or effective dispatch unknown | Stop before workflow/delegation; preserve prior files/confirmation. Report the role and reason; no fallback. |
| Explicit reconfiguration | The same question for both roles, with current values; save only the approved minimal diff, then reload/reinvoke. Cancel preserves the prior pair. |

Cancellation, an incomplete answer, and noninteractive missing input produce
**zero writes and no workflow** (including no Beads readiness/create/claim).
Noninteractive invocations may use an already confirmed pair but cannot perform
setup in this first release; they report the interactive setup/reinvoke action.
Malformed/duplicate fields require human repair, not a whole-file formatter.

### Native fields and one completion marker

Choices live only in these existing role files, relative to ROOT:

| Harness | Implementer / reviewer paths | Explicit selection | Native inheritance |
| --- | --- | --- | --- |
| Claude Code | `.claude/agents/implementer.md`, `.claude/agents/reviewer.md` | YAML frontmatter `model: "ID"`; optional `effort: "LEVEL"` | Write `model: "inherit"`; omit `effort` for inherited effort. |
| Codex | `.codex/agents/implementer.toml`, `.codex/agents/reviewer.toml` | Top-level TOML `model = "ID"`; optional `model_reasoning_effort = "LEVEL"` | Omit `model`; omit `model_reasoning_effort` for inherited effort. Never write a literal model named `inherit`. |
| Copilot | `.github/agents/domestique-v2-copilot-implementer.agent.md`, `.github/agents/domestique-v2-copilot-reviewer.agent.md` | YAML frontmatter `model: "ID"` | Omit `model`, meaning the native default. No invented effort field. |

Model and effort choices are independent for Claude/Codex. Existing explicit
efforts must be displayed and confirmed, not silently retained as an assumed
default when changing models. Omitting effort means native resolution, **not**
necessarily the selected model's default effort. Validate the resulting pair.
An existing Claude model alias may be kept only with displayed native resolution
and confirmation; it is not an exact-ID guarantee. New explicit choices use exact
IDs. No parent model, tools, permissions, MCP, trust, or global config is edited.

Store one logical per-harness completion marker **only in the implementer role
file**: a single comment line `# domestique-model-setup: JSON`, immediately
inside YAML frontmatter or at the beginning of TOML. JSON has exactly
`v` (integer `1`), `project` (absolute physical root string), `harness` (the
entry's enum), `implementer_sha256` and `reviewer_sha256` (lowercase SHA-256 hex).
Each digest covers the complete corresponding role file bytes with that one
marker line removed from the implementer. Reviewer files have no setup marker.
Reject duplicate/misplaced markers. This comment is ignored by native parsers;
it carries confirmation, never a second copy of model choices. No sidecar,
global configuration or parallel model registry is added.

Validate bounded UTF-8 regular files (at most 1 MiB each), unique scalar fields,
and the fixed paths before editing. Encode inserted YAML values as JSON-quoted
strings and TOML values as escaped basic strings using serializers; reject
control characters/newlines in model/effort input. Encode the marker with a JSON
serializer, never shell interpolation/eval. Patch only the selected scalar
values/removals and marker; preserve all other bytes, comments and modes.
If a lossless bounded patch cannot be established, stop for manual resolution.

At every entry compare the marker's project/harness and both computed hashes,
plus existing ownership. Unchanged confirmed files do not prompt again. Any
manual role edit, including instructions or effort, invalidates confirmation;
show the current settings once for explicit reconfirmation, not every run.
Changing another harness or using an alias does not affect this pair. A copied/
moved project does not inherit consent. The marker proves a confirmed file
pair under cooperative local operation, **not** availability or native dispatch.

### Native precedence, qualification and reload

Official sources consulted for this contract (2026-10-23):

- [Claude Code subagents](https://code.claude.com/docs/en/sub-agents):
  current documented model order is invocation parameter, role frontmatter,
  subagent environment default, then parent. `inherit` in frontmatter selects
  the parent model. Force-model settings and spawn hooks can override this;
  older versions differ and native allowlists can substitute models. Effort
  order is environment override, invocation effort, role effort, then session.
  The docs describe file watching with restart exceptions (including newly
  created agent directories), and `/tasks` model/effort display; neither proves
  a pre-dispatch enforcement API in the installed client.
- [Codex subagents](https://developers.openai.com/codex/subagents), redirecting
  to [agent configuration](https://learn.chatgpt.com/docs/agent-configuration/subagents):
  each role-file `model`/`model_reasoning_effort` overrides the value previously
  resolved from explicit spawn, `[agents]` defaults, then parent. If spawn or
  defaults select a model but neither supplies effort, that model's default
  effort is used. A role file setting only `model` preserves the previously
  resolved effort; it does not reset it. Omitting both fields allows native
  resolution, not necessarily direct parent inheritance.
- [Copilot custom-agent configuration](https://docs.github.com/en/copilot/reference/custom-agents-configuration):
  role frontmatter `model` selects the agent model; unset inherits the default.
  This is not proof that a particular CLI version can load, dispatch, or report
  the requested effective model, nor a documented hot-reload guarantee.

Available local **`codex --help` only** was consulted: it describes `--model`
and `--config` but does not establish custom-role reload or an effective-model
verification interface. No other native clients or model calls were run.
For all three adapters, use a **fresh client session after saving**, discover the
exact local role IDs, and explicitly reinvoke; do not rely on hot reload or
resume a previously loaded role context.

Domestique sends no conflicting spawn model/effort override to a confirmed
explicit role. Existing ephemeral `--implementer-model` / `--reviewer-model`
requests remain assertions to verify, not persistence or an override that can
defeat native role precedence. A conflict stops and offers explicit
reconfiguration. For inheritance, native session changes may change resolution;
validate the resolved models/efforts and any user provider restriction anew.
Keep current Copilot OpenAI-only request restrictions until explicitly changed
by a separately approved contract; never infer permission to change vendors.

Before saving, require supported native evidence that **both** proposed model/
effort selections are selectable and available with required tools in the
installed client; check applicable overrides, aliases and inherited resolution.
Unknown support or a defeating override stops without setup writes; do not
invent an API or launch a paid probe. This is a pre-save support check, not
proof of an observed dispatch.

After reload, before workflow/task dispatch, verify exact project-local role
loading, session-resolved selections and overrides using supported native
evidence. If effective selection or prevention of silent substitution cannot be
verified, stop without workflow or further writes. File syntax, a catalog
listing, a user assertion and this marker alone are not dispatch proof.
Actual **observed dispatch/reload qualification** belongs to **hq-7sm.6**, with
a separately user-approved budget. It is not a prerequisite to emitting guarded
instructions or saving choices that pass pre-save checks. Neither documentation
nor static tests clear that later gate, promise pre-observation knowledge or
authorize paid calls.

### Entry and lifecycle boundaries

Decompose-first and goal-first both run the same setup gate before Beads or
delegation. Any successful first confirmation/reconfiguration is **setup only**:
no planning beads, task claim, code, branch/commit, or goal cycle. Disclose the
writes, save only on explicit consent, then end with the fresh-session invocation
to repeat. In particular, the goal request that led to setup is consumed, not
queued for automatic continuation. Missing setup during unattended goal
execution is a stop, never permission to write configuration.

Reconfigure by invoking the harness's Domestique decompose entry with the exact
request **`configure role models`**, reserved as setup-only rather than a planning
brief. This uses the same form and storage, not a new command family. Normal
invocations after confirmation keep their existing action/epic/readiness gates:

| Harness | Decompose (also reconfiguration entry) | Goal requiring a fresh explicit epic request |
| --- | --- | --- |
| Claude | `/dom-decompose`; alias `/decompose` | `/dom-goal EPIC_ID`; alias `/goal EPIC_ID` |
| Codex | `$dom-decompose`; alias `$domestique-decompose` | `$dom-goal EPIC_ID`; alias `$domestique-goal EPIC_ID` |
| Copilot | `/dom-decompose`; alias `/domestique-v2-copilot-decompose` | `/dom-goal EPIC_ID`; alias `/domestique-v2-copilot-goal EPIC_ID` |

Aliases share exactly one pair/marker; no separate consent or configuration.
Ordinary/bootstrap loading stays read-only and grants no goal authority. An
ordinary bounded workflow can use a confirmed pair; if unconfirmed, stop before
delegation and direct the human to the same setup entry, not another wizard.
Standalone instruction loading does not synthesize a harness identity or start
setup. Direct execution paths must receive the explicit native-entry identity
and enforce the same gate; they cannot bypass it through the retained CLI.

Setup may dirty tracked Claude/Codex role files with disclosed consent. Before
goal execution, **all tracked/index dirtiness, including setup changes, requires
human resolution**. Do not auto-stage, commit, stash, discard or hide it. Copilot's
existing refusal of tracked native files remains. Guest mode keeps its existing
local-only footprint/exclusions and uninstall preservation; setup neither hides
tracked files nor expands excludes or changes repository instructions.

### Two-role write and ownership safety

Preflight both roles and the existing ownership data before the first write:
exact root/harness, active ownership, safe regular non-symlink/non-hardlinked
paths, readable bounded metadata, writable parents, proposed lossless patches,
pre-save native support checks, and explicit approval of the complete diff. Recheck input
bytes/identities immediately before publication; changes mean stop/re-prompt.
No task work occurs during this operation.

Prepare both outputs in memory. After consent, invalidate any old completion
marker first, write the reviewer update, then publish the implementer with the
new pair marker last. Use same-directory temporary files and atomic per-file
replacement, preserving modes; do not claim a two-file transaction. Re-read and
verify both outputs and required receipt writes before reporting setup success.
Any failure stops, reports exactly which paths changed, and grants no workflow
authority. A missing/stale marker, digest mismatch or receipt mismatch means
incomplete setup. Retain user bytes; clean only this operation's known temporary
files. Retry is the same explicit two-role preflight/question over current bytes,
not a journal, rollback engine or silent repair.

For Copilot, retain `files[PATH].identity` and `files[PATH].sha256` as immutable
**creation** facts in `.domestique-private/copilot-preview.json`. Add only an
optional `model_setup` object to each of the two existing role entries, containing
`identity` (post-write device/inode pair), `sha256` (complete post-write file hash,
including the implementer marker), and `removable` (boolean). It stores no model
names. Save these two objects together after both role writes; the confirmation
gate also requires both objects to match current bytes/identities. A failed
receipt save cannot yield a confirmed pair, even if the marker was published.
An explicit retry may record the approved current outputs after full preflight;
it must not reset creation facts or claim the interrupted operation succeeded.
Ownership checks recognize the creation identity or a recorded `model_setup`
identity. Same-identity byte edits remain owned customizations eligible for
reconfirmation, never automatic deletion. An identity matching neither record
is a replaced/ambiguous file requiring human ownership resolution, not adoption.

`removable` may be true only when that file matched its creation identity/hash,
or a prior matching `model_setup` with `removable: true`, at preflight and this
operation changed only approved model/effort/marker bytes. Otherwise it is false:
confirming existing owned custom instructions does **not** bless them for
deletion. Inspection continues to show customized versus creation, separately
from model confirmation. Repeat enable/shared update must recognize these owned
replacements but never rewrite them or reset hashes. Disable revokes first and
may remove only a matching creation file or a matching approved update with
`removable: true`; other edits remain with honest partial removal. Interrupted
writes with no matching recorded identity are retained for human resolution.
This is a bounded extension of existing ownership, not a new model registry.

Claude/Codex retain their existing snapshot/three-way update and scoped uninstall
rules. For Claude, the scoped `.claude/.domestique/manifest` inventory and
`base/.claude/agents/{implementer,reviewer}.md` pristine snapshots are management
evidence for the exact role paths, not historical inode records. Missing evidence
or unsafe/unmanaged paths refuse. Current owned customizations can be explicitly
confirmed; recheck safe current paths, identities and bytes within the operation.
Historical creation/setup inode matching above is specific to Copilot.
Setup never replaces pristine merge bases with customized bytes. Updates
preserve choices as local edits; changed role bytes invalidate the marker for
reconfirmation. Uninstall preserves modified files under existing semantics;
reinstall/generated defaults never imply prior consent. Copilot shared updates
remain project-write-free, including old five-definition layouts. No migration
or alias refresh is bundled with setup.

### Bounded adapter acceptance matrix

Offline tests can establish the following; they cannot substitute for hq-7sm.6.

| Case | Required observable result |
| --- | --- |
| Fresh generated defaults; decompose-first / goal-first, each harness | One two-role question; no consent assumed; approved setup ends without Beads/code/goal and asks for fresh invocation. |
| Cancel; one missing answer; noninteractive unconfigured | Identical project/receipt bytes and zero workflow/Beads calls. |
| Explicit pair; inheritance pair; same model for both | Correct native fields/omissions, valid pair marker; next unchanged invocation has no prompt/writes and still checks native readiness. |
| Model changed but old effort incompatible | Stop before writes/dispatch; never silently change effort. |
| Manual model/effort/body edit; copied root; another harness | Only the affected pair loses confirmation; no cross-project/harness writes or automatic adoption. |
| Owned customization; unowned/unsafe/malformed role; Copilot replaced identity | Confirmable owned settings preserve every unrelated byte; ambiguous/unsafe ownership or syntax refuses without writes. Claude/Codex ownership remains snapshot-based. |
| Short/legacy aliases; explicit reconfiguration; ordinary entry | Shared state; same setup-only path; ordinary cannot obtain goal authority or bypass the gate. |
| Marker invalidation, reviewer write, final implementer write, or receipt save fails | No success/workflow; factual partial state; explicit retry or human resolution; customized files remain protected on disable. |
| Copilot pristine minimal update versus customized update | Creation facts unchanged; current hashes truthful; only proven removable updates eligible for deletion. |
| Update, guest, uninstall; tracked setup dirtiness before goal | Choices/customizations preserved by existing lifecycle; no changed excludes/global settings; dirty goal execution stops for the human. |
| Unknown/unavailable model/effort support or defeating override before save | No fallback or setup write; report the gap. After reload unknown effective selection stops workflow/claim/delegation without altering the saved pair. Actual observed dispatch/reload tests remain budget-gated. |

Claude evidence is deliberately split: `test/guest.sh --current` checks real
installer output/alias equality and static protocol assertions (first/repeat,
inheritance, customization, cancellation, publication ordering and setup-only
boundaries). `test/upgrade.sh --current` and `test/uninstall.sh --current` use a
synthetic configured pair to exercise real snapshot merge/preservation behavior.
These do not execute an assistant questionnaire, inject runtime write failures,
or prove native loading/model dispatch. Other adapters and hq-7sm.6 remain pending.

## Workflows, dependencies and inspection

The remainder describes **current shipped Copilot preview behavior**, not its
pending first-use adapter above.

Shared policy/context loading is implemented in **hq-iyu.4**; execution remains
the native caller's job, not a Python loop manager. Entry instructions use the activated
project, exact local role IDs and the same immutable source revision.
Decompose plans through the existing user-managed `bd` CLI without coding.
Only explicit **Domestique goal plus an epic** authorizes its sequential loop;
native Copilot goal/autopilot, ordinary entry and natural-language planning do
not authorize queue draining. One bounded task is in flight, with an independent
review before close/commit, one commit per bead on a dedicated branch, explicit
stop conditions and no automatic push or merge. Ordinary stops after one bounded
explicitly assigned bead. Goal also defaults to one reviewed bead; only an
explicit larger user bound can continue, never more than 15 per session.
One fix pass at most. Clean worktree/index and dedicated known non-default
branch are required, with exact reviewed-path staging only. Never close an
unpassed bead. No-ready plus unfinished descendants means BLOCKED, not complete.

Beads is external and user-managed. Missing `bd`, missing configured project
state or an actual CLI failure stops with prerequisite guidance, not an empty
queue or success fallback. Definition loading and install/update/enable/disable/
inspect never initialize, open, convert or manage a database. Only explicitly
requested workflow actions call normal `bd`; a `.beads` directory alone is not
proof of operational readiness. Requested readiness requires a local `.beads`
discovery anchor to avoid accidental ancestor discovery AND successful normal
CLI version/status calls; no private schema or file-content test. Existing
project/user configuration remains bd's responsibility, including backend
selection. For the subprocess only, remove ambient `GIT_*`, `BEADS_*`, `BD_*`
overrides; env-only retargeted setups must be configured explicitly by the user
for this project instead. No config is read out or repaired by the loader.
Command failure/timeout refuses before delegation and reports command/exit while
withholding raw potentially sensitive output. There is no private DB bridge or
backend setup. Shared instructions run normal scoped create/show/ready/list/dep/
update/close directly after explicit consent/readiness; errors stop honestly.

Models, tools and MCP remain native or ephemeral session choices. Install no
model defaults, questionnaire or registry. Honor explicitly supported OpenAI
role selections with actual native exact-ID/capability confirmation; unavailable requested choices stop rather than silently
switching models/vendors. Do not alter authentication, trust or client settings.

### Exact Copilot entry and fresh clients

Shared public names use portable hyphenated Agent Skills names:

| Client | Planning only | Explicit goal |
| --- | --- | --- |
| Claude, released v1 | `/dom-decompose` | `/dom-goal EPIC_ID` |
| Codex, released v1 | `$dom-decompose` | `$dom-goal EPIC_ID` (or `/skills` selection) |
| Copilot, this preview | `/dom-decompose` | `/dom-goal EPIC_ID` |

Compatibility entries stay supported: Claude `/decompose`, `/goal`; Codex
`$domestique-decompose`, `$domestique-goal`; Copilot
`/domestique-v2-copilot-decompose`, `/domestique-v2-copilot-goal`.
Ordinary/bootstrap names, internal role IDs, models and provider-native policy
are unchanged. Both Codex goal entries retain `allow_implicit_invocation: false`;
both Copilot goal entries permit model loading, never implicit loop authority.

After enabling, editing definitions or disabling, restart/use a fresh Copilot
client and confirm the exact local skill/role IDs. Neither cached discovery nor
hot reload is guaranteed. In that client, natural planning can request
“Use Domestique decompose to plan this bounded change”; the explicit namespaced
entry is `/dom-decompose`. Planning does not authorize coding.
For the loop, request “Use Domestique goal for epic EPIC_ID” and explicitly select
`/dom-goal EPIC_ID`; native goal/autopilot is not Domestique goal.
The compatibility decompose skill was exercised in the bounded demonstration below, but the
goal skill returned `Skill not found: domestique-v2-copilot-goal`. The caller
recovered with the explicit retained CLI, not a successful goal skill load.
The separate read-only probe below confirmed corrected goal skill-tool loading,
not execution of its instructions or a new goal loop.
Your client must discover its own local definitions and approve required access.
Short-name naming/ownership tests are offline fixture evidence only, not new
model/native execution evidence. The unchanged workflow bodies retain the
separate historical qualification limits below; no all-client v2 claim is made.

Copilot shell-command approval and file-path approval are separate. Approve
only the necessary project, shared installation and installed Python paths
through the client's normal permission controls. An allowed Python command can
still be denied when its executable path lies outside the allowed directories;
account for the interpreter's resolved location when it is a symlink.
Session-local `--add-dir` is one supported way to grant directory access.
The installer does not change global trust or permissions, and blanket
`--allow-all` access is not required.

### Refresh existing five-definition activations

The new source accepts original receipts, fixed five-name `native_ids` and their
**original exact six-pattern exclusion blocks**. Workflow guards, inspect and
disable use that recorded layout. Update/repeat enable preserve it and report
legacy layout; they do not falsely claim short names were added.

After a shared-source update, inspect the project and review each customized
adapter before explicitly disabling and re-enabling to obtain the seven-file
layout. Disable removes only unchanged owned files; edited adapters remain and
produce partial disable. Preserve and reconcile each customization yourself,
complete disable, then freshly enable and deliberately reapply appropriate
reviewed edits. Do not delete private customizations to force reactivation.
Restart the native client and confirm IDs. Shared-source updates do not rewrite
local metadata, change creation hashes or migrate aliases in place.
Released v1 users obtain aliases via existing ordinary installer/merge semantics.

### Existing goal skill metadata

Fresh activations from the corrected source omit
`disable-model-invocation: true` on the Copilot goal skill. Old activations set
that model-loading prohibition; the recorded model registry omitted the goal
even though the request was explicit.
Normal skill discovery is not loop authority: the wrapper still requires an
explicit user Domestique goal request naming an epic, and the bare loader is
read-only **SETUP ONLY**, with no Beads calls or queue authority. Operational
use still requires actual user intent, `--domestique-goal`, `--epic` and successful
`--ready`; native goal/autopilot is not authorization.

Shared-source update and repeat enable preserve existing owned metadata
byte-for-byte, including this old flag and private customizations. They do not
migrate wrappers. After updating to the corrected source, unchanged definitions
can be disabled and freshly enabled to receive the new metadata. If definitions
are customized, disable retains those files and may report partial cleanup;
do not discard private edits to force reactivation. Alternatively, manually
review the local goal `SKILL.md` and remove only that metadata restriction,
preserving the explicit-intent wording. Manual edits remain customizations
against the original creation hashes and require fresh native confirmation
before operational `--confirm-native` use. Reload/restart the client and check
the exact skill ID; no hot reload is promised.

Metadata checks or read-only `copilot skill list --json` results are only
catalog evidence, not proof that the model's skill tool can load this entry.
The separately authorized native probe below supplied that narrow confirmation
through an actual skill-tool call and matching injected project-local body.
It did not execute the loader, establish readiness or exercise activation.

Exact standalone loader forms (substitute your actual project, brief and epic):

```sh
# Read-only instruction load: no Beads call.
"$HOME/.local/bin/domestique2" workflow decompose --project "/physical/project root"
# Explicit planning request; checks existing user-configured bd, never initializes it.
"$HOME/.local/bin/domestique2" workflow decompose --project "/physical/project root" --brief "Plan one bounded change" --ready
# Explicit Domestique goal request plus epic; not native autopilot consent.
"$HOME/.local/bin/domestique2" workflow goal --project "/physical/project root" --epic EPIC_ID --domestique-goal --ready
```

Model choices belong to this native session, not install/update metadata.
Optional loader `--implementer-model ID` and `--reviewer-model ID` carry literal
ephemeral requests only; confirm actual native exact OpenAI IDs/capabilities
before dispatch. An unavailable requested choice means stop, never substitute
a model/vendor or change global defaults/trust. No client or model is invoked
by these loaders; `--ready` alone calls existing Beads for prerequisites.

### Read-only inspect

```sh
"$HOME/.local/bin/domestique2" inspect "/physical/project root"
"$HOME/.local/bin/domestique2" --inspect "/physical/project root"
# From the exact physical Git root only:
"$HOME/.local/bin/domestique2" inspect
```

Inspection requires a valid installed machine, not merely a source checkout.
It reports machine/current's checked selected revision (also from a retained
old CLI), the target's receipt state and recorded definition paths (seven fresh,
five legacy), and the
recorded exclusion contribution without changing it. Original creation hashes
and identities determine unchanged/customized/replaced/missing statuses, never
updated templates. An active receipt with missing/unreadable/tracked files or
invalid exclusions reports partial/unknown, not pristine activation. Corrupt,
incompatible, copied or missing receipts never grant ownership to leftover files.
A partial/disabled receipt remains partial even when remaining files match.

Unavailable, non-Git, bare, subdirectory, unsafe, symlinked and unreadable targets
refuse explicitly, without inferring absence or searching for another project.
Exit **0** means complete target ownership observations, including absent preview
or customized files; **1** means refusal or partial/unknown ownership; **2** means
misuse. Legacy classification limitations alone do not change a complete preview
ownership report's exit. Errors withhold raw metadata and Git diagnostics;
paths are escaped. Reads do not require target/exclusion write permission.

Legacy observations reuse the existing bounded lifecycle marker paths and
policy/command anchors only. Named legacy/experimental footprints or Domestique
references are evidence, not proof of a complete installed generation. Actual
indexed evidence is labeled tracked; untracked is **not proof of guest mode**.
Claude/Codex/Copilot containers alone are ambiguous, not installed Domestique.
Other legacy presence, generation, customization and guest mode remain unknown;
there is no ancestor/global scan, legacy baseline, metadata parser or registry.

Inspection separates source checkout, installed machine and target filesystem
discovery from effective native client loading and **workflow readiness: NOT
CHECKED**. It never installs, repairs, changes exclusions, opens Beads or invokes
native/model/MCP clients; it makes no effective-permission or readiness inference.
Use the explicit installed path above: unchanged old `dom`/`dom2` aliases may
still reach older scripts, not this preview.

## Bounded native qualification (2026-09-18)

The hq-iyu.6 demonstration used a disposable installation and project, a fresh
Copilot caller session, and explicitly initialized user-managed Beads. Database
initialization was test setup, not installer behavior.

| Observation | Result |
| --- | --- |
| Runtime source | `ad807064b8b18f89ab60a0cf8e4149ab308bac15` |
| Environment | macOS, Copilot CLI 1.0.86, Beads 1.2.2 |
| Native models | Explicit `gpt-6-astra` for caller, implementer and reviewer |
| Native wall time | 174.31 seconds across planning, goal and both roles |
| Native usage | 175.97425 cumulative AI credits, 24 model requests |
| Run limits | 200-credit soft cap and 300-second wall limit |

Native decompose created one epic and one child without changing code or the
Git index. The attempt-9 goal skill tool returned
`Skill not found: domestique-v2-copilot-goal`; the available-skills registry
listed ordinary/decompose but not goal. The caller recovered through the
explicit retained CLI with Domestique intent, epic and readiness flags.
That direct-CLI goal then dispatched
`domestique-v2-copilot-implementer` and a fresh
`domestique-v2-copilot-reviewer`, both with the requested native model. The
reviewer independently read the actual file and performed the bounded checks.
Only after its PASS did the caller commit the single expected file and close
the child. The disposable epic stayed open; there was no push or merge.
The fixture and its activation were removed after evidence capture, and project
B received no definitions.

The generator correction removes only the Copilot goal's
`disable-model-invocation: true` restriction for new activations; intent and
readiness gates remain. The full workflow run at `ad80706` predates this
two-line template visibility fix; core workflow code is unchanged. Offline
regressions and the older run do not themselves prove corrected skill loading.

A separate **2026-09-18 read-only goal-entry probe** used one fresh actual
Copilot invocation and exact freshly emitted candidate definitions in a unique
disposable Git project. This was explicitly an emitted-template discovery
fixture, not an installation/activation or lifecycle test.

| Entry-probe observation | Result |
| --- | --- |
| Candidate generator | `preview/native.py` SHA-256 `350db6bb92d914a542a185d19fb2fa1af68134483b4f4c59737238a2ae8356df` |
| Environment / actual model provider | macOS, Copilot CLI 1.0.86; `gpt-6-astra` / `openai-responses` |
| Actual skill tool | One `domestique-v2-copilot-goal` execution start and successful completion |
| Injected context | `skill.invoked` identified the unique project-local path; body and delivered-context SHA-256 matched the exact candidate output |
| Native wall time | 12.408678 seconds from process launch |
| Native usage | 10.05175 AI credits, 2 model requests; separate from attempt 9 |
| Run limits | 30-credit soft cap, one 60-second monotonic deadline; no retry or substitution |

Only `skill` was available; MCP servers were disabled session-locally.
The explicit read-only instruction prohibited executing the skill body or
locator. No shell, readiness, Beads, goal, delegation or file-change actions
ran. The fixture's byte/mode/path/identity snapshot was unchanged, and its
owned root was removed after evidence capture. No permission or trust changes
were required. This resolves corrected goal discovery/loading only: the full
decompose/goal/roles cycle was **not rerun** after the metadata fix.

The companion lifecycle demonstration covered install, inspection, shared
update visible to the next workflow without adapter rewrites, retained source
paths, customization preservation and unchanged-only disable. It is separate
from the real native model exercise, not a substitute for it.

The earlier full workflow run restricted its tool catalog to 13 needed built-ins
using Copilot's session-local `--available-tools`: `bash`, `read_bash`,
`stop_bash`, `list_bash`, `view`, `rg`, `glob`, `apply_patch`, `task`, `skill`,
`read_agent`, `write_agent` and `list_agents`. This reduced tool-schema context
from an earlier 132-tool, 36,343-token catalog to 4,283 tokens. It is an optional
validation profile, not an installed tool default or a requirement to remove
your integrations. No global model, MCP, trust or authentication settings were
changed.

The workflow table's usage is attempt 9's final cumulative figure, including
planning and both roles; do not add the planning subtotal again. It excludes
earlier failed attempts and the separately tabulated entry probe. Prior failed
costs and unknowns remain separate. A soft credit cap is not a guaranteed billing
ceiling.
This result is not a readiness flag stored in receipts: default instruction
loading and inspection still do not prove that another client, project or model
can execute the workflow. No real HOME installation, release publication,
Claude/Codex v2 parity or exhaustive platform/model qualification is asserted.

## Portable reuse and acceptance limits

The preserved `.claude/commands/decompose.md`, `.claude/commands/goal.md`,
`.claude/agents/implementer.md` and `.claude/agents/reviewer.md` are ignored local
source material, absent from `19deeab`. Preservation/hashes are not blanket
approval. hq-iyu.4 independently reviewed these four texts; the hashes and
keep/drop decisions are in `preview/workflows/provenance.md`. Adapted shared
policy replaces obsolete vendor/model bindings, full historical-suite mandates,
broad staging, export/database commits and false no-ready completion/queue
authority. No ignored configuration was copied into native project files or
activated as Claude policy in this worktree.

The hq-iyu.5 inspector uses existing preview receipt/Git/read-only validation
helpers in a small `preview/footprint.py`. Bounded review of retained `display`,
`stamp`, `git_root` and `resolve_context` informed escaped paths and honest
unreadable handling; no historical inspector/framework was imported. Exact-root
preview conventions apply, not the retained inspector's alias/ancestor discovery.

Deferred/out of scope: generated executable bundles, launcher ABIs, packet or
observation engines, custom YAML/TOML classifiers, project/model registries,
private DB management, global retirement, automatic ABI2/3 migration, native
hot reload, release signing/distribution and exhaustive platform/provider
matrices. Deferred work is not a preview release dependency.

The earlier bounded demonstration supplies evidence for decompose and the
retained-CLI goal/custom-role/review/commit/closure path. The separate native
probe supplies corrected goal skill discovery/loading evidence, not a new
full-cycle run. Static fixtures or catalog listing alone establish neither.
These results do not qualify the deferred framework or imply that preexisting
ancestor/global client definitions are hidden or removed.
Further native demonstrations require explicit bounded
consent and available prerequisites. Without either, report **BLOCKED /
NOT READY**, never fabricate usability. The preview does not install into the
real HOME or publish a release as part of qualification.
