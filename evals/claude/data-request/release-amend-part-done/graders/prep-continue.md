---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_data_request_release.py.
# A withdrawn part no longer holds the release.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\nrelease_prep:[ \t]*["'']?(?:continue)["'']?[ \t]*(?:#[^\n]*)?\n)(?!(?:(?!\n {0,3}```)[\s\S])*?\nrelease_prep:(?![ \t]*["'']?(?:continue)["'']?[ \t]*(?:#[^\n]*)?\n))'
target: last_message
---
