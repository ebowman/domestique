# V2/1 record and native-metadata interfaces

**PARTIALLY IMPLEMENTED, NOT PUBLISHED.** The internal local publisher implements
machine A/B/D; project binding/admission/recovery remain future owners' work.
[V2/1 contract](v2-install-contract.md) appendix, frozen by hq-1t9.1 at `020c05c`; **sole wire-schema/metadata-admission authority**.
The parent owns CLI, inventories, effects, trust, privacy and acceptance.
`format=2` is not preview format 1. No extension negotiation, generic record engine or new command; writer, guard, recovery and inspector share these rules.

## A. Common record grammar

Unless explicitly excepted, a record is UTF-8 without BOM, LF-terminated `key=value` lines, no blank lines/comments, in the order specified below.
Notation `I`, `K`, `M` expands to ordered lines; brackets/alternatives are notation, never literal wire bytes. Singletons occur exactly once;
only explicitly repeated blocks repeat. Unknown, missing, duplicate, reordered,
truncated, extra or unsupported-version fields refuse the whole record.
No shell sourcing, interpolation, JSON/YAML inference or escape decoding.

* `H` is 64 lowercase SHA-256 hex digits; `R`/`T` is `r-` followed by H;
  `V` uses the parent's exact `2.MINOR.PATCH`. `N` is decimal 1..2^63-1;
  `D` is decimal 0..2^63-1; neither allows leading zeros except `0`.
  `MODE` is four octal digits, no special bits; `X` is 32 lowercase hex
  transaction-ID digits, freshly chosen and not reused in extant scope evidence.
  `P` is `claude|codex|copilot`; provider sets use that order, no duplicates.
* Values are literal, case-sensitive. Paths contain no Unicode controls (U+0000..001F,
  U+007F..009F) or `=`; absolute paths are canonical physical,
  no trailing slash, `//`, `.` or `..` components. Relative paths have no leading
  slash or such components. Spaces, quotes, backslashes and colons are literal.
  Parse `PATH:H:MODE` from the right; never split a path on every colon.
  `-` is absence only where specified, never an empty value or a path.
* Records are at most 1 MiB, 16384 lines, 8192 bytes/line **including LF**; paths at most
  4096 UTF-8 bytes. At most 1024 release blocks, 3 provider blocks, 4096
  transaction items/facts or retirement entries. All limits apply together;
  preflight all aggregate encodings and maximum completed facts/results before
  any publication; overflow refuses intact, never prunes releases/history.
  ASCII inventories sort by byte order; other paths sort by unsigned UTF-8 bytes.
* Final line is `checksum=H`: hash every preceding byte including its final LF,
  excluding this line. Exceptions: `PACKAGE`, `SHA256SUMS` and `active` have
  exactly the parent §2 grammar; `published` has the chained framing in §D.
  Hashes detect corruption, not signatures or ownership. Re-encoding a parsed
  record must reproduce its bytes exactly, including the checksum line.
* Read only exact allowlisted paths. Validate invoking UID, nonsymlink ancestors,
  regular single-link leaves, sizes and directory identity before/after reads;
  compare device/inode, size, mode and nanosecond mtime/ctime where available.
  Before each write/unlink and before releasing guarded output, repeat identity,
  current-byte hash, index and safe-path checks relevant to that scope.
  Machine publication rechecks exact Git/native overlap ancestors, including existing parents, at every creation/write/link/rename/unlink and final success; never caches absence.
  Changed boundaries stop publication and cleanup writes, retaining partial evidence.
  Machine file writes use checked OS I/O, including partial-write/EINTR rechecks;
  error/close cannot flush latent bytes after refusal. Bytes already written before
  the first observed boundary remain evidence, not a zero-side-effect claim.
  Failed temporary machine afterimages are retained without automatic unlink or
  restoration, even if empty or apparently equal; their names confer no cleanup
  authority. Successful no-clobber link cleanup checks the original open inode,
  exact bytes/mode/link count and current boundaries before removing its temporary
  link. Changed or unwitnessed objects remain for manual reconciliation with
  pending/unknown status; no creation fact is inferred from them.
  A change during validation refuses, never retries by adopting new bytes. There is no hostile same-owner writer, native sandbox or fsync guarantee.

