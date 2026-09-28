---
type: regex
# Hand-written; fixtures in evals/claude/data-request/field-renamed-repo-redirect/fixtures.yaml,
# graded by tests/test_eval_data_request_field_graders.py.
# A verbal decision against the newest written comment is recorded as unlinked.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\nlactate_decision_status:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?(?:[Uu]nlinked))'
target: last_message
---
