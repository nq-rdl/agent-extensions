---
description: Analyse MongoDB database performance, offer query and index optimisation insights, and provide actionable recommendations to improve overall database usage. Operates in read-only mode against a connected MongoDB cluster.
license: MIT
metadata:
  upstream: https://github.com/github/awesome-copilot/blob/main/agents/mongodb-performance-advisor.agent.md
  repo: https://github.com/nq-rdl/agent-extensions
---

# Analyse

Inspect MongoDB performance evidence with available read-only database tools. Prefer Atlas Performance Advisor when available; compare explain plans and query semantics without changing the database. Report measured findings and index tradeoffs; do not invent improvements for indexes that were not created.

## Optional delegation

[references/subagent.rst](references/subagent.rst) contains the subagent outline,
handoff inputs, execution boundaries, and expected result. Read it when delegating
would help or the user asks to “create a subagent to execute this.” Otherwise,
work directly from this skill; the reference does not need to be loaded.
