# Small Copilot-first preview

**MACHINE + PROJECT DEFINITION LIFECYCLE IMPLEMENTED / WORKFLOWS NOT READY.**
The hq-iyu.2–.3 source implements installation, explicit update, offline
version/help, and Copilot-only project enable/disable with dry-run.
Inspect and project/Beads/native workflows are not implemented under this
contract. The later native acceptance demonstration is still required.
Documentation, local fixture tests, source checkout, old passing logs and
discoverable metadata do not establish workflow readiness.

## Boundary and source

Support the observed macOS environment and Copilot first: install once from a
trusted, explicitly selected Git revision, explicitly enable one project, and
update the shared workflow source once. Released Claude/Codex v1
`domestique.sh` and `update.sh`, including their existing updater semantics,
remain unchanged. No promise of other-platform or other-provider v2 parity.

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
instructions remain downstream work. Neither the historical package runtime nor ABI3
payload/transport is on this execution path. `install-v2.sh` has been replaced
for **this preview contract only**; it no longer accepts the historical package
bootstrap grammar and does not migrate its installations.

## Commands and availability

The hq-iyu.2 and hq-iyu.3 rows below are implemented. Inspection and workflow
names return an explicit unavailable error, not legacy fallback or successful
workflow execution. `REV` must explicitly resolve to a commit in
the trusted source; there is no default branch selection or implicit download.

| Invocation (availability by owning task) | Routine behavior | Owning task |
| --- | --- | --- |
| `install-v2.sh --source CHECKOUT --ref REV` | Install the selected trusted local Git source revision and stable command; no project activation. | hq-iyu.2 |
| `domestique2 update --ref REV` | Prepare a revision from the recorded source, then switch the owned current pointer; no project rewrites. | hq-iyu.2 |
| `domestique2 enable [TARGET] [--dry-run]` | Install five local Copilot definitions at the exact physical Git worktree root. Omitted target requires cwd itself to be that root. | hq-iyu.3 |
| `domestique2 disable [TARGET] [--dry-run]` | Revoke the receipt, remove only unchanged owned definitions, retain edits and report partial removal. | hq-iyu.3 |
| `domestique2 workflow TYPE --project ROOT` | Reserved thin-loader shape; currently refuses with explicit forthcoming-workflow guidance. | hq-iyu.4 |
| `domestique2 inspect [TARGET]` | Read-only shared-revision and selected-project ownership report; omitted target uses the current worktree. | hq-iyu.5 |
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
Reserved `inspect` and `--inspect` accept at most one literal target and report
unavailable. Unknown/duplicate/empty options, flags in value positions
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

For future workflow code, `preview.machine.resolve_source(root)` is the small
read-only internal API returning one checked absolute revision `Path`. Retain
that path for the whole workflow and delegated roles rather than reading
`current` again. Retained revision CLI help/version also remain callable by
their immutable path; management updates must use the current launcher.

### Bounded local validation

Run only the new scope, not the historical ABI suites:

```sh
python3 -B -W error test/preview-machine-tests.py
python3 -B -W error test/preview-project-tests.py
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
These are definition/machine-lifecycle checks, with no native/model/network/Beads
calls or real HOME installation. Static emitted-command checks are not native
discovery or workflow proof. Historical ABI/bootstrap/inspector suites are not
part of this qualification stage.

## Explicit project ownership

Enable/disable require a valid installed machine runtime but do not write it,
update source, or use the historical `v2/` modules. TARGET must name the exact
physical Git worktree root: subdirectories, symlink paths, non-Git directories
and bare repositories refuse, including default cwd if it is a subdirectory.
Managed machine release checkouts cannot be activated.

```sh
"$HOME/.local/bin/domestique2" enable "/physical/project root" --dry-run
"$HOME/.local/bin/domestique2" enable "/physical/project root"
"$HOME/.local/bin/domestique2" disable "/physical/project root" --dry-run
"$HOME/.local/bin/domestique2" disable "/physical/project root"
```

Only these five local Copilot definitions and the single JSON receipt
`.domestique-private/copilot-preview.json` belong to activation:

- `.github/skills/domestique-v2-copilot/SKILL.md`
- `.github/skills/domestique-v2-copilot-decompose/SKILL.md`
- `.github/skills/domestique-v2-copilot-goal/SKILL.md`
- `.github/agents/domestique-v2-copilot-implementer.agent.md`
- `.github/agents/domestique-v2-copilot-reviewer.agent.md`

#### Thin loader contract for hq-iyu.4

Each definition references the absolute stable installed launcher with this
simple command shape (paths are literal shell-quoted, including spaces, quotes
and `$`):

```text
ABSOLUTE_LAUNCHER workflow TYPE --project ABSOLUTE_PHYSICAL_ROOT
```

TYPE is `ordinary`, `decompose`, `goal`, `implementer` or `reviewer`. These
commands currently validate grammar and the machine runtime, then return **1**
with explicit `forthcoming hq-iyu.4` guidance; they execute no native or Beads
actions. This is a reserved command shape, not a new launcher ABI or an engine.
The wrappers request shared instructions and report load errors, rather than
baking a permanent stop prompt into a local file. Future shared code can
therefore work without replacing locally edited wrappers.

Frontmatter contains only these exact `name` / `description` pairs:

| Name | Description |
| --- | --- |
| `domestique-v2-copilot` | Load the shared Domestique Copilot instructions. |
| `domestique-v2-copilot-decompose` | Load Domestique planning instructions without coding. |
| `domestique-v2-copilot-goal` | Load an explicitly requested Domestique epic workflow. |
| `domestique-v2-copilot-implementer` | Implement one caller-assigned Domestique task. |
| `domestique-v2-copilot-reviewer` | Independently review one caller-assigned Domestique task. |

Goal additionally has `disable-model-invocation: true` and requires an explicit
Domestique goal request naming an epic, not native goal/autopilot. No model,
tool, MCP defaults or permission grants are emitted. Delegated roles await the
caller's bounded task and retained source context; their locator is for the
caller, not permission to start a workflow or resolve `current` independently.
hq-iyu.4 must use one retained source revision for the workflow and roles and
require a valid matching receipt with `state == "active"` before workflow
actions. Definition installation alone is **not operational workflow readiness**.

#### Ordinary ownership and removal

The bounded JSON receipt's `kind` is `domestique-copilot-preview`. It records:

- `project`: physical root, independently resolved Git directory and common
  directory, each with device/inode identity (copied/moved/foreign roots refuse).
- `installation`: machine root identity and stable launcher path, identity and
  hash; `native_ids`: the five exact names, independent of selected source ref.
- `files`: only created native relative paths, their creation identities and
  original SHA-256 hashes (`null` only for a known incomplete write).
- `directories`: only created parents and their identities; `receipt_identity`
  identifies this state file, not a foreign identical copy.
- `token`, `exclusion`: exact six-line-pattern block plus delimiters, original
  prefix length/hash, optional separator newline, exclude identity and
  `planned` / `present` / `removed` state.
- `state`: `partial-enable`, `active` or `disabled`. Only `active` permits future
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
`info/exclude` for exactly the five native files and receipt, never entire
containers or `.beads`. An appended block uses
`# domestique-copilot-preview BEGIN TOKEN` / `END TOKEN` delimiters and six
root-anchored literal patterns. Preserve host bytes and mode, including
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

