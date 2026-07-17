#!/usr/bin/env bash
# domestique.sh — install the Claude Code orchestration config into a repo.
# Embeds CLAUDE.md orchestration policy + .claude/agents/implementer.md +
# .claude/commands/decompose.md, and installs them idempotently.
set -euo pipefail

MARKER_BEGIN='<!-- BEGIN domestique (managed) -->'
MARKER_END='<!-- END domestique -->'

# ---------------------------------------------------------------------------
# Embedded source of truth (verbatim; edit here, nowhere else).
# ---------------------------------------------------------------------------
emit_policy() { cat <<'DOM_EOF'
# Orchestration policy

This session is the **orchestrator**. Your job is planning, delegation, and review — not implementation.

## Roles
- **You (main session, planning model):** decompose work, hold the plan, delegate implementation and review, adjudicate the results, decide what's next. Write code yourself only for trivial one-line edits.
- **`implementer` subagent (Sonnet):** executes one bounded task at a time in its own context and reports back a summary.
- **`reviewer` subagent (Opus):** independently verifies a completed task in a fresh context — inspects the real diff, reads the changed files, runs the tests — and reports a pass/fail verdict against the bead's done-criteria. A stronger, non-peer check than the implementer. Does not fix anything; reviewing is its only job.

## Work tracking: beads
- The plan of record lives in beads (`bd`), not in markdown TODO lists.
- Decompose a goal into an epic + bounded tasks with dependencies using `/decompose`.
- Select the next unit of work with `bd ready` — it returns only unblocked, actionable tasks.
- Record durable insight with `bd remember "<insight>"`. Do not create MEMORY.md files.

## Writing briefs
Plans, bead descriptions, and delegation briefs are executed by a separate model with no access to your reasoning. When you write them:
- Write numbered steps; each step names an action, a target file/symbol, and an acceptance criterion.
- Spell out edge cases and error handling — do not leave them implicit.
- Flag ambiguities explicitly rather than resolving them silently.

## Delegation loop
1. `bd ready` → pick the highest-priority unblocked task.
2. Delegate it to the `implementer` subagent with a precise brief and the bead id.
3. When the implementer returns, delegate verification to the `reviewer` subagent with the same bead id and its done-criteria. The reviewer inspects the real diff, reads the changed files, and runs the tests in a fresh context — judging the work against the done-criteria, not against the implementer's summary — and returns a pass/fail verdict.
4. Adjudicate. Weigh the reviewer's verdict against the implementer's summary: if they agree the work is done, close the bead and commit its changes (one commit, bead id in the message); if the reviewer reports gaps, reopen the bead or file a follow-up and route the fix back to the implementer. Read the diff yourself only when the two reports conflict or the verdict is ambiguous — delegating the review is the point.
5. **Stop and report to the human before dispatching the next task.** Do not drain the queue unattended unless explicitly told to.

## Unattended epic mode (/goal)
- The default remains **stop-and-report between beads** (rule 5 of the Delegation loop above). Nothing changes that by itself.
- A `/goal <epic-id>` invocation is the **only** thing that authorizes continuous, unattended dispatch across an epic's beads. That authorization is scoped to the named epic, expires the instant the epic completes or any stop condition fires, and never carries over to another epic or a later session.
- Unattended runs happen on a **dedicated epic branch** and never commit to the default branch — the human reviews and merges that branch by hand; the loop never merges or pushes.
- The core invariants still hold even while unattended: **one bead in flight at a time, one commit per bead, and never close a bead the reviewer didn't pass.**
- For the full loop mechanics and the complete list of stop conditions, see `.claude/commands/goal.md` — they are not restated here.

## Discipline
- One task in flight at a time. Bounded WIP.
- Subagents return summaries, never full file dumps. Your context is the constraint — keep it lean, don't re-read large outputs.
- Do not spawn agent teams for this sequential pipeline. Subagents only.
- At session end ("land the plane"): file any loose discovered work as beads, then sync (`bd sync --flush-only` and commit `.beads/`).
DOM_EOF
}

