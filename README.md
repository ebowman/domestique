# domestique

A Claude Code config for a **multi-model orchestration workflow**. You run your
main Claude Code session on **Fable** — the **orchestrator** that designs the
work, tracks it in [beads](https://github.com/steveyegge/beads), and delegates.
Each bounded task goes to a **Sonnet** implementer subagent that executes it;
then a separate, fresh-context **Opus** reviewer subagent independently verifies
the result. Fable adjudicates the verdict, closes the bead and commits the
change, and moves to the next one.

The point of the split is to spend model capability where it pays off:

- **Fable** (most capable) plans and makes the final accept/reject call — the
  judgment-heavy work where mistakes are expensive.
- **Sonnet** (fast, cheap) implements — well-scoped execution of a task that's
  already pinned down.
- **Opus** (strong, independent) verifies — a *non-peer* check, so a Sonnet
  implementer's mistakes are caught by a more capable model rather than
  peer-reviewed at the same tier.

Delegating both implementation *and* verification keeps Fable's context lean,
which keeps it a good adjudicator — and the reviewer's independence means the
implementer's "done, tests pass" is checked, not trusted.

## The loop

Roles:

- **Fable orchestrator** — your main Claude Code session. Decomposes goals into
  beads, delegates one task at a time, adjudicates the reviewer's verdict against
  the implementer's report, and decides what's next. Writes code itself only for
  trivial one-liners.
- **Sonnet implementer** — the `implementer` subagent. Receives one bounded
  task, claims it and marks it in progress, does exactly that, runs the
  tests/linter, and returns a terse summary. It does **not** close its own bead
  — the orchestrator closes beads after the reviewer passes them.
- **Opus reviewer** — the `reviewer` subagent. In a *fresh context* (no
  anchoring on the implementer's story), it inspects the real `git diff`, reads
  the changed files, runs the tests itself, and returns a PASS / FAIL / NEEDS-WORK
  verdict judged against the bead's done-criteria. A stronger, non-peer check
  than the implementer. It reviews only — it never edits code or touches bead
  state.

Each subagent's model is pinned in its frontmatter (`model: sonnet` for the
implementer, `model: opus` for the reviewer), so they always run on their own
model no matter what the orchestrator session is set to.

One turn of the flywheel:

1. **Design** — `/decompose <goal>` → Fable turns the goal into a beads epic
   with bounded, dependency-ordered tasks. Nothing is implemented yet.
2. **Pick** — `bd ready` surfaces the next unblocked, actionable task.
3. **Hand off** — Fable delegates that task (with its bead id) to the
   `implementer` subagent → the task runs on Sonnet.
4. **Implement** — Sonnet claims the bead and marks it in progress, does the one
   task, runs tests/lint, and returns a summary (never a full file dump). It
   leaves the bead open — closing it is the orchestrator's call after review.
5. **Verify** — Fable hands the same bead to the `reviewer` subagent. A fresh
   Sonnet independently inspects the real `git diff`, reads the changed files,
   runs the tests itself, and returns a verdict against the done-criteria — it
   judges the work, not the implementer's summary.
6. **Adjudicate** — Fable weighs the reviewer's verdict against the implementer's
   report. Agree it's done → Fable closes the bead and commits the change (one
   commit, bead id in the message). Reviewer flags gaps → reopen or file a
   follow-up and route the fix back to the implementer. Fable reads the diff
   itself only when the two reports conflict.
7. **Repeat** — back to `bd ready`. Fable **stops and checks in with you between
   tasks** — it won't drain the queue unattended unless you tell it to.

```
   you ─▶ /decompose ─▶ ┌──────────────────────────────────────────────┐
                        │  FABLE orchestrator (main session)           │
                        │  plan · bd ready · delegate · adjudicate      │
                        └──┬──────────────▲───────────────▲────────────┘
              one task     │              │ summary       │ PASS / FAIL
             (bead id)     ▼              │               │ verdict
                        ┌──────────────────┴──┐   ┌────────┴─────────────┐
                        │ SONNET implementer   │   │ OPUS reviewer        │
                        │ do task · test ·     │   │ fresh context ·      │
                        │ report back          │   │ diff · tests · judge │
                        └──────────────────────┘   └──────────────────────┘
```

## Setup

Three things make this work. The first is a one-time install; the other two are
how you start each session.

### 1. Install the config into your repo

One-liner into the current directory (add `--with-beads` to initialize beads in
the same step):

```sh
curl -fsSL https://raw.githubusercontent.com/ebowman/domestique/main/domestique.sh | bash -s -- --with-beads
```

Preview first without touching anything:

```sh
curl -fsSL https://raw.githubusercontent.com/ebowman/domestique/main/domestique.sh | bash -s -- --dry-run
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

**Re-running is safe.** Running the installer again in a repo you've already set
up is the supported way to pick up a newer domestique — it's idempotent, and it
preserves your local edits (e.g. MCP tools you added to an agent) via a 3-way
merge instead of overwriting them. See [Upgrading](#upgrading).

### 2. Run the orchestrator session on Fable

Open Claude Code in the repo and set the session model to Fable:

```
/model fable
```

That's the whole model configuration. Each subagent's model is already pinned in
its frontmatter — Sonnet for the implementer, Opus for the reviewer — so
delegation and review each run on the right model **automatically**; you never
switch models by hand mid-flow. To retune, edit `model:` in the agent files:
drop the reviewer to `sonnet` for cheaper/faster peer review, or raise it to
`claude-fable-5` for maximum rigor on high-stakes work.

### 3. Make sure beads is initialized

If you installed with `--with-beads` and `bd` is on your PATH, this is already
done. Otherwise, once per repo:

```sh
bd init && bd setup claude
```

## Running it

A typical session, start to finish:

```
/model fable
/decompose Add rate limiting to the public API, 100 req/min per key, with tests
```

Fable creates the epic and tasks, then prints `bd ready` and the tree for your
review. When you're happy with the plan:

> "Take the top ready task and hand it to the implementer."

Fable delegates it to the `implementer` subagent (on Sonnet), which implements
the task, runs the tests, and reports back (leaving the bead open). Fable then
sends the same bead to the `reviewer` subagent — a fresh Opus that inspects the
diff and re-runs the tests independently — and adjudicates its verdict, then
closes the bead and commits the change before accepting. Then it stops to check
in. You say "next" (or "keep going") and the
loop continues until `bd ready` is empty.

At the end of a session ("land the plane"), Fable files any loose discovered
work as beads and syncs them (`bd sync --flush-only`, then commit `.beads/`).

**Verify it's wired up:** `bd ready` returns tasks (beads is live), and asking
Fable to delegate spawns the `implementer` subagent to do the work and the
`reviewer` subagent to check it — rather than Fable editing or verifying files
itself.

## `/goal` — unattended epic mode

`/decompose` plans; `/goal <epic-id>` executes. It drains one beads epic to
completion by repeatedly running the implementer → reviewer loop **without
stopping between beads**. The default orchestrator rule is "stop and report
before dispatching the next task" (the loop's step 7, above) — `/goal` is the
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
epic branch's diffs and commit history, then merge by hand.

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
