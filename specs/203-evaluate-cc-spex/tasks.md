---
description: "Task list for evaluating cc-spex for the curated external-marketplace set"
---

# Tasks: Evaluate cc-spex for the curated external-marketplace set

**Input**: Design documents from `/specs/203-evaluate-cc-spex/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md (verified upstream facts)

**Tests**: NOT APPLICABLE. This is a documentation/evaluation deliverable with no runtime
surface (see plan.md Constitution Check → Principle III N/A justification). Verification is the
doc's measurable success criteria (SC-001…SC-007) plus the repo CI-parity gates — no unit/bats
tests are written for prose.

**Organization**: Tasks are grouped by the four user stories (US1–US4) so each is independently
verifiable. The deliverable is the single file `docs/evaluations/203-cc-spex-evaluation.md`;
because every story writes a different section of that one file, story sections are written
sequentially (no `[P]` across sections that touch the same file).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files / independent, no ordering dependency)
- **[Story]**: US1–US4 map to the spec's user stories
- Exact file paths are included in each task

## Path Conventions

- Deliverable: `docs/evaluations/203-cc-spex-evaluation.md`
- Changelog fragment: `.changes/unreleased/<kind>-<slug>.yaml`
- Verification: repo root scripts (`scripts/`, `tools/asctl/`, `tests/`)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the deliverable file and its section skeleton.

- [ ] T001 Create `docs/evaluations/` directory and the deliverable file `docs/evaluations/203-cc-spex-evaluation.md` with the required section headings (Summary, Extensions overview, Overlap/conflict, Maintenance/trust, Recommendation, Draft diffs, Sources)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Verified source facts that every section depends on. MUST complete before any story section is written.

**⚠️ CRITICAL**: No user-story section may be written until fact verification is complete.

- [ ] T002 Re-verify all upstream facts against live sources and record them with citations in `specs/203-evaluate-cc-spex/research.md` (releases/cadence, open/closed issues, both marketplace.json manifests, all six `extension.yml` hook/dependency wirings, spec-kit native extension system, license) — correcting any stale claims from the prior draft
- [ ] T003 Confirm the curated-set precondition in `specs/203-evaluate-cc-spex/research.md`: `spex@cc-rhuss-marketplace` resolves from `rhuss/cc-rhuss-marketplace` (valid `.claude-plugin/marketplace.json`) and `rhuss/cc-spex`'s root marketplace is the dev-only `spex-plugin-development` (FR-010)

**Checkpoint**: Facts verified and cited — story sections can now be written.

---

## Phase 3: User Story 1 - Record an evidence-backed adopt/reject decision (Priority: P1) 🎯 MVP

**Goal**: A reader can state the recommendation (adopt / don't adopt / conditional-adopt) and its primary rationale from the doc alone (SC-001).

**Independent Test**: Read `docs/evaluations/203-cc-spex-evaluation.md` and confirm the Summary + Recommendation sections state a single unambiguous verdict with rationale.

- [ ] T004 [US1] Write the "Summary" section of `docs/evaluations/203-cc-spex-evaluation.md` with the one-sentence verdict + primary rationale (FR-004, SC-001)
- [ ] T005 [US1] Write the "Friction-point fit" findings into the Summary/Recommendation of `docs/evaluations/203-cc-spex-evaluation.md`: one written finding each for constitution drift and session continuity, grounded in a representative dry run (FR-001)
- [ ] T006 [US1] Write the "Recommendation" section of `docs/evaluations/203-cc-spex-evaluation.md` with the three-way verdict, enumerated conditions (if conditional), and per-extension scoping; ensure the rationale references at least one concrete finding (FR-004, SC-005)

**Checkpoint**: US1 delivers a defensible decision on its own (MVP).

---

## Phase 4: User Story 2 - Document overlap and conflict with existing tooling (Priority: P2)

**Goal**: Every one of the six extensions is classified against `speckit-lifecycle` (#124), `review`, and `planning` (SC-003).

**Independent Test**: Confirm the Overlap/conflict section labels each extension complementary / overlapping / conflicting vs each comparison target.

- [ ] T007 [US2] Write the "Extensions overview" section of `docs/evaluations/203-cc-spex-evaluation.md` (six extensions, their hooks, dependency chain, commands) from `research.md` (FR-002)
- [ ] T008 [US2] Write the "Overlap/conflict" section of `docs/evaluations/203-cc-spex-evaluation.md` classifying each extension vs `speckit-lifecycle` (#124), the `review` bundle, and the `planning` bundle, naming the `spex-worktrees`↔`worktrunk`/#206 conflict and the SpecKit→Superpowers handoff impact (FR-002, SC-003)

**Checkpoint**: US1 + US2 both stand alone — decision + capability map.

---

## Phase 5: User Story 3 - Establish maintenance and auto-update trust (Priority: P3)

**Goal**: A written maintenance finding + explicit `autoUpdate` recommendation backed by ≥1 dated data point (SC-006).

**Independent Test**: Confirm the Maintenance/trust section summarizes cadence + issue responsiveness and records an explicit `autoUpdate: true`/pinned recommendation.

- [ ] T009 [US3] Write the "Maintenance/trust" section of `docs/evaluations/203-cc-spex-evaluation.md` (release cadence, open/closed issue responsiveness, version lag, license, single-maintainer posture) with dated evidence (FR-003, SC-006)
- [ ] T010 [US3] State the explicit `autoUpdate` suitability recommendation (pin vs track) in `docs/evaluations/203-cc-spex-evaluation.md` with rationale tied to the maintenance evidence (FR-003)

**Checkpoint**: US1–US3 complete — all three evaluation dimensions have findings (SC-002).

---

## Phase 6: User Story 4 - Wire cc-spex into the curated set when adopted (Priority: P3, conditional)

**Goal**: On adopt/conditional-adopt, provide exact unapplied draft diffs for both curated-set files; never edit them (SC-004, SC-005).

**Independent Test**: Confirm the doc contains fenced draft diffs for `docs/external-marketplaces.md` (table row + steps) and `.claude/settings.json` (`extraKnownMarketplaces` key `cc-rhuss-marketplace` + `enabledPlugins` line), and that neither real file is modified by this branch.

- [ ] T011 [US4] Write the fenced, unapplied draft diff for `docs/external-marketplaces.md` (table row + install/pin note) into `docs/evaluations/203-cc-spex-evaluation.md`, matching the existing table format (FR-005, SC-004)
- [ ] T012 [US4] Write the fenced, unapplied draft diff for `.claude/settings.json` (`extraKnownMarketplaces["cc-rhuss-marketplace"]` → `rhuss/cc-rhuss-marketplace` + `enabledPlugins["spex@cc-rhuss-marketplace"]`) into `docs/evaluations/203-cc-spex-evaluation.md`, and name `/reload-plugins` as the user's post-apply verification (FR-006, FR-007)
- [ ] T013 [US4] Add the "why not re-host" note to `docs/evaluations/203-cc-spex-evaluation.md` and verify no edit is made to `.claude/settings.json` or `docs/external-marketplaces.md` (FR-008, SC-005)

**Checkpoint**: On adopt/conditional-adopt the wiring is turnkey and unapplied; on flat don't-adopt the diffs are omitted.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Definition of Done — changelog + green CI-parity gates.

- [ ] T014 Add a `changie` fragment `.changes/unreleased/<kind>-<slug>.yaml` recording the evaluation deliverable (FR-009, SC-007)
- [ ] T015 Run the repo CI-parity gates and confirm green: `asctl repo-check`, `scripts/check_bundle_refs.py`, `check_grouping.py`, `check_consistency.py`, `generate_manifests.py --check`, `generate_bundles_doc.py --check`, `scripts/validate-plugins.sh`, `python3 -m unittest discover -s tests` (constitution Principle V)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup — BLOCKS all stories (facts must be verified first).
- **US1 (Phase 3)**: depends on Foundational. MVP.
- **US2 (Phase 4)**: depends on Foundational; independently testable. Shares the deliverable file with US1, so its sections are appended after US1's.
- **US3 (Phase 5)**: depends on Foundational; independently testable.
- **US4 (Phase 6)**: depends on Foundational + the US1 verdict (only produces diffs on adopt/conditional-adopt).
- **Polish (Phase 7)**: depends on all desired stories complete.

### Within Each User Story

- All facts (Phase 2) verified before any prose is written.
- Because US1–US4 each write different sections of the **same** file, they are written sequentially, not in parallel.

### Parallel Opportunities

- T009 and T011/T012 draw on independent research (maintenance vs wiring) and could be drafted in either order, but both edit the one deliverable file, so serialize the actual writes.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 Setup → Phase 2 Foundational (verify facts) → Phase 3 US1 (verdict + rationale).
2. **STOP and VALIDATE**: a reader can state the recommendation from the doc alone (SC-001).

### Incremental Delivery

1. Setup + Foundational → facts verified.
2. US1 → decision recorded (MVP).
3. US2 → overlap/conflict map.
4. US3 → maintenance/trust + autoUpdate.
5. US4 → draft diffs (conditional on verdict).
6. Polish → changie + green gates.

---

## Notes

- No `[P]` markers on the story sections: they all edit `docs/evaluations/203-cc-spex-evaluation.md`.
- Tests intentionally omitted (docs deliverable, no runtime surface) — see plan.md Complexity Tracking.
- Commit after each phase's artifact; run the full CI-parity suite before finishing (Principle V).
- MUST NOT edit `.claude/settings.json` or `docs/external-marketplaces.md` (adopt is user-gated).
