---
type: regex
# Hand-written; fixtures in tests/test_eval_data_request_graders.py.
# A fenced text or markdown block, not yaml or json, carries the #49 comment.
pattern: '^(?:(?=( {0,3}(`{3,}|~{3,})[^\n]*\n(?:[^\n]*\n)*? {0,3}\2[`~]*[ \t]*(?:\n|$)))\1|(?! {0,3}(?:`{3,}|~{3,}))[^\n]*\n)*? {0,3}(`{3,}|~{3,})(?:[ \t]*(?:text|markdown|md|txt|plain))?[ \t]*\n(?:(?! {0,3}\3)[^\n]*\n)*?(?! {0,3}\3)[^\n]*(?:#49\b|THHSAQUIRE-2090|ENQ1187|THHSRDLENQ-1187)'
target: last_message
---
