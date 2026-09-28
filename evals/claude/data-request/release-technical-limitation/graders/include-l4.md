---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_data_request_release.py.
# The current-record demographics limitation reaches the body; the locking hint does not.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\ninclude:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?\bL4\b)(?=(?:(?!\n {0,3}```)[\s\S])*?\ninclude:)(?!(?:(?!\n {0,3}```)[\s\S])*?\ninclude:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?\bL3\b)'
target: last_message
---
