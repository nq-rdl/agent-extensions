---
type: regex
# Hand-written; fixtures in tests/test_eval_data_request_graders.py.
# A ranked queue: at least two numbered items.
pattern: '(?:^|\n)[ \t]*1[.)][ \t]+\S[^\n]*\n(?:[^\n]*\n)*?[ \t]*2[.)][ \t]+\S'
target: last_message
---
