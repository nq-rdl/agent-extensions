---
license: CC-BY-4.0
compatibility: opencode
description: >-
  Author OpenCode plugins and hooks — JS/TS modules that hook into OpenCode's
  lifecycle to block tools, mutate args, inject env, react to events, or register
  custom tools. Use when building or debugging anything under `.opencode/plugins/`,
  importing `@opencode-ai/plugin`, writing a `tool.execute.before` /
  `tool.execute.after` / `permission.ask` / `shell.env` / `command.execute.before`
  handler, subscribing to OpenCode events via the `event` handler (`session.idle`,
  `command.executed`), registering a custom tool from a plugin, or looking for an
  OpenCode "stop hook" or a settings.json hook table. Distinct from OpenAI Codex.
argument-hint: "What OpenCode plugin/hook do you want? (e.g. 'block reads of .env', 'notify when a session finishes', 'add a custom tool from a plugin')"
user-invocable: true
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

# OpenCode Plugins & Hooks

OpenCode (SST's open-source coding agent, `opencode.ai`, `sst/opencode` — **not**
OpenAI Codex) extends via **plugins**: a JS/TS module exporting
`async (input, options?) => Promise<Hooks>`. There is **no settings-file hook
table like Claude Code** — "hooks" exist *only* as keys of the object your plugin
returns. Get the vocabulary layering right and most plugins are a few lines.

> **Verify-canonical guard.** OpenCode's API moves fast and predates the model's
> training cutoff — before writing plugin code, read `references/plugins.rst` AND
> re-check <https://opencode.ai/docs/plugins/> for drift. The handler-key set is
> defined in `interface Hooks` (`packages/plugin/src/index.ts`).

**Version pins.** Packages `@opencode-ai/plugin` (types + `tool` helper) and
`@opencode-ai/sdk` (the `client`). The `interface Hooks` key set and field names
encoded below were validated against `references/plugins.rst` as fetched
**2026-06-29**; re-check that baseline for drift before pinning a version. SDK/Go
specifics (Go SDK `v0.19.2`, Go 1.22+) belong to the **sdk** facet, not here.

---

## The one trap that breaks most plugins: handlers vs. events

The docs print a single **"Events"** list that silently mixes two different
layers. They share nouns but differ in **tense and access mechanism**:

| Layer | How you use it | Tense | Examples |
|---|---|---|---|
| **Handler keys you RETURN** | top-level keys of the returned object; called with `(input, output)` | **imperative** | `tool.execute.before`, `tool.execute.after`, `permission.ask`, `command.execute.before`, `shell.env`, `chat.message` |
| **Bus events you READ** | only inside the `event` handler, via `event.type` | **past-tense / `.updated` / `.idle`** | `command.executed`, `session.idle`, `session.updated`, `permission.asked`, `file.edited`, `lsp.updated` |

Same word, two layers: `command.execute.before` is a **handler key** you return;
`command.executed` is an **`event.type`** you match. `permission.ask` is a handler;
`permission.asked` is an event. Never write `event: { "session.idle": ... }` — the
`event` handler is one function that switches on `event.type`.

```js
return {
  "command.execute.before": async (input, output) => { /* imperative handler */ },
  event: async ({ event }) => {                          // bus reader
    if (event.type === "session.idle") { /* … */ }
  },
}
```

## Full handler-key set (`interface Hooks`)

Returnable keys, all optional: `dispose`, `event`, `config`, `tool` (a **map**,
not a function), `auth`, `provider`, `chat.message`, `chat.params`, `chat.headers`,
`permission.ask`, `command.execute.before`, `tool.execute.before`,
`tool.execute.after`, `shell.env`, `tool.definition`, and experimental
`experimental.{chat.messages.transform, chat.system.transform, provider.small_model,
session.compacting, compaction.autocontinue, text.complete}`.

- **There is no `stop` hook** — a community gist invents one; it does not exist.
  For "session finished," read `event` + `event.type === "session.idle"`.
- There is **`command.execute.before`** but no `command.execute.after` handler —
  the after-the-fact signal is the `command.executed` *event*.

## The `(input, output)` contract

Imperative handlers receive two args: **`input` is read-only; mutate `output` in
place; `throw` to block** the action.

| Handler | `input` (read) | `output` (mutate) | Block by |
|---|---|---|---|
| `tool.execute.before` | `{ tool, sessionID, callID }` | `{ args }` | `throw` |
| `tool.execute.after` | `{ tool, … }` | `{ title, output, metadata }` | — |
| `permission.ask` | the `Permission` | `{ status: "ask" \| "deny" \| "allow" }` | set `status` |
| `shell.env` | `{ cwd, … }` | `{ env }` | — |
| `command.execute.before` | command info | command args | `throw` |
| `tool.definition` | tool id | `{ description, parameters }` | — |

Gotcha: the field is `output.args`, keyed by tool. For `read` it's
`output.args.filePath`; for the **`apply_patch`** tool it's `output.args.patchText`
(there is no `filePath`). Don't assume a uniform arg shape.

## Where plugins live, and how they load

- **Plural** `.opencode/plugins/` (project) or `~/.config/opencode/plugins/`
  (global) — auto-loaded at startup. (A widely-copied community gist writes the
  singular `.opencode/plugin/`; that is **wrong** and silently loads nothing.)
- **npm packages** via the config `"plugin": [...]` array — Bun-installed to
  `~/.cache/opencode/node_modules/`. Both bare and `@scoped` names work.
- **Local runtime deps**: add `.opencode/package.json`; OpenCode runs `bun install`
  at startup, then your plugin/tool can `import` them.

## PluginInput — the context you destructure

`PluginInput` is `{ client, project, directory, worktree, serverUrl, $ }` (plus
`experimental_workspace`). Two non-obvious points: `$` is **Bun's shell**, and to
log you must use the SDK client — `client.app.log({ body: { service, level,
message, extra } })`, level `debug|info|warn|error` — **not** `console.log`, which
is swallowed.

## Registering a custom tool from a plugin

The `tool` key is a **map** (`{ name: tool(...) }`), not a function — `import
{ tool } from "@opencode-ai/plugin"`, build arg schemas off `tool.schema.*`. A
plugin tool whose name matches a built-in **takes precedence**.

> This is the *programmatic* route. Filesystem-discovered custom tools in
> `.opencode/tools/*.ts` and the full `tool()` API are the **tools** facet
> (`/opencode-dev:tools`) — cross-reference, don't duplicate.

---

## Recipes (full code in `references/plugins.rst`)

| Goal | Key | Sketch |
|---|---|---|
| Block reading `.env` | `tool.execute.before` | `if (input.tool === "read" && output.args.filePath.includes(".env")) throw …` |
| Sanitize bash args | `tool.execute.before` | mutate `output.args.command` (e.g. `shescape`) |
| Notify on session done | `event` | `if (event.type === "session.idle") await $\`…\`` |
| Inject shell env | `shell.env` | `output.env.MY_API_KEY = "…"` |
| Persist context across compaction | `experimental.session.compacting` | `output.context.push("…")` or set `output.prompt` |
| Add a custom tool | `tool` map | `tool({ description, args, execute })` |

Starter scaffold pairing one imperative handler with the `event` reader:
[`assets/starter-plugin.ts`](assets/starter-plugin.ts).

## Reference files

| File | Contents |
|---|---|
| [references/plugins.rst](references/plugins.rst) | Verbatim `/docs/plugins/` (load order, all examples, logging, compaction) + the `interface Hooks` key set and `PluginInput` type surface |
