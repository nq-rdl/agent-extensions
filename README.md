# Agent Extensions

Curated reusable agent skills packaged as self-contained plugins. Claude Code and Codex publish the complete catalog as separate target packages. Canonical skills and optional delegation outlines live under `skills/`, while generated manifests expose target-supported bundles from `plugins/` (Claude) and `dist/codex/plugins/` (Codex).

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

The Codex catalog includes all 36 bundles, with strict skill names, MCP integrations, and native command hooks. See [`docs/codex.md`](docs/codex.md) for verification commands and current limitations.

To invoke an installed skill in Codex, type `$` to select it. Add your request after the skill mention.
For example, the installed `git` plugin provides `$git:pr-comments <PR URL>` in the Codex composer.
The CLI also provides `/skills`. Refer to [Invoking skills](docs/codex.md#invoking-skills)
for desktop menu behaviour and differences from Claude Code slash commands.

See [Delegation](docs/delegation.md) for optional subagent execution and migrated agent names.

## Agent File Management

This repo keeps a single source of truth for top-level agent context files:

- `AGENTS.md` — single source of truth for agent contributor guidance.
- `CLAUDE.md` → symlink to `AGENTS.md`. Claude Code loads `CLAUDE.md` as project context; symlinking keeps the two in sync.

## License

This repo is **scope-licensed** (not an `OR` dual-license — the license depends on the file, not the user's choice):

- **Software** — `SPDX-License-Identifier: MIT`. Full text: [LICENSE](LICENSE).
- **Media** — `SPDX-License-Identifier: CC-BY-4.0`. Full text: [LICENSE-CC-BY-4.0](LICENSE-CC-BY-4.0).
