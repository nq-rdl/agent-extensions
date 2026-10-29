---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_eval_data_request_amend_graders.py.
# The analyst gets a short summary with done, handed-off and open-decision lines.
pattern: '^(?=[\s\S]*(?:^|\n)[ \t>*_`-]*[Dd]one[*_` \t]*:)(?=[\s\S]*(?:^|\n)[ \t>*_`-]*[Hh]anded off[*_` \t]*:)[\s\S]*(?:^|\n)[ \t>*_`-]*[Oo]pen decision[*_` \t]*:'
target: last_message
---
