---
name: opencode
license: MIT
description: >-
  Use when interacting with the OpenCode server via its HTTP API. Covers
  starting the server, creating sessions, sending prompts (sync and async),
  monitoring via SSE, collecting results, and cleanup. Also covers permission
  handling, agent routing, and minimal opencode.json configuration. Trigger
  when automating OpenCode from scripts, orchestrating multi-session workflows,
  planning OpenCode-based pipelines, or driving OpenCode headlessly from any
  agent.
compatibility: >-
  Requires opencode CLI (bun/npm install)
metadata:
  repo: https://github.com/nq-rdl/agent-skills
---

# OpenCode HTTP API Skill

A pure knowledge skill — no code, no dependencies. Teaches any agent how to drive OpenCode programmatically via its REST API at `http://localhost:4096`.

## API Endpoint Reference

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/global/health` | Health check |
| GET | `/event` | SSE event stream |
| GET | `/doc` | OpenAPI spec |
| POST | `/session` | Create session |
| GET | `/session/:id` | Get session details |
| GET | `/session/:id/message` | List messages |
| POST | `/session/:id/message` | Send prompt (sync — blocks until complete) |
| POST | `/session/:id/prompt_async` | Send prompt (async — returns 204 immediately) |
| POST | `/session/:id/abort` | Abort running session |
| DELETE | `/session/:id` | Delete session |
| POST | `/session/:id/permissions/:permID` | Respond to permission request |
| GET | `/agent` | List available agents |

---

## 1. Start the Server

```bash
opencode serve &
# Options:
#   --port 4096        (default)
#   --hostname 0.0.0.0 (default: localhost)
```

Or configure in `opencode.json`:

```json
{
  "server": {
    "port": 4096,
    "hostname": "0.0.0.0"
  }
}
```

## 2. Health Check

```bash
curl -sf http://localhost:4096/global/health
```

Returns 200 when the server is ready. Use this to gate any workflow.

## 3. Create a Session

```bash
SESSION_ID=$(curl -sf -X POST http://localhost:4096/session \
  -H "Content-Type: application/json" \
  -d '{
    "permission": {
      "rules": [
        {"toolName": "write", "action": "allow"},
        {"toolName": "edit", "action": "allow"},
        {"toolName": "read", "action": "allow"},
        {"toolName": "bash", "action": "allow"},
        {"toolName": "glob", "action": "allow"},
        {"toolName": "external_directory", "action": "allow"}
      ]
    }
  }' | jq -r '.id')
```

### Permission Rules

For headless (non-interactive) use, pre-approve the tools the agent will need. Each rule is a `{toolName, action}` pair:

| `action` | Meaning |
|----------|---------|
| `"allow"` | Auto-approve without prompting |
| `"deny"` | Block the tool entirely |
| `"ask"` | Prompt interactively (not useful headless) |

The `external_directory` tool name covers read/write access outside the project root — include it if the agent needs to work across directories.

### Optional: Model Override

Pass `"model"` at session creation to override the default:

```json
{
  "model": "openai/o3-mini",
  "permission": { "rules": [...] }
}
```

## 4. Send a Prompt

### Synchronous (blocks until complete)

```bash
RESPONSE=$(curl -sf -X POST "http://localhost:4096/session/$SESSION_ID/message" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Your prompt text here"
  }')
```

Returns the full message history including the assistant's response.

### Asynchronous (returns 204 immediately)

```bash
curl -sf -X POST "http://localhost:4096/session/$SESSION_ID/prompt_async" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Your prompt text here"
  }'
```

Use async when you want to monitor progress via SSE or dispatch multiple sessions in parallel.

### Agent Routing

Pass the `agent` field to target a named agent:

```json
{
  "content": "Implement the auth middleware",
  "agent": "developer"
}
```

If `agent` is omitted, the default agent handles the prompt. List available agents with:

```bash
curl -sf http://localhost:4096/agent | jq '.[]'
```

## 5. Monitor via SSE

```bash
curl -sf -N http://localhost:4096/event
```

The event stream emits Server-Sent Events. Key event types:

| Event | Meaning |
|-------|---------|
| `session.idle` | Session finished processing — results ready |
| `session.error` | Session encountered an error |
| `session.updated` | Session metadata changed (informational) |
| `message.updated` | New content streamed (for progress display) |

Filter by session ID in your event handler. Example in bash:

```bash
curl -sf -N http://localhost:4096/event | while IFS= read -r line; do
  case "$line" in
    data:*"${SESSION_ID}"*session.idle*)
      echo "Session finished"
      break
      ;;
    data:*"${SESSION_ID}"*session.error*)
      echo "Session errored"
      break
      ;;
  esac
done
```

## 6. Collect Results

```bash
MESSAGES=$(curl -sf "http://localhost:4096/session/$SESSION_ID/message")
```

Returns the full message array. Extract the final assistant message to get output:

```bash
echo "$MESSAGES" | jq '.[-1]'
```

Or get session details (includes metadata):

```bash
curl -sf "http://localhost:4096/session/$SESSION_ID" | jq '.'
```

## 7. Cleanup

```bash
curl -sf -X DELETE "http://localhost:4096/session/$SESSION_ID"
```

Delete sessions when done to free resources.

## 8. Abort a Running Session

```bash
curl -sf -X POST "http://localhost:4096/session/$SESSION_ID/abort"
```

Use when a session is hung or exceeds a timeout.

## 9. Respond to Permission Requests

If a session requests permission (e.g., tool approval), respond with:

```bash
curl -sf -X POST "http://localhost:4096/session/$SESSION_ID/permissions/$PERM_ID" \
  -H "Content-Type: application/json" \
  -d '{"action": "allow"}'
