"""Source-only installer entry; selected runtime bytes always come from Git."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from machine import Refusal, install, parse_pairs

USAGE = """Usage: install-v2.sh --source CHECKOUT --ref REV
       install-v2.sh help | --help
Both selections are required. Trusted local Git only; no download or migration.
Requires existing Bash, Git and Python 3.9+. Installs no dependencies or aliases.
Machine lifecycle only: no project, native client, model or Beads operations."""


def main(args):
    try:
        if args in (["help"], ["--help"]):
            print(USAGE)
            return 0
        values = parse_pairs(args, ("--source", "--ref"))
    except ValueError as exc:
        print(f"{exc}\n{USAGE}", file=sys.stderr)
        return 2
    try:
        changed, revision = install(values["--source"], values["--ref"])
        print(f"domestique-preview {'installed' if changed else 'unchanged'} {revision}")
        return 0
    except (Refusal, OSError, ValueError) as exc:
        print(f"domestique-preview: refused: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
