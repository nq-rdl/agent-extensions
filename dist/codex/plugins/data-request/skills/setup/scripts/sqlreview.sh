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
#   ledger [--session] get TICKET [--against REVISIONS]  load one triage entry; optional selective recheck
#   ledger [--session] set TICKET ENTRY         validate, lock and atomically save .sqlreview/ledger.json
#                                              --session uses durable user state, never writes a child repository
#   ledger check FILE                          validate a schema-1 triage ledger store; no init required
#   lint FILE                                  prose code values (validated machine metadata exempt), provisional wording or
#                                              unlinked decision sources; three columns, exit 10 when any
#   lint --ste FILE                            also STE wording in intent and item text/rationale, any status: one
#                                              "<id>\t<field>\t<rule>\t<detail>" line per hit; exit 10 when any
#   publish SLUG scope|review|lifts DRAFT             validate a staged copy, then atomically replace the final JSON
#   publish --reconfirm-all SLUG KIND DRAFT    same, but refuse any carried (carried_from_revision) confirmation
#   roles ENGINEER ANALYST                     update only the two confirmed role names in config.json
#   guard string-sql on|off                    set only guard.require_lift_for_string_sql in config.json
#   lifts-stale SLUG --tag TAG                  read-only JSON nudges for units newly present at a stable library tag
#                                              uses authenticated gh GETs; unavailable evidence is unknown, never absent
#   fingerprint SQL                            fresh clean-HEAD render: hashes, commit, git_dirty:false, sql_provenance
#   materialize SLUG scope|review REVISION OUTPUT  authenticate exact revision into an external file; caller deletes it
#   snapshot SLUG SQL                          verify final review against committed renders; no SQL writes
#   delta SLUG [scope|review]                  body binding + full hashes; exit 0 full/header-only, 10 body change, 6 no baseline
#   carryover SLUG DRAFT                       review draft items matching confirmed, still-valid scope items (JSON)
#   intake FILE REVISION [DRAFT]              read analyst answers sidecar; optional collision-safe scope draft merge
#                                              missing FILE is a legacy no-op; invalid intake exits 4; never writes
#   carryforward SLUG scope|review DRAFT       draft items whose previous-revision confirmation may be carried (JSON)
#   remap SLUG [DRAFT]                         atomically remap unchanged location/logic ranges in a draft (JSON report)
#                                              default: review.draft.json, else scope.draft.json; seed from published JSON
#                                              changed/ambiguous ranges stay untouched in walk; never publish or confirm
#   impact SLUG                                heuristic: identifiers in the diff traced into unchanged lines
#   notes SQL [--against JSON] [--questions JSON] [--confirmed-by HANDLE]
#                                              read-only: parse the query-builder >= 0.6.0 analysis-notes header
#                                              (leading /* assumptions: / limitations: */ block in the first GO batch,
#                                              before any -- @extract: marker) into JSON {present, lines,
#                                              assumptions, limitations: [{text, rationale, lines}]}; a limitation's
#                                              consequence becomes its rationale; absent detail -> null; no header
#                                              -> present false, exit 0. --against adds match {id, rationale_same}
#                                              (same list, same text) from a review/scope/draft JSON, else null.
#                                              Scope --against adds scope_check: unmatched_header, rationale_differences,
#                                              and question_checks (all open scope-question/header pairs; NOT conflicts).
#                                              --questions selects a staged store; default: sibling questions.json, else
#                                              legacy projection. A declared missing store fails; stage fresh questions.
#                                              Review --against + explicit human HANDLE adds header_carry_over and
#                                              header_walk with git-source evidence; never sets confirmed_*.
#                                              Needs no .sqlreview/. Exit 4: malformed header, "line N: why" on stderr
#   move OLDPATH NEWPATH                       rebind a review directory after the SQL moved (to the readable slug)
#   move PATH PATH                             migrate a legacy-encoded slug to the readable one (no rebind needed)
#   move --slug OLDSLUG NEWPATH                rebind a legacy review whose slug no current path derives
#   questions SLUG [scope|review]                  read shared question store (legacy projection if unmigrated)
#   migrate-questions SLUG                         create stable IDs from legacy strings; no document edits
#   publish-questions SLUG DRAFT                   validate and atomically update only questions.json
#   render SLUG scope|review|lifts                   JSON + templates/<kind>.md -> reviews/SLUG/<kind>.md
#                                              (a missing templates/<kind>.md is first installed from the bundled default)
#
# Exit codes: 0 ok · 1 usage · 2 error · 3 not initialised · 4 invalid document or notes header · 5 slug conflict ·
# 6 no baseline · 10 differences found (init --diff / delta).
set -u
SR_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
# shellcheck source=sqlreview-lib.sh
. "$SR_SCRIPT_DIR/sqlreview-lib.sh"
. "$SR_SCRIPT_DIR/sqlreview-lifts.sh"
. "$SR_SCRIPT_DIR/sqlreview-questions.sh"
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

  # A ledger saved before setup is session state, not an initialized project.
  # Complete only that exact ledger-only tree; any other existing state stays report-only.
  local ledger_only=0
  if [ -f "$target/ledger.json" ] &&
     [ -z "$(find "$target" -mindepth 1 -maxdepth 1 ! -name ledger.json -print)" ]; then
    ledger_only=1
  fi
  if [ "$mode" = "create" ] && { [ ! -d "$target" ] || [ "$ledger_only" = 1 ]; }; then
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
  local json=0 verbose=0 d slug state reason migrate schema lifts rows="[]" f missing="" state_row
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
      state_row="$(sr_state "$slug")" || exit 2
      IFS="$(printf '\t')" read -r state SR_SQL_PATH SR_REVISION <<EOF
