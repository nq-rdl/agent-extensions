---
name: opencode-delegate
license: CC-BY-4.0
compatibility: opencode
description: >-
  Build a Claude Code plugin that delegates coding work to OpenCode (SST's open-source
  agent, opencode.ai) — the OpenCode analog of openai/codex-plugin-cc. Maps the
  codex-plugin-cc template (thin bash forwarders → a Node `.mjs` companion holding a
  persistent connection to the OpenCode daemon → a detached background-job store with
  status/result/cancel) onto OpenCode's three drive paths. Use when building a
  CC→OpenCode delegation/handoff plugin, porting codex-plugin-cc to OpenCode, or
  choosing between `opencode acp`, `opencode serve` + `@opencode-ai/sdk`
  (`createOpencodeClient`), and `opencode run --format json --attach
  --dangerously-skip-permissions` as the transport for delegated tasks.
argument-hint: "e.g. 'build a CC plugin that hands a task off to OpenCode and polls for the result'"
user-invocable: true
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

# Delegate to OpenCode from Claude Code

Build a Claude Code plugin that hands work to **OpenCode** (SST; `opencode.ai`,
GitHub `sst/opencode` — **not** OpenAI Codex). This skill teaches *only* OpenCode's
drive paths and how the codex-plugin-cc architecture maps onto them.

> **Verify-canonical guard.** OpenCode's API moves fast and predates the model's
> training cutoff — before writing delegate code, read `references/cli.rst` and
> `references/acp.rst` AND re-check <https://opencode.ai/docs/acp/> (and
> `/docs/cli/`, `/docs/server/`) for drift. The ACP wire protocol is **not** in
> these references — its JSON-RPC method schema lives at
> <https://agentclientprotocol.com>; verify there, don't recall it.

**Scope guard — do NOT re-teach here:**
- Claude Code plugin authoring (`commands/`, subagents, `hooks/`,
  `${CLAUDE_PLUGIN_ROOT}`) → the `claude-code` bundle + `plugin-dev`.
- OpenCode SDK client surface, server endpoints, `GET /doc` OpenAPI → `opencode-dev:sdk`.

This skill is the **delta**: which OpenCode transport to drive, and the
codex-plugin-cc template mapped onto it.

**Version pins** (verify current before authoring): JS packages `@opencode-ai/sdk`,
`@opencode-ai/plugin`; Go module `github.com/sst/opencode-sdk-go` **v0.19.2**, Go
**1.22+** — verify this exact module path (other namesake Go modules exist).

---

## Pick a drive path

OpenCode exposes three ways an external process can drive it. Choose by how the
delegating plugin needs to talk to it:

| Path | Command | Transport | Persistence / sessions | Cancel | When |
|---|---|---|---|---|---|
| **ACP** | `opencode acp` | JSON-RPC over **stdin/stdout, nd-JSON** (newline-delimited) | Persistent subprocess, editor-style threads | protocol-level (see ACP schema) | Richest; closest analog to codex `app-server`. Editors (Zed/JetBrains) already drive it this way. |
| **serve + SDK** | `opencode serve` + `@opencode-ai/sdk` `createOpencodeClient({baseUrl})` | HTTP + **SSE** (`client.event.subscribe`) | Long-lived daemon, multi-session, default `127.0.0.1:4096` | `client.session.abort(...)` | **Best fit for a codex-plugin-cc-style job store.** Most documented, easiest to keep alive. |
| **run (one-shot)** | `opencode run [msg..] --format json` | child process; **raw JSON event stream on stdout** | Stateless per invocation (`--continue`/`--session`/`--fork` to chain) | kill the (detached) pid | Simplest fire-and-forget subprocess. |

**Default recommendation:** start with **serve + SDK**. It is the verifiable,
documented analog of a persistent daemon and gives you a clean `abort`. Reach for
`acp` only if you need ACP's editor-grade thread protocol; reach for `run` for the
simplest possible one-shot.

### codex `app-server` ↔ `opencode acp` — concept-level only

codex-plugin-cc's companion held a persistent JSON-RPC connection to `codex
app-server` (methods like `turn/start`, `turn/resume`, `turn/interrupt`). **Those
are codex methods — they do NOT exist in OpenCode/ACP.** The analogy is structural:
both are persistent JSON-RPC over stdio. OpenCode's `acp` speaks the **Agent Client
Protocol** (Zed's open standard) with its *own* method namespace — get the actual
method names from <https://agentclientprotocol.com>, not from the codex surface.

---

## Drive-path traps (the things a fresh model gets wrong)

- **`--format json` is the streaming opt-in.** `opencode run` defaults to `--format
  default` (formatted, human text). For a companion you parse, you **must** pass
  `--format json` to get "raw JSON events." The event object shape is **not
  documented here** — capture it empirically (run once, log stdout) before parsing;
  don't hardcode an invented shape.
- **`--attach http://localhost:4096` reuses a running `serve`** — verbatim purpose:
  "to avoid MCP server cold boot times on every run." Without `--attach`, each
  `opencode run` spins up its own server (random port via `--port`) and re-boots MCP
  servers. For a delegation plugin doing many runs, **`serve` once + `run --attach`**
  (or the SDK) is the difference between snappy and sluggish.
