---
name: skill-review
license: CC-BY-4.0
description: >-
  Review skills changed during a development session for actionable bugs and
  improvements. Use after creating, editing, or debugging a skill to capture
  user corrections and close the feedback loop; optionally delegate a second
  opinion using the referenced worker outline.
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

# Skill Review

Review the skills touched in this session against the repository's contributor
instructions and the evidence of what worked or needed correction.

1. Summarize the session: touched skills, changes, user corrections, verified API
   names or versions, and unresolved questions. Use the available conversation
   context; a full transcript read is unnecessary.
2. Locate the touched skill files and applicable `AGENTS.md` or `CLAUDE.md`.
3. Read the changed instructions and references. Compare them with the summary
   and report actionable findings grouped CRITICAL → MODERATE → MINOR, with
   file locations and corrections that still need to be captured.
4. Save the review to the user's chosen path, or
   `~/.claude/skill-reviews/<timestamp>.md` for this Claude Code workflow. Return
   the findings and report where they were saved. Keep reviewed skills unchanged
   unless fixes are requested.

## Optional delegation

[references/subagent.rst](references/subagent.rst) contains the reviewer outline
and handoff contract. Read it when an independent review would help or the user
asks to create a subagent to execute this task. Otherwise review directly without
loading the outline.
