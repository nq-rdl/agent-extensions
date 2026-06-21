# AGENTS.md

Agent guidance for this repository. Use this alongside the README for project context specific to coding agents.

## Project overview

This repo is a Claude Code agent extension catalog. It maintains a single source of truth for reusable agent skills and agents, and publishes them as self-contained Claude Code plugins through a repo-root marketplace manifest. Canonical content lives once (under `skills/` and `agents/`); each bundle is packaged into `plugins/<bundle>/` as real-file copies so installs are self-contained.

## Setup commands

```bash
# Activate git hooks (changie fragment lint, etc.)
git config core.hooksPath .githooks
```

`skills/` is canonical content authored in this repo (formerly vendored from `nq-rdl/agent-skills`, now merged here), not a submodule. Skills are validated against the agentskills.io spec by `asctl` — the Go CLI under `tools/asctl/` (`asctl repo-check`).

## Architecture

```
skills/           ← canonical skills (authored here; validated by tools/asctl)
agents/           ← canonical agents (authored here)
  <name>/
    agent.md
plugins/          ← Claude Code plugins, one per bundle (SELF-CONTAINED — real files)
  <bundle>/
    .claude-plugin/plugin.json  ← GENERATED (scripts/generate_manifests.py)
    skills/<leaf>/       ← real-file copy of skills/<source>/ (renamed to <leaf> per the registry map)
    agents/<name>.md     ← real-file copy of agents/<name>/agent.md
registry/
  bundles/*.yaml   ← single source of truth: skills/agents/keywords per bundle
  marketplace.yaml ← marketplace metadata, plugin defaults, display order, external
                     passthrough entries, and the rdl meta-plugin config
VERSION           ← single version source; stamped into every generated manifest
mcp/
  <name>-go/      ← Go MCP servers, built to plugins/<bundle>/bin/mcp/
tools/
  asctl/          ← Go CLI: agentskills.io spec validator for skills/
hooks/            ← Claude Code hook shell scripts + JSON config
.claude-plugin/
  marketplace.json ← GENERATED Claude Code marketplace manifest (repo root)
```

### How skills and agents flow into plugins

