# Phase 1 Data Model: SpecKit lifecycle skill

This feature has no runtime database; its "entities" are the filesystem/git artifacts the
skill and scripts operate on. Each is defined by its identity, fields (observable
attributes), relationships, lifecycle/state transitions, and the validation rules the spec
imposes.

## Entity: Spec

- **Identity**: `NNN` — a monotonic 3-digit integer, zero-padded, **never reused**.
- **Anchor**: `specs/NNN-slug/` (durable record; survives merge forever).
- **Fields**:
  - `NNN` (string, `^\d{3}$`)
  - `slug` (kebab-case description)
  - `branch` = `NNN-slug` (exists while in progress; deleted on merge)
  - `worktree_slot` = `.claude/worktrees/NNN` (exists while in progress; removed on merge)
  - `parent_branch` (the branch it was cut from — trunk or an integration branch)
  - artifacts under `specs/NNN-slug/`: `spec.md`, `plan.md`, `research.md`, `tasks.md`,
    optional `data-model.md`/`quickstart.md`/`contracts/`
- **Relationships**: 1 Spec ↔ 1 branch ↔ 0..1 Worktree slot; many Specs → 1 Parent branch;
  1 Spec → ordered sequence of Phases.
- **State transitions**:
  `provisioned` (branch + slot exist) → `in-progress` (phases advancing) →
  `completed` (all tasks `[x]`) → `merged` (branch + slot removed, `specs/NNN-slug/` retained).
  A merge that **conflicts** does not transition to `merged`: `merge-spec.sh` aborts and the Spec
  stays `completed` with its branch + slot intact (Clarification 2026-07-02).
  There is **no** `planned-but-unprovisioned` state — pre-provisioning ideas live in a project
  tracker, never in `specs/` on trunk (FR-003).
- **Validation rules**:
  - `NNN` = max(existing `NNN` across `git branch -a`, `specs/`, `.claude/worktrees/`) + 1 (FR-006).
  - A derived/target `NNN` that already exists anywhere → conflict-guard abort (FR-006).
  - After merge, `NNN` is never re-derived or reused (FR-008).

## Entity: Worktree slot

- **Identity**: `.claude/worktrees/NNN` (path keyed by `NNN`).
- **Fields**: filesystem path; the checked-out branch (`NNN-slug`); working-tree cleanliness.
- **Relationships**: 1:1 with a Spec's branch while in progress.
- **State transitions**: `absent` → `provisioned` (via `provision-worktree.sh`) →
  `removed` (via `merge-spec.sh`, **before** branch deletion).
- **Validation rules**:
  - All feature work happens **inside** the slot — never on trunk or an integration branch
    (core invariant).
  - Removal is **idempotent** (already-absent slot is a no-op success) (FR-007).
  - A dirty slot at merge time → **loud refusal**, no data loss (FR-007, SC-006).
  - Removed strictly **before** `git branch -d` (Git refuses deletion of a branch checked out
    in a worktree) (FR-007, SC-006).

## Entity: Phase

- **Identity**: phase name within the SpecKit sequence.
- **Ordered default sequence**: `specify → clarify → plan → tasks → [checklist] → analyze → implement`.
- **Fields**:
  - `name`
  - `skill` (the `/speckit-*` command or, for implement, the loop/strategy)
  - `complete_when` (completion predicate)
  - `conditional` (bool — only `checklist` is conditional; default omits it)
- **Completion predicates**:
  | Phase | Complete when |
  |---|---|
  | Specify | `spec.md` exists |
  | Clarify | no `[NEEDS CLARIFICATION]` markers remain |
  | Plan | `plan.md` + `research.md` exist |
  | Tasks | `tasks.md` has ≥ 1 task |
  | Checklist (conditional) | all declared checklists pass |
  | Analyze | no blockers flagged |
  | Implement | all `tasks.md` items `[x]` |
- **Relationships**: belongs to a Spec; the active phase is the **first incomplete** one.
- **State transitions**: `pending → active → complete`; advancement is strictly forward from
  the first incomplete phase.
- **Validation rules**:
  - The sequence is **repo-configurable** via `CLAUDE.md` or `.specify/`; the built-in default
    omits `checklist` (FR-011).
  - A **declared** phase is **never skipped** (FR-010/FR-011).
  - Implement strategy is **pluggable**: default single-agent loop, or a declared external
    strategy skill (e.g. `forge-quill`) (FR-014).
  - The default Implement loop is **fail-stop**: a task that can't pass validation halts
    advancement (left `[ ]`, task + output reported); later tasks are not started
    (FR-012, Clarification 2026-07-02).

## Entity: Parent branch

- **Identity**: a branch name (trunk, or an integration/epic branch).
- **Fields**: name; whether it is trunk (from `origin/HEAD` discovery).
- **Relationships**: parent of 1..many Specs; determines each child Spec's **merge target**.
- **Validation rules**:
  - Trunk discovered at runtime (`git symbolic-ref refs/remotes/origin/HEAD`; fallback
    `main`/`master`/`trunk`/current-non-spec) — never hardcoded (FR-015).
  - Merge target resolved from git topology via `git merge-base`, not assumed to be trunk
    (FR-007).

## Entity: Bundled script

- **Identity**: `provision-worktree.sh` | `merge-spec.sh` under `skills/speckit-lifecycle/scripts/`.
- **Fields**: version (shipped alongside the skill), CLI signature, exit code, stdout contract,
  side effects (see `contracts/`).
- **Relationships**: invoked by the skill in root mode; probes the target repo's optional
  `.specify/scripts/bash/create-new-feature.sh`.
- **Validation rules**:
  - Deterministic git logic ships as scripts, **not** embedded bash (FR-005).
  - Each probes for `create-new-feature.sh` and falls back to bare git when absent (FR-006).
  - Independently testable via the `.tests/` bats suite (FR-018).
