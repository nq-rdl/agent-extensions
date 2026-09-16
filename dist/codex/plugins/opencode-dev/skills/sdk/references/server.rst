<!-- Source: https://opencode.ai/docs/server/ — fetched 2026-06-29. Canonical truth; verify here (and re-check the live page for drift) before authoring OpenCode sdk code. -->

# OpenCode Server

OpenCode Server is a headless HTTP service that exposes an OpenAPI endpoint for programmatic interaction. The `opencode serve` command starts this server.

## Usage

```
opencode serve [--port <number>] [--hostname <string>] [--cors <origin>]
```

### Options

| Flag | Description | Default |
|------|-------------|---------|
| `--port` | Port to listen on | `4096` |
| `--hostname` | Hostname to listen on | `127.0.0.1` |
| `--mdns` | Enable mDNS discovery | `false` |
| `--mdns-domain` | Custom domain name for mDNS service | `opencode.local` |
| `--cors` | Additional browser origins to allow | `[]` |

Pass `--cors` multiple times for multiple origins:

```
opencode serve --cors http://localhost:5173 --cors https://app.example.com
```

## Authentication

Set environment variables to protect the server:
- `OPENCODE_SERVER_PASSWORD` — required password
- `OPENCODE_SERVER_USERNAME` — defaults to `opencode`

```
OPENCODE_SERVER_PASSWORD=your-password opencode serve
```

## API Specification

Access the OpenAPI 3.1 spec at: `http://<hostname>:<port>/doc`

## Core API Endpoints

### Global
- `GET /global/health` — Server health/version
- `GET /global/event` — Global events (SSE stream)

### Project
- `GET /project` — List all projects
- `GET /project/current` — Current project

### Path & VCS
- `GET /path` — Current path
- `GET /vcs` — VCS info

### Config
- `GET /config` — Get config
- `PATCH /config` — Update config
- `GET /config/providers` — List providers

### Provider
- `GET /provider` — List providers
- `GET /provider/auth` — Auth methods
- `POST /provider/{id}/oauth/authorize` — OAuth authorization
- `POST /provider/{id}/oauth/callback` — OAuth callback

### Sessions
- `GET /session` — List sessions
- `POST /session` — Create session
- `GET /session/:id` — Get session
- `DELETE /session/:id` — Delete session
- `PATCH /session/:id` — Update session
- `POST /session/:id/abort` — Abort session
- `POST /session/:id/fork` — Fork session
- `POST /session/:id/init` — Initialize/analyze app
- `GET /session/:id/diff` — Get session diff
- `POST /session/:id/share` — Share session
- `DELETE /session/:id/share` — Unshare session
- `POST /session/:id/revert` — Revert message
- `POST /session/:id/unrevert` — Restore reverted messages

### Messages
- `GET /session/:id/message` — List messages
- `POST /session/:id/message` — Send message (wait for response)
- `GET /session/:id/message/:messageID` — Get message
- `POST /session/:id/prompt_async` — Send async message
- `POST /session/:id/command` — Execute slash command
- `POST /session/:id/shell` — Run shell command

### Commands
- `GET /command` — List all commands

### Files
- `GET /find?pattern=<pat>` — Search text in files
- `GET /find/file?query=<q>` — Find files/directories
- `GET /find/symbol?query=<q>` — Find workspace symbols
- `GET /file?path=<path>` — List files
- `GET /file/content?path=<p>` — Read file
- `GET /file/status` — Get tracked file status

### Tools (Experimental)
- `GET /experimental/tool/ids` — List tool IDs
- `GET /experimental/tool?provider=<p>&model=<m>` — List tools with schemas

### LSP, Formatters & MCP
- `GET /lsp` — LSP server status
- `GET /formatter` — Formatter status
- `GET /mcp` — MCP server status
- `POST /mcp` — Add MCP server dynamically

### Agents
- `GET /agent` — List available agents

### Logging
- `POST /log` — Write log entry

### TUI
- `POST /tui/append-prompt` — Append prompt text
- `POST /tui/submit-prompt` — Submit prompt
- `POST /tui/clear-prompt` — Clear prompt
- `POST /tui/execute-command` — Execute command
- `POST /tui/show-toast` — Show notification
- `POST /tui/open-help` — Open help
- `POST /tui/open-sessions` — Open session selector
- `POST /tui/open-themes` — Open theme selector
- `POST /tui/open-models` — Open model selector

### Auth
- `PUT /auth/:id` — Set authentication credentials

### Events
- `GET /event` — Server-sent events stream
