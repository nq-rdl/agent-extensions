#!/usr/bin/env bash
# release.sh — evidence and record helper for /data-request:release (#407). The skill drafts the
# researcher-facing release body; this helper answers the questions it must not guess, and checks
# and renders the analyst's record. It never writes: the skill writes the record, the guard checks it.
#
#   evidence REF [SLUG...]   does each .sqlreview review apply to the release at REF? JSON
#                            {ref, commit, reviews: [{slug, kind, sql_path, revision, applies,
#                            sql_sha256_reviewed, sql_sha256_at_ref, reviewed_commit,
#                            reviewed_commit_in_ref, assumptions, limitations, open_questions}]}.
#                            The reviews are read from the working tree (the newest record); the SQL
#                            is read from REF, never the working tree. applies:
#                              current         the SQL at REF is the reviewed SQL
#                              header-only     only the leading comment header differs
#                              changed         the SQL at REF differs: the review is stale for REF
#                              missing-at-ref  REF has no file at sql_path: the review may describe a draft
#                              unreviewed      scope only, no review
#                              invalid         the record fails sqlreview.sh check
#                            reviewed_commit_in_ref: whether the review's git_commit is an ancestor of
#                            REF (null when the review has none or git cannot tell).
#   check FILE | check --stdin
#                            validate a release record (.sqlreview/releases/<tag>/release.json):
#                            one violation per line, exit 4; "ok" otherwise
#   render FILE              the paste-ready release body (Markdown) from a valid record; a draft
#                            shows its pending claims and open questions
#
# Exit codes: 0 ok · 1 usage · 2 error (unknown ref or slug, no jq or git) · 3 not initialised ·
# 4 invalid record · 10 at least one review does not apply to REF (evidence).
set -u
SR_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
# shellcheck source=sqlreview-lib.sh
. "$SR_SCRIPT_DIR/sqlreview-lib.sh"

usage() {
  awk 'NR > 1 && !/^#/ { exit } NR > 1' "$0" | sed 's/^# \{0,1\}//' >&2
  exit 1
}

# Shared jq definitions: record validation and rendering.
RL_JQ='include "sqlreview-identity";
def str: type == "string" and length > 0;
def arr: if type == "array" then . else [] end;
def kept: .decision == "accepted" or .decision == "reworded";
def src_errors($cid; $kept; $ev):
  if type != "object" then "\($cid): every source must be an object"
  elif .kind == "review" then
    if (.slug | str) and (.item | str) and (.revision | type) == "number" then
      if $kept | not then empty
      else . as $s | ([$ev[] | select(.slug == $s.slug)][0]) as $e
        | if $e == null then "\($cid): review \(.slug) is not in evidence"
          elif $e.revision != .revision then
            "\($cid): review \(.slug) revision \(.revision) is not the revision in evidence (\($e.revision))"
          elif $e.applies == "current" or $e.applies == "header-only" then empty
          else "\($cid): review \(.slug) does not apply to the release (\($e.applies)); cite the release files that support the claim, or raise it as a question" end
      end
    else "\($cid): a review source needs slug, item and revision" end
  elif .kind == "scope" then
    if (.slug | str) and (.revision | type) == "number" then empty
    else "\($cid): a scope source needs slug and revision" end
  elif .kind == "file" then
    if (.path | str) and (.ref | str) then empty else "\($cid): a file source needs path and ref" end
  else "\($cid): source kind must be review, scope or file" end;
