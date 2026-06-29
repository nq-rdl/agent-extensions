---
name: opencode-tools
license: CC-BY-4.0
compatibility: opencode
description: >-
  Extend OpenCode's capabilities with the three add-on mechanisms: standalone
  custom tools (`.opencode/tools/*.ts`), MCP servers (the `mcp` config key), and
  LSP servers (the `lsp` config key). Encodes the traps a fresh model gets wrong —
  plural dir + filename-is-toolname + built-in override, the `environment` (MCP)
  vs `env` (LSP) spelling split, MCP tool namespacing + the `tools` glob gate,
  the `lsp` boolean-or-object shape, the built-in tool list, and `apply_patch`
  (not `patch`) sharing the one `edit` permission. Use when the user is writing
  an OpenCode custom tool, importing `tool` from `@opencode-ai/plugin`,
  overriding a built-in like `bash`, wiring an MCP server, configuring `lsp`,
  setting `permission`/`tools` gates, or asks about `.opencode/tools/`,
  `apply_patch`, `patchText`, `environment`, or namespaced MCP tools.
argument-hint: "e.g. 'add a custom .opencode tool that overrides bash' or 'wire a remote MCP server'"
user-invocable: true
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

# OpenCode: extending tools (custom tools, MCP, LSP)

OpenCode's API moves fast and predates the model's training cutoff — before
writing tools code, read `references/custom-tools.rst`, `references/mcp-servers.rst`,
`references/lsp.rst`, `references/tools.rst` AND re-check
https://opencode.ai/docs/custom-tools/ (and the `/mcp-servers/`, `/lsp/`, `/tools/`
pages) for drift.

**Three distinct extension mechanisms — pick one:**

| Want | Mechanism | Where | Surface |
|---|---|---|---|
| Your own callable function | **Custom tool** | file `.opencode/tools/<name>.ts` | `tool()` from `@opencode-ai/plugin` |
| An external MCP toolset | **MCP server** | `mcp` key in `opencode.json` | config only |
| Diagnostics for the agent | **LSP server** | `lsp` key in `opencode.json` | config only |

**Pin:** the load-bearing package is `@opencode-ai/plugin@1.17.11` (frontmatter
`compatibility:`; source of `tool` / `tool.schema`). Re-check the installed
version (`npm view @opencode-ai/plugin version`) against the API recital below
before relying on it. (Go SDK `v0.19.2` / Go 1.22+ belong to `/opencode-dev:sdk`,
not this facet.)

**Facet boundary:** this skill covers **filesystem-discovered** standalone tools.
Registering a tool **programmatically from inside a plugin** (the `tool` map hook)
is `/opencode-dev:plugin` — both import `tool` from `@opencode-ai/plugin`, but
don't duplicate the plugin route here. Permission `allow|ask|deny` *semantics* are
owned by `/opencode-dev:policies`; this skill only shows the `tools` enable/disable
gate and points there.

## 1. Custom tools — the filename/override traps

```ts
// .opencode/tools/database.ts  → tool name is "database" (filename == tool name)
import { tool } from "@opencode-ai/plugin"
export default tool({
  description: "Query the project database",
  args: { query: tool.schema.string().describe("SQL query to execute") },
  async execute(args, context) { return `ran: ${args.query}` },
})
```

- **Dir is plural `.opencode/tools/`** (project) or `~/.config/opencode/tools/`
  (global). Singular is wrong.
- **Filename = tool name.** `database.ts` → `database`.
- **A file named after a built-in OVERRIDES it.** Drop `bash.ts` in
  `.opencode/tools/` and your tool replaces the built-in `bash` (keyed by name).
  This is the supported way to sandbox/restrict a built-in.
- **Multiple named exports → `<filename>_<export>`.** `math.ts` exporting `add`
  and `multiply` yields `math_add` and `math_multiply` (NOT `add`/`multiply`).
- Args use `tool.schema` (Zod re-export). Plain-object form is allowed if you
  `import { z } from "zod"` yourself.
- `execute(args, context)` — `context` = `{ agent, sessionID, messageID,
  directory, worktree }`. Shell out to any language via `Bun.$` (see
  `references/custom-tools.rst` Python example).

## 2. MCP servers — `mcp` key, two transports

