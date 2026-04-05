---
name: gemini-cli
license: MIT
description: >-
  Gemini CLI headless dispatch — spawn headless Gemini CLI processes and give
  them jobs. Use when you need to offload web search, parallel research, code
  review, or file analysis to a Gemini agent. Use this skill proactively whenever
  a task would benefit from Gemini's built-in tools (web search, file management),
  when you want to run a task in parallel without consuming your own context
  window, or when the user asks to 'use Gemini', 'search the web with Gemini',
  'dispatch to Gemini', or 'ask Gemini to...'. Also triggers when building
  automation pipelines that batch-process files through an LLM.
metadata:
  repo: https://github.com/nq-rdl/agent-skills
---

# Gemini CLI Skill

## What Is This Skill?

Gemini CLI headless mode lets you spawn Gemini CLI as a subprocess and give it a job. The result comes back as structured JSON. Two modes are available:

- **Headless (one-shot):** Fire a prompt, get a response. Use for single tasks, parallel dispatch, web search, or any job that doesn't need memory of prior turns.
- **ACP (persistent sessions):** Start a `gemini --acp` subprocess that stays alive and speaks JSON-RPC 2.0. Use for multi-turn Q&A, interactive supervisors, or sequential pipelines where Gemini needs to remember prior context.

## When to Dispatch to Gemini

| Situation | Mode | Why |
|-----------|------|-----|
| Web search needed | Headless | Gemini's built-in search tool, no extra setup |
| Parallel research (multiple independent questions) | Headless (concurrent) | Run multiple processes without blocking |
| Large file review / code audit | Headless | Offloads context; Gemini handles its own window |
| Multi-turn Q&A where prior context matters | ACP | Persistent session with full memory |
| Quick one-liner computation | ❌ Skip | Overhead not worth it |
| Large output task (PDF→JSON, bulk extraction) | Headless + redirect | Keeps caller context clean |
| Task requires your project's codebase access | ❌ Skip | Gemini runs headless with limited cwd access |
| Sensitive credentials / secrets in prompt | ❌ Skip | Don't pass secrets to subprocess |

---

## Headless Mode (One-Shot)

Headless mode activates when `--prompt` is provided. Gemini runs, returns a response, and exits.

### Basic invocation

```bash
gemini --prompt "Summarize the key risks in this architecture" \
  --output-format json \
  --approval-mode yolo
```

`--approval-mode yolo` is **required** for headless — without it, Gemini blocks waiting for interactive confirmation that can never arrive.

### Output format

Use `--output-format json` for a single JSON object:

```json
{
  "response": "The model's final answer text",
  "session_id": "abc123-def456",
  "stats": { ... }
}
```

Use `--output-format stream-json` if you need the `session_id` for multi-turn (the `init` event carries it):

```jsonl
{"type":"init","sessionId":"abc123-def456","model":"gemini-3-flash-preview"}
{"type":"message","role":"assistant","content":"..."}
{"type":"result","response":"Full answer","stats":{...}}
```

### Piping context via stdin

```bash
git diff HEAD~1 | gemini --prompt "Review this diff. Focus on security issues." \
  --approval-mode yolo --output-format json
```

### Multi-turn via `--resume`

Save the `session_id` from a previous call and continue the conversation:

```bash
# First turn — capture session ID
OUTPUT=$(gemini --prompt "Explain transformer attention" \
  --output-format stream-json --approval-mode yolo)
SESSION_ID=$(echo "$OUTPUT" | jq -r 'select(.type=="init") | .sessionId' | head -1)

# Continue the session
gemini --prompt "Compare to linear attention" \
  --resume "$SESSION_ID" \
  --output-format json --approval-mode yolo
```

### System context injection

Write a temporary `GEMINI.md` and pass it via `--include-directories`:

```bash
mkdir -p /tmp/gemini-ctx
cat > /tmp/gemini-ctx/GEMINI.md << 'EOF'
You are a research assistant. Return results as a JSON array with fields:
title, authors, year, summary.
EOF

gemini --prompt "Find papers on MoE architectures" \
  --include-directories /tmp/gemini-ctx \
  --approval-mode yolo --output-format json
```

---

## ACP Mode (Persistent Sessions)

ACP (Agent Communication Protocol) starts `gemini --acp`, a long-lived subprocess that speaks JSON-RPC 2.0 over stdin/stdout. Each named session preserves full conversation context across calls.

### Starting an ACP session

```bash
gemini --acp --model gemini-3-flash-preview --yolo
```

The subprocess then expects a JSON-RPC handshake:

