---
name: pi-rpc
license: MIT
description: >-
  Pi.dev ConnectRPC service — spawn and manage pi.dev coding agent sessions via
  HTTP/JSON endpoints. Use when dispatching coding tasks to pi.dev, managing
  parallel agent sessions, running multi-turn pi.dev conversations, or building
  orchestration pipelines that need full session lifecycle control (create,
  prompt, stream events, abort, delete).
compatibility: >-
  Requires Go 1.24+, pi CLI (pi.dev binary in PATH), buf CLI (for protobuf
  regeneration only)
metadata:
  repo: https://github.com/nq-rdl/agent-skills
---

# Pi.dev RPC Skill

## What Is This Skill?

`pi-rpc` wraps `pi --mode rpc` subprocesses in a Go ConnectRPC HTTP/JSON service. Once running, agents interact with pi.dev coding sessions using standard `curl` POST requests — no gRPC client required. The Connect protocol is wire-compatible with gRPC but also serves plain HTTP/JSON.

## When to Use pi-rpc

| Scenario | Use pi-rpc |
|----------|-----------|
| Multi-turn coding sessions | Yes — maintains subprocess state |
| Parallel agent dispatch | Yes — each session is an independent subprocess |
| Event streaming (tool calls, messages) | Yes — `StreamEvents` RPC |
| One-shot query, no session needed | No — use `pi --mode json "prompt"` directly |
| In-process Node.js embedding | No — use `@mariozechner/pi-coding-agent` SDK |

## Build and Run

You can start the server in the background using the provided wrapper script. It will automatically build the server if needed and wait until it's healthy.

```bash
./skills/pi-rpc/scripts/start.sh
```

To configure default provider/model via environment variables:

```bash
PI_DEFAULT_PROVIDER=anthropic PI_DEFAULT_MODEL=claude-sonnet-4 ./skills/pi-rpc/scripts/start.sh
```

Alternatively, manage it manually:

```bash
cd skills/pi-rpc/scripts
make generate   # Regenerate protobuf code (requires buf CLI)
make build      # Build ./bin/pi-server and ./bin/pi-cli
make test       # Run all tests
make serve      # Start on localhost:4097 (PI_SERVER_PORT to override)
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PI_SERVER_PORT` | `4097` | Listening port for the server |
| `PI_SERVER_URL` | `http://localhost:4097` | Server URL used by pi-cli |
| `PI_DEFAULT_PROVIDER` | `openai` | Fallback provider when `Create` omits it |
| `PI_DEFAULT_MODEL` | `gpt-4.1` | Fallback model when `Create` omits it |
| `PI_BINARY` | `pi` | Path to the pi binary |

## Health Check

```bash
PI_SERVER="${PI_SERVER_URL:-http://localhost:4097}"
curl -sf \
  -H 'Content-Type: application/json' \
  -d '{}' \
  "$PI_SERVER/pirpc.v1.SessionService/List" > /dev/null && echo "ready"
```

If not running, start with `./skills/pi-rpc/scripts/start.sh`.

## Provider and Model Selection

If the user specifies a provider and model, pass them to the `Create` endpoint.
If omitted, the server applies defaults from `PI_DEFAULT_PROVIDER` / `PI_DEFAULT_MODEL` (see Environment Variables above; hardcoded fallbacks: `openai` / `gpt-4.1`).

If explicitly specifying a provider/model pair, validate before creating sessions:

```bash
pi --provider <PROVIDER> --model <MODEL> --mode json "Reply with OK."
```

If this fails, fix the model ID or provider auth before calling `Create`.

## Endpoint Reference

All endpoints accept `Content-Type: application/json` POST requests.

| Endpoint | Purpose | Key Fields |
|----------|---------|------------|
| `pirpc.v1.SessionService/Create` | Spawn a pi.dev subprocess | `provider` (optional), `model` (optional), `cwd`, `thinking_level` |
| `pirpc.v1.SessionService/Prompt` | Send prompt, wait for completion | `session_id`, `message` |
| `pirpc.v1.SessionService/PromptAsync` | Send prompt, return immediately | `session_id`, `message` |
| `pirpc.v1.SessionService/StreamEvents` | Server-streaming events | `session_id`, optional `filter` |
| `pirpc.v1.SessionService/GetMessages` | Retrieve conversation messages | `session_id` |
| `pirpc.v1.SessionService/GetState` | Check session state + metadata | `session_id` |
| `pirpc.v1.SessionService/Abort` | Cancel running operation | `session_id` |
| `pirpc.v1.SessionService/Delete` | Kill subprocess, free resources | `session_id` |
| `pirpc.v1.SessionService/List` | List all active sessions | — |

`Create` returns `{"sessionId":"abc-123","state":"SESSION_STATE_IDLE"}`. Pass `sessionId` to all subsequent calls.

## Session Lifecycle

```
Create → SESSION_STATE_IDLE
  → Prompt/PromptAsync → SESSION_STATE_RUNNING
    → (agent_end) → SESSION_STATE_IDLE
    → (error / timeout) → SESSION_STATE_ERROR
  → Delete → SESSION_STATE_TERMINATED
```

Sessions are killed automatically after 60 seconds of inactivity while in `RUNNING` state.

## Dispatch Examples

```bash
PI_SERVER="${PI_SERVER_URL:-http://localhost:4097}"

# Create a session (with explicit provider/model)
SESSION=$(curl -sf \
  -H 'Content-Type: application/json' \
  -d '{"provider":"<PROVIDER>","model":"<MODEL>","cwd":"/home/user/project"}' \
  "$PI_SERVER/pirpc.v1.SessionService/Create" | jq -r .sessionId)

# Alternatively, create a session using defaults
SESSION=$(curl -sf \
  -H 'Content-Type: application/json' \
  -d '{"cwd":"/home/user/project"}' \
  "$PI_SERVER/pirpc.v1.SessionService/Create" | jq -r .sessionId)

# Send a prompt (synchronous — waits up to 5 minutes)
curl -sf \
  -H 'Content-Type: application/json' \
  -d "{\"sessionId\":\"$SESSION\",\"message\":\"Create a hello world program\"}" \
  "$PI_SERVER/pirpc.v1.SessionService/Prompt"

# Get conversation messages
curl -sf \
  -H 'Content-Type: application/json' \
  -d "{\"sessionId\":\"$SESSION\"}" \
  "$PI_SERVER/pirpc.v1.SessionService/GetMessages"

# Delete when done
curl -sf \
  -H 'Content-Type: application/json' \
  -d "{\"sessionId\":\"$SESSION\"}" \
  "$PI_SERVER/pirpc.v1.SessionService/Delete"
```

## Event Types

| Event | Description |
|-------|-------------|
| `agent_start` | Agent begins processing |
| `agent_end` | Agent completes processing |
| `turn_start` / `turn_end` | Conversation turn boundaries |
| `message_update` | Incremental message content |
| `tool_execution_start` / `tool_execution_end` | Tool invocation lifecycle |
| `compaction` | Context window compacted |
| `retry` | Retrying after transient error |
| `error` | Error occurred |

## Reference Docs

- `references/rpc.md` — Full protocol reference: session lifecycle, all dispatch examples, event types, model mapping, health check

## Protobuf Contract

Full service definition: `scripts/proto/pirpc/v1/session.proto`
