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

```bash
cd skills/pi-rpc/scripts

make generate   # Regenerate protobuf code (requires buf CLI)
make build      # Build ./bin/pi-server
make test       # Run all tests
make serve      # Start on localhost:4097 (PI_SERVER_PORT to override)
```

## Health Check

```bash
PI_SERVER="${PI_SERVER_URL:-http://localhost:4097}"
curl -sf \
  -H 'Content-Type: application/json' \
  -d '{}' \
  "$PI_SERVER/pirpc.v1.SessionService/List" > /dev/null && echo "ready"
```

If not running, start with `make serve` from `skills/pi-rpc/scripts/`.

## Provider and Model Selection

**If the user has not specified a provider and model, ask them.** Do not assume a default. Use `pi --list-models` to show available options.

Once known, validate the provider/model pair before creating sessions:

```bash
pi --provider <PROVIDER> --model <MODEL> --mode json "Reply with OK."
```

If this fails, fix the model ID or provider auth before calling `Create`.

## Endpoint Reference

All endpoints accept `Content-Type: application/json` POST requests.

| Endpoint | Purpose | Key Fields |
|----------|---------|------------|
| `pirpc.v1.SessionService/Create` | Spawn a pi.dev subprocess | `provider`, `model`, `cwd`, `thinking_level` |
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

# Create a session
SESSION=$(curl -sf \
  -H 'Content-Type: application/json' \
  -d '{"provider":"<PROVIDER>","model":"<MODEL>","cwd":"/home/user/project"}' \
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
