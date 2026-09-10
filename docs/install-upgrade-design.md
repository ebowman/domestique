# Install/upgrade design: 3-way merge for local edits

## Problem

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

## Residual risks and resolved decisions

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

## Future private global/local contract (hq-b3q; not current installer behavior)

**Status and boundary.** This section is the approved-direction design for the
private-only replacement, to be implemented on `epic/hq-b3q` from
`58f4d29` (which includes the reviewed Copilot payload commit `2896937`).
It does not describe the legacy implementation above as if it had already
changed. `main` remains unchanged; this plan neither merges/pushes draft PR
#11 nor rewrites completed history. “Private” is the sole ownership mode in
this contract: global and local are distribution scopes, not normal versus
guest modes.

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
* `--local TARGET --with-beads --state-only` is the one explicit
  state-only spelling: it initializes or records only the private Beads
  attachment and installs no adapters. It rejects `--platform`, profile/role,
  MCP, tool, or model modifiers as irrelevant. Without `--state-only`,
  `--with-beads` is valid only with an explicit local adapter/profile request
  and means “also request project-state initialization”; ordinary explicit
  local setup may create the default implementer+reviewer profiles. A bare
  local rerun does not install adapters merely to initialize tasks.
  `--with-beads` with `--global` is a usage error. It never runs `bd setup`.
  No model-selection installer flags are added.
* `--dry-run` performs all scope, ownership, core-compatibility, and merge
  decisions without writes. `--force` may resolve a positively owned,
  untracked, non-symlinked file merge only; it never overrides tracked,
  unknown, customized, ambiguous, or legacy-authority protections. The
  updater accepts and forwards the same explicit scope and selector. An
  updater invocation without a scope remains local compatibility behavior
  (`TARGET`, or `.`), never global.
* `--uninstall --global` removes only positively owned global assets.
  `--uninstall --local TARGET` removes only that worktree’s positively owned
  attachment; old positional/bare uninstall remains local compatibility
  behavior. `--purge-beads` is local-only and may remove only positively
  owned untracked project Beads state after the safeguards below. Global
  uninstall never finds, crawls, or deletes local profiles/state.
* The parser rejects, before any write, conflicting scopes/targets,
  `--uninstall --with-beads`, `--purge-beads` without `--uninstall`, every
  global purge, state-only outside `--local TARGET --with-beads`, and role or
  profile modifiers that are invalid for the selected providers or operation.

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

Publication first creates and fsyncs a new, private, non-symlinked
`releases/<release>` directory, writes and verifies all four role files plus
`API` and `SHA256SUMS` (six files total), then atomically replaces only `active`
with a complete temporary file in `<private-root>`. It never promises native
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
only interface is `resolve-core bind ROOT ROLE [RELEASE]`, which writes the
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
or stages this helper with core compatibility checks, not as a role/provider;
this task does not install it.

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
`created=<provider>:<native-relative-leaf>:<sha256>`. Local keys are
`format`, `scope=local`, `worktree_root` (absolute physical root),
`core_root` (absolute), `core_api=1`, `providers`, repeated `created`, and
repeated `baseline=<provider>:<native-relative-leaf>:<sha256>`; its
`providers` is either one of those seven sets or the literal `none`, which is
valid only for state-only or retained-after-removal state. Native
relative leaves are relative only to that provider's bounded native root
shown in the tables; they must be normalized, nonempty, and contain neither
`..` nor a symlink. Root fields (`core_root`, `worktree_root`) are absolute canonical paths; `beads_path` and `beads_created` are project-relative as defined below.
`created` is the sole native-adapter creation provenance; a pristine byte match never
creates ownership. `baseline` describes generated bytes only and is not
ownership evidence.

