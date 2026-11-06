#!/usr/bin/env bash
# release.sh — evidence and record helper for /data-request:release (#407). The skill drafts the
# researcher-facing release body; this helper answers the questions it must not guess, and checks
# and renders the analyst's record. It writes no file: the skill writes the record, the guard checks it.
# No command here uses the network. Evidence reads local refs only: fetch before you run it.
#
#   fetch-command            print the one fetch command for this project, and run nothing: tags
#                            from origin, else the first configured remote, as
#                            git -C '<project root>' fetch --tags <remote>, so it runs from any
#                            directory. With no remote it
#                            prints a comment line that says to skip the fetch and say so. A fetch
#                            never decides a release: run it, report any failure to the human, and
#                            run evidence anyway. Only exit 2 or 11 of evidence stops the release.
#
#   evidence [--no-amend-hold] REF [SLUG...]
#                            does each .sqlreview review apply to the release at REF? JSON
#                            {ref, commit, reviews: [{slug, kind, sql_path, revision, applies,
#                            sql_sha256_reviewed, sql_sha256_at_ref, reviewed_commit,
#                            reviewed_commit_in_ref, other_paths_changed_since_review, assumptions,
#                            limitations, open_questions}]}.
#                            The reviews are read from the working tree (the newest record); the SQL
#                            is read from REF, never the working tree. applies:
#                              current         the SQL at REF is the reviewed SQL
#                              header-only     only the leading comment header differs
#                              changed         the SQL at REF differs: the review is stale for REF
#                              missing-at-ref  REF has no file at sql_path: the review may describe a draft
#                              unreviewed      scope only, no review
#                              unavailable     the reviewed SQL cannot be read from git at the
#                                              review's git_commit, or its SHA differs: reassess
#                              invalid         the record fails sqlreview.sh check
#                            reviewed_commit_in_ref: whether the review's git_commit is an ancestor of
#                            REF (null when the review has none or git cannot tell).
#                            other_paths_changed_since_review: committed paths outside sql_path and
#                            .sqlreview/ that differ between git_commit and REF (null when unknown).
#                            SQL can be unchanged while code, pins or exports change (#521).
#                            Amend gate: each .sqlreview/amendments/<request>.json is
#                            {schemaVersion: 1, parts: [{id: "P<n>", status, ...}]}, status
#                            "done" (with commit), "handed off" or "withdrawn" (with reason).
#                            A handed-off part, a done commit that is not verified in REF or a
#                            malformed record holds the release (exit 11, ids and fields on stderr).
#                            A done commit is verified against local refs only: rev-parse --verify
#                            to one full SHA, then merge-base --is-ancestor. Only exit 0 of the last
#                            step verifies. Any other result keeps the part open. A commit that is
#                            missing here gets the next line "run the fetch command, then run
#                            evidence again". A commit that is here but not in REF gets the next
#                            line "release from a ref that contains the commit". Evidence checks
#                            exactly the REF given: a local branch is not updated by a fetch, so
#                            name a remote-tracking ref such as origin/main, or a tag.
#                            An entry of .sqlreview/ledger.json at the amend stage whose artifact
#                            names a record file that does not exist holds too. An empty or
#                            malformed record or ledger holds. --no-amend-hold is for the engineer
#                            hand-off gate: it never exits 11 and reports each open part,
#                            malformed record or missing record on stderr as "amend note:".
#   amend-check FILE | amend-check --stdin [--name NAME]
#                            validate an amendment part-state record (.sqlreview/amendments/<request>.json),
#                            as the guard does on each Write, with the rules that the amend gate applies:
#                            one JSON object, schemaVersion 1, kind "amendment" when present, parts[]
#                            with a unique id P<n> and a status done (with commit), handed off or
#                            withdrawn (with reason). One "<field>: <rule>" line per violation, exit 4;
#                            "ok" otherwise. Never a value. --name NAME also checks that the record name
#                            has lower-case letters, digits and hyphens, as the guard needs
#   check FILE | check --stdin
#                            validate a release record (.sqlreview/releases/<tag>/release.json):
#                            one violation per line, exit 4; "ok" otherwise. Inside the project,
#                            an approved record without a criteria table fails when the sidecar
#                            at its commit has a live criterion
#   render FILE              the paste-ready release body (Markdown) from a valid record; a draft
#                            shows its pending claims and open questions. Before the limitations
#                            comes "## Criteria in this release" (the criteria table), or one line:
#                            "Criteria table held: <reasons>" for a held table, "Criteria are not
#                            itemised for this request." for a record without a criteria object
#   criteria TAG [--fingerprints FILE | --answers-invalid]
#                            the record's `criteria` object (the scaffold's criteria design, release-criteria.jq) from
#                            answers.intake.json and the one scope carrying criteria_status at TAG,
#                            the previous release's record (the greatest earlier stable X.Y.Z whose
#                            .sqlreview/releases/<tag>/release.json is in TAG's tree) and this tag's
#                            working-tree record, whose analyst decisions are kept while a row's
#                            note is unchanged. FILE is validate-answers --fingerprints output for
#                            answers.yaml at TAG; --answers-invalid says that validation failed;
#                            with neither the table is held (fingerprints-unchecked). Prints null
#                            when the criteria are not itemised (no sidecar, a schema 1 sidecar,
#                            or no live criterion at TAG); live criteria with no scope carrying
#                            criteria_status hold the table (no-owning-scope). Runs no Python.
#                            Exit 10 when held.
#
# Exit codes: 0 ok · 1 usage · 2 error (unknown ref or slug, no jq or git) · 3 not initialised ·
# 4 invalid record · 10 at least one review does not apply to REF (evidence), or the criteria
# table is held (criteria) · 11 release held by the amend gate (evidence): a part in
# .sqlreview/amendments/*.json is handed off, empty, malformed or done by a commit outside REF.
# The JSON is still printed. 11 takes precedence over 10. --no-amend-hold never gives 11.
set -u
SR_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
# shellcheck source=sqlreview-lib.sh
. "$SR_SCRIPT_DIR/sqlreview-lib.sh"
# shellcheck source=sqlreview-lifts.sh
. "$SR_SCRIPT_DIR/sqlreview-lifts.sh"   # for _sr_release_tag, the stable X.Y.Z rule

