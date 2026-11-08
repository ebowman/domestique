# Historical installer identities

Offline qualification data. The installer consumes only a compact generated
projection, not this provenance document or JSON at runtime. Uses Python's
standard library and existing system shell/Git utilities. Run from the repository:

```sh
python3 tools/historical-identities.py \
  --ref 067569a331539883c326a5d221e0e5837efefddd \
  --allowlist-ref 77e75c74667846475c0205856b423c3882122a76 \
  --output tools/historical-identities.json
python3 test/historical-identities.py
```

`--ref` defaults to `main`, and `--allowlist-ref` to `HEAD`; both resolve once to
immutable commits. For independent reproduction, use the pinned values above,
write a second output into a temporary directory, and compare with `cmp`.
Progress and runtime go to stderr, never into generated JSON. Exit 1 means
recorded historical failures or a missing required policy, **not** that failed
cases were skipped. Unexpected generator errors abort without publishing data.

## Embedded lookup (format 1)

Regenerate only the compact block, without replaying historical installers:

```sh
python3 tools/historical-identities.py --emit-lookup domestique.sh \
  --history-data tools/historical-identities.json --current-source domestique.sh
python3 test/historical-identities.py
```

`--current-source` is required explicitly. It executes that source in fresh
isolated `all` normal/guest installs using the same offline harness. The block
between `BEGIN/END GENERATED HISTORICAL IDENTITIES` contains a shared Python
payload: sorted `(provider, path, install-mode)` keys and exact SHA-256 sets.
It is emitted into the installer's existing shared inventory library, and used
directly by `policy_legacy_base`. There is no runtime repository, generator,
JSON, external helper, or provenance-file dependency; stdin/curl installation
remains self-contained.

**Legacy-base authority is unchanged.**
The reserved `@legacy-policy-base/*` keys contain exactly the original 20
provider-bound hashes. Their provider-only predicate is deliberately unchanged:
the existing caller still supplies all path/mode routing, inventory, pristine
base, safe-path, guard and guest-mode requirements. Neither the larger set of
historical policies nor current guarded policies enters that legacy predicate.

Pre-snapshot policy recovery now separately uses the exact provider/path/mode
lookup on the raw live block body. With no provider snapshot state, a matching
unguarded body can supply an ephemeral historical merge base; edited, unknown,
guard-tampered or misrouted bodies cannot. Existing state still requires its
authoritative base/inventory; this is not missing-base repair. Guest and safe-path
checks remain mandatory, including for `--force` and `--dry-run`.

An unselected policy receives only its harness guard, preserving outside bytes;
its published base is guard plus proven historical body, not today's workflow.
Its new manifest owns **only that policy**, never untouched roles, commands,
helpers or backups. The real `e12f0fc` fixture supports initial Copilot preview
and apply; `067569a` is the refusing negative control. Selected legacy
role/command adoption and subsequent ownership/rerun integration remain hq-dds.6
work. This policy half is not a standalone release or a full Claude upgrade.
Selected pre-snapshot policy recovery requires fresh native inventory destinations:
existing roles, commands or helpers are refused before writes in Git roots,
subdirectories and non-Git targets, including with `--force` or `--dry-run`.
The policy identity alone never proves ownership of those native files.

Projection rules:

* Historical evidence comes only from output sets referenced by successful
  runs, with their set hashes verified. Failed/unsupported partial artifacts,
  orphan sets, and the normalized grouping index confer no authority.
* Include raw policy **body** identities and raw roles, commands and skills
  (`.md`, `.toml`, `.yaml` under `agents`, `commands`, or `skills`).
  Retain every historical identity in that scope, including obsolete paths and
  Codex-owned shared aliases; never reassign their provider or install mode.
* Exclude every normalized role identity (`model_marker_project`), without
  stripping markers or treating normalized pair/project metadata as raw bytes.
  These identities remain in the full historical evidence unchanged.
