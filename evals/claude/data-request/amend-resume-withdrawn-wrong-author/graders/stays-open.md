---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_eval_data_request_amend_graders.py.
# P3 is still handed off and is not on the withdrawn line.
pattern: '^(?![\s\S]*(?:^|\n)[ \t>*_`-]*[Ww]ithdrawn[*_` \t]*:[^\n]*P3)(?=[\s\S]*(?:^|\n)[ \t>*_`-]*[Hh]anded off[*_` \t]*:[^\n]*P3)'
target: last_message
---
