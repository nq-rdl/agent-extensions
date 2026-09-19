---
type: regex
# Scoped to the rewritten file: the last fenced go block (3+ backticks or tildes,
# indented up to 3 spaces) opening with `package account`. Prose, quoted before-code,
# and Go comments/literals inside the file are not graded, for required text as well
# as forbidden text; a reply without that block fails. Comments and literals are
# consumed atomically, (?=(...))\N, to keep matching linear. Known limits, accepted
# for a starter case: malformed literals and a file split across several blocks.
# Shared prefix and fixtures: tests/test_eval_go_naming_graders.py (Python and Node).
# Both getters drop the Get prefix and keep initialisms uniform.
pattern: '(?:^|\n) {0,3}(`{3,}|~{3,})go[^\n]*\n\s*(?://[^\n]*\n\s*)*package\s+account\b(?![\s\S]*\n {0,3}(?:`{3,}|~{3,})go[^\n]*\n\s*(?://[^\n]*\n\s*)*package\s+account\b)(?=(?:(?!\n {0,3}\1)(?:(?=(//[^\n]*|/\*[\s\S]*?\*/|"(?:[^"\\\n]|\\.)*"|''(?:[^''\\\n]|\\.)+''|`[^`]*`))\2|(?!//|/\*|"|''|`)[\s\S]))*\)\s+OwnerID\(\)\s+string)(?=(?:(?!\n {0,3}\1)(?:(?=(//[^\n]*|/\*[\s\S]*?\*/|"(?:[^"\\\n]|\\.)*"|''(?:[^''\\\n]|\\.)+''|`[^`]*`))\3|(?!//|/\*|"|''|`)[\s\S]))*\)\s+BaseURL\(\)\s+string)(?:(?!\n {0,3}\1)(?:(?=(//[^\n]*|/\*[\s\S]*?\*/|"(?:[^"\\\n]|\\.)*"|''(?:[^''\\\n]|\\.)+''|`[^`]*`))\4|(?!//|/\*|"|''|`)[\s\S]))*\n {0,3}\1'
target: last_message
---
