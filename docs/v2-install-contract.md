# Proposed V2 install and activation contract

Contract **V2/1**, frozen by **hq-1t9.1**, 2026-09-16; baseline `020c05c`.
**NOT PUBLISHED; PARTIALLY IMPLEMENTED.** hq-5jc.4 implements the internal
local package/publisher API; hq-1t9.2 adds the verified bootstrap/management
boundary and hq-1t9.4 the internal project records/preflight/guarded helper.
Public provider enable/loaders remain hq-5jc.7, not this internal checkpoint.
See [source boundary](v2-source-boundary.md).
Acceptance authority for hq-1t9's
install-once/project-opt-in boundary, not runnable setup instructions. The
[README](../README.md) and [design history](install-upgrade-design.md) describe
the implemented preview and historical installations, not this proposed CLI.
The [normative interfaces appendix](v2-install-interfaces.md) is the sole V2/1
authority for record grammar, bindings, transaction facts and native metadata
admission. This document owns commands, effects, inventories and acceptance.

`dom2` is the operator's developer-checkout alias, not the installed interface.
Nothing here changes it, `dom`, shell startup, personal models, URLs or installations.
hq-5jc.3 owns separate `domestique2.sh`/`update2.sh` artifacts and preservation of
the v1 `domestique.sh`/`update.sh` channel, including downloaded updaters,
normal/guest and source/environment overrides. Never serve V2 at `main/domestique.sh`.

## 1. Command grammar and effects

Grammar owner: hq-1t9.2; operation owners below. `TARGET` defaults to CWD `.`.
No provider autodetection, dependency install, PATH edit or fallthrough to V1.
Guest/private describes **ownership**, not an activation mode.

| Accepted command | Selection/default; allowed options | Read, network and write scope | Owner |
| --- | --- | --- | --- |
| `install-v2.sh (--version V \| --source PATH)` | Exactly one source selector; optional `--dry-run` | Verify selected package; network only for a non-retained release; write runtime and launcher only | hq-1t9.2; publisher hq-5jc.4 |
| `domestique2` | Read-only help plus the same status projection as `inspect .` | No network/writes; installation is not activation | hq-1t9.2, hq-1t9.6 |
| `domestique2 enable [TARGET]` | Optional `--platform P`, `--dry-run`; fresh default Claude, otherwise active provider union | Read installed runtime and exact target/Git metadata; write selected target native leaves/private state/exclusions only | hq-5jc.7; preflight hq-1t9.4 |
| `domestique2 disable [TARGET]` | Optional `--platform P`, `--dry-run`; omission selects all recorded providers, including disabled leftovers | Same project scope; remove eligible leaves/revoke selected activation, never machine writes | hq-1t9.5 |
| `domestique2 update (--version V \| --source PATH)` | Exactly one source selector; optional `--dry-run`; no target/provider | Machine package/launcher-state reads, verified publication and active switch only; network as for bootstrap | hq-1t9.3 |
| `domestique2 inspect [TARGET]` | No flags beyond help; aliases below | Exact bounded project, runtime and known old global inventory; no writes/network | hq-1t9.6 |
| `domestique2 retire-global --platform P` | Selection required; optional `--dry-run`; no target | Read exact legacy global leaves/provenance; write only eligible old advertisements and retirement bookkeeping | hq-1t9.7 |
| `domestique2 version` or `domestique2 --version` | No value/options | Report contract/launcher ABI and validated active package identity, or unavailable/invalid; no network/writes/project reads | hq-1t9.2, hq-1t9.6 |
| `domestique2 help [COMMAND]`, `domestique2 --help`, `domestique2 -h` | Known command or omission | Static usage, no filesystem discovery/network/writes; exit 0 | hq-1t9.2 |

Parsing is all-or-nothing before operation preflight:

* Command is first, except the exact aliases `domestique2 --inspect [TARGET]`
  and `domestique2 TARGET --inspect`. They mean `inspect [TARGET]`, not enable.
  A positional target without a command is misuse. `--inspect=TARGET` refuses.
* After a command, its flags may precede/follow its sole target. Value flags
  accept `--flag VALUE` and `--flag=VALUE`. Empty values/targets, missing values,
  duplicate flags (even identical), extra targets/commands, unknown commands,
  selectors or flags, and inapplicable/conflicting options exit 2 without writes.
* A final `--` is accepted as an empty terminator; arguments after it refuse.
  A flag-looking target must use a non-flag spelling such as `./-project`.
  Spaces, quotes and backslashes are literal argv, never reparsed/evaluated.
* `COMMAND --help` and `COMMAND -h` are accepted only alone after a known
  command; bootstrap accepts standalone help too. Help does not mask otherwise
  malformed argv. `--version V` is selection only on bootstrap/update;
  installed standalone `--version` is reporting only.
* No `--global`, `--local`, `--guest`, `--no-guest`, `--force`, `--with-beads`,
  `--state-only`, `--uninstall`, `--purge-beads`, model/tool/MCP/profile switches,
  migration/recovery/GC commands or source URLs in `--source` are accepted.
  Unsupported operations fail explicitly; there is no force/adoption bypass.

