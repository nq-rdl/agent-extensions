#!/usr/bin/env bash
# PreToolUse guard (redhat plugin), matcher Bash|WebFetch. Fires only when the call targets a
# Red Hat host; everything else passes silently. Decisions via permissionDecision JSON:
#   WebFetch → Red Hat host                       deny  (Akamai 403; use /redhat:fetch-docs)
#   Bash fetch not via curl/wget                  deny  (python/requests/httpie/node/…)
#   literal token on the command line             deny  (Bearer eyJ…, refresh_token=…, RH_OFFLINE_TOKEN=literal)
#   printing/exporting RH_OFFLINE_TOKEN           deny  (echo/printf/env/set/cat of the secret)
#   direct sso.redhat.com call (not rh-token.sh)  ask   (use rh-token.sh)
#   gated Portal host with no credential found    deny  (→ /redhat:setup); public KCS search allowed
# jq missing or malformed stdin → no-op. Never blocks non-Red-Hat commands.
set -u
command -v jq >/dev/null 2>&1 || exit 0
input="$(cat 2>/dev/null)" || exit 0
tool="$(printf '%s' "$input" | jq -r '.tool_name // empty' 2>/dev/null)" || exit 0
[ -n "$tool" ] || exit 0

decide() { # <allow|deny|ask> <reason>
  jq -nc --arg d "$1" --arg r "$2" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:$d,permissionDecisionReason:$r}}'; exit 0
}
RH_HOSTS='(docs\.redhat\.com|access\.redhat\.com|api\.access\.redhat\.com|sso\.redhat\.com)'
SETUP='Run /redhat:setup — it guides generating a personal Red Hat offline token and storing it (Bitwarden, OS keychain, or a 0600 file).'

if [ "$tool" = "WebFetch" ]; then
  url="$(printf '%s' "$input" | jq -r '.tool_input.url // empty' 2>/dev/null)"
  printf '%s' "$url" | grep -Eq "$RH_HOSTS" || exit 0
  decide deny "WebFetch against Red Hat hosts gets an Akamai 403 (docs.redhat.com) or a locale-redirected, login-gated page (access.redhat.com). Use /redhat:fetch-docs: rh-fetch.sh routes docs.redhat.com URLs to the product's GitHub source and Customer Portal URLs to the KCS API with curl."
fi
[ "$tool" = "Bash" ] || exit 0
cmd="$(printf '%s' "$input" | jq -r '.tool_input.command // empty' 2>/dev/null)"
[ -n "$cmd" ] || exit 0
touches_rh=0; printf '%s' "$cmd" | grep -Eq "$RH_HOSTS" && touches_rh=1
mentions_secret=0; printf '%s' "$cmd" | grep -q 'RH_OFFLINE_TOKEN' && mentions_secret=1
[ "$touches_rh" = 1 ] || [ "$mentions_secret" = 1 ] || exit 0

# 1. Secret hygiene — checked first, applies even to plugin scripts.
if printf '%s' "$cmd" | grep -Eq 'RH_OFFLINE_TOKEN=[^$"'"'"'[:space:]]'; then
  decide deny "That puts a literal Red Hat token on the command line (and in this transcript). Load it from a secret store instead: export RH_OFFLINE_TOKEN=\"\$(bw get notes redhat-credentials)\" in your own shell, or use the OS keychain. $SETUP"
fi
if printf '%s' "$cmd" | grep -Eq '(^|[;&|[:space:]])(echo|printf|cat|env|set|export -p|declare|typeset)([[:space:]]|$)' && [ "$mentions_secret" = 1 ]; then
  decide deny "Never print or dump RH_OFFLINE_TOKEN — it would land in the transcript. Verify it with: rh-token.sh --check (reports source and expiry only)."
fi
if printf '%s' "$cmd" | grep -Eq '(Bearer[[:space:]]+|refresh_token=|client_secret=)[A-Za-z0-9._-]{20,}'; then
  decide deny "Literal bearer/refresh token on the command line. rh-fetch.sh and rh-token.sh pass credentials via a 0600 curl config (-K), never as arguments."
fi
[ "$touches_rh" = 1 ] || exit 0

# 2. Plugin scripts are the sanctioned path.
if printf '%s' "$cmd" | grep -Eq 'rh-(fetch|token|preflight)\.sh'; then exit 0; fi

# 3. Fetcher policy: curl or wget only.
if printf '%s' "$cmd" | grep -Eq '(^|[;&|[:space:]])(python3?|pip3?|node|deno|bun|ruby|perl|php|http|https|httpie|xh|Invoke-WebRequest|iwr)([[:space:]]|$)|requests\.|urllib|fetch\(|axios' \
   && ! printf '%s' "$cmd" | grep -Eq '(^|[;&|[:space:]])(curl|wget)([[:space:]]|$)'; then
  decide deny "Fetch Red Hat hosts with curl (preferred) or wget only — not python/requests/httpie/node. Use rh-fetch.sh from /redhat:fetch-docs, which also picks the route that actually works (docs.redhat.com is Akamai-blocked)."
fi
if printf '%s' "$cmd" | grep -q 'sso\.redhat\.com'; then
  decide ask "Direct call to Red Hat SSO. rh-token.sh does this exchange with the offline token kept out of argv and caches the 15-minute access token — prefer: rh-token.sh --check"
fi

# 4. Gated Portal hosts need a credential (public KCS search metadata does not).
if printf '%s' "$cmd" | grep -Eq 'api\.access\.redhat\.com|access\.redhat\.com/(hydra|[a-z]{2}/)?(solutions|articles|hydra)'; then
  if printf '%s' "$cmd" | grep -q 'search/kcs' && ! printf '%s' "$cmd" | grep -q 'fq=id:'; then exit 0; fi
  pre="${CLAUDE_PLUGIN_ROOT:-}/skills/fetch-docs/scripts/rh-preflight.sh"
  if [ -f "$pre" ]; then bash "$pre" --require-cred >/dev/null 2>&1 && exit 0
  elif [ -n "${RH_OFFLINE_TOKEN:-}" ]; then exit 0; fi
  decide deny "No Red Hat offline token found, and this Customer Portal content is subscriber-only (the API returns 200 with 'subscriber_only' placeholders instead of failing). $SETUP"
fi
exit 0
