# domestique

Private orchestration definitions for **Claude Code, Codex CLI, and GitHub
Copilot CLI**: an orchestrator plans bounded work, an implementer executes it,
and a fresh reviewer independently checks the result. The intended plan of
record is [Beads](https://github.com/steveyegge/beads).

> **IMPLEMENTED PREVIEW — not end-to-end ready.** Shared core, global
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
> metadata reload. **Claude 2.1.268 skill discovery and all three clients'
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
Database retention/unchanged-only purge (.7) is implemented; full native execution
acceptance (.8) remains open.

## Setup: global first

Use the **checked-out current preview script**, once per user, selecting the
client you actually use:

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

### Updates from this checkout

Until published, always specify the local source:

```sh
bash ./update.sh --source ./domestique.sh --global
bash ./update.sh --source ./domestique.sh --local /absolute/project
# Preview only:
bash ./update.sh --source ./domestique.sh --global --dry-run
```

The updater defaults to remote **main**, not this preview. `--source PATH/URL`
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

The [.13 checkpoint](docs/install-upgrade-design.md#hq-b3q13-isolated-native-discovery-checkpoint-bounded-part-of-8)
records the actual 2026-09-12 evidence: **12 native skill observations,
8 blocked records, 0 assertion failures, 22 static-only records; exit 2**.
All six local role files existed only in fixture A, but native local-role
visibility in A, absence in B and global-role coexistence remain blocked for
all clients. Skill description reload is not live core or role/MCP execution.
**45 offline harness unit tests** passed; they are synthetic validation, not
native acceptance.

Contributor commands from the repository root (Bash/Git, ordinary filesystem
utilities and Python 3.11+ for `tomllib`; no added test framework):

```sh
(
mkdir -p .test-private
chmod 700 .test-private
export TMPDIR="$PWD/.test-private" GIT_CEILING_DIRECTORIES="$PWD/.test-private"
bash test/private-core.sh
bash test/global.sh
bash test/local-preflight.sh
bash test/local-profiles.sh
PYTHONDONTWRITEBYTECODE=1 python3 test/global-uninstall.py
PYTHONDONTWRITEBYTECODE=1 python3 test/local-uninstall.py
PYTHONDONTWRITEBYTECODE=1 python3 test/beads-private.py
PYTHONDONTWRITEBYTECODE=1 python3 test/beads-cleanup.py
# Opt-in pinned native cleanup fixture (no AI/auth/MCP):
PYTHONDONTWRITEBYTECODE=1 python3 test/beads-cleanup.py --native
PYTHONDONTWRITEBYTECODE=1 python3 test/beads-production.py --run
PYTHONDONTWRITEBYTECODE=1 python3 test/beads-guard.py
PYTHONDONTWRITEBYTECODE=1 python3 -W error test/native-discovery-tests.py
bash -n domestique.sh update.sh
shellcheck --severity=warning domestique.sh update.sh
git diff --check
rmdir "$TMPDIR"
)
```

Current suites use isolated fixtures; executable guards are offline evidence.
The five shell suites `test/{upgrade,guest,uninstall,codex,copilot}.sh` use
the pinned **b60feef OFFLINE historical installer** via
`test/historical-fixture.sh`. They test retired formats/behavior, not current
production CLI acceptance. Migration fixtures also use that historical source.

Opt-in native metadata harness:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 test/native-discovery.py --run
```

The observed/expected current result is **exit 2 (blocked)**, not 0/full-ready.
Without `--run`, it makes no native calls and returns STATIC_ONLY/exit 2.
It uses only existing installed tools and macOS `sandbox-exec`; unavailable
clients/isolation stop rather than installing tools or weakening isolation.
Temporary physical HOME/XDG/core and two Git roots, an allowlisted environment,
denied network/Keychain access and bounded subprocess lifetimes isolate the
probe. No model, auth, native MCP, trust setup or Beads commands are invoked.
See the checkpoint for exact interfaces, limits and counts.

Private Beads has separate, narrowly qualified evidence. Run the new synthetic
protocol/ownership suite or opt in to actual production native fixtures:

```sh
python3 -I -B test/beads-private.py
python3 -I -B test/beads-production.py --run
```

The latter uses fresh temporary HOME/core and two repositories plus a linked
worktree, the real production initializer, and the emitted standalone
dispatcher. It exercises required CRUD/dependencies/remember/export,
state-only/rerun, immutable identity refusal and host/Git/global privacy.
Every native operation uses production's OS sandbox; setup Git uses the test
sandbox. Installer/dispatcher controllers use the allowlisted fixture
environment (nested default-deny sandbox application is refused on this OS).
It does not access user databases or execute native agent/model/MCP workloads.
The historical `.14` experiment remains separate evidence, not a substitute
for this production test or proof of untested platforms.

## Current authority and history

[Install/upgrade design](docs/install-upgrade-design.md) separates current
implemented behavior from historical normal/guest design and blocked future
acceptance. Historical PRDs remain references, not competing setup directions.

Parent-approved reconciliation has **deferred**, not completed/closed or
reparented, `hq-2su` and its unfinished `.3`–`.7`, `hq-e7f`, and `hq-4oh.15`.
Completed `hq-2su.1/.2` remain closed history; commits `2896937`/`58f4d29`
are reused. Draft #11 remains untouched, unmerged and unpushed.
The [mapping and approved deferral](docs/install-upgrade-design.md#old-plan-disposition-parent-approved-deferral)
retain .6's limited qualification boundary, .7 unchanged-only cleanup, and .8 full
acceptance open. This .9 documentation describes implemented preview behavior
and limited .13 evidence now; it does not declare old criteria fulfilled or
the release complete.

## License

MIT — see [LICENSE](LICENSE).
