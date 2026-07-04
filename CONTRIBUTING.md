# Contributing

Thanks for contributing to the RDL agent extension catalog. This file covers the **rules for
grouping skills and agents into plugins**, the **skill directory structure and content
conventions**, and the **packaging loop** that turns a new skill or agent into an installable
plugin. For repo mechanics (sync scripts, validation, CI), see [`AGENTS.md`](AGENTS.md) and
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

**Tooling:** all repo Python runs via **pixi** (`pixi install` once, then
`pixi run …` for every script below — the environment is defined in `pyproject.toml`).

## Plugin grouping: one plugin per subject

Every skill and agent is invoked as **`<subject>:<facet>`** — the `subject` is the plugin, the
`facet` is what it does. The rules below decide both halves. The colon is always present for
plugin content; only Claude Code's built-in skills are bare.

### 1. One plugin per subject

A **subject** is a tool, library, language, app, or named workflow (`obsidian`, `go`, `r`,
`sops`, `planning`). Each subject is exactly one plugin. A subject with a single facet still gets
its own plugin — small plugins are fine. Its content can be skills, agents, hooks, or MCP servers
in any combination — a bundle may be skill-only, agent-only, or MCP-only (e.g. `lucid` wires only
an MCP server).

### 2. File by *primary* subject, not by tools touched

Put each skill/agent under the one thing it is **primarily about**. Secondary tools it merely
*uses* do not count.

- `shiny-bslib` themes a **Shiny** app with bslib → subject is **Shiny** → `shiny:bslib`. (Not
  a bslib plugin.)

If you're tempted to file something under two subjects, you've applied the wrong test. Ask
"what is this *about*?" — that question returns exactly one answer.

> **The `gh` bundle and its one exception.** `gh` is the team's GitHub *workflow* subject (rule
> 4 below): `changie`, `conventional-commits`, `husky`, `lefthook`, `pre-commit`, `send-pr`, and
> `document-release` all invoke as `/gh:*`. `go-gh` ("GitHub Actions CI/CD **for Go**") is grouped
> there too, as `/gh:actions-go`, even though its primary subject is **Go** — the one sanctioned
> exception to "file by primary subject," not a precedent. The bare `actions` leaf is reserved for
> a future generic GitHub Actions skill. File everything else by what it is *about*.

### 3. The facet is always an action or stage

Name the facet for *what it does*, even when the subject has only one facet. Never repeat the
subject.

- ✅ `sops:encrypt`, `pixi:env`, `obsidian:bases`
- ❌ `sops:sops`, `pixi:pixi`
- Multi-step workflows use stage facets, e.g. a hypothetical `release` subject with
  `release:start`, `release:middle`, `release:close`. Ordering lives in the skill **content**
  — each stage points to the next; the namespace does not enforce order.

The facet is the **leaf** you set in the registry mapping (see rule 6); the canonical skill stays
flat and is renamed to the leaf when the plugin tree is generated.

### 4. No-tool subjects → name the workflow

If a skill/agent isn't about a tool, its subject is the **workflow/activity** it performs — real
workflow subjects include `planning`, `debug`, and `tech-writing`. An action filed under a
workflow subject invokes like any other facet: `gh:send-pr`, `gh:conventional-commits` (subject
`gh`, facet the action).

### 5. Agents: home + description required; companion skill optional

Every agent MUST have:

- a **home plugin** (its subject, per rules 1–4), and
- a clear **`description`** — the "Use when…" frontmatter is the agent's explainer.

Add a **companion skill only when the agent encodes a reusable methodology**: the skill is the
method (runnable by anyone), the agent is the autonomous executor — e.g. a `systematic-debugging`
skill paired with a `debug` agent. Do **not** add a skill just to describe an agent; the
`description` already does that. An **agent-only plugin** (e.g. `terraform`, `postgres`) is fine
when a subject has agents but no skill.

#### Cross-listing an agent (one home, rare guests)

Agent reuse across bundles is deliberate and supported, but every listing has a documented home.
Every agent has exactly **one home** — its subject bundle, per rules 1–4. A **guest listing** in
another bundle is allowed when the agent is load-bearing for that bundle's job; keep guests rare
and annotate them in the registry YAML with a `# guest — home: <bundle>` comment on the agent
line. Docs and hooks always reference the **home-qualified** agent, so a guest listing can be
added or dropped without breaking references.

Guest listings are discoverable at a glance: `grep -rn 'guest — home' registry/bundles/`. For
example, `github-actions-expert` is homed in `gh` and guests in `go`.

### 6. How grouping is expressed (owned here in `agent-extensions`)

