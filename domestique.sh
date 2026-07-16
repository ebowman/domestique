#!/usr/bin/env bash
# domestique.sh — install the Claude Code orchestration config into a repo.
# Embeds CLAUDE.md orchestration policy + .claude/agents/implementer.md +
# .claude/commands/decompose.md, and installs them idempotently.
set -euo pipefail

DOMESTIQUE_VERSION="0.1.0"

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

## Delegation loop
1. `bd ready` → pick the highest-priority unblocked task.
2. Delegate it to the `implementer` subagent with a precise brief and the bead id.
3. When the implementer returns, delegate verification to the `reviewer` subagent with the same bead id and its done-criteria. The reviewer inspects the real diff, reads the changed files, and runs the tests in a fresh context — judging the work against the done-criteria, not against the implementer's summary — and returns a pass/fail verdict.
4. Adjudicate. Weigh the reviewer's verdict against the implementer's summary: if they agree the work is done, close the bead; if the reviewer reports gaps, reopen the bead or file a follow-up and route the fix back to the implementer. Read the diff yourself only when the two reports conflict or the verdict is ambiguous — delegating the review is the point.
5. **Stop and report to the human before dispatching the next task.** Do not drain the queue unattended unless explicitly told to.

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
- If you were given a bead id, claim it before starting and close it when done:
  - `bd update <id> --claim`   (or `bd update <id> --status in_progress`)
  - `bd close <id>`            on success
- Run the project's tests and linter after meaningful changes. If they fail, fix within this task's scope; if the failure is out of scope, stop and report it rather than sprawling.
- Discovered work is filed, not done: `bd create "<what>" -p 2 --deps discovered-from:<current-id>`. Do not chase it yourself.
- Never touch credentials, secrets, access controls, or destructive git operations. Surface these to the orchestrator instead.

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
SUM_MERGED=()
SUM_CONFLICT=()

# Set to 1 if any file ended in a merge conflict or hard merge error this run;
# drives the final non-zero exit (see docs/install-upgrade-design.md §4).
CONFLICT_OCCURRED=0

note_dry() { [ "$DRY_RUN" -eq 1 ] && echo "  [dry-run] $*"; return 0; }

# ---------------------------------------------------------------------------
# Base snapshot / manifest (foundation for a future 3-way merge on upgrade;
# this run only records the snapshot of what was just emitted — it does not
# read or merge against a prior snapshot). See docs/install-upgrade-design.md.
# ---------------------------------------------------------------------------
SNAPSHOT_DIR="$TARGET_DIR/.claude/.domestique"
SNAPSHOT_BASE="$SNAPSHOT_DIR/base"
MANAGED_FILES=".claude/agents/implementer.md,.claude/agents/reviewer.md,.claude/commands/decompose.md,CLAUDE.md"
SNAPSHOT_TOUCHED=0

# rel_to_base <dest> -> absolute path under SNAPSHOT_BASE mirroring <dest>'s
# path relative to TARGET_DIR, 1:1 (including the .claude/ prefix — no
# managed file lives under .claude/.domestique/, so this never recurses).
rel_to_base() {
  local dest="$1"
  printf '%s' "$SNAPSHOT_BASE/${dest#"$TARGET_DIR"/}"
}

# snapshot_plain <dest> <content-file>
# Record the pristine emitted content as the future merge base. Call only
# after <dest> was actually created/overwritten with <content-file>'s bytes
# (never on an identical-skip — the snapshot is already correct there).
snapshot_plain() {
  local dest="$1" content="$2" basepath
  basepath="$(rel_to_base "$dest")"
  SNAPSHOT_TOUCHED=1
  if [ "$DRY_RUN" -eq 1 ]; then
    note_dry "snapshot base -> $basepath"
    return 0
  fi
  mkdir -p "$(dirname "$basepath")"
  cp "$content" "$basepath"
}

# snapshot_claude_block <content-file>
# Record the managed block BODY (no marker lines) as the future merge base
# for CLAUDE.md. Call only after CLAUDE.md was actually created/updated.
snapshot_claude_block() {
  local content="$1" basepath="$SNAPSHOT_BASE/CLAUDE.md.block"
  SNAPSHOT_TOUCHED=1
  if [ "$DRY_RUN" -eq 1 ]; then
    note_dry "snapshot base -> $basepath"
    return 0
  fi
  mkdir -p "$(dirname "$basepath")"
  cp "$content" "$basepath"
}

