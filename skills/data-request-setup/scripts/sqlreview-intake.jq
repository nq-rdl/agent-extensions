# Answers-sidecar contract: skills/setup/references/analyst-intake.rst.
# Never echo malformed source values in diagnostics.
def ine: type == "string" and test("\\S");
def iutc: type == "string" and test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$") and
  (. as $date | try (strptime("%Y-%m-%dT%H:%M:%SZ") | strftime("%Y-%m-%dT%H:%M:%SZ") == $date) catch false);
def iactor: ine and (contains("@") | not);
def iorigin: iutc or (type == "string" and test("^[0-9]{4}-[0-9]{2}-[0-9]{2}$") and
  (. as $date | try (strptime("%Y-%m-%d") | strftime("%Y-%m-%d") == $date) catch false));
def idecision:
  type == "object" and (.id | type == "string" and test("^[A-Za-z0-9][A-Za-z0-9_-]*$"))
  and (.topic as $t | ["cohort", "codes", "outcomes", "outputs", "grain", "governance"] | index($t) != null)
  and (.text | ine) and (.rationale | ine) and (.confirmed_by | iactor)
  and .confirmed_role == "analyst" and (.confirmed_at | iutc)
  and (if has("decided") then .decided | type == "object" and (.by | iactor) and (.role | ine) and (.at | iorigin) and (.source | ine) else true end)
  and (if .topic == "grain" then (.unit | ine) and
    ((.finer_outputs // []) | type == "array" and all(.[]; type == "object" and (.name | ine) and (.unit | ine) and (.description | ine)) and
      (map(.name) | length == (unique | length))) else true end);
def intake_valid:
  type == "object" and .schemaVersion == 1 and (.approval_number | ine)
  and (.decisions | type == "array" and all(.[]; idecision)
    and (map(.id) | length == (unique | length))
    and ([.[] | select(.topic == "grain")] | length <= 1))
  and (.open_questions | type == "array" and all(.[]; ine));
if intake_valid then
  . as $intake | {present: true, approval_number,
    assumptions: [.decisions[] | . as $item |
      {id: ("A-intake-" + .id), text, rationale, location: null, status: "confirmed",
       confirmed_by, confirmed_at, confirmed_revision: $revision,
       upstream: ({source: "analyst-intake", file: $source, intake_id: .id,
                  approval_number: $intake.approval_number, role: "analyst", topic: .topic}
                  + (if .topic == "grain" then {unit, finer_outputs: (.finer_outputs // [])} else {} end))}
       + (if has("decided") then {decided} else {} end)],
    analyst_questions: [.open_questions[] | "Analyst question: " + .]}
else error("invalid analyst intake fields; run validate-answers and correct the sidecar") end
