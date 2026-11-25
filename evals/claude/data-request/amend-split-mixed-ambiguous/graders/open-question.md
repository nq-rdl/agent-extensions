---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_eval_data_request_amend_graders.py.
# The hand-off entry states the open question, not none.
pattern: '(?:^|\n)[ \t>*_`-]*[Oo]pen question[*_` \t]*:(?![*_` \t]*[\"“]?none\b)[*_` \t]*\S'
target: last_message
---
