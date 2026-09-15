#!/usr/bin/env bash
# Verbatim local_untracked from domestique.sh at
# 20b6fe8d924d50c943242dc730725e59ce1ef956. Never refresh from mutable HEAD.
local_untracked() (
  set -o pipefail
  local root="$1" candidate="$2" exact=0
  [ -z "${GIT_DIR+x}${GIT_WORK_TREE+x}${GIT_COMMON_DIR+x}${GIT_INDEX_FILE+x}" ] ||
    { local_fail "unset Git directory/index routing overrides before proving actual ownership"; return 1; }
  while :; do
    # The destination excludes its entire subtree. Ancestors only collide
    # when they are index OBJECTS, not directories with unrelated host leaves.
    # NUL framing and literal pathspecs preserve arbitrary indexed filenames.
    git -C "$root" ls-files -z -- ":(literal)$candidate" | (
      local indexed=""
      while IFS= read -r -d '' indexed; do
        if [ "$exact" = 0 ] || [ "$indexed" = "$candidate" ]; then
          local_fail "tracked/indexed destination or ancestor: $root/$candidate"
          exit 1
        fi
      done
      [ -z "$indexed" ]
    ) || { local_fail "index validation failed: $root/$candidate"; return 1; }
    case "$candidate" in */*) candidate="${candidate%/*}"; exact=1;; *) break;; esac
  done
)
