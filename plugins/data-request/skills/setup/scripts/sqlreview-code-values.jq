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

def code_value_warnings:
  . as $doc
  | paths(type == "string") as $path
  | ($doc | getpath($path)) as $text
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
