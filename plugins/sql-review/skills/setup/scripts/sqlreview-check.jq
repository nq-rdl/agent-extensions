# Validation rules for a .sqlreview/reviews/<slug>/{review,scope}.json document.
# Emits one violation per line; no output means the document is valid. Used by
# `sqlreview.sh check` and, through it, by the PreToolUse guard hook.
def nonempty: type == "string" and length > 0;
def integer: type == "number" and . >= 1 and . == floor;
def line_range: type == "array" and length == 2 and all(.[]; integer) and .[0] <= .[1];
def path_ok: nonempty and endswith(".sql") and (startswith("/") | not) and (split("/") | all(.[]; . != "" and . != "." and . != ".."));
def path_slug: sub("\\.sql$"; "") | (if . == "" then [""] else split("/") end) | map(if . == "" then "%00" else @uri | gsub("~"; "%7E") | gsub("\u0027"; "%27") | gsub("[!]"; "%21") | gsub("[(]"; "%28") | gsub("[)]"; "%29") | gsub("[*]"; "%2A") | gsub("_"; "%5F") | gsub("\\."; "%2E") end) | join("__");
def req($k): if has($k) then empty else "missing key: \($k)" end;

def items($kind; $rev):
  (.[$kind] // []) as $arr
  | ($arr | map(.id // "") | group_by(.) | map(select(length > 1) | .[0]) | .[] | "duplicate id in \($kind): \(.)"),
    ($arr[]
      | (if (.id | type) != "string" or .id == "" then "item without id in \($kind)" else empty end),
        ((.id // "?") | tostring) as $id
      | (if (.text | nonempty | not) then "\($id): empty text" else empty end),
        (if (.rationale | nonempty | not) then "\($id): rationale must be a nonempty string" else empty end),
        (if .location != null and ((.location | type) != "object" or (.location.lines | line_range | not)) then "\($id): location must be null or an object with a line range" else empty end),
        (if .status != "confirmed" then "\($id): status is \(.status // "missing") — every assumption and limitation must be confirmed by the human before it is written" else empty end),
        (if (.confirmed_by | nonempty | not) then "\($id): confirmed_by is empty" else empty end),
        (if (.confirmed_at | nonempty | not) then "\($id): confirmed_at is empty" else empty end),
        (if .confirmed_revision != $rev then "\($id): confirmed_revision \(.confirmed_revision // "missing") != revision \($rev // "missing") — re-confirm for this revision" else empty end)
    );

if type != "object" then "document is not a JSON object"
else
  .revision as $rev
  | (if (.sql_path | path_ok | not) then "sql_path must be a normalized project-relative path" else empty end),
    (if (.slug | nonempty | not) or (.slug | test("^[A-Za-z0-9_%.-]+$") | not) or .slug == "." or .slug == ".." then "unsafe slug" else empty end),
    (if (.sql_path | path_ok) and .slug != (.sql_path | path_slug) then "slug/sql_path binding mismatch" else empty end),
    (["inputs", "outputs"][] as $key | if (.[$key] | type) != "array" or (.[$key] | all(.[]; type == "object" and (.name | nonempty) and (.description | type == "string")) | not) then "\($key) must be an array of named descriptions" else empty end),
    (if has("logic") and ((.logic | type) != "array" or (.logic | all(.[]; type == "object" and (.step | integer) and (.title | type == "string") and (.description | type == "string") and (.lines | line_range)) | not)) then "logic must be an array of numbered steps with line ranges" else empty end),
    (if has("open_questions") and ((.open_questions | type) != "array" or (.open_questions | all(.[]; type == "string") | not)) then "open_questions must be an array of strings" else empty end),
    (if has("changes") and ((.changes | type) != "array" or (.changes | all(.[]; type == "object" and (.revision | integer) and (.at | nonempty) and (.by | nonempty) and (.summary | nonempty)) | not)) then "changes must be an array of revision records" else empty end),
    (if .kind == "review" and ((.purpose | nonempty | not) or (.sql_sha256 | test("^[0-9a-f]{64}$") | not)) then "review requires purpose and SHA256" else empty end),
    (if .kind == "scope" and (.intent | nonempty | not) then "scope requires intent" else empty end),
    (.revision as $rev
  | req("schemaVersion"), req("kind"), req("slug"), req("sql_path"), req("revision"), req("assumptions"), req("limitations"),
    (if has("schemaVersion") and .schemaVersion != 1 then "schemaVersion must be 1" else empty end),
    (if .kind == "review" then (req("purpose"), req("inputs"), req("outputs"), req("logic"), req("sql_sha256"))
     elif .kind == "scope" then (req("intent"), req("inputs"), req("outputs"), req("open_questions"))
     else "kind must be \"review\" or \"scope\" (got \(.kind // "nothing"))" end),
    (if (.revision | integer | not) then "revision must be an integer >= 1" else empty end),
    (if has("assumptions") and (.assumptions | type) != "array" then "assumptions must be an array" else items("assumptions"; $rev) end),
    (if has("limitations") and (.limitations | type) != "array" then "limitations must be an array" else items("limitations"; $rev) end)
    )
end
