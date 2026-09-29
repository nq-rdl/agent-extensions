---
type: regex
# Hand-written; fixtures in tests/test_eval_data_request_graders.py grade it in Python and Node.
# Delivered output that contradicts the agreed plain identifier is a defect: fix, not amend.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\nidentifier_stage:[ \t]*["'']?(?:/?data-request:)?(?:fix)["'']?[ \t]*(?:#[^\n]*)?\n)(?!(?:(?!\n {0,3}```)[\s\S])*?\nidentifier_stage:(?![ \t]*["'']?(?:/?data-request:)?(?:fix)["'']?[ \t]*(?:#[^\n]*)?\n))'
target: last_message
---
