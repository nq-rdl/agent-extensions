#!/usr/bin/env bash
# Shared helpers for the data-request plugin scripts (sourced by sqlreview.sh, not executed).
# Portable across macOS bash 3.2 and Linux bash 5: no associative arrays, no ${var,,}, no mapfile.
# Requires jq >= 1.6 for anything that reads or writes JSON.

SR_DIR=".sqlreview"
# Where the jq programs live (sqlreview.sh sets it before sourcing this file).
: "${SR_SCRIPT_DIR:=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)}"
SR_SETUP_HINT="Run /data-request:setup to initialise the project (creates $SR_DIR/ with config.json and templates/)."

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
  sr_no_symlinks "$SR_REVIEWS" || exit 2
}

# Path relative to $SR_ROOT (dies when the path is outside the project).
sr_relpath() {
  local abs
  case "$1" in /*) abs="$(sr_normpath "$1")" ;; *) abs="$(sr_normpath "$SR_ROOT/$1")" ;; esac
  sr_no_symlinks "$abs" || return 2
  case "$abs" in
    "$SR_ROOT"/*) printf '%s\n' "${abs#"$SR_ROOT"/}" ;;
    *) sr_die 2 "$1 is outside the project root $SR_ROOT" ;;
  esac
}

# Reject symlink components, including missing targets' existing ancestors.
sr_no_symlinks() {
  local p="$1"
  while [ "$p" != / ]; do
    [ ! -L "$p" ] || { printf 'sqlreview: symlink path refused: %s\n' "$p" >&2; return 2; }
    p="$(dirname "$p")"
  done
}
sr_safe_slug() {
  case "$1" in ""|.|..|*[!A-Za-z0-9_%.-]*) sr_die 2 "unsafe slug: $1" ;; esac
  sr_no_symlinks "$SR_REVIEWS/$1" || exit 2
}
sr_safe_sql() {
  case "$1" in ""|/*|*/../*|../*|*/..|..|./*|*/./*|*/.|*//*|*/) sr_die 2 "unsafe sql_path: $1" ;; esac
  sr_no_symlinks "$SR_ROOT/$1" || exit 2
}
# Both encodings of a path, readable then legacy, one per line. The definitions live in
# sqlreview-slug.jq, shared with check's slug/sql_path binding rule (#353).
sr_slug_pair() {
  jq -nr -L "$SR_SCRIPT_DIR" --arg p "$1" 'include "sqlreview-slug"; $p | path_slug, legacy_path_slug'
}
# The readable slug a path is (re)bound to: new reviews and move destinations.
sr_slug_new() {
  sr_slug_pair "$1" | sed -n 1p
}
# The slug of a path's review: the readable slug, unless only a legacy-encoded
# reviews/<legacy>/ exists, so reviews created before #353 keep working untouched.
sr_slug() {
  local pair new legacy
  pair="$(sr_slug_pair "$1")" || return 2
  new="$(printf '%s\n' "$pair" | sed -n 1p)"; legacy="$(printf '%s\n' "$pair" | sed -n 2p)"
  if [ "$new" != "$legacy" ] && [ -n "${SR_REVIEWS:-}" ] && [ ! -d "$SR_REVIEWS/$new" ] && [ -d "$SR_REVIEWS/$legacy" ]; then
    printf '%s\n' "$legacy"
  else
    printf '%s\n' "$new"
  fi
}

sr_sha256() { # <file> -> hex digest
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1
  elif command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | cut -d' ' -f1
  else sr_die 2 "neither sha256sum nor shasum is available"; fi
}

# The executable body of an SQL file (#366), to tell a comment-only change from an SQL change.
# Outside string literals and quoted identifiers ('...', "...", [...]) it drops `--` and /* */
# comments, collapses whitespace runs to one space and drops blank lines; CRLF counts as LF.
# Literal text is kept byte for byte, blank lines inside it too. Block comments do not nest, so a
# nested comment ends early and the rest is compared as code (stricter, never looser). A full-line
# `-- @extract:` marker is kept: query-builder splits extracts on it.
sr_sql_body() { # <file> -> normalised body on stdout
  awk '
    function sp() { if (out != "" && substr(out, length(out), 1) != " ") out = out " " }
    BEGIN { st = 0; q = sprintf("%c", 39) }   # st: 0 code, 1 quote, 2 double quote, 3 bracket, 4 block comment
    {
      line = $0; sub(/\r$/, "", line)
      if (st == 0 && line ~ /^[ \t]*--[ \t]*@extract:/) { sub(/^[ \t]+/, "", line); sub(/[ \t]+$/, "", line); print line; next }
      out = ""; lit = (st >= 1 && st <= 3); n = length(line); i = 1
      while (i <= n) {
        c = substr(line, i, 1); c2 = substr(line, i, 2)
        if (st == 4) { if (c2 == "*/") { st = 0; sp(); i += 2 } else i++; continue }
        if (st == 1) { out = out c; if (c == q) st = 0; i++; continue }
        if (st == 2) { out = out c; if (c == "\"") st = 0; i++; continue }
        if (st == 3) { out = out c; if (c == "]") st = 0; i++; continue }
        if (c2 == "--") break
        if (c2 == "/*") { st = 4; sp(); i += 2; continue }
        if (c == " " || c == "\t") { sp(); i++; continue }
        if (c == q) st = 1; else if (c == "\"") st = 2; else if (c == "[") st = 3
        out = out c; i++
      }
      if (st == 0 || st == 4) { sub(/ $/, "", out); if (out == "" && !lit) next }
      print out
    }' "$1"
}
sr_body_sha256() { # <file> -> hex digest of sr_sql_body
  local tmp sha
  tmp="$(mktemp)" || sr_die 2 "mktemp failed"
  sr_sql_body "$1" > "$tmp" || { rm -f "$tmp"; sr_die 2 "cannot read $1"; }
  sha="$(sr_sha256 "$tmp")"; rm -f "$tmp"
  printf '%s\n' "$sha"
}

