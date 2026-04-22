#!/bin/bash
# Validate Claude Code + Codex plugin structure, hooks, and agents.
#
# Checks:
#   Claude + Codex plugin manifests
#     1. plugin.json is valid JSON
#     2. plugin.json has required "name" and "description" fields
#     3. plugin.json must NOT declare an "agents" field (Claude Code auto-discovers from ./agents/)
#     4. Codex manifest component paths (skills, mcpServers, apps) are ./-prefixed and resolve within the plugin
#     5. Codex interface.defaultPrompt has at most 3 entries
#     6. If a .claude-plugin/ or .codex-plugin/ directory exists, its plugin.json must too
#
#   Codex marketplace
#     7. .agents/plugins/marketplace.json is valid JSON and points at existing plugin dirs
#     8. Each marketplace entry has name, source path, policy, and category
#
#   hooks.json (optional — only if present)
#     9. hooks.json is valid JSON
#    10. Each event maps to an array of rule groups
#    11. Each rule group has a "hooks" array (not bare hook objects)
#    12. Each hook entry has required "type" and "command" fields
#    13. Event names are from the known set
#    14. Scripts referenced via ${CLAUDE_PLUGIN_ROOT} exist relative to plugin root
#
#   agents (new)
#    15. Every agent listed in registry/bundles/<b>.yaml has a source file
#        at agents/<name>/agent.md
#    16. Every Claude-target bundle agent has a symlink at
#        plugins/<plugin>/agents/<name>.md (cross-checked against the bundle
#        YAML, not just scanned from disk — catches missing symlinks)
#    17. Every symlink under .gemini/agents/*.md resolves (if .gemini/ exists)
#    18. Every agents/<name>/agent.md has frontmatter keys `name`, `description`
#    19. Every mcp entry in a bundle YAML is wired in the bundle plugin's
#        .claude-plugin/.mcp.json
#
# Usage:
#   validate-plugins.sh                       # validate all plugins + agents
#   validate-plugins.sh plugins/swe/...       # validate only plugins touched by changed files

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

