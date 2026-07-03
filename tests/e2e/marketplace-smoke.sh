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

# (B) /claude-code:skill-audit present (folded in from the retired `skill` plugin)
[ -d skills/skill-audit ] && pass "B: skills/skill-audit/ exists" || bad "B: skills/skill-audit/ missing"
[ -d plugins/claude-code/skills/skill-audit ] && pass "B: plugins/claude-code/skills/skill-audit/ synced" || bad "B: skill-audit leaf not synced"
grep -q 'leaf: skill-audit' registry/bundles/claude-code.yaml 2>/dev/null && pass "B: claude-code bundle maps skill-audit" || bad "B: claude-code bundle missing skill-audit"
[ -f agents/skill-auditor/agent.md ] && pass "B: skill-auditor agent exists" || bad "B: skill-auditor agent missing"
[ -f plugins/claude-code/hooks/hooks.json ] && pass "B: skill-audit hook present" || bad "B: skill-audit hook missing"

# (C) known plugin still loads
jq -e '.plugins[]|select(.name=="go")' "$MP" >/dev/null 2>&1 && pass "C: go plugin present" || bad "C: go plugin missing"

# Live mode runs only with --live (devcontainer + claude CLI); never in CI. A
# missing CLI marks the run bad but falls through to the unified RED/GREEN
# banner below instead of exiting early (which would skip the summary line).
if [ "${1:-}" = "--live" ]; then
  echo "== live assertions (claude CLI) =="
  ws="${WORKSPACE_DIR:-/workspace}"
  if ! command -v claude >/dev/null; then
    bad "live: claude CLI not found"
  else
    # Per-run temp dir, not fixed /tmp/smoke-*.out paths: those are vulnerable to
    # collision and symlink clobbering across overlapping runs. Cleaned on exit.
    tmp="$(mktemp -d)" || { echo "FATAL: mktemp failed" >&2; exit 2; }
    trap 'rm -rf "$tmp"' EXIT
    # Capture claude's OWN exit status (a pipe would report the downstream tool's).
    if claude plugin validate "$ws" >"$tmp/validate.out" 2>&1; then pass "live: plugin validate"; else bad "live: plugin validate failed"; tail -3 "$tmp/validate.out"; fi
    # marketplace add is idempotent: a non-zero exit is benign ONLY when the CLI
    # reports the marketplace is already added. Any other failure (bad workspace,
    # CLI error) is real and must not slip through as GREEN via `|| true`.
    if claude plugin marketplace add "$ws" >"$tmp/add.out" 2>&1; then
      pass "live: marketplace add"
    elif grep -qi 'already' "$tmp/add.out"; then
      pass "live: marketplace already added"
    else
      bad "live: marketplace add failed"; tail -3 "$tmp/add.out"
    fi
    # The `rdl` meta-plugin (install-everything) was removed; install a real
    # subject plugin instead. `claude-code` is asserted present just below.
    if claude plugin install claude-code@rdl-agent-extensions >"$tmp/install.out" 2>&1; then pass "live: install claude-code@rdl-agent-extensions"; else bad "live: install claude-code@rdl-agent-extensions failed"; tail -3 "$tmp/install.out"; fi
    # Verify `plugin list` itself succeeded before drawing conclusions from its
    # output — otherwise an errored listing has no "zod" line and false-PASSes the
    # removal assertion below.
    if list="$(claude plugin list 2>&1)"; then
      printf '%s\n' "$list" | grep -qiw zod && bad "live: zod still installed" || pass "live: zod not installed"
      # The retired `skill` plugin folded into `claude-code`; verify that new
      # home plugin is installed (case-insensitive, word-bounded).
      printf '%s\n' "$list" | grep -Eiq '(^|[^[:alnum:]_])claude-code([^[:alnum:]_]|$)' && pass "live: claude-code plugin installed" || bad "live: claude-code plugin missing"
    else
      bad "live: plugin list failed"; printf '%s\n' "$list" | tail -3
    fi
  fi
fi

echo
[ "$fail" -eq 0 ] && echo "SMOKE: GREEN" || echo "SMOKE: RED"
exit $fail
