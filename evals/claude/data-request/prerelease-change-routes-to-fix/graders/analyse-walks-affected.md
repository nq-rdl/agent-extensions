---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_data_request_prerelease_change.py.
# analyse walks every item the change can affect; a carried item is not asked again.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\nanalyse:[ \t]*["'']?(?:walk affected items)["'']?[ \t]*(?:#[^\n]*)?\n)(?!(?:(?!\n {0,3}```)[\s\S])*?\nanalyse:(?![ \t]*["'']?(?:walk affected items)["'']?[ \t]*(?:#[^\n]*)?\n))'
target: last_message
---
