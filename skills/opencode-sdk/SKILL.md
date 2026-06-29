---
name: opencode-sdk
license: CC-BY-4.0
compatibility: opencode
description: >-
  Drive OpenCode (the SST coding agent, opencode.ai) programmatically — the
  @opencode-ai/sdk JS/TS client, the github.com/sst/opencode-sdk-go Go client,
  and the `opencode serve` HTTP/OpenAPI server it talks to. Use when building an
  integration on top of OpenCode, calling createOpencode / createOpencodeClient,
  running `opencode serve`, hitting the OpenAPI spec at /doc, listing or prompting
  sessions over HTTP, wiring OPENCODE_SERVER_PASSWORD auth, requesting structured
  (json_schema) output, or using opencode.NewClient / Session.List / the Field
  param wrappers in Go. NOT OpenAI Codex; NOT the opencode.ai/docs/go Zen
  subscription.
argument-hint: "What do you want to build on the OpenCode SDK/server? (e.g. 'prompt a session over HTTP and get JSON back', 'spin up a server from Node', 'list sessions in Go')"
user-invocable: true
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

# OpenCode SDK & server

Control OpenCode the way the TUI does: the TUI is itself a client of the `opencode serve`
HTTP server, so the SDK can do anything the TUI does. SDK types are **generated from the
server's OpenAPI 3.1 spec** — the spec at `/doc` is the real contract; the SDK is a typed
shell over it.

> **OpenCode's API moves fast and predates the model's training cutoff** — before writing
> sdk code, read `references/sdk.rst` (+ `server.rst`, `go.rst`) AND re-check
> <https://opencode.ai/docs/sdk/> for drift. Pin versions; don't trust memory of method names.

## Pick your entry point

| You want to… | Use | From |
|---|---|---|
| Spawn a server **and** get a client in one Node call | **`createOpencode()`** | `@opencode-ai/sdk` |
| Connect to an **already-running** server | **`createOpencodeClient({ baseUrl })`** | `@opencode-ai/sdk` |
| Drive from Go | **`opencode.NewClient()`** | `github.com/sst/opencode-sdk-go` |
| Talk raw HTTP / any language | `opencode serve` + the endpoints in `references/server.rst` | OpenAPI at `/doc` |

> **There is NO `createOpencodeServer`.** It appears only in third-party material and is
> not on the official SDK page. The canonical JS surface is exactly two factories:
> `createOpencode` (server + client) and `createOpencodeClient` (client only). Do not
> propagate `createOpencodeServer`.

## Version pins (record + verify current)

| Thing | Pin | Note |
|---|---|---|
| Go SDK module | `github.com/sst/opencode-sdk-go@v0.19.2` | **official path** — other namesake Go modules exist; verify this one |
| Go toolchain | **Go 1.22+** | required by the SDK |
| JS package | `@opencode-ai/sdk` | `npm install @opencode-ai/sdk` |
| Plugin/tool types | `@opencode-ai/plugin` | for in-plugin clients (see `/opencode-dev:plugin`) |

`createOpencode`'s `client` is the same type as `PluginInput.client` — code written here
is reusable inside a plugin.

## `opencode serve` — the server

```
opencode serve [--port 4096] [--hostname 127.0.0.1] [--cors <origin>] [--mdns] [--mdns-domain <d>]
```

- Defaults: **port `4096`, host `127.0.0.1`** (loopback-only — not exposed to the network).
- **Auth is opt-in via env, not flags:** set `OPENCODE_SERVER_PASSWORD` to require HTTP basic
  auth; username defaults to `opencode` (override with `OPENCODE_SERVER_USERNAME`). No password
  set ⇒ no auth.
- `--cors` is **repeatable** (pass once per origin); browsers need it, server-to-server doesn't.
- **OpenAPI 3.1 spec lives at `GET /doc`** — fetch it to regenerate types or to find any
  endpoint not yet wrapped by the SDK. This is the source of truth, not this file.

Endpoint traps (full list in `references/server.rst`):
- Health is **`GET /global/health`** (returns `{ healthy, version }`), not `/health`.
- Send-and-wait is `POST /session/:id/message`; fire-and-forget is **`POST /session/:id/prompt_async`**.
- Search is `GET /find?pattern=`, files `GET /find/file?query=`, symbols `GET /find/symbol?query=`,
  read `GET /file/content?path=`.
- SSE event stream: `GET /event` (per-session) / `GET /global/event`.

## JS/TS client

```javascript
import { createOpencode } from "@opencode-ai/sdk"
const { client, server } = await createOpencode()   // server.url, server.close()
```

`createOpencode` options: `hostname` (`127.0.0.1`), `port` (`4096`), `timeout` (`5000`),
`signal`, `config` (an inline `Config` that **overrides `opencode.json`**). Always
`await server.close()` when done — the factory owns the spawned process.

