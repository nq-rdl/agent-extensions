---
description: Migrating a thinking-disabled Opus 5 route flags the 400, the medium default effort, thinking in max_tokens, and the reasoning-extraction risk
tags: [migration, effort, thinking]
runs: 5
max_turns: 6
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, Skill]
---

We're switching an agentic coding service from `claude-opus-5` to `claude-opus-5-5`. Every request currently sends:

```json
{"model": "claude-opus-5", "max_tokens": 8000, "thinking": {"type": "disabled"}, "output_config": {"effort": "high"}}
```

The system prompt ends with: "Before the final answer, write out your full step-by-step reasoning under a `Reasoning:` heading."

What has to change in the request and in the system prompt for Opus 5.5? Be specific about each field.
