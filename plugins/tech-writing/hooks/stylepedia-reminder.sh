#!/usr/bin/env bash
# Advisory context for the copyedit skill; no network calls or permission changes.
set -euo pipefail
command -v jq >/dev/null 2>&1 || exit 0
input="$(cat)"
event="$(printf '%s' "$input" | jq -er '.hook_event_name | strings' 2>/dev/null)" || exit 0
case "$event" in
  PreToolUse)
    skill="$(printf '%s' "$input" | jq -er 'select(.tool_name == "Skill") | .tool_input.skill | strings' 2>/dev/null)" || exit 0
    ;;
  UserPromptExpansion)
    skill="$(printf '%s' "$input" | jq -er 'select(.expansion_type == "slash_command") | .command_name | strings' 2>/dev/null)" || exit 0
    ;;
  *) exit 0 ;;
esac
case "$skill" in
  tech-writing:copyedit|tech-writing-copyedit) ;;
  *) exit 0 ;;
esac
jq -nc --arg event "$event" '{hookSpecificOutput: {
  hookEventName: $event,
  additionalContext: "The copyedit skill includes a Stylepedia topic index: https://stylepedia.net/style/#part-Writing_Style_Guide . Its workflow starts by checking the index and consulting sections relevant to the current prose. House rules, established project locale, normative modals, and the recommendation exception take precedence. Unrelated sections need no lookup."
}}'
