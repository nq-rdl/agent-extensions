---
type: regex
# Hand-written; fixtures in tests/test_eval_claude_prompting_graders.py.
# Disabled thinking is flagged as rejected, or thinking as always on.
pattern: '(?:disabled|[Tt]hinking)[^\n]{0,160}(?:\b400\b|reject|no longer (?:accepted|supported|allowed)|(?:not|isn''t|isn’t) (?:accepted|supported|allowed)|always[ -]on|can(?:not|''t|’t) be (?:disabled|turned off))|(?:\b400\b|[Rr]eject|[Aa]lways[ -]on)[^\n]{0,160}(?:disabled|[Tt]hinking)'
target: last_message
---
