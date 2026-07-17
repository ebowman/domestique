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
> work well as the orchestrator — you simply
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
alias dom="$HOME/.local/bin/domestique.sh"   # add to ~/.zshrc or ~/.bashrc
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
frontmatter — Sonnet for the implementer, Opus for the reviewer — so
delegation and review each run on the right model **automatically** no matter
what you set here (see [The loop](#the-loop), above). To retune, edit
`model:` in the agent files: drop the reviewer to `sonnet` for cheaper/faster
peer review, or raise it for maximum rigor on high-stakes work.

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

## `/goal` — unattended epic mode

`/decompose` plans; `/goal <epic-id>` executes. It drains one beads epic to
completion by repeatedly running the implementer → reviewer loop **without
stopping between beads**. The default orchestrator rule is to stop and check
in with you between beads (see [The loop](#the-loop), above) — `/goal` is the
only thing that lifts that rule, and only within strict bounds.

**Authorization is scoped and temporary.** A `/goal <epic-id>` invocation is
the sole thing that authorizes continuous, unattended dispatch — and only
across that epic's beads. It expires the instant the epic completes or any
stop condition fires, and it never carries over to another epic or a later
session.

**Safety comes from branch isolation and the same invariants, held harder.**
Before touching anything, Fable creates or switches to a dedicated epic
branch (e.g. `epic/<epic-id>`) and never commits to the default branch for
the rest of the run — it never merges or pushes that branch either; you
review and merge it by hand. Within the run, the core invariants still hold:
one bead in flight at a time, one commit per bead (never batched), and never
close a bead the reviewer didn't pass. A hard ceiling stops the run after 15
beads closed in one go, even if the epic isn't finished, as a runaway-loop
backstop rather than a target.

**Stop conditions halt the loop immediately** and hand control back to you:
a bead failing review twice, any full-suite regression, a decision needing
operator input (spec ambiguity, scope change, unsettled UX/semantics), anything
requiring a push, a config change, or touching files outside the project, or
two consecutive infrastructure/API errors. On completion, on hitting the
ceiling, or on any stop condition, Fable runs the full test suite once more,
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

- **Your `CLAUDE.md` survives.** If it exists without markers, the managed block
  is appended and every existing byte is preserved verbatim. If it already has
  the markers, only the content between them is replaced.
- **Backups.** Any existing file that would change is copied to
  `<file>.bak.<timestamp>` first. `CLAUDE.md` is *always* backed up before
  modification, even under `--force`.
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
  --help, -h     Show this help.
```

The installer is a single self-contained bash script with the five config files
embedded — no network access needed beyond fetching the script itself.

## Upgrading

Re-running the installer against a repo you've already installed into is how
you pick up a newer domestique — and it's designed so **your local edits
survive**. Say you hand-added an MCP tool to `implementer.md`'s frontmatter;
upgrading won't clobber it.

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

## License

MIT — see [LICENSE](LICENSE).
