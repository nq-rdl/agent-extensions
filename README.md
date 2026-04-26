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

## Agent File Management

This repo follows two conventions for top-level agent context files. The third one is intentionally different from how most repos handle it:

- `AGENTS.md` — single source of truth for agent contributor guidance.
- `CLAUDE.md` → symlink to `AGENTS.md`. Claude Code loads `CLAUDE.md` as project context; symlinking keeps the two in sync.
- `GEMINI.md` — **not** a symlink, unlike `CLAUDE.md`. This repo is itself a Gemini CLI extension, and `GEMINI.md` is consumed as the extension's published catalog (the bundles, skills, and agents this extension provides) rather than as agent contributor guidance. It is regenerated from `registry/bundles/*.yaml` by `scripts/generate-gemini-extension.sh`, and CI fails if it drifts. To update its content, edit the registry bundles and run the regen script — don't hand-edit.

A second, subtler reason `GEMINI.md` cannot be a symlink: the regen script writes via Python's `Path.write_text()`, which follows symlinks. If `GEMINI.md → AGENTS.md` existed, the next regen would silently overwrite `AGENTS.md` with the bundle catalog.

## License

This repo is **scope-licensed**: code and content carry different licenses (this is *not* an `OR` dual-license — there is no choice; the license depends on the file).

- **Code** — `SPDX-License-Identifier: MIT` — Go MCP servers in `mcp/`, shell scripts in `scripts/`, hooks, plugin manifests. Full text: [LICENSE](LICENSE).
- **Documentation and skill/agent content** — `SPDX-License-Identifier: CC-BY-4.0` — `*.md` files in `agents/`, `docs/`, `skills/`, and the repo root. Full text: [LICENSE-CC-BY-4.0](LICENSE-CC-BY-4.0).
