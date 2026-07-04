# Agent Extensions

Curated reusable agent skills and agents packaged as Claude Code plugins. Each **subject** (a tool, library, language, or workflow) is one plugin: skills are invoked as `/<subject>:<facet>` (e.g. `/go:secure`, `/gh:send-pr`) and agents are delegated as subagents. Canonical skills live under `skills/` and agents under `agents/`; each subject is published as a self-contained plugin under `plugins/`, listed in the repo-root marketplace manifest (`.claude-plugin/marketplace.json`).

Claude Code is the only publication target.

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

## Agent File Management

This repo keeps a single source of truth for top-level agent context files:

- `AGENTS.md` — single source of truth for agent contributor guidance.
- `CLAUDE.md` → symlink to `AGENTS.md`. Claude Code loads `CLAUDE.md` as project context; symlinking keeps the two in sync.

## License

This repo is **scope-licensed** (not an `OR` dual-license — the license depends on the file, not the user's choice):

- **Software** — `SPDX-License-Identifier: MIT`. Full text: [LICENSE](LICENSE).
- **Media** — `SPDX-License-Identifier: CC-BY-4.0`. Full text: [LICENSE-CC-BY-4.0](LICENSE-CC-BY-4.0).
