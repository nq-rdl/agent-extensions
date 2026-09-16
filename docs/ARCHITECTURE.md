---
icon: lucide/network
---

# Architecture

This repository is an **agent extension catalog**. It keeps a single source of truth for reusable agent behavior — *skills* with optional delegation outlines — and publishes self-contained plugins for Claude Code and Codex.

Both targets publish all bundles. Codex component flags select skills, native command hooks and MCP independently. Oh My Pi is out of scope.

## Problem statement

We want one place to author and version reusable agent extensions, and a deterministic way to ship them to Claude Code users.

What is authored once and reused:

- **Skills** written as `SKILL.md` (authored here; validated against the [agentskills.io](https://agentskills.io) spec by `asctl`)
- **Delegation outlines** written as `references/subagent.rst` inside their owning skill
- Reference material colocated with each skill
- MCP server integrations
- Bundle and release metadata

What is derived:

- The per-plugin trees under `plugins/<bundle>/` — real-file copies of the canonical skills, refreshed by a script.

The repository's core decision is that **the canonical content lives once and the plugin trees are generated from it**, so there is exactly one edit point per skill.

## Repository layout

```text
skills/                    ← canonical skills (authored here; validated by tools/asctl)
  <name>/
    SKILL.md
    references/subagent.rst ← optional worker instructions

hooks/                     ← Claude Code hook scripts + JSON config (authored here)
mcp/                       ← Go MCP servers (authored here; none currently)
tools/
  asctl/                   ← Go CLI: agentskills.io spec validator for skills/ (authored here)

registry/
  bundles/*.yaml           ← single source of truth: which skills/hooks/mcp each bundle ships
  marketplace.yaml         ← marketplace metadata, plugin defaults, and display order

.claude-plugin/
  marketplace.json         ← Claude Code marketplace manifest (repo root)

.agents/plugins/
  marketplace.json         ← native Codex marketplace manifest (repo root)

plugins/                   ← Claude Code plugins, one per bundle (SELF-CONTAINED — real files)
  <bundle>/
    .claude-plugin/plugin.json
    skills/<name>/         ← real-file copy of skills/<name>/
    bin/mcp/               ← prebuilt MCP server binaries
    .mcp.json              ← MCP server wiring
```

## Why plugin trees hold real-file copies

Claude Code installs a plugin by `cp -R`-ing its source directory into a per-user cache. Symlinks survive that copy *verbatim*, so any link whose target sits **outside** the copied subtree dangles in the cache. This was the root cause of issue #83.

To make installs self-contained, `plugins/<bundle>/skills/<name>/` holds **real-file copies** of the canonical content. The canonical source under `skills/` remains the single edit point; the plugin trees are derivative and rebuilt by `scripts/sync-plugins.sh`.

- **Edit canonical content** under `skills/<name>/` (both authored here).
- **Refresh plugin trees** with `bash scripts/sync-plugins.sh` (optionally scoped to a bundle). The script reads `registry/bundles/<b>.yaml`, prunes stale copies, and rewrites the plugin tree from the canonical sources.

## Skills

`skills/` is canonical content authored in this repo. It was formerly vendored from `nq-rdl/agent-skills` through a `repository_dispatch` + clone-and-overwrite sync; that repo has been merged here and the sync removed (it was the single biggest source of operational brittleness — a non-atomic cross-repo handoff that could push a branch but then fail to open the PR). Skills are now authored directly, validated by `asctl`, and packaged into plugin trees by `scripts/sync-plugins.sh`.

Codex copies are generated separately under `dist/codex/plugins/<subject>/`.
They carry explicit leaf names and native manifests with OpenAI metadata. Skills and optional delegation outlines
still originate in `skills/`. `scripts/codex_package.py` validates and copies
selected MCP, native command hooks, and runtime resources, rejects symlinks,
and checks both content and executable modes for drift. No agents tree is restored.

### `asctl` — the skills spec validator

`tools/asctl/` is a Go CLI imported from the former agent-skills repo. `asctl repo-check` validates every skill directory under `skills/` (frontmatter, structure, and prompt generation) against the [agentskills.io](https://agentskills.io) spec. It runs in CI as the `validate-skills` job, and locally:

```bash
go -C tools/asctl build -o /tmp/asctl ./cmd/asctl/ && /tmp/asctl repo-check
```

**Registry resilience:** the registry names skills by directory name, so a rename or removal can leave a stale reference. `scripts/sync-plugins.sh` reports it as a `::warning::` and skips it (it never aborts); the authoritative gate is `validate.yml`'s `validate-bundles` job, which fails the PR until a human reconciles the registry in the same change.

### `validate.yml` — on every PR / push to main

- `validate-bundles`: bundle references resolve, the grouping contract holds, and generated Claude/Codex manifests plus `docs/bundles.md` match the registry (`check_bundle_refs`, `check_grouping`, `generate_manifests --check`, `generate_bundles_doc --check`, `check_consistency`).
- `validate-symlinks`: any symlink under `plugins/` resolves (plugin trees are real-file copies, so this is a guardrail against accidental links).
- `validate-plugins`: plugin manifests (`plugin.json`), hooks, and `.mcp.json` wiring are well-formed (`scripts/validate-plugins.sh`); a pinned Codex CLI then installs every native marketplace entry and verifies installed skill discovery (`scripts/smoke-codex-marketplace.sh`).
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
  - {source: go-mcp-expert, leaf: build-mcp}
hooks: []                      # resolved from hooks/
prompts: []
mcp: []                        # wired into the plugin's .mcp.json (e.g. playwright, lucid)
targets:
  claude:
    enabled: true
    pluginName: go
    marketplaceName: rdl-agent-extensions
  codex:
    enabled: true
    pluginName: go
    marketplaceName: rdl-agent-extensions
    category: Developer Tools
    components:
      skills: true
      mcp: false
      hooks: false
      apps: false
```

Required behavior:

- A bundle maps to one Claude Code plugin. `targets.claude.enabled: false` disables a bundle without deleting it.
- A Codex bundle needs at least one selected capability. MCP and hooks require explicit native config paths; apps require registered integration work. Codex names and skill exclusions can differ from Claude.
- Native entrypoints use explicit skill names and host-aware execution instructions. Claude/OpenCode authoring examples remain artifacts for their target host, not native Codex API calls.
- Skills are referenced by name and resolved from `skills/`. Hooks, prompts, and MCP integrations resolve from their respective root-level directories.

## Optional delegation

The reusable procedure is a skill. `SKILL.md` describes direct execution and links
to `references/subagent.rst` for optional delegation. That reference holds the
worker outline, inputs, capability needs, scope, and output contract; it is read
only when delegation helps or the user asks for a subagent.

The host supplies the worker mechanism. The catalog does not install named agent
definitions, model overrides, tool allowlists, or automatic skill preloads.
A reference is instruction text and cannot enforce sandbox permissions. Give the
worker the resolved skill/reference paths and relevant companion instructions;
verify its returned evidence before presenting the result.

Former agent procedures retain their upstream attribution and licenses in their
owning skill and reference. See [Delegation](delegation.md) for migrated invocation
names and the distinction from Codex's optional `agents/openai.yaml` UI metadata.

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
| New first-party CLI helper or MCP server | Go (`CGO_ENABLED=0`, `GOOS`/`GOARCH` matrix) | Zero-install prebuilt binaries; no runtime dep on Node |
| Vendored/forked plugin runtime | May retain its upstream language | Full-fidelity forks must not be rewritten; allowed when the design documents runtime availability and distribution |
| Skill helper script (small, shared by a plugin's skills and hooks; `skills/<name>/scripts/`) | Bash 3.2-compatible + `jq` | File/JSON/git plumbing only — no compiled artefact to distribute; `rh-*.sh` and `sqlreview.sh` are the reference shape |
| File-format or ML skill | Python + `ensure-deps.sh` | Direct library access; bootstrapping handled by the script |
| Documentation-only skill | Markdown | No execution needed |
| Plugin wiring | JSON/YAML/shell | Manifests and glue only |
| New TypeScript | Not permitted | Bun hard-dependency, no CI, no binary output path |

The **vendored-runtime** row exists for the Codex plugin (see *Codex plugin: full-fidelity fork* below). It vendors the upstream Node.js `.mjs` runtime as-is; Bun is the local dev manager; it carries zero runtime npm dependencies; and Node.js >=18.18.0 is an external user prerequisite enforced by a first-use preflight (the hook `.sh` wrappers and the setup skill both check it and emit one exact message). This is a scoped exception to "new executable code is Go" — it applies only to code inherited from an upstream fork, not to net-new first-party tooling. If such a runtime is ever packaged rather than vendored in-tree, GitHub Packages/ghcr is the org distribution channel.

### Go house style

MCP servers in `mcp/*-go/` follow a Makefile with a `cross-compile` target that produces `$(DESTDIR)/<name>-<os>-<arch>` binaries (`CGO_ENABLED=0`, `-X main.version=$(git describe)` ldflags).

### Python / pixi

`pixi` provides the repo's reproducible Python environments — the default (`python` + `pyyaml`, solved for `linux-64`/`osx-64`/`osx-arm64`) runs the registry/pipeline scripts, and `docs` (`zensical`) builds the docs site via the `zensical` pixi task (`pixi run zensical serve` / `pixi run zensical build`). It stays optional, though: the `docs` environment is `linux-64` only, so macOS contributors build docs either in the dedicated **Zensical Docs** dev container (`.devcontainer/docs/`, pinned to `linux/amd64` so the `linux-64` env resolves) or with `uv`/`pip` directly, and Python skill `ensure-deps.sh` scripts walk `pixi > uv > mamba > conda > pip`, so they work without pixi.

## Codex plugin: full-fidelity fork

The `codex` plugin is a **full-fidelity fork** of
[`openai/codex-plugin-cc`](https://github.com/openai/codex-plugin-cc) at **v1.0.6
@ `db52e28`** (Apache-2.0). "Full-fidelity" means the upstream Node.js `.mjs`
runtime (broker, job store, socket protocol, app-server wiring) is vendored **as-is**
under `plugins/codex/scripts/` with only surgical patches — it is not rewritten in
Go. This is the concrete case the *vendored-runtime* language-policy row was added
for: rewriting a live agent runtime would forfeit correctness, so the fork keeps
upstream's language.

**Targeted-modernization boundary.** The modifications are deliberately narrow:

- The 8 deprecated upstream slash-commands become 8 user-invocable **action skills**
  (1:1), invoked as `/codex:setup`, `/codex:review`, `/codex:rescue`, etc.
- Rescue executes through the companion task contract directly or through an
  optional worker outline; it no longer requires a registered Claude subagent.
- The prompting knowledge is rewritten for the **GPT-5.6** catalog (Sol / Terra /
  Luna, the `low|medium|high|xhigh|max|ultra` effort ladder, `spark`), with a new
  `codex-model-guide` skill.
- Hooks are re-expressed in Claude Code **exec form** with a Node.js >=18.18.0
  external preflight in the `.sh` wrappers.
- A **first-party defect-logging subsystem** (`scripts/lib/defect-log.mjs`,
  `scripts/lib/defect-classify.mjs`, `scripts/codex-defects.mjs`,
  `scripts/defect-report-hook.mjs`, its `.sh` wrapper, and the
  `codex-report-defect` skill) is added alongside the vendored runtime, and
  `codex-companion.mjs`'s top-level `main().catch` handler is patched to record a
  marker. This is original nq-rdl code, not an upstream derivation — see
  **Licensing** below.

The job store also uses atomic file replacement for state and job JSON, so status
readers cannot observe a background worker's partially written record. The remaining
vendored internals — broker, socket protocol, app-server wiring — are untouched.

**Licensing.** Provenance is preserved with a split-license treatment:

- a per-bundle `license: Apache-2.0` override in `registry/bundles/codex.yaml`,
  stamped into the generated `plugin.json` and `marketplace.json` (the generator's
  default is the repo's MIT);
- `plugins/codex/LICENSE` (Apache-2.0 text) and `plugins/codex/NOTICE` (upstream
  copyright + fork/modification statement);
- a repo-root `NOTICE` that maps every Apache-derived path under the otherwise-MIT
  repo;
- per-file `SPDX-License-Identifier: Apache-2.0` headers on the derived canonical
  Markdown/shell/rST files, while the vendored `.mjs`/prompt/schema trees are
  covered wholesale by the plugin LICENSE/NOTICE (kept header-free to stay
  "vendored as-is");
- a **first-party carve-out**: the defect-logging subsystem listed above is
  original nq-rdl work living inside the vendored `scripts/` tree. It is licensed
  Apache-2.0 to match the bundle, but its copyright is nq-rdl's, so each of those
  files carries both an `SPDX-License-Identifier: Apache-2.0` and an
  `SPDX-FileCopyrightText: 2026 nq-rdl` line. Header *presence* alone is
  therefore not a provenance signal inside `plugins/codex/scripts/` — the
  `SPDX-FileCopyrightText` line is. The repo-root `NOTICE` holds the
  authoritative path list.

**Future evolution.** The long-term direction (Approach C) is to replace the
vendored app-server broker with native `codex exec --json` / `--output-schema`
once that CLI surface stabilizes, shrinking the vendored runtime toward a thin
Go or shell adapter. The fork boundary above is what keeps that migration
tractable.

## CI and release design

### Pull-request validation

`validate.yml` validates the bundle registry, resolves skill references, and checks plugin manifests/hooks/`.mcp.json`. `docs.yml` builds the docs site.

Workflow results and enforced merge requirements are separate. On **2026-09-16**,
the `main` protection API omitted `required_status_checks`, and the branch rules
API returned `[]`: no required status checks were configured. Protection required
one PR approval and resolved conversations, with administrator enforcement
disabled. This is a dated observation, not a claim about earlier settings.
[AGENTS.md](https://github.com/nq-rdl/agent-extensions/blob/main/AGENTS.md#build-test-lint) records the API endpoints, intended
always-run check inventory, and responsibility for keeping check names aligned
if maintainers enable enforcement. See [GitHub's protected-branch documentation](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).

External `check-links` remains advisory for merging and uses root `lychee.toml`
without caching. Its current scan covers skill Markdown and Spec Kit RST when
those paths change. The deterministic local Markdown/RST reference check and
broader external coverage in [#300](https://github.com/nq-rdl/agent-extensions/issues/300)
and advisory weekly monitoring in [#301](https://github.com/nq-rdl/agent-extensions/issues/301)
are planned, not implemented. Local lefthook checks can still reject a commit;
that behavior does not establish GitHub merge enforcement.

### Release

Releases are cut through a reviewable PR, not a local tag push, so that **merge authorization
equals release authorization**: branch protection on `main` already governs who can merge, and
reusing that gate for releases avoids a second, parallel trust boundary. There is no direct push
to `main` and no force-moved tag in the flow — a tag is created exactly once, on the commit that
was actually reviewed.

The **"Release — Prepare PR"** workflow (`workflow_dispatch`, GitHub App token:
`RELEASE_APP_ID` / `RELEASE_APP_PRIVATE_KEY`) takes an explicit `version` input (`X.Y.Z`, no
leading `v`, no zero-padded components). Explicit
version selection is retained deliberately rather than inferring a bump from commit kinds: SemVer
is silent on what a breaking change means for a `0.x` series, so the human cutting the release
still decides the number. The workflow batches and merges the changie changelog for that version,
stamps `VERSION` (and `pyproject.toml`), regenerates all manifests from the registry
(`scripts/generate_manifests.py`), and opens a `release/v<version>` PR labelled `skip-changelog` —
run under the App token so the PR's own CI executes on it like any other PR. If opening the PR
fails after the branch is pushed, the run deletes the branch itself (lease-protected, so a branch
someone has since moved is left alone and reported) so Prepare can simply be re-dispatched.

Reviewing and squash-merging that PR is the release gate. On merge, **"Release — Finalize on
merge"** (triggered by `pull_request: closed` against `main`, gated to merged `release/v*` PRs)
tags `v<version>` on the resulting squash-merge commit and publishes the GitHub release from
`.changes/<version>.md`. It never pushes to `main`, and it is idempotent: re-running it recovers a
partial failure where the tag was created but the release publish step did not complete. It also
fails closed: in every state an existing `v<version>` tag must point at the merge commit, a
release that exists without its tag is a hard failure, and a remote lookup error stops the run
rather than being read as "absent". Finalize runs are serialized in a single job-level concurrency
queue (`queue: max`, FIFO across versions), so the newest-tag monotonic backstop is sound even when
two release PRs merge within seconds of each other.

`marketplace.json` plugin sources are relative paths (`./plugins/<bundle>`), so installs read directly from the pinned ref — no separate release branch.

### Release channels

`stable` is the default channel; `preview` may be used via separate marketplace refs or tags.

## Install flow

Claude Code:

```bash
/plugin marketplace add nq-rdl/agent-extensions
/plugin install go@rdl-agent-extensions --scope project  # install a single subject
```

Codex:

```bash
codex plugin marketplace add nq-rdl/agent-extensions
codex plugin add go@rdl-agent-extensions --json
```

Both marketplaces publish from this repository and resolve self-contained plugin roots under `plugins/`. OpenAI's public Plugins Directory is a separate submission process.

## Platform requirements

macOS and Linux only — the build and sync scripts require POSIX shell tooling (`bash`, `find`, `cp -R`). Windows users must run under WSL2.

## Design principles

- One canonical source per skill; generated plugin trees over hand-maintained copies.
- Self-contained installs (real-file copies, not cross-subtree symlinks).
- Registry resilience: plugin generation continues even when a registry reference is momentarily stale (warn-and-skip); PR validation reports unresolved references. Merge enforcement depends on configured protection settings.
- Install documentation is part of the product.

## Non-goals

This repository should not:

- publish to a target without a native marketplace/install model and target-specific generated validation;
- hand-edit generated output (`plugins/*/` trees, target `plugin.json` and `marketplace.json` files, `docs/bundles.md`) — run the generator scripts instead.

For contribution expectations and authoring guidance, see the repository-root `AGENTS.md`.