Exactly seven selectors remain: `claude`, `codex`, `copilot`, `both`
(Claude+Codex, **not** Copilot), `claude-copilot`, `codex-copilot`, `all`
(all three). Explicit enable selection is union with currently enabled
providers, never subtraction. Omission reuses a nonempty active union;
with no enabled providers it selects Claude. Re-enabling retained disabled
providers validates identity and compatible leaves before reactivation.
Disable selects an intersection, not an addition; a selected absent provider
is a no-op only if its exact inventory has no conflicting evidence.
Machine install/update packages all providers and has no provider selection.

**Status contract** (operation owners above): 0 means complete supported operation/
report, including genuine no-op/absence/customization; 1 means refusal, unavailable
prerequisite, unsafe/corrupt/foreign/mixed/partial state, incompatible ABI, pending
recovery or runtime failure; 2 means argv misuse. Report separate dimensions:
`runtime`, `activation[provider]`, `compatibility`, `customization`,
`legacy-global`, `recovery`, `native-evidence`, `beads-readiness`.
Known disabled/absent inspection can return 0; unreadable scope/inconsistent receipt
returns 1. Unobtained native evidence is `BLOCKED`/`unknown` even with structural exit 0.
Diagnostics contain escaped paths/reasons, not native values/content.
Prerequisites: existing Bash 3.2+, Git, SHA-256/filesystem utilities; official
fetch also curl/tar; inspection Python 3.9+ stdlib. Missing tools refuse, never install.

**Dry-run** runs only the trusted bootstrap/installed verifier/planner, never
candidate scripts, installed resolver/bridge, native clients or Beads. Explicit
release fetch and owned private staging outside destinations are allowed, but no
destination directory/lock/receipt/journal/exclusion/launcher/pointer writes.
Never stage user metadata. Apply repeats validation; failed preview blocks apply.
No-op application preserves destination bytes, modes, mtimes and membership.

## 2. Package selection, verification and machine state

Owners: hq-5jc.3 (channel/major), hq-5jc.4 (package/publisher),
hq-1t9.2 (bootstrap/launcher), hq-1t9.3 (update/rollback).

`V` is exact stable `2.MINOR.PATCH`, canonical nonnegative decimals. No `latest`,
ranges, branches, `main`, prereleases, `v` prefix or implicit default release.
Bootstrap/update precedence: (1) reject both/neither selector; (2) `--source`
uses only that local package; (3) `--version` uses its verified retained
official-release mapping if present, otherwise the exact official release.
A corrupt/inconsistent retained mapping refuses, never downloads over it.
An already installed different digest for the same official version refuses.
Nonempty `DOMESTIQUE_UPDATE_SOURCE` on bootstrap/update refuses with explicit-
selector guidance; no legacy URL or other environment source override applies.
Bootstrap against a valid existing installation uses the same transaction as
update (same selection is a no-op); pending/unknown state is never repair consent.

The proposed official distribution is repository `ebowman/domestique`, exact
tag `vV`, assets `domestique2-V.tar.gz` and `domestique2-V.tar.gz.sha256`.
These names are a **future publication contract, not live download links**;
no published V2 version is asserted. Fetch the fixed `github.com` release path;
allow at most three HTTPS redirects only to `github.com`,
`release-assets.githubusercontent.com` or `objects.githubusercontent.com`.
No arbitrary mirror, HTTP downgrade, credentials, user curl configuration or remote script
execution. Per fetch: connect limit 10 seconds, total 120 seconds, no retries;
maximum archive and expanded payload each 64 MiB. Missing/offline/truncated/
oversize/timeout sources refuse, preserving the prior installation.
The sidecar is exactly `<sha256><two spaces>domestique2-V.tar.gz\n`; validate
the archive digest before parsing/extraction. Metadata files are capped at 1 MiB.

`--source PATH` is a physical nonsymlinked **package directory**, relative to CWD
or absolute, not a URL, shell file or arbitrary checkout. Require the complete
official inventory; copy only allowlisted regular leaves to owned staging,
reverify there, never execute the mutable source path. Record `source_kind=local`,
not publisher authentication or an official version mapping. Same-package reruns
are idempotent; source relocation cannot affect bindings. Reselect old development
packages with `--source`; official rollback uses retained `update --version` offline.

Archive entries have one `domestique2/` root. The closed payload inventory is
`PACKAGE`, `domestique2.sh`, `update2.sh`, `bin/resolve-core`,
`roles/{orchestrator,implementer,reviewer,goal}.md`,
`adapters/{claude,codex,copilot}.templates`, plus `SHA256SUMS`.
Templates are inert native serialization data, not three workflow engines;
the one shared implementation emits bootstrap/launcher and provider loaders.
No archive links, devices, sockets, FIFOs, absolute/traversal/duplicate/extra
entries or non-directory parents are accepted, including empty extra folders.
Check inventory before extraction; do not honor archive owners/modes.
No extraction overwrites an existing destination.

