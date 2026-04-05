#!/bin/bash
# Validate Claude Code plugin hooks.json files.
#
# Checks:
#   1. All hooks.json files are valid JSON
#   2. Each event maps to an array of rule groups
#   3. Each rule group has a "hooks" array (not bare hook objects)
#   4. Each hook entry has required "type" and "command" fields
#   5. Event names are from the known set
#   6. Scripts referenced via ${CLAUDE_PLUGIN_ROOT} exist relative to plugin root
#   7. plugin.json is valid JSON with required "name" and "description" fields
#
# Usage:
#   validate-plugin-hooks.sh                   # validate all plugins
#   validate-plugin-hooks.sh plugins/hooks/...  # validate only changed files

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

KNOWN_EVENTS=(
  SessionStart
  UserPromptSubmit
  PreToolUse
  PostToolUse
  PostToolUseFailure
  PermissionRequest
  Stop
  Notification
  SubagentStart
  SubagentStop
  ConfigChange
  CwdChanged
  FileChanged
  PreCompact
  PostCompact
  SessionEnd
)

errors=0
plugin_errors=0

error() {
  echo "::error file=$1::$2" >&2
  errors=$((errors + 1))
  plugin_errors=$((plugin_errors + 1))
}

warn() {
  echo "::warning file=$1::$2" >&2
}

