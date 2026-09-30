# Independent question records; no SQL revision or confirmation fields.
include "sqlreview-identity";
include "sqlreview-slug";
def qtext: type == "string" and test("\\S");
def question_errors:
  identity_violations,
  (if .schemaVersion != 1 or .kind != "questions" then "questions requires schemaVersion 1 and kind questions" else empty end),
  (if (.slug | type) != "string" or (.slug | test("^[A-Za-z0-9_%.-]+$") | not) or .slug == "." or .slug == ".." then "unsafe question slug" else empty end),
  (if (.sql_path | qtext | not) then "questions requires sql_path"
   elif (.sql_path | startswith("/") or (split("/") | any(.[]; . == "" or . == "." or . == ".."))) then "unsafe question sql_path"
   elif .slug != (.sql_path | path_slug) and .slug != (.sql_path | legacy_path_slug) then "question slug/sql_path binding mismatch" else empty end),
  (if has("revision") then "questions must not have a SQL-bound revision" else empty end),
  (if (.questions | type) != "array" then "questions must be an array" else
    (.questions | map(.id) | group_by(.)[] | select(length > 1) | "duplicate question id"),
    (.questions[] | if type != "object" then "question must be an object" else
      (if (.id | type) != "string" or (.id | test("^Q[1-9][0-9]*$") | not) then "invalid question id" else empty end),
      (if (.text | qtext | not) then "question text must be nonempty" else empty end),
      (if .applies != "scope" and .applies != "review" then "question applies must be scope or review" else empty end),
      (if has("owner") | not then "question requires owner (null when unknown)"
       elif .owner != null and ((.owner | qtext | not) or (.owner | contains("@"))) then "question owner must be a handle, not an email address" else empty end),
      (if .status != "open" and .status != "closed" then "question status must be open or closed" else empty end),
      (if .status == "open" and has("closed") then "open question must not carry closure" else empty end),
      (if .status == "closed" then
        if (.closed | type) != "object" then "closed question requires answered closure provenance"
        else (["answer", "by", "at", "source"][] as $k | if (.closed[$k] | qtext | not) then "closed.\($k) must be nonempty" else empty end) end
       else empty end),
      (if has("decided") then
        if (.decided | type) != "object" then "question decided must be an object"
        else (["by", "role", "at", "source"][] as $k | if (.decided[$k] | qtext | not) then "decided.\($k) must be nonempty" else empty end) end
       else empty end)
    end)
  end);
# Scope first, then review-only. Deduplicate exact text only; never infer semantic identity.
def legacy_questions($scope; $review; $slug; $path):
  reduce ((($scope.open_questions // [])[] | {text: ., applies: "scope"}),
          (($review.open_questions // [])[] | {text: ., applies: "review"})) as $q
    ([]; if any(.[]; .text == $q.text) then . else . + [$q + {id: "Q\(length + 1)", owner: null, status: "open"}] end)
  | {schemaVersion: 1, kind: "questions", slug: $slug, sql_path: $path, questions: .};
def legacy_covered($scope; $review):
  .questions as $qs
  | all(($scope.open_questions // [])[]; . as $text | any($qs[]; .text == $text and .applies == "scope"))
    and all(($review.open_questions // [])[]; . as $text | any($qs[]; .text == $text));
def visible_questions($kind): .questions |= map(select($kind == "review" or .applies == "scope"));