`PACKAGE` is strict UTF-8 LF `key=value` in this order: `format=2`,
`product=domestique`, `major=2`, `version=V`, `core_api=1`, `adapter_abi=2`,
`activation_format=2`, `helper_abi=2`, `launcher_abi=2`.
`SHA256SUMS` lists every other payload file, including `PACKAGE`, in ASCII
path order, one `<64 lowercase hex><two spaces><relative path>\n` per file.
The immutable release ID `R` is `r-` plus SHA-256 of those exact sums bytes.
All contents, not merely prompts, participate. Version selection must equal
`PACKAGE.version`. Unknown/duplicate/missing fields, wrong major/API/ABI or
digest mismatch refuse before candidate execution or publication.
Colocated checksums detect corruption, **not independent publisher authentication**.
Trust is HTTPS/account/repository control plus the operator's trusted bootstrap;
local source is operator-trusted development input. No stronger signature claim,
autoinstalled verifier or “verified” label based only on a name.

Let `S = ${DOMESTIQUE_HOME:-${XDG_STATE_HOME:-$HOME/.local/state}/domestique}`
and **`G = S/v2`**. Unset/empty overrides use that existing default convention.
An explicit `DOMESTIQUE_HOME` is the base, not a guessed already-versioned path.
The stable executable is **`$HOME/.local/bin/domestique2`**, with its exact
physical `G` embedded; it never retargets to another root from ambient env.
A conflicting nonempty root override refuses operational commands. Relocation
means an explicit new installation and separately approved project rebind,
not rewriting old identities or discovering an alternate root.
Supplied HOME/state-root paths must be absolute, canonical and nonsymlinked;
literal spaces/quotes are allowed, relative overrides/control characters are not.

Machine inventory: `G/releases/R/<payload>`, `G/active` (exact `release=R\n`),
`G/state/runtime-manifest`, and transaction files below. The manifest records
format/physical root/launcher path/ABI, official version mappings, release IDs,
source kinds and separate created/baseline records for every owned leaf.
Its exact closed schema and integrity rules are in appendix sections A/B.
It records no projects, local registrations, leases, models or credentials.
Launcher publication is collision-safe, invoking-user-owned and nonsymlinked.
Identical unowned existing commands refuse. Within ABI 2 its bytes are stable:
compatible updates do not replace the dispatcher or an old workflow's helpers.

Every execution-bearing policy, factory, resolver and any later qualified
bridge is immutable within `releases/R`; adding a bridge changes the closed
package schema explicitly, not an unversioned side installation. The launcher
contains only the frozen verified dispatch/bootstrap protocol, never mutable
workflow policy. Management dispatch verifies its entrypoint against recorded
provenance; ordinary new management invocations use active. `inspect`, help,
version and safe disable must not execute the workflow resolver/bridge.
Missing workflow bodies do not prevent disable with an intact verified
management entrypoint; a missing/corrupt command runtime requires explicit
bootstrap repair, not execution of an unknown fallback.

## 3. Worktree identity, native payloads and guards

Owners: hq-1t9.4 (identity/guards/state), hq-5jc.7 (payloads/compatibility).
Activation commands require an existing **exact physical Git worktree
top-level**: normalize `.`/relative components, but refuse symlink components,
subdirectory targets, non-Git/missing/unreadable targets and bare repositories.
Workflow invocation from a subdirectory resolves its nearest Git worktree root;
it cannot inherit activation across a nested Git root. Inspection instead
retains hq-ln2 normalization: readable directory aliases/subdirectories may
resolve to a physical Git root; non-Git scope is that directory alone.
Non-Git definition migration mentioned in hq-5jc.7's retained migration note
belongs to hq-5jc.11, not this fresh-enable interface.

Project state is exclusively **`W/.domestique-private/v2/`**, never the V1
manifest at its parent and never a machine registry. Worktree identity is the
tuple of canonical physical `worktree_root`, `git_dir`, `git_common_dir`,
and each directory's `(device,inode)` identity, plus invoking owner UID.
Linked worktrees sharing a common dir have distinct root/git-dir identities.
Moving/copying/cloning/restoring at the old path, changing Git boundaries,
replacing a root inode or relocating `G` invalidates the binding. Refuse intact;
do not rewrite/adopt old receipts. Requalification/rebind with preservation is
explicit migration under hq-5jc.23/.11, not a compatible machine update.

### Native inventory (project-relative; no global counterpart)

| Provider | Three skills; exact names and entry forms | Two native role leaves and IDs |
| --- | --- | --- |
| Claude | `.claude/skills/domestique-v2-claude{,-decompose,-goal}/SKILL.md`; `/domestique-v2-claude{,-decompose,-goal}` | `.claude/agents/domestique-v2-claude-{implementer,reviewer}.md`; basename without `.md` |
| Codex | `.agents/skills/domestique-v2-codex{,-decompose,-goal}/SKILL.md`; `$domestique-v2-codex{,-decompose,-goal}` | `.codex/agents/domestique-v2-codex-{implementer,reviewer}.toml`; basename without `.toml` |
| Copilot | `.github/skills/domestique-v2-copilot{,-decompose,-goal}/SKILL.md`; `/domestique-v2-copilot{,-decompose,-goal}` | `.github/agents/domestique-v2-copilot-{implementer,reviewer}.agent.md`; basename without `.agent.md` |

