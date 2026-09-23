---
type: regex
# Hand-written; fixtures in tests/test_eval_data_request_graders.py.
# resume_stage is validate, the interrupted stage.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\nresume_stage:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?(?:[Vv]alidat|VALIDAT))'
target: last_message
---