emit_implementer() { cat <<'DOM_EOF'
---
name: implementer
description: Executes a single well-scoped, bounded coding task and reports back a terse summary. Use proactively for any discrete implementation step handed down by the orchestrator — one bead / one task at a time.
tools: Read, Write, Edit, Bash, Glob, Grep
model: sonnet
---

You are an implementer. You receive one bounded task and complete exactly that task — nothing more.

## Operating rules
- Do the assigned task only. Do not expand scope, refactor adjacent code, or start the next task.
- If you were given a bead id, claim it and mark it in progress before starting; do NOT close it — the orchestrator closes beads after independent review:
  - `bd update <id> --claim`   (or `bd update <id> --status in_progress`)
- Run the project's tests and linter after meaningful changes. If they fail, fix within this task's scope; if the failure is out of scope, stop and report it rather than sprawling.
- Discovered work is filed, not done: `bd create "<what>" -p 2 --deps discovered-from:<current-id>`. Do not chase it yourself.
- Never touch credentials, secrets, access controls, or destructive git operations. Surface these to the orchestrator instead.
- Implement the brief exactly as written; do not substitute your own interpretation.
- If anything is ambiguous or not covered by the brief, stop and report the question in your summary — do not improvise.

## What you return
A terse summary only — never full file contents:
- What changed (files touched, one line each)
- Test / lint result
- Any beads you filed as discovered work
- Blockers or decisions the orchestrator should know about

Keep the return small. The orchestrator's context is the scheduling constraint; do not flood it.
DOM_EOF
}

emit_reviewer() { cat <<'DOM_EOF'
---
name: reviewer
description: Independently verifies one completed task against its bead's done-criteria in a fresh context — inspects the real diff, reads the changed files, runs the tests — and returns a pass/fail verdict with specific findings. Use after the implementer reports a task done, before the orchestrator closes the bead.
tools: Read, Bash, Glob, Grep
model: opus
---

You are a reviewer. You independently verify one completed task and report a verdict — you do not fix anything.

## Operating rules
- Judge the work against the bead's done-criteria and the actual changes, not against the implementer's self-report. Assume the summary may be wrong or incomplete; check it against reality.
- Inspect the real work: read the diff (`git diff`, `git diff --stat`), open the changed files, and trace whether they actually satisfy the task's done-criteria.
- Run the project's tests and linter yourself. Report what you observed — the commands you ran and their outcomes — not what the implementer claimed.
- Do not edit code, refactor, or fix problems you find. Do not close or reopen beads. Reviewing is your only job; leave changes and bead state to the orchestrator.
- Stay in scope: review this task only. Note adjacent problems in one line, but don't chase them.
- Never touch credentials, secrets, or destructive git operations.

## What you return
A terse verdict only — never full file contents:
- **Verdict:** PASS, FAIL, or NEEDS-WORK (partial).
- Test / lint result you actually ran (command + outcome).
- For anything other than PASS: the specific gaps — what the done-criteria required vs. what the diff does, each in one line.
- Any risks or follow-ups the orchestrator should weigh.

Keep it small. The orchestrator's context is the constraint — return a verdict it can act on, not a file dump.
DOM_EOF
}

emit_decompose() { cat <<'DOM_EOF'
---
description: Decompose a goal or spec into a beads epic with bounded, dependency-ordered tasks.
argument-hint: <goal, or path to a spec file>
---

Decompose the following into a beads work graph: $ARGUMENTS

Rules for a good decomposition:
- Create one epic for the goal:
  `bd create "<goal>" -t epic -p 1 --description "<why + high-level design>"`
- Break it into **bounded tasks** — each completable by a fresh Sonnet session in a single pass. A task has one clear deliverable and a testable done-criterion. If it needs more than that, split it.
  `bd create "<task>" -t task -p <2-3> --parent <epic-id> --description "<input, output, done-criteria>"`
- Wire real dependencies so `bd ready` only ever surfaces work that can actually start:
  `bd dep add <blocked-id> <blocker-id>`   # blocked depends on blocker
- Keep `bd ready` crisp. No vague someday-items, no research-maybe tasks, nothing not immediately actionable. If it isn't ready to be worked, it doesn't belong in the graph yet.
- Do not implement anything. Planning only.

When done, print the resulting graph (`bd ready` plus the epic tree) for my review before any execution.
DOM_EOF
}