usage() {
  awk 'NR > 1 && !/^#/ { exit } NR > 1' "$0" | sed 's/^# \{0,1\}//' >&2
  exit 1
}

# Shared jq definitions: record validation and rendering. The criteria table is release-criteria.jq.
RL_JQ='include "sqlreview-identity";
include "sqlreview-noecho";
include "release-criteria";
def str: type == "string" and length > 0;
def arr: if type == "array" then . else [] end;
def kept: .decision == "accepted" or .decision == "reworded";
# A claim sourced from a research criterion is in the criteria table, never repeated under
# "Extraction Assumptions / Important limitations" (FR-018; rc_criterion_claim). $itemised: the
# record has a criteria object; a legacy record keeps every claim.
def limitation_shown($itemised): .section != "assumptions" or ($itemised | not) or (rc_criterion_claim | not);
# A source label is written into an HTML comment of the paste-ready body. A double hyphen, an angle bracket or a
# control character could close the comment and render text or a link. The finding names the field and the rule.
def label_errors($cid):
  ("slug", "item", "path", "ref") as $f
  | if has($f) and .[$f] != null and (.[$f] | type) != "string" then "\($cid): source \($f) must be a string"
    elif (.[$f] | type) == "string" and (.[$f] | test("--|<|>|[\\x00-\\x1f\\x7f]"))
    then "\($cid): source \($f) must not contain --, < or > or control characters"
    else empty end;
def src_kind_errors($cid; $kept; $ev):
  if .kind == "review" then
    if (.slug | str) and (.item | str) and (.revision | type) == "number" then
      if $kept | not then empty
      else . as $s | ([$ev[] | select(.slug == $s.slug)][0]) as $e
        | if $e == null then "\($cid): review \(.slug | safe_slug) is not in evidence"
          elif $e.revision != .revision then
            "\($cid): review \(.slug | safe_slug) revision \(.revision) is not the revision in evidence (\($e.revision))"
          elif $e.applies == "current" or $e.applies == "header-only" then empty
          else "\($cid): review \(.slug | safe_slug) does not apply to the release (\($e.applies)); cite the release files that support the claim, or raise it as a question" end
      end
    else "\($cid): a review source needs slug, item and revision" end
  elif .kind == "scope" then
    if (.slug | str) and (.revision | type) == "number" then empty
    else "\($cid): a scope source needs slug and revision" end
  elif .kind == "file" then
    if (.path | str) and (.ref | str) then empty else "\($cid): a file source needs path and ref" end
  else "\($cid): source kind must be review, scope or file" end;
def src_errors($cid; $kept; $ev):
  if type != "object" then "\($cid): every source must be an object"
  else label_errors($cid), src_kind_errors($cid; $kept; $ev) end;
def claim_errors($ev):
  (.id | safe_id("^C[1-9][0-9]*$")) as $id
  | (if (.id | str) and (.id | test("^C[1-9][0-9]*$")) then empty else "claim id must be C<n>" end),
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
  (.id | safe_id("^Q[1-9][0-9]*$")) as $id
  | (if (.id | str) and (.id | test("^Q[1-9][0-9]*$")) then empty else "question id must be Q<n>" end),
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
      (.claims | arr | map(objects | .id) | group_by(.)[] | select(length > 1) | "duplicate claim id \(.[0] | safe_id("^C[1-9][0-9]*$"))"),
      (.questions | arr | map(objects | .id) | group_by(.)[] | select(length > 1) | "duplicate question id \(.[0] | safe_id("^Q[1-9][0-9]*$"))"),
      (if .status != "approved" then empty else
         (.claims | arr | .[] | objects | select(.decision == "pending") | "approved: \(.id | safe_id("^C[1-9][0-9]*$")) is pending"),
         (.questions | arr | .[] | objects | select(.resolution == null) | "approved: \(.id | safe_id("^Q[1-9][0-9]*$")) is unresolved"),
         (((.criteria | type) == "object") as $itemised
          | ("summary", "assumptions") as $s
          | if any(.claims | arr | .[] | objects; .section == $s and kept and limitation_shown($itemised)) then empty
            else "approved: no kept claim in \($s)" end)
       end),
      rc_errors
  end;
