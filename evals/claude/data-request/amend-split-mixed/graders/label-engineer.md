---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_eval_data_request_amend_graders.py.
# The ward-label part is engineer-required, and is nowhere called analyst-safe.
pattern: '^(?![\s\S]*(?:^|\n)[^\n]*(?:[Ww]ard|[Ll]abel)[^\n]*\n(?:[ \t]*\n)?[ \t>*_`-]*[Cc]lassification[*_` \t]*:[*_` \t]*analyst-safe\b)[\s\S]*(?:^|\n)[^\n]*(?:[Ww]ard|[Ll]abel)[^\n]*\n(?:[ \t]*\n)?[ \t>*_`-]*[Cc]lassification[*_` \t]*:[*_` \t]*engineer-required\b'
target: last_message
---
