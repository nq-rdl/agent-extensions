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

# Epoch mtime of a file: GNU `stat -c %Y`, then BSD `stat -f %m`, else 0. (BSD `date -r` takes an
# epoch, not a path, so it cannot be used for this; GNU must be probed first because GNU `stat -f`
# means "file-system status" and would succeed with the wrong answer.)
rh_file_mtime() {
  stat -c %Y "$1" 2>/dev/null || stat -f %m "$1" 2>/dev/null || echo 0
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
    # bw reads BW_SESSION from the environment — never pass it as --session (it would show in ps).
    if bw get notes "$RH_BW_ITEM" >/dev/null 2>&1; then echo bitwarden; return 0; fi
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
      notes="$(bw get notes "$RH_BW_ITEM" 2>/dev/null | tr -d '\r')"
      # Accept `export RH_OFFLINE_TOKEN=…`, `RH_OFFLINE_TOKEN=…`, or a bare JWT line (three
      # base64url segments — a label-like line such as a date or a name is not a token).
      printf '%s\n' "$notes" | sed -n 's/^[[:space:]]*\(export[[:space:]]\{1,\}\)\{0,1\}RH_OFFLINE_TOKEN=["'"'"']\{0,1\}\([^"'"'"'[:space:]]*\).*/\2/p' | head -1 | grep . \
        || printf '%s\n' "$notes" | grep -m1 -E '^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$' ;;
  esac
}

# Per-user runtime cache dir. The location is predictable, so a pre-planted directory or symlink in
# a shared /tmp must not be adopted: it has to be a real directory we own, mode 700.
rh_cache_dir() {
  local d="${XDG_RUNTIME_DIR:-${TMPDIR:-/tmp}}/rh-token-$(id -u)"
  [ -d "${d%/*}" ] || mkdir -p "${d%/*}" 2>/dev/null
  [ -e "$d" ] || [ -L "$d" ] || mkdir -m 700 "$d" 2>/dev/null || { echo "cannot create cache dir $d — point XDG_RUNTIME_DIR or TMPDIR at a writable private directory" >&2; return 1; }
  if [ -L "$d" ] || [ ! -d "$d" ] || [ ! -O "$d" ]; then
    echo "refusing cache dir $d: it must be a directory owned by you (not a symlink) — remove it, or point XDG_RUNTIME_DIR/TMPDIR at a private directory" >&2; return 1
  fi
  chmod 700 "$d" 2>/dev/null
  [ "$(rh_file_mode "$d")" = 700 ] || { echo "refusing cache dir $d: cannot set mode 700" >&2; return 1; }
  printf '%s\n' "$d"
}

# rh_atomic_write <file>  (content on stdin): write via a 0600 temp file in the same dir, then
# rename over the target, so a pre-existing file or symlink is replaced rather than followed.
rh_atomic_write() {
  local t; t="$(mktemp "$1.XXXXXX")" || return 1
  cat > "$t" && chmod 600 "$t" && mv -f "$t" "$1"
}

# _rh_wget <outfile> <url> [wget args…] → prints the last HTTP status seen (like curl -w). Keeps the
# response body on 4xx/5xx (--content-on-error) so callers can read error_description; when no HTTP
# status came back at all (DNS/connect failure) prints nothing, echoes wget's message, returns 1.
_rh_wget() {
  local out="$1" url="$2" errf code; shift 2
  errf="$(mktemp "${TMPDIR:-/tmp}/rh-wget.XXXXXX")" || return 1
  wget -q -S --content-on-error -O "$out" "$@" "$url" 2>"$errf"
  code="$(sed -n 's/^ *HTTP\/[0-9.]* \([0-9]*\).*/\1/p' "$errf" | tail -1)"
  [ -n "$code" ] || echo "wget: $(grep -v '^ ' "$errf" | tail -1)" >&2
  rm -f "$errf"
  printf '%s' "$code"; [ -n "$code" ]
}

# rh_http_get <url> <outfile> [curl-config]  → prints HTTP status; curl first, wget fallback.
# The optional config carries the Authorization header. curl reads it with -K; for wget it is
# translated into a 0600 wgetrc passed via --config, so the Bearer token never enters argv
# (/proc/<pid>/cmdline, ps) on either fetcher.
rh_http_get() {
  local url="$1" out="$2" cfg="${3:-}"
  if command -v curl >/dev/null 2>&1; then
    if [ -n "$cfg" ]; then curl -sS -L -K "$cfg" -o "$out" -w '%{http_code}' "$url"; else curl -sS -L -o "$out" -w '%{http_code}' "$url"; fi
  elif command -v wget >/dev/null 2>&1; then
    local rc=""
    if [ -n "$cfg" ]; then
      rc="$(mktemp "${TMPDIR:-/tmp}/rh-wgetrc.XXXXXX")" || return 1
      chmod 600 "$rc"
      # curl:  header = "Authorization: Bearer …"   →   wgetrc:  header = Authorization: Bearer …
      sed -n 's/^header = "\(.*\)"$/header = \1/p' "$cfg" > "$rc"
    fi
    _rh_wget "$out" "$url" ${rc:+"--config=$rc"}
    local status=$?
    [ -z "$rc" ] || rm -f "$rc"
    return $status
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
    _rh_wget "$out" "$url" --header='Content-Type: application/x-www-form-urlencoded' --post-file="$body"
  else
    echo "no fetcher: install curl (preferred) or wget" >&2; return 1
  fi
}
