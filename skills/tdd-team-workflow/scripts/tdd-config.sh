#!/usr/bin/env bash
# tdd-config.sh — Display the current TDD configuration (read-only).
# Usage: bash tdd-config.sh
set -euo pipefail

SEPARATOR='─────────────────────────'

if [ -f .tdd/config.yaml ]; then
  printf 'Config: .tdd/config.yaml\n'
  printf '%s\n' "$SEPARATOR"
  while IFS= read -r line || [ -n "$line" ]; do
    printf '%s\n' "$line"
  done < .tdd/config.yaml
  exit 0
fi

printf 'Config: .tdd/config.yaml (not found — using defaults)\n'
printf '%s\n' "$SEPARATOR"
printf 'state_tracking: true (default)\n'
printf 'backends: all claude:subagent (default)\n'
printf 'test_command: auto-detect (default)\n'
printf 'max_cycles: 3 (default)\n'