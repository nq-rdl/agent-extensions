---
name: codex-rescue
license: Apache-2.0
description: Forward investigation, an explicit fix request, or follow-up rescue work to the Codex companion runtime
argument-hint: "[--background|--wait] [--resume|--fresh] [--model <model|spark>] [--effort <low|medium|high|xhigh|max|ultra>] [what Codex should investigate, solve, or continue]"
user-invocable: true
allowed-tools: Bash(node:*), AskUserQuestion, Agent
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

<!--
SPDX-License-Identifier: Apache-2.0
Derived from openai/codex-plugin-cc v1.0.6 (db52e28), Apache-2.0. Modified for rdl-agent-extensions.
-->

Forward the request through the `codex:cli-runtime` skill's companion `task`
contract. Read that skill before executing the task call. Run directly unless
isolation is useful or the user requests a subagent; the optional outline below
specifies the worker handoff. Do not recursively invoke `codex:rescue`.
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

- If the request includes `--background`, run the forwarding task using the host’s background execution support.
- If the request includes `--wait`, run the forwarding task in the foreground.
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
- If the user chooses continue, add `--resume` before forwarding the task.
- If the user chooses a new thread, add `--fresh` before forwarding the task.
- If the helper reports `available: false`, do not ask. Route normally.

Operating rules:

- The executor is a thin forwarder only. Use one `Bash` call to invoke `node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" task ...` and return that command's stdout as-is.
- Return the Codex companion stdout verbatim to the user.
- Do not paraphrase, summarize, rewrite, or add commentary before or after it.
- The executor must not inspect files, monitor progress, poll `/codex:status`, fetch `/codex:result`, call `/codex:cancel`, summarize output, or do follow-up work of its own.
- Leave `--effort` unset unless the user explicitly asks for a specific reasoning effort. Accepted efforts are `low`, `medium`, `high`, `xhigh`, `max`, and `ultra` (`ultra` is Sol/Terra only); unknown values warn and pass through to Codex.
- Leave the model unset unless the user explicitly asks for one. If they ask for `spark`, map it to `gpt-5.3-codex-spark`. If they ask for `sol`, `terra`, or `luna`, map to `gpt-5.6-sol`, `gpt-5.6-terra`, or `gpt-5.6-luna`.
- Leave `--resume` and `--fresh` in the forwarded request. The runtime contract handles that routing when it builds the `task` command.
- If the helper reports that Codex is missing or unauthenticated, stop and tell the user to run `/codex:setup`.
- If the user did not supply a request, ask what Codex should investigate or fix.

## Optional delegation

[references/subagent.rst](references/subagent.rst) contains the subagent outline,
handoff inputs, execution boundaries, and expected result. Read it when delegating
would help or the user asks to “create a subagent to execute this.” Otherwise,
work directly from this skill; the reference does not need to be loaded.

## Codex packaging

For execution in a native Codex package, use the host-specific entrypoint in
[references/codex.rst](references/codex.rst). The registry selects it during packaging;
the Claude entrypoint above remains the Claude workflow.