$state_row
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
  if jq -e '.kind == "questions"' "$tmp" >/dev/null; then
    out="$(jq -r -L "$SR_SCRIPT_DIR" 'include "sqlreview-questions"; question_errors' "$tmp" 2>&1)"; rc=$?
  else
    out="$(jq -r -L "$SR_SCRIPT_DIR" -f "$SR_SCRIPT_DIR/sqlreview-check.jq" "$tmp" 2>&1)"; rc=$?
  fi
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
# code-value (#439) checks string leaves in scopes/reviews/drafts at any status,
# including nested provenance and future fields, except validated known machine metadata:
# root SQL path/bound slug, SHA256/git fingerprints and known ISO timestamp locations.
# One warning per maximal run of 8 to 10 digits; never reword fingerprints or path bindings.
# Item = nearest id, else indexed object path (logic[0]), else "-"; field = relative leaf path.
# No matched value is printed; all lint diagnostics redact such runs, including ids/keys.
# --ste uses four columns, including decision-source/code-value warnings; plain lint keeps three
# columns (the third starts "code-value:" for this rule). This does not change check/publish.
cmd_lint() {
  local ste=0
  if [ "${1:-}" = "--ste" ]; then ste=1; shift; fi
  [ $# -eq 1 ] || usage
  case "$1" in -*) usage ;; esac
  sr_need_jq
  [ -f "$1" ] || sr_die 2 "no such file: $1"
  # jq runtime errors can quote malformed draft values. Suppress raw diagnostics;
  # the generic exit-4 error below is safe and keeps the existing failure contract.
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
    ' "$1" 2>/dev/null)" || sr_die 4 "invalid JSON: $1"
  else
  out="$(jq -r '
    ("should be confirmed|to be confirmed|needs? (to be )?confirm(ing|ed|ation)?|pending confirmation|awaiting confirmation|unconfirmed|\\bproposed\\b|\\btbc\\b") as $re
    | (.assumptions // [], .limitations // [])[]
    | select(type == "object" and .status == "confirmed") as $item
    | ("text", "rationale") as $field
    | ([($item[$field] // "" | strings) | match($re; "gi").string | ascii_downcase] | unique) as $hits
    | select($hits | length > 0)
    | "\($item.id // "?")\t\($field)\t\($hits | join(", "))"
  ' "$1" 2>/dev/null)" || sr_die 4 "invalid JSON: $1"
  fi
  local decisions
  decisions="$(jq -L "$SR_SCRIPT_DIR" -r --argjson ste "$ste" '
    include "sqlreview-decision";
    decision_source_warnings
    | if $ste == 1 then "\(.id)\t\(.field)\tdecision-source\t\(.detail)"
      else "\(.id)\t\(.field)\t\(.detail)" end
  ' "$1" 2>/dev/null)" || sr_die 4 "invalid JSON: $1"
  local codes
  codes="$(jq -L "$SR_SCRIPT_DIR" -r --argjson ste "$ste" '
    include "sqlreview-code-values";
    code_value_warnings
    | if $ste == 1 then "\(.id)\t\(.field)\tcode-value\t\(.detail)"
      else "\(.id)\t\(.field)\tcode-value: \(.detail)" end
  ' "$1" 2>/dev/null)" || sr_die 4 "invalid JSON: $1"
  [ -n "$out" ] || [ -n "$decisions" ] || [ -n "$codes" ] || return 0
  {
    [ -z "$out" ] || printf '%s\n' "$out"
    [ -z "$decisions" ] || printf '%s\n' "$decisions"
    [ -z "$codes" ] || printf '%s\n' "$codes"
  } | jq -L "$SR_SCRIPT_DIR" -Rr 'include "sqlreview-code-values"; code_value_redact' || sr_die 4 "lint redaction failed"
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

# Re-prove fresh header claims on every publish path, including header-only/idempotent returns.
_verify_header_decisions() ( # DOC SQL binding reconfirm-all
  local doc="$1" sql="$2" binding="$3" reconfirm_all="$4" actor notes proof="$1" tmp
  jq -e 'any((.assumptions[], .limitations[]); .carried_basis == "header-decision")' "$doc" >/dev/null || return 0
  [ "$(jq -r .kind "$doc")" = review ] && [ "$reconfirm_all" = false ] || sr_die 4 "header-decision basis requires a review carry-all answer"
  if [ "$binding" = 10 ]; then
    # The authenticated body binding permits the old full hash, but notes must inspect
    # current SQL. Refresh only the proof copy, never the published fingerprint/answers.
    tmp="$(mktemp -d)" || sr_die 2 "mktemp failed"
    trap 'rm -rf "$tmp"' EXIT
    trap 'exit 2' HUP INT TERM
    proof="$tmp/proof.json"
    jq --arg sha "$(sr_sha256 "$sql")" '.sql_sha256 = $sha' "$doc" > "$proof" || sr_die 2 "cannot stage header evidence"
  fi
  while IFS= read -r actor; do
    notes="$(cmd_notes "$sql" --against "$proof" --confirmed-by "$actor")" || sr_die 4 "cannot verify header-decision evidence"
    printf '%s' "$notes" | jq -e --slurpfile doc "$doc" --arg actor "$actor" '
      .header_carry_over as $rows | all(("assumptions", "limitations") as $k | $doc[0][$k][] |
        select(.carried_basis == "header-decision" and .confirmed_by == $actor) | {kind:$k, item:.};
        .kind as $k | .item as $item | any($rows[]; .kind == $k and .id == $item.id and .decided == $item.decided and .location == $item.location))' >/dev/null || sr_die 4 "header-decision evidence refused; walk the affected items"
  done < <(jq -r '[.assumptions[], .limitations[] | select(.carried_basis == "header-decision") | .confirmed_by] | unique[]' "$doc")
)

# ---------------------------------------------------------------------------------------------
cmd_publish() (
  local reconfirm_all=false
  if [ "${1:-}" = "--reconfirm-all" ]; then reconfirm_all=true; shift; fi
  [ $# -eq 3 ] || usage
  sr_need_jq
  sr_require_root
  local slug="$1" kind="$2" draft="$3" dest tmp rel previous work history="" history_tmp="" history_added=false committed=false
  local original_dest="" original_draft head="" current_sql="" header_only=false already=false proposed_sha=""
  sr_safe_slug "$slug"
  case "$kind" in scope|review|lifts) ;; *) usage ;; esac
  dest="$SR_REVIEWS/$slug/$kind.json"
  sr_no_symlinks "$dest" || exit 2
  [ ! -d "$dest" ] || sr_die 2 "publish destination is a directory"
  sr_no_symlinks "$(sr_abspath "$draft")" || exit 2
  [ -f "$draft" ] || sr_die 2 "no such draft: $draft"
  mkdir -p "$SR_REVIEWS/$slug" || sr_die 2 "cannot create review directory"
  tmp="$(mktemp "$SR_REVIEWS/$slug/.publish.XXXXXX")" || sr_die 2 "mktemp failed"
  umask 077
  work=""
  trap 'if [ "$history_added" = true ] && [ "$committed" = false ] && { [ ! -f "$dest" ] || [ "$(sr_sha256 "$dest" 2>/dev/null)" != "$proposed_sha" ]; }; then rm -f "$history"; fi; rm -f "$tmp"; [ -z "$history_tmp" ] || rm -f "$history_tmp"; [ -z "$work" ] || rm -rf "$work"' EXIT
  work="$(mktemp -d "${TMPDIR:-/tmp}/sqlreview-publish.XXXXXX")" || sr_die 2 "mktemp failed"
  trap 'exit 2' HUP INT TERM
  original_draft="$(sr_sha256 "$draft")"
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
    original_dest="$(sr_sha256 "$dest")"
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
    local binding current_mode current_prefix
    sr_source_clean || exit 2
    # Reconstruct and authenticate the original full bytes before considering a body match,
    # even when HEAD's full hash is identical. Legacy records use the same authentication.
    sr_source_auth "$tmp" "$work/recorded.sql" || exit $?
    sr_source_render HEAD "$rel" "$work/current.sql" || exit 2
    head="$SR_SOURCE_COMMIT"; current_mode="$SR_SOURCE_MODE"; current_prefix="$SR_SOURCE_PREFIX"
    current_sql="$work/current.sql"
    sr_binding "$tmp" "$current_sql" "$work/recorded.sql"; binding=$?
    case "$binding" in
      0) ;;
      10)
        local amended
        amended="$(jq --arg sha "$(sr_sha256 "$current_sql")" --arg at "$(sr_now)" --arg body "$(sr_body_sha256 "$current_sql")" \
          --arg commit "$head" --arg mode "$current_mode" --arg prefix "$current_prefix" '
          .header_revisions = ((.header_revisions // []) +
            (if any((.header_revisions // [])[]; .sql_sha256 == $sha and .git_commit == $commit) then []
             else [{sql_sha256: $sha, sql_body_sha256: $body, revision: .revision, at: $at,
               git_commit: $commit, git_dirty: false,
               sql_provenance: {mode: $mode, project_root: $prefix, commit: $commit}}] end))' "$tmp")" || sr_die 2 "cannot record header revision"
        printf '%s\n' "$amended" > "$tmp"
        ;;
      *) sr_die 2 "SQL changed since fingerprint; reassess before publishing; re-put intent, inputs, outputs and affected items, then refresh sql_sha256" ;;
    esac
  fi
  if [ "$kind" != lifts ]; then
    _verify_header_decisions "$tmp" "${current_sql:-$SR_ROOT/$rel}" "${binding:-0}" "$reconfirm_all" || exit $?
  fi
  if [ -f "$dest" ] && cmp -s "$tmp" "$dest"; then
    already=true
  fi
  if [ "$kind" != lifts ] && [ "${binding:-}" = 10 ] && [ -f "$dest" ] && jq -e --slurpfile old "$dest" '
    del(.header_revisions) == ($old[0] | del(.header_revisions))' "$tmp" >/dev/null; then
    header_only=true
  fi
  if [ "$header_only" = false ] && [ "$already" = false ]; then
    jq -e --argjson previous "$previous" '.revision == ($previous + 1)' "$tmp" >/dev/null || sr_die 4 "revision must follow the existing document (first revision is 1)"
    local needs_carry=false
    if [ "$kind" != lifts ]; then
      needs_carry="$(jq -r 'any((.assumptions[], .limitations[]); .carried_from_revision != null)' "$tmp")" || sr_die 2 "cannot inspect carried confirmations"
    fi
    if [ "$needs_carry" = true ]; then
      # A carried confirmation must be proved from the prior revision and its SQL.
      local violations
      _carry_context "$slug" "$kind" "$rel"
      violations="$(_carry_jq "$tmp" 'carry_violations($ctx; $reconfirm_all)' --argjson reconfirm_all "$reconfirm_all")" || sr_die 2 "carry-forward check failed to run"
      if [ -n "$violations" ]; then printf '%s\n' "$violations"; sr_die 4 "carried confirmations refused; re-confirm those items for this revision"; fi
    fi
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
  if [ -f "$dest" ] && [ "$header_only" = false ] && [ "$already" = false ]; then
    history="$SR_REVIEWS/$slug/history/$kind/$previous.json"
    sr_no_symlinks "$history" || exit 2
    [ ! -e "$history" ] || { [ -f "$history" ] && cmp -s "$dest" "$history"; } || sr_die 2 "$kind history conflict"
    mkdir -p "$(dirname "$history")" || sr_die 2 "cannot create $kind history"
    history_tmp="$(mktemp "$(dirname "$history")/.history.XXXXXX")" || sr_die 2 "cannot stage $kind history"
    cp "$dest" "$history_tmp" || sr_die 2 "cannot stage $kind history"
  fi
  # Refuse stale work after rendering and validation, before any history/final mutation.
  [ "$(sr_sha256 "$draft")" = "$original_draft" ] || sr_die 2 "draft changed during publication"
  sr_no_symlinks "$dest" || exit 2
  if [ -n "$original_dest" ]; then
    [ -f "$dest" ] && [ "$(sr_sha256 "$dest")" = "$original_dest" ] || sr_die 2 "published document changed during publication"
  else
    [ ! -e "$dest" ] || sr_die 2 "published document appeared during publication"
  fi
  if [ -n "$head" ]; then
    sr_source_clean || exit 2
    [ "$(git -C "$SR_ROOT" rev-parse --verify HEAD)" = "$head" ] || sr_die 2 "source commit changed during publication"
  fi
  if [ "$already" = true ]; then
    printf 'already published\t%s\n' "${dest#"$SR_ROOT"/}"
    exit 0
  fi
  proposed_sha="$(sr_sha256 "$tmp")"
  if [ -n "$history" ] && [ -e "$history" ]; then
    sr_no_symlinks "$history" || exit 2
    [ -f "$history" ] && cmp -s "$history_tmp" "$history" || sr_die 2 "$kind history changed during publication"
  fi
  if [ -n "$history" ] && [ ! -e "$history" ]; then
    mkdir -p "$(dirname "$history")" || sr_die 2 "cannot create $kind history"
    sr_no_symlinks "$history" || exit 2
    # Set rollback intent before the move so a trapped signal cannot leave history advanced.
    history_added=true
    mv "$history_tmp" "$history" || sr_die 2 "cannot retain $kind history"
  fi
  mv "$tmp" "$dest" || sr_die 2 "cannot publish document"
  committed=true
  printf 'published\t%s\n' "${dest#"$SR_ROOT"/}"
)

# ---------------------------------------------------------------------------------------------
cmd_fingerprint() (
  [ $# -eq 1 ] || usage
  sr_need_jq
  sr_require_root
  local rel sha body="" tmp
  rel="$(sr_relpath "$1")" || exit $?
  sr_safe_sql "$rel"
  sr_source_clean || exit 2
  umask 077
  tmp="$(mktemp -d "${TMPDIR:-/tmp}/sqlreview-fingerprint.XXXXXX")" || exit 2
  trap 'rm -rf "$tmp"' EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM HUP
  sr_source_render HEAD "$rel" "$tmp/render.sql" || exit 2
  sha="$(sr_sha256 "$tmp/render.sql")"
  body="$(sr_body_sha256 "$tmp/render.sql" || true)"
  jq -n --arg p "$rel" --arg sha "$sha" --arg body "$body" --arg c "$SR_SOURCE_COMMIT" \
    --arg mode "$SR_SOURCE_MODE" --arg prefix "$SR_SOURCE_PREFIX" \
    '{sql_path: $p, sql_sha256: $sha, sql_body_sha256: (if $body == "" then null else $body end), git_commit: $c, git_dirty: false,
      sql_provenance: {mode: $mode, project_root: $prefix, commit: $c}}'
)

# ---------------------------------------------------------------------------------------------
cmd_materialize() (
  [ $# -eq 4 ] || usage
  sr_need_jq
  sr_require_root
  local slug="$1" kind="$2" revision="$3" output doc current work staged=""
  sr_safe_slug "$slug"
  case "$kind" in scope|review) ;; *) usage ;; esac
  case "$revision" in ""|*[!0-9]*|0|0*) sr_die 2 "revision must be a positive integer" ;; esac
  case "$4" in /*) output="$(sr_normpath "$4")" ;; *) sr_die 2 "output must be absolute and outside the git tree" ;; esac
  sr_source_context || exit 2
  sr_no_symlinks "$output" || exit 2
  case "$output" in "$SR_SOURCE_TOP"|"$SR_SOURCE_TOP"/*) sr_die 2 "output must be outside the git tree" ;; esac
  [ ! -e "$output" ] || [ -f "$output" ] || sr_die 2 "output is not a regular file"
  current="$SR_REVIEWS/$slug/$kind.json"
  sr_no_symlinks "$current" || exit 2
  if [ -f "$current" ] && [ "$(jq -r '.revision' "$current")" = "$revision" ]; then doc="$current"
  else doc="$SR_REVIEWS/$slug/history/$kind/$revision.json"; fi
  sr_no_symlinks "$doc" || exit 2
  [ -f "$doc" ] || sr_die 6 "recorded $kind revision $revision unavailable"
  cmd_check "$doc" >/dev/null || sr_die 4 "invalid recorded $kind revision"
  jq -e --arg slug "$slug" --arg kind "$kind" --argjson revision "$revision" \
    '.slug == $slug and .kind == $kind and .revision == $revision' "$doc" >/dev/null || sr_die 4 "recorded revision identity differs"
  work="$(sr_source_workspace)" || exit 2
  trap '[ -z "$staged" ] || rm -f "$staged"; rm -rf "$work"' EXIT
  trap 'exit 2' HUP INT TERM
  cp "$doc" "$work/document.json" || exit 2
  sr_source_auth "$work/document.json" "$work/recorded.sql" || exit $?
  # Never truncate an existing output inode: an external hard link may share
  # that inode with an in-repository file. Stage a fresh sibling and rename it.
  umask 077
  staged="$(mktemp "$(dirname "$output")/.sqlreview-materialize.XXXXXX")" || sr_die 2 "cannot stage authenticated output"
  cp "$work/recorded.sql" "$staged" || sr_die 2 "cannot copy authenticated render to output"
  sr_no_symlinks "$output" || exit 2
  [ ! -e "$output" ] || [ -f "$output" ] || sr_die 2 "output is not a regular file"
  mv "$staged" "$output" || sr_die 2 "cannot publish authenticated output"
  staged=""
)

cmd_snapshot() (
  [ $# -eq 2 ] || usage
  sr_need_jq
  sr_require_root
  local slug="$1" rel doc work binding original head
  rel="$(sr_relpath "$2")" || exit $?
  sr_safe_sql "$rel"
  sr_safe_slug "$slug"
  [ "$slug" = "$(sr_slug "$rel")" ] || sr_die 2 "slug/path mismatch"
  doc="$SR_REVIEWS/$slug/review.json"
  sr_no_symlinks "$doc" || exit 2
  cmd_check "$doc" >/dev/null || sr_die 4 "write a validated review before snapshot verification"
  [ "$(jq -r .sql_path "$doc")" = "$rel" ] || sr_die 2 "review/path mismatch"
  sr_source_clean || exit 2
  umask 077
  work="$(mktemp -d "${TMPDIR:-/tmp}/sqlreview-verify.XXXXXX")" || sr_die 2 "mktemp failed"
  trap 'rm -rf "$work"' EXIT
  trap 'exit 2' HUP INT TERM
  original="$(sr_sha256 "$doc")"
  cp "$doc" "$work/review.json" || sr_die 2 "cannot stage review verification"
  sr_source_auth "$work/review.json" "$work/recorded.sql" || exit $?
  sr_source_render HEAD "$rel" "$work/current.sql" || exit 2
  head="$SR_SOURCE_COMMIT"
  sr_binding "$work/review.json" "$work/current.sql" "$work/recorded.sql"; binding=$?
  sr_no_symlinks "$doc" || exit 2
  [ "$(sr_sha256 "$doc")" = "$original" ] || sr_die 2 "published document changed during verification"
  sr_source_clean || exit 2
  [ "$(git -C "$SR_ROOT" rev-parse --verify HEAD)" = "$head" ] || sr_die 2 "source commit changed during verification"
  case "$binding" in
    0|10) printf 'verified\t%s\t%s\n' "$slug" "$(jq -r .sql_sha256 "$doc")" ;;
    *) sr_die 2 "SQL changed since fingerprint; reassess before snapshot verification" ;;
  esac
)

# ---------------------------------------------------------------------------------------------
# Shared by delta and impact: sets SR_BASE, SR_CUR, SR_SQL_PATH; returns 0 unchanged, 10 changed.
_delta_prepare() {
  local slug="$1" kind="${2:-}" doc
  sr_need_jq
  sr_require_root
  sr_safe_slug "$slug"
  [ -d "$SR_REVIEWS/$slug" ] || sr_die 2 "no review directory for slug '$slug'"
  if [ -n "$kind" ]; then
    case "$kind" in scope|review) ;; *) usage ;; esac
    doc="$SR_REVIEWS/$slug/$kind.json"
    sr_no_symlinks "$doc" || exit 2
    [ -f "$doc" ] || sr_die 6 "no published $kind source evidence"
  else
    doc="$(sr_doc_for "$slug")" || sr_die 2 "reviews/$slug/ has no review.json or scope.json"
  fi
  cmd_check "$doc" >/dev/null || sr_die 4 "invalid document"
  SR_SQL_PATH="$(jq -r '.sql_path // ""' "$doc")"
  sr_safe_sql "$SR_SQL_PATH"
  SR_BASE="$work/base.sql"
  SR_CUR="$work/current.sql"
  sr_source_auth "$doc" "$SR_BASE" || exit $?
  sr_source_clean || exit 2
  sr_source_render HEAD "$SR_SQL_PATH" "$SR_CUR" || exit 2
  local binding
  sr_binding "$doc" "$SR_CUR" "$SR_BASE"; binding=$?
  [ "$binding" = 10 ] && { printf 'header-only revision; SQL body unchanged\n'; return 0; }
  [ "$binding" = 0 ] && return 0
  return 10
}

cmd_delta() (
  [ $# -eq 1 ] || [ $# -eq 2 ] || usage
  local rc work
  case "${2:-}" in ""|scope|review) ;; *) usage ;; esac
  sr_require_root
  sr_safe_slug "$1"
  if [ -f "$SR_REVIEWS/$1/rebind-required" ]; then
    printf 'SQL path moved; binding requires reassessment before comparison\n'; return 10
  fi
  work="$(sr_source_workspace)" || exit 2
  trap 'rm -rf "$work"' EXIT
  trap 'exit 2' HUP INT TERM
  _delta_prepare "$@"; rc=$?
  printf 'baseline_sha256=%s current_sha256=%s sql_path=%s\n' "$(sr_sha256 "$SR_BASE")" "$(sr_sha256 "$SR_CUR")" "$SR_SQL_PATH"
  if [ "$rc" -eq 0 ] && cmp -s "$SR_BASE" "$SR_CUR"; then
    printf 'unchanged since the reviewed source\n'; return 0
  fi
  local diff_rc
  diff -u -L "reviewed ($1 recorded source)" -L "current ($SR_SQL_PATH)" "$SR_BASE" "$SR_CUR"; diff_rc=$?
  [ "$diff_rc" -le 1 ] || sr_die 2 "cannot diff the reviewed source against current SQL"
  return "$rc"
)

cmd_impact() (
  [ $# -eq 1 ] || usage
  local rc changed idents ident work diff_rc
  sr_require_root
  sr_safe_slug "$1"
  if [ -f "$SR_REVIEWS/$1/rebind-required" ]; then
    printf 'SQL path moved; binding requires reassessment before comparison\n'; return 10
  fi
  work="$(sr_source_workspace)" || exit 2
  trap 'rm -rf "$work"' EXIT
  trap 'exit 2' HUP INT TERM
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
  diff -u "$SR_BASE" "$SR_CUR" > "$work/diff"; diff_rc=$?
  [ "$diff_rc" -le 1 ] || sr_die 2 "cannot diff the reviewed source against current SQL"
  # Line numbers (in the current file) that belong to the diff hunks.
  changed="$(awk '
    /^@@/ { split($3, p, ","); n = substr(p[1], 2) + 0; next }
    /^\+\+\+/ || /^---/ { next }
    /^\+/ { print n; n++; next }
    /^-/ { next }
    { n++ }' "$work/diff")"
  # Identifiers on added/removed lines, minus SQL keywords and common functions.
  idents="$(awk '/^[+-]/ && !/^(\+\+\+|---)/' "$work/diff" | sed 's/^[+-]//' \
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
)

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

cmd_carryover() (
  [ $# -eq 2 ] || usage
  sr_need_jq
  sr_require_root
  local slug="$1" draft="$2" scope base sql cur scope_sha cur_sha have_base body_same before_sql work
  sr_safe_slug "$slug"
  [ -f "$draft" ] || sr_die 2 "no such draft: $draft"
  jq -e 'type == "object"' "$draft" >/dev/null 2>&1 || sr_die 4 "invalid JSON: $draft"
  sql="$(jq -r '.sql_path // "" | strings' "$draft")"
  sr_safe_sql "$sql"
  work="$(sr_source_workspace)" || exit 2
  trap 'rm -rf "$work"' EXIT
  trap 'exit 2' HUP INT TERM
  _carry_context "$slug" scope "$sql"
  scope="$CF_PRIOR" base="$CF_BASE" cur="$CF_CUR"
  scope_sha="$CF_PRIOR_SHA" cur_sha="$CF_CUR_SHA" have_base="$CF_HAVE_BASE"
  body_same="$CF_BODY_SAME" before_sql="$CF_PRIOR_ABSENT"
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
       walk: [$rows[] | select(.basis == null) | {kind, id, why}
              + (if has("decided") then {decided} else {} end)]}'
)

# ---------------------------------------------------------------------------------------------
# Evidence for carrying scope/review confirmations forward (#348), shared by publish and
# carryforward. The previous published <kind>.json is the prior revision; its immutable source
# is reconstructed and authenticated against the full recorded SHA before any comparison.
# Sets CF_KIND, CF_PRIOR, CF_BASE, CF_CUR (a path or /dev/null), CF_HAVE_BASE, CF_HAVE_CUR, CF_PRIOR_SHA,
# CF_CUR_SHA and CF_BODY_SAME (baseline and current SQL differ at most in the leading comment header, #366).
_carry_context() { # <slug> <scope|review> <sql_path>
  local d="$SR_REVIEWS/$1" absent=1
  CF_KIND="$2" CF_PRIOR=/dev/null CF_BASE=/dev/null CF_CUR=/dev/null
  CF_HAVE_BASE=false CF_HAVE_CUR=false CF_PRIOR_SHA="" CF_CUR_SHA=""
  CF_BODY_SAME=false CF_PRIOR_ABSENT=false CF_CUR_ABSENT=false
  sr_no_symlinks "$d/$2.json" || exit 2
  if [ -f "$d/$2.json" ]; then
    cmd_check "$d/$2.json" >/dev/null || sr_die 4 "existing $2.json is invalid; see sqlreview.sh check"
    CF_PRIOR="$d/$2.json"
    CF_PRIOR_SHA="$(jq -r '.sql_sha256 // "" | strings' "$CF_PRIOR")"
    if [ "$2" = scope ] && [ -z "$CF_PRIOR_SHA" ]; then
      CF_PRIOR_ABSENT=true
    else
      CF_BASE="$work/carry-base.sql"
      sr_source_auth "$CF_PRIOR" "$CF_BASE" || exit $?
      CF_HAVE_BASE=true
    fi
  fi
  sr_source_clean || exit 2
  # Only a scope explicitly framed before SQL may treat a committed undeclared path
  # as absent. Missing historical evidence above always fails authentication.
  if [ "$CF_PRIOR_ABSENT" = true ] || { [ "$CF_KIND" = scope ] && [ "$CF_PRIOR" = /dev/null ]; }; then
    sr_source_path_absent HEAD "$3"; absent=$?
  fi
  [ "$absent" -le 1 ] || exit 2
  if [ "$absent" = 0 ]; then
    CF_CUR_ABSENT=true
  else
    CF_CUR="$work/carry-current.sql"
    sr_source_render HEAD "$3" "$CF_CUR" || exit 2
    CF_HAVE_CUR=true
    CF_CUR_SHA="$(sr_sha256 "$CF_CUR")" || exit 2
  fi
  if [ "$CF_HAVE_BASE" = true ] && [ "$CF_HAVE_CUR" = true ] && sr_body_same "$CF_BASE" "$CF_CUR"; then CF_BODY_SAME=true; fi
}

# Run a jq filter over a draft with sqlreview-carry.jq included and $ctx bound (see its header).
_carry_jq() { # <draft> <filter> [jq options...]
  local draft="$1" filter="$2"
  shift 2
  jq -r -L "$SR_SCRIPT_DIR" "$@" --slurpfile prior "$CF_PRIOR" --rawfile base "$CF_BASE" --rawfile cur "$CF_CUR" \
    --argjson have_base "$CF_HAVE_BASE" --argjson have_cur "$CF_HAVE_CUR" --arg prior_sha "$CF_PRIOR_SHA" --arg cur_sha "$CF_CUR_SHA" \
    --argjson body_same "$CF_BODY_SAME" --argjson prior_absent "$CF_PRIOR_ABSENT" --argjson cur_absent "$CF_CUR_ABSENT" --arg cf_kind "$CF_KIND" \
    "include \"sqlreview-carry\";
     {kind: \$cf_kind, prior: \$prior[0], base: (if \$have_base then \$base else null end), cur: (if \$have_cur then \$cur else null end),
      prior_sha: \$prior_sha, cur_sha: \$cur_sha, prior_absent: \$prior_absent, cur_absent: \$cur_absent, body_unchanged: \$body_same} as \$ctx | $filter" "$draft"
}

# Which draft items may keep the confirmation of the previous published revision (#348). Read-only.
cmd_carryforward() (
  [ $# -eq 3 ] || usage
  sr_need_jq
  sr_require_root
  local slug="$1" kind="$2" draft="$3" sql work
  work="$(sr_source_workspace)" || exit 2
  trap 'rm -rf "$work"' EXIT
  trap 'exit 2' HUP INT TERM
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
)

# Draft range plumbing only: diff authentic baseline bytes against frozen current SQL.
# Match ranges by published item id/logic step, so retries cannot apply an offset twice.
cmd_remap() (
  [ $# -ge 1 ] && [ $# -le 2 ] || usage
  sr_need_jq
  sr_require_root
  local slug="$1" draft="${2:-}" kind prior sql work input code had_draft=false
  sr_safe_slug "$slug"
  if [ -z "$draft" ]; then
    prior="$(sr_doc_for "$slug")" || sr_die 6 "no published scope/review baseline"
    kind="$(jq -r .kind "$prior")"
    case "$kind" in scope|review) ;; *) sr_die 4 "remap requires scope or review" ;; esac
    draft="$SR_REVIEWS/$slug/$kind.draft.json"
  fi
  draft="$(sr_abspath "$draft")"
  sr_no_symlinks "$draft" || exit 2
  [ "$(dirname "$draft")" = "$SR_REVIEWS/$slug" ] || sr_die 2 "draft must be directly inside this slug's review directory"
  case "$(basename "$draft")" in
    scope.json|review.json|lifts.json) sr_die 2 "remap cannot write published JSON" ;;
    *.json) ;; *) sr_die 2 "draft must be a JSON file, never an SQL snapshot" ;;
  esac
  [ ! -d "$draft" ] || sr_die 2 "draft is a directory"
  if [ -f "$draft" ]; then
    had_draft=true
    input="$draft"
    kind="$(jq -r '.kind // ""' "$input" 2>/dev/null)" || sr_die 4 "invalid draft JSON"
  else
    [ $# -eq 1 ] || sr_die 2 "no such draft: $draft"
    input="$prior"
  fi
  case "$kind" in scope|review) ;; *) sr_die 4 "remap requires scope or review" ;; esac
  prior="$SR_REVIEWS/$slug/$kind.json"
  sr_no_symlinks "$prior" || exit 2
  [ -f "$prior" ] || sr_die 6 "no published $kind source evidence"
  cmd_check "$prior" >/dev/null || sr_die 4 "published $kind is invalid"
  sql="$(jq -r .sql_path "$prior")"
  sr_safe_sql "$sql"
  [ ! -f "$SR_REVIEWS/$slug/rebind-required" ] || sr_die 6 "SQL path moved; reassess before remapping"
  jq -e --arg s "$slug" --arg k "$kind" --arg p "$sql" '
    .slug == $s and .kind == $k and .sql_path == $p' "$input" >/dev/null || sr_die 4 "draft slug/kind/sql_path must match published source"
  work="$(sr_source_workspace)" || exit 2
  trap 'rm -rf "$work"; [ -z "${staged:-}" ] || rm -f "$staged"' EXIT
  trap 'exit 2' HUP INT TERM
  cp "$input" "$work/draft.json" && cp "$prior" "$work/prior.json" || sr_die 2 "cannot stage remap inputs"
  sr_source_auth "$work/prior.json" "$work/base.sql" || exit $?
  sr_source_clean || exit 2
  sr_source_render HEAD "$sql" "$work/current.sql" || exit 2
  local head="$SR_SOURCE_COMMIT" staged=""
  jq -e -L "$SR_SCRIPT_DIR" 'include "sqlreview-remap"; remap_valid' "$work/draft.json" >/dev/null || sr_die 4 "invalid draft ranges"
  LC_ALL=C diff -U 0 "$work/base.sql" "$work/current.sql" > "$work/diff"
  code=$?
  [ "$code" -le 1 ] || sr_die 2 "diff failed"
  if [ "$code" -eq 1 ]; then
    grep -q '^@@ ' "$work/diff" || sr_die 2 "diff has no text line map (binary SQL is unsupported)"
  fi
  jq -e -L "$SR_SCRIPT_DIR" --slurpfile prior "$work/prior.json" --rawfile base "$work/base.sql" \
    --rawfile cur "$work/current.sql" --rawfile delta "$work/diff" '
      include "sqlreview-remap"; remap_result' "$work/draft.json" > "$work/result.json" || sr_die 2 "cannot compute line map"
  jq '.draft' "$work/result.json" > "$work/remapped.json" || sr_die 2 "cannot stage remapped draft"
  # Refuse concurrent edits rather than overwriting work or publishing a map for stale SQL.
  cmp -s "$prior" "$work/prior.json" && cmp -s "$input" "$work/draft.json" &&
    [ "$(git -C "$SR_ROOT" rev-parse HEAD)" = "$head" ] || sr_die 2 "remap inputs changed; retry"
  sr_source_clean || sr_die 2 "remap inputs changed; retry"
  sr_no_symlinks "$draft" || exit 2
  if [ "$had_draft" = false ] && [ -e "$draft" ]; then sr_die 2 "draft appeared during remap; retry"; fi
  if ! cmp -s "$draft" "$work/remapped.json"; then
    # JSON-only sibling staging keeps the final rename on the destination filesystem.
    staged="$(mktemp "$SR_REVIEWS/$slug/.remap-json.XXXXXX")" || sr_die 2 "mktemp failed"
    cp "$work/remapped.json" "$staged" || sr_die 2 "cannot stage remapped draft"
    cmp -s "$prior" "$work/prior.json" && cmp -s "$input" "$work/draft.json" &&
      [ "$(git -C "$SR_ROOT" rev-parse HEAD)" = "$head" ] || sr_die 2 "remap inputs changed; retry"
    sr_source_clean || sr_die 2 "remap inputs changed; retry"
    sr_no_symlinks "$draft" || exit 2
    if [ "$had_draft" = false ] && [ -e "$draft" ]; then sr_die 2 "draft appeared during remap; retry"; fi
    mv "$staged" "$draft" || sr_die 2 "cannot replace draft"
  fi
  jq '.report' "$work/result.json"
)

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
  local sql="" against="" questions="" confirmer="" recs errs parsed
  while [ $# -gt 0 ]; do
    case "$1" in
      --against) [ $# -ge 2 ] || usage; against="$2"; shift ;;
      --questions) [ $# -ge 2 ] || usage; questions="$2"; shift ;;
      --confirmed-by) [ $# -ge 2 ] || usage; confirmer="$2"; shift ;;
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
  [ -z "$questions" ] || { [ -n "$against" ] && [ "$(jq -r .kind "$against")" = scope ]; } || usage
  recs="$(_notes_scan "$sql")" || sr_die 2 "cannot read $sql"
  errs="$(printf '%s\n' "$recs" | awk 'BEGIN { FS = "\037" } $1 == "E" { printf "line %s: %s\n", $2, $3 }')"
  [ -z "$errs" ] || sr_die 4 "malformed analysis-notes header in $sql: $errs"
  parsed="$(printf '%s\n' "$recs" | jq -R -s --slurpfile against "${against:-/dev/null}" '
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
     assumptions: items("assumptions"), limitations: items("limitations")}')" || sr_die 2 "cannot parse notes"
  if [ -n "$against" ] && [ "$(jq -r .kind "$against")" = scope ]; then
    _scope_notes "$against" "$questions" "$parsed"
  elif [ -n "$against" ] && [ "$(jq -r .kind "$against")" = review ] &&
     { [ -n "$confirmer" ] || [ "$(printf '%s' "$parsed" | jq -r .present)" = true ]; }; then
    _header_decisions "$sql" "$against" "$confirmer" "$parsed"
  else printf '%s\n' "$parsed"; fi
}

# Pre-publish scope evidence (#433). Explicit staged questions support first bootstrap without
# publishing early; resume defaults to the authoritative store, not historical embedded strings.
_scope_notes() { # scope-draft optional-question-draft parsed-notes
  local draft="$1" questions="$2" parsed="$3" qdoc diagnostics published
  if [ -z "$questions" ]; then
    questions="$(dirname "$draft")/questions.json"
    sr_no_symlinks "$(sr_abspath "$questions")" || exit 2
    if [ ! -e "$questions" ]; then
      jq -e 'has("question_store")' "$draft" >/dev/null && sr_die 4 "declared questions.json is missing; supply --questions with the staged question draft"
      questions=""
    fi
  fi
  if [ -n "$questions" ]; then
    sr_no_symlinks "$(sr_abspath "$questions")" || exit 2
    [ -f "$questions" ] && [ -r "$questions" ] || sr_die 2 "no such readable question file: $questions"
    diagnostics="$(cmd_check "$questions")" || sr_die 4 "invalid question store: $questions: $diagnostics"
    jq -e -L "$SR_SCRIPT_DIR" --slurpfile draft "$draft" '
      include "sqlreview-questions";
      .kind == "questions" and .slug == $draft[0].slug and .sql_path == $draft[0].sql_path
      and legacy_covered($draft[0]; null)' "$questions" >/dev/null || sr_die 4 "question store binding mismatch or untracked legacy questions"
    # A staged draft cannot hide identities or closed rows that publish-questions would
    # reject later, after scope publication. Keep notes usable without an initialised project.
    published="$(dirname "$draft")/questions.json"
    sr_no_symlinks "$(sr_abspath "$published")" || exit 2
    if [ -e "$published" ]; then
      [ -f "$published" ] && [ -r "$published" ] || sr_die 2 "no such readable published question store: $published"
      diagnostics="$(cmd_check "$published")" || sr_die 4 "invalid published question store: $published: $diagnostics"
      jq -e -L "$SR_SCRIPT_DIR" --slurpfile old "$published" '
        include "sqlreview-questions"; question_history_retained($old[0])
      ' "$questions" >/dev/null || sr_die 4 "question identity/history changed, removed, or new question already closed"
    fi
    qdoc="$(jq . "$questions")" || sr_die 4 "cannot read question store"
  else
    qdoc="$(jq -L "$SR_SCRIPT_DIR" '
      include "sqlreview-questions"; legacy_questions(.; null; .slug; .sql_path)' "$draft")" || sr_die 4 "cannot project legacy questions"
    printf '%s\n' "$qdoc" | jq -e -L "$SR_SCRIPT_DIR" '
      include "sqlreview-questions"; [question_errors] | length == 0' >/dev/null || sr_die 4 "invalid legacy questions"
  fi
  printf '%s\n' "$parsed" | jq -L "$SR_SCRIPT_DIR" --argjson questions "$qdoc" '
    include "sqlreview-scope-notes"; scope_notes($questions)' || sr_die 2 "cannot compare scope notes"
}

# Header decisions are never confirmations. Read reachable git objects as the dated source;
# inspect every subsequent path revision, including a reverted change. No snapshot or draft
# supplied by the caller establishes history. Relevant merges/renames and shallow history
# fail closed; unrelated PR merges with identical path blobs do not invalidate evidence.
_header_decisions() ( # SQL DRAFT intended-human-confirmer parsed-notes
  local sql="$1" draft="$2" actor="$3" parsed="$4" root rel tmp commit epoch parents start safe=true row_safe path_sha=""
  local project source_rel source_sql generated=false manifest entry
  # Replacement refs/grafts are not evidence of the original object ancestry.
  export GIT_NO_REPLACE_OBJECTS=1
  project="$(sr_find_root)" || project=""
  if [ -n "$project" ]; then
    SR_ROOT="$project"
    tmp="$(sr_source_workspace)" || return 2
  else tmp="$(mktemp -d)" || return 2; fi
  trap 'rm -rf "$tmp"' EXIT
  trap 'exit 2' HUP INT TERM
  : > "$tmp/rows" || return 2
  # Publication supplies temporary authenticated bytes. Resolve their maintained
  # path from the draft's project, rather than treating the temporary file as source.
  if [ -n "$project" ]; then
    rel="$(jq -r '.sql_path' "$draft")"
    source_sql="$project/$rel"
  else source_sql="$sql"; fi
  if root="$(git -C "${project:-$(dirname "$source_sql")}" rev-parse --show-toplevel 2>/dev/null)"; then
    source_rel="$(sr_abspath "$source_sql")"
    source_rel="${source_rel#"$root"/}"
    [ -n "$project" ] || rel="$source_rel"
    case "$(cd "$tmp" && pwd -P)" in "$root"|"$root"/*) sr_die 2 "temporary header evidence must be outside the git tree" ;; esac
    path_sha="$(sr_sha256 "$sql")"
    if jq -e '.sql_provenance.mode == "rendered"' "$draft" >/dev/null; then generated=true; safe=false; fi
    manifest=""
    # The provenance manifest belongs at the project SQL directory, not beside
    # arbitrary nested SQL paths. A declared generated source has no complete
    # committed rendered-header history yet, so fresh decisions require a walk.
    if [ -n "$project" ]; then
      manifest="${project#"$root"}"
      manifest="${manifest#/}"
      manifest="${manifest:+$manifest/}sql/provenance.json"
      if git -C "$root" show "HEAD:$manifest" > "$tmp/manifest" 2>/dev/null; then
        entry="$(jq -r --arg p "$rel" '.requests[$p].source // ""' "$tmp/manifest")" || safe=false
        case "$entry" in builder|cohort|spec) generated=true; safe=false ;; hand-written) ;; *) safe=false ;; esac
      fi
    fi
    git -C "$root" log --full-history --topo-order --reverse --format='%H %ct %P' HEAD -- ":(literal)$source_rel" ${manifest:+":(literal)$manifest"} > "$tmp/history" 2>/dev/null || safe=false
    [ "$(git -C "$root" rev-parse --is-shallow-repository 2>/dev/null)" = false ] || safe=false
    local grafts blob parent parent_blob changes
    grafts="$(git -C "$root" rev-parse --git-path info/grafts)"
    case "$grafts" in /*) ;; *) grafts="$root/$grafts" ;; esac
    [ ! -s "$grafts" ] || safe=false
    [ -s "$tmp/history" ] || safe=false
    while read -r commit epoch parents; do
      [ -n "$commit" ] || continue
      row_safe=true
      if [ -n "$manifest" ]; then
        git -C "$root" ls-tree -r "$commit" -- "$manifest" > "$tmp/manifest-tree" 2>/dev/null || safe=false
        if [ -s "$tmp/manifest-tree" ]; then
          if git -C "$root" show "$commit:$manifest" > "$tmp/manifest" 2>/dev/null; then
            entry="$(jq -r --arg p "$rel" '.requests[$p].source // ""' "$tmp/manifest")" || row_safe=false
            case "$entry" in hand-written) ;; *) row_safe=false ;; esac
          else safe=false; fi
        fi
      fi
      # Git simplification must not hide an alternate-parent edit or a path move.
      changes="$(git -C "$root" diff-tree --root --no-commit-id -r -M -m "$commit" 2>/dev/null)" || row_safe=false
      if printf '%s\n' "$changes" | awk -F '\t' -v path="$source_rel" '$1 ~ / R[0-9]+$/ && ($2 == path || $3 == path) { found=1 } END { exit !found }'; then row_safe=false; fi
      case "$parents" in
        *" "*)
          blob="$(git -C "$root" rev-parse "$commit:$source_rel" 2>/dev/null)" || blob=absent
          for parent in $parents; do
            parent_blob="$(git -C "$root" rev-parse "$parent:$source_rel" 2>/dev/null)" || parent_blob=absent
            [ "$parent_blob" = "$blob" ] || row_safe=false
          done ;;
      esac
      if git -C "$root" show "$commit:$source_rel" > "$tmp/sql" 2>/dev/null; then
        bash "$SR_SCRIPT_DIR/sqlreview.sh" notes "$tmp/sql" > "$tmp/notes" 2>/dev/null || { printf 'null\n' > "$tmp/notes"; row_safe=false; }
        start="$(sr_body_start "$tmp/sql")" || { start=0; row_safe=false; }
      else
        printf 'null\n' > "$tmp/notes"; start=0; row_safe=false
        # An absent path can precede a new source; an unreadable existing object can
        # hide an earlier source and invalidates ancestry availability globally.
        git -C "$root" ls-tree -r "$commit" -- "$source_rel" > "$tmp/path-tree" 2>/dev/null || safe=false
        [ ! -s "$tmp/path-tree" ] || safe=false
      fi
      # Append one file-backed JSON row per revision; SQL/history never enter argv.
      jq -nc --arg commit "$commit" --argjson at "$epoch" --slurpfile notes "$tmp/notes" \
        --argjson start "$start" --argjson safe "$row_safe" --rawfile sql "$tmp/sql" '
        {commit:$commit, at:$at, safe:$safe, notes:$notes[0], body_start:$start,
         sql:($sql | rtrimstr("\n") | split("\n"))}' >> "$tmp/rows" || safe=false
    done < "$tmp/history"
  else root=""; rel=""; safe=false; fi
  start="$(sr_body_start "$sql")" || start=0
  printf '%s\n' "$parsed" | jq -L "$SR_SCRIPT_DIR" --slurpfile draft "$draft" --rawfile sql "$sql" \
    --argjson generated "$generated" --arg actor "$actor" --arg path "$rel" --arg sha "$path_sha" --argjson safe "$safe" --argjson start "$start" --slurpfile history "$tmp/rows" \
    'include "sqlreview-header"; header_candidates($draft[0]; $sql; $actor; $path; $sha; $safe; $start; $history)
      | if $generated then .header_walk |= map(.why = "generated source has no proven committed rendered-header history; confirm ordinarily") else . end'
)

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
  for f in review.json scope.json lifts.json questions.json rebind-required; do
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
  for f in review.json scope.json lifts.json questions.json; do
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
  local question_rows='[]' question_doc
  if [ "$kind" != lifts ]; then
    question_doc="$(cmd_questions "$slug" "$kind")" || return $?
    question_rows="$(printf '%s' "$question_doc" | jq -c .questions)"
  fi
  vars="$(jq -c --argjson question_rows "$question_rows" --slurpfile cfgs "$cfg" -f "$SR_SCRIPT_DIR/sqlreview-render.jq" "$doc")" || sr_die 2 "render failed for reviews/$slug/$kind.json"
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
  ledger) . "$SR_SCRIPT_DIR/sqlreview-ledger.sh"; cmd_ledger "$@" ;;
  lint) cmd_lint "$@" ;;
  publish) cmd_publish "$@" ;;
  roles) cmd_roles "$@" ;;
  guard) cmd_guard "$@" ;;
  lifts-stale) cmd_lifts_stale "$@" ;;
  fingerprint) cmd_fingerprint "$@" ;;
  materialize) cmd_materialize "$@" ;;
  snapshot) cmd_snapshot "$@" ;;
  delta) cmd_delta "$@" ;;
  impact) cmd_impact "$@" ;;
  carryover) cmd_carryover "$@" ;;
  intake) cmd_intake "$@" ;;
  carryforward) cmd_carryforward "$@" ;;
  remap) cmd_remap "$@" ;;
  notes) cmd_notes "$@" ;;
  move) cmd_move "$@" ;;
  questions) cmd_questions "$@" ;;
  migrate-questions) cmd_migrate_questions "$@" ;;
  publish-questions) cmd_publish_questions "$@" ;;
  render) cmd_render "$@" ;;
  -h|--help|help) usage ;;
  *) printf 'sqlreview: unknown command: %s\n' "$cmd" >&2; usage ;;
esac
