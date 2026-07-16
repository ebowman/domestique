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

Because the emitters (`emit_implementer`, `emit_reviewer`, `emit_decompose`,
`emit_policy`) live inside the script itself, an upgraded `domestique.sh`
cannot reconstruct what an *older* version of itself emitted. The merge base
must therefore be snapshotted to disk at install time, not recomputed.

**Correctness invariant (the crux of this whole design): the snapshot base
advances only on a clean apply, never on conflict.** Clean merge/write →
overwrite the live file AND advance the snapshot to the freshly-emitted
`theirs`. Conflict → live file is left untouched AND the snapshot stays at
its old value. Advancing the snapshot on a conflicted file would make the
conflict un-re-mergeable on the next run (the next run's "base" would no
longer reflect what the user actually last saw).

Also note: `domestique.sh` has no `VERSION` constant today. Correctness of
the merge comes entirely from the byte-for-byte content of the snapshotted
base files, not from any version number. The manifest's version/ref field
below is diagnostic only (useful for `--help`/debugging/telemetry), not load
bearing. Introducing a real version constant is out of scope for this design
(file as follow-up if wanted).

---

## 1. Base snapshot / manifest

**Location:** `.claude/.domestique/` in the target repo.

```
.claude/.domestique/
  manifest                              # small key:value file, shell-parseable
  base/
    CLAUDE.md.block                     # last-installed managed-block BODY (no markers)
    claude/agents/implementer.md
    claude/agents/reviewer.md
    claude/commands/decompose.md
```

The `base/` tree mirrors the installed file layout 1:1 (with `.claude/`
stripped from the prefix to avoid `.claude/.domestique/claude/.domestique/...`
recursion), one pristine copy per managed file, **except** for `CLAUDE.md`,
where we snapshot only the managed block's *body* (the content between the
markers, not the markers themselves and not the surrounding user content) —
see §3.

**Manifest format:** flat `key=value` lines, one per line, no nesting — avoids
a `jq`/`yq` dependency in a `bash + git + coreutils` script.

```
installed_ref=<git describe/short-sha of domestique.sh's own repo, or "unknown">
installed_at=<ISO8601 timestamp>
files=.claude/agents/implementer.md,.claude/agents/reviewer.md,.claude/commands/decompose.md,CLAUDE.md
```

**When it's written:**
- **At install** (first time, no `.claude/.domestique/` present): after each
  file is successfully written (create or clean overwrite), write/refresh its
  base snapshot and update the manifest.
- **After each successful apply on upgrade**: same rule — a file's base
  snapshot advances *only* when that file's live copy was just brought to
  exactly the freshly-emitted content (clean install, clean merge, or
  `--force` overwrite). A conflicted file's base snapshot is left untouched.

**Gitignore:** default to **yes** — recommend the installer append
`.claude/.domestique/` to the target repo's `.gitignore` if one exists (or
note it in the summary if none exists / user should add it). Rationale: it is
per-working-copy merge state, not a shareable artifact, and different clones
of the same repo could each have their own locally-edited files with
independently-advancing bases. Tension: a fresh clone (or a clone that never
ran domestique with this feature) has no `.claude/.domestique/` at all, so it
falls back to legacy backup+overwrite behavior on that first run (see below),
then starts snapshotting from there. This is an accepted, explicitly-noted
tradeoff, not a defect.

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
- `base`   = `.claude/.domestique/base/<relpath>` (the pristine snapshot).
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
feature):** fall back to today's behavior — backup `.bak.<ts>` + overwrite
(unless `--force`), identical-file skip unchanged — and *then* write a fresh
base snapshot for the file so future runs can merge. This one upgrade still
loses local edits (there is no base to merge against), which is an accepted,
explicitly-called-out limitation of adopting this feature on a pre-existing
install; every run after that is protected.