`I` = `worktree_root`, `git_dir`, `git_common_dir` (absolute paths), then
`worktree_dev`, `worktree_ino`, `git_dir_dev`, `git_dir_ino`, `git_common_dev`,
`git_common_ino`, `owner_uid` (D), as defined by parent §3.
`K` = `core_root=G`, `core_api=1`, `adapter_abi=2`, `activation_format=2`,
`helper_abi=2`. `M` = `core_root=G`, `core_dev=D`, `core_ino=D`, `owner_uid=D`,
`launcher_path=$HOME/.local/bin/domestique2`, `launcher_abi=2`.
Machine records must agree on M; project I/K and binding machine inode fields
must agree with the independently validated machine, not an ambient root.

`created=PATH:H:MODE` means a witnessed successful exclusive creation, not
planned bytes or subsequent equality. `baseline=PATH:H:MODE` is pristine
generated comparison data, paired immediately after created for the same path.
Never advance either to user-edited bytes. Recreating a removed owned leaf in
an authorized new generation records that new creation, not adoption by equality.
Mutable bookkeeping is owned by exclusive scope/journal publication, with
before/after integrity in §D; it is not recursively hashed into its own manifest.
No native preimages, values, source paths, credentials or project lists in G.

## B. Runtime manifest

Path **`G/state/runtime-manifest`**. Writers: hq-5jc.4/hq-1t9.2/.3; readers: launcher/guards hq-1t9.2/.4 and inspector hq-1t9.6.
Ordered lines: `format=2`, `scope=runtime`, M, `core_api=1`, `adapter_abi=2`,
`activation_format=2`, `helper_abi=2`, then launcher created/baseline pair
(absolute launcher path), then release blocks ordered by R, then checksum.
Each block: `release=R`, `version=V`, `source_kind=local|official`, `official_version=V|-`, all payload created/baseline pairs, `end_release=R`.
Payload paths are **`releases/R/<payload>`**, in ASCII order, with exactly the parent's closed inventory including `PACKAGE` and `SHA256SUMS`.
Executable payload/launcher modes are `0755`; other payloads are `0644`. Metadata records/active are `0600`; owned private state directories are `0700`.

R equals the exact SHA256SUMS digest; every listed baseline must match that
verified package, and every retained immutable payload must match its creation
hash/mode. Launcher baseline is the trusted bootstrap's ABI-2 dispatcher with M's
G embedded, not a candidate-provided arbitrary command. A manifest is published
only after these exclusive creations succeed; failed intent remains only in §D.
For local input `official_version=-`; for official input it equals V. This field
is the sole retained official mapping, unique by V as well as R; local packages
with the same V may have different R and never qualify as official by equality.
Explicit verified official selection of an already retained local R may add its
mapping and change source_kind to official; creation pairs remain unchanged.
This requires the full official verification, not inference from package bytes.

The manifest does **not** name current active: only `G/active` selects it.
Active and manifest publication provenance is scope metadata under §D, not
payload creation pairs. Validate active as exactly `release=R\n`, R membership
and the selected package/ABI before dispatch; never select the last manifest
block. Validate T and explicitly bound R similarly without resampling active.
All retained mappings are structurally checked; safe disable needs only the
verified management entrypoint, not intact workflow bodies (parent §2).
During pending, complete old/new releases can remain usable; incomplete,
unlisted or corrupt selections are unavailable, not inferred rollback.

## C. Project records and whole-provider binding

Paths **`W/.domestique-private/v2/manifest`** and **`routing/P.receipt`**
relative to that state directory. Writers: hq-1t9.4/hq-5jc.7, disable hq-1t9.5;
guard hq-1t9.4 and inspector hq-1t9.6 are readers.
Manifest lines: `format=2`, `scope=project`, I, K, provider blocks in
Claude/Codex/Copilot order, exclusion lines in ASCII pattern order, checksum.
Provider block: `provider=P`, `status=enabled|disabled`, `generation=N`,
`template_release=T`, created/baseline pairs in ASCII LEAF order,
`end_provider=P`. LEAF is exactly the parent's provider inventory, including
Codex's goal sidecar; each block retains the complete creation/baseline history
even when disabled leaves are absent. Native baseline modes are `0644`.
Exclusion line: `exclude=PATTERN:created|preexisting:H`; PATTERN is one of
parent §4's exact patterns. H hashes the identity-qualified managed block
including delimiters/LFs, or the exact `PATTERN\n` for a preexisting line.
Managed delimiters are `# BEGIN domestique-v2 H\n` and
`# END domestique-v2 H\n`, where delimiter H hashes the exact I lines.
Between them put only created patterns in ASCII order, each with LF.
Every created exclusion line records that same block hash; no empty block.
Here created proves successful block publication under §D, not ownership of
the host file. Preexisting lines confer no edit/removal authority.