```jsonc
{ "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "local-srv":  { "type": "local",  "command": ["npx","-y","my-mcp"],
                    "enabled": true, "environment": { "MY_VAR": "v" } },
    "remote-srv": { "type": "remote", "url": "https://x.com", "enabled": true,
                    "headers": { "Authorization": "Bearer KEY" } } } }
```

- **Local env key is `environment`** (full word). This is the #1 trap — see §4.
- `type` (`"local"`/`"remote"`) is required. Non-obvious optionals: `timeout`
  (ms, default **5000**), plus `cwd` and `oauth`.
- **OAuth:** omit it and OpenCode auto-detects 401 → Dynamic Client Registration
  (RFC 7591). `"oauth": {}` triggers DCR explicitly; `"oauth": false` disables it.
  CLI: `opencode mcp auth|list|logout|debug <srv>`.
- **MCP tools are namespaced by the server name as prefix** — server `sentry`
  exposes `sentry_*`. You reference and gate them by that prefix.
- Caveat: MCP servers add to context; enabling a heavy one (e.g. GitHub MCP) can
  blow the context window.

### Gating MCP tools — `tools` (enable/disable), not `permission`

Two separate mechanisms, do not conflate:

- **`tools`** = top-level glob map that **enables/disables** tools:
  `"tools": { "sentry_*": false }`. Re-enable per agent:
  `"agent": { "my-agent": { "tools": { "sentry_*": true } } }`.
- **`permission`** = `allow|ask|deny` over actions (owned by
  `/opencode-dev:policies`). Different axis.

## 3. LSP servers — `lsp` key is boolean-or-object

Disabled by default. The `lsp` key accepts a **boolean OR an object**:

| Value | Effect |
|---|---|
| `true` | Enable all 30+ built-in servers |
| `false` | Disable all LSP |
| `{}` | Keep built-ins + add/override custom entries |
| `{ "<srv>": { "disabled": true } }` | Disable one server, keep the rest |

```json
{ "$schema": "https://opencode.ai/config.json",
  "lsp": { "typescript": { "disabled": true },
           "custom-lsp": { "command": ["custom-lsp-server","--stdio"],
                           "extensions": [".custom"] } } }
```

Per-server fields beyond the example: `env` (object — NOT `environment`; see §4)
and `initialization` (object). Suppress auto-download with
`OPENCODE_DISABLE_LSP_DOWNLOAD=true`.

## 4. The two cross-cutting traps

**`environment` vs `env` — same concept, two spellings:**

| Layer | Env key |
|---|---|
| MCP local server (`mcp.<srv>`) | **`environment`** (full word) |
| LSP server (`lsp.<srv>`) | **`env`** (short) |
| Custom tool `tool()` | neither — use `Bun.$` / `process.env` in `execute` |

**`lsp` is overloaded three ways — keep them separate:**

| `lsp` as… | What it is |
|---|---|
| top-level **config key** | wires LSP *servers* (boolean-or-object, §3) |
| built-in **tool** named `lsp` | experimental; needs `OPENCODE_EXPERIMENTAL_LSP_TOOL=true` |
| **permission** key `lsp` | gates that tool's actions (policies facet) |

## 5. Built-in tools + the `apply_patch` / `edit` trap

Built-in tool names (this is the permission/gating vocabulary): `bash`, `edit`,
`write`, `read`, `grep`, `glob`, `lsp` (experimental), `apply_patch`, `skill`,
`todowrite`, `webfetch`, `websearch`, `question`.

- **`edit`, `write`, and `apply_patch` share ONE `edit` permission** — denying
  `edit` blocks all three. There is no separate `write`/`apply_patch` permission.
- The patch tool is **`apply_patch`**, NOT `patch`. Its argument is
  **`output.args.patchText`** (NOT `filePath`) — relevant when a plugin's
  `tool.execute.before` inspects patch operations. Marker lines
  (`*** Add File:` / `*** Update File:` / `*** Delete File:`) carry relative
  paths inside `patchText`.
- `grep`/`glob` are powered by ripgrep and respect `.gitignore`; add a `.ignore`
  with `!node_modules/` to allow ignored paths.
- `todowrite` is disabled for subagents by default; `websearch` needs Exa
  (`OPENCODE_ENABLE_EXA=1` or the OpenCode provider).

## Assets
- `assets/custom-tool.ts` — minimal standalone tool template.
- `assets/mcp.json` — local + remote MCP server config (note `environment`).
- `assets/lsp.json` — custom + disabled LSP server config (note `env`).
