#!/usr/bin/env bash
# tdd-new.sh — Generate a new TDD cycle YAML file.
# Usage: bash tdd-new.sh <slug> <feature> <test_file> <impl_file> <language> <framework>
set -euo pipefail

if [ $# -lt 6 ]; then
  echo "Usage: tdd-new.sh <slug> <feature> <test_file> <impl_file> <language> <framework>" >&2
  exit 1
fi

SLUG="$1"
FEATURE="$2"
TEST_FILE="$3"
IMPL_FILE="$4"
LANGUAGE="$5"
FRAMEWORK="$6"

if ! [[ "$SLUG" =~ ^[a-z0-9]([a-z0-9-]{0,38}[a-z0-9])$ ]]; then
  echo "Error: slug must be lowercase alphanumeric with hyphens, 2-40 chars" >&2
  exit 1
fi

if [ -f .tdd/config.yaml ]; then
  ST_RAW=$(grep '^state_tracking:' .tdd/config.yaml | awk '{print $2}' || true)
  if [ "$ST_RAW" = "false" ]; then
    echo "Feature: ${FEATURE}"
    echo "Slug: ${SLUG}"
    echo "Phase: red"
    echo "Cycle: 1"
    echo "State tracking disabled — cycle not persisted"
    exit 0
  fi
fi

TARGET=".tdd/active/${SLUG}.yaml"

if [ ! -d .tdd/active ]; then
  echo "Error: .tdd/active/ does not exist — run tdd-init.sh first" >&2
  exit 1
fi

if [ -f "$TARGET" ]; then
  echo "Error: ${TARGET} already exists" >&2
  exit 1
fi

FEATURE_ESCAPED="${FEATURE//\"/\\\"}"
TEST_FILE_ESCAPED="${TEST_FILE//\"/\\\"}"
IMPL_FILE_ESCAPED="${IMPL_FILE//\"/\\\"}"
LANGUAGE_ESCAPED="${LANGUAGE//\"/\\\"}"
FRAMEWORK_ESCAPED="${FRAMEWORK//\"/\\\"}"

NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

cat > "$TARGET" <<EOF
feature: "${FEATURE_ESCAPED}"
test_file: "${TEST_FILE_ESCAPED}"
impl_file: "${IMPL_FILE_ESCAPED}"
language: "${LANGUAGE_ESCAPED}"
framework: "${FRAMEWORK_ESCAPED}"

cycle: 1
phase: red

phases: []

created: "${NOW}"
updated: "${NOW}"
EOF

echo "Created ${TARGET}"

OTHER_COUNT=0
for f in .tdd/active/*.yaml; do
  [ -f "$f" ] || continue
  [ "$f" = "$TARGET" ] && continue
  OTHER_COUNT=$((OTHER_COUNT + 1))
done
if [ "$OTHER_COUNT" -gt 0 ]; then
  echo "Note: ${OTHER_COUNT} other active cycle(s) — use /tdd-team.list to see all"
fi