def claim_errors($ev):
  (.id // "?") as $id
  | (if (.id | str) and (.id | test("^C[1-9][0-9]*$")) then empty else "claim id must be C<n>: \($id)" end),
    (if .section == "summary" or .section == "assumptions" then empty
     else "\($id): section must be summary or assumptions" end),
    (if (.proposed | str) then empty else "\($id): proposed wording is empty" end),
    (if .decision == "pending" or .decision == "accepted" or .decision == "reworded" or .decision == "rejected" then empty
     else "\($id): decision must be pending, accepted, reworded or rejected" end),
    (if .decision == "pending" then empty else
       (if (.decided_by | str) then empty else "\($id): decided_by is required for a decided claim" end),
       (if (.decided_at | str) then empty else "\($id): decided_at is required for a decided claim" end)
     end),
    (if .decision == "accepted" and .final != .proposed then
       "\($id): an accepted claim keeps the proposed wording as final"
     elif .decision == "reworded" and ((.final | str | not) or .final == .proposed) then
       "\($id): a reworded claim needs new final wording"
     elif .decision == "rejected" and .final != null then "\($id): a rejected claim has no final wording"
     elif .decision == "pending" and .final != null then "\($id): a pending claim has no final wording"
     else empty end),
    (if (.sources | type) == "array" and (.sources | length) > 0
     then kept as $k | .sources[] | src_errors($id; $k; $ev)
     else "\($id): sources must be a nonempty array" end);
def question_errors:
  (.id // "?") as $id
  | (if (.id | str) and (.id | test("^Q[1-9][0-9]*$")) then empty else "question id must be Q<n>: \($id)" end),
    (if (.text | str) then empty else "\($id): text is empty" end),
    (if (.sources | type) == "array" then empty else "\($id): sources must be an array" end),
    (if .resolution == null then empty
     elif (.resolution | str) and (.resolved_by | str) and (.resolved_at | str) then empty
     else "\($id): a resolution needs resolved_by and resolved_at" end);
def release_errors:
  if type != "object" then "not a JSON object"
  else
    (.evidence | arr) as $ev
    | identity_violations,
      (if .schemaVersion == 1 then empty else "schemaVersion must be 1" end),
      (if .kind == "release" then empty else "kind must be release" end),
      (if (.tag | str) and (.tag | test("^[A-Za-z0-9][A-Za-z0-9._-]*$")) and (.tag | contains("..") | not)
       then empty else "tag must be a release tag name (letters, digits, . _ -)" end),
      (if (.commit | type) == "string" and (.commit | test("^[0-9a-f]{7,64}$")) then empty
       else "commit must be the hash of the tagged commit" end),
      (if .status == "draft" or .status == "approved" then empty else "status must be draft or approved" end),
      (if (.recorded_at | str) and (.recorded_by | str) then empty else "recorded_at and recorded_by are required" end),
      (if (.evidence | type) == "array"
          and all(.evidence[]; type == "object" and (.slug | str) and (.revision | type) == "number" and (.applies | str))
       then empty else "evidence must be an array of {slug, revision, applies} from release.sh evidence" end),
      (if (.questions | type) == "array" then empty else "questions must be an array" end),
      (if (.claims | type) == "array" and (.claims | length) > 0 then empty else "claims must be a nonempty array" end),
      (.claims | arr | .[] | if type == "object" then claim_errors($ev) else "every claim must be an object" end),
      (.questions | arr | .[] | if type == "object" then question_errors else "every question must be an object" end),
      (.claims | arr | map(objects | .id) | group_by(.)[] | select(length > 1) | "duplicate claim id \(.[0])"),
      (.questions | arr | map(objects | .id) | group_by(.)[] | select(length > 1) | "duplicate question id \(.[0])"),
      (if .status != "approved" then empty else
         (.claims | arr | .[] | objects | select(.decision == "pending") | "approved: \(.id) is pending"),
         (.questions | arr | .[] | objects | select(.resolution == null) | "approved: \(.id) is unresolved"),
         (("summary", "assumptions") as $s
          | if any(.claims | arr | .[] | objects; .section == $s and kept) then empty
            else "approved: no kept claim in \($s)" end)
       end)
  end;
def src_label:
  if .kind == "review" then "review \(.slug) \(.item) r\(.revision)"
  elif .kind == "scope" then "scope \(.slug)\(if .item then " " + .item else "" end) r\(.revision)"
  else "file \(.path)@\(.ref)" end;
def claim_line:
  "- \(if .decision == "pending" then "[pending] " + .proposed else .final end)"
  + " <!-- \(.id): \(.sources | map(src_label) | join("; ")) -->";
def section_lines($s):
  [.claims[] | select(.section == $s and (kept or .decision == "pending")) | claim_line]
  | if length == 0 then ["_No claims yet._"] else . end | join("\n");
def render:
  (if .status == "draft"
   then "> **Draft, not approved.** Resolve the pending claims and open questions below before release.\n\n"
   else "" end)
  + "## Extraction Summary\n\n" + section_lines("summary") + "\n\n"
  + "## Extraction Assumptions / Important limitations\n\n" + section_lines("assumptions") + "\n"
  + ([.questions[] | select(.resolution == null) | "- \(.id): \(.text)"]
     | if length == 0 then "" else "\n## Open questions (resolve before release)\n\n" + join("\n") + "\n" end);
'

# Validate a record read from $1 (a file) and print its violations; returns 4 when any.
rl_check_file() {
  local out
  out="$(jq -r -L "$SR_SCRIPT_DIR" "$RL_JQ"' release_errors' "$1" 2>/dev/null)" || { printf 'not valid JSON\n'; return 4; }
  [ -z "$out" ] || { printf '%s\n' "$out"; return 4; }
}

cmd_check() {
  sr_need_jq
  local f tmp rc
  case "${1:-}" in
    --stdin) [ $# -eq 1 ] || usage
      tmp="$(mktemp)" || sr_die 2 "mktemp failed"
      cat > "$tmp"
      rl_check_file "$tmp"; rc=$?; rm -f "$tmp" ;;
    "") usage ;;
    *) [ $# -eq 1 ] || usage
      f="$1"; [ -f "$f" ] || sr_die 2 "no such file: $f"
      rl_check_file "$f"; rc=$? ;;
  esac
  [ "$rc" -eq 0 ] && printf 'ok\n'
  return "$rc"
}

cmd_render() {
  sr_need_jq
  [ $# -eq 1 ] || usage
  [ -f "$1" ] || sr_die 2 "no such file: $1"
  local errs
  errs="$(rl_check_file "$1")" || { printf '%s\n' "$errs" >&2; exit 4; }
  jq -r -L "$SR_SCRIPT_DIR" "$RL_JQ"' render' "$1"
}

# One review directory -> one JSON row on stdout.
rl_review_row() { # <slug> <commit>
  local slug="$1" commit="$2" d="$SR_REVIEWS/$1" doc kind sql reviewed at="" body_at="" applies tmp gc inref="null" binding
  doc="$(sr_doc_for "$slug")" || return 1
  kind="$(jq -r '.kind // ""' "$doc")"
  if ! bash "$SR_SCRIPT_DIR/sqlreview.sh" check "$doc" >/dev/null 2>&1; then
    jq -nc --arg slug "$slug" --arg kind "$kind" \
      '{slug: $slug, kind: $kind, sql_path: null, revision: null, applies: "invalid"}'
    return 0
  fi
  sql="$(jq -r '.sql_path' "$doc")"
  sr_safe_sql "$sql"
  reviewed="$(jq -r '.sql_sha256 // ""' "$doc")"
  tmp="$(mktemp)" || sr_die 2 "mktemp failed"
  # ./ makes the path relative to SR_ROOT, which need not be the repository top level.
  if git -C "$SR_ROOT" cat-file -e "$commit:./$sql" 2>/dev/null &&
     git -C "$SR_ROOT" show "$commit:./$sql" > "$tmp" 2>/dev/null; then
    at="$(sr_sha256 "$tmp")"
  fi
  if [ "$kind" = scope ]; then applies="unreviewed"
  elif [ -z "$at" ]; then applies="missing-at-ref"
  else
    sr_no_symlinks "$d/source.sql" || exit 2
    sr_binding "$doc" "$tmp" "$d/source.sql"; binding=$?
    case "$binding" in 0) applies="current" ;; 10) applies="header-only" ;; *) applies="changed" ;; esac
  fi
  [ -z "$at" ] || body_at="$(sr_body_sha256 "$tmp" || true)"
  rm -f "$tmp"
  gc="$(jq -r '.git_commit // "" | strings' "$doc")"
  case "$gc" in
    ""|*[!0-9a-f]*) ;;
    *) if git -C "$SR_ROOT" merge-base --is-ancestor "$gc" "$commit" 2>/dev/null; then inref=true
       elif [ $? -eq 1 ]; then inref=false; fi ;;
  esac
  jq -c --arg slug "$slug" --arg applies "$applies" --arg at "$at" --arg body_at "$body_at" --argjson inref "$inref" '
    def items: [(. // [])[] | {id, text, rationale, confirmed_revision}];
    {slug: $slug, kind, sql_path, revision, applies: $applies,
     sql_sha256_reviewed: .sql_sha256, sql_sha256_at_ref: (if $at == "" then null else $at end),
     sql_body_sha256_reviewed: (.sql_body_sha256 // null), sql_body_sha256_at_ref: (if $body_at == "" then null else $body_at end),
     reviewed_commit: .git_commit, reviewed_commit_in_ref: $inref,
     assumptions: (.assumptions | items), limitations: (.limitations | items),
     open_questions: (.open_questions // [])}' "$doc"
}

cmd_evidence() {
  [ $# -ge 1 ] || usage
  sr_need_jq
  command -v git >/dev/null 2>&1 || sr_die 2 "git is required to read the release"
  local ref="$1" commit slug rows="" row
  shift
  sr_require_root
  case "$ref" in ""|-*) sr_die 2 "unsafe ref: $ref" ;; esac
  commit="$(git -C "$SR_ROOT" rev-parse --verify --quiet "$ref^{commit}" 2>/dev/null)" ||
    sr_die 2 "unknown ref: $ref (give the release tag or candidate commit)"
  if [ $# -eq 0 ]; then
    for d in "$SR_REVIEWS"/*/; do
      [ -d "$d" ] || continue
      slug="$(basename "$d")"
      [ -f "$d/review.json" ] || [ -f "$d/scope.json" ] || continue
      set -- "$@" "$slug"
    done
  fi
  for slug in "$@"; do
    sr_safe_slug "$slug"
    [ -f "$SR_REVIEWS/$slug/review.json" ] || [ -f "$SR_REVIEWS/$slug/scope.json" ] ||
      sr_die 2 "no review or scope for slug: $slug"
    row="$(rl_review_row "$slug" "$commit")" || sr_die 2 "cannot read review $slug"
    rows="$rows$row"$'\n'
  done
  printf '%s' "$rows" | jq -s --arg ref "$ref" --arg commit "$commit" \
    '{ref: $ref, commit: $commit, reviews: .}' || sr_die 2 "cannot assemble evidence"
  printf '%s' "$rows" | jq -se 'all(.[]; .applies == "current" or .applies == "header-only")' >/dev/null || exit 10
}

cmd="${1:-}"
[ -n "$cmd" ] || usage
shift
case "$cmd" in
  evidence) cmd_evidence "$@" ;;
  check) cmd_check "$@" ;;
  render) cmd_render "$@" ;;
  *) usage ;;
esac
