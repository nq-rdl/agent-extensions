#!/usr/bin/env bash
# sqlreview.sh — the sql-code plugin's shared helper. One entry point, subcommands below.
# Shared by /sql-code:setup, :bootstrap, :analyse and :explain via
#   S="${CLAUDE_PLUGIN_ROOT}/skills/setup/scripts"; bash "$S/sqlreview.sh" <command> ...
# and by the plugin's hooks. Contract: docs/specs/2026-09-15-sql-review-plugin-design.md §4.
#
#   init [--diff] [--apply PATH...] [--json]   create .sqlreview/ from the bundled default; never overwrites
#   status [--json]                            reviews and their state; exit 3 when not initialised
#   slug PATH                                  slug for a project path; exit 5 on a conflicting binding
#   check FILE | check --stdin                 validate a review/scope JSON; exit 4 with one violation per line
#   publish SLUG scope|review DRAFT             validate a staged copy, then atomically replace the final JSON
#   roles ENGINEER ANALYST                     update only the two confirmed role names in config.json
#   fingerprint SQL                            {sql_path, sql_sha256, git_commit, git_dirty}
#   snapshot SLUG SQL                          verify final review SHA, retain history, advance source.sql
#   delta SLUG                                 diff source.sql vs the current SQL; exit 10 when changed, 6 no baseline
#   impact SLUG                                heuristic: identifiers in the diff traced into unchanged lines
#   move OLDPATH NEWPATH                       rebind a review directory after the SQL moved
#   render SLUG scope|review                   JSON + templates/<kind>.md -> reviews/SLUG/<kind>.md
#
# Exit codes: 0 ok · 1 usage · 2 error · 3 not initialised · 4 invalid document · 5 slug conflict ·
# 6 no baseline · 10 differences found (init --diff / delta).
set -u
SR_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
# shellcheck source=sqlreview-lib.sh
. "$SR_SCRIPT_DIR/sqlreview-lib.sh"
SR_ASSETS="$SR_SCRIPT_DIR/../assets/sqlreview"

usage() {
  sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//' >&2
  exit 1
}

# ---------------------------------------------------------------------------------------------
cmd_init() {
  local mode="create" json=0 apply=() root target f state rc=0 any=0 entries="[]"
  while [ $# -gt 0 ]; do
    case "$1" in
      --diff) mode="diff" ;;
      --json) json=1 ;;
      --apply) mode="apply"; shift; while [ $# -gt 0 ]; do apply+=("$1"); shift; done; break ;;
      *) usage ;;
    esac
    shift
  done
  [ -d "$SR_ASSETS" ] || sr_die 2 "bundled default not found at $SR_ASSETS (plugin install incomplete)"
  root="$(sr_init_root)"
  target="$root/$SR_DIR"
  sr_no_symlinks "$target" || exit 2
  local files
  files="$(cd "$SR_ASSETS" && find . -type f | sed 's|^\./||' | sort)"

  if [ "$mode" = "apply" ]; then
    [ "${#apply[@]}" -gt 0 ] || sr_die 1 "--apply needs at least one path (relative to $SR_DIR/)"
    for f in "${apply[@]}"; do
      case "$f" in config.json|templates/scope.md|templates/review.md) ;; *) sr_die 2 "unknown bundled path: $f" ;; esac
      printf '%s\n' "$files" | grep -Fxq -- "$f" || sr_die 2 "no such file in the bundled default: $f"
      sr_no_symlinks "$target/$f" || exit 2
      mkdir -p "$target/$(dirname "$f")" || sr_die 2 "cannot create target directory"
      cp "$SR_ASSETS/$f" "$target/$f" || sr_die 2 "cannot copy $f"
      printf 'applied\t%s\n' "$f"
    done
    return 0
  fi

  if [ "$mode" = "create" ] && [ ! -d "$target" ]; then
    for f in $files; do
      sr_no_symlinks "$target/$f" || exit 2
      mkdir -p "$target/$(dirname "$f")" || sr_die 2 "cannot create target directory"
      cp "$SR_ASSETS/$f" "$target/$f" || sr_die 2 "cannot copy $f"
    done
    mkdir -p "$target/reviews" || sr_die 2 "cannot create reviews"
    if [ "$json" = 1 ]; then
      jq -n --arg root "$root" --arg files "$files" '{root: $root, created: true, files: ($files | split("\n"))}'
    else
      printf 'created\t%s\n' "$target"
      for f in $files; do printf 'file\t%s\n' "$f"; done
    fi
    return 0
  fi

  # Report mode (explicit --diff, or init on an existing tree): never write anything.
  for f in $files; do
    if [ ! -f "$target/$f" ]; then state="new"; any=1
    elif cmp -s "$SR_ASSETS/$f" "$target/$f"; then state="same"
    else state="differs"; any=1
    fi
    if [ "$json" = 1 ]; then
      entries="$(printf '%s' "$entries" | jq -c --arg p "$f" --arg s "$state" '. + [{path: $p, state: $s}]')"
    else
      printf '%s\t%s\n' "$state" "$f"
      if [ "$state" = "differs" ]; then
        diff -u -L "bundled default: $f" -L "project: $SR_DIR/$f" "$SR_ASSETS/$f" "$target/$f" | sed 's/^/    /'
      fi
    fi
  done
  [ "$any" = 1 ] && rc=10
  if [ "$json" = 1 ]; then
    printf '%s' "$entries" | jq --arg root "$root" --argjson exists "$([ -d "$target" ] && echo true || echo false)" \
      '{root: $root, exists: $exists, files: .}'
  fi
  return "$rc"
}

