# Portable policy review (hq-iyu.4)

Independently read the four original ignored local policies and compared their
SHA-256 to `hq-iyu.1-preservation/manifest.json` and `original-files-before.json`.
They are absent from baseline `19deeab`; preserved source material, not installed
Claude configuration or imported experimental runtime.

| Original local source | SHA-256 |
| --- | --- |
| `.claude/commands/decompose.md` | `3160002319c36f1e815ea55684b11407b646c4b494b1856db3eb4ff1f01ff847` |
| `.claude/commands/goal.md` | `90c77aeaa5b51a07e5e5ee6bc46954e75e6dbf837ea0fb69b757dc800f507a69` |
| `.claude/agents/implementer.md` | `d50fdb9a7bec1d457ea21547038985a46965b02e0b71416fde6969ccfb1e9e8c` |
| `.claude/agents/reviewer.md` | `ed4ed88a3d16684dc4f9733d66753af86d3d6d91349c12c34666e97acb793631` |

Portable intent retained: bounded dependency-ordered plans without coding;
one assigned implementer; fresh reviewer inspecting actual diff/tests; explicit
epic-only sequential goal, dedicated branch, one reviewed commit/bead, one fix
pass, hard ceiling, no push/merge, terse factual reports.

Adaptations: remove vendor/model metadata and guest/legacy installer coupling.
Use relevant task tests/lint, not full historical suites. Exact reviewed-path
staging replaces broad staging. No-ready with unfinished descendants is BLOCKED,
not epic complete. Ordinary entry stops after one bead; only actual explicit
Domestique goal plus epic can authorize a loop (one bead by default, never more
than 15 per explicit bounded session). Remove automatic export/database commits,
backend debugging and queue-draining/session-close authority. Claim/commit/close
belong to the caller; roles never close unpassed work.

`common.md` plus small entry/role sections are repository-owned shared policy.
Native `.3` creation templates remain byte-identical thin locators. No model
registry, provider schema, private Beads bridge or historical engine is reused.
