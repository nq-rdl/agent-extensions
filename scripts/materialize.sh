#!/bin/bash
# Materialize host plugin/extension trees by dereferencing symlinks.
#
# On `main`, plugins/<bundle>/skills/<name> and similar paths under
# .gemini/, opencode/, pidev/ are symlinks pointing OUTSIDE the plugin
# root (into the skills/ submodule or agents/). Hosts like Claude Code
# install plugins by `cp -R`'ing the plugin source into a cache dir,
# which preserves the symlinks verbatim — and because the targets sit
# above the plugin root, every link dangles in the cache. See issue #79.
#
# This script produces a self-contained tree at OUTPUT_DIR (default
# dist/release/) where every symlink has been replaced by a copy of
# the file or directory it pointed to. The release workflow force-
# pushes that tree to the `release` branch; user-facing install paths
# (marketplace.json sources) point at that branch via git-subdir, so
# `cp -R` of any plugin subtree resolves to real files.
#
# Usage:
#   scripts/materialize.sh [OUTPUT_DIR]

set -euo pipefail

OUTPUT_DIR="${1:-dist/release}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# Refuse to operate on dangerous paths. `rm -rf "$OUTPUT_DIR"` below
# would otherwise happily delete /, the repo root, or anything outside
# the repo if a caller passes a typo or absolute path.
case "$OUTPUT_DIR" in
  ""|"/"|"."|"..") echo "::error::Refusing to materialize into '$OUTPUT_DIR'." >&2; exit 1 ;;
  *..*) echo "::error::OUTPUT_DIR may not contain '..' segments (got: $OUTPUT_DIR)." >&2; exit 1 ;;
esac
case "$OUTPUT_DIR" in
  /*) abs_output="$OUTPUT_DIR" ;;
  *)  abs_output="$REPO_ROOT/$OUTPUT_DIR" ;;
esac
case "$abs_output" in
  "$REPO_ROOT"|"$REPO_ROOT/") echo "::error::Refusing to materialize into the repo root." >&2; exit 1 ;;
  "$REPO_ROOT"/*) ;;  # ok: inside the repo
  *) echo "::error::OUTPUT_DIR must be inside the repo (got: $abs_output)." >&2; exit 1 ;;
esac

echo "Materializing into $OUTPUT_DIR"
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

# rsync -a preserves permissions (incl. the executable bit on hooks
# and scripts) and timestamps; -L dereferences symlinks so the output
# tree is self-contained.
for src in plugins .gemini opencode pidev; do
  [ -d "$src" ] || continue
  echo "  → $src/"
  rsync -aL "$src/" "$OUTPUT_DIR/$src/"
done

# Sanity check: rsync -L should have left zero symlinks behind. If any
# survive, materialization is incomplete and the release would ship
# dangling links to users.
remaining=$(find "$OUTPUT_DIR" -type l 2>/dev/null | wc -l)
if [ "$remaining" -gt 0 ]; then
  echo "::error::Materialization left $remaining symlink(s) behind:" >&2
  find "$OUTPUT_DIR" -type l >&2
  exit 1
fi

file_count=$(find "$OUTPUT_DIR" -type f 2>/dev/null | wc -l)
echo "Done. $file_count file(s) materialized at $OUTPUT_DIR"
