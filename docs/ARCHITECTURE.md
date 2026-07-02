---
icon: lucide/network
---

# Architecture

This repository is a **Claude Code extension catalog**. It keeps a single source of truth for reusable agent behavior — *skills* and *agents* — and publishes them as self-contained Claude Code plugins through a repo-root marketplace manifest.

> Claude Code is the **only** publication target. Tools with a different install model (their own CLI or package manager) are out of scope — they belong in CLI- or package-driven repos, not here.

## Problem statement

We want one place to author and version reusable agent extensions, and a deterministic way to ship them to Claude Code users.

What is authored once and reused:

- **Skills** written as `SKILL.md` (authored here; validated against the [agentskills.io](https://agentskills.io) spec by `asctl`)
- **Agents** written as `agent.md` (authored in this repo)
- Reference material colocated with each skill/agent
- MCP server integrations
- Bundle and release metadata

What is derived:

- The per-plugin trees under `plugins/<bundle>/` — real-file copies of the canonical skills and agents, refreshed by a script.

The repository's core decision is that **the canonical content lives once and the plugin trees are generated from it**, so there is exactly one edit point per skill or agent.

## Repository layout

```text
skills/                    ← canonical skills (authored here; validated by tools/asctl)
agents/                    ← canonical agents (authored here)
  <name>/
    agent.md
    references/            ← optional colocated reference material

hooks/                     ← Claude Code hook scripts + JSON config (authored here)
mcp/                       ← Go MCP servers (authored here; none currently)
tools/
  asctl/                   ← Go CLI: agentskills.io spec validator for skills/ (authored here)

registry/
  bundles/*.yaml           ← single source of truth: which skills/agents/hooks/mcp each bundle ships
  marketplace.yaml         ← marketplace metadata, plugin defaults, display order, and the rdl meta-plugin config

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

- **Edit canonical content** under `skills/<name>/` or `agents/<name>/agent.md` (both authored here).
- **Refresh plugin trees** with `bash scripts/sync-plugins.sh` (optionally scoped to a bundle). The script reads `registry/bundles/<b>.yaml`, prunes stale copies, and rewrites the plugin tree from the canonical sources.

## Skills

`skills/` is canonical content authored in this repo. It was formerly vendored from `nq-rdl/agent-skills` through a `repository_dispatch` + clone-and-overwrite sync; that repo has been merged here and the sync removed (it was the single biggest source of operational brittleness — a non-atomic cross-repo handoff that could push a branch but then fail to open the PR). Skills are now authored directly, validated by `asctl`, and packaged into plugin trees by `scripts/sync-plugins.sh`.

### `asctl` — the skills spec validator

`tools/asctl/` is a Go CLI imported from the former agent-skills repo. `asctl repo-check` validates every skill directory under `skills/` (frontmatter, structure, and prompt generation) against the [agentskills.io](https://agentskills.io) spec. It runs in CI as the `validate-skills` job, and locally:

```bash
go -C tools/asctl build -o /tmp/asctl ./cmd/asctl/ && /tmp/asctl repo-check
```

**Registry resilience:** the registry names skills/agents by directory name, so a rename or removal can leave a stale reference. `scripts/sync-plugins.sh` reports it as a `::warning::` and skips it (it never aborts); the authoritative gate is `validate.yml`'s `validate-bundles` job, which fails the PR until a human reconciles the registry in the same change.

### `validate.yml` — on every PR / push to main

- `validate-bundles`: bundle references resolve, the grouping contract holds, and the generated manifests + `docs/bundles.md` match the registry (`check_bundle_refs`, `check_grouping`, `generate_manifests --check`, `generate_bundles_doc --check`, `check_consistency`).
- `validate-symlinks`: any symlink under `plugins/` resolves (plugin trees are real-file copies, so this is a guardrail against accidental links).
- `validate-plugins`: plugin manifests (`plugin.json`), hooks, and `.mcp.json` wiring are well-formed (`scripts/validate-plugins.sh`).
- `unit-tests`: the pipeline scripts' unit tests pass (`python3 -m unittest discover -s tests`).
- `validate-skills`: every skill under `skills/` passes `asctl repo-check` (agentskills.io spec + prompt generation), built from `tools/asctl/`.

## Registry schema

The registry describes installable subject plugins, not raw files. One bundle = one subject.

```yaml
schemaVersion: v1
id: go
displayName: Go
description: Go — idiomatic naming and secure error handling
keywords: [go, naming, security]   # marketplace keywords (generated into the manifests)
owners:
  - rdl
channels:
  - stable
skills:                                # flat <name> (resolved from skills/<name>/), or a
  - {source: go-naming, leaf: naming}  #   {source, leaf} map → invokes as /go:naming
  - {source: go-secure, leaf: secure}
agents:                        # resolved from agents/<name>/agent.md
  - go-mcp-expert
hooks: []                      # resolved from hooks/
prompts: []
mcp: []                        # wired into the plugin's .mcp.json (e.g. playwright, lucid)
targets:
  claude:
    enabled: true
    pluginName: go
    marketplaceName: rdl
```

Required behavior:

- A bundle maps to one Claude Code plugin. `targets.claude.enabled: false` disables a bundle without deleting it.
- Skills and agents are referenced by name and resolved from `skills/` and `agents/`. Hooks, prompts, and MCP integrations resolve from their respective root-level directories.

## Agents primitive

Agents are the second authored primitive (alongside skills). They live at `agents/<name>/agent.md` and flow into plugins as flat `.md` real-file copies.

A skill is knowledge that activates contextually; an agent is a delegatable role with a focused tool allowlist and system prompt that Claude Code auto-routes on its `description`. The two are orthogonal: an agent may preload skills via frontmatter, but neither requires the other.

`agents/` is authored and versioned in this repo alongside hooks, prompts, and MCP servers.

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

### Asset ownership

| Asset | Authored in | Distributed from |
|---|---|---|
| `mcp/*-go/` Go MCP servers | this repo | this repo (prebuilt binaries in `plugins/*/bin/mcp/`) |
| `tools/asctl/` Go spec validator | this repo | this repo (built in CI; not shipped in plugins) |
| `skills/*/scripts/` Go/Python tools | this repo | bundled into plugin skill trees |
| `skills/{csv,docx,pdf,xlsx}/scripts/` | this repo | run in-place via `ensure-deps.sh` |
| `plugins/<subject>/bin/` prebuilt binaries | this repo | committed here, rebuilt by CI |
| `registry/bundles/*.yaml` | this repo | this repo |

**Note:** `skills/` is canonical and authored here. The former `nq-rdl/agent-skills` repo (the prior upstream source) has been merged into this repo and archived — edit skills directly here.

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

Releases are cut through a reviewable PR, not a local tag push, so that **merge authorization
equals release authorization**: branch protection on `main` already governs who can merge, and
reusing that gate for releases avoids a second, parallel trust boundary. There is no direct push
to `main` and no force-moved tag in the flow — a tag is created exactly once, on the commit that
was actually reviewed.

The **"Release — Prepare PR"** workflow (`workflow_dispatch`, GitHub App token:
`RELEASE_APP_ID` / `RELEASE_APP_PRIVATE_KEY`) takes an explicit `version` input (`X.Y.Z`). Explicit
version selection is retained deliberately rather than inferring a bump from commit kinds: SemVer
is silent on what a breaking change means for a `0.x` series, so the human cutting the release
still decides the number. The workflow batches and merges the changie changelog for that version,
stamps `VERSION` (and `pyproject.toml`), regenerates all manifests from the registry
(`scripts/generate_manifests.py`), and opens a `release/v<version>` PR labelled `skip-changelog` —
run under the App token so the PR's own CI executes on it like any other PR.

Reviewing and squash-merging that PR is the release gate. On merge, **"Release — Finalize on
merge"** (triggered by `pull_request: closed` against `main`, gated to merged `release/v*` PRs)
tags `v<version>` on the resulting squash-merge commit and publishes the GitHub release from
`.changes/<version>.md`. It never pushes to `main`, and it is idempotent: re-running it recovers a
partial failure where the tag was created but the release publish step did not complete.

`marketplace.json` plugin sources are relative paths (`./plugins/<bundle>`), so installs read directly from the pinned ref — no separate release branch.

### Release channels

`stable` is the default channel; `preview` may be used via separate marketplace refs or tags.

## Install flow

```bash
/plugin marketplace add nq-rdl/agent-extensions
/plugin install rdl@rdl                 # the meta-plugin installs every subject
# …or install a single subject:
/plugin install go@rdl --scope project
```

Publication target: this repository, with `.claude-plugin/marketplace.json` at the root and plugins under `plugins/`.

## Platform requirements

macOS and Linux only — the build and sync scripts require POSIX shell tooling (`bash`, `find`, `cp -R`). Windows users must run under WSL2.

## Design principles

- One canonical source per skill/agent; generated plugin trees over hand-maintained copies.
- Self-contained installs (real-file copies, not cross-subtree symlinks).
- Registry resilience: plugin generation continues even when a registry reference is momentarily stale (warn-and-skip); correctness is enforced as a PR gate.
- Install documentation is part of the product.

## Non-goals

This repository should not:

- republish to hosts whose install model isn't Claude Code's `/plugin` marketplace — those belong in CLI- or package-driven repos;
- hand-edit generated output (`plugins/*/` trees, `plugin.json`, `marketplace.json`, `docs/bundles.md`) — run the generator scripts instead.

For contribution expectations and authoring guidance, see the repository-root `AGENTS.md`.
