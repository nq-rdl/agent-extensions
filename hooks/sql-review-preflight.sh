#!/usr/bin/env bash
# SessionStart hook (sql-review plugin): one declarative line of context about the session's
# project — whether .sqlreview/ is initialised and which reviews are stale or missing — so the
# model knows which /sql-review:* stage applies before it is asked. Runs `sqlreview.sh status
# --json` from the event's cwd. Advisory only: any failure (no helper, no cwd, no jq) is a silent
# no-op, and an uninitialised project only gets a hint when it actually contains SQL files.
set -u
input="$(cat 2>/dev/null)" || exit 0
field() {
  if command -v jq >/dev/null 2>&1; then printf '%s' "$input" | jq -r "$1 // empty" 2>/dev/null
  elif command -v python3 >/dev/null 2>&1; then printf '%s' "$input" | python3 -c 'import json,sys
try: d = json.load(sys.stdin)
except Exception: sys.exit(0)
for k in sys.argv[1].strip(".").split("."):
    d = d.get(k) if isinstance(d, dict) else None
sys.stdout.write(d if isinstance(d, str) else "")' "$1" 2>/dev/null
  fi
}
cwd="$(field .cwd)"; [ -n "$cwd" ] || cwd="$(pwd -P 2>/dev/null)"
[ -d "$cwd" ] || exit 0
command -v jq >/dev/null 2>&1 || exit 0

here="$(cd "$(dirname "$0")" 2>/dev/null && pwd -P)"
helper=""
for c in "${CLAUDE_PLUGIN_ROOT:-/nonexistent}/skills/setup/scripts/sqlreview.sh" \
         "$here/../skills/setup/scripts/sqlreview.sh" \
         "$here/../skills/sql-review-setup/scripts/sqlreview.sh"; do
  [ -f "$c" ] && { helper="$c"; break; }
done
[ -n "$helper" ] || exit 0

status="$(cd "$cwd" && bash "$helper" status --json 2>/dev/null)"; rc=$?
ctx=""
if [ "$rc" -eq 3 ]; then
  has_sql="$(cd "$cwd" && { git ls-files -- '*.sql' '**/*.sql' 2>/dev/null; find . -maxdepth 3 -name '*.sql' -not -path './.git/*' 2>/dev/null; } | head -1)"
  [ -n "$has_sql" ] || exit 0
  ctx="SQL Review: this project contains SQL files but has no .sqlreview/ directory. /sql-review:setup initialises it (once per project); then /sql-review:bootstrap, :analyse and :explain use it."
elif [ "$rc" -eq 0 ] && [ -n "$status" ]; then
  ctx="$(printf '%s' "$status" | jq -r '
    . as $r
    | def names(s): [$r.reviews[] | select(.state == s) | .slug] | join(", ");
    (.counts.total // 0) as $n
    | if $n == 0 then
        "SQL Review: .sqlreview/ is initialised (schema \(.schemaVersion)) with no reviews yet — /sql-review:bootstrap scopes a new SQL file, /sql-review:analyse reviews an existing one."
      else
        "SQL Review: .sqlreview/ is initialised (schema \(.schemaVersion)), \($n) review\(if $n == 1 then "" else "s" end): "
        + ([ (.counts.current // 0 | select(. > 0) | "\(.) current"),
             (.counts.scoped // 0 | select(. > 0) | "\(.) scoped (bootstrap only)"),
             (.counts.stale // 0 | select(. > 0) | "\(.) stale (\(names("stale")))"),
             (.counts["no-baseline"] // 0 | select(. > 0) | "\(.) without a baseline (\(names("no-baseline")))"),
             (.counts.missing // 0 | select(. > 0) | "\(.) whose SQL is missing (\(names("missing")))") ] | join(", "))
        + ". Stale or baseline-less reviews need /sql-review:analyse --update before /sql-review:explain; a missing SQL file is rebound with sqlreview.sh move."
      end' 2>/dev/null)"
fi
[ -n "$ctx" ] || exit 0
jq -nc --arg c "$ctx" '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:$c}}'
exit 0
