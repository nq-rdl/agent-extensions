#!/bin/bash
# Validate Claude Code and native Codex plugin structure, hooks, skills.
#
# Validate manifests, hooks, skill copies, and MCP wiring against the registry.
# Standalone agent declarations and trees are retired; delegation lives in
# optional skill references. Claude prompt/agent hooks remain hook components.
# Usage: validate-plugins.sh [plugins/<bundle>/changed-file ...]

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

KNOWN_EVENTS=(
  SessionStart
  UserPromptSubmit
  UserPromptExpansion
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

  # Repository packaging policy: reusable behavior is shipped as skills.
  if jq -e 'has("agents")' "$manifest_json" >/dev/null; then
    error "$manifest_json" \
      "plugin.json must not declare an \"agents\" field — this catalog uses skill delegation references"
  fi
}

# Validate the phase-one native Codex manifest. Non-skill capabilities remain
# gated off in the registry generator until they have dedicated runtime tests.
validate_codex_manifest_json() {
  local manifest_json="$1"

  if ! jq empty "$manifest_json" 2>/dev/null; then
    error "$manifest_json" "Invalid JSON in $(basename "$manifest_json")"
    return
  fi

  local skills
  if ! jq -e '(.name | type) == "string" and (.name | test("\\S"))' \
    "$manifest_json" >/dev/null; then
    error "$manifest_json" "Codex plugin.json name must be a non-empty string"
  fi
  if ! jq -e '(.version | type) == "string" and (.version | test("\\S"))' \
    "$manifest_json" >/dev/null; then
    error "$manifest_json" "Codex plugin.json version must be a non-empty string"
  fi
  if ! jq -e '(.description | type) == "string" and (.description | test("\\S"))' \
    "$manifest_json" >/dev/null; then
    error "$manifest_json" "Codex plugin.json description must be a non-empty string"
  fi
  if ! jq -e \
    'if has("keywords") then (.keywords | type) == "array" and all(.keywords[]; type == "string") else true end' \
    "$manifest_json" >/dev/null; then
    error "$manifest_json" "Codex plugin.json keywords must be a list of strings"
  fi
  if ! jq -e 'if has("interface") then (.interface | type) == "object" else true end' \
    "$manifest_json" >/dev/null; then
    error "$manifest_json" "Codex plugin.json interface must be an object"
  fi

  skills=$(jq -r 'if (.skills | type) == "string" then .skills else empty end' "$manifest_json")

  if [ -z "$skills" ]; then
    error "$manifest_json" "Phase-one Codex plugin.json missing required 'skills' field"
  elif [ "$skills" != "./skills/" ]; then
    error "$manifest_json" "Phase-one Codex skills must be declared as './skills/'"
  elif [ ! -d "$(dirname "$manifest_json")/../skills" ]; then
    error "$manifest_json" "Codex skills path './skills/' does not exist at the plugin root"
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
    if [ -d "$d/.claude-plugin" ] || [ -d "$d/.codex-plugin" ]; then
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
  codex_plugin_json="$plugin_dir/.codex-plugin/plugin.json"
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

  if [ -d "$plugin_dir/.codex-plugin" ]; then
    if [ -f "$codex_plugin_json" ]; then
      validate_codex_manifest_json "$codex_plugin_json"
    else
      error "$plugin_rel" "Missing .codex-plugin/plugin.json"
    fi
  fi

  if [ -e "$agents_dir" ] || [ -L "$agents_dir" ]; then
    error "$plugin_rel" "Retired agents/ tree — run sync-plugins.sh; use skill references for delegation"
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
        case "$hook_type" in
          prompt|agent)
            hook_prompt=$(jq -r --arg e "$event" --argjson i "$i" --argjson j "$j" \
              '.hooks[$e][$i].hooks[$j].prompt // empty' "$hooks_json")
            [ -z "$hook_prompt" ] && \
              error "$hooks_json" "Event '$event' group[$i] hook[$j]: missing 'prompt' field"
            ;;
          *)
            [ -z "$hook_cmd" ] && \
              error "$hooks_json" "Event '$event' group[$i] hook[$j]: missing 'command' field"
            ;;
        esac

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

