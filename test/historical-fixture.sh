#!/usr/bin/env bash
# shellcheck disable=SC2034 # DOM/UPDATER are the sourcing harness's public API.
# Sourced only by historical regression harnesses. These tests preserve the
# retired merge/normal/guest formats as OFFLINE fixtures, not production CLI
# acceptance. Current replacements: local-profiles, local-preflight, global,
# private-core. No network or checkout mutation.
git -C "$SCRIPT_DIR/.." show b60feef:domestique.sh > "$WORKROOT/historical-domestique.sh" || exit 1
git -C "$SCRIPT_DIR/.." show b60feef:update.sh > "$WORKROOT/historical-update.sh" || exit 1
chmod +x "$WORKROOT/historical-domestique.sh" "$WORKROOT/historical-update.sh"
DOM="$WORKROOT/historical-domestique.sh"
UPDATER="$WORKROOT/historical-update.sh"
export HOME="$WORKROOT/historical-home"
mkdir -p "$HOME"
echo "HISTORICAL b60feef fixture coverage (not current production CLI)"
