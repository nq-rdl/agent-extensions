<!--
Sync Impact Report
==================
Version change: (template, unversioned) → 1.0.0
Rationale: Initial ratification. First concrete constitution filled from the
  template; MAJOR baseline for a project newly adopting a formal governance model.

Modified principles: none (initial adoption)
Added principles:
  - I. Spec-First Authority (SpecKit owns the "what")
  - II. Execution via Superpowers (owns the "how")
  - III. Test-Driven Development (NON-NEGOTIABLE)
  - IV. Single-Executor Routing (NON-NEGOTIABLE)
  - V. Definition of Done
Added sections:
  - Workflow Pipeline & Handoff Boundary
  - Quality Gates
  - Governance

Templates reviewed for alignment:
  - .specify/templates/plan-template.md ✅ aligned — its generic "Constitution
    Check" gate now resolves against Principles I–V and the Quality Gates section;
    no edit required.
  - .specify/templates/spec-template.md ✅ aligned — spec scope (the "what") is
    consistent with Principle I; no edit required.
  - .specify/templates/tasks-template.md ✅ aligned — its "tests FIRST, ensure
    they FAIL" discipline matches Principle III; task-list granularity supports
    Principle IV; no edit required.
  - .specify/templates/commands/*.md ⚠ not present in this project (no commands
    template directory); nothing to reconcile.

Follow-up TODOs: none.
-->

# nq-rdl/agent-extensions Constitution

This project is the `rdl` Claude Code marketplace — it authors reusable skills and
agents and publishes them as self-contained plugins. It adopts **SpecKit** for
planning and **Superpowers** for execution. This constitution fixes the boundary
between the two so that every feature moves through a single, predictable pipeline.

## Core Principles

### I. Spec-First Authority (SpecKit owns the "what")

SpecKit planning is **authoritative for the "what"**. Every non-trivial change MUST
originate from the SpecKit planning sequence, run in order:
`/speckit.specify` → `/speckit.clarify` → `/speckit.plan` → `/speckit.tasks`.
The resulting spec MUST live at `specs/NNN-slug/` and is the **durable anchor** for
the work: scope, requirements, and success criteria are decided there, not in commit
messages, chat, or code comments. If execution reveals the spec is wrong, the fix is
to amend the spec and re-run the affected planning stage — not to silently diverge in
the implementation.

**Rationale**: A single, versioned source of intent keeps parallel agents and future
maintainers aligned. When the "what" lives in one reviewable place, the "how" can vary
safely.

### II. Execution via Superpowers (owns the "how")

Superpowers owns the **"how" of execution only**. Once a task list exists, execution
MUST follow the Superpowers workflow in order:
**worktree isolation → TDD red-green-refactor → subagent-driven execution →
code review → finish-branch**
(`using-git-worktrees` → `test-driven-development` → `subagent-driven-development` /
`executing-plans` → `requesting-code-review` / `receiving-code-review` →
`finishing-a-development-branch`). Superpowers MUST NOT redefine scope or requirements;
where an execution decision would change the "what", it is escalated back to SpecKit
(Principle I).

**Rationale**: Execution mechanics (isolation, test discipline, review) are
project-invariant and benefit from a fixed, battle-tested routine, freeing the spec to
focus purely on intent.

### III. Test-Driven Development (NON-NEGOTIABLE)

During execution, TDD is mandatory: write the failing test first, watch it fail
(red), make it pass (green), then refactor. Implementation code MUST NOT be written
before a test that exercises it exists and has been observed to fail. Bugfixes MUST
start with a test that reproduces the bug. This mirrors the task-template rule that
tests are written and confirmed failing before implementation.

**Rationale**: Red-green-refactor is the only reliable evidence that a change does
what the spec claims and that the test actually tests it.

### IV. Single-Executor Routing (NON-NEGOTIABLE)

Exactly one executor drives any given task, and the planning pipeline is never
short-circuited. Two anti-patterns are **forbidden**:

- **No dual executor.** For a single task, you MUST NOT run both `/speckit.implement`
  AND the Superpowers execution workflow. Choose one executor per task; running both
  produces conflicting edits to the same worktree and non-deterministic state.
- **No skipping `/speckit.tasks`.** You MUST NOT hand work to Superpowers execution
  without first running `/speckit.tasks`. Superpowers plan-decomposition expects the
  small, independently-testable 2–5 minute tasks that `/speckit.tasks` produces;
  skipping it starves the executor of its unit of work.

**Rationale**: These are the routing rules that keep the SpecKit/Superpowers handoff
unambiguous. Violating either collapses the boundary this constitution exists to
protect.

### V. Definition of Done

A task, and the branch that carries it, is **done** only when all of the following
hold — no exceptions, no "will fix later":

- **Validation is green.** No task is marked complete while its validation is failing
  (per `verification-before-completion`: evidence before assertions).
- **A changie fragment exists.** Every change ships with a changelog entry created via
  `changie new` (the `changelog-check.yml` gate enforces this; bypass only with the
  `skip-changelog` label for genuinely changelog-exempt changes).
- **Repo CI-parity checks pass.** The local `lefthook` checks — which mirror
  `validate.yml` — pass before the branch is finished.

**Rationale**: A crisp, machine-checkable done state is what lets subagents and
reviewers trust "complete" without re-verifying from scratch.

## Workflow Pipeline & Handoff Boundary

Every feature moves left-to-right through one pipeline. **SpecKit** owns the left half;
**Superpowers** owns the right half. The handoff is a hard boundary:

```
  ── SpecKit (the "what") ────────────────────┐   ┌──── Superpowers (the "how") ────
  /speckit.specify → /speckit.clarify →         │   │  worktree → TDD → subagent exec
  /speckit.plan → /speckit.tasks               │   │  → code review → finish-branch
                                       ────────>│HANDOFF│>────────
                                    (task list = the boundary)
```

- The **handoff happens at the task-list boundary** — after `/speckit.tasks` has
  produced `specs/NNN-slug/tasks.md`. Before that point, no execution begins.
- Crossing the boundary is one-directional per task: once execution starts, changing
  the "what" means returning to SpecKit, not editing scope in place.
- `/speckit.analyze` and `/speckit.checklist` are planning-side aids (left of the
  boundary) and MAY be used to harden a spec before handoff.

## Quality Gates

Concrete gates that operationalize Principle V for this repository. Canonical content
lives under `skills/` and `agents/`; the plugin trees under `plugins/` are generated —
never hand-edit generated manifests. Before a branch is finished:

- `bash scripts/sync-plugins.sh` has been run after any skill/agent edit, so plugin
  trees match canonical sources.
- `python3 scripts/generate_manifests.py . --check` and
  `python3 scripts/generate_bundles_doc.py . --check` report no drift.
- `bash scripts/validate-plugins.sh`, the bundle/grouping/consistency checks, and
  `asctl repo-check` (built from `tools/asctl/`) pass.
- The pipeline unit tests (`python3 -m unittest discover -s tests`) pass.

These are exactly the checks `lefthook` and `validate.yml` run; passing them locally is
the CI-parity requirement of Principle V.

## Governance

This constitution supersedes ad-hoc workflow habits. It governs how work flows through
SpecKit and Superpowers; it does not replace `CLAUDE.md`/`CONTRIBUTING.md` for
content-authoring conventions, which remain in force alongside it.

- **Authority & compliance.** The `/speckit.plan` "Constitution Check" gate MUST be
  evaluated against Principles I–V and the Quality Gates section before Phase 0 and
  re-checked after design. Reviewers MUST verify compliance; any deviation must be
  recorded in the plan's Complexity Tracking table with a justification and the
  rejected simpler alternative.
- **Amendment procedure.** Amendments are proposed as a spec/PR that edits this file,
  updates the Sync Impact Report, and reconciles the dependent `.specify/templates/`.
  An amendment merges only after review confirms the templates stay in sync.
- **Versioning policy.** This constitution is versioned semantically:
  **MAJOR** for backward-incompatible governance changes or principle
  removals/redefinitions; **MINOR** for a newly added principle or materially expanded
  guidance; **PATCH** for clarifications and non-semantic wording fixes.

**Version**: 1.0.0 | **Ratified**: 2026-07-02 | **Last Amended**: 2026-07-02
