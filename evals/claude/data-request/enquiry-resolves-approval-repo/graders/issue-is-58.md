---
type: regex
# Hand-written; fixtures in tests/test_eval_data_request_graders.py.
# issue is service-desk #58, never the enquiry number 1196.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\nissue:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?(?:\b58\b))(?=(?:(?!\n {0,3}```)[\s\S])*?\nissue:(?:(?!1196)(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*(?:\n[^ \t\n-]|\n {0,3}```))'
target: last_message
---
