#!/usr/bin/env bash
# SessionStart hook (redhat plugin): one declarative line of context — OS, fetcher, and
# whether a Red Hat offline token is present (source name only, never the value) — so the
# model knows the fetch route and whether /redhat:setup is needed before it tries anything.
# Advisory only: any failure (missing plugin root, preflight error) is a silent no-op. Without jq
# the same line is printed as plain text — for SessionStart, plain stdout is also added to the
# model's context (the repo's other advisory hooks use the same fallback), and a jq-less host is
# exactly where the "jq=no" advice matters.
set -u
cat >/dev/null 2>&1 || true   # drain stdin
pre="${CLAUDE_PLUGIN_ROOT:-}/skills/fetch-docs/scripts/rh-preflight.sh"
[ -f "$pre" ] || exit 0
line="$(bash "$pre" 2>/dev/null)" || exit 0
[ -n "$line" ] || exit 0
ctx="Red Hat docs plugin preflight: $line. docs.redhat.com returns 403 to non-browser fetches; /redhat:fetch-docs (rh-fetch.sh) routes to the product's source repo or the Customer Portal API with curl."
if command -v jq >/dev/null 2>&1; then
  jq -nc --arg c "$ctx" '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:$c}}'
else
  printf '%s\n' "$ctx"
fi
exit 0
