---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_eval_data_request_amend_graders.py.
# No hand-off is drafted, and the summary says that nothing is handed off.
pattern: '^(?![\s\S]*[Aa]mendment hand-off[*_` \t]*:)(?![\s\S]*[Rr]equested change[*_` \t]*:)[\s\S]*(?:^|\n)[ \t>*_`-]*[Hh]anded off[*_` \t]*:[*_` \t]*[\"“]?none\b'
target: last_message
---
