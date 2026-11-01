---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_data_request_release.py.
# A held table is reported as held and the record is not approved.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\nstatus:[ \t]*["'']?(?:held)["'']?[ \t]*(?:#[^\n]*)?\n)(?!(?:(?!\n {0,3}```)[\s\S])*?\nstatus:(?![ \t]*["'']?(?:held)["'']?[ \t]*(?:#[^\n]*)?\n))(?=(?:(?!\n {0,3}```)[\s\S])*?\napprove:[ \t]*["'']?(?:no)["'']?[ \t]*(?:#[^\n]*)?\n)(?!(?:(?!\n {0,3}```)[\s\S])*?\napprove:(?![ \t]*["'']?(?:no)["'']?[ \t]*(?:#[^\n]*)?\n))'
target: last_message
---