# Cross-check canonical skills, plugin copies, registry fields, and MCP wiring.
echo "Validating skill packaging"

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


def frontmatter_name(skill_md):
    """Return the SKILL.md frontmatter `name:` coerced to str, or None when the
    file is missing, has no frontmatter block, has no `name` key, or sets it to
    null. An absent/null name is valid — Claude Code then labels the skill by its
    `<plugin>:<leaf>` id. Any present, non-null value (string, number, bool, …)
    is returned as a str: Claude Code coerces it via `String(name)` into a bare
    label, so the caller's guard must reject it regardless of YAML type.

    Raise ValueError when a frontmatter block IS present but is unparseable YAML,
    so the caller fails validation instead of silently skipping the no-name
    guard on a broken header.
    """
    if not skill_md.is_file():
        return None
    parts = skill_md.read_text(encoding="utf-8").split("---\n", 2)
    if len(parts) < 3 or parts[0].strip():
        return None
    try:
        fm = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML frontmatter: {exc}") from exc
    val = fm.get("name")
    return None if val is None else str(val)


if (repo / "agents").exists():
    err(repo / "agents", "Canonical agents/ is retired; use skills with references/subagent.rst")

for skill_md in sorted((repo / "skills").glob("*/SKILL.md")):
    outline = skill_md.parent / "references" / "subagent.rst"
    text = skill_md.read_text(encoding="utf-8")
    linked = "(references/subagent.rst)" in text
    if outline.exists() and not linked:
        err(skill_md, "Delegation outline exists but SKILL.md does not link references/subagent.rst")
    if linked and not outline.is_file():
        err(skill_md, "Linked references/subagent.rst does not exist")