Receipt lines: `format=2`, I, `provider=P`, K, `generation=N`,
`record_sha256=H` (exact provider block including end line), `skill=ID` lines,
`role=ID` lines, checksum. IDs are exactly the table IDs, ASCII ordered within
each category, three skills/two roles. No sidecar ID; its leaf is still required.
Absent block means absent; disabled block has no valid enabled receipt.
First generation is 1; disabled-to-enabled increments; unchanged enabled
providers do not increment. Refuse overflow. T never advances on a compatible
rerun/update. Compare protected bytes against pristine T, not current metadata.

An ephemeral **BINDING** is one literal LF-containing argv, never persisted.
Ordered lines: `format=2`, `scope=binding`, I, `provider=P`, K,
`core_dev=D`, `core_ino=D`, `generation=N`, `receipt_sha256=H` (entire receipt),
`release=R`, `entry_skill=ID`, then `adapter=LEAF:H:MODE` lines in ASCII order
for the **complete current provider inventory**, `route_implementer=ID:H`,
`route_reviewer=ID:H`, checksum. Five adapters for Claude/Copilot, six for Codex:
roles, all skills and the goal sidecar, not merely the two role files.
Route hashes equal the corresponding adapter hashes; modes must equal baseline.
No extra/missing leaf, duplicate ID, other-provider leaf or symbolic role token.
This is a trusted caller-carried binding, not a global mutable session registry.

Internal ABI: `start G W P SKILL` emits only BINDING;
`read G W P ROLE BINDING` emits only guarded body;
`route G W P ROLE BINDING` emits only the bound `ID:H\n` role token.
Unknown/empty/extra argv refuses, errors emit no stdout. SKILL is an exact
table ID; read ROLE is `orchestrator|goal|implementer|reviewer`, route ROLE
is `implementer|reviewer`. Only start may sample active, once, after guarding
via the verified immutable T helper. Subsequent helper/bridge/body is same-R.
Goal reads additionally require entry_skill to be that provider's goal ID;
an explicit epic remains required by the guarded workflow, not supplied by
metadata or inferred from a role token. Ordinary/decompose never confer goal.

Start validates all current leaves under §F, loader/identity, I/K/M, complete
manifest/receipt and absence of project-pending/revocation; hashes **live bytes**,
samples/verifies R and rechecks that same snapshot before emitting the binding.
Before every skill/body read and delegation, including delegated role entry,
revalidate those conditions and every adapter byte hash against BINDING.
Receipt/pristine hashes alone cannot hide changed current skills or sidecars.
Any admitted metadata edit (even whitespace), unsafe/missing leaf, stale
generation/receipt, changed inode identity of W/G, or unsupported edit stops
the old binding before body output/delegation. Never hot-rebind or resample.
A fresh workflow may validate permitted metadata and acquire a new binding,
with fresh exact-native-ID/capability confirmation under parent §5.
No metadata/model/tool permission grants unattended authorization.

## D. Transaction records and state interpretation

Reuse **`pending`**, **`previous`**, **`published`** in J:
machine J=`G/state`; project J=`W/.domestique-private/v2`;
retirement J=`G/state/retire-global`. Writers are the parent §4 operation owners;
same owners reconcile manual recovery, hq-1t9.4 guards and hq-1t9.6 inspects.
Pending is the exclusive no-clobber lock, not a PID/timeout lease; any uncleared
journal or project exclude-afterimage refuses mutating reruns.
Machine and retirement mutators also refuse each other's pending/orphan files.
No process-liveness inference, automatic takeover/resume or recovery command.

