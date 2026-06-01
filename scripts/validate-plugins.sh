#!/bin/bash
# Validate Claude Code plugin structure, hooks, and agents.
#
# Checks:
#   Claude plugin manifests
#     1. plugin.json is valid JSON
#     2. plugin.json has required "name" and "description" fields
#     3. plugin.json must NOT declare an "agents" field (Claude Code auto-discovers from ./agents/)
#     4. If a .claude-plugin/ directory exists, its plugin.json must too
#
#   hooks.json (optional — only if present)
#     5. hooks.json is valid JSON
#     6. Each event maps to an array of rule groups
#     7. Each rule group has a "hooks" array (not bare hook objects)
#     8. Each hook entry has required "type" and "command" fields
#     9. Event names are from the known set
#    10. Scripts referenced via ${CLAUDE_PLUGIN_ROOT} exist relative to plugin root
#
#   agents
#    11. Every agent listed in registry/bundles/<b>.yaml has a source file
#        at agents/<name>/agent.md
#    12. Every Claude-target bundle agent has a symlink at
#        plugins/<plugin>/agents/<name>.md (cross-checked against the bundle
#        YAML, not just scanned from disk — catches missing symlinks)
#    13. Every agents/<name>/agent.md has frontmatter keys `name`, `description`
#    14. Every mcp entry in a bundle YAML is wired in the bundle plugin's
#        .mcp.json (at plugin root, per Claude Code plugin spec)
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

# Validate a Claude plugin manifest.
validate_manifest_json() {
  local manifest_json="$1"

  if ! jq empty "$manifest_json" 2>/dev/null; then
    error "$manifest_json" "Invalid JSON in $(basename "$manifest_json")"
    return
  fi

  local name desc
  name=$(jq -r '.name // empty' "$manifest_json")
  desc=$(jq -r '.description // empty' "$manifest_json")
  [ -z "$name" ] && error "$manifest_json" "$(basename "$manifest_json") missing required 'name' field"
  [ -z "$desc" ] && error "$manifest_json" "$(basename "$manifest_json") missing required 'description' field"

  # Claude Code auto-discovers agents from ./agents/ — no manifest field required.
  # Reject the "agents" field if present (Claude's validator rejects it).
  if [ -n "$(jq -r '.agents // empty' "$manifest_json")" ]; then
    error "$manifest_json" \
      "plugin.json must not declare an \"agents\" field — agents are auto-discovered from ./agents/"
  fi
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
    if [ -d "$d/.claude-plugin" ]; then
      plugins+=("plugins/$(basename "$d")")
    fi
  done
fi

if [ ${#plugins[@]} -eq 0 ]; then
  echo "No plugins to validate"
else

# ── Validate each plugin ────────────────────────────────────────────────────
for plugin_rel in "${plugins[@]}"; do
  plugin_dir="$REPO_ROOT/$plugin_rel"
  claude_plugin_json="$plugin_dir/.claude-plugin/plugin.json"
  hooks_json="$plugin_dir/hooks/hooks.json"
  agents_dir="$plugin_dir/agents"

  plugin_errors=0
  echo "Validating $plugin_rel"

  # ── plugin manifest ──────────────────────────────────────────────────────
  # If .claude-plugin/ exists, its plugin.json must too — catches partial
  # scaffolds where someone created the directory without the manifest file.
  if [ -d "$plugin_dir/.claude-plugin" ]; then
    if [ -f "$claude_plugin_json" ]; then
      validate_manifest_json "$claude_plugin_json"
    else
      error "$plugin_rel" "Missing .claude-plugin/plugin.json"
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

fi

# ── Agent-level validation ──────────────────────────────────────────────────
# 1. Every bundle YAML agents: entry resolves to agents/<name>/agent.md
# 2. Every agents/<name>/agent.md has frontmatter name + description
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
    # Use `or {}` (not .get(k, {})) so a bare `claude:` (null value) does not
    # crash with AttributeError — .get returns None for a present-but-null key.
    claude = (data.get("targets") or {}).get("claude") or {}
    claude_enabled = claude.get("enabled")
    plugin_name = claude.get("pluginName") or bundle_id

    for name in data.get("agents") or []:
        src = repo / "agents" / name / "agent.md"
        if not src.is_file():
            err(bundle, f"Agent '{name}' declared but missing source file agents/{name}/agent.md")
        if claude_enabled:
            link = repo / "plugins" / plugin_name / "agents" / f"{name}.md"
            if not link.exists():
                err(bundle, f"Agent '{name}' declared for Claude target but missing symlink plugins/{plugin_name}/agents/{name}.md")

    # Skills: declared bundle skills must resolve to a canonical source and (for
    # Claude targets) to a self-contained plugin copy. Without this, the issue
    # #100 scenario — registry references a skill removed upstream — passes the
    # local `validate-plugins.sh` pre-merge check silently (audit finding #3).
    for name in data.get("skills") or []:
        src = repo / "skills" / name
        if not src.is_dir():
            err(bundle, f"Skill '{name}' declared but missing source dir skills/{name}/")
        elif claude_enabled:
            copy = repo / "plugins" / plugin_name / "skills" / name
            if not copy.is_dir():
                err(bundle, f"Skill '{name}' declared for Claude target but missing plugin copy plugins/{plugin_name}/skills/{name}/")

    mcp_json = repo / "plugins" / plugin_name / ".mcp.json"
    declared_mcp = data.get("mcp") or []
    if declared_mcp and not mcp_json.is_file():
        err(bundle, f"Bundle declares mcp servers {declared_mcp} but plugins/{plugin_name}/.mcp.json does not exist")
    elif declared_mcp:
        try:
            wired = set(json.loads(mcp_json.read_text()).get("mcpServers", {}).keys())
        except json.JSONDecodeError as exc:
            err(mcp_json, f"Invalid JSON: {exc}")
            wired = set()
        for key in declared_mcp:
            if key not in wired:
                err(bundle, f"mcp entry '{key}' not wired in plugins/{plugin_name}/.mcp.json")

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

if [ $errors -gt 0 ]; then
  echo ""
  echo "Plugin/agent validation failed with $errors error(s)"
  exit 1
fi

echo ""
echo "All plugins and agents valid"
