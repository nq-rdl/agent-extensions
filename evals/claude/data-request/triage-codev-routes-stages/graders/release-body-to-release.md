---
type: regex
# Hand-written; fixtures in tests/test_eval_data_request_graders.py grade it in Python and Node.
# The researcher-facing release body is drafted by release, not by analyse or explain.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\nrelease_body_stage:[ \t]*["'']?(?:/?data-request:)?(?:release)["'']?[ \t]*(?:#[^\n]*)?\n)(?!(?:(?!\n {0,3}```)[\s\S])*?\nrelease_body_stage:(?![ \t]*["'']?(?:/?data-request:)?(?:release)["'']?[ \t]*(?:#[^\n]*)?\n))'
target: last_message
---