Skills are authored in this repo as a **flat** library — `skills/<skill>/SKILL.md`, one level, no
group folders. **Grouping is a packaging decision** expressed in the bundle registry:

- A bundle sets `pluginName: <subject>` and lists each skill member as either:
  - a **flat string** `<name>` — packaged as-is (`leaf == <name>`); or
  - an explicit **`{source, leaf}` mapping** — packages the flat `skills/<source>/` under a
    different `leaf` (e.g. `{source: go-gh, leaf: actions-go}` → `gh:actions-go`).
- A bundle may also wire `hooks:` and `mcp:` entries; see the registry schema in `AGENTS.md`.
- `scripts/sync-plugins.sh` copies `skills/<source>/` → `plugins/<subject>/skills/<leaf>/`, renaming
  to the leaf — so the plugin tree is one level deep and Claude Code invokes `<subject>:<leaf>`.
  **The leaf folder name drives invocation.** Claude Code labels a skill in `/`-autocomplete as
  `frontmatter.name || <subject>:<leaf>` — a present `name:` would override the namespaced id with
  a bare label (e.g. `/gh` listing `go-gh` instead of `gh:actions-go`), so `sync-plugins.sh`
  **strips the copy's `name:` entirely**. The canonical `skills/` source is never touched; only the
  derivative plugin copy is stripped.
- Validators enforce: every member has a valid shape · no duplicate leaf within a bundle ·
  `pluginName` unique across bundles (`scripts/check_grouping.py`) · each plugin skill copy carries
  **no** frontmatter `name:` (`scripts/validate-plugins.sh`).

So to add `obsidian:bases`, the canonical skill stays flat `skills/obsidian-bases/`; the registry
maps `{source: obsidian-bases, leaf: bases}` under `pluginName: obsidian`. Agents are authored here
under `agents/<name>/agent.md` and placed by subject in the registry. See [`AGENTS.md`](AGENTS.md)
for the mechanical add-and-sync steps.

### 7. Manifests are generated

`plugin.json` and the `marketplace.json` entry for a subject are **generated from
`registry/bundles/<subject>.yaml`** — do **not** hand-edit them. When you add a **new subject**,
append it to the `order:` list in `registry/marketplace.yaml` (see step 4 below). CI consistency
checks fail if the registry and the generated manifests disagree.

## Skill directory structure

A skill lives at `skills/<name>/` and follows a fixed v1 layout so the catalog stays predictable
and installs stay clean. `asctl repo-check` enforces this contract — a violation fails CI (see the
`validate-skills` job in [`.github/workflows/validate.yml`](.github/workflows/validate.yml), which
builds `asctl` and runs `asctl repo-check` on every PR and push).

The rules:

1. **`SKILL.md` is required** at the skill root — it is the skill. The filename must be exactly
   `SKILL.md` (uppercase); a lowercase `skill.md` is rejected.
2. **Only three non-hidden subdirectories are allowed:** `scripts/`, `references/`, and `assets/`.
   Any other non-hidden subdirectory is an error.
3. **`references/` is `.rst`-only.** Every file under `references/` (at any depth) must be `.rst`;
   anything else is an error.
