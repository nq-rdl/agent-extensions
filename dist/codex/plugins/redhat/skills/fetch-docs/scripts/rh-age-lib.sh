#!/usr/bin/env bash
# Shared path and device detection; optional device argument supports offline fixtures.
rh_age_key_file() {
  if [ -n "${SOPS_AGE_KEY_FILE:-}" ]; then
    printf '%s\n' "$SOPS_AGE_KEY_FILE"
  else
    case "$(uname -s)" in
      Darwin) printf '%s/sops/age/keys.txt\n' "${XDG_CONFIG_HOME:-$HOME/Library/Application Support}" ;;
      *) printf '%s/sops/age/keys.txt\n' "${XDG_CONFIG_HOME:-$HOME/.config}" ;;
    esac
  fi
}
rh_tpm_status() {
  local device="${1:-/dev/tpmrm0}"
  if [ "$(uname -s)" != Linux ] || [ ! -e "$device" ]; then
    echo none
  elif [ -r "$device" ] && [ -w "$device" ]; then
    echo accessible
  else
    echo present
  fi
}
