# Feature Specification: Standardize worktree management on Worktrunk

**Feature Branch**: `206-worktrunk-consolidation`
**Created**: 2026-07-02
**Status**: Decision recorded
**Input**: Epic #207 child #206 — evaluate consolidating `speckit-lifecycle` (#124) worktree scripts and any `cc-spex` worktree extension onto Worktrunk (`wt`).

## Problem

Three worktree-lifecycle implementations sit in one workflow: #124's bespoke
`provision-worktree.sh`/`merge-spec.sh`, `cc-spex`'s `spex-worktrees` (if adopted per
#203), and Superpowers' own `using-git-worktrees`. Three parallel implementations risk
the divergence this epic exists to avoid. Should #124's scripts delegate to `wt`?

## What this issue decides

A recorded decision — **consolidate onto Worktrunk** (update `speckit-lifecycle` to
delegate) **or keep bespoke scripts** (with rationale) — after comparing `wt`'s
capabilities against #124's script requirements and the overlap with `cc-spex`.

## Requirements

- FR-1: Compare `wt` against each `provision-worktree.sh`/`merge-spec.sh` requirement:
  NNN derivation, conflict guards, `--base` parentage, merge-target topology, post-merge cleanup, worktree location.
- FR-2: Document overlap with `cc-spex`'s `spex-worktrees` given #203's evaluation (`docs/evaluations/203-cc-spex-evaluation.md`, PR #213: conditional — do not adopt now).
- FR-3: Record the decision (consolidate / keep bespoke) with rationale.
- FR-4: If keeping bespoke, confirm #124's acceptance criteria need no Worktrunk dependency; if consolidating, update them.
- FR-5: Capture the follow-up: whether `wt`'s worktree location should be remapped to `.claude/worktrees/` (the epic-execution edge case surfaced during Wave 0).
- FR-6: changie fragment.

## Success Criteria

- SC-1: A `docs/evaluations/206-worktrunk-consolidation.md` decision doc exists with the capability matrix, the decision, and rationale.
- SC-2: The decision is consistent with #124 (no orphaned dependency) and with #203's recommendation (cc-spex conditional-no; if later adopted, `spex-worktrees` stays disabled — no competing worktree mechanism).

## Non-goals

Changing the `worktrunk` plugin itself; changing Superpowers' `using-git-worktrees`.
