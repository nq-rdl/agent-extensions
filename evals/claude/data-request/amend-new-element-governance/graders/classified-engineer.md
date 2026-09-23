---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_eval_data_request_amend_graders.py.
# The reply classifies the change as engineer-required, and nowhere as analyst-safe.
pattern: '^(?![\s\S]*(?:^|\n)[ \t>*_`-]*[Cc]lassification[*_` \t]*:[*_` \t]*analyst-safe\b)[\s\S]*(?:^|\n)[ \t>*_`-]*[Cc]lassification[*_` \t]*:[*_` \t]*engineer-required\b'
target: last_message
---
