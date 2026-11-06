#!/usr/bin/env bash
# Shared helpers for the data-request plugin scripts (sourced by sqlreview.sh, not executed).
# Portable across macOS bash 3.2 and Linux bash 5: no associative arrays, no ${var,,}, no mapfile.
# Requires jq >= 1.6 for anything that reads or writes JSON.

SR_DIR=".sqlreview"
# Where the jq programs live (sqlreview.sh sets it before sourcing this file).
: "${SR_SCRIPT_DIR:=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)}"
# Field separators for the IFS of a read, set once: a command substitution in a loop costs a fork per review.
SR_TAB="$(printf '\t')"
SR_US="$(printf '\037')"
# Printed in place of a stored sql_path that holds characters beyond letters, digits and _ . / -.
# SR_UNSAFE_RULE is the end of check's message for that rule.
SR_UNSAFE='(unsafe sql_path)'
SR_UNSAFE_RULE='sql_path must not contain quotes'
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
  # Split only on slashes: line-oriented tools rewrite newline-containing names,
  # and awk -v would also interpret backslash escapes in the path.
  local rest="$1" part out=""
  while :; do
    part="${rest%%/*}"
    case "$part" in
      ""|.) ;;
      ..) out="${out%/*}" ;;
      *) out="$out/$part" ;;
    esac
    [ "$rest" != "$part" ] || break
    rest="${rest#*/}"
  done
  printf '%s\n' "${out:-/}"
}

