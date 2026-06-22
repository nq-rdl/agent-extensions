#!/usr/bin/env bash
# Advisory PostToolUse nudge: when a skills/**/SKILL.md is edited, suggest /skill:audit.
# matcher limits to Edit|Write; this script applies the PATH filter (matcher is tool-name only).
set -euo pipefail
# Advisory-only: if jq is unavailable, no-op silently rather than erroring.
command -v jq >/dev/null 2>&1 || exit 0
input="$(cat)"
# Tolerate malformed/non-JSON stdin: a parse error must no-op, not abort.
path="$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null || true)"
case "$path" in
  */skills/*/SKILL.md|skills/*/SKILL.md)
    jq -nc --arg p "$path" '{
      hookSpecificOutput: {
        hookEventName: "PostToolUse",
        additionalContext: ("Skill edited (" + $p + "). Consider running /skill:audit to check it encodes non-inferable value (CONTRIBUTING.md → Skill content conventions).")
      }
    }'
    ;;
  *) exit 0 ;;
esac
