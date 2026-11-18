---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_data_request_release.py.
# The engineer's `done:` comment, with its commit in the release ref, closes P3.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\np3_closed_by:[ \t]*["'']?(?:done)["'']?[ \t]*(?:#[^\n]*)?\n)(?!(?:(?!\n {0,3}```)[\s\S])*?\np3_closed_by:(?![ \t]*["'']?(?:done)["'']?[ \t]*(?:#[^\n]*)?\n))'
target: last_message
---
