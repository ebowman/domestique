# Source-only major boundary (hq-5jc.3)

This is an intermediate checkout, not a release or the proposed installed CLI.
`domestique2.sh --inspect [TARGET]` (also `TARGET --inspect`) preserves ln2's
read-only preview/legacy inventory, parser, privacy and ownership distinctions.
Its help is current; it does not report V2/1 activation or certify native readiness.
`domestique2.sh` without inspection refuses. `update2.sh` has no default fetch;
explicit `--source PATH` / `--version 2.MINOR.PATCH` and optional `--dry-run`
still refuse before candidate execution or destination mutation. Empty/missing,
duplicate, malformed or conflicting updater arguments exit 2; unsupported
publication/source kinds exit 1. Help alone exits 0. The retained inspector
keeps its older help-precedence behavior; this is not the new installed parser.

## Verified public v1

Local `main`, `origin/main` and `origin/HEAD` identify
`4de726c2e38e731c67f5f37d4a16206d7b3d99af` (merged Codex support).
The public artifacts are byte-identical to that source:

* `domestique.sh` Git blob `85fbfb4cd6dcc1cbfbeefdbcfca1463e8cadda1b`
* `update.sh` Git blob `beb611c86705d6d99cfb83ade5f48ed31f57d4f8`

The tag `v0.1.0` predates this guest/two-provider channel. Neither the draft
Copilot branch nor fixture pin `b60feef4d0d41b8d99b7afec68dd5e6ef648b027`
is public v1. The old updater's default remains
`https://raw.githubusercontent.com/ebowman/domestique/main/domestique.sh`,
including already-downloaded copies. Explicit local/URL sources override
`DOMESTIQUE_UPDATE_SOURCE`; unset/empty env uses that same old default.
Normal, sticky guest, `--no-guest`, Claude/Codex and `both` retain actual v1
behavior, including legacy merging/preview limitations. This is preservation,
not a retrofit of V2 guarantees into downloaded v1 code.

## Why writes are gated rather than renamed

The retained b3q publisher emits format 1 under `S`, with
`.domestique-private/manifest`, old globally advertised native IDs and an
unversioned helper. Simply adding `/v2` or renaming IDs would falsely certify
V2/1 authority while omitting the frozen package inventory, format-2 identities,
creation facts, guarded receipts and mandatory activation. Leaving its dispatch
live would instead collide with old owners. Neither is safe compatibility.

The bounded solution is **no writer reachable through either new artifact**.
The proposed identities remain reserved: `G=S/v2` (even with explicit base
`DOMESTIQUE_HOME`), `.domestique-private/v2/`, launcher
`$HOME/.local/bin/domestique2`, and the exact provider-qualified
`domestique-v2-{claude,codex,copilot}` skill/role inventories in the
[frozen contract](v2-install-contract.md) and
[normative appendix](v2-install-interfaces.md). No PACKAGE, format-2 manifest,
launcher or native adapter is manufactured by this checkpoint. Prior previews
are legacy inputs only. Their roots, helpers, profiles and Beads are neither
adopted nor cleaned. Inspection retains their *old* inventory intentionally.

Implementing publication/verification, bootstrap/installed grammar and project
activation remains hq-5jc.4, hq-1t9.2/.4 and hq-5jc.7 respectively.
No V2 URL is asserted, and the old default is not redirected elsewhere.

## Test source qualification

Each new artifact contains exactly one `BEGIN RETAINED PREVIEW SOURCE` boundary
followed by the byte-identical reviewed `58732cc` body. `test/preview_fixture.py`
extracts that body **only into disposable test-owned roots**; there is no flag,
environment variable or production sourcing bypass for it. Lifecycle tests
exercise this retained engine, not the public gated writer. CURRENT is a source
test registry, not a claim that every registered scope tests V2 installation.
Acceptance labels retained-engine results accordingly; none qualify V2 records.

The complete inspection matrix still runs the real new `--inspect` artifact.
Six setup calls retain all old inventories/scenarios; only the two preview
install calls use the explicitly extracted body. Their Origin now says
`retained-private-preview`, hashes the actual executed extracted bytes, and
also binds the new outer artifact and extraction helper in qualification.
The historical and pre-snapshot pins/origins are unchanged. Parser controls
without inspection test the retained parser, while live boundary tests test
refusal. Static embedded Python/resolver extraction targets the same body.
Old b3q/ln2 green totals are not reused as current execution evidence.

Run complete inspection/fixture/acceptance unit scopes and the focused
`test/version-boundary-tests.py`, plus CURRENT syntax/lint/AST. Use one declared
1200-second wall budget including owned cleanup, independent suite roots in
parallel as needed; never enlarge ordinary 120/install 300/session 900 limits.
Keep full command output/exits/source hashes in a new session.
Heavy lifecycle/native suites are not this checkpoint's gate; their existing
cases remain available, now explicitly retained-preview rather than V2 tests.
Native Claude discovery/all roles remain **BLOCKED** under the previous
bounded observations. No native client, model, MCP or DB proof is inferred.

The frozen contract's source trace `020c05c:domestique.sh` refers to that Git
object, not today's v1 file at the relative link; its preserved body is now
in `domestique2.sh`. The [design history](install-upgrade-design.md) and
[README historical sections](../README.md#retained-qualification-history)
retain the completed b3q/ln2 qualification limits.

The operator must manually retarget any developer `dom2` alias from the old
external `domestique.sh` to this checkout's `domestique2.sh` for inspection.
No alias, personal config or installation was changed.
