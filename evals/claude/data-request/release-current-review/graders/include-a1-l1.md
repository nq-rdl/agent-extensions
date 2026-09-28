---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_data_request_release.py.
# A1 and L1 reach the release body; L2 and L3 do not.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\ninclude:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?\bA1\b)(?=(?:(?!\n {0,3}```)[\s\S])*?\ninclude:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?\bL1\b)(?=(?:(?!\n {0,3}```)[\s\S])*?\ninclude:)(?!(?:(?!\n {0,3}```)[\s\S])*?\ninclude:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?\bL2\b)(?=(?:(?!\n {0,3}```)[\s\S])*?\ninclude:)(?!(?:(?!\n {0,3}```)[\s\S])*?\ninclude:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?\bL3\b)'
target: last_message
---
