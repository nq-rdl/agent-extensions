---
type: regex
# Hand-written; fixtures in tests/test_eval_data_request_graders.py.
# The plan names capability tiers, never a model family or id.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?![Oo]pus|OPUS|[Ss]onnet|SONNET|[Hh]aiku|HAIKU|[Ff]able|FABLE|[Cc]laude-[a-z]|[Gg][Pp][Tt]-?\d|\b[Ss]ol\b|\b[Tt]erra\b|\b[Ll]una\b)(?!\n {0,3}```)[\s\S])*\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\ntasks:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?(?:model_tier))'
target: last_message
---
