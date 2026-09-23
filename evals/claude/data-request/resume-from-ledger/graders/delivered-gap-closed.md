---
type: regex
# Hand-written; fixtures in tests/test_eval_data_request_graders.py.
# The delivered G-PATH-ACCESSION is closed or stale, not open.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\nopen_gaps:(?:(?!G-PATH-ACCESSION)(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*(?:\n[^ \t\n-]|\n {0,3}```))(?=(?:(?!\n {0,3}```)[\s\S])*?\nclosed_or_stale_gaps:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?(?:G-PATH-ACCESSION))'
target: last_message
---