**File deleted by the user:** treated as "missing" exactly as today —
`install_plain`'s missing-file branch fires (write theirs fresh), and the
base snapshot is (re)written. No merge is attempted since there is no `ours`
to merge.

**Identical case:** if `ours` == `base` == `theirs` (nothing changed on
either side), or `ours` == `theirs` (independently converged), skip as
today — no write, no backup, snapshot may still be refreshed defensively
though it's already correct.

---

## 3. CLAUDE.md managed-block merge (`install_claude_md`)

The 3-way merge applies **only to the block body** (the content strictly
between `MARKER_BEGIN` and `MARKER_END`), never to the surrounding user
content, which is preserved byte-for-byte exactly as today.

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
- **No snapshot present (legacy):** same fallback as §2 — do today's
  replace-in-place, then write a fresh `CLAUDE.md.block` snapshot.

---

## 4. CLI / UX

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
  - (`Error` cases fold into `Conflicted` in the printed summary but are
    logged distinctly to stderr with the underlying reason.)
- **Exit codes** (matching the script's *existing* mapping, not inventing a
  new one — confirmed against the current script: unknown/unexpected CLI
  args already exit `2`; missing target dir and half-marker refusal already
  exit `1`):
  - `0`: everything applied cleanly (creates, updates, clean merges, skips).
  - `1`: unchanged from today — operational refusals: missing target dir,
    half-marker `CLAUDE.md`.
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

A future "fetch latest `domestique.sh` from GitHub and re-run" updater is a
thin wrapper around this same mechanism and needs no new merge logic: it
downloads the new script, runs it against the target directory exactly as a
manual upgrade would, and the existing snapshot in `.claude/.domestique/`
(written by whichever run last succeeded — manual or automated) is the base
for the 3-way merge regardless of how the new script arrived. The only thing
the updater adds on top is deciding *when* to trigger a run (e.g. on a
schedule, or on detecting a newer upstream ref) and where to surface
conflicts for human attention (e.g. failing a CI job or opening an issue) —
it should treat exit code `3` (conflicts) as "applied partially, needs a
human," not as a hard failure of the updater itself, and exit codes `1`/`2`
as script/invocation bugs worth escalating differently.

---

## Open questions / risks

- **Is "`--force` = discard-and-take-theirs" the right redefinition, or does
  anyone want a separate `--force-merge` flag that forces a merge attempt
  even when e.g. a snapshot is missing (by treating "no base" as
  "base = ours", so it merges against a no-op diff)?** Current design keeps
  `--force` as the simple, well-understood escape hatch and does not add a
  second flag. This needs an operator decision only if the discard-everything
  behavior turns out to be too blunt in practice.
- **`.gitignore` mutation:** should the installer actually *edit* the target
  repo's `.gitignore` to add `.claude/.domestique/`, or only print a
  recommendation? Editing another project's `.gitignore` automatically is a
  bigger claim on the target repo than the current script makes anywhere
  else (it only ever writes inside `.claude/` and `CLAUDE.md`). Defaulted
  here to **print a recommendation, do not auto-edit** `.gitignore` — but
  this is a real product-behavior fork that should be confirmed, not just
  assumed.
- **Snapshot corruption/tampering:** if a file inside `.claude/.domestique/base/`
  is hand-edited or deleted between runs, `git merge-file` will happily merge
  against garbage or the "no snapshot" fallback fires. This design does not
  add integrity checking (e.g. a checksum in the manifest) — flagging as a
  known gap, not solved here.
- **Multiple concurrent installs / CI matrix runs** writing to the same
  target directory simultaneously could race on `.claude/.domestique/` writes.
  No locking is proposed; out of scope unless this becomes a real usage
  pattern.
- **First-adoption backfill:** existing installs (already on disk before this
  feature ships) get zero merge protection on their very first upgrade after
  adopting this design (per §2/§3's legacy fallback) — worth flagging loudly
  in release notes/CHANGELOG when this ships, not just in this doc.
