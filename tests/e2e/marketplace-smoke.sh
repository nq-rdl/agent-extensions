#!/usr/bin/env bash
# Marketplace smoke E2E for the skills value audit (#140-#146).
# Static mode (default): asserts repo + generated marketplace.json end-state.
# Live mode (--live): also installs the marketplace via the claude CLI and
# asserts plugin visibility. Run --live inside `devcontainer exec`.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)" || exit 2
MP=".claude-plugin/marketplace.json"
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
  command -v claude >/dev/null || { bad "live: claude CLI not found"; exit $fail; }
  claude plugin validate /workspace 2>&1 | tail -2 || bad "live: plugin validate failed"
  claude plugin marketplace add /workspace 2>&1 | tail -2 || true
  claude plugin install rdl@rdl 2>&1 | tail -2 || bad "live: install rdl@rdl failed"
  list="$(claude plugin list 2>&1)"
  echo "$list" | grep -qiw zod && bad "live: zod still installed" || pass "live: zod not installed"
  echo "$list" | grep -qiw skill && pass "live: skill plugin installed" || bad "live: skill plugin missing"
fi

echo
[ "$fail" -eq 0 ] && echo "SMOKE: GREEN" || echo "SMOKE: RED"
exit $fail
