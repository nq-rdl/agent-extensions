---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_data_request_prerelease_change.py.
# analyse re-runs with a full re-walk; plain carry-forward would keep unchanged-line items.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\nanalyse:[ \t]*["'']?(?:rerun --reconfirm-all)["'']?[ \t]*(?:#[^\n]*)?\n)(?!(?:(?!\n {0,3}```)[\s\S])*?\nanalyse:(?![ \t]*["'']?(?:rerun --reconfirm-all)["'']?[ \t]*(?:#[^\n]*)?\n))'
target: last_message
---
