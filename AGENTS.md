# AGENTS.md

Agent guidance for this repository. Use this alongside the README for project context specific to coding agents.

## Project overview

This repo is a Claude Code agent extension catalog. It maintains a single source of truth for reusable agent skills and agents, and publishes them as self-contained Claude Code plugins through a repo-root marketplace manifest. Canonical content lives once (under `skills/` and `agents/`); each bundle is packaged into `plugins/<bundle>/` as real-file copies so installs are self-contained.

## Setup commands

```bash
# Activate git hooks (changie fragment lint, etc.)
git config core.hooksPath .githooks
```

`skills/` is vendored real content (synced from `nq-rdl/agent-skills` via the `sync-skills.yml` workflow), not a submodule — no `git submodule update` step.

## Architecture

```
skills/           ← canonical skills (synced from nq-rdl/agent-skills) — do not edit
agents/           ← canonical agents (authored here)
  <name>/
    agent.md
plugins/          ← Claude Code plugins, one per bundle (SELF-CONTAINED — real files)
  <bundle>/
    .claude-plugin/plugin.json
    skills/<name>/       ← real-file copy of skills/<name>/
    agents/<name>.md     ← real-file copy of agents/<name>/agent.md
registry/
  bundles/*.yaml  ← single source of truth: which skills/agents belong to which bundle
mcp/
  <name>-go/      ← Go MCP servers, built to plugins/<bundle>/bin/mcp/
hooks/            ← Claude Code hook shell scripts + JSON config
.claude-plugin/
  marketplace.json ← Claude Code marketplace manifest (repo root, points at ./plugins/<bundle>)
```

### How skills and agents flow into plugins

Claude Code installs a plugin by `cp -R`-ing its source directory into a per-user cache. Symlinks survive that copy verbatim, so any link whose target sits *outside* the copied subtree dangles in the cache (this was the cause of issue #83).

To make installs self-contained, `plugins/<bundle>/skills/<name>/` and `plugins/<bundle>/agents/<name>.md` hold **real-file copies** of the canonical content under `skills/` and `agents/`. The canonical source remains the single edit point — the plugin trees are derivative.

- **Edit canonical content** under `skills/<name>/` (vendored from upstream) or `agents/<name>/agent.md` (authored here).
- **Refresh plugin trees** by running `bash scripts/sync-plugins.sh` (or pass a bundle name to scope it). The script reads `registry/bundles/<b>.yaml`, removes any stale copies, and rewrites `plugins/<b>/skills/<name>/` and `plugins/<b>/agents/<name>.md` from the canonical sources.
- **CI** validates that every bundle YAML reference resolves and that every plugin manifest is well-formed. See `scripts/validate-plugins.sh`.

When the upstream skills repo releases, `sync-skills.yml` pulls the new content into `skills/`, runs `sync-plugins.sh`, and opens a PR with both `skills/` and `plugins/` changes in the same commit.

### Python skills (csv, pdf, xlsx, docx)

These skills call Python directly (no CLI wrapper). Each has a `requirements.txt` and an `ensure-deps.sh` bootstrap script (authored in `nq-rdl/agent-skills`, vendored here — do not edit; refresh via `sync-skills.yml`). Install `uv` (recommended) or `pixi` (linux-64 only) for the docs environment; neither is required for skill execution.

## Language Policy

| Work type | Language |
|---|---|
| New CLI helper or MCP server | Go (`CGO_ENABLED=0`, prebuilt binaries) |
| File-format or ML skills | Python + `ensure-deps.sh` |
| Documentation-only skill | Markdown |
| New TypeScript | Not permitted in either repo |

MCP servers are authored in `mcp/*-go/` in this repo and distributed as prebuilt binaries under `plugins/<bundle>/bin/mcp/`. See `docs/ARCHITECTURE.md` for the cross-repo scope split.

## MCP Servers

MCP servers are Go binaries under `mcp/<name>-go/`, cross-compiled into `plugins/dev-tools/bin/mcp/` and wired via the bundle plugin's `.mcp.json` — no separate install step required. The catalog currently ships no MCP servers.

To build locally:

```bash
cd mcp/<name>-go
make build            # builds for the current platform
make cross-compile DESTDIR=../../plugins/dev-tools/bin/mcp
```

## Build, test, lint

```bash
# Validate all plugin hooks.json, plugin.json, and agents
bash scripts/validate-plugins.sh

# Validate only plugins touched by changed files
bash scripts/validate-plugins.sh plugins/swe/hooks/hooks.json

# Refresh plugin trees from canonical skills/ and agents/. Run after
# editing an agent or syncing skills from upstream.
bash scripts/sync-plugins.sh           # all bundles
bash scripts/sync-plugins.sh swe       # one bundle

# Bundle reference + three-way consistency checks (also run by validate.yml)
python3 scripts/check_bundle_refs.py .   # registry refs resolve to skills/ & agents/
python3 scripts/check_consistency.py .   # bundle <-> marketplace.json <-> plugins/ agree

# Unit tests for the pipeline scripts (zero deps beyond python3 + pyyaml)
python3 -m unittest discover -s tests -p 'test_*.py'
```

CI runs `validate.yml` on every PR/push to main. It checks:
- Bundle YAML skill references resolve to `skills/<name>/` (`scripts/check_bundle_refs.py`)
- Bundle YAML agent references resolve to `agents/<name>/agent.md`
- Registry bundles, `marketplace.json`, and `plugins/` dirs stay in lockstep (`scripts/check_consistency.py`)
- Plugin manifests, hooks, skills, and `.mcp.json` wiring are valid (`scripts/validate-plugins.sh`)
- Every `agents/<name>/agent.md` has frontmatter `name` + `description`
- The pipeline scripts' unit tests pass (`tests/`)

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
skills: [go-naming, go-secure] # must exist as skills/<name>/
agents: [debug, janitor]      # must exist as agents/<name>/agent.md
hooks: []
targets:
  claude:
    enabled: true
    pluginName: swe
```

When adding a skill to a bundle: (1) add it to the YAML, (2) run `bash scripts/sync-plugins.sh <bundle>` to copy `skills/<name>/` into `plugins/<bundle>/skills/<name>/`.

When adding an agent to a bundle: (1) create `agents/<name>/agent.md`, (2) add it to the YAML `agents:` list, (3) run `bash scripts/sync-plugins.sh <bundle>` to copy it into `plugins/<bundle>/agents/<name>.md`.

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

The workflow:
1. Verifies the tag is on `main`.
2. Bumps versions across all manifests and commits the bump back to `main`.
3. Moves the tag forward to include the bump commit and creates the GitHub release.

`marketplace.json` sources are relative paths (`./plugins/<bundle>`) — installs read directly from `main` (or whatever ref the user pinned), no separate release branch involved.

## Docs

The docs site uses Zensical (configured in `zensical.toml`). Source is `docs/`. Architecture decisions live in `docs/ARCHITECTURE.md`. Local install walkthrough: [`docs/local-testing.md`](docs/local-testing.md).

## Platform Notes

- macOS and Linux only — symlink resolution requires native symlink support (WSL2 for Windows)
- `dist/` is generated output — do not hand-edit
