#!/usr/bin/env bash
# tdd-list.sh — List all active and completed TDD cycles.
# Usage: bash tdd-list.sh
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

archive_result() {
  local phase="$1"

  case "$phase" in
    done)
      printf '%s' "APPROVED"
      ;;
    cancelled)
      printf '%s' "CANCELLED"
      ;;
    "" | null)
      printf '%s' "UNKNOWN"
      ;;
    *)
      printf '%s' "${phase^^}"
      ;;
  esac
}

print_active_cycle() {
  local slug="$1"
  local file="$2"
  local max_cycles="$3"
  local slug_width="$4"
  local feature
  local cycle
  local phase
  local updated
  local backend

  feature=$(strip_yaml_scalar "$(yaml_top_level_value feature "$file")")
  cycle=$(strip_yaml_scalar "$(yaml_top_level_value cycle "$file")")
  phase=$(strip_yaml_scalar "$(yaml_top_level_value phase "$file")")
  updated=$(strip_yaml_scalar "$(yaml_top_level_value updated "$file")")
  backend=$(strip_yaml_scalar "$(yaml_last_phase_value backend "$file")")

  if [ -z "$backend" ] || [ "$backend" = "null" ]; then
    backend="claude:subagent"
  fi

  if [ -z "$cycle" ] || [ "$cycle" = "null" ]; then
    cycle="?"
  fi

  if [ -z "$phase" ] || [ "$phase" = "null" ]; then
    phase="unknown"
  fi

  : "$feature" "$updated"

  printf '  %-*s  cycle %s/%s   phase: %-9s %s\n' \
    "$slug_width" "$slug" "$cycle" "$max_cycles" "$phase" "$backend"
}

print_completed_cycle() {
  local slug="$1"
  local cycle="$2"
  local file="$3"
  local slug_width="$4"
  local feature
  local phase
  local updated
  local result

  feature=$(strip_yaml_scalar "$(yaml_top_level_value feature "$file")")
  phase=$(strip_yaml_scalar "$(yaml_top_level_value phase "$file")")
  updated=$(strip_yaml_scalar "$(yaml_top_level_value updated "$file")")
  result=$(archive_result "$phase")

  : "$feature" "$updated"

  printf '  %-*s  cycle %s     result: %s\n' \
    "$slug_width" "$slug" "$cycle" "$result"
}

if [ $# -ne 0 ]; then
  echo "Usage: bash tdd-list.sh" >&2
  exit 1
fi

# State tracking guard
if [ -f .tdd/config.yaml ]; then
  ST_RAW=$(grep '^state_tracking:' .tdd/config.yaml | awk '{print $2}' || true)
  if [ "$ST_RAW" = "false" ]; then
    echo "State tracking is disabled — enable it in `.tdd/config.yaml` to use this command"
    exit 0
  fi
fi

if [ ! -d .tdd/active ]; then
  echo "Error: .tdd/active/ does not exist — run tdd-init.sh first" >&2
  exit 1
fi

shopt -s nullglob

ACTIVE_FILES=(.tdd/active/*.yaml)
ARCHIVE_FILES=(.tdd/archive/*.yaml)
MAX_CYCLES=$(read_max_cycles)
ACTIVE_SLUG_WIDTH=12
COMPLETED_SLUG_WIDTH=12

for f in "${ACTIVE_FILES[@]}"; do
  SLUG=$(basename "$f" .yaml)
  if [ ${#SLUG} -gt "$ACTIVE_SLUG_WIDTH" ]; then
    ACTIVE_SLUG_WIDTH=${#SLUG}
  fi
done

for f in "${ARCHIVE_FILES[@]}"; do
  NAME=$(basename "$f" .yaml)
  if [[ "$NAME" =~ ^(.+)-c([0-9]+)$ ]]; then
    SLUG="${BASH_REMATCH[1]}"
  else
    SLUG="$NAME"
  fi

  if [ ${#SLUG} -gt "$COMPLETED_SLUG_WIDTH" ]; then
    COMPLETED_SLUG_WIDTH=${#SLUG}
  fi
done

if [ ${#ACTIVE_FILES[@]} -eq 0 ]; then
  echo "Active: (none)"
else
  echo "Active:"
  for f in "${ACTIVE_FILES[@]}"; do
    SLUG=$(basename "$f" .yaml)
    print_active_cycle "$SLUG" "$f" "$MAX_CYCLES" "$ACTIVE_SLUG_WIDTH"
  done
fi

printf '\n'

if [ ${#ARCHIVE_FILES[@]} -eq 0 ]; then
  echo "Completed: (none)"
else
  echo "Completed:"
  for f in "${ARCHIVE_FILES[@]}"; do
    NAME=$(basename "$f" .yaml)
    CYCLE="?"

    if [[ "$NAME" =~ ^(.+)-c([0-9]+)$ ]]; then
      SLUG="${BASH_REMATCH[1]}"
      CYCLE="${BASH_REMATCH[2]}"
    else
      SLUG="$NAME"
    fi

    print_completed_cycle "$SLUG" "$CYCLE" "$f" "$COMPLETED_SLUG_WIDTH"
  done
fi
