#!/usr/bin/env bash
#
# announce-capabilities.sh — SessionStart hook.
#
# Enumerates the skills, slash-commands and MCP servers present in *this*
# runner and injects a concise summary as `additionalContext`, so Claude is
# aware of them even on a blank / isolated runner (a GitHub Action job, a web
# sandbox) where it would otherwise have no cheap way to discover what was
# provisioned. This is the awareness companion to the platform's declarative plugin
# install (enabledPlugins in .claude/settings.json) and any vendored skills under
# .claude/skills/. Plugins are reported as *installed* (verified against `claude
# plugin list`), not merely declared, so a plugin that failed to install is flagged
# rather than silently announced as present.
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
# had not completed (its marketplace source was unreachable). Cross-check the two
# so a declared plugin that did not install is surfaced, not hidden. When the claude CLI is unavailable (some Action
# runners) or errors, we cannot verify, so report the declared set as UNVERIFIED.
# NOTE: jq is required for the whole plugin canary — reading the declared set AND the
# verify step both use it. Without jq this section is silent (no declared/installed
# lines at all); jq is present in every target environment this hook runs in, and the
# hook's own JSON emit already depends on it.
declared_plugins=()
if command -v jq >/dev/null 2>&1 && [ -f "$PROJECT_DIR/.claude/settings.json" ]; then
  while IFS= read -r p; do
    [ -n "$p" ] && declared_plugins+=("$p")
  done < <(jq -r '(.enabledPlugins // {}) | to_entries[] | select(.value == true) | .key' \
             "$PROJECT_DIR/.claude/settings.json" 2>/dev/null)
fi

# Actually installed + enabled plugin ids, from `claude plugin list --json` (an
# array of {id, enabled, scope, projectPath, …}). Parse the JSON with jq rather than
# scraping the human table: that table's bullet is a non-ASCII `❯` that silently broke an
# earlier `>`-based parser (it matched nothing, so every declared plugin looked
# NOT-installed even with 80+ actually installed). Key "can we verify?" on getting
# PARSEABLE JSON back, not on non-empty output: a successful `[]` means "nothing
# installed" (declared plugins genuinely NOT installed), distinct from the CLI missing /
# erroring / emitting non-JSON ("cannot verify") — those must not be demoted to a false
# "NOT installed".
#
# Scope filter: an entry enabled at PROJECT scope for a DIFFERENT project carries a
# `projectPath` pointing at that other project's dir; user/global-scoped entries have NO
# projectPath field. Keep an entry only when it applies to THIS project — it has no
# projectPath (user/global), OR its projectPath equals the current project dir — so a
# plugin enabled only for another project's worktree is NOT falsely counted as installed
# here. (Such a plugin then correctly falls through to "declared but NOT installed" for
# this project.) PROJECT_DIR (computed above) is passed to jq via --arg.
installed_enabled=()
have_plugin_list=0
if command -v claude >/dev/null 2>&1 && command -v jq >/dev/null 2>&1; then
  # ONE jq call does the shape check, scope filter AND extraction, and its exit status is
  # CAPTURED — the result is assigned to _ids, not read through a process substitution whose
  # exit is invisible. A non-array shape (a future `{"plugins":[…]}` wrapper or an error
  # object) raises error() => jq exits non-zero => the `&&` fails => have_plugin_list stays
  # 0 => "cannot verify", never a silently-truncated list read as a false "NOT installed". A
  # successful empty array `[]` yields no ids and exit 0 => genuinely "NOT installed". (No
  # `-e`: it would wrongly treat the legitimate empty-array case as an error.)
  if _pl="$(claude plugin list --json 2>/dev/null)" \
     && _ids="$(printf '%s' "$_pl" | jq -r --arg proj "$PROJECT_DIR" '
          if type == "array"
          then .[] | select(type == "object" and .enabled == true
                   and ((.projectPath // null) == null or .projectPath == $proj))
               | .id // empty
          else error("claude plugin list --json did not return an array") end' 2>/dev/null)"; then
    have_plugin_list=1
    while IFS= read -r id; do
      [ -n "$id" ] && installed_enabled+=("$id")
    done <<< "$_ids"
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
  add "**Enabled plugins (installed/enabled):** $uniq_plugins"
  add "Installed and enabled per \`claude plugin list\`. This confirms install, not in-process activation: on the web's FIRST session a freshly-installed plugin's skills/hooks can land too late to be active this turn (issue #63028). If a \`/plugin:skill\` is missing, a session resume on the same VM may surface it (a fresh session re-clones and can re-fail) — the same-session re-scan does not cover the plugin cache, so \`/reload-skills\` will not surface it. Vendored skills under \`.claude/skills/\` avoid this entirely."
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
  add "Declared in .claude/settings.json (enabledPlugins) but not reported installed-and-enabled by \`claude plugin list --json\` — either the session-start marketplace install did not complete (unreachable source, stale index, wrong plugin id, or the in-sandbox git proxy 403'ing an external marketplace) or the plugin is installed but disabled. Declarative plugins are best-effort and their web activation is unverified; for a guaranteed first-session skill, VENDOR it into \`.claude/skills/\` (part of the clone)."
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
# in #160). So it surfaces vendored skills committed under .claude/ (and any a project
# fetched into ~/.claude/skills/), but NOT a marketplace plugin — a declared plugin that
# did not install at session start only appears the NEXT session (and is flagged above).
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
