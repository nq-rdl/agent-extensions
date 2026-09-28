---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_data_request_release.py.
# The locking hint stays internal; the demographics limitation does not.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\ninternal:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?\bL3\b)(?=(?:(?!\n {0,3}```)[\s\S])*?\ninternal:)(?!(?:(?!\n {0,3}```)[\s\S])*?\ninternal:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?\bL4\b)'
target: last_message
---
