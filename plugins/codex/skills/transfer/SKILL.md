---
description: Transfer the current Claude Code session into a resumable Codex thread
argument-hint: "[--source <claude-jsonl>]"
user-invocable: true
disable-model-invocation: true
allowed-tools: Bash(node:*)
---

<!--
SPDX-License-Identifier: Apache-2.0
Derived from openai/codex-plugin-cc v1.0.6 (db52e28), Apache-2.0. Modified for rdl-agent-extensions.
-->

## Preflight — Node.js runtime

Before running the companion, verify Node >=18.18.0:

```bash
node --version >/dev/null 2>&1 && node -e 'const [a,b]=process.versions.node.split(".").map(Number); process.exit(a>18||(a===18&&b>=18)?0:1)'
```

If that check fails (non-zero exit or `node` not found), stop and tell the user exactly: `Codex plugin requires Node.js >=18.18.0; install or upgrade Node: https://nodejs.org/en/download`. Do not surface a raw `command not found` or version error.

## Run

```bash
node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" transfer "$ARGUMENTS"
```

Present the command output to the user exactly as returned. Preserve the Codex session ID and the `codex resume <session-id>` command.
