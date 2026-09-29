---
type: regex
# Hand-written; fixtures in tests/test_eval_data_request_graders.py grade it in Python and Node.
# A rename in an extract the researcher already has is an amendment to a released extract: amend, not fix.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\nrename_stage:[ \t]*["'']?(?:/?data-request:)?(?:amend)["'']?[ \t]*(?:#[^\n]*)?\n)(?!(?:(?!\n {0,3}```)[\s\S])*?\nrename_stage:(?![ \t]*["'']?(?:/?data-request:)?(?:amend)["'']?[ \t]*(?:#[^\n]*)?\n))'
target: last_message
---
