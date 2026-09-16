# Runtime-only bootstrap checkpoint — hq-1t9.2

This is development functionality, not a published release or native workflow
qualification. The frozen V2/1 CLI and machine wire schemas are unchanged.
No real HOME, operator alias, native client/model/config/DB or project was used
for installation qualification. Future project inventory belongs to hq-1t9.6;
public update belongs to hq-1t9.3.

## Currently implemented

`install-v2.sh (--version 2.MINOR.PATCH | --source PACKAGE_DIRECTORY) [--dry-run]`
accepts exactly one explicit selection (both value-flag forms). Standalone help
is available. Local source means a complete physical, nonsymlinked **directory**,
not this checkout or a script/URL. A developer can emit such a directory with
`v2.build.emit_package(new_absolute_directory, "2.0.0")`; this example version
identifies development bytes, not an official release.

The bootstrap is a generated, self-contained trusted execution root: it imports
no repository modules when run. `v2.build.bootstrap_bytes()` deterministically
bundles the modular verifier, publisher, transport and parser and the exact
launcher renderer. `python3 -B -m v2.build NEW_PATH` emits a new artifact without
overwriting existing files. The checked-in generated shell is necessarily
larger than hand-maintained modules. Candidate shell code is never invoked by
bootstrap, including dry-run; verified snapshots are staged, reverified and
published through the one existing publisher. Downloads are capped in private
process memory; only verified closed payload leaves enter owned disk staging.
All 12 leaves remain in the frozen inventory; there is no side-installed module.

Existing Python **3.9+ runtime**, Bash 3.2+ and Git are needed; explicit official
fetch additionally needs curl. No dependencies are installed. The macOS
`/usr/bin/python3` developer-tools setup launcher is not accepted as an available
runtime. Python uses `-I -S -B`; build-time AST facilities are not installed
imports. Direct executable entry uses `bash -p` to ignore BASH_ENV/exported
startup functions. Invoking a script through an already compromised shell
cannot undo that shell's earlier startup; use a trusted execution environment.

The fixed command is `$HOME/.local/bin/domestique2`; `G=S/v2` is literal physical
state, with normal DOMESTIQUE_HOME/XDG defaults. It never follows a different
ambient root. It accepts static help, validated version, `inspect [TARGET]`,
both exact `--inspect` aliases and bare read-only help plus `inspect .`.
Command parsing is all-or-nothing; misuse is 2, refusal is 1.
Valid enable/disable/update/retire-global forms explicitly return nonzero
**UNIMPLEMENTED**, without fetch, writes or legacy fallthrough. No automatic
alias or PATH edits occur. An optional human alias can point `dom2` at the
installed absolute executable; the user's existing external alias is untouched.

## Dispatch and development-prototype compatibility

The `8b48b6a` ABI-2 prototype deliberately had NO candidate dispatch. This new
dispatcher is different bytes, and **cannot be a compatible replacement for
that prototype**. Existing different prototype/edited/unowned/symlinked launchers
are refused and preserved, even if a candidate has identical content. No ABI
bump, silent migration, provenance invention or repair switch was introduced.
Only fresh installations establish this dispatcher; compatible package updates
must preserve its exact bytes. A future protocol change requires explicit design
review, not replacement under the current ABI label. The old prototype function
is retained for its internal API/history, not used as a fallback.

The dispatcher validates the manifest's closed ordered provenance, physical
identity, every recorded package header/sums identity and active selection, then
checks the selected management leaf's live hash/mode before executing its
**verified in-memory bytes**, never the original source path. Package workflow
bodies and resolvers are not read/executed for management. Watches are registered
before the authenticated reads and directory validation throughout this dispatch
chain; byte, inode, mode or timestamp changes refuse, even when the in-memory
afterimage itself is still authentic. No post-read snapshot becomes a baseline.
Retained bootstrap validation likewise carries the original directory, launcher,
manifest, active and complete package watches through selection and preflight
into publication. Revisiting a path compares its earlier witness; only checked
owned mutations may advance it. Observed drift refuses before further writes or
success, preserving unexpected replacements and any already-written evidence.
This is observation-bound preservation, not hostile-writer atomicity.
The legacy inspection
engine is extracted byte-for-byte from the retained source and embedded only in
the immutable `domestique2.sh` package leaf; its parser, privacy protections and
bounded collection remain unchanged. The installed outer parser does not inherit
the old help-precedence behavior. This reports legacy/preview inventory plus
current runtime availability, not enabled V2 projects or native readiness.