- **`--dangerously-skip-permissions` auto-approves only permissions that are NOT
  explicitly denied** — `deny` rules in config/agent still block. It is not a
  blanket bypass. A delegated headless run needs this (no TTY to answer prompts), so
  pair it with a tight `permission` policy on the OpenCode side.
- **Basic auth:** set `OPENCODE_SERVER_PASSWORD` on `serve`/`web`; the companion
  passes `--password/-p` (or `OPENCODE_SERVER_PASSWORD`) and `--username/-u`
  (default `opencode`). The SDK client needs the matching credential too.
- **ACP loses `/undo` and `/redo`** (and only those slash commands) — verbatim
  caveat. Everything else (tools, MCP, AGENTS.md rules, agents, permissions) works
  identically over ACP.
- **`createOpencodeClient` (connect-only) vs `createOpencode` (starts server +
  client).** There is **no `createOpencodeServer`** in the SDK — ignore third-party
  material that uses it. Full SDK detail lives in `opencode-dev:sdk`.

---

## The codex-plugin-cc template, mapped onto OpenCode

The thing users clone is a Claude Code plugin whose entire CC-facing surface is
**transport-agnostic**; porting Codex→OpenCode means **swapping only the transport
layer** inside the companion.

```
Claude Code plugin (UNCHANGED across Codex/OpenCode)
  commands/{review,transfer,status,result,cancel,setup}.md   ← thin bash forwarders
  agents/<delegator>.md                                       ← delegation subagent
        │  every command/agent shells out to ONE call:
        ▼
  node "${CLAUDE_PLUGIN_ROOT}/scripts/companion.mjs" <verb> ...
        │
        ▼
  companion.mjs  ← THE ONLY LAYER YOU PORT
     • owns the connection to the OpenCode daemon (swap transport here)
     • spawns a DETACHED worker per task; never blocks Claude Code
     • persists a job store: {id,status,phase,pid,logFile,sessionID,request}
     • verbs: task | status | result | cancel
        │
        ▼
  OpenCode daemon  ← serve+SDK  |  acp  |  run --attach
```

**What stays identical** when porting from codex-plugin-cc: the slash commands, the
delegation subagent, the `${CLAUDE_PLUGIN_ROOT}/scripts/*.mjs` forwarder convention,
the detached-job store with `status`/`result`/`cancel`, and the `/<plugin>:setup`
command that checks/installs the foreign CLI (here: `opencode`; needs Node 18+).

**What you swap** — the companion's transport (pick from the table above):

| codex-plugin-cc | OpenCode equivalent |
|---|---|
| persistent JSON-RPC to `codex app-server` | `opencode serve` + `createOpencodeClient` **(recommended)**, or `opencode acp` (ACP JSON-RPC/stdio) |
| `turn/start` start a turn | SDK `client.session.create` + `client.session.prompt` *(verify signatures in `opencode-dev:sdk` + `GET /doc`)* |
| `turn/interrupt` | SDK `client.session.abort(...)`; for the `run` path, kill the detached pid |
| streamed turn events | SDK `client.event.subscribe()` (SSE), or `run --format json` stdout stream |

### Detached background jobs — the load-bearing pattern

A delegated task must outlive the (synchronous, fast) Claude Code tool call. Spawn
the worker truly detached, record its pid, and poll via separate `status`/`result`
verbs:

```js
const child = spawn(process.execPath, [worker, jobId], {
  detached: true,
  stdio: "ignore",   // or redirect to logFile
});
child.unref();       // REQUIRED — without unref the parent won't exit / job isn't detached
```

Then `status` reads the job-store file; `result` tails `logFile`; `cancel` calls
`client.session.abort(...)` (serve+SDK) or `process.kill(job.pid)` (run path).

See `assets/companion.skeleton.mjs` for a minimal serve+SDK companion and
`assets/delegate-command.md` for a starter forwarder command.

---

## Before you ship

1. Read `references/cli.rst` (every `run`/`serve`/`acp` flag) + `references/acp.rst`
   and confirm flags against your installed `opencode --version`.
2. Decide one drive path; keep the CC-facing surface transport-agnostic so the other
   two remain swap-in options.
3. Capture the real `run --format json` event shape (or the SDK event stream)
   empirically before parsing it.
4. Cross-reference `opencode-dev:sdk` for client signatures and server auth — do not
   re-derive them here.
