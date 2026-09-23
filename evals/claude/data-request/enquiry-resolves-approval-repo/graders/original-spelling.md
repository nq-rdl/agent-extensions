---
type: regex
# Hand-written; fixtures in tests/test_eval_data_request_graders.py.
# approval_as_written keeps the unhyphenated original spelling.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\napproval_as_written:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?(?:THHSAQUIRE9903\b))'
target: last_message
---
