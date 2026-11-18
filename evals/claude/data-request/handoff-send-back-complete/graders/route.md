---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_data_request_handoff.py.
# A logic change goes to fix.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\nroute:[ \t]*["'']?(?:fix)["'']?[ \t]*(?:#[^\n]*)?\n)(?!(?:(?!\n {0,3}```)[\s\S])*?\nroute:(?![ \t]*["'']?(?:fix)["'']?[ \t]*(?:#[^\n]*)?\n))'
target: last_message
---
