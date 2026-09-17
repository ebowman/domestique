#!/bin/bash -p
# Stable indirection only: command grammar and behavior belong to the revision.
set -eu
if ! command -v python3 >/dev/null 2>&1 ||
   { [[ "$OSTYPE" == darwin* ]] && [[ "$(command -v python3)" == /usr/bin/python3 ]]; }; then
    echo "domestique-preview: provide an existing Python 3.9+ (not the macOS developer-tools stub); nothing was installed." >&2
    exit 1
fi
exec python3 -I -S -B -c '
import os, pathlib, re, runpy, sys
if sys.version_info < (3, 9):
    sys.exit("domestique-preview: provide an existing Python 3.9+; nothing was installed.")
root = pathlib.Path(sys.argv[1])
sys.argv = sys.argv[2:]
try:
    target = os.readlink(root / "current")
    if not re.fullmatch(r"releases/([0-9a-f]{40}|[0-9a-f]{64})", target):
        raise ValueError("invalid current pointer")
    source = root / target
    runpy.run_path(str(source / "preview/cli.py"), run_name="__main__")
except (OSError, ValueError) as exc:
    sys.exit("domestique-preview: refused: " + str(exc))
' @ROOT@ "$0" "$@"
