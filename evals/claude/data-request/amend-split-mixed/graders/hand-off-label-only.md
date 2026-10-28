---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_eval_data_request_amend_graders.py.
# The hand-off has one requested change, for the label part, and lists what the analyst already did.
pattern: '^(?![\s\S]*[Rr]equested change[*_` \t]*:[\s\S]*[Rr]equested change[*_` \t]*:)(?=[\s\S]*[Rr]equested change[*_` \t]*:[^\n]*(?:[Ww]ard|[Ll]abel))[\s\S]*[Aa]lready done by the analyst[*_` \t]*:(?![*_` \t]*[\"“]?none\b)'
target: last_message
---
