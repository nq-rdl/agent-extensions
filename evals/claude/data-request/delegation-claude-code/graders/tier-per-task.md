---
type: regex
# Hand-written; fixtures in tests/test_eval_data_request_graders.py.
# Each of the three tasks has a model_tier.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\ntasks:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?(?:model_tier:[ \t]*[''\"]?[A-Za-z](?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?model_tier:[ \t]*[''\"]?[A-Za-z](?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?model_tier:[ \t]*[''\"]?[A-Za-z]))'
target: last_message
---
