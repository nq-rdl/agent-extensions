---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_eval_data_request_amend_graders.py.
# The rename goes through CohortQuery.select(..., rename=...) with MRN mapped to URN.
pattern: 'rename\s*=\s*(?:\{[^}]*[\"'']MRN[\"'']\s*:\s*[\"'']URN[\"'']|dict\([^)]*\bMRN\s*=\s*[\"'']URN[\"''])'
target: last_message
---
