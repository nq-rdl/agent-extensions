# AGENTS.md

Agent guidance for this repository. Use this alongside the README for project context specific to coding agents.

## What this repo is

This repo is **a Claude Code marketplace** — the published product. It *is* the `rdl-agent-extensions`
marketplace: it authors reusable skills and agents (canonical content under
`skills/` and `agents/`) and publishes them as self-contained plugins through the
repo-root marketplace manifest (`.claude-plugin/marketplace.json`). This is what
users install.

> **`.claude/` contributor tooling was removed.** This repo previously carried a
> `.claude/` folder — *not* part of the published product — that configured Claude
> Code for work *inside this repo*: a project `settings.json` (model, SessionStart /
> PreToolUse hooks, and a curated external-plugin set) plus helper scripts under
> `.claude/scripts/`. That tooling has been removed; how we configure Claude Code for
> developing the catalog is being re-approached. It never affected what ships to users.

**Where to look:** **`CONTRIBUTING.md`** outlines the development requirements (skill
content conventions, the grouping contract, packaging a skill into a plugin); the
PR and changelog flow is in this file's **`## PR instructions`** section below.
**`docs/`** is the project documentation — `docs/ARCHITECTURE.md` (design + packaging
decisions), `docs/external-marketplaces.md` (recommended external dev-helper plugins), and
`docs/local-testing.md` (install walkthrough).

## Project overview

This repo is a Claude Code agent extension catalog. It maintains a single source of truth for reusable agent skills and agents, and publishes them as self-contained Claude Code plugins through a repo-root marketplace manifest. Canonical content lives once (under `skills/` and `agents/`); each bundle is packaged into `plugins/<bundle>/` as real-file copies so installs are self-contained.

## Setup commands

```bash
# Activate local git hooks (pre-commit + pre-push CI parity, via lefthook)
lefthook install

# Create the pixi environment (python + pyyaml). ALL repo Python is managed by
# pixi — invoke the registry/pipeline scripts via `pixi run`, never a system python3.
pixi install
```

Local hooks mirror CI so failures surface before you push. **pre-commit** runs
fast checks (gofmt/vet/build of `tools/asctl`, `asctl repo-check`, plugin
validation, generated-artifact drift, a per-fragment changie body-length cap,
lychee links); **pre-push** runs `asctl` tests, the pipeline unit tests, a
non-blocking SkillSpector scan, and a hard changie-fragment gate. Prereqs:
`lefthook`, Go, `pixi` (provides the Python toolchain — hook jobs call
`pixi run`); optional `lychee` and Docker. Bypass with `LEFTHOOK=0` or
`git commit --no-verify`.

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
  marketplace.yaml ← marketplace metadata, plugin defaults, and display order
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
- **Refresh plugin trees** by running `pixi run bash scripts/sync-plugins.sh` (or pass a bundle name to scope it). The script reads `registry/bundles/<b>.yaml`, removes any stale copies, and rewrites `plugins/<b>/skills/<name>/` and `plugins/<b>/agents/<name>.md` from the canonical sources.
- **CI** validates that every bundle YAML reference resolves and that every plugin manifest is well-formed. See `scripts/validate-plugins.sh`.

**Grouped skills.** A bundle skill member is either a flat string (`changie` → `leaf == changie`) or an explicit `{source, leaf}` mapping (`{source: go-gh, leaf: actions-go}` in the `gh` bundle → `/gh:actions-go`). `sync-plugins.sh` copies the flat canonical `skills/<source>/` → `plugins/<pluginName>/skills/<leaf>/`, **renaming to the leaf**, so the plugin tree stays one level deep and Claude Code invokes `<pluginName>:<leaf>` (the leaf folder drives invocation). Claude Code labels a skill in `/`-autocomplete as `frontmatter.name || <pluginName>:<leaf>` — so a present `name:` (the canonical `go-gh` **or** the leaf `actions-go`) overrides the namespaced id with a bare, un-prefixed label, and `/gh` lists `go-gh`/`actions-go` instead of `gh:actions-go`. To get the namespaced label, sync **strips the copy's `name:` entirely** so the label falls back to `<pluginName>:<leaf>`. The canonical `skills/` tree is never touched; grouping is owned **here** in the registry and stays flat. See `CONTRIBUTING.md` §6 for the rules, `scripts/check_grouping.py` for the contract, and `scripts/validate-plugins.sh` for the no-name guard.

Skills and agents are authored directly under `skills/` and `agents/`. After editing one, run `pixi run bash scripts/sync-plugins.sh` to refresh the plugin trees; CI's `validate-skills` job runs `asctl repo-check` to validate `skills/` against the agentskills.io spec.

