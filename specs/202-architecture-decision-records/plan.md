# Implementation Plan: Architecture Decision Records Skill (Structured MADR)

**Branch**: `202-architecture-decision-records` | **Date**: 2026-07-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/202-architecture-decision-records/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Author a new documentation-only skill, `skills/architecture-decision-records/`, that
detects architectural-decision moments **inside an ordinary coding session**, offers
(consent-gated) to capture them, and emits **Structured MADR v4** records under
`docs/adr/` with a maintained index. It answers "why did we choose X?" from that
index and adds a **speckit-archival** path that maps a merged `specs/NNN-slug/` spec
into an ADR. The skill is packaged into the existing **`planning`** bundle and
cross-linked with the existing `agents/adr-generator/` (the agent stays for one-shot
generation; the skill adds in-session detection + speckit archival).

The three open questions the spec deferred to implementation are **decided here**
(recorded in `research.md`): format = **Structured MADR v4**; relationship to the
agent = **cross-link, keep both**; filename = **`NNNN-title.md`** (greenfield;
pre-existing `docs/adr/` files, if any, are left byte-unchanged).

## Technical Context

This feature ships a **Markdown documentation skill** in a skill/agent marketplace
repo — there is no runtime, service, or database. The "Technical Context" fields
below are therefore intentionally `N/A`; the real constraints are the repo's
authoring, validation, and packaging pipeline.

**Language/Version**: N/A
**Primary Dependencies**: N/A
**Storage**: N/A
**Testing**: N/A
**Target Platform**: N/A
**Project Type**: Documentation skill (marketplace catalog content)
**Performance Goals**: N/A
**Constraints**: N/A
**Scale/Scope**: N/A

**Real technical context (repo-specific):**

- **Deliverable medium**: a single canonical skill at `skills/architecture-decision-records/SKILL.md`
  (uppercase manifest name required by `asctl`), authored in Markdown per the repo
  Language Policy for documentation-only skills — **no CLI wrapper, no MCP server**.
- **Validation surface**: `asctl repo-check` (built from `tools/asctl/`) validates the
  skill against the agentskills.io spec + directory-structure standard. Hard limits:
  frontmatter `name` (required, ≤ 64 runes — `architecture-decision-records` = 29),
  `description` (required, ≤ 1024 runes); manifest filename must be exactly `SKILL.md`;
  only `SKILL.md` and `lychee.toml` allowed at the skill top level; supporting files
  live under `references/`.
- **Format spec pinned**: MADR (`adr/madr`) **v4** — the version is pinned in the skill
  frontmatter `compatibility:` so drift is visible/reviewable (FR-004), with a
  verify-canonical guard pointing at `https://adr.github.io/madr/` /
  `https://github.com/adr/madr`.
- **Packaging pipeline**: add the skill to `registry/bundles/planning.yaml` `skills:`,
  then `bash scripts/sync-plugins.sh planning` copies canonical → `plugins/planning/skills/`.
  `python3 scripts/generate_manifests.py .` and `python3 scripts/generate_bundles_doc.py .`
  regenerate manifests/docs. Cross-linking the agent means editing
  `agents/adr-generator/agent.md` and re-syncing (`plugins/planning/agents/adr-generator.md`).
- **Changelog**: a `changie` fragment (kind `Added`) is mandatory (Constitution V,
  `changelog-check.yml`).
- **Existing collisions to reconcile in-content**: the agent writes `adr-NNNN-slug.md`;
  the skill writes `NNNN-title.md`. Both target `docs/adr/`. The skill must derive the
  next number from the **highest existing number across both conventions** (max + 1,
  never reused) and never rename/rewrite existing files (FR-006, FR-008, SC-007).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against the project constitution v1.0.0 (Principles I–V + Quality Gates).

