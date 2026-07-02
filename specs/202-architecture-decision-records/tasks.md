# Tasks: Architecture Decision Records Skill (Structured MADR)

**Input**: Design documents from `/specs/202-architecture-decision-records/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md, data-model.md, contracts/, quickstart.md

**Status (reconciled 2026-07-03)**: T001–T018 are complete — the skill is authored,
registered, synced, and passes the full CI-parity gate (T018 verified green). **T019**
(interactive behavioral walkthrough, `claude --plugin-dir ./plugins/planning`) and **T020**
(`/skill:audit`) remain open: both require a manual/runtime pass that has not been evidenced,
so they are intentionally left unchecked rather than asserted complete.

**Tests**: This is a documentation-only skill (no runtime code). Per plan.md Constitution
Check III, the "red→green" evidence is the **validation gate** (`asctl repo-check` +
CI-parity checks) plus the behavioral walkthrough in `quickstart.md` — there are no
unit-test files to author. No separate test tasks are generated; validation tasks live in
Setup (green baseline) and Polish (full gate + walkthrough).

**Organization**: Tasks are grouped by user story to enable independent implementation and
testing. All three stories are authored into the **same** `SKILL.md`, so tasks that edit
`SKILL.md` are strictly serial; separate `assets/*.md`, `agent.md`, `planning.yaml`,
and changie files are parallelizable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- Canonical skill: `skills/architecture-decision-records/` (single edit point)
- Registry: `registry/bundles/planning.yaml`
- Agent cross-link: `agents/adr-generator/agent.md`
- Generated (never hand-edited): `plugins/planning/`, `docs/bundles.md`,
  `.claude-plugin/marketplace.json`, `plugins/planning/.claude-plugin/plugin.json`
- `docs/adr/` is a **runtime artifact the skill offers to create in the user's project** —
  NOT a directory this feature adds.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Scaffold the canonical skill and establish the green validation baseline.

- [x] T001 Create the canonical skill scaffold: directory `skills/architecture-decision-records/` with an empty `assets/` subdirectory (top level will hold only `SKILL.md` per the agentskills.io directory standard).
- [x] T002 Author `SKILL.md` frontmatter in `skills/architecture-decision-records/SKILL.md` per `contracts/skill-frontmatter.md`: `name: architecture-decision-records` (≤64 runes), `license`, a `description` (≤1024 runes) enumerating explicit cues + the implicit "weighing alternatives" cue + retrieval + archival entry points, `compatibility:` pinning **MADR (adr/madr) v4** (FR-004, FR-012), and `metadata` (repo + `spec_url: https://adr.github.io/madr/`).
- [x] T003 [P] Register the skill as a flat member in `registry/bundles/planning.yaml` under `skills:` (change `skills: []` to `skills: [architecture-decision-records]`; leaf == directory name, no `{source, leaf}` rename).

**Checkpoint**: `go -C tools/asctl build -o /tmp/asctl ./cmd/asctl/ && /tmp/asctl repo-check` recognizes the new skill directory and validates its frontmatter (name/description/filename limits) as the green baseline.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The `assets/*.md` templates and the shared `SKILL.md` machinery (consent
gate, verify-canonical guard, numbering rule, store/index rules, agent cross-link) that ALL
three user stories reuse.

**⚠️ CRITICAL**: No user story flow (Phases 3–5) can be authored until this phase completes.

- [x] T004 [P] Author `skills/architecture-decision-records/assets/madr-v4-template.md` — the Structured MADR v4 skeleton per `contracts/adr-madr-v4-template.md`: status/date/deciders frontmatter, `# NNNN. <title>`, Context and Problem Statement, **Decision Drivers (first)**, Considered Options, Decision Outcome (references a driver) + Consequences, **one Pros/Cons block per option**, and a `Links` section for supersession.
- [x] T005 [P] Author `skills/architecture-decision-records/assets/index-template.md` — the `docs/adr/README.md` seed + row format per `contracts/adr-index.md` (`# Architecture Decision Records` header + `| ADR | Title | Status | Date |` table; one row per ADR).
- [x] T006 [P] Author `skills/architecture-decision-records/assets/spec-to-adr-mapping.md` — the speckit-spec → MADR field mapping table per `contracts/spec-to-adr-mapping.md` (Context/Problem→Context; Success Criteria/Constraints→Decision Drivers; considered options/Alternatives→Considered Options + per-option Pros/Cons; chosen decision→Decision Outcome; silent field→"Not recorded in the spec"; spec link→Links).
- [x] T007 Author the `SKILL.md` core-rules body in `skills/architecture-decision-records/SKILL.md`: the **consent gate** (never create/modify a file without explicit affirmative consent — FR-002), a one-line **verify-canonical guard** pointing at `https://adr.github.io/madr/` / `https://github.com/adr/madr` (FR-014), the **non-inferable-delta** framing (encode repo-specific rules, not a restatement of the public MADR spec), and the **cross-link** to `agents/adr-generator/` for one-shot generation (FR-011).
- [x] T008 Author the numbering + store rules section in `skills/architecture-decision-records/SKILL.md`: next number = **`max(highest numeric filename prefix, highest number in the docs/adr/README.md index) + 1`** scanning **both** `docs/adr/NNNN-*.md` and legacy `docs/adr/adr-NNNN-*.md` filenames **and** the index, sequential and **never reused** even after deletion — the retained index row is the high-water mark (Clarifications 2026-07-02), zero-padded 4-digit, first = `0001` (FR-006, FR-013, SC-003); maintain the index at `docs/adr/README.md` (FR-005); initialize `docs/adr/` (index + `template.md` copy) **only on explicit consent** (FR-007); never rename/overwrite pre-existing files (FR-008, SC-007).

**Checkpoint**: Templates and shared machinery exist; user-story flows can now be authored.

---

## Phase 3: User Story 1 - Capture an architectural decision in-session (Priority: P1) 🎯 MVP

**Goal**: Detect a decision moment mid-session, offer (consent-gated) to capture, and on
consent emit a Structured MADR v4 record under `docs/adr/NNNN-title.md` with the index
updated and the next sequential number assigned.

**Independent Test**: `quickstart.md` Part B rows 1–5, 9, 10 — trigger a decision moment,
confirm an OFFER with no write; on consent confirm a MADR v4 file (drivers first, per-option
pros/cons, driver-linked outcome, `Links`) numbered `0001` and indexed; on decline confirm
nothing is written; confirm supersession links the old file and preserves it; confirm mixed
`adr-NNNN-*` legacy files are scanned for numbering and left byte-unchanged.

- [x] T009 [US1] Author the decision-moment detection section in `skills/architecture-decision-records/SKILL.md`: recognize explicit cues ("let's record this decision", "ADR this", "why did we choose X?"), the implicit cue (user weighs significant alternatives — framework/library/db/pattern/API/auth/infra — and reaches a conclusion), and the archival cue, and always respond with an **OFFER** only (FR-001, FR-002).
- [x] T010 [US1] Author the capture flow in `skills/architecture-decision-records/SKILL.md`: on consent, fill `assets/madr-v4-template.md` (drivers-first, one Pros/Cons block per option, outcome that names a driver, `Links`), assign the next number (per T008), write `docs/adr/NNNN-<kebab-title>.md`, initialize `docs/adr/` (index + template) on the first capture if absent, and append exactly one row to `docs/adr/README.md` (FR-003, FR-005, FR-006, FR-007, FR-013, SC-001).
- [x] T011 [US1] Author supersession handling in `skills/architecture-decision-records/SKILL.md`: a superseding ADR is written as a new file that links the old one, sets the old file's `status:` to `superseded by NNNN` and updates its index row, and otherwise preserves the old file — all consent-gated (FR-003, edge case, SC-007).

**Checkpoint**: User Story 1 is fully functional and independently testable (quickstart rows 1–5, 9, 10) — this is the MVP.

---

## Phase 4: User Story 2 - Answer "why did we choose X?" from recorded ADRs (Priority: P2)

**Goal**: Read the ADR index and matching record to answer rationale questions from what is
recorded; when nothing matches, say so honestly and offer to capture.

**Independent Test**: `quickstart.md` Part B rows 6–7 — with an ADR on disk, ask "why did we
choose X?" and confirm the answer quotes the recorded Decision Drivers + Outcome via the
index; ask about an unrecorded decision and confirm a "not recorded" answer plus an offer,
with no fabricated rationale.

- [x] T012 [US2] Author the retrieval flow in `skills/architecture-decision-records/SKILL.md`: read `docs/adr/README.md`, match the question against index titles (and, failing that, the indexed ADRs' Decision Drivers), open the matched file, and answer from its Decision Drivers + Decision Outcome; on no match (or missing store) state "not recorded" and offer to capture (consent-gated) — never fabricate a rationale (FR-009, SC-004).

**Checkpoint**: User Stories 1 AND 2 both work independently.

---

## Phase 5: User Story 3 - Archive a merged speckit spec as an ADR (Priority: P2)

**Goal**: On a spec merged to `main`, offer (consent-gated) to archive it as an ADR, mapping
spec fields into MADR fields without dropping or fabricating any.

**Independent Test**: `quickstart.md` Part B row 8 — point the archival path at a merged
`specs/NNN-slug/` with context/options/outcome; confirm an OFFER, and on consent an ADR whose
Context/Drivers/Options/Outcome carry the spec's fields, with any silent field marked "Not
recorded in the spec" rather than invented.

- [x] T013 [US3] Author the speckit-archival flow in `skills/architecture-decision-records/SKILL.md`: on a merged `specs/NNN-slug/` (trigger = #124 merge step or explicit user invocation, no forge polling), OFFER to archive; on consent map fields per `assets/spec-to-adr-mapping.md` (Context/Problem→Context; Success Criteria/Constraints→Drivers; considered options/Alternatives→Options + per-option Pros/Cons; chosen decision→Outcome; spec link→Links), write a silent field as "Not recorded in the spec" (never fabricated), assign the next number, write `docs/adr/NNNN-title.md`, and update the index (FR-010, SC-005).

**Checkpoint**: All three user stories are independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Bidirectional agent cross-link, changelog, plugin/manifest regeneration, and the
full CI-parity + behavioral gates.

- [x] T014 Add the reverse cross-link in `agents/adr-generator/agent.md`: a note pointing at the `architecture-decision-records` skill for in-session auto-detection + speckit archival (completes the bidirectional FR-011 relationship; agent stays for one-shot generation).
- [x] T015 [P] Add a changie fragment (`changie new --interactive=false --kind Added --body "..."`, writing to `.changes/unreleased/*.yaml`) that records the new skill AND the resolved FR-011 relationship decision (cross-link, keep both) (FR-016, FR-011).
- [x] T016 Sync the plugin tree: `bash scripts/sync-plugins.sh planning` — copies canonical `skills/architecture-decision-records/` → `plugins/planning/skills/architecture-decision-records/` and re-syncs `plugins/planning/agents/adr-generator.md` with the cross-link (depends on T007–T014 complete; do not hand-edit `plugins/planning/`).
- [x] T017 Regenerate manifests + docs: `python3 scripts/generate_manifests.py .` and `python3 scripts/generate_bundles_doc.py .` (refreshes `plugins/planning/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, and `docs/bundles.md`; never hand-edit these).
- [x] T018 Run the full CI-parity validation gate (quickstart Part A step 8): `/tmp/asctl repo-check`, `python3 scripts/check_bundle_refs.py .`, `python3 scripts/check_grouping.py .`, `python3 scripts/generate_manifests.py . --check`, `python3 scripts/generate_bundles_doc.py . --check`, `python3 scripts/check_consistency.py .`, `bash scripts/validate-plugins.sh`, and `python3 -m unittest discover -s tests -p 'test_*.py'` — all must pass (SC-006).
- [ ] T019 Run the behavioral acceptance walkthrough (quickstart Part B, `claude --plugin-dir ./plugins/planning`, rows 1–11) confirming consent-gating (SC-002), MADR completeness (SC-001), monotonic never-reused numbering (SC-003), retrieval honesty (SC-004), spec→ADR mapping (SC-005), installability in the `planning` plugin (SC-006), and pre-existing `docs/adr/` files byte-unchanged (SC-007).
- [ ] T020 [P] Audit `skills/architecture-decision-records/SKILL.md` against CONTRIBUTING "Skill content conventions" (non-inferable delta, MADR v4 version pin, verify-canonical guard) — e.g. via `/skill:audit` (FR-014).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately. T001 → T002 (same file); T003 is independent.
- **Foundational (Phase 2)**: Depends on Setup. T004/T005/T006 (separate reference files) parallel with each other; T007 → T008 (both edit `SKILL.md`, after T002). **BLOCKS all user stories.**
- **User Stories (Phase 3–5)**: All depend on Foundational. Because they all edit the single `SKILL.md`, they proceed **serially** (US1 → US2 → US3) rather than in parallel.
- **Polish (Phase 6)**: T014 (agent.md) can start any time; T015 (changie) independent. T016 depends on all `SKILL.md` authoring (T007–T013) **and** T014. T017 depends on T016. T018/T019 depend on T017. T020 depends on the `SKILL.md` body (T007–T013).

### User Story Dependencies

- **US1 (P1)**: Depends only on Foundational — the standalone MVP.
- **US2 (P2)**: Reads the index/records US1 produces; authored after US1 (same file). Independently testable against ADRs on disk.
- **US3 (P2)**: Reuses US1's capture/format/numbering machinery; authored after US1 (same file). Independently testable by invoking the archival path against a merged spec.

### Within Each User Story

- Reference templates (Phase 2) before the `SKILL.md` flows that fill them.
- Core rules (T007–T008) before story-specific flows (T009–T013).
- Story authoring complete before sync/regenerate/validate (Phase 6).

### Parallel Opportunities

- **Setup**: T003 ∥ T002.
- **Foundational**: T004 ∥ T005 ∥ T006 (three separate `assets/*.md` files).
- **Polish**: T015 (changie) and T020 (audit) are parallelizable with the agent/sync work as noted.
- **Not parallel**: every task that edits `SKILL.md` (T002, T007–T013) — same file, must be serial.

---

## Parallel Example: Foundational reference templates

```bash
# Author the three reference files together (separate files, no shared state):
Task: "Author assets/madr-v4-template.md per contracts/adr-madr-v4-template.md"
Task: "Author assets/index-template.md per contracts/adr-index.md"
Task: "Author assets/spec-to-adr-mapping.md per contracts/spec-to-adr-mapping.md"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (scaffold + frontmatter + registry line).
2. Complete Phase 2: Foundational (reference templates + core `SKILL.md` rules) — CRITICAL, blocks all stories.
3. Complete Phase 3: User Story 1 (in-session capture).
4. **STOP and VALIDATE**: run the Phase 6 sync/regenerate/validate on US1 alone (quickstart rows 1–5, 9, 10) — this is a complete, shippable skill.

### Incremental Delivery

1. Setup + Foundational → shared machinery ready.
2. Add US1 → validate (MVP: in-session capture works end-to-end).
3. Add US2 → validate (retrieval answers "why did we choose X?").
4. Add US3 → validate (speckit spec archival).
5. Finish Polish (cross-link, changie, regenerate, full gate, walkthrough).

### Note on single-file authoring

All three user stories are authored into one `SKILL.md`. Parallelization is limited to the
separate `assets/*.md`, `agent.md`, `planning.yaml`, and changie files — the `SKILL.md`
edits themselves must be sequenced. A single executor should own the `SKILL.md` body.

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks.
- [Story] label maps a task to its user story for traceability.
- `docs/adr/` is never created by this feature — the skill offers to create it at runtime, consent-gated (FR-007).
- Generated trees (`plugins/planning/`, manifests, `docs/bundles.md`) are produced by scripts — never hand-edit them (regenerate via T016/T017).
- Definition of Done (Constitution V): Phase 6 gate green, changie fragment present, and `lefthook` (pre-commit + pre-push) passes.
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.
