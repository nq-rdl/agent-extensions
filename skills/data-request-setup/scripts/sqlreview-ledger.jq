# Triage ledger schema 1. Independent of SQL-bound review/scope revisions and questions.
def nonempty: type == "string" and test("\\S");
def identity: nonempty and (contains("@") | not);
# A waiver must come from a human. Agent and bot logins cannot waive a gate.
def human: identity and (test("\\[bot\\]$") | not) and
  (ascii_downcase | IN("claude", "codex", "copilot", "github-actions", "agent") | not);
def stage: IN("intake", "bootstrap", "map", "draft", "validate", "analyse", "run", "uat", "handoff", "lift", "report", "review", "fix", "amend", "release", "parked");
def strings: type == "array" and all(.[]; nonempty);
def revisions: type == "object" and all(to_entries[]; (.key | nonempty) and (.value | nonempty));
def repo: type == "string" and test("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$");
def ticket: type == "string" and test("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+#[1-9][0-9]*$");
# The written record of a human decision on GitHub: a comment, a review or a review-line comment.
def comment_url: type == "string" and
  test("^https://github\\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/(pull|issues)/[1-9][0-9]*#(issuecomment-[0-9]+|pullrequestreview-[0-9]+|discussion_r[0-9]+)$");
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
   else keys == ["at", "by", "decision", "scope", "value"] and
     .decision == "generativeMode" and .value == "direct" and
     (.by | identity) and (.at | nonempty) and (.scope | repo)
   end);
# Only a CI check can be waived. The waiver holds for one check on one head commit.
def waiver:
  # The waivers command prints tab-separated rows, so no field may hold a tab or a line break.
  def plain: type == "string" and (test("[\\t\\r\\n]") | not);
  type == "object" and all(.[]; plain) and keys == ["at", "by", "check", "gate", "head_sha", "issue", "reason", "source"] and
  .gate == "ci" and (.check | nonempty) and (.head_sha | type == "string" and test("^[0-9a-f]{40}$")) and
  (.issue | ticket) and (.by | human) and (.at | nonempty) and (.source | comment_url) and (.reason | nonempty);
# One [field, passed] pair per rule, so a refusal can name the field and never the value.
def entry_checks:
  . as $entry |
  [["entry", type == "object"]] +
  if type != "object" then [] else
  [["ticket", (.ticket | ticket)],
   ["enquiry", (.enquiry | nonempty)],
   (["approval_as_written", "approval", "branch"][] as $k | [$k, (if $entry | has($k) then $entry[$k] | nonempty else true end)]),
   ["repo", (if has("repo") then (.repo | repo) else true end)],
   ["owner", (if has("owner") then (.owner | identity) else true end)],
   ["stage", (.stage | stage)],
   ["stages_done", (.stages_done | type == "array" and all(.[]; stage) and length == (unique | length))],
   ["evidence_revision", (.evidence_revision | revisions and ((has("sql") and has("sql_commit")) | not))],
   ["stage_evidence", (.stage_evidence | type == "object") and
     ((.stages_done | type) == "array") and
     all(.stages_done[]; . as $stage |
       $entry.stage_evidence[$stage] |
       type == "object" and (.sources | strings) and (.sources | length > 0) and
       all(.sources[]; . as $source | $entry.evidence_revision | type == "object" and has($source)) and
       (.artifacts | type == "array" and all(.[];
         type == "object" and (.path | safe_path) and
         (.sha256 | type == "string" and test("^[0-9a-f]{64}$"))))) and
     all(.stage_evidence | keys[]; . as $stage | $entry.stages_done | index($stage) != null)],
   ["decisions", (.decisions | type == "array" and all(.[]; decision))],
   ["blockers", (.blockers | type == "array" and all(.[]; type == "object" and (.class | nonempty) and (.detail | nonempty)))],
   ["depends_on", (.depends_on | strings)],
   ["next_action", (.next_action | nonempty)],
   ["verification", (.verification | type == "object" and (.status | IN("unverified", "partial", "verified")) and
     (.commands | strings) and (.at | nonempty))],
   ["handoff", (if has("handoff") then (.handoff | type == "object" and (.pr | ticket) and
     (.head_sha | nonempty) and (.reviewer | identity) and (.board_state | nonempty) and (.date | nonempty)) else true end)],
   ["gate_waivers", (if has("gate_waivers") then (.gate_waivers | type == "array" and all(.[]; waiver) and
     length == (map([.gate, .check, .head_sha]) | unique | length)) else true end)]]
  end;
def entry: all(entry_checks[]; .[1] == true);
def entry_errors: [entry_checks[] | select(.[1] != true) | .[0]];
def store:
  type == "object" and .schemaVersion == 1 and
  (.entries | type == "array" and all(.[]; entry) and
    length == (map(.ticket) | unique | length));
def store_errors:
  if type != "object" or .schemaVersion != 1 then ["schemaVersion"]
  elif (.entries | type) != "array" then ["entries"]
  else [(.entries | to_entries[] | .key as $i | .value | entry_errors[] | "entries[\($i)].\(.)"),
        (if (.entries | length) != (.entries | map(.ticket) | unique | length) then "entries (duplicate ticket)" else empty end)]
  end;
# The scaffold sweep refuses a field named sql. Ledgers saved before the rename stay readable,
# and every write saves the key as sql_commit.
def sql_key_clash: type == "object" and (.evidence_revision | type == "object" and has("sql") and has("sql_commit"));
def legacy_sql_key: type == "object" and (.evidence_revision | type == "object" and has("sql"));
# A revisions object that holds both keys is ambiguous: no read may choose one of them.
def revisions_clash: type == "object" and has("sql") and has("sql_commit");
def store_clash: type == "object" and (.entries | type == "array" and any(.[]; sql_key_clash));
def rename_sql_key:
  if legacy_sql_key and (sql_key_clash | not) then
    .evidence_revision |= with_entries(if .key == "sql" then .key = "sql_commit" else . end) |
    if (.stage_evidence | type) == "object" then
      .stage_evidence |= map_values(if type == "object" and (.sources | type) == "array"
        then .sources |= map(if . == "sql" then "sql_commit" else . end) else . end)
    else . end
  else . end;
if $mode == "entry" then entry
elif $mode == "entry-errors" then entry_errors | join(", ")
elif $mode == "entry-clash" then sql_key_clash
elif $mode == "store-clash" then store_clash
elif $mode == "revisions-clash" then revisions_clash
elif $mode == "sql-key" then (if sql_key_clash then "clash" elif legacy_sql_key then "legacy" else "ok" end)
elif $mode == "rename-entry" then rename_sql_key
elif $mode == "rename-store" then .entries |= map(rename_sql_key)
elif $mode == "store-errors" then store_errors | join(", ")
elif $mode == "revisions" then revisions and (revisions_clash | not)
else store end