emit_goal() { cat <<'DOM_EOF'
---
description: Drain a beads epic to completion unattended — dedicated branch, one bead per commit, reviewer-gated, bounded loop.
argument-hint: <epic-id>
---

Drive epic $ARGUMENTS to completion, unattended, within the bounds below. This invocation is your explicit authorization to skip the normal "stop and report before dispatching the next task" rule from CLAUDE.md — but that authorization is scoped and time-limited: it covers only beads under epic $ARGUMENTS, and it expires the instant the epic completes or any stop condition below fires. It never carries to another epic or a later session.

## Branch isolation (load-bearing)
Before touching anything, create or switch to a dedicated branch for this epic (e.g. derived from `$ARGUMENTS`, such as `epic/$ARGUMENTS`). Never commit to the default branch for the rest of this run. The human reviews and merges this branch by hand — you never merge or push it.

## Per-cycle loop
For each cycle:
1. `bd ready` scoped to epic $ARGUMENTS — pick the highest-priority unblocked task. If none, the epic is done; go to Completion below.
2. Assert a clean working tree before starting the bead. If it's dirty, stop and report — do not paper over it.
3. Claim it and mark in_progress (`bd update <id> --claim`).
4. Dispatch to the `implementer` subagent with a precise brief built from the bead's description, input/output, and done-criteria.
5. Dispatch to the `reviewer` subagent with the same bead id and its done-criteria. The reviewer must run the full test suite and inspect the real diff every time — never trust the implementer's summary in place of that.
6. Adjudicate:
   - Reviewer PASS → `git add -A` and commit, message including the bead id, one bead per commit (never batch). Then `bd close <id>`.
   - Reviewer reports gaps → route at most one fix pass back to the implementer, then re-review. A second failed review on the same bead is a stop condition (see below) — do not loop further on it.

## Hard ceiling
Stop and report after 15 beads closed in this run (or sooner if you judge the budget exhausted), even if the epic isn't finished. This is a runaway-loop backstop, not a target.

## Stop conditions — halt immediately, do not dispatch further work, and report to the human
- A bead fails review twice: leave it `in_progress` with notes on what's wrong; do not force a third pass.
- Any full-suite regression: stop immediately, do not attempt to attribute the cause yourself.
- A decision needs operator input: spec ambiguity, scope change, or UX/semantics not already settled by the bead's description.
- Anything requires a push, a config change, or touching files outside the project.
- Two consecutive infrastructure/API errors: before concluding it's an API outage, check `bd memories` for machine-sleep or known-flake notes.

## On epic completion (or hitting the ceiling)
Run the full test suite once more. Summarize: beads closed, commits made (with ids), any follow-ups filed as beads, and residual risks that need human hands-on attention. Land the plane per the session-close protocol — file loose discovered work as beads, `bd sync --flush-only`, commit `.beads/`. Anything requiring push or merge authority is reported as a PROPOSED command for the human to run, never executed by you.

## Invariants — restate these to yourself at the end of the report
- One bead in flight at a time.
- One commit per bead, never batched.
- Never close a bead the reviewer didn't pass.
- Never touch the default branch.
DOM_EOF
}

# ---------------------------------------------------------------------------
usage() {
  cat <<'EOF'
Usage: domestique.sh [TARGET_DIR] [options]

Installs the domestique Claude Code orchestration config into TARGET_DIR
(default: current directory):
  CLAUDE.md                        orchestration policy (in a managed block)
  .claude/agents/implementer.md    implementer subagent
  .claude/agents/reviewer.md       reviewer subagent
  .claude/commands/decompose.md    /decompose command
  .claude/commands/goal.md         /goal command

Options:
  --dry-run      Print planned changes; touch nothing.
  --with-beads   If `bd` is on PATH: `bd init` (only when no .beads/) then
                 `bd setup claude`. If `bd` is absent, note it and skip.
  --force        Overwrite differing .claude/ files without a .bak backup.
                 (CLAUDE.md is ALWAYS backed up before modification.)
  --help, -h     Show this help.

Behavior:
  * Existing .claude/ files that differ are backed up to <file>.bak.<timestamp>
    before overwriting (unless --force). Identical files are left untouched.
  * CLAUDE.md: created if absent; if it has the managed markers only the
    content between them is replaced; otherwise the block is appended and all
    existing content is preserved verbatim. Always backed up before change.
  * Running twice in a row makes no changes on the second run.
EOF
}

