---
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
compatibility: >-
  Requires `git` and a SpecKit `.specify/` layout with the
  `speckit-{specify,clarify,plan,tasks,checklist,analyze}` phase skills; the two bundled
  scripts are tested with bats-core 1.13.0. Optional: `gh` for PR actioning and
  `.specify/scripts/bash/create-new-feature.sh` (runtime-probed, bare-git fallback).
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
   `.specify/`** from the most recent spec branch (never overwrite `CLAUDE.md`). If no
   spec branch exists to restore from, offer the **opt-in `specify init` bootstrap**
   (FR-020): scaffold `.specify/` only on explicit confirmation via the official `specify`
   CLI (e.g. `uvx … specify init`) — never automatically, never vendoring your own
   templates — and error clearly only if the bootstrap is declined or the CLI is unavailable.
2. **Offer the routing baseline** (first setup in a repo): if `constitution.md` /
   `CLAUDE.md` lack SpecKit⇄Superpowers routing, offer it. Probe the repo's registered
   extension catalogs first — when the **rdl-routing** extension is available
   (`nq-rdl/spec-kit-extensions` via the RDL catalog), offer
   `specify extension add rdl-routing`; otherwise fall back to the copy-paste playbook in
   this skill's source repo (`metadata.repo`,
   `docs/playbooks/speckit-constitution-routing.md`) — the constitution clause +
   `CLAUDE.md` routing block. Apply only on consent; never edit
   `constitution.md`/`CLAUDE.md` unasked.
3. Run `scripts/provision-worktree.sh <slug> [--base <branch>]` — cut from trunk, or
   pass `--base` to group the spec with related work on an existing integration branch.
   (When the repo has the **rdl-worktree** extension installed, prefer its provision
   command — see *Extension migration* below.)
4. Invoke `/speckit-specify` **inside the worktree**. All planning phases run in the
   worktree — trunk never holds partial artifacts.
5. Report the worktree path and the `claude --worktree .claude/worktrees/NNN` invocation.

### 2c. Merge a completed spec

**Specs are ephemeral; ADRs are the durable record.** Before merging to **trunk**, offer
to archive the spec's decision points as an ADR (delegate to the
`architecture-decision-records` skill or the `adr-generator` agent) — the ADR in
`docs/adr/` is what survives on trunk.

Then run `scripts/merge-spec.sh <NNN>` (or, when the repo has the **rdl-worktree** /
**rdl-adr** extensions installed, prefer their merge + `speckit.adr.finalize` commands —
see *Extension migration* below). The merge target is resolved from git topology.
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

**`CLAUDE.md` guard (read-only discovery input).** Before advancing any phase whose
SpecKit tooling writes `CLAUDE.md` — e.g. `plan`'s `update-agent-context.sh` — detect an
**externally-managed** `CLAUDE.md` (a symlink, or a repo/`.specify/`-declared managed flag)
and guard it: skip or revert that write, preserving the file or link, then flag it. A repo
whose `CLAUDE.md` is unmanaged still receives its normal agent-context update (FR-019).

### 3a. Implementation loop

For each `[ ]` task: implement → validate → commit (single-line conventional:
imperative, no body, no attribution) → mark `[x]`. Never mark a task complete with
failing validation. **Fail-stop:** a task that cannot be made to pass after your fix
attempt **halts the loop** — leave it `[ ]`, report the task and its validation output,
and do not start later tasks (FR-012). When no test suite exists, discover validation from
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

**Extension migration (epic #207 re-architecture).** These mechanics are migrating
speckit-side to RDL-owned extensions in `nq-rdl/spec-kit-extensions`, so any agent or a
human can run them without this skill: **rdl-worktree** (provision/merge, wrapping these
scripts' semantics) and **rdl-adr** (`speckit.adr.finalize` — spec→ADR archive + the
ephemeral strip). Probe the repo at runtime: when those extension commands are installed,
prefer them and treat the bundled scripts as the fallback; until they ship, the scripts
remain canonical. This skill keeps only discovery + delegation either way.

**Verify canonical:** SpecKit conventions evolve — when a phase command, a `.specify/`
path, or a `create-new-feature.sh` flag would change behavior and being wrong would
mislead, verify against the authoritative SpecKit docs
(<https://github.com/github/spec-kit>) rather than trusting this prose. The two bundled
scripts (guarded by `bats .tests/`) remain the source of truth for the git operations.