def src_label:
  if .kind == "review" then "review \(.slug) \(.item) r\(.revision)"
  elif .kind == "scope" then "scope \(.slug)\(if .item then " " + .item else "" end) r\(.revision)"
  else "file \(.path)@\(.ref)" end;
def claim_line:
  "- \(if .decision == "pending" then "[pending] " + .proposed else .final end)"
  + " <!-- \(.id): \(.sources | map(src_label) | join("; ")) -->";
def section_lines($s):
  ((.criteria | type) == "object") as $itemised
  | [.claims[] | select(.section == $s and (kept or .decision == "pending") and limitation_shown($itemised)) | claim_line]
  | if length == 0 then ["_No claims yet._"] else . end | join("\n");
def render:
  (if .status == "draft"
   then "> **Draft, not approved.** Resolve the pending claims and open questions below before release.\n\n"
   else "" end)
  + "## Extraction Summary\n\n" + section_lines("summary") + "\n\n"
  + rc_section
  + "## Extraction Assumptions / Important limitations\n\n" + section_lines("assumptions") + "\n"
  + ([.questions[] | select(.resolution == null) | "- \(.id): \(.text)"]
     | if length == 0 then "" else "\n## Open questions (resolve before release)\n\n" + join("\n") + "\n" end);
'

# An approved record with no criteria table, at a commit whose answers.intake.json is a schema 2
# sidecar with a live criterion: `release.sh criteria` gives such a tag a table (held, at worst, as
# no-owning-scope), so null there would tell the researcher "not itemised" falsely (FR-017). Read
# only when the record sits in a .sqlreview/ project whose git history holds its commit; elsewhere
# (a record checked outside its repository) the held table from `criteria` is the gate.
rl_itemised_without_table() { # <record file>; prints the violation, returns 4 when found
  local commit tag root
  commit="$(jq -r 'select(type == "object" and .status == "approved" and .criteria == null) | .commit | strings' "$1" 2>/dev/null)"
  case "$commit" in ""|*[!0-9a-f]*) return 0 ;; esac
  command -v git >/dev/null 2>&1 || return 0
  root="$(sr_find_root)" || return 0
  commit="$(git -C "$root" rev-parse --verify --quiet "$commit^{commit}" 2>/dev/null)" || return 0
  git -C "$root" cat-file -e "$commit:answers.intake.json" 2>/dev/null || return 0
  git -C "$root" show "$commit:answers.intake.json" 2>/dev/null |
    jq -e '.schemaVersion == 2 and any(.criteria | if type == "array" then .[] else empty end;
             type == "object" and .withdrawn == null)' >/dev/null 2>&1 || return 0
  tag="$(jq -r '.tag | strings | select(test("^[A-Za-z0-9][A-Za-z0-9._-]*$"))' "$1" 2>/dev/null)"
  printf 'approved: criteria are itemised at %s; embed the release.sh criteria table\n' "${tag:-the release commit}"
  return 4
}

# Validate a record read from $1 (a file) and print its violations; returns 4 when any.
rl_check_file() {
  local out more
  out="$(jq -r -L "$SR_SCRIPT_DIR" "$RL_JQ"' release_errors' "$1" 2>/dev/null)" || { printf 'not valid JSON\n'; return 4; }
  more="$(rl_itemised_without_table "$1")"
  [ -z "$out" ] && [ -z "$more" ] && return 0
  [ -z "$out" ] || printf '%s\n' "$out"
  [ -z "$more" ] || printf '%s\n' "$more"
  return 4
}

