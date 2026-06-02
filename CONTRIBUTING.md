# Contributing

Thanks for contributing to the RDL agent extension catalog. This file covers the **rules for
grouping skills and agents into plugins**. For repo mechanics (sync scripts, validation,
release), see [`AGENTS.md`](AGENTS.md) and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Plugin grouping: one plugin per subject

> **Status:** adopted grouping model. The *strategy* (retire legacy domain bundles — `swe`,
> `infra`, `informatics`, `dev-tools`, `meta`, `hooks` — and regroup by subject) is
> [#101](https://github.com/nq-rdl/agent-extensions/issues/101); the *mechanism* (the cross-repo
> grouping contract + sync/packaging) is [#102](https://github.com/nq-rdl/agent-extensions/issues/102)
> and [agent-skills#118](https://github.com/nq-rdl/agent-skills/pull/118). Design:
> `docs/specs/2026-06-02-plugin-grouping-design.md`.

Every skill and agent is invoked as **`<subject>:<facet>`** — the `subject` is the plugin, the
`facet` is what it does. The rules below decide both halves. The colon is always present for
plugin content; only Claude Code's built-in skills are bare.

### 1. One plugin per subject

A **subject** is a tool, library, language, app, or named workflow (`obsidian`, `go`, `r`,
`sops`, `release`). Each subject is exactly one plugin. A subject with a single facet still gets
its own plugin — small plugins are fine.

### 2. File by *primary* subject, not by tools touched

Put each skill/agent under the one thing it is **primarily about**. Secondary tools it merely
*uses* do not count.

- `go-gh` is "GitHub Actions CI/CD **for Go**" → subject is **Go** → `go:gh`. (Not a GitHub
  Actions plugin.)
- `jules-dispatch-creator` sets up **Jules** GitHub Actions workflows → subject is **Jules** →
  `jules:dispatch-creator`.

If you're tempted to file something under two subjects, you've applied the wrong test. Ask
"what is this *about*?" — that question returns exactly one answer.

### 3. The facet is always an action or stage

Name the facet for *what it does*, even when the subject has only one facet. Never repeat the
subject.

- ✅ `sops:encrypt`, `pixi:env`, `obsidian:bases`
- ❌ `sops:sops`, `pixi:pixi`
- Multi-step workflows use stage facets: `release:start`, `release:middle`, `release:close`.
  Ordering lives in the skill **content** — each stage points to the next; the namespace does
  not enforce order.

The facet is the **leaf folder name** chosen upstream (see rule 6) — there is no separate
rename step.

### 4. No-tool subjects → name the workflow

If a skill/agent isn't about a tool, its subject is the **workflow/activity** it performs:
`git:send-pr`, `git:conventional-commits`, `review:<facet>`.

### 5. Agents: home + description required; companion skill optional

Every agent MUST have:

- a **home plugin** (its subject, per rules 1–4), and
- a clear **`description`** — the "Use when…" frontmatter is the agent's explainer.

Add a **companion skill only when the agent encodes a reusable methodology**: the skill is the
method (runnable by anyone), the agent is the autonomous executor — e.g. a `systematic-debugging`
skill paired with a `debug` agent. Do **not** add a skill just to describe an agent; the
`description` already does that. An **agent-only plugin** (e.g. `terraform`, `postgres`) is fine
when a subject has agents but no skill.

### 6. How grouping is expressed across the two repos (the #102 contract)

Skills are authored upstream in [`nq-rdl/agent-skills`](https://github.com/nq-rdl/agent-skills),
and **grouping is expressed upstream by folder layout** (per
[#102](https://github.com/nq-rdl/agent-extensions/issues/102) / agent-skills#118):

- A skill is either **flat** `skills/<skill>/SKILL.md` (standalone) or **grouped**
  `skills/<group>/<leaf>/SKILL.md` (exactly one level; a group folder holds no direct `SKILL.md`).
- **Group folder == plugin name** (the subject); **leaf folder == facet**; frontmatter
  **`name:` == leaf folder**.
- Here in `agent-extensions`, the bundle sets `pluginName: <group>` and lists members
  path-qualified as `<group>/<leaf>`. `scripts/sync-plugins.sh` copies `skills/<group>/<leaf>/` →
  `plugins/<group>/skills/<leaf>/`, **dropping the `<group>/` prefix** — so the plugin tree is one
  level deep and Claude Code invokes `<group>:<leaf>`.
- Validators enforce: `name:` == leaf · group == `pluginName` · no duplicate leaf within a bundle ·
  `pluginName` unique across bundles.

So to add `obsidian:bases`, create `skills/obsidian/bases/SKILL.md` upstream — **not**
`skills/obsidian-bases/`. Agents are authored here under `agents/<name>/agent.md` and placed by
subject in the registry. See [`AGENTS.md`](AGENTS.md) for the mechanical add-and-sync steps.

### 7. Manifests are generated; new subjects join the `rdl` meta-plugin

`plugin.json` and the `marketplace.json` entry for a subject are **generated from
`registry/bundles/<subject>.yaml`** — do **not** hand-edit them. When you add a **new subject**,
it is also registered as a dependency of the **`rdl` meta-plugin**, so `claude plugin install
rdl@rdl` keeps installing the full set. CI consistency checks fail if registry, generated
manifests, and the meta-plugin dependency list disagree.
