<!-- Source: https://opencode.ai/docs/lsp/ — fetched 2026-06-29. Canonical truth; verify here (and re-check the live page for drift) before authoring OpenCode tools code. -->

# LSP Servers Configuration Guide

## Overview
OpenCode integrates with Language Server Protocol servers to provide diagnostics feedback for agents. The feature is disabled by default.

## Built-in LSP Servers

OpenCode includes 30+ pre-configured LSP servers for languages including:

- **JavaScript/TypeScript**: typescript, eslint, deno
- **Python**: pyright
- **Rust**: rust-analyzer
- **Go**: gopls
- **Java**: jdtls
- **C/C++**: clangd
- **PHP**: intelephense
- **Ruby**: ruby-lsp
- **And many others** (Astro, Bash, C#, Clojure, Dart, Elixir, F#, Gleam, Haskell, Kotlin, Lua, Nix, OCaml, Prisma, Razor, Svelte, Vue, YAML, Zig)

Each server has specific file extensions and requirements listed in the documentation table.
(Note: the fetch summarized the per-language extension/requirement table; re-check the
live page for the full table when wiring a built-in server.)

## Configuration

### Enable All Built-in Servers
```json
{
  "$schema": "https://opencode.ai/config.json",
  "lsp": true
}
```

### Custom Configuration
```json
{
  "$schema": "https://opencode.ai/config.json",
  "lsp": {}
}
```

### Server Entry Properties

| Property | Type | Purpose |
|----------|------|---------|
| `disabled` | boolean | Disable specific server |
| `command` | string[] | Command to start server |
| `extensions` | string[] | File extensions handled |
| `env` | object | Environment variables |
| `initialization` | object | LSP initialization options |

### Environment Variables Example
```json
{
  "lsp": {
    "rust": {
      "command": ["rust-analyzer"],
      "env": {
        "RUST_LOG": "debug"
      }
    }
  }
}
```

### Custom LSP Server
```json
{
  "lsp": {
    "custom-lsp": {
      "command": ["custom-lsp-server", "--stdio"],
      "extensions": [".custom"]
    }
  }
}
```

### Disable Servers
```json
{
  "lsp": false
}
```

Or disable specific server:
```json
{
  "lsp": {
    "typescript": {
      "disabled": true
    }
  }
}
```

## PHP Intelephense License

Place license key in text file at:
- **macOS/Linux**: `$HOME/intelephense/license.txt`
- **Windows**: `%USERPROFILE%/intelephense/license.txt`

File should contain only the license key.

## Auto-download

Suppress LSP server auto-download with `OPENCODE_DISABLE_LSP_DOWNLOAD=true`.
