---
type: regex
# Hand-written; fixtures in tests/test_eval_data_request_graders.py.
# excluded_fields names the unapproved pathology fields.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\nexcluded_fields:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?(?:[eE][Gg][Ff][Rr]))(?=(?:(?!\n {0,3}```)[\s\S])*?\nexcluded_fields:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?(?:[Hh][Bb][Aa]1[Cc]))'
target: last_message
---
