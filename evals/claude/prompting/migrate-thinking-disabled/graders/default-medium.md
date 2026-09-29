---
type: regex
# Hand-written; fixtures in tests/test_eval_prompting_graders.py.
# The default effort is named as medium.
pattern: '[Dd]efault[^\n]{0,120}`?medium`?|`?medium`?[^\n]{0,120}[Dd]efault'
target: last_message
---
