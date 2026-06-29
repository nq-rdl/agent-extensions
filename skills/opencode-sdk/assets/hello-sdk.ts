// Drive OpenCode from JS/TS via @opencode-ai/sdk.
// Verify the surface in references/sdk.md and re-check https://opencode.ai/docs/sdk/ for drift.
//   npm install @opencode-ai/sdk
//
// createOpencode() spawns `opencode serve` AND returns a connected client.
// To attach to an already-running server instead, use:
//   import { createOpencodeClient } from "@opencode-ai/sdk"
//   const client = createOpencodeClient({ baseUrl: "http://localhost:4096" })
// There is NO createOpencodeServer in the official SDK — do not use it.

import { createOpencode } from "@opencode-ai/sdk"

const { client, server } = await createOpencode({ hostname: "127.0.0.1", port: 4096 })

try {
  const health = await client.global.health() // { healthy: true, version }
  console.log("server", server.url, health)

  const session = await client.session.create({ body: {} })
  const id = session.data.id

  // Structured output: model is forced through a json_schema StructuredOutput tool.
  const result = await client.session.prompt({
    path: { id },
    body: {
      parts: [{ type: "text", text: "Summarize this repo in one sentence." }],
      format: {
        type: "json_schema",
        schema: {
          type: "object",
          properties: { summary: { type: "string" } },
          required: ["summary"],
        },
      },
    },
  })

  if (result.data.info.error?.name === "StructuredOutputError") {
    console.error("structured output failed:", result.data.info.error.message)
  } else {
    console.log(result.data.info.structured_output)
  }
} finally {
  await server.close()
}
