#!/usr/bin/env bash
# Search the web through Cloudflare Web Search API (open beta, docs as of
# 2026-10-02): POST /client/v4/accounts/{account_id}/ai/websearch/ via an AI Gateway.
#
# Usage: cf-websearch.sh [--provider ceramic|exa|linkup] [--limit 1-10]
#                        [--gateway ID] [--byok-alias ALIAS] [--text] [--] QUERY
#
# Credentials come from the environment and are never printed:
#   CLOUDFLARE_API_TOKEN   token with Account > Workers AI > Read and AI Gateway > Read
#   CLOUDFLARE_ACCOUNT_ID  account that owns the gateway
#   CLOUDFLARE_AI_GATEWAY_ID  optional default gateway (else "default")
# The token reaches curl as a config file read from stdin, so it never appears
# in argv or the process list.
#
# Output: the normalized result JSON ({items, metadata}); --text prints one
# numbered "title / url / description" block per item instead.
# Exit: 0 ok, 1 API or network error, 2 usage error, 3 missing credential or tool.
# Every call is billed (AI Gateway credits at provider list price, or BYOK).
set -euo pipefail

usage() { sed -n '5,6p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }
die() { printf 'cf-websearch: %s\n' "$1" >&2; exit "${2:-2}"; }

provider="" limit="" gateway="${CLOUDFLARE_AI_GATEWAY_ID:-default}" alias="" text=0 query=""
while [ $# -gt 0 ]; do
  case "$1" in
    --provider) [ $# -ge 2 ] || usage; provider="$2"; shift 2 ;;
    --limit) [ $# -ge 2 ] || usage; limit="$2"; shift 2 ;;
    --gateway) [ $# -ge 2 ] || usage; gateway="$2"; shift 2 ;;
    --byok-alias) [ $# -ge 2 ] || usage; alias="$2"; shift 2 ;;
    --text) text=1; shift ;;
    -h|--help) usage ;;
    --) shift; break ;;
    -*) die "unknown option: $1" ;;
    *) break ;;
  esac
done
[ $# -eq 1 ] || usage
query="$1"

# Documented request limits; reject locally instead of paying for a 400.
[ -n "$query" ] || die "query must not be empty"
[ "${#query}" -le 1024 ] || die "query is ${#query} characters; the limit is 1024"
case "$provider" in ""|ceramic|exa|linkup) ;; *) die "provider must be ceramic, exa or linkup" ;; esac
if [ -n "$limit" ]; then
  case "$limit" in ''|*[!0-9]*) die "limit must be an integer from 1 to 10" ;; esac
  [ "$limit" -ge 1 ] && [ "$limit" -le 10 ] || die "limit must be an integer from 1 to 10"
fi
if [ -n "$alias" ]; then
  case "$alias" in *[!A-Za-z0-9_-]*) die "byok alias must match [A-Za-z0-9_-]{1,64}" ;; esac
  [ "${#alias}" -le 64 ] || die "byok alias must match [A-Za-z0-9_-]{1,64}"
fi
case "$gateway" in ''|*[!A-Za-z0-9_-]*) die "gateway id must contain only letters, digits, - and _" ;; esac

command -v curl >/dev/null 2>&1 || die "curl is required" 3
command -v jq >/dev/null 2>&1 || die "jq is required" 3
[ -n "${CLOUDFLARE_API_TOKEN:-}" ] || die "CLOUDFLARE_API_TOKEN is not set" 3
[ -n "${CLOUDFLARE_ACCOUNT_ID:-}" ] || die "CLOUDFLARE_ACCOUNT_ID is not set" 3
case "$CLOUDFLARE_ACCOUNT_ID" in *[!A-Za-z0-9]*) die "CLOUDFLARE_ACCOUNT_ID must be alphanumeric" 3 ;; esac
# A token with a quote, backslash or line break would break the curl config line.
case "$CLOUDFLARE_API_TOKEN" in *[!A-Za-z0-9._~+/=_-]*) die "CLOUDFLARE_API_TOKEN contains unexpected characters" 3 ;; esac

body="$(jq -nc --arg q "$query" --arg p "$provider" --arg l "$limit" --arg g "$gateway" --arg a "$alias" \
  '{query: $q, options: {gateway: {id: $g}}}
   + (if $p != "" then {provider: $p} else {} end)
   + (if $l != "" then {limit: ($l | tonumber)} else {} end)
   + (if $a != "" then {byokAlias: $a} else {} end)')"

out="$(mktemp "${TMPDIR:-/tmp}/cf-websearch.XXXXXX")"
trap 'rm -f "$out"' EXIT
url="https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/ai/websearch/"
set +e
code="$(printf 'header = "Authorization: Bearer %s"\n' "$CLOUDFLARE_API_TOKEN" |
  curl --silent --show-error --max-time 60 --config - --request POST \
    --header 'Content-Type: application/json' --data "$body" \
    --output "$out" --write-out '%{http_code}' "$url")"
status=$?
set -e
[ "$status" -eq 0 ] || die "request failed (curl exit $status)" 1

if [ "$code" != 200 ]; then
  # Cloudflare v4 errors carry {errors: [{code, message}]}; never echo request headers.
  msg="$(jq -r '[.errors[]? | "\(.code // "")\(if .code then ": " else "" end)\(.message // "")"]
                | join("; ")' "$out" 2>/dev/null || true)"
  hint=""
  case "$code" in
    400) [ -n "$alias" ] && hint=" (byokAlias set: the alias or provider key is not configured on gateway '$gateway'; no fallback to credits)" ;;
    401|403) hint=" (check the token has Account > Workers AI > Read and AI Gateway > Read)" ;;
  esac
  die "HTTP $code${msg:+: $msg}$hint" 1
fi

# The documented shape is {items, metadata}; also accept a v4 {result: ...} envelope.
result='if type == "object" and has("result") and (.result | type) == "object" then .result else . end'
jq -e "$result | has(\"items\")" "$out" >/dev/null 2>&1 || die "unexpected response shape (no items)" 1
if [ "$text" -eq 1 ]; then
  jq -r "$result | .items | to_entries[] |
    \"\(.key + 1). \(.value.title // \"(untitled)\")\n   \(.value.url)\" +
    (if .value.description then \"\n   \(.value.description | gsub(\"\\\\s+\"; \" \") | .[0:300])\" else \"\" end)" "$out"
else
  jq "$result" "$out"
fi
