---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_data_request_release.py.
# The next step is the engineer re-binding the record (sqlreview.sh rebind), not a new review and not wording from the items.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\nnext_step:[ \t]*["'']?(?:rebind)["'']?[ \t]*(?:#[^\n]*)?\n)(?!(?:(?!\n {0,3}```)[\s\S])*?\nnext_step:(?![ \t]*["'']?(?:rebind)["'']?[ \t]*(?:#[^\n]*)?\n))'
target: last_message
---
