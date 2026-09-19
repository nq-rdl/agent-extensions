---
type: regex
# A method receiver must be present and none may be this/self. A plain
# not_contains would pass vacuously on an empty or failed reply.
pattern: '^(?![\s\S]*func\s+\(\s*(?:this|self)\b)[\s\S]*func\s+\(\s*\w+\s+\*?\w+\s*\)'
target: last_message
---
