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

echo "Materializing into $OUTPUT_DIR"
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

for src in plugins .gemini opencode pidev; do
  [ -d "$src" ] || continue
  echo "  → $src/"
  rsync -rL "$src/" "$OUTPUT_DIR/$src/"
done

# Sanity check: rsync -L should have left zero symlinks behind.
remaining=$(find "$OUTPUT_DIR" -type l 2>/dev/null | wc -l)
if [ "$remaining" -gt 0 ]; then
  echo "::error::Materialization left $remaining symlink(s) behind:" >&2
  find "$OUTPUT_DIR" -type l >&2
  exit 1
fi

# Sanity check: no broken targets (would mean a symlink pointed at a
# missing file in the source tree, which the install would have hit too).
broken=$(find "$OUTPUT_DIR" -xtype l 2>/dev/null | wc -l)
if [ "$broken" -gt 0 ]; then
  echo "::error::Materialization left $broken broken target(s) behind:" >&2
  find "$OUTPUT_DIR" -xtype l >&2
  exit 1
fi

file_count=$(find "$OUTPUT_DIR" -type f 2>/dev/null | wc -l)
echo "Done. $file_count file(s) materialized at $OUTPUT_DIR"
