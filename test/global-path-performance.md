# Bounded path-validation performance checkpoint

This is not full `.8` acceptance or native-client/Beads qualification.

`global_path` still runs at every existing validation/mutation boundary.
Within each call it inventories only exact ancestors, batches fresh BSD/GNU
stat records (at most 32 paths and 8192 argv payload bytes), performs the
existing permission/type/searchability checks, and rereads metadata. Records
contain owner, octal permissions, device, inode and the exact path. Count,
association, numeric grammar, complete output and command success are required.
NUL is converted to a forbidden byte before Bash captures output.
Changed identity/permissions/inventory or symlinks refuse; missing tails are
checked again. Nothing is cached across calls, including the platform probe.
An exec/ARG_MAX failure refuses; there is no silent fallback. Like the original
path walk, these checks are not an atomic filesystem snapshot or protection
against an adversary changing a path after the final check.

BSD permissions now use `%Mp%03Lp`: exactly four octal digits including
setuid, setgid and sticky, rather than `%Lp`'s low bits alone. Root-owned
sticky writable directories OUTSIDE the boundary are allowed as intended;
user-owned sticky writable ancestors and writable paths INSIDE the boundary
remain refused. Metadata stability includes changes to all three special bits.

The internal `global_stat` output now includes identity/path fields; it is not
a persisted ownership/API format. The standalone resolver includes the new
batch helper. The existing local-preflight permission injection uses the new
internal record shape. No Git/index checks were optimized in that path checkpoint;
the subsequent index-only checkpoint is recorded below.

## Reproduction and evidence

* `PYTHONDONTWRITEBYTECODE=1 python3 test/global-path-tests.py`: bounded unittest
  comparison against immutable helpers on actual isolated paths, plus synthetic
  malformed/error/dialect injection. Included once in acceptance `CURRENT`,
  classified by the runner's strict unittest report handling.
* `PYTHONDONTWRITEBYTECODE=1 python3 test/global-path-benchmark.py`: one actual
  before/after global-all + local-all install, no native clients/DB. Uses current
  `acceptance.execute`, `environment`, and `Control`: 120 seconds per operation,
  300 seconds overall, cleanup/reaping included. Both sources use the same
  temporary path/topology; the baseline restores only the frozen path helpers and
  resolver declaration list. This multi-minute benchmark is explicitly opt-in,
  never a default acceptance suite. Core starts absent under `work/scope/core`, below
  the Git discovery ceiling, and project init uses the isolated Git template.

The small `test/global-path-baseline.sh` fixture is the verbatim helper block
from `domestique.sh` at **20b6fe8d924d50c943242dc730725e59ce1ef956**.
`test/global_path_baseline.py` checks its SHA256 and the current replacement
layout before either comparison. Missing/malformed fixtures fail, never skip.
No Git history or mutable HEAD is required, including in fresh/shallow checkouts.
The legacy BSD bug is deliberately retained in the oracle and asserted as an
intentional before/after difference, not silently accepted as current behavior.
Both fixture files are included by acceptance's syntax/lint and provenance
file inventories.

Observed **before the special-bit correction and immutable-oracle wiring** on
Darwin arm64, native `/bin/bash` 3.2.57 and BSD stat, untraced (not rerun here):

| Operation | Before | After | Measured speedup |
| --- | ---: | ---: | ---: |
| Global, all providers | 7.095 s | 5.875 s | 1.208x |
| Local, all providers | 86.195 s | 56.823 s | 1.517x |

One sample per operation, not a statistical benchmark. An initial benchmark
invocation used an invalid CLI option and refused before installation; the
table is the corrected, successful identical-topology experiment.

Native evidence covers real paths, modes, symlinks, FIFO refusal, missing
tails, readonly validation, unusual allowed names, deep/count/byte boundaries,
and actual mid-validation mutations. Wrong owner is synthetic (no chown);
GNU dispatch/serialization is translated to native BSD stat, **not** a native
GNU run. Malformed/partial/reordered-path/error outputs are synthetic. The
host's shared temporary ancestor is not modified to make the fixture pass.
Real Darwin cases now explicitly distinguish the oracle's erroneous refusal of
root-owned sticky `/private/tmp` from the corrected allowance outside the
boundary. They also cover in-boundary refusal, user-owned sticky/writable
refusal, and detected sticky/setgid/setuid-only mutations of isolated directories.
No shared host ancestor is chmodded and nothing is chowned.

Prior to this correction, private-core coverage passed **117** checks, path
coverage **16** tests and acceptance-runner coverage **53** units.
The earlier concurrent bounded attempt ran **18** path tests (2 errors) and **54** runner
units (2 failing subtests, 3 errors): **neither suite passed**. Both were run
concurrently with Python warnings as errors; failures involved existing
`ps` inspection/cleanup deadlines, including cleanup-incomplete/ResourceWarning
diagnostics in runner units. No timeout was increased and no supervision code
was changed. Work stopped at this out-of-scope validation blocker; private-core
was not rerun. Current syntax/lint/diff validation passed: **13 shell files +
emitted resolver**, **17 Python files + embedded Python**, zero warning-level
ShellCheck diagnostics; immutable fixture checksum/layout passed.

The earlier affected
full local-preflight shell suite exceeded its supervised 120-second budget;
its exact processes were stopped/reaped, not rerun with a larger budget.
That timeout is NOT a pass. Full applicable `.8` matrices, native acceptance
and independent review remain pending; this checkpoint makes no final `.8` PASS.