4. **No `agents/` inside a skill.** Agents are not skill content — they live in top-level
   `agents/<name>/agent.md` and are bundled into the plugin through the registry (see
   [§5](#5-agents-home--description-required-companion-skill-optional) and the agent add-and-sync
   steps in [`AGENTS.md`](AGENTS.md)). A `skills/*/agents/` directory is an error.
5. **Hidden entries are ignored.** Dot-prefixed files and directories (e.g. `.evals`) are not
   linted; the structure check does not descend into or flag them.
6. **Top-level files: `SKILL.md` plus a small config allowlist.** The only non-hidden top-level
   file permitted besides `SKILL.md` is `lychee.toml` (used by `skills/lychee`). Any other
   non-hidden top-level file is an error.

### The 3-bucket rule

When a skill ships more than its `SKILL.md`, sort each extra file into exactly one bucket:

- **`scripts/`** — runnable files the skill invokes (`.sh`, compiled helpers, and the like).
- **`references/`** — prose docs Claude reads on demand. `.rst` only.
- **`assets/`** — everything else the skill ships: sample configs, templates, fixtures, and files
  like `.json`, `.env`, `.yml.tmpl`, or icons. Not prose, not executed as a script.

If a file is neither runnable nor `.rst` prose, it belongs in `assets/`.

## Skill content conventions

A skill must encode a **gap the fresh model cannot see** — not restate public
knowledge. Before writing or accepting skill content, apply these:

### Prefer the non-inferable delta
Ask Biggs's test: *"could a fresh model write this verbatim, with no prior
struggle?"* If yes, cut it. Don't restate public specs or style guides; encode
the gaps, gotchas, and project-specific decisions instead. Empirically
(SkillsBench), wins concentrate in **concise** skills carrying verifier-facing,
non-inferable detail — "comprehensive" prose scores worst and can displace the
model's own stronger default.

### Pin versions
When a skill encodes a library or tool API surface, pin the version in
`compatibility:` so drift is visible and reviewable. An unpinned API recital is
how stale guidance (e.g. a deprecated method form) silently overrides the
model's newer, correct default.

### Add a verify-canonical guard
For fast-moving or correctness-critical subjects, include a one-line "verify
against the canonical source when being wrong would mislead," and point to the
authoritative docs. See `skills/rust-explain/SKILL.md` for the model pattern.

References: Biggs, *You're Probably Using Agent Skills Wrong*; SkillsBench (arXiv 2602.12670).

## Packaging a new skill into a plugin

A new skill authored under `skills/<name>/` is **not installable until you map it into a bundle**
— authoring the `SKILL.md` only adds it to the flat library; the registry decides which plugin
(subject) it belongs to. Here is the full loop, using a hypothetical `sql-review-analyse` skill
that should become `sql-review:analyse`:

1. **Pick the subject and facet** (the rules above). Subject → the plugin (`sql-review`); facet →
   the action/stage leaf (`analyse`). Never repeat the subject in the facet.
2. **Choose or create the bundle.** If `registry/bundles/sql-review.yaml` exists, add to it;
   otherwise copy an existing single-subject bundle (e.g. `registry/bundles/sops.yaml`) and set
   `id`, `displayName`, `description` (no trailing period), `keywords`, and
   `targets.claude.pluginName: sql-review`.
3. **Add the skill member.** Under `skills:`, write either a flat string (when the skill's
   directory name already equals the leaf you want) or a `{source, leaf}` mapping to rename:
   ```yaml
   skills:
     - {source: sql-review-analyse, leaf: analyse}   # → /sql-review:analyse
   ```
4. **If it is a brand-new subject, add it to the marketplace order.** Append `sql-review` to the
   `order:` list in `registry/marketplace.yaml` (otherwise it is appended alphabetically with a
   CI `::warning::`).
5. **Build the plugin tree and manifests:**
   ```bash
   pixi run bash scripts/sync-plugins.sh sql-review     # copies skills/<source>/ → plugins/sql-review/skills/<leaf>/
   pixi run python3 scripts/generate_manifests.py .     # writes plugin.json + marketplace.json
   pixi run python3 scripts/generate_bundles_doc.py .   # refreshes docs/bundles.md
   ```
6. **Validate** exactly what CI will:
   ```bash
   pixi run python3 scripts/check_bundle_refs.py .   && \
   pixi run python3 scripts/check_grouping.py .      && \
   pixi run python3 scripts/generate_manifests.py . --check && \
   pixi run python3 scripts/generate_bundles_doc.py . --check && \
   pixi run python3 scripts/check_consistency.py .   && \
   pixi run bash scripts/validate-plugins.sh
   ```

Adding an **agent** follows the same loop: author `agents/<name>/agent.md` (with frontmatter
`name` + `description`), list it under a bundle's `agents:`, then run steps 5–6. An agent-only
subject (no skill) is fine — give it its own bundle with an empty `skills: []`.

## Claude Code on the web

Cloud sessions run on a fresh VM with only a clone of this repo. This repo used to
auto-configure dev-helper plugins for those sessions through a project `.claude/settings.json`
(`enabledPlugins` + `extraKnownMarketplaces`) plus a pair of SessionStart hooks under
`.claude/scripts/` — `install-deps.sh` (per-session tooling) and `announce-capabilities.sh`
(cross-checking which declared plugins actually landed). That `.claude/` tooling has been
**removed**; how dev-helper plugins are provisioned for web sessions is being re-approached.

The external dev-helpers themselves (Go/LSP, PR review, Python tooling, git worktrees, general
workflows) are unchanged — see [`docs/external-marketplaces.md`](docs/external-marketplaces.md)
for the curated set and how to enable them in your **user** settings in the meantime. As before,
never enable the `rdl-agent-extensions` marketplace or any of its published plugins for catalog
development — a session for developing the catalog should not install the catalog itself.

## Cutting a release

Releases are dispatched from the Actions tab (**"Release — Prepare PR"**) and land as a
reviewable `release/v<version>` PR — reviewing and squash-merging that PR is the release gate.
See [`docs/releasing.md`](docs/releasing.md) for the full runbook, including partial-failure
recovery and rollback.
