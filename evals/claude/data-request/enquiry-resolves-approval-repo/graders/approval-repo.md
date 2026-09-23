---
type: regex
# Hand-written; fixtures in tests/test_eval_data_request_graders.py.
# repo is the approval-ID repository THHSAQUIRE-9903, not an enquiry-named one.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\nrepo:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?(?:THHSAQUIRE-9903\b))(?=(?:(?!\n {0,3}```)[\s\S])*?\nrepo:(?:(?!THHSRDLENQ)(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*(?:\n[^ \t\n-]|\n {0,3}```))'
target: last_message
---
