# Custom Tools Reference

Custom tools give the LLM a new callable function. The LLM decides when to call them based on the `description`.

## Placement

| Location | Scope |
|----------|-------|
| `.opencode/tools/<name>.ts` | Project-local (current project only) |
| `~/.config/opencode/tools/<name>.ts` | Global (all projects) |

OpenCode discovers tools at startup by scanning these directories.

## `tool()` Function Signature

```typescript
import { tool } from "@opencode-ai/plugin"

tool({
  description: string,  // What the tool does — the LLM reads this to decide when to call it
  args: {
    [paramName: string]: ZodSchema,  // Define each parameter
  },
  async execute(args: ParsedArgs, context: ToolContext): Promise<any>
})
```

## Args Schema

Two equivalent approaches — prefer `tool.schema` for brevity:

```typescript
// Approach 1: tool.schema (thin Zod wrapper)
args: {
  query:  tool.schema.string().describe("SQL query to execute"),
  limit:  tool.schema.number().describe("Max rows to return"),
  dryRun: tool.schema.boolean().describe("If true, don't execute"),
}

// Approach 2: raw Zod (more power, e.g. enums, unions)
import { z } from "zod"
args: {
  format: z.enum(["json", "csv", "table"]).describe("Output format"),
  config: z.object({ timeout: z.number() }).describe("Config object"),
}
```

## Execute Context

```typescript
interface ToolContext {
  agent: string      // e.g. "build", "plan", or custom agent ID
  sessionID: string  // UUID of the current session
  messageID: string  // UUID of the current message
  directory: string  // absolute path to the session working directory
  worktree: string   // absolute path to the git worktree root
}
```

## Naming Rules

| File | Exports | Tool names |
|------|---------|------------|
| `search.ts` | `export default tool(...)` | `search` |
| `git.ts` | `export const status = tool(...)`, `export const log = tool(...)` | `git_status`, `git_log` |

Custom tools with the same name as a built-in tool **override** the built-in.

## Patterns

### API Tool

```typescript
// .opencode/tools/github-pr.ts
import { tool } from "@opencode-ai/plugin"

export default tool({
  description: "Fetch a GitHub PR's title, body, and diff",
  args: {
    repo:   tool.schema.string().describe("owner/repo"),
    number: tool.schema.number().describe("PR number"),
  },
  async execute(args, context) {
    const token = process.env.GITHUB_TOKEN
    if (!token) throw new Error("GITHUB_TOKEN not set")

    const resp = await fetch(
      `https://api.github.com/repos/${args.repo}/pulls/${args.number}`,
      { headers: { Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json" } }
    )
    if (!resp.ok) throw new Error(`GitHub API error: ${resp.status}`)

    const pr = await resp.json()
    return {
      title: pr.title,
      body: pr.body,
      state: pr.state,
      author: pr.user.login,
    }
  },
})
```

### Shell Tool (using Bun.$)

```typescript
// .opencode/tools/git-stats.ts
import { tool } from "@opencode-ai/plugin"

export const recentLog = tool({
  description: "Get the last N git commits with authors and messages",
  args: {
    count: tool.schema.number().describe("Number of commits to return"),
  },
  async execute(args, context) {
    const result = await Bun.$`git -C ${context.worktree} log --oneline -${args.count} --pretty=format:"%h %an: %s"`.text()
    return result.trim()
  },
})

export const diff = tool({
  description: "Get the git diff for a specific commit",
  args: {
    sha: tool.schema.string().describe("Commit SHA"),
  },
  async execute(args, context) {
    const result = await Bun.$`git -C ${context.worktree} show ${args.sha} --stat`.text()
    return result.trim()
  },
})
// Tools exposed as: git-stats_recentLog, git-stats_diff
```

### Database Tool

```typescript
// .opencode/tools/db-query.ts
import { tool } from "@opencode-ai/plugin"
import { Database } from "bun:sqlite"

export default tool({
  description: "Run a read-only SQL query against the project database",
  args: {
    sql: tool.schema.string().describe("SQL SELECT query (read-only)"),
  },
  async execute(args, context) {
    if (!args.sql.trim().toUpperCase().startsWith("SELECT")) {
      throw new Error("Only SELECT queries are allowed")
    }

    const db = new Database(`${context.directory}/db.sqlite`, { readonly: true })
    try {
      const rows = db.query(args.sql).all()
      return JSON.stringify(rows, null, 2)
    } finally {
      db.close()
    }
  },
})
```

### File Transformation Tool

```typescript
// .opencode/tools/format-json.ts
import { tool } from "@opencode-ai/plugin"

export default tool({
  description: "Pretty-print or minify a JSON file",
  args: {
    path:   tool.schema.string().describe("Absolute path to the JSON file"),
    action: tool.schema.string().describe("'pretty' or 'minify'"),
  },
  async execute(args, context) {
    const file = Bun.file(args.path)
    if (!(await file.exists())) throw new Error(`File not found: ${args.path}`)

    const raw = await file.text()
    const parsed = JSON.parse(raw)
    const output = args.action === "minify"
      ? JSON.stringify(parsed)
      : JSON.stringify(parsed, null, 2)

    await Bun.write(args.path, output)
    return `${args.action === "minify" ? "Minified" : "Formatted"}: ${args.path} (${output.length} bytes)`
  },
})
```

## Error Handling

```typescript
async execute(args, context) {
  try {
    // ... your logic
  } catch (err) {
    // Throw a descriptive error — the LLM will read this and decide what to do
    throw new Error(`Tool failed: ${err instanceof Error ? err.message : String(err)}`)
  }
}
```

Return strings, objects, or arrays — OpenCode serialises them for the LLM.

## Per-Project Dependencies

If your tool needs npm packages, add a `.opencode/package.json`:

```json
{
  "dependencies": {
    "date-fns": "^3.0.0",
    "lodash-es": "^4.17.21"
  }
}
```

OpenCode runs `bun install` at startup. Import normally in your tool file.
