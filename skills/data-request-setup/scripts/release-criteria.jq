# The release body's "Criteria in this release" table (spec 017, contracts/release-criteria-table.md).
# A def-only module for release.sh: `criteria` builds the record's `criteria` object, `check`
# validates it (rc_errors) and `render` places its section (rc_section) before "Extraction
# Assumptions / Important limitations". Load it with `jq -L <this directory>`; it includes the
# criteria vocabulary (sqlreview-criteria.jq). Diagnostics name ids, fields and reasons, never values.
#
# `criteria` object: {previous_tag, scope: {slug, revision} | null, status: complete | held,
# held_reasons: [...], rows: [...]}; null (or an absent `criteria`) is a legacy request, rendered as
# one "not itemised" line. A row: {id, kind, text, state, proposed_note, final_note, decision,
# change, previous_state?, replaced_by?, decided_by?, decided_at?}. `state` is the owning scope's
# state at the tag, "withdrawn" for a criterion the researcher withdrew, or null (held) when no
# usable state is recorded. Decisions follow the claims: pending, accepted, reworded, rejected.
#
# Change values: "—" (no comparable previous table), unchanged, changed (previous_state),
# new, text-reworded, withdrawn, replaced (replaced_by). A withdrawn criterion is listed while
# there is no previous table, or when the previous table lists it with a state other than
# "withdrawn"; one the previous table already showed withdrawn, or did not list, is left out, so a
# withdrawal is reported once, in the release where it happened.
#
# A claim is criterion-sourced when any of its sources is a scope source whose `item` is a
# criterion id (^[NIED][1-9][0-9]*$, the key of the scope's criteria_status row). Such claims are
# never rendered under "Extraction Assumptions / Important limitations" (FR-018): the table carries
# them (rc_criterion_claim). Only a record with a criteria object hides them; a legacy record keeps
# every claim.
include "sqlreview-criteria";

def rc_str: type == "string" and test("\\S");
def rc_cell: tostring | gsub("\\|"; "&#124;") | gsub("[\r\n]+"; "<br>");
def rc_fp_fields: ["cohort_entry_event", "inclusion_criteria", "exclusion_criteria", "requested_data_elements"];
def rc_changes: ["—", "unchanged", "changed", "new", "text-reworded", "withdrawn", "replaced"];
def rc_decisions: ["pending", "accepted", "reworded", "rejected"];
def rc_id: type == "string" and test("^[NIED][1-9][0-9]*\\z");
def rc_criterion_claim:
  any(.sources | if type == "array" then .[] else empty end;
      type == "object" and .kind == "scope" and (.item | rc_id));

# Held reasons in contract order; the rank sorts them, then ids in criteria order.
def rc_reason_rank:
  if . == "review-stale" then [0, 0, 0]
  elif startswith("state-missing:") then [1] + (.[14:] | {id: ., kind: crit_kind_of_id} | crit_order)
  elif startswith("fingerprint-mismatch:") then [2, (.[21:] as $f | rc_fp_fields | index([$f])), 0]
  elif . == "owning-scope-ambiguous" then [3, 0, 0]
  elif startswith("note-rejected:") then [4] + (.[14:] | {id: ., kind: crit_kind_of_id} | crit_order)
  elif . == "answers-invalid" then [5, 0, 0]
  else [6, 0, 0] end;
def rc_reason_ok:
  type == "string"
  and (test("^(review-stale|owning-scope-ambiguous|answers-invalid|fingerprints-unchecked)\\z")
       or test("^(state-missing|note-rejected):[NIED][1-9][0-9]*\\z")
       or (startswith("fingerprint-mismatch:") and (.[21:] as $f | rc_fp_fields | index([$f])) != null));

# --- build -------------------------------------------------------------------------------------

# A scope criteria_status row usable for criterion $c: a state its kind allows, with the reason,
# flag or researcher basis that state needs (sqlreview.sh criteria's rules, re-checked at the tag).
def rc_usable($c):
  type == "object" and (.state | type) == "string"
  and (.state as $s | crit_states($c.kind) | index([$s])) != null
  and (if (.state as $s | crit_reason_required | index([$s])) != null then .reason | rc_str else true end)
  and (if .state == "flagged" then (.flag | type) == "object" and (.flag.output | rc_str) and (.flag.column | rc_str) else true end)
  and (if .state == "researcher-applies" then $c.applied_by == "researcher" else true end);

