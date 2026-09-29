#!/usr/bin/env bash
# Drop-in Bitwarden shell functions for ~/.zshrc or ~/.bashrc.
# Requires: bw (Bitwarden Password Manager CLI), jq, awk.
#
# Source this file: source /path/to/bw-env.sh
# This file is the single implementation owner; SKILL.md and the references
# describe it but do not carry divergent copies.
#
# Storage format: a Secure Note whose notes are lines of
#   export NAME='literal value'
# plus comments and blank lines. bwc/bwu write this form from a .env file;
# bwe refuses to eval anything else. Values are literal: no $VAR interpolation.
# No function prints a stored value, except bwf (meant for $(...) capture) and
# bwdotenv (writes a plaintext file on request).

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# _bw_env_exports <env-file>
# Convert a .env file to export lines with single-quoted literal values.
# Accepts NAME=value, export NAME=value, "double" or 'single' quoted values,
# and drops " #comment" after an unquoted value. Fails on any other line and
# reports only its line number, never its content.
_bw_env_exports() {
  awk -v sq="'" '
    function quote(v,   out) {
      out = v
      gsub(sq, sq "\\" sq sq, out)
      return sq out sq
    }
    /^[[:space:]]*#/ || /^[[:space:]]*$/ { print; next }
    {
      line = $0
      sub(/^[[:space:]]+/, "", line)
      sub(/^export[[:space:]]+/, "", line)
      eq = index(line, "=")
      name = substr(line, 1, eq - 1)
      if (eq == 0 || name !~ /^[A-Za-z_][A-Za-z0-9_]*$/) {
        printf "bw-env: line %d is not NAME=value\n", NR > "/dev/stderr"
        bad = 1
        next
      }
      value = substr(line, eq + 1)
      sub(/[[:space:]\r]+$/, "", value)
      first = substr(value, 1, 1)
      last = substr(value, length(value), 1)
      if (length(value) >= 2 && (first == "\"" || first == sq) && last == first) {
        value = substr(value, 2, length(value) - 2)
      } else {
        sub(/[[:space:]]+#.*$/, "", value)
      }
      print "export " name "=" quote(value)
    }
    END { exit bad }
  ' "$1"
}

# _bw_env_check <notes>
# Succeed only when every non-comment line is export NAME=<safe value>:
# single-quoted, double-quoted without $ ` \, or bare without shell syntax.
_bw_env_check() {
  printf '%s\n' "$1" | awk -v sq="'" '
    BEGIN {
      name = "^export [A-Za-z_][A-Za-z0-9_]*="
      single = sq "[^" sq "]*(" sq "\\\\" sq sq "[^" sq "]*)*" sq
      double = "\"[^\"$`\\\\]*\""
      bare = "[^[:space:]" sq "\"$`\\\\;&|<>(){}]*"
      ok = name "(" single "|" double "|" bare ")$"
    }
    /^[[:space:]]*#/ || /^[[:space:]]*$/ { next }
    $0 !~ ok { printf "bw-env: note line %d is not a plain export; refusing to eval\n", NR > "/dev/stderr"; bad = 1 }
    END { exit bad }
  '
}

# ---------------------------------------------------------------------------
# bwss — unlock the vault if this shell has no session
# ---------------------------------------------------------------------------
bwss() {
  if [[ -z "${BW_SESSION:-}" ]]; then
    >&2 echo "bw: vault locked — unlocking..."
    local session
    session="$(bw unlock --raw)" || return 1
    [[ -n "$session" ]] || return 1
    export BW_SESSION="$session"
  fi
}

# ---------------------------------------------------------------------------
# bwe <item-name-or-uuid>
# Load a Secure Note written by bwc/bwu into the current shell.
# ---------------------------------------------------------------------------
bwe() {
  if [[ -z "${1:-}" ]]; then
    >&2 echo "Usage: bwe <vault-item-name-or-uuid>"
    return 1
  fi
  bwss || return 1
  local notes
  notes="$(bw get notes "$1" --session "$BW_SESSION")"
  if [[ -z "$notes" ]]; then
    >&2 echo "bwe: item '$1' not found or has no notes"
    return 1
  fi
  _bw_env_check "$notes" || return 1
  eval "$notes"
  >&2 echo "bwe: loaded '$1'"
}

# ---------------------------------------------------------------------------
# bwc <item-name> [env-file]
# Create a Secure Note from a .env file (default: ./.env).
# ---------------------------------------------------------------------------
bwc() {
  if [[ -z "${1:-}" ]]; then
    >&2 echo "Usage: bwc <vault-item-name> [path-to-env-file]"
    return 1
  fi
  local name="$1"
  local envfile="${2:-.env}"
  if [[ ! -f "$envfile" ]]; then
    >&2 echo "bwc: file not found: $envfile"
    return 1
  fi
  local notes created
  notes="$(_bw_env_exports "$envfile")" || return 1
  bwss || return 1
  # bw create prints the whole item, notes included: keep it off the terminal.
  created="$(bw get template item \
    | jq --arg n "$notes" --arg name "$name" \
         '.type = 2 | .secureNote = {type: 0} | .login = null | .notes = $n | .name = $name' \
    | bw encode | bw create item --session "$BW_SESSION")" || return 1
  >&2 echo "bwc: created '$name' ($(printf '%s' "$created" | jq -r '.id'))"
}

# ---------------------------------------------------------------------------
# bwu <item-name> [env-file]
# Replace an existing item's notes from a .env file (default: ./.env).
# ---------------------------------------------------------------------------
bwu() {
  if [[ -z "${1:-}" ]]; then
    >&2 echo "Usage: bwu <vault-item-name> [path-to-env-file]"
    return 1
  fi
  local name="$1"
  local envfile="${2:-.env}"
  if [[ ! -f "$envfile" ]]; then
    >&2 echo "bwu: file not found: $envfile"
    return 1
  fi
  local notes id
  notes="$(_bw_env_exports "$envfile")" || return 1
  bwss || return 1
  id="$(bw get item "$name" --session "$BW_SESSION" | jq -r '.id')"
  if [[ -z "$id" || "$id" == "null" ]]; then
    >&2 echo "bwu: item '$name' not found — use bwc to create it first"
    return 1
  fi
  bw get item "$id" --session "$BW_SESSION" \
    | jq --arg n "$notes" '.notes = $n' \
    | bw encode | bw edit item "$id" --session "$BW_SESSION" >/dev/null || return 1
  >&2 echo "bwu: updated '$name'"
}

# ---------------------------------------------------------------------------
# bwl [search] — list item names; bwll [search] — names with UUIDs
# ---------------------------------------------------------------------------
bwl() {
  bwss || return 1
  bw list items --search "${1:-}" --session "$BW_SESSION" \
    | jq -r '.[].name' | sort
}

bwll() {
  bwss || return 1
  bw list items --search "${1:-}" --session "$BW_SESSION" \
    | jq -r '.[] | "\(.name)\t\(.id)"' | sort
}

# ---------------------------------------------------------------------------
# bwf <item-name> <field-name>
# Print one custom field value. Prints a secret: capture it with $(...).
# ---------------------------------------------------------------------------
bwf() {
  if [[ -z "${1:-}" || -z "${2:-}" ]]; then
    >&2 echo "Usage: bwf <item-name> <field-name>"
    return 1
  fi
  bwss || return 1
  bw get item "$1" --session "$BW_SESSION" \
    | jq -r --arg f "$2" '.fields[] | select(.name == $f) | .value'
}

# ---------------------------------------------------------------------------
# bwdd <item-name> — move an item to the trash (recoverable for 30 days)
# ---------------------------------------------------------------------------
bwdd() {
  if [[ -z "${1:-}" ]]; then
    >&2 echo "Usage: bwdd <vault-item-name>"
    return 1
  fi
  bwss || return 1
  local id
  id="$(bw get item "$1" --session "$BW_SESSION" | jq -r '.id')" || return 1
  bw delete item "$id" --session "$BW_SESSION" || return 1
  >&2 echo "bwdd: '$1' moved to trash"
}

# ---------------------------------------------------------------------------
# bwunload <item-name> — unset every variable the item exports
# ---------------------------------------------------------------------------
bwunload() {
  if [[ -z "${1:-}" ]]; then
    >&2 echo "Usage: bwunload <vault-item-name>"
    return 1
  fi
  bwss || return 1
  local vars v
  vars="$(bw get notes "$1" --session "$BW_SESSION" \
    | sed -n 's/^export \([A-Za-z_][A-Za-z0-9_]*\)=.*/\1/p')"
  for v in $(printf '%s\n' "$vars"); do
    unset "$v"
  done
  >&2 echo "bwunload: unset vars from '$1'"
}

# ---------------------------------------------------------------------------
# bwdotenv <item-name> [output-file]
# Write the note as a plaintext NAME='value' .env file for tools that need one.
# WARNING: plaintext on disk. Delete it after use; never commit it.
# ---------------------------------------------------------------------------
bwdotenv() {
  if [[ -z "${1:-}" ]]; then
    >&2 echo "Usage: bwdotenv <vault-item-name> [output-file]"
    return 1
  fi
  bwss || return 1
  local out="${2:-.env}"
  (umask 077 && bw get notes "$1" --session "$BW_SESSION" | sed 's/^export //' > "$out") || return 1
  >&2 echo "bwdotenv: wrote '$out' — DELETE THIS FILE when done, never commit it"
}
