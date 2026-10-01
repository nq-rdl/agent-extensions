#!/usr/bin/env bash
# User-terminal helper: encrypt a hidden paste (or optional Bitwarden seed).
# No plaintext temporary file, token argv, transcript output, or traced secret.
{ set +x +v; } 2>/dev/null
set -u
set -o pipefail
. "$(cd "$(dirname "$0")" && pwd)/rh-lib.sh"

recipient="${1:-}"; seed="${2:-}"
if [ -z "$recipient" ] || { [ -n "$seed" ] && [ "$seed" != --from-bitwarden ]; } || [ "$#" -gt 2 ]; then
  echo 'Usage: rh-store-sops.sh <public-age-recipient> [--from-bitwarden]' >&2; exit 2
fi
command -v sops >/dev/null 2>&1 || { echo 'Install sops >= 3.10 first. Run /redhat:setup.' >&2; exit 2; }
if [ "$seed" = --from-bitwarden ]; then
  RH_CRED_SOURCES=bitwarden
  t="$(rh_cred_token)" || { echo 'Bitwarden lookup failed; unlock/sync the vault in this terminal.' >&2; exit 3; }
else
  printf 'Paste offline token: ' >&2
  IFS= read -rs t || { echo 'Token prompt cancelled.' >&2; exit 3; }
  printf '\n' >&2
fi
# Tokens are JWT/base64url text. Reject newlines/dotenv injection before encrypting.
case "$t" in
  ''|*[!A-Za-z0-9._-]*) unset t; echo 'Empty or invalid token; nothing stored. Run /redhat:setup.' >&2; exit 3 ;;
esac
f="$(rh_cred_sops_file)"
umask 077
mkdir -p "$(dirname "$f")" || exit 2
# mktemp in the destination directory + rename replaces even a pre-existing symlink.
tmp="$(mktemp "$f.XXXXXX")" || exit 2
trap 'rm -f "$tmp"' EXIT
trap 'exit 2' HUP INT TERM
chmod 600 "$tmp" || exit 2
# sops 3.13.3: no positional filename means stdin; --filename-override is required.
# Only ciphertext is written to disk. Explicit regex prevents config from leaving this key clear.
if builtin printf 'RH_OFFLINE_TOKEN=%s\n' "$t" | sops encrypt --age "$recipient" \
    --input-type dotenv --output-type yaml --filename-override "$f" \
    --encrypted-regex '^RH_OFFLINE_TOKEN$' > "$tmp" 2>/dev/null \
    && [ -s "$tmp" ] && mv -f "$tmp" "$f"; then
  unset t
  printf 'stored in %s (sops + age)\n' "$f"
else
  unset t
  echo 'sops encryption/write failed; existing file unchanged. Check recipient and sops version.' >&2
  exit 2
fi
