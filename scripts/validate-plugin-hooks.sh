#!/bin/bash
# Validate Claude and Codex plugin manifests plus Claude hook configs.
#
# Checks:
#   1. Claude and Codex plugin manifests are valid JSON
#   2. Each manifest has required "name" and "description" fields
#   3. Codex manifest component paths are ./-prefixed and resolve within the plugin
#   4. Codex marketplace metadata is valid JSON and points at existing plugin dirs
#   5. Claude hooks.json files are valid JSON
#   6. Each Claude hook event maps to an array of rule groups
#   7. Each Claude rule group has a "hooks" array (not bare hook objects)
#   8. Each Claude hook entry has required "type" and "command" fields
#   9. Claude hook event names are from the known set
#  10. Scripts referenced via ${CLAUDE_PLUGIN_ROOT} exist relative to plugin root
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

validate_manifest_json() {
  local manifest_json="$1"
  local manifest_kind="$2"
  local plugin_dir="$3"

  if ! jq empty "$manifest_json" 2>/dev/null; then
    error "$manifest_json" "Invalid JSON in $(basename "$manifest_json")"
    return
  fi

  local name desc
  name=$(jq -r '.name // empty' "$manifest_json")
  desc=$(jq -r '.description // empty' "$manifest_json")
  [ -z "$name" ] && error "$manifest_json" "$(basename "$manifest_json") missing required 'name' field"
  [ -z "$desc" ] && error "$manifest_json" "$(basename "$manifest_json") missing required 'description' field"

  if [ "$manifest_kind" != "codex" ]; then
    return
  fi

  local field rel_path prompt_count
  for field in skills mcpServers apps; do
    rel_path=$(jq -r --arg field "$field" '.[$field] // empty' "$manifest_json")
    [ -z "$rel_path" ] && continue

    if [[ "$rel_path" != ./* ]]; then
      error "$manifest_json" "Field '$field' must be a relative path starting with './'"
      continue
    fi

    if [ ! -e "$plugin_dir/${rel_path#./}" ]; then
      error "$manifest_json" "Field '$field' points to a missing path: $rel_path"
    fi
  done

  prompt_count=$(jq '(.interface.defaultPrompt // []) | length' "$manifest_json")
  if [ "$prompt_count" -gt 3 ]; then
    error "$manifest_json" "interface.defaultPrompt may contain at most 3 entries"
  fi
}

validate_codex_marketplace() {
  local marketplace_json="$REPO_ROOT/.agents/plugins/marketplace.json"
  [ -f "$marketplace_json" ] || return

  echo "Validating .agents/plugins/marketplace.json"

  if ! jq empty "$marketplace_json" 2>/dev/null; then
    error "$marketplace_json" "Invalid JSON in marketplace.json"
    return
  fi

  local name is_array count entry_name source_path install_policy auth_policy category
  name=$(jq -r '.name // empty' "$marketplace_json")
  [ -z "$name" ] && error "$marketplace_json" "marketplace.json missing required 'name' field"

  is_array=$(jq '.plugins | type == "array"' "$marketplace_json")
  if [ "$is_array" != "true" ]; then
    error "$marketplace_json" "marketplace.json field 'plugins' must be an array"
    return
  fi

  count=$(jq '.plugins | length' "$marketplace_json")
  for ((i = 0; i < count; i++)); do
    entry_name=$(jq -r --argjson i "$i" '.plugins[$i].name // empty' "$marketplace_json")
    source_path=$(jq -r --argjson i "$i" '
      if (.plugins[$i].source | type) == "object" then
        .plugins[$i].source.path // empty
      else
        .plugins[$i].source // empty
      end
    ' "$marketplace_json")
    install_policy=$(jq -r --argjson i "$i" '.plugins[$i].policy.installation // empty' "$marketplace_json")
    auth_policy=$(jq -r --argjson i "$i" '.plugins[$i].policy.authentication // empty' "$marketplace_json")
    category=$(jq -r --argjson i "$i" '.plugins[$i].category // empty' "$marketplace_json")

    [ -z "$entry_name" ] && error "$marketplace_json" "plugins[$i] missing required 'name' field"
    [ -z "$source_path" ] && error "$marketplace_json" "plugins[$i] missing required source path"
    [ -z "$install_policy" ] && error "$marketplace_json" "plugins[$i] missing policy.installation"
    [ -z "$auth_policy" ] && error "$marketplace_json" "plugins[$i] missing policy.authentication"
    [ -z "$category" ] && error "$marketplace_json" "plugins[$i] missing category"

    if [[ -n "$source_path" && "$source_path" != ./* ]]; then
      error "$marketplace_json" "plugins[$i] source.path must start with './': $source_path"
      continue
    fi

    if [[ -n "$source_path" && ! -e "$REPO_ROOT/${source_path#./}" ]]; then
      error "$marketplace_json" "plugins[$i] source.path does not exist: $source_path"
    fi
  done
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
    if [ -d "$d/.claude-plugin" ] || [ -d "$d/.codex-plugin" ]; then
      plugins+=("plugins/$(basename "$d")")
    fi
  done
fi

if [ ${#plugins[@]} -eq 0 ]; then
  # Still validate the Codex marketplace even when no plugin dirs are in scope
  # (e.g. targeted run against only .agents/plugins/marketplace.json).
  validate_codex_marketplace
  if [ $errors -gt 0 ]; then
    echo ""
    echo "Plugin validation failed with $errors error(s)"
    exit 1
  fi
  echo "No plugins to validate"
  exit 0
fi

# ── Validate each plugin ────────────────────────────────────────────────────
for plugin_rel in "${plugins[@]}"; do
  plugin_dir="$REPO_ROOT/$plugin_rel"
  claude_plugin_json="$plugin_dir/.claude-plugin/plugin.json"
  codex_plugin_json="$plugin_dir/.codex-plugin/plugin.json"
  hooks_json="$plugin_dir/hooks/hooks.json"

  plugin_errors=0
  echo "Validating $plugin_rel"

  # ── plugin manifests ─────────────────────────────────────────────────────
  # If the host subdirectory exists, its plugin.json must exist too — catches
  # partial scaffolds where someone created .claude-plugin/ (or .codex-plugin/)
  # without the manifest file inside it.
  if [ -d "$plugin_dir/.claude-plugin" ]; then
    if [ -f "$claude_plugin_json" ]; then
      validate_manifest_json "$claude_plugin_json" "claude" "$plugin_dir"
    else
      error "$plugin_rel" "Missing .claude-plugin/plugin.json"
    fi
  fi

  if [ -d "$plugin_dir/.codex-plugin" ]; then
    if [ -f "$codex_plugin_json" ]; then
      validate_manifest_json "$codex_plugin_json" "codex" "$plugin_dir"
    else
      error "$plugin_rel" "Missing .codex-plugin/plugin.json"
    fi
  fi

  # ── hooks.json (optional — only validate if present) ─────────────────────
  if [ -f "$hooks_json" ]; then
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
  fi

  [ "$plugin_errors" -eq 0 ] && echo "  OK"
done

validate_codex_marketplace

if [ $errors -gt 0 ]; then
  echo ""
  echo "Plugin validation failed with $errors error(s)"
  exit 1
fi

echo ""
echo "All plugins valid"
