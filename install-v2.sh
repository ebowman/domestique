#!/bin/bash -p
# This replaces the historical package bootstrap for docs/v2-preview.md only.
set -eu
if ! command -v python3 >/dev/null 2>&1 ||
   { [[ "$OSTYPE" == darwin* ]] && [[ "$(command -v python3)" == /usr/bin/python3 ]]; }; then
    echo "domestique-preview: provide an existing Python 3.9+ (not the macOS developer-tools stub); nothing was installed." >&2
    exit 1
fi
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
exec python3 -I -S -B "$here/preview/install.py" "$@"
