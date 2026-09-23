---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_eval_data_request_amend_graders.py.
# The paste-ready hand-off names the requested change, the boundary rule it hits and the affected maintained source.
pattern: '^(?=[\s\S]*[Rr]equested change[*_` \t]*:)(?=[\s\S]*[Bb]oundary rule[*_` \t]*:)(?=[\s\S]*[Aa]ffected files[*_` \t]*:)[\s\S]*src/cohort/falls\.py'
target: last_message
---
