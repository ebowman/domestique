# domestique

A Claude Code config for a **multi-model orchestration workflow**: an
**orchestrator** session that designs the work and adjudicates, an
**implementer** subagent that executes, and a **reviewer** subagent that
independently verifies — with the plan of record tracked in
[beads](https://github.com/steveyegge/beads). The orchestrator runs on a
strong planning model (**Fable and Opus both work well**); the implementer
and reviewer are pinned to Sonnet and Opus respectively. See the three agent
subsections below for what each one does and why.

The point of the split is to spend model capability where it pays off.
Delegating both implementation *and* verification keeps the orchestrator's
context lean, which keeps it a good adjudicator — and the reviewer's
independence means the implementer's "done, tests pass" is checked, not
trusted.

## The loop

The topology has three steps, at three different frequencies — that's the
whole loop:

> After setting your session's model once per session — Fable and Opus both
> work well as the orchestrator — run:
>
> `/decompose <significant task or milestone>`
> * determines an overall architecture
> * breaks work into Task beads, under an Epic, including detailed design
>   instructions and inter-task dependencies
>
> repeat this prompt: **"dispatch next ready bead"**, at which point the
> orchestrator:
> * claims the bead for implementation
> * dispatches the bead to the implementer agent and waits for its return
>   notes, and inspects any new side-task beads it nominates
> * if satisfied, dispatches the bead to the reviewer, in a fresh context
> * when the reviewer returns, assesses its feedback and declares PASS
>   (closing the bead) or FAIL/NEEDS-WORK (sending it back to the implementer)
>
> When all tasks in an epic are complete, tell the orchestrator to
> **"land the plane"** and it will:
> * close the Epic bead
> * sync your beads to the remote
> * update your milestone definition file per your policy in CLAUDE.md

The three agents behind that topology — each pinned to the model tier that
matches what it's for:

### Orchestrator (Fable or Opus)

Your main Claude Code session, on a strong planning model. Decomposes goals
into beads, claims and dispatches one bead at a time, adjudicates the
reviewer's verdict against the implementer's report, and decides what's next.
Writes code itself only for trivial one-liners — it's reserved for the
judgment-heavy work, where mistakes are expensive.

### Implementer (Sonnet)

The `implementer` subagent, on a fast, cheap model. Receives one bounded task,
claims it and marks it in progress, does exactly that, runs the tests/linter,
and returns a terse summary. It does **not** close its own bead — the
orchestrator closes beads after the reviewer passes them.

### Reviewer (Opus)

The `reviewer` subagent, on a strong, independent model. In a *fresh context*
(no anchoring on the implementer's story), it inspects the real `git diff`,
reads the changed files, runs the tests itself, and returns a PASS / FAIL /
NEEDS-WORK verdict judged against the bead's done-criteria — a stronger,
non-peer check than the implementer, since a peer at the same tier as Sonnet
would be more likely to miss what Sonnet missed. It reviews only — it never
edits code or touches bead state.

Each subagent's model is pinned in its frontmatter (`model: sonnet` for the
implementer, `model: opus` for the reviewer), so they always run on their own
model no matter what the orchestrator session is set to — running the
orchestrator on Opus doesn't undermine the Opus reviewer, either: the
reviewer's value is its fresh context and independence, not being a
different model tier from the orchestrator. The agents are the first-class
objects here — the model tier is just the capability each one runs on.

By default, the orchestrator stops and checks in with you between beads — it
won't drain the queue unattended unless you tell it to (see
[`/goal`](#goal--unattended-epic-mode), below).

**Per Epic:**

```
   you ─▶ /decompose ─▶ ┌──────────────────────────────────────────────┐
                        │  ORCHESTRATOR (main session)                 │
                        │  architecture · design · deps · beads        │
                        └──────────────────────────────────────────────┘
```

**Per Task:**

```
   you ─▶ "dispatch" ─▶ ┌──────────────────────────────────────────────┐
                        │  ORCHESTRATOR (main session)                 │
                        │  bd ready · delegate · adjudicate            │
                        └──┬──────────────▲───────────────▲────────────┘
              one task     │              │ summary       │ PASS / FAIL
             (bead id)     ▼              │               │ verdict
                        ┌──────────────────┴──┐   ┌────────┴─────────────┐
                        │ SONNET implementer   │   │ OPUS reviewer        │
                        │ do task · test ·     │   │ fresh context ·      │
                        │ report back          │   │ diff · tests · judge │
                        └──────────────────────┘   └──────────────────────┘
```

**On Epic Completion:**

```
   you ─▶ "land the plane" ─▶ ┌───────────────────────────────────────┐
                              │  close epic · sync beads ·            │
                              │  update milestone file                │
                              └───────────────────────────────────────┘
```

## Setup

**About beads.** [beads](https://github.com/steveyegge/beads) is the
dependency-aware issue tracker that holds domestique's plan of record —
epics, tasks, and the dependencies between them. Its `bd` binary needs to be
installed on your machine *before* you set anything up here: see the beads
README for full install instructions, or if you're on macOS or Linux with
Homebrew, `brew install beads` works well. The steps below (and the
installer's `--with-beads` flag) only *initialize* beads inside a given
repo — they assume `bd` is already installed.

Three things make this work. The first installs — or upgrades — the config with
one idempotent command; the other two are how you start each session.

### 1. Install (or upgrade) the config in your repo

**One idempotent command does both.** Run it in a repo to install; run it
again anytime to upgrade — it installs what's missing and safely
3-way-merges any files you've edited locally instead of overwriting them
(see [Upgrading](#upgrading)). One-liner into the current directory (add
`--with-beads` to initialize beads in the same step, or `--dry-run` to
preview without touching anything):

```sh
curl -fsSL https://raw.githubusercontent.com/ebowman/domestique/main/domestique.sh | bash -s -- --with-beads
```

Or clone once and reuse across machines (recommended):

```sh
git clone https://github.com/ebowman/domestique.git ~/.local/share/domestique
ln -sf ~/.local/share/domestique/domestique.sh ~/.local/bin/domestique.sh
alias dom="$HOME/.local/bin/domestique.sh"          # add to ~/.zshrc or ~/.bashrc
alias dom-guest="$HOME/.local/bin/domestique.sh --guest"  # guest installs (see below)
# then, in any repo:
dom --with-beads
```

This installs `CLAUDE.md` (the orchestration policy, in a managed block that
coexists with your own content), `.claude/agents/implementer.md` (the Sonnet
implementer) and `.claude/agents/reviewer.md` (the Opus reviewer), and
`.claude/commands/decompose.md` (the `/decompose` command) and
`.claude/commands/goal.md` (the `/goal` command).

**Installing locally, per project, makes the agents yours to extend.** Since
the config lands in your own repo rather than some shared global location,
you're free to customize it: add MCP tools to an agent's frontmatter, adjust
its prompt, or retune its `model:` pin. Re-running the installer to pick up
upstream changes preserves those local edits via the 3-way merge described
above — see [Upgrading](#upgrading) for the mechanics.

### 2. Set the orchestrator session's model

Open Claude Code in the repo and set the session model once — Fable and Opus
both work well as the orchestrator:

```
/model fable
```

(`/model opus` works too.) Each subagent's model is already pinned in its
frontmatter, independent of this setting (see [The loop](#the-loop), above).
To retune, edit `model:` in the agent files: drop the reviewer to `sonnet`
for cheaper/faster peer review, or raise it for maximum rigor on high-stakes
work.

### 3. Make sure beads is initialized in this repo

This assumes `bd` is already installed (see "About beads", above). If you
installed with `--with-beads` and `bd` was on your PATH, this repo-level
initialization is already done. Otherwise, once per repo:

```sh
bd init && bd setup claude
```

**Verify it's wired up:** `bd ready` returns tasks (beads is live), and asking
the orchestrator to "dispatch next ready bead" spawns the `implementer`
subagent to do the work and the `reviewer` subagent to check it — rather than
the orchestrator editing or verifying files itself.

## Using domestique in a repo you don't own

Working in someone else's repo (a client project, a coworker's service) but
still want the loop? Pass `--guest`:

```sh
curl -fsSL https://raw.githubusercontent.com/ebowman/domestique/main/domestique.sh | bash -s -- --guest
```

Or, with the clone-once setup from [Setup](#1-install-or-upgrade-the-config-in-your-repo),
use the `dom-guest` alias in any repo:

```sh
dom-guest
```

**What it guarantees.** Nothing lands in the repo's tracked history. The
orchestration policy goes into `CLAUDE.local.md` instead of `CLAUDE.md` — the
tracked `CLAUDE.md` is never read, written, or backed up. Everything domestique
creates (`CLAUDE.local.md`, `.claude/`, `.beads/`, and the `.bak.<timestamp>`/
`.new` files a merge conflict might produce) is added to a managed block in
`<git-common-dir>/info/exclude` (the local, never-committed sibling of
`.gitignore` — resolved via `git rev-parse --git-common-dir`, so it lands in
the right place even when you're in a worktree; `.gitignore` itself is never
touched). Run `git status` right after a guest install *without*
`--with-beads` and it comes back clean. With `--with-beads`, this doesn't
currently hold: `bd setup claude` also writes `.agents/`, `.codex/`,
`.gitignore`, `AGENTS.md`, and `CLAUDE.md`, none of which guest mode's exclude
block covers, so those show up as tracked-file edits or untracked paths in
`git status`. This is a known limitation and is being addressed. Real output
from `domestique.sh --dry-run --guest` (no `--with-beads`) in a scratch repo
(per-file `snapshot base ->` and the
manifest-write lines elided for brevity):

```
domestique: installing into .
(dry run — no files will be modified)
  [dry-run] create ./CLAUDE.local.md (managed block only)
  [dry-run] create ./.claude/agents/implementer.md
  [dry-run] create ./.claude/agents/reviewer.md
  [dry-run] create ./.claude/commands/decompose.md
  [dry-run] create ./.claude/commands/goal.md
  [dry-run] update ./.git/info/exclude (managed block)
  [dry-run] write mode marker -> ./.claude/.domestique/mode (guest)

Summary (planned):
  Created:
    - ./CLAUDE.local.md
    - ./.claude/agents/implementer.md
    - ./.claude/agents/reviewer.md
    - ./.claude/commands/decompose.md
    - ./.claude/commands/goal.md
  Updated:
    - ./.git/info/exclude
  (dry run: nothing was actually changed)
Done.
```

If any of those paths is already tracked in the host repo, domestique warns
(an exclude entry can't hide a tracked path) but keeps going. If the target
isn't a git repository at all, the exclude step is skipped with a warning and
the rest of the guest install still proceeds.

**Sticky mode.** A guest install writes a marker at
`.claude/.domestique/mode`. Re-running the plain install command later (no
`--guest`, no `--no-guest`) against the same directory detects that marker
and stays in guest mode — it won't silently start writing into the tracked
`CLAUDE.md`. `update.sh` respects the same marker on upgrades. Pass
`--no-guest` to convert on purpose: it removes the marker, prints by-hand
instructions for folding `CLAUDE.local.md` into `CLAUDE.md` (nothing is
auto-migrated), and that same run installs `CLAUDE.md` normally. Passing
both `--guest` and `--no-guest` together is a usage error.

## `/goal` — unattended epic mode

`/decompose` plans; `/goal <epic-id>` executes. It drains one beads epic to
completion by repeatedly running the implementer → reviewer loop **without
stopping between beads**. `/goal` is the only thing that lifts the default
check-in-between-beads rule (see [The loop](#the-loop), above), and only
within strict bounds.

**Authorization is scoped and temporary.** A `/goal <epic-id>` invocation is
the sole thing that authorizes continuous, unattended dispatch — and only
across that epic's beads. It expires the instant the epic completes or any
stop condition fires, and it never carries over to another epic or a later
session.

**Safety comes from branch isolation and the same invariants, held harder.**
Before touching anything, the orchestrator creates or switches to a dedicated epic
branch (e.g. `epic/<epic-id>`) and never commits to the default branch for
the rest of the run — it never merges or pushes that branch either; that's
yours to do (see below). Within the run, the core invariants still hold:
one bead in flight at a time, one commit per bead (never batched), and never
close a bead the reviewer didn't pass. A hard ceiling stops the run after 15
beads closed in one go, even if the epic isn't finished, as a runaway-loop
backstop rather than a target.

**Stop conditions halt the loop immediately** and hand control back to you:
a bead failing review twice, any full-suite regression, a decision needing
operator input (spec ambiguity, scope change, unsettled UX/semantics), anything
requiring a push, a config change, or touching files outside the project, or
two consecutive infrastructure/API errors. On completion, on hitting the
ceiling, or on any stop condition, the orchestrator runs the full test suite once more,
summarizes beads closed and commits made, land-the-planes as usual, and
reports anything needing push/merge authority as a proposed command for you
to run — never executing it itself.

```
/decompose Add rate limiting to the public API   # plan: epic + bounded tasks
/goal <epic-id>                                   # execute: drain the epic, unattended, on its own branch
```

When `/goal` stops — completion, ceiling, or a stop condition — review the
epic branch's diffs and commit history, then merge the epic branch into main
by hand, or prompt Claude to do it for you.

## Safety & idempotency

- **Your `CLAUDE.md` survives.** Everything outside the managed block is
  preserved byte-for-byte, whether or not the block existed before (see
  [Upgrading](#upgrading) for merge specifics).
- **Backups.** Any file that would change is backed up first — `CLAUDE.md`
  *always*, even under `--force`.
- **Run it twice** and the second run makes no changes (and creates no new
  backup).
- **`--dry-run`** computes and prints the full plan while touching nothing.

## Installer usage

```
domestique.sh [TARGET_DIR] [options]

Options:
  --dry-run      Print planned changes; touch nothing.
  --with-beads   If `bd` is on PATH: `bd init` (only when no .beads/) then
                 `bd setup claude`. If `bd` is absent, note it and skip.
  --force        Overwrite differing .claude/ files without a .bak backup.
                 (CLAUDE.md is ALWAYS backed up before modification.)
  --guest        Route the managed policy block to CLAUDE.local.md instead of
                 CLAUDE.md — for installing into a repo you don't own (see
                 "Using domestique in a repo you don't own", above).
  --no-guest     Convert an existing guest install back to normal. Mutually
                 exclusive with --guest.
  --uninstall    Remove everything domestique installed (see "Uninstalling",
                 below). Combinable only with --dry-run, --force,
                 --purge-beads, and TARGET_DIR.
  --purge-beads  Only valid with --uninstall: also remove TARGET_DIR/.beads.
  --help, -h     Show this help.
```

Run `domestique.sh --help` for the full option reference, including exact
behavior notes for each flag.

The installer is a single self-contained bash script with the five config files
embedded — no network access needed beyond fetching the script itself.

## Uninstalling

```sh
dom --uninstall path/to/repo            # remove everything domestique installed
dom --uninstall --dry-run path/to/repo  # preview only
dom --uninstall --purge-beads path/to/repo   # also remove .beads/
```

(`dom` is the alias from [Setup](#1-install-or-upgrade-the-config-in-your-repo),
above; substitute your own `domestique.sh` invocation and TARGET_DIR as
needed — TARGET_DIR defaults to the current directory.)

`--uninstall` removes exactly what domestique installed, and nothing else:
the four `.claude/` files, the managed block in `CLAUDE.md` and/or
`CLAUDE.local.md` (whichever carry it), the managed block in
`<git-common-dir>/info/exclude`, and the `.claude/.domestique/` snapshot dir
and mode marker. It prunes `.claude/agents`, `.claude/commands`, and
`.claude` itself only if they're left empty, and it never touches `.beads/`
unless you pass `--purge-beads`. If nothing was installed, it's a no-op
(exit 0).

**Safety-compared, not blindly deleted.** Each of the four `.claude/` files
is compared against its recorded base snapshot (or the pristine emitted
content if no snapshot exists) before removal. Untouched files are deleted
outright; files you've hand-edited are kept, renamed to
`<file>.uninstalled.<timestamp>`, unless you pass `--force`. The same logic
applies to the policy files: a managed block that was never modified is
stripped with no backup (the file is deleted outright if stripping it leaves
nothing behind); a modified block is backed up to `<file>.bak.<timestamp>`
first.

**Marker-sanity refusals.** If a policy file's managed-block markers are
duplicated, mismatched, or in the wrong order, `--uninstall` refuses to touch
that file — it's reported under `Conflicted`, the run exits `3`, and the file
is left byte-untouched. Other files still get uninstalled normally; only the
corrupt one is skipped.

**The round-trip guarantee.** For the common case — a `--guest` install into
an otherwise-clean repo, with nothing touched by hand afterward, followed
immediately by `--uninstall` — every installed file is deleted outright, the
exclude block is fully stripped back out, and the repo returns to
byte-for-byte clean `git status`. If you modified an installed file first,
that file is deliberately preserved instead of deleted (renamed to
`<file>.uninstalled.<timestamp>`), so it will show up as untracked in
`git status` afterward — this is by design (see "Safety-compared, not
blindly deleted", above), not a broken round trip. Real output from a
`--guest` install immediately followed by `--uninstall` in a fresh scratch
repo:

```
$ domestique.sh --guest .
domestique: installing into .

Summary:
  Created:
    - ./CLAUDE.local.md
    - ./.claude/agents/implementer.md
    - ./.claude/agents/reviewer.md
    - ./.claude/commands/decompose.md
    - ./.claude/commands/goal.md
  Updated:
    - ./.git/info/exclude (managed block)
Done.

$ git status
On branch main
nothing to commit, working tree clean

$ domestique.sh --uninstall .
domestique: uninstalling from .

Summary (uninstall):
  Removed:
    - ./.claude/agents/implementer.md
    - ./.claude/agents/reviewer.md
    - ./.claude/commands/decompose.md
    - ./.claude/commands/goal.md
    - ./CLAUDE.local.md
    - ./.git/info/exclude (managed block)
    - ./.claude/.domestique
Done.

$ git status
On branch main
nothing to commit, working tree clean
```

and `.claude/` no longer exists at all.

## Upgrading

Re-running the installer 3-way-merges your local edits against upstream
changes instead of overwriting them.

**How it works.** Every install/upgrade records a base snapshot in
`.claude/.domestique/` — a pristine copy of what was last installed, plus the
`CLAUDE.md` managed-block body and a manifest. The next time you run the
installer, it does a **3-way merge** (`git merge-file`) between your current
file (yours), that snapshot (base), and the newly emitted content (upstream).
If your edits and upstream's changes don't overlap, the merge is clean: your
edits and the new upstream content are both applied, and the snapshot
advances so the next upgrade merges from here.

**On conflict.** If the same lines changed on both sides, the merge can't
reconcile them automatically. In that case domestique:
- leaves your live file (e.g. `implementer.md`, or `CLAUDE.md`) **untouched**,
- writes the merge result, conflict markers and all, to `<file>.new` (for
  `CLAUDE.md` this is `CLAUDE.md.new`),
- backs up your current file to `<file>.bak.<timestamp>`,
- and exits **3** so scripts/CI notice.

To resolve: open `<file>.new`, reconcile the conflict blocks by hand, copy
the result over the live file, then delete the `.new`. Re-run the installer
once you're done to refresh the snapshot. The conflicts use `diff3` style,
so each block has four parts — `<<<<<<<` your version, `|||||||` the
original base, `=======`, and `>>>>>>>` the incoming upstream version;
delete the markers and the sections you don't want.

**CLAUDE.md specifics.** Only the managed block (between the
`<!-- BEGIN domestique (managed) -->` / `<!-- END domestique -->` markers) is
ever merged or replaced. Everything you've written outside the markers is
preserved byte-for-byte, merge or no merge, conflict or no conflict.

**`--force` and `--dry-run`.** `--force` skips the merge entirely and takes
upstream verbatim, discarding local edits to that file (`CLAUDE.md` is still
always backed up first). `--dry-run` computes and prints the full plan —
including what a merge or conflict would do — without writing anything.

**First upgrade of a legacy install.** The 3-way merge needs a base snapshot
to diff against. If a managed file (or the `CLAUDE.md` managed block)
predates the snapshot feature (no `.claude/.domestique/base/...` entry for it
yet) and differs from what domestique would emit, that first upgrade
**adopts** it instead of overwriting it: domestique seeds the base snapshot
from the pristine emitted content and leaves your live file **untouched** —
no `.bak` is written, because nothing was changed. It reports the file under
an "Adopted" heading as *"local edits preserved; re-run to merge upstream"*.
This is default behavior, not a flag — there's nothing to opt into.

That means an existing, customized install (say, an `implementer.md` with a
hand-added `mcp__…` tool) is brought under management on the very next
`domestique.sh` run without losing anything: nothing merges and nothing is
overwritten on the adoption run itself. Run the installer again afterward
and upstream changes merge normally against the newly-seeded base — your
edits are kept, upstream's changes are applied, and if the same lines
changed on both sides you get an ordinary conflict: `<file>.new` written,
`.bak` taken, the live file left untouched, and exit `3`, exactly as
described above. Adoption never silently loses local edits, and it never
silently drops upstream changes either — a conflict is always surfaced,
never swallowed.

`.claude/.domestique/` is domestique's own bookkeeping (snapshots + manifest)
— it's safe to add to `.gitignore` if you'd rather not track it.

## Updating from GitHub

`update.sh` is a thin wrapper that fetches the latest `domestique.sh` and
runs it through the same merge path above:

```sh
./update.sh                       # update current directory
./update.sh path/to/repo          # update a specific target
./update.sh --dry-run             # preview only, applies nothing
./update.sh --force               # discard local edits, take upstream verbatim
./update.sh --source ./domestique.sh   # use a local file instead of GitHub
```

The source defaults to the `main` branch on GitHub and can be overridden with
`--source <path|url>` or the `DOMESTIQUE_UPDATE_SOURCE` env var. It's safe to
run on a schedule (e.g. cron or a periodic CI job) — it always previews with
`--dry-run` first, then applies, and exits:
- `0` — applied cleanly, or already up to date.
- `3` — one or more files hit a merge conflict; check the `.new`/`.bak`
  files and resolve by hand as described above.
- `4` — couldn't fetch or validate the source `domestique.sh`; nothing was
  touched.

## Testing the installer itself

Three self-contained suites cover the installer's own behavior — install/
upgrade merges, guest mode, and uninstall — each runnable directly, no setup
beyond a shell and `git`:

```sh
bash test/upgrade.sh     # 12 scenarios: fresh install, merges, conflicts, adopt
bash test/guest.sh       # 14 scenarios: --guest, sticky mode, --no-guest, worktrees
bash test/uninstall.sh   # 23 scenarios: --uninstall, --purge-beads, round-trip, marker refusals
```

## License

MIT — see [LICENSE](LICENSE).
