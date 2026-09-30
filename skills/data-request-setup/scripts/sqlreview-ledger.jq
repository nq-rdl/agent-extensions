# Triage ledger schema 1. Independent of SQL-bound review/scope revisions and questions.
def nonempty: type == "string" and test("\\S");
def identity: nonempty and (contains("@") | not);
def stage: IN("intake", "bootstrap", "map", "draft", "validate", "analyse", "lift", "report", "review", "fix", "amend", "release", "parked");
def strings: type == "array" and all(.[]; nonempty);
def revisions: type == "object" and all(to_entries[]; (.key | nonempty) and (.value | nonempty));
def repo: type == "string" and test("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$");
def ticket: type == "string" and test("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+#[1-9][0-9]*$");
def safe_path:
  nonempty and (test("[\\t\\r\\n]") | not) and
  (startswith("/") | not) and
  (split("/") | all(.[]; . != "" and . != "." and . != ".."));
def origin:
  type == "object" and (.by | identity) and (.role | nonempty) and
  (.at | nonempty) and (.source | nonempty);
def decision:
  type == "object" and (.decision | nonempty) and
  (if has("decided") then (.decided | origin)
   elif has("date") or has("who") or has("source") then
     (.date | nonempty) and (.who | identity) and (.source | nonempty)
   else (.by | identity) and (.at | nonempty) and (.value | nonempty) and (.scope | repo)
   end);
def entry:
  . as $entry |
  type == "object" and (.ticket | ticket) and (.enquiry | nonempty) and
  all(["approval_as_written", "approval", "branch"][]; . as $k | if $entry | has($k) then $entry[$k] | nonempty else true end) and
  (if has("repo") then (.repo | repo) else true end) and
  (if has("owner") then (.owner | identity) else true end) and
  (.stage | stage) and
  (.stages_done | type == "array" and all(.[]; stage) and length == (unique | length)) and
  (.evidence_revision | revisions) and
  (.stage_evidence | type == "object") and
  all(.stages_done[]; . as $stage |
    $entry.stage_evidence[$stage] |
    type == "object" and (.sources | strings) and (.sources | length > 0) and
    all(.sources[]; . as $source | $entry.evidence_revision | has($source)) and
    (.artifacts | type == "array" and all(.[];
      type == "object" and (.path | safe_path) and
      (.sha256 | type == "string" and test("^[0-9a-f]{64}$"))))) and
  all(.stage_evidence | keys[]; . as $stage | $entry.stages_done | index($stage) != null) and
  (.decisions | type == "array" and all(.[]; decision)) and
  (.blockers | type == "array" and all(.[]; type == "object" and (.class | nonempty) and (.detail | nonempty))) and
  (.depends_on | strings) and (.next_action | nonempty) and
  (.verification | type == "object" and (.status | IN("unverified", "partial", "verified")) and
    (.commands | strings) and (.at | nonempty)) and
  (if has("handoff") then (.handoff | type == "object" and (.pr | ticket) and
    (.head_sha | nonempty) and (.reviewer | identity) and (.board_state | nonempty) and (.date | nonempty)) else true end);
def store:
  type == "object" and .schemaVersion == 1 and
  (.entries | type == "array" and all(.[]; entry) and
    length == (map(.ticket) | unique | length));
if $mode == "entry" then entry
elif $mode == "revisions" then revisions
else store end
