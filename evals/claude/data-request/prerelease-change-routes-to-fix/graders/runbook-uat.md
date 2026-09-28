---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_data_request_prerelease_change.py.
# The runbook and the UAT checklist change with the SQL, including the renamed validation column.
pattern: '^(?=[\s\S]*\b[Rr]unbook\b)(?=[\s\S]*\bUAT checklist\b|[\s\S]*uat-checklist\.md)[\s\S]*\bdistinct_patient_key\b'
target: last_message
---
