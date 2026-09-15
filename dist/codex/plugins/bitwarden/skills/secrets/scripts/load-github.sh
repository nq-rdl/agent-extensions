#!/usr/bin/env bash
# On-demand GitHub token loader — Gruntwork pattern.
#
# Setup:
#   1. Store your GitHub PAT as a Secure Note in Bitwarden.
#      The note content is just the raw token (no "export" prefix needed).
#   2. Find the item UUID:
#        bw list items --search "GITHUB_TOKEN" | jq -r '.[0].id'
#   3. Replace ITEM_UUID below with the actual UUID.
#   4. Add to ~/.zshrc:
#        fpath=(~/.zsh_autoload_functions "${fpath[@]}")
#        autoload -Uz load_github
#      Then copy this file to ~/.zsh_autoload_functions/load_github
#
# Usage (in terminal, on demand):
#   load_github

load_github() {
  if [[ -z "$BW_SESSION" ]]; then
    >&2 echo "bw: vault locked — unlocking..."
    export BW_SESSION="$(bw unlock --raw)"
  fi

  # Use UUID (not name) — immune to item renames
  local ITEM_UUID="REPLACE-WITH-YOUR-ITEM-UUID"

  local token
  token="$(bw get notes "$ITEM_UUID" --session "$BW_SESSION")"

  if [[ -z "$token" ]]; then
    >&2 echo "load_github: token not found — check ITEM_UUID and run 'bw sync'"
    return 1
  fi

  # Export under multiple names for broad tool compatibility
  export GITHUB_OAUTH_TOKEN="$token"
  export GITHUB_TOKEN="$token"
  export GIT_TOKEN="$token"

  >&2 echo "load_github: GitHub token loaded (unset GITHUB_TOKEN to clear)"
}

load_github "$@"
