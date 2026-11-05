---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_eval_data_request_amend_graders.py.
# The code-to-words part is engineer-required, and is nowhere called analyst-safe.
pattern: '^(?![\s\S]*(?:^|\n)[^\n]*(?:[Ss]ex|[Ww]ords)[^\n]*\n(?:[ \t]*\n)?[ \t>*_`-]*[Cc]lassification[*_` \t]*:[*_` \t]*analyst-safe\b)[\s\S]*(?:^|\n)[^\n]*(?:[Ss]ex|[Ww]ords)[^\n]*\n(?:[ \t]*\n)?[ \t>*_`-]*[Cc]lassification[*_` \t]*:[*_` \t]*engineer-required\b'
target: last_message
---
