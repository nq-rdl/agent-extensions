# Gemini CLI Headless Mode Reference

Headless mode provides a programmatic, non-interactive interface to Gemini CLI. It returns structured output — JSON or streaming JSONL — without requiring a terminal UI.

## Triggering Headless Mode

Headless mode activates when either condition is met:
- The `-p` / `--prompt` flag is provided
- The process runs in a non-TTY environment (e.g., piped stdin/stdout)

```bash
gemini -p "Summarize the key risks in this architecture"
```

---

## Output Formats

Control output format with `--output-format` (alias `-o`):

| Format | Flag | Description |
|--------|------|-------------|
| Text | `--output-format text` | Plain text response (default for interactive) |
| JSON | `--output-format json` | Single JSON object with response + stats |
| Streaming JSON | `--output-format stream-json` | Newline-delimited JSON (JSONL) event stream |

### JSON format (`--output-format json`)

Returns a single JSON object after the full response completes:

```json
{
  "response": "The model's final answer text",
  "stats": {
    "totalTokens": 1234,
    "latencyMs": 5432
  },
  "error": null
}
```

Use this for simple one-shot calls where you only need the final response.

### Streaming JSON format (`--output-format stream-json`)

Returns a stream of newline-delimited JSON objects (JSONL). Each line is a self-contained JSON event.

**Why prefer `stream-json` over `json`**: The `init` event carries the `sessionId` needed for `--resume` (multi-turn sessions). Use `stream-json` when you need the session ID.

---

## JSONL Event Types (stream-json)

### `init` — Session initialization

Emitted immediately when the session starts. Contains metadata for multi-turn support.

```json
{
  "type": "init",
  "sessionId": "abc123-def456",
  "model": "gemini-2.5-pro"
}
```

**Critical**: Save `sessionId` if you need `--resume` for follow-up prompts.

### `message` — Content chunks

Streamed as the model generates output. Each chunk is a partial or complete message.

```json
{
  "type": "message",
  "role": "assistant",
  "content": "Here are the key risks..."
}
```

For user messages (echoed back):
```json
{
  "type": "message",
  "role": "user",
  "content": "Summarize the key risks..."
}
```

### `tool_use` — Tool invocation request

Emitted when Gemini decides to use a tool (web search, file read, shell command, etc.).

```json
{
  "type": "tool_use",
  "tool": "web_search",
  "args": {
    "query": "transformer attention complexity papers 2025"
  }
}
```

### `tool_result` — Tool output

Emitted after a tool call completes with its result.

```json
{
  "type": "tool_result",
  "tool": "web_search",
  "result": {
    "snippets": ["..."],
    "urls": ["https://..."]
  }
}
```

### `error` — Non-fatal warnings

Emitted for recoverable issues (rate limits, retried requests, etc.). Does not stop execution.

```json
{
  "type": "error",
  "message": "Rate limit hit, retrying in 2s",
  "code": "RATE_LIMIT"
}
```

### `result` — Final outcome

The last event emitted. Contains the complete response and aggregated statistics.

```json
{
  "type": "result",
  "response": "Full final answer text...",
  "stats": {
    "totalTokens": 2456,
    "inputTokens": 312,
    "outputTokens": 2144,
    "latencyMs": 8934,
    "modelBreakdown": {
      "gemini-2.5-pro": {
        "inputTokens": 312,
        "outputTokens": 2144
      }
    }
  }
}
```

---

## Exit Codes

| Code | Meaning | Action |
|------|---------|--------|
| `0` | Success | Parse response normally |
| `1` | General error or API failure | Check stderr for details |
| `42` | Input error (invalid prompt or args) | Fix the command arguments |
| `53` | Turn limit exceeded | Use `--resume` or break into smaller tasks |

---

## Session Continuity (`--resume`)

Each session has a `sessionId` from the `init` event. Use `--resume <sessionId>` to continue a conversation:

```bash
# First turn
gemini -p "Explain transformer attention" --output-format stream-json
# → parse sessionId from init event: "session-abc123"

# Continue the session
gemini -p "Compare it to linear attention" --resume session-abc123 --output-format stream-json
```

Sessions persist on disk (Gemini CLI manages history). Use `--resume` to build multi-turn workflows without re-sending prior context.

---

## Parsing JSONL Output

Shell example using `jq`:

```bash
# Run and capture stream-json output
output=$(gemini -p "your prompt" --output-format stream-json)

# Extract session ID
session_id=$(echo "$output" | jq -r 'select(.type == "init") | .sessionId' | head -1)

# Extract final response
response=$(echo "$output" | jq -r 'select(.type == "result") | .response' | head -1)

echo "Session: $session_id"
echo "Response: $response"
```

TypeScript/Node.js example:

```typescript
import { spawn } from 'child_process';

async function runGemini(prompt: string): Promise<{ response: string; sessionId: string }> {
  const proc = spawn('gemini', ['-p', prompt, '--output-format', 'stream-json', '--approval-mode', 'yolo', '--sandbox']);

  let sessionId = '';
  let response = '';

  for await (const line of proc.stdout) {
    const event = JSON.parse(line.toString().trim());
    if (event.type === 'init') sessionId = event.sessionId;
    if (event.type === 'result') response = event.response;
  }

  return { response, sessionId };
}
```
