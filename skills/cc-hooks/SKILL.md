---
name: cc-hooks
license: MIT
description: >-
  Create, manage, and debug Claude Code hooks — event-driven scripts that run
  before or after agent actions. Use when the user asks about hooks,
  guardrails, pre/post tool execution, safety rules, command blocking, context
  injection, or completion checklists for Claude Code. Also trigger on mentions
  of PreToolUse, PostToolUse, SessionStart, Stop, settings.json hooks, or when
  the user wants to prevent destructive commands, protect files, or add
  automated checks to their Claude Code workflow.
metadata:
  repo: https://github.com/nq-rdl/agent-skills
---

# Claude Code Hooks

Event-driven scripts that run before or after Claude Code agent actions — enabling guardrails, automation, and custom workflows without modifying the agent's core behavior.

---

## Hook Basics

Hooks are defined in Claude Code's `settings.json` files under the `"hooks"` key. Three levels, merged at runtime (most specific wins):

| Level | File | Scope |
|-------|------|-------|
| Global | `~/.claude/settings.json` | All projects for this user |
| Project (shared) | `.claude/settings.json` | This project, committed to git |
| Project (local) | `.claude/settings.local.json` | This project, gitignored |

## Events

| Event | When it fires | Can block? |
|-------|--------------|------------|
| `SessionStart` | Session begins | No |
| `SessionEnd` | Session ends | No |
| `PreToolUse` | Before a tool executes | Yes — emit `{"decision":"block","reason":"..."}` |
| `PostToolUse` | After a tool completes | No — but can inject context |
| `Stop` | Agent wants to stop | Yes — emit `{"reason":"..."}` to continue |
| `SubagentStop` | Subagent wants to stop | Yes — same as Stop |
| `Notification` | Agent sends a notification | No |
| `UserPromptSubmit` | User submits a prompt | No — but can inject context |
| `PostToolUsePreResponse` | After tool completes, before agent responds | No — can inject context |

## Hook Structure

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash -c 'your script here'",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

**Key fields:**
- `matcher` — optional tool name filter (e.g., `"Bash"`, `"Write"`, `"Edit"`). Without it, fires for every tool.
- `type` — always `"command"` (shell command)
- `command` — receives event context as JSON on stdin, emits decisions on stdout
- `timeout` — seconds before the hook is killed (action proceeds as if allowed)

## I/O Contract

Hooks receive JSON on **stdin** with the event context:

```json
{
  "session_id": "...",
  "tool_name": "Bash",
  "tool_input": {
    "command": "rm -rf /"
  }
}
```

Hooks emit JSON on **stdout** to make decisions:

| Hook type | Block output | Context injection |
|-----------|-------------|-------------------|
| `PreToolUse` | `{"decision":"block","reason":"..."}` | `{"context":"reminder text"}` |
| `Stop` | `{"reason":"checklist: tests passing?"}` | — |
| `PostToolUse` | N/A | `{"context":"additional info"}` |
| `UserPromptSubmit` | N/A | Plain text or JSON context |

**stderr** is ignored — use it for debug logging.

## Common Patterns

### 1. Safety guardrails
Block destructive shell commands (`rm -rf /`, force push, `dd`). See `examples/block-rm-rf.json`.

### 2. Protected files
Prevent edits to `.env`, credentials, lock files. See `examples/protect-env-files.json`.

### 3. Completion checklist
Require tests/lint to pass before the agent stops. See `examples/stop-checklist.json`.

### 4. Context injection
Inject project context or reminders at session start or prompt submit.

### 5. Notification routing
Forward agent notifications to webhooks, Slack, or other services.

---

## Reference Files

| File | Contents |
|------|----------|
| [references/claude-code.md](references/claude-code.md) | Complete Claude Code hook reference — all 9 events, config schema, detailed examples |
| [references/recipes.md](references/recipes.md) | Common hook patterns with full implementations |
| [references/debugging.md](references/debugging.md) | Debugging checklist for when hooks aren't working |

## Example Files

| File | What it does |
|------|-------------|
| [examples/block-rm-rf.json](examples/block-rm-rf.json) | Block `rm -rf` commands |
| [examples/protect-env-files.json](examples/protect-env-files.json) | Prevent writing to `.env` files |
| [examples/stop-checklist.json](examples/stop-checklist.json) | Inject completion checklist before stopping |
