---
type: regex
# Hand-written; fixtures in tests/test_eval_data_request_graders.py.
# The enquiry-number repository link is reported as stale.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\nstale_links:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?(?:THHSRDLENQ-9003))'
target: last_message
---
