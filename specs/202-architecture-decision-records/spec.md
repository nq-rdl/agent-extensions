# Feature Specification: Architecture Decision Records Skill (Structured MADR)

**Feature Branch**: `202-architecture-decision-records`  
**Created**: 2026-07-02  
**Status**: Draft  
**Input**: User description: "Architecture Decision Records skill (Structured MADR) in the planning bundle"

## Clarifications

### Session 2026-07-02

- Q: When the highest-numbered ADR is deleted, how is the next number derived so it is never reused? → A: Next number = `max(highest numeric filename prefix in docs/adr/, highest number in the docs/adr/README.md index) + 1`. A manual deletion leaves the index row behind, so the index preserves the high-water mark even when the file is gone; taking the max of both sources guarantees a number is never reused even when the highest-numbered ADR's file is deleted.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Capture an architectural decision in-session (Priority: P1)

A developer working in an ordinary coding session reaches a decision point — they
say "let's record this decision", ask "why did we choose X?", or are visibly
weighing significant alternatives. The skill recognizes the moment, offers to
capture an Architecture Decision Record, and — only after the developer agrees —
writes a Structured MADR document that names the decision drivers first, gives each
considered option its own pros/cons block, states an outcome tied back to those
drivers, and includes a `Links` section for later supersession. It files the record
under `docs/adr/`, assigns the next sequential number, and updates the ADR index.

**Why this priority**: This is the core value of the feature — turning a decision
that would otherwise vanish into chat history into a durable, house-standard record,
surfaced at the moment the decision is made rather than requiring a separate agent
to be dispatched after the fact. Delivered alone, it is a complete, useful product.