* Current membership covers actual fresh policy bodies and role/command/skill
  emissions in both modes. For the three marked implementers, use the actual
  **unmarked pristine snapshot bytes** emitted by the installer, not normalized
  live roles or reconstructed marker-stripped content. Assert those pristine
  files have no model marker. Other current payloads use exact installed bytes.
  This is the existing pristine-base product contract, not authority to accept
  arbitrary marked live files, custom models, or arbitrary role pairs.
* Explicitly exclude model-setup Python helpers, manifest/state/receipt data,
  Git excludes, and the installer/generated-library source itself. Helpers and
  generated libraries may carry embedded identities; hashing those into their
  own authority would create a self-reference. Their existing ownership proofs
  are unchanged. No wildcard whole-tree membership assertion is used.
* Missing original policy allowlist hashes abort projection rather than silently
  dropping entries. Current emissions are additive and cannot remove historical
  identities.

The focused tests regenerate the exact block from checked-in history plus the
working-tree source, and check both HEAD and working-tree current membership.
Emitter changes in the authority scope therefore require regeneration. Tests
also check complete raw historical retention, exact legacy predicate equality,
unknown hashes, provider/path/mode mismatches, normalized-role refusal, failed
partial evidence exclusion, and the shell wrapper's exact byte hashing.
The history qualification below remains unchanged; projection does not rerun
or claim to repair its 232 failed fixtures.

## Coverage and evidence

* `history`: every `git log --full-history --topo-order --reverse REF --
  domestique.sh` entry, including side-branch changes and merges. No checkout.
  Identical installer blobs execute once, retaining **all** commit provenance.
  First/last refer to this topological order, not commit timestamps.
* `runs`: actual executions for no selector, `claude`, `codex`, `copilot`, `both`,
  and `all`, each in normal and `--guest` mode. Preview combination selectors
  `claude-copilot` and `codex-copilot` also execute when present in the parser.
  Capability detection uses actual CLI rejection, never an assumed successful
  fallback or an edited emitter. Unknown errors and timeouts are failures;
  failures retain exit status, diagnostics, and any partial artifacts but
  contribute **no** ownership identities or successful output sets.
* `identities`: finite provider/path/mode/content SHA-256 identities, with first,
  last, and complete matching commit provenance. Roles, commands, skills, helper
  scripts, and substantive model metadata retain their exact bytes (the
  validated model-marker project path is normalized as described below).
  Policy identity is the **managed block body**, using the installer's whole-line
  marker/awk-print semantics (no markers, every body line terminated by LF).
  Malformed or duplicate markers fail. Original `.agents/skills/domestique*`
  files belong to Codex; later shared `.agents` files use provider `shared`.
* `output_sets`: distinct complete changed-file inventories, including snapshot
  state and guest excludes, indexed by SHA-256 of their canonical JSON.
  Each successful run links to its set and records replayable blob, commits,
  selector, arguments, and mode; the document records host platform. Each file
  records permissions and a whole-file output hash, independently of its
  ownership identity. Initial Git files are baseline, not installer output.
* `allowlist` and `unreproduced_allowlist`: every literal hash from
  `policy_legacy_base` at the pinned authority commit, compared by provider
  against reproduced policy bodies. The required `5211df2a...bac5d` body is
  checked separately. Missing hashes remain visible; no guessed bytes enter
  the inventory.

There are exactly two content normalizations:

1. The single UTC `installed_at` field of `*/.domestique/manifest` becomes
   `installed_at=<UTC-INSTALL-TIME>`.
2. The `project` field in an installer-written `# domestique-model-setup:` marker
   becomes `<PHYSICAL-PROJECT-ROOT>`. Only the three known implementer paths are
   eligible. Before normalization the marker must occupy the expected line,
   occur exactly once, have canonical JSON and the exact v1 key set, match the
   provider and actual physical project root, and attest both the unmarked
   implementer and actual reviewer SHA-256. Invalid markers fail. The marker is
   **not removed**: both attestation hashes, harness, version, all model fields,
   and every other role byte are preserved. Such normalized identities are
   explicitly labeled `model_marker_project`; they are not raw-byte allowlist
   entries suitable for use without the same strict validation.

