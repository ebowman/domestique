# domestique

A one-command installer for a **Claude Code orchestration config**: an
orchestrator/implementer workflow backed by [beads](https://github.com/steveyegge/beads)
issue tracking.

It drops three files into a target repo:

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Orchestration policy — the main session plans & delegates, it doesn't implement. Installed inside a managed block so it coexists with your own `CLAUDE.md` content. |
| `.claude/agents/implementer.md` | An `implementer` subagent (Sonnet) that executes one bounded task at a time and reports back a terse summary. |
| `.claude/commands/decompose.md` | A `/decompose` command that turns a goal or spec into a beads epic with dependency-ordered tasks. |

## Install

### One-liner (into the current directory)

```sh
curl -fsSL https://raw.githubusercontent.com/ebowman/domestique/main/domestique.sh | bash
```

Preview without touching anything:

```sh
curl -fsSL https://raw.githubusercontent.com/ebowman/domestique/main/domestique.sh | bash -s -- --dry-run
```

Into a specific repo, and initialize beads too:

```sh
curl -fsSL https://raw.githubusercontent.com/ebowman/domestique/main/domestique.sh | bash -s -- ~/path/to/repo --with-beads
```

### Clone (recommended for reuse across machines)

```sh
git clone https://github.com/ebowman/domestique.git ~/.local/share/domestique
ln -sf ~/.local/share/domestique/domestique.sh ~/.local/bin/domestique.sh
alias dom="$HOME/.local/bin/domestique.sh"   # add to ~/.zshrc or ~/.bashrc
```

Then, in any repo:

```sh
dom                 # install into the current directory
dom --dry-run       # preview the changes
dom ~/other/repo    # install elsewhere
```

## Usage

```
domestique.sh [TARGET_DIR] [options]

Options:
  --dry-run      Print planned changes; touch nothing.
  --with-beads   If `bd` is on PATH: `bd init` (only when no .beads/) then
                 `bd setup claude`. If `bd` is absent, note it and skip.
  --force        Overwrite differing .claude/ files without a .bak backup.
                 (CLAUDE.md is ALWAYS backed up before modification.)
  --help, -h     Show this help.
```

## Safety & idempotency

- **Your `CLAUDE.md` survives.** If it exists without markers, the managed
  block is appended and every existing byte is preserved verbatim. If it
  already has the markers, only the content between them is replaced.
- **Backups.** Any existing file that would change is copied to
  `<file>.bak.<timestamp>` first. `CLAUDE.md` is *always* backed up before
  modification, even under `--force`.
- **Run it twice** and the second run makes no changes (and creates no new
  backup).
- **`--dry-run`** computes and prints the full plan while touching nothing.

The installer is a single self-contained bash script with the three config
files embedded — no network access needed beyond fetching the script itself.

## License

MIT — see [LICENSE](LICENSE).
