---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_eval_data_request_amend_graders.py.
# The reply names the writer of the line and says the analyst was expected.
pattern: '^(?=[\s\S]*drive-by-lee)[\s\S]*(?:only the analyst|not the analyst|analyst named|expected)'
target: last_message
---