# The researcher-facing note for a usable status row.
def rc_note:
  if .state == "applied" then "Applied"
  elif .state == "delivered" then "Delivered"
  elif .state == "researcher-applies" then "Researcher applies"
  elif .state == "flagged" then "Flagged: `\(.flag.output).\(.flag.column)` = 1"
  else {"partially-applied": "Partially applied", "not-applied": "Not applied",
        "not-delivered": "Not delivered", "not-doable": "Not doable"}[.state] + ": " + .reason end;

# Inputs (all JSON):
#   $intake    `sqlreview.sh intake` output for answers.intake.json at the tag (criteria, fingerprints)
#   $scopes    [{slug, revision, criteria_status}] for every scope at the tag carrying criteria_status
#   $stale     true when the owning scope's review does not apply to the tag
#   $previous  {tag, criteria} of the previous release (research R9), or null
#   $current   the `criteria` of this tag's record in the working tree (its analyst decisions), or null
#   $fp        the fingerprints file (validate-answers --fingerprints), or null
#   $mode      "fingerprints", "answers-invalid" or "unchecked"
def rc_build($intake; $scopes; $stale; $previous; $current; $fp; $mode):
  ($intake.criteria // []) as $crit
  | if ($crit | length) == 0 or ($scopes | length) == 0 then null
    else
      ($scopes | if length == 1 then .[0] else null end) as $scope
      | (reduce (($scope.criteria_status // []) | if type == "array" then .[] else empty end) as $r
           ({}; if ($r | type) == "object" and ($r.criterion | rc_id) then .[$r.criterion] = $r else . end)) as $st
      | ($previous.criteria
         | if type == "object" and .status == "complete" and (.rows | type) == "array"
           then reduce (.rows[] | objects | select(.id | rc_id)) as $p ({}; .[$p.id] = $p) else null end) as $pby
      | ($current
         | if type == "object" and (.rows | type) == "array"
           then reduce (.rows[] | objects | select(.id | rc_id)) as $p ({}; .[$p.id] = $p) else {} end) as $cby
      | [ $crit[] | . as $c | ($pby[$c.id] // null) as $p
          | if $c.withdrawn != null then
              if $pby == null then {state: "withdrawn", change: "—"}
              # Not in the previous table: reported withdrawn earlier, or added and withdrawn between releases.
              elif $p == null or $p.state == "withdrawn" then empty
              elif $c.withdrawn.replaced_by != null then {state: "withdrawn", change: "replaced", replaced_by: $c.withdrawn.replaced_by}
              else {state: "withdrawn", change: "withdrawn"} end
              | . + {proposed_note: "Withdrawn by researcher"}
            else
              ($st[$c.id] // null) as $s
              | (if $scope != null and ($s | rc_usable($c)) then {state: $s.state, proposed_note: ($s | rc_note)}
                 else {state: null, proposed_note: null} end)
              | if .state == null or $pby == null then . + {change: "—"}
                elif $p == null then . + {change: "new"}
                elif $p.state != .state then . + {change: "changed", previous_state: $p.state}
                elif $p.text != $c.text then . + {change: "text-reworded"}
                else . + {change: "unchanged"} end
            end
          | {id: $c.id, kind: $c.kind, text: $c.text} + .
          | ($cby[.id] // null) as $was
          | if .proposed_note != null and $was != null and $was.proposed_note == .proposed_note
               and $was.text == .text and ($was.decision == "accepted" or $was.decision == "reworded" or $was.decision == "rejected")
            then . + {final_note: $was.final_note, decision: $was.decision,
                      decided_by: $was.decided_by, decided_at: $was.decided_at}
            else . + {final_note: null, decision: "pending"} end
        ] | sort_by(crit_order) as $rows
      | [ (if $scope != null and $stale then "review-stale" else empty end),
          (if $scope == null then empty
           else $rows[] | select(.state == null) | "state-missing:\(.id)" end),
          (if $mode == "fingerprints" then
             rc_fp_fields[] as $f | select($fp[$f] != $intake.fingerprints[$f]) | "fingerprint-mismatch:\($f)"
           else empty end),
          (if ($scopes | length) > 1 then "owning-scope-ambiguous" else empty end),
          ($rows[] | select(.decision == "rejected") | "note-rejected:\(.id)"),
          (if $mode == "answers-invalid" then "answers-invalid" else empty end),
          (if $mode == "unchecked" then "fingerprints-unchecked" else empty end)
        ] | sort_by(rc_reason_rank) as $held
      | {previous_tag: ($previous.tag // null),
         scope: (if $scope == null then null else {slug: $scope.slug, revision: $scope.revision} end),
         status: (if ($held | length) > 0 then "held" else "complete" end),
         held_reasons: $held,
         rows: $rows}
    end;

# --- check -------------------------------------------------------------------------------------

def rc_row_errors($held; $reasons):
  (.id // "?") as $id
  | if (crit_id_ok | not) then "criteria: every row needs a criterion id matching its kind"
    else
      (if (.text | rc_str) then empty else "criteria \($id): text is empty" end),
      (if .state == null then
         (if $held then empty else "criteria \($id): a complete table needs a state for every row" end)
       elif .state == "withdrawn" or ((.state | type) == "string" and (.state as $s | crit_states(.kind) | index([$s])) != null) then empty
       else "criteria \($id): state is not allowed for its kind" end),
      (if .state == null then
         (if .proposed_note == null then empty else "criteria \($id): a row without a state has no proposed note" end)
       elif (.proposed_note | rc_str) then empty
       else "criteria \($id): proposed_note is empty" end),
      (if (.decision as $d | rc_decisions | index([$d])) != null then empty
       else "criteria \($id): decision must be pending, accepted, reworded or rejected" end),
      (if .decision == "pending" then empty else
         (if (.decided_by | rc_str) then empty else "criteria \($id): decided_by is required for a decided note" end),
         (if (.decided_at | rc_str) then empty else "criteria \($id): decided_at is required for a decided note" end)
       end),
      (if .decision != "pending" and .proposed_note == null then "criteria \($id): a row without a note cannot be decided"
       elif .decision == "accepted" and .final_note != .proposed_note then
         "criteria \($id): an accepted note keeps the proposed note as final"
       elif .decision == "reworded" and ((.final_note | rc_str | not) or .final_note == .proposed_note) then
         "criteria \($id): a reworded note needs a new final note"
       elif (.decision == "rejected" or .decision == "pending") and .final_note != null then
         "criteria \($id): a \(.decision) note has no final note"
       else empty end),
      (if .decision == "rejected" and (($held | not) or (($reasons | type) == "array" and ($reasons | index(["note-rejected:\($id)"])) == null))
       then "criteria \($id): a rejected note holds the table with note-rejected:\($id)" else empty end),
      (if (.change as $ch | rc_changes | index([$ch])) == null then
         "criteria \($id): change must be —, unchanged, changed, new, text-reworded, withdrawn or replaced"
       elif .change == "changed" and (.previous_state | rc_str | not) then "criteria \($id): a changed row needs previous_state"
       elif .change == "replaced" and ((.replaced_by | rc_id | not) or (.replaced_by | crit_kind_of_id) != .kind) then
         "criteria \($id): a replaced row needs replaced_by"
       elif (.change == "withdrawn" or .change == "replaced") and .state != "withdrawn" then
         "criteria \($id): a withdrawn or replaced row has state withdrawn"
       elif .state == "withdrawn" and (.change == "—" or .change == "withdrawn" or .change == "replaced" | not) then
         "criteria \($id): a withdrawn row changes by withdrawn or replaced"
       else empty end)
    end;

# . = the release record. Legacy (no criteria, or null) passes.
def rc_errors:
  .status as $record_status
  | .criteria as $c
  | if $c == null then empty
    elif ($c | type) != "object" then "criteria must be an object (release.sh criteria) or null"
    else
      ($c.status == "held") as $held
      | ($c.rows | if type == "array" then . else [] end) as $rows
      | ($c.held_reasons // []) as $reasons
      | (if $c.status == "complete" or $c.status == "held" then empty else "criteria: status must be complete or held" end),
        (if $c.previous_tag == null or (($c.previous_tag | rc_str) and ($c.previous_tag | test("^[A-Za-z0-9][A-Za-z0-9._-]*$")))
         then empty else "criteria: previous_tag must be a release tag or null" end),
        (if $c.scope == null then
           (if $c.status == "complete" then "criteria: a complete table names its owning scope" else empty end)
         elif ($c.scope | type) == "object" and ($c.scope.slug | rc_str) and ($c.scope.revision | type) == "number" then empty
         else "criteria: scope must be {slug, revision} or null" end),
        (if ($reasons | type) != "array" then "criteria: held_reasons must be an array"
         elif any($reasons[]; rc_reason_ok | not) then "criteria: unknown held reason"
         elif $held and ($reasons | length) == 0 then "criteria: a held table needs held_reasons"
         elif ($held | not) and ($reasons | length) > 0 then "criteria: a complete table has no held_reasons"
         else empty end),
        (if ($c.rows | type) == "array" then empty else "criteria: rows must be an array" end),
        ($rows[] | if type == "object" then rc_row_errors($held; $reasons) else "criteria: every row must be an object" end),
        # Only a well-formed id is named; a malformed one is reported by rc_row_errors without its value.
        ($rows | map(objects | .id | select(rc_id)) | group_by(.)[] | select(length > 1) | "criteria: duplicate row \(.[0])"),
        (if all($rows[]; type == "object" and crit_id_ok)
         then ($rows | map(crit_order)) as $keys
           | if $keys != ($keys | sort) then "criteria: rows must be in criteria order" else empty end
         else empty end),
        (if $c.previous_tag == null and any($rows[]; type == "object" and .change != "—")
         then "criteria: a first release has no change but —" else empty end),
        (if ($reasons | type) != "array" then empty
         else $reasons[] | select(rc_reason_ok and startswith("note-rejected:")) | .[14:] as $i
           | if any($rows[]; type == "object" and .id == $i and .decision == "rejected") then empty
             else "criteria: note-rejected:\($i) names no rejected row" end end),
        (if $record_status != "approved" then empty
         elif $held then "approved: criteria table held: \($reasons | if type == "array" then map(select(rc_reason_ok)) | join(", ") else "" end)"
         else ($rows[] | objects | select(.decision == "pending" and (.id | rc_id)) | "approved: criteria \(.id) is pending") end)
    end;

# --- render ------------------------------------------------------------------------------------

def rc_words: tostring | gsub("-"; " ");
def rc_change_text:
  if .change == "changed" then "Changed (was \(.previous_state | rc_words))"
  elif .change == "new" then "New"
  elif .change == "text-reworded" then "Reworded"
  elif .change == "withdrawn" then "Withdrawn by researcher"
  elif .change == "replaced" then "Replaced by \(.replaced_by)"
  else "—" end;
def rc_this_release: if .decision == "pending" then "[pending] " + .proposed_note else .final_note end;

# . = the release record -> the section text, ending in a blank line.
def rc_section:
  .criteria as $c
  | if $c == null then "Criteria are not itemised for this request.\n\n"
    elif $c.status == "held" then "Criteria table held: \($c.held_reasons | join(", "))\n\n"
    else "## Criteria in this release\n\n"
      + (if ($c.rows | length) == 0 then "_Every criterion was withdrawn in an earlier release._\n\n"
         else "| ID | Researcher's request | This release | "
           + (if $c.previous_tag == null then "Change" else "Change since \($c.previous_tag)" end) + " |\n"
           + "|---|---|---|---|\n"
           + ($c.rows | map("| \(.id) | \(.text | rc_cell) | \(rc_this_release | rc_cell) | \(rc_change_text | rc_cell) |\n") | join(""))
           + "\n" end)
    end;
