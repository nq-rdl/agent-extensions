---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_data_request_prerelease_change.py.
# Absent release signals are not proof: the release status stays unconfirmed.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\nrelease_status:[ \t]*["'']?(?:unconfirmed)["'']?[ \t]*(?:#[^\n]*)?\n)(?!(?:(?!\n {0,3}```)[\s\S])*?\nrelease_status:(?![ \t]*["'']?(?:unconfirmed)["'']?[ \t]*(?:#[^\n]*)?\n))'
target: last_message
---