TARGET_DIR=""
DRY_RUN=0
WITH_BEADS=0
FORCE=0

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run)    DRY_RUN=1 ;;
    --with-beads) WITH_BEADS=1 ;;
    --force)      FORCE=1 ;;
    -h|--help)    usage; exit 0 ;;
    --) shift; break ;;
    -*) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    *)
      if [ -z "$TARGET_DIR" ]; then TARGET_DIR="$1"
      else echo "Unexpected argument: $1" >&2; exit 2; fi
      ;;
  esac
  shift
done
TARGET_DIR="${TARGET_DIR:-.}"

if [ ! -d "$TARGET_DIR" ]; then
  echo "Target directory does not exist: $TARGET_DIR" >&2
  exit 1
fi

TS="$(date +%Y%m%d%H%M%S)"
TMPDIR_WORK="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_WORK"' EXIT

# Summary accumulators.
SUM_CREATED=()
SUM_UPDATED=()
SUM_BACKEDUP=()
SUM_SKIPPED=()

note_dry() { [ "$DRY_RUN" -eq 1 ] && echo "  [dry-run] $*"; return 0; }

# install_plain <dest> <emitter-fn>
# Missing -> write. Differs -> (backup unless --force) then overwrite.
# Identical -> skip.
install_plain() {
  local dest="$1" emitter="$2" staged
  staged="$TMPDIR_WORK/staged"
  "$emitter" > "$staged"

  if [ ! -e "$dest" ]; then
    if [ "$DRY_RUN" -eq 1 ]; then
      note_dry "create $dest"
    else
      mkdir -p "$(dirname "$dest")"
      cp "$staged" "$dest"
    fi
    SUM_CREATED+=("$dest")
    return 0
  fi

  if cmp -s "$staged" "$dest"; then
    SUM_SKIPPED+=("$dest (identical)")
    return 0
  fi

  # Differs.
  if [ "$FORCE" -eq 1 ]; then
    if [ "$DRY_RUN" -eq 1 ]; then
      note_dry "overwrite $dest (--force, no backup)"
    else
      cp "$staged" "$dest"
    fi
    SUM_UPDATED+=("$dest (forced)")
  else
    local backup="$dest.bak.$TS"
    if [ "$DRY_RUN" -eq 1 ]; then
      note_dry "backup $dest -> $backup, then overwrite"
    else
      cp "$dest" "$backup"
      cp "$staged" "$dest"
    fi
    SUM_BACKEDUP+=("$backup")
    SUM_UPDATED+=("$dest")
  fi
}

