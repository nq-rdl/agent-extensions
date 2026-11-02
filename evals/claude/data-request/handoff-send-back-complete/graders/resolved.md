---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_data_request_handoff.py.
# The note lists what the analyst already resolved, not none.
pattern: '^(?=[\s\S]*(?:^|\n)[ \t>*_`-]*[Aa]lready resolved by the analyst[*_` \t]*:(?![*_` \t]*["“]?none\b)[^\n]*\S)(?=[\s\S]*(?:^|\n)[ \t>*_`-]*[Aa]ffected files[*_` \t]*:[^\n]*\S)[\s\S]*(?:^|\n)[ \t>*_`-]*[Ww]aiting on[*_` \t]*:[^\n]*\S[\s\S]*`{3,}ya?ml'
target: last_message
---