Codex also has the exact local goal sidecar
`.agents/skills/domestique-v2-codex-goal/agents/openai.yaml`.
There are no generic/unqualified IDs, root policies, indexes or local core
copies. All payloads are thin native metadata plus the same guarded loader.
Identity comes from the native `name` as well as the path; both must match.
No native permission/model/MCP grants or personal defaults are changed.
Tools, MCP and model settings remain native/session choices; no model registry,
vendor translation, authentication, trust approvals or server installation.
Unavailable explicitly requested capability/model stops, not substitution.
Only explicit `*-goal` plus an explicit epic authorizes unattended work;
ordinary and decompose are not goal, nor are Copilot native `/goal` or autopilot.
Goal uses documented explicit-only metadata (Claude/Copilot
`disable-model-invocation: true`, Codex `allow_implicit_invocation: false`);
metadata is not proof of native enforcement.

### Records and execution binding

Appendix sections A/C define the exact `manifest`, `routing/P.receipt` and
ephemeral BINDING schemas: ordered UTF-8 LF records, closed fields/inventories,
checksums, limits, physical identities, compatibility tuple and generations.
No shell sourcing, extension fields or format-1 adoption is permitted.
Absent blocks mean absent; disabled blocks have no valid enabled receipt.
Creation records prove successful exclusive creation, not intent. Baselines
identify pristine generated bytes/modes; body/identity comparison uses the
retained template T, never user metadata preimages. Equal bytes or inspection
do not establish ownership. This is trusted local provenance, not protection
against an owner maliciously rewriting the complete ledger.

Before **any shared body read**, a NEW workflow checks current physical
worktree/provider, no project-pending/revoked state, manifest/receipt consistency,
owned local IDs and intact loader protocol. Its loader calls the immutable
template-T helper for this initial guard and selection protocol (ABI 2).
Verify helper T's own digest/provenance before execution, without core-body reads.
After its activation guard, sample `G/active` once, validate the full selected
release/ABI and return an ephemeral binding.
The binding covers the complete live provider inventory: both roles, all three
skills and Codex's goal sidecar, with exact byte hashes and modes. It also binds
physical identities, receipt/generation, release, entry skill and role tokens.
Pass explicit literal task-brief argv, never inherited environment defaults,
user config or a persistent central session registry.

Every subsequent skill, body load, pre-delegation check and delegated role
requires that binding. Recheck revocation/current identity/receipt and every
bound native leaf **before** reading orchestrator or role body. Never resample
active or substitute another provider/global/default/broader role. Invoke only
`G/releases/R/bin/resolve-core` (and an explicitly qualified same-R bridge),
not an unversioned helper chosen by current active. Missing R or helper,
changed adapter/receipt/generation, missing role, forked loader, denied native
trust or unconfirmed exact native ID/capability stops with no body output or
delegation. Revocation stops old bindings; cached text cannot be erased.
Machine-pending is not project revocation: a complete validated old/new active
or explicitly bound release remains usable during interrupted machine publication;
mutating management commands still refuse pending state. No native sandbox is claimed.

Appendix C fixes the internal `start`/`read`/`route` argv and output grammar.
Only `start` may sample active; errors emit no body or binding on stdout.
Goal reads require a goal entry binding as well as explicit epic authorization.

Compatible owned metadata-only edits survive enable **byte-for-byte**; baselines
never advance to live bytes. Compare reserved name/identity/bootstrap/body with
recorded pristine T, not today's template. Appendix F is the exact per-format
admission classifier, including tools/MCP/model shapes and protected goal controls;
the existing inspector field allowlists are not that validator. Unclassified
syntax/fields, reserved/additive body edits, prompt forks or ABI changes refuse intact.
No serialization, secret snapshots/backups/diffs/conflicts or automatic merge.
Any admitted edit, including skill or sidecar metadata, stales existing bindings;
a fresh workflow must revalidate and obtain fresh native confirmation. Compatible
machine updates never visit local files and accept only the exact ABI tuple,
preserving every admitted adapter without scans. Incompatibility requires
hq-5jc.23's preserving staged rebase and hq-5jc.11's approved publication.

## 4. Publication, removal and readiness boundaries

Owners: hq-5jc.4/hq-1t9.2/.3 (machine), hq-1t9.4/hq-5jc.7 (enable),
hq-1t9.5 (disable), hq-1t9.7 (retirement).

Preflight every exact parent/leaf and relevant Git index entry before any
publication: invoking ownership, readable/writable/searchable permissions,
no symlink/hardlink/nonregular leaf, safe ancestors, no tracked or index-only
private/native paths, unknown identical files, unsafe collisions or concurrent
changes. No chmod/config repair. Existing machine destinations cannot enter a
worktree or native discovery root, contain/equal HOME, or overlap project state.
Existing V1/preview project authority, unknown Domestique policy/forks or mixed generations
block enable for explicit preserving migration, not silent shadowing.
An existing `.domestique-private` parent does not grant ownership of its V1
children; `v2` is independently preflighted.

Project writes allow only table leaves, V2 state and **exact private exclusions**
in the resolved Git common-dir `info/exclude`. No `.gitignore`, tracked/index,
root CLAUDE/AGENTS policy, provider settings, hooks, Beads or global native
HOME changes. Never hide/adopt a host `.beads`. Missing ordinary `info/`
is a **preflight refusal before publication** in this contract (hq-1t9.4);
do not reproduce the existing partial-publication bug or fix config implicitly.
Shared exclusions use `/<native-leaf>` and `/.domestique-private/v2/` patterns,
a worktree-identity-qualified block and recorded preexisting-versus-created lines. Their ignore
effect can span linked worktrees; report this, never treat it as activation.
Preserve other blocks/preexisting lines. Appendix D's block-scoped edit records
full before/after hashes, never whole-file ownership; its bounded private
apply-only afterimage is not a journal backup. Shared ambiguity refuses enable
or retains exclusions on disable (PARTIAL); never scan siblings for ownership.

