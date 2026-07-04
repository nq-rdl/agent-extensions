#!/usr/bin/env bash
# UserPromptSubmit hook (speckit-dev plugin) — nudges "where to publish?" when the
# user is publishing a spec-kit extension. Fires only on spec-kit + publish
# markers; injects DECLARATIVE, fenced advisory context (never an instruction),
# via the UserPromptSubmit additionalContext channel. Silent no-op otherwise.

set -euo pipefail

input=$(cat)

if command -v jq >/dev/null 2>&1; then
  prompt=$(printf '%s' "$input" | jq -r '.prompt // empty')
elif command -v python3 >/dev/null 2>&1; then
  prompt=$(printf '%s' "$input" | python3 -c 'import sys, json; print(json.load(sys.stdin).get("prompt") or "")' 2>/dev/null || true)
else
  # Last-resort POSIX fallback (no jq/python3): scrape the "prompt" string
  # value with sed. Avoids grep -oP (PCRE), which BSD grep (macOS) lacks.
  prompt=$(printf '%s' "$input" | sed -n 's/.*"prompt"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' || true)
fi

# Gate: require a spec-kit marker AND a publish/distribute marker (or the explicit
# /speckit-dev:publish invocation). Avoids firing on scaffold/validate/manage.
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
