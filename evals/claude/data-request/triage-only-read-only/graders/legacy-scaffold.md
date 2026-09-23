---
type: regex
# Hand-written; fixtures in tests/test_eval_data_request_graders.py.
# The scaffold state is classified as legacy.
pattern: '(?:[Ll]egacy|LEGACY)[\s\S]{0,300}(?:scaffold|template|shell)|(?:scaffold|template|shell)[\s\S]{0,300}(?:[Ll]egacy|LEGACY)'
target: last_message
---
