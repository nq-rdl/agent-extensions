---
type: regex
# Hand-written; fixtures in tests/test_eval_data_request_graders.py.
# The undelivered G-DECEASED stays open.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\nopen_gaps:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?(?:G-DECEASED))(?=(?:(?!\n {0,3}```)[\s\S])*?\nclosed_or_stale_gaps:(?:(?!G-DECEASED)(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*(?:\n[^ \t\n-]|\n {0,3}```))'
target: last_message
---
