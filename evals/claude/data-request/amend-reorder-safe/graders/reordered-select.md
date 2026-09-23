---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_eval_data_request_amend_graders.py.
# The reorder is a new field order in the existing .select(): EncounterId, then MRN, then the rest.
pattern: '\.select\(\s*[\"'']EncounterId[\"'']\s*,\s*[\"'']MRN[\"'']\s*,\s*[\"'']AdmitDateTime[\"'']'
target: last_message
---