_bundles_dir = repo / "registry" / "bundles"
for bundle in sorted(list(_bundles_dir.glob("*.yaml")) + list(_bundles_dir.glob("*.yml"))):
    with bundle.open() as f:
        data = yaml.safe_load(f) or {}
    bundle_id = data.get("id") or bundle.stem
    # Use `or {}` (not .get(k, {})) so a bare `claude:` (null value) does not
    # crash with AttributeError — .get returns None for a present-but-null key.
    claude = (data.get("targets") or {}).get("claude") or {}
    claude_enabled = claude.get("enabled")
    plugin_name = claude.get("pluginName") or bundle_id
    codex = (data.get("targets") or {}).get("codex") or {}
    codex_enabled = codex.get("enabled")
    codex_plugin_name = codex.get("pluginName") or bundle_id

    if codex_enabled:
        codex_manifest = repo / "dist/codex/plugins" / codex_plugin_name / ".codex-plugin" / "plugin.json"
        if not codex_manifest.is_file():
            err(
                bundle,
                f"Codex target is enabled but missing dist/codex/plugins/{codex_plugin_name}/"
                ".codex-plugin/plugin.json",
            )

    if data.get("agents"):
        err(bundle, "Standalone agents are retired; use skills with references/subagent.rst")

    # Skills: declared bundle skills must resolve to a canonical source and (for
    # Claude targets) to a self-contained plugin copy. Without this, the issue
    # #100 scenario — registry references a skill removed upstream — passes the
    # local `validate-plugins.sh` pre-merge check silently (audit finding #3).
    for member in data.get("skills") or []:
        # A member is flat `<name>` (source == leaf) or an explicit {source, leaf}
        # mapping packaging a flat upstream skill under a different leaf. The
        # canonical source is skills/<source>/; the plugin copy is keyed by LEAF
        # (sync-plugins.sh drops the source name). Mirrors _registry.normalize_member.
        if isinstance(member, str):
            source, leaf = member, member
        elif (
            isinstance(member, dict)
            and isinstance(member.get("source"), str) and member.get("source")
            and isinstance(member.get("leaf"), str) and member.get("leaf")
        ):
            source, leaf = member["source"], member["leaf"]
        else:
            err(bundle, f"Malformed skill member {member!r} — expected a string or {{source, leaf}} mapping")
            continue
        src = repo / "skills" / source
        if not src.is_dir():
            err(bundle, f"Skill '{source}' declared but missing source dir skills/{source}/")
        elif claude_enabled:
            copy = repo / "plugins" / plugin_name / "skills" / leaf
            if not copy.is_dir():
                err(bundle, f"Skill '{source}' declared for Claude target but missing plugin copy plugins/{plugin_name}/skills/{leaf}/")
            else:
                # Claude Code labels a plugin skill in /-autocomplete as
                # `frontmatter.name || <plugin>:<leaf>` — so a present `name:`
                # (ANY value) overrides the namespaced id with a bare label
                # (`/go` would list `gh`, not `go:gh`). The copy must carry NO
                # `name:` at all. sync-plugins.sh strips it on copy; this guards
                # a hand-edited or stale tree.
                try:
                    copy_name = frontmatter_name(copy / "SKILL.md")
                except ValueError as exc:
                    err(copy / "SKILL.md", str(exc))
                    copy_name = None
                if copy_name is not None:
                    err(
                        copy / "SKILL.md",
                        f"plugin skill copy must carry NO frontmatter name: "
                        f"(found '{copy_name}') so the /-autocomplete label "
                        f"falls back to the {plugin_name}:{leaf} invocation — "
                        f"re-run scripts/sync-plugins.sh {bundle_id}",
                    )

        if codex_enabled and (source not in codex.get("excludeSkills", []) and (codex.get("components") or {}).get("skills", True)):
            copy = repo / "dist/codex/plugins" / codex_plugin_name / "skills" / leaf
            skill_md = copy / "SKILL.md"
            if not skill_md.is_file():
                err(
                    bundle,
                    f"Skill '{source}' declared for Codex target but missing plugin copy "
                    f"plugins/{codex_plugin_name}/skills/{leaf}/SKILL.md",
                )
            else:
                try:
                    parts = skill_md.read_text(encoding="utf-8").split("---\n", 2)
                    if len(parts) < 3 or parts[0].strip():
                        raise ValueError("missing YAML frontmatter")
                    frontmatter = yaml.safe_load(parts[1]) or {}
                    if not isinstance(frontmatter, dict):
                        raise ValueError("frontmatter must be a mapping")
                except (ValueError, yaml.YAMLError) as exc:
                    err(skill_md, f"invalid Codex skill frontmatter: {exc}")
                    frontmatter = {}
                if frontmatter.get("name") != leaf:
                    err(skill_md, "Codex skill name must match its leaf directory")
                description = frontmatter.get("description")
                if "description" not in frontmatter:
                    err(skill_md, "Codex skill frontmatter missing required 'description'")
                elif not isinstance(description, str) or not description.strip():
                    err(skill_md, "Codex skill description must be a non-empty string")
                elif len(description) > 1024:
                    err(skill_md, "Codex skill description exceeds 1024 characters")
                if len(leaf) > 64:
                    err(
                        skill_md,
                        f"Codex base skill name '{leaf}' exceeds 64 characters",
                    )
                if len(f"{codex_plugin_name}:{leaf}") > 129:
                    err(
                        skill_md,
                        f"Codex qualified skill name '{codex_plugin_name}:{leaf}' exceeds "
                        "129 characters",
                    )

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

if [ $errors -gt 0 ]; then
  echo ""
  echo "Plugin/skill validation failed with $errors error(s)"
  exit 1
fi

echo ""
python3 "$REPO_ROOT/scripts/codex_package.py" "$REPO_ROOT" --validate
echo "All plugins and skills valid"
