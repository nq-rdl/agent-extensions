---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_data_request_prerelease_change.py.
# The reply names the pre-release path and never classifies the change as an amendment
# (no amend "classification:" line), because no released extract exists to amend.
pattern: '^(?![\s\S]*(?:^|\n)[ \t>*_`-]*[Cc]lassification[*_` \t]*:[*_` \t]*(?:analyst-safe|engineer-required)\b)[\s\S]*\b[Pp]re-?release\b'
target: last_message
---
