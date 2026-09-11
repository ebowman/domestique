#!/usr/bin/env bash
# Current production CLI/runtime acceptance; no native clients or network.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
PYTHONDONTWRITEBYTECODE=1 python3 "$ROOT/test/local-profiles.py"
