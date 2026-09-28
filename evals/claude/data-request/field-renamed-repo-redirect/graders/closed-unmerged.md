---
type: regex
# Hand-written; fixtures in evals/claude/data-request/field-renamed-repo-redirect/fixtures.yaml,
# graded by tests/test_eval_data_request_field_graders.py.
# A PR closed with merged_at null is not merged, whatever merge_commit_sha says.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\npr_5_merged:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?(?:[ \t]*(?:[Ff]alse|[Nn]o)\b))(?=(?:(?!\n {0,3}```)[\s\S])*?\npr_5_merged:(?:(?![Tt]rue\b)(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*(?:\n[^ \t\n-]|\n {0,3}```))'
target: last_message
---
