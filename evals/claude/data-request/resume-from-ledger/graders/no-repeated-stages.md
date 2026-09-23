---
type: regex
# Hand-written; fixtures in tests/test_eval_data_request_graders.py.
# next_actions validates and repeats no completed stage or cohort discovery.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\nnext_actions:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?(?:[Vv]alidat))(?=(?:(?!\n {0,3}```)[\s\S])*?\nnext_actions:(?:(?![Bb]ootstrap|[Ii]ntake|data-request:map|[Cc]ohort[ -]discovery|[Dd]iscover(?:y of)? the cohort|[Ff]ind the cohort|[Ii]dentify the cohort|[Rr]e-?draft)(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*(?:\n[^ \t\n-]|\n {0,3}```))'
target: last_message
---
