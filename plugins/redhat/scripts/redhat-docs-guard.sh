#!/usr/bin/env bash
# PreToolUse guard (redhat plugin), matcher Bash|WebFetch. Fires only when the call targets a
# Red Hat host or handles the offline token; everything else passes silently. Decisions via
# permissionDecision JSON:
#   WebFetch → Red Hat host                       deny  (Akamai 403; use /redhat:fetch-docs)
#   literal token on the command line             deny  (Bearer eyJ…, refresh_token=…, RH_OFFLINE_TOKEN=literal,
#                                                        quoted or not; RH_OFFLINE_TOKEN="$(…)" / $VAR / `…` pass)
#   printing/dumping/reading the token            deny  (echo/printf "$RH_OFFLINE_TOKEN", env|set|printenv dumps
#                                                        that mention it, cat/grep of the 0600 token file)
#   $RH_OFFLINE_TOKEN expanded on a curl/wget     deny  (the offline token is not a bearer; use rh-token.sh)
#   direct sso.redhat.com call                    ask   (use rh-token.sh)
#   Bash fetch not via curl/wget                  deny  (python/requests/httpie/node/…)
#   gated Portal host with no credential found    deny  (→ /redhat:setup); public KCS search allowed
# Hosts must appear as URL/bare hosts (…//docs.redhat.com/…), and tool names as command words, so
# `git commit -m "… RH_OFFLINE_TOKEN"`, `grep -rn RH_OFFLINE_TOKEN hooks/`, `oc get node …` and
# WebFetch of example.com/?ref=docs.redhat.com are not blocked — the plugin's own sources stay editable.
# The plugin scripts (rh-fetch.sh / rh-token.sh / rh-preflight.sh) are the sanctioned path and skip
# the fetcher and credential checks — but only when one of them is the command actually invoked
# from the plugin tree ("$S/rh-fetch.sh", "$CLAUDE_PLUGIN_ROOT/…/scripts/rh-fetch.sh"), not when the
# name merely appears in a comment, string, or argument, and not a look-alike such as ./rh-fetch.sh
# or my-rh-fetch.sh. The SSO check runs before that exemption, and the fetcher check runs per
# command segment (split on ; | && || newline), so "python … requests.get(<rh host>) # rh-fetch.sh"
# and "curl sso… ; : rh-token.sh" are still caught.
# JSON in/out via jq, falling back to python3; neither present, or malformed stdin → no-op.
set -u
command -v jq >/dev/null 2>&1 || command -v python3 >/dev/null 2>&1 || exit 0
input="$(cat 2>/dev/null)" || exit 0

field() { # <.dotted.path> → string value from $input, or empty
  if command -v jq >/dev/null 2>&1; then
    printf '%s' "$input" | jq -r "$1 // empty" 2>/dev/null
  else
    printf '%s' "$input" | python3 -c 'import json,sys
try: d = json.load(sys.stdin)
except Exception: sys.exit(0)
for k in sys.argv[1].strip(".").split("."):
    d = d.get(k) if isinstance(d, dict) else None
sys.stdout.write(d if isinstance(d, str) else "")' "$1" 2>/dev/null
  fi
}
decide() { # <allow|deny|ask> <reason>
  if command -v jq >/dev/null 2>&1; then
    jq -nc --arg d "$1" --arg r "$2" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:$d,permissionDecisionReason:$r}}'
  else
    python3 -c 'import json,sys; print(json.dumps({"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":sys.argv[1],"permissionDecisionReason":sys.argv[2]}}))' "$1" "$2"
  fi
  exit 0
}
tool="$(field .tool_name)"; [ -n "$tool" ] || exit 0

# A Red Hat host as a URL host or bare host word — not inside another host or a query value.
RH_HOSTS="(^|//|[[:space:]\"'])(docs|access|api\\.access|sso)\\.redhat\\.com([/:?#[:space:]\"']|$)"
SETUP='Run /redhat:setup — it guides generating a personal Red Hat offline token and storing it (Bitwarden, OS keychain, or a 0600 file).'