Manifest script digests, versions, refs, inventories, all substantive payloads,
and model values are preserved. State metadata participates in whole-output
sets, **not** the payload ownership allowlist. Sandbox paths in diagnostics
become `<SANDBOX>`; diagnostic substitutions never touch artifact bytes.

## Isolation and limits

Each execution gets a new temporary Git repository, empty Git template, HOME,
XDG directories, TMPDIR, and an environment constructed from scratch. Git
system/global configuration and prompts are disabled. The installer is obtained
with `git show`, written outside any repository, and executed unmodified.
Its `installed_ref=unknown` is therefore genuine, not this tool's repository HEAD;
`script_sha256` still attests the actual historical installer.

PATH contains only explicitly allowlisted system utilities, the running Python,
and failing/logging stubs for network, package-manager, Beads, and native-client
commands. Even a swallowed stub error fails qualification. No `--with-beads`,
native model setup, dependency installation, host configurations, consumer
projects, or user-provided files are involved. Unknown output paths and writes
to isolated HOME/XDG directories fail rather than disappearing from evidence.
This is isolation of **audited repository history**, not a sandbox for arbitrary
untrusted shell programs.

Every subprocess has a deadline (default 60 seconds); timed-out process groups
are killed and scratch directories cleaned. Replays are serial within a run;
the independent determinism check used two generators concurrently, at most
two installers. Current normal/guest entrypoints are exercised as they actually
existed: private-preview versions requiring a separately installed global core
fail explicitly in the fresh environment. The generator does not bootstrap
that different lifecycle, patch the installer, or synthesize successful output.

## Qualification

Two final independent full-history runs on Darwin with Python **3.14.7**
produced **byte-identical** data after strict project-marker normalization.
No generator correction was needed in this final qualification. The runs
executed concurrently, each with its own fresh scratch repositories, using
these exact commands from the repository root (default subprocess timeout: 60s):

```sh
python3 tools/historical-identities.py --ref 067569a331539883c326a5d221e0e5837efefddd --allowlist-ref 77e75c74667846475c0205856b423c3882122a76 --output /tmp/domestique-history-proof.IgMgMp/first.json
python3 tools/historical-identities.py --ref 067569a331539883c326a5d221e0e5837efefddd --allowlist-ref 77e75c74667846475c0205856b423c3882122a76 --output /tmp/domestique-history-proof.IgMgMp/second.json
cmp /tmp/domestique-history-proof.IgMgMp/first.json /tmp/domestique-history-proof.IgMgMp/second.json
cp /tmp/domestique-history-proof.IgMgMp/first.json tools/historical-identities.json
cmp tools/historical-identities.json /tmp/domestique-history-proof.IgMgMp/second.json
```

The temporary directory was created with
`mktemp -d /tmp/domestique-history-proof.XXXXXX`; use a new directory when
reproducing. Both `cmp` checks passed. First/second runtimes were
**3973.345 / 3972.820 seconds**. Both generators exited **1**, intentionally
reporting the retained historical failures below rather than hiding them.
Each enumerated **96 changing commits / 82 installer blobs / 1,048 cases**:
**509 successes / 307 explicit unsupported cases / 232 failures**,
yielding **423 distinct output sets / 437 ownership identities**.
Identity counts by provider are Claude **165**, Codex **135**, Copilot **89**,
shared **48**. All changing-commit provenance remains in the dataset, including
commits sharing a blob. The published file is **6,506,008 bytes**, SHA-256:

```text
587946287030388b82f8ae001ce80bd3c7edc9029fc07fd339029b7b9d2d4103
```

All **20** pinned policy allowlist entries were reproduced (**14/14 Claude,
6/6 Codex**; no Copilot allowlist at this authority ref). Reproduced distinct
policy-body hashes are **31 Claude / 13 Codex / 8 Copilot**, a provider-specific
superset of that allowlist. `unreproduced_allowlist` is empty for both providers.
The required
`5211df2a6c2c03d7ec6d385a0c204ea2e79fc9aaa2855406ec8bd0cf791bac5d`
is present. No policy bytes are normalized; normalized role identities remain
explicitly labeled and require the strict validation described above, not
unconditional raw-hash adoption.

