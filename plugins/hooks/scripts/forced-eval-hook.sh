#!/bin/bash
# UserPromptSubmit hook that surfaces available skills as advisory context.
#
# Triggers only when the prompt expresses intent to use a skill — an action
# verb (use, invoke, run, apply, ...) appears near "skill"/"skills". Silent
# no-op otherwise. Output is the skill catalogue, emitted via the
# UserPromptSubmit additionalContext channel as advisory (not coercive) text.
#
# Dynamically discovers available skills from:
#   1. Standalone skills:     ~/.claude/skills/*/SKILL.md
#   2. Standalone sub-skills: ~/.claude/skills/*/*/SKILL.md
#   3. Plugin skills:         <installPath>/skills/*/SKILL.md
#   4. Plugin commands:       <installPath>/commands/*.md
# Plugin install paths come from ~/.claude/plugins/installed_plugins.json.
#
# Cache: ${XDG_CACHE_HOME:-$HOME/.cache}/claude-hooks/skill-catalog.cache
# Invalidated when: skills dir, installed_plugins.json, or this script changes.
# Requires jq for plugin scanning; degrades gracefully if missing.

set -euo pipefail

# ---------------------------------------------------------------------------
# Intent gate — fire only when an action verb sits near "skill"/"skills",
# signalling intent to use one. Metalinguistic mentions ("skills should
# always be reviewed") no longer trigger a catalogue dump. Silent no-op
# otherwise.
# ---------------------------------------------------------------------------
input=$(cat)

if command -v jq >/dev/null 2>&1; then
  prompt=$(printf '%s' "$input" | jq -r '.prompt // empty')
else
  prompt=$(printf '%s' "$input" | grep -oP '"prompt"\s*:\s*"\K[^"]+' || true)
fi

intent='use|using|invoke|invoking|run|running|apply|applying|activate|activating|load|loading|call|calling|trigger|triggering|consider|considering|check|checking'
if ! printf '%s' "$prompt" | grep -qiE "\b(${intent})\b.{0,40}\bskills?\b|\bskills?\b.{0,40}\b(${intent})\b"; then
  exit 0
fi

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SKILLS_DIR="${HOME}/.claude/skills"
PLUGINS_JSON="${HOME}/.claude/plugins/installed_plugins.json"
CACHE_DIR="${XDG_CACHE_HOME:-${HOME}/.cache}/claude-hooks"
CACHE_FILE="${CACHE_DIR}/skill-catalog.cache"
SEEN_NAMES_FILE=""

