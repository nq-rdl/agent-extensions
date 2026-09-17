#!/usr/bin/env bash
# Read-only validation before every agent-mediated checkpoint write.
set -euo pipefail
fail() { echo "$*" >&2; exit 2; }
[ "$#" -eq 2 ] || fail 'usage: checkpoint.sh /absolute/repo /absolute/checkpoint.json'
repo=$1
checkpoint=$2
case "$repo" in /*) ;; *) fail 'repo must be absolute' ;; esac
root=$(git -C "$repo" rev-parse --show-toplevel)
physical=$(cd -- "$root" && pwd -P)
case "$checkpoint" in "$physical"/*) ;; *) fail 'checkpoint must be beneath the physical worktree' ;; esac
relative=${checkpoint#"$physical"/}
case "/$relative/" in *'//'*|*'/./'*|*'/../'*) fail 'checkpoint path must be canonical' ;; esac
# Inspect each component, including dangling symlinks and the final file.
# Reject internal symlinks too: an alias can hide tracked state or another unit.
remaining=$relative
parent=$physical
while :; do
  component=${remaining%%/*}
  candidate=$parent/$component
  [ ! -L "$candidate" ] || fail "checkpoint path contains a symlink: $candidate"
  if [ "$remaining" = "$component" ]; then
    [ ! -e "$candidate" ] || [ -f "$candidate" ] || fail 'checkpoint must be a regular file'
    break
  fi
  [ ! -e "$candidate" ] || [ -d "$candidate" ] || fail 'checkpoint parent is not a directory'
  parent=$candidate
  remaining=${remaining#*/}
done
# Resolve the nearest existing parent before creating any directories.
ancestor=$parent
while [ ! -d "$ancestor" ]; do ancestor=${ancestor%/*}; done
resolved=$(cd -- "$ancestor" && pwd -P)
case "$resolved/" in "$physical/"*) ;; *) fail 'checkpoint parent escapes the physical worktree' ;; esac
[ -z "$(git -C "$physical" ls-files -- "$relative")" ] || fail 'checkpoint must not be tracked'
git -C "$physical" check-ignore -q -- "$relative" || fail 'checkpoint must be ignored; configure its exact path in Git info/exclude before launch'
printf '%s\n' "$checkpoint"