cmd_check() {
  sr_need_jq
  local f tmp rc
  case "${1:-}" in
    --stdin) [ $# -eq 1 ] || usage
      tmp="$(mktemp)" || sr_die 2 "mktemp failed"
      cat > "$tmp"
      rl_check_file "$tmp"; rc=$?
      rm -f -- "$tmp" ;;
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
rl_review_row() ( # <slug> <commit>
  local slug="$1" commit="$2" d="$SR_REVIEWS/$1" doc kind sql reviewed at="" body_at="" applies tmp gc inref="null" binding others="null"
  doc="$(sr_doc_for "$slug")" || return 1
  kind="$(jq -r '.kind // ""' "$doc")"
  if ! bash "$SR_SCRIPT_DIR/sqlreview.sh" check "$doc" >/dev/null 2>&1; then
    jq -nc --arg slug "$slug" --arg kind "$kind" \
      '{slug: $slug, kind: $kind, sql_path: null, revision: null, applies: "invalid"}'
    return 0
  fi
  sql="$(jq -r '.sql_path' "$doc")"
  # A stored path is read from git at REF, never from the work tree, so a legacy record bound to a path the
  # input policy now refuses must not block the release: structural check only (#516).
  sr_safe_path "$sql"
  reviewed="$(jq -r '.sql_sha256 // ""' "$doc")"
  local rc
  tmp="$(sr_source_workspace)" || return 2
  trap 'rm -rf "$tmp"' EXIT
  trap 'exit 2' HUP INT TERM
  applies=unavailable
  if [ "$kind" = scope ]; then applies=unreviewed
  else
    sr_source_auth "$doc" "$tmp/recorded.sql"; rc=$?
    case "$rc" in 0) ;; 6) ;; *) return 2 ;; esac
  fi
  if [ "$kind" = scope ] || [ "$rc" = 0 ]; then
    sr_source_show "$commit" "$sql" "$tmp/release.sql" 2>/dev/null; rc=$?
    case "$rc" in
      0)
        at="$(sr_sha256 "$tmp/release.sql")" || return 2
        body_at="$(sr_body_sha256 "$tmp/release.sql")" || return 2
        if [ "$kind" != scope ]; then
          sr_binding "$doc" "$tmp/release.sql" "$tmp/recorded.sql"; binding=$?
          case "$binding" in 0) applies=current ;; 10) applies=header-only ;; *) applies=changed ;; esac
        fi ;;
      6) [ "$kind" = scope ] || applies=missing-at-ref ;;
      *) return 2 ;;
    esac
  fi
  gc="$(jq -r '.git_commit // "" | strings' "$doc")"
  case "$gc" in
    ""|*[!0-9a-f]*) ;;
    *) if git -C "$SR_ROOT" merge-base --is-ancestor "$gc" "$commit" 2>/dev/null; then inref=true
       elif [ $? -eq 1 ]; then inref=false; fi
       # SQL can stay identical while code, pins or exports change (#521). Report the paths as evidence;
       # the reviewer decides whether a change matters.
       if git -C "$SR_ROOT" diff --name-only -z "$gc" "$commit" -- . ":(exclude).sqlreview" ":(exclude)$sql" \
         > "$tmp/others" 2>/dev/null; then
         others="$(tr '\0' '\n' < "$tmp/others" | jq -Rsc 'split("\n") | map(select(length > 0))')" || return 2
       fi ;;
  esac
  local question_doc question_rc
  # Question evidence reads no SQL: structural path checks only, as status does.
  question_doc="$(SR_Q_STRUCTURAL=1 bash "$SR_SCRIPT_DIR/sqlreview.sh" questions "$slug" "$kind")" || {
    question_rc=$?
    [ "$question_rc" -eq 4 ] || sr_die 2 "cannot read shared question evidence"
    jq -nc --arg slug "$slug" --arg kind "$kind" \
      '{slug: $slug, kind: $kind, sql_path: null, revision: null, applies: "invalid"}'
    return 0
  }
  jq -c --argjson question_doc "$question_doc" --arg slug "$slug" --arg applies "$applies" --arg at "$at" --arg body_at "$body_at" --argjson inref "$inref" --argjson others "$others" '
    def items: [(. // [])[] | {id, text, rationale, confirmed_revision}];
    {slug: $slug, kind, sql_path, revision, applies: $applies,
     sql_sha256_reviewed: .sql_sha256, sql_sha256_at_ref: (if $at == "" then null else $at end),
     sql_body_sha256_reviewed: (.sql_body_sha256 // null), sql_body_sha256_at_ref: (if $body_at == "" then null else $body_at end),
     reviewed_commit: .git_commit, reviewed_commit_in_ref: $inref, other_paths_changed_since_review: $others,
     assumptions: (.assumptions | items), limitations: (.limitations | items),
     questions: $question_doc.questions,
     open_questions: [$question_doc.questions[] | select(.status == "open") | .text]}' "$doc"
)

# The amendment record validator (SR_AMEND_JQ) and the ledger filter (SR_AMEND_LEDGER_JQ) live in
# sqlreview-lib.sh, because status reads the same definitions.

# One jq read of .sqlreview/ledger.json. Sets $missing to one hold line per amended entry whose
# amend artifact names a record file that does not exist. An amended entry that names no record is
# a single-part amendment: it writes none, so it does not hold. A ledger that is empty or not valid
# JSON also holds.
rl_amend_ledger_missing() {
  local ledger="$SR_ROOT/$SR_DIR/ledger.json" line nl='
' next="$SR_AMEND_NEXT"
  missing=""
  [ -e "$ledger" ] || return 0
  sr_no_symlinks "$ledger" || exit 2
  while read -r line; do
    case "$line" in
      "") ;;
      bad) missing="$missing${nl}$SR_AMEND_LEDGER_HELD. Next: $SR_AMEND_LEDGER_NEXT" ;;
      path*) line="${line#path?}"
        [ -f "$SR_ROOT/$line" ] ||
          missing="$missing${nl}release held: the ledger shows an amendment but $line is missing. Next: $next" ;;
    esac
  done <<EOT
$(jq -rs "$SR_AMEND_LEDGER_JQ" "$ledger" 2>/dev/null || printf 'bad\n')
EOT
}

# Print, and never run, the one fetch command: tags from origin, else the first configured remote.
# The command names the project root with -C, so it fetches into the project that the remotes came
# from, whatever the caller's directory is. The root is single-quoted, and each embedded single quote
# is written as '\'' . This is plain POSIX quoting, because printf %q differs between Bash versions.
# No remote prints a comment line, so a shell that runs the output does nothing. Every skill and
# every hint takes the command from here, so there is one instruction. This function uses no network.
rl_fetch_command() {
  local remote root nl='
'
  remote="$(git -C "$SR_ROOT" remote 2>/dev/null </dev/null)" || remote=""
  case "$nl$remote$nl" in
    *"${nl}origin${nl}"*) remote=origin ;;
    *) remote="${remote%%"$nl"*}" ;;
  esac
  case "$remote" in
    ""|-*) printf '# no remote is configured: skip the fetch and say so\n' ;;
    *)
      root="$(printf '%s\n' "$SR_ROOT" | sed "s/'/'\\\\''/g")"
      printf "git -C '%s' fetch --tags %q\n" "$root" "$remote" ;;
  esac
}

