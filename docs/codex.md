---
icon: lucide/blocks
---

# Codex

How agent-extensions packages skills and MCP integrations for Codex as native plugins.

## Architecture

Codex uses a **marketplace -> plugin -> skills** model that is close to Claude Code, but with native marketplace metadata at `.agents/plugins/marketplace.json`:

```text
.agents/
  plugins/
    marketplace.json        <- Codex marketplace manifest (repo root)

plugins/
  swe/
    .codex-plugin/
      plugin.json           <- plugin manifest
    skills/
      tdd -> ../../../skills/tdd
      go-secure -> ../../../skills/go-secure
  dev-tools/
    .codex-plugin/
      plugin.json
    .mcp.json               <- bundled MCP server config
    scripts/
      run-pi-rpc-mcp.sh
      run-gemini-cli-mcp.sh
```

## How it works

1. **Marketplace manifest** (`.agents/plugins/marketplace.json`) defines the `rdl` marketplace and the six Codex-installable bundles: `swe`, `infra`, `dataops`, `informatics`, `dev-tools`, and `meta`.

2. **Plugin manifests** (`plugins/<bundle>/.codex-plugin/plugin.json`) declare bundle metadata and point Codex at `./skills/`. The `dev-tools` bundle also points at `./.mcp.json`.

3. **Skill symlinks** (`plugins/<bundle>/skills/<name>`) reuse the shared `skills/` submodule. Each entry is a relative symlink back to `../../../skills/<name>`.

4. **Bundled MCP** lives at the plugin root. `plugins/dev-tools/.mcp.json` exposes the prebuilt `pi-rpc` and `gemini-cli` MCP launchers through the same wrapper scripts already shipped for Claude.

    Claude and Codex now share a single `plugins/dev-tools/.mcp.json` at the plugin root. Both hosts execute MCP `command` entries with the plugin root as the working directory, so `./scripts/...` resolves correctly without depending on host-specific env-var expansion (e.g. Claude's `${CLAUDE_PLUGIN_ROOT}`).

5. **Hooks are different in Codex.** Codex discovers hooks from `<repo>/.codex/hooks.json` or `~/.codex/hooks.json`, behind `features.codex_hooks = true`. Hooks are not packaged as plugin components, so the Claude-specific `hooks` bundle is intentionally not exposed in the Codex marketplace.

Codex can also read a Claude-style marketplace at `.claude-plugin/marketplace.json`, but this repo ships a native Codex marketplace so the plugin directory only shows the bundles Codex can actually install.

## Install

### Local development

```bash
git clone git@github.com:nq-rdl/agent-extensions.git
cd agent-extensions
git submodule update --init
codex plugin marketplace add .
codex
/plugins
```

Install the bundles you want from the `RDL Agent Extensions` marketplace, then start a new thread and ask Codex to use them. You can also mention a plugin with `@` or a bundled skill with `$`.

### Remote marketplace

Codex also supports Git-backed marketplace sources:

```bash
codex plugin marketplace add owner/repo
codex plugin marketplace add owner/repo --ref main
```

For this repository, a local checkout is the safest path while the shared `skills/` content continues to live in the git submodule.

## Validation

```bash
# Validate Claude and Codex plugin manifests plus Claude hook configs
bash scripts/validate-plugin-hooks.sh
```
