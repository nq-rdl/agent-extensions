#!/usr/bin/env bash
# recurring-decisions.sh — read the data-request list of recurring scope decisions (#362).
# The list is ../assets/recurring-decisions.json, the one maintained home. Contract:
# ../references/recurring-decisions.rst. Read-only: it never writes a record.
#
#   list                  the list as JSON: {updated, tracking_issue, decisions: [...]}
#   match [--any-kind] DRAFT
#                         HINTS ONLY: scope/review items whose text or rationale contains a whole-word
#                         term from every term group of a listed decision. Only items in the list of
#                         the decision's kind (assumptions or limitations) match; --any-kind drops
#                         that filter. JSON {updated, tracking_issue, matches: [{kind, id, decision,
#                         title, status, expected_kind, marked, evidence, library_issue,
#                         related_issues, tracking_issue, proposal, retired_by, house_default?}]}
#                         `evidence` links to the library issue rows that name the prior enquiries.
#   marked RECORD...      marked items grouped by decision, for /data-request:lift. JSON
#                         {decisions: [{decision, known, title, status, evidence, library_issue,
#                         related_issues, tracking_issue, retired_by, house_default?, items: [{file, kind, id, text}]}]}
#
# SQLREVIEW_RECURRING_DECISIONS overrides the list path (tests and local trials).
# Exit codes: 0 ok · 1 usage · 2 error (missing file, no jq) · 4 invalid list, document or marker.
set -u
RD_DIR="$(cd "$(dirname "$0")" && pwd -P)"
RD_LIST="${SQLREVIEW_RECURRING_DECISIONS:-$RD_DIR/../assets/recurring-decisions.json}"

usage() {
  awk 'NR > 1 && !/^#/ { exit } NR > 1' "$0" | sed 's/^# \{0,1\}//' >&2
  exit 1
}
die() { printf 'recurring-decisions: %s\n' "$1" >&2; exit "${2:-2}"; }

command -v jq >/dev/null 2>&1 || die "jq is required"

