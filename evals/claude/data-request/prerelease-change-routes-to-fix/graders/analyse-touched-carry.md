---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_data_request_prerelease_change.py.
# analyse re-runs and walks only touched items with one carry question; a plain re-run is not enough.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\nanalyse:[ \t]*["'']?(?:rerun carry)["'']?[ \t]*(?:#[^\n]*)?\n)(?!(?:(?!\n {0,3}```)[\s\S])*?\nanalyse:(?![ \t]*["'']?(?:rerun carry)["'']?[ \t]*(?:#[^\n]*)?\n))'
target: last_message
---
