# Playbook: SpecKit ⇄ Superpowers routing templates (#205)

Part of epic #207. Drop-in templates for a **target** speckit repo that prevent
dual-ownership drift: SpecKit planning stays authoritative, Superpowers owns execution,
and the handoff is explicit at the task-list boundary.

> **Interim delivery.** Per ADR-0001 (#204, the epic's re-architecture), this payload
> migrates into the planned **rdl-routing** speckit extension in
> `nq-rdl/spec-kit-extensions` — installed per repo via the RDL catalog
> (`specify extension add rdl-routing`) instead of copied from here. Until that ships,
> this playbook is the copy-paste source of truth; when it ships, this file becomes a
> pointer. The templates are deliberately zero-dependency so they stand alone either way.

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

`CLAUDE.md` is re-read at the start of **every** session and after `/clear`, so routing
placed here survives context resets — guidance stated once in chat or during planning is
lost the moment context clears. The routing block is durable *because* it lives in
`CLAUDE.md`, not in the conversation; that is the whole reason it belongs here rather than
being explained once and forgotten.

```markdown
## SpecKit + Superpowers routing (read every session, including after `/clear`)

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
  otherwise duplicate work and fight over the same files.
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

The archive+strip mechanics are planned to move speckit-side as the **rdl-adr**
extension's `speckit.adr.finalize` command (see ADR-0001, #204), so GitHub-PR merges get
the same mechanization as CLI merges; the principle text above is unaffected.

## 5. Worktree isolation: standardize on one tool (#206)

The execution discipline in §1/§2 begins with **worktree isolation** — but three
implementations can supply it, and layering all three into one workflow reintroduces
exactly the divergence this playbook exists to prevent:

- `speckit-lifecycle`'s `provision-worktree.sh` / `merge-spec.sh` (#124),
- `cc-spex`'s `spex-worktrees` extension (#203),
- Superpowers' own `using-git-worktrees` skill.

Route worktree provisioning through a **single owner**: the speckit-side provision/merge
mechanics — today `speckit-lifecycle`'s bundled scripts, migrating to the planned
**rdl-worktree** extension (`nq-rdl/spec-kit-extensions`; see ADR-0001, #204). The #206
evaluation settled the roles: the bespoke semantics (`NNN` derivation anchored to
`specs/`, spec seeding, topology-aware merge) are the automation owner, and Worktrunk's
`wt` CLI (`worktrunk`, in this repo's curated external-marketplace set since #147) is the
recommended **interactive complement** — not the owner. Superpowers' `using-git-worktrees`
is upstream (out of scope to change) — note only whether it complements or conflicts for
the target repo. Never run more than one provisioning mechanism against the same task.

## How this is delivered to a repo

**Target:** `specify extension add rdl-routing` from the RDL catalog
(`nq-rdl/spec-kit-extensions`) installs §1/§2/§4 natively — any agent or a human can run
it. **Interim:** `speckit-lifecycle` (#124) offers this playbook when it sets a repo up —
apply §1 and §4 to `constitution.md` and §2 to `CLAUDE.md`, on consent only.

## References

- Epic constitution (this repo, `.specify/memory/constitution.md`) — encodes the same principles.
- #204 — ADR-0001: RDL-owned speckit extensions (`superb` evaluated, not adopted).
- #203 — cc-spex evaluation. #206 — worktree evaluation (bespoke semantics own automation; `wt` complementary).
- #124 — `speckit-lifecycle` (offers these at setup).
- `nq-rdl/spec-kit-extensions` — target home of rdl-routing / rdl-adr / rdl-worktree / brainstorm-handoff.