When authoring or compressing a skill, follow **CONTRIBUTING.md → "Skill content conventions"** (non-inferable delta, version pins, verify-canonical guard). The `/claude-code:skill-audit` skill checks these.

### Python skills (csv, pdf, xlsx, docx)

These skills call Python directly (no CLI wrapper). Each has a `requirements.txt` and an `ensure-deps.sh` bootstrap script, so end users need no extra setup. For work *inside this repo*, Python is managed by **pixi** (`pyproject.toml`): the default environment carries `python` + `pyyaml` for the registry scripts, and the `docs` environment (linux-64 only) carries Zensical.

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

All Python (including the `python3` heredocs inside the shell scripts) runs through
the pixi environment — hence the `pixi run` prefix on every command below.

```bash
# Validate all plugin hooks.json, plugin.json, and agents
pixi run bash scripts/validate-plugins.sh

# Validate only plugins touched by changed files
pixi run bash scripts/validate-plugins.sh plugins/claude-code/hooks/hooks.json

# Refresh plugin trees from canonical skills/ and agents/. Run after
# editing a skill or agent.
pixi run bash scripts/sync-plugins.sh           # all bundles
pixi run bash scripts/sync-plugins.sh go        # one bundle

# Regenerate plugin.json + marketplace.json from the registry. These manifests
# are GENERATED — never hand-edit them. Run after changing a bundle's
# description/keywords, marketplace.yaml, or VERSION.
pixi run python3 scripts/generate_manifests.py .          # write manifests
pixi run python3 scripts/generate_manifests.py . --check  # CI gate: fail on drift

# Regenerate docs/bundles.md from the registry (also a --check CI gate).
pixi run python3 scripts/generate_bundles_doc.py .          # write
pixi run python3 scripts/generate_bundles_doc.py . --check  # CI gate: fail on drift

# Bundle reference + grouping + three-way consistency checks (also run by validate.yml)
pixi run python3 scripts/check_bundle_refs.py .   # registry refs resolve to skills/ & agents/
pixi run python3 scripts/check_grouping.py .      # grouping contract: valid member shape, unique leaf + pluginName
pixi run python3 scripts/check_consistency.py .   # bundle <-> marketplace.json <-> plugins/ agree

# Unit tests for the pipeline scripts (deps come from the pixi env)
pixi run python3 -m unittest discover -s tests -p 'test_*.py'

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
- Skills validate against the agentskills.io spec **and the directory-structure standard** (`asctl repo-check`, built from `tools/asctl/`)

Three more workflows run on PRs alongside `validate.yml`:
- `changelog-check.yml` — fails if no changie fragment was added (bypass with the `skip-changelog` label), and lints each *added* fragment's body against the 200-char per-fragment cap (`scripts/check_changie_length.py`)
- `link-check.yml` — lychee link check over changed `skills/**/*.md`
- `skillspector.yml` — NVIDIA SkillSpector scan over `skills/`; informational, uploads SARIF to code scanning (non-gating)

The same checks run locally via `lefthook` (see Setup commands).

**Required status checks on `main` are coupled to these job names.** The always-run
`validate.yml` jobs above are marked as required status checks so red CI blocks the merge
button (`docs/branch-protection.md`). A required check is matched by the **exact job
`name:`** — renaming or dropping a `name:` in `validate.yml` silently drops the
requirement (the gate disappears while still showing green). When you rename, add, or
remove an always-run `validate.yml` job, update the required-checks list per
`docs/branch-protection.md`. Keep the subset-only checks **out of this always-run set**:
`link-check`'s `paths:` filter would hang non-skill PRs, and `check-changie-fragment` /
SkillSpector `scan` are excluded. (`version-monotonic` is also outside this set, but the
release flow *does* require it separately — see `docs/releasing.md`.) See
`docs/branch-protection.md` for the reasoning.

## Testing instructions

To verify skills are visible before release, install the repo as a local Claude Code marketplace:

```bash
# Single-session in-place (preferred in devcontainer — no cache copy, reads files directly from the working tree)
claude --plugin-dir ./plugins/go

# Persistent install (workspace must stay mounted at /workspace)
claude plugin marketplace add /workspace
claude plugin install go@rdl-agent-extensions

# Onboarding onto the team's Claude Code setup goes through the rdl-team plugin:
claude plugin install rdl-team@rdl-agent-extensions
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
description: Go — idiomatic naming and secure error handling  # no trailing period
keywords: [go, naming, security]           # marketplace keywords (generated into the manifests)
owners: [rdl]
channels: [stable]
skills:                                    # flat <name> (leaf == name), or {source, leaf} to rename
  - {source: go-naming, leaf: naming}      #   → invokes as /go:naming
  - {source: go-secure, leaf: secure}      #   → /go:secure
