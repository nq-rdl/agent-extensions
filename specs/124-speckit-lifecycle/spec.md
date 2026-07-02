# Feature Specification: SpecKit lifecycle skill for worktree-based development

**Feature Branch**: `124-speckit-lifecycle`  
**Created**: 2026-07-02  
**Status**: Draft  
**Input**: User description: "SpecKit lifecycle skill for development on worktrees" (GitHub issue #124, part of the #207 SpecKit + Superpowers workflow epic). Generalizes the `dst-autoloop` prior art into a repo-agnostic, runtime-discovered lifecycle skill shipped as a new `speckit` bundle.

## User Scenarios & Testing *(mandatory)*

This feature ships a single `speckit-lifecycle` skill, two bundled deterministic
scripts, a bats test suite, and a new `speckit` marketplace bundle. The skill drives
the complete SpecKit development lifecycle for **any** repo following SpecKit
conventions (`.specify/`, `specs/NNN-slug/`, `.claude/worktrees/NNN`). It detects
context from the current branch and switches between two modes; everything it does is
discovered at runtime, with no hardcoded paths, commands, or forge APIs. The actors are
a maintainer orchestrating a backlog from the default branch and a developer advancing a
single spec inside its worktree — both invoke the skill identically.

**Core invariant: all feature work happens inside a spec worktree — never on trunk or an
integration branch.**

### User Story 1 - Advance a spec through its phases inside a worktree (Priority: P1)

A developer working inside a spec worktree invokes the skill; it recognizes worktree mode
from the `^\d{3}-` branch prefix, identifies the spec, loads `spec.md`/`plan.md`/`tasks.md`,
and advances from the first incomplete phase through the SpecKit phase sequence, ending in
the implementation loop.

**Why this priority**: This is the heart of "drive implementation" — even with nothing else,
a developer who can open a spec worktree and have the skill carry the spec from its current
phase to completed, correctly-marked tasks has the core value and can ship a feature.

**Independent Test**: In a worktree on a `NNN-slug` branch with a partially-complete spec,
invoke the skill and confirm it resumes at the first incomplete phase, runs each remaining
phase's SpecKit skill in order, and drives the implementation loop until every task is `[x]`.

**Acceptance Scenarios**:

1. **Given** a worktree on branch `124-foo` with `spec.md` present but unresolved clarification
   markers remaining, **When** the skill runs, **Then** it starts at the Clarify phase (not
   Specify) and advances forward from there.
2. **Given** a spec whose `tasks.md` has unchecked tasks, **When** the implementation loop
   runs, **Then** each task is implemented → validated → committed (single-line conventional,
   no body, no attribution) → marked `[x]`, and a task with failing validation is never marked
   complete.
3. **Given** a repo whose phase list declares a checklist phase, **When** the skill advances,
   **Then** the checklist phase runs; **Given** a repo whose default omits it, **Then** the
   checklist phase is skipped.
4. **Given** a repo with no automated test suite, **When** a task needs validation, **Then**
   the skill discovers validation from `Makefile`/`CLAUDE.md`/`pixi.toml`/`package.json` or
   performs best-effort checks and **explicitly flags** that no automated validation exists,
   never silently passing.

---

### User Story 2 - Orchestrate the backlog from the default branch (Priority: P2)

A maintainer on the default branch invokes the skill; it recognizes root mode, surveys all
specs first, then can create a new spec + worktree (with the spec authored in the same
session), merge a completed spec, or action PR review comments — all from one entry point.

**Why this priority**: Root-mode orchestration turns the per-spec worktree loop into a managed
backlog. It depends on the scripts (US3) but delivers the coordination value a team needs to
run many specs without hand-rolling per-repo tooling.

**Independent Test**: On the default branch, invoke the skill and confirm a survey table
renders first (specs grouped by parent branch with phase + worktree presence), then confirm
each of create / merge / PR-action can be initiated from the same invocation.

**Acceptance Scenarios**:

1. **Given** the default branch, **When** the skill runs any root-mode action, **Then** a
   survey runs first — a status table of provisioned specs (branch + worktree exist) and
   completed specs recorded in `specs/`, grouped by parent branch, with no
   "planned-but-unprovisioned" rows.
2. **Given** a request to create a new spec, **When** the skill provisions it, **Then** it
   ensures `.specify/` is present on the parent branch (restoring **only** `.specify/` from the
   most recent spec branch if missing, never overwriting `CLAUDE.md`, and erroring clearly if no
   spec branch exists), runs `provision-worktree.sh`, invokes `/speckit-specify` inside the new
   worktree, and reports the worktree path plus the `claude --worktree .claude/worktrees/NNN`
   invocation.
3. **Given** a completed spec, **When** the skill merges it, **Then** it runs `merge-spec.sh NNN`,
   the merge target is inferred from git topology (trunk or the integration branch it was cut
   from), and `specs/NNN-slug/` remains as a permanent record with `NNN` never reused.
4. **Given** an open PR, **When** the skill actions it, **Then** it fetches both review
   summaries and inline thread comments (separate endpoints), triages by severity (HIGH → fix +
   reply with commit SHA; MEDIUM → fix or decline with rationale; LOW → judgement call, always
   reply), and posts replies back to the inline threads.

---

### User Story 3 - Deterministic provisioning and merge via bundled scripts (Priority: P2)

The deterministic git operations ship as two versioned, independently testable scripts —
`provision-worktree.sh` and `merge-spec.sh` — rather than embedded bash, so they deploy
everywhere at once and can be unit/integration tested against a throwaway fixture repo.

**Why this priority**: Correct, testable NNN derivation, conflict guarding, and merge/cleanup
topology are the safety-critical core of root mode. Extracting them as scripts is what makes
concurrent-creation collisions and post-merge cleanup verifiable rather than best-effort prose.

**Independent Test**: Run each script against a fixture repo and confirm the exact semantics
below hold via the bats suite (NNN derivation, conflict-guard abort, branch/worktree creation,
`--base` parentage, merge-target topology, post-merge cleanup) with the suite passing.

**Acceptance Scenarios**:

1. **Given** existing spec branches, `specs/` dirs, and `.claude/worktrees/` slots, **When**
   `provision-worktree.sh <slug>` runs, **Then** `NNN` is derived as the max across all three
   sources + 1, zero-padded to three digits.
2. **Given** an `NNN` that already exists as a branch, spec dir, or worktree slot, **When**
   provisioning runs, **Then** it aborts on the conflict guard without mutating any state.
3. **Given** `provision-worktree.sh <slug>`, **When** it runs with no `--base`, **Then** the
   branch and worktree are cut from the detected trunk; **Given** `--base <branch>`, **Then**
   they are cut from `<branch>` to group the spec with related work.
4. **Given** `.specify/scripts/bash/create-new-feature.sh` is present, **When** provisioning
   runs, **Then** it is invoked with `--allow-existing-branch`; **Given** it is absent, **Then**
   provisioning falls back to bare git.
5. **Given** `merge-spec.sh <NNN>`, **When** it runs, **Then** it resolves the merge target via
   `git merge-base`, performs a `--no-ff` merge, removes the worktree slot **before** deleting the
   branch, deletes the branch (`git branch -d` + `git push origin --delete`), is idempotent on
   worktree removal, and refuses loudly if the worktree slot has uncommitted changes.

---

### User Story 4 - Package the skill as a new `speckit` bundle (Priority: P3)

The skill, its scripts, and its tests are packaged as a new `speckit` marketplace bundle so
users install and invoke it the same way as any other bundle in this catalog, and the repo's
own validation (`asctl repo-check`, plugin/manifest checks) stays green.

**Why this priority**: Packaging is what makes the skill installable and maintained centrally
rather than re-authored per repo, but it is gated on the skill and scripts existing first.

**Independent Test**: After adding the bundle and running the sync/generation scripts, confirm
`asctl repo-check`, `generate_manifests.py --check`, `generate_bundles_doc.py --check`, and
`check_consistency.py` all pass and the skill appears under the `speckit` plugin.

**Acceptance Scenarios**:

1. **Given** `registry/bundles/speckit.yaml` (id `speckit`, displayName `SpecKit`, skill
   `speckit-lifecycle`, target `claude` pluginName `speckit` marketplaceName `rdl`) and the
   `speckit` entry added to `registry/marketplace.yaml` order + `rdl` meta-plugin deps, **When**
   the pipeline scripts run, **Then** manifests, docs, and plugin trees regenerate without drift.
2. **Given** the bats suite lives under a hidden `.tests/` directory inside the skill, **When**
   `asctl repo-check` runs, **Then** it passes (hidden dirs are ignored; only `assets/`,
   `references/`, `scripts/` are allowed non-hidden subdirs).

---

### Edge Cases

- **Ad-hoc branch** (neither the default branch nor `^\d{3}-`) → the skill halts and asks rather
  than guessing a mode.
- **Missing `.specify/` on the parent branch** → restore only `.specify/` from the most recent
  spec branch; if no spec branch exists, error clearly.
- **Concurrent spec creation from two root sessions** → the script conflict guard makes the losing
  session fail safely rather than clobbering an NNN slot (concurrent creation is otherwise a
  non-goal).
- **Merge target is not trunk** → topology resolves it to the integration branch the spec was cut
  from; the merge never assumes trunk.
- **Worktree slot has uncommitted changes at merge time** → loud refusal, no data loss.
- **`CLAUDE.md` at `docs/CLAUDE.md` instead of root** → discovery finds it; the path is never
  hardcoded.

## Clarifications

### Session 2026-07-02

- Q: Where do the bats tests live so they ship with the skill but `asctl repo-check` (which allows only `assets/`, `references/`, `scripts/` as non-hidden subdirs) still passes? → A: A hidden `skills/speckit-lifecycle/.tests/` directory — asctl ignores dot-directories (verified against `tools/asctl/internal/structure`), so the suite ships alongside the skill without tripping the disallowed-subdir check.
- Q: How are the deterministic scripts packaged and located? → A: As versioned files under `skills/speckit-lifecycle/scripts/` (modeled on `skills/bitwarden/scripts` and `skills/cc-web-setup/scripts`), copied into the plugin tree by `sync-plugins.sh`; each script probes for `.specify/scripts/bash/create-new-feature.sh` and falls back to bare git when absent.
- Q: What is the default phase sequence, and is the checklist phase included by default? → A: `specify → clarify → plan → tasks → analyze → implement`; the conditional checklist phase runs only when a repo declares it, and the default omits it. No declared phase is ever skipped.
- Q: When resolving where a merged spec goes and what trunk is, are these fixed or discovered? → A: Both are discovered at runtime — trunk from `git symbolic-ref refs/remotes/origin/HEAD` (fallback: first of `main`, `master`, `trunk`, else current non-spec branch); the merge target from git topology via `git merge-base`. Neither is hardcoded to `main`.
- Q: What forge does PR actioning target, and how is it chosen? → A: Inferred from the remote URL (GitHub / Gitea / GitLab), with a `CLAUDE.md` override; GitHub via `gh` is the practical default. Bespoke forge support beyond inference is a non-goal.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The skill MUST detect its mode from the current branch: the detected default branch → root mode; a branch matching `^\d{3}-` → worktree mode; anything else → halt and ask.
- **FR-002**: The skill MUST discover and read the project's `CLAUDE.md` (root or `docs/CLAUDE.md`) after detection, never hardcoding the path.
- **FR-003**: In root mode, the skill MUST run a survey first — a status table of provisioned and completed specs grouped by parent branch, derived from `specs/`, `.claude/worktrees/`, and `git worktree list`, with no unprovisioned rows.
- **FR-004**: The skill MUST create a new spec + worktree in a single session: ensure `.specify/` on the parent branch (restoring only `.specify/` from the latest spec branch if missing, never overwriting `CLAUDE.md`, erroring if no spec branch exists), provision via script, invoke `/speckit-specify` inside the worktree, and report the worktree path + `claude --worktree` invocation.
- **FR-005**: Provisioning and merging MUST run via the bundled scripts (`provision-worktree.sh`, `merge-spec.sh`), not embedded bash.
- **FR-006**: `provision-worktree.sh <slug> [--base <branch>]` MUST derive `NNN` as the max across `git branch -a`, `specs/`, and `.claude/worktrees/` + 1, zero-padded to three digits; abort on any conflict; create the branch + worktree off trunk (or off `--base`); and invoke `create-new-feature.sh --allow-existing-branch` when present, else fall back to bare git.
- **FR-007**: `merge-spec.sh <NNN>` MUST resolve the merge target via `git merge-base`, perform a `--no-ff` merge, remove the worktree slot **before** deleting the branch, delete the branch locally and on the remote, be idempotent on worktree removal, and refuse loudly on uncommitted changes in the slot.
- **FR-008**: `specs/NNN-slug/` MUST remain as a permanent record after merge, and `NNN` MUST never be reused.
- **FR-009**: PR actioning MUST fetch both review summaries and inline thread comments (separate endpoints), triage by severity (HIGH/MEDIUM/LOW), and post replies back to inline threads; auth and API shape MUST be inferred from the remote URL or a `CLAUDE.md` override.
- **FR-010**: In worktree mode, the skill MUST identify the spec from the branch prefix (`NNN=${BRANCH:0:3}`), load `spec.md`/`tasks.md`/`plan.md`, and advance from the first incomplete phase through the configured phase sequence, never skipping a declared phase.
- **FR-011**: The phase sequence MUST be repo-configurable (`CLAUDE.md` or `.specify/`); the default is `specify → clarify → plan → tasks → analyze → implement` with the checklist phase run only when declared.
- **FR-012**: The implementation loop MUST, for each `[ ]` task, implement → validate → commit (single-line conventional; imperative; no body; no attribution) → mark `[x]`, and MUST NOT mark a task complete while its validation fails.
- **FR-013**: When no test suite exists, the skill MUST discover validation from `Makefile`/`CLAUDE.md`/`pixi.toml`/`package.json` or perform best-effort checks, and MUST explicitly flag the absence of automated validation rather than silently passing.
- **FR-014**: The Implement phase strategy MUST be pluggable — the default is the single-agent loop, but a repo MAY delegate it to an external strategy skill (e.g. `forge-quill`) declared in `CLAUDE.md`/`.specify/`; the skill owns reaching the Implement phase, not how tasks within it execute.
- **FR-015**: The skill MUST NOT hardcode paths, commands, or forge API details — trunk branch, merge target, validation commands, PR API, phase list, implement strategy, and `CLAUDE.md` location are all discovered at runtime.
- **FR-016**: The skill's `description` frontmatter MUST use generic trigger phrases with no repo-specific references (e.g. "new spec", "start/pick up a spec", "what specs are in progress", "drive implementation", "work through the backlog", "merge spec NNN", "action PR comments").
- **FR-017**: The skill MUST be packaged as a new `speckit` bundle (`registry/bundles/speckit.yaml`, id `speckit`, displayName `SpecKit`, skill `speckit-lifecycle`, target `claude` pluginName `speckit` marketplaceName `rdl`), added to `registry/marketplace.yaml` order + `rdl` meta-plugin deps, with plugin trees, manifests, and docs regenerated so all CI validators stay green.
- **FR-018**: The bats test suite MUST cover NNN derivation, conflict-guard abort, branch/worktree creation, `--base` parentage, merge-target topology, and post-merge cleanup; it MUST pass and MUST live where `asctl repo-check` continues to pass (a hidden `.tests/` directory).

### Key Entities *(include if feature involves data)*

- **Spec**: A unit of feature work anchored by `specs/NNN-slug/` (durable record) with a matching `NNN-slug` branch and `.claude/worktrees/NNN` slot while in progress. Identified by `NNN`; `NNN` is monotonic and never reused.
- **Worktree slot**: `.claude/worktrees/NNN`, the isolated checkout where all of a spec's phases run; removed on merge before its branch is deleted.
- **Phase**: A stage in the SpecKit sequence (specify, clarify, plan, tasks, [checklist], analyze, implement) with a completion condition and an optional conditional flag.
- **Parent branch**: The branch a spec was cut from (trunk or an integration branch); determines the merge target via topology.
- **Bundled script**: `provision-worktree.sh` / `merge-spec.sh` — versioned, independently testable deterministic git operations shipped under the skill's `scripts/`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Invoked from the default branch and from within a spec worktree, the skill selects the correct mode 100% of the time and halts-and-asks on any branch that is neither the default nor `^\d{3}-`.
- **SC-002**: The bats suite covers all six required areas (NNN derivation, conflict-guard abort, branch/worktree creation, `--base` parentage, merge-target topology, post-merge cleanup) and passes with zero failures.
- **SC-003**: `asctl repo-check`, `generate_manifests.py --check`, `generate_bundles_doc.py --check`, `check_bundle_refs.py`, `check_grouping.py`, `check_consistency.py`, and `validate-plugins.sh` all pass after the `speckit` bundle is added.
- **SC-004**: Every acceptance-criteria item in issue #124 maps to at least one functional requirement or acceptance scenario in this spec (full traceability), and the `description` frontmatter contains no repo-specific references.
- **SC-005**: A new spec is created — worktree provisioned and `spec.md` committed inside it — within a single skill session, with the correct `claude --worktree` invocation reported.
- **SC-006**: On merge, the worktree slot is removed before the branch is deleted in 100% of runs, and a slot with uncommitted changes is never silently discarded (loud refusal every time).

## Assumptions

- The target repo follows SpecKit conventions: `.specify/`, `specs/NNN-slug/`, and `.claude/worktrees/NNN`. Non-SpecKit repos are out of scope.
- `git` is available and the repo has a resolvable trunk (via `origin/HEAD` or one of `main`/`master`/`trunk`).
- Only one root session creates specs at a time; concurrent creation is guarded (fails safely) but not otherwise supported.
- Prior art is `dst-autoloop`; the skill generalizes it with no data-science-specific behavior, paths, or commands.
- The forge is GitHub/Gitea/GitLab and inferable from the remote URL (or overridden in `CLAUDE.md`); bespoke forges beyond inference are out of scope.
- Paired/multi-agent implementation strategies (e.g. `forge-quill`) are a separate skill; this skill only reaches and, by default, runs the single-agent Implement loop.
