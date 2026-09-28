---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_data_request_release.py.
# The proposed wording says the demographics reflect the current record.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\nclaims:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?\b(?:current|currently|today|now|latest|most recent|at extraction)\b)'
target: last_message
---
