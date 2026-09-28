---
description: An unattended Opus 5.5 loop that stops on progress reports gets a checklist, bounded continuations, display updates and a first-request prompt addition
tags: [agents, progress-updates]
runs: 5
max_turns: 6
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, Skill]
---

Our overnight agent runs unattended on `claude-opus-5-5`. The harness loop treats the task as finished whenever `stop_reason` is `end_turn`. Since we moved from Opus 5, runs often stop halfway: the last message is a progress summary ending with something like "Next I'll migrate the remaining endpoints." Our UI also shows nothing between tool calls during long turns, although Opus 5 used to write short notes there.

What should we change in the harness and in the system prompt?
