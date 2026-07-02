# Tasks: SpecKit lifecycle skill for worktree-based development

**Feature**: `124-speckit-lifecycle` · **Input**: spec.md, plan.md, research.md, data-model.md, contracts/, quickstart.md

TDD is requested (spec §Testing): bats tests for the two bundled scripts are written **before** their implementation.

## Phase 1: Setup

- [x] T001 Create skill tree `skills/speckit-lifecycle/{scripts,.tests}/` (`.tests/` hidden so `asctl repo-check` ignores it; asctl only allows `assets/`,`references/`,`scripts/`)
- [x] T002 Add bats helper `skills/speckit-lifecycle/.tests/helper.bash` (throwaway fixture-repo setup/teardown: `git init`, seed trunk, stub `.specify/scripts/bash/create-new-feature.sh`)

## Phase 2: Foundational (blocks all stories)

- [x] T003 Author `skills/speckit-lifecycle/SKILL.md` frontmatter + description (generic trigger phrases, no repo-specific refs) and the runtime-discovery section (trunk via `git symbolic-ref refs/remotes/origin/HEAD` w/ fallback; CLAUDE.md at root or docs/; phase list from CLAUDE.md/.specify/; validation from Makefile/pixi.toml/package.json/CLAUDE.md; PR API from remote URL)
- [x] T004 Add context-detection block to `skills/speckit-lifecycle/SKILL.md` (default branch → root mode; `^\d{3}-` → worktree mode; anything else → halt and ask)

## Phase 3: User Story 3 — deterministic provisioning & merge scripts (P2, foundational for US1/US2)

Tests first (TDD):
- [x] T005 [P] [US3] Write `skills/speckit-lifecycle/.tests/provision-worktree.bats`: NNN derivation (max across `git branch -a`/`specs/`/worktrees +1, zero-padded), conflict-guard abort, branch+worktree creation, `--base` parentage, `create-new-feature.sh` probe + bare-git fallback
- [x] T006 [P] [US3] Write `skills/speckit-lifecycle/.tests/merge-spec.bats`: merge-target via `git merge-base`, `--no-ff` merge, worktree slot removed BEFORE `git branch -d`, idempotent worktree removal, loud refusal on uncommitted changes, merge-conflict abort (`git merge --abort`, non-zero exit, **no cleanup** — slot + branch intact; FR-007), and `specs/NNN-slug/` retention after merge (spec dir survives; `NNN` still counted in later derivation, never reused; FR-008)
Then implement:
- [x] T007 [US3] Implement `skills/speckit-lifecycle/scripts/provision-worktree.sh <slug> [--base <branch>]` to pass T005 (model layout on `skills/bitwarden/scripts`)
- [x] T008 [US3] Implement `skills/speckit-lifecycle/scripts/merge-spec.sh <NNN>` to pass T006
- [x] T009 [US3] Run `bats skills/speckit-lifecycle/.tests` — all green

## Phase 4: User Story 1 — advance a spec through phases inside a worktree (P1)

- [x] T010 [US1] Add worktree-mode section to `skills/speckit-lifecycle/SKILL.md`: identify spec from `NNN=${BRANCH:0:3}`; load spec/tasks/plan; advance from first incomplete phase (specify→clarify→plan→tasks→[checklist]→analyze→implement) — never skip a declared phase
- [x] T011 [US1] Add the implementation loop to `skills/speckit-lifecycle/SKILL.md`: per `[ ]` task implement→validate→commit (single-line conventional)→mark `[x]`; never mark on failing validation; **fail-stop** — a task that can't be made to pass halts the loop (left `[ ]`, task + validation output reported, later tasks not started; FR-012); explicit flag when no automated validation exists; pluggable Implement strategy (default loop, or declared external skill)
- [x] T021 [US1] Add the **`CLAUDE.md` guard** to `skills/speckit-lifecycle/SKILL.md` worktree-mode phase advancement: before any phase whose SpecKit tooling writes `CLAUDE.md` (e.g. `plan`'s `update-agent-context.sh`), detect an externally-managed `CLAUDE.md` (symlink or `.specify/`-declared managed flag) and guard it (skip/revert the write, then flag it), preserving the file/link; an unmanaged `CLAUDE.md` updates normally (FR-019)

## Phase 5: User Story 2 — orchestrate the backlog from the default branch (P2)

- [x] T012 [US2] Add root-mode **survey** to `skills/speckit-lifecycle/SKILL.md`: status table grouped by parent branch from `specs/`, `.claude/worktrees/`, `git worktree list`
- [x] T013 [US2] Add root-mode **create spec + worktree** flow: ensure `.specify/` present (restore only `.specify/` from latest spec branch without overwriting CLAUDE.md; if no spec branch exists to restore from, offer the opt-in `specify init` bootstrap per FR-020, erroring only if declined or the CLI is unavailable); call `provision-worktree.sh`; invoke `/speckit-specify` inside worktree **for a human to author `spec.md`** (never autonomously author/commit `spec.md` in root mode); report `claude --worktree` invocation
- [x] T014 [US2] Add root-mode **merge** (`merge-spec.sh <NNN>`) + **PR actioning** (fetch review summaries AND inline thread comments; triage HIGH/MEDIUM/LOW; post replies to inline threads)

## Phase 6: User Story 4 — package as a new `speckit` bundle (P3)

- [x] T015 [US4] Create `registry/bundles/speckit.yaml` (model on `registry/bundles/pixi.yaml`; id `speckit`, displayName `SpecKit`, description, keywords, skills `[{source: speckit-lifecycle, leaf: lifecycle}]` → invokes as `speckit:lifecycle`, targets.claude pluginName `speckit` marketplaceName `rdl`)
- [x] T016 [US4] Add `speckit` to `registry/marketplace.yaml` display order + the `rdl` meta-plugin dependency list
- [x] T017 [US4] Run `bash scripts/sync-plugins.sh speckit`, `python3 scripts/generate_manifests.py .`, `python3 scripts/generate_bundles_doc.py .`

## Phase 7: Polish & cross-cutting

- [x] T018 Add a verify-canonical guard + version pins to `skills/speckit-lifecycle/SKILL.md` per CONTRIBUTING §"Skill content conventions"
- [x] T019 Add a changie fragment in `.changes/unreleased/` (kind Added)
- [x] T020 Run full CI-parity: `asctl repo-check`, `check_bundle_refs.py`/`check_grouping.py`/`check_consistency.py`, `generate_manifests.py --check`, `generate_bundles_doc.py --check`, `validate-plugins.sh`, `python3 -m unittest discover -s tests`
- [x] T022 Scenario-verify the model-driven behaviors (not bats-covered): SC-001 mode selection / halt-and-ask on trunk, `^\d{3}-`, and ad-hoc branches; SC-007 CLAUDE.md guard (symlink repo → link preserved, write flagged; unmanaged → updated normally); SC-008 opt-in bootstrap (no auto-scaffold; declined or CLI-absent → clear error, never a partial scaffold)

## Dependencies

Setup (T001–T002) → Foundational (T003–T004) → US3 scripts+tests (T005–T009, blocks nothing but underpins US1/US2 provisioning) → US1 (T010–T011, T021) → US2 (T012–T014) → US4 packaging (T015–T017) → Polish (T018–T020, T022). US4 requires the skill dir (T003) to exist for `sync-plugins`. T021 (CLAUDE.md guard) extends the US1 SKILL.md worktree-mode section; T022 scenario-verifies SC-001/SC-007/SC-008 once the skill body (T003–T004, T010–T013, T021) has landed.

## MVP

US1 (worktree-mode phase advancement) + US3 (scripts) form the minimum useful increment.
