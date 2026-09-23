---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_eval_data_request_amend_graders.py.
# The same rename is routed through the maintained source and regenerated.
pattern: '^(?=[\s\S]*\b[Rr]egenerat)[\s\S]*rename\s*=\s*(?:\{[^}]*[\"'']MRN[\"'']\s*:\s*[\"'']URN[\"'']|dict\([^)]*\bMRN\s*=\s*[\"'']URN[\"''])'
target: last_message
---
