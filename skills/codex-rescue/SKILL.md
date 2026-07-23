---
name: codex-rescue
description: Delegate investigation, an explicit fix request, or follow-up rescue work to the Codex rescue subagent
argument-hint: "[--background|--wait] [--resume|--fresh] [--model <model|spark>] [--effort <low|medium|high|xhigh|max|ultra>] [what Codex should investigate, solve, or continue]"
user-invocable: true
allowed-tools: Bash(node:*), AskUserQuestion, Agent
---

<!--
SPDX-License-Identifier: Apache-2.0
Derived from openai/codex-plugin-cc v1.0.6 (db52e28), Apache-2.0. Modified for rdl-agent-extensions.
-->

Invoke the `codex:codex-rescue` subagent via the `Agent` tool (`subagent_type: "codex:codex-rescue"`), forwarding the raw user request as the prompt.
`codex:codex-rescue` is a subagent, not a skill — do not call `Skill(codex:codex-rescue)` (no such skill) or `Skill(codex:rescue)` (that re-enters this command and hangs the session). The command runs inline so the `Agent` tool stays in scope; forked general-purpose subagents do not expose it.
The final user-visible response must be Codex's output verbatim.

## Preflight — Node.js runtime

Before running the companion helper or the subagent, verify Node >=18.18.0:

```bash
node --version >/dev/null 2>&1 && node -e 'const [a,b]=process.versions.node.split(".").map(Number); process.exit(a>18||(a===18&&b>=18)?0:1)'
```

If that check fails (non-zero exit or `node` not found), stop and tell the user exactly: `Codex plugin requires Node.js >=18.18.0; install or upgrade Node: https://nodejs.org/en/download`. Do not surface a raw `command not found` or version error.

Raw user request:
$ARGUMENTS

Execution mode:

- If the request includes `--background`, run the `codex:codex-rescue` subagent in the background.
- If the request includes `--wait`, run the `codex:codex-rescue` subagent in the foreground.
- If neither flag is present, default to foreground.
- `--background` and `--wait` are execution flags for Claude Code. Do not forward them to `task`, and do not treat them as part of the natural-language task text.
- `--model` and `--effort` are runtime-selection flags. Preserve them for the forwarded `task` call, but do not treat them as part of the natural-language task text.
- If the request includes `--resume`, do not ask whether to continue. The user already chose.
- If the request includes `--fresh`, do not ask whether to continue. The user already chose.
- Otherwise, before starting Codex, check for a resumable rescue thread from this Claude session by running:

```bash
node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" task-resume-candidate --json
```

- If that helper reports `available: true`, use `AskUserQuestion` exactly once to ask whether to continue the current Codex thread or start a new one.
- The two choices must be:
  - `Continue current Codex thread`
  - `Start a new Codex thread`
- If the user is clearly giving a follow-up instruction such as "continue", "keep going", "resume", "apply the top fix", or "dig deeper", put `Continue current Codex thread (Recommended)` first.
- Otherwise put `Start a new Codex thread (Recommended)` first.
- If the user chooses continue, add `--resume` before routing to the subagent.
- If the user chooses a new thread, add `--fresh` before routing to the subagent.
- If the helper reports `available: false`, do not ask. Route normally.

Operating rules:

- The subagent is a thin forwarder only. It should use one `Bash` call to invoke `node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" task ...` and return that command's stdout as-is.
- Return the Codex companion stdout verbatim to the user.
- Do not paraphrase, summarize, rewrite, or add commentary before or after it.
- Do not ask the subagent to inspect files, monitor progress, poll `/codex:status`, fetch `/codex:result`, call `/codex:cancel`, summarize output, or do follow-up work of its own.
- Leave `--effort` unset unless the user explicitly asks for a specific reasoning effort. Accepted efforts are `low`, `medium`, `high`, `xhigh`, `max`, and `ultra` (`ultra` is Sol/Terra only); unknown values warn and pass through to Codex.
- Leave the model unset unless the user explicitly asks for one. If they ask for `spark`, map it to `gpt-5.3-codex-spark`. If they ask for `sol`, `terra`, or `luna`, map to `gpt-5.6-sol`, `gpt-5.6-terra`, or `gpt-5.6-luna`.
- Leave `--resume` and `--fresh` in the forwarded request. The subagent handles that routing when it builds the `task` command.
- If the helper reports that Codex is missing or unauthenticated, stop and tell the user to run `/codex:setup`.
- If the user did not supply a request, ask what Codex should investigate or fix.
