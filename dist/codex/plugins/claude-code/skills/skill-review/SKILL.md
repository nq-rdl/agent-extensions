---
name: skill-review
license: CC-BY-4.0
description: Review skills changed during a development session for actionable bugs
  and improvements. Use after creating, editing, or debugging a skill to capture user
  corrections and close the feedback loop; optionally delegate a second opinion using
  the referenced worker outline.
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

## Codex execution

Delegation is optional. Read references/subagent.rst only when delegation is useful or requested. It does not install a named agent or grant permissions.

# Skill Review

Review the skills touched in this session against the repository's contributor
instructions and the evidence of what worked or needed correction.

Use the user's chosen output path. Otherwise use
`${CODEX_HOME}/skill-reviews/<timestamp>.md` when CODEX_HOME is set, or
`~/.codex/skill-reviews/<timestamp>.md`. Expand the home directory and create
the parent directory if needed; quote the resolved path when using shell tools.

Read and follow [references/review.rst](references/review.rst), the required shared
review procedure. Return the findings and the saved report path.

## Optional delegation

[references/subagent.rst](references/subagent.rst) contains the reviewer outline
and handoff contract. Read it when an independent review would help or the user
requests delegation. Otherwise review directly without loading the outline.
