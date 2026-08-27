#!/usr/bin/env bash
# Shared helpers for the redhat plugin scripts (sourced, not executed).
# Portable across macOS bash 3.2 and Linux bash 5: no associative arrays,
# no ${var,,}, no mapfile. Never prints a token to stdout unless the caller
# explicitly asks via rh_cred_token (used only by rh-token.sh).

RH_SSO_TOKEN_URL='https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token'
RH_SSO_CLIENT_ID='rhsm-api'
RH_KCS_API='https://api.access.redhat.com/support/search/kcs'
RH_TOKEN_PAGE='https://access.redhat.com/management/api'
RH_SETUP_HINT='Run /redhat:setup — it guides generating a personal Red Hat offline token and storing it (Bitwarden, OS keychain, or a 0600 file).'
RH_BW_ITEM="${RH_BW_ITEM:-redhat-credentials}"
RH_CRED_SOURCES="${RH_CRED_SOURCES:-env,keychain,file,bitwarden}"

rh_os() {
  case "$(uname -s 2>/dev/null)" in
    Darwin) echo Darwin ;;
    Linux)
      if [ -r /proc/version ] && grep -qi microsoft /proc/version 2>/dev/null; then echo WSL; else echo Linux; fi ;;
    *) uname -s 2>/dev/null || echo unknown ;;
  esac
}

rh_fetcher() {
  if command -v curl >/dev/null 2>&1; then
    printf 'curl %s\n' "$(curl --version 2>/dev/null | head -1 | awk '{print $2}')"
  elif command -v wget >/dev/null 2>&1; then
    printf 'wget %s\n' "$(wget --version 2>/dev/null | head -1 | awk '{print $3}')"
  else
    echo none
  fi
}

rh_cred_file() {
  printf '%s\n' "${RH_OFFLINE_TOKEN_FILE:-${XDG_CONFIG_HOME:-$HOME/.config}/redhat/offline-token}"
}

rh_file_mode() { # octal permission bits of a file, GNU or BSD stat
  if stat -c %a "$1" >/dev/null 2>&1; then stat -c %a "$1"; else stat -f %Lp "$1" 2>/dev/null; fi
}

_rh_source_enabled() { case ",$RH_CRED_SOURCES," in *",$1,"*) return 0 ;; *) return 1 ;; esac; }

# Print the name of the first credential source that yields a token, or nothing.
rh_cred_source() {
  local f
  if _rh_source_enabled env && [ -n "${RH_OFFLINE_TOKEN:-}" ]; then echo env; return 0; fi
  if _rh_source_enabled keychain; then
    case "$(rh_os)" in
      Darwin) if security find-generic-password -a "$USER" -s RH_OFFLINE_TOKEN -w >/dev/null 2>&1; then echo keychain; return 0; fi ;;
      *) if command -v secret-tool >/dev/null 2>&1 && [ -n "$(secret-tool lookup service redhat key RH_OFFLINE_TOKEN 2>/dev/null)" ]; then echo keychain; return 0; fi ;;
    esac
  fi
  if _rh_source_enabled file; then
    f="$(rh_cred_file)"
    if [ -s "$f" ]; then echo file; return 0; fi
  fi
  if _rh_source_enabled bitwarden && command -v bw >/dev/null 2>&1 && [ -n "${BW_SESSION:-}" ]; then
    if bw get notes "$RH_BW_ITEM" --session "$BW_SESSION" >/dev/null 2>&1; then echo bitwarden; return 0; fi
  fi
  return 1
}

# Print the token itself. ONLY rh-token.sh may call this; callers must capture
# into a variable and never echo it.
rh_cred_token() {
  local src f notes
  src="$(rh_cred_source)" || return 1
  case "$src" in
    env) printf '%s\n' "$RH_OFFLINE_TOKEN" ;;
    keychain)
      case "$(rh_os)" in
        Darwin) security find-generic-password -a "$USER" -s RH_OFFLINE_TOKEN -w 2>/dev/null ;;
        *) secret-tool lookup service redhat key RH_OFFLINE_TOKEN 2>/dev/null ;;
      esac ;;
    file)
      f="$(rh_cred_file)"
      case "$(rh_file_mode "$f")" in
        600|400) ;;
        *) echo "warning: $f is not mode 0600 — run: chmod 600 '$f'" >&2 ;;
      esac
      head -1 "$f" | tr -d '[:space:]' ;;
    bitwarden)
      notes="$(bw get notes "$RH_BW_ITEM" --session "$BW_SESSION" 2>/dev/null)"
      # Accept `export RH_OFFLINE_TOKEN=…`, `RH_OFFLINE_TOKEN=…`, or a bare token line.
      printf '%s\n' "$notes" | sed -n 's/^[[:space:]]*\(export[[:space:]]\{1,\}\)\{0,1\}RH_OFFLINE_TOKEN=["'"'"']\{0,1\}\([^"'"'"'[:space:]]*\).*/\2/p' | head -1 | grep . \
        || printf '%s\n' "$notes" | grep -m1 -E '^[A-Za-z0-9._-]{20,}$' ;;
  esac
}

rh_cache_dir() {
  local d="${XDG_RUNTIME_DIR:-${TMPDIR:-/tmp}}/rh-token-$(id -u)"
  mkdir -p "$d" 2>/dev/null && chmod 700 "$d" 2>/dev/null
  printf '%s\n' "$d"
}

# rh_http_get <url> <outfile> [curl-config]  → prints HTTP status; curl first, wget fallback.
rh_http_get() {
  local url="$1" out="$2" cfg="${3:-}"
  if command -v curl >/dev/null 2>&1; then
    if [ -n "$cfg" ]; then curl -sS -L -K "$cfg" -o "$out" -w '%{http_code}' "$url"; else curl -sS -L -o "$out" -w '%{http_code}' "$url"; fi
  elif command -v wget >/dev/null 2>&1; then
    local hdr=""
    [ -n "$cfg" ] && hdr="$(sed -n 's/^header = "\(.*\)"$/\1/p' "$cfg" | head -1)"
    wget -q -S -O "$out" ${hdr:+--header="$hdr"} "$url" 2>&1 | sed -n 's/^ *HTTP\/[0-9.]* \([0-9]*\).*/\1/p' | tail -1
  else
    echo "no fetcher: install curl (preferred) or wget" >&2; return 1
  fi
}

# rh_http_post_form <url> <bodyfile> <outfile> → prints HTTP status (body file holds form data).
rh_http_post_form() {
  local url="$1" body="$2" out="$3"
  if command -v curl >/dev/null 2>&1; then
    curl -sS -o "$out" -w '%{http_code}' -X POST -H 'Content-Type: application/x-www-form-urlencoded' --data-binary "@$body" "$url"
  elif command -v wget >/dev/null 2>&1; then
    wget -q -S -O "$out" --header='Content-Type: application/x-www-form-urlencoded' --post-file="$body" "$url" 2>&1 | sed -n 's/^ *HTTP\/[0-9.]* \([0-9]*\).*/\1/p' | tail -1
  else
    echo "no fetcher: install curl (preferred) or wget" >&2; return 1
  fi
}
