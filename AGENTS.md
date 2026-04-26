# AGENTS.md

Agent guidance for this repository. Use this alongside the README for project context specific to coding agents.

## Project overview

This repo is a multi-host agent extension catalog. It maintains a single source of truth for reusable agent skills and publishes host-native outputs for Claude Code, Codex, Gemini CLI, pi.dev, and OpenCode. The key constraint: each host has incompatible extension formats, so the repo adapts shared content to native targets rather than inventing a universal format.

## Setup commands

```bash
# Activate git hooks (auto-syncs submodule after checkout/merge)
git config core.hooksPath .githooks

# Hydrate the skills submodule
git submodule sync --recursive && git submodule update --init
```

## Architecture

```
skills/           ← git submodule (nq-rdl/agent-skills) — do not edit here
agents/           ← authored here: one directory per agent; file inside is agent.md
  <name>/
    agent.md
plugins/          ← Claude Code plugins, one per bundle
  <bundle>/
    .claude-plugin/plugin.json
    skills/       ← symlinks into ../../../skills/<skill>
    agents/       ← flat .md symlinks into ../../../agents/<name>/agent.md
.gemini/          ← Gemini CLI native discovery tree
  skills/<name>   ← symlink into ../../skills/<skill>
  agents/<name>.md ← symlink into ../../agents/<name>/agent.md
registry/
  bundles/*.yaml  ← single source of truth: which skills/agents belong to which bundle/target
mcp/
  gemini-cli-go/  ← Go MCP server, wraps Gemini CLI as MCP tools
  pi-rpc-go/      ← Go MCP server, wraps pi.dev RPC via HTTP/ConnectRPC
hooks/            ← Claude Code hook shell scripts + JSON config
.claude-plugin/
  marketplace.json ← Claude Code marketplace manifest (repo root)
```

### How skills and agents flow into plugins

Skills and agents reach each host as **symlinks** into the canonical source under `skills/` (submodule) or `agents/` (authored here). Never copy content — update the source and resymlink.

- **Skills**: `plugins/<bundle>/skills/<skill>` is a directory symlink into `skills/<skill>/` (the submodule). One symlink per skill per bundle.
- **Agents**: `plugins/<bundle>/agents/<name>.md` is a *flat file* symlink into `agents/<name>/agent.md`. Claude Code's plugin spec expects agents as flat `.md` files under `./agents/`, so the symlink flattens the nested source layout.
- **Gemini**: `.gemini/skills/<name>` (directory) and `.gemini/agents/<name>.md` (flat file) mirror the same sources so `gemini extensions link .` at the repo root sees both primitives.

Claude Code and Gemini CLI both follow symlinks during install, so the installed extension is self-contained.

When a bundle YAML references a skill or agent, CI validates that `skills/<name>/` (or `agents/<name>/agent.md`) exists and that every plugin/.gemini symlink resolves. See `scripts/validate-plugins.sh` for the validation logic (the old name `validate-plugin-hooks.sh` is kept as a back-compat symlink).

### Python skills (csv, pdf, xlsx, docx)

These skills call Python directly (no CLI wrapper). Each has a `requirements.txt` and an `ensure-deps.sh` bootstrap script (authored in `nq-rdl/agent-skills`, vendored here via submodule — do not edit). Install `uv` (recommended) or `pixi` (linux-64 only) for the docs environment; neither is required for skill execution.

## Language Policy

| Work type | Language |
|---|---|
| New CLI helper or MCP server | Go (`CGO_ENABLED=0`, prebuilt binaries) |
| File-format or ML skills | Python + `ensure-deps.sh` |
| Documentation-only skill | Markdown |
| New TypeScript | Not permitted in either repo |

MCP servers are authored in `mcp/*-go/` in this repo and distributed as prebuilt binaries under `plugins/<bundle>/bin/mcp/`. See `docs/ARCHITECTURE.md` for the cross-repo scope split.

## MCP Servers

Both MCP servers are Go binaries distributed under `plugins/dev-tools/bin/mcp/`. The plugin wires them via `.claude-plugin/.mcp.json` — no separate install step required.

To build locally:

```bash
cd mcp/pi-rpc-go      # or mcp/gemini-cli-go
make build            # builds for the current platform
make cross-compile DESTDIR=../../plugins/dev-tools/bin/mcp
```

## Build, test, lint

```bash
# Validate all plugin hooks.json, plugin.json, and agents
bash scripts/validate-plugins.sh

# Validate only plugins touched by changed files
bash scripts/validate-plugins.sh plugins/swe/hooks/hooks.json
```

CI runs `validate.yml` on every PR/push to main. It checks:
- Bundle YAML skill references resolve to `skills/<name>/`
- Bundle YAML agent references resolve to `agents/<name>/agent.md`
- All symlinks under `plugins/`, `.gemini/`, `opencode/`, `pidev/` are not broken
- Every `agents/<name>/agent.md` has frontmatter `name` + `description`

## Testing instructions

To verify skills are visible before release, install the repo as a local Claude Code marketplace:

```bash
# Single-session in-place (preferred in devcontainer — no cache copy, symlinks resolve in-place)
claude --plugin-dir ./plugins/swe

# Persistent install (workspace must stay mounted at /workspace)
claude plugin marketplace add /workspace
claude plugin install swe@rdl
```

See [`docs/local-testing.md`](docs/local-testing.md) for the full walkthrough including cleanup and the symlink path caveat.

## Registry Bundles

`registry/bundles/*.yaml` defines what each bundle contains and which targets are enabled. Schema:

```yaml
schemaVersion: v1
id: swe
skills: [tdd, go-secure]      # must exist in skills/ submodule
agents: [debug, janitor]      # must exist in agents/<name>/agent.md
hooks: []
targets:
  claude:
    enabled: true
    pluginName: swe
  gemini:
    enabled: false
```

When adding a skill to a bundle: (1) add it to the YAML, (2) add a directory symlink in `plugins/<bundle>/skills/`.

When adding an agent to a bundle: (1) create `agents/<name>/agent.md`, (2) add it to the YAML `agents:` list, (3) add flat `.md` symlinks in `plugins/<bundle>/agents/<name>.md` and `.gemini/agents/<name>.md`.

## PR instructions

### Changelog

Use `changie` for all changelog entries:

```bash
changie new               # create an unreleased change entry
changie batch auto        # batch unreleased into a version (uses semver from kind)
changie merge             # merge versions into CHANGELOG.md
```

### Release

Releases are triggered by pushing a `v*` tag. The tag must point to a commit already on `main`. The release workflow uses a GitHub App token (`RELEASE_APP_ID` / `RELEASE_APP_PRIVATE_KEY`).

## Docs

The docs site uses Zensical (configured in `zensical.toml`). Source is `docs/`. Architecture decisions live in `docs/ARCHITECTURE.md`. Local install walkthrough: [`docs/local-testing.md`](docs/local-testing.md).

## Platform Notes

- macOS and Linux only — symlink resolution requires native symlink support (WSL2 for Windows)
- `dist/` is generated output — do not hand-edit
- Gemini CLI requires a self-contained extension; monorepo publishing to Gemini is via release archive or mirror repo (Phase 2)
