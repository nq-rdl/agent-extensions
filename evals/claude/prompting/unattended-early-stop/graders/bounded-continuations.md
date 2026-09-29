---
type: regex
# Hand-written; fixtures in tests/test_eval_prompting_graders.py.
# Automatic continuations are capped.
pattern: '(?:[Tt]wo or three|[Tt]wo to three|\b2 ?(?:or|to|-|–) ?3\b)[^\n]{0,120}(?:continu|nudge|reminder|retr|time|attempt)|(?:[Cc]ap|[Ll]imit|[Bb]ound|[Mm]ax(?:imum)?)[^\n]{0,80}continuation|continuation[^\n]{0,80}(?:cap|limit|bound|max)'
target: last_message
---
