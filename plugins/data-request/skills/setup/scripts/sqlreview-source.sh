#!/usr/bin/env bash
# Source reconstruction shared by SQL review consumers. Bash 3.2 + jq only.
# Callers supply an absolute output in their trapped private directory outside git.

# Status contract: 6 is unavailable/nonreproducible historical evidence;
# 2 is malformed invocation, unsafe paths or operational I/O/tool failure.
sr_source_error() { printf 'sqlreview: %s\n' "$*" >&2; return 2; }
sr_source_unavailable() { printf 'sqlreview: %s\n' "$*" >&2; return 6; }

sr_source_context() {
  SR_SOURCE_TOP="$(git -C "$SR_ROOT" rev-parse --show-toplevel 2>/dev/null)" || {
    sr_source_error "committed source requires a git repository"; return 2;
  }
  SR_SOURCE_TOP="$(cd "$SR_SOURCE_TOP" && pwd -P)" || return 2
  case "$SR_ROOT" in
    "$SR_SOURCE_TOP") SR_SOURCE_PREFIX="" ;;
    "$SR_SOURCE_TOP"/*) SR_SOURCE_PREFIX="${SR_ROOT#"$SR_SOURCE_TOP"/}" ;;
    *) sr_source_error "unsafe project-root prefix"; return 2 ;;
  esac
  [ -z "$SR_SOURCE_PREFIX" ] || sr_safe_sql "$SR_SOURCE_PREFIX"
  local grafts
  grafts="$(git -C "$SR_SOURCE_TOP" rev-parse --git-path info/grafts)" || return 2
  case "$grafts" in /*) ;; *) grafts="$SR_SOURCE_TOP/$grafts" ;; esac
  if [ -s "$grafts" ] || [ -n "$(git -C "$SR_SOURCE_TOP" for-each-ref --format='%(refname)' refs/replace/)" ]; then
    sr_source_error "replacement refs/grafts refused for source evidence"; return 2
  fi
}

# Review records are not source. Everything else, including untracked sources,
# config, generator adapters and pins, must be committed before fingerprinting.
sr_source_clean() {
  sr_source_context || return 2
  local tmp entry status path other store
  tmp="$(mktemp)" || return 2
  if ! git -C "$SR_SOURCE_TOP" status --porcelain=v1 -z --untracked-files=all > "$tmp"; then
    rm -f "$tmp"; sr_source_error "source status unavailable"; return 2
  fi
  store="${SR_SOURCE_PREFIX:+$SR_SOURCE_PREFIX/}.sqlreview"
  while IFS= read -r -d '' entry; do
    status="${entry:0:2}"; path="${entry:3}"
    case "$path" in
      "$store"/reviews/*|"$store"/releases/*|"$store"/templates/*|"$store"/ledger.json|"$store"/.gitignore) ;;
      *) rm -f "$tmp"; sr_source_error "uncommitted source changes; commit builder/configuration/pins before fingerprinting"; return 2 ;;
    esac
    case "$status" in *R*|*C*)
      IFS= read -r -d '' other || { rm -f "$tmp"; return 2; }
      case "$other" in
        "$store"/reviews/*|"$store"/releases/*|"$store"/templates/*|"$store"/ledger.json|"$store"/.gitignore) ;;
        *) rm -f "$tmp"; sr_source_error "uncommitted source rename"; return 2 ;;
      esac ;;
    esac
  done < "$tmp"
  rm -f "$tmp"
}

# Scaffold schema-1 sha256 authenticates canonical SQL, not the review's raw
# bytes: remove an initial BOM, CRLF -> LF, trailing LF -> exactly one LF.
sr_source_canonical() {
  jq -nj --rawfile sql "$1" '$sql | ltrimstr("\ufeff") | gsub("\r\n"; "\n") | sub("\n*$"; "") + "\n"' > "$2"
}

# Only the explicitly selected executable search path crosses the runtime
# boundary. Home/config/cache/temp state is private; no startup files, current
# project overrides, exported shell functions or credentials are inherited.
sr_source_isolated() { # PRIVATE_WORKSPACE COMMAND [ARG...]
  local private="$1"; shift
  command env -i PATH="$PATH" HOME="$private/home" TMPDIR="$private/runtime" \
    XDG_CONFIG_HOME="$private/config" XDG_CACHE_HOME="$private/cache" \
    XDG_DATA_HOME="$private/data" XDG_STATE_HOME="$private/state" \
    LC_ALL=C LANG=C TZ=UTC GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null "$@"
}

sr_source_render() { # REF SQL_PATH OUTPUT; sets SR_SOURCE_{COMMIT,MODE,PREFIX}
  [ $# -eq 3 ] || { sr_source_error "render requires ref, sql_path and output"; return 2; }
  sr_source_context || return 2
  sr_safe_sql "$2"
  case "$1" in ""|-*) sr_source_error "unsafe source ref"; return 2 ;; esac
  local ref_status
  SR_SOURCE_COMMIT="$(git -C "$SR_SOURCE_TOP" rev-parse --verify --quiet "$1^{commit}" 2>/dev/null)" || {
    ref_status=$?
    if [ "$ref_status" = 1 ]; then sr_source_unavailable "source commit unavailable"; return 6; fi
    sr_source_error "cannot resolve source commit"; return 2
  }
  case "$3" in /*) ;; *) sr_source_error "output must be absolute and outside the git tree"; return 2 ;; esac
  local output="$(sr_normpath "$3")" manifest entry mode manifest_json status
  case "$output" in "$SR_SOURCE_TOP"|"$SR_SOURCE_TOP"/*)
    sr_source_error "output must be outside the git tree"; return 2 ;;
  esac
  sr_no_symlinks "$output" || return 2
  [ ! -e "$output" ] || [ -f "$output" ] || { sr_source_error "output is not a regular file"; return 2; }
  # Read the selected commit before checkout to expose mode to the caller.
  manifest="${SR_SOURCE_PREFIX:+$SR_SOURCE_PREFIX/}sql/provenance.json"
  if git -C "$SR_SOURCE_TOP" cat-file -e "$SR_SOURCE_COMMIT:$manifest" 2>/dev/null; then
    manifest_json="$(git -C "$SR_SOURCE_TOP" show "$SR_SOURCE_COMMIT:$manifest")" || {
      sr_source_error "cannot read source provenance manifest"; return 2;
    }
    entry="$(printf '%s' "$manifest_json" | jq -ce --arg p "$2" '
      select(.schema == 1 and (.requests | type) == "object") | .requests[$p] |
      select(type == "object" and (.source == "builder" or .source == "cohort" or .source == "spec" or .source == "hand-written"))')" || {
      status=$?
      case "$status" in 1|4|5) sr_source_unavailable "malformed/undeclared provenance entry or unsupported manifest schema"; return 6 ;;
        *) sr_source_error "cannot parse source provenance manifest"; return 2 ;; esac
    }
    mode="$(printf '%s' "$entry" | jq -r '.source')" || return 2
    if [ "$mode" = hand-written ]; then SR_SOURCE_MODE=tracked; else SR_SOURCE_MODE=rendered; fi
  else
    status=$?
    [ "$status" = 128 ] || { sr_source_error "cannot inspect source provenance manifest"; return 2; }
    entry='{}'; SR_SOURCE_MODE=tracked
  fi
  (
    umask 077
    local tmp root cfg arg command=() sha algorithm expected status
    tmp="$(mktemp -d "${TMPDIR:-/tmp}/sqlreview-source.XXXXXX")" || exit 2
    trap 'rm -rf "$tmp"' EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM HUP
    case "$(cd "$tmp" && pwd -P)" in "$SR_SOURCE_TOP"|"$SR_SOURCE_TOP"/*)
      sr_source_error "temporary checkout must be outside the git tree"; exit 2 ;;
    esac
    mkdir "$tmp/home" "$tmp/runtime" "$tmp/config" "$tmp/cache" "$tmp/data" "$tmp/state" || exit 2
    if git -C "$SR_SOURCE_TOP" ls-tree -r "$SR_SOURCE_COMMIT" | awk '$1 == "120000" { found=1 } END { exit !found }'; then
      sr_source_unavailable "source symlinks refused"; exit 6
    fi
    sr_source_isolated "$tmp" git -c core.hooksPath=/dev/null clone --quiet --shared --no-checkout "$SR_SOURCE_TOP" "$tmp/tree" > "$tmp/git.log" 2>&1 &&
      sr_source_isolated "$tmp" git -C "$tmp/tree" -c core.hooksPath=/dev/null -c core.autocrlf=false checkout --quiet --detach "$SR_SOURCE_COMMIT" >> "$tmp/git.log" 2>&1 || {
        sr_source_error "source checkout unavailable"; exit 2;
      }
    root="$tmp/tree${SR_SOURCE_PREFIX:+/$SR_SOURCE_PREFIX}"
    [ -d "$root" ] || { sr_source_unavailable "historical project root unavailable"; exit 6; }
    if [ "$SR_SOURCE_MODE" = tracked ]; then
      [ -f "$root/$2" ] && [ ! -L "$root/$2" ] || {
        sr_source_unavailable "committed SQL source unavailable; declare a generator and configure its adapter"; exit 6;
      }
      git -C "$SR_SOURCE_TOP" show "$SR_SOURCE_COMMIT:${SR_SOURCE_PREFIX:+$SR_SOURCE_PREFIX/}$2" > "$tmp/render.sql" 2> "$tmp/git.log" || {
        sr_source_error "committed SQL blob unavailable"; exit 2;
      }
    else
      cfg="$root/.sqlreview/config.json"
      [ -f "$cfg" ] || {
        sr_source_unavailable "generated SQL requires sql_render.command argv adapter in committed config; install a render-only adapter"; exit 6;
      }
      jq -e '.sql_render.command | type == "array" and length > 0 and all(.[]; type == "string" and length > 0 and (contains("\u0000") | not))' "$cfg" >/dev/null 2>&1 || {
        status=$?
        case "$status" in 1|4|5) sr_source_unavailable "generated SQL requires sql_render.command argv adapter in committed config; install a render-only adapter"; exit 6 ;;
          *) sr_source_error "cannot validate committed render adapter configuration"; exit 2 ;; esac
      }
      jq -j '.sql_render.command[] | ., "\u0000"' "$cfg" > "$tmp/argv" || {
        sr_source_error "cannot read committed render adapter arguments"; exit 2;
      }
      while IFS= read -r -d '' arg; do command+=("$arg"); done < "$tmp/argv"
      if ! (cd "$root" && sr_source_isolated "$tmp" "${command[@]}" --sql-path "$2" --output "$tmp/render.sql") > "$tmp/adapter.log" 2>&1; then
        sr_source_unavailable "render failed: adapter/dependencies unavailable; inspect the committed render-only adapter and pins"; exit 6
      fi
      [ -f "$tmp/render.sql" ] && [ ! -L "$tmp/render.sql" ] || {
        sr_source_unavailable "render output missing or not a regular file (symlinks refused)"; exit 6;
      }
      if ! (cd "$root" && sr_source_isolated "$tmp" "${command[@]}" --sql-path "$2" --output "$tmp/repeat.sql") >> "$tmp/adapter.log" 2>&1; then
        sr_source_unavailable "render failed on repeat: adapter/dependencies unavailable"; exit 6
      fi
      [ -f "$tmp/repeat.sql" ] && [ ! -L "$tmp/repeat.sql" ] || {
        sr_source_unavailable "repeat render output missing or not a regular file"; exit 6;
      }
      cmp -s "$tmp/render.sql" "$tmp/repeat.sql" || {
        status=$?
        [ "$status" = 1 ] || { sr_source_error "cannot compare repeated render output"; exit 2; }
        sr_source_unavailable "nondeterministic render; repeated output differs"; exit 6;
      }
    fi
    printf '%s' "$entry" | jq -e 'if has("sha256") then .sha256 | type == "string" and test("^[0-9a-f]{64}$") else true end' >/dev/null || {
      status=$?
      [ "$status" = 1 ] || { sr_source_error "cannot validate manifest SHA256"; exit 2; }
      sr_source_unavailable "malformed manifest SHA256"; exit 6;
    }
    expected="$(printf '%s' "$entry" | jq -r '.sha256 // ""')" || exit 2
    algorithm="$(printf '%s' "$entry" | jq -r 'if has("hash_algorithm") then .hash_algorithm else "sha256-canonical-v1" end')" || exit 2
    case "$algorithm" in sha256-canonical-v1|sha256-raw) ;; *) sr_source_unavailable "unsupported manifest hash algorithm"; exit 6 ;; esac
    if [ -n "$expected" ]; then
      if [ "$algorithm" = sha256-raw ]; then sha="$(sr_sha256 "$tmp/render.sql")" || exit 2
      else sr_source_canonical "$tmp/render.sql" "$tmp/canonical.sql" || exit 2; sha="$(sr_sha256 "$tmp/canonical.sql")" || exit 2; fi
      [ "$sha" = "$expected" ] || { sr_source_unavailable "manifest hash mismatch with fresh render"; exit 6; }
    fi
    cp "$tmp/render.sql" "$output" || { sr_source_error "cannot write caller output"; exit 2; }
  )
}

sr_source_auth() { # DOC OUTPUT; status 6 evidence unavailable, 2 operational failure
  local doc="$1" output="$2" commit path provenance prefix mode full body actual status
  sr_no_symlinks "$doc" || return 2
  commit="$(jq -r '.git_commit // ""' "$doc")" || return 2
  path="$(jq -r '.sql_path // ""' "$doc")" || return 2
  jq -e '(.git_commit | type == "string" and test("^[0-9a-f]{40}$|^[0-9a-f]{64}$")) and
      (.git_dirty == null or .git_dirty == false) and (.sql_sha256 | type == "string" and test("^[0-9a-f]{64}$"))' "$doc" >/dev/null || {
    status=$?
    [ "$status" = 1 ] || { sr_source_error "cannot validate recorded source evidence"; return 2; }
    sr_source_unavailable "record lacks clean immutable source evidence; reassess"; return 6
  }
  provenance="$(jq -r 'has("sql_provenance")' "$doc")" || return 2
  if [ "$provenance" = true ]; then
    jq -e '.git_dirty == false and (.sql_provenance | type == "object") and
      .sql_provenance.commit == .git_commit and (.sql_provenance.mode == "tracked" or .sql_provenance.mode == "rendered") and (.sql_provenance.project_root | type == "string")' "$doc" >/dev/null || {
      status=$?
      [ "$status" = 1 ] || { sr_source_error "cannot validate recorded SQL provenance"; return 2; }
      sr_source_unavailable "invalid recorded SQL provenance"; return 6
    }
  fi
  sr_source_render "$commit" "$path" "$output" || return $?
  if [ "$provenance" = true ]; then
    prefix="$(jq -r '.sql_provenance.project_root' "$doc")" || return 2
    mode="$(jq -r '.sql_provenance.mode' "$doc")" || return 2
    [ "$prefix" = "$SR_SOURCE_PREFIX" ] && [ "$mode" = "$SR_SOURCE_MODE" ] || {
      sr_source_unavailable "recorded SQL provenance differs from reconstructed source"; return 6
    }
  fi
  full="$(jq -r '.sql_sha256' "$doc")" || return 2
  actual="$(sr_sha256 "$output")" || { sr_source_error "cannot hash recorded SQL render"; return 2; }
  [ "$actual" = "$full" ] || { sr_source_unavailable "recorded full SHA mismatch; reassess"; return 6; }
  body="$(jq -r '.sql_body_sha256 // ""' "$doc")" || return 2
  if [ -n "$body" ]; then
    actual="$(sr_body_sha256 "$output")" || { sr_source_error "cannot hash recorded SQL body"; return 2; }
    [ "$actual" = "$body" ] || { sr_source_unavailable "recorded body SHA mismatch; reassess"; return 6; }
  fi
}