# install_claude_md <dest>
install_claude_md() {
  local dest="$1"
  local blk="$TMPDIR_WORK/block" result="$TMPDIR_WORK/claude_result"

  # Build the managed block: BEGIN marker + verbatim policy + END marker.
  {
    printf '%s\n' "$MARKER_BEGIN"
    emit_policy
    printf '%s\n' "$MARKER_END"
  } > "$blk"

  # Case A: no CLAUDE.md -> create it as just the managed block.
  if [ ! -e "$dest" ]; then
    if [ "$DRY_RUN" -eq 1 ]; then
      note_dry "create $dest (managed block only)"
    else
      cp "$blk" "$dest"
    fi
    SUM_CREATED+=("$dest")
    return 0
  fi

  # Refuse to guess on a half-marked file (BEGIN but no END): swallowing
  # everything after BEGIN would be data loss. Leave it untouched and bail.
  if grep -qF "$MARKER_BEGIN" "$dest" && ! grep -qF "$MARKER_END" "$dest"; then
    echo "Error: $dest has a '$MARKER_BEGIN' marker but no matching '$MARKER_END'." >&2
    echo "       Refusing to edit a half-marked file. Fix it by hand and re-run." >&2
    exit 1
  fi

  # Case B: has both markers -> replace only the region between them, verbatim rest.
  if grep -qF "$MARKER_BEGIN" "$dest"; then
    awk -v beginm="$MARKER_BEGIN" -v endm="$MARKER_END" -v blockfile="$blk" '
      BEGIN { while ((getline line < blockfile) > 0) block = block line ORS }
      $0 == beginm && !seen { seen=1; inblock=1; printf "%s", block; next }
      inblock && $0 == endm { inblock=0; next }
      inblock { next }
      { print }
    ' "$dest" > "$result"
  else
    # Case C: no markers -> append the block, preserving existing bytes verbatim.
    # Add a single newline first only if the file does not already end in one,
    # so the BEGIN marker starts on its own line.
    cp "$dest" "$result"
    if [ -s "$result" ] && [ "$(tail -c 1 "$result" | wc -l)" -eq 0 ]; then
      printf '\n' >> "$result"
    fi
    cat "$blk" >> "$result"
  fi

  # Idempotency guard: if nothing would change, skip (no backup, no write).
  if cmp -s "$result" "$dest"; then
    SUM_SKIPPED+=("$dest (managed block already current)")
    return 0
  fi

  local backup="$dest.bak.$TS"
  if [ "$DRY_RUN" -eq 1 ]; then
    note_dry "backup $dest -> $backup, then update managed block"
  else
    cp "$dest" "$backup"        # CLAUDE.md is ALWAYS backed up before change.
    cp "$result" "$dest"
  fi
  SUM_BACKEDUP+=("$backup")
  SUM_UPDATED+=("$dest (managed block)")
}

# ---------------------------------------------------------------------------
echo "domestique: installing into $TARGET_DIR"
[ "$DRY_RUN" -eq 1 ] && echo "(dry run — no files will be modified)"

install_claude_md "$TARGET_DIR/CLAUDE.md"
install_plain     "$TARGET_DIR/.claude/agents/implementer.md"   emit_implementer
install_plain     "$TARGET_DIR/.claude/agents/reviewer.md"      emit_reviewer
install_plain     "$TARGET_DIR/.claude/commands/decompose.md"   emit_decompose
install_plain     "$TARGET_DIR/.claude/commands/goal.md"        emit_goal

# --- beads (opt-in) --------------------------------------------------------
if [ "$WITH_BEADS" -eq 1 ]; then
  if command -v bd >/dev/null 2>&1; then
    if [ -d "$TARGET_DIR/.beads" ]; then
      SUM_SKIPPED+=("bd init (.beads/ already present)")
    else
      if [ "$DRY_RUN" -eq 1 ]; then
        note_dry "run: bd init (in $TARGET_DIR)"
      else
        ( cd "$TARGET_DIR" && bd init )
      fi
      SUM_CREATED+=(".beads/ (bd init)")
    fi
    if [ "$DRY_RUN" -eq 1 ]; then
      note_dry "run: bd setup claude (in $TARGET_DIR)"
    else
      ( cd "$TARGET_DIR" && bd setup claude )
    fi
    SUM_UPDATED+=("bd setup claude")
  else
    SUM_SKIPPED+=("beads: 'bd' not found on PATH — skipped (install not required)")
  fi
fi

# --- summary ---------------------------------------------------------------
echo
if [ "$DRY_RUN" -eq 1 ]; then echo "Summary (planned):"; else echo "Summary:"; fi
print_group() {
  local label="$1"; shift
  [ "$#" -eq 0 ] && return 0
  echo "  $label:"
  local item
  for item in "$@"; do echo "    - $item"; done
}
[ "${#SUM_CREATED[@]}"  -gt 0 ] && print_group "Created"   "${SUM_CREATED[@]}"
[ "${#SUM_UPDATED[@]}"  -gt 0 ] && print_group "Updated"   "${SUM_UPDATED[@]}"
[ "${#SUM_BACKEDUP[@]}" -gt 0 ] && print_group "Backed up" "${SUM_BACKEDUP[@]}"
[ "${#SUM_SKIPPED[@]}"  -gt 0 ] && print_group "Skipped"   "${SUM_SKIPPED[@]}"
[ "$DRY_RUN" -eq 1 ] && echo "  (dry run: nothing was actually changed)"
echo "Done."
