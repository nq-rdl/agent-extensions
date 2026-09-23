---
type: regex
# Hand-written; fixtures in tests/test_eval_data_request_graders.py.
# Both the scaffold PR 2 and the competing triage PR 6 are named.
pattern: '^(?=[\s\S]*(?:#|PR ?|pull/)2\b)(?=[\s\S]*(?:#|PR ?|pull/)6\b)'
target: last_message
---