All mutators validate/stage privately and use a same-scope exclusive `pending`
journal/cooperating lock, `previous` metadata and append-only `published` facts.
Machine journals: `G/state`; project journals: `W/.domestique-private/v2`.
Appendix D fixes bounded chunked metadata snapshots, path/actions, integrity
chains, publication phases and pending/cleanup/unknown interpretations.
Record phase/provider/generation, allowlisted paths/digests, previous identities
and successful creations/removals, never native text. Intent is not creation.
Pending refuses mutating reruns (project-pending also blocks workflow entry);
no automatic lock takeover/resume.

Machine order: verify entire staged release; exclusively claim its final
directory; populate no-clobber; verify final inventory; exclusively create and
postverify the final launcher on first install; publish provenance/manifest;
atomically rename active **last**. Universal phases are
`release,launcher,manifest,active,complete`; a valid existing launcher phase
has no writes. Manifest creation pairs assert witnessed final creations,
never launcher intent. Before manifest/active exists, version and operational commands must refuse unavailable, never select staging or certify runtime.
Static help alone remains exit 0 with no filesystem discovery (§1); this is usage, not installation readiness or successful runtime publication.
Complete old releases remain forever in this scope. Project enable order:
preflight all selected providers; journal; protect exclusions; publish native
leaves; manifest; receipts last; revalidate; clear pending last. Guards refuse
throughout pending, so a receipt never certifies partial publication. No-op
reruns create no journal. Local operations never write G or launcher; machine
operations never enumerate, read or rewrite project payloads/receipts.

Before active switch, failures preserve old active/launcher usability; afterwards
report actual new selection and pending, not fictional rollback. Failed fresh
install is partial/unavailable, not enabled. Checked writes/renames/rechecks and
journals are not cross-root native atomicity or power-loss/fsync guarantees.
Manual recovery requires stopped writers and exact trusted-source/provenance
reconciliation before finish/restore; preserve divergent/unknown assets,
incomplete releases and ambiguous facts. Equality cannot prove ownership.
No automatic recovery/GC, registry/crawl, hot reload or auto-update.

Disable preflights the selected removal, then journals **revocation before
deletion** so even retained edited adapters cannot pass guards. Remove only
unchanged, owned, untracked selected native leaves/receipts and owned exact
exclusions when safe; retain disabled manifest/generation history, user edits,
Beads/exports, runtimes and unselected providers/worktrees. Edited/unowned/
tracked/unsafe leftovers give exit 1 `PARTIAL`, not “fully disabled/quiet”.
If valid ownership cannot establish revocation, report `revocation=unknown`,
not success. Pending failures stay fail-closed. Repeated complete disable is
an exact no-op; re-enable validates retained identity and increments the
selected disabled provider's generation, invalidating old tokens.

Retire-global first displays the exact selected known global inventory and
retention reasons (dry-run is the read-only preview); the explicit command
without dry-run authorizes applying that scope, with no hidden prompt.
Only source-qualified creation provenance plus an unchanged installed baseline
permits removal. Names/equal templates/inspector presence never suffice.
Preserve all old runtimes/helpers/releases, projects, settings and history.
Retirement evidence is separate under `G/state/retire-global/`, not edits to
the old runtime manifest; inspection joins old provenance with removal facts
without adopting it. Appendix D/E fixes the retirement-only derived ledger:
pending -> removal facts -> ledger publication -> commit; absence is not removal.
Journals retain partial removal; unowned/edited leftovers
mean nonzero partial/manual status. Install/update never implicitly retire.
Retained runtime does not guarantee old native entrypoint availability after
retirement. Cached sessions need restart; unresolved globals preclude “quiet”.

**Beads is separate.** Enable/disable/install/update/inspect/guards never invoke
Beads, open a DB, initialize/adopt `.beads`, export or probe readiness.
Absent/unknown/unqualified Beads blocks actual Beads-backed ordinary planning,
decompose, goal, claim and landing; it is not an empty queue or raw-`bd` fallback.
Definition activation is not an operational workflow success. The existing
preview's explicit qualified private setup is narrowly Darwin arm64/Beads 1.1.2
CGO; it does not authorize a V2 receipt, database conversion or preview setup
inside a V2 project. V2 fresh setup and existing-state attachment remain explicit
qualified prerequisites owned by hq-5jc.12/.10, outside this CLI. Full native
role/model/tool/MCP/workflow gates remain hq-5jc.18/.19/.20.

## 5. Native evidence and admission

Owners: hq-1t9.8 Claude, hq-1t9.9 Codex, hq-1t9.10 Copilot. Authoritative
**public documentation read 2026-09-16**: rolling editions, not tested CLI
versions/self-description. All mappings remain **proposed until actual probes**.

