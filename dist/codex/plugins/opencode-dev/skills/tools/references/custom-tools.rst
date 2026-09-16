<!-- Source: https://opencode.ai/docs/custom-tools/ — fetched 2026-06-29. Canonical truth; verify here (and re-check the live page for drift) before authoring OpenCode tools code. -->

# Custom Tools - OpenCode Technical Documentation

## Overview
Custom tools are functions that LLMs can invoke during conversations in OpenCode. They operate alongside built-in tools like `read`, `write`, and `bash`.

## Creating a Tool

### Location
Tools can be defined in two locations:
- **Locally**: `.opencode/tools/` directory in your project
- **Globally**: `~/.config/opencode/tools/`

### Structure
Tools are defined as TypeScript or JavaScript files using the `tool()` helper:

```typescript
import { tool } from "@opencode-ai/plugin"
export default tool({
  description: "Query the project database",
  args: {
    query: tool.schema.string().describe("SQL query to execute"),
  },
  async execute(args) {
    // Your database logic here
    return `Executed query: ${args.query}`
  },
})
```

The filename becomes the tool name (e.g., `database.ts` creates a `database` tool).

### Multiple Tools Per File
Export multiple tools with naming convention `<filename>_<exportname>`:

```typescript
import { tool } from "@opencode-ai/plugin"
export const add = tool({
  description: "Add two numbers",
  args: {
    a: tool.schema.number().describe("First number"),
    b: tool.schema.number().describe("Second number"),
  },
  async execute(args) {
    return (args.a + args.b).toString()
  },
})

export const multiply = tool({
  description: "Multiply two numbers",
  args: {
    a: tool.schema.number().describe("First number"),
    b: tool.schema.number().describe("Second number"),
  },
  async execute(args) {
    return (args.a * args.b).toString()
  },
})
```

This creates `math_add` and `math_multiply` tools.

### Name Collisions
Custom tools override built-in tools with identical names. Example replacing `bash`:

```typescript
import { tool } from "@opencode-ai/plugin"
export default tool({
  description: "Restricted bash wrapper",
  args: {
    command: tool.schema.string(),
  },
  async execute(args) {
    return `blocked: ${args.command}`
  },
})
```

### Arguments
Define arguments using `tool.schema` (Zod-based):

```typescript
args: {
  query: tool.schema.string().describe("SQL query to execute")
}
```

Or import Zod directly:

```typescript
import { z } from "zod"
export default {
  description: "Tool description",
  args: {
    param: z.string().describe("Parameter description"),
  },
  async execute(args, context) {
    return "result"
  },
}
```

### Context
Tools receive session context:

```typescript
import { tool } from "@opencode-ai/plugin"
export default tool({
  description: "Get project information",
  args: {},
  async execute(args, context) {
    const { agent, sessionID, messageID, directory, worktree } = context
    return `Agent: ${agent}, Session: ${sessionID}, Message: ${messageID}, Directory: ${directory}, Worktree: ${worktree}`
  },
})
```

Key properties:
- `context.directory` - session working directory
- `context.worktree` - git worktree root

## Examples

### Write a Tool in Python

Python script (`.opencode/tools/add.py`):
```python
import sys
a = int(sys.argv[1])
b = int(sys.argv[2])
print(a + b)
```

Tool definition (`.opencode/tools/python-add.ts`):
```typescript
import { tool } from "@opencode-ai/plugin"
import path from "path"

export default tool({
  description: "Add two numbers using Python",
  args: {
    a: tool.schema.number().describe("First number"),
    b: tool.schema.number().describe("Second number"),
  },
  async execute(args, context) {
    const script = path.join(context.worktree, ".opencode/tools/add.py")
    const result = await Bun.$`python3 ${script} ${args.a} ${args.b}`.text()
    return result.trim()
  },
})
```

Uses Bun's `$` shell utility for script execution.
