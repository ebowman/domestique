# Source boundary: verified bootstrap (hq-1t9.2)

Current functionality, compatibility decisions and source-closure limits are in
[the bootstrap guide](v2-bootstrap.md). `install-v2.sh` is now a standalone
verified runtime-only writer; installed help/version/legacy inspection work
offline. Public update and all project/native activation remain unimplemented.
Different existing help-only prototype launcher bytes are explicitly refused,
not overwritten under a claim of stable ABI-2 compatibility.

Public v1 and retained preview bytes remain unchanged. The following section is
the **historical hq-5jc.4 checkpoint at 8b48b6a**, not a statement that today's
bootstrap is still missing. Its complete test totals do not qualify changed
bootstrap/publisher integration without fresh, source-bound scope evidence.

## Historical isolated local-runtime checkpoint (hq-5jc.4)

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

There is still **no writer reachable through either checkout shell artifact**.
The internal local publisher now creates only `G=S/v2` (even with explicit base
`DOMESTIQUE_HOME`) and launcher `$HOME/.local/bin/domestique2`.
Project `.domestique-private/v2/` and the exact provider-qualified
`domestique-v2-{claude,codex,copilot}` skill/role inventories in the
[frozen contract](v2-install-contract.md) and
[normative appendix](v2-install-interfaces.md) remain future activation work.
The publisher emits a real PACKAGE and
format-2 runtime manifest, with a trusted minimal stable launcher; packaged
native templates remain inert data, never HOME/project advertisements. Prior previews
are legacy inputs only. Their roots, helpers, profiles and Beads are neither
adopted nor cleaned. Inspection retains their *old* inventory intentionally.

Bootstrap/installed grammar and project activation remain hq-1t9.2/.4 and
hq-5jc.7 respectively; public update/rollback remains hq-1t9.3.
No V2 URL is asserted, and the old default is not redirected elsewhere.

## Internal local API and interface ownership

* `v2.build.emit_package(destination, version)` exclusively emits the deterministic
  closed 12-leaf package. `PACKAGE` and complete sorted sums define R. Development
  modules use stdlib bundling; no undeclared installed modules or new build tool.
* `v2.package.verify_package(directory)` validates physical, bounded local input
  without executing it. `v2.publisher.publish_local(source, env, dry_run=False)`
  stages only allowlisted payloads outside destinations, reverifies, then
  publishes provider-independently. Explicit trusted `env` supplies HOME,
  optional DOMESTIQUE_HOME/XDG_STATE_HOME, PATH and a safe temporary parent.
  Existing Python 3.9+, Bash and Git are required; nothing installs dependencies.
  No inherited Git directory/config/ceiling can hide a machine-worktree overlap.
  Exact Git/native ancestors and path identities are checked afresh before every
  publication/staging write and final success, even with preexisting parents.
  A change stops writes, including automatic cleanup in newly forbidden areas;
  private staging/temporary afterimages can remain as partial evidence.
* `v2.safe` adapts the retained global safe-path/exclusive-creation and stdlib
  bridge primitives. `v2.records` owns the shared machine A/B/D encodings and
  strict checked readers; `v2.journal` classifies hash-valid pending prefixes,
  committed cleanup-pending and orphan/corrupt/stale unknown evidence.
  Previous stores metadata only, chunked and bounded.
  `pending` is exclusive, never a PID lease. Release then **actual final launcher**
  creation/facts precede manifest, active switches last, and clearing is
  published/previous/pending. No-op preserves destination identity/mtime/mode.
* `v2.build.launcher_bytes(G, HOME)` deterministically bundles only trusted
  verifier/protocol code with the physical root embedded. The installed ABI-2
  launcher currently supports static help and verified version/availability.
  Missing manifest/active makes version/operations unavailable even if a complete
  release exists. Static help is the explicit discovery-free exit-0 exception:
  it reports usage only and does not certify runtime/install readiness.
  During pending, a complete validated old/new selection remains reportable.
  Version reports that actual selection but exits 1 while recovery is not none;
  missing framing is unknown, never a fictional completed transaction.
  Unsupported management/activation/Beads operations do not delegate to a
  candidate entrypoint, old resolver, or workflow body.
* `v2.runtime.runtime_read` verifies without workflow execution. hq-1t9.2
  integrates this minimal protocol with the future bootstrap/parser/fetcher;
  it must preserve the stable ABI-2 dispatcher, not rewrite it on compatible
  updates. hq-1t9.4 supplies guarded binding/read/route; hq-5jc.7 replaces the
  currently fail-closed loader data with guarded project native adapters.
  Those changes version execution helpers inside R. No unversioned helper
  or format-1 bootstrap bypass is installed here.
* `v2.factories.factory(provider)` returns inert JSON mapping exact native leaf
  paths to native YAML/Markdown/TOML strings (including Codex's goal sidecar).
  No config, trust/auth, model registry, tools/MCP/default grants. Four policies
  under `v2/roles/` reuse the reviewed sequential lifecycle, without its obsolete
  format-1/global-routing protocol. One loader/policy implementation serves all
  three serializers; until guards exist it explicitly stops before body access.

The API returns actual runtime selection, recovery, changed and dry-run fields;
after publication failure `PublicationFailure.selected/recovery` reports actual
old/new/unavailable plus retained recovery evidence, never fictional rollback.
Any pending/orphan/corrupt/unowned scope refuses reruns; no resume, repair, GC,
old-helper deletion, project registry, rebase or native-global retirement exists.
Trusted `hook(event, path)` is test-only API injection, not a CLI/environment flag.
Readers requiring recovery interpretation must validate the exact plan/snapshot
against A/B/D; these writer readers do not provide an automatic recovery API.

## Test source qualification

Each new artifact contains exactly one `BEGIN RETAINED PREVIEW SOURCE` boundary
followed by the byte-identical reviewed `58732cc` body. `test/preview_fixture.py`
extracts that body **only into disposable test-owned roots**; there is no flag,
environment variable or production sourcing bypass for it. Lifecycle tests
exercise this retained engine, not the public gated writer. CURRENT is a source
test registry, not a claim that every registered scope tests V2 installation.
Acceptance labels retained-engine results accordingly; none qualify V2 records.

The separate CURRENT `v2-publisher-tests.py` and `v2-records-tests.py` exercise
the **actual** format-2 API, not extracted preview source. They reuse the
identity-qualified FixtureSession snapshot, stdio limits and cleanup oracle in
owned physical OS-temp roots outside Git (no production ceiling bypass).
They cover real creation/idempotence, three inert schemas, bounded input,
collisions/races, metadata/fact framing, 23 fresh and 11 update fault points and
fresh-launcher-before-manifest version/operation refusal plus static-help exception.
Actual post-preflight/phase Git/redirect mutations assert zero additional writes;
whole-input journal tests reject malformed complete/torn suffixes while every
possible normal fact/commit prefix remains pending. Subcase logs name actual exercised
fault/refusal inventories; unittest selectors are partial evidence, not a full
suite claim. Native/client/model/DB readiness is not inferred.
CURRENT fingerprints include every new development module/policy and immediate
contract/interface/source-boundary documentation. Static checks include their
AST and deterministically bundled launcher/three executable payloads.

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
parallel only after isolated publisher/records and acceptance103 runs; acceptance's
unchanged 10-second subprocess limit must not compete with heavy fixture load.
Never enlarge ordinary 120/install 300/session 900 limits.
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