# Absolute, normalised form of a path given on the command line (relative paths resolve
# against the current directory).
sr_abspath() {
  local here
  case "$1" in
    /*) sr_normpath "$1" ;;
    *)  here="$(pwd -P)"; sr_normpath "$here/$1" ;;
  esac
}

# The project root: $SQLREVIEW_ROOT when it holds .sqlreview/, else the nearest ancestor of the
# cwd that does. Prints nothing and returns 1 when the project is not initialised.
sr_find_root() {
  if [ -n "${SQLREVIEW_ROOT:-}" ]; then
    [ -d "$SQLREVIEW_ROOT/$SR_DIR" ] && { sr_abspath "$SQLREVIEW_ROOT"; return 0; }
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
  if [ -n "${SQLREVIEW_ROOT:-}" ]; then sr_abspath "$SQLREVIEW_ROOT"; return 0; fi
  sr_find_root && return 0
  git rev-parse --show-toplevel 2>/dev/null || pwd -P
}

sr_require_root() {
  local here
  SR_ROOT="$(sr_find_root)" || { here="$(pwd -P)"; sr_die 3 "not initialised: no $SR_DIR/ found above $here. $SR_SETUP_HINT"; }
  SR_REVIEWS="$SR_ROOT/$SR_DIR/reviews"
  sr_no_symlinks "$SR_REVIEWS" || exit 2
}

# Path relative to $SR_ROOT (dies when the path is outside the project). The reviewed-tree rule
# applies unless the second argument is "nopolicy": move names a record's old path only to find it.
sr_relpath() {
  local abs
  case "$1" in /*) abs="$(sr_normpath "$1")" ;; *) abs="$(sr_normpath "$SR_ROOT/$1")" ;; esac
  # Checked on the path as given, not the folded one: "link/.." means different things to the two.
  if [ "${2:-}" != nopolicy ]; then
    case "$1" in /*) sr_refuse_unreviewed "$1" "$1" || return 2 ;; *) sr_refuse_unreviewed "$SR_ROOT/$1" "$1" || return 2 ;; esac
  fi
  # sr_refuse_unreviewed applies the same fold-versus-resolution check to every policy path. move's old path
  # skips the policy, but its folded form is the record key, so it gets the check here.
  if [ "${2:-}" = nopolicy ]; then
    local raw physraw physabs
    case "$1" in /*) raw="$1" ;; *) raw="$SR_ROOT/$1" ;; esac
    physraw="$(sr_realpath_m "$raw")" && physabs="$(sr_realpath_m "$abs")" ||
      sr_die 2 "refused path: the path cannot be resolved, so it cannot be checked (fail closed)"
    [ "$physraw" = "$physabs" ] ||
      sr_die 2 "refused path: a .. component follows a symbolic link, so the path names different files before and after resolution (rule: no .. after a symlink)"
  fi
  sr_no_symlinks "$abs" || return 2
  case "$abs" in
    "$SR_ROOT"/*) printf '%s\n' "${abs#"$SR_ROOT"/}" ;;
    *) sr_die 2 "$1 is outside the project root $SR_ROOT" ;;
  esac
}

# Reject symlink components, including missing targets' existing ancestors. Walks up with
# parameter expansion, not dirname: status calls this many times per review, inside a 5-second hook.
sr_no_symlinks() {
  local p="$1"
  while [ "$p" != / ] && [ "$p" != . ]; do
    [ ! -L "$p" ] || { printf 'sqlreview: symlink path refused: %s\n' "$p" >&2; return 2; }
    # dirname: drop trailing slashes, then the last component ("a" -> ".", "/a" -> "/").
    while :; do case "$p" in ?*/) p="${p%/}" ;; *) break ;; esac; done
    case "$p" in */*) p="${p%/*}" ;; *) p=. ;; esac
    while :; do case "$p" in ?*/) p="${p%/}" ;; *) break ;; esac; done
    p="${p:-/}"
  done
}
sr_safe_slug() {
  case "$1" in ""|.|..|*[!A-Za-z0-9_%.-]*) sr_die 2 "unsafe slug: $1" ;; esac
  sr_no_symlinks "$SR_REVIEWS/$1" || exit 2
}
# Physical form of an absolute path: every symlink resolved, "." and ".." applied after resolution
# (like realpath -m, which macOS lacks). The path may be missing; its missing tail is kept as
# written. Returns 1 when it cannot be resolved (loop, unreadable link), so callers fail closed.
sr_realpath_m() {
  local rest="$1" cur="" hops=0 part cand target
  case "$rest" in /*) rest="${rest#/}" ;; *) return 1 ;; esac
  while [ -n "$rest" ]; do
    case "$rest" in */*) part="${rest%%/*}"; rest="${rest#*/}" ;; *) part="$rest"; rest="" ;; esac
    case "$part" in
      ""|.) continue ;;
      ..) cur="${cur%/*}"; continue ;;
    esac
    cand="$cur/$part"
    if [ -L "$cand" ]; then
      hops=$((hops + 1)); [ "$hops" -le 40 ] || return 1
      # Sentinel keeps a trailing newline in the link text; a control character fails closed.
      target="$(readlink "$cand"; printf x)" || return 1
      target="${target%x}"; target="${target%$'\n'}"
      case "$target" in ""|*[[:cntrl:]]*) return 1 ;; esac
      case "$target" in
        /*) cur=""; rest="${target#/}${rest:+/$rest}" ;;
        *) rest="$target${rest:+/$rest}" ;;
      esac
    else
      cur="$cand"
    fi
  done
  printf '%s\n' "${cur:-/}"
}

# Absolute form of a path as the OS will open it: relative to the cwd, "." and ".." left for
# sr_realpath_m to apply after symlink resolution (sr_abspath would fold ".." lexically first, so
# sql/v1/link/../x.csv would be checked as sql/v1/x.csv while the kernel opens link's parent).
sr_rawabs() {
  local d
  case "$1" in
    /*) printf '%s\n' "$1" ;;
    *) d="$(pwd -P; printf x)"; d="${d%x}"; printf '%s/%s\n' "${d%$'\n'}" "$1" ;;
  esac
}

# Which files may be read into .sqlreview/ (#516). Researcher-supplied values live under data/ and
# in pipeline SQL under sql/<name>/, so only a reviewed sql/v<N>/ tree (the scaffold's rule:
# v[0-9]+([.-][0-9]+)*) may be copied, hashed or parsed into the committed review records.
# Checked on the canonical path (symlinks and ".." resolved against the project root), so a
# link or a ".." cannot lead a reviewed-looking path into data/ or sql/<name>/. Fails closed when
# the path cannot be resolved. Messages name the rule, never the path or file content (no-echo).
# Hard-link count of a file, portably (GNU stat -c, BSD stat -f). Fails when it cannot be read.
sr_nlink() { # FILE
  local n
  n="$(stat -c %h "$1" 2>/dev/null)" || n="$(stat -f %l "$1" 2>/dev/null)" || return 1
  case "$n" in ""|*[!0-9]*) return 1 ;; esac
  printf '%s\n' "$n"
}

# A render the helper itself wrote (materialize, the header-evidence check and the release criteria sidecar) carries FILE.sqlreview-render
# with the file's SHA-256. notes and intake accept an outside-project file only with a matching marker, so a
# directory or file made by hand under any name is refused. Not a defence against a hostile
# same-user process, which could write the marker too.
sr_helper_render_marker() { # FILE
  [ -f "$1" ] && [ ! -L "$1" ] && [ -f "$1.sqlreview-render" ] && [ ! -L "$1.sqlreview-render" ] || return 1
  [ "$(cat "$1.sqlreview-render" 2>/dev/null)" = "$(sr_sha256 "$1" 2>/dev/null)" ]
}

# Write FILE.sqlreview-render. Never write through an existing marker: a symlink or hard link there would
# make a plain redirection overwrite the linked file. Refuse a symlink, stage a fresh file beside the
# marker and rename it over the target, which replaces the directory entry and leaves the old inode alone.
sr_write_render_marker() { # FILE
  local marker="$1.sqlreview-render" staged
  [ ! -L "$marker" ] || { printf 'sqlreview: symlink path refused for the render marker\n' >&2; return 2; }
  [ ! -e "$marker" ] || [ -f "$marker" ] || return 2
  staged="$(umask 077; mktemp "$marker.XXXXXX")" || return 2
  if sr_sha256 "$1" > "$staged" && mv -f "$staged" "$marker"; then return 0; fi
  rm -f "$staged"; return 2
}

# The data/ and sql/ rules for a physical path PHYS inside the initialised project ROOT (both already resolved).
sr_policy_under() { # ROOT PHYS
  local rel first second re='^v[0-9]+([.-][0-9]+)*$'
  rel="${2#"$1"/}"
  first="${rel%%/*}"
  case "$rel" in */*) second="${rel#*/}"; second="${second%%/*}" ;; *) second="" ;; esac
  first="$(printf '%s' "$first" | tr '[:upper:]' '[:lower:]')"
  case "$first" in
    data)
      sr_die 2 "refused path: data/ holds researcher-supplied values and is never read into $SR_DIR/ (rule: no data/ paths)" ;;
    sql)
      [[ "$second" =~ $re ]] ||
        sr_die 2 "refused path: only a reviewed version directory sql/v<N>/ may be read into $SR_DIR/; pipeline SQL under sql/<name>/ may hold cohort values (rule: sql/ paths must be inside sql/v[0-9]+([.-][0-9]+)*/)" ;;
  esac
}

