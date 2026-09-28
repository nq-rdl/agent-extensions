---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_data_request_release.py.
# L2 (locking hint) and L3 (row order) stay internal; A1 and L1 do not.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\ninternal:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?\bL2\b)(?=(?:(?!\n {0,3}```)[\s\S])*?\ninternal:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?\bL3\b)(?=(?:(?!\n {0,3}```)[\s\S])*?\ninternal:)(?!(?:(?!\n {0,3}```)[\s\S])*?\ninternal:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?\bA1\b)(?=(?:(?!\n {0,3}```)[\s\S])*?\ninternal:)(?!(?:(?!\n {0,3}```)[\s\S])*?\ninternal:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?\bL1\b)'
target: last_message
---
