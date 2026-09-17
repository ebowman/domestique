## Decompose: PLANNING ONLY

After the user's explicit planning request/brief and retained readiness, use
normal project-scoped Beads commands to create one epic and bounded tasks:

- `bd -C ROOT create TITLE -t epic -p 1 --description WHY_AND_DESIGN`
- `bd -C ROOT create TITLE -t task -p 2 --parent EPIC_ID --description INPUT_OUTPUT_DONE`
- `bd -C ROOT dep add BLOCKED_ID BLOCKER_ID`

Each task has one deliverable, explicit done-criteria and a small relevant test
set, completable in one ordinary session/pass. Split larger work; wire only
real dependencies, not speculative someday tasks. Treat all titles/descriptions
as literal argv elements, preserving newlines. Check every command result and
retain actual returned IDs; never fabricate successful creation.

Show scoped ready work and the epic dependency tree for human review. No code
writes, implementation/reviewer delegation, claims, close, Git staging or commits.
Planning does NOT authorize execution, even if native goal/autopilot is active.
