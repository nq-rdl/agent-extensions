---
license: CC-BY-4.0
compatibility: >-
  spec-kit >=0.12 (verified against 0.13.4), superpowers >=6.1 (verified against
  6.1.1). Coupled to both systems' behavior, so phase names and git side effects are
  runtime-discovered, not hardcoded: in current spec-kit (0.13.x) core phases touch
  no git — branch/commit are an optional extension (older lines differ). Re-verify
  phases and git behavior at github.github.io/spec-kit when being wrong would
  misroute the flow.
description: >-
  The RDL team's standard end-to-end development workflow — it bridges superpowers
  (brainstorming, subagent-driven-development, test-driven-development) with GitHub
  spec-kit's spec-driven flow (specify → clarify → plan → tasks → analyze). Use this
  whenever starting real feature or epic work in an RDL spec-kit repo, resuming or
  picking up an in-progress spec, or driving implementation of an existing tasks.md.
  Triggers on "run the RDL workflow", "let's spec this out", "spec-driven
  development", "brainstorm then speckit", "turn this into specs / an epic", "pick up
  the next spec", "work through the backlog", "drive implementation", or questions
  about how brainstorming hands off to spec-kit or how to implement spec-kit tasks
  with superpowers. Reach for this before a plain brainstorming or a bare /speckit
  command, so the two systems get stitched at the seams instead of colliding.
argument-hint: "What are we building? (a single feature, or a larger epic spanning several specs)"
user-invocable: true
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

# The RDL standard development workflow

