#!/usr/bin/env bash
# Marketplace smoke E2E for the skills value audit (#140-#146).
# Static mode (default): asserts repo + generated marketplace.json end-state.
# Live mode (--live): also installs the marketplace via the claude CLI and
# asserts plugin visibility. Run --live inside `devcontainer exec`.
set -uo pipefail
# Resolve and validate the repo root before cd. `cd "$(git rev-parse ...)"`
# alone is unsafe: outside a repo the substitution is empty and `cd ""` returns
# 0, so the guard never fires and assertions silently run against the caller's
# cwd (e.g. a sibling repo's marketplace.json) — a false GREEN/RED.
root="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "FATAL: not inside a git repo" >&2; exit 2; }
[ -n "$root" ] || { echo "FATAL: could not resolve repo root" >&2; exit 2; }
cd "$root" || { echo "FATAL: cannot cd to repo root $root" >&2; exit 2; }
MP=".claude-plugin/marketplace.json"
# Preflight: the static assertions below shell out to jq against $MP. Without
# this gate a missing jq binary or missing/invalid marketplace file would make
# the `jq -e ... 2>/dev/null` checks fall through to a false GREEN.
command -v jq >/dev/null 2>&1 || { echo "FATAL: jq not found (required for marketplace.json assertions)" >&2; exit 2; }
jq -e . "$MP" >/dev/null 2>&1 || { echo "FATAL: $MP missing or not valid JSON" >&2; exit 2; }
fail=0
pass() { printf '  PASS  %s\n' "$1"; }
bad()  { printf '  FAIL  %s\n' "$1"; fail=1; }

echo "== static assertions =="
# (A) zod fully removed
if jq -e '.plugins[]|select(.name=="zod")' "$MP" >/dev/null 2>&1; then
  bad "A: zod still in marketplace.json"; else pass "A: zod absent from marketplace.json"; fi
[ -d skills/zod ] && bad "A: skills/zod/ still exists" || pass "A: skills/zod/ gone"
[ -d plugins/zod ] && bad "A: plugins/zod/ still exists" || pass "A: plugins/zod/ gone"
[ -f registry/bundles/zod.yaml ] && bad "A: registry/bundles/zod.yaml still exists" || pass "A: zod bundle gone"

# (B) /skill:audit present
[ -d skills/skill-audit ] && pass "B: skills/skill-audit/ exists" || bad "B: skills/skill-audit/ missing"
[ -d plugins/skill/skills/audit ] && pass "B: plugins/skill/skills/audit/ synced" || bad "B: audit leaf not synced"
grep -q 'leaf: audit' registry/bundles/skill.yaml 2>/dev/null && pass "B: skill bundle maps audit" || bad "B: skill bundle missing audit"
[ -f agents/skill-auditor/agent.md ] && pass "B: skill-auditor agent exists" || bad "B: skill-auditor agent missing"
[ -f plugins/skill/hooks/hooks.json ] && pass "B: skill hook present" || bad "B: skill hook missing"

# (C) known plugin still loads
jq -e '.plugins[]|select(.name=="go")' "$MP" >/dev/null 2>&1 && pass "C: go plugin present" || bad "C: go plugin missing"

if [ "${1:-}" = "--live" ]; then
  echo "== live assertions (claude CLI) =="
  ws="${WORKSPACE_DIR:-/workspace}"
  command -v claude >/dev/null || { bad "live: claude CLI not found"; exit $fail; }
  # Capture claude's OWN exit status (a pipe would report the downstream tool's).
  if claude plugin validate "$ws" >/tmp/smoke-validate.out 2>&1; then pass "live: plugin validate"; else bad "live: plugin validate failed"; tail -3 /tmp/smoke-validate.out; fi
  claude plugin marketplace add "$ws" >/tmp/smoke-add.out 2>&1 || true   # idempotent; "already added" is fine
  if claude plugin install rdl@rdl >/tmp/smoke-install.out 2>&1; then pass "live: install rdl@rdl"; else bad "live: install rdl@rdl failed"; tail -3 /tmp/smoke-install.out; fi
  # Verify `plugin list` itself succeeded before drawing conclusions from its
  # output — otherwise an errored listing has no "zod" line and false-PASSes the
  # removal assertion below.
  if list="$(claude plugin list 2>&1)"; then
    printf '%s\n' "$list" | grep -qiw zod && bad "live: zod still installed" || pass "live: zod not installed"
    # Case-insensitive (matches line 'zod' check) word-bounded match for the
    # 'skill' plugin name (not a substring of e.g. 'skills').
    printf '%s\n' "$list" | grep -Eiq '(^|[^[:alnum:]_])skill([^[:alnum:]_]|$)' && pass "live: skill plugin installed" || bad "live: skill plugin missing"
  else
    bad "live: plugin list failed"; printf '%s\n' "$list" | tail -3
  fi
fi

echo
[ "$fail" -eq 0 ] && echo "SMOKE: GREEN" || echo "SMOKE: RED"
exit $fail
