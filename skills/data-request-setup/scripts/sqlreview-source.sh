#!/usr/bin/env bash
# Committed SQL source shared by SQL review consumers. Bash 3.2 + jq only.
# Old SQL comes from git at the recorded commit, never from a copy under .sqlreview/.
# Callers supply an absolute output in their trapped private directory outside git.

# A partial clone fetches a missing blob from its remote when git reads it. Release evidence must make no
# network call, so every git here refuses that fetch (a git that reads this variable). Some gits ignore it, so
# sr_partial_gate also refuses every partial clone.
export GIT_NO_LAZY_FETCH=1

# Status contract: 6 is unavailable or unauthenticated historical evidence;
# 2 is malformed invocation, unsafe paths or operational I/O/tool failure.
sr_source_error() { printf 'sqlreview: %s\n' "$*" >&2; return 2; }
sr_source_unavailable() { printf 'sqlreview: %s\n' "$*" >&2; return 6; }

# Fail closed in a partial clone, whatever the git version. Version numbers do not tell whether a git refuses
# a lazy fetch, so the rule does not use them. A partial clone has extensions.partialclone, a remote with
# promisor=true, or a remote with partialclonefilter. The message is fixed and names no path. The answer is
# kept in SR_PARTIAL_OK, which subshells inherit. Status never calls this, so it adds no git call there.
sr_partial_gate() { # [DIR]
  [ -z "${SR_PARTIAL_OK:-}" ] || return 0
  local dir="${1:-$SR_ROOT}" key val partial=""
  while read -r key val; do
    [ -n "$key" ] || continue
    case "$key" in
      *.promisor) [ "$val" = false ] || partial=1 ;;
      *) partial=1 ;;
    esac
  done <<EOF2
$(git -C "$dir" config --get-regexp '^(extensions\.partialclone|remote\..*\.(promisor|partialclonefilter))$' 2>/dev/null)
EOF2
  if [ -n "$partial" ]; then
    sr_source_error "this repository is a partial clone, so a read could fetch from the network. Use a full clone or fetch the missing blobs first"
    return 2
  fi
  SR_PARTIAL_OK=1
}

