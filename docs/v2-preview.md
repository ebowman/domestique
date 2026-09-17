# Small Copilot-first preview

**NEW PREVIEW NOT IMPLEMENTED / NOT READY.** This is the product scope and
proposed command contract for hq-iyu, not an installation guide for today's
scripts. The commands below become usable only when their owning tasks land
and the native acceptance demonstration passes. Documentation, source checkout,
old passing logs and discoverable metadata do not establish workflow readiness.

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

The new runtime will be small repository-owned `preview/` source, a thin stable
command, native project-local adapters and one shared workflow source.
Neither the historical package runtime nor ABI3 payload/transport is on that
future execution path. No runtime source is added by this documentation step.

## Proposed commands

All commands in this table are **proposed, not currently available under this
contract**. `REV` must explicitly resolve to a commit in the trusted source;
there is no default branch selection or implicit download.

| Proposed invocation | Routine behavior | Owning task |
| --- | --- | --- |
| `install-v2.sh --source CHECKOUT --ref REV` | Install the selected trusted local Git source revision and stable command; no project activation. | hq-iyu.2 |
| `domestique2 update --ref REV` | Prepare a revision from the recorded source, then switch the owned current pointer; no project rewrites. | hq-iyu.2 |
| `domestique2 enable [TARGET]` | Explicitly opt the selected physical Git worktree into Copilot only. Omitted target uses the current worktree. | hq-iyu.3 |
| `domestique2 disable [TARGET]` | Remove only unchanged owned local definitions; retain edits and report partial removal. | hq-iyu.3 |
| `domestique2 inspect [TARGET]` | Read-only shared-revision and selected-project ownership report; omitted target uses the current worktree. | hq-iyu.5 |
| `domestique2 --inspect [TARGET]` | Alias of `inspect [TARGET]`, not an installation or repair operation. | hq-iyu.5 |
| `domestique2 version` / `domestique2 --version` | Report the selected source revision offline. | hq-iyu.2 |
| `domestique2 help` / `domestique2 --help` | Describe only supported commands and prerequisite boundaries. | hq-iyu.2 |

The install location is
`${XDG_DATA_HOME:-$HOME/.local/share}/domestique-preview`; the stable executable
is `$HOME/.local/bin/domestique2`. Installation writes only owned source
revision directories, the current pointer and that command. No shell startup,
PATH, aliases, default branch, native global definitions or project registry
are changed. Existing `dom`/`dom2` aliases may still invoke older scripts.

Missing source/ref, dirty or foreign destinations, unsafe paths, an unowned
command collision or incompatible experimental installation cause refusal.
Do not adopt even identical unowned files. No force, automatic migration,
`git pull` merge, auto-update or release download. Prepare before switching;
failure retains the old selection. Retain prior revisions, without garbage
collection. Updates affect the next workflow; running workflows and delegated
roles retain one immutable source revision resolved once at workflow entry.

## Explicit project ownership

Enable is restricted to the exact physical Git worktree. Only these local
Copilot definitions and one small `.domestique-private` preview ownership
receipt belong to activation:

- `.github/skills/domestique-v2-copilot/SKILL.md`
- `.github/skills/domestique-v2-copilot-decompose/SKILL.md`
- `.github/skills/domestique-v2-copilot-goal/SKILL.md`
- `.github/agents/domestique-v2-copilot-implementer.agent.md`
- `.github/agents/domestique-v2-copilot-reviewer.agent.md`

Adapters reference the shared workflow source, not a copied engine. The receipt
records project identity, exact created paths and their original content
hashes. Hash comparisons establish unchanged versus customized bytes, **not**
approval of arbitrary native metadata or effective permissions.

Refuse tracked/index-only, symlinked, unknown or incompatible target collisions
before writing. Repeat enable preserves owned edits byte-for-byte. Disable
removes only unchanged owned definitions, retains customized/unowned material
and reports partial state. Never rewrite root instructions, settings, hooks,
the index or tracked `.gitignore`; never initialize or hide `.beads`.

The only Git exclusion change is an exact owned contribution to the Git-common
`info/exclude` for the created private paths. Preserve all host bytes and record
the precise contribution; do not claim ownership of preexisting matching lines.
Disable removes only a contribution proven to be its own. Missing/unsafe
exclusion parents refuse before publication. Shared Git-common files and linked
worktrees can make attribution ambiguous: retain or refuse, never guess, crawl
siblings, or remove a shared contribution on another worktree's behalf.

Safety assumes trusted local source and cooperative single-writer operations,
normal Git/filesystem validation and an atomic owned current-pointer switch.
It does **not** promise hostile same-owner/concurrent-writer atomicity, native
sandboxing or invisibility. Existing ancestor/global definitions may still
advertise Domestique; enabling or disabling this preview does not retire them
or erase cached native context. Use fresh clients when qualifying discovery.

## Workflows, dependencies and inspection

Native project-local ordinary/decompose/goal entrypoints use the activated
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

Inspect reports the selected shared revision, target activation, unchanged/
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
tests and performs no native/model/installation demonstration.
