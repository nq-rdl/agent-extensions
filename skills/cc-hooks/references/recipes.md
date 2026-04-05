# Hook Recipes

Common Claude Code hook patterns with full implementations.

---

## 1. Block Destructive Shell Commands

Block `rm -rf /`, force push, `dd`, and similar dangerous operations.

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash -c 'input=$(cat); cmd=$(echo \"$input\" | jq -r \".tool_input.command // empty\"); if echo \"$cmd\" | grep -qE \"rm\\s+-rf\\s+(/|~)|git\\s+push\\s+.*--force|dd\\s+if=.*of=/dev\"; then echo \"{\\\"decision\\\":\\\"block\\\",\\\"reason\\\":\\\"Destructive command blocked\\\"}\"; fi'",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

---

## 2. Protect Sensitive Files

Prevent edits to `.env`, credentials, private keys, and lock files.

### Script — `protect-files.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path // .tool_input.path // empty')

if echo "$file_path" | grep -qE '\.(env|pem|key)$|credentials|secrets|pixi\.lock$'; then
    echo "{\"decision\":\"block\",\"reason\":\"Protected file: $file_path\"}"
    exit 0
fi
```

### Config

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit",
        "hooks": [
          {"type": "command", "command": "bash protect-files.sh", "timeout": 10}
        ]
      },
      {
        "matcher": "Write",
        "hooks": [
          {"type": "command", "command": "bash protect-files.sh", "timeout": 10}
        ]
      }
    ]
  }
}
```

---

## 3. Completion Checklist

Remind the agent to run tests and lint before stopping.

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

---

## 4. Session Start Banner

Inject project context when a session begins.

### Script — `session-banner.sh`

```bash
#!/usr/bin/env bash
branch=$(git branch --show-current 2>/dev/null || echo "unknown")
last_commit=$(git log -1 --oneline 2>/dev/null || echo "no commits")
echo "Project branch: $branch | Last commit: $last_commit"
```

### Config

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash session-banner.sh",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

---

## 5. Notification Routing

Forward agent notifications to a webhook (Slack, Discord, etc.).

### Script — `notify-webhook.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
input=$(cat)
message=$(echo "$input" | jq -r '.message // "Agent notification"')

curl -s -X POST "${WEBHOOK_URL}" \
  -H 'Content-Type: application/json' \
  -d "{\"text\": \"$message\"}" >&2

echo '{}'
```

Set `WEBHOOK_URL` in your environment.

### Config

```json
{
  "hooks": {
    "Notification": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash notify-webhook.sh",
            "timeout": 15
          }
        ]
      }
    ]
  }
}
```
