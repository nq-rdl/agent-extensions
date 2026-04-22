# Agent Extensions

Curated reusable agent skills and integrations published in host-native formats. Shared skills live in the `skills/` submodule; host-specific packaging for Claude Code, Codex, Gemini CLI, `pi.dev`, and OpenCode lives in this repository.

## Installation

### Codex

Codex uses a native repo marketplace at `.agents/plugins/marketplace.json` plus bundle-local `.codex-plugin/plugin.json` manifests.

```bash
git clone git@github.com:nq-rdl/agent-extensions.git
cd agent-extensions
git submodule update --init
codex plugin marketplace add .
codex
/plugins
```

Install the bundles you want from the `RDL Agent Extensions` marketplace: `swe`, `infra`, `dataops`, `informatics`, `dev-tools`, and `meta`.

Codex hooks do not package the same way as Claude hooks. Codex discovers hooks from `<repo>/.codex/hooks.json` or `~/.codex/hooks.json`, so the Claude-only `hooks` bundle is not exposed in the Codex marketplace.

See [`docs/codex.md`](docs/codex.md) for the Codex packaging model and bundle layout.

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
