#!/usr/bin/env bash
# sqlreview.sh — the data-request plugin's shared helper. One entry point, subcommands below.
# Shared by /data-request:setup, :bootstrap, :analyse and :explain via
#   S="${CLAUDE_PLUGIN_ROOT}/skills/setup/scripts"; bash "$S/sqlreview.sh" <command> ...
# and by the plugin's hooks. Contract: docs/specs/2026-09-15-sql-review-plugin-design.md §4.
#
#   init [--diff] [--apply PATH...] [--json]   create .sqlreview/ from the bundled default (plus an empty
#                                              reviews/.gitkeep so git keeps reviews/); never overwrites
#   status [--json] [--verbose]                reviews and their state (--verbose: why invalid/missing, and the
#                                              move that migrates a legacy-encoded slug); exit 3 when not initialised
#                                              missing bundled templates: JSON missing_templates, else one stderr line
#   slug PATH                                  slug for a project path; exit 5 on a conflicting binding. Readable:
#                                              sql/cohort_pipeline/x.sql -> sql__cohort_pipeline__x; an existing
#                                              legacy-encoded reviews/sql__cohort%5Fpipeline__x/ is kept
#   check FILE | check --stdin                 validate a review/scope JSON; exit 4 with one violation per line
#   lint FILE                                  provisional confirmed wording or unlinked decision sources; exit 10 when any
#   lint --ste FILE                            STE wording in intent and item text/rationale, any status: one
#                                              "<id>\t<field>\t<rule>\t<detail>" line per hit; exit 10 when any
#   publish SLUG scope|review|lifts DRAFT             validate a staged copy, then atomically replace the final JSON
#   publish --reconfirm-all SLUG KIND DRAFT    same, but refuse any carried (carried_from_revision) confirmation
#   roles ENGINEER ANALYST                     update only the two confirmed role names in config.json
#   guard string-sql on|off                    set only guard.require_lift_for_string_sql in config.json
#   fingerprint SQL                            {sql_path, sql_sha256, sql_body_sha256, git_commit, git_dirty}
#   snapshot SLUG SQL                          verify final review SHA, retain history, advance source.sql
#   delta SLUG                                 body binding + full hashes; exit 0 full/header-only, 10 body change, 6 no baseline
#   carryover SLUG DRAFT                       review draft items matching confirmed, still-valid scope items (JSON)
#   intake FILE REVISION [DRAFT]              read analyst answers sidecar; optional collision-safe scope draft merge
#                                              missing FILE is a legacy no-op; invalid intake exits 4; never writes
#   carryforward SLUG scope|review DRAFT       draft items whose previous-revision confirmation may be carried (JSON)
#   impact SLUG                                heuristic: identifiers in the diff traced into unchanged lines
#   notes SQL [--against JSON]                 read-only: parse the query-builder >= 0.6.0 analysis-notes header
#                                              (leading /* assumptions: / limitations: */ block in the first GO batch,
#                                              before any -- @extract: marker) into JSON {present, lines,
#                                              assumptions, limitations: [{text, rationale, lines}]}; a limitation's
#                                              consequence becomes its rationale; absent detail -> null; no header
#                                              -> present false, exit 0. --against adds match {id, rationale_same}
#                                              (same list, same text) from a review/scope/draft JSON, else null.
#                                              Needs no .sqlreview/. Exit 4: malformed header, "line N: why" on stderr
#   move OLDPATH NEWPATH                       rebind a review directory after the SQL moved (to the readable slug)
#   move PATH PATH                             migrate a legacy-encoded slug to the readable one (no rebind needed)
#   move --slug OLDSLUG NEWPATH                rebind a legacy review whose slug no current path derives
#   render SLUG scope|review|lifts                   JSON + templates/<kind>.md -> reviews/SLUG/<kind>.md
#                                              (a missing templates/<kind>.md is first installed from the bundled default)
#
# Exit codes: 0 ok · 1 usage · 2 error · 3 not initialised · 4 invalid document or notes header · 5 slug conflict ·
# 6 no baseline · 10 differences found (init --diff / delta).
set -u
SR_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
# shellcheck source=sqlreview-lib.sh
. "$SR_SCRIPT_DIR/sqlreview-lib.sh"
SR_ASSETS="$SR_SCRIPT_DIR/../assets/sqlreview"

usage() {
  awk 'NR > 1 && !/^#/ { exit } NR > 1' "$0" | sed 's/^# \{0,1\}//' >&2
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
      case "$f" in config.json|templates/scope.md|templates/review.md|templates/lifts.md) ;; *) sr_die 2 "unknown bundled path: $f" ;; esac
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
    # Git does not track an empty directory: a placeholder keeps reviews/ in a committed .sqlreview/
    # (#379). It is project state, not a bundled default, so --diff/--apply never report it; every
    # reader of reviews/ iterates slug directories only.
    mkdir -p "$target/reviews" || sr_die 2 "cannot create reviews"
    [ -e "$target/reviews/.gitkeep" ] || : > "$target/reviews/.gitkeep" || sr_die 2 "cannot create reviews/.gitkeep"
    if [ "$json" = 1 ]; then
      jq -n --arg root "$root" --arg files "$files" '{root: $root, created: true, files: ($files | split("\n") + ["reviews/.gitkeep"])}'
    else
      printf 'created\t%s\n' "$target"
      for f in $files reviews/.gitkeep; do printf 'file\t%s\n' "$f"; done
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
  local json=0 verbose=0 d slug state reason migrate schema lifts rows="[]" f missing=""
  while [ $# -gt 0 ]; do
    case "$1" in --json) json=1 ;; --verbose) verbose=1 ;; *) usage ;; esac
    shift
  done
  sr_need_jq
  sr_require_root
  schema="$(jq -r '.schemaVersion // "?"' "$SR_ROOT/$SR_DIR/config.json" 2>/dev/null || echo '?')"
  # Bundled templates the project lacks (e.g. lifts.md in a project initialised before lifts, #349).
  for f in "$SR_ASSETS"/templates/*.md; do
    [ -f "$f" ] || continue
    f="templates/$(basename "$f")"
    [ -f "$SR_ROOT/$SR_DIR/$f" ] || missing="$missing${missing:+ }$f"
  done
  if [ -n "$missing" ] && [ "$json" = 0 ]; then
    printf 'sqlreview: missing bundled template(s): %s; render installs them automatically, or add them now with: sqlreview.sh init --apply %s\n' "$missing" "$missing" >&2
  fi
  if [ -d "$SR_REVIEWS" ]; then
    for d in "$SR_REVIEWS"/*/; do
      [ -d "$d" ] || continue
      slug="$(basename "$d")"
      IFS="$(printf '\t')" read -r state SR_SQL_PATH SR_REVISION <<EOF