# ---------------------------------------------------------------------------
# Parse YAML frontmatter — extracts name and description
# Usage: parse_frontmatter <file>
# Output: "name|description" (one line; name is empty for command files)
# ---------------------------------------------------------------------------
parse_frontmatter() {
  awk '
  BEGIN { in_front=0; name=""; desc=""; state=""; }
  /^---$/ {
    if (in_front == 0) { in_front=1; next }
    else { exit }
  }
  !in_front { next }
  state == "folded_wait" {
    stripped=$0; gsub(/^[[:space:]]+/, "", stripped);
    if (stripped != "" && stripped !~ /^[a-zA-Z_-]+:/) {
      desc=stripped; state="";
    }
    next;
  }
  /^name:/ {
    state="";
    val=$0; sub(/^name:[[:space:]]*/, "", val); gsub(/"/, "", val);
    name=val; next;
  }
  /^description:/ {
    state="";
    val=$0; sub(/^description:[[:space:]]*/, "", val);
    if (val == ">" || val == "|") {
      state="folded_wait";
    } else {
      gsub(/^"/, "", val); gsub(/"$/, "", val);
      desc=val;
    }
    next;
  }
  END { print name "|" desc }
  ' "$1"
}

# ---------------------------------------------------------------------------
# Format "key|description" lines → "  - key: description" (80-char limit)
# ---------------------------------------------------------------------------
format_list() {
  awk '
  {
    sep=index($0, "|");
    if (sep == 0) next;
    key=substr($0, 1, sep-1);
    desc=substr($0, sep+1);
    if (length(desc) > 80) {
      s=substr(desc, 1, 80);
      while (length(s) > 0 && substr(s, length(s), 1) != " ")
        s=substr(s, 1, length(s)-1);
      if (length(s) == 0) s=substr(desc, 1, 80);
      else s=substr(s, 1, length(s)-1);
      desc=s "...";
    }
    print "  - " key ": " desc;
  }'
}

# ---------------------------------------------------------------------------
# Cache freshness — returns 0 if fresh, 1 if stale/missing
# ---------------------------------------------------------------------------
check_cache() {
  [[ -f "$CACHE_FILE" ]] || return 1
  local cache_mtime
  cache_mtime=$(stat -c %Y "$CACHE_FILE" 2>/dev/null) || return 1
  local src src_mtime
  for src in "$0" "$SKILLS_DIR" "$PLUGINS_JSON"; do
    [[ -e "$src" ]] || continue
    src_mtime=$(stat -c %Y "$src" 2>/dev/null) || continue
    [[ "$src_mtime" -le "$cache_mtime" ]] || return 1
  done
  return 0
}

# ---------------------------------------------------------------------------
# Atomic cache write
# ---------------------------------------------------------------------------
write_cache() {
  mkdir -p "$CACHE_DIR"
  local tmp
  tmp=$(mktemp "${CACHE_FILE}.XXXXXX")
  printf '%s\n' "$1" > "$tmp"
  mv "$tmp" "$CACHE_FILE"
}

# ---------------------------------------------------------------------------
# Scan standalone skills (level 1 + 2)
# ---------------------------------------------------------------------------
scan_standalone_skills() {
  local skill_md parsed name desc key parent sub

  for skill_md in "$SKILLS_DIR"/*/SKILL.md; do
    [[ -f "$skill_md" ]] || continue
    parsed=$(parse_frontmatter "$skill_md")
    name="${parsed%%|*}"
    desc="${parsed#*|}"
    [[ -n "$desc" ]] || continue
    key=$(basename "$(dirname "$skill_md")")
    [[ -n "$name" ]] && echo "$name" >> "$SEEN_NAMES_FILE"
    printf '%s|%s\n' "$key" "$desc"
  done

  for skill_md in "$SKILLS_DIR"/*/*/SKILL.md; do
    [[ -f "$skill_md" ]] || continue
    parsed=$(parse_frontmatter "$skill_md")
    name="${parsed%%|*}"
    desc="${parsed#*|}"
    [[ -n "$desc" ]] || continue
    sub=$(basename "$(dirname "$skill_md")")
    parent=$(basename "$(dirname "$(dirname "$skill_md")")")
    key="${parent}/${sub}"
    [[ -n "$name" ]] && echo "$name" >> "$SEEN_NAMES_FILE"
    printf '%s|%s\n' "$key" "$desc"
  done
}

# ---------------------------------------------------------------------------
# Emit plugin names + install paths from installed_plugins.json
# ---------------------------------------------------------------------------
get_plugin_paths() {
  jq -r '
    .plugins | to_entries[] |
    (.key | split("@")[0]) as $name |
    .value[0].installPath as $path |
    "\($name)|\($path)"
  ' "$PLUGINS_JSON" 2>/dev/null
}

# ---------------------------------------------------------------------------
# Scan plugin skills (dedup against standalone)
# ---------------------------------------------------------------------------
scan_plugin_skills() {
  local plugin install_path skill_md parsed name desc skill_dir key

  while IFS='|' read -r plugin install_path; do
    [[ -d "${install_path}/skills" ]] || continue
    for skill_md in "${install_path}/skills"/*/SKILL.md; do
      [[ -f "$skill_md" ]] || continue
      parsed=$(parse_frontmatter "$skill_md")
      name="${parsed%%|*}"
      desc="${parsed#*|}"
      [[ -n "$desc" ]] || continue
      if [[ -n "$name" ]] && grep -qxF "$name" "$SEEN_NAMES_FILE" 2>/dev/null; then
        continue
      fi
      skill_dir=$(basename "$(dirname "$skill_md")")
      key="${plugin}:${skill_dir}"
      printf '%s|%s\n' "$key" "$desc"
    done
  done < <(get_plugin_paths)
}

# ---------------------------------------------------------------------------
# Scan plugin commands
# ---------------------------------------------------------------------------
scan_plugin_commands() {
  local plugin install_path cmd_md parsed desc stem key

  while IFS='|' read -r plugin install_path; do
    [[ -d "${install_path}/commands" ]] || continue
    for cmd_md in "${install_path}/commands"/*.md; do
      [[ -f "$cmd_md" ]] || continue
      parsed=$(parse_frontmatter "$cmd_md")
      desc="${parsed#*|}"
      [[ -n "$desc" ]] || continue
      stem=$(basename "$cmd_md" .md)
      key="${plugin}:${stem}"
      printf '%s|%s\n' "$key" "$desc"
    done
  done < <(get_plugin_paths)
}

# ---------------------------------------------------------------------------
# Build the advisory skill catalogue
#
# Descriptive, non-coercive framing wrapped in a stable <skill-catalog> fence
# so downstream agents can recognise it as hook-provided context rather than
# an injected instruction. The <available_skills> / <available_commands>
# blocks are the useful payload.
# ---------------------------------------------------------------------------
build_prompt() {
  local skills_block="$1"
  local commands_block="$2"

  printf '<skill-catalog>\n'
  printf 'Skills and commands available for this prompt are listed below, discovered\n'
  printf 'from your local Claude configuration by a UserPromptSubmit hook. Consider\n'
  printf 'whether any fit the task; if one does, load it with the Skill tool. Advisory only.\n'
  printf '\n'
  printf '<available_skills>\n%s</available_skills>\n' "$skills_block"

  if [[ -n "$commands_block" ]]; then
    printf '\n<available_commands>\n%s</available_commands>\n' "$commands_block"
  fi

  printf '</skill-catalog>\n'
}

# ---------------------------------------------------------------------------
# Emit the catalogue. Preferred channel is the UserPromptSubmit
# additionalContext field (added discreetly as system context); falls back to
# plain stdout when jq is unavailable.
# ---------------------------------------------------------------------------
emit() {
  local payload="$1"
  if command -v jq >/dev/null 2>&1; then
    jq -n --arg ctx "$payload" '{
      hookSpecificOutput: {
        hookEventName: "UserPromptSubmit",
        additionalContext: $ctx
      }
    }'
  else
    printf '%s\n' "$payload"
  fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
  if check_cache; then
    emit "$(cat "$CACHE_FILE")"
    return 0
  fi

  SEEN_NAMES_FILE=$(mktemp)
  trap 'rm -f "$SEEN_NAMES_FILE"' EXIT

  local skill_data
  skill_data=$(scan_standalone_skills | sort)

  local cmd_data=""
  if command -v jq >/dev/null 2>&1 && [[ -f "$PLUGINS_JSON" ]]; then
    local ps pc
    ps=$(scan_plugin_skills | sort)
    pc=$(scan_plugin_commands | sort)
    if [[ -n "$ps" ]]; then
      skill_data=$(printf '%s\n%s\n' "$skill_data" "$ps" | grep -v '^$' | sort)
    fi
    cmd_data="$pc"
  else
    printf 'forced-eval-hook: jq not found or %s missing — plugin skills skipped\n' \
      "$PLUGINS_JSON" >&2
  fi

  local skills_block
  skills_block=$(printf '%s\n' "$skill_data" | grep -v '^$' | format_list)

  local commands_block=""
  if [[ -n "$cmd_data" ]]; then
    commands_block=$(printf '%s\n' "$cmd_data" | grep -v '^$' | format_list)
  fi

  local output
  output=$(build_prompt "$skills_block" "$commands_block")
  write_cache "$output"
  emit "$output"
}

main