`previous` lines: `format=2`, `scope=previous`, `tx=X`,
`transaction_scope=machine|project|retire`, identity (M for machine/retire,
I then K for project), path blocks ordered by absolute path, checksum.
Each path block: `path=ABS`, `state=absent|file|directory`, `sha256=H|-`,
`mode=MODE|-`, `dev=D|-`, `ino=D|-`, `record_bytes=D`, `record_chunks=D`,
zero or more `record_chunk=N:HEX` lines, `end_path=ABS`.
Absent uses `-` for hash/mode/dev/ino; directory uses `-/MODE/D/D`;
file uses `H/MODE/D/D`. Only prior runtime/project/retirement manifests, receipts and
active MUST carry their entire validated bytes; all other paths have counts
0 and no chunks. No native/exclude/user preimages. For B metadata bytes,
C=ceil(B/4000), indices are contiguous 1..C, lowercase hex decodes exactly
4000 bytes per nonfinal chunk, 1..4000 in the final chunk. No empty chunks.
Counts, concatenated length/hash, inner schema/checksum and outer checksum
must all agree; missing/extra/reordered/truncated chunks refuse, never salvage.
B<=1048576 gives C<=263 and at most 8018 bytes/chunk line including LF.
Encoded chunks cost exactly 2B + sum(15+digits(i), i=1..C) bytes; framing
and all other paths also count toward previous's 1 MiB/16384-line limits.

`pending` lines: `format=2`, `scope=pending`, `tx=X`, `operation=` one of
`install|update|enable|disable|retire-global`, transaction_scope and identity
as above, `previous_sha256=H`, `selected=SET`, `old_release=R|-`,
`new_release=R|-`, `outcome=complete|partial`, item blocks, retire-only lines, checksum.
SET is comma-separated P in provider order for project/retire, `-` for machine;
machine old/new are prior active (or absent on first install)/selected R;
non-machine old/new are `-`. Partial is legal only for disable/retire retention.
Item block: `item=N`, `phase=PHASE`,
`action=create|replace|remove|mkdir|keep|edit-exclude`,
`path=ABS`, `after_sha256=H|-|retirement-ledger-v1`, `after_mode=MODE|-`,
`reason=none|edited|unowned|tracked|unsafe|unreadable|missing|shared`,
`end_item=N`. N is contiguous from 1, execution order below, then path order
within a phase. One item per path; previous contains exactly these paths.
Create/mkdir require prior absence; replace/remove require prior whole-file
ownership and unchanged preflight identity/hash. Create/replace uses H/MODE
or the sole sentinel below; mkdir uses `-/0700` (native nonprivate parents
`0755`); remove/keep uses `-/-`.
Keep is only for disable/retire leftovers, requires a non-none reason and
partial outcome; all other actions require reason none. The sole derived hash
sentinel, retirement-ledger-v1, is mandatory only on retire-global's exact
§E manifest create/replace item, phase manifest, mode 0600; nowhere else.
Retire-only lines: `home_root=ABS`, `home_dev=D`, `home_ino=D`, then §E entry
blocks for each native remove/keep item, sorted as §E, one per path.
These are validated provenance/observation inputs: status is planned-removal
for remove (reason none), retained or absent for keep (matching reason);
removal_tx/removal_fact_sha256 are both `-`. No other fields differ from §E.
All non-retire pending omits these lines; this plan asserts no removal fact.
Freeze previous/pending bytes in memory; exclusively publish pending, then
previous, then the published header, before any item. Hashes are known already.

Paths are limited to the operation's parent write set: machine package leaves/
their exact parents, launcher, active, runtime-manifest; project table leaves/
parents, manifest, exact receipts, common-dir info/exclude; retirement exact
qualified old global native leaves and §E manifest. Journal paths themselves
are framing, not items. No recursive directory removal, arbitrary path from
input records, native replacement/backup, settings write or new info directory.
Missing ancestors may be mkdir items before their children; a path's directory
claim is not proof of later child creation. Planned hashes are never facts.