```

In headless workflows, pre-configure permission rules at session creation to avoid interactive prompts.

---

## Complete Workflow Example

This is the proven pattern for dispatching work to an OpenCode agent and collecting results:

```bash
#!/bin/bash
set -euo pipefail

BASE_URL="http://localhost:4096"
AGENT="developer"
PROMPT="Implement JWT validation middleware in src/middleware/auth.ts"

# 1. Health check
curl -sf "$BASE_URL/global/health" > /dev/null 2>&1 || {
  echo "ERROR: OpenCode server not running at $BASE_URL"
  exit 1
}

# 2. Create session with auto-approved permissions
SESSION_ID=$(curl -sf -X POST "$BASE_URL/session" \
  -H "Content-Type: application/json" \
  -d '{
    "permission": {
      "rules": [
        {"toolName": "write", "action": "allow"},
        {"toolName": "edit", "action": "allow"},
        {"toolName": "read", "action": "allow"},
        {"toolName": "bash", "action": "allow"},
        {"toolName": "glob", "action": "allow"},
        {"toolName": "external_directory", "action": "allow"}
      ]
    }
  }' | jq -r '.id')

echo "Session created: $SESSION_ID"

# 3. Send prompt (sync — blocks until done)
RESPONSE=$(curl -sf -X POST "$BASE_URL/session/$SESSION_ID/message" \
  -H "Content-Type: application/json" \
  -d "$(jq -n --arg content "$PROMPT" --arg agent "$AGENT" \
    '{content: $content, agent: $agent}')")

echo "Response received"

# 4. Extract result
echo "$RESPONSE" | jq '.[-1].content // .[-1]'

# 5. Cleanup
curl -sf -X DELETE "$BASE_URL/session/$SESSION_ID"
echo "Session deleted"
```

### Async Variant (parallel dispatch)

```bash
# Dispatch multiple sessions without blocking
for TASK in "task 1" "task 2" "task 3"; do
  SESSION_ID=$(curl -sf -X POST "$BASE_URL/session" \
    -H "Content-Type: application/json" \
    -d '{"permission":{"rules":[{"toolName":"write","action":"allow"},{"toolName":"read","action":"allow"},{"toolName":"bash","action":"allow"},{"toolName":"glob","action":"allow"},{"toolName":"external_directory","action":"allow"}]}}' \
    | jq -r '.id')

  curl -sf -X POST "$BASE_URL/session/$SESSION_ID/prompt_async" \
    -H "Content-Type: application/json" \
    -d "$(jq -n --arg c "$TASK" '{content: $c, agent: "developer"}')"

  echo "$SESSION_ID"  # collect IDs for monitoring
done

# Then monitor via SSE until all sessions reach idle
```

---

## Configuration: opencode.json

Minimal project configuration for headless use:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "model": "anthropic/claude-sonnet-4-5",
  "permission": {
    "bash": { "*": "allow" },
    "write": "allow",
    "edit": "allow"
  },
  "server": {
    "port": 4096
  }
}
```

### Model Format

Models use `provider/model-id` format:

- `anthropic/claude-sonnet-4-5`
- `anthropic/claude-opus-4-5`
- `openai/o3-mini`
- `google/gemini-2.5-pro`

### Provider Auth

Set environment variables for your chosen provider:

```bash
export ANTHROPIC_API_KEY=sk-...
export OPENAI_API_KEY=sk-...
```

Or configure in `opencode.json`:

```json
{
  "provider": {
    "openai": {
      "apiKey": "{env:OPENAI_API_KEY}"
    }
  }
}
```

---

## Troubleshooting

### Common Issues

| Issue | Symptom | Fix |
|-------|---------|-----|
| **Stale OAuth token** | `prompt_async` returns 204 but session never produces AI responses; server logs show `ProviderModelNotFoundError` | Restart the server after re-authenticating (see restart snippet below) |
| **Server not reachable** | `GET /global/health` fails or times out | Confirm `opencode serve` is running; check `--port` matches your `BASE_URL` |
| **Session stuck / hung** | No `session.idle` or `session.error` SSE events after sending a prompt | Abort the session with `POST /session/:id/abort`; check for unresolved permission prompts blocking the worker |

### Server Restart (Token Refresh)

The server loads the OAuth token into memory at startup and does **not** hot-reload it. If you re-authenticate (e.g., `opencode auth` or TUI `/connect`) while the server is running, the server still holds the expired token. Restart it:

```bash
kill $(pgrep -f 'opencode serve')
sleep 2
opencode serve --port 4096 &
# Wait for healthy
until curl -sf http://localhost:4096/global/health > /dev/null 2>&1; do sleep 1; done
```

### Diagnostic Checklist

When a session silently fails, walk through these four checks in order:

1. **Health** — `curl -sf http://localhost:4096/global/health` → must return 200
2. **Logs** — inspect server stderr for `ProviderModelNotFoundError` or `worker shutting down`
3. **Token freshness** — check `~/.config/opencode/auth.json` expiry vs. server start time; restart if token was refreshed after server started
4. **Session state** — `GET /session/:id` → look for pending permission requests or error status

---

## Extension Authoring

For building OpenCode tools, plugins, agents, or MCP server integrations, see the extension docs in `references/`:

- `custom-tools.rst` — Custom tool authoring with `@opencode-ai/plugin`
- `plugins.rst` — Plugin bundling and lifecycle hooks
- `agents.rst` — Agent configuration (markdown + JSON)
- `mcp-servers.rst` — MCP server setup
- `opencode-json.rst` — Complete `opencode.json` schema reference
