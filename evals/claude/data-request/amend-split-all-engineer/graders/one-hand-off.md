---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_eval_data_request_amend_graders.py.
# A single hand-off comment carries one requested-change entry for each part.
pattern: '^(?![\s\S]*[Aa]mendment hand-off[*_` \t]*:[\s\S]*[Aa]mendment hand-off[*_` \t]*:)(?=[\s\S]*[Aa]mendment hand-off[*_` \t]*:)(?=[\s\S]*[Rr]equested change[*_` \t]*:[\s\S]*[Rr]equested change[*_` \t]*:)'
target: last_message
---
