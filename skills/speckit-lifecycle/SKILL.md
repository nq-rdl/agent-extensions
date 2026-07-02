---
name: speckit-lifecycle
description: >-
  Drives the full speckit development lifecycle in any repo following speckit
  conventions. Detects context from the current branch and switches mode: on the
  default branch it orchestrates — survey specs, create a new spec + worktree (spec
  written in the same session), merge completed specs, action PR review comments;
  inside a spec worktree it advances the speckit phase sequence (specify → clarify →
  plan → tasks → analyze) and runs the implementation loop. Load whenever the user
  says "new spec", "start/pick up a spec", "what specs are in progress", "drive
  implementation", "work through the backlog", "merge spec NNN", "action PR comments",
  or anything implying spec creation, lifecycle advancement, or orchestration in a
  speckit repo.
license: MIT
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

# SpecKit lifecycle

Drives the complete [SpecKit](https://github.com/github/spec-kit) development
lifecycle for **any** repo following speckit conventions (`.specify/`,
`specs/NNN-slug/`, `.claude/worktrees/NNN`). Context is detected from the current
branch; you invoke it the same way everywhere.

**Core invariant:** all feature work happens inside a spec worktree — never on trunk
or an integration branch.

## 0. Runtime discovery — never hardcode

Everything below is discovered at runtime. Never assume a path, command, or forge.

| What | How |
|---|---|
| Trunk branch | `git symbolic-ref refs/remotes/origin/HEAD` → strip; fallback: first of `main`, `master`, `trunk`, else current branch (if not a spec branch) |
| Merge target | git topology (`git merge-base`) — trunk, or the integration branch the spec was cut from |
| `CLAUDE.md` location | root or `docs/CLAUDE.md` — discover, never hardcode |
| Validation commands | `Makefile`, `pixi.toml`, `package.json`, `CLAUDE.md` |
| Phase list | `CLAUDE.md` or `.specify/` (default omits the checklist phase) |
| Implement strategy | default single-agent loop, or an external strategy skill declared in `CLAUDE.md`/`.specify/` |
| PR API | remote URL or `CLAUDE.md` override (GitHub / Gitea / GitLab) |

## 1. Context detection — run first

```bash
git rev-parse --abbrev-ref HEAD
```

| Branch pattern | Mode |
|---|---|
| Detected default (trunk) branch | **Root mode** (§2) |
| `^\d{3}-` | **Worktree mode** (§3) |
| Anything else | **Halt and ask** — do not guess |

Then discover and read the project's `CLAUDE.md` (root or `docs/CLAUDE.md`) to
re-establish rules before acting.

## 2. Root mode — orchestration only

You are on trunk. Coordinate; never write feature code here.

### 2a. Survey — always first

Status table of all specs grouped by parent branch, showing current phase and
worktree presence, derived from `specs/`, `.claude/worktrees/`, and
`git worktree list`. There is no "planned-but-unprovisioned" state — the survey shows
only provisioned specs (branch + worktree exist) and completed specs recorded in
`specs/`. Pre-provisioning ideas belong in a project tracker, not in `specs/` on trunk.

### 2b. Create a new spec + worktree (single session)

1. Ensure `.specify/` is present on the parent branch; if missing, restore **only
   `.specify/`** from the most recent spec branch (never overwrite `CLAUDE.md`). Error
   clearly if no spec branch exists.
2. Run `scripts/provision-worktree.sh <slug> [--base <branch>]` — cut from trunk, or
   pass `--base` to group the spec with related work on an existing integration branch.
3. Invoke `/speckit-specify` **inside the worktree**. All planning phases run in the
   worktree — trunk never holds partial artifacts.
4. Report the worktree path and the `claude --worktree .claude/worktrees/NNN` invocation.

### 2c. Merge a completed spec

**Specs are ephemeral; ADRs are the durable record.** Before merging to **trunk**, offer
to archive the spec's decision points as an ADR (delegate to the
`architecture-decision-records` skill or the `adr-generator` agent) — the ADR in
`docs/adr/` is what survives on trunk.

Then run `scripts/merge-spec.sh <NNN>`. The merge target is resolved from git topology.
On a **trunk** merge the spec is ephemeral: `merge-spec.sh` strips `specs/NNN-slug/`
(its decisions now live in `docs/adr/`), keeping trunk clean. On an **integration-branch**
merge the spec is retained (work continues under the integration branch). `NNN` is never
reused. The `.specify/` scaffolding and the speckit phase skills are **branch-only**
execution tooling — they are not trunk deliverables and do not merge to trunk.

### 2d. Action PR review comments

Fetch review **summaries** *and* inline **thread** comments (separate endpoints).
Triage by severity: **HIGH** → fix + reply with the commit SHA; **MEDIUM** → fix or
decline with rationale; **LOW** → judgement call, always reply. Post replies back to
the inline threads. Infer auth and API shape from the remote URL or a `CLAUDE.md`
override.

## 3. Worktree mode — spec execution

Identify the spec from the branch prefix: `NNN=${BRANCH:0:3}`; load `spec.md`,
`tasks.md`, `plan.md`. Advance from the **first incomplete** phase:

| Phase | Skill | Complete when | Conditional? |
|---|---|---|---|
| Specify | `/speckit-specify` | `spec.md` exists | No |
| Clarify | `/speckit-clarify` | no `[NEEDS CLARIFICATION]` markers | No |
| Plan | `/speckit-plan` | `plan.md` + `research.md` exist | No |
| Tasks | `/speckit-tasks` | `tasks.md` has ≥1 task | No |
| Checklist | `/speckit-checklist` | all checklists pass | Only if declared |
| Analyze | `/speckit-analyze` | no blockers flagged | No |
| Implement | loop (§3a, pluggable) | all tasks `[x]` | No |

The phase list is repo-configured (`CLAUDE.md` or `.specify/`); the default omits the
checklist phase. **Never skip a declared phase.**

### 3a. Implementation loop

For each `[ ]` task: implement → validate → commit (single-line conventional:
imperative, no body, no attribution) → mark `[x]`. Never mark a task complete with
failing validation. When no test suite exists, discover validation from
`Makefile`/`CLAUDE.md`/`pixi.toml`/`package.json` or perform best-effort lint/syntax
checks — and **explicitly flag** that no automated validation exists rather than
silently passing.

The Implement *strategy* is pluggable: the default is this single-agent loop, but a
repo may delegate the phase to an external strategy skill declared in
`CLAUDE.md`/`.specify/`. This skill owns *reaching* the Implement phase, not how tasks
within it are executed.

## Bundled scripts (canonical, versioned)

Deterministic operations ship as versioned scripts so they are independently testable
and deploy everywhere at once. **These scripts are the source of truth — never inline
their logic into prose.** Each probes for `.specify/scripts/bash/create-new-feature.sh`
and falls back to bare git if absent.

- `scripts/provision-worktree.sh <slug> [--base <branch>]` — NNN derivation, conflict
  guard, branch + worktree creation, spec seeding. Tested in `.tests/provision-worktree.bats`.
- `scripts/merge-spec.sh <NNN>` — topology-based merge target, `--no-ff` merge,
  worktree-slot removal **before** branch deletion, idempotent cleanup, loud refusal on
  uncommitted changes, and **strips the ephemeral `specs/NNN-slug/` on a trunk merge**
  (retains it on integration merges). Tested in `.tests/merge-spec.bats`.

Compatibility: SpecKit `.specify/` project layout; speckit phase skills
`speckit-{specify,clarify,plan,tasks,checklist,analyze}`. Run `bats .tests/` after
changing either script.
