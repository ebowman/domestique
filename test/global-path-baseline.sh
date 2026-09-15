#!/bin/bash
# Immutable verbatim helper block from domestique.sh at
# 20b6fe8d924d50c943242dc730725e59ce1ef956, global_stat through global_path.
# Block SHA256: 2b2d7b84a6a91bcdf36b5c0927bdc388e6e1e1aa2094757918d35e41c48b021e
# Intentionally retains the legacy BSD %Lp special-bit omission.
global_stat() {
  if [ "$(uname -s)" = Darwin ]; then stat -f '%u %Lp' "$1"
  else stat -c '%u %a' "$1"; fi
}

# Walk only exact ancestors, never provider directory inventories. System
# ancestors may be root-owned; writable shared ancestors must be sticky.
global_path() {
  local path="$1" boundary="$2" walk="" rest part info owner mode bits parent
  case "$path" in /|/*/|*//*|*/./*|*/../*|*/.|*/..|*[=$'\001'-$'\037'$'\177']*)
    global_fail "noncanonical or non-data path";;
    /*) ;; *) global_fail "absolute paths required";; esac
  rest="${path#/}"
  while [ -n "$rest" ]; do
    part="${rest%%/*}"; walk="$walk/$part"
    [ "$part" = "$rest" ] && rest="" || rest="${rest#*/}"
    [ ! -L "$walk" ] || global_fail "symlinked path component: $walk"
    if [ -e "$walk" ]; then
      [ -z "$rest" ] || [ -d "$walk" ] || global_fail "non-directory parent: $walk"
      info="$(global_stat "$walk")" || global_fail "cannot stat path"
      owner="${info%% *}"; mode="${info#* }"; bits=$((8#$mode))
      case "$walk/" in "$boundary/"*)
        [ "$owner" = "$G_UID" ] || global_fail "unowned path: $walk"
        [ $((bits & 022)) -eq 0 ] || global_fail "writable by others: $walk"
        if [ "${G_READONLY:-0}" = 1 ]; then
          [ $((bits & 0400)) -ne 0 ] && [ -r "$walk" ] || global_fail "unreadable path: $walk"
        else
          [ $((bits & 0600)) -eq 384 ] || global_fail "owner read/write permissions required: $walk"
          [ -r "$walk" ] && [ -w "$walk" ] || global_fail "unreadable/unwritable path: $walk"
        fi
        ;;
        *)
          [ "$owner" = 0 ] || [ "$owner" = "$G_UID" ] || global_fail "unsafe ancestor owner: $walk"
          [ $((bits & 022)) -eq 0 ] || {
            [ -d "$walk" ] && [ $((bits & 01000)) -ne 0 ] && [ "$owner" = 0 ] ||
              global_fail "unsafe writable ancestor: $walk"
          }
          ;;
      esac
      [ ! -d "$walk" ] || [ -x "$walk" ] || global_fail "unsearchable directory: $walk"
      [ -f "$walk" ] || [ -d "$walk" ] || global_fail "unsupported filesystem object: $walk"
    else
      parent="${walk%/*}"; [ -n "$parent" ] || parent=/
      if [ -e "$parent" ]; then
        [ -d "$parent" ] && { [ "${G_READONLY:-0}" = 1 ] || [ -w "$parent" ]; } && [ -x "$parent" ] ||
          global_fail "cannot create under parent: $parent"
      fi
    fi
  done
}
