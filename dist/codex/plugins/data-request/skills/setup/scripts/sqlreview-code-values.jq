include "sqlreview-slug";

# Exact maximal ASCII digit runs, not substrings of longer numbers. This is an
# advisory drafting rule, not a code-set lookup or a replacement for the PII gate.
def code_value_pattern: "(?<![0-9])[0-9]{8,10}(?![0-9])";

# Apply to ALL lint diagnostics: an item id or extension key may itself contain
# a value, even in an unrelated STE/provenance/provisional-wording warning.
def code_value_redact: gsub(code_value_pattern; "[redacted]");

def lint_field_path:
  reduce .[] as $part ("";
    if $part | type == "number" then . + "[\($part)]"
    else . + (if . == "" then "" else "." end) + $part end);

# Exempt only known machine locations with valid formats, never a key anywhere
# in the tree. Lint still scans extensions and invalid metadata; check/publish
# remain responsible for authoritative binding and fingerprint verification.
def code_value_path_ok:
  type == "string" and length > 0 and (startswith("/") | not)
  and (split("/") | all(.[]; . != "" and . != "." and . != ".."));
def code_value_machine_field($doc; $path; $text):
  if ($path == ["sql_sha256"] or $path == ["sql_body_sha256"] or
      ($path | length == 3 and .[0] == "header_revisions" and
        (.[1] | type) == "number" and (.[2] == "sql_sha256" or .[2] == "sql_body_sha256"))) then
    $text | test("^[0-9a-f]{64}$")
  elif $path == ["git_commit"] then $text | test("^([0-9a-f]{40}|[0-9a-f]{64})$")
  elif $path == ["sql_path"] then $text | code_value_path_ok
  elif $path == ["slug"] then
    ($doc.sql_path | code_value_path_ok) and
    ($text == ($doc.sql_path | path_slug) or $text == ($doc.sql_path | legacy_path_slug))
  elif ($path == ["recorded_at"] or
        ($path | length == 3 and (.[0] == "changes" or .[0] == "header_revisions") and
          (.[1] | type) == "number" and .[2] == "at") or
        ($path | length == 3 and (.[0] == "assumptions" or .[0] == "limitations") and
          (.[1] | type) == "number" and .[2] == "confirmed_at") or
        ($path | length == 4 and (.[0] == "assumptions" or .[0] == "limitations") and
          (.[1] | type) == "number" and .[2:] == ["decided", "at"])) then
    $text | test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\\.[0-9]+)?(Z|[+-][0-9]{2}:[0-9]{2})$")
  else false end;

def code_value_warnings:
  . as $doc
  | paths(type == "string") as $path
  | ($doc | getpath($path)) as $text
  | select(code_value_machine_field($doc; $path; $text) | not)
  # Prefer the nearest owning item id (also works for structured questions).
  | ([range(0; $path | length) as $n
      | $path[:$n] as $prefix | ($doc | getpath($prefix)) as $owner
      | select(($owner | type) == "object" and ($owner.id | type) == "string")
      | {id: $owner.id, prefix: $prefix}] | last) as $named
  # Otherwise locate an object in a collection by its zero-based index.
  | ([range(1; $path | length) as $n
      | select(($path[$n - 1] | type) == "number")
      | $path[:$n] as $prefix
      | select(($doc | getpath($prefix) | type) == "object")
      | {id: ($prefix | lint_field_path), prefix: $prefix}] | last) as $indexed
  | ($named // $indexed // {id: "-", prefix: []}) as $item
  | ($path[($item.prefix | length):] | lint_field_path) as $field
  | [$text | match(code_value_pattern; "g")] | to_entries[]
  | {id: $item.id, field: $field,
     detail: "digit run \(.key + 1); name the constant, never its value"};
