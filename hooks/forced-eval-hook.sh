#!/bin/bash
# UserPromptSubmit hook that forces explicit skill evaluation
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
#
# Installation:
#   1. Copy forced-eval-hook.json into your project's .claude/settings.local.json
#      (or merge the hooks block into your existing settings).
#   2. Ensure this script is accessible at the path referenced in the JSON
#      (default: hooks/forced-eval-hook.sh relative to your project root).
#      Update the "command" path in the JSON if you place it elsewhere.
#   3. Ensure this script is executable: chmod +x forced-eval-hook.sh
#
# How it works:
#   - On every UserPromptSubmit event, this script emits a structured prompt
#     that Claude sees as additional context.
#   - The prompt forces a 3-step sequence: Evaluate → Activate → Implement.
#   - Claude must call Skill() for every skill or command it marks YES.

SKILLS_DIR="${HOME}/.claude/skills"
PLUGINS_JSON="${HOME}/.claude/plugins/installed_plugins.json"
CACHE_DIR="${XDG_CACHE_HOME:-${HOME}/.cache}/claude-hooks"
CACHE_FILE="${CACHE_DIR}/skill-catalog.cache"
SEEN_NAMES_FILE=""

# ---------------------------------------------------------------------------
# Parse YAML frontmatter — extracts name and description
# Usage: parse_frontmatter <file>
# Output: "name|description" (one line; name is empty for command files)
#
# Handles these description formats:
#   description: Plain one-liner text
#   description: "Double-quoted text"
#   description: >          ← folded block, indented continuation
#     Indented first line
#   description: >          ← folded block, unindented continuation (ansible)
#   Unindented first line
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
# Input: stdin lines of "key|description"
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
# Output: "key|description" lines
# Side-effect: appends frontmatter names to $SEEN_NAMES_FILE for dedup
# ---------------------------------------------------------------------------
scan_standalone_skills() {
  local skill_md parsed name desc key parent sub

  # Level 1 — ~/.claude/skills/*/SKILL.md
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

  # Level 2 — ~/.claude/skills/*/*/SKILL.md (sub-skills)
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
# Output: "plugin-name|install-path" lines
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
# Scan plugin skills
# Output: "plugin:skill-dir|description" lines
# Skips skills whose frontmatter name matches a standalone skill (standalone wins)
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
      # Skip if frontmatter name matches a standalone skill
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
# Output: "plugin:command-stem|description" lines
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
# Build the forced evaluation prompt
# ---------------------------------------------------------------------------
build_prompt() {
  local skills_block="$1"
  local commands_block="$2"

  printf 'INSTRUCTION: MANDATORY SKILL ACTIVATION SEQUENCE\n'
  printf '\n'
  printf 'Before proceeding with ANY implementation, you MUST complete all three steps below.\n'
  printf '\n'
  printf '<available_skills>\n%s</available_skills>\n' "$skills_block"

  if [[ -n "$commands_block" ]]; then
    printf '\n<available_commands>\n%s</available_commands>\n' "$commands_block"
  fi

  printf '\n'
  printf 'Step 1 — EVALUATE (print this table in your response):\n'
  printf 'For EACH skill and command listed above, state:\n'
  printf '  [name] — YES/NO — [one-line reason]\n'
  printf '\n'
  printf 'Step 2 — ACTIVATE (immediately after Step 1):\n'
  printf '  IF any skills or commands are marked YES → Call Skill(name) for EACH one NOW.\n'
  printf '  IF none are YES                          → State "No skills apply" and proceed to Step 3.\n'
  printf '\n'
  printf 'Step 3 — IMPLEMENT:\n'
  printf '  Only after ALL Skill() calls from Step 2 have returned, proceed with implementation.\n'
  printf '\n'
  printf 'CRITICAL RULES:\n'
  printf '• You MUST call the Skill() tool in Step 2. Do NOT skip to implementation.\n'
  printf '• The evaluation table (Step 1) is WORTHLESS unless you ACTIVATE (Step 2).\n'
  printf '• If you skip Step 2, you have violated this instruction — stop and redo.\n'
  printf '\n'
  printf 'Example of a correct sequence:\n'
  printf '\n'
  printf '  Step 1 — Evaluate:\n'
  printf '    academic-super                  — NO  — not an academic task\n'
  printf '    charm-tui                       — YES — building a terminal UI\n'
  printf '    use-modern-go                   — YES — writing Go code\n'
  printf '    frontend-design:frontend-design — NO  — not a web UI task\n'
  printf '    commit-commands:commit          — NO  — not committing code\n'
  printf '    (... remaining skills and commands ...)\n'
  printf '\n'
  printf '  Step 2 — Activate:\n'
  printf '    > Skill(charm-tui)\n'
  printf '    > Skill(use-modern-go)\n'
  printf '\n'
  printf '  Step 3 — Implement:\n'
  printf '    (only now begin writing code)\n'
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
  # Return cached output if still fresh
  if check_cache; then
    cat "$CACHE_FILE"
    return 0
  fi

  # Temp file for standalone name tracking (dedup)
  SEEN_NAMES_FILE=$(mktemp)
  trap 'rm -f "$SEEN_NAMES_FILE"' EXIT

  # Scan standalone skills
  local skill_data
  skill_data=$(scan_standalone_skills | sort)

  # Scan plugin skills and commands (requires jq)
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

  # Format skill list
  local skills_block
  skills_block=$(printf '%s\n' "$skill_data" | grep -v '^$' | format_list)

  # Format command list (optional)
  local commands_block=""
  if [[ -n "$cmd_data" ]]; then
    commands_block=$(printf '%s\n' "$cmd_data" | grep -v '^$' | format_list)
  fi

  # Build, cache, and emit the prompt
  local output
  output=$(build_prompt "$skills_block" "$commands_block")
  write_cache "$output"
  printf '%s\n' "$output"
}

main
