#!/usr/bin/env bash
# Drop-in Bitwarden shell functions for ~/.zshrc or ~/.bashrc
# Requires: bw (Bitwarden CLI), jq
#
# Source this file: source /path/to/bw-env.sh
# Or copy the functions directly into your shell config.

# ---------------------------------------------------------------------------
# Session management — unlock vault if no active session
# ---------------------------------------------------------------------------
bwss() {
  if [[ -z "$BW_SESSION" ]]; then
    >&2 echo "bw: vault locked — unlocking..."
    export BW_SESSION="$(bw unlock --raw)"
  fi
}

# ---------------------------------------------------------------------------
# bwe <item-name-or-uuid>
# Load a Secure Note's content as env vars into the current shell.
# The note must contain lines like: export KEY=value
# ---------------------------------------------------------------------------
bwe() {
  if [[ -z "$1" ]]; then
    >&2 echo "Usage: bwe <vault-item-name-or-uuid>"
    return 1
  fi
  bwss
  local notes
  notes="$(bw get notes "$1" --session "$BW_SESSION")"
  if [[ -z "$notes" ]]; then
    >&2 echo "bwe: item '$1' not found or has no notes"
    return 1
  fi
  eval "$notes"
  >&2 echo "bwe: loaded '$1'"
}

# ---------------------------------------------------------------------------
# bwc <item-name> [env-file]
# Create a new Secure Note vault item from a .env file.
# Default env file: .env in current directory.
# ---------------------------------------------------------------------------
bwc() {
  if [[ -z "$1" ]]; then
    >&2 echo "Usage: bwc <vault-item-name> [path-to-env-file]"
    return 1
  fi
  bwss
  local name="$1"
  local envfile="${2:-.env}"
  if [[ ! -f "$envfile" ]]; then
    >&2 echo "bwc: file not found: $envfile"
    return 1
  fi
  local notes
  notes="$(awk '/^[[:space:]]*#/ || /^[[:space:]]*$/ { print; next } /^export / { print; next } { print "export " $0 }' "$envfile")"
  bw get template item \
    | jq --arg n "$notes" --arg name "$name" \
         '.type = 2 | .secureNote.type = 0 | .notes = $n | .name = $name' \
    | bw encode | bw create item --session "$BW_SESSION"
}

# ---------------------------------------------------------------------------
# bwu <item-name> [env-file]
# Update an existing vault item's notes from a .env file.
# Default env file: .env in current directory.
# ---------------------------------------------------------------------------
bwu() {
  if [[ -z "$1" ]]; then
    >&2 echo "Usage: bwu <vault-item-name> [path-to-env-file]"
    return 1
  fi
  bwss
  local name="$1"
  local envfile="${2:-.env}"
  if [[ ! -f "$envfile" ]]; then
    >&2 echo "bwu: file not found: $envfile"
    return 1
  fi
  local id
  id="$(bw get item "$name" --session "$BW_SESSION" | jq -r '.id')"
  if [[ -z "$id" || "$id" == "null" ]]; then
    >&2 echo "bwu: item '$name' not found — use bwc to create it first"
    return 1
  fi
  local notes
  notes="$(awk '/^[[:space:]]*#/ || /^[[:space:]]*$/ { print; next } /^export / { print; next } { print "export " $0 }' "$envfile")"
  bw get item "$id" --session "$BW_SESSION" \
    | jq --arg n "$notes" '.notes = $n' \
    | bw encode | bw edit item "$id" --session "$BW_SESSION"
  >&2 echo "bwu: updated '$name'"
}

# ---------------------------------------------------------------------------
# bwl [search]
# List vault item names (optionally filtered by search term).
# ---------------------------------------------------------------------------
bwl() {
  bwss
  bw list items --search "${1:-}" --session "$BW_SESSION" \
    | jq -r '.[].name' | sort
}

# bwll [search] — list with UUIDs
bwll() {
  bwss
  bw list items --search "${1:-}" --session "$BW_SESSION" \
    | jq -r '.[] | "\(.name)\t\(.id)"' | sort
}

# ---------------------------------------------------------------------------
# bwf <item-name> <field-name>
# Get a single custom field value from a Login item.
# ---------------------------------------------------------------------------
bwf() {
  if [[ -z "$1" || -z "$2" ]]; then
    >&2 echo "Usage: bwf <item-name> <field-name>"
    return 1
  fi
  bwss
  bw get item "$1" --session "$BW_SESSION" \
    | jq -r --arg f "$2" '.fields[] | select(.name == $f) | .value'
}

# ---------------------------------------------------------------------------
# bwdd <item-name>
# Delete a vault item by name (sends to trash — recoverable for 30 days).
# ---------------------------------------------------------------------------
bwdd() {
  if [[ -z "$1" ]]; then
    >&2 echo "Usage: bwdd <vault-item-name>"
    return 1
  fi
  bwss
  local id
  id="$(bw get item "$1" --session "$BW_SESSION" | jq -r '.id')"
  bw delete item "$id" --session "$BW_SESSION"
  >&2 echo "bwdd: '$1' moved to trash"
}

# ---------------------------------------------------------------------------
# bwunload <item-name>
# Unset all env vars that were loaded from a given vault item.
# ---------------------------------------------------------------------------
bwunload() {
  if [[ -z "$1" ]]; then
    >&2 echo "Usage: bwunload <vault-item-name>"
    return 1
  fi
  bwss
  local vars
  vars="$(bw get notes "$1" --session "$BW_SESSION" | sed -n 's/^export \([a-zA-Z_][a-zA-Z0-9_]*\)=.*/\1/p')"
  for v in $vars; do
    unset "$v"
  done
  >&2 echo "bwunload: unset vars from '$1'"
}

# ---------------------------------------------------------------------------
# bwdotenv <item-name> [output-file]
# Write vault Secure Note to a .env file (for tools that require files).
# WARNING: Creates plaintext file. Delete after use. Never commit.
# Default output: .env in current directory.
# ---------------------------------------------------------------------------
bwdotenv() {
  if [[ -z "$1" ]]; then
    >&2 echo "Usage: bwdotenv <vault-item-name> [output-file]"
    return 1
  fi
  bwss
  local out="${2:-.env}"
  bw get notes "$1" --session "$BW_SESSION" \
    | sed 's/^export //' \
    > "$out"
  >&2 echo "bwdotenv: wrote '$out' — DELETE THIS FILE when done, never commit it"
}
