---
type: regex
# Hand-written; fixtures in evals/claude/data-request/field-read-branch-no-checkout/fixtures.yaml,
# graded by tests/test_eval_data_request_field_graders.py.
# Commands read the branch with git show or git ls-tree and never check it out.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\ncommands:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?(?:\bgit\b[^\n]*\s(?:show|ls-tree)\b))(?=(?:(?!\n {0,3}```)[\s\S])*?\ncommands:(?:(?!\s(?:checkout|switch|pull|reset|restore|merge|rebase|stash)(?![\w-])|\bworktree[ \t]+add\b)(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*(?:\n[^ \t\n-]|\n {0,3}```))'
target: last_message
---
