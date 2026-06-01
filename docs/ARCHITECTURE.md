---
icon: lucide/network
---

# Architecture

This repository is a **Claude Code extension catalog**. It keeps a single source of truth for reusable agent behavior — *skills* and *agents* — and publishes them as self-contained Claude Code plugins through a repo-root marketplace manifest.

> Other hosts (Codex, OpenCode, pi.dev) are **not** publication targets. They use external CLI or packaging tooling rather than Claude Code's `/plugin` marketplace model, so they belong in CLI- or package-driven repos, not here.

## Problem statement

We want one place to author and version reusable agent extensions, and a deterministic way to ship them to Claude Code users.

What is authored once and reused:

- **Skills** written as `SKILL.md` (managed upstream in [`nq-rdl/agent-skills`](https://github.com/nq-rdl/agent-skills), vendored here as real files)
- **Agents** written as `agent.md` (authored in this repo)
- Reference material colocated with each skill/agent
- MCP server integrations
- Bundle and release metadata

What is derived:

- The per-plugin trees under `plugins/<bundle>/` — real-file copies of the canonical skills and agents, refreshed by a script.

The repository's core decision is that **the canonical content lives once and the plugin trees are generated from it**, so there is exactly one edit point per skill or agent.

## Repository layout

```text
skills/                    ← canonical skills (vendored from nq-rdl/agent-skills) — do not edit here
agents/                    ← canonical agents (authored here)
  <name>/
    agent.md
    references/            ← optional colocated reference material

hooks/                     ← Claude Code hook scripts + JSON config (authored here)
mcp/                       ← Go MCP servers (authored here; none currently)

registry/
  bundles/*.yaml           ← single source of truth: which skills/agents/hooks/mcp each bundle ships

.claude-plugin/
  marketplace.json         ← Claude Code marketplace manifest (repo root)

plugins/                   ← Claude Code plugins, one per bundle (SELF-CONTAINED — real files)
  <bundle>/
    .claude-plugin/plugin.json
    skills/<name>/         ← real-file copy of skills/<name>/
    agents/<name>.md       ← real-file copy of agents/<name>/agent.md
    bin/mcp/               ← prebuilt MCP server binaries
    .mcp.json              ← MCP server wiring
```

## Why plugin trees hold real-file copies

Claude Code installs a plugin by `cp -R`-ing its source directory into a per-user cache. Symlinks survive that copy *verbatim*, so any link whose target sits **outside** the copied subtree dangles in the cache. This was the root cause of issue #83.

To make installs self-contained, `plugins/<bundle>/skills/<name>/` and `plugins/<bundle>/agents/<name>.md` hold **real-file copies** of the canonical content. The canonical source under `skills/` and `agents/` remains the single edit point; the plugin trees are derivative and rebuilt by `scripts/sync-plugins.sh`.

- **Edit canonical content** under `skills/<name>/` (vendored — file bugs/PRs upstream) or `agents/<name>/agent.md` (authored here).
- **Refresh plugin trees** with `bash scripts/sync-plugins.sh` (optionally scoped to a bundle). The script reads `registry/bundles/<b>.yaml`, prunes stale copies, and rewrites the plugin tree from the canonical sources.

## Skills sync

`skills/` is real content vendored from `nq-rdl/agent-skills`. Two mechanisms keep it fresh.

### `sync-skills.yml` — scheduled and on release

Runs weekly, on `workflow_dispatch`, and on a `repository_dispatch` fired by an agent-skills release. It clones agent-skills at the latest release tag, replaces `skills/`, runs `scripts/sync-plugins.sh`, and opens a PR.

**Decoupling (resilience):** the registry in this repo names skills/agents by upstream directory name. When upstream renames or removes a skill, that registry reference goes stale. To prevent a stale reference from silently blocking the entire sync (the failure mode behind a multi-week sync outage), `sync-plugins.sh` **never aborts** on a missing source — it emits a `::warning::` and skips that entry, so the skills PR always opens. The authoritative gate is `validate.yml`'s `validate-bundles` job, which fails the PR until a human reconciles the registry in the same change. `sync-skills.yml` also opens/updates a tracking issue if the workflow fails, so breakage is never silent.

### `validate.yml` — on every PR / push to main

- `validate-bundles`: every skill in a bundle YAML resolves to `skills/<name>/`, every agent to `agents/<name>/agent.md`.
- `validate-symlinks`: any symlink under `plugins/` resolves (plugin trees are real-file copies, so this is a guardrail against accidental links).
- `validate-plugins`: plugin manifests (`plugin.json`), hooks, and `.mcp.json` wiring are well-formed (`scripts/validate-plugins.sh`).
- `validate-mcp-servers`: the Go MCP servers under `mcp/*-go/` build and vet.

## Registry schema

The registry describes installable bundles, not raw files.

```yaml
schemaVersion: v1
id: swe
displayName: SWE
description: Software engineering workflows and coding assistance.
owners:
  - rdl
channels:
  - stable
skills:                        # resolved from skills/<name>/
  - go-naming
  - go-secure
agents:                        # resolved from agents/<name>/agent.md
  - debug
  - janitor
hooks: []                      # resolved from hooks/
prompts: []
mcp:                           # wired into the plugin's .mcp.json
  - playwright
targets:
  claude:
    enabled: true
    pluginName: swe
    marketplaceName: rdl
```

Required behavior:

- A bundle maps to one Claude Code plugin. `targets.claude.enabled: false` disables a bundle without deleting it.
- Skills and agents are referenced by name and resolved from `skills/` and `agents/`. Hooks, prompts, and MCP integrations resolve from their respective root-level directories.

## Agents primitive

Agents are the second authored primitive (alongside skills). They live at `agents/<name>/agent.md` and flow into plugins as flat `.md` real-file copies.

A skill is knowledge that activates contextually; an agent is a delegatable role with a focused tool allowlist and system prompt that Claude Code auto-routes on its `description`. The two are orthogonal: an agent may preload skills via frontmatter, but neither requires the other.

`agents/` is authored and versioned in **this** repo (not vendored from agent-skills), alongside hooks, prompts, and MCP servers.

### Frontmatter schema

```yaml
---
name: <kebab-case>
description: >-
  <delegation trigger; first sentence is Claude Code's match target>
license: MIT
tools:
  - Read            # Read, Edit, Grep, Bash, Write, …
model: inherit       # 'inherit' | 'opus' | 'sonnet' | 'haiku'
maxTurns: 30
skills: []           # optional preload
color: blue          # optional UI hint
metadata:
  upstream: https://…            # attribution link for forks
  repo: https://github.com/nq-rdl/agent-extensions
---
```

### Flow into plugins

| Discovery path | Shape |
|---|---|
| `plugins/<bundle>/agents/<name>.md` (convention-based; no manifest declaration) | flat `.md` real-file copy of `agents/<name>/agent.md`, refreshed by `scripts/sync-plugins.sh` |

The nested source layout (`agents/<name>/agent.md`) exists so future per-agent `references/` sibling directories have a home.

### Attribution

Agents derived from external sources (e.g. `github/awesome-copilot`, MIT) carry two forms of attribution: `metadata.upstream: <url>` in the frontmatter (machine-readable, used to diff against origin), and an HTML comment block at the top of the body naming the upstream license and any conversion steps.

## Language policy

### Cross-repo scope split

| Asset | Authored in | Distributed from |
|---|---|---|
| `mcp/*-go/` Go MCP servers | this repo | this repo (prebuilt binaries in `plugins/*/bin/mcp/`) |
| `skills/*/scripts/` Go/Python tools | `nq-rdl/agent-skills` | vendored here |
| `skills/{csv,docx,pdf,xlsx}/scripts/` | `nq-rdl/agent-skills` | run in-place via `ensure-deps.sh` |
| `plugins/dev-tools/bin/` prebuilt binaries | this repo | committed here, rebuilt by CI |
| `registry/bundles/*.yaml` | this repo | this repo |

**Important:** the `skills/` tree is owned by `nq-rdl/agent-skills`. Edits made here are overwritten on the next `sync-skills` PR — file bugs and PRs upstream.

### Per-language rules

| Work type | Language | Rationale |
|---|---|---|
| New CLI helper or MCP server | Go (`CGO_ENABLED=0`, `GOOS`/`GOARCH` matrix) | Zero-install prebuilt binaries; no runtime dep on Node |
| File-format or ML skill | Python + `ensure-deps.sh` | Direct library access; bootstrapping handled by the script |
| Documentation-only skill | Markdown | No execution needed |
| Plugin wiring | JSON/YAML/shell | Manifests and glue only |
| New TypeScript | Not permitted | Bun hard-dependency, no CI, no binary output path |

### Go house style

MCP servers in `mcp/*-go/` follow a Makefile with a `cross-compile` target that produces `$(DESTDIR)/<name>-<os>-<arch>` binaries (`CGO_ENABLED=0`, `-X main.version=$(git describe)` ldflags).

### Python / pixi

`pixi` is optional — its only role here is a reproducible docs environment (`zensical`) on linux-64. The `pixi.lock` is linux-64 only; macOS contributors use `uv`. Python skill `ensure-deps.sh` scripts walk `pixi > uv > mamba > conda > pip`, so they work without pixi.

## CI and release design

### Pull-request validation

`validate.yml` validates the bundle registry, resolves skill/agent references, and checks plugin manifests/hooks/`.mcp.json`. `docs.yml` builds the docs site.

### Release

Releases are triggered by pushing a `v*` tag pointing at a commit already on `main`. The release workflow (GitHub App token: `RELEASE_APP_ID` / `RELEASE_APP_PRIVATE_KEY`):

1. Verifies the tag is on `main`.
2. Bumps versions across `marketplace.json` and every `plugins/*/.claude-plugin/plugin.json`, and commits the bump back to `main`.
3. Moves the tag forward to include the bump commit and creates the GitHub release.

`marketplace.json` plugin sources are relative paths (`./plugins/<bundle>`), so installs read directly from the pinned ref — no separate release branch.

### Release channels

`stable` is the default channel; `preview` may be used via separate marketplace refs or tags.

## Install flow

```bash
/plugin marketplace add nq-rdl/agent-extensions
/plugin install swe@rdl --scope project
```

Publication target: this repository, with `.claude-plugin/marketplace.json` at the root and plugins under `plugins/`.

## Platform requirements

macOS and Linux only — the skill-resolution strategy depends on native symlink support. Windows users must run under WSL2.

## Design principles

- One canonical source per skill/agent; generated plugin trees over hand-maintained copies.
- Self-contained installs (real-file copies, not cross-subtree symlinks).
- Sync resilience: content flows even when the registry is momentarily stale; correctness is enforced as a PR gate, and failures are never silent.
- Install documentation is part of the product.

## Non-goals

This repository should not:

- republish to hosts whose install model isn't Claude Code's `/plugin` marketplace (Codex, OpenCode, pi.dev) — those belong in CLI- or package-driven repos;
- hand-edit vendored skill content (it is owned upstream and overwritten on sync);
- hand-edit generated output under `dist/`.

For contribution expectations and authoring guidance, see the repository-root `AGENTS.md`.
