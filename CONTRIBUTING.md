# Contributing

Thanks for contributing to the RDL agent extension catalog. This file covers the **rules for
grouping skills and agents into plugins**. For repo mechanics (sync scripts, validation,
release), see [`AGENTS.md`](AGENTS.md) and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Plugin grouping: one plugin per subject

> **Status:** live. The legacy domain bundles (`swe`, `infra`, `informatics`, `dev-tools`, `meta`)
> have been **retired** and every skill and agent is now grouped by subject (`go`, `git`, `r`,
> `terraform`, `review`, …). The *strategy* is
> [#101](https://github.com/nq-rdl/agent-extensions/issues/101); the *mechanism* (the
> registry-owned `{source, leaf}` mapping + sync/packaging) is
> [#102](https://github.com/nq-rdl/agent-extensions/issues/102). Grouping is owned **here** in
> `agent-extensions`, so the upstream `agent-skills` tree stays flat — no upstream restructure is
> required (the earlier upstream-grouping plan, agent-skills#118, was closed as superseded). Design:
> `docs/specs/2026-06-02-plugin-grouping-design.md`; rollout: `docs/specs/2026-06-05-plugin-mapping-migration.md`.

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

The facet is the **leaf** you set in the registry mapping (see rule 6); the upstream skill stays
flat and is renamed to the leaf at sync time.

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

### 6. How grouping is expressed (owned here in `agent-extensions`)

Skills are authored upstream in [`nq-rdl/agent-skills`](https://github.com/nq-rdl/agent-skills) as
a **flat** library — `skills/<skill>/SKILL.md`, one level, no group folders. **Grouping is a
packaging decision and lives here**, in the bundle registry (per
[#102](https://github.com/nq-rdl/agent-extensions/issues/102)):

- A bundle sets `pluginName: <subject>` and lists each skill member as either:
  - a **flat string** `<name>` — packaged as-is (`leaf == <name>`); or
  - an explicit **`{source, leaf}` mapping** — packages the flat upstream `skills/<source>/` under a
    different `leaf` (e.g. `{source: go-gh, leaf: gh}` → `go:gh`).
- `scripts/sync-plugins.sh` copies `skills/<source>/` → `plugins/<subject>/skills/<leaf>/`, renaming
  to the leaf — so the plugin tree is one level deep and Claude Code invokes `<subject>:<leaf>`.
  **The leaf folder name drives invocation.** Claude Code labels the skill in `/`-autocomplete as
  `frontmatter.name || <subject>:<leaf>` — so a present `name:` (the upstream `go-gh` **or** the
  leaf `gh`) *overrides* the namespaced id with a bare, un-prefixed label, and `/go` lists
  `go-gh`/`gh` instead of `go:gh`. So the sync **strips the copy's `name:` entirely**, letting the
  label fall back to `<subject>:<leaf>`. The canonical `skills/` source is never touched; only the
  derivative plugin copy is stripped.
- Validators enforce: every member has a valid shape · no duplicate leaf within a bundle ·
  `pluginName` unique across bundles (`scripts/check_grouping.py`) · each plugin skill copy carries
  **no** frontmatter `name:` (`scripts/validate-plugins.sh`).

So to add `obsidian:bases`, the upstream skill stays flat `skills/obsidian-bases/`; the registry
maps `{source: obsidian-bases, leaf: bases}` under `pluginName: obsidian`. Agents are authored here
under `agents/<name>/agent.md` and placed by subject in the registry. See [`AGENTS.md`](AGENTS.md)
for the mechanical add-and-sync steps.

### 7. Manifests are generated; new subjects join the `rdl` meta-plugin

`plugin.json` and the `marketplace.json` entry for a subject are **generated from
`registry/bundles/<subject>.yaml`** — do **not** hand-edit them. When you add a **new subject**,
it is also registered as a dependency of the **`rdl` meta-plugin**, so `claude plugin install
rdl@rdl` keeps installing the full set. CI consistency checks fail if registry, generated
manifests, and the meta-plugin dependency list disagree.

## Packaging a new skill into a plugin

A skill synced from `nq-rdl/agent-skills` lands in `skills/<name>/` but is **not installable
until you map it into a bundle**. The `sync-skills` workflow only copies — it never maps (it can't
decide the subject for you). The sync PR flags every unmapped skill under "📦 Action required".
Here is the full loop, using a hypothetical `sql-review-analyse` upstream skill that should become
`sql-review:analyse`:

1. **Pick the subject and facet** (the rules above). Subject → the plugin (`sql-review`); facet →
   the action/stage leaf (`analyse`). Never repeat the subject in the facet.
2. **Choose or create the bundle.** If `registry/bundles/sql-review.yaml` exists, add to it;
   otherwise copy an existing single-subject bundle (e.g. `registry/bundles/sops.yaml`) and set
   `id`, `displayName`, `description` (no trailing period), `keywords`, and
   `targets.claude.pluginName: sql-review`.
3. **Add the skill member.** Under `skills:`, write either a flat string (when the upstream name
   already equals the leaf you want) or a `{source, leaf}` mapping to rename:
   ```yaml
   skills:
     - {source: sql-review-analyse, leaf: analyse}   # → /sql-review:analyse
   ```
4. **If it is a brand-new subject, add it to the marketplace order.** Append `sql-review` to the
   `order:` list in `registry/marketplace.yaml` (otherwise it is appended alphabetically with a
   CI `::warning::`). It joins the `rdl` meta-plugin automatically.
5. **Build the plugin tree and manifests:**
   ```bash
   bash scripts/sync-plugins.sh sql-review     # copies skills/<source>/ → plugins/sql-review/skills/<leaf>/
   python3 scripts/generate_manifests.py .     # writes plugin.json + marketplace.json
   python3 scripts/generate_bundles_doc.py .   # refreshes docs/bundles.md
   ```
6. **Validate** exactly what CI will:
   ```bash
   python3 scripts/check_bundle_refs.py .   && \
   python3 scripts/check_grouping.py .      && \
   python3 scripts/generate_manifests.py . --check && \
   python3 scripts/generate_bundles_doc.py . --check && \
   python3 scripts/check_consistency.py .   && \
   bash scripts/validate-plugins.sh
   ```

Adding an **agent** follows the same loop: author `agents/<name>/agent.md` (with frontmatter
`name` + `description`), list it under a bundle's `agents:`, then run steps 5–6. An agent-only
subject (no skill) is fine — give it its own bundle with an empty `skills: []`.
