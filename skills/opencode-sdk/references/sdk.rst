<!-- Source: https://opencode.ai/docs/sdk/ — fetched 2026-06-29. Canonical truth; verify here (and re-check the live page for drift) before authoring OpenCode sdk code. -->

# OpenCode SDK

A type-safe JS client for interacting with the OpenCode server, to build integrations and control it programmatically. The TUI is itself a client, so the SDK can do anything the TUI does. SDK types are generated from the server's OpenAPI 3.1 spec.

## Installation

```
npm install @opencode-ai/sdk
```

## Client Creation

### Full instance — `createOpencode()` (starts server + client)

```javascript
import { createOpencode } from "@opencode-ai/sdk"
const { client } = await createOpencode()
```

Options:
- `hostname` (string, default: `127.0.0.1`)
- `port` (number, default: `4096`)
- `signal` (AbortSignal)
- `timeout` (number, default: `5000`)
- `config` (Config object)

Returns an object exposing the `client` plus the spawned server (`server.url`, `server.close()`).

### Client-only connection — `createOpencodeClient({ baseUrl })`

```javascript
import { createOpencodeClient } from "@opencode-ai/sdk"
const client = createOpencodeClient({
  baseUrl: "http://localhost:4096",
})
```

Options:
- `baseUrl` (string, default: `http://localhost:4096`)
- `fetch` (custom function)
- `parseAs` (string)
- `responseStyle` (string: `data` or `fields`)
- `throwOnError` (boolean)

> NOTE: `createOpencodeServer` does NOT appear on the official SDK page. The canonical surface is `createOpencode` + `createOpencodeClient`.

## Configuration

Configuration can be passed inline, overriding `opencode.json`:

```javascript
const opencode = await createOpencode({
  hostname: "127.0.0.1",
  port: 4096,
  config: {
    model: "anthropic/claude-3-5-sonnet-20241022",
  },
})
```

## Types

```javascript
import type { Session, Message, Part } from "@opencode-ai/sdk"
```

## Structured Output

Format types:
- `text` – Standard text response (default)
- `json_schema` – Validated JSON matching provided schema

`json_schema` format fields:
- `type` (required): `'json_schema'`
- `schema` (required): JSON Schema object
- `retryCount` (optional): Validation retry attempts (default: 2)

```javascript
const result = await client.session.prompt({
  path: { id: sessionId },
  body: {
    parts: [{ type: "text", text: "Research Anthropic and provide company info" }],
    format: {
      type: "json_schema",
      schema: {
        type: "object",
        properties: {
          company: { type: "string", description: "Company name" },
          founded: { type: "number", description: "Year founded" },
          products: {
            type: "array",
            items: { type: "string" },
            description: "Main products",
          },
        },
        required: ["company", "founded"],
      },
    },
  },
})
console.log(result.data.info.structured_output)
```

Error handling:

```javascript
if (result.data.info.error?.name === "StructuredOutputError") {
  console.error("Failed to produce structured output:", result.data.info.error.message)
  console.error("Attempts:", result.data.info.error.retries)
}
```

## API Methods

### Global
- `global.health()` – Returns `{ healthy: true, version: string }`

### App
- `app.log()` – Write log entry (returns `boolean`)
- `app.agents()` – List available agents (returns `Agent[]`)

### Project
- `project.list()` – List all projects (returns `Project[]`)
- `project.current()` – Get current project (returns `Project`)

### Path
- `path.get()` – Get current path info (returns `Path`)

### Config
- `config.get()` – Get config info (returns `Config`)
- `config.providers()` – List providers and defaults

### Sessions
- `session.list()`
- `session.get({ path })`
- `session.children({ path })`
- `session.create({ body })`
- `session.delete({ path })`
- `session.update({ path, body })`
- `session.init({ path, body })` – Analyze app, create `AGENTS.md`
- `session.abort({ path })`
- `session.share({ path })`
- `session.unshare({ path })`
- `session.summarize({ path, body })`
- `session.messages({ path })`
- `session.message({ path })`
- `session.prompt({ path, body })` – Supports `noReply: true` and `outputFormat`
- `session.command({ path, body })`
- `session.shell({ path, body })`
- `session.revert({ path, body })`
- `session.unrevert({ path })`
- `postSessionByIdPermissionsByPermissionId({ path, body })`

### Files
- `find.text({ query })` – Search text in files
- `find.files({ query })` – Find files/directories by name (query supports `type` ("file"/"directory"), `directory`, `limit` 1–200)
- `find.symbols({ query })` – Find workspace symbols
- `file.read({ query })` – Read file content
- `file.status({ query? })` – Get tracked file status

### TUI
- `tui.appendPrompt({ body })`
- `tui.openHelp()`
- `tui.openSessions()`
- `tui.openThemes()`
- `tui.openModels()`
- `tui.submitPrompt()`
- `tui.clearPrompt()`
- `tui.executeCommand({ body })`
- `tui.showToast({ body })`

### Auth
- `auth.set({ ... })` – Set authentication credentials

### Events
- `event.subscribe()` – Server-sent events stream
