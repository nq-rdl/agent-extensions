---
name: cc-hook
license: CC-BY-4.0
description: >-
  Create, manage, and debug Claude Code hooks — user-defined commands that run
  at specific points in Claude Code's lifecycle for deterministic control. Use
  when the user asks about hooks, guardrails, pre/post tool execution, safety
  rules, command blocking, context injection, auto-formatting, permission
  auto-approval, or completion checklists for Claude Code. Also trigger on
  mentions of PreToolUse, PostToolUse, PermissionRequest, SessionStart, Stop,
  UserPromptSubmit, settings.json hooks, prompt-based or agent-based hooks, or
  when the user worries that hook output looks like prompt injection. Covers all
  five hook types (command, http, mcp_tool, prompt, agent), the full event
  lifecycle, the JSON output contract (permissionDecision / decision /
  hookSpecificOutput), exit codes, and safe context-injection patterns.
argument-hint: "What hook do you want to create or debug? (e.g. 'block rm -rf', 'format on save', 'why is my Stop hook ignored')"
user-invocable: true
metadata:
  repo: https://github.com/nq-rdl/agent-skills
---

# Claude Code Hooks

Hooks are **user-defined commands that execute at specific points in Claude Code's
lifecycle**. They give deterministic control over behavior — an action *always*
happens, rather than relying on the model to choose to run it. Use them to enforce
project rules, automate repetitive tasks (formatting, logging), block dangerous
operations, and inject context.

> Authoritative sources, kept verbatim with links, live in `references/`. Read the
> matching reference before writing or debugging a hook — the I/O contract has
> changed across Claude Code versions and getting it wrong is the most common bug.

---

## Decision tree — pick the right hook type

| You want to… | Use | Reference |
|--------------|-----|-----------|
| Run a deterministic check/script (block, format, log) | `type: "command"` | `references/claude-code.rst` |
| Call a web service / shared endpoint | `type: "http"` | `references/claude-code.rst` |
| Call a tool on a connected MCP server | `type: "mcp_tool"` | `references/claude-code.rst` |
| Make a yes/no judgment with a small model | `type: "prompt"` | `references/prompt-and-agent-hooks.rst` |
| Verify against real codebase state (run tests, read files) | `type: "agent"` *(experimental)* | `references/prompt-and-agent-hooks.rst` |

> **`prompt` hooks are NOT static text.** A common misconception (and a bug in old
> versions of this skill) is that `type: "prompt"` injects a fixed reminder string.
> It does not. It sends your prompt + the event data to a Claude model that returns
> `{"ok": true|false, "reason": "..."}`. See `references/prompt-and-agent-hooks.rst`.

## Where hooks live

| Location | Scope | Shareable |
|----------|-------|-----------|
| `~/.claude/settings.json` | All your projects | No (your machine) |
| `.claude/settings.json` | One project | Yes — commit it |
| `.claude/settings.local.json` | One project | No — gitignored |
| Managed policy settings | Organization-wide | Admin-controlled |
| Plugin `hooks/hooks.json` | When plugin enabled | Bundled with plugin |
| Skill / agent frontmatter | While that component is active | In the component |

Run `/hooks` in Claude Code to browse configured hooks (read-only; edit the JSON or
ask Claude to change them). Set `"disableAllHooks": true` to turn them all off.

## Configuration shape

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/check.sh",
            "if": "Bash(git *)",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

- **matcher** — filters *which* calls fire the hook. Meaning depends on the event
  (tool name for tool events, `startup`/`resume`/… for `SessionStart`, etc.). Omit
  to match everything. See the matcher table in `references/claude-code.rst`.
- **if** (v2.1.85+) — filters by tool name *and arguments* using permission-rule
  syntax (`"Bash(git *)"`, `"Edit(*.ts)"`). Tool events only.
- **type** — `command` (default), `http`, `mcp_tool`, `prompt`, or `agent`.
- **timeout** — seconds. Defaults: command/http/mcp_tool 10 min (30 s under
  `UserPromptSubmit`), prompt 30 s, agent 60 s.

## The I/O contract (read this before writing output)

A hook reads **event JSON on stdin** and replies through **stdout + exit code**.

**Exit codes** (command hooks):

| Code | Meaning |
|------|---------|
| `0` | No objection. stdout is parsed as JSON for structured control. For `UserPromptSubmit`, `UserPromptExpansion`, `SessionStart`, plain stdout is added to context. |
| `2` | Blocking error. stdout/JSON ignored; **stderr is fed to Claude** as feedback. Effect depends on event (blocks `PreToolUse`, rejects a prompt, continues `Stop`, …). Not all events can block. |
| other | Non-blocking error. Transcript shows `<hook> hook error` + first stderr line; action proceeds. |

> Don't mix the two: use **exit 2 + stderr** *or* **exit 0 + JSON**. Claude Code
> ignores JSON when you exit 2.