if [ "$tool" = "WebFetch" ]; then
  printf '%s' "$(field .tool_input.url)" | grep -Eq "$RH_HOSTS" || exit 0
  decide deny "WebFetch against Red Hat hosts gets an Akamai 403 (docs.redhat.com) or a locale-redirected, login-gated page (access.redhat.com). Use /redhat:fetch-docs: rh-fetch.sh routes docs.redhat.com URLs to the product's GitHub source and Customer Portal URLs to the KCS API with curl."
fi
[ "$tool" = "Bash" ] || exit 0
cmd="$(field .tool_input.command)"; [ -n "$cmd" ] || exit 0
has() { printf '%s' "$cmd" | grep -Eq "$1"; }

# Command position: start of line/segment, optionally after do/then/else and NAME=value prefixes.
CMDPOS='(^|[;&|(])[[:space:]]*((do|then|else)[[:space:]]+)?([A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*[[:space:]]+)*'
touches_rh=0; has "$RH_HOSTS" && touches_rh=1
assigns=0;    has 'RH_OFFLINE_TOKEN=' && assigns=1
expands=0;    has '\$\{?RH_OFFLINE_TOKEN' && expands=1
dumps=0;      has "${CMDPOS}((env|set|declare|typeset)[[:space:]]*(\$|[|>;&])|(export|declare|typeset)[[:space:]]+-p|printenv([[:space:]]|\$))" && has 'RH_OFFLINE_TOKEN' && dumps=1
reads_file=0; has "${CMDPOS}(cat|less|more|head|tail|bat|xxd|od|strings|grep|sed|awk|cp|scp)[[:space:]][^|;&]*redhat/offline-token" && reads_file=1
[ "$touches_rh" = 1 ] || [ "$assigns" = 1 ] || [ "$expands" = 1 ] || [ "$dumps" = 1 ] || [ "$reads_file" = 1 ] || exit 0

# 1. Secret hygiene — checked first, applies even to plugin scripts.
#    A literal value is anything after "=" (and an optional opening quote) that is not an expansion.
if has "RH_OFFLINE_TOKEN=[\"']?[^\$\`\"'[:space:]]"; then
  decide deny "That puts a literal Red Hat token on the command line (and in this transcript). Load it from a secret store instead: export RH_OFFLINE_TOKEN=\"\$(bw get notes redhat-credentials)\" in your own shell, or use the OS keychain. $SETUP"
fi
if [ "$expands" = 1 ] && has "${CMDPOS}(echo|printf)([[:space:]]|\$)"; then
  decide deny "Never print RH_OFFLINE_TOKEN — it would land in the transcript. Verify it with: rh-token.sh --check (reports source and expiry only)."
fi
if [ "$dumps" = 1 ]; then
  decide deny "Never dump the environment around RH_OFFLINE_TOKEN (env/set/printenv/declare) — the value would land in the transcript. Verify it with: rh-token.sh --check."
fi
if [ "$reads_file" = 1 ]; then
  decide deny "Never read the offline-token file into the transcript. rh-preflight.sh reports whether it exists; rh-token.sh --check verifies it."
fi
if [ "$expands" = 1 ] && has "${CMDPOS}(curl|wget)([[:space:]]|\$)"; then
  decide deny "Do not put \$RH_OFFLINE_TOKEN on a curl/wget command line: the offline token is a refresh token, not a bearer, and the expansion would be logged. rh-token.sh exchanges it and hands curl a 0600 config: curl -K \"\$(rh-token.sh --curl-config)\" URL"
fi
if has '(Bearer[[:space:]]+|refresh_token=|client_secret=)[A-Za-z0-9._-]{20,}'; then
  decide deny "Literal bearer/refresh token on the command line. rh-fetch.sh and rh-token.sh pass credentials via a 0600 curl config (-K), never as arguments."
fi
[ "$touches_rh" = 1 ] || exit 0

# 2. Direct SSO call — before the script exemption, so "curl sso… ; bash rh-token.sh" still asks.
if has "(^|//|[[:space:]\"'])sso\\.redhat\\.com([/:?#[:space:]\"']|\$)"; then
  decide ask "Direct call to Red Hat SSO. rh-token.sh does this exchange with the offline token kept out of argv and caches the 15-minute access token — prefer: rh-token.sh --check"
fi

