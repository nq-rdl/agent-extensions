---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_eval_data_request_amend_graders.py.
# The other parts are still classified analyst-safe, so one part does not stop the rest.
pattern: '(?:^|\n)[ \t>*_`-]*[Cc]lassification[*_` \t]*:[*_` \t]*analyst-safe\b'
target: last_message
---
