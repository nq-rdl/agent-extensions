#!/usr/bin/env bash
#
# announce-capabilities.sh — SessionStart hook.
#
# Enumerates the skills, slash-commands and MCP servers present in *this*
# runner and injects a concise summary as `additionalContext`, so Claude is
# aware of them even on a blank / isolated runner (a GitHub Action job, a web
# sandbox) where it would otherwise have no cheap way to discover what was
# provisioned. This is the awareness companion to the explicit plugin install
# done in the Claude workflows (see .github/workflows/claude*.yml) and the
# enabledPlugins in .claude/settings.json.
#
# Output contract (Claude Code SessionStart hook): emit a single JSON object
# with hookSpecificOutput.additionalContext, or — as a fallback — plain text on
# stdout (also accepted). The hook must never fail the session, so it always
# exits 0.
#
# Refs: code.claude.com/docs/en/hooks-guide (SessionStart, additionalContext).

set -u

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-${GITHUB_WORKSPACE:-$(pwd)}}"

# --- gather sections -------------------------------------------------------

lines=()
add() { lines+=("$1"); }

# Join deduped stdin lines with a literal ", ". Avoids `paste -sd', '`, whose
# multi-char delimiter is cycled char-by-char (a,b c) on GNU and truncated to
# the first char (a,b) on BSD — neither yields stable comma+space separation.
join_comma() { sort -u | awk 'NR > 1 { printf ", " } { printf "%s", $0 }'; }

# Repo slash-commands (.claude/commands/*.md)
commands=()
if [ -d "$PROJECT_DIR/.claude/commands" ]; then
  for f in "$PROJECT_DIR"/.claude/commands/*.md; do
    [ -e "$f" ] || continue
    name="$(basename "$f" .md)"
    commands+=("/$name")
  done
fi

# Repo skills (.claude/skills/*/SKILL.md) — name + first line of description
skills=()
if [ -d "$PROJECT_DIR/.claude/skills" ]; then
  for s in "$PROJECT_DIR"/.claude/skills/*/SKILL.md; do
    [ -e "$s" ] || continue
    sname="$(sed -n 's/^name:[[:space:]]*//p' "$s" | head -n1)"
    [ -n "$sname" ] || sname="$(basename "$(dirname "$s")")"
    # Description's first human line. Handle BOTH the inline form
    # (`description: text`) and YAML block/folded scalars (`description: >-` or
    # `|` followed by indented lines): a bare `sed` on the `description:` line
    # would capture the literal `>-`/`|` indicator for the folded form. For a
    # block indicator (or an empty value) fall through to the first non-empty
    # continuation line, and strip one layer of surrounding quotes.
    sdesc="$(awk -v sq="'" '
      /^description:([[:space:]]|$)/ {
        line = $0
        sub(/^description:[[:space:]]*/, "", line)
        if (line == "" || line ~ /^[|>][+-]?[[:space:]]*$/) {
          # The text is on the following INDENTED continuation line(s). Reset
          # first so a missing continuation (e.g. an indicator at EOF) yields an
          # empty description rather than the literal `>-`/`|`. Skip blank lines,
          # but STOP at a column-0 line — the closing `---` or a sibling key is
          # not part of this scalar and must never be taken as the description.
          line = ""
          while ((getline nl) > 0) {
            if (nl ~ /^[[:space:]]*$/) continue
            if (nl !~ /^[[:space:]]/) break
            sub(/^[[:space:]]+/, "", nl); line = nl; break
          }
        }
        sub(/^"/, "", line); sub(/"$/, "", line)
        sub("^" sq, "", line); sub(sq "$", "", line)
        print line
        exit
      }
    ' "$s" | cut -c1-120)"
    if [ -n "$sdesc" ]; then
      skills+=("/$sname — $sdesc")
    else
      skills+=("/$sname")
    fi
  done
fi

# MCP servers (.mcp.json at root, plus any mcpServers in .claude/settings.json)
mcp=()
if command -v jq >/dev/null 2>&1; then
  for cfg in "$PROJECT_DIR/.mcp.json" "$PROJECT_DIR/.claude/settings.json"; do
    [ -f "$cfg" ] || continue
    while IFS= read -r srv; do
      [ -n "$srv" ] && mcp+=("$srv")
    done < <(jq -r '(.mcpServers // {}) | keys[]?' "$cfg" 2>/dev/null)
  done
fi

# Enabled plugins — read the authoritative enabledPlugins map from the project
# settings (true => enabled). This is checked out in both web and Action runs
# and avoids listing un-enabled marketplace plugins or version-dir noise.
plugins=()
if command -v jq >/dev/null 2>&1 && [ -f "$PROJECT_DIR/.claude/settings.json" ]; then
  while IFS= read -r p; do
    [ -n "$p" ] && plugins+=("$p")
  done < <(jq -r '(.enabledPlugins // {}) | to_entries[] | select(.value == true) | .key' \
             "$PROJECT_DIR/.claude/settings.json" 2>/dev/null)
fi

# --- render ----------------------------------------------------------------

add "## Runner capabilities"
add ""
add "This session runs on an isolated/blank runner. The following project capabilities are present and ready to use — prefer a relevant skill before acting, and invoke skills explicitly with the Skill tool / \`/skill-name\` (plugin skills use \`/plugin:skill\`)."
add ""

if [ "${#skills[@]}" -gt 0 ]; then
  add "**Repo skills (.claude/skills):**"
  for x in "${skills[@]}"; do add "- $x"; done
  add ""
fi

if [ "${#commands[@]}" -gt 0 ]; then
  add "**Slash-commands (.claude/commands):** ${commands[*]}"
  add ""
fi

if [ "${#mcp[@]}" -gt 0 ]; then
  # de-dupe
  uniq_mcp="$(printf '%s\n' "${mcp[@]}" | join_comma)"
  add "**MCP servers:** $uniq_mcp"
  add ""
fi

if [ "${#plugins[@]}" -gt 0 ]; then
  uniq_plugins="$(printf '%s\n' "${plugins[@]}" | join_comma)"
  add "**Enabled plugins:** $uniq_plugins"
  add "Their skills are available via the Skill tool (\`/plugin:skill\`) — list and invoke as relevant."
  add ""
fi

context="$(printf '%s\n' "${lines[@]}")"

# --- emit ------------------------------------------------------------------

if command -v jq >/dev/null 2>&1; then
  jq -cn --arg ctx "$context" \
    '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $ctx}}'
else
  printf '%s\n' "$context"
fi

exit 0