**Existing-host exclusion edit exception.** Only enable/disable may use
edit-exclude, phase exclusions, on independently Git-resolved I.git_common_dir
`/info/exclude`; never a path trusted merely because a manifest names it.
Preflight the common-dir/info identities, UID, regular single-link leaf,
mode and full live bytes/hash; recheck §A's snapshot immediately before rename.
Nonempty input must be UTF-8 LF-terminated; input/output obey §A text bounds.
The before hash/identity is in previous (counts 0); after_sha256 is the exact
full transformed-file hash, after_mode the unchanged host mode.
To edit/remove an existing own block, prior project provenance must prove its publication;
validate its exact old delimiters, ordered patterns and recorded block hash.
Absent provenance plus even identical markers, edited/duplicate/half markers
or ambiguous overlap refuses enable; disable retains with reason edited/unowned/shared.
An unmanaged exact PATTERN+LF outside all managed blocks stays preexisting,
byte-unchanged; it is not inserted into our block or adopted by matching hash.
Other-worktree blocks remain opaque and byte-unchanged, never borrowed authority.
With no prior own block, append only the new block at EOF; otherwise transform
U+old_block+V to U+new_block+V at the same offset, preserving U/V exactly.
New block contains only required created patterns in ASCII order; remove a
pattern only when no retained/other-provider/shared need remains. Empty new
block means remove only old_block, retaining even an empty exclude file.
Unprovable shared effect/need refuses enable or retains exclusions on disable
(reason shared, PARTIAL); do not scan siblings or alter other-worktree blocks.
An absent allowlisted exclude uses create, mode 0644, containing only our block.
Existing exclude may be modified only by edit-exclude, never replace/remove,
even if we created it. Successful create/edit plus manifest publication proves
only owned block provenance; equality alone never grants it. No-op emits no item.

`edit-exclude` apply may stage one afterimage at `J/exclude-afterimage` in
0700 J, exclusively, initially 0600, <=1 MiB; preflight the same filesystem as exclude.
This is a temporary publication copy, NOT a journal backup/baseline/preimage;
no native metadata staging, dry-run copy, logged content or recovery adoption.
Set only the staged file to the planned host mode; recheck live before bytes/
identity, atomically rename, verify outside bytes and full after hash/identity,
then record exclude-edited. A race refuses, never recomputes/adopts new input.
Clean owned staging before commit/clear; failure leaves pending. Crash leftovers
are private but not guaranteed erased: refuse reruns, report pending/unknown,
manually reconcile/discard only proven staging, never restore host from it.

`published` starts `format=2`, `scope=published`, `tx=X`,
`pending_sha256=H`, `header_sha256=H` (hash all preceding header bytes).
Then append fact blocks, each: `sequence=N`, `phase=PHASE`, `item=N|0`,
`result=created|replaced|removed|directory-created|exclude-edited|revoked|committed`,
`provider=P|-`, `generation=N|-`, `sha256=H|-`, `mode=MODE|-`,
`dev=D|-`, `ino=D|-`, `fact_sha256=H`.
Sequence is contiguous from 1. Hash input is the preceding header/fact hash
as 64 ASCII hex bytes plus LF, followed by this block before fact_sha256.
Applied items occur at most once, in plan order; result must match action
(keep has no fact). Creation/replacement/exclude-edited reports actual verified post-write
hash/mode/dev/ino; directory-created has hash `-`; removed uses all `-`.
All use provider/generation `-` except revocation, which uses selected P and
its previous enabled generation, item 0, and hash/mode/dev/ino `-`.
Commit is last, phase complete, item 0, all other value fields `-`.
Exclude-edited matches only edit-exclude and its full before/after contract.
Retirement manifest created/replaced reports the actual §E-derived digest,
never the sentinel. Other file-result hashes must equal their planned H.

PHASE order: machine `release,launcher,manifest,active,complete`;
enable `exclusions,native,manifest,receipt,complete`;
disable `revocation,native,receipt,exclusions,manifest,complete`;
retire `native,manifest,complete`. Mkdir uses its child's phase; launcher
parents use launcher. A compatible existing launcher has no items/writes.
First-install exclusive final launcher creation and postverification precede its manifest created/baseline assertion; intent never supplies this pair.
Before manifest/active exist, version/operations refuse unavailable without selecting staging or guessing a release. Static help alone is discovery-free
exit 0, not runtime certification (parent §1). Initial J/ancestor claims are framing, performed
exclusively after preflight; a crash before valid framing is unknown partial,
never creation authority. Skip empty phases, not required work. Disable appends
selected-provider revocation facts before any deletion; pending already blocks
all project workflows. Manifest disabled status persists revocation after clear.
Publish receipts/active last as in parent §4; revalidate actual final state
before committed, then unlink published, previous, pending in that order.

