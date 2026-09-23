---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_eval_data_request_amend_graders.py.
# The hand edit of generated SQL is refused, and the reply ships no edited SQL.
pattern: '^(?![\s\S]*(?:^|\n) {0,3}(?:```|~~~)[ \t]*(?:sql|SQL|tsql|t-sql)\b[^\n]*\n(?:(?! {0,3}(?:```|~~~))[^\n]*\n)*?[^\n]*\b[Aa][Ss][ \t]+[\[\"]?URN\b)[\s\S]*\b[Rr]efus(?:e|ed|es|ing|al)\b'
target: last_message
---
