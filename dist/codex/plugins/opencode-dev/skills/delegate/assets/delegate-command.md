---
description: Delegate a coding task to OpenCode and return a job id to poll
argument-hint: "<task description>"
---
<!--
  Starter Claude Code slash command — a THIN BASH FORWARDER into the companion.
  No logic lives here; the companion owns the OpenCode connection + job store.
  Companion paths: `${CLAUDE_PLUGIN_ROOT}/scripts/companion.mjs`.
  Prereqs (handle in a /<plugin>:setup command, not here): `opencode` CLI on PATH,
  a running `opencode serve` (default 127.0.0.1:4096), Node 18+.
  Sibling forwarders reuse the same one-line pattern: status / result / cancel.
-->

Delegate this task to OpenCode and report the job id:

```bash
node "${CLAUDE_PLUGIN_ROOT}/scripts/companion.mjs" task "$ARGUMENTS"
```

Then tell the user the returned `id` and that they can poll with
`/<plugin>:status <id>`, fetch output with `/<plugin>:result <id>`, or stop it with
`/<plugin>:cancel <id>`. Do not block waiting for completion — the companion ran the
work in a detached worker.

<!--
  Transport note: this forwarder is identical whether the companion drives OpenCode
  via `serve`+SDK, `opencode acp`, or `opencode run --format json --attach ...`.
  Swap the companion's transport, not this command. See SKILL.md.
-->
