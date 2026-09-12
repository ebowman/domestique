# Install/upgrade design: current private preview and historical contracts

## Reading this document

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
| Beads operations | .10 implemented fail-closed guard; **every current case stops**, including decompose and goal; .6 safe private initialization **blocked** |
| Removal | .11 global and .12 local profile-only implemented; .7 database retention/purge and integrated final cleanup **open** |
| Native evidence | .13 limited discovery/skill metadata reload observed; exact counts below. Claude skills and all roles blocked; full role/tool/MCP execution acceptance .8 **open** |
| Documentation | .9 approved **now** against implemented preview and .13 evidence, explicitly deferring blocked full .8; not a release-complete claim |
| Old plans | Parent-reconciled **deferred**, not completed/closed/reparented; see final disposition table |

Within the private section, checkpoint accounts record what existed **at that
checkpoint**. Their older “future” statements are superseded by this table and
later implemented checkpoints, not competing active instructions. Future Beads
formats/acceptance are expressly labelled and are not accepted by current
parsers. No successful private database backend or end-to-end workflow is claimed.

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

#### hq-b3q.10 Beads operation boundary checkpoint (.6 still blocked)

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

#### hq-b3q.12 local profile-only removal checkpoint

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
`BLOCKED` names an unavailable/unsafe interface or runtime refusal;
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
  behavior. `--purge-beads` is currently unsupported (exit 2); the future
  database safeguards below confer no present deletion authority. Global
  uninstall never finds, crawls, or deletes local profiles/state.
* The parser rejects, before any write, conflicting scopes/targets,
  `--uninstall --with-beads`, `--purge-beads` without `--uninstall`, every
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

No version threshold is asserted here; .13 records limited observed versions
and .8 full native execution remains open. Domestique emits minimal adapters,
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
local `--with-beads` refuses before inspection/writes as specified in .10;
the runtime guard separately classifies eligibility without reading database
contents or invoking bd. The only
Beads location this contract uses is the literal repo-relative `.beads/`
(`beads_path=.beads` in the local manifest); it does not auto-discover an
arbitrary Beads storage location or assume a resolver/environment route.
Tracked, shared, unknown, symlinked, or otherwise unsafe `.beads/` stops for
an explicit user decision. In particular, an already existing host
`.beads/`, even if it looks initialized, is unowned and is neither hidden nor
adopted.

#### Future Beads lifecycle acceptance (.6 blocked; .7 open, not current parser format)

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

### Later implementation acceptance matrix (not run by this documentation task)

Using a temporary HOME and two disposable Git repositories (including a linked
worktree fixture where applicable), later work must demonstrate:

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

This is the retained full acceptance matrix, **not a completed checklist**.
Current offline coverage and the strictly bounded .13 native metadata
observations are recorded separately above. Role execution, MCP/tool/trust,
model/goal sessions and actual database workflows remain unverified; .8 is
open and .6 blocks database-dependent criteria.

### Old-plan disposition (parent-approved deferral)

The parent has already reconciled **hq-2su and unfinished .3–.7, hq-e7f and
hq-4oh.15 as DEFERRED**, not completed/closed or reparented. No bead queries or
mutations are part of this documentation change. Completed `hq-2su.1/.2`
remain closed history; commits `2896937`/`58f4d29` are reused. Draft #11 is
untouched, not merged or pushed.

| Deferred historical work | Retained private-plan mapping / current status |
| --- | --- |
| hq-2su.3 guest preflight | hq-b3q.4 done; .6 private Beads initialization blocked |
| hq-2su.4 uninstall | .11 global / .12 local profile-only done; .7 database purge/integrated cleanup open |
| hq-2su.5 policy/discovery | .2/.5 done; .13 limited native evidence; .8 full execution open |
| hq-2su.6 acceptance | .8 **OPEN**, not completed by offline tests or .13 discovery |
| hq-2su.7 documentation | current .9, approved now using implemented preview + .13 evidence |
| hq-e7f missing-mode safety | .4 fail-closed legacy classification; absent/corrupt mode never permits normal writes |
| hq-4oh.15 setup/init | no `bd setup`; .6 initialization remains blocked, not solved by four flags |

Old normal/guest dual-mode prescriptions are retired; do not restore
`--no-guest`, unsafe init/rollback or force-overwrite paths. Approval explicitly
defers blocked full .8 rather than holding .9 behind it or presenting the old
plan as ready. This records disposition, **not fulfillment of all old criteria
or release completion**.
