#!/usr/bin/env bash
# data-request plugin smoke E2E (#131 / #126 #127 #128 #130).
# Static mode (default): asserts the repo + generated-artifact end-state for the plugin.
# Live mode (--live): inside the sandbox container — installs the marketplace via the claude CLI,
# installs data-request, then drives the INSTALLED helper and hooks in a scratch project. With
# credentials available it also runs the first-run acceptance test (`claude -p '/data-request:setup
# --default --yes'` must leave .sqlreview/config.json behind); without them that step is reported
# as SKIPPED and the run goes RED — never green by omission.
set -uo pipefail
root="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "FATAL: not inside a git repo" >&2; exit 2; }
[ -n "$root" ] || { echo "FATAL: could not resolve repo root" >&2; exit 2; }
cd "$root" || exit 2
MP=".claude-plugin/marketplace.json"
command -v jq >/dev/null 2>&1 || { echo "FATAL: jq not found" >&2; exit 2; }
jq -e . "$MP" >/dev/null 2>&1 || { echo "FATAL: $MP missing or not valid JSON" >&2; exit 2; }
fail=0
pass() { printf '  PASS  %s\n' "$1"; }
bad()  { printf '  FAIL  %s\n' "$1"; fail=1; }
skip() { printf '  SKIP  %s\n' "$1"; fail=1; }

echo "== static assertions =="
jq -e '.plugins[]|select(.name=="data-request")' "$MP" >/dev/null 2>&1 && pass "A: data-request in marketplace.json" || bad "A: data-request missing from marketplace.json"
[ -f registry/bundles/data-request.yaml ] && pass "A: bundle yaml" || bad "A: bundle yaml missing"
for leaf in setup bootstrap analyse explain guardrails map draft validate fix lift; do
  [ -f "plugins/data-request/skills/$leaf/SKILL.md" ] && pass "B: plugin skill $leaf synced" || bad "B: plugin skill $leaf missing"
  grep -q '^name:' "plugins/data-request/skills/$leaf/SKILL.md" 2>/dev/null && bad "B: $leaf copy still carries name:" || pass "B: $leaf copy has no name: (labels as data-request:$leaf)"
done
for f in scripts/sqlreview.sh scripts/sqlreview-lib.sh scripts/sqlreview-check.jq scripts/sqlreview-slug.jq scripts/sqlreview-render.jq \
         assets/sqlreview/config.json assets/sqlreview/templates/scope.md assets/sqlreview/templates/review.md references/definitions.rst; do
  [ -f "plugins/data-request/skills/setup/$f" ] && pass "C: setup/$f shipped" || bad "C: setup/$f missing from plugin"
done
for h in data-request-guard.sh data-request-preflight.sh; do
  cmp -s "hooks/$h" "plugins/data-request/hooks/$h" && pass "D: $h copy identical" || bad "D: $h copy differs from hooks/"
done
jq -e '.hooks.PreToolUse[0].matcher == "Write|Edit" and (.hooks.SessionStart|length) == 1' plugins/data-request/hooks/hooks.json >/dev/null 2>&1 && pass "D: hooks.json wiring" || bad "D: hooks.json wiring"

# Exercise the canonical helper end to end in a scratch project (no claude CLI needed).
drive_helper() { # <sqlreview.sh path> <label>
  local S="$1" label="$2" tmp
  tmp="$(mktemp -d)" || { bad "$label: mktemp"; return; }
  (
    cd "$tmp" && git init -q && git config user.email t@example && git config user.name t
    bash "$S" init >/dev/null || exit 1
    mkdir -p reports && printf 'WITH s AS (SELECT * FROM adm.stays)\nSELECT month, COUNT(*) AS n FROM s GROUP BY month;\n' > reports/monthly.sql
    slug="$(bash "$S" slug reports/monthly.sql)" && [ "$slug" = "reports__monthly" ] || exit 2
    fp="$(bash "$S" fingerprint reports/monthly.sql)" || exit 3
    sha="$(printf '%s' "$fp" | jq -r .sql_sha256)"
    mkdir -p ".sqlreview/reviews/$slug" || exit 4
    now="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    jq -n --arg slug "$slug" --arg sha "$sha" --arg now "$now" '{
      schemaVersion:1, kind:"review", slug:$slug, sql_path:"reports/monthly.sql", title:"Monthly", revision:1,
      recorded_at:$now, recorded_by:"smoke", sql_sha256:$sha, git_commit:null, git_dirty:true,
      purpose:"Counts stays per month.", grain:"one row per month",
      inputs:[{name:"adm.stays",description:"one row per stay"}], outputs:[{name:"month",description:"month"},{name:"n",description:"count"}],
      logic:[{step:1,title:"Count",lines:[1,2],description:"group by month"}],
      assumptions:[{id:"A1",text:"All stays count",rationale:"request",location:{lines:[1,1]},status:"confirmed",confirmed_by:"smoke",confirmed_at:$now,confirmed_revision:1}],
      limitations:[], open_questions:[], changes:[{revision:1,at:$now,by:"smoke",summary:"initial"}]}' > ".sqlreview/reviews/$slug/review.json"
    bash "$S" check ".sqlreview/reviews/$slug/review.json" >/dev/null || exit 5
    bash "$S" snapshot "$slug" reports/monthly.sql >/dev/null || exit 4
    bash "$S" render "$slug" review >/dev/null || exit 6
    grep -q '| A1 |' ".sqlreview/reviews/$slug/review.md" || exit 7
    bash "$S" delta "$slug" >/dev/null || exit 8                         # unchanged → 0
    printf -- '-- tweak\n' >> reports/monthly.sql
    bash "$S" delta "$slug" >/dev/null; [ $? -eq 10 ] || exit 9         # changed → 10
    bash "$S" status --json | jq -e '.reviews[0].state == "stale"' >/dev/null || exit 10
  )
  rc=$?
  rm -rf "$tmp"
  [ "$rc" -eq 0 ] && pass "$label: init/slug/fingerprint/snapshot/check/render/delta/status" || bad "$label: helper round-trip failed at step $rc"
}
drive_hooks() { # <plugin root> <label>
  local P="$1" label="$2" tmp out
  tmp="$(mktemp -d)" || { bad "$label: mktemp"; return; }
  ( cd "$tmp" && bash "$P/skills/setup/scripts/sqlreview.sh" init >/dev/null )
  out="$(printf '{"tool_name":"Write","tool_input":{"file_path":"%s/.sqlreview/reviews/x/review.json","content":"{\\"kind\\":\\"review\\",\\"revision\\":1,\\"assumptions\\":[{\\"id\\":\\"A1\\",\\"text\\":\\"x\\",\\"status\\":\\"pending\\"}],\\"limitations\\":[]}"},"cwd":"%s"}' "$tmp" "$tmp" \
        | CLAUDE_PLUGIN_ROOT="$P" bash "$P/hooks/data-request-guard.sh")"
  printf '%s' "$out" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null 2>&1 && pass "$label: guard denies unconfirmed A1" || bad "$label: guard did not deny (got: ${out:-nothing})"
  out="$(printf '{"cwd":"%s"}' "$tmp" | CLAUDE_PLUGIN_ROOT="$P" bash "$P/hooks/data-request-preflight.sh")"
  printf '%s' "$out" | jq -e '.hookSpecificOutput.additionalContext | test("initialised")' >/dev/null 2>&1 && pass "$label: preflight reports initialised project" || bad "$label: preflight context missing (got: ${out:-nothing})"
  rm -rf "$tmp"
}
drive_helper "$root/skills/data-request-setup/scripts/sqlreview.sh" "E: canonical helper"
drive_hooks "$root/plugins/data-request" "E: repo plugin copy"

