#!/usr/bin/env bash
# Exchange the personal Red Hat offline token for a short-lived access token.
# The token never appears on a command line, in output, or in a world-readable file.
#
#   rh-token.sh [--check]     # exchange NOW (ignores the cache, so it verifies the stored token),
#                             # refresh the cache, print source + expiry (default)
#   rh-token.sh --curl-config # reuse the cached access token if still valid, else exchange; print
#                             # the path of a 0600 curl config carrying the Authorization header:
#                             #   curl -K "$(rh-token.sh --curl-config)" URL
#   rh-token.sh --clear       # drop the cached access token
#
# Exit codes: 0 ok · 2 network/HTTP error · 3 no offline token found (→ /redhat:setup)
#             4 offline token rejected/expired (invalid_grant → regenerate, then /redhat:setup)
set -u
# shellcheck source=rh-lib.sh
. "$(cd "$(dirname "$0")" && pwd)/rh-lib.sh"

mode="${1:---check}"
cache="$(rh_cache_dir)" || exit 2
acc="$cache/access.env"; cfg="$cache/curl.cfg"

if [ "$mode" = "--clear" ]; then rm -f "$acc" "$cfg"; echo "cleared $cache"; exit 0; fi

now="$(date +%s)"
# Only --curl-config may use the cache: --check exists to prove the *stored offline token* works,
# and a cache hit would report success for a token that was just re-stored wrongly.
if [ "$mode" = "--curl-config" ] && [ -s "$acc" ] && [ ! -L "$acc" ] && [ -s "$cfg" ] && [ ! -L "$cfg" ]; then
  exp="$(sed -n 's/^exp=//p' "$acc")"
  if [ -n "$exp" ] && [ "$((exp - now))" -gt 60 ]; then printf '%s\n' "$cfg"; exit 0; fi
fi

src="$(rh_cred_source 2>/dev/null || true)"
if [ -z "$src" ]; then
  echo "No Red Hat offline token found (looked in: $RH_CRED_SOURCES). $RH_SETUP_HINT" >&2; exit 3
fi
tok="$(rh_cred_token)"
if [ -z "$tok" ]; then echo "Credential source '$src' returned an empty token. $RH_SETUP_HINT" >&2; exit 3; fi

body="$(mktemp "$cache/post.XXXXXX")"; out="$(mktemp "$cache/resp.XXXXXX")"
trap 'rm -f "$body" "$out"' EXIT
chmod 600 "$body" "$out"
# Offline tokens are base64url JWTs — no percent-encoding needed; the body goes via file, not argv.
printf 'grant_type=refresh_token&client_id=%s&refresh_token=%s' "$RH_SSO_CLIENT_ID" "$tok" > "$body"
unset tok
code="$(rh_http_post_form "$RH_SSO_TOKEN_URL" "$body" "$out")" || exit 2

if [ "$code" != "200" ]; then
  err="$(jq -r '.error // empty' "$out" 2>/dev/null)"; desc="$(jq -r '.error_description // empty' "$out" 2>/dev/null)"
  if [ "$err" = "invalid_grant" ] || [ "$code" = "400" ] || [ "$code" = "401" ]; then
    rm -f "$acc" "$cfg"   # a rejected offline token must not leave a stale access token behind
    echo "Red Hat SSO rejected the offline token from '$src' (HTTP $code${err:+ $err}${desc:+: $desc}). Offline tokens expire after 30 days unused — generate a new one at $RH_TOKEN_PAGE, store it, then re-run. $RH_SETUP_HINT" >&2; exit 4
  fi
  echo "Token exchange failed: HTTP $code from $RH_SSO_TOKEN_URL" >&2; exit 2
fi
access="$(jq -r '.access_token // empty' "$out")"; ttl="$(jq -r '.expires_in // 900' "$out")"
[ -n "$access" ] || { echo "Token exchange returned no access_token" >&2; exit 2; }
# Atomic 0600 writes: a pre-existing curl.cfg (or symlink) is replaced, never truncated in place.
printf 'header = "Authorization: Bearer %s"\n' "$access" | rh_atomic_write "$cfg" || { echo "cannot write $cfg" >&2; exit 2; }
printf 'source=%s\nexp=%s\n' "$src" "$((now + ttl))" | rh_atomic_write "$acc" || { echo "cannot write $acc" >&2; exit 2; }
unset access
[ "$mode" = "--curl-config" ] && { printf '%s\n' "$cfg"; exit 0; }
echo "source=$src access_token=ok expires_in=${ttl}s"