# write_manifest — flat key=value manifest describing the snapshot.
write_manifest() {
  local manifest="$SNAPSHOT_DIR/manifest" ref sha
  ref="$(git -C "$(dirname "$0")" rev-parse --short HEAD 2>/dev/null)" || ref="unknown"
  [ -z "$ref" ] && ref="unknown"
  if command -v sha256sum >/dev/null 2>&1; then
    sha="$(sha256sum "$0" 2>/dev/null | awk '{print $1}')" || sha=""
  elif command -v shasum >/dev/null 2>&1; then
    sha="$(shasum -a 256 "$0" 2>/dev/null | awk '{print $1}')" || sha=""
  else
    sha=""
  fi
  [ -z "$sha" ] && sha="unavailable"
  {
    printf 'snapshot_format=1\n'
    printf 'domestique_version=%s\n' "$DOMESTIQUE_VERSION"
    printf 'installed_ref=%s\n' "$ref"
    printf 'installed_at=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'script_sha256=%s\n' "$sha"
    printf 'files=%s\n' "$MANAGED_FILES"
  } > "$manifest"
}

# install_plain <dest> <emitter-fn>
# Missing -> write. Identical -> skip. --force -> overwrite verbatim, no merge.
# Differs (no --force):
#   - base snapshot exists -> 3-way merge (git merge-file); clean merge
#     overwrites dest and advances the snapshot; conflict/error leaves dest
#     untouched, writes dest.new + a .bak, and does not advance the snapshot.
#   - no base snapshot (legacy/pre-snapshot install) -> today's
#     backup+overwrite, then write a fresh snapshot for future runs.
# See docs/install-upgrade-design.md §2.
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
    snapshot_plain "$dest" "$staged"
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
    snapshot_plain "$dest" "$staged"
    return 0
  fi

  local basepath
  basepath="$(rel_to_base "$dest")"

  if [ ! -e "$basepath" ]; then
    # Legacy fallback: no prior snapshot to merge against — today's behavior,
    # then start snapshotting so future runs can merge.
    local backup="$dest.bak.$TS"
    if [ "$DRY_RUN" -eq 1 ]; then
      note_dry "backup $dest -> $backup, then overwrite (no base snapshot; legacy fallback)"
    else
      cp "$dest" "$backup"
      cp "$staged" "$dest"
    fi
    SUM_BACKEDUP+=("$backup")
    SUM_UPDATED+=("$dest (no base; overwritten)")
    snapshot_plain "$dest" "$staged"
    return 0
  fi

  # 3-way merge: ours=$dest, base=$basepath, theirs=$staged.
  local merged rc=0
  merged="$TMPDIR_WORK/merged"
  git merge-file -p --diff3 \
    -L "yours (local edits)" -L "base (last installed)" -L "upstream (new domestique)" \
    "$dest" "$basepath" "$staged" > "$merged" || rc=$?

  if [ "$rc" -eq 0 ]; then
    if [ "$DRY_RUN" -eq 1 ]; then
      note_dry "merge $dest (clean)"
    else
      cp "$merged" "$dest"
    fi
    SUM_MERGED+=("$dest")
    snapshot_plain "$dest" "$staged"
    return 0
  fi

  # Conflict (rc = number of conflicted hunks, 1..127) or hard error (rc>=128).
  # Either way: leave the live file untouched, do not advance the snapshot,
  # and force a non-zero exit for the whole run.
  CONFLICT_OCCURRED=1
  local newfile="$dest.new" backup="$dest.bak.$TS" kind="conflict"
  if [ "$rc" -ge 128 ]; then
    kind="error"
    echo "Error: git merge-file failed unexpectedly for $dest (exit $rc)." >&2
  else
    echo "Warning: merge conflict in $dest ($rc hunk(s)) — see $newfile" >&2
  fi
  if [ "$DRY_RUN" -eq 1 ]; then
    note_dry "merge $dest ($kind) — would write $newfile, back up $dest -> $backup, leave $dest untouched"
  else
    cp "$merged" "$newfile"
    cp "$dest" "$backup"
    SUM_BACKEDUP+=("$backup")
  fi
  SUM_CONFLICT+=("$dest ($kind; see $newfile)")
}

