---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_eval_data_request_amend_graders.py.
# Validation compares the row count and the key set with the previous extract.
pattern: '^(?=[\s\S]*\b[Rr]ow[-\s]+counts?\b)[\s\S]*\b[Kk]ey[-\s]+sets?\b'
target: last_message
---
