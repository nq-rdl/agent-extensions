---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_data_request_release.py.
# The criteria table sits before Extraction Assumptions / Important limitations.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\ntable_position:[ \t]*["'']?(?:before-limitations)["'']?[ \t]*(?:#[^\n]*)?\n)(?!(?:(?!\n {0,3}```)[\s\S])*?\ntable_position:(?![ \t]*["'']?(?:before-limitations)["'']?[ \t]*(?:#[^\n]*)?\n))'
target: last_message
---