# Patterns shared by steps 3–5.
#   SANCTIONED: a plugin script in command position, run directly or via bash/sh/"." with flags,
#   whose path is variable-prefixed ($S/, "${CLAUDE_PLUGIN_ROOT}"/…) or lives under a …/scripts/
#   directory — so a same-named file in the working directory (./rh-fetch.sh, my-rh-fetch.sh) is not exempt.
QT="[\"']?"
SANCTIONED="${CMDPOS}"'((bash|sh|source|\.)[[:space:]]+(-[A-Za-z]+[[:space:]]+)*)?'"$QT"'(\$\{?[A-Za-z_][A-Za-z0-9_]*\}?'"$QT"'/|[^[:space:]#;&|]*/scripts/)rh-(fetch|token|preflight)\.sh'"$QT"'([[:space:]]|$)'
#   INTERP: a non-curl fetcher as a command word, or an HTTP-library marker anywhere.
INTERP="${CMDPOS}(python3?|pip3?|node|deno|bun|ruby|perl|php|http|https|httpie|xh|Invoke-WebRequest|iwr)([[:space:]]|\$)|requests\\.|urllib|fetch\\(|axios"
#   FETCHER: curl/wget as a command word (a "curl" in a comment or argument does not count).
FETCHER="${CMDPOS}(curl|wget)([[:space:]]|\$)"
FETCH_DENY="Fetch Red Hat hosts with curl (preferred) or wget only — not python/requests/httpie/node. Use rh-fetch.sh from /redhat:fetch-docs, which also picks the route that actually works (docs.redhat.com is Akamai-blocked)."

# 3. Fetcher policy per command segment: a segment that names a Red Hat host and is not itself a
#    sanctioned-script invocation must not use a non-curl fetcher (a later "; bash rh-fetch.sh" or a
#    trailing "# rh-fetch.sh" comment does not launder it).
segments="$(printf '%s\n' "$cmd" | sed -e 's/&&/;/g' -e 's/||/;/g' | tr ';|' '\n\n')"
while IFS= read -r seg; do
  printf '%s' "$seg" | grep -Eq "$RH_HOSTS" || continue
  printf '%s' "$seg" | grep -Eq "$SANCTIONED" && continue
  if printf '%s' "$seg" | grep -Eq "$INTERP" && ! printf '%s' "$seg" | grep -Eq "$FETCHER"; then
    decide deny "$FETCH_DENY"
  fi
done <<<"$segments"

# 4. Plugin scripts are the sanctioned path (when actually invoked).
if has "$SANCTIONED"; then exit 0; fi

# 5. Fetcher policy over the whole command (catches an interpreter whose quoted code was split by ;).
if has "$INTERP" && ! has "$FETCHER"; then
  decide deny "$FETCH_DENY"
fi

# 6. Gated Portal hosts need a credential (public KCS search metadata does not). The preflight
#    script is looked up via CLAUDE_PLUGIN_ROOT, then relative to this hook's own plugin copy;
#    without it, the env var and the 0600 file are checked directly.
if has 'api\.access\.redhat\.com|access\.redhat\.com/(hydra|[a-z]{2}/)?(solutions|articles|hydra)'; then
  if has 'search/kcs' && ! has 'fq=id:'; then exit 0; fi
  pre=""
  for c in "${CLAUDE_PLUGIN_ROOT:-/nonexistent}/skills/fetch-docs/scripts/rh-preflight.sh" \
           "$(cd "$(dirname "$0")" 2>/dev/null && pwd)/../skills/fetch-docs/scripts/rh-preflight.sh"; do
    [ -f "$c" ] && { pre="$c"; break; }
  done
  if [ -n "$pre" ]; then bash "$pre" --require-cred >/dev/null 2>&1 && exit 0
  elif [ -n "${RH_OFFLINE_TOKEN:-}" ] || [ -s "${RH_OFFLINE_TOKEN_FILE:-${XDG_CONFIG_HOME:-$HOME/.config}/redhat/offline-token}" ]; then exit 0; fi
  decide deny "No Red Hat offline token found, and this Customer Portal content is subscriber-only (the API returns 200 with 'subscriber_only' placeholders instead of failing). $SETUP"
fi
exit 0
