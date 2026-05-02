#!/usr/bin/env bash
# tdd-cancel.sh — Cancel an active TDD cycle with confirmation.
# Usage: bash tdd-cancel.sh [slug]
set -euo pipefail

trim() {
  local value="${1-}"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "$value"
}

strip_yaml_scalar() {
  local value
  value=$(trim "${1-}")

  if [ "${value#\"}" != "$value" ] && [ "${value%\"}" != "$value" ]; then
    value="${value#\"}"
    value="${value%\"}"
    value="${value//\\\"/\"}"
  fi

  printf '%s' "$value"
}

detect_single_active_slug() {
  local count=0
  local slug=""
  local f
  local slugs=()

  for f in .tdd/active/*.yaml; do
    [ -f "$f" ] || continue
    slug=$(basename "$f" .yaml)
    slugs+=("$slug")
    count=$((count + 1))
  done

  if [ "$count" -eq 0 ]; then
    echo "Error: no active TDD cycles found" >&2
    exit 1
  fi

  if [ "$count" -gt 1 ]; then
    echo "Error: multiple active TDD cycles found — specify a slug:" >&2
    for slug in "${slugs[@]}"; do
      echo "  - ${slug}" >&2
    done
    exit 1
  fi

  printf '%s\n' "${slugs[0]}"
}

if [ $# -gt 1 ]; then
  echo "Usage: bash tdd-cancel.sh [slug]" >&2
  exit 1
fi

# State tracking guard
if [ -f .tdd/config.yaml ]; then
  ST_RAW=$(grep '^state_tracking:' .tdd/config.yaml | awk '{print $2}' || true)
  if [ "$ST_RAW" = "false" ]; then
    echo "State tracking is disabled — enable it in \`.tdd/config.yaml\` to use this command"
    exit 0
  fi
fi

if [ ! -d .tdd/active ]; then
  echo "Error: .tdd/active/ does not exist — run tdd-init.sh first" >&2
  exit 1
fi

if [ $# -eq 1 ]; then
  SLUG="$1"
else
  SLUG=$(detect_single_active_slug)
fi

if ! [[ "$SLUG" =~ ^[a-z0-9]([a-z0-9-]{0,38}[a-z0-9])?$ ]]; then
  echo "Error: slug must be lowercase alphanumeric with hyphens, 1-40 chars" >&2
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

printf "Cancel active cycle '%s'? (y/N)" "$SLUG"
read -r CONFIRM || true

case "$CONFIRM" in
  y|Y)
    ;;
  *)
    echo "Cancelled — no changes made"
    exit 0
    ;;
esac

NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
sed -i \
  -e 's/^phase:[[:space:]]*.*/phase: cancelled/' \
  -e "s|^updated:[[:space:]]*.*|updated: \"${NOW}\"|" \
  "$SOURCE"

DEST=".tdd/archive/${SLUG}-c${CYCLE}.yaml"
mv "$SOURCE" "$DEST"
echo "Cancelled and archived: ${SLUG}"
