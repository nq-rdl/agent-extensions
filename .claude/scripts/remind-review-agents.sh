#!/usr/bin/env bash
#
# remind-review-agents.sh — PreToolUse hook (Edit|Write|MultiEdit).
#
# `.claude/` is contributor tooling for developing THIS marketplace (settings,
# hooks, helper scripts, the curated external-plugin set) — not part of the
# published catalog. When Claude is about to edit/write a file under this repo's
# `.claude/`, inject a short, factual reminder that AGENTS.md (repo root) is the
# authoritative guide for such changes, so settings and docs don't drift (this
# set is easy to edit out of sync with docs/external-marketplaces.md).
#
# Contract (Claude Code PreToolUse hook): read the tool-call JSON on stdin; if the
# target path is under the project's `.claude/`, emit exit-0 JSON with
# hookSpecificOutput.additionalContext (NO permissionDecision — the normal
# permission flow is left untouched). For any other path, emit nothing. The
# reminder is emitted at most once per session (a marker keyed on session_id), so
# a multi-file `.claude/` change isn't re-nagged on every edit. The hook must
# never disrupt a tool call, so it always exits 0.
#
# Phrasing is DECLARATIVE on purpose: imperative "system command" wording trips
# Claude's prompt-injection defenses and gets surfaced to the user instead of
# acted on (see the claude-code:hook skill, references/prompt-injection.rst).
#
# Portable: POSIX-clean (no bash-only constructs). Field extraction uses jq when
# present; the grep/sed fallback is best-effort (it cannot parse a value that
# contains an escaped quote), so jq is the supported path. settings.json invokes
# this via `bash <script>`, so the executable bit is not load-bearing. Refs:
# code.claude.com/docs/en/hooks-guide (PreToolUse).

set -u

payload="$(cat)"

# json_str <jq-path> <fallback-key>: extract a JSON string field from the
# payload — jq when available, else a best-effort grep/sed scan of the first
# matching key. The fallback stops at the first unescaped quote, so a value
# containing an escaped quote (rare in a path) is truncated; jq is exact.
json_str() {
  if command -v jq >/dev/null 2>&1; then
    printf '%s' "$payload" | jq -r "$1 // empty" 2>/dev/null
  else
    printf '%s' "$payload" \
      | grep -o "\"$2\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" \
      | head -n1 \
      | sed "s/.*\"$2\"[[:space:]]*:[[:space:]]*\"//; s/\"\$//"
  fi
}

path="$(json_str '.tool_input.file_path' 'file_path')"

# Remind only for edits under THIS repo's .claude/. Anchor absolute paths to
# $CLAUDE_PROJECT_DIR so a checkout that merely *lives* beneath some other
# `.claude/` ancestor (e.g. a clone under ~/.claude/) doesn't trip the reminder
# on every edit; a relative path is already repo-rooted, so a bare `.claude/`
# prefix is safe. If the project dir isn't in the environment, fall back to an
# unanchored match so the guardrail still fires.
proj="${CLAUDE_PROJECT_DIR:-}"
under_claude=""
if [ -n "$proj" ]; then
  case "$path" in
    "$proj"/.claude/*|.claude/*) under_claude=1 ;;
  esac
else
  case "$path" in
    */.claude/*|.claude/*) under_claude=1 ;;
  esac
fi

[ -n "$under_claude" ] || exit 0

# Emit at most once per session (best-effort). session_id comes from Claude Code;
# sanitize it to a safe filename charset before using it in a marker path. If it
# is absent or the marker can't be written, fall through and emit.
sid="$(json_str '.session_id' 'session_id' | tr -cd 'A-Za-z0-9._-')"
if [ -n "$sid" ]; then
  marker="${TMPDIR:-/tmp}/claude-remind-review.${sid}"
  [ -e "$marker" ] && exit 0
  : > "$marker" 2>/dev/null || true
fi

cat <<'JSON'
{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"This path is under .claude/ — contributor tooling for developing the rdl-agent-extensions marketplace (project settings, hooks, helper scripts, the curated external-plugin set), not part of the published catalog. AGENTS.md at the repo root is the authoritative guide for .claude/ changes: CONTRIBUTING.md covers the development requirements and docs/ holds the project documentation (docs/external-marketplaces.md documents the curated plugin set). Reviewing AGENTS.md in full before changing .claude/ keeps the project settings and docs in sync."}}
JSON

exit 0
