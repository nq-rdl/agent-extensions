# Specification Quality Checklist: CLAUDE.md and constitution routing guidance

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-07-03
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [ ] Success criteria are technology-agnostic (no implementation details)
- [ ] All acceptance scenarios are defined
- [ ] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [ ] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

This is a **documentation / copy-paste-templates** feature whose subject matter *is* the
integration between two named frameworks. Several standard checklist items are treated as
justified exceptions rather than defects:

- **Framework/command/CLI names are domain vocabulary, not leaked implementation.** SpecKit,
  Superpowers, `/speckit.tasks`, and Worktrunk's `wt` are the *what* this playbook routes;
  a tech-agnostic phrasing would make the deliverable meaningless. This is why the
  "technology-agnostic success criteria" and "no implementation details" items are noted as
  intentional exceptions (the latter still holds for incidental tech — no languages, no APIs,
  no code structure leak in).

- **No explicit User Scenarios / acceptance-scenario / edge-case sections.** The spec keeps a
  deliberately terse, hand-authored structure (Problem → What it delivers → Requirements →
  Success Criteria → Non-goals). Expanding to full spec-template scenarios was offered and
  **declined** in favor of a targeted gap-fix; the unchecked items above reflect that choice,
  not an oversight. Each FR still maps to a verifiable artifact in
  `docs/playbooks/speckit-constitution-routing.md`.

- **#206 synthesis reconciled (2026-07-03).** The spec's Input line claimed a #203/#204/#206
  synthesis that the deliverable did not contain. FR-6 + SC-3 were added and the playbook now
  synthesizes #206 (single worktree owner, Worktrunk `wt`, §5), making the claim true. The
  CLAUDE.md block's after-`/clear` rationale (issue #205's stated motivation) was also made
  explicit in playbook §2.

Items marked incomplete are accepted deviations for this feature type, not blockers for
`/speckit.plan` (planning already exists at `plan.md`).