cmd_fetch_command() {
  [ $# -eq 0 ] || usage
  command -v git >/dev/null 2>&1 || sr_die 2 "git is required to read the remotes"
  sr_require_root
  rl_fetch_command
}

# The fixed line for a local branch that is behind its upstream. It compares two local refs and
# uses no network. A fetch moves origin/<branch>, never the local branch itself.
rl_behind_note() { # <ref>
  local n
  git -C "$SR_ROOT" show-ref --verify --quiet "refs/heads/$1" </dev/null 2>/dev/null || return 0
  n="$(git -C "$SR_ROOT" rev-list --count "$1..$1@{upstream}" 2>/dev/null </dev/null)" || return 0
  case "$n" in ""|0) return 0 ;; esac
  printf 'next: %s is behind its upstream: fast-forward it, or release from the remote-tracking ref (such as origin/main), then run evidence again\n' "$1" >&2
}

# Verify one done commit as /data-request:amend step 2 does, against local refs only: resolve to
# one full SHA, then merge-base --is-ancestor. Only exit 0 of the last step verifies the part. Returns 0 verified,
# 1 not in the release, 3 not a commit here, 4 check could not run (such as exit 128). stdin is
# closed so git cannot read the record rows that the caller is looping over.
rl_amend_verify() { # <commit> <release commit>
  local full rc=0
  full="$(git -C "$SR_ROOT" rev-parse --verify --quiet "$1^{commit}" 2>/dev/null </dev/null)" || return 3
  git -C "$SR_ROOT" merge-base --is-ancestor "$full" "$2" </dev/null >/dev/null 2>&1 || rc=$?
  case "$rc" in 0) return 0 ;; 1) return 1 ;; *) return 4 ;; esac
}

