#!/usr/bin/env bash
#
# remind-review-agents.sh — PreToolUse hook (Edit|Write|MultiEdit).
#
# `.claude/` is contributor tooling for developing THIS marketplace (settings,
# hooks, helper scripts, the curated external-plugin set) — not part of the
# published catalog. When Claude is about to edit/write a file under `.claude/`,
# inject a short, factual reminder that AGENTS.md (repo root) is the authoritative
# guide for such changes, so settings and docs don't drift (see this repo's own
# history of removing-then-restoring the documented curated plugin set).
#
# Contract (Claude Code PreToolUse hook): read the tool-call JSON on stdin; if the
# target path is under `.claude/`, emit exit-0 JSON with
# hookSpecificOutput.additionalContext (NO permissionDecision — the normal
# permission flow is left untouched). For any other path, emit nothing. The hook
# must never disrupt a tool call, so it always exits 0.
#
# Phrasing is DECLARATIVE on purpose: imperative "system command" wording trips
# Claude's prompt-injection defenses and gets surfaced to the user instead of
# acted on (see the claude-code:hook skill, references/prompt-injection.rst).
#
# Portable: uses jq when present, falls back to grep/sed otherwise. No bashisms
# beyond `case`. Refs: code.claude.com/docs/en/hooks-guide (PreToolUse).

set -u

payload="$(cat)"

# Extract the edited file path from the tool input.
if command -v jq >/dev/null 2>&1; then
  path="$(printf '%s' "$payload" | jq -r '.tool_input.file_path // empty' 2>/dev/null)"
else
  path="$(printf '%s' "$payload" \
    | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' \
    | head -n1 \
    | sed 's/.*"file_path"[[:space:]]*:[[:space:]]*"//; s/"$//')"
fi

case "$path" in
  */.claude/*|.claude/*)
    cat <<'JSON'
{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"This path is under .claude/ — contributor tooling for developing the rdl marketplace (project settings, hooks, helper scripts, the curated external-plugin set), not part of the published catalog. AGENTS.md at the repo root is the authoritative guide for .claude/ changes: CONTRIBUTING.md covers the development requirements and docs/ holds the project documentation (docs/external-marketplaces.md documents the curated plugin set). Reviewing AGENTS.md in full before changing .claude/ keeps the project settings and docs in sync."}}
JSON
    ;;
esac

exit 0