| Source / documentation version | Evidence level and bounded claim |
| --- | --- |
| [Claude skills](https://code.claude.com/docs/en/skills), rolling; [Claude subagents](https://code.claude.com/docs/en/sub-agents), rolling | DOC: project `.claude/skills` and `.claude/agents`; parent-to-Git-root discovery, nested skills and caching/refresh caveats. Agent docs explicitly date nearest-directory precedence to 2.1.178 and wizard removal to 2.1.198; neither is a Domestique support minimum. |
| [Codex skills](https://developers.openai.com/codex/skills/), rolling; [Codex subagents](https://developers.openai.com/codex/subagents/), rolling | DOC: `.agents/skills` along CWD-to-repository-root; same-name skills are not merged; standalone project `.codex/agents/*.toml`. No exact CLI version support is supplied by these pages. |
| [Copilot skills](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills), Free/Pro/Team latest; [Copilot CLI reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference), same rolling edition | DOC: `.github/skills` and `.github/agents`; alternative `.claude`/`.agents` skill discovery and `.claude/agents` interoperability, ancestor discovery and precedence make provider/ID collision checks necessary. This is not a version-qualified local discovery pass. |

The [native harness](../test/native-discovery.py) and [README evidence](../README.md#native-evidence-and-validation)
are HISTORICAL OBSERVATION, not V2 proof: Codex 0.154.0/Copilot 1.0.83 global skills
observed; Claude 2.1.269 skills and all roles blocked. Earlier Claude 2.1.268
design-history observations are not V2 support either.

Admission requires recorded client executable/version/hash, OS, candidate/source
hash, exact-ID native response, scope/layout and fresh-session/reload procedure.
Prove skills **and** roles in A/C, none from V2 install in HOME/untouched B,
actual ignored-file discovery, disable disappearance, explicit goal/planning
metadata and legacy/provider/ID collisions. Use bounded non-model introspection
with proven disposable HOME/config/network isolation. Missing capability/consent
is **BLOCKED**, malformed evidence/assertion mismatch is failure. No client
install, auth/trust/config changes or model/API/MCP/Beads calls to obtain proof.

Nested roots/ancestors, additional search directories, linked/client-copied
worktrees, alternate client homes, cached/resumed sessions and unknown versions
are not automatically admitted. Probe claimed layouts; failure means unsupported,
not “quiet” because a guard stopped execution. Guards can stop core loading/
delegation, not hide ancestral metadata or erase cached context. Native refresh
does not authorize Domestique hot reload/resampling. Duplicate IDs/source
ambiguity or cross-provider invocation stops, not precedence-based selection.
No universal quiet claim on unprobed boundaries.

## 6. Named acceptance matrix and bounded gate

These rows are **requirements, not by themselves executed tests or native PASS**.
The CURRENT `v2-project-tests.py` scope exercises the internal
`V2-GUARD-STATES`, `V2-PHYSICAL-BOUNDARY` and `V2-PREFLIGHT-COLLISIONS`
boundaries using actual fixture-owned publication and generated installed helpers.
It does not qualify public enable, native discovery or the final epic gate.
The owner must register each named case/subcase in existing fixtures and the
final hq-1t9.11 gate, without a new framework. `P` below means the preservation/
privacy oracle: snapshot owned HOME/runtime, A/C/B, Git common-dir/index/
exclusions and temp state (bytes, modes, mtimes, membership, link targets);
allow only the command's declared write set. No atime/hostile-writer claim.

Reuse [inspect_fixture.py](../test/inspect_fixture.py)'s actual pinned builders:
`HISTORICAL_PIN=b60feef4d0d41b8d99b7afec68dd5e6ef648b027`,
`PRE_SNAPSHOT_PIN=69f39c468b65335d05260b8c5bc4653a7cf3c9f3`,
six cold source-backed installer phases, actual adoption, `Origin`,
`qualified_cohort`, `Case.accept`, private fragments/sentinels and seven
observable forbidden markers (`bd`, `beads`, `claude`, `codex`, `copilot`,
`curl`, `wget`). V2 fixtures must identify the **actual** separated candidate
source/package hashes; do not relabel today's preview emitter as V2.
Historical pins are local Git objects, never fetched or replaced with today's
templates. Synthetic Beads metadata is preservation evidence only.

| Named case (required subcases are finite) | Owner | Observable oracle, in addition to P |
| --- | --- | --- |
| `V2-ARGV` | hq-1t9.2 | Every command/alias/allowed flag form/default above; empty, extra, duplicate, unknown, conflicting, inapplicable, separator and quoting branches return specified 0/1/2; misuse produces no operation writes/calls. |
| `V2-INERT-HOME-ABC` | hq-5jc.4 | One runtime with all three inert factories; no new global native IDs or project bytes; B untouched before/after A/C enable. Static inventory is not native discovery. |
| `V2-ROOTS-LAUNCHER` | hq-1t9.2 | Default/XDG/DOMESTIQUE_HOME, empty/relative/unsafe/overlapping roots, spaces/quotes, alternate root conflict, identical-unowned or edited launcher, missing dependency; no PATH/startup/dom/dom2 changes or auto-install. |
| `V2-SOURCE-EXACT` | hq-1t9.2 | Local package and stub official fetch exercise selector precedence, absent/both selectors, legacy env refusal, no latest/main, pinned version match, retained offline selection and local relocation. |
| `V2-SOURCE-REFUSE` | hq-1t9.2 | Wrong major/version/API/ABI; missing/corrupt/digest-mismatched/truncated/oversize payload, malicious archive paths/links/duplicates/extras, timeout/offline/redirect refusal; previous launcher/active usable, candidate execution marker absent. |
| `V2-PUBLISH-FAULTS` | hq-5jc.4, hq-1t9.2 | Inject failure at stage, directory claim, leaf publication, launcher, manifest, before/after active rename and journal clear; fresh launcher version/operations refuse before manifest/active, static help alone stays discovery-free exit 0; fresh Git/native/identity boundary changes stop all further writes/cleanup and success, including existing parents; appendix A/B/D field/order/checksum/phase tests, chunk 4000/4001-byte boundaries, missing/extra/reordered/truncated chunks and aggregate byte/line/item overflow refuse before writes; validate all torn suffix bytes before pending/unknown classification; exact old/new active truth, creation versus intent, metadata-only snapshots. |
| `V2-ENABLE-AC` | hq-5jc.7 | A and C get only table-native thin payloads/receipts/exclusions; B and G unchanged; explicit core absence refuses without HOME writes. Existing host exclude accepts only owned-block append with full before/after hashes and outside bytes/mode preserved; absent exclude uses exclusive create, matching preexisting patterns remain unowned/unchanged. |
| `V2-SELECTORS` | hq-5jc.7 | Seven fresh selections and seven additions to each of seven existing nonempty sets (49), selector omission on fresh/nonempty/disabled state, both excludes Copilot, all includes it, duplicate/refusal cases; exact provider union/IDs. Reuse one qualified cohort, not 49 cold installs. |
| `V2-IDEMPOTENCE-METADATA` | hq-5jc.7 | Exact rerun no writes; every appendix F admitted field/shape and its invalid/protected counterpart, including three distinct MCP grammars, goal controls and sidecar interface edits; admitted bytes retained without pristine-base advance or secret copies; unsupported/fork/ABI edits refuse intact. |
| `V2-GUARD-STATES` | hq-1t9.4 | Appendix C exact inventory/binding grammar; absent, disabled, foreign-root/provider, corrupt/duplicate records, missing helper/leaf, stale generation/route, pending/revoked states. Mutate each bound skill/role/sidecar while receipts stay pristine: old binding emits no body/delegation; only fresh admitted validation may bind again. |
| `V2-PHYSICAL-BOUNDARY` | hq-1t9.4 | Root/subdirectory invocation distinction, non-Git/bare refusal, moved/cloned/recreated root, source/runtime relocation, nested Git root, sibling linked worktree, changed Git-dir identity: no inherited activation or record rewrite. |
| `V2-PREFLIGHT-COLLISIONS` | hq-1t9.4 | Tracked/index-only/identical-unowned/active V1/preview, symlink/hardlink/FIFO/socket/directory, unsafe ownership/mode, racing leaves, missing info/exclude parent and shared-worktree exclusion conflicts refuse before publication. Edited/unknown/equal/half/duplicate blocks confer no authority; independently resolve Git common path, refuse unsupported exclude bounds or cross-filesystem afterimage rename. |
| `V2-ENABLE-FAULTS` | hq-5jc.7 | Failure at journal/exclusion/native/manifest/receipt/clear boundaries leaves honest pending, no early activation, old unselected state intact; guarded body marker absent. Exclude stage/rename/recheck/fact/cleanup faults and full-file races never adopt new host bytes or infer block ownership; no journal preimages, private afterimage leftovers reported honestly. |
| `V2-R1-R2-BINDINGS` | hq-1t9.3; integration hq-1t9.11 | A/C workflows pin R1; ordinary first update journals the full 12-leaf prior runtime manifest in bounded chunks and publishes R2 without visiting project metadata; fresh A/C bind R2 while old roles still execute R1 helper as well as R1 body; B/native HOME unchanged. Distinct helper markers prove execution, not just prompt pinning. |
| `V2-ROLLBACK-RETAINED` | hq-1t9.3 | `update --version` retained R1 works offline for fresh A/C; running R2 retains R2 helpers/body; all releases and local metadata retained. |
| `V2-UPDATE-REFUSALS` | hq-1t9.3 | Preview failure, corrupted source/retained map, different digest same version, missing bound release, incompatible activation/adapter/helper/launcher ABI and interrupted switch; intact bound helpers still work during machine-pending; no project scan/rebase or active-resampling fallback. |
| `V2-DISABLE` | hq-1t9.5 | Each selector, omitted all, absent/partial selection, mixed/all removal, repeat and re-enable, missing workflow core; only selected activation revoked, generation changes on re-enable, core/Beads/other providers untouched. |
| `V2-DISABLE-PARTIAL` | hq-1t9.5 | Edited/unowned/tracked/unsafe leftovers, invalid revocation authority and each removal failure boundary; retained bytes/history, nonzero partial, stale guards blocked, no fake disappearance. Remove only proven own exclusion block/patterns while preserving host/preexisting/other-worktree bytes and even an empty host file; shared ambiguity retains with PARTIAL, never whole-file deletion/ownership. |
| `V2-V1-CHANNEL` | hq-5jc.3 | Actual pinned old updater with candidate repository source keeps old URL/override/default/normal/guest semantics; explicit V2 rejects old inputs; historical inspector cohorts retain real source fingerprints. |
| `V2-RETIRE-GLOBAL` | hq-1t9.7 | Real manifest-derived old globals in all formats; seven selections plus missing selector; appendix D/E pending sentinel -> header -> successful removal fact -> exact derived ledger -> actual ledger-publication digest/fact -> commit, with refusal of sentinel elsewhere and faults at every edge. Preserve prior ledger metadata/evidence; removed/retained/absent, malformed/torn/stale/recreated-leaf cases, explicit dry-run/removal, edited/unowned/tracked/unsafe leftovers and mid-removal failure stay honest; old runtimes/projects/bindings/local DB retained, nonquiet partial reported. |
| `V2-INSPECT-EXACT` | hq-1t9.6 | Actual installed command/bare/aliases, not scanner-only: runtime-only, enabled/disabled/partial A/C versus B, metadata edits, all old cohorts, update/rollback, absent/moved/corrupt receipts, ABI mismatch, damaged global/invalid target; exact scopes/dimensions/0/1/2 plus P with zero allowed writes. |
| `V2-INSPECT-PRIVACY` | hq-1t9.6 | Quoted requested/resolved paths, traversal/input-limit/encoding failures; recorded pristine comparisons, permission field names only, no raw native values/prompts/ref strings/errors/secret sentinel; all forbidden markers observed empty. Validated V2 package version/R may be displayed, unknown recorded strings stay suppressed. |
| `V2-DRYRUN-EXACT` | hq-1t9.2; operation owners above | Every mutator's success/refusal/fault preflight: no destination byte/mode/mtime/member changes, no candidate/helper/native/Beads execution, only explicitly requested stub fetch staging; zero calls for local source. |
| `V2-PRIVATE-BEADS-NOOP` | hq-1t9.4, hq-5jc.7 | Absent, synthetic existing host/private/unsupported metadata preserved through all definition operations; forbidden bd/beads markers empty; workflow readiness blocked, never init/adopt/empty queue. |
| `V2-NATIVE-CLAUDE` | hq-1t9.8 | Actual version/source-qualified skills and role discovery, HOME/A/C/B, ignored files, nesting/ancestry, linked/cached sessions, IDs/provider collisions, explicit goal, disable and legacy leftovers under §5 admission. Missing probe = BLOCKED. |
| `V2-NATIVE-CODEX` | hq-1t9.9 | Same finite admission cases, actual `.agents`/`.codex` evidence and goal implicit-invocation control; no merging/default-model inference or synthetic PASS. |
| `V2-NATIVE-COPILOT` | hq-1t9.10 | Same finite admission cases, actual `.github` and cross-provider discovery, goal versus native autopilot, disappearance after fresh session; no synthetic PASS. |
| `V2-PRESERVING-HANDOFF` | hq-5jc.23/.11 (outside focused gate) | Incompatible/unknown/forked cases from this scope stay intact and name explicit preserving rebase/publication prerequisite; no claim that this epic implements that path. |
| `V2-FINAL-SOURCE-GATE` | hq-1t9.11 | Complete named offline cases, full existing inspection inventory/privacy validators, true source/tool fingerprints, setup counters, completed IDs and owned cleanup plus fresh independent review; native evidence separately bounded, missing scope BLOCKED. |

Inspection retains hq-ln2's read-only collection limits and Python 3.9+
stdlib prerequisite/refusal, adding only the specified V2 records and appendix F
safe metadata classification. Invalid targets do not hide independent machine
evidence or establish project absence. No HOME/repository/registry scan, DB open,
repair, raw diff/JSON export; separate compatibility, ownership and discovery.

The **final offline gate is one 1200-second (20-minute) wall deadline including
setup and owned cleanup**, not per row/suite. Clip existing 120-second command,
300-second installer and 900-second cohort caps to remaining gate time.
Reuse asserted cohorts. Concurrency requires proven disjoint HOME/temp/ports/
processes/fixtures, never a shared mutable cohort; measure real outer wall time.
Use existing source validators and full per-scope results, not hours-long lifecycle
Cartesian runs or selected/QUICK relabeled full. Timeout retains sanitized partial
evidence, never PASS. Native probes have separate declared finite deadlines;
offline markers cannot replace them. Missing native capability remains BLOCKED
even after offline success. No full-runtime or GA claim.

## 7. Source trace and checkpoint validation

Source at `020c05c`: [domestique.sh](../domestique.sh) inventories, `emit_private_adapter_body`,
`emit_private_core_resolver`, `emit_private_core_sums`, manifests/publication/guards/inspector;
[inspect_fixture.py](../test/inspect_fixture.py) pins, six phases, privacy/preservation.
Today's six-file core excludes its resolver; adapters read bodies before routing, not V2 guards.

hq-1t9.1 checks docs/links, source/owner/branch coverage and `git diff --check`, not implementation/tests, Beads, publication, aliases or unrelated defects.
Owners must satisfy this contract or return a reviewed change; hq-1t9.11 owns final
review, hq-5jc migration/Beads/full execution. No native mapping or implementation is claimed here.
