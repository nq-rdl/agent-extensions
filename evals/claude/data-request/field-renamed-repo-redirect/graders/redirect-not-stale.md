---
type: regex
# Hand-written; fixtures in evals/claude/data-request/field-renamed-repo-redirect/fixtures.yaml,
# graded by tests/test_eval_data_request_field_graders.py.
# Only the link that does not resolve is stale; the redirecting link is not.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\nstale_links:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?(?:THHSRDLENQ-9006\b))(?=(?:(?!\n {0,3}```)[\s\S])*?\nstale_links:(?:(?!THHSRDLENQ-9005\b)(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*(?:\n[^ \t\n-]|\n {0,3}```))'
target: last_message
---
