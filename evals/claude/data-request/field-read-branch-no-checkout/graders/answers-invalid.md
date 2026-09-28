---
type: regex
# Hand-written; fixtures in evals/claude/data-request/field-read-branch-no-checkout/fixtures.yaml,
# graded by tests/test_eval_data_request_field_graders.py.
# answers.yaml does not parse; PyYAML reports line 3.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\nanswers_yaml_parses:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?(?:[ \t]*(?:[Ff]alse|[Nn]o)\b))(?=(?:(?!\n {0,3}```)[\s\S])*?\nanswers_yaml_parses:(?:(?![Tt]rue\b)(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*(?:\n[^ \t\n-]|\n {0,3}```))(?=(?:(?!\n {0,3}```)[\s\S])*?\nanswers_yaml_error_line:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?(?:\b3\b))'
target: last_message
---
