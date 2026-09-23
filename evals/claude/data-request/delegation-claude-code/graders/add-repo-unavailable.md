---
type: regex
# Hand-written; fixtures in tests/test_eval_data_request_graders.py.
# The missing add_repo capability is disclosed.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\nunavailable:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?(?:add_repo))'
target: last_message
---
