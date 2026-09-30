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

sr_sha256() ( # <file> -> hex digest
  set -o pipefail
  # Hash stdin so filename escaping (e.g. backslashes) cannot prefix the digest.
  if command -v sha256sum >/dev/null 2>&1; then sha256sum < "$1" | cut -d' ' -f1
  elif command -v shasum >/dev/null 2>&1; then shasum -a 256 < "$1" | cut -d' ' -f1
  else sr_die 2 "neither sha256sum nor shasum is available"; fi
)

# Where the SQL body starts, after the leading comment header (#366): the first line number that
# is not a blank line, a full-line `--` comment or part of a leading /* */ block. The body is then
# compared byte for byte, so any edit after the header (a comment edit included) is a change.
# Fails closed, keeping more of the file in the body, never less:
#   - a `-- @extract:` line ends the header (query-builder splits extracts on it); a header block
#     that mentions `@extract:` is kept in the body
#   - a header block with a nested /* is kept in the body (dialects disagree on nesting)
#   - code after a closing */ starts the body at that line
#   - a `--` line with text after a lone CR starts the body there: awk splits lines on LF only, but
#     databases and editors also break lines on CR, so that text may be code
#   - /*! and /*+ (MySQL executable comments, optimiser hints) are code, not header
#   - an unterminated header block: exit 3, so the caller treats the body as changed
sr_body_start() { # <file> -> line number (N+1 when the whole file is header)
  awk '
    function hstart(n) { start = n; done = 1; exit }
    # Scan line from position i with the current depth; returns when the line is consumed.
    function scan(line, i,    r) {
      while (1) {
        if (depth > 0) {
          r = substr(line, i)
          po = index(r, "/*"); pc = index(r, "*/")
          if (!po && !pc) return
          if (po && (!pc || po < pc)) { depth++; nested = 1; i += po + 1; continue }
          depth--; i += pc + 1
          if (depth == 0 && (nested || bad)) hstart(bstart)
          continue
        }
        r = substr(line, i); sub(/^[ \t\r]+/, "", r)
        if (r == "") return
        if (substr(r, 1, 3) == "/*!" || substr(r, 1, 3) == "/*+") hstart(NR)
        if (substr(r, 1, 2) == "/*") {
          bstart = NR; nested = 0; bad = (tolower(r) ~ /@extract:/); depth = 1
          i = length(line) - length(r) + 3; continue
        }
        if (substr(r, 1, 2) == "--" && tolower(r) !~ /^--[ \t]*@extract:/) {
          p = index(r, cr)
          if (p) { t = substr(r, p + 1); gsub(/[ \t]/, "", t); gsub(cr, "", t); if (t != "") hstart(NR) }
          return
        }
        hstart(NR)                      # code, or a -- @extract: marker: the body starts here
      }
    }
    BEGIN { depth = 0; done = 0; cr = sprintf("%c", 13) }
    {
      if (depth > 0 && tolower($0) ~ /@extract:/) bad = 1
      scan($0, 1)
    }
    END {
      if (done) print start
      else if (depth > 0) exit 3
      else print NR + 1
    }' "$1"
}
# SHA256 of the SQL body (tail from sr_body_start). Prints nothing and returns 1 on any failure
# (unterminated header, awk/tail/mktemp error): callers compare only two non-empty digests.
sr_body_sha256() { # <file> -> hex digest
  local n tmp sha
  n="$(sr_body_start "$1")" || return 1
  case "$n" in ""|*[!0-9]*) return 1 ;; esac
  tmp="$(mktemp)" || return 1
  if ! tail -n +"$n" "$1" > "$tmp"; then rm -f "$tmp"; return 1; fi
  sha="$( (sr_sha256 "$tmp") 2>/dev/null )"; rm -f "$tmp"
  case "$sha" in [0-9a-f]*) printf '%s\n' "$sha" ;; *) return 1 ;; esac
}
# True when both files' bodies are known and equal (a failure on either side counts as a change).
sr_body_same() { # <file> <file>
  local a b
  a="$(sr_body_sha256 "$1")" && b="$(sr_body_sha256 "$2")" && [ -n "$a" ] && [ "$a" = "$b" ]
}

# A body digest never authenticates a snapshot. If one exists its full hash must match the
# document before it can support a binding (including legacy records without a body hash).
sr_binding() { # <document> <current SQL> <optional baseline>; 0 full, 10 header-only, 1 changed
  local doc="$1" cur="$2" base="$3" full body current
  sr_no_symlinks "$base" || return 1
  full="$(jq -r '.sql_sha256 // ""' "$doc")"
  body="$(jq -r '.sql_body_sha256 // ""' "$doc")"
  if [ -f "$base" ]; then
    [ "$(sr_sha256 "$base")" = "$full" ] || return 1
    if [ -n "$body" ]; then [ "$(sr_body_sha256 "$base")" = "$body" ] || return 1; fi
  fi
  current="$(sr_sha256 "$cur")"
  if [ "$current" = "$full" ]; then
    if [ -n "$body" ]; then [ "$(sr_body_sha256 "$cur")" = "$body" ] || return 1; fi
    return 0
  fi
  if [ -n "$body" ]; then
    [ "$(sr_body_sha256 "$cur")" = "$body" ] && return 10
  elif [ -f "$base" ] && sr_body_same "$base" "$cur"; then return 10; fi
  return 1
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
    */scope.json)
      state="scoped"
      if jq -e '.sql_sha256 != null' "$doc" >/dev/null; then
        if [ ! -f "$SR_ROOT/$sql" ]; then state="missing"
        else
          local bound
          sr_binding "$doc" "$SR_ROOT/$sql" "$d/scope.source.sql"; bound=$?
          case "$bound" in 0) ;; 10) state="scoped-header-only" ;; *) state="stale" ;; esac
        fi
      fi ;;
    */lifts.json) state="lifts" ;;
    *)
      if [ ! -f "$SR_ROOT/$sql" ]; then state="missing"
      elif [ ! -f "$d/source.sql" ]; then state="no-baseline"
      elif [ -f "$d/rebind-required" ]; then state="stale"
      else
        local bound
        sr_binding "$doc" "$SR_ROOT/$sql" "$d/source.sql"; bound=$?
        case "$bound" in 0) state="current" ;; 10) state="header-only" ;; *) state="stale" ;; esac
      fi ;;
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