# Shared jq definitions: list and document validation, matching and lookup.
RD_JQ='
def str: type == "string" and length > 0;
def list_errors:
  if type != "object" or (.decisions | type) != "array" then "list: decisions must be an array"
  else
    (.decisions | map(.id) | group_by(.)[] | select(length > 1) | "list: duplicate id \(.[0])"),
    (.decisions[] | (.id // "?") as $id
      | (if (.id | str) and (.id | test("^[a-z][a-z0-9-]*$")) then empty else "list: \($id): id must be kebab-case" end),
        (if (.title | str) then empty else "list: \($id): title is empty" end),
        (if .kind == "assumption" or .kind == "limitation" then empty else "list: \($id): kind must be assumption or limitation" end),
        (if .status == "open" or .status == "retired" then empty else "list: \($id): status must be open or retired" end),
        (if (.proposal.text | str) and (.proposal.rationale | str) then empty else "list: \($id): proposal needs text and rationale" end),
        (if has("house_default") and ((.house_default | type) != "object" or
             (.house_default.facility_code | str | not) or
             (.house_default.confirmed_by | (str and (contains("@") | not)) | not) or
             (.house_default.confirmed_at | str | not) or
             (.house_default.decided | type) != "object" or
             ([.house_default.decided.by, .house_default.decided.role,
               .house_default.decided.at, .house_default.decided.source] | all(.[]; str) | not) or
             (.house_default.decided.by | contains("@")))
         then "list: \($id): house_default needs a string facility code, recorded confirmation and decided origin" else empty end),
        (if (.match | type) == "array" and (.match | length) > 0
            and (.match | all(.[]; type == "array" and length > 0 and all(.[]; str)))
         then (if (.match | all(.[][]; . == ascii_downcase)) then empty else "list: \($id): match terms must be lowercase" end)
         else "list: \($id): match must be a nonempty array of nonempty term arrays" end),
        (if (.evidence | type) == "array" and (.evidence | length) > 0
            and (.evidence | all(.[]; str and startswith("https://github.com/")))
         then empty else "list: \($id): evidence must be a nonempty array of GitHub links" end),
        (if .library_issue == null or ((.library_issue | str) and (.library_issue | startswith("https://github.com/")))
         then empty else "list: \($id): library_issue must be a GitHub link or null" end),
        (if .status != "retired" or ((.retired_by.unit | str) and (.retired_by.version | str)) then empty
         else "list: \($id): a retired decision needs retired_by {unit, version}" end))
  end;
def doc_errors:
  if type != "object" then "not a JSON object"
  else ("assumptions", "limitations") as $k
    | if has($k) | not then empty
      elif (.[$k] | type) != "array" then "\($k) must be an array"
      else .[$k][]
        | if type != "object" then "\($k): every item must be an object"
          elif has("upstream") and ((.upstream | type) != "object" or (.upstream.decision | str | not))
          then "\(.id // "?"): upstream must be an object with a nonempty decision id"
          else empty end
      end
  end;
# A term hits when it appears as a whole word or phrase: no letter, digit or underscore on either side.
def esc: gsub("(?<c>[.*+?^$(){}|\\[\\]\\\\/-])"; "\\\(.c)");
def hit($d): (((.text // "") + "\n" + (.rationale // "")) | ascii_downcase) as $t
  | all($d.match[]; any(.[]; . as $term | $t | test("(?<![a-z0-9_])" + ($term | esc) + "(?![a-z0-9_])")));
def summary($list):
  {title, status, evidence, library_issue, related_issues: (.related_issues // []),
   tracking_issue: (.tracking_issue // $list.tracking_issue), retired_by}
  + (if has("house_default") then {house_default} else {} end);
'

load_list() {
  [ -f "$RD_LIST" ] || die "no list at $RD_LIST"
  local errs
  errs="$(jq -r "$RD_JQ"' list_errors' "$RD_LIST" 2>&1)" || die "list is not valid JSON: $RD_LIST" 4
  [ -z "$errs" ] || { printf '%s\n' "$errs" >&2; exit 4; }
}

# Every document the helper reads must be valid before any matching: exit 4 otherwise.
check_doc() {
  [ -f "$1" ] || die "no such file: $1"
  local errs
  errs="$(jq -r "$RD_JQ"' doc_errors' "$1" 2>/dev/null)" || die "$1: not valid JSON" 4
  [ -z "$errs" ] || { printf '%s\n' "$errs" | sed "s|^|$1: |" >&2; exit 4; }
}

cmd_list() {
  [ $# -eq 0 ] || usage
  load_list
  jq '{updated, tracking_issue, decisions}' "$RD_LIST"
}

cmd_match() {
  local any=false
  [ "${1:-}" = "--any-kind" ] && { any=true; shift; }
  [ $# -eq 1 ] || usage
  load_list
  check_doc "$1"
  jq --slurpfile list "$RD_LIST" --argjson any "$any" "$RD_JQ"'
    $list[0] as $l
    | {updated: $l.updated, tracking_issue: $l.tracking_issue,
       matches: [("assumptions", "limitations") as $k
         | (.[$k] // [])[] | . as $i
         | $l.decisions[] | select(. as $d | ($any or $k == $d.kind + "s") and ($i | hit($d)))
         | {kind: $k, id: $i.id, decision: .id, expected_kind: .kind,
            marked: ($i.upstream.decision == .id), proposal}
           + summary($l)]}' "$1" || die "match failed on $1"
}

cmd_marked() {
  [ $# -ge 1 ] || usage
  load_list
  local f rows="[]" more
  for f in "$@"; do
    check_doc "$f"
    more="$(jq -c --arg file "$f" '[("assumptions", "limitations") as $k | (.[$k] // [])[]
      | select(has("upstream")) | {decision: .upstream.decision, file: $file, kind: $k, id, text}]' "$f")" \
      || die "marked failed on $f"
    rows="$(jq -cn --argjson a "$rows" --argjson b "$more" '$a + $b')"
  done
  jq -n --argjson rows "$rows" --slurpfile list "$RD_LIST" "$RD_JQ"'
    $list[0] as $l
    | {decisions: [$rows | group_by(.decision)[] | .[0].decision as $id
        | ([$l.decisions[] | select(.id == $id)][0]) as $d
        | {decision: $id, known: ($d != null)}
          + (if $d == null then {} else ($d | summary($l)) end)
          + {items: map(del(.decision))}]}'
}

cmd="${1:-}"
[ -n "$cmd" ] || usage
shift
case "$cmd" in
  list) cmd_list "$@" ;;
  match) cmd_match "$@" ;;
  marked) cmd_marked "$@" ;;
  *) usage ;;
esac
