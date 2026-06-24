#!/usr/bin/env bash
# PostToolUse guard — keeps /claude-code:web-setup on track. When a .claude/settings.json
# is written or edited during a setup session, verify that every enabled plugin id
# actually EXISTS in its marketplace catalog. This catches the "declared but
# non-existent plugin" failure (dataops#169): a hallucinated id whose @marketplace is
# real but whose plugin NAME is not in that marketplace — which the cover/ensure guards
# do not detect (they only check the marketplace suffix is declared), so it lands as
# "Declared but NOT installed" every session.
#
# matcher (in hooks.json) limits this to Edit|Write; the PATH filter below scopes it to
# .claude/settings.json. Advisory only: it injects context telling the model to fix the
# bad ids — it never blocks the edit, and it stays silent on a clean file or when the
# marketplace is merely unreachable (which verify reports as unverifiable, not missing).
set -euo pipefail

# Advisory-only: if jq is unavailable, no-op silently rather than erroring.
command -v jq >/dev/null 2>&1 || exit 0

input="$(cat)"
# Tolerate malformed/non-JSON stdin: a parse error must no-op, not abort.
path="$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null || true)"
case "$path" in
  */.claude/settings.json|.claude/settings.json) ;;
  *) exit 0 ;;
esac
[ -f "$path" ] || exit 0

# The verify helper ships beside the web-setup skill inside this plugin.
helper="${CLAUDE_PLUGIN_ROOT:-}/skills/web-setup/scripts/web-settings.sh"
[ -f "$helper" ] || exit 0

# verify prints non-existent ids to stdout (exit 1); unverifiable ones go to stderr
# (exit 0). Swallow the exit code — a non-empty stdout is the signal we act on.
missing="$(bash "$helper" verify "$path" 2>/dev/null || true)"
[ -n "$missing" ] || exit 0

# Join the newline-separated ids into "a, b, c". `paste -sd,` collapses with a single
# delimiter (a delimiter LIST like ', ' would cycle comma/space, mis-joining 3+ ids);
# the sed then pads each comma to ", ".
ids="$(printf '%s' "$missing" | paste -sd, - 2>/dev/null | sed 's/,/, /g')"
[ -n "$ids" ] || ids="$(printf '%s' "$missing" | tr '\n' ' ')"
jq -nc --arg ids "$ids" --arg p "$path" '{
  hookSpecificOutput: {
    hookEventName: "PostToolUse",
    additionalContext: ("⚠️ web-setup: " + $p + " enables plugin id(s) NOT present in their marketplace catalog: " + $ids + ". These do not exist and will be \"Declared but NOT installed\" every session. Remove them, or correct the id by checking each marketplace.json / re-running the marketplace-scout agent, before committing. See the cc-web-setup skill (Phase 2/4) — only ever enable ids confirmed present in a fetched catalog or the curated marketplaces.json.")
  }
}'