A valid prefix plus syntactically possible torn/missing final fact is **pending failure**, not a
completed removal/creation. Reconcile only its complete hash-valid prefix;
an action without its fact is ambiguous even if bytes equal intent/are absent.
Apply §A byte/line/UTF-8/control limits to all observed bytes before prefix classification, including torn suffixes;
impossible fields/values/checksum prefixes are unknown, not extensions or ignored tails. Preserve exact bytes.
An exclude rename without its fact is likewise ambiguous, not block ownership.
Valid committed plus leftover journal files is **cleanup-pending**, not a
mutating no-op. Orphan/malformed/checksum-mismatched/cross-identity files are
**recovery-unknown**; preserve everything. No age/PID makes them stale-safe.
No journal means consult current manifests/live leaves, not historical intent.
Disable may finish with known retained edits, clear a committed transaction
and return 1 PARTIAL; failed writes leave pending. Invalid prior ownership
cannot prove revocation: report unknown without claiming selected providers off.
Machine-pending does not revoke complete validated active/bound releases;
inspection separately reports actual old/new/unavailable and recovery status.

## E. Global retirement evidence

Path **`G/state/retire-global/manifest`**; writer/reconciliation hq-1t9.7,
reader hq-1t9.6. Ordered lines: `format=2`, `scope=retire-global`, M,
`home_root=ABS`, `home_dev=D`, `home_ino=D`, entry blocks, checksum.
Entries sort by absolute leaf path then source manifest hash. Each block:
`leaf=ABS`, `provider=P`, `origin=GEN`, `source_sha256=H|-`,
`source_manifest=ABS|-`, `source_manifest_sha256=H|-`,
`created_sha256=H|-`, `created_mode=MODE|-`,
`baseline_sha256=H|-`, `baseline_mode=MODE|-`,
`status=removed|retained|absent`, `reason=REASON`,
`removal_tx=X|-`, `removal_fact_sha256=H|-`, `end_leaf=ABS`.
GEN is `legacy-pre-snapshot|v1-snapshot-1|historical-draft-copilot|
private-preview-api-1|unknown` (one token, no embedded LF).
REASON is `none|edited|unowned|tracked|unsafe|unreadable|missing|shared`.

Paths must be exactly source-qualified old HOME-relative native inventory
resolved beneath recorded HOME, never an old core/helper/setting/project.
Reuse the parent's pinned Origin/qualified_cohort decoders and exact old
manifest grammars; no new format-1 writer/adoption or guessed inventory.
source_sha256 is the qualified originating installer hash, not a URL/version
claim. Source manifest path/hash plus created hash/mode establish witnessed
creation only when that source actually records it. Snapshot/digest baselines
alone do not. Missing evidence fields use `-`, never invented pristine values;
baseline mode unavailable in old evidence must be qualified from that exact
source's installation convention, otherwise removal refuses.

Removed requires every provenance field, reason none and X/H of its successful
§D removed fact. Retained has a non-none/non-missing reason, no X/H; absent has
reason missing, no X/H. Absence/equality is **not proven retirement**.
Return 0 only with no retained/ambiguous selected inventory, not universal quiet.
Retained and new absent observations (keep/missing) give 1 PARTIAL.
Mid-removal failure stays pending; never publish the ledger incrementally.

**Acyclic ledger publication.** Validate prior ledger from previous (or empty),
HOME identity and source evidence before fixing pending's plan. For a repeated
entry key, provenance fields must equal prior metadata; only status/reason and
removal X/H may change. Never replace a prior removed entry; preserve untouched
entries byte-for-byte, including old removal evidence. Stale prior evidence
refuses, not permission to mint a second removal under another source key.
Once pending/header are fixed, perform native removals and append successful
facts. Only after every planned removal has its complete validated fact, derive
the ledger: overlay planned entries on prior keys, change planned-removal to
removed and fill X and that item's fact H; keep retained/absent inputs unchanged.
Sort, use pending M/HOME (must match prior), serialize/checksum under §A/E. Preflight
its maximum encoded size using fixed-width X/H placeholders, not future hashes.
Publish this exact ledger no-clobber or owned replacement, re-read/verify it,
then append its created/replaced fact with actual digest, then committed.
Dependency order is pending -> header -> removal facts -> ledger -> ledger
publication fact -> commit; no ledger digest occurs in pending/removal facts.
While journals exist, verification reconstructs that exact result from validated
previous/plan/facts. Missing/torn removal or ledger-publication fact stays pending,
even if live absence/ledger bytes match; no automatic completion or inferred fact.

