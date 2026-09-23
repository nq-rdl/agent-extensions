---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_eval_data_request_amend_graders.py.
# A new data element is a separate governance check: point to the Data Amendments SOP and ask for the original request ID and the reason.
pattern: '^(?=[\s\S]*Data Amendments SOP)(?=[\s\S]*\b[Rr]equest ID\b)[\s\S]*\b[Rr]eason\b'
target: last_message
---
