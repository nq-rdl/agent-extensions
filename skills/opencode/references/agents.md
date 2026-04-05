# Agent Configuration Reference

Agents are specialized AI personas — different prompts, models, and tool restrictions. They require no code.

## Placement

```
.opencode/agents/<name>.md           # project-local (markdown format)
~/.config/opencode/agents/<name>.md  # global (markdown format)
opencode.json → "agent" key          # JSON format (same project config file)
```

## Markdown Format

```markdown
---
description: One-line description of what this agent does
mode: subagent
model: anthropic/claude-sonnet-4-5
temperature: 0.2
tools:
  write: false
  bash: true
permission:
  bash: ask
hidden: false
---

Full system prompt goes here. Write it as detailed instructions for the agent.

The filename (without .md) becomes the agent ID. For example, `security-reviewer.md`
creates agent ID `security-reviewer`.
```

## All Frontmatter Fields

| Field | Type | Description |
|-------|------|-------------|
| `description` | string | **Required.** Brief purpose — shown in agent picker and used for routing |
| `mode` | `"primary"` \| `"subagent"` \| `"all"` | Where agent appears (default: depends on context) |
| `model` | string | Model in `provider/model-id` format |
| `temperature` | number | 0.0–1.0 (model default if omitted) |
| `top_p` | number | 0.0–1.0, controls response diversity |
| `steps` | number | Max agentic iterations before stopping |
| `prompt` | string | File reference: `{file:./prompt.txt}` |
| `tools` | object | Tool enable/disable map |
| `permission` | object | Permission levels per operation |
| `color` | string | UI accent color (hex or theme name) |
| `hidden` | boolean | Hide from autocomplete (agents with `mode: subagent` only) |
| `disable` | boolean | Deactivate without deleting |

## Mode Values

| Mode | Appears in | Use case |
|------|-----------|---------|
| `primary` | Top-level agent picker | User-facing agents (build, plan) |
| `subagent` | Invoked by other agents | Specialized helpers |
| `all` | Both | General-purpose agents |

## Model Format

```
provider/model-id
```

Examples:
- `anthropic/claude-opus-4-5`
- `anthropic/claude-sonnet-4-5`
- `anthropic/claude-haiku-4-5-20251001`
- `openai/gpt-4o`
- `google/gemini-2.5-pro`
- `ollama/llama3.2`  (local)

## Tool Configuration

```yaml
tools:
  write: false        # Disable write tool
  bash: true          # Explicitly enable bash
  edit: false         # Disable edit tool
  mymcp_*: false      # Disable all tools from "mymcp" server
```

Wildcard patterns disable all tools matching the prefix.

## Permission Levels

```yaml
permission:
  bash: ask         # Prompt user before running any bash command
  edit: allow       # Auto-approve file edits
  write: deny       # Always block write operations
```

Bash supports command-specific patterns:

```yaml
permission:
  bash:
    "*": ask                # Ask for all commands by default
    "git status": allow     # Auto-approve safe git commands
    "git log *": allow
    "rm *": deny            # Always block destructive commands
```

## JSON Format (in opencode.json)

```json
{
  "agent": {
    "code-reviewer": {
      "description": "Reviews code for style and correctness",
      "mode": "subagent",
      "model": "anthropic/claude-sonnet-4-5",
      "tools": {
        "write": false,
        "bash": false
      },
      "permission": {
        "bash": "deny"
      }
    },
    "test-writer": {
      "description": "Writes unit tests for existing code",
      "model": "anthropic/claude-haiku-4-5-20251001",
      "tools": {
        "write": true,
        "bash": true
      }
    }
  }
}
```

## Built-in Agents

| ID | Mode | Description |
|----|------|-------------|
| `build` | primary | Full tool access for development work |
| `plan` | primary | Read-only analysis and planning |
| `general` | subagent | Multi-step task execution |
| `explore` | subagent | Read-only codebase exploration |

## Design Patterns

### Read-Only Analyst

```markdown
---
description: Analyses code and suggests improvements without making changes
mode: subagent
model: anthropic/claude-sonnet-4-5
tools:
  write: false
  edit: false
  bash: false
permission:
  bash: deny
---

You are a code analyst. Read code and provide detailed suggestions.
Never make changes — only describe what should be changed and why.
```

### Domain Expert

```markdown
---
description: Expert in the project's domain (e.g., clinical data pipelines)
mode: primary
model: anthropic/claude-opus-4-5
temperature: 0.1
---

You have deep expertise in [domain]. When helping with this codebase:
- Always consider [domain-specific constraint 1]
- Follow [domain-specific convention]
- When in doubt about [domain concept], ask for clarification before proceeding.
```

### Fast Task Runner

```markdown
---
description: Quick one-shot tasks — format, rename, simple transforms
mode: subagent
model: anthropic/claude-haiku-4-5-20251001
steps: 5
hidden: true
---

You are a fast task executor. Complete the requested task in as few steps as possible.
```

### External Prompt File

When the system prompt is long, keep it in a separate file:

```markdown
---
description: Complex agent with detailed instructions
model: anthropic/claude-sonnet-4-5
prompt: "{file:.opencode/prompts/my-agent-prompt.txt}"
---
```

The `{file:...}` syntax is relative to the project root.

## Using Agents from the CLI

```bash
# Switch to a specific agent in a session
# (via TUI or SDK)
opencode --agent security-reviewer

# Or via SDK:
await client.session.prompt({
  sessionID: session.id,
  text: "Review this PR",
  agentID: "security-reviewer",
})
```
