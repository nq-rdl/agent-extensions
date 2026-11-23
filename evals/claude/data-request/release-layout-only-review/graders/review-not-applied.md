---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_data_request_release.py.
# The review does not apply to the tag yet: layout-only is evidence, not a pass.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\nreview_applies:[ \t]*["'']?(?:no)["'']?[ \t]*(?:#[^\n]*)?\n)(?!(?:(?!\n {0,3}```)[\s\S])*?\nreview_applies:(?![ \t]*["'']?(?:no)["'']?[ \t]*(?:#[^\n]*)?\n))'
target: last_message
---
