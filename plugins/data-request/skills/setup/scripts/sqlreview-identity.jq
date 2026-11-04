# Identity rule shared by `sqlreview.sh check`, `release.sh check` and the guard's explain.json
# check (#419). A `by` or `*_by` field records a person by handle: the GitHub login, else
# `git config user.name`. It never records an email address, because the record is committed.
# Any string value with an "@" is refused. The value itself is not echoed. A violation is labelled
# with its item's id (A1, C2) when the field sits in one, else with the field's path. No-echo: an id
# prints only when it is a well-formed identifier, and a path key only when it is a lower snake case
# field name. Any other key prints as "(key)", because a key can carry free text.
def _identity_safe: if type == "string" and test("^[A-Za-z0-9][A-Za-z0-9._-]{0,63}\\z") then . else null end;
def _identity_key: if type == "string" and test("^[a-z][a-z0-9_]{0,63}\\z") then . else null end;
def identity_violations:
  . as $doc
  | paths(type == "string") as $p
  | ($p[-1]) as $k
  | select(($k | type) == "string" and ($k == "by" or ($k | endswith("_by"))))
  | select($doc | getpath($p) | contains("@"))
  | ($doc | getpath($p[:-1]) | .id? // null) as $id
  | "\(($id | _identity_safe) // ($p | map(if type == "number" then tostring else (_identity_key // "(key)") end) | join("."))): \($k) must be a handle (GitHub login or git user.name), not an email address";
