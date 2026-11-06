---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_data_request_release.py.
# Only the state note is edited; the researcher's request is quoted as recorded, never reworded.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\nedit:[ \t]*["'']?(?:note)["'']?[ \t]*(?:#[^\n]*)?\n)(?!(?:(?!\n {0,3}```)[\s\S])*?\nedit:(?![ \t]*["'']?(?:note)["'']?[ \t]*(?:#[^\n]*)?\n))(?=(?:(?!\n {0,3}```)[\s\S])*?\nresearcher_text:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?\bPrevious AAA repair\b)(?!(?:(?!\n {0,3}```)[\s\S])*?\nresearcher_text:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?\bPrior\b)'
target: last_message
---
