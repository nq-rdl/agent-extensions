---
name: address-comments
description: Use when asked to address pull request review comments; it evaluates
  each comment, makes targeted fixes, ensures test coverage, and commits changes with
  descriptive messages.
license: MIT
metadata:
  upstream: https://github.com/github/awesome-copilot/blob/main/agents/address-comments.agent.md
  repo: https://github.com/nq-rdl/agent-extensions
---

## Codex execution

Delegation is optional. Read references/subagent.rst only when delegation is useful or requested. It does not install a named agent or grant permissions.

# Address Comments

Evaluate each review comment against the code and intended behavior. Make targeted fixes, cover changed behavior with tests, and report comments addressed or declined with reasons. Commit only within the user-authorized workflow.

## Optional delegation

[references/subagent.rst](references/subagent.rst) contains the subagent outline,
handoff inputs, execution boundaries, and expected result. Read it when delegating
would help or the user asks to “create a subagent to execute this.” Otherwise,
work directly from this skill; the reference does not need to be loaded.