| Principle | Status | Notes |
|---|---|---|
| **I. Spec-First Authority** | PASS | Work originates from `specs/202-architecture-decision-records/spec.md`; scope/requirements/success criteria live there. The three deferred questions (FR-011–013) are resolved in `research.md` under this spec, not in chat/commits. |
| **II. Execution via Superpowers** | PASS (deferred) | This is the planning stage. Execution (worktree → TDD → subagent → review → finish-branch) happens after `/speckit.tasks`. No scope is redefined here. |
| **III. Test-Driven Development** | PASS (adapted) | A documentation skill has no unit-testable code. The "red→green" evidence is the **validation gate**: `asctl repo-check`, `check_grouping.py`, `generate_manifests.py --check`, `check_consistency.py`, `validate-plugins.sh` fail before the skill/registry edits and pass after. `quickstart.md` defines the behavioral acceptance checks (consent-gating, MADR completeness, monotonic numbering, retrieval honesty, spec mapping) that stand in for tests, each traceable to an SC. |
| **IV. Single-Executor Routing** | PASS | One executor per task; `/speckit.tasks` runs before any Superpowers execution. No dual-executor. |
| **V. Definition of Done** | PASS (planned) | Done requires: validation green, a `changie` fragment (FR-016), and CI-parity (`lefthook`) passing. Captured as explicit tasks in Phase 2. |

**Quality Gates (repo-specific):** the skill is canonical content under `skills/`;
`plugins/planning/` is generated — never hand-edited. After the skill/agent edit, the
plan mandates `sync-plugins.sh`, the two `--check` generators, `validate-plugins.sh`,
the bundle/grouping/consistency checks, `asctl repo-check`, and the pipeline unit
tests. **No violations → Complexity Tracking is empty.**

**Post-Design re-check (after Phase 1):** PASS — the design adds only Markdown content
+ one registry line + generated copies + one changie fragment; no new project, no new
language, no MCP server, no generated-manifest hand-edits. Constitution remains
satisfied.

## Project Structure

### Documentation (this feature)

```text
specs/202-architecture-decision-records/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output — resolves FR-011/012/013 + MADR v4 shape
├── data-model.md        # Phase 1 output — ADR, index, template, spec→ADR mapping entities
├── quickstart.md        # Phase 1 output — behavioral acceptance walkthrough (SC-linked)
├── contracts/           # Phase 1 output — skill trigger, MADR record, index, spec-map contracts
│   ├── skill-frontmatter.md
│   ├── adr-madr-v4-template.md
│   ├── adr-index.md
│   └── spec-to-adr-mapping.md
├── checklists/          # pre-existing (requirements checklist)
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created by /speckit.plan)
```

### Source Code (repository root)

This is a marketplace catalog, not an application; "source" is canonical skill/agent
content plus the registry that packages it. Concrete paths this feature touches:

```text
skills/
└── architecture-decision-records/        # NEW — canonical skill (single edit point)
    ├── SKILL.md                          #   frontmatter (name, description, license,
    │                                     #   compatibility: MADR v4 pin) + skill body
    └── references/                       #   supporting files (progressive disclosure)
        ├── madr-v4-template.md           #   the Structured MADR v4 skeleton emitted
        ├── index-template.md             #   docs/adr/README.md index seed + row format
        └── spec-to-adr-mapping.md        #   speckit spec fields → MADR fields table

agents/
└── adr-generator/
    └── agent.md                          # EDIT — add cross-reference to the skill

registry/
└── bundles/
    └── planning.yaml                     # EDIT — add the skill under skills:

plugins/                                  # GENERATED — via sync-plugins.sh (do not hand-edit)
└── planning/
    ├── skills/architecture-decision-records/   # real-file copy of the canonical skill
    └── agents/adr-generator.md                 # re-synced copy carrying the cross-link

docs/bundles.md                           # GENERATED — regenerated by generate_bundles_doc.py
.claude-plugin/marketplace.json           # GENERATED — regenerated by generate_manifests.py
plugins/planning/.claude-plugin/plugin.json  # GENERATED — regenerated by generate_manifests.py
.changes/unreleased/*.yaml                # NEW — changie fragment (kind: Added)

docs/adr/                                 # NOT created by this feature — the skill creates it
                                          #   at RUNTIME only on explicit user consent (FR-007).
```

**Structure Decision**: Single canonical documentation skill under
`skills/architecture-decision-records/` (leaf name equals directory name, so it enters
the `planning` bundle as a **flat** member — no `{source, leaf}` rename needed), with
supporting material under `references/` per the agentskills.io directory standard. The
`planning` plugin tree is regenerated from canonical sources; generated manifests/docs
are refreshed by their scripts. `docs/adr/` is a **runtime artifact the skill offers to
create in the user's own project**, not a repo directory this feature adds.

## Complexity Tracking

> No Constitution Check violations — this table is intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
