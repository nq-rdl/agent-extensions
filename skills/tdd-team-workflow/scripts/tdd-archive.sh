#!/usr/bin/env bash
# tdd-archive.sh — Move a completed cycle from active/ to archive/.
# Usage: bash tdd-archive.sh <slug>
# Compatible with reworked TDDCycle schema (2026-03-22)
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: tdd-archive.sh <slug>" >&2
  exit 1
fi

SLUG="$1"

if ! [[ "$SLUG" =~ ^[a-z0-9]([a-z0-9-]{0,38}[a-z0-9])?$ ]]; then
  echo "Error: slug must be lowercase alphanumeric with hyphens, 2-40 chars" >&2
  exit 1
fi

SOURCE=".tdd/active/${SLUG}.yaml"

if [ ! -f "$SOURCE" ]; then
  echo "Error: ${SOURCE} does not exist" >&2
  exit 1
fi

if [ ! -d .tdd/archive ]; then
  echo "Error: .tdd/archive/ does not exist — run tdd-init.sh first" >&2
  exit 1
fi

CYCLE=$(grep '^cycle:' "$SOURCE" | awk '{print $2}')

if [ -z "$CYCLE" ]; then
  echo "Error: could not read cycle number from ${SOURCE}" >&2
  exit 1
fi

if ! [[ "$CYCLE" =~ ^[0-9]+$ ]]; then
  echo "Error: could not parse cycle number from ${SOURCE}" >&2
  exit 1
fi

DEST=".tdd/archive/${SLUG}-c${CYCLE}.yaml"
mv "$SOURCE" "$DEST"
echo "Archived ${SOURCE} → ${DEST}"
