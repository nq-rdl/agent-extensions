---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_eval_data_request_amend_graders.py.
# The reply names the writer of the line and says the engineer was expected.
pattern: '^(?=[\s\S]*analyst-jo)[\s\S]*(?:only the engineer|not the engineer|engineer named|expected)'
target: last_message
---
