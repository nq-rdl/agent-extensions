# Agent Extensions

Curated reusable agent skills and integrations published in host-native formats. Shared skills live in the `skills/` submodule; host-specific packaging for Claude Code, Codex, Gemini CLI, `pi.dev`, and OpenCode lives in this repository.

## Installation

### Codex

See [`docs/codex.md`](docs/codex.md) for installation, the native Codex marketplace model, and the bundle layout.

### Claude Code

1. Enable the marketplace

```bash
/plugin marketplace add nq-rdl/agent-extensions
```

2. Navigate to `/plugin` and enable bundles

### Gemini CLI

```bash
gemini extensions add nq-rdl/agent-extensions
```

See [`docs/local-testing.md`](docs/local-testing.md) for local/devcontainer install.

### `pi.dev` and OpenCode

_TBA._

## License

- **Code** — [MIT](LICENSE) (Go MCP servers in `mcp/`, shell scripts in `scripts/`, hooks, plugin manifests).
- **Documentation and skill/agent content** — [CC BY 4.0](LICENSE-CC-BY-4.0) (`*.md` files in `agents/`, `docs/`, `skills/`, and the repo root).
