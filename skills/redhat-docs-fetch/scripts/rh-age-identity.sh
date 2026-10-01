#!/usr/bin/env bash
# User-terminal helper. stdout contains only one public recipient, never key material.
{ set +x +v; } 2>/dev/null
set -eu
set -o pipefail
. "$(cd "$(dirname "$0")" && pwd)/rh-age-lib.sh"
[ "$#" -eq 0 ] || { echo 'Usage: rh-age-identity.sh' >&2; exit 2; }
k="$(rh_age_key_file)"
umask 077
[ ! -L "$k" ] || { echo 'Refusing a symlink identity.' >&2; exit 2; }
if [ ! -e "$k" ]; then
  tool=age-keygen
  if [ "$(rh_tpm_status)" = accessible ] && command -v age-plugin-tpm >/dev/null 2>&1; then
    tool=age-plugin-tpm
  fi
  command -v "$tool" >/dev/null 2>&1 || { echo "Install $tool first." >&2; exit 2; }
  mkdir -p "$(dirname "$k")"
  tmp="$(mktemp "$k.XXXXXX")"
  trap 'rm -f "$tmp"' EXIT
  trap 'exit 2' HUP INT TERM
  # Generate to stdout into an already-private file, then publish without clobbering.
  if [ "$tool" = age-plugin-tpm ]; then
    "$tool" --generate > "$tmp" 2>/dev/null || { echo 'TPM identity generation failed.' >&2; exit 2; }
  else
    "$tool" > "$tmp" 2>/dev/null || { echo 'age identity generation failed.' >&2; exit 2; }
  fi
  [ -s "$tmp" ] || { echo 'Empty identity; nothing created.' >&2; exit 2; }
  chmod 600 "$tmp"
  ln "$tmp" "$k" || { echo 'Identity appeared concurrently; not overwritten.' >&2; exit 2; }
fi
[ -f "$k" ] && [ -r "$k" ] || { echo 'Identity is not a readable file.' >&2; exit 2; }
# Existing identities determine the tool; never replace a plain key with a TPM key.
if grep -q '^AGE-PLUGIN-TPM-' "$k"; then
  tool=age-plugin-tpm
else
  tool=age-keygen
fi
command -v "$tool" >/dev/null 2>&1 || { echo "Install $tool to read the existing identity." >&2; exit 2; }
r="$("$tool" -y "$k" 2>/dev/null)" || { echo 'Cannot derive public recipient from identity.' >&2; exit 2; }
case "$r" in
  age1*) case "$r" in *[!a-z0-9]*) echo 'Expected one public age recipient; supply recipients explicitly to rh-store-sops.sh for multi-key files.' >&2; exit 2 ;; esac ;;
  *) echo 'Invalid public age recipient.' >&2; exit 2 ;;
esac
printf '%s\n' "$r"
