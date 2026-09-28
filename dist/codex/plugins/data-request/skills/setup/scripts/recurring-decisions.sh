#!/usr/bin/env bash
# recurring-decisions.sh — read the data-request list of recurring scope decisions (#362).
# The list is ../assets/recurring-decisions.json, the one maintained home. Contract:
# ../references/recurring-decisions.rst. Read-only: it never writes a record.
#
#   list                  the list as JSON: {updated, tracking_issue, decisions: [...]}
#   match DRAFT           HINTS ONLY: scope/review items whose text or rationale contains every
#                         term group of a listed decision. JSON {updated, tracking_issue,
#                         matches: [{kind, id, decision, title, status, expected_kind, marked,
#                         evidence, library_issue, related_issues, tracking_issue, proposal, retired_by}]}
#                         `evidence` links to the library issue rows that name the prior enquiries.
#   marked RECORD...      items that carry an `upstream` marker, for /data-request:lift. JSON
#                         {items: [{file, kind, id, text, decision, known, title, status, evidence,
#                         library_issue, related_issues, tracking_issue, retired_by}]}
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

# Shared jq definitions: list validation, matching and lookup.
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
        (if (.match | type) == "array" and (.match | length) > 0
            and (.match | all(.[]; type == "array" and length > 0 and all(.[]; str)))
         then empty else "list: \($id): match must be a nonempty array of nonempty term arrays" end),
        (if (.evidence | type) == "array" and (.evidence | length) > 0
            and (.evidence | all(.[]; str and startswith("https://github.com/")))
         then empty else "list: \($id): evidence must be a nonempty array of GitHub links" end),
        (if .library_issue == null or (.library_issue | str) then empty else "list: \($id): library_issue must be a URL or null" end),
        (if .status != "retired" or ((.retired_by.unit | str) and (.retired_by.version | str)) then empty
         else "list: \($id): a retired decision needs retired_by {unit, version}" end))
  end;
def hit($d): (((.text // "") + "\n" + (.rationale // "")) | ascii_downcase) as $t
  | all($d.match[]; any(.[]; ascii_downcase as $term | $t | contains($term)));
def summary($list):
  {title, status, evidence, library_issue, related_issues: (.related_issues // []),
   tracking_issue: (.tracking_issue // $list.tracking_issue), retired_by};
'

load_list() {
  [ -f "$RD_LIST" ] || die "no list at $RD_LIST"
  local errs
  errs="$(jq -r "$RD_JQ"' list_errors' "$RD_LIST" 2>&1)" || die "list is not valid JSON: $RD_LIST" 4
  [ -z "$errs" ] || { printf '%s\n' "$errs" >&2; exit 4; }
}

check_doc() {
  [ -f "$1" ] || die "no such file: $1"
  jq -e 'type == "object"' "$1" >/dev/null 2>&1 || die "$1: not a JSON object" 4
}

cmd_list() {
  [ $# -eq 0 ] || usage
  load_list
  jq '{updated, tracking_issue, decisions}' "$RD_LIST"
}

cmd_match() {
  [ $# -eq 1 ] || usage
  load_list
  check_doc "$1"
  jq --slurpfile list "$RD_LIST" "$RD_JQ"'
    $list[0] as $l
    | {updated: $l.updated, tracking_issue: $l.tracking_issue,
       matches: [("assumptions", "limitations") as $k
         | (.[$k] // [] | if type == "array" then .[] else empty end) | select(type == "object") | . as $i
         | $l.decisions[] | select(. as $d | $i | hit($d))
         | {kind: $k, id: $i.id, decision: .id, expected_kind: .kind,
            marked: (($i.upstream.decision // null) == .id), proposal}
           + summary($l)]}' "$1"
}

cmd_marked() {
  [ $# -ge 1 ] || usage
  load_list
  local f bad out="[]" rows
  for f in "$@"; do
    check_doc "$f"
    bad="$(jq -r '("assumptions", "limitations") as $k | (.[$k] // [])[] | select(type == "object" and has("upstream"))
      | select((.upstream | type) != "object" or (.upstream.decision | type) != "string" or (.upstream.decision | length) == 0)
      | "\(.id // "?"): upstream must be an object with a nonempty decision id"' "$f")"
    [ -z "$bad" ] || { printf '%s: %s\n' "$f" "$bad" >&2; exit 4; }
    rows="$(jq --arg file "$f" --slurpfile list "$RD_LIST" "$RD_JQ"'
      $list[0] as $l
      | [("assumptions", "limitations") as $k | (.[$k] // [])[] | select(type == "object" and has("upstream")) | . as $i
         | ([$l.decisions[] | select(.id == $i.upstream.decision)][0]) as $d
         | {file: $file, kind: $k, id: $i.id, text: $i.text, decision: $i.upstream.decision, known: ($d != null)}
           + (if $d == null then {} else ($d | summary($l)) end)]' "$f")" || exit 2
    out="$(jq -n --argjson a "$out" --argjson b "$rows" '$a + $b')"
  done
  jq -n --argjson items "$out" '{items: $items}'
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
