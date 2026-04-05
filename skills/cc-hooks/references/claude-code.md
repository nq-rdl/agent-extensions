# Claude Code Hooks Reference

## Config Location

Hooks are defined under the `"hooks"` key in JSON settings files. Three levels, merged at runtime (most specific wins):

| Level | File | Scope |
|-------|------|-------|
| Global | `~/.claude/settings.json` | All projects for this user |
| Project (shared) | `.claude/settings.json` | This project, committed to git |
| Project (local) | `.claude/settings.local.json` | This project, gitignored |

---

## Event Reference

### Session Lifecycle
| Event | When it fires |
|-------|--------------|
| `SessionStart` | Session begins |
| `SessionEnd` | Session ends |

### Tool Execution
| Event | When it fires |
|-------|--------------|
| `PreToolUse` | Before a tool executes (can block) |
| `PostToolUse` | After a tool completes |

### Agent Control
| Event | When it fires |
|-------|--------------|
| `Stop` | Agent wants to stop responding |
| `SubagentStop` | A subagent completes |

### User Input
| Event | When it fires |
|-------|--------------|
| `UserPromptSubmit` | User sends a message |

### Context Management
| Event | When it fires |
|-------|--------------|
| `PreCompact` | Before context window compaction |

### Notifications
| Event | When it fires |
|-------|--------------|
| `Notification` | A notification fires |

Tool events (`PreToolUse`, `PostToolUse`) use **matchers** to target specific tools: `Bash`, `Edit`, `Write`, `Read`, `Glob`, `Grep`, `Agent`, `WebFetch`, etc. Omit the matcher to match all tools.

---

## Configuration Schema

```json
{
  "hooks": {
    "<EventName>": [
      {
        "matcher": "ToolName",
        "hooks": [
          {
            "type": "command",
            "command": "bash /path/to/script.sh",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

### Fields

- **matcher** (optional): Tool name filter. Only meaningful for `PreToolUse` and `PostToolUse`. Omit to match all tools.
- **hooks** (required): Array of hook definitions.
- **type** (required): `"command"`, `"http"`, `"prompt"`, or `"agent"` — see Hook Types below.
- **command** (for type `"command"`): Shell command to execute. Receives event context via stdin as JSON.
- **timeout** (optional): Seconds before the hook is killed. Default: 60, max: 600.

---

## Hook Types

| Type | What it does | When to use |
|------|-------------|-------------|
| `command` | Runs a shell command, passes stdin JSON, reads stdout | Most hooks — safety checks, scripts, notifications |
| `http` | Sends HTTP POST to a URL with event JSON | Remote webhooks, logging services |
| `prompt` | Injects a static prompt string into context | Simple reminders, checklists |
| `agent` | Runs a Claude agent prompt | Complex validation needing LLM reasoning |

Most hooks use `"command"`. Use `"prompt"` for simple context injection without a script.

---

## Stdin JSON Shapes

Each hook receives event context on stdin. Key shapes:

**PreToolUse (Bash)**:
```json
{
  "tool_name": "Bash",
  "tool_input": {
    "command": "rm -rf /tmp/data",
    "description": "Delete temp data"
  }
}
```

**PreToolUse (Edit/Write)**:
```json
{
  "tool_name": "Write",
  "tool_input": {
    "file_path": "/path/to/file.py",
    "content": "..."
  }
}
```

**Stop**:
```json
{
  "stop_reason": "end_turn"
}
```

**UserPromptSubmit**:
```json
{
  "prompt": "the user's message text"
}
```

**Notification**:
```json
{
  "message": "Claude wants to run: rm -rf /tmp/data",
  "type": "tool_permission"
}
```

---

## Decision Output

Hooks communicate decisions via stdout JSON:

```json
{"decision": "block", "reason": "Dangerous command blocked by safety hook"}
```

| Decision | Effect |
|----------|--------|
| `"allow"` | Permit the action (default if no output) |
| `"block"` | Prevent the action; show reason to agent |
| `"approve"` | Auto-approve without user confirmation prompt |

For non-blocking events (`PostToolUse`, `SessionStart`, etc.), any stdout is injected as context into the conversation.

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success — stdout is processed normally |
| 2 | Blocking error — action is blocked, stderr shown |
| Other | Non-blocking error — warning shown, action proceeds |

---

## Examples

### Block destructive commands

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash -c 'input=$(cat); cmd=$(echo \"$input\" | jq -r \".tool_input.command // empty\"); if echo \"$cmd\" | grep -qE \"rm\\s+-rf\\s+(/|~)|git\\s+push\\s+.*--force|dd\\s+if=\"; then echo \"{\\\"decision\\\":\\\"block\\\",\\\"reason\\\":\\\"Destructive command blocked\\\"}\"; fi'",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

### Protect sensitive files

```python
#!/usr/bin/env python3
"""protect-files.py — Block edits to protected files."""
import json, sys, re

data = json.load(sys.stdin)
tool = data.get("tool_name", "")
path = data.get("tool_input", {}).get("file_path", "")

PROTECTED = [r"\.env$", r"credentials", r"\.pem$", r"\.key$", r"pixi\.lock$"]

if tool in ("Edit", "Write"):
    for pattern in PROTECTED:
        if re.search(pattern, path):
            print(json.dumps({
                "decision": "block",
                "reason": f"Blocked: {path} is a protected file"
            }))
            sys.exit(0)
```

Config (add an entry for both `Edit` and `Write` since the script guards both):
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit",
        "hooks": [{"type": "command", "command": "python3 protect-files.py", "timeout": 10}]
      },
      {
        "matcher": "Write",
        "hooks": [{"type": "command", "command": "python3 protect-files.py", "timeout": 10}]
      }
    ]
  }
}
```

### Completion checklist (Stop hook)

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "prompt",
            "prompt": "Before stopping: 1) Did you run tests? 2) Did you run the linter? 3) Did you verify your changes work?"
          }
        ]
      }
    ]
  }
}
```

### Context injection (SessionStart)

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "echo 'Project: MyApp | Branch: '$(git branch --show-current)' | Last commit: '$(git log -1 --oneline)",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

---

## Curated Configs

Ready-to-deploy hook configurations are available in `hooks/` in this repository. Copy or merge them into your project's `.claude/settings.local.json`.

```bash
# Copy a config
cp hooks/<config>.json .claude/settings.local.json

# Merge into existing settings
jq -s '.[0] * .[1]' .claude/settings.local.json hooks/<config>.json > /tmp/merged.json \
  && mv /tmp/merged.json .claude/settings.local.json
```
