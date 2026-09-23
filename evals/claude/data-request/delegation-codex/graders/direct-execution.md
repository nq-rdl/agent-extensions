---
type: regex
# Hand-written; fixtures in tests/test_eval_data_request_graders.py.
# Without subagents the plan runs directly.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\nexecution:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?(?:[Dd]irect))(?=(?:(?!\n {0,3}```)[\s\S])*?\nexecution:(?:(?![Dd]elegat|[Ss]ubagent)(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*(?:\n[^ \t\n-]|\n {0,3}```))'
target: last_message
---