**SpecKit owns the _what_; Superpowers owns the _how_.** This skill is the router
between them. It sequences the existing skills and commands and stitches them at
the two seams where they don't line up on their own — it does not re-implement
either system and it installs no hooks. Guidance and delegation, the lightest
structure that fits (`/claude-code:pipeline`'s rule): a skill *advises* the flow,
it does not *gate* it.

> **Why no hooks / no auto-loop (project memory).** An earlier attempt
> over-mechanized this with prescriptive hooks and an implementation auto-loop; it
> didn't mesh and was put on hold pending "a rethink of the mechanical invocation
> model." This iteration stays advisory on purpose. Drive the flow by invoking each
> step and pausing only where the underlying skills already pause (design approval,
> clarify Q&A). Don't add gates the user didn't ask for.

## The flow at a glance

```
superpowers:brainstorming                 ← design (may decompose into an EPIC)
        │  ⟵ SEAM 1: redirect its handoff away from writing-plans
        ▼
ensure a spec-kit constitution exists      ← once per project
        ▼
for each spec, in order:
  speckit specify → clarify → plan → tasks → analyze
        │  ⟵ SEAM 2: feed spec-kit's artifacts to superpowers, NOT /speckit implement
        ▼
superpowers:subagent-driven-development    ← execution (the pluggable "Implement")
        ▼
superpowers:finishing-a-development-branch ← per spec, then close the epic
```

## Before you start — discover, don't assume

- **Is this a spec-kit project?** Look for a `.specify/`/`specs/` tree and available
  phase commands. If not, this workflow doesn't apply yet — spec-kit must be
  initialized first.
- **Phase command names differ by integration.** spec-kit's phases show up either
  as slash commands `/speckit.specify`, `/speckit.clarify`, … *or* as skills
  `/speckit-specify`, `/speckit-clarify`, … Discover which form your session
  exposes and use it. Below they're written neutrally as **speckit specify** etc.
- **superpowers must be installed** (`brainstorming`, `subagent-driven-development`,
  `test-driven-development`, `finishing-a-development-branch`). If they aren't, say
  so rather than approximating them.
- **Derive the trunk branch at runtime** (don't assume `main`) — later steps branch
  and merge against it.
- **Know what spec-kit does to git — it may be nothing.** In current spec-kit
  (0.13.x) the core phases touch **no git**: `specify` creates `specs/<n>-<slug>/`
  and `.specify/feature.json` but **creates no branch and commits nothing**. Branch
  creation, `git init`, and auto-commit are an **optional git extension** — check for
  `.specify/extensions.yml`. If it registers the git extension, `before_specify` runs
  `git checkout -b <n>-<slug>` in the *current* checkout (plus a `git fetch`); if it
  doesn't, you manage branches yourself. Either way spec-kit resolves the feature via
  `.specify/feature.json` / `$SPECIFY_FEATURE`, **never the branch name**. Those
  `before_`/`after_` phase events are spec-kit's *only* hook mechanism — there's no
  other core hook to wire.

## Orient — you rarely start at the top

The phases are written top-to-bottom, but a real invocation lands mid-stream just as
often — a fresh idea on trunk, a half-planned spec, or an in-progress worktree. Read
the state first, then jump to the phase that matches. This is **orientation, not an
auto-loop**: confirm where you are, run that phase, and stop where the underlying
skills stop — don't silently advance the whole pipeline.

| What you observe | Jump to |
|---|---|
| Fresh idea, no `specs/<n>-…/` yet | Phase 1 (brainstorm) |
| `specs/<n>-<slug>/` exists, no `tasks.md` | Phase 4 — resume at the first missing artifact |
| `tasks.md` present, tasks unchecked, on the spec's branch/worktree | Phase 5 (subagent-driven-development) |
| All tasks `[x]`, branch unmerged | Phase 6 (finish) |
| Several specs in flight | you're orchestrating an epic — pick the next unblocked spec per the epic doc's order, then jump by its state above |

From trunk you **orchestrate** (survey specs, pick the next one, provision a
worktree); inside a spec worktree you **execute** that one spec. Don't write feature
code from trunk — that's what the per-spec branch/worktree is for.

## Phase 1 — Brainstorm the design (superpowers:brainstorming)

Run `superpowers:brainstorming` and let it run its full course — don't
short-circuit its clarifying questions or approval gate; that discipline is why
we start here.

**SEAM 1 — redirect the handoff.** `superpowers:brainstorming` is hard-wired to
end by invoking `superpowers:writing-plans`. In this workflow it must not: when
brainstorming reaches that terminal step, **skip `writing-plans` entirely** and
carry the *approved design* into **speckit specify** instead. spec-kit's
`specify → plan → tasks` is our replacement for `writing-plans`; running both
produces two rival plans.

## Phase 2 — One spec, or an epic?

A single coherent feature is **one spec** → Phase 3. Work that decomposes into
multiple independently-shippable pieces is an **epic**.

- In this repo family, an **epic is a git convention** (not a spec-kit feature): a
  base integration branch that groups related spec branches. Create the epic branch
  off trunk; each child spec branches off the epic branch and merges back; the epic
  merges to trunk once all its specs land. (With the git extension active, run
  `specify` while checked out on the epic branch so the new spec branch forks from
  it; without it, create the spec branch yourself.)
- Capture brainstorming's decomposition in a short **epic doc**: the child specs and
  the build order (dependencies first). It's a running order, not a second design.
- Then run Phases 3-6 **per spec, sequentially**, in that order.

## Phase 3 — Ensure a constitution exists (once per project)

Before the first `specify`, confirm the project has a spec-kit **constitution**; if
it's missing, run **speckit constitution** and let the user shape it. It's
project-level and one-time — don't regenerate it per spec.

## Phase 4 — Run the spec-kit phases, in order, per spec

Run every phase, skip none: **specify → clarify → plan → tasks → analyze**. The
phase catalog is spec-kit's own (see its docs); only two rules are load-bearing
here:

- **Never skip `tasks`.** `subagent-driven-development` consumes `tasks.md` as its
  unit of work — no `tasks.md`, nothing to drive.
- **`spec.md` (the _what_) + `plan.md` (the _how_) become Phase 5's Global
  Constraints** — keep them; Phase 5 needs them.
- **`specify` produces files, not a commit.** It writes the `specs/<n>-<slug>/` tree
  and `.specify/feature.json`; core spec-kit leaves them **uncommitted** — which
  Phase 5 must handle before spawning a worktree.

If **analyze** surfaces inconsistencies across spec/plan/tasks, resolve them (loop
back to the relevant phase) *before* handing off to execution.

## Phase 5 — Implement with superpowers, NOT `speckit implement`

We treat spec-kit's Implement phase as the **pluggable slot** and substitute
superpowers execution for it. **Do not run speckit implement.** Invoke
`superpowers:subagent-driven-development` (fresh implementer subagent per task,
review after each, broad review at the end).

**SEAM 2 — the plan spec-kit hands over is split across three files.**
`subagent-driven-development` expects one superpowers-style plan (a header carrying
goal, architecture, and **Global Constraints**; task blocks carrying the steps —
superpowers plans normally live under `docs/superpowers/plans/`). spec-kit spreads
that same information across three files, so bridge it explicitly when you dispatch:

- Point `subagent-driven-development` at **`specs/<n>-<slug>/tasks.md`** as its
  plan — each spec-kit task (`T001`, `T002`, …) is one SDD task. Follow tasks.md's
  phase/dependency order, and tick each task to `[X]` as it lands (what `speckit
  implement` would have done, so status stays readable). The `[P]` parallel markers
  don't override SDD's one-implementer-at-a-time rule.
- Supply **`spec.md`** and **`plan.md`** as the **Global Constraints / interface
  context** the plan header would otherwise hold. Without them, implementer
  subagents see tasks with no binding requirements around them.
- spec-kit tasks are often coarser than superpowers' 2-5-minute steps — fine;
  SDD's per-task implement→review→fix loop still gates quality.

**Test-first (the RDL norm).** TDD lives Claude-side, not in a spec-kit extension:
implementers write the failing test first via `superpowers:test-driven-development`
(SDD already dispatches them that way — keep it, don't waive it). If `tasks.md`
splits "write tests" and "implement" into separate tasks, that's compatible; each
implementation task still starts from a red test.

**Anti-pattern:** running `speckit implement` *and* the superpowers loop on the
same task. They're two executors for one job and will fight — pick the superpowers
loop; that's the RDL resolution.

**Worktree ↔ spec-kit reconciliation (the load-bearing gotcha).** Execution should
run in an isolated workspace off trunk — delegate provisioning to
`superpowers:using-git-worktrees` (or the team's worktree tooling); don't
re-implement it. But two spec-kit facts will silently break the handoff if ignored:

- **Core spec-kit commits nothing**, so `specs/<n>-<slug>/` (including `tasks.md`) is
  *uncommitted*. A fresh `git worktree add` starts clean and **won't carry those
  files** — SDD would find no plan. So **commit `specs/<n>-<slug>/` (and
  `.specify/feature.json`) before spawning the worktree**, or run the spec-kit phases
  inside the worktree from the start.
- **If the git extension is active**, `before_specify` already did
  `git checkout -b <n>-<slug>` in your current checkout, and git won't let one branch
  live in two worktrees. Either implement in that existing checkout, or switch it back
  to trunk before adding a worktree for `<n>-<slug>`. Don't double-create the branch.

## Phase 6 — Finish

When a spec's tasks are done and reviewed, use
`superpowers:finishing-a-development-branch` to integrate it (into the epic branch
for an epic, else trunk). For an epic, repeat Phases 3-6 for the next spec, then
close the epic branch once every child has landed. Each spec owns its branch
(`<n>-<slug>`) and reaches trunk only through that integration — the team's
convention is a `--no-ff` merge, so each spec lands as one legible unit in history
rather than a direct commit on trunk. Durable decisions worth keeping beyond the
(ephemeral) spec belong in an ADR — point at the team's ADR skill rather than
inventing a record format here.

## What this skill does NOT do

- **No re-implementing spec-kit or superpowers.** Every phase is delegated to the
  system that owns it; this skill owns only the *seams* and the *order*.
- **No worktree / ADR / constitution mechanics of its own** — call the skills that
  own them.

## Verify against canonical source

spec-kit moves fast (near-daily releases) and predates the model's training cutoff;
superpowers evolves too. When a wrong phase name, flag, or handoff would misroute
real work, verify against the canonical sources rather than recall:
[spec-kit reference](https://github.github.io/spec-kit/) and the installed
superpowers skills.
