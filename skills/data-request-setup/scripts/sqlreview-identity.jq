# Identity rule shared by `sqlreview.sh check`, `release.sh check` and the guard's explain.json
# check (#419). A `by` or `*_by` field records a person by handle: the GitHub login, else
# `git config user.name`. It never records an email address, because the record is committed.
# Any string value with an "@" is refused. The value itself is not echoed. A violation is labelled
# with its item's id (A1, C2) when the field sits in one, else with the field's path.
def identity_violations:
  . as $doc
  | paths(type == "string") as $p
  | ($p[-1]) as $k
  | select(($k | type) == "string" and ($k == "by" or ($k | endswith("_by"))))
  | select($doc | getpath($p) | contains("@"))
  | ($doc | getpath($p[:-1]) | .id? // null) as $id
  | "\(if ($id | type) == "string" and $id != "" then $id else $p | map(tostring) | join(".") end): \($k) must be a handle (GitHub login or git user.name), not an email address";
