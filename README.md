# domestique

A Claude Code config for a **multi-model orchestration workflow**. You run your
main Claude Code session on **Fable** — the **orchestrator** that designs the
work, tracks it in [beads](https://github.com/steveyegge/beads), and delegates.
Each bounded task goes to a **Sonnet** implementer subagent that executes it;
then a separate, fresh-context **Opus** reviewer subagent independently verifies
the result. Fable adjudicates the verdict, closes the bead, and moves to the
next one.

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
  task, does exactly that, runs the tests/linter, closes its bead, and returns a
  terse summary.
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
4. **Implement** — Sonnet claims the bead, does the one task, runs tests/lint,
   closes the bead, and returns a summary (never a full file dump).
5. **Verify** — Fable hands the same bead to the `reviewer` subagent. A fresh
   Sonnet independently inspects the real `git diff`, reads the changed files,
   runs the tests itself, and returns a verdict against the done-criteria — it
   judges the work, not the implementer's summary.
6. **Adjudicate** — Fable weighs the reviewer's verdict against the implementer's
   report. Agree it's done → close the bead. Reviewer flags gaps → reopen or file
   a follow-up and route the fix back to the implementer. Fable reads the diff
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
                        │ close bead           │   │ diff · tests · judge │
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
`.claude/commands/decompose.md` (the `/decompose` command).

### 2. Run the orchestrator session on Fable

Open Claude Code in the repo and set the session model to Fable:

```
/model claude-fable-5
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
/model claude-fable-5
/decompose Add rate limiting to the public API, 100 req/min per key, with tests
```

Fable creates the epic and tasks, then prints `bd ready` and the tree for your
review. When you're happy with the plan:

> "Take the top ready task and hand it to the implementer."

Fable delegates it to the `implementer` subagent (on Sonnet), which implements
the task, runs the tests, closes the bead, and reports back. Fable then sends
the same bead to the `reviewer` subagent — a fresh Opus that inspects the diff
and re-runs the tests independently — and adjudicates its verdict before
accepting. Then it stops to check in. You say "next" (or "keep going") and the
loop continues until `bd ready` is empty.

At the end of a session ("land the plane"), Fable files any loose discovered
work as beads and syncs them (`bd sync --flush-only`, then commit `.beads/`).

**Verify it's wired up:** `bd ready` returns tasks (beads is live), and asking
Fable to delegate spawns the `implementer` subagent to do the work and the
`reviewer` subagent to check it — rather than Fable editing or verifying files
itself.

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

The installer is a single self-contained bash script with the four config files
embedded — no network access needed beyond fetching the script itself.

## License

MIT — see [LICENSE](LICENSE).
