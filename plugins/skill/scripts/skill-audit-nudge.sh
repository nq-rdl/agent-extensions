#!/usr/bin/env bash
# Advisory PostToolUse nudge: when a skills/**/SKILL.md is edited, suggest /skill:audit.
# matcher limits to Edit|Write; this script applies the PATH filter (matcher is tool-name only).
set -euo pipefail
input="$(cat)"
path="$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty')"
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
