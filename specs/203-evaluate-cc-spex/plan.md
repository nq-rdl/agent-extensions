# Implementation Plan: Evaluate cc-spex for the curated external-marketplace set

**Branch**: `203-evaluate-cc-spex` | **Date**: 2026-07-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/203-evaluate-cc-spex/spec.md`

## Summary

Produce a single, evidence-backed evaluation doc at `docs/evaluations/203-cc-spex-evaluation.md`
that decides whether `rhuss/cc-spex` (distribution marketplace `cc-rhuss-marketplace`,
plugin `spex`) should join the team's curated external-plugin set. The doc assesses three
dimensions — friction-point fit (constitution drift, session continuity), overlap/conflict
with `speckit-lifecycle` (#124) + the `review` and `planning` bundles, and maintenance/trust
(release cadence, issue responsiveness, `autoUpdate` suitability) — and records an adopt /
don't-adopt / conditional-adopt verdict. On an adopt or conditional-adopt verdict it embeds
**unapplied** draft diffs for `docs/external-marketplaces.md` and `.claude/settings.json`.
The technical approach is **research + writing only**: verify every factual claim against
live upstream sources (GitHub API for releases/issues/manifests, spec-kit repo, the two
marketplace.json files) and cite URLs. The deliverable **never edits** `.claude/settings.json`
or `docs/external-marketplaces.md` — applying the draft diffs is a user-gated follow-up.

## Technical Context

**Language/Version**: Markdown (documentation deliverable); Bash + `gh` CLI for source verification
**Primary Dependencies**: `gh` (GitHub API for cc-spex releases/issues/manifests + github/spec-kit), WebSearch/WebFetch for corroboration
**Storage**: Files under `docs/evaluations/` and `specs/203-evaluate-cc-spex/`
**Testing**: Repo CI-parity gates (`asctl repo-check`, `scripts/validate-plugins.sh`, `generate_manifests.py --check`, `generate_bundles_doc.py --check`, bundle/grouping/consistency checks, `python3 -m unittest discover -s tests`); no unit tests apply to a markdown doc (no runtime surface)
**Target Platform**: This repo's docs tree (consumed by maintainers)
**Project Type**: Documentation / evaluation deliverable (no product code)
**Performance Goals**: N/A
**Constraints**: MUST NOT edit `.claude/settings.json` or `docs/external-marketplaces.md` (adopt decision is user-gated); MUST NOT re-host cc-spex content in `rdl`; any wiring targets the distribution marketplace `cc-rhuss-marketplace` (never the dev-only `spex-plugin-development`); every factual claim carries a cited source URL
**Scale/Scope**: One evaluation doc; six cc-spex extensions × three comparison targets; one changie fragment

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Spec-First Authority** — PASS. Scope/requirements/success criteria are fixed in
  `specs/203-evaluate-cc-spex/spec.md` (the durable anchor); this plan derives from it and
  does not redefine the "what".
- **II. Execution via Superpowers** — PASS (adapted). Work runs in an isolated git worktree
  (`203-evaluate-cc-spex`), proceeds through subagent-driven execution, and finishes with a
  reviewable branch. There is no product code, so the code-review/refactor legs apply to the
  doc's internal consistency and its cited sources rather than to source files.
- **III. Test-Driven Development (NON-NEGOTIABLE)** — N/A with justification, recorded in
  Complexity Tracking per the constitution's Governance deviation clause. The deliverable is a
  markdown evaluation with no runtime surface to exercise;
  there is no implementation code that a failing test could gate. Verification is the doc's
  measurable success criteria (SC-001…SC-007) plus the repo CI-parity gates.
- **IV. Single-Executor Routing (NON-NEGOTIABLE)** — PASS. Exactly one executor — the
  Superpowers execution workflow (`subagent-driven-development`) — drives this task, matching
  Check II; `/speckit.tasks` runs first so `tasks.md` exists before execution begins, and
  `/speckit.implement` is **not** also run. No dual executor.
- **V. Definition of Done** — PASS (planned). Validation green (CI-parity gates), a changie
  fragment added, lefthook/`validate.yml`-equivalent checks pass before finish.

## Project Structure

### Documentation (this feature)

```text
specs/203-evaluate-cc-spex/
├── plan.md              # This file (/speckit.plan output)
├── research.md          # Phase 0 output: verified upstream facts + citations
├── spec.md              # Feature spec (already present)
├── checklists/
│   └── requirements.md  # Spec quality checklist (already present)
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

No `data-model.md`, `contracts/`, or `quickstart.md`: this feature exposes no external
interface and defines no persisted entities beyond the doc's own sections, so those Phase 1
artifacts are intentionally skipped (see plan-template Phase 1 guidance — "skip if project is
purely internal").

### Source Code (repository root)

```text
docs/
└── evaluations/
    └── 203-cc-spex-evaluation.md   # THE deliverable (research + recommendation)

.changes/
└── unreleased/
    └── <kind>-<slug>.yaml          # changie fragment (Definition of Done)
```

**Structure Decision**: This is a documentation deliverable. The only product artifact is
`docs/evaluations/203-cc-spex-evaluation.md` plus a changie fragment. `docs/external-marketplaces.md`
and `.claude/settings.json` are shown as **draft diffs inside the doc** and are never edited by
this feature.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Principle III (TDD) not applied as red-green-refactor | The deliverable is a markdown evaluation doc with no runtime/behavioral surface; there is no implementation code for a test to gate | Writing a "failing test" for prose would be theater, not evidence. The honest verification is (a) the doc's own measurable success criteria SC-001…SC-007, and (b) the repo CI-parity gates (`asctl repo-check`, `validate-plugins.sh`, generated-artifact `--check`, `unittest`) — all of which run and must pass before the branch is finished |
