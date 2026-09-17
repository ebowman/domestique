"""The installed command surface travels with the selected Git revision."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from machine import Refusal, check_install, parse_pairs, update
from native import DEFINITIONS
from project import arguments as project_arguments, operate

HELP = """Usage: domestique2 [help | --help | version | --version]
       domestique2 update --ref REV
       domestique2 enable [TARGET] [--dry-run]
       domestique2 disable [TARGET] [--dry-run]
Update uses the recorded trusted LOCAL Git checkout; no fetch from a remote.
Existing Bash, Git and Python 3.9+ required; dependencies are never installed.
Project TARGET defaults to cwd; must be the exact physical Git worktree root.
Copilot definitions only; edited files preserved, partial disable returns 1.
inspect and --inspect are reserved and unavailable.
workflow TYPE --project ROOT is reserved; Copilot/Beads workflows are NOT READY.
No native global definitions, startup, PATH, alias, model or Beads setup."""


def main(args):
    try:
        ref = None
        if not args or args in (["help"], ["--help"], ["version"], ["--version"]):
            command = args[0] if args else "help"
        elif args[0] == "update":
            command = "update"
            ref = parse_pairs(args[1:], ("--ref",))["--ref"]
        elif args[0] in ("enable", "disable"):
            command = args[0]
            target, dry_run = project_arguments(args[1:])
        elif args[0] == "workflow":
            command = "workflow"
            if (len(args) != 4 or args[1] not in DEFINITIONS or args[2] != "--project" or
                    not args[3] or not Path(args[3]).is_absolute()):
                raise ValueError("expected workflow TYPE --project ABSOLUTE_ROOT")
        elif args[0] in ("inspect", "--inspect"):
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
        elif command in ("enable", "disable"):
            code, message = operate(command, target, dry_run, root, receipt)
            print("domestique-preview: " + message, file=sys.stderr if code else sys.stdout)
            return code
        elif command == "workflow":
            print("domestique-preview: workflow unavailable; forthcoming hq-iyu.4; "
                  "definitions are not operational workflow readiness.", file=sys.stderr)
            return 1
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
