---
type: regex
# Hand-written; fixtures in tests/test_eval_claude_prompting_graders.py.
# The system-prompt addition goes in from the first request of the session.
pattern: '[Ff]irst request|(?:start|beginning) of (?:the|each|every) session|session start|mid-?(?:session|conversation)[^\n]{0,120}(?:invalidat|thinking block|cache)|(?:invalidat|thinking block)[^\n]{0,120}mid-?(?:session|conversation)'
target: last_message
---
