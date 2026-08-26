# domestique

A Claude Code and Codex config for a **multi-model orchestration workflow**: an
**orchestrator** session that designs the work and adjudicates, an
**implementer** subagent that executes, and a **reviewer** subagent that
independently verifies — with the plan of record tracked in
[beads](https://github.com/steveyegge/beads). The orchestrator runs on a
strong planning model. Claude installs pin the implementer and reviewer to
Sonnet and Opus; Codex installs pin them to `gpt-5.6-terra` at medium effort
and `gpt-5.6` at high effort. See the three agent subsections below for what
each one does and why.

The point of the split is to spend model capability where it pays off.
Delegating both implementation *and* verification keeps the orchestrator's
context lean, which keeps it a good adjudicator — and the reviewer's
independence means the implementer's "done, tests pass" is checked, not
trusted.

## The loop

The topology has three steps, at three different frequencies — that's the
whole loop:

> After setting your session's orchestrator model, start with one of these
> platform-native invocations:
>
> - Claude Code: `/decompose <significant task or milestone>`
> - Codex: `$domestique-decompose <significant task or milestone>`
>
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
> * file any loose discovered work as beads
> * run the final quality gates
> * follow Claude's installed session-close policy, or in Codex report
>   proposed handoff commands and obey the active commit/sync/push authority

The three agents behind that topology — each pinned to the model tier that
matches what it's for:

### Orchestrator

Your main Claude Code or Codex session, on a strong planning model. Decomposes goals
into beads, claims and dispatches one bead at a time, adjudicates the
reviewer's verdict against the implementer's report, and decides what's next.
Writes code itself only for trivial one-liners — it's reserved for the
judgment-heavy work, where mistakes are expensive.

### Implementer

The `implementer` subagent, on a fast, efficient model. Receives one bounded task,
claims it and marks it in progress, does exactly that, runs the tests/linter,
and returns a terse summary. It does **not** close its own bead — the
orchestrator closes beads after the reviewer passes them.

### Reviewer

The `reviewer` subagent, on a strong, independent model. In a *fresh context*
(no anchoring on the implementer's story), it inspects the real `git diff`,
reads the changed files, runs the tests itself, and returns a PASS / FAIL /
NEEDS-WORK verdict judged against the bead's done-criteria — a stronger,
non-peer check than the implementer. It reviews only — it never edits code or
touches bead state. In Codex, the orchestrator fingerprints tracked and staged
changes plus bead state before and after review; any reviewer-introduced delta
is a failed review and an immediate stop.

Each subagent has a platform-native model pin: Claude frontmatter uses
`model: sonnet` and `model: opus`; Codex TOML uses `gpt-5.6-terra` with
`model_reasoning_effort = "medium"` and `gpt-5.6` with
`model_reasoning_effort = "high"`. The agents are the first-class objects —
the model tier is just the capability each one runs on. If a pinned Codex
model is unavailable to your account, Codex reports the affected role and
model. Edit that role's TOML, or remove its `model` and
`model_reasoning_effort` keys to inherit the parent; domestique never silently
substitutes one role's model for another.

By default, the orchestrator stops and checks in with you between beads — it
won't drain the queue unattended unless you tell it to (see
[unattended epic mode](#unattended-epic-mode), below).

**Per Epic:**

```
   you ─▶ decompose ─▶ ┌──────────────────────────────────────────────┐
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
                        │ implementer          │   │ reviewer             │
                        │ do task · test ·     │   │ fresh context ·      │
                        │ report back          │   │ diff · tests · judge │
                        └──────────────────────┘   └──────────────────────┘
```

**On Epic Completion:**

```
   you ─▶ "land the plane" ─▶ ┌───────────────────────────────────────┐
                              │  final gates · file loose work ·      │
                              │  policy/authority-aware handoff       │
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
(see [Upgrading](#upgrading)). Select the client explicitly for a new Codex
or dual-client install; omitting `--platform` on a brand-new install preserves
the original Claude-only default:

```sh
# Claude Code (the backward-compatible default)
curl -fsSL https://raw.githubusercontent.com/ebowman/domestique/main/domestique.sh | bash -s -- --with-beads

# Codex only
curl -fsSL https://raw.githubusercontent.com/ebowman/domestique/main/domestique.sh | bash -s -- --platform codex --with-beads

# Both clients in the same repo
curl -fsSL https://raw.githubusercontent.com/ebowman/domestique/main/domestique.sh | bash -s -- --platform both --with-beads
```

Or clone once and reuse across machines (recommended):

```sh
git clone https://github.com/ebowman/domestique.git ~/.local/share/domestique
ln -sf ~/.local/share/domestique/domestique.sh ~/.local/bin/domestique.sh
alias dom="$HOME/.local/bin/domestique.sh"          # add to ~/.zshrc or ~/.bashrc
alias dom-guest="$HOME/.local/bin/domestique.sh --guest"  # guest installs (see below)
# then, in any repo:
dom --platform codex --with-beads
```

The platform projections are deliberately separate:

- **Claude Code:** `CLAUDE.md` policy block,
  `.claude/agents/{implementer,reviewer}.md`, and
  `.claude/commands/{decompose,goal,drain}.md`.
- **Codex:** a policy block in an existing root `AGENTS.override.md`, or in
  `AGENTS.md` when no override exists; custom agents at
  `.codex/agents/{implementer,reviewer}.toml`; and namespaced repo skills at
  `.agents/skills/domestique*/`. The goal skill's `agents/openai.yaml`
  disables implicit invocation, so only an explicit `$domestique-goal`
  authorizes unattended work.

An explicit platform install adds that projection to domestique's persisted
platform set. Later runs without `--platform` update the recorded set rather
than guessing from installed binaries or arbitrary project files. A legacy
provider state tree with no platform record implies that provider. `--platform codex`
in a fresh repo creates no `.claude/` artifacts; use `--platform both` when
you intentionally want both clients.

**Installing locally, per project, makes the agents yours to extend.** Since
the config lands in your own repo rather than some shared global location,
you're free to customize it: add MCP tools to an agent's frontmatter, adjust
its prompt, or retune its `model:` pin. Re-running the installer to pick up
upstream changes preserves those local edits via the 3-way merge described
above — see [Upgrading](#upgrading) for the mechanics.

### 2. Set the orchestrator session's model

In Claude Code, Fable and Opus both work well as the orchestrator:

```
/model fable
```

(`/model opus` works too.) In Codex, select the main session model with its
normal model control. Subagents remain pinned independently in their TOML
files. Local edits to either platform's agent files survive upgrades through
the same three-way merge path.

### 3. Make sure beads is initialized in this repo

This assumes `bd` is already installed (see "About beads", above). If you
installed with `--with-beads`, `bd` was on your PATH, and it supports the
required safe flags, this repo-level initialization is already done. Otherwise
domestique warns and skips it. In normal mode, domestique initializes beads
without allowing `bd init` to install agent files or hooks, then runs the
recipe for each selected client. Equivalent manual setup is:

```sh
bd init --skip-agents --skip-hooks --non-interactive
bd setup claude   # Claude projection
bd setup codex    # Codex projection; run both recipes for --platform both
```

Guest mode is stricter: it uses
`bd init --stealth --skip-agents --skip-hooks --non-interactive` and
intentionally skips all provider setup recipes, because those recipes may
modify host instructions, hooks, or tracked files. If the installed `bd` does
not support the safe init flags, domestique skips initialization with a
warning instead of weakening guest isolation.

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

**What it guarantees.** Nothing domestique creates lands in the repo's
tracked history. Guest mode never edits `.gitignore`; it writes a managed
block in
`<git-common-dir>/info/exclude`, the local never-committed sibling of
`.gitignore`. Resolving the Git common directory makes the same guarantee in
a worktree. A fresh guest install in a previously clean repository, including
one using the safe `--with-beads` path, leaves `git status` clean.

The two clients achieve that isolation differently:

- **Claude guest:** the policy goes into `CLAUDE.local.md`; tracked
  `CLAUDE.md` is never read, changed, or backed up. Claude agents, commands,
  and state are excluded by the compatibility entries `CLAUDE.local.md` and
  `.claude/`; this legacy broad `.claude/` entry can also hide pre-existing
  untracked content below that directory. `.beads/` is excluded only when domestique
  created it through the safe guest initialization path.
- **Codex guest:** both `AGENTS.md` and `AGENTS.override.md` are always left
  byte-untouched. Codex has no additive local project-instruction file, and
  creating an override would shadow the host's `AGENTS.md`. Domestique
  therefore installs only the two custom agents and the namespaced skills,
  excluded at their exact paths, with provider state under
  `.codex/.domestique`. Start each new Codex session with `$domestique`.
  Operational skills are self-contained; the base skill can also match
  “dispatch next ready bead” and “land the plane.” This is functional guest
  support, not a claim that Codex automatically loads domestique policy at
  session startup.

Codex guest excludes are intentionally narrow: domestique does not hide an entire
pre-existing `.agents/` or `.codex/` tree, and it does not newly hide a path
that was already untracked before installation. It also does not add broad
`*.new` or backup-suffix patterns. A tracked collision cannot
be hidden by `info/exclude`; domestique reports it instead of claiming a
clean install. If the target is not a Git repository, the exclude step is
skipped with a warning and the remaining guest install can proceed.

Examples:

```sh
dom --guest                         # Claude guest (legacy default)
dom --guest --platform codex        # Codex skills-only guest
dom --guest --platform both         # both local projections
dom --guest --platform codex --with-beads
```

**Sticky mode and platform selection.** Guest mode is recorded separately in
each installed provider's state (`.claude/.domestique` and/or
`.codex/.domestique`). Re-running without `--guest` or `--no-guest` respects
that state, as does `update.sh`. The persisted platform set likewise makes a
selector-less rerun update the already installed provider set. Pass
`--no-guest` to convert deliberately; Claude prints guidance for folding any
`CLAUDE.local.md` customization into `CLAUDE.md`, while Codex begins managing
the active root AGENTS file. Nothing is auto-migrated. Passing `--guest` and
`--no-guest` together remains a usage error.

## Unattended epic mode

Claude uses `/decompose` and `/goal <epic-id>`; Codex uses
`$domestique-decompose` and `$domestique-goal <epic-id>`. The goal workflow
drains one beads epic to
completion by repeatedly running the implementer → reviewer loop **without
stopping between beads**. The platform's explicit goal invocation is the
only thing that lifts the default check-in-between-beads rule (see
[The loop](#the-loop), above), and only within strict bounds. The Codex goal
skill cannot be invoked implicitly. On Claude, `/drain <epic-id>` is an
alias of `/goal <epic-id>` — identical semantics, since "draining an epic"
is the term this section already uses.

**Authorization is scoped and temporary.** A goal invocation is
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
# Claude Code
/decompose Add rate limiting to the public API
/goal <epic-id>        # or: /drain <epic-id>

# Codex
$domestique-decompose Add rate limiting to the public API
$domestique-goal <epic-id>
```

When goal execution stops — completion, ceiling, or a stop condition — review the
epic branch's diffs and commit history, then merge the epic branch into main
by hand, or explicitly ask your coding client to do it.

## Safety & idempotency

- **Your project instructions survive.** In normal mode, everything outside
  the managed block in `CLAUDE.md`, `AGENTS.md`, or `AGENTS.override.md` is
  preserved byte-for-byte. Codex guest mode never touches either AGENTS file.
- **Backups.** Policy files are backed up before modification, including
  under `--force`; plain managed files follow the documented merge/force
  rules.
- **Run it twice** and the second run makes no changes (and creates no new
  backup).
- **`--dry-run`** computes and prints the full plan while touching nothing.

## Installer usage

```
domestique.sh [TARGET_DIR] [options]

Options:
  --platform P   Select claude, codex, or both. A new selector-less install
                 defaults to claude; later selector-less runs use persisted
                 selection.
  --dry-run      Print planned changes; touch nothing.
  --with-beads   Initialize beads with agent/hook writes disabled. Normal
                 mode then runs setup recipes for selected providers; guest
                 mode skips provider setup to preserve isolation.
  --force        Overwrite differing managed plain files instead of merging;
                 policy files are still backed up before modification.
  --guest        Install local-only state for a repo you don't own. Claude
                 uses CLAUDE.local.md; Codex uses skills only and leaves both
                 AGENTS files untouched.
  --no-guest     Convert an existing guest install back to normal. Mutually
                 exclusive with --guest.
  --uninstall    Remove everything domestique installed (see "Uninstalling",
                 below). Add --platform for a scoped uninstall; omit it to
                 scan all managed providers.
  --purge-beads  Only valid with --uninstall: also remove TARGET_DIR/.beads.
  --help, -h     Show this help.
```

Run `domestique.sh --help` for the full option reference, including exact
behavior notes for each flag.

The installer is a single self-contained Bash script with every Claude and
Codex template embedded — no network access is needed beyond fetching the
script itself.

## Uninstalling

```sh
dom --uninstall path/to/repo            # remove all managed providers
dom --uninstall --platform codex path/to/repo  # remove only Codex
dom --uninstall --dry-run path/to/repo  # preview only
dom --uninstall --purge-beads path/to/repo   # also remove .beads/
```

(`dom` is the alias from [Setup](#1-install-or-upgrade-the-config-in-your-repo),
above; substitute your own `domestique.sh` invocation and TARGET_DIR as
needed — TARGET_DIR defaults to the current directory.)

`--uninstall` removes exactly what domestique installed, and nothing else.
Without `--platform`, it scans both provider inventories. With a platform it
removes only that projection, updates the persisted platform set, and
regenerates the shared guest-exclude union for anything still installed.
Claude ownership covers its five `.claude/` files and policy destinations;
Codex ownership covers the two `.codex/agents` files, three namespaced
`SKILL.md` leaves plus goal metadata, and any managed normal-mode AGENTS block.
Provider state is removed only for the selected projection. `.beads/` is
never removed unless you pass `--purge-beads`.

Parent directories such as `.claude/agents`, `.codex/agents`, and
`.agents/skills` are pruned only when empty. A Codex uninstall never removes
an entire user-owned `.codex/` or `.agents/` tree.

**Safety-compared, not blindly deleted.** Each managed Claude or Codex plain
file is compared against its provider's recorded base snapshot (or the
pristine emitted content if no snapshot exists) before removal. Domestique
first requires ownership evidence: that provider's state tree or a managed
policy marker. A fixed inventory pathname alone is never enough. Untouched files are deleted
outright; files you've hand-edited are kept, renamed to
`<file>.uninstalled.<timestamp>`, unless you pass `--force`. This removal
applies only to paths domestique created; an adopted, pre-existing Codex file
is left at its original path. For policy files, a managed block that was never modified is
stripped with no backup (the file is deleted outright if stripping it leaves
nothing behind); a modified block is backed up to `<file>.bak.<timestamp>`
first.

**Marker-sanity refusals.** If a Claude or Codex policy file's managed-block markers are
duplicated, mismatched, or in the wrong order, `--uninstall` refuses to touch
that file — it's reported under `Conflicted`, the run exits `3`, and the file
is left byte-untouched. Other files still get uninstalled normally; only the
corrupt one is skipped.

**The round-trip guarantee.** For the common case — a `--guest` install into
an otherwise-clean repo, with nothing touched by hand afterward, followed
immediately by `--uninstall` — every installed file is deleted outright, the
exclude block is fully stripped back out, and the repo returns to
byte-for-byte clean `git status`, for Claude, Codex, or both. Safe guest
`--with-beads` never runs provider setup recipes, but `.beads/` is deliberately
preserved on uninstall and becomes visible again unless `--purge-beads` is
also passed. If you modified an installed file first,
that file is deliberately preserved instead of deleted (renamed to
`<file>.uninstalled.<timestamp>`), so it will show up as untracked in
`git status` afterward — this is by design (see "Safety-compared, not
blindly deleted", above), not a broken round trip. Real output from a
Claude `--guest` install immediately followed by `--uninstall` in a fresh
scratch repo (Codex reports its own agent, skill, and state paths instead):

```
$ domestique.sh --guest .
domestique: installing into . (platforms=claude)
domestique: platform=claude mode=guest policy=CLAUDE.local.md

Summary:
  Created:
    - ./CLAUDE.local.md
    - ./.claude/agents/implementer.md
    - ./.claude/agents/reviewer.md
    - ./.claude/commands/decompose.md
    - ./.claude/commands/goal.md
    - ./.claude/commands/drain.md
  Updated:
    - ./.git/info/exclude (managed block)
Done.

$ git status
On branch main
nothing to commit, working tree clean

$ domestique.sh --uninstall .
domestique: uninstalling from . (platform=all)

Summary (uninstall):
  Removed:
    - ./.claude/agents/implementer.md
    - ./.claude/agents/reviewer.md
    - ./.claude/commands/decompose.md
    - ./.claude/commands/goal.md
    - ./.claude/commands/drain.md
    - ./CLAUDE.local.md
    - ./.git/info/exclude (managed block)
    - ./.claude/.domestique
Done.

$ git status
On branch main
nothing to commit, working tree clean
```

and `.claude/` no longer exists at all. A scoped Codex uninstall leaves the
Claude projection and its exclusion entries intact, and vice versa.

## Upgrading

Re-running the installer 3-way-merges your local edits against upstream
changes instead of overwriting them.

**How it works.** Every install/upgrade records a provider-specific base
snapshot: `.claude/.domestique/` for Claude and `.codex/.domestique/` for
Codex. Each holds pristine copies of what was last installed, managed policy
block bodies, the persisted platform set, and a manifest of the provider's
actual owned inventory. The next time you run the installer, it does a
**3-way merge** (`git merge-file`) between your current file (yours), that
snapshot (base), and the newly emitted content (upstream).
If your edits and upstream's changes don't overlap, the merge is clean: your
edits and the new upstream content are both applied, and the snapshot
advances so the next upgrade merges from here.

**On conflict.** If the same lines changed on both sides, the merge can't
reconcile them automatically. In that case domestique:
- leaves your live file (e.g. `implementer.md`, or `CLAUDE.md`) **untouched**,
- writes the merge result, conflict markers and all, to `<file>.new` (for
  `CLAUDE.md` this is `CLAUDE.md.new`; an AGENTS policy conflict follows the
  same naming rule),
- backs up your current file to `<file>.bak.<timestamp>`,
- and exits **3** so scripts/CI notice.

To resolve: open `<file>.new`, reconcile the conflict blocks by hand, copy
the result over the live file, then delete the `.new`. Re-run the installer
once you're done to refresh the snapshot. The conflicts use `diff3` style,
so each block has four parts — `<<<<<<<` your version, `|||||||` the
original base, `=======`, and `>>>>>>>` the incoming upstream version;
delete the markers and the sections you don't want.

**Policy-file specifics.** Only the managed block (between the
`<!-- BEGIN domestique (managed) -->` / `<!-- END domestique -->` markers) is
ever merged or replaced. This applies to `CLAUDE.md`, `CLAUDE.local.md`, and
the active normal-mode `AGENTS.md` or `AGENTS.override.md`. Everything outside
the markers is preserved byte-for-byte. Codex guest mode is the exception by
design: it never reads or writes either root AGENTS file.

**`--force` and `--dry-run`.** `--force` skips the merge entirely and takes
upstream verbatim, discarding local edits to that file (policy files are still
backed up first). `--dry-run` computes and prints the full plan —
including what a merge or conflict would do — without writing anything.

**First upgrade of a legacy install.** The 3-way merge needs a base snapshot
to diff against. If a managed file or policy block predates the snapshot
feature (no provider-state base entry for it
yet) and differs from what domestique would emit, that first upgrade
**adopts** it instead of overwriting it: domestique seeds the base snapshot
from the pristine emitted content and leaves your live file **untouched** —
no `.bak` is written, because nothing was changed. It reports the file under
an "Adopted" heading as *"local edits preserved; re-run to merge upstream"*.
This is default behavior, not a flag — there's nothing to opt into.

That means an existing, customized install (say, an `implementer.md`, Codex
agent TOML, or skill with local changes) is brought under management on the very next
`domestique.sh` run without losing anything: nothing merges and nothing is
overwritten on the adoption run itself. Run the installer again afterward
and upstream changes merge normally against the newly-seeded base — your
edits are kept, upstream's changes are applied, and if the same lines
changed on both sides you get an ordinary conflict: `<file>.new` written,
`.bak` taken, the live file left untouched, and exit `3`, exactly as
described above. Adoption never silently loses local edits, and it never
silently drops upstream changes either — a conflict is always surfaced,
never swallowed.

`.claude/.domestique/` and `.codex/.domestique/` are domestique's own
provider bookkeeping. Normal installs may track them as part of the project;
guest installs exclude only the relevant provider state locally.

## Updating from GitHub

`update.sh` is a thin wrapper that fetches the latest `domestique.sh` and
runs it through the same merge path above:

```sh
./update.sh                       # update current directory
./update.sh path/to/repo          # update a specific target
./update.sh --dry-run             # preview only, applies nothing
./update.sh --force               # discard local edits, take upstream verbatim
./update.sh --platform codex      # explicitly update/add the Codex projection
./update.sh --platform both       # update/add both projections
./update.sh --source ./domestique.sh   # use a local file instead of GitHub
```

The source defaults to the `main` branch on GitHub and can be overridden with
`--source <path|url>` or the `DOMESTIQUE_UPDATE_SOURCE` env var. It's safe to
run on a schedule (e.g. cron or a periodic CI job): `update.sh` forwards an
explicit `--platform`, while a selector-less update relies on the target's
persisted platform set (a provider state tree without a platform marker
implies that provider). It always previews with
`--dry-run` first, then applies, and exits:
- `0` — applied cleanly, or already up to date.
- `3` — one or more files hit a merge conflict; check the `.new`/`.bak`
  files and resolve by hand as described above.
- `4` — couldn't fetch or validate the source `domestique.sh`; nothing was
  touched.

## Testing the installer itself

The self-contained suites cover install/upgrade merges, guest mode, Codex,
mixed-platform state, Beads routing, and uninstall. They require only a shell
and `git` (plus any suite-specific fake command fixtures):

```sh
bash test/upgrade.sh     # 12 scenarios: fresh install, merges, conflicts, adopt
bash test/guest.sh       # 14 scenarios: --guest, sticky mode, --no-guest, worktrees
bash test/uninstall.sh   # 23 scenarios: --uninstall, --purge-beads, round-trip, marker refusals
bash test/codex.sh       # 16 scenarios: Codex, platforms, guest, Beads, updater, uninstall
```

## License

MIT — see [LICENSE](LICENSE).