```json
// 1. Initialize
→ {"jsonrpc":"2.0","id":1,"method":"initialize","params":{"clientCapabilities":{}}}
← {"jsonrpc":"2.0","id":1,"result":{...}}

// 2. Create session
→ {"jsonrpc":"2.0","id":2,"method":"session/new","params":{"cwd":"/path/to/project"}}
← {"jsonrpc":"2.0","id":2,"result":{"sessionId":"abc123"}}

// 3. Send prompt
→ {"jsonrpc":"2.0","id":3,"method":"session/prompt","params":{"sessionId":"abc123","prompt":"Review this schema."}}
// Notifications arrive (streamed text chunks):
← {"jsonrpc":"2.0","method":"session/update","params":{"update":{"text":"The schema..."}}}
// Final response:
← {"jsonrpc":"2.0","id":3,"result":{"stopReason":"end_turn","usage":{...}}}
```

Accumulate `session/update` notification text chunks to reconstruct the full answer.

### Key ACP behaviors

- **Lazy init**: spawn the subprocess once, reuse for all turns
- **Named sessions**: run multiple concurrent sessions (e.g. `"supervisor"` on quality model, `"checker"` on fast)
- **Model + system context locked on first call**: set them when creating the session, not per-prompt
- **Turn counter**: track conversation depth to know when context is getting long
- **Graceful shutdown**: send `SIGTERM` to the subprocess when done

---

## Headless vs ACP Decision Guide

| Pattern | Mode | Why |
|---------|------|-----|
| Single question | Headless | No session overhead |
| Multi-turn Q&A with memory | ACP | Full context preserved |
| Interactive supervisor | ACP | Persistent persona across checks |
| Parallel independent tasks | Headless (concurrent) | No shared context needed |
| Sequential pipeline with feedback | ACP | Accumulates context per step |
| One-time large output | Headless + stdout redirect | Clean, no process to manage |

---

## Model Selection

| Preset | Resolves to | When to use |
|--------|-------------|-------------|
| `fast` | `gemini-3-flash-preview` | **Default.** Most tasks — search, review, generation, analysis |
| `quality` | `gemini-3.1-pro-preview` | Complex reasoning, architecture, nuanced writing |
| `auto` | cheapest available | Avoid — routes to `gemini-2.5-flash-lite` regardless of task |

Full model IDs also accepted: `gemini-3-flash-preview`, `gemini-3.1-pro-preview`, `gemini-2.5-pro`, `gemini-2.5-flash`, `gemini-2.5-flash-lite`.

Default when `--model` is omitted: `GEMINI_DEFAULT_MODEL` env var → `gemini-3-flash-preview`.

---

## System Context Injection

Gemini reads `GEMINI.md` from the working directory as project context (analogous to `CLAUDE.md`).

Inject per-call context via a temp file + `--include-directories`:

```bash
# This pattern sets Gemini's persona/output format for one invocation
TMPDIR=$(mktemp -d)
cat > "$TMPDIR/GEMINI.md" << 'EOF'
You are a security auditor. Flag OWASP top 10 issues only. Be concise.
EOF

gemini --prompt "Review this code" \
  --include-directories "$TMPDIR" \
  --approval-mode yolo --output-format json

rm -rf "$TMPDIR"
```

For a persistent default: set `GEMINI_SYSTEM_MD=/path/to/default.md` — read this file and pass its contents as `system_context` on every call.

---

## Composition Patterns

### Parallel web research

Fire multiple headless processes concurrently — each is independent:

```bash
# Start all searches in parallel
gemini --prompt "Search the web for: latest MoE architecture papers 2025" \
  --approval-mode yolo --output-format json &

gemini --prompt "Search the web for: transformer scaling laws survey 2025" \
  --approval-mode yolo --output-format json &

wait  # collect results when both finish
```

### Code review with piped context

```bash
git diff HEAD~1 | gemini \
  --prompt "Review this diff. Focus on security issues and edge cases. Be concise." \
  --approval-mode yolo --output-format json | jq -r '.response'
```

### Multi-turn research with `--resume`

```bash
OUTPUT=$(gemini --prompt "Explain transformer attention complexity" \
  --output-format stream-json --approval-mode yolo)
SESSION=$(echo "$OUTPUT" | jq -r 'select(.type=="init") | .sessionId' | head -1)
RESPONSE=$(echo "$OUTPUT" | jq -r 'select(.type=="result") | .response' | head -1)

# Drill down in the same session
gemini --prompt "Compare the top 3 approaches by memory efficiency" \
  --resume "$SESSION" --output-format json --approval-mode yolo | jq -r '.response'
```

### Large output to file

```bash
cat large-document.pdf | gemini \
  --prompt "Convert this document to structured JSON" \
  --approval-mode yolo --output-format json > /tmp/output.json
```

---

## Defaults and Safety

- `--approval-mode yolo` is required for headless — `default` blocks waiting for TTY confirmation
- `--sandbox` is optional — Gemini CLI's sandbox sets `HOME=/home/node` internally, which requires a specific system setup. Disable unless your system supports it.
- Default timeout: 5 minutes. For long tasks (large files, deep research), increase or use background processes.

---

## Reference Docs

- `references/headless.md` — Headless mode: output formats, JSONL event schema, exit codes
- `references/cli-reference.md` — Full CLI flags reference for headless automation
- `references/automation.md` — Shell-level automation patterns (piping, bulk processing, functions)
