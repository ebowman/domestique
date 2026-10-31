# domestique

Project configuration for a **multi-model orchestration workflow** in Claude
Code, Codex and GitHub Copilot: an **orchestrator** designs and adjudicates,
an **implementer** executes, and a fresh **reviewer** independently verifies.
The plan of record lives in [Beads](https://github.com/steveyegge/beads).
Delegating implementation and verification keeps the orchestrator's context
lean; “done, tests pass” is checked, not trusted.

## Standalone 0.2.0

This tree prepares **v0.2.0** for publication; it is not itself a published tag
or an update to remote main. Runtime logic is unchanged from the qualified
standalone candidate; only its version label changes. Native/full-matrix
qualification is reused, with [limitations and two unresolved historical
failures](docs/install-upgrade-design.md#qualification-and-known-issues).
Their residual risk and retention of candidate history were explicitly accepted
for this release preparation; no fixes are claimed.

### What's new

- One standalone `domestique.sh`, through the existing `dom` command. No
  `dom2`, project enable step, source checkout or global runtime.
- Selector-less fresh installs **and reruns select all three clients**.
  Explicit `--platform claude`, `codex`, `copilot`, `both` or `all` remain;
  **`both` means Claude+Codex**, not Copilot.
- Independent, consent-bound first-use setup for each project's native role
  pair, with reload only when needed before execution. Compatible customizations and model choices survive
  preserving upgrades.
- Shared Codex/Copilot planning and goal skills, sticky normal/guest modes,
  scoped removal, and bounded migration of supported Copilot preview projects.

## Remote install and upgrade

Run from the intended project root. Installation needs Bash, Git and Python
3.11+ for the all-three path. It installs **configuration**, not clients, models,
credentials or Beads itself. Native clients and usable models are prerequisites
for workflow execution, not configuration installation.

After publication to main, existing aliases need no change:

```sh
alias dom='curl -fsSL https://raw.githubusercontent.com/ebowman/domestique/main/domestique.sh | bash -s --'
dom --dry-run
dom
# Explicit selection; both does not add Copilot:
dom --platform both --dry-run
dom --platform both
```

Equivalent direct transport:

```sh
curl -fsSL https://raw.githubusercontent.com/ebowman/domestique/main/domestique.sh | bash -s -- --dry-run
curl -fsSL https://raw.githubusercontent.com/ebowman/domestique/main/domestique.sh | bash -s --
```

`main` is a **moving channel**: its next invocation downloads whatever is
published there. There is no background auto-update; a tag alone does not update
main or an alias. Until publication, use the reviewed local script in a
disposable project, not these URLs to test 0.2.0.
For repeatable dry-run/apply, replace `main` in **both** commands with the same
full reviewed published commit SHA. `v0.2.0` URLs work only once that tag is
published. Pinning script bytes does not reverse migrated project state.

Read the version-labelled target/provider/mode plan before applying.
There are no installer stdin prompts. Explicit selections are **additive**:
persisted Claude/Codex may also be selected; unselected Copilot is retained.
Use scoped uninstall, not an install selector, to remove a provider.

## First use and the workflow

| Native client | Explicitly configure both role models | Fresh explicit goal |
| --- | --- | --- |
| Claude Code | `/dom-decompose configure role models` | `/dom-goal EPIC_ID` |
| Codex | `$dom-decompose configure role models` | `$dom-goal EPIC_ID` |
| GitHub Copilot | `/dom-decompose configure role models` | `/dom-goal EPIC_ID` |

Use the same planning entry with a task brief to decompose work into an epic and
bounded tasks. Codex also offers `/skills` selection. Loading a skill alone
never authorizes goal work. A goal must explicitly name the intended epic;
require fresh independent reviewer **PASS before task commit or closure**.
Planning never requires model setup, helper verification, loaded roles or a
restart—even with missing/unconfirmed/manually edited roles—and never delegates
or executes tasks. Only the exact `configure role models` argument selects setup;
a planning brief mentioning models does not.

1. On explicit configuration or first **interactive goal**, reuse saved selections.
   Missing/unconfirmed choices are requested together in one concise form for
   **both implementer and reviewer models**, including supported effort.
   Explicit native inheritance is allowed; defaults or absent fields are not
   consent. No global model registry is used.
2. Verify actual native availability and persistent role support. The installed
   deterministic helper prepares the minimal diff **read-only**, with no
   scratch/staged plan. Review a compact summary of project/harness, current →
   chosen settings, exact role files/change scope and tracked consequences.
   Detailed diff is available on request; raw hashes/marker JSON are not required.
   Confirm **Save these choices?**, then approve any ordinary scoped native writes.
   Selection alone is not consent to the prepared plan; changes renew consent.
   Wait for terminal save completion and pair verification; pending/partial/error
   results are not success. Cancel writes nothing.
3. Planning can proceed without reload or repeating an already supplied brief.
   Setup never queues goal work. Before execution, reload/start a fresh native
   invocation if registrations are stale/unknown. Verify registrations, effective choices,
   precedence and availability. Review and explicitly dispose of tracked setup
   changes before work, for example through a separately reviewed setup commit;
   never automatically stage, stash or hide them. Issue a **fresh** goal.
4. Unchanged confirmed pairs do not reprompt on rerun. Changed role bytes,
   including custom body edits, invalidate confirmation. Unavailable/mismatched
   models stop execution, not planning: reconfigure, consent and reload as needed;
   never fall back silently.

The helper proves filesystem consistency, **not** which bytes/models a native
client loaded. See [pair paths and native limitations](docs/install-upgrade-design.md#first-use-role-setup).

## Sharing, guest mode and removal

Normal configuration is repository-shared when committed. Guest mode is
personal/local Git visibility, **not access control**:

```sh
dom --guest --dry-run
dom --guest
dom --no-guest --dry-run
dom --uninstall --platform copilot --dry-run
dom --uninstall --dry-run
```

Modes are sticky per provider. Missing providers inherit a uniformly normal or
guest set; fresh defaults to normal. Mixed modes plus a missing selected
provider refuse until explicitly resolved with `--guest` or `--no-guest`.
Shared Codex/Copilot routes are private only when all valid consumers are guest.
Git-common exclusions affect linked worktrees and **cannot hide tracked files**.
Claude guest policy uses `CLAUDE.local.md`; Codex/Copilot leave host policies
untouched and bootstrap via **`$domestique` / `/domestique-v2-copilot`**.

Remove `--dry-run` only after review. Scoped removal retains shared routes
until the last consumer is removed. Modified owned files are preserved as
timestamped uninstall backups unless forced; unowned files and Beads are not
ordinary removal targets. **`--force` can discard provider customizations** and
is not a migration/refusal bypass.

Read the [install, upgrade and recovery guide](docs/install-upgrade-design.md)
before converting modes or resolving refusals. Supported five/seven-definition
Copilot preview project migration preserves selections and backups but requires
fresh pair confirmation. Keep recovery evidence; do not blindly downgrade.
The [historical preview boundary](docs/v2-preview.md) is not another runtime to
install for this release.

## Contributing and testing

Propose bounded changes with regression coverage and an independent review.
Use disposable projects, never a working project's configuration as a fixture.
For the standalone tests, use a **full-history clone with tags**; historical
fixture commits are required. No runtime source checkout is needed by users.

```sh
python3 -B -Werror test/model-setup-tests.py
python3 -B -Werror test/all-current.py
bash test/upgrade.sh --current
```

Selected shell suites also include `guest.sh`, `codex.sh` and `uninstall.sh`;
without `--current` they run frozen historical fixtures, not current acceptance.
The release reuses the candidate's full/native qualification; see the guide for
fixture ancestry and what the smaller publication tree does **not** retest.

## License

MIT — see [LICENSE](LICENSE).
