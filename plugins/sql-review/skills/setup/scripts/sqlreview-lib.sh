#!/usr/bin/env bash
# Shared helpers for the sql-review plugin scripts (sourced by sqlreview.sh, not executed).
# Portable across macOS bash 3.2 and Linux bash 5: no associative arrays, no ${var,,}, no mapfile.
# Requires jq >= 1.6 for anything that reads or writes JSON.

SR_DIR=".sqlreview"
SR_SETUP_HINT="Run /sql-review:setup to initialise the project (creates $SR_DIR/ with config.json and templates/)."

sr_die() { # <exit-code> <message>
  local code="$1"; shift
  printf 'sqlreview: %s\n' "$*" >&2
  exit "$code"
}

sr_need_jq() {
  command -v jq >/dev/null 2>&1 || sr_die 2 "jq is required (jq >= 1.6): brew install jq / dnf install jq / apt install jq"
}

# Collapse "." and ".." segments and duplicate slashes in an absolute path, without touching the
# filesystem (the path may not exist yet — bootstrap names SQL that is still to be written).
sr_normpath() {
  printf '%s\n' "$1" | awk -F/ '{
    n = 0
    for (i = 1; i <= NF; i++) {
      if ($i == "" || $i == ".") continue
      if ($i == "..") { if (n > 0) n--; continue }
      parts[++n] = $i
    }
    out = ""
    for (i = 1; i <= n; i++) out = out "/" parts[i]
    if (out == "") out = "/"
    print out
  }'
}

# Absolute, normalised form of a path given on the command line (relative paths resolve
# against the current directory).
sr_abspath() {
  case "$1" in
    /*) sr_normpath "$1" ;;
    *)  sr_normpath "$(pwd -P)/$1" ;;
  esac
}

# The project root: $SQLREVIEW_ROOT when it holds .sqlreview/, else the nearest ancestor of the
# cwd that does. Prints nothing and returns 1 when the project is not initialised.
sr_find_root() {
  if [ -n "${SQLREVIEW_ROOT:-}" ]; then
    [ -d "$SQLREVIEW_ROOT/$SR_DIR" ] && { sr_normpath "$SQLREVIEW_ROOT"; return 0; }
    return 1
  fi
  local d
  d="$(pwd -P)"
  while :; do
    [ -d "$d/$SR_DIR" ] && { printf '%s\n' "$d"; return 0; }
    [ "$d" = "/" ] && return 1
    d="$(dirname "$d")"
  done
}

# Where init creates the tree when nothing exists yet: $SQLREVIEW_ROOT, the git top-level, or the cwd.
sr_init_root() {
  if [ -n "${SQLREVIEW_ROOT:-}" ]; then sr_normpath "$SQLREVIEW_ROOT"; return 0; fi
  sr_find_root && return 0
  git rev-parse --show-toplevel 2>/dev/null || pwd -P
}

sr_require_root() {
  SR_ROOT="$(sr_find_root)" || sr_die 3 "not initialised: no $SR_DIR/ found above $(pwd -P). $SR_SETUP_HINT"
  SR_REVIEWS="$SR_ROOT/$SR_DIR/reviews"
}

# Path relative to $SR_ROOT (dies when the path is outside the project).
sr_relpath() {
  local abs
  abs="$(sr_abspath "$1")"
  case "$abs" in
    "$SR_ROOT"/*) printf '%s\n' "${abs#"$SR_ROOT"/}" ;;
    *) sr_die 2 "$1 is outside the project root $SR_ROOT" ;;
  esac
}

# Slug for a project-relative path: extension dropped, "/" -> "__", other unsafe characters -> "-".
# reports/monthly.sql -> reports__monthly ; audits/monthly.sql -> audits__monthly (no collision).
sr_slug() {
  local rel="$1" base dir stem
  base="${rel##*/}"
  dir="${rel%"$base"}"
  case "$base" in
    *.*) stem="${base%.*}" ;;
    *)   stem="$base" ;;
  esac
  printf '%s%s\n' "$dir" "$stem" | sed -e 's|/|__|g' -e 's|[^A-Za-z0-9_.-]|-|g'
}

sr_sha256() { # <file> -> hex digest
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1
  elif command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | cut -d' ' -f1
  else sr_die 2 "neither sha256sum nor shasum is available"; fi
}

sr_now() { date -u +%Y-%m-%dT%H:%M:%SZ; }

# The authoritative document of a review directory: review.json, else scope.json, else nothing.
sr_doc_for() { # <slug> -> path
  local d="$SR_REVIEWS/$1"
  if [ -f "$d/review.json" ]; then printf '%s\n' "$d/review.json"
  elif [ -f "$d/scope.json" ]; then printf '%s\n' "$d/scope.json"
  else return 1; fi
}

# State of one review directory, from bytes on disk (never from git). Prints
# "<state>\t<sql_path>\t<revision>" so a caller can `IFS=$'\t' read -r state sql rev`.
#   scoped       scope.json only
#   missing      the SQL file is gone
#   no-baseline  review.json but no source.sql snapshot
#   stale        source.sql differs from the current SQL
#   current      identical
sr_state() { # <slug>
  local d="$SR_REVIEWS/$1" doc sql rev state
  doc="$(sr_doc_for "$1")" || { printf 'invalid\t\t\n'; return 0; }
  sql="$(jq -r '.sql_path // ""' "$doc" 2>/dev/null)"
  rev="$(jq -r '.revision // ""' "$doc" 2>/dev/null)"
  case "$doc" in
    */scope.json) state="scoped" ;;
    *)
      if [ ! -f "$SR_ROOT/$sql" ]; then state="missing"
      elif [ ! -f "$d/source.sql" ]; then state="no-baseline"
      elif cmp -s "$d/source.sql" "$SR_ROOT/$sql"; then state="current"
      else state="stale"; fi ;;
  esac
  printf '%s\t%s\t%s\n' "$state" "$sql" "$rev"
}
