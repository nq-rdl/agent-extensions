#!/usr/bin/env bash
# changie-fragment-lint.sh — PreToolUse hook for Bash tool calls.
#
# Lints `changie new` commands before execution.
# Rules enforced:
#   BLOCK  — Rule #1 fusion:   body contains fusion markers (also fixes, and also, additionally, , also)
#   BLOCK  — Missing --interactive=false flag
#   BLOCK  — Word count >20 when CHANGIE_LINT_STRICT=1
#   WARN   — Word count >20 (default — warns but allows)
#   WARN   — Rule #7 trailing single period
#   WARN   — --kind not in the six capitalised values
#
# Skips:
#   - Commands that are not `changie new`
#   - changie batch, changie merge, changie --help
#   - Repo root has .changie/.no-lint

set -euo pipefail

INPUT=$(cat)
COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null || true)

[[ -z "$COMMAND" ]] && exit 0

# Skip if not a changie new invocation
if ! printf '%s' "$COMMAND" | grep -qE '(^|[;|&]\s*)changie\s+new\b'; then
  exit 0
fi

# Skip changie batch, merge, --help explicitly
if printf '%s' "$COMMAND" | grep -qE 'changie\s+(batch|merge)\b|changie\s+--help'; then
  exit 0
fi

# Per-repo opt-out
if [[ -f ".changie/.no-lint" ]]; then
  exit 0
fi

# ── Extract --body value ────────────────────────────────────────────────────
# Handles double-quoted, single-quoted, and $'...' body values
# || true guards prevent set -e from exiting on no-match grep returns
BODY=""
if printf '%s' "$COMMAND" | grep -qP -- "--body\s+['\"]"; then
  BODY=$(printf '%s' "$COMMAND" | grep -oP "(?<=--body\s')[^']*(?=')" | head -1 || true)
  if [[ -z "$BODY" ]]; then
    BODY=$(printf '%s' "$COMMAND" | grep -oP '(?<=--body\s")[^"]*(?=")' | head -1 || true)
  fi
fi

# ── Extract --kind value ────────────────────────────────────────────────────
KIND=$(printf '%s' "$COMMAND" | grep -oP '(?<=--kind\s)\S+' | head -1 || true)

VALID_KINDS="Added Changed Deprecated Removed Fixed Security"
WARNINGS=""
BLOCK_REASON=""

# ── Rule: missing --interactive=false ──────────────────────────────────────
if ! printf '%s' "$COMMAND" | grep -q -- '--interactive=false'; then
  BLOCK_REASON="changie-fragment-lint: missing --interactive=false — changie opens a TUI that agents cannot interact with"
fi

# ── Rule #1: fusion markers ─────────────────────────────────────────────────
if [[ -z "$BLOCK_REASON" && -n "$BODY" ]]; then
  BODY_LOWER=$(printf '%s' "$BODY" | tr '[:upper:]' '[:lower:]')
  if printf '%s' "$BODY_LOWER" | grep -qE '\balso fixes\b|\band also\b|\badditionally\b|,\s*also\s'; then
    BLOCK_REASON="changie-fragment-lint: Rule #1 — body contains a fusion marker ('also fixes', 'and also', 'additionally', or ', also'). Split into two separate changie new calls."
  fi
fi

if [[ -n "$BLOCK_REASON" ]]; then
  printf '{"decision":"block","reason":"%s"}' \
    "$(printf '%s' "$BLOCK_REASON" | sed 's/"/\\"/g')"
  exit 0
fi

# ── Rule #2: word count ─────────────────────────────────────────────────────
if [[ -n "$BODY" ]]; then
  BODY_NO_REF=$(printf '%s' "$BODY" | sed 's/(#[0-9]\+)[[:space:]]*$//')
  WORD_COUNT=$(printf '%s' "$BODY_NO_REF" | wc -w)
  if [[ "$WORD_COUNT" -gt 20 ]]; then
    if [[ "${CHANGIE_LINT_STRICT:-0}" == "1" ]]; then
      printf '{"decision":"block","reason":"changie-fragment-lint: Rule #2 — body is %d words (limit 20, excluding issue ref). Count words and trim before continuing."}' \
        "$WORD_COUNT"
      exit 0
    else
      WARNINGS="${WARNINGS}[WARN] changie-fragment-lint: body is ${WORD_COUNT} words — Rule #2 limit is 20 (excluding issue ref); consider trimming\\n"
    fi
  fi
fi

# ── Rule #7: trailing period ────────────────────────────────────────────────
if [[ -n "$BODY" ]]; then
  # Allow ellipsis (..) but not a single trailing period
  if printf '%s' "$BODY" | grep -qP '\.[^.]\s*$' || \
     { printf '%s' "$BODY" | grep -qP '\.$' && ! printf '%s' "$BODY" | grep -qP '\.\.\s*$'; }; then
    WARNINGS="${WARNINGS}[WARN] changie-fragment-lint: Rule #7 — body ends with a period; entries render as bullet items, not sentences\\n"
  fi
fi

# ── Kind validation ─────────────────────────────────────────────────────────
if [[ -n "$KIND" ]]; then
  if ! printf '%s' "$VALID_KINDS" | grep -qw "$KIND"; then
    WARNINGS="${WARNINGS}[WARN] changie-fragment-lint: --kind '${KIND}' is not one of the six capitalised values (Added, Changed, Deprecated, Removed, Fixed, Security)\\n"
  fi
fi

# ── Emit warnings ──────────────────────────────────────────────────────────
if [[ -n "$WARNINGS" ]]; then
  printf '{"context":"%s"}' \
    "$(printf '%s' "$WARNINGS" | sed 's/"/\\"/g' | tr -d '\n')"
fi

exit 0
