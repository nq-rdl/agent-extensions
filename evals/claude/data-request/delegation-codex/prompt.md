---
description: Codex co-development plan runs directly when subagents and Workflow scripts are unavailable, discloses those limits, and selects models by capability
tags: [delegation, codex]
runs: 3
max_turns: 6
timeout_seconds: 240
allowed_tools: [Read, Glob, Grep, Skill]
---

We are in co-development mode on ENQ1213 (rdl-service-desk/service-desk#76, approval repository SSAQHTS-43408), running in the Codex CLI rather than Claude Code. With the human we agreed three tasks:

1. Plan the G-PROJECTION library slice in nq-rdl/query-builder (output projection for screening logs).
2. Copyedit the ENQ1213 triage report before the human posts it.
3. Re-verify that the draft's anti-join is correlated, against the fixed query-builder core.

This Codex profile disables native subagent delegation, Claude Code Workflow scripts cannot run here, and there is no `add_repo`. The model selector offers several models at different reasoning levels. The previous plan named "GPT-5.6 Sol" for planning and "Luna" for copyedits.

Write the execution plan. End your reply with one fenced `yaml` block with exactly these top-level keys: `execution` (`direct` or `delegated`), `tasks` (a list; each item has `task` and `model_tier`) and `unavailable` (a list of the capabilities this session lacks that the plan depends on).