# ── Determine which plugins to validate ─────────────────────────────────────
if [ $# -gt 0 ]; then
  # Extract unique plugin dirs from changed file paths
  declare -A plugin_dirs
  for file in "$@"; do
    # Normalise to repo-relative path
    rel="${file#"$REPO_ROOT"/}"
    # Match plugins/<name>/... pattern
    if [[ "$rel" =~ ^plugins/([^/]+)/ ]]; then
      plugin_dirs["plugins/${BASH_REMATCH[1]}"]=1
    fi
  done
  plugins=("${!plugin_dirs[@]}")
else
  # Validate all plugins
  plugins=()
  for d in "$REPO_ROOT"/plugins/*/; do
    [ -d "$d/.claude-plugin" ] && plugins+=("plugins/$(basename "$d")")
  done
fi

if [ ${#plugins[@]} -eq 0 ]; then
  echo "No plugins to validate"
  exit 0
fi

# ── Validate each plugin ────────────────────────────────────────────────────
for plugin_rel in "${plugins[@]}"; do
  plugin_dir="$REPO_ROOT/$plugin_rel"
  plugin_json="$plugin_dir/.claude-plugin/plugin.json"
  hooks_json="$plugin_dir/hooks/hooks.json"

  plugin_errors=0
  echo "Validating $plugin_rel"

  # ── plugin.json ──────────────────────────────────────────────────────────
  if [ ! -f "$plugin_json" ]; then
    error "$plugin_rel" "Missing .claude-plugin/plugin.json"
    continue
  fi

  if ! jq empty "$plugin_json" 2>/dev/null; then
    error "$plugin_json" "Invalid JSON in plugin.json"
    continue
  fi

  name=$(jq -r '.name // empty' "$plugin_json")
  desc=$(jq -r '.description // empty' "$plugin_json")
  [ -z "$name" ] && error "$plugin_json" "plugin.json missing required 'name' field"
  [ -z "$desc" ] && error "$plugin_json" "plugin.json missing required 'description' field"

  # ── hooks.json (optional — only validate if present) ─────────────────────
  [ -f "$hooks_json" ] || continue

  if ! jq empty "$hooks_json" 2>/dev/null; then
    error "$hooks_json" "Invalid JSON in hooks.json"
    continue
  fi

  # Check top-level has "hooks" object
  has_hooks=$(jq 'has("hooks")' "$hooks_json")
  if [ "$has_hooks" != "true" ]; then
    error "$hooks_json" "hooks.json must have a top-level 'hooks' object"
    continue
  fi

  # Validate each event
  events=$(jq -r '.hooks | keys[]' "$hooks_json")
  for event in $events; do
    # Check event name is known
    known=false
    for ke in "${KNOWN_EVENTS[@]}"; do
      [ "$event" = "$ke" ] && known=true && break
    done
    $known || warn "$hooks_json" "Unknown hook event '$event' — check spelling"

    # Each event must map to an array
    is_array=$(jq --arg e "$event" '.hooks[$e] | type == "array"' "$hooks_json")
    if [ "$is_array" != "true" ]; then
      error "$hooks_json" "Event '$event' must map to an array of rule groups"
      continue
    fi

    # Each rule group must have a "hooks" array
    group_count=$(jq --arg e "$event" '.hooks[$e] | length' "$hooks_json")
    for ((i = 0; i < group_count; i++)); do
      has_inner=$(jq --arg e "$event" --argjson i "$i" \
        '.hooks[$e][$i] | has("hooks")' "$hooks_json")

      if [ "$has_inner" != "true" ]; then
        # Check if user accidentally put hook fields at rule-group level
        has_type=$(jq --arg e "$event" --argjson i "$i" \
          '.hooks[$e][$i] | has("type")' "$hooks_json")
        if [ "$has_type" = "true" ]; then
          error "$hooks_json" \
            "Event '$event' group[$i]: hook definition placed directly in rule group. " \
            "Wrap it: { \"hooks\": [{ \"type\": ..., \"command\": ... }] }"
        else
          error "$hooks_json" \
            "Event '$event' group[$i]: missing required 'hooks' array"
        fi
        continue
      fi

      # Validate each hook entry inside the rule group
      hook_count=$(jq --arg e "$event" --argjson i "$i" \
        '.hooks[$e][$i].hooks | length' "$hooks_json")
      for ((j = 0; j < hook_count; j++)); do
        hook_type=$(jq -r --arg e "$event" --argjson i "$i" --argjson j "$j" \
          '.hooks[$e][$i].hooks[$j].type // empty' "$hooks_json")
        hook_cmd=$(jq -r --arg e "$event" --argjson i "$i" --argjson j "$j" \
          '.hooks[$e][$i].hooks[$j].command // empty' "$hooks_json")

        [ -z "$hook_type" ] && \
          error "$hooks_json" "Event '$event' group[$i] hook[$j]: missing 'type' field"
        [ -z "$hook_cmd" ] && \
          error "$hooks_json" "Event '$event' group[$i] hook[$j]: missing 'command' field"

        # If command references ${CLAUDE_PLUGIN_ROOT}, check the script exists
        if [[ "$hook_cmd" == *'${CLAUDE_PLUGIN_ROOT}'* ]]; then
          rel_script="${hook_cmd/\$\{CLAUDE_PLUGIN_ROOT\}/}"
          rel_script="${rel_script#/}"
          # Strip any prefix command (e.g. "bash ", "python3 ")
          rel_script="${rel_script#bash }"
          rel_script="${rel_script#python3 }"
          # Remove surrounding quotes
          rel_script="${rel_script#\"}"
          rel_script="${rel_script%\"}"
          abs_script="$plugin_dir/$rel_script"
          if [ ! -f "$abs_script" ]; then
            error "$hooks_json" \
              "Event '$event' group[$i] hook[$j]: script not found: $rel_script"
          elif [ ! -x "$abs_script" ] && [[ "$hook_cmd" != *python3* ]] && [[ "$hook_cmd" != *bash* ]]; then
            warn "$hooks_json" \
              "Event '$event' group[$i] hook[$j]: script not executable: $rel_script"
          fi
        fi
      done
    done
  done

  [ "$plugin_errors" -eq 0 ] && echo "  OK"
done

if [ $errors -gt 0 ]; then
  echo ""
  echo "Plugin validation failed with $errors error(s)"
  exit 1
fi

echo ""
echo "All plugins valid"