**Structured JSON output** — `PreToolUse` permission control (current canonical form):

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "Use rg instead of grep"
  }
}
```

`permissionDecision` is one of `allow` / `deny` / `ask` (and `defer` in `-p` mode).
**Other events use different shapes** — `PostToolUse`/`Stop` use top-level
`{"decision": "block", "reason": "..."}`; `PermissionRequest` uses
`hookSpecificOutput.decision.behavior`. The full per-event matrix is in
`references/output.rst`. The legacy `{"decision":"approve"}` form for `PreToolUse`
is superseded by `permissionDecision` — don't use it for new hooks.

## ⚠️ Hook output vs. prompt injection

This is the concern most people hit. Text returned via `additionalContext` (or
plain stdout on `SessionStart`/`UserPromptSubmit`) is injected as a **system
reminder that Claude reads as plain text**. If you phrase it as imperative,
"out-of-band system commands," Claude's prompt-injection defenses can fire and it
may **surface the text to the user instead of acting on it.**

- ✅ Factual, declarative: `"The deployment target is production."`
- ❌ Imperative/authoritative: `"SYSTEM: You must never deploy to production."`

Keep context short and factual, prefer `additionalContext` over raw stdout, use
`suppressOutput` to hide noisy stdout, and never echo untrusted data unescaped.
Full guidance + the strings>10k-chars behavior + `terminalSequence` allowlist are in
`references/prompt-injection.rst`. **Read it before writing any context-injecting hook.**

---

## Workflows

Three focused procedures live in [references/workflows.rst](references/workflows.rst).
Load it and follow the matching one; each step points at the reference to read.
These headings are stable entrypoints — a downstream Claude Code plugin maps them
to `/cc-hook:create`, `/cc-hook:debug`, and `/cc-hook:audit`.

| Workflow | Use when | Anchor |
|----------|----------|--------|
| **Create a hook** | Going from "I want X to always happen" to a registered, tested hook | `workflow-create` |
| **Debug a hook** | A hook doesn't fire, fires wrong, or its output is ignored | `workflow-debug` |
| **Audit hooks** | Reviewing every hook that can run for correctness, safety, portability | `workflow-audit` |

---

## Common patterns

| Goal | Event | Example |
|------|-------|---------|
| Block destructive shell commands | `PreToolUse` (Bash) | `examples/block-rm-rf.json` |
| Protect sensitive files | `PreToolUse` (Edit/Write) | `examples/protect-env-files.json` |
| Continue until tasks done (judgment) | `Stop` (prompt) | `examples/prompt-hook-stop.json` |
| Require tests/lint before stopping | `Stop` (command) | `examples/stop-checklist.json` |
| Inject safe project context | `SessionStart` | `examples/safe-context-injection.json` |
| Auto-format edited files | `PostToolUse` (Edit/Write) | `examples/auto-format.json` |
| Auto-approve a known prompt | `PermissionRequest` | `examples/auto-approve-exit-plan.json` |

## Reference files

| File | Contents |
|------|----------|
| [references/workflows.rst](references/workflows.rst) | The create / debug / audit procedures, with stable anchors for plugin lenses |
| [references/claude-code.rst](references/claude-code.rst) | Core reference — config, hook types, matchers, `if`, env vars, full event table |
| [references/lifecycle.rst](references/lifecycle.rst) | The lifecycle: every event, firing order, and which events can block |
| [references/output.rst](references/output.rst) | Output contract — exit codes, JSON schema, decision control per event |
| [references/prompt-injection.rst](references/prompt-injection.rst) | Safe context injection — avoiding the prompt-injection trap, output safety, security |
| [references/prompt-and-agent-hooks.rst](references/prompt-and-agent-hooks.rst) | `type: "prompt"` and `type: "agent"` hooks (model-driven decisions) |
| [references/recipes.rst](references/recipes.rst) | Copy-paste patterns with full implementations |
| [references/debugging.rst](references/debugging.rst) | Debugging checklist, common errors, the Stop-hook block cap, debug log |

## Example files

| File | What it does |
|------|-------------|
| [examples/block-rm-rf.json](examples/block-rm-rf.json) | Deny `rm -rf` via `permissionDecision` |
| [examples/protect-env-files.json](examples/protect-env-files.json) | Block edits/writes to `.env` files |
| [examples/stop-checklist.json](examples/stop-checklist.json) | Continue the turn until checks pass (`decision: block`) |
| [examples/prompt-hook-stop.json](examples/prompt-hook-stop.json) | Model-judged completion check (`type: prompt`) |
| [examples/safe-context-injection.json](examples/safe-context-injection.json) | Inject context with injection-safe phrasing |
| [examples/auto-format.json](examples/auto-format.json) | Run a formatter after edits (`PostToolUse`) |
| [examples/auto-approve-exit-plan.json](examples/auto-approve-exit-plan.json) | Auto-approve `ExitPlanMode` (`PermissionRequest`) |
