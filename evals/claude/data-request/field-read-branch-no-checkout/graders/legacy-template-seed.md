---
type: regex
# Hand-written; fixtures in evals/claude/data-request/field-read-branch-no-checkout/fixtures.yaml,
# graded by tests/test_eval_data_request_field_graders.py.
# Old _src_path with the current scaffold directories is a legacy-template seed.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\nscaffold_state:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?(?:[Ll]egacy[- ][Tt]emplate[- ][Ss]eed))'
target: last_message
---
