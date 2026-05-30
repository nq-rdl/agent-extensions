# Agent Extensions

Curated reusable agent skills and integrations packaged as Claude Code plugins. Canonical skills live under `skills/` and agents under `agents/`; each bundle is published as a self-contained plugin under `plugins/`, listed in the repo-root Claude Code marketplace manifest (`.claude-plugin/marketplace.json`).

> Other hosts (Codex, OpenCode, pi.dev) are not currently published from this repo — they require external CLI or packaging tooling rather than an in-host `/plugin` install.

## Installation

### Claude Code

1. Enable the marketplace

```bash
/plugin marketplace add nq-rdl/agent-extensions
```

2. Navigate to `/plugin` and enable bundles

See [`docs/local-testing.md`](docs/local-testing.md) for local/devcontainer install.

## Agent File Management

This repo keeps a single source of truth for top-level agent context files:

- `AGENTS.md` — single source of truth for agent contributor guidance.
- `CLAUDE.md` → symlink to `AGENTS.md`. Claude Code loads `CLAUDE.md` as project context; symlinking keeps the two in sync.

## License

This repo is **scope-licensed** (not an `OR` dual-license — the license depends on the file, not the user's choice):

- **Software** — `SPDX-License-Identifier: MIT`. Full text: [LICENSE](LICENSE).
- **Media** — `SPDX-License-Identifier: CC-BY-4.0`. Full text: [LICENSE-CC-BY-4.0](LICENSE-CC-BY-4.0).