agents:                                    # must exist as agents/<name>/agent.md (subagent)
  - go-mcp-expert
  - wg-code-sentinel
  - github-actions-expert  # guest — home: gh (cross-listing: CONTRIBUTING §5)
hooks: []
prompts: []
mcp: []                                    # wired in plugins/<pluginName>/.mcp.json
targets:
  claude:
    enabled: true
    pluginName: go
    marketplaceName: rdl-agent-extensions
```

The bundle's `description` + `keywords` (plus `registry/marketplace.yaml` and `VERSION`) **generate** `plugins/<bundle>/.claude-plugin/plugin.json` and the bundle's `marketplace.json` entry — do not hand-edit those (CI `generate_manifests.py --check` enforces it). After editing a bundle's `description`/`keywords`, run `pixi run python3 scripts/generate_manifests.py .`.

When adding a skill to a bundle: (1) add it to the YAML (flat `<name>`, or a `{source, leaf}` map to repackage a flat upstream skill under a new leaf), (2) run `pixi run bash scripts/sync-plugins.sh <bundle>` to copy `skills/<source>/` into `plugins/<bundle>/skills/<leaf>/`.

When adding an agent to a bundle: (1) create `agents/<name>/agent.md`, (2) add it to the YAML `agents:` list, (3) run `pixi run bash scripts/sync-plugins.sh <bundle>` to copy it into `plugins/<bundle>/agents/<name>.md`.

## PR instructions

### Changelog

Use `changie` for all changelog entries:

```bash
changie new               # create an unreleased change entry
changie batch auto        # batch unreleased into a version (uses semver from kind)
changie merge             # merge versions into CHANGELOG.md
```

**One idea per fragment; keep it short.** Each fragment `body` has a hard
**200-character cap** (`.changie.yaml` `body.maxLength`). Changie has no `lint`
command, so this is enforced two ways: `changie new` rejects an over-long body
at creation, and `scripts/check_changie_length.py` re-lints *added* fragments in
the pre-commit hook and in `changelog-check.yml` (catching fragments written
directly, bypassing the prompt). The cap is **per fragment, not per change** —
there is no limit on how many fragments a branch adds, so split a large change
into several: run `changie new` once per idea (`Added: thing 1`, `Added: thing
2`, …) rather than packing everything into one run-on body. The cap governs
**current unreleased and future** fragments only; already-released versions
(`.changes/<version>.md` + the GitHub release body) are immutable and out of
scope. Override the limit for a run with `CHANGIE_MAX_BODY_LENGTH` (keep it in
sync with `.changie.yaml`).

### Release

Releases are cut from the GitHub UI, not a local tag push. Run the **"Release — Prepare PR"**
workflow (Actions tab, `workflow_dispatch`) with an explicit `version` input (`X.Y.Z`, no leading
`v`). It batches the changie changelog, stamps `VERSION` (and `pyproject.toml`), regenerates all
manifests from the registry, and opens a `release/v<version>` PR labelled `skip-changelog` — all
via the GitHub App token (`RELEASE_APP_ID` / `RELEASE_APP_PRIVATE_KEY`) so the PR's own CI runs on
it. Reviewing and squash-merging that PR **is** the release gate (branch protection controls who
can merge). A pre-merge **"Release — PR guard"** check runs on every `release/v*` PR and fails
closed if the PR's version doesn't match its branch name or isn't strictly newer than `main`'s
current `VERSION`, catching a stale release PR before it can merge. On merge, **"Release —
Finalize on merge"** tags `v<version>` on the squash-merge commit and publishes the GitHub release
from `.changes/<version>.md` — it never pushes to `main`, and it is idempotent (safe to re-run;
recovers a tag-pushed-but-release-missing partial failure).

`marketplace.json` sources are relative paths (`./plugins/<bundle>`) — installs read directly from `main` (or whatever ref the user pinned), no separate release branch involved.

See [`docs/releasing.md`](docs/releasing.md) for the step-by-step runbook (cutting a release, partial-failure recovery, rollback).

## Docs

The docs site uses Zensical (configured in `zensical.toml`), provided by the pixi `docs` environment (linux-64 only — `pixi run -e docs …`). Source is `docs/`. Architecture decisions live in `docs/ARCHITECTURE.md`. Local install walkthrough: [`docs/local-testing.md`](docs/local-testing.md).

## Platform Notes

- macOS and Linux only — the build scripts require POSIX shell tooling (WSL2 for Windows)
- Generated outputs (`plugins/` trees, `plugins/*/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `docs/bundles.md`) are produced by the generator scripts — do not hand-edit.