# Nearest initialised project above a physical path, from the path's own location and not from the cwd.
# Prints nothing and returns 1 when no directory above it holds .sqlreview/.
sr_root_of_path() { # PHYS
  local d="${1%/*}"
  while [ -n "$d" ]; do
    [ ! -d "$d/$SR_DIR" ] || { printf '%s\n' "$d"; return 0; }
    d="${d%/*}"
  done
  return 1
}

sr_refuse_unreviewed() { # ABS_PATH AS_GIVEN [helper-render|outside-ok]
  local root phys links d
  # First, before any canonicalisation: command substitution strips trailing newlines, so a name
  # such as "alias.sql<LF>" would be checked as a different path from the one opened. Refuse
  # newline, CR, tab and every other control character outright (fail closed).
  case "$1$2${SR_ROOT:-}" in
    *[[:cntrl:]]*) sr_die 2 "refused path: it contains a control character such as a newline, carriage return or tab (rule: no control characters in paths)" ;;
  esac
  [ -n "${SR_ROOT:-}" ] || sr_die 2 "refused path: the project root is unknown, so the path cannot be checked (fail closed)"
  root="$(sr_realpath_m "$SR_ROOT")" && phys="$(sr_realpath_m "$1")" ||
    sr_die 2 "refused path: the path cannot be resolved, so it cannot be checked (fail closed)"
  # Every initialised project above the file applies its own data/ and sql/ rules to it, whatever the cwd or
  # SQLREVIEW_ROOT says: a file in another project, or a nested one, is judged by that project too.
  d="${phys%/*}"
  while [ -n "$d" ]; do
    if [ "$d" != "$root" ] && [ -d "$d/$SR_DIR" ]; then sr_policy_under "$d" "$phys"; fi
    d="${d%/*}"
  done
  case "$phys" in
    "$root"/*) sr_policy_under "$root" "$phys" ;;
    *)
      # notes and intake pass "helper-render": the documented flows run them on a render the helper wrote.
      [ "${3:-}" = helper-render ] && sr_helper_render_marker "$phys" && return 0
      # amend-check prints rule lines only, so a record file outside the project may be checked there.
      [ "${3:-}" = outside-ok ] && return 0
      sr_die 2 "refused path: it resolves outside the project root; copy it into sql/v<N>/ first (rule: no paths that leave the project)" ;;
  esac
  # The kernel opens the path as given, but callers fold ".." lexically (sr_relpath, sr_abspath) and then use the
  # folded form. If a symlink makes the two differ, the folded path names a file this policy never judged.
  [ "$(sr_realpath_m "$(sr_normpath "$1")")" = "$phys" ] ||
    sr_die 2 "refused path: a .. component follows a symbolic link, so the path names different files before and after resolution (rule: no .. after a symlink)"
  # A hard link shares the inode of a file the path rules never see (a data/ file linked into sql/v1/).
  if [ -f "$phys" ]; then
    links="$(sr_nlink "$phys")" || sr_die 2 "refused path: its hard-link count cannot be read, so it cannot be checked (fail closed)"
    [ "$links" -le 1 ] || sr_die 2 "refused path: the file has $links hard links, and one may be under data/ (rule: no hard-linked files)"
  fi
}

# THE entry point for any user-supplied path whose content a command reads, copies, hashes into a
# record or prints (#516): the full policy (data/, unreviewed sql/, outside the project root unless
# a helper-marked render is allowed, symlink target, hard-link count), exiting 2 when refused.
# Every subcommand's file arguments go through here, either as sr_guard_input at the dispatch
# (tests/test_sql_review_path_guard.py runs every command on a refused path and fails on an unlisted
# command). A command that copies or reads the file later does not guard it a second time.
# MODE is helper-render (accept an outside-project file that carries a helper marker) or outside-ok (accept any
# file outside the project, but never data/ or unreviewed sql/ inside it).
# With no initialised .sqlreview/ from the cwd, the project is discovered from the file itself: the nearest
# initialised directory above its physical path governs it, so an alias into data/ is refused as data/.
# With no project above the file either, a path that has a data or sql directory in its spelling or in its
# physical form is refused (fail closed). Other paths, such as a scratch file in a temporary directory,
# are checked against the git top level or the cwd.
sr_guard_input() { # PATH [helper-render|outside-ok]
  local low phys
  if [ -z "${SR_ROOT:-}" ]; then
    if ! SR_ROOT="$(sr_find_root 2>/dev/null)"; then
      SR_ROOT=""
      low="$(printf '/%s/' "$(sr_rawabs "$1")" | tr '[:upper:]' '[:lower:]')"
      case "$low" in
        *[[:cntrl:]]*) sr_die 2 "refused path: it contains a control character such as a newline, carriage return or tab (rule: no control characters in paths)" ;;
      esac
      phys="$(sr_realpath_m "$(sr_rawabs "$1")")" ||
        sr_die 2 "refused path: the path cannot be resolved, so it cannot be checked (fail closed)"
      if SR_ROOT="$(sr_root_of_path "$phys")"; then :
      else
        SR_ROOT=""
        low="$low$(printf '/%s/' "$phys" | tr '[:upper:]' '[:lower:]')"
        case "$low" in
          */data/*|*/sql/*) sr_die 2 "refused path: no initialised $SR_DIR/ project is found from here or above the file and the path is under a data or sql directory, so it cannot be checked (fail closed)" ;;
        esac
        SR_ROOT="$(sr_init_root)"
      fi
    fi
  fi
  sr_refuse_unreviewed "$(sr_rawabs "$1")" "$1" "${2:-}" || exit 2
}

# True when a stored path holds only letters, digits and _ . / - (the rule of check for sql_path).
# A bash case with the characters spelled out, so it starts no process and does not depend on the locale.
# Status and the next-command hints print a path only when this holds.
sr_path_printable() { # <path>
  case "$1" in ''|*[!ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_./-]*) return 1 ;; esac
  return 0
}

# Structural checks on a stored or derived project-relative path (no policy; see sr_safe_sql).
sr_safe_path() {
  case "$1" in ""|/*|*/../*|../*|*/..|..|./*|*/./*|*/.|*//*|*/) sr_die 2 "unsafe sql_path" ;; esac
  sr_no_symlinks "$SR_ROOT/$1" || exit 2
}
# A SQL path about to be read into .sqlreview/: the structural checks first (a no-echo "unsafe sql_path"), then the reviewed-tree rule.
sr_safe_sql() {
  sr_safe_path "$1"
  case "$1" in /*) sr_refuse_unreviewed "$1" "$1" ;; *) sr_refuse_unreviewed "$SR_ROOT/$1" "$1" ;; esac || exit 2
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
  # Hash stdin so filename escaping (e.g. backslashes) cannot prefix the digest. A brace body and
  # ${h%% *}, not a subshell and cut: status hashes several files per review.
  local h
  if command -v sha256sum >/dev/null 2>&1; then h="$(sha256sum < "$1")" || return $?
  elif command -v shasum >/dev/null 2>&1; then h="$(shasum -a 256 < "$1")" || return $?
  else sr_die 2 "neither sha256sum nor shasum is available"; fi
  printf '%s\n' "${h%% *}"
}

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
# (unterminated header, awk/tail/hash error): callers compare only two non-empty digests.
sr_body_sha256() { # <file> -> hex digest
  local n sha
  n="$(sr_body_start "$1")" || return 1
  case "$n" in ""|*[!0-9]*) return 1 ;; esac
  # A pipe, not a temporary file: status hashes several bodies per review.
  sha="$( (set -o pipefail; tail -n +"$n" "$1" | sr_sha256 /dev/stdin) 2>/dev/null )" || return 1
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
  IFS="$SR_US" read -r full body <<EOF
$(jq -r '[(.sql_sha256 // "" | tostring), (.sql_body_sha256 // "" | tostring)] | join("\u001f")' "$doc")
EOF
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

. "$SR_SCRIPT_DIR/sqlreview-source.sh"

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

# State of one review directory, from the recorded hashes and the SQL on disk. It never runs
# git: old SQL is read only where a diff, carry or release check needs it. Prints
# "<state>\t<sql_path>\t<revision>", which a caller splits on the tab (SR_TAB) with read -r.
#   scoped       scope.json only
#   missing      the SQL file is gone
#   no-baseline  review.json without a clean recorded git_commit, so old SQL cannot be read
#   stale        the SQL differs from the recorded sql_sha256
#   current      identical
sr_state() { # <slug>
  sr_safe_slug "$1"
  local d="$SR_REVIEWS/$1" doc sql rev state kind sha authentic bound
  doc="$(sr_doc_for "$1")" || {
    if [ -f "$d/review.draft.json" ] || [ -f "$d/scope.draft.json" ]; then printf 'draft\t\t\n'; else printf 'invalid\t\t\n'; fi
    return 0
  }
  cmd_check "$doc" >/dev/null || {
    # A record whose sql_path holds unsafe characters reports a fixed text in place of the path, so the next
    # command and the session-start context never repeat it. Only an invalid record pays for the second check.
    case "$(cmd_check "$doc" 2>/dev/null)" in
      *"$SR_UNSAFE_RULE"*) printf 'invalid\t%s\t\n' "$SR_UNSAFE" ;;
      *) printf 'invalid\t\t\n' ;;
    esac
    return 0
  }
  # One jq call for five fields. \037 is not IFS whitespace, so an empty field stays in place.
  IFS="$SR_US" read -r kind sql rev sha authentic <<EOF
$(jq -r '[(.kind | tostring), (.sql_path // "" | tostring), (.revision // "" | tostring), (.sql_sha256 != null | tostring),
  (((.git_commit | type == "string" and test("^[0-9a-f]{40}$|^[0-9a-f]{64}$")) and
    (.git_dirty == null or .git_dirty == false)) | tostring)] | join("\u001f")' "$doc" 2>/dev/null)
EOF
  if [ "$kind" != lifts ]; then
    # The question store must load, as `sqlreview.sh questions` loads it. In a subshell, not a child
    # bash, which would read sqlreview.sh again per review. Its review filter keeps every question.
    # Structural path checks only: the input policy applies to what is read, and status reads nothing new.
    ( SR_Q_STRUCTURAL=1; _q_context "$1" ) >/dev/null 2>&1 || { printf 'invalid\t\t\n'; return 0; }
  fi
  sr_safe_path "$sql"
  case "$kind" in
    scope)
      state="scoped"
      if [ "$sha" = true ]; then
        if [ ! -f "$SR_ROOT/$sql" ]; then state="missing"
        else
          sr_binding "$doc" "$SR_ROOT/$sql" /dev/null; bound=$?
          case "$bound" in 0) ;; 10) state="scoped-header-only" ;; *) state="stale" ;; esac
        fi
      fi ;;
    lifts) state="lifts" ;;
    *)
      if [ ! -f "$SR_ROOT/$sql" ]; then state="missing"
      elif [ "$authentic" != true ]; then state="no-baseline"
      elif [ -f "$d/rebind-required" ]; then state="stale"
      else
        sr_binding "$doc" "$SR_ROOT/$sql" /dev/null; bound=$?
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
      if [ -z "$violations" ] && [ "$(jq -r .kind "$doc")" != lifts ]; then
        violations="$(bash "$SR_SCRIPT_DIR/sqlreview.sh" questions "$slug" 2>&1 >/dev/null | tr '\n' ';' | sed 's/;$//')"
      fi
      why="$(basename "$doc"): $violations"
      # No-echo: only a known schema version prints. Any other value prints as its rule.
      schema="$(jq -r 'if .schemaVersion == 1 or .schemaVersion == 2 then .schemaVersion
        elif has("schemaVersion") then "invalid" else "missing" end | tostring' "$doc" 2>/dev/null || echo unreadable)"
      why="$why; schemaVersion $schema"
      sql="$(jq -r '.sql_path // "" | strings' "$doc" 2>/dev/null || true)"
      if [ -n "$sql" ]; then
        case "$sql" in
          /*|*..*) why="$why; unsafe sql_path (not project-relative)" ;;
          *) if sr_path_printable "$sql"; then [ -f "$SR_ROOT/$sql" ] || why="$why; sql_path target missing"
             else why="$why; (unsafe sql_path)"; fi ;;
        esac
      fi
      case "$violations" in *"binding mismatch"*)
        why="$why; the slug is not derived from any current path — rebind with: sqlreview.sh move --slug $slug <sql path>" ;;
      esac ;;
    no-baseline)
      why="the review records no clean git_commit, so its SQL cannot be read from git — reassess with /data-request:analyse --update" ;;
    missing)
      sql="$(jq -r '.sql_path // ""' "$(sr_doc_for "$slug")" 2>/dev/null)"
      # A record that check refuses never reaches this state. The test is a second layer: the path is
      # free text, so it prints only when it holds safe characters only.
      if sr_path_printable "$sql"; then
        why="sql_path target missing: $sql — if it moved, run: sqlreview.sh move '$sql' <new path>"
      else why="sql_path target missing: $SR_UNSAFE"; fi ;;
  esac
  printf '%s\n' "$why"
}

# A private scratch directory under TMPDIR, printed as its physical path. TMPDIR is often
# reached through a symlink (macOS /var/folders and /tmp), and paths built from this one go
# through sr_no_symlinks, which must refuse only caller-supplied links, not this one.
sr_private_tmpdir() { # PREFIX
  local dir
  dir="$(mktemp -d "${TMPDIR:-/tmp}/$1.XXXXXX")" || return 1
  (cd "$dir" && pwd -P) || {
    rm -rf -- "$dir"
    return 1
  }
}

# Private consumer inputs must never live within the repository, even with a local TMPDIR.
sr_source_workspace() (
  sr_source_context || exit 2
  umask 077
  local work
  work="$(sr_private_tmpdir sqlreview-inputs)" || exit 2
  case "$work" in "$SR_SOURCE_TOP"|"$SR_SOURCE_TOP"/*)
    rm -rf "$work"; sr_source_error "temporary inputs must be outside the git tree"; exit 2 ;;
  esac
  printf '%s\n' "$work"
)

# Uncommitted source paths (untracked, modified or staged), one per line between newlines, and
# their count. Fingerprint and a bound publish refuse ANY uncommitted source in the git tree
# (sr_source_clean), not only the reviewed SQL, so the next command names a commit first whenever
# this list is not empty. The exemptions are sr_source_clean's: review records under the store.
# cmd_status sets both once per run with ONE git call, before its loop over the reviews. Paths are
# relative to $SR_ROOT (outside it they start ../). Empty when git or the repository is unavailable:
# then no commit is named.
SR_NL='
'
sr_load_uncommitted() {
  local line p
  SR_UNCOMMITTED="$SR_NL"; SR_UNCOMMITTED_N=0
  command -v git >/dev/null 2>&1 || return 0
  while IFS= read -r line; do
    p="${line#???}"
    # A quoted path (one with a space) loses its quotes. A path that git escapes does not match
    # a SQL path, but still counts as an uncommitted source.
    case "$p" in \"*\") p="${p#\"}"; p="${p%\"}" ;; esac
    case "$p" in
      ''|"$SR_DIR"/reviews/*|"$SR_DIR"/releases/*|"$SR_DIR"/amendments/*|"$SR_DIR"/templates/*|"$SR_DIR"/ledger.json|"$SR_DIR"/.gitignore) ;;
      *) SR_UNCOMMITTED="$SR_UNCOMMITTED$p$SR_NL"; SR_UNCOMMITTED_N=$((SR_UNCOMMITTED_N + 1)) ;;
    esac
  done <<EOF
$(git --no-optional-locks -C "$SR_ROOT" -c core.quotePath=false -c status.relativePaths=true -c color.status=false \
    status --short --untracked-files=all --no-renames -- ':/' 2>/dev/null)
EOF
}
sr_uncommitted() { # <sql_path>: true when the run's git status lists it
  case "${SR_UNCOMMITTED-}" in *"$SR_NL$1$SR_NL"*) return 0 ;; esac
  return 1
}
# The commit prerequisite for a step that fingerprints or binds <sql_path>, or nothing.
sr_commit_first() { # <sql_path>
  [ "${SR_UNCOMMITTED_N:-0}" -gt 0 ] || return 0
  if [ -f "$SR_ROOT/$1" ] && sr_uncommitted "$1"; then
    if [ "$SR_UNCOMMITTED_N" -gt 1 ]; then printf 'commit %s and the other uncommitted source changes (git status), then ' "$1"
    else printf 'commit %s, then ' "$1"; fi
  else printf 'commit the uncommitted source changes (git status), then '; fi
}

# The next command for one review directory, on one line (#514). Derived only from records that
# already exist: the state, scope.json and its recorded SQL binding (sql_sha256), the root answers.intake.json
# and explain.json. A bound scope whose SQL body moved on, whose imported analyst decisions no
# longer match the sidecar, or (for the scope that carries criteria_status) whose research criteria
# moved on, names bootstrap as the rescope step. Cheap: a few jq and hash calls,
# because status runs from a SessionStart hook with a 5-second timeout.
sr_next() { # <slug> <state> <sql_path>
  local d="$SR_REVIEWS/$1" state="$2" sql="$3" scope srev="" bound="" intake="" why="" gap="" follow="" ex pre=""
  # The path is free text from the record. A hint that names it is a paste-ready command, so an unsafe
  # path (anything beyond letters, digits and _ . / -) gets a fixed text and no command.
  if [ "$sql" = "$SR_UNSAFE" ] || { [ -n "$sql" ] && ! sr_path_printable "$sql"; }; then
    case "$state" in draft|lifts) ;; *)
      printf '%s repair the record, then run sqlreview.sh status --verbose\n' "$SR_UNSAFE"; return 0 ;;
    esac
  fi
  case "$state" in
    draft)
      if [ -f "$d/scope.draft.json" ]; then printf 'resume /data-request:bootstrap to finish the scope draft\n'
      else printf 'resume /data-request:analyse to finish the review draft\n'; fi
      return 0 ;;
    invalid) printf 'run sqlreview.sh status --verbose to see why, then repair the documents\n'; return 0 ;;
    lifts) printf '/data-request:lift to close out the lift ledger\n'; return 0 ;;
    missing) printf "sqlreview.sh move '%s' <new path> if the SQL moved\n" "$sql"; return 0 ;;
  esac
  scope="$d/scope.json"
  if [ -f "$scope" ]; then
    local sidecar="$SR_ROOT/answers.intake.json" prog='
      def mine: [.assumptions[]? | select(.upstream.source? == "analyst-intake")
                 | {id, text, rationale, confirmed_by, confirmed_at, decided}] | sort_by(.id);
      def theirs: [.decisions[] | {id: ("A-intake-" + .id), text, rationale, confirmed_by, confirmed_at, decided}] | sort_by(.id);
      # Only the scope that owns the criteria (it carries criteria_status) tracks them. It is behind
      # when a live criterion has no row, a withdrawn one keeps its row, or a criterion was
      # re-confirmed (reworded, or applied_by changed) after the scope revision was recorded. The
      # time test runs only on UTC "Z" stamps, compared to the second, so another format is no signal.
      def utc: if type == "string" and test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\\.[0-9]+)?Z$")
               then .[0:19] else null end;
      def criteria_moved($doc):
        ($doc | has("criteria_status")) and ((.criteria | type) == "array")
        and ([.criteria[] | select(.withdrawn == null)] as $live | ($doc.recorded_at | utc) as $at
             | ([$live[].id] | sort) != ([$doc.criteria_status[]? | .criterion] | sort)
               or ($at != null and any($live[]; (.confirmed_at | utc) as $c | $c != null and $c > $at)));
      $s[0] as $doc
      | [($doc.revision // "-" | tostring),
         (if ($doc.sql_sha256 | type) == "string" then "y" else "n" end),
         (if $i == null then "n" else (try (if ($doc | mine) == ($i[0] | theirs) and ($i[0] | criteria_moved($doc) | not) then "n" else "y" end) catch "n") end)]
      | join("\t")'
    IFS="$SR_TAB" read -r srev bound intake <<EOF2
$( { [ -f "$sidecar" ] && jq -rn --slurpfile s "$scope" --slurpfile i "$sidecar" "$prog" 2>/dev/null; } ||
   jq -rn --slurpfile s "$scope" --argjson i null "$prog" 2>/dev/null )
EOF2
    case "$srev" in ''|*[!0-9]*) srev="" ;; esac
  fi
  # Analyse fingerprints, and a bound bootstrap publishes, from a clean tree only (sr_source_clean),
  # so any uncommitted source is committed first.
  pre="$(sr_commit_first "$sql")"
  if [ -n "$srev" ]; then
    # The scope document's own staleness is the state itself. Under a review, test the scope
    # binding directly: analyse alone never refreshes scope.json. A scope framed before the SQL
    # existed has no binding to compare, so a stale review over it also names the rescope.
    if [ "$state" = stale ] && [ ! -f "$d/review.json" ]; then why="The SQL"
    elif [ -f "$d/review.json" ] && [ "$bound" = y ] && [ -f "$SR_ROOT/$sql" ]; then
      sr_binding "$scope" "$SR_ROOT/$sql" /dev/null >/dev/null 2>&1
      [ $? -eq 1 ] && why="The SQL"
    elif [ "$state" = stale ] && [ -f "$d/review.json" ] && [ "$bound" = n ]; then
      why="The SQL"; gap=", which has no SQL binding"
    fi
    if [ "$intake" = y ]; then why="${why:+$why and the analyst intake}"; why="${why:-The analyst intake}"; fi
    if [ -n "$why" ]; then
      # Bootstrap binds the scope to committed SQL, so a commit comes before it, not after.
      if [ -f "$d/review.json" ]; then follow="/data-request:analyse $sql --update"
      elif [ -f "$SR_ROOT/$sql" ]; then follow="/data-request:analyse $sql"
      else follow="/data-request:draft to write $sql"; fi
      printf '%s changed after scope revision %s%s: %srun /data-request:bootstrap %s to publish scope revision %s, then %s\n' \
        "$why" "$srev" "$gap" "$pre" "$sql" "$((srev + 1))" "$follow"
      return 0
    fi
  fi
  case "$state" in
    scoped)
      if [ ! -f "$SR_ROOT/$sql" ]; then printf '/data-request:draft to write %s, then /data-request:analyse %s\n' "$sql" "$sql"
      elif [ "$bound" = n ]; then
        printf '%s/data-request:bootstrap %s to bind the scope to the SQL, then /data-request:analyse %s\n' "$pre" "$sql" "$sql"
      else printf '%s/data-request:analyse %s to review the SQL\n' "$pre" "$sql"; fi ;;
    scoped-header-only) printf '%s/data-request:bootstrap %s to record the header revision of the scope\n' "$pre" "$sql" ;;
    stale|no-baseline) printf '%s/data-request:analyse %s --update\n' "$pre" "$sql" ;;
    header-only) printf '%s/data-request:analyse %s to record the header revision of the review\n' "$pre" "$sql" ;;
    current)
      ex=""
      if [ -f "$d/explain.json" ] && [ ! -L "$d/explain.json" ]; then
        ex="$(jq -rn --slurpfile e "$d/explain.json" --slurpfile r "$d/review.json" '
          if ($e[0].sql_sha256 == $r[0].sql_sha256 and $e[0].review_revision == $r[0].revision)
          then (if $e[0].completed == true then "done" else "partial" end) else "" end' 2>/dev/null)"
      fi
      case "$ex" in
        done) printf '/data-request:release <candidate ref> after the analyst accepts the explained SQL\n' ;;
        partial) printf '/data-request:explain %s to resume the walkthrough\n' "$sql" ;;
        *) printf '/data-request:explain %s to walk the analyst through the review\n' "$sql" ;;
      esac ;;
    *) printf '\n' ;;
  esac
}

# Amend gate: the one validator of an amendment record. The evidence hold (release.sh rl_amend_hold),
# the write-time check (release.sh amend-check) and the status line all read its rows, so they
# agree on what is valid. One TSV row per finding: kind, part id, field path, rule. It emits part
# ids, field paths, fixed rules and done commits only, never part text, reasons or other values.
SR_AMEND_JQ='def row($k; $id; $f; $r): [$k, $id, $f, $r] | join("\t");
def bad($f; $r): row("bad"; "-"; $f; $r);
def ne: type == "string" and test("\\S");
def check:
if type != "object" then bad("(document)"; "must be a JSON object")
else
  (if .schemaVersion == 1 then empty else bad("schemaVersion"; "must be 1") end),
  (if (has("kind") | not) or .kind == "amendment" then empty else bad("kind"; "must be amendment") end),
  (if (.parts | type) != "array" or (.parts | length) == 0 then bad("parts"; "must be a nonempty array")
   else
     (if [.parts[] | objects | .id | strings] | group_by(.) | any(length > 1)
      then bad("parts[].id (duplicate)"; "must be unique") else empty end),
     (.parts | to_entries[] | .key as $i | .value as $p | "parts[\($i)]" as $at
      | if ($p | type) != "object" then bad($at; "must be an object")
        else
          (($p.id | type) == "string" and ($p.id | test("^P[1-9][0-9]*$"))) as $idok
          | (if $idok then empty else bad("\($at).id"; "must be P<n>") end),
            (if $p.status == "handed off" then (if $idok then row("open"; $p.id; "-"; "-") else empty end)
             elif $p.status == "withdrawn" then
               (if ($p.reason | ne) then empty else bad("\($at).reason"; "required for a withdrawn part") end)
             elif $p.status == "done" then
               (if ($p.commit | type) == "string" and ($p.commit | test("^[0-9a-f]{7,64}$"))
                then (if $idok then row("done"; $p.id; "-"; $p.commit) else empty end)
                else bad("\($at).commit"; "required for a done part (a commit hash)") end)
             else bad("\($at).status"; "must be done, handed off or withdrawn") end)
        end)
   end)
end;
if length == 1 then .[0] | check else bad("(document)"; "must be one JSON document") end'

# The triage ledger shows an amendment when an entry has the amend stage. Emits each recorded
# amendment record path once, or "bad" for a ledger that is empty or has no entries. An amended entry
# that names no record is a single-part amendment, so it adds no row. Paths only, no values. Release
# holds on a named record that is missing, and status names it, so both read this one definition.
# Two entries that name one record give one row, so neither reader repeats a line.
SR_AMEND_LEDGER_JQ='def rec: type == "string" and test("^\\.sqlreview/amendments/[a-z0-9][a-z0-9-]*\\.json\\z");
def paths:
if type != "object" or (.entries | type) != "array" then "bad"
else [.entries[] | objects | select(.stage == "amend" or ((.stages_done | arrays | index("amend")) != null))
  | .stage_evidence | objects | .amend | objects | .artifacts | arrays | .[] | objects | .path | select(rec) | "path\t" + .]
  | unique[]
end;
if length == 1 then .[0] | paths else "bad" end'
SR_AMEND_LEDGER_HELD='release held: field entries is missing or invalid in .sqlreview/ledger.json'
SR_AMEND_LEDGER_NEXT='repair .sqlreview/ledger.json so it is one JSON object with an entries array (sqlreview.sh ledger set), then run status again'
SR_AMEND_NEXT='write it from the amendment hand-off comment on the deliverable PR (/data-request:amend step 5)'

# The shape of an amendment record name, in one place: the guard (through amend-check --name), the
# release hold and status all accept and print a name in this shape only. Lower-case letters, digits
# and hyphens, with no leading hyphen.
SR_AMEND_NAME_RULE='the record name must use lower-case letters, digits and hyphens'
sr_amend_name_ok() { # <name>
  case "$1" in ""|-*|*[!a-z0-9-]*) return 1 ;; esac
}
# The name a record file prints under: its name without .json, or "(invalid name)". Sets SR_AMEND_NAME.
sr_amend_label() { # <record file path>
  SR_AMEND_NAME="${1##*/}"; SR_AMEND_NAME="${SR_AMEND_NAME%.json}"
  sr_amend_name_ok "$SR_AMEND_NAME" || SR_AMEND_NAME="(invalid name)"
}
# The validator rows (SR_AMEND_JQ) of one record file, or of standard input when no file is given. A
# document that jq cannot parse is one fixed bad row, so every reader reports the same finding, and
# jq error text, which can quote a value, never reaches the output.
sr_amend_rows() { # [file]
  jq -rs "$SR_AMEND_JQ" "$@" 2>/dev/null || printf 'bad\t-\t(document)\tnot valid JSON\n'
}
