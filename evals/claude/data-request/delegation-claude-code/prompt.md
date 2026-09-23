---
description: Claude Code co-development plan selects models by capability, not family names, and discloses the missing add_repo capability
tags: [delegation, claude-code]
runs: 3
max_turns: 6
timeout_seconds: 240
allowed_tools: [Read, Glob, Grep, Skill]
---

We are in co-development mode on ENQ1213 (rdl-service-desk/service-desk#76, approval repository SSAQHTS-43408). With the human we agreed three tasks:

1. Plan the G-PROJECTION library slice in nq-rdl/query-builder (output projection for screening logs).
2. Copyedit the ENQ1213 triage report before the human posts it.
3. Re-verify that the draft's anti-join is correlated, against the fixed query-builder core.

This Claude Code session can start subagents, and its model picker offers several models at different capability and cost levels. There is no `add_repo` tool, and SSAQHTS-43408 is not cloned or otherwise in session scope. The session prompt we used last month said "use Opus for brainstorm, plan and analyse, and Sonnet otherwise".

Write the delegation plan. End your reply with one fenced `yaml` block with exactly these top-level keys: `tasks` (a list; each item has `task`, `model_tier` and `worker_scope`) and `unavailable` (a list of the capabilities this session lacks that the plan depends on).