sr_now() { date -u +%Y-%m-%dT%H:%M:%SZ; }

# The authoritative document of a review directory: review.json, else scope.json, else nothing.
sr_doc_for() { # <slug> -> path
  sr_safe_slug "$1"
  local d="$SR_REVIEWS/$1"
  sr_no_symlinks "$d/review.json" || exit 2
  sr_no_symlinks "$d/scope.json" || exit 2
  if [ -f "$d/review.json" ]; then printf '%s\n' "$d/review.json"
  elif [ -f "$d/scope.json" ]; then printf '%s\n' "$d/scope.json"
  elif [ -f "$d/lifts.json" ]; then sr_no_symlinks "$d/lifts.json" || exit 2; printf '%s\n' "$d/lifts.json"
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
  sr_safe_slug "$1"
  local d="$SR_REVIEWS/$1" doc sql rev state
  doc="$(sr_doc_for "$1")" || {
    if [ -f "$d/review.draft.json" ] || [ -f "$d/scope.draft.json" ]; then printf 'draft\t\t\n'; else printf 'invalid\t\t\n'; fi
    return 0
  }
  sr_no_symlinks "$d/source.sql" || exit 2
  cmd_check "$doc" >/dev/null || { printf 'invalid\t\t\n'; return 0; }
  sql="$(jq -r '.sql_path // ""' "$doc" 2>/dev/null)"
  sr_safe_sql "$sql"
  rev="$(jq -r '.revision // ""' "$doc" 2>/dev/null)"
  case "$doc" in
    */scope.json) state="scoped" ;;
    */lifts.json) state="lifts" ;;
    *)
      if [ ! -f "$SR_ROOT/$sql" ]; then state="missing"
      elif [ ! -f "$d/source.sql" ]; then state="no-baseline"
      elif [ -f "$d/rebind-required" ]; then state="stale"
      elif [ "$(sr_sha256 "$d/source.sql")" != "$(jq -r .sql_sha256 "$doc")" ]; then state="stale"
      elif cmp -s "$d/source.sql" "$SR_ROOT/$sql"; then state="current"
      else state="stale"; fi ;;
  esac
  printf '%s\t%s\t%s\n' "$state" "$sql" "$rev"
}

# Why a review is invalid or missing, on one line (empty otherwise). Kept apart from sr_state:
# tab-separated reads collapse empty fields, and invalid rows have no sql_path or revision.
sr_state_reason() { # <slug> <state>
  local slug="$1" d="$SR_REVIEWS/$1" doc violations schema sql why=""
  case "$2" in
    invalid)
      doc="$(sr_doc_for "$slug")" || { printf 'no review.json, scope.json or lifts.json\n'; return 0; }
      violations="$(cmd_check "$doc" 2>&1 | grep -v '^ok$' | tr '\n' ';' | sed 's/;$//; s/;/; /g')"
      why="$(basename "$doc"): $violations"
      schema="$(jq -r '.schemaVersion // "missing" | tostring' "$doc" 2>/dev/null || echo unreadable)"
      why="$why; schemaVersion $schema"
      sql="$(jq -r '.sql_path // "" | strings' "$doc" 2>/dev/null || true)"
      if [ -n "$sql" ]; then
        case "$sql" in /*|*..*) why="$why; sql_path '$sql' is not project-relative" ;; *)
          [ -f "$SR_ROOT/$sql" ] || why="$why; sql_path target missing: $sql" ;;
        esac
      fi
      case "$violations" in *"binding mismatch"*)
        why="$why; the slug is not derived from any current path — rebind with: sqlreview.sh move --slug $slug <sql path>" ;;
      esac ;;
    missing)
      sql="$(jq -r '.sql_path // ""' "$(sr_doc_for "$slug")" 2>/dev/null)"
      why="sql_path target missing: $sql — if it moved, run: sqlreview.sh move '$sql' <new path>" ;;
  esac
  printf '%s\n' "$why"
}
