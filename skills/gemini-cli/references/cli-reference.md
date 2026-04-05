# Gemini CLI Reference (Headless Automation)

This reference covers the CLI flags most relevant for headless/programmatic use. For the interactive UI, see the official Gemini CLI docs.

## Core Invocation

```bash
gemini [OPTIONS] [PROMPT]
# or
gemini -p "prompt text" [OPTIONS]
```

When `-p` is provided, the CLI runs headlessly and exits after completion.

---

## Key Flags for Headless Use

### Prompt

| Flag | Alias | Description |
|------|-------|-------------|
| `--prompt <text>` | `-p` | Provide prompt directly; triggers headless mode |

### Output Format

| Flag | Alias | Values | Default |
|------|-------|--------|---------|
| `--output-format <fmt>` | `-o` | `text`, `json`, `stream-json` | `text` |

Use `stream-json` to get session IDs and streaming events. Use `json` for simple one-shot calls.

### Model Selection

| Flag | Alias | Values |
|------|-------|--------|
| `--model <model>` | `-m` | `auto`, `pro`, `flash`, `flash-lite` |

Model guidance:
- `auto` — Gemini routes to the best model for the task (default)
- `pro` — Gemini 2.5 Pro: highest quality, slowest, most expensive
- `flash` — Gemini 2.5 Flash: balanced speed/quality, good for web search
- `flash-lite` — Fastest, lowest cost; best for simple lookups

### Approval Mode

| Flag | Values | Default |
|------|--------|---------|
| `--approval-mode <mode>` | `default`, `auto_edit`, `yolo` | `default` |

| Mode | Behavior |
|------|---------|
| `default` | Requires confirmation for all tool actions — **BLOCKS** in headless (no TTY) |
| `auto_edit` | Auto-approves file edits; prompts for shell/network actions |
| `yolo` | Auto-approves all actions — **required for headless** |

> ⚠️ Always use `--approval-mode yolo` in headless/automated contexts. Without it, Gemini CLI will block waiting for interactive confirmation that can never arrive.

### Sandbox

| Flag | Alias | Description |
|------|-------|-------------|
| `--sandbox` | `-s` | Run tool execution in a sandboxed environment |

Use `--sandbox` with `--approval-mode yolo` to auto-approve actions while limiting their blast radius. Recommended default for all headless calls.

### Session Continuation

| Flag | Alias | Description |
|------|-------|-------------|
| `--resume <session-id>` | `-r` | Resume a previous session (multi-turn) |

Session IDs come from the `init` event in `stream-json` output. Allows multi-turn conversations without re-sending prior context.

### Tool Control

| Flag | Description |
|------|-------------|
| `--allowed-tools <tools>` | Comma-separated list of tools that skip confirmation (e.g., `web_search,read_file`) |
| `--extensions <ext>` | Limit which extensions are loaded (comma-separated) |

### Workspace Control

| Flag | Description |
|------|-------------|
| `--include-directories <dirs>` | Add extra directories to Gemini's workspace (comma-separated paths) |

This is the mechanism used to inject system context via GEMINI.md files in temp directories.

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Google AI API key (required unless using OAuth) |
| `GEMINI_MODEL` | Default model override (same values as `--model`) |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | General error / API failure |
| `42` | Input error (bad prompt or arguments) |
| `53` | Turn limit exceeded |

---

## Complete Headless Example

```bash
# Full headless invocation with all recommended flags
gemini \
  --prompt "Search for recent papers on mixture-of-experts architectures" \
  --output-format stream-json \
  --model flash \
  --approval-mode yolo \
  --sandbox \
  --include-directories /tmp/gemini-context-xyz
```

Where `/tmp/gemini-context-xyz/GEMINI.md` contains the system context:

```markdown
You are a research assistant. Return results as a JSON array with fields:
- title (string)
- authors (string[])
- year (number)
- summary (string, 1-2 sentences)
```

---

## Piping Context

Gemini CLI reads stdin in headless mode, allowing you to pipe file contents or command output:

```bash
# Pipe a git diff for review
git diff HEAD~1 | gemini -p "Review this diff. Focus on security issues." --approval-mode yolo

# Pipe a log file
tail -n 1000 app.log | gemini -p "What's causing these errors?" --approval-mode yolo

# Pipe command output
kubectl describe pod my-pod | gemini -p "Is this pod healthy? What's wrong?" --approval-mode yolo
```

---

## GEMINI.md (Project Context)

Gemini CLI reads `GEMINI.md` files from the current working directory (and parent directories) as project context — analogous to Claude Code's `CLAUDE.md`.

Use `--include-directories <path>` to add directories containing additional `GEMINI.md` files without changing the working directory. This is the recommended way to inject per-call system context.