# Validate a Claude or Codex plugin manifest. For Codex, also verifies
# component paths and defaultPrompt cardinality.
validate_manifest_json() {
  local manifest_json="$1"
  local manifest_kind="$2"  # "claude" or "codex"
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

  if [ "$manifest_kind" = "claude" ]; then
    # Claude Code auto-discovers agents from ./agents/ — no manifest field required.
    # Reject the "agents" field if present (Claude's validator rejects it).
    if [ -n "$(jq -r '.agents // empty' "$manifest_json")" ]; then
      error "$manifest_json" \
        "plugin.json must not declare an \"agents\" field — agents are auto-discovered from ./agents/"
    fi
    return
  fi

  # Codex-specific checks
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

# Validate the Codex marketplace manifest if present.
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
  declare -A plugin_dirs
  for file in "$@"; do
    rel="${file#"$REPO_ROOT"/}"
    if [[ "$rel" =~ ^plugins/([^/]+)/ ]]; then
      plugin_dirs["plugins/${BASH_REMATCH[1]}"]=1
    fi
  done
  plugins=("${!plugin_dirs[@]}")
else
  plugins=()
  for d in "$REPO_ROOT"/plugins/*/; do
    if [ -d "$d/.claude-plugin" ] || [ -d "$d/.codex-plugin" ]; then
      plugins+=("plugins/$(basename "$d")")
    fi
  done
fi

if [ ${#plugins[@]} -eq 0 ]; then
  # Still validate the Codex marketplace even when no plugin dirs are in scope.
  validate_codex_marketplace
  echo "No plugins to validate"
else

# ── Validate each plugin ────────────────────────────────────────────────────
for plugin_rel in "${plugins[@]}"; do
  plugin_dir="$REPO_ROOT/$plugin_rel"
  claude_plugin_json="$plugin_dir/.claude-plugin/plugin.json"
  codex_plugin_json="$plugin_dir/.codex-plugin/plugin.json"
  hooks_json="$plugin_dir/hooks/hooks.json"
  agents_dir="$plugin_dir/agents"

  plugin_errors=0
  echo "Validating $plugin_rel"

  # ── plugin manifests ─────────────────────────────────────────────────────
  # If a host subdirectory exists, its plugin.json must exist too — catches
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

  # ── agent symlinks under plugins/<b>/agents/ ─────────────────────────────
  if [ -d "$agents_dir" ]; then
    for link in "$agents_dir"/*.md; do
      [ -e "$link" ] || [ -L "$link" ] || continue
      if [ ! -e "$link" ]; then
        error "$plugin_rel" "Broken agent symlink: $link -> $(readlink "$link" || echo '?')"
      fi
    done
  fi

  # ── hooks.json (optional) ────────────────────────────────────────────────
  [ -f "$hooks_json" ] || { [ "$plugin_errors" -eq 0 ] && echo "  OK"; continue; }

  if ! jq empty "$hooks_json" 2>/dev/null; then
    error "$hooks_json" "Invalid JSON in hooks.json"
    continue
  fi

  has_hooks=$(jq 'has("hooks")' "$hooks_json")
  if [ "$has_hooks" != "true" ]; then
    error "$hooks_json" "hooks.json must have a top-level 'hooks' object"
    continue
  fi

  events=$(jq -r '.hooks | keys[]' "$hooks_json")
  for event in $events; do
    known=false
    for ke in "${KNOWN_EVENTS[@]}"; do
      [ "$event" = "$ke" ] && known=true && break
    done
    $known || warn "$hooks_json" "Unknown hook event '$event' — check spelling"

    is_array=$(jq --arg e "$event" '.hooks[$e] | type == "array"' "$hooks_json")
    if [ "$is_array" != "true" ]; then
      error "$hooks_json" "Event '$event' must map to an array of rule groups"
      continue
    fi

    group_count=$(jq --arg e "$event" '.hooks[$e] | length' "$hooks_json")
    for ((i = 0; i < group_count; i++)); do
      has_inner=$(jq --arg e "$event" --argjson i "$i" \
        '.hooks[$e][$i] | has("hooks")' "$hooks_json")

      if [ "$has_inner" != "true" ]; then
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

        if [[ "$hook_cmd" == *'${CLAUDE_PLUGIN_ROOT}'* ]]; then
          rel_script="${hook_cmd/\$\{CLAUDE_PLUGIN_ROOT\}/}"
          rel_script="${rel_script#/}"
          rel_script="${rel_script#bash }"
          rel_script="${rel_script#python3 }"
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

validate_codex_marketplace

fi

# ── Agent-level validation ──────────────────────────────────────────────────
# 1. Every bundle YAML agents: entry resolves to agents/<name>/agent.md
# 2. Every agents/<name>/agent.md has frontmatter name + description
# 3. Every .gemini/agents/*.md symlink resolves
echo ""
echo "Validating agents"

# Cross-check every bundle YAML: each declared agent resolves to a source file,
# each declared Claude-targeted agent has a plugin symlink, and each declared
# mcp: entry is wired in the bundle's .mcp.json. Uses PyYAML so inline-flow
# lists (agents: [a, b]) and inline comments parse correctly.
python3 - "$REPO_ROOT" <<'PY' || errors=$((errors + 1))
import sys, json
from pathlib import Path
import yaml

repo = Path(sys.argv[1])
fail = False

def err(path, msg):
    global fail
    print(f"::error file={path}::{msg}", file=sys.stderr)
    fail = True

for bundle in sorted((repo / "registry" / "bundles").glob("*.yaml")):
    with bundle.open() as f:
        data = yaml.safe_load(f) or {}
    bundle_id = data.get("id") or bundle.stem
    claude_enabled = (data.get("targets") or {}).get("claude", {}).get("enabled")
    plugin_name = (data.get("targets") or {}).get("claude", {}).get("pluginName") or bundle_id

    for name in data.get("agents") or []:
        src = repo / "agents" / name / "agent.md"
        if not src.is_file():
            err(bundle, f"Agent '{name}' declared but missing source file agents/{name}/agent.md")
        if claude_enabled:
            link = repo / "plugins" / plugin_name / "agents" / f"{name}.md"
            if not link.exists():
                err(bundle, f"Agent '{name}' declared for Claude target but missing symlink plugins/{plugin_name}/agents/{name}.md")

    mcp_json = repo / "plugins" / plugin_name / ".claude-plugin" / ".mcp.json"
    declared_mcp = data.get("mcp") or []
    if declared_mcp and not mcp_json.is_file():
        err(bundle, f"Bundle declares mcp servers {declared_mcp} but plugins/{plugin_name}/.claude-plugin/.mcp.json does not exist")
    elif declared_mcp:
        try:
            wired = set(json.loads(mcp_json.read_text()).get("mcpServers", {}).keys())
        except json.JSONDecodeError as exc:
            err(mcp_json, f"Invalid JSON: {exc}")
            wired = set()
        for key in declared_mcp:
            if key not in wired:
                err(bundle, f"mcp entry '{key}' not wired in plugins/{plugin_name}/.claude-plugin/.mcp.json")

sys.exit(1 if fail else 0)
PY

# Validate every agents/<name>/agent.md has the required frontmatter.
if [ -d "$REPO_ROOT/agents" ]; then
  for agent_md in "$REPO_ROOT"/agents/*/agent.md; do
    [ -f "$agent_md" ] || continue
    python3 - "$agent_md" <<'PY' || errors=$((errors + 1))
import sys
import yaml
path = sys.argv[1]
with open(path, "r", encoding="utf-8") as f:
    text = f.read()
if not text.startswith("---\n"):
    print(f"::error file={path}::missing YAML frontmatter", file=sys.stderr)
    sys.exit(1)
parts = text.split("---\n", 2)
if len(parts) < 3:
    print(f"::error file={path}::unterminated YAML frontmatter", file=sys.stderr)
    sys.exit(1)
try:
    fm = yaml.safe_load(parts[1]) or {}
except yaml.YAMLError as exc:
    print(f"::error file={path}::invalid YAML frontmatter: {exc}", file=sys.stderr)
    sys.exit(1)
missing = [k for k in ("name", "description") if not fm.get(k)]
if missing:
    print(
        f"::error file={path}::agent frontmatter missing required key(s): {', '.join(missing)}",
        file=sys.stderr,
    )
    sys.exit(1)
PY
  done
fi

# Validate .gemini/agents/*.md symlinks resolve.
if [ -d "$REPO_ROOT/.gemini/agents" ]; then
  for link in "$REPO_ROOT"/.gemini/agents/*.md; do
    [ -e "$link" ] || [ -L "$link" ] || continue
    if [ ! -e "$link" ]; then
      error ".gemini/agents" "Broken agent symlink: $link -> $(readlink "$link" || echo '?')"
    fi
  done
fi

# Validate .gemini/skills/* symlinks resolve (directory symlinks into submodule).
if [ -d "$REPO_ROOT/.gemini/skills" ]; then
  for link in "$REPO_ROOT"/.gemini/skills/*; do
    [ -e "$link" ] || [ -L "$link" ] || continue
    if [ ! -e "$link" ]; then
      error ".gemini/skills" "Broken skill symlink: $link -> $(readlink "$link" || echo '?')"
    fi
  done
fi

if [ $errors -gt 0 ]; then
  echo ""
  echo "Plugin/agent validation failed with $errors error(s)"
  exit 1
fi

echo ""
echo "All plugins and agents valid"