Exact duplicate keys are forbidden. Revalidate source identity/hash and leaf state
before removal and during inspection. A missing/changed source or recreated
leaf makes old evidence **stale**: report recovery/legacy-global unknown or
present, exit 1, never delete again or claim quiet. Old immutable removal facts
remain historical truth, not current ownership. Record no observed edited
hashes/values/preimages; keep inspection transient and diagnostics sanitized.

## F. Bounded native metadata admission

Owner hq-5jc.7 implements this classifier with hq-1t9.4 guard reuse;
hq-1t9.6 projects safe field names/status only. No dependency on hq-5jc.23's
deferred incompatible rebase engine. Authoritative rolling docs read 2026-09-16:
[Claude agents](https://code.claude.com/docs/en/sub-agents#supported-frontmatter-fields),
[Claude skills](https://code.claude.com/docs/en/skills#frontmatter-reference),
[Claude MCP](https://code.claude.com/docs/en/mcp),
[Codex agents](https://developers.openai.com/codex/subagents/),
[Codex MCP](https://developers.openai.com/codex/mcp/),
[Codex skills](https://developers.openai.com/codex/skills/),
[Copilot CLI](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference),
[Copilot agent MCP](https://docs.github.com/en/copilot/reference/custom-agents-configuration#mcp-server-configuration-details).
These justify shapes, not tested support or effective permissions; parent §5
still requires native qualification. No interpretation of settings elsewhere.

All native leaves: UTF-8 without BOM, LF (including final LF), <=1 MiB,
<=16384 lines, <=8192 bytes/line, <=4096 bytes/string, <=32 MCP servers,
<=64 entries/array or map, depth <=5. Bounds apply before classification.
Mutable strings S are double-quoted with only `\"`/`\\` escapes, single-quoted
with doubled apostrophes (YAML only), or plain `[A-Za-z0-9_./*+@-][A-Za-z0-9_./*+@:-]*`.
Reject controls and bare YAML boolean/null/number tokens where S is required;
quote them instead. Model is nonempty S, opaque native ID/alias, not a registry.
Bool is bare `true|false`; integer is canonical decimal 1..3600 where used.
String arrays are one-line `[S, S]` (optional spaces, no trailing comma),
including `[]`; distinct decoded entries only. Names for servers/map keys are
`[A-Za-z_][A-Za-z0-9_-]{0,63}`, unique and case-sensitive.

YAML frontmatter starts at byte zero `---\n`, ends at the next `---\n`;
after that, **every body byte** is protected. Maps use `key: value` or
`key:\n` and two-space child indentation; no tabs, flow maps, anchors, aliases,
tags, merge keys, multiline/folded scalars, document markers or inline comments.
Blank lines and whole-line `#` comments are allowed only inside mutable spans.
Claude MCP is the explicit list exception illustrated below: two-space `-`,
inline named-map entry, six-space server fields, eight-space env map keys.
Copilot server fields use four spaces, nested env keys six spaces.
Mutable fields may be ordered freely; duplicate keys anywhere refuse.

TOML mutable fields use `key = value`, quoted S only (no single-quoted strings),
Bool/integer/arrays as above; tables exactly as listed below. No dotted
assignments, quoted keys, inline tables, arrays of tables, multiline values,
dates, floats, escapes beyond `\"`/`\\`, or reopened/duplicate tables.
Protected `developer_instructions` is the one multiline exception: exact
template-T delimiter/value bytes, never a parser-selected mutable string.

Admission is **optional fields in the table only**, at those locations/types.
Removing/inserting/changing a whole admitted field subtree is allowed. Delete
those spans from live and T **in memory**; the remaining protected bytes must
match exactly. Comments/spacing outside those spans are protected too.
Fresh templates use this grammar, no tools/model/MCP defaults or grants.
Required name/description, loader/core binding, body, all goal/user/implicit
invocation controls and their presence/absence are protected. Codex goal
`policy.allow_implicit_invocation=false` and Claude/Copilot goal
`disable-model-invocation=true` cannot change. Also protect absent `context`,
`agent`, `hooks`, `skills`, `infer`, `models`, `modelPolicy`, `default_prompt`,
`dependencies` and all other routing/authorization controls: none are editable
through a metadata escape hatch, including additional prompts/automatic entry.

| Native location | Admitted optional fields (all others protected or unsupported) |
| --- | --- |
| Claude role frontmatter | `model: S`; `tools`, `disallowedTools`: string arrays or quoted comma-separated tool names; `mcpServers`: list below. |
| Claude skill frontmatter, including goal | `model: S`; `allowed-tools`: same tool list. No skill mcpServers field. |
| Codex role TOML | `model = S`; `model_reasoning_effort = S` restricted to `minimal,low,medium,high,xhigh,max,ultra`; `sandbox_mode = S` restricted to `read-only,workspace-write,danger-full-access`; MCP tables below provide native tool filters (no invented top-level tools key). |
| Codex skill frontmatter | No mutable fields in this subset. |
| Codex goal `agents/openai.yaml` | Optional `interface` map containing only `display_name: S`, `short_description: S` (at least one). `policy` is protected; no model/tools/dependencies extension here. |
| Copilot role frontmatter | `model: S`; `tools`: string array or quoted comma-separated tool names; `mcp-servers`: map below. |
| Copilot skill frontmatter, including goal | `allowed-tools`: same tool list. No skill model/mcp-servers field in this subset. |

Tool name is `[A-Za-z0-9_./*:-]+`, <=256 bytes; comma form splits on comma
with optional ASCII spaces and rejects empty/duplicate entries. Arrays may be
empty, not omitted by serialization; omission and explicit empty keep native
semantics. Tool specifier expressions are unsupported, not widened to all tools.

Claude `mcpServers` is a list of unique server-name S references or unique
named inline maps, not a single server map or JSON string. Inline subset is
stdio only: required `command: S`, optional `type: stdio`, `args: [S, S]`,
`env` map of environment names to S. Environment names use
`[A-Za-z_][A-Za-z0-9_]*`, <=64 bytes. Reference/inline names cannot collide.
For example (inert shape, not an instruction to run a server):
```yaml
mcpServers:
  - configured_server
  - local_server:
      type: stdio
      command: "operator-chosen-command"
      args: []
      env:
        EXAMPLE: "literal"
```
Codex permits `[mcp_servers.NAME]`: exactly one of `command = S` (stdio)
or `url = S` (HTTP); optional `enabled`, `required` Bool, `enabled_tools`,
`disabled_tools` string arrays, `startup_timeout_sec`, `tool_timeout_sec`
integer. Stdio additionally permits `args` and `env_vars` string arrays,
`cwd = S`, and `[mcp_servers.NAME.env]` environment-name/S assignments.
env_vars contains environment names only, not objects. HTTP has no stdio
fields; no other nested table/auth/header/helper field is admitted here.

Copilot `mcp-servers` is a NAME-to-map, **not Claude's list**. This subset is
local/stdio only: required `type: local` or `type: stdio`, `command: S`,
`tools: [S, S]`; optional `args: [S, S]`, `env` environment-name/S map.
Both documented type spellings are preserved, never translated. Remote
Copilot/Claude MCP configurations are unsupported here, not silently accepted
as equivalent to Codex URL tables. Strings may contain native variable/secret
reference syntax when quoted; Domestique never resolves, evaluates or logs it.

Unsupported syntax/shape/field, oversize input, protected edits or inconsistent
inventory: enable/start/read/route refuse (exit 1, no body/delegation or writes);
inspect reports compatibility unsupported/unknown, exit 1, no content detail.
Report only fixed reason codes and admitted permission field names, never
unknown key names, model/server names, values or parser excerpts. hq-ln2's
existing NATIVE_FIELDS omits all three MCP keys and is **not** this validator.
Supported metadata survives compatible enable byte-for-byte, with no
reserialization, snapshots, backups, diffs, staging or baseline advancement.
Machine updates do not read any native leaves: they preserve even unsupported
bytes untouched but do **not** thereby admit them for workflow use. Unselected/
unmanaged files are untouched, not classified/adopted as supported. Disable
can revoke and retain edited/unsupported leaves without parsing their values.
No credential/trust/model translation, server execution/installation, native
fallback or wider role on refusal; unavailable requested capabilities stop.
