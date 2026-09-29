#!/usr/bin/env bash
# UserPromptSubmit hook (speckit-dev plugin) — nudges "where to publish?" when the
# user is publishing a spec-kit extension. Fires only on spec-kit + publish
# markers; injects DECLARATIVE, fenced advisory context (never an instruction),
# via the UserPromptSubmit additionalContext channel. Silent no-op otherwise.

set -euo pipefail

input=$(cat)

# Extract the prompt text: jq, then python3, then a POSIX `sed -E` scrape. Any
# parse failure yields an empty prompt, so malformed input is a silent no-op.
# The scrape runs on bash 3.2 with BSD/BusyBox sed (no grep -P). It keeps JSON
# escapes except \n \r \t, which become spaces; the gate below only needs markers.
if command -v jq >/dev/null 2>&1; then
  prompt=$(printf '%s' "$input" | jq -r 'if type == "object" then (.prompt | strings) else empty end' 2>/dev/null || true)
elif command -v python3 >/dev/null 2>&1; then
  prompt=$(printf '%s' "$input" | python3 -c 'import sys, json
try: d = json.load(sys.stdin)
except Exception: sys.exit(0)
p = d.get("prompt") if isinstance(d, dict) else None
print(p if isinstance(p, str) else "")' 2>/dev/null || true)
else
  prompt=$(printf '%s' "$input" | tr '\n' ' ' | sed -nE 's/.*"prompt"[[:space:]]*:[[:space:]]*"(([^"\\]|\\.)*)".*/\1/p' | sed -E 's/\\[nrt]/ /g' || true)
fi

# Gate: fire only when BOTH a spec-kit marker AND a publish/distribute marker
# are present. A /speckit-dev:publish invocation satisfies both on its own (its
# text contains "speckit" and "publish"). Skips pure scaffold/validate prompts;
# note catalog/release wording overlaps the manage skill, so managing a catalog
# can also trip the nudge (harmless — the injected payload is advisory only).
speckit='(^|[^[:alnum:]_])(spec-kit|speckit)([^[:alnum:]_]|$)|\.specify/|speckit-dev:publish'
publish='(publish|distribut|release|catalog|submit)'
if ! printf '%s' "$prompt" | grep -qiE "$speckit"; then exit 0; fi
if ! printf '%s' "$prompt" | grep -qiE "$publish"; then exit 0; fi

read -r -d '' payload <<'CTX' || true
<speckit-publish-guidance>
This looks like publishing a spec-kit extension. Confirm WHERE before proceeding.

Default team target: https://github.com/nq-rdl/spec-kit-extensions
  → add a catalog entry there (team catalog, install_allowed: true).
Alternative: the public community catalog (github/spec-kit) — submit via its
  extension_submission.yml issue template, NOT a direct PR.

Load /speckit-dev:publish for the full flow (release tag, sha256, catalog entry).
Advisory only.
</speckit-publish-guidance>
CTX

if command -v jq >/dev/null 2>&1; then
  jq -n --arg ctx "$payload" '{
    hookSpecificOutput: {
      hookEventName: "UserPromptSubmit",
      additionalContext: $ctx
    }
  }'
else
  printf '%s\n' "$payload"
fi
