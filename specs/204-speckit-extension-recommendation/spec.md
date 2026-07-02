# Feature Specification: SpecKit-side Superpowers extension recommendation

**Feature Branch**: `204-speckit-extension-recommendation`
**Created**: 2026-07-02
**Status**: Recommendation recorded
**Input**: Epic #207 child #204 — recommend a SpecKit-native extension that enforces the
worktree → TDD → subagent → review → finish discipline in a target speckit repo.

## Problem

SpecKit's *own* extension system (`specify extension add`, scoped per target repo) is a
different layer from this repo's Claude Code plugin set (#203). Teams need a
recommendation for which SpecKit-native extension to wire into a fresh speckit repo to
enforce Superpowers execution discipline, and how it addresses the reported friction:
`constitution.md` drift during execution, and session-continuity across pauses.

## Clarifications

### Session 2026-07-02

- Q: Where should the operational edge cases (Spec Kit `>=0.12.0`, catalog `--install-allowed`, external-catalog-disallowed fallback) be recorded — spec, plan, or ADR? → A: Capture in `plan.md` on this branch now; defer the ADR to the epic-branch (#207) merge. No direct pushes to `main`.

## Options to compare

- **`RbBtSn0w/spec-kit-extensions` → `superpowers-bridge`** (catalog id `superb`): adds
  evidence-first gates to SpecKit's commands — plan-gate validation, RED-GREEN-REFACTOR
  enforcement before `/speckit.implement`, and a post-implementation verify gate.
- **`cc-spex` bundled extensions** (register at spec-kit hooks `after_specify`/`after_tasks`/`after_implement`).
- **Minimal hand-rolled constitution clause** (the #205 routing baseline).

## Requirements

- FR-1: Compare the three options against the two friction points (constitution drift, session continuity).
- FR-2: Recommend one (or a layered combination), consistent with #203 (cc-spex conditional-not-adopted).
- FR-3: Give concrete setup steps for a **target** speckit repo (not this repo).
- FR-4: Deliver as a `docs/` playbook that `speckit-lifecycle` (#124) can reference.
- FR-5: changie fragment.

## Success Criteria

- SC-1: `docs/playbooks/speckit-superpowers-extension.md` exists with the comparison, a clear recommendation, and target-repo setup steps.
- SC-2: The recommendation is consistent with #203 and #205.

## Non-goals

Building a new bridge extension from scratch; adopting cc-spex (deferred per #203).
