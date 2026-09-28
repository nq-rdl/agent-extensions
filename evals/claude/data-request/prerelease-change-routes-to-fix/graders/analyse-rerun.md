---
type: regex
# Hand-written; fixtures in ../fixtures.yaml are graded by tests/test_data_request_prerelease_change.py.
# The existing .sqlreview review is stale and /data-request:analyse re-runs before release.
pattern: '^(?=[\s\S]*\bstale\b)[\s\S]*\bdata-request:analyse\b'
target: last_message
---