# Hold while any part in .sqlreview/amendments/*.json is handed off, malformed, or done by a
# commit that is not verified in the release. One jq read per document; the messages name part
# ids, files and fields only. Prints the hold on stderr and returns 11 when held. With mode "note"
# it verifies no commit, prints "amend note:" lines for the open parts and findings, and returns 0.
rl_amend_hold() { # <ref> <commit> [note]
  local ref="$1" commit="$2" mode="${3:-hold}" f rel kind id field c rows open="" stale="" unver="" bad="" missing="" vrc fc nl='
'
  for f in "$SR_ROOT/$SR_DIR"/amendments/*.json; do
    [ -e "$f" ] || continue
    # A record file name prints only in the shape that the guard allows (no-echo), as status does.
    sr_amend_label "$f"
    rel="$SR_DIR/amendments/$SR_AMEND_NAME.json"
    sr_no_symlinks "$f" || exit 2
    rows="$(sr_amend_rows "$f")"
    while IFS="$(printf '\t')" read -r kind id field c; do
      if [ "$kind" = open ]; then open="$open $id"
      elif [ "$kind" = bad ]; then bad="$bad${nl}release held: $rel: field $field is missing or invalid"
      elif [ "$kind" = done ] && [ "$mode" = hold ]; then
        vrc=0
        rl_amend_verify "$c" "$commit" || vrc=$?
        case "$vrc" in
          0) ;;
          1) stale="$stale $id" ;;
          *) unver="$unver $id" ;;
        esac
      fi
    done <<EOT
$rows
EOT
  done
  rl_amend_ledger_missing  # sets missing: amended in the ledger, record file named but absent
  [ -n "$open$stale$unver$bad$missing" ] || return 0
  if [ "$mode" = note ]; then
    [ -z "$open" ] || printf 'amend note: amend part handed off and open:%s\n' "$open" >&2
    [ -z "$bad" ] || printf '%s\n' "${bad#?}" | sed 's/^release held:/amend note:/' >&2
    [ -z "$missing" ] || printf '%s\n' "${missing#?}" | sed 's/^release held:/amend note:/' >&2
    printf 'amend note: %s\n' "this does not block the hand-off, but the release stays held until the record is closed" >&2
    return 0
  fi
  [ -z "$open" ] || printf 'release held: amend part handed off and open:%s\n' "$open" >&2
  [ -z "$stale" ] || printf 'release held: amend part done by a commit not in %s:%s\n' "$ref" "$stale" >&2
  [ -z "$unver" ] || printf 'release held: amend part done but its commit is not verified (rev-parse or merge-base did not succeed):%s\n' "$unver" >&2
  [ -z "$bad" ] || printf '%s\n' "${bad#?}" >&2
  [ -z "$missing" ] || printf '%s\n' "${missing#?}" >&2
  # Each next line names the real part id, so the reader can paste it (N2). Part ids are the P<n>
  # values already checked by SR_AMEND_JQ, so they carry no record text.
  for id in $open; do
    printf 'next: the engineer comments done: %s <commit> or the analyst comments withdrawn: %s <reason> on the deliverable PR, then the record is updated\n' "$id" "$id" >&2
  done
  for id in $stale; do
    printf 'next: %s is done by a commit outside %s: release from a ref that contains the commit, or the engineer comments done: %s <commit> with a commit in %s\n' "$id" "$ref" "$id" "$ref" >&2
  done
  if [ -n "$unver" ]; then
    fc="$(rl_fetch_command)"
    case "$fc" in
      "#"*) fc="no remote is configured, so fetch nothing: check that the commit is in this clone" ;;
      *) fc="run $fc" ;;
    esac
    for id in $unver; do
      printf 'next: the commit of %s is missing here or does not resolve: %s, then run evidence again\n' "$id" "$fc" >&2
    done
  fi
  [ -z "$stale$unver" ] || rl_behind_note "$ref"
  [ -z "$bad" ] || printf '%s\n' "next: correct each record field named above, then run evidence again" >&2
  return 11
}

cmd_evidence() {
  local amend=hold
  if [ "${1:-}" = --no-amend-hold ]; then amend=note; shift; fi
  [ $# -ge 1 ] || usage
  sr_need_jq
  command -v git >/dev/null 2>&1 || sr_die 2 "git is required to read the release"
  local ref="$1" commit slug rows="" row
  shift
  sr_require_root
  sr_partial_gate || exit 2
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
  if [ "$amend" = note ]; then rl_amend_hold "$ref" "$commit" note
  else rl_amend_hold "$ref" "$commit" || exit 11
  fi
  printf '%s' "$rows" | jq -se 'all(.[]; .applies == "current" or .applies == "header-only")' >/dev/null || exit 10
}

# Is the owning scope current for the SQL at COMMIT? The body rule of carry_criteria_rows in
# sqlreview-carry.jq: the full sha256 is equal (both absent counts), or the body sha256 of the SQL at
# COMMIT equals a body the scope recorded, so a header-only change is current. The recorded bodies are
# sql_body_sha256, each header_revisions body, and the body of the SQL at the scope's own git_commit
# when its sha256 equals the recorded one (hash-only reviews, #548: no scope.source.sql copy exists).
# One git show per file. Exit 0 current, 1 stale, 2 operational.
rl_scope_current() { # <slug> <commit>
  local slug="$1" commit="$2" doc sql full gc at="" body tmp known
  doc="$(git -C "$SR_ROOT" show "$commit:./$SR_DIR/reviews/$slug/scope.json" 2>/dev/null)" || return 2
  sql="$(printf '%s' "$doc" | jq -r '.sql_path // "" | strings' 2>/dev/null)" || return 2
  full="$(printf '%s' "$doc" | jq -r '.sql_sha256 // "" | strings' 2>/dev/null)" || return 2
  [ -z "$sql" ] || sr_safe_path "$sql"
  tmp="$(mktemp -d)" || return 2
  if [ -n "$sql" ] && git -C "$SR_ROOT" show "$commit:./$sql" > "$tmp/sql" 2>/dev/null; then at="$(sr_sha256 "$tmp/sql")"; fi
  if [ "$at" = "$full" ]; then rm -rf "$tmp"; return 0; fi
  if [ -z "$at" ] || [ -z "$full" ] || ! body="$(sr_body_sha256 "$tmp/sql")"; then rm -rf "$tmp"; return 1; fi
  known="$(printf '%s' "$doc" | jq -r '(.sql_body_sha256, (.header_revisions // [] | .[]? | .sql_body_sha256)) | strings' 2>/dev/null)"
  gc="$(printf '%s' "$doc" | jq -r '.git_commit // "" | strings' 2>/dev/null)" || gc=""
  case "$gc" in
    ""|*[!0-9a-f]*) ;;
    *) if git -C "$SR_ROOT" show "$gc:./$sql" > "$tmp/base" 2>/dev/null && [ "$(sr_sha256 "$tmp/base")" = "$full" ]; then
         known="$known
$(sr_body_sha256 "$tmp/base" || true)"
       fi ;;
  esac
  rm -rf "$tmp"
  printf '%s\n' "$known" | grep -qx "$body"
}

# Greatest stable release below TAG whose record is in TAG's tree (research R9); prints nothing for a
# first release, or when TAG has no X.Y.Z version (a pre-release TAG compares by its X.Y.Z). Stable is
# _sr_release_tag's rule; jq sorts the versions numerically, since Bash 3.2 has no sort -V.
release_previous_tag() { # <tag>  (needs SR_ROOT)
  local tag="$1" commit path name names=""
  commit="$(git -C "$SR_ROOT" rev-parse --verify --quiet "$tag^{commit}" 2>/dev/null)" || return 1
  while IFS= read -r path; do
    case "$path" in "$SR_DIR"/releases/*/release.json) ;; *) continue ;; esac
    name="${path#"$SR_DIR"/releases/}"; name="${name%/release.json}"
    case "$name" in */*) continue ;; esac
    _sr_release_tag "$name" || continue
    names="$names$name"$'\n'
  done <<EOF
$(git -C "$SR_ROOT" ls-tree -r --name-only "$commit" -- "$SR_DIR/releases" 2>/dev/null)
EOF
  printf '%s' "$names" | jq -Rnr --arg tag "$tag" '
    def ver: capture("^v?(?<a>[0-9]+)\\.(?<b>[0-9]+)\\.(?<c>[0-9]+)") | [.a, .b, .c] | map(tonumber);
    ([$tag | ver][0]) as $cur
    | if $cur == null then empty
      else [inputs | select(length > 0) | {name: ., v: ver} | select(.v < $cur)]
        | sort_by(.v, .name) | last | .name // empty end'
}

cmd_criteria() {
  [ $# -ge 1 ] || usage
  local tag="$1" mode=unchecked fpfile="" fp=null commit tmp intake path slug doc row rows="" scopes stale=false review_prefix previous_src
  local prev previous=null current=null f out
  shift
  case "$tag" in ""|-*) usage ;; esac
  while [ $# -gt 0 ]; do
    case "$1" in
      --fingerprints) { [ $# -ge 2 ] && [ "$mode" = unchecked ]; } || usage
        mode=fingerprints; fpfile="$2"; shift 2 ;;
      --answers-invalid) [ "$mode" = unchecked ] || usage
        mode=answers-invalid; shift ;;
      *) usage ;;
    esac
  done
  sr_need_jq
  command -v git >/dev/null 2>&1 || sr_die 2 "git is required to read the release"
  sr_require_root
  sr_partial_gate || exit 2
  commit="$(git -C "$SR_ROOT" rev-parse --verify --quiet "$tag^{commit}" 2>/dev/null)" ||
    sr_die 2 "unknown ref: $tag (give the release tag)"
  if [ "$mode" = fingerprints ]; then
    [ -f "$fpfile" ] || sr_die 2 "no such fingerprints file"
    fp="$(jq -sce '
      ["cohort_entry_event", "exclusion_criteria", "inclusion_criteria", "requested_data_elements"] as $k
      | if length == 1 and (.[0] | type == "object" and keys == $k
             and all(.[]; type == "string" and test("^sha256:[0-9a-f]{64}\\z")))
        then .[0] else error("fingerprints") end' "$fpfile" 2>/dev/null)" ||
      sr_die 2 "invalid fingerprints file: pass the validate-answers --fingerprints output for answers.yaml at $tag"
  fi
  # The analyst's sidecar at the tag (the git top level), read through `sqlreview.sh intake` so its
  # validation applies. No sidecar: the criteria are not itemised.
  if ! git -C "$SR_ROOT" cat-file -e "$commit:answers.intake.json" 2>/dev/null; then
    printf 'null\n'
    return 0
  fi
  tmp="$(mktemp)" || sr_die 2 "mktemp failed"
  if ! git -C "$SR_ROOT" show "$commit:answers.intake.json" > "$tmp" 2>/dev/null; then
    rm -f "$tmp"; sr_die 2 "cannot read answers.intake.json at $tag"
  fi
  # A render of a committed blob, outside the project: mark it so intake accepts it there.
  if ! sr_write_render_marker "$tmp"; then
    rm -f "$tmp" "$tmp.sqlreview-render"; sr_die 2 "cannot mark answers.intake.json at $tag"
  fi
  if ! intake="$(bash "$SR_SCRIPT_DIR/sqlreview.sh" intake "$tmp" 1 2>/dev/null)"; then
    rm -f "$tmp" "$tmp.sqlreview-render"; sr_die 2 "invalid analyst intake (answers.intake.json) at $tag; run validate-answers and correct the sidecar"
  fi
  rm -f "$tmp" "$tmp.sqlreview-render"
  # Every scope at the tag that carries criteria_status; exactly one may own the criteria (research R6).
  review_prefix="$SR_DIR/reviews/"
  while IFS= read -r path; do
    case "$path" in "$SR_DIR"/reviews/*/scope.json) ;; *) continue ;; esac
    slug="${path#$review_prefix}"; slug="${slug%/scope.json}"
    case "$slug" in */*|.|..|*[!A-Za-z0-9_%.-]*) sr_die 2 "unsafe review directory name at $tag" ;; esac
    doc="$(git -C "$SR_ROOT" show "$commit:./$path" 2>/dev/null)" || sr_die 2 "cannot read $slug/scope.json at $tag"
    row="$(printf '%s' "$doc" | jq -c --arg slug "$slug" '
      select(type == "object" and has("criteria_status")) | {slug: $slug, revision, criteria_status}' 2>/dev/null)" ||
      sr_die 2 "cannot read $slug/scope.json at $tag"
    [ -z "$row" ] || rows="$rows$row"$'\n'
  done <<EOF
$(git -C "$SR_ROOT" ls-tree -r --name-only "$commit" -- "$SR_DIR/reviews" 2>/dev/null)
EOF
  scopes="$(printf '%s' "$rows" | jq -sc '.')" || sr_die 2 "cannot assemble the scopes at $tag"
  # The owning scope's review must apply to the tag, by release.sh evidence's rule (current or
  # header-only); a scope with no review in the working tree is stale too.
  if [ "$(printf '%s' "$scopes" | jq 'length')" = 1 ]; then
    slug="$(printf '%s' "$scopes" | jq -r '.[0].slug')"
    sr_safe_slug "$slug"
    if [ -f "$SR_REVIEWS/$slug/review.json" ] || [ -f "$SR_REVIEWS/$slug/scope.json" ]; then
      row="$(rl_review_row "$slug" "$commit")" || sr_die 2 "cannot read review $slug"
      printf '%s' "$row" | jq -e '.applies == "current" or .applies == "header-only"' >/dev/null || stale=true
    else
      stale=true
    fi
  fi
  prev="$(release_previous_tag "$tag")" || sr_die 2 "cannot list the release records at $tag"
  if [ -n "$prev" ]; then
    previous_src="$(git -C "$SR_ROOT" show "$commit:./$SR_DIR/releases/$prev/release.json" 2>/dev/null)"
    previous="$(printf '%s' "$previous_src" | jq -c --arg tag "$prev" '{tag: $tag, criteria: (.criteria // null)}' 2>/dev/null)" ||
      sr_die 2 "cannot read the release record of $prev at $tag"
  fi
  # The record of this tag in the working tree: its analyst decisions survive while the note of a row is unchanged.
  case "$tag" in
    *..*|*[!A-Za-z0-9._-]*|[!A-Za-z0-9]*) ;;
    *) f="$SR_ROOT/$SR_DIR/releases/$tag/release.json"
       sr_no_symlinks "$f" || exit 2
       if [ -f "$f" ]; then current="$(jq -c '.criteria // null' "$f" 2>/dev/null)" || current=null; fi
       [ -n "$current" ] || current=null ;;
  esac
  # The states of the owning scope describe the SQL it recorded. A changed SQL body at the tag holds the table.
  local scope_stale=false
  if [ "$(printf '%s' "$scopes" | jq 'length')" = 1 ]; then
    slug="$(printf '%s' "$scopes" | jq -r '.[0].slug')"
    rl_scope_current "$slug" "$commit"
    case $? in
      0) ;;
      1) scope_stale=true
         printf 'criteria held: scope %s is stale (scope-stale): rescope with /data-request:bootstrap, then publish\n' "$slug" >&2 ;;
      *) sr_die 2 "cannot read scope $slug at $tag" ;;
    esac
  fi
  out="$(jq -n -L "$SR_SCRIPT_DIR" --argjson intake "$intake" --argjson scopes "$scopes" --argjson stale "$stale" \
    --argjson previous "$previous" --argjson current "$current" --argjson fp "$fp" --arg mode "$mode" \
    --argjson scope_stale "$scope_stale" \
    'include "release-criteria"; rc_build($intake; $scopes; $stale; $previous; $current; $fp; $mode)
     | rc_scope_stale($scope_stale)')" ||
    sr_die 2 "cannot build the criteria table"
  printf '%s\n' "$out"
  printf '%s' "$out" | jq -e '. == null or .status == "complete"' >/dev/null || exit 10
}

cmd_amend_check() {
  sr_need_jq
  local rows kind id field rule out="" rc=0 nl='
' name="" have_name=0 target=""
  # Arguments: FILE or --stdin, then optionally --name NAME, the record name from the file name.
  while [ $# -gt 0 ]; do
    case "$1" in
      --stdin) [ -z "$target" ] || usage; target=--stdin ;;
      --name) [ $# -ge 2 ] && [ "$have_name" = 0 ] || usage; name="$2"; have_name=1; shift ;;
      "") usage ;;
      *) [ -z "$target" ] || usage; target="$1" ;;
    esac
    shift
  done
  [ -n "$target" ] || usage
  # The rows are the ones the evidence hold reads (sr_amend_rows, SR_AMEND_JQ): a parse failure
  # is one fixed row, because jq error text can quote a value (no-echo). Only bad rows are findings
  # here. Standard input goes straight to jq, with no temporary file to clean up.
  if [ "$target" = --stdin ]; then
    rows="$(sr_amend_rows)"
  else
    # Inside the project, data/ and unreviewed sql/ paths are refused (#516). The output is rule lines only.
    sr_guard_input "$target" outside-ok
    [ -f "$target" ] || sr_die 2 "amend-check: the record file does not exist"
    rows="$(sr_amend_rows "$target")"
  fi
  if [ "$have_name" = 1 ] && ! sr_amend_name_ok "$name"; then out="(name): $SR_AMEND_NAME_RULE"; fi
  while IFS="$(printf '\t')" read -r kind id field rule; do
    if [ "$kind" = bad ]; then out="$out${out:+$nl}$field: $rule"; fi
  done <<EOT
$rows
EOT
  if [ -n "$out" ]; then printf '%s\n' "$out"; rc=4; else printf 'ok\n'; fi
  return "$rc"
}

cmd="${1:-}"
[ -n "$cmd" ] || usage
shift
# File arguments go through the shared guard (#516): no data/, no unreviewed sql/, nothing outside the project.
case "$cmd" in
  # A release record is checked or rendered anywhere (it is not project input), so only data/ and unreviewed
  # sql/ inside an initialised project are refused, as for amend-check.
  check) [ $# -lt 1 ] || [ "$1" = --stdin ] || sr_guard_input "$1" outside-ok ;;
  render) [ $# -lt 1 ] || sr_guard_input "$1" outside-ok ;;
esac
case "$cmd" in
  evidence) cmd_evidence "$@" ;;
  amend-check) cmd_amend_check "$@" ;;
  fetch-command) cmd_fetch_command "$@" ;;
  check) cmd_check "$@" ;;
  render) cmd_render "$@" ;;
  criteria) cmd_criteria "$@" ;;
  *) usage ;;
esac
