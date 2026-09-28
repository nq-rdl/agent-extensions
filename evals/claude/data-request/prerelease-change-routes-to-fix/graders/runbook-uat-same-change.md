---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_data_request_prerelease_change.py.
# The runbook and UAT checklist change in the same change as the SQL.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\nrunbook_uat:[ \t]*["'']?(?:same change)["'']?[ \t]*(?:#[^\n]*)?\n)(?!(?:(?!\n {0,3}```)[\s\S])*?\nrunbook_uat:(?![ \t]*["'']?(?:same change)["'']?[ \t]*(?:#[^\n]*)?\n))'
target: last_message
---