## Resumed index-query checkpoint (2026-09-14)

Starting branch `epic/hq-b3q`, HEAD
`20b6fe8d924d50c943242dc730725e59ce1ef956`; starting full tracked diff SHA256
`e2395b7c22e121f56dd850fecebe1a741fe38a1d80e5bd999f2dbd6daa3278eb`
was verified. Existing path batching, signal/finalization changes and the stopped
`.acceptance-kh91ktfz` fixture were preserved.

Only `local_untracked` production code changes in this checkpoint. Each call
performs one fresh `git ls-files -z -- ":(top,literal)$outer"` query, where
`outer` is the candidate's first component. Real Git differential tests establish
that this includes the destination/subtree and every possible exact ancestor
index object. Bash byte comparisons distinguish those collisions from unrelated
siblings, including siblings within ancestor directories. No cache, new
dependency, filesystem-check batching or removed per-mutation validation.

The local callers use canonical ASCII native/metadata inventory leaves; the
global-removal caller always refuses any worktree destination even if its index
check succeeds. Thus the internal candidate contract now refuses empty, absolute,
noncanonical (`//`, `.`/`..`, trailing slash), control-byte and non-ASCII paths
before querying, rather than comparing a spelling Git could normalize.
Spaces, backslashes and literal metacharacters are supported. Roots still come
from the existing top-level validation, not a new filesystem walk.
Git's literal case-sensitive matching is retained (tested with
`core.ignorecase=true`); inherited Bash `nocasematch` is disabled only inside the
guard subshell. All four directory/index routing overrides still refuse, and all
four `GIT_*PATHSPECS` overrides now refuse even when set to an empty string.

The query is NUL-framed and streamed, not captured by command substitution.
Empty output means an empty matching index; an empty *frame*, malformed canonical
path, out-of-query record, unterminated tail or nonzero command (including after
output) refuses via the existing pipefail error path. Indexed filenames themselves
are opaque, so unrelated LF/tab/non-UTF8/Unicode names do not cause false refusals.
These are fresh per-call observations, not an atomic snapshot or protection
against index mutation after the final validation.

`test/local-index-baseline.sh` captures the verbatim original index helper at
the full commit above; its helper-block SHA256 is
`930fd3fa19b40b82d874b0d6c38568516dba084df4bca369f6aa1172cb3a9493`.
Capture was checked byte-for-byte against that immutable Git object.
`local_index_baseline.py` verifies checksum/layout and substitutes only that
block. Path helpers and resolver emission stay unchanged. Missing/corrupt
fixtures fail, never skip. Provenance and syntax/lint inventories include the
new fixture/loader; `local-index-tests.py` appears once in `CURRENT`, while both
the fixture and opt-in benchmark stay out of suite membership.

Sequential validation, with existing budgets:

* `python3 -B test/local-index-tests.py`: **12 tests PASS**, 55.879s.
  Actual fresh indexes cover destinations/descendants and each exact ancestor
  as regular file, symlink and gitlink, deleted worktree leaves, literal unusual
  names, opaque unrelated bytes, siblings, overrides and consecutive index
  changes. Empty → collision → empty calls in one shell observe **7 old vs 3 new
  actual Git query invocations**, not a timing extrapolation. Protocol faults
  are explicitly synthetic; no native Beads/client evidence is claimed.
  Initial run: one fixture failure because sourced `errexit` prevented observing
  an expected refusal; fixed by disabling errexit only in that multi-call test.
* `python3 -B test/global-path-tests.py`: **18 tests PASS**, 28.927s, unchanged.
* `python3 -B test/acceptance-tests.py`: **55 units PASS**, 20.656s, including
  new membership, malformed/duplicate completion and provenance regressions.
* Supervised `test/private-core.sh`: **117 checks PASS**, 120s total budget shared
  with subsequent syntax/lint validation. Initial lint caught missing baseline
  shell identification (SC2148); fixed with a shebang outside the pinned block.
* Corrected bounded validation: **14 shell files + emitted resolver**, **20
  Python files + embedded Python**, zero warning-level ShellCheck diagnostics,
  `git diff --check` and immutable index checksum/layout **PASS**. No suppression
  or budget increase was added.

`python3 -B test/local-index-benchmark.py` reuses the existing benchmark's
`acceptance.execute`, `environment`, `Control` and identical disposable topology.
Only the index helper differs between sources; core begins absent below
`work/scope/core`, not directly at the Git ceiling. Limits remained **120s per
operation / 300s overall**, including cleanup. No native clients/DB/network.

| Actual operation (one each per source) | Before | After | Difference |
| --- | ---: | ---: | ---: |
| Global-all setup | 10.148s | 6.556s | 3.592s |
| Local-all | 73.425s | 54.929s | 18.497s (25.2%, 1.337x) |

**Four successful operations total**, two global-all and two local-all, in one
bounded before/after experiment. Not a statistical claim; global setup variability
is not evidence of local index speedup. The earlier independently supplied
path-batching result (103.892 → 69.491s local) is separate evidence, not mixed into
this index-only timing.

Parent's complete local-preflight still lacks a completed summary after a
**599.16s timeout**. No timeout was raised; no local-preflight/global-uninstall/
local-uninstall/local-profiles full matrices were rerun. Full `.8` acceptance
remains pending; this is one bounded performance checkpoint only.
