---
type: regex
# Hand-written; fixtures in evals/claude/data-request/field-renamed-repo-redirect/fixtures.yaml,
# graded by tests/test_eval_data_request_field_graders.py.
# merged_at and a merge commit mean merged, whatever the merged flag says.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\nscaffold_pr_4_merged:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?(?:[ \t]*(?:[Tt]rue|[Yy]es)\b))(?=(?:(?!\n {0,3}```)[\s\S])*?\nscaffold_pr_4_merged:(?:(?![Ff]alse\b)(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*(?:\n[^ \t\n-]|\n {0,3}```))'
target: last_message
---