An explicit install adds its selected providers to that scope's persisted
union; a bare rerun uses that union. Scoped uninstall removes only requested
providers from its own scope, leaving every other provider and the other
scope unaffected. A local `providers=none` bare rerun is state-only and
installs no adapter. Missing state defaults only to a fresh requested install
when every destination is absent. Missing, corrupt, conflicting, or
out-of-root state with an existing destination is an error; known legacy
names enter the explicit legacy classification path, and unknown files do
not. Neither case scans executables, guesses provenance, or repairs state.
The installer may add the exact `.domestique-private/` tree and exact
positively proven-owned `.beads/` subtrees to the worktree's private exclude
mechanism only after linked-worktree accounting proves they belong to that
worktree. This positive ownership exception does not permit excluding whole
provider directories, `.beads/` wholesale, or any unknown/host state.

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

| Provider | Bounded emitted native fields | Core declaration location / source fact | Reload and trust |
| --- | --- | --- | --- |
| Claude | documented agent `name`, `description`, `tools`, `mcpServers`; Markdown body | body instruction declares `core_root`, API, role, and resolver; [subagents](https://code.claude.com/docs/en/sub-agents), [skills](https://code.claude.com/docs/en/skills) | restart/reload as documented; project/server trust must be confirmed |
| Codex | documented agent TOML fields and `mcp_servers` only | `developer_instructions` prompt-body value contains the declaration/resolver, not a new TOML key; [subagents](https://developers.openai.com/codex/subagents/), [skills](https://developers.openai.com/codex/skills/) | start/reload a new session and confirm native trust/capability |
| Copilot | documented agent frontmatter `name`, `description`, `tools`, `mcp-servers`; Markdown body | body instruction declares the protocol; [CLI reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference) | documented reload/discovery plus project/server trust confirmation |

No version threshold is asserted here; later `.8` tests actual supported
versions. Domestique scaffolds only this metadata, accepts no arbitrary MCP
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
outside this bounded supported provider/version table are reported by
Domestique preflight as unsupported (with provider, field, and detected
version if available), not presented as native schema validation and not
silently dropped or broadened. New-scope generated cores and adapters contain no credentials. If an owned
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
Retained modified files/backups/state remain private/excluded recovery
evidence after uninstall. Removing global core warns that linked local
adapters will stop on their required-core check; it does not repair them by
fallback.

Global definition installation and project Beads initialization are distinct.
Loading a skill creates neither a database nor Git artifact. On explicit
local `--with-beads`, existing project state is first classified. The only
Beads location this contract uses is the literal repo-relative `.beads/`
(`beads_path=.beads` in the local manifest); it does not auto-discover an
arbitrary Beads storage location or assume a resolver/environment route.
Tracked, shared, unknown, symlinked, or otherwise unsafe `.beads/` stops for
an explicit user decision. In particular, an already existing host
`.beads/`, even if it looks initialized, is unowned and is neither hidden nor
adopted.

For an absent eligible `.beads/`, only
`bd init --stealth --skip-agents --skip-hooks --non-interactive` (or a
verified equivalent with all safety flags) may run. The local manifest records
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

These are bounded offline/smoke procedures for hq-b3q.8; no live native
runtime check, build, or runtime-version success is claimed by this document.

### Old-plan disposition (requires parent approval before bead changes)

`hq-2su.3` (Copilot guest isolation), `hq-2su.4` (mixed uninstall),
`hq-2su.5` (policy/command discovery), `hq-2su.6` (lifecycle/runtime
acceptance), and `hq-2su.7` (Copilot documentation) are **not closed or
reparented here**. Their normal/guest dual-mode acceptance is intentionally
retired; their retained criteria map respectively to hq-b3q.4/.6 (private
preflight/Beads), .7 (ownership-safe scoped removal), .2/.5 (native routing),
.8 (offline plus real-runtime evidence), and .9 (post-evidence docs).
`hq-e7f` is carried forward as “corrupt/absent mode never falls back to normal
writes,” now implemented by rejecting legacy ambiguity. `hq-4oh.15` is
carried forward as “no `bd setup`; safe project initialization only,” rather
than as a guest exception. User approval covers the implementation direction,
not silent alteration of these historical beads or claims that their old work
completed.