if [ "${1:-}" = "--live" ]; then
  echo "== live assertions (claude CLI) =="
  ws="${WORKSPACE_DIR:-/workspace}"
  if ! command -v claude >/dev/null; then
    bad "live: claude CLI not found"
  else
    tmp="$(mktemp -d)" || { echo "FATAL: mktemp failed" >&2; exit 2; }
    trap 'rm -rf "$tmp"' EXIT
    if claude plugin validate "$ws/plugins/data-request" >"$tmp/validate.out" 2>&1; then pass "live: plugin validate"; else bad "live: plugin validate failed"; tail -3 "$tmp/validate.out"; fi
    if claude plugin marketplace add "$ws" >"$tmp/add.out" 2>&1; then pass "live: marketplace add"
    elif grep -qi 'already' "$tmp/add.out"; then pass "live: marketplace already added"
    else bad "live: marketplace add failed"; tail -3 "$tmp/add.out"; fi
    if claude plugin install data-request@rdl-agent-extensions >"$tmp/install.out" 2>&1; then pass "live: install data-request@rdl-agent-extensions"; else bad "live: install failed"; tail -3 "$tmp/install.out"; fi
    if list="$(claude plugin list 2>&1)"; then
      printf '%s\n' "$list" | grep -Eiq '(^|[^[:alnum:]_])data-request([^[:alnum:]_]|$)' && pass "live: data-request listed as installed" || { bad "live: data-request not in plugin list"; printf '%s\n' "$list" | tail -5; }
    else bad "live: plugin list failed"; fi
    # The installed copy (the cache Claude Code actually runs) must be self-contained.
    inst="$(find "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/plugins/cache" -maxdepth 4 -type d -path '*rdl-agent-extensions/data-request/*' 2>/dev/null | head -1)"
    if [ -n "$inst" ] && [ -f "$inst/skills/setup/scripts/sqlreview.sh" ]; then
      pass "live: installed copy at $inst"
      drive_helper "$inst/skills/setup/scripts/sqlreview.sh" "live: installed helper"
      drive_hooks "$inst" "live: installed hooks"
    else
      bad "live: installed data-request copy not found under the plugin cache"
    fi
    # First-run acceptance: the skill itself must initialise an empty project non-interactively.
    if [ -f "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/.credentials.json" ] || [ -n "${ANTHROPIC_API_KEY:-}" ]; then
      proj="$tmp/proj"; mkdir -p "$proj"; ( cd "$proj" && git init -q )
      if ( cd "$proj" && timeout 600 claude -p '/data-request:setup --default --yes' --permission-mode bypassPermissions >"$tmp/setup.out" 2>&1 ) && [ -f "$proj/.sqlreview/config.json" ]; then
        pass "live: /data-request:setup --default --yes created .sqlreview/config.json"
        jq -e '.definitions.assumption | test("RDL")' "$proj/.sqlreview/config.json" >/dev/null 2>&1 && pass "live: config carries the shared definitions" || bad "live: config missing definitions"
      else
        bad "live: /data-request:setup did not create .sqlreview/config.json"; tail -15 "$tmp/setup.out"
      fi
    else
      skip "live: first-run acceptance (no credentials mounted — required before declaring verification complete)"
    fi
  fi
fi

echo
[ "$fail" -eq 0 ] && echo "SMOKE: GREEN" || echo "SMOKE: RED"
exit $fail