Management conservatively reports `recovery=unknown` and exits 1 if any machine
or retirement journal is present: it does not load workflow bodies to classify
publication facts. The publisher's full verifier still distinguishes pending,
cleanup-pending and unknown and reports actual old/new/unavailable selection.
Missing/corrupt management is a refusal, not a fallback to a workflow/old helper.
Bootstrap retains the existing checked unbuffered writes, per-write Git/native
boundary checks, creation-versus-baseline facts, launcher-before-manifest and
active-last ordering. Failed afterimages/journals remain manual evidence; there
is no automatic cleanup across a refused boundary, rollback, takeover or GC.

## Future official source and trust

The fixed source is `ebowman/domestique`, exact tag `vV`, assets
`domestique2-V.tar.gz` and `.tar.gz.sha256`. **No live V2 release is claimed.**
The initial URL is GitHub HTTPS; at most three manually validated HTTPS
redirects may reach github.com, release-assets.githubusercontent.com or
objects.githubusercontent.com. Per asset: connect 10s, total 120s, no retries,
curlrc, inherited proxies, credential environment, netrc or client-auth options.
No third-party network library or remote executable main is used.
The decoded HTTP body-byte cap is cumulative across every redirect response and
the final response (1 MiB for the sidecar, 64 MiB for the archive). Redirect
bodies consume this budget but are discarded, never included in the artifact or
diagnostics. Header bounds apply separately to each response. Reads are bounded
by the remaining body allowance plus at most one byte to detect overflow,
including reads that straddle the header/body boundary.

Sidecar format/filename and the archive SHA-256 are checked before gzip/tar
parsing. The compressed archive and the entire decompressed tar stream each
have an exact 64 MiB ceiling. The latter includes all file data, directory/file
headers, block padding, end markers, trailing padding and concatenated gzip
members; there is no extra framing allowance. One extra decoded byte detects
overflow and refuses the whole input, never truncates it into a valid archive.
At the ceiling, EOF and gzip trailers must still validate. File-data totals
also remain bounded by 64 MiB; metadata is 1 MiB with the frozen line/field
limits. Every raw tar header is inspected; the exact
root/directories/leaves are required and duplicates, extras, links, devices,
absolute/traversal paths and GNU/PAX extension entries refuse. Fixed names need
no extension records. Owners/modes/timestamps in the archive are ignored; output
leaves are exclusive creations with package modes.

Colocated checksums detect corruption, **not independent publisher
authentication**. Trust rests on the operator's bootstrap plus HTTPS/account/
repository control; local development packages are operator-trusted input and
never mint official mappings. Verified retained official selection is offline;
corrupt existing mappings refuse before network and are never downloaded over.
Ordinary installed command use is always offline.

## Source-qualified validation scope

CURRENT registers `v2-bootstrap-tests.py` using the existing owned FixtureSession,
not a new runner. Its standalone local/official-stub installs, offline command
cases, exact argv, bad inputs/archives, no-op snapshots, prototype refusal and
one pending update fault supplement, not replace, the publisher/records matrices.
Native/Beads/curl/wget markers remain observable; only the exact deterministic
transport stub is explicitly permitted, with its own argv log.

Per-scope closure: `records.py`, `journal.py`, `factories.py`, policies and
retained preview/public v1 bytes are unchanged. Parser/dispatcher/build,
filesystem watches, runtime/package verification and publisher selection/
mapping/plan inputs are affected. Prior full publisher/records proofs are
**not** full proofs of these new bytes. The complete publisher/records matrices
require fresh source-bound stages; unchanged historical inspection/fixture
certificates are not relabeled current. Installed inspection integration remains
in the bootstrap scope. Selected successes are not full-offline acceptance.

The resumed-fix qualification freezes all sources before bounded serial stages,
each reserving 90 seconds for cleanup. Direct `python3 -B -Werror`
programs run serially: the full bootstrap scope (including actual transport,
decompression, retained-bootstrap and dispatch-mutation counterexamples),
acceptance unit scope, version boundary and syntax/ShellCheck/AST/diff first
(1200s stage). Full publisher (1200s) and records (900s) follow as separate
stages, not a single final twenty-minute gate. Ordinary 120s/install
300s/cohort 900s limits remain unchanged. No outer process-table controller or
concurrent heavy fixture gate is used. New session logs record exact
commands/exits/counts, source hashes, validators, mutation witnesses, fixture
identities and qualified cleanup. Old proof files are not rewritten; any
remaining full-scope proof is a partial handoff, not full-offline acceptance.