### Complete case accounting

Counts are actual blob executions; each execution carries all matching commits.
Only Darwin was qualified; this is not a cross-OS qualification.

| Selector | Normal: success / unsupported / failure | Guest: success / unsupported / failure |
| --- | ---: | ---: |
| default | 68 / 0 / 14 | 53 / 15 / 14 |
| claude | 43 / 25 / 14 | 43 / 25 / 14 |
| codex | 43 / 25 / 14 | 43 / 25 / 14 |
| copilot | 35 / 33 / 14 | 31 / 33 / 18 |
| both | 43 / 25 / 14 | 43 / 25 / 14 |
| all | 34 / 34 / 14 | 30 / 34 / 18 |
| claude-copilot | 0 / 2 / 14 | 0 / 2 / 14 |
| codex-copilot | 0 / 2 / 14 | 0 / 2 / 14 |

Every failed case is recorded individually in JSON `runs`, including blob,
full commit provenance, selector, mode, arguments, exit code, stdout/stderr,
timeout flag, errors, and partial artifacts. None contributes ownership
identities or successful output sets. The complete failure grouping is:

* **8 cases:** `copilot/guest` and `all/guest` at each of
  `58f4d299e62bc573ad4571fd65aca44394c36d1e`,
  `46ae60dc1eab77d67c2ead92766d70e5ad7a79f3`,
  `c01962d4d242365cf9a3bdb2312a55961adf2d95`,
  `b60feef4d0d41b8d99b7afec68dd5e6ef648b027`.
  Historical installers exit 1 with “Copilot guest install or conversion is
  not supported yet; no files were changed.” These are conservatively retained
  as failures, not CLI-unsupported cases.
* **224 cases:** all eight selectors in both modes at each of
  `3aa5798c81886bc11e03b698c8549da336ffb8c7`,
  `7ca8d86436d9c47359d71e694034ddf220a747f1`,
  `67018f3c4fec609929b8d03f373da5ed553500b5`,
  `d51de169608d135eb773c27d3716048d096e6b28`,
  `ef1ceb33a2abe0bdab8a9b405087d9daaaca8649`,
  `074e6e58a543bd9a019c5eacf6bde34244f9204c`,
  `20b6fe8d924d50c943242dc730725e59ce1ef956`,
  `0a34d678193186cd656d6ff1bfe04bef1e1e1793`,
  `974493d5b7753c5967cc84f5965fe1c89a4cf5ff`,
  `38fd3e8923b2cab2a4da505d3e586bddeb2b6ff3`,
  `56e1454fdbe6fcd0bf3b2523c2f978b7e01ed8c1`,
  `096c72f10a3b5d60d5a4afe4f4c3a6cfd38819a2`,
  `c7c3d366b50684c5901b06d094d53ff28b2e97ec`,
  `020c05c563ab9ed9b7dc27bc74cbe3dc35a9399d`.
  These private-local previews exit 1 because the fresh environment lacks
  their required global core/manifest (112 normal, 112 guest; guest also warns
  it is a deprecated no-op). No global installation was performed.

All 232 failures have exit code 1, no timeout, and no generator validation
errors. No dependency stub invocations or isolated HOME/XDG writes occurred.

### Final checks

```sh
python3 test/historical-identities.py
python3 -m py_compile tools/historical-identities.py test/historical-identities.py
shellcheck --severity=warning domestique.sh update.sh test/*.sh
git --no-pager diff --check
```

All pass: **10 focused behavior tests plus the checked-in-data test (11 total)**,
Python syntax, warning-level ShellCheck **0.11.0**, and whitespace checks.
Baseline informational ShellCheck findings are not blockers; no installer
changes or lint suppressions were made. The huge project baseline was not run
for this tool-only task. Dataset generation does not embed identities, change
adoption authority, or implement an upgrade matrix.