sr_source_context() {
  SR_SOURCE_TOP="$(git -C "$SR_ROOT" rev-parse --show-toplevel 2>/dev/null)" || {
    sr_source_error "committed source requires a git repository"; return 2;
  }
  SR_SOURCE_TOP="$(cd "$SR_SOURCE_TOP" && pwd -P)" || return 2
  sr_partial_gate "$SR_SOURCE_TOP" || return 2
  case "$SR_ROOT" in
    "$SR_SOURCE_TOP") SR_SOURCE_PREFIX="" ;;
    "$SR_SOURCE_TOP"/*) SR_SOURCE_PREFIX="${SR_ROOT#"$SR_SOURCE_TOP"/}" ;;
    *) sr_source_error "unsafe project-root prefix"; return 2 ;;
  esac
  [ -z "$SR_SOURCE_PREFIX" ] || sr_safe_path "$SR_SOURCE_PREFIX"
  local grafts
  grafts="$(git -C "$SR_SOURCE_TOP" rev-parse --git-path info/grafts 2>/dev/null)" || return 2
  case "$grafts" in /*) ;; *) grafts="$SR_SOURCE_TOP/$grafts" ;; esac
  if [ -s "$grafts" ] || [ -n "$(git -C "$SR_SOURCE_TOP" for-each-ref --format='%(refname)' refs/replace/ 2>/dev/null)" ]; then
    sr_source_error "replacement refs/grafts refused for source evidence"; return 2
  fi
}

# Review records are not source. Everything else, including untracked sources,
# builders, configuration and pins, must be committed before fingerprinting, so
# the recorded commit identifies all inputs (SQL and non-SQL) of the review.
sr_source_clean() {
  sr_source_context || return 2
  local tmp entry status path other store
  tmp="$(mktemp)" || return 2
  if ! git -C "$SR_SOURCE_TOP" status --porcelain=v1 -z --untracked-files=all > "$tmp" 2>/dev/null; then
    rm -f "$tmp"; sr_source_error "source status unavailable"; return 2
  fi
  store="${SR_SOURCE_PREFIX:+$SR_SOURCE_PREFIX/}.sqlreview"
  while IFS= read -r -d '' entry; do
    status="${entry:0:2}"; path="${entry:3}"
    sr_store_exempt "$store" "$path" || {
      rm -f "$tmp"; sr_source_error "uncommitted source changes; commit SQL, builders, configuration and pins before fingerprinting"; return 2
    }
    case "$status" in *R*|*C*)
      IFS= read -r -d '' other || { rm -f "$tmp"; return 2; }
      sr_store_exempt "$store" "$other" || { rm -f "$tmp"; sr_source_error "uncommitted source rename"; return 2; } ;;
    esac
  done < "$tmp"
  rm -f "$tmp"
}

sr_source_show() { # REF SQL_PATH OUTPUT; copies the committed blob, sets SR_SOURCE_{COMMIT,PREFIX}
  [ $# -eq 3 ] || { sr_source_error "render requires ref, sql_path and output"; return 2; }
  sr_source_context || return 2
  # Structural check only: every caller that takes a new path applies the reviewed-tree rule first, and a
  # history entry kept by move may name a path the rule now refuses (its blob is read from Git, not the work tree).
  sr_safe_path "$2"
  case "$1" in ""|-*) sr_source_error "unsafe source ref"; return 2 ;; esac
  local ref_status
  SR_SOURCE_COMMIT="$(git -C "$SR_SOURCE_TOP" rev-parse --verify --quiet "$1^{commit}" 2>/dev/null)" || {
    ref_status=$?
    if [ "$ref_status" = 1 ]; then sr_source_unavailable "source commit unavailable"; return 6; fi
    sr_source_error "cannot resolve source commit"; return 2
  }
  case "$3" in /*) ;; *) sr_source_error "output must be absolute and outside the git tree"; return 2 ;; esac
  local output path row
  output="$(sr_normpath "$3")"
  case "$output" in "$SR_SOURCE_TOP"|"$SR_SOURCE_TOP"/*)
    sr_source_error "output must be outside the git tree"; return 2 ;;
  esac
  sr_no_symlinks "$output" || return 2
  [ ! -e "$output" ] || [ -f "$output" ] || { sr_source_error "output is not a regular file"; return 2; }
  # Every request SQL file is committed, whatever sql/provenance.json says produced it.
  path="${SR_SOURCE_PREFIX:+$SR_SOURCE_PREFIX/}$2"
  row="$(git -C "$SR_SOURCE_TOP" ls-tree "$SR_SOURCE_COMMIT" -- ":(literal)$path" 2>/dev/null)" || {
    sr_source_error "cannot inspect committed SQL source"; return 2;
  }
  case "$row" in
    "100644 blob "*|"100755 blob "*) ;;
    "") sr_source_unavailable "SQL source not committed at ${SR_SOURCE_COMMIT}: $2"; return 6 ;;
    *) sr_source_unavailable "committed SQL source is not a regular file (symlinks refused): $2"; return 6 ;;
  esac
  ( umask 077; git -C "$SR_SOURCE_TOP" show "$SR_SOURCE_COMMIT:$path" > "$output" 2>/dev/null ) || {
    sr_source_error "committed SQL blob unavailable"; return 2;
  }
  # No render marker here: callers use this for internal workspace files (evidence, publish, delta, impact).
  # Only materialize marks its output, and only for a record bound to a reviewed path (#516).
}

sr_source_auth() { # DOC OUTPUT; status 6 evidence unavailable, 2 operational failure
  local doc="$1" output="$2" commit path full body actual status
  sr_no_symlinks "$doc" || return 2
  commit="$(jq -r '.git_commit // ""' "$doc")" || return 2
  path="$(jq -r '.sql_path // ""' "$doc")" || return 2
  jq -e '(.git_commit | type == "string" and test("^[0-9a-f]{40}$|^[0-9a-f]{64}$")) and
      (.git_dirty == null or .git_dirty == false) and (.sql_sha256 | type == "string" and test("^[0-9a-f]{64}$"))' "$doc" >/dev/null || {
    status=$?
    [ "$status" = 1 ] || { sr_source_error "cannot validate recorded source evidence"; return 2; }
    sr_source_unavailable "record lacks clean immutable source evidence; reassess"; return 6
  }
  sr_source_show "$commit" "$path" "$output" || return $?
  full="$(jq -r '.sql_sha256' "$doc")" || return 2
  actual="$(sr_sha256 "$output")" || { sr_source_error "cannot hash recorded SQL"; return 2; }
  [ "$actual" = "$full" ] || { sr_source_unavailable "recorded full SHA mismatch; reassess"; return 6; }
  body="$(jq -r '.sql_body_sha256 // ""' "$doc")" || return 2
  if [ -n "$body" ]; then
    actual="$(sr_body_sha256 "$output")" || { sr_source_error "cannot hash recorded SQL body"; return 2; }
    [ "$actual" = "$body" ] || { sr_source_unavailable "recorded body SHA mismatch; reassess"; return 6; }
  fi
}
