---
type: regex
# Hand-written; fixtures in tests/test_eval_claude_prompting_graders.py.
# Progress-update thinking blocks are surfaced with display: updates.
pattern: 'display[^\n]{0,40}updates|thinking-display-updates'
target: last_message
---