**Independent Test**: In a session, trigger a decision moment (e.g. "let's record
why we picked the queue over the cron poller"). Confirm the skill offers to capture,
writes nothing until consent is given, then on consent produces a Structured MADR
file with drivers, per-option pros/cons, a driver-linked outcome, and a `Links`
section, numbered sequentially and indexed.

**Acceptance Scenarios**:

1. **Given** a session where the developer says "let's record this decision", **When** the skill detects the cue, **Then** it offers to capture an ADR and writes no file until the developer explicitly consents.
2. **Given** the developer consents, **When** the ADR is written, **Then** the document is a Structured MADR with decision drivers named first, each considered option in its own pros/cons block, an outcome that references the drivers, and a `Links` section.
3. **Given** existing ADRs numbered up to N, **When** a new ADR is created, **Then** it receives number N+1 and the ADR index is updated to list it.
4. **Given** no `docs/adr/` exists yet, **When** the first capture is confirmed, **Then** the skill offers to initialize `docs/adr/` with an index and template and only does so on confirmation.
5. **Given** the developer declines the offer to capture, **When** they continue working, **Then** no file is created or modified.

---

### User Story 2 - Answer "why did we choose X?" from recorded ADRs (Priority: P2)

A developer (or a later maintainer) asks why a past choice was made. The skill reads
the ADR index and the relevant record and answers from what is recorded, rather than
guessing or re-deriving the rationale.

**Why this priority**: The records only pay off if they are read back. Retrieval
turns the store from write-only archive into a living rationale source, and is
independently valuable even before speckit archival exists.

**Independent Test**: With one or more ADRs on disk, ask "why did we choose X?" and
confirm the answer is grounded in the recorded drivers/outcome of the matching ADR;
when no ADR matches, confirm the skill says so and offers to capture one.

**Acceptance Scenarios**:

1. **Given** an ADR recording a decision about X, **When** the developer asks "why did we choose X?", **Then** the skill locates it via the index and answers from its drivers and outcome.
2. **Given** no ADR records the decision, **When** the developer asks, **Then** the skill states that none is recorded and offers to capture one.

---

### User Story 3 - Archive a merged speckit spec as an ADR (Priority: P2)

When a speckit spec is merged to `main` (the #124 lifecycle merge step), the
context, considered options, and decision outcome captured in `specs/NNN-slug/`
would otherwise be lost once that directory stops being actively read. The skill
offers — consent-gated — to archive the merged spec as an ADR, mapping the spec's
fields into the corresponding MADR fields so the durable record survives worktree
teardown.

**Why this priority**: This is the tie-in that distinguishes the skill from the
existing one-shot agent and closes the #124 rationale-preservation gap. It depends
on the capture and formatting machinery from User Story 1, so it follows P1.

**Independent Test**: Given a merged spec with context, considered options, and an
outcome, invoke the archival path and confirm the skill offers to archive, and on
consent produces an ADR whose MADR fields carry the spec's context, options, and
outcome — with no field silently dropped and none fabricated where the spec is
silent.

**Acceptance Scenarios**:

1. **Given** a spec merged to `main`, **When** the archival path runs, **Then** the skill offers to archive it and writes nothing without consent.
2. **Given** consent, **When** the ADR is produced, **Then** the spec's context, considered options, and decision outcome each map to their corresponding MADR fields.
3. **Given** the spec is silent on a MADR-relevant field, **When** the ADR is produced, **Then** that field is marked absent rather than invented.

---

### Edge Cases

- **No ADR store yet**: `docs/adr/` is created only on explicit confirmation; the skill never creates it silently.
- **Numbering gaps or deleted records**: the next number is `max(highest file prefix, highest index entry) + 1`; because the index retains a deleted ADR's row, a number is never reused even when the highest-numbered ADR's file has been deleted.
- **Supersession**: a new ADR that replaces an earlier one links to it and marks the earlier record superseded; the earlier file is preserved, not overwritten.
- **Filename-convention collision**: the skill writes `NNNN-title.md` while any pre-existing agent files use `adr-NNNN-slug.md`; the two conventions coexist. Next-number derivation reads the numeric prefix across both, so a shared number is never minted twice, and existing files are never renamed.
- **Declined capture**: no file is written or changed.
- **Retrieval miss**: asking "why did we choose X?" when nothing is recorded yields an honest "not recorded" plus an offer to capture, not a fabricated rationale.
- **Merged spec missing fields**: absent spec content is represented as absent in the ADR, never fabricated.

## Requirements *(mandatory)*

### Functional Requirements

**Detection & consent**

- **FR-001**: The skill MUST auto-detect decision moments during an ordinary session, from both explicit cues ("let's record this decision", "ADR this", "why did we choose X?") and implicit ones (the user weighing significant alternatives — framework, library, database, pattern, API, auth, or infrastructure — and reaching a conclusion).
- **FR-002**: The skill MUST offer to capture an ADR at a detected moment and MUST NOT create or modify any file without the user's explicit consent.

**ADR format**

- **FR-003**: The skill MUST produce Structured MADR documents in which decision drivers are named first, each considered option has its own pros/cons block, the outcome is stated explicitly and tied back to the drivers, and a `Links` section supports supersession.
- **FR-004**: The skill MUST pin the MADR specification version it targets (baseline `adr/madr` v4), so format drift is visible and reviewable.

**ADR store & numbering**

- **FR-005**: The skill MUST maintain an ADR index at `docs/adr/README.md` that lists recorded ADRs.
- **FR-006**: The skill MUST derive the next ADR number as `max(highest numeric filename prefix in docs/adr/, highest number recorded in the docs/adr/README.md index) + 1`, scanning both `NNNN-*.md` and legacy `adr-NNNN-*.md` filenames. Numbers MUST be sequential, zero-padded to 4 digits (first ADR = `0001`), and MUST never be reused — because the index retains a deleted ADR's row as a high-water mark, deleting even the highest-numbered ADR does not free its number.
- **FR-007**: The skill MUST initialize `docs/adr/` (index + template) only on explicit user confirmation, never silently.
- **FR-008**: The on-disk location MUST remain `docs/adr/`, and any pre-existing ADRs there MUST be left untouched.

**Retrieval**

- **FR-009**: The skill MUST answer "why did we choose X?" by matching the question against the ADR index — first by ADR title, then, if no title matches, by scanning the recorded Decision Drivers of the indexed ADRs — and answering from the matched ADR's drivers and outcome; when none matches, it MUST say so and offer to capture one.

**Speckit archival**

- **FR-010**: When a speckit spec is merged to `main`, the skill MUST offer (consent-gated) to archive it as an ADR, mapping the spec's context, considered options, and decision outcome into the corresponding MADR fields, without fabricating fields the spec leaves silent.

**Reconciliation with the existing tooling (decided)**

- **FR-011**: Both the skill and the existing `adr-generator` agent MUST be kept and cross-linked — the agent remains the one-shot, explicitly-dispatched generator; the skill provides in-session detection, retrieval, and speckit archival. The relationship MUST be documented in both the skill and the agent, and recorded in a changie fragment.
- **FR-012**: The skill MUST target Structured MADR (`adr/madr`) v4, pinned per FR-004 so format drift stays visible and reviewable. A future successor superseding v4 would be a new decision, recorded as its own ADR.
- **FR-013**: ADR files the skill writes MUST use the `NNNN-title.md` convention (4-digit zero-padded number + kebab-case title). Pre-existing `adr-NNNN-slug.md` files MUST NOT be renamed, and next-number derivation (FR-006) MUST span both conventions.

**Delivery & conventions**

- **FR-014**: The skill MUST live at `skills/architecture-decision-records/`, validate against `asctl repo-check`, and follow the CONTRIBUTING skill-content conventions (encode the non-inferable delta, pin versions, include a verify-canonical guard pointing at the authoritative MADR source).
- **FR-015**: The skill MUST be added to the `planning` bundle and its plugin tree synced so it installs as part of that plugin.
- **FR-016**: The change MUST ship with a changie fragment.

### Key Entities *(include if feature involves data)*

- **Architecture Decision Record (ADR)**: a single Structured MADR document — title, status, decision drivers, considered options with per-option pros/cons, driver-linked outcome, `Links`/supersession, and a sequential number. Stored under `docs/adr/`.
- **ADR index**: the catalog at `docs/adr/README.md` listing recorded ADRs and their numbering; the source consulted for retrieval and next-number derivation.
- **ADR template**: the skeleton used to create a new ADR consistently.
- **Speckit spec**: `specs/NNN-slug/spec.md` and its siblings — the source whose context, considered options, and outcome are mapped into an ADR at archival.
- **Decision moment**: an in-session trigger (explicit cue or observed weighing of alternatives) that prompts the skill to offer capture.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of ADRs the skill produces contain all required MADR elements — decision drivers, per-option pros/cons, a driver-linked outcome, and a `Links` section.
- **SC-002**: Zero ADR files are ever created or modified without a recorded user confirmation.
- **SC-003**: ADR numbers across the store are unique and monotonic — no duplicated or reused numbers, even after a file is deleted.
- **SC-004**: For any recorded decision, a developer asking "why did we choose X?" receives an answer grounded in that ADR; for an unrecorded decision, they are told it is not recorded.
- **SC-005**: For a merged speckit spec, its context, considered options, and outcome are each represented in the archived ADR, with no field dropped and no field fabricated where the spec is silent.
- **SC-006**: The skill passes `asctl repo-check` and the repo CI-parity checks, and appears as an installable member of the `planning` plugin.
- **SC-007**: Every pre-existing file under `docs/adr/` is byte-unchanged after the skill is introduced.

## Assumptions

- **Baseline format**: Structured MADR (`adr/madr`) v4 is the target format (FR-012), pinned in the skill; a future successor superseding it would be a new, separately recorded decision.
- **On-disk location**: `docs/adr/` is the canonical location, matching the existing `adr-generator` agent, so existing ADRs are unaffected.
- **Skill medium**: the deliverable is a documentation/markdown skill (no CLI wrapper or MCP server), per the repo Language Policy for documentation-only skills.
- **Merge signal**: detection of "merged to `main`" relies on the #124 speckit lifecycle merge step or the user invoking the archival path at that point; no bespoke forge polling or integration beyond reading the merged spec is assumed (a stated non-goal).
- **Consent**: "explicit consent" means an affirmative user response in-session before any write.
- **Reconciliation decisions are durably recorded, not just in-spec**: the three reconciliation choices (FR-011–FR-013) are settled — keep-both-and-cross-link, MADR v4, `NNNN-title.md`. Because speckit specs are branch-ephemeral, these are recorded durably outside the spec (in the skill body, the `adr-generator` cross-link, and a changie fragment), so they survive the spec being stripped at trunk merge. Their rationale/alternatives are captured in `research.md` (R1–R4).

## Out of Scope (Non-goals)

- Speckit lifecycle orchestration itself — that is #124, not this feature.
- Auto-writing ADRs without user confirmation.
- Bespoke forge integration beyond what is needed to read a merged spec.
- Renaming or rewriting existing ADRs under `docs/adr/`.

## Dependencies

- The #124 speckit lifecycle work provides the merge step that triggers the archival path (FR-010); the archival user story is fully useful only alongside it.
- The `planning` bundle and the repo's sync/validation pipeline (`scripts/sync-plugins.sh`, `asctl repo-check`) are the delivery vehicle (FR-014–FR-015).
