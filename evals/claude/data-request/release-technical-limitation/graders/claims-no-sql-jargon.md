---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_data_request_release.py.
# The proposed wording states the consequence without SQL terms.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\nclaims:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?\S)(?=(?:(?!\n {0,3}```)[\s\S])*?\nclaims:)(?!(?:(?!\n {0,3}```)[\s\S])*?\nclaims:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?\b(?:JOIN|join|Join|NOLOCK|nolock|NoLock|SELECT|select|CTE|LEFT|left join)\b)'
target: last_message
---
