---
name: record-decision
description: Use when the user wants to record an architectural decision (ADR) for
  a change or tradeoff they are making. Gathers context, assigns sequential numbering,
  and produces a structured markdown ADR file.
license: MIT
metadata:
  upstream: https://github.com/github/awesome-copilot/blob/main/agents/adr-generator.agent.md
  repo: https://github.com/nq-rdl/agent-extensions
---

## Codex execution

Delegation is optional. Read references/subagent.rst only when delegation is useful or requested. It does not install a named agent or grant permissions.

# Record Decision

Read existing ADRs to choose the next four-digit number. Record the decision, context, alternatives, consequences, status, and references in the repository’s ADR directory. Preserve unresolved decisions and honest tradeoffs rather than inventing consensus.

## Optional delegation

[references/subagent.rst](references/subagent.rst) contains the subagent outline,
handoff inputs, execution boundaries, and expected result. Read it when delegating
would help or the user asks to “create a subagent to execute this.” Otherwise,
work directly from this skill; the reference does not need to be loaded.
