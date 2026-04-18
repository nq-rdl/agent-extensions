# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Purpose

This repo is a multi-host agent extension catalog. It maintains a single source of truth for reusable agent skills and publishes host-native outputs for Claude Code, Gemini CLI, pi.dev, and OpenCode. The key constraint: each host has incompatible extension formats, so the repo adapts shared content to native targets rather than inventing a universal format.

## Setup

```bash
# Activate git hooks (auto-syncs submodule after checkout/merge)
git config core.hooksPath .githooks

# Hydrate the skills submodule
git submodule sync --recursive && git submodule update --init
```

## Architecture

```
skills/           ← git submodule (nq-rdl/agent-skills) — do not edit here
plugins/          ← Claude Code plugins, one per bundle
  <bundle>/
    .claude-plugin/plugin.json
    skills/       ← symlinks into ../../skills/<skill>
registry/
  bundles/*.yaml  ← single source of truth: which skills belong to which bundle/target
mcp/
  gemini-cli-go/  ← Go MCP server, wraps Gemini CLI as MCP tools
  pi-rpc-go/      ← Go MCP server, wraps pi.dev RPC via HTTP/ConnectRPC
hooks/            ← Claude Code hook shell scripts + JSON config
.claude-plugin/
  marketplace.json ← Claude Code marketplace manifest (repo root)
```

### How skills flow into plugins

Skills in `plugins/<bundle>/skills/` are **symlinks** into `skills/<skill>/`. Never copy skill content — update the submodule and resymlink. Claude Code follows symlinks during install, so the installed plugin is self-contained.

When a bundle YAML references a skill, CI validates that `skills/<skill>/` exists and that plugin symlinks resolve. See `scripts/validate-plugin-hooks.sh` for the hooks validation logic.

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

## Validation

```bash
# Validate all plugin hooks.json and plugin.json files
bash scripts/validate-plugin-hooks.sh

# Validate only plugins touched by changed files
bash scripts/validate-plugin-hooks.sh plugins/swe/hooks/hooks.json
```

CI runs `validate.yml` on every PR/push to main. It checks:
- Bundle YAML skill references resolve to `skills/<name>/`
- All symlinks under `plugins/`, `opencode/`, `pidev/` are not broken

## Registry Bundles

`registry/bundles/*.yaml` defines what each bundle contains and which targets are enabled. Schema:

```yaml
schemaVersion: v1
id: swe
skills: [tdd, go-secure]      # must exist in skills/ submodule
hooks: []
targets:
  claude:
    enabled: true
    pluginName: swe
  gemini:
    enabled: false
```

When adding a skill to a bundle: (1) add it to the YAML, (2) add a symlink in `plugins/<bundle>/skills/`.

## Changelog

Use `changie` for all changelog entries:

```bash
changie new               # create an unreleased change entry
changie batch auto        # batch unreleased into a version (uses semver from kind)
changie merge             # merge versions into CHANGELOG.md
```

## Release

Releases are triggered by pushing a `v*` tag. The tag must point to a commit already on `main`. The release workflow uses a GitHub App token (`RELEASE_APP_ID` / `RELEASE_APP_PRIVATE_KEY`).

## Docs

The docs site uses Zensical (configured in `zensical.toml`). Source is `docs/`. Architecture decisions live in `docs/ARCHITECTURE.md`.

## Platform Notes

- macOS and Linux only — symlink resolution requires native symlink support (WSL2 for Windows)
- `dist/` is generated output — do not hand-edit
- Gemini CLI requires a self-contained extension; monorepo publishing to Gemini is via release archive or mirror repo (Phase 2)
