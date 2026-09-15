# Validation rules for a .sqlreview/reviews/<slug>/{review,scope}.json document.
# Emits one violation per line; no output means the document is valid. Used by
# `sqlreview.sh check` and, through it, by the PreToolUse guard hook.
def req($k): if has($k) then empty else "missing key: \($k)" end;

def items($kind; $rev):
  (.[$kind] // []) as $arr
  | ($arr | map(.id // "") | group_by(.) | map(select(length > 1) | .[0]) | .[] | "duplicate id in \($kind): \(.)"),
    ($arr[]
      | (if (.id | type) != "string" or .id == "" then "item without id in \($kind)" else empty end),
        ((.id // "?") | tostring) as $id
      | (if ((.text // "") | tostring) == "" then "\($id): empty text" else empty end),
        (if .status != "confirmed" then "\($id): status is \(.status // "missing") — every assumption and limitation must be confirmed by the human before it is written" else empty end),
        (if ((.confirmed_by // "") | tostring) == "" then "\($id): confirmed_by is empty" else empty end),
        (if ((.confirmed_at // "") | tostring) == "" then "\($id): confirmed_at is empty" else empty end),
        (if .confirmed_revision != $rev then "\($id): confirmed_revision \(.confirmed_revision // "missing") != revision \($rev // "missing") — re-confirm for this revision" else empty end)
    );

if type != "object" then "document is not a JSON object"
else
  .revision as $rev
  | req("schemaVersion"), req("kind"), req("slug"), req("sql_path"), req("revision"), req("assumptions"), req("limitations"),
    (if has("schemaVersion") and .schemaVersion != 1 then "schemaVersion must be 1" else empty end),
    (if .kind == "review" then (req("purpose"), req("inputs"), req("outputs"), req("logic"), req("sql_sha256"))
     elif .kind == "scope" then (req("intent"), req("inputs"), req("outputs"), req("open_questions"))
     else "kind must be \"review\" or \"scope\" (got \(.kind // "nothing"))" end),
    (if ((.revision | type) != "number") or (.revision < 1) then "revision must be an integer >= 1" else empty end),
    (if has("assumptions") and (.assumptions | type) != "array" then "assumptions must be an array" else items("assumptions"; $rev) end),
    (if has("limitations") and (.limitations | type) != "array" then "limitations must be an array" else items("limitations"; $rev) end)
end
