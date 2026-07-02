# Contract: skill mode detection & behavior

Behavioral contract for `skills/speckit-lifecycle/SKILL.md`. Not machine-tested by bats (it is
model-driven prose); verified by scenario tests and the acceptance criteria in the spec.

## Frontmatter

- `name: speckit-lifecycle`.
- `description`: the issue's generic trigger description **verbatim** — no repo-specific
  references (no "template", no data-science terms). Must contain the trigger phrases: "new
  spec", "start/pick up a spec", "what specs are in progress", "drive implementation", "work
  through the backlog", "merge spec NNN", "action PR comments" (FR-016, SC-004).

## Context detection (runs first)

| Current branch | Mode |
|---|---|
| Detected default branch (trunk) | **Root mode** |
| Matches `^\d{3}-` | **Worktree mode** |
| Anything else | **Halt and ask** — never guess (FR-001, SC-001) |

After detecting the mode, discover and read the project's `CLAUDE.md` at **root or
`docs/CLAUDE.md`** — path never hardcoded (FR-002). `CLAUDE.md` is **read-only discovery
input**: the skill never clobbers it (FR-019, see Worktree mode).

## Root mode

1. **Survey first, always** — status table of provisioned specs (branch + slot exist) and
   completed specs (in `specs/`), grouped by parent branch, derived from `specs/`,
   `.claude/worktrees/`, and `git worktree list`. No "planned-but-unprovisioned" rows (FR-003).
2. **Create spec + worktree** (single root-mode session): ensure `.specify/` on the parent
   branch — restore **only** `.specify/` from the most recent spec branch if missing (never
   overwrite `CLAUDE.md`; if no spec branch exists to restore from, offer the opt-in `specify
   init` bootstrap per FR-020, erroring only if declined or the `specify` CLI is unavailable)
   → `provision-worktree.sh <slug>
   [--base]` → launch `/speckit-specify` **inside the new worktree** → report path + `claude
   --worktree .claude/worktrees/NNN` (FR-004). The skill **hands off `spec.md` authoring to a
   human** in that launched worktree session — it never autonomously authors or commits `spec.md`
   in root mode (Clarification 2026-07-02). Trunk never holds partial planning artifacts.
3. **Merge** — `merge-spec.sh <NNN>` (FR-005/FR-007).
4. **PR actioning** — fetch review summaries **and** inline thread comments (separate
   endpoints), triage HIGH/MEDIUM/LOW, post replies to inline threads; forge/API inferred from
   remote URL or `CLAUDE.md` override (FR-009).

## Worktree mode

1. Identify the spec: `NNN=${BRANCH:0:3}`; load `spec.md`/`tasks.md`/`plan.md`.
2. Advance from the **first incomplete** phase through the configured sequence
   (`specify → clarify → plan → tasks → [checklist] → analyze → implement`); never skip a
   declared phase; run `checklist` only when declared (default omits it) (FR-010/FR-011).
   Before any phase whose SpecKit tooling writes `CLAUDE.md` (e.g. `plan`'s
   `update-agent-context.sh`), detect an **externally-managed** `CLAUDE.md` — a symlink or a
   repo/`.specify/`-declared managed flag — and guard it (skip or revert that write, then flag
   it), preserving the file or link; an unmanaged `CLAUDE.md` receives its normal update (FR-019).
3. **Implementation loop** (default strategy): for each `[ ]` task → implement → validate →
   commit (single-line conventional; imperative; no body; no attribution) → mark `[x]`. Never
   mark complete while validation fails (FR-012). **Fail-stop**: a task that cannot be made to
   pass after the skill's fix attempt **halts the loop** — left `[ ]`, task + validation output
   reported, later tasks not started (Clarification 2026-07-02; keeps every committed task
   validated). Discover validation from `Makefile`/`CLAUDE.md`/`pixi.toml`/`package.json`; when
   no automated suite exists, run best-effort checks and **explicitly flag** the absence — never
   silently pass (FR-013).
4. **Pluggable implement strategy**: default single-agent loop, or delegate the Implement phase
   to a declared external strategy skill (e.g. `forge-quill`) when configured in
   `CLAUDE.md`/`.specify/`. The skill owns *reaching* Implement, not how tasks execute (FR-014).

## Global invariant

All feature work happens inside a spec worktree — never on trunk or an integration branch. No
paths, commands, or forge API details are hardcoded (FR-015).
