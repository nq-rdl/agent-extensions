# Playbook: SpecKit ⇄ Superpowers routing templates (#205)

Part of epic #207. Drop-in templates for a **target** speckit repo that prevent
dual-ownership drift: SpecKit planning stays authoritative, Superpowers owns execution,
and the handoff is explicit at the task-list boundary. Pair with #204's extension
recommendation (the `superb` gates mechanically enforce what these templates route by
convention).

## 1. Constitution clause (add to `constitution.md`)

```markdown
## Principle: SpecKit plans, Superpowers executes

SpecKit is authoritative for the **what**. The `/speckit.specify → /speckit.clarify →
/speckit.plan → /speckit.tasks` sequence owns scope, and `specs/NNN-slug/` is the
durable record. Do not produce a parallel spec by any other means.

Superpowers owns the **how** of execution only, and only after `/speckit.tasks`:
worktree isolation → TDD (red-green-refactor) → subagent-driven execution → code review
→ finish-branch. The handoff is fixed at the **task-list boundary** — execution begins
from `tasks.md`, never before it exists.

Definition of done: no task is marked complete with failing validation; every change
carries a changelog entry; the repo's CI-parity checks pass.
```

## 2. CLAUDE.md routing block (add to `CLAUDE.md`)

```markdown
## SpecKit + Superpowers routing (read every session)

- **Constitution**: `.specify/memory/constitution.md` is authoritative. Read it before
  planning or executing. It routes ownership (SpecKit = planning, Superpowers = execution).
- **Where specs live**: `specs/NNN-slug/` (spec.md, plan.md, tasks.md). `NNN` is
  sequential and never reused.
- **Planning is SpecKit's**: use `/speckit.specify → clarify → plan → tasks`. Do NOT let
  brainstorming/writing-plans create a parallel spec — if a "let's build X" cue fires,
  route it into `/speckit.specify`.
- **Execution is Superpowers'**: only after `/speckit.tasks`. worktree → TDD → subagent →
  review → finish-branch.
- **Definition of done**: validation green before a task is `[x]`; changelog entry added;
  CI-parity green.
```

## 3. Anti-patterns (call these out explicitly)

- **Dual-executor conflict** — running **both** `/speckit.implement` **and** the
  Superpowers execution workflow on the same task. Pick one executor per task; they will
  otherwise duplicate work and fight over the same files. (The `superb` verify gate, #204,
  makes this mechanical.)
- **Skipping `/speckit.tasks`** — Superpowers' plan-decomposition expects the small
  2–5 minute tasks that `/speckit.tasks` produces. Skipping it forces duplicate
  re-planning at execution time. Never hand off to execution without `tasks.md`.

## 4. Spec lifecycle: ephemeral specs, durable ADRs

Add this principle to `constitution.md` alongside §1:

```markdown
## Principle: specs are ephemeral, ADRs are durable

A `specs/NNN-slug/` directory is scaffolding that lives on its worktree/integration
branch only. Its decision points — context, options considered, chosen outcome — are the
lasting value, and are captured as an ADR (`docs/adr/NNNN-*.md`) at merge time.

On a merge to **trunk/main**: (1) archive the spec's decisions as an ADR, then (2) strip
the ephemeral speckit artifacts from trunk — the `specs/NNN-slug/` directory, the
`.specify/` scaffolding, and the installed speckit phase skills. Trunk keeps only the
real deliverables plus `docs/adr/`. On a merge to an **integration branch**, the spec is
retained (work continues). `speckit-lifecycle`'s `merge-spec.sh` performs the spec strip
automatically on a trunk merge.
```

## How this is delivered to a repo

`speckit-lifecycle` (#124) references this playbook when it sets a repo up: apply §1 to
`constitution.md` and §2 to `CLAUDE.md`, then (optionally) add the `superb` gates from
#204 for mechanical enforcement.

## References

- Epic constitution (this repo, `.specify/memory/constitution.md`) — encodes the same principles.
- #204 — extension recommendation (mechanical enforcement layer).
- #203 — cc-spex evaluation. #124 — `speckit-lifecycle` (applies these at setup).
