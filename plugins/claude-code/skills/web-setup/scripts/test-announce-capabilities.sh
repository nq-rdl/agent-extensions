#!/usr/bin/env bash
# scripts/test-announce-capabilities.sh
# Tests for assets/announce-capabilities.sh — focused on the plugin CANARY: a
# declared plugin must be reported as installed / NOT installed / unverified
# correctly, and NEVER mislabeled "installed" when it isn't. Runs the hook as a
# subprocess with a stubbed `claude` (and jq) on a scoped PATH. No network.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="${HERE}/../assets/announce-capabilities.sh"
PASS=0; FAIL=0; SKIP=0
ok()   { PASS=$((PASS+1)); echo "  PASS  $*"; }
fail() { FAIL=$((FAIL+1)); echo "  FAIL  $*"; }

WORK="$(mktemp -d "${TMPDIR:-/tmp}/announce-test.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

# announce emits its banner as JSON (hookSpecificOutput.additionalContext) when jq is
# present; we parse that field back out with jq, so jq is required for these tests.
if ! command -v jq >/dev/null 2>&1; then
  echo "announce: 0 passed, 0 failed, 1 skipped (jq unavailable)"; exit 0
fi

COREUTILS="bash jq awk sed sort cat printf grep id basename dirname find head cut tr mktemp rm ln"
new_path() {
  local d t r; d="$(mktemp -d "$WORK/path.XXXXXX")"
  for t in $COREUTILS; do r="$(command -v "$t" 2>/dev/null || true)"; [ -n "$r" ] && ln -s "$r" "$d/$t"; done
  echo "$d"
}

# Run announce against a project that declares foo@bar, with an optional `claude`
# stub body ($1 empty => no claude on PATH). Echoes the additionalContext text.
run_announce() {
  local d proj; d="$(new_path)"; proj="$(mktemp -d "$WORK/proj.XXXXXX")"; mkdir -p "$proj/.claude"
  printf '{"enabledPlugins":{"foo@bar":true}}' > "$proj/.claude/settings.json"
  if [ -n "${1-}" ]; then printf '#!/usr/bin/env bash\n%s\n' "$1" > "$d/claude"; chmod +x "$d/claude"; fi
  ( export PATH="$d" CLAUDE_PROJECT_DIR="$proj" TMPDIR="$WORK"; bash "$SCRIPT" ) 2>/dev/null \
    | jq -r '.hookSpecificOutput.additionalContext // ""'
}

# `claude plugin list` lists foo@bar as enabled => installed.
test_installed() {
  local out; out="$(run_announce 'printf "> foo@bar\n  Status: enabled\n"; exit 0')"
  printf '%s' "$out" | grep -q 'Enabled plugins (installed):.*foo@bar' \
    && ok "installed: reported as installed" || fail "installed: not reported installed. [$out]"
  printf '%s' "$out" | grep -qiE 'unverified|NOT installed' \
    && fail "installed: also flagged unverified/missing" || ok "installed: not flagged unverified/missing"
}

# claude SUCCEEDS (exit 0) but lists nothing => the declared plugin genuinely did NOT
# install. This must read as "NOT installed", not "unverified".
test_missing_on_successful_empty() {
  local out; out="$(run_announce 'exit 0')"
  printf '%s' "$out" | grep -q 'Declared but NOT installed:.*foo@bar' \
    && ok "empty-success: declared plugin reported NOT installed" || fail "empty-success: not flagged missing. [$out]"
  printf '%s' "$out" | grep -q 'Enabled plugins (installed):' \
    && fail "empty-success: wrongly reported installed" || ok "empty-success: not reported installed"
}

# claude ERRORS => cannot verify => report unverified, NEVER "installed".
test_unverified_on_error() {
  local out; out="$(run_announce 'echo boom >&2; exit 1')"
  printf '%s' "$out" | grep -q 'install unverified.*foo@bar' \
    && ok "cli-error: reported unverified" || fail "cli-error: not unverified. [$out]"
  printf '%s' "$out" | grep -q 'Enabled plugins (installed):' \
    && fail "cli-error: wrongly reported installed" || ok "cli-error: not reported installed"
}

# No claude CLI on PATH => cannot verify => unverified (the original false-"installed"
# regression: this used to be labeled installed).
test_unverified_on_no_cli() {
  local out; out="$(run_announce '')"
  printf '%s' "$out" | grep -q 'install unverified.*foo@bar' \
    && ok "no-cli: reported unverified" || fail "no-cli: not unverified. [$out]"
  printf '%s' "$out" | grep -q 'Enabled plugins (installed):' \
    && fail "no-cli: wrongly reported installed" || ok "no-cli: not reported installed"
}

test_installed
test_missing_on_successful_empty
test_unverified_on_error
test_unverified_on_no_cli

echo ""
echo "announce: ${PASS} passed, ${FAIL} failed, ${SKIP} skipped"
[ "$FAIL" -eq 0 ]