$(sr_state "$slug")
EOF
      lifts="{}"
      if [ -f "$d/lifts.json" ]; then
        if cmd_check "$d/lifts.json" >/dev/null; then
          lifts="$(jq -c '.lifts | group_by(.status) | map({key: .[0].status, value: length}) | from_entries' "$d/lifts.json")"
        else lifts='{"invalid":true}'; fi
      fi
      reason="" migrate=""
      [ "$verbose" = 1 ] && reason="$(sr_state_reason "$slug" "$state")"
      # A legacy-encoded slug (#353) of the path it records can be migrated to the readable one.
      if [ "$verbose" = 1 ] && [ -n "$SR_SQL_PATH" ] &&
         [ "$(sr_slug_pair "$SR_SQL_PATH" | sed -n 2p)" = "$slug" ] && [ "$(sr_slug_new "$SR_SQL_PATH")" != "$slug" ]; then
        migrate="sqlreview.sh move '$SR_SQL_PATH' '$SR_SQL_PATH'"
      fi
      if [ "$json" = 1 ]; then
        rows="$(printf '%s' "$rows" | jq -c --arg slug "$slug" --arg state "$state" --arg sql "$SR_SQL_PATH" --arg rev "$SR_REVISION" --argjson lifts "$lifts" \
          --arg reason "$reason" --arg migrate "$migrate" --argjson verbose "$verbose" \
          '. + [{slug: $slug, state: $state, sql_path: $sql, revision: ($rev | tonumber? // null), lifts: $lifts}
                + (if $verbose == 1 then {reason: (if $reason == "" then null else $reason end),
                                          migrate: (if $migrate == "" then null else $migrate end)} else {} end)]')"
      else
        printf '%s\t%s\t%s\t%s\tlifts=%s' "$slug" "$state" "$SR_SQL_PATH" "$SR_REVISION" "$lifts"
        [ -z "$reason" ] || printf '\treason=%s' "$reason"
        [ -z "$migrate" ] || printf '\tmigrate=%s' "$migrate"
        printf '\n'
      fi
    done
  fi
  if [ "$json" = 1 ]; then
    printf '%s' "$rows" | jq --arg root "$SR_ROOT" --arg schema "$schema" --arg missing "$missing" \
      '{root: $root, schemaVersion: ($schema | tonumber? // $schema), reviews: .,
        counts: (group_by(.state) | map({key: .[0].state, value: length}) | from_entries | . + {total: (map(.) | add // 0)}),
        missing_templates: ($missing | split(" ") | map(select(. != ""))),
        missing_templates_fix: (if $missing == "" then null else "sqlreview.sh init --apply " + $missing end)}'
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
  elif [ -d "$SR_REVIEWS" ]; then
    # A legacy review (non-path-derived slug) bound to this path would otherwise be silently orphaned.
    for doc in "$SR_REVIEWS"/*/review.json "$SR_REVIEWS"/*/scope.json; do
      [ -f "$doc" ] && [ ! -L "$doc" ] || continue
      bound="$(basename "$(dirname "$doc")")"
      [ "$bound" != "$slug" ] && [ "$(jq -r '.sql_path // "" | strings' "$doc" 2>/dev/null)" = "$rel" ] || continue
      printf 'sqlreview: legacy review reviews/%s/ records sql_path %s; to keep its history run: sqlreview.sh move --slug %s %s\n' "$bound" "$rel" "$bound" "$rel" >&2
      break
    done
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
  out="$(jq -r -L "$SR_SCRIPT_DIR" -f "$SR_SCRIPT_DIR/sqlreview-check.jq" "$tmp" 2>&1)"; rc=$?
  rm -f "$tmp"
  if [ "$rc" -ne 0 ]; then printf 'check failed to run: %s\n' "$out"; return 4; fi
  if [ -n "$out" ]; then printf '%s\n' "$out"; return 4; fi
  printf 'ok\n'
  return 0
}

# ---------------------------------------------------------------------------------------------
# Advisory, not part of check: a confirmed item whose text or rationale still reads as a proposal
# contradicts its confirmation (#340), or decision provenance lacks a written source (#434). Prints "<id>\t<field>\t<phrases>" per hit; exit 10 when any.
# --ste (#394) checks STE wording instead, whatever the status, so it can run on candidates before
# the human is asked: intent, and each assumption/limitation text and rationale. One
# "<id>\t<field>\t<rule>\t<detail>" line per hit (id "-" for intent); exit 10 when any. Rules:
#   sentence-length  a sentence of more than 25 words (the STE limit for descriptive text);
#                    detail = its word count. A backtick span or quoted literal counts as one word;
#                    a hyphenated term is one word; "e.g."/"i.e." do not end a sentence.
#   contraction      n't, 're, 've, 'll, 'd, 'm, and 's after a pronoun (not a possessive); detail = the words
#   semicolon        detail = how many
#   abbreviation     e.g. / i.e.; detail = which
# --ste uses four columns, including decision-source warnings; plain lint keeps three columns.
cmd_lint() {
  local ste=0
  if [ "${1:-}" = "--ste" ]; then ste=1; shift; fi
  [ $# -eq 1 ] || usage
  case "$1" in -*) usage ;; esac
  sr_need_jq
  [ -f "$1" ] || sr_die 2 "no such file: $1"
  local out
  if [ "$ste" = 1 ]; then
    out="$(jq -r '
      def words: [splits("\\s+") | select(test("[[:alnum:]]"))] | length;
      def sentences:
        gsub("`[^`]*`"; "CODE") | gsub("\"[^\"]*\""; "QUOTE") | gsub("\\b[eE]\\.[gG]\\."; "eg")
        | gsub("\\b[iI]\\.[eE]\\."; "ie")
        | [splits("[.!?]+[\"'"'"')\\]]*(\\s+|$)|\\n+")] | map(select(test("[[:alnum:]]")));
      def hits($id; $field):
        strings as $t
        | ($t | sentences[] | words | select(. > 25) | "\($id)\t\($field)\tsentence-length\t\(.)"),
          ([$t | match("\\b[A-Za-z]+n[\u0027\u2019]t\\b|\\b[A-Za-z]+[\u0027\u2019](re|ve|ll|d|m)\\b|\\b(it|that|there|what|here|he|she|who|where|how|let)[\u0027\u2019]s\\b"; "gi").string]
           | select(length > 0) | "\($id)\t\($field)\tcontraction\t\(join(", "))"),
          ([$t | match(";"; "g")] | length | select(. > 0) | "\($id)\t\($field)\tsemicolon\t\(.)"),
          ([$t | match("\\b[eE]\\.[gG]\\.?|\\b[iI]\\.[eE]\\.?"; "g").string | ascii_downcase | if endswith(".") then . else . + "." end]
           | unique | .[] | "\($id)\t\($field)\tabbreviation\t\(.)");
      (.intent // null | hits("-"; "intent")),
      ((.assumptions // [], .limitations // []) | if type == "array" then .[] else empty end
       | select(type == "object") | . as $item
       | ("text", "rationale") as $field | $item[$field] | hits($item.id // "?"; $field))
    ' "$1")" || sr_die 4 "invalid JSON: $1"
  else
  out="$(jq -r '
    ("should be confirmed|to be confirmed|needs? (to be )?confirm(ing|ed|ation)?|pending confirmation|awaiting confirmation|unconfirmed|\\bproposed\\b|\\btbc\\b") as $re
    | (.assumptions // [], .limitations // [])[]
    | select(type == "object" and .status == "confirmed") as $item
    | ("text", "rationale") as $field
    | ([($item[$field] // "" | strings) | match($re; "gi").string | ascii_downcase] | unique) as $hits
    | select($hits | length > 0)
    | "\($item.id // "?")\t\($field)\t\($hits | join(", "))"
  ' "$1")" || sr_die 4 "invalid JSON: $1"
  fi
  local decisions
  decisions="$(jq -L "$SR_SCRIPT_DIR" -r --argjson ste "$ste" '
    include "sqlreview-decision";
    decision_source_warnings
    | if $ste == 1 then "\(.id)\t\(.field)\tdecision-source\t\(.detail)"
      else "\(.id)\t\(.field)\t\(.detail)" end
  ' "$1")" || sr_die 4 "invalid JSON: $1"
  [ -n "$out" ] || [ -n "$decisions" ] || return 0
  [ -z "$out" ] || printf '%s\n' "$out"
  [ -z "$decisions" ] || printf '%s\n' "$decisions"
  return 10
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
    if length == 1 and (.[0] | type == "object" and (.schemaVersion == 1 or .schemaVersion == 2) and (.roles | type == "object"))
    then .[0] | .roles.engineer = $engineer | .roles.analyst = $analyst
    else error("expected one schema-1 or schema-2 configuration with a roles object") end
  ' "$config" > "$tmp" || sr_die 4 "invalid configuration; original preserved"
  mv "$tmp" "$config" || sr_die 2 "cannot update roles"
  printf 'updated\tconfig.json roles\n'
)

# ---------------------------------------------------------------------------------------------
# The experimental string-SQL lift guard (#379): set only guard.require_lift_for_string_sql, as
# roles does for the role names, so setup never patches config.json by hand.
cmd_guard() (
  [ $# -eq 2 ] && [ "$1" = string-sql ] || usage
  local value config tmp
  case "$2" in on) value=true ;; off) value=false ;; *) usage ;; esac
  sr_need_jq
  sr_require_root
  config="$SR_ROOT/$SR_DIR/config.json"
  sr_no_symlinks "$config" || exit 2
  [ -f "$config" ] || sr_die 2 "config.json is missing"
  tmp="$(mktemp "$SR_ROOT/$SR_DIR/.guard.XXXXXX")" || sr_die 2 "mktemp failed"
  trap 'rm -f "$tmp"' EXIT
  trap 'exit 2' HUP INT TERM
  jq -se --argjson v "$value" '
    if length == 1 and (.[0] | type == "object" and .schemaVersion == 2 and ((.guard // {}) | type == "object"))
    then .[0] | .guard = ((.guard // {}) + {require_lift_for_string_sql: $v})
    else error("expected one schema-2 configuration") end
  ' "$config" > "$tmp" || sr_die 4 "invalid configuration; original preserved"
  mv "$tmp" "$config" || sr_die 2 "cannot update guard"
  printf 'updated\tconfig.json guard.require_lift_for_string_sql=%s\n' "$value"
)

# ---------------------------------------------------------------------------------------------
cmd_publish() (
  local reconfirm_all=false
  if [ "${1:-}" = "--reconfirm-all" ]; then reconfirm_all=true; shift; fi
  [ $# -eq 3 ] || usage
  sr_need_jq
  sr_require_root
  local slug="$1" kind="$2" draft="$3" dest tmp rel previous
  sr_safe_slug "$slug"
  case "$kind" in scope|review|lifts) ;; *) usage ;; esac
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
  local bound_doc
  if bound_doc="$(sr_doc_for "$slug")"; then
    [ "$(jq -r .sql_path "$bound_doc")" = "$rel" ] || sr_die 5 "slug is bound to another pipeline path"
  fi
  previous=0
  if [ -f "$dest" ]; then
    cmd_check "$dest" >/dev/null || sr_die 4 "existing document is invalid"
    previous="$(jq -r .revision "$dest")"
  fi
  # Header history is helper-owned. A draft may retain it or omit it, never alter it.
  if jq -e 'has("header_revisions")' "$tmp" >/dev/null; then
    local history_doc=/dev/null
    [ ! -f "$dest" ] || history_doc="$dest"
    jq -e --slurpfile old "$history_doc" '.header_revisions == ($old[0].header_revisions // [])' "$tmp" >/dev/null || sr_die 4 "header_revisions is helper-owned; retain or omit the published history"
  fi
  if [ -f "$dest" ] && jq -e 'has("header_revisions")' "$dest" >/dev/null; then
    local inherited
    inherited="$(jq --slurpfile old "$dest" '.header_revisions = $old[0].header_revisions' "$tmp")" || sr_die 2 "cannot preserve header history"
    printf '%s\n' "$inherited" > "$tmp"
  fi
  if [ "$kind" = review ] || { [ "$kind" = scope ] && jq -e '.sql_sha256 | type == "string"' "$tmp" >/dev/null; }; then
    [ -f "$SR_ROOT/$rel" ] || sr_die 2 "scope records sql_sha256 but the SQL is missing: $rel (no such SQL)"
    local baseline="$SR_REVIEWS/$slug/source.sql" binding
    [ "$kind" != scope ] || baseline="$SR_REVIEWS/$slug/scope.source.sql"
    sr_no_symlinks "$baseline" || exit 2
    if [ -f "$baseline" ] && [ -f "$dest" ] && [ "$(sr_sha256 "$SR_ROOT/$rel")" != "$(jq -r .sql_sha256 "$tmp")" ]; then
      [ "$(sr_sha256 "$baseline")" = "$(jq -r .sql_sha256 "$dest")" ] || sr_die 2 "published baseline is corrupt; reassess before publishing"
    fi
    # A fresh confirmed body revision has a new full fingerprint; the previous baseline
    # remains evidence for carry checks, rather than evidence for the new fingerprint.
    if [ -f "$baseline" ] && [ "$(sr_sha256 "$baseline")" != "$(jq -r .sql_sha256 "$tmp")" ]; then baseline=/dev/null; fi
    sr_binding "$tmp" "$SR_ROOT/$rel" "$baseline"; binding=$?
    case "$binding" in
      0) ;;
      10)
        if [ "$kind" = scope ] && [ -f "$dest" ]; then
          # Republishing a saved scope needs its original authenticated bytes, not just
          # a claimed body digest. A fresh full-fingerprint reassessment takes case 0.
          [ -f "$baseline" ] || sr_die 2 "header-only scope publication requires an authenticated original scope baseline; recover scope.source.sql or reassess"
        fi
        local amended
        amended="$(jq --arg sha "$(sr_sha256 "$SR_ROOT/$rel")" --arg at "$(sr_now)" --arg body "$(sr_body_sha256 "$SR_ROOT/$rel")" '
          .header_revisions = ((.header_revisions // []) +
            (if any((.header_revisions // [])[]; .sql_sha256 == $sha) then []
             else [{sql_sha256: $sha, sql_body_sha256: $body, revision: .revision, at: $at}] end))' "$tmp")" || sr_die 2 "cannot record header revision"
        printf '%s\n' "$amended" > "$tmp"
        ;;
      *) sr_die 2 "SQL changed since fingerprint or baseline is corrupt; reassess before publishing; re-put intent, inputs, outputs and affected items, then refresh sql_sha256" ;;
    esac
  fi
  if [ -f "$dest" ] && cmp -s "$tmp" "$dest"; then
    printf 'already published\t%s\n' "${dest#"$SR_ROOT"/}"
    exit 0
  fi
  if [ "$kind" != lifts ] && [ "${binding:-}" = 10 ] && [ -f "$dest" ] && jq -e --slurpfile old "$dest" '
    del(.header_revisions) == ($old[0] | del(.header_revisions))' "$tmp" >/dev/null; then
    mv "$tmp" "$dest" || sr_die 2 "cannot publish header revision"
    printf 'published header revision\t%s\n' "${dest#"$SR_ROOT"/}"
    exit 0
  fi
  jq -e --argjson previous "$previous" '.revision == ($previous + 1)' "$tmp" >/dev/null || sr_die 4 "revision must follow the existing document (first revision is 1)"
  if [ "$kind" != lifts ]; then
    # A carried confirmation must be provable from the previous revision and its SQL baseline (#348).
    local violations
    _carry_context "$slug" "$kind" "$rel"
    violations="$(_carry_jq "$tmp" 'carry_violations($ctx; $reconfirm_all)' --argjson reconfirm_all "$reconfirm_all")" || sr_die 2 "carry-forward check failed to run"
    if [ -n "$violations" ]; then printf '%s\n' "$violations"; sr_die 4 "carried confirmations refused; re-confirm those items for this revision"; fi
  fi
  if [ "$kind" = lifts ] && [ ! -f "$dest" ]; then
    jq -e 'all(.lifts[]; .revision == 1 and .status == "candidate")' "$tmp" >/dev/null || sr_die 4 "new ledger entries start as candidates"
  fi
  if [ "$kind" = lifts ] && [ -f "$dest" ]; then
    # Entry revisions let silent capture append candidates without refreshing human answers.
    jq -e --slurpfile old "$dest" '
      def rank: ["candidate", "confirmed", "filed", "released", "recomposed"] as $states | . as $s | $states | index($s);
      all(.lifts[]; . as $new |
        ([$old[0].lifts[] | select(.id == $new.id)][0]) as $prior |
        if $prior == null then .revision == 1 and .status == "candidate"
        else
          if (.status | rank) < ($prior.status | rank) or (.status | rank) > (($prior.status | rank) + 1) then false
          else (del(.status,.issue_url,.confirmed_by,.confirmed_at,.confirmed_revision,.revision,.release_evidence,.recomposition_evidence) ==
            ($prior | del(.status,.issue_url,.confirmed_by,.confirmed_at,.confirmed_revision,.revision,.release_evidence,.recomposition_evidence))) as $same |
          if $same then .revision == $prior.revision
          else .revision == ($prior.revision + 1) end end
        end)
    ' "$tmp" >/dev/null || sr_die 4 "lift entry revision must match its evidence; new entries start as candidates"
  fi
  if [ "$kind" = review ] && jq -e 'any(.limitations[]; has("lift_id"))' "$tmp" >/dev/null; then
    local ledger="$SR_REVIEWS/$slug/lifts.json"
    sr_no_symlinks "$ledger" || exit 2
    cmd_check "$ledger" >/dev/null || sr_die 4 "linked limitations require a valid lift ledger"
    jq -e --slurpfile ledger "$ledger" '
      all(.limitations[] | select(has("lift_id")); . as $lim |
        [$ledger[0].lifts[] | select(.id == $lim.lift_id and
          (.status == "filed" or .status == "released" or .status == "recomposed"))] as $entries |
        ($entries | length) == 1 and
        $lim.text == ($entries[0].need + " resolved with in-repo SQL. Library unit tracked in " + $entries[0].issue_url + ". Not backported."))
    ' "$tmp" >/dev/null || sr_die 4 "lift limitation wording must match its ledger entry"
  fi
  if [ "$kind" = lifts ] && [ -f "$dest" ]; then
    local history="$SR_REVIEWS/$slug/history/lifts/$previous.json"
    sr_no_symlinks "$history" || exit 2
    mkdir -p "$(dirname "$history")" || sr_die 2 "cannot create lift history"
    if [ -e "$history" ]; then
      cmp -s "$dest" "$history" || sr_die 2 "lift history conflict"
    else cp "$dest" "$history" || sr_die 2 "cannot retain lift history"; fi
  fi
  mv "$tmp" "$dest" || sr_die 2 "cannot publish document"
  printf 'published\t%s\n' "${dest#"$SR_ROOT"/}"
)

# ---------------------------------------------------------------------------------------------
cmd_fingerprint() {
  [ $# -eq 1 ] || usage
  sr_need_jq
  sr_require_root
  local rel abs sha body="" commit="" dirty=false
  rel="$(sr_relpath "$1")" || exit $?
  sr_safe_sql "$rel"
  abs="$SR_ROOT/$rel"
  [ -f "$abs" ] || sr_die 2 "no such file: $rel"
  sha="$(sr_sha256 "$abs")"
  body="$(sr_body_sha256 "$abs" || true)"
  if git -C "$SR_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    commit="$(git -C "$SR_ROOT" rev-parse HEAD 2>/dev/null || true)"
    [ -n "$(git -C "$SR_ROOT" status --porcelain --untracked-files=all -- "$rel" 2>/dev/null)" ] && dirty=true
  fi
  jq -n --arg p "$rel" --arg sha "$sha" --arg body "$body" --arg c "$commit" --argjson dirty "$dirty" \
    '{sql_path: $p, sql_sha256: $sha, sql_body_sha256: (if $body == "" then null else $body end), git_commit: (if $c == "" then null else $c end), git_dirty: $dirty}'
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
  local binding
  local baseline="$SR_REVIEWS/$slug/source.sql"
  [ "$sha" != "$(jq -r .sql_sha256 "$doc")" ] || baseline=/dev/null
  sr_binding "$doc" "$tmp" "$baseline"; binding=$?
  if [ "$binding" = 10 ] && [ -f "$SR_REVIEWS/$slug/source.sql" ]; then
    # Retain the authenticated bytes that were reviewed, never replace them with a body match.
    cp "$SR_REVIEWS/$slug/source.sql" "$tmp" || { rm -f "$tmp"; sr_die 2 "baseline copy failed"; }
    sha="$(sr_sha256 "$tmp")"
  elif [ "$binding" != 0 ]; then
    rm -f "$tmp"; sr_die 2 "SQL changed since fingerprint; reassess before snapshot (header-only requires an authenticated original baseline)"
  fi
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
  [ -f "$SR_BASE" ] || sr_die 6 "no baseline: reviews/$slug/source.sql is missing, so there is nothing to diff against — run a full /data-request:analyse (it records the snapshot)"
  [ -f "$SR_CUR" ] || sr_die 2 "the reviewed SQL no longer exists: $SR_SQL_PATH (moved? see: sqlreview.sh move)"
  [ ! -f "$SR_REVIEWS/$slug/rebind-required" ] || return 10
  local binding
  sr_binding "$doc" "$SR_CUR" "$SR_BASE"; binding=$?
  [ "$binding" = 10 ] && { printf 'header-only revision; SQL body unchanged\n'; return 0; }
  [ "$binding" = 0 ] && return 0
  return 10
}

cmd_delta() {
  [ $# -eq 1 ] || usage
  local rc
  _delta_prepare "$1"; rc=$?
  printf 'baseline_sha256=%s current_sha256=%s sql_path=%s\n' "$(sr_sha256 "$SR_BASE")" "$(sr_sha256 "$SR_CUR")" "$SR_SQL_PATH"
  if [ "$rc" -eq 0 ] && cmp -s "$SR_BASE" "$SR_CUR"; then
    printf 'unchanged since the reviewed snapshot\n'; return 0
  fi
  local diff_rc
  diff -u -L "reviewed (reviews/$1/source.sql)" -L "current ($SR_SQL_PATH)" "$SR_BASE" "$SR_CUR"; diff_rc=$?
  [ "$diff_rc" -le 1 ] || sr_die 2 "cannot diff the reviewed snapshot against current SQL"
  return "$rc"
}

cmd_impact() {
  [ $# -eq 1 ] || usage
  local rc changed idents ident
  _delta_prepare "$1"; rc=$?
  if [ "$rc" -eq 0 ]; then
    if cmp -s "$SR_BASE" "$SR_CUR"; then
      printf 'no change since the reviewed snapshot; nothing to trace\n'
    else
      printf 'no SQL body change since the reviewed snapshot; nothing to trace\n'
    fi
    return 0
  fi
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
# Which review-draft items restate a confirmed item of the current scope revision (same list, same
# text and rationale). Analyse offers each list as one bulk confirmation (#346); the basis says why.
# carry_over: the SQL under the item did not change since scope publish
#   sql-unchanged       the whole SQL is unchanged (SHA)
#   sql-body-unchanged  only the leading comment header changed, e.g. the scope copied into the SQL
#                       header (#366, sr_body_start); the rest of the file is byte-identical
#   lines-unchanged     the draft item's location lines are unchanged
# carry_over_intent: the SQL changed (or did not exist) under an unchanged scope statement (#366)
#   scope-before-sql    the scope was confirmed before the SQL existed (sql_sha256 null, no baseline)
#   intent-unchanged    the SQL changed, but the scope item has no location: it states intent
# Every other matching item is walked, as is every new or reworded item.
cmd_intake() {
  [ $# -eq 2 ] || [ $# -eq 3 ] || usage
  sr_need_jq
  case "$2" in ''|*[!0-9]*|0) sr_die 1 "revision must be an integer >= 1" ;; esac
  if [ ! -e "$1" ]; then
    if [ $# -eq 3 ]; then cat "$3"; return $?; fi
    printf '%s\n' '{"present":false,"assumptions":[],"analyst_questions":[]}'
    return 0
  fi
  [ -f "$1" ] || sr_die 4 "intake must be a regular JSON file"
  local out
  out="$(jq -se --arg source "$1" --argjson revision "$2" '
    if length == 1 then .[0] else error("expected one intake object") end
  ' "$1" 2>/dev/null | jq --arg source "$1" --argjson revision "$2" -f "$SR_SCRIPT_DIR/sqlreview-intake.jq" 2>/dev/null)" || sr_die 4 "invalid analyst intake; run validate-answers and correct the sidecar"
  [ -n "$out" ] || sr_die 4 "invalid analyst intake; expected one JSON object"
  if [ $# -eq 3 ]; then
    printf '%s\n' "$out" | jq --slurpfile drafts "$3" --argjson revision "$2" '
      . as $intake | $drafts[0] as $d |
      if ($drafts | length) != 1 or $d.kind != "scope" or $d.revision != $revision or
         ($d.assumptions | type) != "array" or ($d.open_questions | type) != "array" or
         ($d.approval_number != null and $d.approval_number != $intake.approval_number) or
         ($d.assumptions | any(.[]; .upstream.source == "analyst-intake" and
           .upstream.approval_number != $intake.approval_number)) or
         ($d | has("intake_questions") and (.intake_questions | type != "array" or
           (all(.[]; type == "string" and startswith("Analyst question: ")) | not))) or
         ($d.assumptions | map(.id) | length != (unique | length)) then
        error("invalid scope draft or mismatched approval/revision")
      else
        reduce $intake.assumptions[] as $item ($d;
          [.assumptions[] | select(.id == $item.id)] as $matches |
          if ($matches | length) == 0 then .assumptions += [$item]
          elif ($matches[0] | {text, rationale, location, confirmed_by, confirmed_at, upstream, decided}) ==
               ($item | {text, rationale, location, confirmed_by, confirmed_at, upstream, decided}) then .
          else error("intake ID collision or changed analyst answer; ask analyst") end)
        # Only replace questions owned by the previous sidecar import. Independently
        # raised research gaps also use the prefix and must not disappear on refresh.
        | ($d.open_questions - ($d.intake_questions // [])) as $manual
        | .open_questions = ($manual + $intake.analyst_questions | unique)
        | .intake_questions = ($intake.analyst_questions - $manual | unique)
      end
    ' 2>/dev/null || sr_die 4 "cannot merge intake: invalid draft, collision, changed answer or mismatched approval/revision"
  else
    printf '%s\n' "$out"
  fi
}

cmd_carryover() {
  [ $# -eq 2 ] || usage
  sr_need_jq
  sr_require_root
  local slug="$1" draft="$2" scope base sql cur scope_sha="" base_sha="" cur_sha="" have_base=false
  local body_same=false before_sql=false
  sr_safe_slug "$slug"
  [ -f "$draft" ] || sr_die 2 "no such draft: $draft"
  jq -e 'type == "object"' "$draft" >/dev/null 2>&1 || sr_die 4 "invalid JSON: $draft"
  scope="$SR_REVIEWS/$slug/scope.json"
  base="$SR_REVIEWS/$slug/scope.source.sql"
  sr_no_symlinks "$scope" || exit 2
  sr_no_symlinks "$base" || exit 2
  if [ -f "$scope" ]; then
    cmd_check "$scope" >/dev/null || sr_die 4 "scope.json is invalid; see sqlreview.sh check"
    sql="$(jq -r .sql_path "$scope")"
    scope_sha="$(jq -r '.sql_sha256 // "" | strings' "$scope")"
  else
    scope=/dev/null  # nothing to carry over: every draft item is walked
    sql="$(jq -r '.sql_path // "" | strings' "$draft")"
  fi
  if [ -n "$sql" ]; then
    sr_safe_sql "$sql"
    cur="$SR_ROOT/$sql"
    [ -f "$cur" ] && cur_sha="$(sr_sha256 "$cur")"
  fi
  if [ "$scope" != /dev/null ] && [ -f "$base" ]; then
    base_sha="$(sr_sha256 "$base")"
    # A baseline that disagrees with the SHA the scope recorded is not evidence of anything.
    if [ -z "$scope_sha" ] || [ "$scope_sha" = "$base_sha" ]; then have_base=true; scope_sha="$base_sha"; fi
  fi
  # Scope-first: framed and confirmed before any SQL existed, so there is no SQL to compare with.
  if [ "$scope" != /dev/null ] && [ -z "$scope_sha" ] && [ ! -f "$base" ]; then before_sql=true; fi
  if [ "$have_base" = true ] && [ -n "$cur_sha" ] && sr_body_same "$base" "$cur"; then body_same=true; fi
  jq -n --slurpfile scope "$scope" --slurpfile draft "$draft" \
    --rawfile base "$([ "$have_base" = true ] && echo "$base" || echo /dev/null)" \
    --rawfile cur "$([ -n "$cur_sha" ] && echo "$cur" || echo /dev/null)" \
    --argjson have_base "$have_base" --arg scope_sha "$scope_sha" --arg cur_sha "$cur_sha" \
    --argjson body_same "$body_same" --argjson before_sql "$before_sql" '
    ($scope[0] // {revision: null, assumptions: [], limitations: []}) as $s | ($draft[0]) as $d
    | ($scope_sha != "" and $cur_sha != "" and $scope_sha == $cur_sha) as $unchanged
    | ($unchanged or $body_same) as $body
    | ($base | split("\n")) as $b | ($cur | split("\n")) as $c
    | def lines_same($l): $have_base and $cur_sha != "" and ($l | type) == "array" and ($l | length) == 2 and
        ($l | all(type == "number" and . >= 1)) and $l[0] <= $l[1] and $l[1] <= ($b | length) and $l[1] <= ($c | length) and $b[$l[0] - 1:$l[1]] == $c[$l[0] - 1:$l[1]];
    [ ("assumptions", "limitations") as $k | ($d[$k] // [])[] | select(type == "object") | . as $i
      | ([$s[$k][] | select(.text == $i.text and .rationale == $i.rationale and .decided == $i.decided)][0]) as $m
      | {kind: $k, id: $i.id, text: $i.text, rationale: $i.rationale, location: $i.location}
        + (if $i | has("decided") then {decided: $i.decided} else {} end)
        + if $m == null then {basis: null, why: "new, or text/rationale/decided provenance differs from the scope"}
          elif $unchanged then {scope_id: $m.id, basis: "sql-unchanged"}
          elif $body then {scope_id: $m.id, basis: "sql-body-unchanged"}
          elif lines_same(($i.location | objects | .lines) // null) then {scope_id: $m.id, basis: "lines-unchanged"}
          elif $before_sql then {scope_id: $m.id, basis: "scope-before-sql"}
          elif $m.location == null then {scope_id: $m.id, basis: "intent-unchanged"}
          else {scope_id: $m.id, basis: null, why: "SQL changed since scope publish, scope item \($m.id) has a location, and the lines at the draft location differ between the scope baseline and the current SQL"} end
    ] as $rows
    | {scope_revision: $s.revision, sql_unchanged: $unchanged, sql_body_unchanged: $body,
       scope_before_sql: $before_sql,
       carry_over: [$rows[] | select(.basis == "sql-unchanged" or .basis == "sql-body-unchanged" or .basis == "lines-unchanged")],
       carry_over_intent: [$rows[] | select(.basis == "scope-before-sql" or .basis == "intent-unchanged")],
       walk: [$rows[] | select(.basis == null) | {kind, id, why}]}'
}

# ---------------------------------------------------------------------------------------------
# Evidence for carrying scope/review confirmations forward (#348), shared by publish and
# carryforward. The previous published <kind>.json is the prior revision; its baseline is the SQL
# bytes recorded after that publish (analyse: snapshot → source.sql; bootstrap: scope.source.sql),
# counted only when its SHA256 equals the prior document's sql_sha256 (when it recorded one).
# Sets CF_KIND, CF_PRIOR, CF_BASE, CF_CUR (a path or /dev/null), CF_HAVE_BASE, CF_HAVE_CUR, CF_PRIOR_SHA,
# CF_CUR_SHA and CF_BODY_SAME (baseline and current SQL differ at most in the leading comment header, #366).
_carry_context() { # <slug> <scope|review> <sql_path>
  local d="$SR_REVIEWS/$1" base_sha
  CF_KIND="$2" CF_PRIOR=/dev/null CF_CUR=/dev/null CF_HAVE_BASE=false CF_HAVE_CUR=false CF_PRIOR_SHA="" CF_CUR_SHA=""
  CF_BODY_SAME=false
  if [ "$2" = review ]; then CF_BASE="$d/source.sql"; else CF_BASE="$d/scope.source.sql"; fi
  sr_no_symlinks "$d/$2.json" || exit 2
  sr_no_symlinks "$CF_BASE" || exit 2
  if [ -f "$d/$2.json" ]; then
    cmd_check "$d/$2.json" >/dev/null || sr_die 4 "existing $2.json is invalid; see sqlreview.sh check"
    CF_PRIOR="$d/$2.json"
    CF_PRIOR_SHA="$(jq -r '.sql_sha256 // "" | strings' "$CF_PRIOR")"
  fi
  if [ -f "$SR_ROOT/$3" ]; then CF_CUR="$SR_ROOT/$3"; CF_HAVE_CUR=true; CF_CUR_SHA="$(sr_sha256 "$CF_CUR")"; fi
  if [ "$CF_PRIOR" != /dev/null ] && [ -f "$CF_BASE" ]; then
    base_sha="$(sr_sha256 "$CF_BASE")"
    if [ -z "$CF_PRIOR_SHA" ] || [ "$CF_PRIOR_SHA" = "$base_sha" ]; then CF_HAVE_BASE=true; CF_PRIOR_SHA="$base_sha"; fi
  fi
  [ "$CF_HAVE_BASE" = true ] || CF_BASE=/dev/null
  if [ "$CF_HAVE_BASE" = true ] && [ "$CF_HAVE_CUR" = true ] && sr_body_same "$CF_BASE" "$CF_CUR"; then CF_BODY_SAME=true; fi
}

# Run a jq filter over a draft with sqlreview-carry.jq included and $ctx bound (see its header).
_carry_jq() { # <draft> <filter> [jq options...]
  local draft="$1" filter="$2"
  shift 2
  jq -r -L "$SR_SCRIPT_DIR" "$@" --slurpfile prior "$CF_PRIOR" --rawfile base "$CF_BASE" --rawfile cur "$CF_CUR" \
    --argjson have_base "$CF_HAVE_BASE" --argjson have_cur "$CF_HAVE_CUR" --arg prior_sha "$CF_PRIOR_SHA" --arg cur_sha "$CF_CUR_SHA" \
    --argjson body_same "$CF_BODY_SAME" --arg cf_kind "$CF_KIND" \
    "include \"sqlreview-carry\";
     {kind: \$cf_kind, prior: \$prior[0], base: (if \$have_base then \$base else null end), cur: (if \$have_cur then \$cur else null end),
      prior_sha: \$prior_sha, cur_sha: \$cur_sha, body_unchanged: \$body_same} as \$ctx | $filter" "$draft"
}

# Which draft items may keep the confirmation of the previous published revision (#348). Read-only.
cmd_carryforward() {
  [ $# -eq 3 ] || usage
  sr_need_jq
  sr_require_root
  local slug="$1" kind="$2" draft="$3" sql
  sr_safe_slug "$slug"
  case "$kind" in scope|review) ;; *) usage ;; esac
  [ -f "$draft" ] || sr_die 2 "no such draft: $draft"
  jq -e 'type == "object"' "$draft" >/dev/null 2>&1 || sr_die 4 "invalid JSON: $draft"
  sql="$(jq -r '.sql_path // "" | strings' "$SR_REVIEWS/$slug/$kind.json" 2>/dev/null)"
  [ -n "$sql" ] || sql="$(jq -r '.sql_path // "" | strings' "$draft")"
  sr_safe_sql "$sql"
  _carry_context "$slug" "$kind" "$sql"
  _carry_jq "$draft" 'carry_rows($ctx) as $rows
    | {document: $document, prior_revision: ($ctx.prior.revision // null),
       revision: (if $ctx.prior == null then 1 else $ctx.prior.revision + 1 end),
       sql_unchanged: ($ctx.prior_sha != "" and $ctx.prior_sha == $ctx.cur_sha),
       sql_body_unchanged: (($ctx.prior_sha != "" and $ctx.prior_sha == $ctx.cur_sha) or $ctx.body_unchanged),
       carry: [$rows[] | select(.basis != null) | {kind, id, basis, set}],
       bulk: [$rows[] | select(.basis == null and .bulk) | {kind, id, text, rationale, location, why}],
       walk: [$rows[] | select(.basis == null and (.bulk | not)) | {kind, id, why}]}' --arg document "$kind"
}

# ---------------------------------------------------------------------------------------------
# query-builder >= 0.6.0 renders record_assumption()/record_limitation() as a leading comment header
# (nq-rdl/query-builder docs/ANALYSIS_NOTES.md, #355). Read-only: the header is review *evidence*;
# analyse seeds candidates from it and the human still confirms every item.
# Search window: from the top of the file, skipping blank lines, `--` comments, SET/USE statements
# and other block comments; it ends at a `-- @extract:` marker, a GO line or any other statement.
# The header is a block whose `/*` and `*/` lines stand alone and whose first line is a section key.
_notes_scan() { # <sql file> → records separated by \037: H start end · I kind start end text has_detail detail · E line why
  awk '
    function rtrim(s) { sub(/[ \t\r]+$/, "", s); return s }
    function bad(n, why) { printf "E\037%d\037%s\n", n, why; err = 1; exit }
    function flush() {
      if (have) printf "I\037%s\037%d\037%d\037%s\037%d\037%s\n", sect, istart, iend, itext, hasd, dtext
      have = 0
    }
    BEGIN { st = "pre" }
    {
      line = rtrim($0)
      if (st == "open") st = (line == "assumptions:" || line == "limitations:") ? "hdr" : "other"
      if (st == "other") {        # a block comment that is not the header (e.g. a licence banner)
        p = index(line, "*/")
        if (p) { st = "pre"; if (substr(line, p + 2) ~ /[^ \t]/) exit }
        next
      }
      if (st == "hdr") {
        if (line == "*/") {
          if (!nitems) bad(sline, sect ": section is empty")
          flush(); printf "H\037%d\037%d\n", hstart, NR; st = "done"; exit
        }
        if (line == "") next
        if (line == "assumptions:" || line == "limitations:") {
          name = substr(line, 1, length(line) - 1)
          if (sect != "" && !nitems) bad(sline, sect ": section is empty")
          if (name == "assumptions" && (seen_a || seen_l)) bad(NR, "assumptions: must come before limitations: and appear once")
          if (name == "limitations" && seen_l) bad(NR, "limitations: must appear once")
          flush(); sect = name; sline = NR; nitems = 0
          if (name == "assumptions") seen_a = 1; else seen_l = 1
          next
        }
        if (line == "  -" || line ~ /^  - [ \t]*$/) bad(NR, "empty item text")
        if (substr(line, 1, 4) == "  - ") {
          flush(); have = 1; istart = NR; iend = NR; itext = substr(line, 5); hasd = 0; dtext = ""; nitems++
          next
        }
        if (line ~ /^    (rationale|consequence):/) {
          key = substr(line, 5); sub(/:.*/, "", key)
          want = (sect == "assumptions") ? "rationale" : "consequence"
          if (!have) bad(NR, key ": without an item above it")
          if (key != want) bad(NR, key ": is not valid under " sect ": (expected " want ":)")
          if (hasd) bad(NR, "second " key ": for one item")
          dtext = substr(line, 6 + length(key)); sub(/^[ \t]+/, "", dtext)
          if (dtext == "") bad(NR, "empty " key ":")
          hasd = 1; iend = NR
          next
        }
        bad(NR, "unexpected line in notes header: " line)
      }
      t = line; sub(/^[ \t]+/, "", t)
      if (t == "") next
      if (substr(t, 1, 2) == "--") { if (t ~ /^--[ \t]*@extract:/) exit; next }
      if (line == "/*") { st = "open"; hstart = NR; next }
      if (substr(t, 1, 2) == "/*") {
        p = index(substr(t, 3), "*/")
        if (!p) { st = "other"; next }
        if (substr(t, p + 4) ~ /[^ \t]/) exit
        next
      }
      if (tolower(t) ~ /^(set|use)[ \t]/) next
      exit                        # GO or executable SQL: the header can only precede them
    }
    END { if (!err && st == "hdr") printf "E\037%d\037%s\n", hstart, "unterminated notes header: no closing */ line" }
  ' "$1"
}

cmd_notes() {
  local sql="" against="" recs errs
  while [ $# -gt 0 ]; do
    case "$1" in
      --against) [ $# -ge 2 ] || usage; against="$2"; shift ;;
      -*) usage ;;
      *) [ -z "$sql" ] || usage; sql="$1" ;;
    esac
    shift
  done
  [ -n "$sql" ] || usage
  sr_need_jq
  [ -f "$sql" ] && [ -r "$sql" ] || sr_die 2 "no such readable file: $sql"
  if [ -n "$against" ]; then
    [ -f "$against" ] && [ -r "$against" ] || sr_die 2 "no such readable file: $against"
    jq -e 'type == "object"' "$against" >/dev/null 2>&1 || sr_die 4 "invalid JSON: $against"
  fi
  recs="$(_notes_scan "$sql")" || sr_die 2 "cannot read $sql"
  errs="$(printf '%s\n' "$recs" | awk 'BEGIN { FS = "\037" } $1 == "E" { printf "line %s: %s\n", $2, $3 }')"
  [ -z "$errs" ] || sr_die 4 "malformed analysis-notes header in $sql: $errs"
  printf '%s\n' "$recs" | jq -R -s --slurpfile against "${against:-/dev/null}" '
    (split("\n") | map(select(. != "") | split("\u001f"))) as $recs
    | ($against[0] // null) as $doc
    | ([$recs[] | select(.[0] == "H")][0]) as $h
    | def items($k): [$recs[] | select(.[0] == "I" and .[1] == $k)
        | {text: .[4], rationale: (if .[5] == "1" then .[6] else null end), lines: [(.[2] | tonumber), (.[3] | tonumber)]}
        | if $doc == null then . else . as $i
            | ([($doc[$k] // [] | arrays)[] | select(type == "object" and .text == $i.text)][0]) as $m
            | . + {match: (if $m == null then null else {id: $m.id, rationale_same: ($m.rationale == $i.rationale)} end)}
          end];
    {present: ($h != null), lines: (if $h == null then null else [($h[1] | tonumber), ($h[2] | tonumber)] end),
     assumptions: items("assumptions"), limitations: items("limitations")}'
}

# ---------------------------------------------------------------------------------------------
cmd_move() {
  sr_need_jq
  sr_require_root
  local oldrel="" newrel oldslug newslug f tmp rebind=1
  if [ "${1:-}" = "--slug" ]; then
    # Legacy reviews (e.g. schema 1 with a hand-chosen slug) are named by no current path.
    [ $# -eq 3 ] || usage
    oldslug="$2"
    newrel="$(sr_relpath "$3")" || exit $?
  else
    [ $# -eq 2 ] || usage
    oldrel="$(sr_relpath "$1")" || exit $?; newrel="$(sr_relpath "$2")" || exit $?
    sr_safe_sql "$oldrel"
    oldslug="$(sr_slug "$oldrel")"
  fi
  sr_safe_sql "$newrel"
  newslug="$(sr_slug_new "$newrel")"
  sr_safe_slug "$oldslug"
  sr_safe_slug "$newslug"
  [ -d "$SR_REVIEWS/$oldslug" ] || sr_die 2 "no review directory for '${oldrel:-$oldslug}' (slug $oldslug)"
  if [ "$oldrel" = "$newrel" ] && [ "$oldslug" = "$newslug" ]; then
    printf 'unchanged\t%s\t%s\n' "$newslug" "$newrel"
    printf 'sqlreview: reviews/%s/ already uses the readable slug for %s; nothing to move\n' "$newslug" "$newrel" >&2
    return 0
  fi
  [ "$oldslug" = "$newslug" ] || [ ! -e "$SR_REVIEWS/$newslug" ] || sr_die 2 "reviews/$newslug/ already exists"
  for f in review.json scope.json lifts.json rebind-required; do
    sr_no_symlinks "$SR_REVIEWS/$oldslug/$f" || exit 2
    [ ! -d "$SR_REVIEWS/$oldslug/$f" ] || sr_die 2 "unexpected directory: $f"
  done
  # Migrating a legacy-encoded slug to the readable one for the same path (#353) leaves the SQL
  # binding unchanged, so it does not force a re-analysis: no rebind-required marker.
  if [ "$oldslug" != "$newslug" ] && [ "$oldslug" = "$(sr_slug_pair "$newrel" | sed -n 2p)" ]; then
    rebind=0
    for f in review.json scope.json lifts.json; do
      [ -f "$SR_REVIEWS/$oldslug/$f" ] || continue
      [ "$(jq -r '.sql_path // "" | strings' "$SR_REVIEWS/$oldslug/$f" 2>/dev/null)" = "$newrel" ] || rebind=1
    done
  fi
  [ "$oldslug" = "$newslug" ] || mv "$SR_REVIEWS/$oldslug" "$SR_REVIEWS/$newslug" || sr_die 2 "move failed"
  [ "$rebind" = 0 ] || touch "$SR_REVIEWS/$newslug/rebind-required" || sr_die 2 "cannot mark stale"
  rm -f "$SR_REVIEWS/$newslug/review.md" "$SR_REVIEWS/$newslug/scope.md" "$SR_REVIEWS/$newslug/lifts.md" || sr_die 2 "cannot remove stale renders"
  for f in review.json scope.json lifts.json; do
    [ -f "$SR_REVIEWS/$newslug/$f" ] || continue
    tmp="$(mktemp "$SR_REVIEWS/$newslug/.move.XXXXXX")" || sr_die 2 "mktemp failed"
    jq --arg p "$newrel" --arg s "$newslug" '.sql_path = $p | .slug = $s' "$SR_REVIEWS/$newslug/$f" > "$tmp" && mv "$tmp" "$SR_REVIEWS/$newslug/$f" || { rm -f "$tmp"; sr_die 2 "rebind failed; review needs repair"; }
  done
  printf 'moved\t%s\t%s\t%s\n' "$oldslug" "$newslug" "$newrel"
}

# ---------------------------------------------------------------------------------------------
# Install the bundled templates/<kind>.md when the project lacks it (#349): never replaces an
# existing file, refuses symlink components, stages beside the target. Returns 1 when not bundled.
_render_install_template() { # <kind>
  local dir="$SR_ROOT/$SR_DIR/templates" src="$SR_ASSETS/templates/$1.md" tmp
  [ -f "$src" ] || return 1
  sr_no_symlinks "$dir/$1.md" || exit 2
  [ ! -e "$dir/$1.md" ] || sr_die 2 "template is not a regular file: $SR_DIR/templates/$1.md"
  mkdir -p "$dir" || sr_die 2 "cannot create $SR_DIR/templates"
  tmp="$(mktemp "$dir/.install.XXXXXX")" || sr_die 2 "mktemp failed"
  cp "$src" "$tmp" || { rm -f "$tmp"; sr_die 2 "cannot stage templates/$1.md"; }
  chmod 644 "$tmp" || { rm -f "$tmp"; sr_die 2 "cannot stage templates/$1.md"; }  # mktemp makes 0600; match init's copies
  # ln refuses an existing target, so a template that appeared meanwhile is kept; mv covers
  # filesystems without hard links.
  if ln "$tmp" "$dir/$1.md" 2>/dev/null || { [ ! -e "$dir/$1.md" ] && mv "$tmp" "$dir/$1.md"; }; then
    printf 'sqlreview: installed missing template %s/templates/%s.md from the bundled default\n' "$SR_DIR" "$1" >&2
  fi
  rm -f "$tmp"
  [ -f "$dir/$1.md" ] || sr_die 2 "cannot install $SR_DIR/templates/$1.md; run: sqlreview.sh init --apply templates/$1.md"
}

cmd_render() {
  [ $# -eq 2 ] || usage
  sr_need_jq
  sr_require_root
  local slug="$1" kind="$2" doc tpl cfg out rendered unknown
  case "$kind" in scope|review|lifts) ;; *) sr_die 2 "kind must be scope or review (got '$kind')" ;; esac
  sr_safe_slug "$slug"
  doc="$SR_REVIEWS/$slug/$kind.json"
  [ -f "$doc" ] || sr_die 2 "no such document: reviews/$slug/$kind.json"
  cfg="$SR_ROOT/$SR_DIR/config.json"
  [ -f "$cfg" ] || sr_die 2 "config missing: $SR_DIR/config.json ($SR_SETUP_HINT)"
  tpl="$SR_ROOT/$SR_DIR/templates/$kind.md"
  [ -f "$tpl" ] || _render_install_template "$kind" || sr_die 2 "template missing: $SR_DIR/templates/$kind.md ($SR_SETUP_HINT)"
  sr_no_symlinks "$doc" || exit 2
  cmd_check "$doc" >/dev/null || sr_die 4 "invalid document"
  out="$SR_REVIEWS/$slug/$kind.md"
  sr_no_symlinks "$out" || exit 2
  local vars
  vars="$(jq -c --slurpfile cfgs "$cfg" -f "$SR_SCRIPT_DIR/sqlreview-render.jq" "$doc")" || sr_die 2 "render failed for reviews/$slug/$kind.json"
  rendered="$(jq -r -n --rawfile tpl "$tpl" --argjson vars "$vars" \
    'reduce ($vars | keys[]) as $k ($tpl; gsub("\\{\\{\($k)\\}\\}"; $vars[$k]))')" || sr_die 2 "render failed for reviews/$slug/$kind.json"
  if jq -e '(.header_revisions // []) | length > 0' "$doc" >/dev/null; then
    rendered="$rendered

Header revision history: metadata changed without changing its corresponding SQL body; full-file header hashes and timestamps are recorded in $kind.json. Changed assumption text still requires confirmation."
  fi
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
  lint) cmd_lint "$@" ;;
  publish) cmd_publish "$@" ;;
  roles) cmd_roles "$@" ;;
  guard) cmd_guard "$@" ;;
  fingerprint) cmd_fingerprint "$@" ;;
  snapshot) cmd_snapshot "$@" ;;
  delta) cmd_delta "$@" ;;
  impact) cmd_impact "$@" ;;
  carryover) cmd_carryover "$@" ;;
  intake) cmd_intake "$@" ;;
  carryforward) cmd_carryforward "$@" ;;
  notes) cmd_notes "$@" ;;
  move) cmd_move "$@" ;;
  render) cmd_render "$@" ;;
  -h|--help|help) usage ;;
  *) printf 'sqlreview: unknown command: %s\n' "$cmd" >&2; usage ;;
esac
