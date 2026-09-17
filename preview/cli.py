"""The installed command surface travels with the selected Git revision."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from machine import Refusal, check_install, parse_pairs, update

HELP = """Usage: domestique2 [help | --help | version | --version]
       domestique2 update --ref REV
Update uses the recorded trusted LOCAL Git checkout; no fetch from a remote.
Existing Bash, Git and Python 3.9+ required; dependencies are never installed.
enable, disable, inspect and --inspect are reserved and unavailable.
Machine lifecycle only; project/Copilot/Beads workflows are NOT READY.
No project, native global definitions, startup, PATH or alias edits."""


def main(args):
    try:
        ref = None
        if not args or args in (["help"], ["--help"], ["version"], ["--version"]):
            command = args[0] if args else "help"
        elif args[0] == "update":
            command = "update"
            ref = parse_pairs(args[1:], ("--ref",))["--ref"]
        elif args[0] in ("enable", "disable", "inspect", "--inspect"):
            if len(args) > 2 or (len(args) == 2 and
                                 (not args[1] or args[1].startswith("-"))):
                raise ValueError("expected at most one literal target")
            print(f"domestique-preview: {args[0]} unavailable; forthcoming task, no activation.",
                  file=sys.stderr)
            return 1
        else:
            raise ValueError("unsupported arguments")
    except ValueError as exc:
        print(f"{exc}\n{HELP}", file=sys.stderr)
        return 2
    # __file__ is already the immutable path selected once by the launcher.
    source = Path(__file__).parent.parent
    root = source.parent.parent
    try:
        receipt = check_install(root, source)
        if command == "update":
            changed, revision = update(root, source, receipt, ref)
            print(f"domestique-preview {'updated' if changed else 'unchanged'} {revision}")
        elif command in ("version", "--version"):
            print(f"domestique-preview {source.name}")
        else:
            print(HELP)
        return 0
    except (Refusal, OSError, ValueError) as exc:
        print(f"domestique-preview: refused: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
