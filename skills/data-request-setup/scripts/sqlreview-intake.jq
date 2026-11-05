# Answers-sidecar contract: skills/setup/references/analyst-intake.rst (schema 1 and 2). The rules
# mirror data-analysis-scaffold's validate_intake; the criterion vocabulary is sqlreview-criteria.jq,
# so run this with `jq -L <this directory>`.
# Never echo malformed source values in diagnostics.
include "sqlreview-criteria";
def ine: type == "string" and test("\\S");
# jq strptime/strftime can retain February 30; prove Gregorian days explicitly.
def ical:
  capture("^(?<y>[0-9]{4})-(?<m>[0-9]{2})-(?<d>[0-9]{2})")
  | (.y | tonumber) as $y | (.m | tonumber) as $m | (.d | tonumber) as $d
  | ($y % 4 == 0 and ($y % 100 != 0 or $y % 400 == 0)) as $leap
  | $y >= 1 and $m >= 1 and $m <= 12 and $d >= 1 and
    $d <= ([31, (if $leap then 29 else 28 end), 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][$m - 1]);
def iutc: type == "string" and test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$") and
  ical and (.[11:13] | tonumber) <= 23 and (.[14:16] | tonumber) <= 59 and (.[17:19] | tonumber) <= 59;
def iactor: ine and (contains("@") | not);
def iorigin: iutc or (type == "string" and test("^[0-9]{4}-[0-9]{2}-[0-9]{2}$") and ical);
def idecided: type == "object" and (.by | iactor) and (.role | ine) and (.at | iorigin) and (.source | ine);
def idecision:
  type == "object" and (.id | type == "string" and test("^[A-Za-z0-9][A-Za-z0-9_-]*$"))
  and (.topic as $t | ["cohort", "codes", "outcomes", "outputs", "grain", "governance"] | index($t) != null)
  and (.text | ine) and (.rationale | ine) and (.confirmed_by | iactor)
  and .confirmed_role == "analyst" and (.confirmed_at | iutc)
  and (if has("decided") then .decided | idecided else true end)
  and (if .topic == "grain" then (.unit | ine) and
    ((if has("finer_outputs") then .finer_outputs else [] end) | type == "array" and all(.[]; type == "object" and (.name | ine) and (.unit | ine) and (.description | ine)) and
      (map(.name) | length == (unique | length))) else true end);
# Schema 2 criteria. $known maps every well-formed id (prefix agrees with kind) to true.
def iwithdrawn($self; $known):
  type == "object" and (.reason | ine) and (.at | iorigin)
  and (if has("replaced_by") then
         .replaced_by as $t
         | ($t | type) == "string" and ($known[$t] // false) and $t != $self.id
           and $t[0:1] == ($self.kind | crit_prefix)
       else true end);
def icriterion($known):
  type == "object" and crit_id_ok
  and (.text | ine) and (.confirmed_by | iactor) and .confirmed_role == "analyst" and (.confirmed_at | iutc)
  and (if has("applied_by") then (.applied_by == "rdl" or .applied_by == "researcher")
         and (.kind == "inclusion" or .kind == "exclusion") else true end)
  and (if has("decided") then .decided | idecided else true end)
  and (if has("withdrawn") then . as $self | .withdrawn | iwithdrawn($self; $known) else true end);
def icriteria_list:
  . as $c
  | [$c[] | select(type == "object" and crit_id_ok) | .id] as $ids
  | (reduce $ids[] as $i ({}; .[$i] = true)) as $known
  | ($ids | length) == ($ids | unique | length) and all($c[]; icriterion($known));
def ifingerprints:
  type == "object"
  and (keys == ["cohort_entry_event", "exclusion_criteria", "inclusion_criteria", "requested_data_elements"])
  and all(.[]; type == "string" and test("\\Asha256:[0-9a-f]{64}\\z"));
def icriteria_valid:
  (if has("criteria") then .criteria | type == "array" and icriteria_list else true end)
  and (if has("fingerprints") then .fingerprints | ifingerprints else true end)
  and (if (.criteria | type == "array" and length > 0) then has("fingerprints") else true end);
def intake_valid:
  type == "object" and (.schemaVersion == 1 or .schemaVersion == 2) and (.approval_number | ine)
  and (.decisions | type == "array" and all(.[]; idecision)
    and (map(.id) | length == (unique | length))
    and ([.[] | select(.topic == "grain")] | length <= 1))
  and (.open_questions | type == "array" and all(.[]; ine))
  and (if .schemaVersion == 1 then ((has("criteria") or has("fingerprints")) | not) else icriteria_valid end);
if intake_valid then
  . as $intake | {present: true, approval_number,
    assumptions: [.decisions[] | . as $item |
      {id: ("A-intake-" + .id), text, rationale, location: null, status: "confirmed",
       confirmed_by, confirmed_at, confirmed_revision: $revision,
       upstream: ({source: "analyst-intake", file: ($source | split("/") | last), intake_id: .id,
                  approval_number: $intake.approval_number, role: "analyst", topic: .topic}
                  + (if .topic == "grain" then {unit, finer_outputs: (.finer_outputs // [])} else {} end))}
       + (if has("decided") then {decided} else {} end)],
    analyst_questions: [.open_questions[] | "Analyst question: " + .]}
    # Schema 2 only; the criteria and fingerprints are passed through verbatim for the callers.
    + (if .schemaVersion == 2 then {criteria: (.criteria // []), fingerprints: (.fingerprints // null)} else {} end)
else error("invalid analyst intake fields; run validate-answers and correct the sidecar") end
