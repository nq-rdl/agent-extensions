---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_eval_data_request_amend_graders.py.
# The reply classifies the change as analyst-safe, and nowhere as engineer-required.
pattern: '^(?![\s\S]*(?:^|\n)[ \t>*_`-]*[Cc]lassification[*_` \t]*:[*_` \t]*engineer-required\b)[\s\S]*(?:^|\n)[ \t>*_`-]*[Cc]lassification[*_` \t]*:[*_` \t]*analyst-safe\b'
target: last_message
---
