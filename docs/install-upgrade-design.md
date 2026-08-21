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
