---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_data_request_prerelease_change.py.
# No file is edited until the release status is answered.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\nedits:[ \t]*["'']?(?:none)["'']?[ \t]*(?:#[^\n]*)?\n)(?!(?:(?!\n {0,3}```)[\s\S])*?\nedits:(?![ \t]*["'']?(?:none)["'']?[ \t]*(?:#[^\n]*)?\n))'
target: last_message
---
