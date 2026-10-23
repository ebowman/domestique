# domestique

## Small Copilot/macOS preview — retained-CLI workflow and separate goal skill load demonstrated

The [Copilot/macOS preview contract](docs/v2-preview.md) now has a small,
repository-owned `preview/` installer, offline version/help and explicit local
Git update, plus explicit Copilot-only project enable/disable and dry-run.
Shared ordinary/decompose/goal and delegated-role instructions now load from that
source. Explicit `--ready` checks existing user-managed Beads; no private bridge.
Read-only `inspect` reports the selected revision and target ownership footprint.
Installed definitions and fake-CLI fixtures do
**not** establish native discovery, model dispatch or end-to-end qualification.
A separate [native demonstration](docs/v2-preview.md#bounded-native-qualification-2026-09-18)
at `ad80706` completed real decompose and an explicit retained-CLI goal,
GPT-6 Astra implementation and independent review, one local commit and Beads
closure on macOS with Copilot CLI 1.0.86. The goal skill invocation failed
(`Skill not found`); the caller recovered through the retained CLI. The generator
now permits goal skill model loading. On 2026-09-18 a separate read-only native
probe loaded its exact corrected project-local body successfully using Copilot
CLI 1.0.86, `gpt-6-astra` / `openai-responses`: 10.05175 AI credits in 12.408678
seconds. The earlier full workflow used 175.97425 cumulative credits in 174.31
seconds and predates the two-line template visibility fix; shared workflow
instruction bodies are unchanged. That probe proves skill discovery/loading only, not a rerun of the
full cycle or activation lifecycle.
This is a bounded preview result, not a published release or qualification of
every client, model, provider or platform.
Requires existing **Bash, Git and Python 3.9+** (not the macOS developer-tools
Python stub); nothing installs dependencies or changes aliases/PATH.

### Shared public names

| Client | Planning only | Explicit named epic |
| --- | --- | --- |
| Claude (released v1 installer) | `/dom-decompose` | `/dom-goal EPIC_ID` |
| Codex (released v1 installer) | `$dom-decompose` | `$dom-goal EPIC_ID` |
| Copilot (this project-local preview) | `/dom-decompose` | `/dom-goal EPIC_ID` |

Codex also supports `/skills` selection. Compatibility entries remain:
Claude `/decompose`, `/goal`; Codex `$domestique-decompose`, `$domestique-goal`;
Copilot `/domestique-v2-copilot-decompose`, `/domestique-v2-copilot-goal`.
Goal still needs an explicit request naming the epic; loading/matching a skill
alone never authorizes unattended work. Ordinary/bootstrap entries and role IDs
are unchanged. These additive
names do **not** imply full Claude/Codex v2 parity. Naming/ownership evidence is
offline regression coverage, not new native execution qualification; the earlier
workflow-body demonstration above remains its separate, bounded evidence.

The v1 installer now emits shared **first-use role-model setup protocols**
for Claude and Codex command/skill names and aliases. Generated defaults need explicit confirmation;
setup ends without Beads/code/goal work and requires a fresh session/reinvocation.
Use `/dom-decompose configure role models` (Claude) or
`$dom-decompose configure role models` (Codex) to reconfigure both roles. Ordinary
unconfirmed delegation redirects there. Existing snapshot update/uninstall
semantics preserve customized roles. This is instruction-driven and **native
unqualified**; unknown native support/selection stops without fallback.
Copilot setup and paid observed qualification remain pending.
See [the contract and evidence limits](docs/v2-preview.md#first-use-role-models--claudecodex-protocols-implemented-native-unqualified).

From a checkout containing the new entrypoint:

```sh
bash -p ./install-v2.sh --source "/path/to/trusted checkout" --ref REV
"$HOME/.local/bin/domestique2" version
"$HOME/.local/bin/domestique2" help
"$HOME/.local/bin/domestique2" update --ref NEXT_REV
"$HOME/.local/bin/domestique2" enable "/physical/project root" --dry-run
"$HOME/.local/bin/domestique2" enable "/physical/project root"
"$HOME/.local/bin/domestique2" inspect "/physical/project root"
# Exact synonym; omitted target means cwd itself must be the physical Git root:
"$HOME/.local/bin/domestique2" --inspect "/physical/project root"
"$HOME/.local/bin/domestique2" workflow decompose --project "/physical/project root"
# Only on an explicit user planning request (opens user-managed Beads):
"$HOME/.local/bin/domestique2" workflow decompose --project "/physical/project root" --brief "Plan one bounded change" --ready
# Only for an explicit Domestique goal request naming this epic:
"$HOME/.local/bin/domestique2" workflow goal --project "/physical/project root" --epic EPIC_ID --domestique-goal --ready
"$HOME/.local/bin/domestique2" disable "/physical/project root" --dry-run
"$HOME/.local/bin/domestique2" disable "/physical/project root"
```

Both install selections and the update ref are required. The selected **commit**
must contain the new preview CLI/runtime; uncommitted files are not revision
content. No implicit branch, fetch from a remote, download or `git pull`.
The recorded local source is user-managed. Version/help keep working if it moves
or disappears; update refuses until that recorded source is available again.

Only `${XDG_DATA_HOME:-$HOME/.local/share}/domestique-preview` and the stable
`$HOME/.local/bin/domestique2` are installed. Updates prepare standalone revisions
before atomically switching the owned `current` pointer; old paths are retained.
This assumes a cooperative single writer, not hostile-writer protection.
Unknown/dirty destinations and old ABI2/3 installations refuse, even if an
unowned launcher has identical bytes. No adoption, migration, force, GC, automatic
recovery or shell startup edits. Machine install/update never activate projects.

Project commands require the **exact physical Git worktree root** (default cwd
must itself be the root, not a subdirectory or symlink). Fresh activation installs five
skills (`dom-decompose`, `dom-goal`, `domestique-v2-copilot{,-decompose,-goal}`) and two
`domestique-v2-copilot-{implementer,reviewer}` agents under `.github`, plus
`.domestique-private/copilot-preview.json`. The receipt binds physical root,
Git/common identities, installed launcher and original creation hashes. Only
these eight paths receive an owned Git-common `info/exclude` block; host bytes
and preexisting matching lines stay unowned. `.beads`, index, hooks, settings,
`.gitignore` and root policy are untouched.

Repeat enable preserves customized local metadata **and bodies byte-for-byte**,
without parsing/approving them or advancing original hashes, including across
shared updates. Disable revokes the receipt before deleting only unchanged owned
files. Edited/unowned/tracked/unsafe leftovers remain with **1 / PARTIAL** and a
disabled receipt; resolve them yourself and repeat disable before re-enabling.
Complete/no-op returns **0**, misuse **2**. Dry-run writes nothing and reports
the same refusal or predicted partial result. No identical-file adoption.
Missing ordinary Git-common `info/` refuses; no automatic repair. Linked
worktrees share ignore effects, not activation: only one preview activation
per common repository is supported, and ambiguous blocks are retained/refused.

Existing five-definition Copilot receipts and their original six-pattern
exclusion blocks remain valid. Update/repeat enable do not add aliases or rewrite
local metadata; they report the legacy layout. To obtain short names, update the
shared source, inspect and review **each customized file**, then explicitly
disable/re-enable. Unchanged files are removable; partial disable retains edits.
Preserve/reconcile those edits yourself before completing disable and fresh enable;
never discard custom files merely to force a refresh. Restart the client afterward.
Released v1 installations can gain aliases through the ordinary existing installer
rerun/merge behavior; the updater transport and lifecycle are unchanged.

Thin loaders reference `ABSOLUTE_LAUNCHER workflow TYPE --project ABSOLUTE_ROOT`.
Existing `.3` locators keep working without rewriting native files or creation
hashes. Default loads never invoke Beads. Bare goal supplies setup guidance that
forwards the user's explicit epic to a retained-source command with `--epic ID
--domestique-goal --ready`; native goal/autopilot/natural planning is not consent.
Role locators alone load no role body: the caller supplies explicit project/task/
brief/exact role ID and its original immutable `preview/cli.py` path. All later
calls keep that source, even after update; only a new workflow samples current.

Before any operational body, validate the active receipt, exact root/Git/machine
binding and presence of every recorded owned definition (seven fresh, five legacy). Customized bytes remain
opaque/preserved and need fresh native exact-ID/capability confirmation before
`--ready --confirm-native`; that assertion is not native proof. No global fallback.
`--ready` runs bounded normal `bd --version` and project-scoped `status`, requiring
local project discovery state plus actual success, not just `.beads` presence.
Ambient Git/Beads retargeting is removed for those subprocesses. The user configures
Beads separately; no init, backend management, migration or automatic repair.
Install/load/help/inspect/enable/disable/update never open a database.

Decompose plans only. Ordinary handles one explicitly assigned bounded bead.
Only explicit Domestique goal plus an epic authorizes its bounded serial
implementer → fresh-reviewer cycle, one bead by default, one fix pass, exact
reviewed-path staging/one local commit per passed bead on a clean dedicated
non-default branch; never push/merge or close unpassed work. No ready work with
unfinished descendants means **BLOCKED**, not complete.
Models/tools/MCP stay native/session-local, installed models unset. Optional
`--implementer-model` / `--reviewer-model` are literal ephemeral requests; actual
native exact OpenAI ID/capability confirmation is required, unavailable means
stop without substitution. See the contract for complete optional loader flags.

After enable, definition edits or disable, restart/use a **fresh Copilot client**
and confirm the exact skill/role IDs before use; no hot reload is promised.
For planning, ask “Use Domestique decompose to plan this change” or explicitly
select `/dom-decompose`. For the bounded loop, explicitly ask
“Use Domestique goal for epic EPIC_ID” and select `/dom-goal EPIC_ID`.
Native goal/autopilot is not this entry and does not authorize it. Corrected
goal skill loading was separately confirmed in the bounded read-only probe.
Existing adapters are not rewritten by update or repeat enable; see the
[legacy goal metadata guidance](docs/v2-preview.md#existing-goal-skill-metadata).
The recorded demonstration does not replace discovery and permission approval
in your own client; shell-command approval and file-path approval are separate.

Inspection never installs, repairs, opens Beads, invokes a native/model/MCP
client or changes exclusions. It compares original **creation hashes**, including
across shared updates; it does not parse native metadata or infer permissions.
Missing/corrupt/incompatible ownership or unreadable evidence remains partial/
unknown (**1**); absent preview and complete observations, including customization,
return **0**. Legacy named markers/references and tracked evidence are reported
only at the selected root; arbitrary provider containers are not installations,
untracked is not proof of guest mode, and other/global legacy state is unknown.
Source checkout, installed machine, project filesystem discovery and operational
readiness are separate: inspect establishes neither effective client loading nor
workflow readiness. Use the explicit installed path; existing `dom`/`dom2`
aliases were not changed and do not imply preview access.

Targeted local-only checks:
Run serially: `python3 -B -Werror test/preview-inspect-tests.py`,
`python3 -B -Werror test/preview-workflow-tests.py`,
`python3 -B -Werror test/preview-project-tests.py`, then
`python3 -B -Werror test/preview-machine-tests.py`.
See the contract for grammar, exit codes and acceptance limits.
The ABI2 checkpoint below is **retained history**, not this preview's runtime or
acceptance gate. The separate original-worktree ABI3 experiment remains
unreviewed/incomplete. Released Claude/Codex **v1** (`domestique.sh` / `update.sh`)
now adds compatible short names; its lifecycle and updater transport remain unchanged.

## Historical verified bootstrap checkpoint (hq-1t9.2)

**No V2 release is published; no real HOME installation or project activation
was performed.** At that checkpoint a standalone runtime-only bootstrap and
offline help/version/legacy-inspection interface existed. Its update, activation
and global retirement were unimplemented. See the historical
[bounded bootstrap guide](docs/v2-bootstrap.md).
These artifact meanings are historical, except for the explicitly replaced entrypoint:

| Source | Current behavior |
| --- | --- |
| [`domestique.sh`](domestique.sh), [`update.sh`](update.sh) | Public **v1**, historically restored byte-for-byte from locally verified `main`/`origin/main` at `4de726c2e38e731c67f5f37d4a16206d7b3d99af`; the installer now adds the compatible public names above. Claude/Codex normal/guest lifecycle and the old updater's URL, `--source PATH/URL`, and `DOMESTIQUE_UPDATE_SOURCE` semantics remain unchanged. Draft Copilot is not this released channel. |
| [`domestique2.sh`](domestique2.sh) | Source-only transition: reviewed read-only `--inspect` and help. **All installation/removal/activation operations refuse.** The format-1 preview engine is retained for fixture extraction/reuse, not executable setup through this entrypoint. |
| [`update2.sh`](update2.sh) | Fail-closed transition: accepts explicit source/version selection syntax but **refuses all updates**, before candidate execution, fetch or destination writes. No default source; nonempty legacy source environment override refuses. Shell files, including this checkout's scripts, are not V2 packages. |
| [`install-v2.sh`](install-v2.sh) | **Replaced on this preview branch** by the thin `--source CHECKOUT --ref REV` entrypoint above. The historical package/`--version`/`--dry-run` bootstrap interface no longer applies to this artifact. This is not automatic migration of existing installs. |
| [`v2/`](v2/) | Trusted Python 3.9+ stdlib development APIs: deterministic 12-leaf package emission, strict local verifier, machine-only publication and minimal trusted stable version/availability protocol. All three inert native-template factories share four core policies. No native files, projects, client settings or Beads operations. |

The frozen [V2/1 contract](docs/v2-install-contract.md) and
[normative interfaces](docs/v2-install-interfaces.md) are **partially implemented**:
the local package/publisher path implements format-2 runtime `S/v2` and
`$HOME/.local/bin/domestique2`. Bootstrap selection/transport, installed grammar
and retained legacy inspection are implemented; guarded project activation,
V2 activation inspection, public update and usable native loaders remain downstream work.
Project
`.domestique-private/v2/`, format-2 records and `domestique-v2-P...` native IDs
must never adopt format-1 preview state. See the
[source boundary and fixture qualification](docs/v2-source-boundary.md).

The internal interface is `v2.build.emit_package(destination, "2.MINOR.PATCH")`
then `v2.publisher.publish_local(package_directory, explicit_environment,
dry_run=False)`. This development API is also used by the standalone bootstrap.
Local checksums are corruption checks, not publisher
authentication. The stable launcher can report verified `version`; unsupported
activation/body/delegation/Beads paths stop before execution. Installation adds
no global native advertisements, but does **not** remove or certify quiet any
old global definitions already on the machine. No published V2 release is asserted.

**Alias boundary:** the existing `dom2` alias points to an old
`domestique.sh` outside this project. It was not changed and does not imply a
working new interface. Use the installed absolute path in the preview guide
above, or the explicit retained source-only command below for that historical
inspector. Neither `dom`, shell startup, personal models nor native configuration
was changed.

### Retained qualification history

The b3q/ln2 observations and limits below remain completed history, **not V2/1
installation or native qualification**. Below the inspection section, setup/
update/removal examples describe the pre-split source at `020c05c`/`58732cc`,
where `domestique.sh` still meant the preview. **Do not execute those historical
commands against today's public v1 paths or treat them as a V2 install guide.**

Private orchestration definitions for **Claude Code, Codex CLI, and GitHub
Copilot CLI**: an orchestrator plans bounded work, an implementer executes it,
and a fresh reviewer independently checks the result. The intended plan of
record is [Beads](https://github.com/steveyegge/beads).

> **QUALIFIED PREVIEW — not end-to-end ready.** Shared core, global
> definitions, optional private local profiles, routing guards, and
> profile-only removal are implemented on `epic/hq-b3q`. **Private Beads init
> and controlled operations now have a narrowly qualified Darwin arm64 path**
> for the observed Beads 1.1.2 CGO embedded artifact. Other versions/backends
> and platforms refuse; existing host `.beads/` is never adopted. Definition
> loading and routing remain read-only. Full native role execution and
> tool/MCP access are still not verified.
>
> Limited native evidence: **Codex 0.154.0** and **Copilot 1.0.83** global
> skills were observed in two repositories, including fresh-process skill
> metadata reload. **Claude 2.1.269 skill discovery and all three clients'
> role discovery remain blocked** in the bounded offline harness. These are
> versions observed, not minimum supported versions or claims that the
> products lack roles. See [native evidence](#native-evidence-and-validation).

Those four native init flags alone are **not isolation**: from a Git root
they can change broad Git policy. The implemented path instead uses a private
non-Git CWD, an absolute final DB target, a constructed environment, a pinned
executable, and an actual default-deny OS sandbox. Native `--sandbox` only
disables auto-push. No host-root init/rollback, configuration repair, force
bypass, DB copying, or provider setup is performed. Even database reads can
write engine state; loading/routing/structural guards never invoke Beads.
Database retention/unchanged-only purge (.7) is implemented. Final acceptance
distinguishes offline lifecycle coverage and qualified native observations from
the remaining role/tool/MCP execution limitations; see the evidence below.

## Historical source-only inspection (not the installed preview)

The retained **`domestique2.sh`** supports its historical inspection without
setup. This is not the installed `domestique2 inspect` interface described above
or a released v2 command; its different target/discovery rules below apply only
to the retained source-only inspector:

```sh
bash ./domestique2.sh --inspect
bash ./domestique2.sh --inspect /path/to/project
```

The optional target defaults to the current directory. A Git root,
subdirectory, or linked worktree resolves to its physical worktree root; a
non-Git directory is inspected **only at that directory**, without guessing an
ancestor project. An existing directory alias can resolve to its physical
target. Missing/non-directory/unreadable targets cannot establish project
absence; independently readable global evidence is still reported.

The deterministic report separates **global preview availability** from
**project-local providers and generations**. Global definitions alone do not
mean a local installation exists. Provider rows retain normal, guest, mixed,
or unknown mode; multiple generations remain separate rows with explicitly
combined provider state. Partial or unknown evidence is never called clean.
Comparison uses recorded installed snapshots/digests, not today's templates
or Git status: even committed permission edits are customizations.

Old installations without snapshots can be installed with **unknown**
customization. Missing baselines also remain unknown. Digest-only preview
baselines can identify a changed file but cannot recover metadata/instruction
differences. Supported textual baselines can report those categories and
known permission **field names**, never their values. These are filesystem
observations, not proof of native discovery, readiness, effective permissions,
or creation authority.

The exact requested directory argument and resolved physical project scope are
shown separately, quoted with control characters escaped. Each section prints
its directory; `<project>/...` and `<global>/...` file paths are relative to those
explicit roots. Path/scope fields are public, including user-chosen directory
names. Reports omit raw configuration, native values, prompts, baseline contents,
recorded version/ref values, exception payloads and diffs.

Inspection requires an **existing Python 3.9+ with its standard library**;
it never installs a runtime and refuses explicitly if one is unavailable.
This requirement is added only to inspection; other operations retain their
existing dependency contracts. Inspection makes no application writes,
network/native-client/Beads calls, or database opens. Beads presence is
metadata-only, not a runtime permission or readiness claim. It needs neither
an installed global core nor a Beads runtime.

Do not combine inspection with `--global`, `--local`, `--platform` (either
spelling), `--dry-run`, `--force`, `--guest`, `--no-guest`, `--with-beads`,
`--state-only`, `--uninstall`, or `--purge-beads`. Empty/extra targets,
`--inspect=TARGET`, and unknown options are rejected. A trailing `--` is
accepted, but arguments after it are rejected. `-h`/`--help` remains
nonmutating, including with inspection.

Exit **0** means a supported complete report, including absence, customization,
or an unavailable old baseline; **1** means partial/mixed/unsafe/corrupt/
unreadable/inconsistent evidence or a runtime failure; **2** means argument
misuse. A failed scope does not hide independently readable evidence. The
internal scanner/comparison records are reusable by the future migration
planner; this command performs no migration, repair, JSON export, or raw diff.

### Focused inspection qualification

Run the complete inspection scopes directly from this checkout, capturing each
command's full stdout/stderr and exit status against unchanged source:

```sh
python3 -B -W error test/inspect-tests.py
python3 -B -W error test/inspect-fixture-tests.py
python3 -B -W error test/acceptance-tests.py
# Existing syntax/lint/AST scope; selected acceptance, not full repository acceptance:
python3 -B -W error test/acceptance.py --suite CURRENT:syntax-lint-ast-diff
```

The direct commands do not share an automatic outer timer. Use one declared
cumulative 1200-second wall budget for the focused gate, including setup and
owned cleanup; preserve partial evidence on exhaustion rather than extending
the budget or starting unrelated lifecycle/native suites.

Test-only fixture construction allows each real installer at most 300 seconds,
versus 120 seconds for ordinary fixture commands, inside the original finite
900-second fixture session. Execution allowances are clipped to remaining
session time (including launch time); neither these caps nor separate sessions
extend the cumulative 1200-second gate. Production/native/inspection limits
and process cleanup behavior are unchanged.

Each attempted install emits a supplemental `INSPECTION_INSTALL_PHASE=` JSON
line: `phase` (historical_normal, historical_guest, pre_snapshot,
historical_adoption, current_global, current_local), `limit_seconds`,
`elapsed_seconds`, `outcome` (returned, nonzero-exit, or fixture failure
classification), and numeric/null `returncode`. Only known labels and timing/
process facts are logged, never argv, child output or configuration. These
events leave the strict qualification schema unchanged and survive setup
failure. Six successful events plus completed cohort qualification establish
actual setup; measured elapsed time can show whether the earlier 120-second
cap was insufficient, but cannot diagnose a host/API/sleep cause.

The inspection suite invokes the actual `bash domestique2.sh --inspect` entrypoint
for every named frozen matrix case, including invalid targets and CLI misuse,
plus independently damaged-global and traversal cases. It retains the earlier
collection/scanner/comparison, parser-control and escaped-path privacy oracles.
One source-qualified cohort per suite reuses six offline installer calls, five
Git initializations and one linked worktree; other boundary/control fixtures
do not repeat that cold installation cohort. Historical sources are pinned
local Git objects, never fetched. The fixture-only suite proves builders and
model/oracle annotations, **not inspector execution or native readiness**.

`INSPECTION_QUALIFICATION` is emitted after the actual unittest result and owned
cleanup, with completed test/case IDs, counts, source/tool fingerprints, runtime
and setup counters. Only the complete, unselected, no-skip scope may report
`COMPLETE_INSPECTION_SCOPE`. Unit selectors (including `-k`) are partial even if
they happen to select every test. `test/acceptance.py`'s existing `offline_report`
also validates these summaries in captured direct results against current
source; a bare `Ran 1 test` / `OK` is insufficient. This is source-bound scoped
evidence, not cryptographic execution proof or a fabricated aggregate runner
report. Both inspection suites are in CURRENT, **not default QUICK**; full/quick
and `--suite` selection rules are unchanged.

Actual runtime qualification is **Python 3.14.7 on macOS (Darwin arm64)**.
Python 3.9 has static syntax/stdlib API evidence, not an actual 3.9 runtime pass.
Preservation measures owned project/Git common-dir/index/exclusions, isolated
HOME/core and temporary-state bytes, modes, mtimes and membership, with all
seven forbidden-tool markers observable. It does not claim unchanged atime or
atomicity against hostile concurrent writers. Synthetic Beads metadata is not
native database/discovery/readiness or effective-permission evidence. These
focused scopes do not establish whole-epic native or GA readiness, and default
QUICK remains explicitly **not full offline acceptance**. A final independent
gate must qualify the frozen candidate; no passing totals are assumed here.

## Historical preview setup: global first (not current commands)

Before the source split, the reviewed preview used these commands. They are
retained as history only; today `domestique.sh` is v1 and `domestique2.sh`
explicitly refuses installation. Do not install from these examples:

```sh
bash ./domestique.sh --global --platform copilot
```

This installs personal native skills/roles and the shared private core. It
does not touch any project. It does not install clients/plugins, configure
authentication/environment, register or execute MCP servers, or approve trust.
All templates are embedded; the installer itself needs no network.

**Publication boundary:** `main` and historical draft PR **#11 do not contain
these private-global/local changes**. Do not substitute a `curl .../main`
installer for this checkout. This preview is not a completed release.
Commands here are usage examples, not examples executed against a real HOME.

Both scopes accept exactly seven `--platform` selectors:

| Selector | Providers |
| --- | --- |
| `claude` | Claude |
| `codex` | Codex |
| `copilot` | Copilot |
| `both` | Claude + Codex (not all three) |
| `claude-copilot` | Claude + Copilot |
| `codex-copilot` | Codex + Copilot |
| `all` | All three |

Explicit install selection adds to that scope's persisted union; omission
reuses it. A fresh selector-less install defaults to Claude, not auto-detected
clients. **Bare invocation and positional targets remain private LOCAL**
(`.` by default), never an implicit global install. `--guest` is a deprecated
warning-only no-op; `--no-guest` is refused. Normal/guest dual-mode behavior
and three-way merging are historical, not current installation options.

### Optional project profiles

Only add a local profile when a role's tools/MCP metadata really needs to
differ from what the native client already inherits from the project:

```sh
bash ./domestique.sh --local /absolute/project --platform copilot
```

The target must already be an exact **physical Git worktree top-level**, not
a subdirectory or symlinked destination. Local setup requires an installed,
compatible global core and never installs/updates it implicitly. It creates
only qualified local role files, receipts, private ownership metadata and
exact private exclusions: no local skills, core body copies, root instruction
policy, settings, index, hooks, `.gitignore` or Beads.

`--dry-run` performs preflight without destination writes. Tracked (including
index-only), unknown, corrupt, unsafe or symlinked state refuses even with
`--force`. Identical bytes alone never prove ownership.

### Historical preview updates (not current commands)

The pre-split preview required a local source as below. Today's `update2.sh`
does not fetch or apply anything, even with an explicit source:

```sh
bash ./update.sh --source ./domestique.sh --global
bash ./update.sh --source ./domestique.sh --local /absolute/project
# Preview only:
bash ./update.sh --source ./domestique.sh --global --dry-run
```

The retained preview updater defaulted to remote **main**, not this preview. `--source PATH/URL`
or `DOMESTIQUE_UPDATE_SOURCE` overrides that default. It previews first and
does not apply after **any** failed preview. Scope/selection semantics match
the installer; it is update-only, not an uninstall wrapper. There are no
installer/updater model, MCP or tool configuration flags.

### Optional private task database

After installing/updating the global core from this checkout:

```sh
# DB only: no local agents or workflow body copies
bash ./domestique.sh --local /absolute/project --with-beads --state-only
# Or explicitly request profiles and the DB together
bash ./domestique.sh --local /absolute/project --with-beads --platform copilot
```

State-only starts with `providers=none` and preserves existing profiles,
receipts and customized native bytes unchanged. Combined requests preflight
all destinations before writing; automatic refresh of edited profiles still
refuses, even with force. Missing global helper capability requires an explicit
global update, never an implicit installation.
State-only also preserves valid original record ordering and refuses active
legacy profiles rather than silently migrating/removing them.

Qualification requires **Darwin arm64, existing Python 3.9+ (stdlib), existing
macOS sandbox-exec, Git, and the observed Beads 1.1.2 CGO embedded binary**
(SHA-256 `cb77069648d90fef8876f775d647997beb7bb0ab5461509394c29d5bf14b7c42`).
No installer/replacement or assumption about 1.2.2 is made. Qualification
help/version and OS denial probes run only in private temporary staging.
Dry-run performs no project/global/index/exclude writes or native DB calls.
Unsupported contexts/dependencies refuse before project writes.
Beads project paths cannot contain `:` (Git's ceiling-list separator).
The stdlib controller uses `-I -S -B`: no user/global site startup hooks or
bytecode-cache writes. Empty Git configuration is generated inside the context.
Python 3.9+ alone is insufficient: the interpreter/kernel must expose working
`os.waitid(P_PID, WEXITED|WNOHANG|WNOWAIT)`, POSIX nonblocking pipes and sessions,
and Darwin's `libproc proc_listpids` via stdlib ctypes.
Some Darwin Python builds lack `waitid`; they refuse before qualification/init
writes or child creation. Default SIGCHLD and a single-threaded exclusive
child reaper are required; competing reapers are unsupported.

The embedded bridge retains its direct leader through its last group signal,
then reaps, with the original 60-second execution / five-second cleanup bounds.
It drains both pipes fairly and preserves text decoding/newlines. Cleanup errors
are explicit and retain private partial output/status, never raw public argv or
payload. Darwin `killpg` EPERM is accepted only with a positively completed,
still exclusively unreaped leader, revalidated before and after a single
kernel-locked, exact-group PID-membership query. Empty membership or only that
leader proves no live members; any other PID (even another zombie), full tiny
buffer, error/errno, malformed result, ownership loss or exhausted original
cleanup budget refuses. Missing libproc capability refuses before child creation
or relevant Beads writes. No `ps`/per-process state reads are used.
Harmless Darwin happy paths pass; successful native qualification has **not**
been re-established for this changed bridge. It does not contain descendants
that leave the group or claim future containment.
FD8 remains inherited by a surviving native leader until it terminates.

The DB is created directly at `.beads/`; all lifecycle/context/export state
is under `.domestique-private/`. The process runs from
`.domestique-private/beads-context/run` with private HOME/XDG/tmp, no inherited
tokens, Git selectors, proxies, telemetry endpoints or native configuration.
OS policy denies network and writes outside the owned DB/context (plus the
dedicated export directory for export). No broad `.beads/` exclusion is added:
only known owned leaves/subtrees, with shared-worktree collision accounting.
Unknown existing DBs, failed attempts, symlinks, tracked state, configuration
redirects and identity changes refuse without adoption, reinit or purge.

Every actual operation uses the installed `bin/resolve-core beads CORE PROJECT
RELEASE COMMAND ...` dispatcher, with **literal** bound core/project/release
arguments in each fresh shell. Approved operations are ready/show/list,
epic/task create, update/claim, close, dep add/remove, remember and export;
the dispatcher validates the exact argv grammar, pins executable/UUID/backend
and immutable selectors, then checks native ping/where under the sandbox.
Mutable engine bytes do not need to match their initial purge baseline.
Export accepts only optional `--include-memories` and writes
`.domestique-private/exports/issues.jsonl`. No raw `bd` fallback or arbitrary
global/path/config/remote/SQL/setup flags are allowed. Definition loading
alone grants no mutation authority; role trust/capability checks still apply.

Changed executable/context requires explicit manual requalification, not
editing a manifest to suppress a guard. Failed native init/readiness leaves a
failed attempt, never successful Beads creation records. A later publication
interruption may retain verified DB ownership alongside pending journals; it
still cannot qualify for database use. Stop writers, retain journals and
reconcile exact paths manually. Before journals/context or native execution,
exclusive empty-directory reservations and all shared-worktree collisions are
checked, then the owned private tree and exact known native paths are protected.
Reservations/attempt proof are not readiness, successful creation or purge
authority. Unknown native artifacts receive no ownership or new exclusions:
keep them out of commits and reconcile manually; do not adopt or retry.
Do not stage or commit private artifacts.
Local uninstall retains successfully owned Beads state by default (see below).
Global uninstall never touches project state, but a removed core makes the
dispatcher unavailable. Filesystem retention/purge needs neither that core nor
the qualified `bd` executable.

The updater forwards both flags and never applies a failed preview. Invalid
bare/global Beads, state-only without explicit local+Beads, platform+state-only,
uninstall+init, and global/non-uninstall purge requests refuse before writes.
The updater remains update-only and rejects all uninstall/purge requests before fetch.

## Workflow definitions and intended invocation

These names match the current emitters. The qualified database bridge is
implemented, but **full native role execution remains unverified**. A table
entry is not proof of discovery or trust in a blocked native client.

| Client | Load ordinary definition | Decompose significant work | Explicit unattended epic |
| --- | --- | --- | --- |
| Claude | `/domestique-claude` | `/domestique-claude-decompose <task>` | `/domestique-claude-goal <epic-id>` |
| Codex | `$domestique-codex` | `$domestique-codex-decompose <task>` | `$domestique-codex-goal <epic-id>` |
| Copilot | `/domestique-copilot` | `/domestique-copilot-decompose <task>` | `/domestique-copilot-goal <epic-id>` |

Natural-language planning/base requests are allowed (for example, “use
Copilot Domestique to discuss this plan”); they do not authorize database
creation or unattended work. Copilot's emitted skills disable implicit model
invocation, so do not assume automatic skill discovery/loading from that
wording. Only an explicit **same-provider qualified goal trigger** authorizes
unattended dispatch. Copilot's native `/goal` alias and `/autopilot` are **not
Domestique authorization**. Loading goal text, vague intent, or another
provider's syntax is not authorization either. Current private goal names
differ from legacy `/goal` and `$domestique-goal`.

The intended loop is **one implementer, wait, then one fresh reviewer**,
never concurrent implementation/review. The orchestrator adjudicates the
real diff and review, not just the implementer's report; only the orchestrator
closes a passed bead. “Independent” means a separate fresh context, not a
guaranteed stronger model or different vendor. Reviewers never call `bd`,
including reads; they use supplied criteria/evidence. Ordinary work checks
in between beads. Explicit goal authority is limited to one epic, a dedicated
non-default branch and at most 15 closures; ambiguity, regression, repeated
review/infrastructure failure and other core stop conditions return control.
Source commits require user authorization. **Never push, merge, or commit
private state/personal configuration.**

## Where definitions live

The exact core-root expression is
`${DOMESTIQUE_HOME:-${XDG_STATE_HOME:-$HOME/.local/state}/domestique}`.
Use the same environment for later global updates/recovery. Roots must be
absolute, canonical, nonsymlinked and safe for the invoking user.

```text
<core-root>/
  releases/r-<sha256>/API
  releases/r-<sha256>/SHA256SUMS
  releases/r-<sha256>/roles/{orchestrator,implementer,reviewer,goal}.md
  bin/resolve-core
  active
  state/global-manifest
```

Each immutable **Core API 1** release has exactly six files: API, checksums
and four role bodies. The standalone helper is outside releases. It verifies
the release and all role digests; a new workflow binds one release, then
passes that literal binding to delegated roles instead of resampling `active`.
Routing and database guards are separate from loading. Missing/incompatible
core stops without embedded-policy or broader-role fallback.

For the following paths, `{implementer,reviewer}` means the two role files,
and `{,-decompose,-goal}` means the three skills:

| Provider | Global native skills | Global native agents |
| --- | --- | --- |
| Claude | `$HOME/.claude/skills/domestique-claude{,-decompose,-goal}/SKILL.md` | `$HOME/.claude/agents/domestique-claude-{implementer,reviewer}.md` |
| Codex | `$HOME/.agents/skills/domestique-codex{,-decompose,-goal}/SKILL.md` | `$HOME/.codex/agents/domestique-codex-{implementer,reviewer}.toml` |
| Copilot | `$HOME/.copilot/skills/domestique-copilot{,-decompose,-goal}/SKILL.md` | `$HOME/.copilot/agents/domestique-copilot-{implementer,reviewer}.agent.md` |

Codex goal also owns `agents/openai.yaml` under its skill directory, with
implicit invocation disabled.

| Provider | Optional project-local native agents |
| --- | --- |
| Claude | `.claude/agents/domestique-claude-local-{implementer,reviewer}.md` |
| Codex | `.codex/agents/domestique-codex-local-{implementer,reviewer}.toml` |
| Copilot | `.github/agents/domestique-copilot-local-{implementer,reviewer}.agent.md` |

The exact native ID is the qualified filename stem, without `.md`, `.toml`
or `.agent.md`. Each project owns `.domestique-private/manifest` and
`.domestique-private/routing/<provider>.receipt` at its physical root.
No local registry, receipt or lease is written in HOME/core/Git metadata.

Routing binds implementer/reviewer independently: explicit global-only is a
deliberate choice, never recovery. Otherwise local receipt/adapter evidence
requires that exact local role. Broken required receipts, changed bound
profiles, missing/colliding discovery or denied trust/capability **STOP**;
they never silently fall back to global or broader tools. File/receipt
validation is not native discovery proof.

### Local tools/MCP metadata, not prompt copies

Adapters are **complete native configurations**, not merged fields or a
portable `extends` mechanism. Edit only provider-supported metadata while
preserving the **exact emitted `name` and entire stable loader body** (Codex:
the whole `developer_instructions` value). The following are **snippets for
existing local implementers, not replacement files**:

Claude frontmatter, above the preserved Markdown loader:

```yaml
name: domestique-claude-local-implementer
tools: Read, Write, Edit, Bash, Glob, Grep
```

Copilot frontmatter, above the preserved Markdown loader:

```yaml
name: domestique-copilot-local-implementer
tools: ["read", "search", "execute", "edit"]
```

Codex top-level metadata, above the preserved exact `name` and
`developer_instructions` loader value (inline TOML keeps the loader at
top-level rather than accidentally placing it inside an MCP table):

```toml
mcp_servers = { docs = { url = "https://docs.example.invalid/mcp" } }
```

The URL is a nonworking placeholder, not a service to run. Preserve
`name = "domestique-codex-local-implementer"` and the existing top-level
fields. For real edits consult the recorded official
[Claude subagent](https://code.claude.com/docs/en/sub-agents)
(`tools`, `mcpServers`),
[Codex subagent](https://developers.openai.com/codex/subagents/)
(`mcp_servers`), and
[Copilot CLI](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference)
(`tools`, `mcp-servers`) references for your installed version. There is no
universal `tools`/MCP schema or automatic validator here.

MCP **registration/authentication and tool allowlists are separate**. A tools
list cannot register a server, authenticate it, grant trust or make an
unavailable tool usable. No automatic execution or trust approval is implied.
Do not put secrets in these examples, receipts, logs, backups or Beads.

Owned edited metadata is allowed by runtime provenance checks, but requires
fresh native confirmation of exact role ID, no collision, trust, read/shell
capability and the active core protocol before delegation. Use the client's
reload/new-process boundary; **no hot-swap guarantee** exists. The current
native evidence does not verify role capability reload.

**Installer refresh refuses edited native files untouched, even with force.**
It never copies live edited metadata into snapshots, logs, `.bak` or `.new`
files. Compatible global core updates do not rewrite local configs. A full
prompt fork is user-maintained, outside shared-core upgrades, never silently
relinked, and cannot qualify for core delegation after removing the protocol.

### Models are native defaults or explicit session choices

Current private emitters have **no model pins**: Claude retains native
Anthropic defaults, Codex native OpenAI defaults, and Copilot inherits native
personal subagent/parent selection with no Domestique pin. Historical Sonnet,
Opus and `gpt-5.6`/Terra file pins are not current private defaults.

An optional request such as “for this session only, use Terra for implementer
and Astra for reviewer” is a **session role choice**, not a portable model ID
or support claim. Confirm exact available native model/effort identifiers,
state the mapping before dispatch, and use supported per-call/session controls.
Never persist the request in agent files, settings, Beads or memory.
Copilot `/subagents` personal settings are persistent, not an ephemeral way to
make that request. If an explicitly requested choice is unavailable, stop
without substitution; an incomplete vendor restriction needs clarification.
Native precedence still applies. Copilot itself may fall back: Domestique's
instruction is not hard vendor/billing enforcement. Avoid Auto when vendor
selection matters.

## Uninstall and recovery

```sh
bash ./domestique.sh --uninstall --global --dry-run
bash ./domestique.sh --uninstall --global --platform copilot
bash ./domestique.sh --uninstall --global
bash ./domestique.sh --uninstall --local /absolute/project
```

Without a selector removal uses that scope's persisted union. Only unchanged,
positively owned selected leaves are removed. An edited selected provider is
retained **whole**, with nonzero status even under force/dry-run; other clean
selected providers may be removed. No live backup/rename/snapshot is made.
Unknown, tracked, corrupt or symlinked state refuses rather than adopting,
repairing or falling back to the old normal installer.

**Global:** never crawls or edits projects. Final-provider removal removes
owned core files and release history but leaves unproven empty containers,
including the core root. Reinstall deliberately refuses that root without a
valid manifest, even if empty. Stop writers, inspect the exact now-empty core
containers and manually `rmdir` them bottom-up (release `roles/`, release
directories, `releases/`, `bin/`, `state/`, then the core root as applicable).
Use only exact inspected empty paths, never a broad root `rm -rf`, glob cleanup
or secret-bearing backup. Leave native/host containers alone. Explicitly
reinstall to the same root afterward; unchanged local loaders can then use it.
See the [full recovery specification](docs/install-upgrade-design.md#implemented-global-format-preflight-and-recovery).

**Local:** removal works even with a missing/unusable global
core. Last-provider removal retains a valid `providers=none` manifest and
its private-tree exclusion; a bare install rerun creates no agents.
Explicit `--platform` reinstall reuses that attachment with a compatible
global core. Do not delete the valid attachment as a normal reinstall step.
Host `.beads/` and its visibility remain untouched. For a successfully initialized
owned database, ordinary removal preserves every DB/context/export byte and all
original ordered Beads identity, attempt and creation hashes. Last-provider
removal changes only `beads_status=ready` to `retained`, including an already-none
attachment. Repeated retention is read-only. Explicit `--with-beads` reactivation
requires a successful qualified query before `ready`; it never rebaselines a used DB.

```bash
bash ./domestique.sh --uninstall --local /absolute/project --purge-beads --dry-run
bash ./domestique.sh --uninstall --local /absolute/project --purge-beads
```

Purge requires successful ownership, **no remaining provider** (including any
unselected or customized provider), and unchanged **initial** hashes for all eight
recorded `.beads` artifacts, private context and exports. Any changed/missing/extra,
tracked, hard-linked, symlinked, foreign or malformed state refuses before any
profile or DB removal, even with `--force`. Failed/pending attempts never qualify.
Git directory/index routing overrides refuse rather than proving ownership
against another index; unset them explicitly before retrying.
Purge/dry-run never launches or queries `bd`: even a query can change the baseline.
Only validated recorded leaves and bottom-up empty subtrees are removed; metadata
is last. The proven by-init empty `.beads` container is then removed. Successful
purge clears Beads fields only after deletion, retaining the valid private
`providers=none` manifest and its exclusion for reuse.

**Stop raw/older writers first.** Current wrappers, profile changes and cleanup
cooperate through an exclusive nonblocking `flock` on existing owned
`.beads/metadata.json`, held through child reaping/deletion. Busy or
changed-generation metadata refuses. Native `native.lock` is initialization-only,
not a writer lock. This is not a process census or an atomicity promise against
raw/older/hostile writers. Shared exclusions account for every linked worktree:
only no-longer-needed owned rules disappear, never other worktree or host privacy.

**Interruptions:** stop writers, retain `pending`/`published` and available
provenance, and manually reconcile exact paths/digests and exclusion ownership
before retry. Intent is not proof of completed creation/removal. Global
journals live in core `state/`; all local recovery stays only in the project's
`.domestique-private/`, protected by its owned private exclusion, never in a
Git-common-dir sidecar. Pending state refuses ordinary reruns/default routing.
Do not copy edited metadata into recovery or discard unexplained journals.
Bounded shell revalidation is not cross-root atomicity, power-loss durability
or protection against a hostile concurrent same-user writer.

### Shared worktrees and legacy migration

Private `info/exclude` rules are the exact owned native leaves and
`/.domestique-private/`, accounted across every actual linked worktree.
They never hide whole provider trees or unknown/preexisting patterns.
Foreign rules outside managed blocks are preserved, not adopted. Missing or
unreadable worktrees, same-path host collisions, unproven managed rules and
host ignore negations can refuse the whole operation. No shared exclusion
scheme protects future host files at the same path; stop writers and recheck
after worktree/state changes. Concurrent destruction of exclusions can expose
state and is not repaired by overwriting foreign rules.

Legacy migration begins with inventory and a **dry-run plan**, through an
explicit private invocation such as
`bash ./domestique.sh --local /absolute/project --platform copilot --dry-run`.
Only positively created, unchanged, untracked legacy leaves qualify for
automatic removal. Active legacy root policy, modified/adopted assets and
normal/mixed installs without whole-leaf proof require manual reconciliation,
not silent shadowing. Missing/corrupt mode or ownership never means normal
fallback. Broad historical excludes require manual ownership accounting;
force never authorizes index, `.gitignore` or host-policy edits.
Preserve retained legacy evidence privately; do not force-add it or commit
personal state. Export of an eligible private Beads database is supported only
through the qualified wrapper and its approved private export destination;
this does not authorize adoption of an existing unowned database.

## Native evidence and validation

### Final acceptance (2026-09-13)

**Final acceptance remains pending after the runner safety checkpoint.** All
completed matrix results below are dated **prior-runner evidence (2026-09-13)**,
not acceptance of the updated runner or .8/epic completion.

Prior native metadata rerun: **12 observed, 8 blocked, 22 static-only, 0 failures;
exit 2**. Codex **0.154.0** and Copilot **1.0.83** still expose global skills
and fresh-process skill-description reload in A/B. Claude is now **2.1.269**
(the dated .13 checkpoint observed 2.1.268). All six local role files exist
only in A, with B and global state unchanged during local setup, but **all
native role discovery/routing and Claude skill discovery remain blocked**.
No role/MCP/model execution pass is inferred.

Reproduce from this checkout, not `main` or draft #11. Requirements are existing
Bash/Git, ordinary filesystem utilities, ShellCheck and Python 3.11+ (`tomllib`);
the synthetic Beads integration also exercises the existing Darwin sandbox.
No tools or test framework are installed:

```sh
python3 -B -W error test/acceptance.py        # QUICK subset, NOT full-offline acceptance
# One cheap selected scope under default QUICK limits (partial coverage):
python3 -B -W error test/acceptance.py --suite CURRENT:syntax-lint-ast-diff
# Repeat exact selectors; submission order is caller order (partial coverage):
python3 -B -W error test/acceptance.py --suite CURRENT:syntax-lint-ast-diff --suite CURRENT:private-core.sh
# Separately authorized exhaustive OFFLINE run; potentially many hours:
python3 -B -W error test/acceptance.py --exhaustive --jobs 1 --total-seconds 43200 --suite-seconds 14400
# ONLY with separate explicit non-model native consent (not offline coverage):
python3 -B -W error test/acceptance.py --exhaustive --native-only --jobs 1 --total-seconds 43200 --suite-seconds 14400
# Or both groups, with that same explicit native consent:
python3 -B -W error test/acceptance.py --exhaustive --native --jobs 1 --total-seconds 43200 --suite-seconds 14400
```

The runner prints `SESSION_ARTIFACTS` (private temporary logs and JSON report,
not committed files), constructs an allowlisted environment/private HOME and
checkout-local fixture TMPDIR, and removes owned fixtures afterward. Discovery,
its offline protocol units and native context staging are outside the checkout.
Invoke the runner with the ordinary OS-private TMPDIR, not an inherited
checkout-local override. QUICK selects only `private-core.sh`, the native-discovery,
beads-native-context, acceptance, global-path and local-index **unit** suites,
`global-diagnostics-tests.py` (disposable actual-helper probes),
`native-supervision-tests.py` (safe shared-helper wiring/ownership tests), and syntax/lint.
The QUICK and CURRENT inventories also include `beads-fixture-tests.py`
(synthetic qualified-path selection, isolation and provenance units) and
`beads-execution-tests.py` (actual embedded primitive, mocked ownership faults
and harmless children; Darwin happy-path success is not native qualification).
It does not select historical, lifecycle or native-operation suites. The full
CURRENT/HISTORICAL inventories remain available only via `--exhaustive`.
Reports print the mode, exact requested suites, jobs/budgets and progress.
QUICK exit 0 is explicitly `QUICK_SUBSET_NOT_FULL_OFFLINE` with
`full_offline_acceptance: false`; it cannot satisfy full .8 acceptance.
Native-only also never implies offline coverage.

**Global-uninstall fixture modes (test-only).** Direct invocation defaults to
the complete original matrix: 7 cold provider unions, 7 subset/project/lifecycle
cases, 4 retention variants, ownership/index/history/PATH faults and CLI gates,
plus all 15 journal and 24 core faults. Only those last two groups reuse a
production-created synthetic baseline, in memory at its original paths. Root
identities, bytes, modes and mtimes are verified; there are no DB copies,
transplanted manifests or cached production validators. Reset/cleanup requires
all prior assertions and the no-native/network/Beads guard to pass; a failed
eligible case retains its physical temporary evidence instead.

```sh
python3 -B -W error test/global-uninstall.py --list       # exact old-source case inventory
python3 -B -W error test/global-uninstall.py --self-test  # fast synthetic isolation/CLI units
# Reviewer-only representative selection; repeat with each fixture mode:
python3 -B -W error test/global-uninstall.py --fixture-mode fresh --case core:native:current/API:edit --case core:previous:old/API:edit
python3 -B -W error test/global-uninstall.py --fixture-mode reuse --case core:native:current/API:edit --case core:previous:old/API:edit
```

`--case` is exact and repeatable; unknown/duplicate IDs refuse before fixtures.
Execution follows inventory order. List, self-test and selected runs explicitly
report **PARTIAL**, which the unchanged acceptance parser rejects as full global
completion. Self-tests also run by default. `--fixture-mode fresh` repeats the
old genuine setup for the **same bodies**: journal = global install + two Git
project inits/local installs; core additionally performs the real second-release
upgrade and history check. Reuse performs that setup once per compatible group;
restoration is verified before another mutation. Cold cases remain cold in both
modes. Stdout JSON records the exact cases, source SHA-256 pins, actual fixture
setup-command counts, per-fault durations and total elapsed time including
self-tests, setup, restore and final cleanup (not just mutation time).

Independent measurement uses the two commands above in **fresh/reuse/reuse/fresh**
serial order: two matched pairs, **20 minutes total across all four runs**,
including setup. Stop if the remaining budget cannot accommodate the sample;
do not replace these cases with a proxy. Save JSON/stdout in session artifacts,
not the repository. The target is at least 25% elapsed reduction; no result is
claimed yet, and the historical 6920.20s/3173-check full baseline is not current
wall-time equivalence. Run the entire changed global suite once only after
independent correctness/measurement PASS; no native qualification is implied.

**Private qualified Beads fixture (test-only).** The native Beads context,
production and cleanup harnesses default to
`/opt/homebrew/Cellar/beads/1.1.2/bin/beads`. If that file is absent, manually
provision the already-qualified executable in a private location and explicitly
set `DOMESTIQUE_TEST_BEADS_BINARY=/absolute/private/path/to/beads` for the
authorized test invocation. Tests never download or install it, never fall back
to ambient `bd`, and do not require changing the system `bd` symlink or version.
The physical readable regular executable must have SHA-256 exactly
`cb77069648d90fef8876f775d647997beb7bb0ab5461509394c29d5bf14b7c42`;
another 1.1.2 build is not interchangeable. Empty, relative, malformed, missing,
unreadable/non-executable or wrong-digest explicit selections fail loudly,
without native execution or fallback. Production PIN/platform/ABI validation
and native sandboxing remain unchanged.

The runner forwards this setting only to `NATIVE:beads-native-context.py`,
`NATIVE:beads-production.py` and `NATIVE:beads-cleanup.py`. Offline/synthetic
and AI discovery scopes ignore it; product and native command environments
do not inherit it. Context grants only an additional literal read for the
selected executable, not its private parent. Production/cleanup still use the
production sandbox, without nesting it inside a test sandbox. Native opt-in
(`--run` / cleanup `--native`) and separate non-model operator consent are
unchanged; this is not a model questionnaire or user database operation.
Native evidence records the actual resolved path and digest (cleanup prefixes
its completion line with `NATIVE_FIXTURE=` JSON). The runner records them per
relevant scope as `native_fixture`, alongside source-hashed outer provenance,
and rechecks the selection after the scope. These private reports can contain
the selected private path; no machine/session path is committed.

Repeatable `--suite CATEGORY:NAME` filters only exact entries available under the
chosen mode/flags. Categories are `CURRENT`, `HISTORICAL_FIXTURE` and `NATIVE`;
names are literal manifest entries, not paths, globs, regexes or shorthands.
Empty, unknown, duplicate, wrong-category and mode-unavailable selections fail
before provenance capture, fixtures or child launch. For example,
`CURRENT:local-uninstall.py` requires `--exhaustive` and both explicit budgets;
`NATIVE:beads-cleanup.py` additionally requires `--native` or `--native-only`
and separate explicit non-model native consent. `CURRENT:beads-cleanup.py` is a
different, offline scope. Selectors never bypass budgets or the exhaustive serial
guard. Without selectors the ordinary lists/order are unchanged. With selectors,
the requested list and submission order follow the caller; QUICK `--jobs 2`
can overlap work and results can arrive in completion order.

Every explicit selection reports `SELECTED_SCOPES_NOT_FULL_ACCEPTANCE` and
`full_offline_acceptance: false`, even when selecting every available scope or
all native-only entries. Reports retain exact requested category/name order,
provenance, budgets and results. Exit 0 means only the selected work passed;
validated native blockers remain exit 2, and failure/incomplete work exit 1.
There is **no automatic trusted reuse**: no report import, cache, resume trust or
coverage-union generation. Prior failed reports remain unchanged. Any eventual
historical-plus-fresh coverage union requires independent attestation of the exact
runs, source dependencies and tool-fingerprint limitations, plus fresh native
evidence. These selectors do not complete .8 or establish current full acceptance.

Positive finite `--total-seconds` (QUICK default/max **1200**) and
`--suite-seconds` (QUICK default/max **600**) bound execution, including validation and
shutdown; each suite is capped by the remaining total. Shutdown and fixture
cleanup reserve time **inside**, not beyond, these deadlines. Invalid budgets
fail before artifact creation. EXHAUSTIVE requires **both explicit budgets** and
rejects `--jobs 2` before artifacts; native flags require `--exhaustive` too.
No deadline is silently extended. Assertion failures and timeouts stop scheduling,
cancel active remaining work and mark uncompleted coverage `INCOMPLETE`, exit 1,
preserving the original failure rather than labelling it only user cancellation.
Validated native BLOCKED/exit 2 remains distinct and does not trigger fail-fast.

Use serial execution for the next exhaustive run: heavyweight overlap is not
qualified. Earlier healthy observations for global, preflight, profiles,
global-uninstall and local-uninstall were respectively 577, 1079, 3803, 11868
and 9930 seconds (over 7.5 hours combined). The explicit 12-hour total / 4-hour
per-suite example above provides bounded headroom over those observations; it
is neither a completion guarantee nor permission to retry or extend a deadline.
A timeout is reported as `INCOMPLETE` with exit 1, not a proven product assertion
failure. These ceilings are operator-chosen conservative bounds, not expected
current runtime, automatic permission to start, or an exact exhaustive estimate.
Process inspection has a five-second maximum **per-attempt** allowance capped by the
remaining original execution or cleanup deadline; it does not extend either budget.
Only `TimeoutExpired` permits one fresh retry, without sleeping; work cancellation
and fail-fast are checked before retry, while cleanup continues best-effort.
Normal work requires a fresh, fully parsed snapshot within that deadline; partial
output is never used. Recovered incidents emit `PROCESS_INSPECTION_RECOVERED` to
supervisor stderr (including native helpers); runner suite results also retain
`process_inspection_recoveries` counts. These qualify success, not native BLOCKED/2.
Repeated timeouts, nonzero inspector exits, OS failures, empty or
malformed inspection and unsafe/incomplete cleanup are explicit `INCOMPLETE`,
exit 1, `failure_kind: supervision`, distinct from test-budget `timeout` and native
blockers. Isolated `.error` diagnostics retain inspection details and any primary
failure when cleanup also fails; observed descendants still receive identity-checked
cleanup attempts using a fresh snapshot for each individual target. These birth
checks are best-effort (snapshot races and second-resolution birth timestamps),
not kernel ownership. Process states must match
Darwin/Linux primary-state and suffix-flag grammar; only primary `Z` is a zombie.
A child exit observed before cleanup is retained in the suite's `exit` field and
isolated diagnostics alongside stdout/stderr, even when cleanup fails. Cleanup-induced
signal exits do not replace a timeout, cancellation or earlier supervision failure.

Group cleanup requires retained kernel ownership of the direct session leader:
`waitid(P_PID, WEXITED|WNOHANG|WNOWAIT)` observes live/completed children without
reaping, and nonblocking pipe draining preserves stdout/stderr independently of
leader completion. The leader stays unreaped through **all** TERM/KILL group
attempts and cleanup verification, reserving its PID/PGID even after exit.
Only then may drain/wait finalization reap; there is no post-reap group fallback.
Ordinary descendants holding pipes do not delay starting cleanup after leader
completion. `waitid`/`WNOWAIT` support, default SIGCHLD disposition and exclusive
ownership of this child's reaping are required; competing reapers are unsupported.
The runner does not change SIGCHLD configuration. Unsupported disposition,
ECHILD, premature reap or contradictory leader identity permanently disables
group signaling and fails supervision, not success. This is not general kernel
containment: new-session descendants that detach/reparent between observations
can escape detection; positively observed descendants receive separate fresh
birth-checked cleanup. A QUICK pass still does not complete .8.

The stdlib `supervised_process` lifecycle in `test/acceptance.py` is also shared
by native-discovery's batch `run` and interactive `Rpc` startup/close, including
the imported Beads context/production fixtures. Cwd, allowlisted environment,
sandbox argv and optional stdin are forwarded unchanged; stdin writes and both
output pipes are nonblocking (64 MiB batch output / 4 MiB RPC metadata limits).
RPC has its protocol deadline plus a fixed five-second ownership/cleanup allowance;
the outer acceptance 1200/600 caps remain unchanged. These helpers do not poll,
wait or communicate before their last group signal. The embedded production
bridge has its own small stdlib retained-leader primitive (not a test import);
`beads-private.py` reuses that extracted primitive with 600 seconds plus the
same five-second cleanup allowance. `beads-execution-tests.py` exercises actual
production bodies using fully mocked reuse/ownership faults and harmless Python
children, not native evidence. Its 27 tests require Darwin natural zero/nonzero
success, dual-pipe text fidelity, own-group cleanup and FD8 inheritance, and
exercise PID-only EPERM proof/refusal and the original cleanup budget.
Path-based imports work standalone,
through importlib and through runpy without a native/runner dependency cycle.
RPC close also checks non-reaping completion frozen at the first cleanup signal
boundary: valid replies cannot hide a natural nonzero exit. Supervisor-initiated
termination of a still-live server is not a preexisting runtime failure. Natural
status/output and any primary protocol failure survive cleanup errors.

Native timeout/deadline, EOF, generic runtime and cleanup failures are **exit 1**,
not legitimate blockers. Native reports carry structured `failure_kind` values;
validators reject them even if a nested row is mislabeled BLOCKED. Only typed
absent-tool, source-backed unsupported-interface (including optional embedded
SQL), or documented denied tool-approval blockers qualify for exit 2. Diagnostic
prose alone is not a blocker classification. Earlier native reports remain
previous evidence, not requalification under this corrected helper.

For a future separately authorized diagnostic run, append `--global-diagnostics`
to the exhaustive offline command above. This retains `global-progress.tsv`
outside snapshot/native roots in SESSION_ARTIFACTS, alongside source/tool hashes,
configuration/mode/budgets, exact requested commands, exits and suite elapsed times.
Raw `DOM_TEST_DIAG=/absolute/private/path/global.diag bash test/global.sh` is only
an instrumentation interface, **not a provenance-complete acceptance command**.
The parent directory must exist and the path must be outside fixture roots.
`global-diag-v1` records append whole seconds, fixture id, stable caller line,
fixed operation/phase and status; never argv, payload or arbitrary check labels.
Helper start/end timings are paired by case/caller/operation and chronological
order, nested rather than additive; setup, direct operations and gaps remain
unattributed. Interrupted starts may have no end. Diagnostic open/write failure
is explicit and fails the suite, including failures inside snapshot substitutions.
Fixtures are cleaned; append-only progress survives cancellation for inspection.
Operators remove retained session artifacts after evidence review.
The one isolated diagnostic run completed all 316 assertions in 343.74 seconds;
the prior concurrent run timed out at 599.24 seconds. This is consistent with
contention, not proof of causality. That measurement used earlier completion-only
instrumentation, so its event gaps cannot separate snapshot and operation costs.
This predates final formatting and is diagnostic evidence only, **not new-source
acceptance**; no per-operation attribution is inferred. Persistent helper probes
cover noninterference/failures/cancellation without rerunning the 316 assertions.
Current start/end instrumentation has not been rerun across the full suite.
Full .8 still requires independently completed current-source `--exhaustive`
coverage plus qualified native evidence-or-blockers and independent review;
quick green is insufficient. None is automatically launched by this checkpoint.
No phase sampling, implicit native execution,
bytecode caches or silent skips. `local-profiles.sh` runs its Python suite once;
`private-core-commands.py` is a helper, not another suite.
`global-path-tests.py` is included once in `CURRENT`; its checksum-pinned
`20b6fe8d924d50c943242dc730725e59ce1ef956` helper fixture needs no Git history.
`global-path-benchmark.py` remains a separate explicit opt-in, not a default
suite. BSD path metadata now includes special permission bits: root-owned
sticky writable ancestors are allowed outside the boundary, while user-owned
sticky/writable ancestors and unsafe in-boundary paths still refuse.
See the [bounded path/index checkpoints](test/global-path-performance.md).
The resumed index-only checkpoint passed sequentially: **12 index tests,
18 path tests, 55 runner units, 117 private-core checks**. Earlier concurrent
path/runner attempts failed process-inspection/cleanup deadlines; those failures
are retained in the checkpoint record, not counted as passes.
`local-index-tests.py` appears once in `CURRENT`, using a checksum-pinned original
`20b6fe8` index helper; `local-index-benchmark.py` is opt-in only. One fresh
NUL-delimited literal index query per validation replaces per-ancestor queries;
all mutation revalidations, routing/error refusal and path checks remain.
The one actual index-only before/after local-all sample improved
**73.425 → 54.929 seconds** (25.2%, 1.337x), with unchanged 120-second operation
and 300-second total limits. Full local-preflight still has no complete current
summary (prior 599.16-second timeout); no full matrix was rerun here.
Full acceptance remains pending.

SIGINT/SIGTERM stop scheduling, terminate owned groups and observed descendants
(including nested new sessions), and reap direct children with bounded shutdown.
Descendant PID/start-time identities are checked with `ps`, not process names;
terminated orphan descendants are reaped by the OS. This is best-effort process
tracking, not kernel containment: descendants that detach/reparent between
snapshots can escape observation. Cleanup inspection/termination failures are
collected and reported as failures; one failed signal does not stop bounded
best-effort cleanup/escalation of the other positively identified descendants.
Unfinished fixture cleanup is not hidden. Uninterruptible
OS/filesystem operations can delay return. No promise is made to intercept SIGKILL
or an external agent/CLI lifecycle event. **Agent cancellation that sends this
runner no signal is bounded only by the runner's own total deadline.**

Every completed/failed/cancelled task atomically updates a sanitized `report.json`;
it starts as `INCOMPLETE` with exit 1 and includes requested coverage, source-file
hashes (including uncommitted runner/tests), tool binary hashes and timestamps.
The report remains `INCOMPLETE`/`CANCELLED` on partial failure/cancellation.
Cancellation captured during final fixture cleanup, incomplete-report serialization,
or handler restoration is also exit 1, even if all requested suites already passed.
Both previous signal dispositions are restored before the definitive outcome
snapshot and completion write. Once each disposition is restored, that signal has
ordinary native behavior, not runner cancellation; a later native termination can
leave the last persisted report intact. Final-report errors remain nonzero.
Progress heartbeats appear at most every ten seconds while tasks run. Raw fixture
diagnostics stay in the private artifact directory. Reports are never resumed or
used as cached successes.

**Exit 0** means all requested checks passed (native-only does not assert offline
coverage); **exit 1** means a real
test, timeout, malformed report or dependency error; **exit 2** means validated,
precisely reported native blockers, not global readiness. Reports distinguish
`CURRENT`, `HISTORICAL_FIXTURE`, `NATIVE_OBSERVED`, `BLOCKED`, `STATIC_ONLY`
and `ASSERTION_FAILURE`. Native protocols' JSON/counts/required fields and
cleanup completion are validated, not inferred from exit 2 alone.

The **prior** completed stable-source offline runner returned **exit 0**; the separate
native runner returned **exit 2**, solely for the documented native blockers.
These used runner SHA256
`4cdcbd5f2e2c9a3eecd6d4d16a76968320da9bd4f60d574b159452818d9f2d45`,
before this checkpoint. Updated-runner final acceptance and independent review
remain required before .8 closure.

Prior completed **CURRENT offline** per-suite results (reported checks, not native
operation counts):

| Suite under `test/` | Passed |
| --- | ---: |
| `private-core.sh` | 117 |
| `global.sh` | 316 |
| `local-preflight.sh` | 366 |
| `local-profiles.sh` (Python wrapper once) | 1134 |
| `global-uninstall.py` | 3173 |
| `local-uninstall.py` (all phases) | 1365 |
| `beads-guard.py` | 1697 |
| `beads-private.py` (synthetic) | 823 |
| `beads-cleanup.py` (synthetic) | 212 |
| `native-discovery-tests.py` (offline units) | 45 |
| `beads-native-context-tests.py` (offline units) | 31 |
| `acceptance-tests.py` (runner/report/timeout/help units) | 30 |

**HISTORICAL_FIXTURE b60feef**, separately: `codex.sh` **16**,
`copilot.sh` **85**, `guest.sh` **14**, `uninstall.sh` **23**, `upgrade.sh` **12**
reported passes. Syntax/lint: **12 shell files + emitted resolver**, **14 Python
files + embedded controller** passed; warning-level ShellCheck required **no
new warning exceptions**. Observed toolchain: macOS **26.6.2 arm64**, Bash
**3.2.57**, Python **3.14.6**, Apple Git **2.50.1**, ShellCheck **0.11.0**.
Synthetic cleanup recorded **71 fake Beads / 107 instrumented process calls**,
with zero calls during cleanup; it is not native engine evidence.

The five historical shell suites use **b60feef** through
`test/historical-fixture.sh`, with their original retired normal/guest/merge
coverage. They are reported separately, never added to current production
acceptance. Prompt-text/model/goal assertions and synthetic protocol units are
offline contract checks, not native runtime proof.

Native opt-in runs these existing harnesses (only in owned temporary fixtures):

```sh
python3 -B test/native-discovery.py --run
python3 -B test/beads-native-context.py --run  # separate historical experiment
python3 -B test/beads-production.py --run     # CURRENT initializer/bridge
# Requires a private checkout-local TMPDIR; the runner supplies/cleans it:
python3 -B test/beads-cleanup.py --native
```

Production Beads uses fresh temporary HOME/core and two repositories plus a linked
worktree, the real production initializer, and the emitted standalone
dispatcher. It exercises required CRUD/dependencies/remember/export,
state-only/rerun, immutable identity refusal, retention/reactivation,
used-database purge refusal and host/Git/global privacy. Separate native cleanup
exercises pristine purge and cooperative metadata `flock`, with **zero native
queries during cleanup**.
The actual production fixture passed **85 checked processes**; full native
cleanup passed **92 checks**, **38 native Beads / 56 instrumented process calls**,
none during cleanup. The separate historical context experiment passed **8
proofs** across **71 recorded commands**, with **1 optional SQL query blocked**:
`Error: 'bd sql' is not yet supported in embedded mode` (exit 2). Its identity
negative controls are not native AI role execution.
Every native operation uses production's OS sandbox; setup Git uses the test
sandbox. Installer/dispatcher controllers use the allowlisted fixture
environment (nested default-deny sandbox application is refused on this OS).
These are qualified **Darwin arm64 / Beads 1.1.2 CGO embedded / exact SHA-256
`cb77069648d90fef8876f775d647997beb7bb0ab5461509394c29d5bf14b7c42`**
observations, requiring Python and `sandbox-exec`, not universal Beads support.
Raw/older writers must be stopped; only current wrappers cooperate on the
metadata lock. No user DB, authentication, paid/model inference, MCP/trust setup
or native agent execution is part of this acceptance.

See [final evidence and unexecuted runtime gates](docs/install-upgrade-design.md#final-acceptance-2026-09-13)
for per-suite counts, exact blocked interfaces and independent-review boundary.

## Current authority and history

[Install/upgrade design](docs/install-upgrade-design.md) separates current
implemented behavior from historical normal/guest design and blocked future
acceptance. Historical PRDs remain references, not competing setup directions.

Parent-approved reconciliation has **deferred**, not completed/closed or
reparented, `hq-2su` and its unfinished `.3`–`.7`, `hq-e7f`, and `hq-4oh.15`.
Completed `hq-2su.1/.2` remain closed history; commits `2896937`/`58f4d29`
are reused. Draft #11 remains untouched, unmerged and unpushed.
The [mapping and approved deferral](docs/install-upgrade-design.md#old-plan-disposition-parent-approved-deferral)
retain .6's limited qualification boundary, .7 unchanged-only cleanup, and .8's
explicit runtime limitations. Final acceptance and independent review do not
declare all old native criteria fulfilled or the release complete.

## License

MIT — see [LICENSE](LICENSE).
