---
type: regex
# Hand-written; fixtures in evals/claude/data-request/field-renamed-repo-redirect/fixtures.yaml,
# graded by tests/test_eval_data_request_field_graders.py.
# The enquiry-named link redirects to the approval-ID repository: use it and report the redirect.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\nrepo:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?(?:THHSAQUIRE-9905\b))(?=(?:(?!\n {0,3}```)[\s\S])*?\nredirected_links:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?(?:THHSRDLENQ-9005\b))'
target: last_message
---
