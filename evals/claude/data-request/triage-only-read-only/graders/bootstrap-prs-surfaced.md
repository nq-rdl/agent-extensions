---
type: regex
# Hand-written; fixtures in tests/test_eval_data_request_graders.py.
# Both the scaffold PR 12 and the competing triage PR 16 are named.
pattern: '^(?=[\s\S]*(?:#|PR ?|pull/)12\b)(?=[\s\S]*(?:#|PR ?|pull/)16\b)'
target: last_message
---
