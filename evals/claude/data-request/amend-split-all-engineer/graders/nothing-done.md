---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_eval_data_request_amend_graders.py.
# The summary says that the analyst completed nothing.
pattern: '(?:^|\n)[ \t>*_`-]*[Dd]one[*_` \t]*:[*_` \t]*[\"“]?none\b'
target: last_message
---
