---
type: regex
# Hand-written; fixtures in evals/claude/data-request/field-renamed-repo-redirect/fixtures.yaml,
# graded by tests/test_eval_data_request_field_graders.py.
# A verbal decision against the newest written comment is unlinked; the written value stands or a conflict is shown.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\nlactate_decision_status:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?(?:[Uu]nlinked))(?=(?:(?!\n {0,3}```)[\s\S])*?\nlactate_decision_status:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?(?:[Cc]onflict|[Kk]eep|[Kk]ept|[Ss]tands|[Rr]etain))(?=(?:(?!\n {0,3}```)[\s\S])*?\nlactate_decision_status:(?:(?![Aa]pplied\b|(?:lactate|field)(?: result)?(?: field)? (?:is |was |now )?(?:dropped|removed))(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*(?:\n[^ \t\n-]|\n {0,3}```))'
target: last_message
---
