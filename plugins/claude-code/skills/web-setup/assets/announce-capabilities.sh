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
# enabledPlugins in .claude/settings.json. Plugins are reported as *installed*
# (verified against `claude plugin list`), not merely declared, so a plugin that
# failed to install is flagged rather than silently announced as present.
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

# Enabled plugins — report what is actually INSTALLED + enabled, not merely
# DECLARED. The intended set is .claude/settings.json (enabledPlugins == true);
# the *loaded* set comes from `claude plugin list`. Reporting the declared set
# alone produced a false positive — the banner looked healthy while the slash
# menu was empty because the platform's session-start install of a declared plugin
# had not completed (its marketplace source was unreachable — see
# docs/claude-code-web.md). Cross-check the two so a declared plugin that did not
# install is surfaced, not hidden. When the claude CLI is unavailable (some Action
# runners) or errors, we cannot verify, so report the declared set as UNVERIFIED.
declared_plugins=()
if command -v jq >/dev/null 2>&1 && [ -f "$PROJECT_DIR/.claude/settings.json" ]; then
  while IFS= read -r p; do
    [ -n "$p" ] && declared_plugins+=("$p")
  done < <(jq -r '(.enabledPlugins // {}) | to_entries[] | select(.value == true) | .key' \
             "$PROJECT_DIR/.claude/settings.json" 2>/dev/null)
fi

# Actually installed + enabled plugin ids, parsed from `claude plugin list`
# (each plugin is a `> <id>` line followed by a `Status: … enabled` line). Key
# "can we verify?" on the COMMAND'S EXIT STATUS, not on non-empty output: a
# successful-but-empty list means "nothing installed" (so declared plugins are
# genuinely NOT installed), which must be distinguished from the CLI missing/erroring
# ("cannot verify"). Treating empty output as "cannot verify" would wrongly demote a
# real failed-install to merely "unverified".
installed_enabled=()
have_plugin_list=0
if command -v claude >/dev/null 2>&1; then
  if _pl="$(claude plugin list 2>/dev/null)"; then
    have_plugin_list=1
    while IFS= read -r id; do
      [ -n "$id" ] && installed_enabled+=("$id")
    done < <(printf '%s\n' "$_pl" | awk '
      /^[[:space:]]*>[[:space:]]/ { id = $2; next }
      /Status:/ { if (id != "" && /enabled/) print id; id = ""; next }
    ')
  fi
fi

# Partition the declared set into verified-loaded vs declared-but-missing — but
# only when we have a plugin list to verify against. Without one we must NOT claim
# the declared plugins are installed (declared ≠ installed): report them as a
# separate UNVERIFIED state so a failed install is never masked as "installed".
plugins=()
missing_plugins=()
unverified_plugins=()
if [ "$have_plugin_list" -eq 1 ]; then
  installed_blob="$(printf '%s\n' ${installed_enabled[@]+"${installed_enabled[@]}"})"
  for d in ${declared_plugins[@]+"${declared_plugins[@]}"}; do
    if printf '%s\n' "$installed_blob" | grep -qxF -- "$d"; then
      plugins+=("$d")
    else
      missing_plugins+=("$d")
    fi
  done
else
  unverified_plugins=(${declared_plugins[@]+"${declared_plugins[@]}"})
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
  add "**Enabled plugins (installed):** $uniq_plugins"
  add "Their skills are available via the Skill tool (\`/plugin:skill\`) — list and invoke as relevant."
  add ""
fi

if [ "${#unverified_plugins[@]}" -gt 0 ]; then
  uniq_unverified="$(printf '%s\n' "${unverified_plugins[@]}" | join_comma)"
  add "**Enabled plugins (declared; install unverified):** $uniq_unverified"
  add "Declared in .claude/settings.json, but \`claude plugin list\` was unavailable here, so their install could NOT be confirmed (this is not a claim that they are installed). If a \`/plugin:skill\` is missing, the marketplace install likely did not complete — vendor the skill into \`.claude/skills/\` for a guaranteed first-session copy."
  add ""
fi

if [ "${#missing_plugins[@]}" -gt 0 ]; then
  uniq_missing="$(printf '%s\n' "${missing_plugins[@]}" | join_comma)"
  add "**⚠️ Declared but NOT installed:** $uniq_missing"
  add "Enabled in .claude/settings.json but absent from \`claude plugin list\`. On Claude Code (web) declared plugins install at session start from their marketplace (web docs, \"what carries over\"), so this line means that install did not complete — commonly the marketplace's source was unreachable (check the environment's network access), the local index was stale, or the plugin id is wrong. Declarative plugins are best-effort and race skill enumeration on the first session; for a guaranteed first-session skill, VENDOR it into \`.claude/skills/\` (part of the clone) — see the cc-web-setup skill."
  add ""
fi

context="$(printf '%s\n' "${lines[@]}")"

# --- emit ------------------------------------------------------------------

# On a cloud session, also request a same-session skill/command re-scan via
# `reloadSkills: true`, so any repo-local skills/commands committed under
# .claude/ are picked up once all SessionStart hooks return. Gate on
# CLAUDE_CODE_REMOTE so a local session does not pay for a needless re-scan.
# NOTE: this re-scan covers the loose skill/command dirs (~/.claude/skills/,
# .claude/skills/, .claude/commands/) only, NOT the plugin install cache (confirmed
# in #160). So it surfaces vendored skills and anything bootstrap-web.sh fetched into
# ~/.claude/skills/, but NOT a marketplace plugin — a declared plugin that did not
# install at session start only appears the NEXT session (and is flagged above).
if command -v jq >/dev/null 2>&1; then
  if [ "${CLAUDE_CODE_REMOTE:-}" = "true" ]; then
    jq -cn --arg ctx "$context" \
      '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $ctx, reloadSkills: true}}'
  else
    jq -cn --arg ctx "$context" \
      '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $ctx}}'
  fi
else
  printf '%s\n' "$context"
fi

exit 0