# ---------------------------------------------------------------------------------------------
cmd_status() {
  local json=0 d slug state schema rows="[]"
  [ "${1:-}" = "--json" ] && json=1
  sr_need_jq
  sr_require_root
  schema="$(jq -r '.schemaVersion // "?"' "$SR_ROOT/$SR_DIR/config.json" 2>/dev/null || echo '?')"
  if [ -d "$SR_REVIEWS" ]; then
    for d in "$SR_REVIEWS"/*/; do
      [ -d "$d" ] || continue
      slug="$(basename "$d")"
      IFS="$(printf '\t')" read -r state SR_SQL_PATH SR_REVISION <<EOF
$(sr_state "$slug")
EOF
      if [ "$json" = 1 ]; then
        rows="$(printf '%s' "$rows" | jq -c --arg slug "$slug" --arg state "$state" --arg sql "$SR_SQL_PATH" --arg rev "$SR_REVISION" \
          '. + [{slug: $slug, state: $state, sql_path: $sql, revision: ($rev | tonumber? // null)}]')"
      else
        printf '%s\t%s\t%s\t%s\n' "$slug" "$state" "$SR_SQL_PATH" "$SR_REVISION"
      fi
    done
  fi
  if [ "$json" = 1 ]; then
    printf '%s' "$rows" | jq --arg root "$SR_ROOT" --arg schema "$schema" \
      '{root: $root, schemaVersion: ($schema | tonumber? // $schema), reviews: .,
        counts: (group_by(.state) | map({key: .[0].state, value: length}) | from_entries | . + {total: (map(.) | add // 0)})}'
  fi
  return 0
}

# ---------------------------------------------------------------------------------------------
cmd_slug() {
  [ $# -eq 1 ] || usage
  sr_need_jq
  sr_require_root
  local rel slug doc bound
  rel="$(sr_relpath "$1")" || exit $?
  sr_safe_sql "$rel"
  slug="$(sr_slug "$rel")" || exit $?
  sr_safe_slug "$slug"
  if doc="$(sr_doc_for "$slug")"; then
    bound="$(jq -r '.sql_path // ""' "$doc")"
    if [ -n "$bound" ] && [ "$bound" != "$rel" ]; then
      sr_die 5 "reviews/$slug/ is already bound to '$bound', not '$rel'. If the SQL moved, run: sqlreview.sh move '$bound' '$rel'"
    fi
  fi
  printf '%s\n' "$slug"
}

# ---------------------------------------------------------------------------------------------
cmd_check() {
  [ $# -eq 1 ] || usage
  sr_need_jq
  local src="$1" tmp out rc
  tmp="$(mktemp)" || sr_die 2 "mktemp failed"

  if [ "$src" = "--stdin" ]; then cat > "$tmp"; else
    [ -f "$src" ] || { rm -f "$tmp"; sr_die 2 "no such file: $src"; }
    cat "$src" > "$tmp"
  fi
  if ! jq -se 'length == 1 and (.[0] | type == "object")' "$tmp" >/dev/null 2>&1; then
    rm -f "$tmp"; printf 'invalid JSON: the document does not parse\n'; return 4
  fi
  out="$(jq -r -f "$SR_SCRIPT_DIR/sqlreview-check.jq" "$tmp" 2>&1)"; rc=$?
  rm -f "$tmp"
  if [ "$rc" -ne 0 ]; then printf 'check failed to run: %s\n' "$out"; return 4; fi
  if [ -n "$out" ]; then printf '%s\n' "$out"; return 4; fi
  printf 'ok\n'
  return 0
}

# ---------------------------------------------------------------------------------------------
cmd_roles() (
  [ $# -eq 2 ] || usage
  sr_need_jq
  sr_require_root
  local config="$SR_ROOT/$SR_DIR/config.json" tmp
  sr_no_symlinks "$config" || exit 2
  [ -f "$config" ] || sr_die 2 "config.json is missing"
  [ -n "$1" ] && [ -n "$2" ] || sr_die 4 "role names must not be empty"
  tmp="$(mktemp "$SR_ROOT/$SR_DIR/.roles.XXXXXX")" || sr_die 2 "mktemp failed"
  trap 'rm -f "$tmp"' EXIT
  trap 'exit 2' HUP INT TERM
  jq -se --arg engineer "$1" --arg analyst "$2" '
    if length == 1 and (.[0] | type == "object" and .schemaVersion == 1 and (.roles | type == "object"))
    then .[0] | .roles.engineer = $engineer | .roles.analyst = $analyst
    else error("expected one schema-1 configuration with a roles object") end
  ' "$config" > "$tmp" || sr_die 4 "invalid configuration; original preserved"
  mv "$tmp" "$config" || sr_die 2 "cannot update roles"
  printf 'updated\tconfig.json roles\n'
)

# ---------------------------------------------------------------------------------------------
cmd_publish() (
  [ $# -eq 3 ] || usage
  sr_need_jq
  sr_require_root
  local slug="$1" kind="$2" draft="$3" dest tmp rel previous
  sr_safe_slug "$slug"
  case "$kind" in scope|review) ;; *) usage ;; esac
  dest="$SR_REVIEWS/$slug/$kind.json"
  sr_no_symlinks "$dest" || exit 2
  [ ! -d "$dest" ] || sr_die 2 "publish destination is a directory"
  [ -f "$draft" ] || sr_die 2 "no such draft: $draft"
  mkdir -p "$SR_REVIEWS/$slug" || sr_die 2 "cannot create review directory"
  tmp="$(mktemp "$SR_REVIEWS/$slug/.publish.XXXXXX")" || sr_die 2 "mktemp failed"
  trap 'rm -f "$tmp"' EXIT
  trap 'exit 2' HUP INT TERM
  cp "$draft" "$tmp" || sr_die 2 "cannot stage draft"
  cmd_check "$tmp" || exit 4
  jq -e --arg s "$slug" --arg k "$kind" '.slug == $s and .kind == $k' "$tmp" >/dev/null || sr_die 4 "document slug/kind must match destination"
  rel="$(jq -r .sql_path "$tmp")"
  sr_safe_sql "$rel"
  previous=0
  if [ -f "$dest" ]; then
    cmd_check "$dest" >/dev/null || sr_die 4 "existing document is invalid"
    previous="$(jq -r .revision "$dest")"
  fi
  if [ "$kind" = review ]; then
    [ -f "$SR_ROOT/$rel" ] || sr_die 2 "no such SQL: $rel"
    [ "$(sr_sha256 "$SR_ROOT/$rel")" = "$(jq -r .sql_sha256 "$tmp")" ] || sr_die 2 "SQL changed since fingerprint; reassess before publishing"
  fi
  if [ -f "$dest" ] && cmp -s "$tmp" "$dest"; then
    printf 'already published\t%s\n' "${dest#"$SR_ROOT"/}"
    exit 0
  fi
  jq -e --argjson previous "$previous" '.revision == ($previous + 1)' "$tmp" >/dev/null || sr_die 4 "revision must follow the existing document (first revision is 1)"
  mv "$tmp" "$dest" || sr_die 2 "cannot publish document"
  printf 'published\t%s\n' "${dest#"$SR_ROOT"/}"
)

# ---------------------------------------------------------------------------------------------
cmd_fingerprint() {
  [ $# -eq 1 ] || usage
  sr_need_jq
  sr_require_root
  local rel abs sha commit="" dirty=false
  rel="$(sr_relpath "$1")" || exit $?
  sr_safe_sql "$rel"
  abs="$SR_ROOT/$rel"
  [ -f "$abs" ] || sr_die 2 "no such file: $rel"
  sha="$(sr_sha256 "$abs")"
  if git -C "$SR_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    commit="$(git -C "$SR_ROOT" rev-parse HEAD 2>/dev/null || true)"
    [ -n "$(git -C "$SR_ROOT" status --porcelain --untracked-files=all -- "$rel" 2>/dev/null)" ] && dirty=true
  fi
  jq -n --arg p "$rel" --arg sha "$sha" --arg c "$commit" --argjson dirty "$dirty" \
    '{sql_path: $p, sql_sha256: $sha, git_commit: (if $c == "" then null else $c end), git_dirty: $dirty}'
}

# ---------------------------------------------------------------------------------------------
cmd_snapshot() {
  [ $# -eq 2 ] || usage
  sr_require_root
  local slug="$1" rel abs
  rel="$(sr_relpath "$2")" || exit $?
  sr_safe_sql "$rel"
  abs="$SR_ROOT/$rel"
  [ -f "$abs" ] || sr_die 2 "no such file: $rel"
  sr_need_jq
  sr_safe_slug "$slug"
  [ "$slug" = "$(sr_slug "$rel")" ] || sr_die 2 "slug/path mismatch"
  local doc tmp sha revision
  doc="$SR_REVIEWS/$slug/review.json"
  sr_no_symlinks "$doc" || exit 2
  sr_no_symlinks "$SR_REVIEWS/$slug/source.sql" || exit 2
  [ ! -d "$SR_REVIEWS/$slug/source.sql" ] || sr_die 2 "snapshot destination is a directory"
  sr_no_symlinks "$SR_REVIEWS/$slug/rebind-required" || exit 2
  cmd_check "$doc" >/dev/null || sr_die 4 "write a validated review before snapshot"
  [ "$(jq -r .sql_path "$doc")" = "$rel" ] || sr_die 2 "review/path mismatch"
  tmp="$(mktemp "$SR_REVIEWS/$slug/.snapshot.XXXXXX")" || sr_die 2 "mktemp failed"
  cp "$abs" "$tmp" || { rm -f "$tmp"; sr_die 2 "snapshot copy failed"; }
  sha="$(sr_sha256 "$tmp")"
  [ "$sha" = "$(jq -r .sql_sha256 "$doc")" ] || { rm -f "$tmp"; sr_die 2 "SQL changed since fingerprint; reassess before snapshot"; }
  revision="$(jq -r .revision "$doc")"
  sr_no_symlinks "$SR_REVIEWS/$slug/history/$revision.sql" || { rm -f "$tmp"; exit 2; }
  mkdir -p "$SR_REVIEWS/$slug/history" || { rm -f "$tmp"; sr_die 2 "cannot create history"; }
  if [ -e "$SR_REVIEWS/$slug/history/$revision.sql" ]; then
    cmp -s "$tmp" "$SR_REVIEWS/$slug/history/$revision.sql" || { rm -f "$tmp"; sr_die 2 "revision history conflict"; }
  else
    cp "$tmp" "$SR_REVIEWS/$slug/history/$revision.sql" || { rm -f "$tmp"; sr_die 2 "history copy failed"; }
  fi
  mv "$tmp" "$SR_REVIEWS/$slug/source.sql" || sr_die 2 "snapshot replacement failed"
  rm -f "$SR_REVIEWS/$slug/rebind-required" || sr_die 2 "cannot clear rebind marker"
  printf 'snapshot\t%s\t%s\n' "$slug" "$sha"
}

# ---------------------------------------------------------------------------------------------
# Shared by delta and impact: sets SR_BASE, SR_CUR, SR_SQL_PATH; returns 0 unchanged, 10 changed.
_delta_prepare() {
  local slug="$1" doc
  sr_need_jq
  sr_require_root
  sr_safe_slug "$slug"
  [ -d "$SR_REVIEWS/$slug" ] || sr_die 2 "no review directory for slug '$slug'"
  doc="$(sr_doc_for "$slug")" || sr_die 2 "reviews/$slug/ has no review.json or scope.json"
  cmd_check "$doc" >/dev/null || sr_die 4 "invalid document"
  SR_SQL_PATH="$(jq -r '.sql_path // ""' "$doc")"
  sr_safe_sql "$SR_SQL_PATH"
  SR_BASE="$SR_REVIEWS/$slug/source.sql"
  SR_CUR="$SR_ROOT/$SR_SQL_PATH"
  sr_no_symlinks "$SR_BASE" || exit 2
  [ -f "$SR_BASE" ] || sr_die 6 "no baseline: reviews/$slug/source.sql is missing, so there is nothing to diff against — run a full /sql-code:analyse (it records the snapshot)"
  [ -f "$SR_CUR" ] || sr_die 2 "the reviewed SQL no longer exists: $SR_SQL_PATH (moved? see: sqlreview.sh move)"
  [ ! -f "$SR_REVIEWS/$slug/rebind-required" ] || return 10
  [ "$(sr_sha256 "$SR_BASE")" = "$(jq -r .sql_sha256 "$doc")" ] || return 10
  cmp -s "$SR_BASE" "$SR_CUR" && return 0
  return 10
}

cmd_delta() {
  [ $# -eq 1 ] || usage
  local rc
  _delta_prepare "$1"; rc=$?
  printf 'baseline_sha256=%s current_sha256=%s sql_path=%s\n' "$(sr_sha256 "$SR_BASE")" "$(sr_sha256 "$SR_CUR")" "$SR_SQL_PATH"
  if [ "$rc" -eq 0 ]; then printf 'unchanged since the reviewed snapshot\n'; return 0; fi
  diff -u -L "reviewed (reviews/$1/source.sql)" -L "current ($SR_SQL_PATH)" "$SR_BASE" "$SR_CUR"
  return 10
}

cmd_impact() {
  [ $# -eq 1 ] || usage
  local rc changed idents ident
  _delta_prepare "$1"; rc=$?
  if [ "$rc" -eq 0 ]; then printf 'no change since the reviewed snapshot; nothing to trace\n'; return 0; fi
  printf '# impact hints — HEURISTIC. Identifiers that appear in the changed lines, traced to unchanged lines\n'
  printf '# that mention them. This suggests where to look; it does not prove anything unaffected. Every\n'
  printf '# assumption and limitation is reassessed on an update regardless of this list.\n'
  # Line numbers (in the current file) that belong to the diff hunks.
  changed="$(diff -u "$SR_BASE" "$SR_CUR" | awk '
    /^@@/ { split($3, p, ","); n = substr(p[1], 2) + 0; next }
    /^\+\+\+/ || /^---/ { next }
    /^\+/ { print n; n++; next }
    /^-/ { next }
    { n++ }')"
  # Identifiers on added/removed lines, minus SQL keywords and common functions.
  idents="$(diff -u "$SR_BASE" "$SR_CUR" | awk '/^[+-]/ && !/^(\+\+\+|---)/' | sed 's/^[+-]//' \
    | tr -c 'A-Za-z0-9_\n' '\n' | grep -E '^[A-Za-z_][A-Za-z0-9_]*$' | sort -u \
    | grep -Eivx 'select|from|where|join|left|right|inner|outer|full|cross|on|as|with|group|by|order|having|limit|offset|and|or|not|null|is|in|exists|between|like|case|when|then|else|end|union|all|distinct|count|sum|min|max|avg|coalesce|cast|over|partition|asc|desc|true|false|into|insert|update|delete|set|values|create|table|view|temp|temporary|if|top|using|natural|except|intersect|fetch|first|next|rows|only|int|integer|varchar|text|date|timestamp|numeric|decimal|boolean' || true)"
  for ident in $idents; do
    grep -n -w -- "$ident" "$SR_CUR" | while IFS= read -r hit; do
      local n="${hit%%:*}" text="${hit#*:}"
      printf '%s\n' "$changed" | grep -qx "$n" && continue
      printf '%s\tline %s\t%s\n' "$ident" "$n" "$text"
    done
  done
  return 0
}

# ---------------------------------------------------------------------------------------------
cmd_move() {
  [ $# -eq 2 ] || usage
  sr_need_jq
  sr_require_root
  local oldrel newrel oldslug newslug f tmp
  oldrel="$(sr_relpath "$1")" || exit $?; newrel="$(sr_relpath "$2")" || exit $?
  sr_safe_sql "$oldrel"
  sr_safe_sql "$newrel"
  oldslug="$(sr_slug "$oldrel")"; newslug="$(sr_slug "$newrel")"
  [ -d "$SR_REVIEWS/$oldslug" ] || sr_die 2 "no review directory for '$oldrel' (slug $oldslug)"
  [ "$oldslug" = "$newslug" ] || [ ! -e "$SR_REVIEWS/$newslug" ] || sr_die 2 "reviews/$newslug/ already exists"
  sr_safe_slug "$oldslug"
  sr_safe_slug "$newslug"
  for f in review.json scope.json rebind-required; do
    sr_no_symlinks "$SR_REVIEWS/$oldslug/$f" || exit 2
    [ ! -d "$SR_REVIEWS/$oldslug/$f" ] || sr_die 2 "unexpected directory: $f"
  done
  [ "$oldslug" = "$newslug" ] || mv "$SR_REVIEWS/$oldslug" "$SR_REVIEWS/$newslug" || sr_die 2 "move failed"
  touch "$SR_REVIEWS/$newslug/rebind-required" || sr_die 2 "cannot mark stale"
  rm -f "$SR_REVIEWS/$newslug/review.md" "$SR_REVIEWS/$newslug/scope.md" || sr_die 2 "cannot remove stale renders"
  for f in review.json scope.json; do
    [ -f "$SR_REVIEWS/$newslug/$f" ] || continue
    tmp="$(mktemp "$SR_REVIEWS/$newslug/.move.XXXXXX")" || sr_die 2 "mktemp failed"
    jq --arg p "$newrel" --arg s "$newslug" '.sql_path = $p | .slug = $s' "$SR_REVIEWS/$newslug/$f" > "$tmp" && mv "$tmp" "$SR_REVIEWS/$newslug/$f" || { rm -f "$tmp"; sr_die 2 "rebind failed; review needs repair"; }
  done
  printf 'moved\t%s\t%s\t%s\n' "$oldslug" "$newslug" "$newrel"
}

# ---------------------------------------------------------------------------------------------
cmd_render() {
  [ $# -eq 2 ] || usage
  sr_need_jq
  sr_require_root
  local slug="$1" kind="$2" doc tpl cfg out rendered unknown
  case "$kind" in scope|review) ;; *) sr_die 2 "kind must be scope or review (got '$kind')" ;; esac
  sr_safe_slug "$slug"
  doc="$SR_REVIEWS/$slug/$kind.json"
  [ -f "$doc" ] || sr_die 2 "no such document: reviews/$slug/$kind.json"
  tpl="$SR_ROOT/$SR_DIR/templates/$kind.md"
  [ -f "$tpl" ] || sr_die 2 "template missing: $SR_DIR/templates/$kind.md ($SR_SETUP_HINT)"
  cfg="$SR_ROOT/$SR_DIR/config.json"
  [ -f "$cfg" ] || sr_die 2 "config missing: $SR_DIR/config.json ($SR_SETUP_HINT)"
  sr_no_symlinks "$doc" || exit 2
  cmd_check "$doc" >/dev/null || sr_die 4 "invalid document"
  out="$SR_REVIEWS/$slug/$kind.md"
  sr_no_symlinks "$out" || exit 2
  local vars
  vars="$(jq -c --slurpfile cfgs "$cfg" -f "$SR_SCRIPT_DIR/sqlreview-render.jq" "$doc")" || sr_die 2 "render failed for reviews/$slug/$kind.json"
  rendered="$(jq -r -n --rawfile tpl "$tpl" --argjson vars "$vars" \
    'reduce ($vars | keys[]) as $k ($tpl; gsub("\\{\\{\($k)\\}\\}"; $vars[$k]))')" || sr_die 2 "render failed for reviews/$slug/$kind.json"
  printf '%s\n' "$rendered" > "$out" || sr_die 2 "cannot write rendered report"
  unknown="$(grep -o '{{[A-Za-z0-9_]*}}' "$out" | sort -u || true)"
  if [ -n "$unknown" ]; then
    printf 'sqlreview: unknown placeholder(s) left in place: %s\n' "$(printf '%s' "$unknown" | tr '\n' ' ')" >&2
  fi
  printf 'rendered\t%s\n' "${out#"$SR_ROOT"/}"
}

# ---------------------------------------------------------------------------------------------
[ $# -ge 1 ] || usage
cmd="$1"; shift
case "$cmd" in
  init) cmd_init "$@" ;;
  status) cmd_status "$@" ;;
  slug) cmd_slug "$@" ;;
  check) cmd_check "$@" ;;
  publish) cmd_publish "$@" ;;
  roles) cmd_roles "$@" ;;
  fingerprint) cmd_fingerprint "$@" ;;
  snapshot) cmd_snapshot "$@" ;;
  delta) cmd_delta "$@" ;;
  impact) cmd_impact "$@" ;;
  move) cmd_move "$@" ;;
  render) cmd_render "$@" ;;
  -h|--help|help) usage ;;
  *) printf 'sqlreview: unknown command: %s\n' "$cmd" >&2; usage ;;
esac
