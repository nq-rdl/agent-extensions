#!/usr/bin/env bash
# tdd-status.sh — Display the current state of active TDD cycles.
# Usage: bash tdd-status.sh [slug]
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

yaml_top_level_value() {
  local key="$1"
  local file="$2"

  awk -v key="$key" '
    index($0, key ":") == 1 {
      sub("^[^:]+:[[:space:]]*", "", $0)
      print
      exit
    }
  ' "$file"
}

yaml_last_phase_value() {
  local key="$1"
  local file="$2"

  awk -v key="$key" '
    function finish_entry() {
      if (entry_started) {
        last = current
      }
      current = ""
    }

    /^phases:[[:space:]]*\[\][[:space:]]*$/ {
      exit
    }

    /^phases:[[:space:]]*$/ {
      in_phases = 1
      next
    }

    in_phases && /^[^[:space:]]/ {
      finish_entry()
      in_phases = 0
      next
    }

    in_phases && /^  - / {
      finish_entry()
      entry_started = 1
      next
    }

    in_phases && entry_started && $0 ~ ("^    " key ":[[:space:]]*") {
      line = $0
      sub("^    " key ":[[:space:]]*", "", line)
      current = line
    }

    END {
      if (in_phases) {
        finish_entry()
      }
      print last
    }
  ' "$file"
}

read_max_cycles() {
  local max_cycles="3"
  local raw=""

  if [ -f .tdd/config.yaml ]; then
    raw=$(awk '
      /^max_cycles:[[:space:]]*/ {
        sub(/^max_cycles:[[:space:]]*/, "", $0)
        print
        exit
      }
    ' .tdd/config.yaml)
    raw=$(strip_yaml_scalar "$raw")
    if [[ "$raw" =~ ^[0-9]+$ ]]; then
      max_cycles="$raw"
    fi
  fi

  printf '%s' "$max_cycles"
}

print_cycle_status() {
  local slug="$1"
  local file="$2"
  local max_cycles="$3"
  local feature
  local phase
  local cycle
  local updated
  local backend
  local last_test

  feature=$(strip_yaml_scalar "$(yaml_top_level_value feature "$file")")
  phase=$(strip_yaml_scalar "$(yaml_top_level_value phase "$file")")
  cycle=$(strip_yaml_scalar "$(yaml_top_level_value cycle "$file")")
  updated=$(strip_yaml_scalar "$(yaml_top_level_value updated "$file")")

  backend=$(strip_yaml_scalar "$(yaml_last_phase_value backend "$file")")
  if [ -z "$backend" ] || [ "$backend" = "null" ]; then
    backend="claude:subagent"
  fi

  last_test=$(strip_yaml_scalar "$(yaml_last_phase_value test_summary "$file")")
  if [ -z "$last_test" ] || [ "$last_test" = "null" ]; then
    last_test="(none)"
  fi

  printf 'Feature: %s\n' "$feature"
  printf 'Slug: %s\n' "$slug"
  printf 'Phase: %s\n' "$phase"
  printf 'Cycle: %s/%s\n' "$cycle" "$max_cycles"
  printf 'Backend: %s\n' "$backend"
  printf 'Last test: %s\n' "$last_test"
  printf 'Updated: %s\n' "$updated"
}

# State tracking guard
if [ -f .tdd/config.yaml ]; then
  ST_RAW=$(grep '^state_tracking:' .tdd/config.yaml | awk '{print $2}' || true)
  if [ "$ST_RAW" = "false" ]; then
    echo "State tracking is disabled — enable it in `.tdd/config.yaml` to use this command"
    exit 0
  fi
fi

if [ ! -d .tdd/active ]; then
  echo "No .tdd/active/ directory found — run tdd-init.sh first" >&2
  exit 1
fi

MAX_CYCLES=$(read_max_cycles)

if [ $# -ge 1 ]; then
  # Show a specific cycle
  if ! [[ "$1" =~ ^[a-z0-9]([a-z0-9-]{0,38}[a-z0-9])?$ ]]; then
    echo "Error: slug must be lowercase alphanumeric with hyphens, 2-40 chars" >&2
    exit 1
  fi
  FILE=".tdd/active/${1}.yaml"
  if [ ! -f "$FILE" ]; then
    echo "No active cycle for slug '${1}'" >&2
    exit 1
  fi
  print_cycle_status "$1" "$FILE" "$MAX_CYCLES"
  exit 0
fi

FOUND=0
COUNT=0
FIRST=1
for f in .tdd/active/*.yaml; do
  [ -f "$f" ] || continue
  FOUND=1
  COUNT=$((COUNT + 1))
  SLUG=$(basename "$f" .yaml)
  if [ "$FIRST" -eq 0 ]; then
    printf '\n'
  fi
  FIRST=0
  print_cycle_status "$SLUG" "$f" "$MAX_CYCLES"
done

if [ "$FOUND" -eq 0 ]; then
  echo "No active TDD cycles"
elif [ "$COUNT" -gt 1 ]; then
  printf '\nHint: specify a slug for single-cycle details\n'
fi
