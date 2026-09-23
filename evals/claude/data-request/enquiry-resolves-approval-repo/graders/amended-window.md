---
type: regex
# Hand-written; fixtures in tests/test_eval_data_request_graders.py.
# The amendment extends the window; the exclusive end is 2026-01-01.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\nwindow_start:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?(?:2021-01-01))(?=(?:(?!\n {0,3}```)[\s\S])*?\nwindow_end_exclusive:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?(?:2026-01-01))'
target: last_message
---
