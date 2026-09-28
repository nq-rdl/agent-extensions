---
type: regex
# Hand-written; fixtures in evals/claude/data-request/field-read-branch-no-checkout/fixtures.yaml,
# graded by tests/test_eval_data_request_field_graders.py.
# No pyproject.toml: the pixi solve is skipped and the reason recorded.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\npixi_solve:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?(?:[Ss]kip))(?=(?:(?!\n {0,3}```)[\s\S])*?\npixi_solve:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?(?:pyproject))'
target: last_message
---
