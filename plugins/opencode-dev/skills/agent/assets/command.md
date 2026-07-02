---
# Save as .opencode/commands/test.md (project) or ~/.config/opencode/commands/test.md
# The FILENAME is the command name → run this as `/test`.
# The body below is the prompt TEMPLATE (JSON form puts it under `command.test.template`).
description: Run tests with coverage and triage failures
agent: build         # which agent runs it; if a subagent, runs as a subtask by default
# subtask: true      # force a subagent invocation even for a `primary` agent
model: anthropic/claude-3-5-sonnet-20241022
---

Run the test suite (focus area: $ARGUMENTS — first arg $1).

Current results (shell output spliced in; runs in the project root):
!`npm test`

Project test config for reference:
@vitest.config.ts

Based on these results, list each failing test and suggest a concrete fix.