# install_claude_md <dest>
# Missing/no-markers/half-marker -> unchanged from before (create, append,
# refuse). Has both markers, block differs:
#   - --force -> replace block wholesale, no merge, advance snapshot.
#   - base block snapshot exists -> 3-way merge the BLOCK BODY (git
#     merge-file); clean merge splices the merged body back between fresh
#     markers, preserving everything outside the markers byte-for-byte, and
#     advances the snapshot; conflict/error leaves dest untouched, writes
#     dest.new (full file, conflict-marked block spliced in) + a .bak, and
#     does not advance the snapshot.
#   - no base snapshot (legacy/pre-snapshot install) -> today's wholesale
#     block replace + backup, then write a fresh block snapshot.
# See docs/install-upgrade-design.md §3.
install_claude_md() {
  local dest="$1"
  local blk="$TMPDIR_WORK/block" result="$TMPDIR_WORK/claude_result"
  local policybody="$TMPDIR_WORK/policybody"

  emit_policy > "$policybody"

  # Build the managed block: BEGIN marker + verbatim policy + END marker.
  {
    printf '%s\n' "$MARKER_BEGIN"
    cat "$policybody"
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
    snapshot_claude_block "$policybody"
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
    # Extract the current on-disk block body (ours-block) for a potential
    # 3-way merge, and build the wholesale-replace result (today's behavior)
    # for the no-merge-needed / legacy / --force paths.
    local oursblock="$TMPDIR_WORK/oursblock"
    awk -v beginm="$MARKER_BEGIN" -v endm="$MARKER_END" '
      $0 == beginm && !seen { seen=1; inblock=1; next }
      inblock && $0 == endm { inblock=0; next }
      inblock { print }
    ' "$dest" > "$oursblock"

    awk -v beginm="$MARKER_BEGIN" -v endm="$MARKER_END" -v blockfile="$blk" '
      BEGIN { while ((getline line < blockfile) > 0) block = block line ORS }
      $0 == beginm && !seen { seen=1; inblock=1; printf "%s", block; next }
      inblock && $0 == endm { inblock=0; next }
      inblock { next }
      { print }
    ' "$dest" > "$result"

    # If the block body is already current (no user edit, or already up to
    # date), the wholesale-replace result is byte-identical to $dest already
    # — no merge needed. Fall through to the idempotency guard below.
    if ! cmp -s "$oursblock" "$policybody"; then
      if [ "$FORCE" -eq 1 ]; then
        : # wholesale replace (already computed in $result above), no merge.
      else
        local basepath="$SNAPSHOT_BASE/CLAUDE.md.block"
        if [ -e "$basepath" ]; then
          # 3-way merge the block body: ours=$oursblock, base=$basepath,
          # theirs=$policybody.
          local mergedblock rc=0
          mergedblock="$TMPDIR_WORK/mergedblock"
          git merge-file -p --diff3 \
            -L "yours (local edits)" -L "base (last installed)" -L "upstream (new domestique)" \
            "$oursblock" "$basepath" "$policybody" > "$mergedblock" || rc=$?

          if [ "$rc" -eq 0 ]; then
            # Clean merge: splice the merged block body back between fresh
            # markers, preserving everything outside the markers verbatim.
            awk -v beginm="$MARKER_BEGIN" -v endm="$MARKER_END" -v blockfile="$mergedblock" '
              BEGIN { while ((getline line < blockfile) > 0) block = block line ORS }
              $0 == beginm && !seen { seen=1; inblock=1; print beginm; printf "%s", block; next }
              inblock && $0 == endm { inblock=0; print endm; next }
              inblock { next }
              { print }
            ' "$dest" > "$result"

            if cmp -s "$result" "$dest"; then
              SUM_SKIPPED+=("$dest (managed block already current)")
              return 0
            fi

            local backup="$dest.bak.$TS"
            if [ "$DRY_RUN" -eq 1 ]; then
              note_dry "backup $dest -> $backup, then merge managed block (clean)"
            else
              cp "$dest" "$backup"
              cp "$result" "$dest"
            fi
            SUM_BACKEDUP+=("$backup")
            SUM_MERGED+=("$dest (CLAUDE.md block)")
            snapshot_claude_block "$policybody"
            return 0
          fi

          # Conflict (rc = number of conflicted hunks, 1..127) or hard error
          # (rc>=128): leave the live file untouched, do not advance the
          # snapshot, write the conflict-marked full file to dest.new, back
          # up the current live file, force a non-zero exit for the run.
          CONFLICT_OCCURRED=1
          local newfile="$dest.new" backup2="$dest.bak.$TS" kind="conflict"
          if [ "$rc" -ge 128 ]; then
            kind="error"
            echo "Error: git merge-file failed unexpectedly for $dest block (exit $rc)." >&2
          else
            echo "Warning: merge conflict in $dest managed block ($rc hunk(s)) — see $newfile" >&2
          fi

          local conflictresult="$TMPDIR_WORK/conflict_result"
          awk -v beginm="$MARKER_BEGIN" -v endm="$MARKER_END" -v blockfile="$mergedblock" '
            BEGIN { while ((getline line < blockfile) > 0) block = block line ORS }
            $0 == beginm && !seen { seen=1; inblock=1; print beginm; printf "%s", block; next }
            inblock && $0 == endm { inblock=0; print endm; next }
            inblock { next }
            { print }
          ' "$dest" > "$conflictresult"

          if [ "$DRY_RUN" -eq 1 ]; then
            note_dry "merge $dest block ($kind) — would write $newfile, back up $dest -> $backup2, leave $dest untouched"
          else
            cp "$conflictresult" "$newfile"
            cp "$dest" "$backup2"
            SUM_BACKEDUP+=("$backup2")
          fi
          SUM_CONFLICT+=("$dest ($kind; see $newfile)")
          return 0
        fi
        # else: no base snapshot -> legacy fallback, fall through to the
        # wholesale-replace $result computed above; snapshot gets written
        # fresh at the bottom of this function.
      fi
    fi
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
  snapshot_claude_block "$policybody"
}

# ---------------------------------------------------------------------------
echo "domestique: installing into $TARGET_DIR"
[ "$DRY_RUN" -eq 1 ] && echo "(dry run — no files will be modified)"

install_claude_md "$TARGET_DIR/CLAUDE.md"
install_plain     "$TARGET_DIR/.claude/agents/implementer.md"   emit_implementer
install_plain     "$TARGET_DIR/.claude/agents/reviewer.md"      emit_reviewer
install_plain     "$TARGET_DIR/.claude/commands/decompose.md"   emit_decompose

# --- snapshot manifest ------------------------------------------------------
# Only (re)write the manifest if at least one managed file was actually
# created/updated/backed-up this run. On a fully clean no-op run (everything
# skipped as identical) the manifest is left untouched so re-running the
# installer twice in a row produces byte-identical .claude/.domestique/ state.
if [ "$SNAPSHOT_TOUCHED" -eq 1 ]; then
  if [ "$DRY_RUN" -eq 1 ]; then
    note_dry "write/update manifest -> $SNAPSHOT_DIR/manifest"
  else
    mkdir -p "$SNAPSHOT_DIR"
    write_manifest
  fi
fi

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
[ "${#SUM_CREATED[@]}"  -gt 0 ] && print_group "Created"    "${SUM_CREATED[@]}"
[ "${#SUM_UPDATED[@]}"  -gt 0 ] && print_group "Updated"    "${SUM_UPDATED[@]}"
[ "${#SUM_MERGED[@]}"   -gt 0 ] && print_group "Merged"     "${SUM_MERGED[@]}"
[ "${#SUM_BACKEDUP[@]}" -gt 0 ] && print_group "Backed up"  "${SUM_BACKEDUP[@]}"
[ "${#SUM_SKIPPED[@]}"  -gt 0 ] && print_group "Skipped"    "${SUM_SKIPPED[@]}"
[ "${#SUM_CONFLICT[@]}" -gt 0 ] && print_group "Conflicted" "${SUM_CONFLICT[@]}"
[ "$DRY_RUN" -eq 1 ] && echo "  (dry run: nothing was actually changed)"

if [ "$CONFLICT_OCCURRED" -eq 1 ]; then
  echo
  echo "One or more files ended in conflict/error — see 'Conflicted' above and the .new/.bak files for each." >&2
  exit 3
fi
echo "Done."