Claude Code installs a plugin by `cp -R`-ing its source directory into a per-user cache. Symlinks survive that copy verbatim, so any link whose target sits *outside* the copied subtree dangles in the cache (this was the cause of issue #83).

To make installs self-contained, `plugins/<bundle>/skills/<name>/` and `plugins/<bundle>/agents/<name>.md` hold **real-file copies** of the canonical content under `skills/` and `agents/`. The canonical source remains the single edit point — the plugin trees are derivative.

- **Edit canonical content** under `skills/<name>/` or `agents/<name>/agent.md` (both authored here).
- **Refresh plugin trees** by running `bash scripts/sync-plugins.sh` (or pass a bundle name to scope it). The script reads `registry/bundles/<b>.yaml`, removes any stale copies, and rewrites `plugins/<b>/skills/<name>/` and `plugins/<b>/agents/<name>.md` from the canonical sources.
- **CI** validates that every bundle YAML reference resolves and that every plugin manifest is well-formed. See `scripts/validate-plugins.sh`.

**Grouped skills.** A bundle skill member is either a flat string (`go-gh` → `leaf == go-gh`) or an explicit `{source, leaf}` mapping (`{source: go-gh, leaf: gh}`). `sync-plugins.sh` copies the flat canonical `skills/<source>/` → `plugins/<pluginName>/skills/<leaf>/`, **renaming to the leaf**, so the plugin tree stays one level deep and Claude Code invokes `<pluginName>:<leaf>` (the leaf folder drives invocation). Claude Code labels a skill in `/`-autocomplete as `frontmatter.name || <pluginName>:<leaf>` — so a present `name:` (the upstream `go-gh` **or** the leaf `gh`) overrides the namespaced id with a bare, un-prefixed label, and `/go` lists `go-gh`/`gh` instead of `go:gh`. To get the namespaced label, sync **strips the copy's `name:` entirely** so the label falls back to `<pluginName>:<leaf>`. The canonical `skills/` tree is never touched; grouping is owned **here** in the registry and stays flat. See `CONTRIBUTING.md` §6 for the rules, `scripts/check_grouping.py` for the contract, and `scripts/validate-plugins.sh` for the no-name guard.

Skills and agents are authored directly under `skills/` and `agents/`. After editing one, run `bash scripts/sync-plugins.sh` to refresh the plugin trees; CI's `validate-skills` job runs `asctl repo-check` to validate `skills/` against the agentskills.io spec.

### Python skills (csv, pdf, xlsx, docx)

These skills call Python directly (no CLI wrapper). Each has a `requirements.txt` and an `ensure-deps.sh` bootstrap script. Install `uv` (recommended) or `pixi` (linux-64 only) for the docs environment; neither is required for skill execution.

## Language Policy

| Work type | Language |
|---|---|
| New CLI helper or MCP server | Go (`CGO_ENABLED=0`, prebuilt binaries) |
| File-format or ML skills | Python + `ensure-deps.sh` |
| Documentation-only skill | Markdown |
| New TypeScript | Not permitted |

MCP servers are authored in `mcp/*-go/` and distributed as prebuilt binaries under `plugins/<bundle>/bin/mcp/`. See `docs/ARCHITECTURE.md` for the full language and packaging policy.

## MCP Servers

MCP servers are Go binaries under `mcp/<name>-go/`, cross-compiled into `plugins/<subject>/bin/mcp/` (the subject plugin that wires the server) and referenced via that plugin's `.mcp.json` — no separate install step required. The catalog currently ships no Go MCP servers; the hosted Lucid (`lucid`) and Playwright (`playwright`) servers are wired by URL/command, not as committed binaries.

To build locally:

```bash
cd mcp/<name>-go
make build            # builds for the current platform
make cross-compile DESTDIR=../../plugins/<subject>/bin/mcp
```

## Build, test, lint

```bash
# Validate all plugin hooks.json, plugin.json, and agents
bash scripts/validate-plugins.sh

# Validate only plugins touched by changed files
bash scripts/validate-plugins.sh plugins/hooks/hooks/hooks.json

# Refresh plugin trees from canonical skills/ and agents/. Run after
# editing a skill or agent.
bash scripts/sync-plugins.sh           # all bundles
bash scripts/sync-plugins.sh go        # one bundle

# Regenerate plugin.json + marketplace.json from the registry. These manifests
# are GENERATED — never hand-edit them. Run after changing a bundle's
# description/keywords, marketplace.yaml, or VERSION.
python3 scripts/generate_manifests.py .          # write manifests
python3 scripts/generate_manifests.py . --check  # CI gate: fail on drift

# Regenerate docs/bundles.md from the registry (also a --check CI gate).
python3 scripts/generate_bundles_doc.py .          # write
python3 scripts/generate_bundles_doc.py . --check  # CI gate: fail on drift

# Bundle reference + grouping + three-way consistency checks (also run by validate.yml)
python3 scripts/check_bundle_refs.py .   # registry refs resolve to skills/ & agents/
python3 scripts/check_grouping.py .      # grouping contract: valid member shape, unique leaf + pluginName
python3 scripts/check_consistency.py .   # bundle <-> marketplace.json <-> plugins/ agree

# Unit tests for the pipeline scripts (zero deps beyond python3 + pyyaml)
python3 -m unittest discover -s tests -p 'test_*.py'

# Build + run the skills spec validator (Go), and its unit tests
go -C tools/asctl build -o /tmp/asctl ./cmd/asctl/ && /tmp/asctl repo-check
go -C tools/asctl test ./...
```

CI runs `validate.yml` on every PR/push to main. It checks:
- Bundle YAML skill references resolve to `skills/<name>/` (`scripts/check_bundle_refs.py`)
- Bundle YAML agent references resolve to `agents/<name>/agent.md`
- The skill-grouping contract holds (`scripts/check_grouping.py`)
- Generated `plugin.json` + `marketplace.json` match the registry (`scripts/generate_manifests.py --check`)
- Generated `docs/bundles.md` matches the registry (`scripts/generate_bundles_doc.py --check`)
- Registry bundles, `marketplace.json`, and `plugins/` dirs stay in lockstep (`scripts/check_consistency.py`)
- Plugin manifests, hooks, skills, and `.mcp.json` wiring are valid (`scripts/validate-plugins.sh`)
- Any symlink under `plugins/` resolves (`validate-symlinks` — plugin trees are real-file copies, so this guards against accidental links)
- Every `agents/<name>/agent.md` has frontmatter `name` + `description`
- The pipeline scripts' unit tests pass (`tests/`)
- Skills validate against the agentskills.io spec (`asctl repo-check`, built from `tools/asctl/`)

## Testing instructions

To verify skills are visible before release, install the repo as a local Claude Code marketplace:

```bash
# Single-session in-place (preferred in devcontainer — no cache copy, reads files directly from the working tree)
claude --plugin-dir ./plugins/go

# Persistent install (workspace must stay mounted at /workspace)
claude plugin marketplace add /workspace
claude plugin install go@rdl

# One command installs every subject via the rdl meta-plugin (it declares each
# subject as a dependency). Requires Claude Code ≥ 2.1.110; prune needs ≥ 2.1.121.
claude plugin install rdl@rdl
claude plugin uninstall rdl --prune   # remove the set + orphaned dependencies
```

See [`docs/local-testing.md`](docs/local-testing.md) for the full walkthrough including cleanup and self-contained plugin tree details.

## Registry Bundles

`registry/bundles/*.yaml` defines what each **subject** plugin contains and which targets are
enabled. One bundle = one subject = one plugin (see `CONTRIBUTING.md` for the grouping rules).
Schema:

```yaml
schemaVersion: v1
id: go
displayName: Go
description: Go — idiomatic naming, secure error handling, and GitHub Actions CI/CD  # no trailing period
keywords: [go, naming, security, ci-cd]   # marketplace keywords (generated into the manifests)
skills:                                    # flat <name> (leaf == name), or {source, leaf} to rename
  - {source: go-gh, leaf: gh}              #   → invokes as /go:gh
  - {source: go-naming, leaf: naming}      #   → /go:naming
agents: [go-mcp-expert]                    # must exist as agents/<name>/agent.md (subagent)
hooks: []
prompts: []
mcp: []                                    # wired in plugins/<pluginName>/.mcp.json
targets:
  claude:
    enabled: true
    pluginName: go
    marketplaceName: rdl
```

The bundle's `description` + `keywords` (plus `registry/marketplace.yaml` and `VERSION`) **generate** `plugins/<bundle>/.claude-plugin/plugin.json` and the bundle's `marketplace.json` entry — do not hand-edit those (CI `generate_manifests.py --check` enforces it). After editing a bundle's `description`/`keywords`, run `python3 scripts/generate_manifests.py .`.

When adding a skill to a bundle: (1) add it to the YAML (flat `<name>`, or a `{source, leaf}` map to repackage a flat upstream skill under a new leaf), (2) run `bash scripts/sync-plugins.sh <bundle>` to copy `skills/<source>/` into `plugins/<bundle>/skills/<leaf>/`.

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
2. Batches and merges the changie changelog for the version — idempotent: it skips the batch when `.changes/<version>.md` is already present (e.g. a pre-batched release PR).
3. Writes the release version to `VERSION`, regenerates all manifests from the registry (`scripts/generate_manifests.py`), and commits the result back to `main`.
4. Moves the tag forward to include the bump commit and creates the GitHub release.

`marketplace.json` sources are relative paths (`./plugins/<bundle>`) — installs read directly from `main` (or whatever ref the user pinned), no separate release branch involved.

## Docs

The docs site uses Zensical (configured in `zensical.toml`). Source is `docs/`. Architecture decisions live in `docs/ARCHITECTURE.md`. Local install walkthrough: [`docs/local-testing.md`](docs/local-testing.md).

## Platform Notes

- macOS and Linux only — the build scripts require POSIX shell tooling (WSL2 for Windows)
- Generated outputs (`plugins/` trees, `plugins/*/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `docs/bundles.md`) are produced by the generator scripts — do not hand-edit
