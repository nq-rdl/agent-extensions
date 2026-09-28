---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_data_request_prerelease_change.py.
# The renamed validation column is carried into the runbook and UAT checklist.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\nrenamed:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?(?:distinct_mrn["'']?[ \t]*(?:->|→|:)[ \t]*["'']?distinct_patient_key\b))'
target: last_message
---
