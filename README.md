# Agent Extensions

Curated reusable agent skills and agents packaged as self-contained plugins. Claude Code publishes the complete catalog; Codex publishes a skill-only pilot. Canonical skills live under `skills/` and agents under `agents/`, while generated manifests expose target-supported bundles from `plugins/`.

## Installation

### Claude Code

```bash
# Add the marketplace (once)
/plugin marketplace add nq-rdl/agent-extensions

# Install a single subject
/plugin install go@rdl-agent-extensions

# Onboarding: install the rdl-team plugin
/plugin install rdl-team@rdl-agent-extensions
```

See [`docs/bundles.md`](docs/bundles.md) for the full subject list.

### Codex

```bash
# Add the native marketplace (once)
codex plugin marketplace add nq-rdl/agent-extensions

# List and install a Codex-enabled subject
codex plugin list --marketplace rdl-agent-extensions --available --json
codex plugin add go@rdl-agent-extensions --json
```

The initial Codex catalog contains `go`, `rust`, `shiny`, `quarto`, and `obsidian`. See [`docs/codex.md`](docs/codex.md) for verification commands and current limitations.

## Agent File Management

This repo keeps a single source of truth for top-level agent context files:

- `AGENTS.md` — single source of truth for agent contributor guidance.
- `CLAUDE.md` → symlink to `AGENTS.md`. Claude Code loads `CLAUDE.md` as project context; symlinking keeps the two in sync.

## License

This repo is **scope-licensed** (not an `OR` dual-license — the license depends on the file, not the user's choice):

- **Software** — `SPDX-License-Identifier: MIT`. Full text: [LICENSE](LICENSE).
- **Media** — `SPDX-License-Identifier: CC-BY-4.0`. Full text: [LICENSE-CC-BY-4.0](LICENSE-CC-BY-4.0).
