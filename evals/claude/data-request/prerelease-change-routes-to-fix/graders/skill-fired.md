---
type: tool_used
# Plugin-fired indicator: the fix entry point, which owns pre-release logic changes, was loaded
# (sync strips name:, so match the leaf).
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?fix"'
---
