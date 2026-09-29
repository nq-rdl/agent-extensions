// Drive OpenCode from JS/TS via @opencode-ai/sdk (v2 entry point).
// Verify the surface in references/sdk.rst and the generated types
// (packages/sdk/js/src/v2/gen/types.gen.ts at your installed release tag);
// the docs page lags the package. Checked against 1.18.33 types by reading,
// not compiled here.
//   npm install @opencode-ai/sdk
//
// createOpencode() spawns `opencode serve` (the `opencode` binary must be on PATH)
// AND returns a connected client. To attach to an already-running server instead:
//   import { createOpencodeClient } from "@opencode-ai/sdk/v2"
//   const client = createOpencodeClient({ baseUrl: "http://localhost:4096" })
// createOpencodeServer() (server only, { url, close }) is also exported.
//
// The root "@opencode-ai/sdk" entry uses { path, body } params and its
// session.prompt body type has no `format` field; v2 takes flat params.

import { createOpencode } from "@opencode-ai/sdk/v2"

const { client, server } = await createOpencode({ hostname: "127.0.0.1", port: 4096 })

try {
  const health = await client.global.health() // data: { healthy: true, version }
  console.log("server", server.url, health.data)

  const session = await client.session.create({})
  if (!session.data) throw new Error(`session.create failed: ${JSON.stringify(session.error)}`)
  const sessionID = session.data.id

  // Structured output: the model is forced through a json_schema StructuredOutput tool.
  const result = await client.session.prompt({
    sessionID,
    parts: [{ type: "text", text: "Summarize this repo in one sentence." }],
    format: {
      type: "json_schema",
      schema: {
        type: "object",
        properties: { summary: { type: "string" } },
        required: ["summary"],
      },
    },
  })

  const info = result.data?.info
  if (!info) {
    console.error("prompt failed:", result.error) // HTTP errors are returned, not thrown
  } else if (info.error?.name === "StructuredOutputError") {
    // The call still resolves; message and retries live under error.data.
    console.error("structured output failed:", info.error.data.message, info.error.data.retries)
  } else {
    console.log(info.structured) // the parsed object (docs say structured_output; the field is structured)
  }
} finally {
  await server.close()
}