## Workflows, dependencies and inspection

The following workflow behavior belongs to **hq-iyu.4, not this implementation**.
Native project-local ordinary/decompose/goal entrypoints will use the activated
project, exact local role IDs and the same immutable source revision.
Decompose plans through the existing user-managed `bd` CLI without coding.
Only explicit **Domestique goal plus an epic** authorizes its sequential loop;
native Copilot goal/autopilot, ordinary entry and natural-language planning do
not authorize queue draining. One bounded task is in flight, with an independent
review before close/commit, one commit per bead on a dedicated branch, explicit
stop conditions and no automatic push or merge.

Beads is external and user-managed. Missing `bd`, missing configured project
state or an actual CLI failure stops with prerequisite guidance, not an empty
queue or success fallback. Definition loading and install/update/enable/disable/
inspect never initialize, open, convert or manage a database. Only explicitly
requested workflow actions call normal `bd`; a `.beads` directory alone is not
proof of operational readiness. There is no private DB bridge or backend setup.

Models, tools and MCP remain native or ephemeral session choices. Install no
model defaults, questionnaire or registry. Honor explicitly supported OpenAI
role selections; unavailable requested choices stop rather than silently
switching models/vendors. Do not alter authentication, trust or client settings.

The forthcoming hq-iyu.5 inspect command will report the selected shared revision, target activation, unchanged/
customized/missing owned files and legacy v1/experimental presence or unknown
state. Compare with receipt creation hashes, not current templates. It does not
repair, modify exclusions, scan the whole machine, open Beads or invoke a native
client/model/MCP; unreadable and partial states remain honest unknowns.

## Portable reuse and acceptance limits

The preserved `.claude/commands/decompose.md`, `.claude/commands/goal.md`,
`.claude/agents/implementer.md` and `.claude/agents/reviewer.md` are ignored local
source material, absent from `19deeab`. Preservation/hashes are not blanket
approval. Independently review portable policy text before adapting it into
repository-owned shared instructions in hq-iyu.4. Replace obsolete vendor/model
bindings, full historical-suite requirements and old queue-authority rules
with this bounded plan. Do not copy complete ignored configuration or activate
these Claude files in the new worktree.

For hq-iyu.5, selected read-only helpers in `domestique2.sh`'s `inspect_main`
(for example `git_root`, `resolve_context`, `stamp`, `display` and report
formatting helpers) are candidates for individual review/adaptation. This is
not approval to import the whole inspector, its customization classifiers, the
legacy setup engine or ABI3 `v2/handoff.py` / `v2/workflow_protocol.py`.

Deferred/out of scope: generated executable bundles, launcher ABIs, packet or
observation engines, custom YAML/TOML classifiers, project/model registries,
private DB management, global retirement, automatic ABI2/3 migration, native
hot reload, release signing/distribution and exhaustive platform/provider
matrices. Deferred work is not a preview release dependency.

Readiness requires the later, explicitly consent-gated small native
demonstration in a fresh isolated Copilot session: A discovers the exact local
skills/roles; decompose creates a small plan without coding; explicit goal
completes one bounded bead with requested native models and independent review.
Untouched B receives no definitions. A shared update is used by the next
workflow without rewriting adapters; edits survive, disable retains customized
files and inspect reports reality. Static fixtures are not this proof. Without
bounded native/model consent or a necessary prerequisite, report **BLOCKED /
NOT READY**, never fabricate usability. This checkpoint runs no future-feature
engine tests and performs no native/model or real-HOME demonstration.
