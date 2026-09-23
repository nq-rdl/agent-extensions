---
type: regex
# Hand-written; fixtures in tests/test_eval_data_request_graders.py.
# Both missing subagents and the Workflow runtime are disclosed.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\nunavailable:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?(?:[Ss]ub-?agent))(?=(?:(?!\n {0,3}```)[\s\S])*?\nunavailable:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?(?:[Ww]orkflow))'
target: last_message
---
