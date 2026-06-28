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

# Like run_announce but with an explicit enabledPlugins map ($1 = JSON object) so one run
# can declare several plugins at once. $2 is the optional `claude` stub body (empty => no
# claude on PATH). Echoes the additionalContext text.
run_announce_with() {
  local d proj; d="$(new_path)"; proj="$(mktemp -d "$WORK/proj.XXXXXX")"; mkdir -p "$proj/.claude"
  printf '{"enabledPlugins":%s}' "$1" > "$proj/.claude/settings.json"
  if [ -n "${2-}" ]; then printf '#!/usr/bin/env bash\n%s\n' "$2" > "$d/claude"; chmod +x "$d/claude"; fi
  ( export PATH="$d" CLAUDE_PROJECT_DIR="$proj" TMPDIR="$WORK"; bash "$SCRIPT" ) 2>/dev/null \
    | jq -r '.hookSpecificOutput.additionalContext // ""'
}

# Production reality: several plugins declared, some installed and some not, in ONE run.
# a@m and c@m are installed+enabled; b@m is not. The partition loop must bucket each id
# correctly and BOTH render blocks must coexist — never collapse to a single verdict.
test_multi_plugin_mixed() {
  local out; out="$(run_announce_with '{"a@m":true,"b@m":true,"c@m":true}' \
    'printf "[{\"id\":\"a@m\",\"enabled\":true},{\"id\":\"c@m\",\"enabled\":true}]\n"; exit 0')"
  printf '%s' "$out" | grep -q 'Enabled plugins (installed.*a@m.*c@m' \
    && ok "multi: a@m and c@m reported installed" || fail "multi: installed set wrong. [$out]"
  printf '%s' "$out" | grep -q 'Declared but NOT installed:.*b@m' \
    && ok "multi: b@m reported NOT installed" || fail "multi: b@m not flagged missing. [$out]"
  # No cross-contamination: the NOT-installed line must not carry an installed id.
  printf '%s' "$out" | grep 'Declared but NOT installed' | grep -qE 'a@m|c@m' \
    && fail "multi: installed plugin leaked into NOT-installed line. [$out]" \
    || ok "multi: no installed plugin in NOT-installed line"
}

# Exact-line match, not substring: declared foo@bar must NOT be satisfied by an installed
# foo@barbaz. Locks in the script's `grep -qxF`; a regression to substring matching fails here.
test_exact_match_only() {
  local out; out="$(run_announce_with '{"foo@bar":true}' \
    'printf "[{\"id\":\"foo@barbaz\",\"enabled\":true}]\n"; exit 0')"
  printf '%s' "$out" | grep -q 'Declared but NOT installed:.*foo@bar' \
    && ok "exact-match: foo@bar not satisfied by foo@barbaz" || fail "exact-match: substring wrongly matched. [$out]"
}

# `claude plugin list --json` lists foo@bar enabled => installed.
test_installed() {
  local out; out="$(run_announce 'printf "[{\"id\":\"foo@bar\",\"enabled\":true,\"scope\":\"user\"}]\n"; exit 0')"
  printf '%s' "$out" | grep -q 'Enabled plugins (installed.*foo@bar' \
    && ok "installed: reported as installed" || fail "installed: not reported installed. [$out]"
  printf '%s' "$out" | grep -qiE 'unverified|NOT installed' \
    && fail "installed: also flagged unverified/missing" || ok "installed: not flagged unverified/missing"
}

# claude SUCCEEDS with an empty array `[]` => the declared plugin genuinely did NOT
# install. This must read as "NOT installed", not "unverified".
test_missing_on_successful_empty() {
  local out; out="$(run_announce 'printf "[]\n"; exit 0')"
  printf '%s' "$out" | grep -q 'Declared but NOT installed:.*foo@bar' \
    && ok "empty-success: declared plugin reported NOT installed" || fail "empty-success: not flagged missing. [$out]"
  printf '%s' "$out" | grep -q 'Enabled plugins (installed' \
    && fail "empty-success: wrongly reported installed" || ok "empty-success: not reported installed"
}

# A plugin present but enabled:false => NOT installed/enabled (must not count as installed).
test_disabled_is_missing() {
  local out; out="$(run_announce 'printf "[{\"id\":\"foo@bar\",\"enabled\":false}]\n"; exit 0')"
  printf '%s' "$out" | grep -q 'Declared but NOT installed:.*foo@bar' \
    && ok "disabled: reported NOT installed" || fail "disabled: not flagged missing. [$out]"
}

# claude ERRORS => cannot verify => report unverified, NEVER "installed".
test_unverified_on_error() {
  local out; out="$(run_announce 'echo boom >&2; exit 1')"
  printf '%s' "$out" | grep -q 'install unverified.*foo@bar' \
    && ok "cli-error: reported unverified" || fail "cli-error: not unverified. [$out]"
  printf '%s' "$out" | grep -q 'Enabled plugins (installed' \
    && fail "cli-error: wrongly reported installed" || ok "cli-error: not reported installed"
}

# claude SUCCEEDS but emits non-JSON (e.g. an old CLI lacking --json) => cannot parse
# => unverified, never silently "NOT installed".
test_unverified_on_non_json() {
  local out; out="$(run_announce 'printf "not json\n"; exit 0')"
  printf '%s' "$out" | grep -q 'install unverified.*foo@bar' \
    && ok "non-json: reported unverified" || fail "non-json: not unverified. [$out]"
}

# claude SUCCEEDS with valid JSON of the WRONG shape (an object, not the documented array)
# => cannot trust it => unverified, never a false "NOT installed".
test_unverified_on_wrong_shape() {
  local out; out="$(run_announce 'printf "{\"plugins\":[{\"id\":\"foo@bar\",\"enabled\":true}]}\n"; exit 0')"
  printf '%s' "$out" | grep -q 'install unverified.*foo@bar' \
    && ok "wrong-shape: reported unverified" || fail "wrong-shape: not unverified. [$out]"
}

# No claude CLI on PATH => cannot verify => unverified (the original false-"installed"
# regression: this used to be labeled installed).
test_unverified_on_no_cli() {
  local out; out="$(run_announce '')"
  printf '%s' "$out" | grep -q 'install unverified.*foo@bar' \
    && ok "no-cli: reported unverified" || fail "no-cli: not unverified. [$out]"
  printf '%s' "$out" | grep -q 'Enabled plugins (installed' \
    && fail "no-cli: wrongly reported installed" || ok "no-cli: not reported installed"
}

test_installed
test_missing_on_successful_empty
test_disabled_is_missing
test_multi_plugin_mixed
test_exact_match_only
test_unverified_on_error
test_unverified_on_non_json
test_unverified_on_wrong_shape
test_unverified_on_no_cli

echo ""
echo "announce: ${PASS} passed, ${FAIL} failed, ${SKIP} skipped"
[ "$FAIL" -eq 0 ]
