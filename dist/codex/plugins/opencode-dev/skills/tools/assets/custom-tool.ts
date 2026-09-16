// .opencode/tools/database.ts
// Filename == tool name → this registers a tool called "database".
// (A file named after a built-in, e.g. bash.ts, OVERRIDES that built-in.)
// For multiple tools per file, use named exports → tool name is `<file>_<export>`.
import { tool } from "@opencode-ai/plugin"

export default tool({
  description: "Query the project database",
  args: {
    // tool.schema is a Zod re-export; or `import { z } from "zod"` and use z.
    query: tool.schema.string().describe("SQL query to execute"),
  },
  // context = { agent, sessionID, messageID, directory, worktree }
  async execute(args, context) {
    // Shell out to any language via Bun.$ if needed:
    // const out = await Bun.$`psql -c ${args.query}`.text()
    return `Executed query against ${context.directory}: ${args.query}`
  },
})