`createOpencodeClient` options: `baseUrl` (`http://localhost:4096`), `fetch`, `parseAs`,
**`responseStyle`** (`"data"` | `"fields"`), **`throwOnError`** (bool). Default style returns
`{ data, ... }` — note results are accessed as **`result.data.…`** (e.g.
`result.data.info.structured_output`), so a missing `.data` is the usual "why is my field
undefined" bug.

API surfaces are **namespaced objects**, not flat: `client.global.health()`,
`client.app.log()/agents()`, `client.project.list()/current()`, `client.session.*`
(`list/get/create/update/delete/prompt/command/shell/messages/abort/share/init/revert/…`),
`client.find.text/files/symbols`, `client.file.read/status`, `client.tui.*`,
`client.auth.set`, `client.event.subscribe()`. Full method list in `references/sdk.rst`.

### Structured output (the json_schema path)

```javascript
const result = await client.session.prompt({
  path: { id: sessionId },
  body: {
    parts: [{ type: "text", text: "…" }],
    format: { type: "json_schema", schema: { /* JSON Schema */ }, retryCount: 2 },
  },
})
result.data.info.structured_output            // the parsed object
result.data.info.error?.name === "StructuredOutputError"  // check this before reading output
```

- `format.type` is `"text"` (default) or **`"json_schema"`**; the schema goes in
  `format.schema`, retries in `format.retryCount` (default `2`).
- Under the hood the model is forced through a `StructuredOutput` tool. On failure
  `info.error.name === "StructuredOutputError"` (with `.message`, `.retries`) — **the call
  still resolves**, so guard on the error field rather than a `try/catch`.

See `assets/hello-sdk.ts` for a runnable spawn → prompt → structured-output → close flow.

## Go client

```go
import "github.com/sst/opencode-sdk-go"
client := opencode.NewClient()
sessions, err := client.Session.List(context.TODO(), opencode.SessionListParams{})
```

- **Every request param is wrapped in a `Field`** to separate zero/null/omitted. Build with
  `opencode.F(v)`, `opencode.Null[T]()`, `opencode.Raw[T](any)` (and `String/Int/Float`
  helpers). A bare `""`/`0` is **not sent** unless wrapped — forgetting `F()` silently omits it.
- Response fields are plain value types; inspect presence via the per-field
  `res.JSON.<Field>.IsNull()/IsMissing()/IsInvalid()` and undocumented keys via
  `res.JSON.ExtraFields[...]`.
- Errors: `errors.As(err, &apiErr)` into **`*opencode.Error`** (`StatusCode`,
  `DumpRequest/DumpResponse`). Retries default to **2** (connection errors, 408/409/429/≥500);
  **no default timeout** — set one via `context` + `option.WithRequestTimeout()`.
- Reach undocumented endpoints with `client.Get/Post(...)` and `option.WithJSONSet/WithQuerySet`.

`NewClient()` targets `127.0.0.1:4096` by default; configure base URL/headers/auth via the
`option` package. See `assets/hello-sdk.go`. Full API in the SDK's own `api.md`.

## Traps to avoid

- ⚠️ **`opencode.ai/docs/go/` is the wrong page for the Go SDK** — it documents the paid
  "OpenCode Zen Go" model subscription, not the library. The Go *SDK* is
  `github.com/sst/opencode-sdk-go` (see `references/go.rst`).
- ⚠️ **This is SST OpenCode, not OpenAI Codex.** Don't import Codex/`app-server` APIs.
- ⚠️ No `createOpencodeServer`; no Python package is officially verified (JS/TS + Go only).
- ⚠️ JS results are under **`result.data`** (default `responseStyle`); structured-output
  failures surface as `info.error`, not a thrown exception (unless `throwOnError`).

## Reference & example files

| File | Contents |
|---|---|
| [references/sdk.rst](references/sdk.rst) | JS/TS SDK — factories, options, all `client.*` methods, structured output |
| [references/server.rst](references/server.rst) | `opencode serve` flags, env auth, full endpoint list, OpenAPI `/doc` |
| [references/go.rst](references/go.rst) | Go SDK — install/pin, `NewClient`, `Field` wrappers, errors, retries, options |
| [assets/hello-sdk.ts](assets/hello-sdk.ts) | Node: spawn server → create session → structured prompt → close |
| [assets/hello-sdk.go](assets/hello-sdk.go) | Go: `NewClient` → `Session.List` with `*opencode.Error` handling |

Related facets: programmatic tool/hook code → `/opencode-dev:plugin`; delegating from a
Claude Code plugin (ACP / `serve` / `opencode run`) → `/opencode-dev:delegate`.
