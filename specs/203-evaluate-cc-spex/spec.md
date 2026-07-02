# Feature Specification: Evaluate cc-spex for the curated external-marketplace set

**Feature Branch**: `203-evaluate-cc-spex`  
**Created**: 2026-07-02  
**Status**: Draft  
**Input**: User description: "Evaluate rhuss/cc-spex for the curated external-marketplace set (SpecKit + Superpowers plugin)" (GitHub issue #203, part of the #207 SpecKit + Superpowers workflow epic)

## User Scenarios & Testing *(mandatory)*

This feature is an **evaluation and decision** deliverable, not a code change. Its
product is a defensible, recorded verdict on whether `rhuss/cc-spex` (marketplace
`cc-rhuss-marketplace`, plugin `spex`) joins the team's curated external-plugin set —
plus the curated-set wiring **only if** the verdict is "adopt". The actors are the
repo maintainer who runs the evaluation and records the decision, and the downstream
team members who consume the curated set when working inside this repo.

### User Story 1 - Record an evidence-backed adopt/reject decision (Priority: P1)

A maintainer assesses `cc-spex` against the team's actual `speckit-lifecycle` workflow
for the two friction points reported upstream — **constitution drift** (spec/constitution
intent decaying as work progresses) and **session continuity** (losing workflow state
between Claude Code sessions) — and records a clear "adopt" or "don't adopt" decision
with rationale.

**Why this priority**: The decision is the whole point of the issue. Even with nothing
else, a maintainer who can state "adopt because X" or "reject because Y" grounded in a
representative run has delivered the core value and unblocks the #207 epic.

**Independent Test**: Read issue #203 (and the evaluation artifacts it references) and
confirm a reader can state the decision and its primary rationale without consulting
outside notes.

**Acceptance Scenarios**:

1. **Given** the two named friction points, **When** the maintainer runs `cc-spex`
   through a representative `speckit-lifecycle` dry run, **Then** each friction point has
   a written finding (does `cc-spex` address it, partially, or not).
2. **Given** those findings, **When** the evaluation concludes, **Then** issue #203
   carries a single, unambiguous adopt/reject decision with rationale.
3. **Given** a "reject" outcome, **When** the decision is recorded, **Then** the
   rationale is stated and (optionally) an alternative is proposed, and no curated-set
   changes are made.

---

### User Story 2 - Document overlap and conflict with existing tooling (Priority: P2)

Before adopting anything, the maintainer documents whether `cc-spex`'s bundled
extensions — `spex-gates`, `spex-worktrees`, `spex-teams`, `spex-deep-review`,
`spex-collab` — overlap or conflict with what `speckit-lifecycle` (#124), the `review`
bundle, and the `planning` bundle already provide.

**Why this priority**: Adopting tooling that duplicates or fights existing capabilities
(e.g. worktree isolation, review gates, planning agents) would create confusion and
violate the constitution's single-pipeline boundary. This analysis is a required input
to the P1 decision but is separately valuable as a capability map.

**Independent Test**: Confirm a written overlap/conflict finding exists for each of the
five bundled extensions against each of the three comparison targets (`speckit-lifecycle`,
`review`, `planning`).

**Acceptance Scenarios**:

1. **Given** the five bundled extensions, **When** the overlap check runs, **Then** each
   extension is classified as complementary, overlapping, or conflicting versus
   `speckit-lifecycle`, `review`, and `planning`.
2. **Given** a conflict is found (e.g. two competing worktree mechanisms — see #206),
   **When** it is documented, **Then** the finding names the conflicting capability and
   its impact on the SpecKit → Superpowers handoff boundary.

---

### User Story 3 - Establish maintenance and auto-update trust (Priority: P3)

The maintainer checks whether `cc-spex` is actively maintained (release cadence, issue
responsiveness) and decides whether `autoUpdate: true` is an acceptable posture, matching
the "Auto-update and trust" guidance in `docs/external-marketplaces.md`.

**Why this priority**: `autoUpdate: true` pulls the vendor's default branch at startup
and runs with the user's privileges, so trust must be established before committing to it.
This gates *how* an adopted plugin is wired, not *whether* it is adopted.

**Independent Test**: Confirm a written maintenance finding exists (recent release/commit
activity and issue-response evidence) plus an explicit `autoUpdate` recommendation.

**Acceptance Scenarios**:

1. **Given** the upstream repo, **When** the maintenance check runs, **Then** release
   cadence and issue responsiveness are summarized with concrete evidence.
2. **Given** that evidence, **When** the check concludes, **Then** an explicit
   `autoUpdate: true`/pinned recommendation is recorded with its rationale.

---

### User Story 4 - Wire cc-spex into the curated set when adopted (Priority: P3, conditional)

If, and only if, the decision is "adopt", a team member finds `cc-spex` in the curated
set: a new row in the `docs/external-marketplaces.md` table plus installation steps in
the existing format, and matching `extraKnownMarketplaces` + `enabledPlugins` entries in
`.claude/settings.json`, verified via `/reload-plugins`.

**Why this priority**: This is the deliverable that lets the team actually *use* the tool,
but it is entirely gated on the P1 verdict — a "reject" outcome produces no wiring.

**Independent Test**: On an "adopt" outcome, follow only the documented steps and confirm
`spex@cc-rhuss-marketplace` resolves and enables after `/reload-plugins`; on a "reject"
outcome, confirm no curated-set files changed.

**Acceptance Scenarios**:

1. **Given** an "adopt" decision, **When** the curated set is updated, **Then**
   `docs/external-marketplaces.md` gains a table row and install steps consistent with the
   existing entries, and `.claude/settings.json` gains an `extraKnownMarketplaces` entry
   (keyed by the marketplace `name`) and an `enabledPlugins` line.
2. **Given** the settings change, **When** `/reload-plugins` runs, **Then** the plugin
   resolves and enables without error, and this is noted as verification.
3. **Given** any outcome, **When** the change ships, **Then** a `changie` fragment is
   added (per the constitution's Definition of Done).

---

### Edge Cases

- **`speckit-lifecycle` (#124) not yet merged**: it is a sibling Wave-1 item, so the
  evaluation MUST proceed against a *representative dry run* of the intended workflow
  rather than blocking on the merged skill.
- **Reject outcome**: the issue is closed with rationale (and optionally an alternative);
  no `docs/` or `settings.json` edits are made — the changie fragment then records the
  decision itself, not a wiring change.
- **Partial fit**: `cc-spex` solves one friction point but not the other, or a subset of
  its extensions conflict — the decision MUST state which parts are adopted/enabled and
  which are declined, rather than an all-or-nothing verdict.
- **Marketplace shape mismatch**: if `rhuss/cc-spex` lacks a valid
  `.claude-plugin/marketplace.json` or the `spex@cc-rhuss-marketplace` id does not resolve,
  it fails the curated-set precondition and cannot be adopted as-is.
- **Auto-update risk**: if maintenance evidence is weak, the recommendation must be a
  pinned `ref` with `autoUpdate: false` rather than tracking the default branch.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The evaluation MUST assess `cc-spex` against the two upstream-reported
  friction points — constitution drift and session continuity — using real
  `speckit-lifecycle` usage or a representative dry run, and record a written finding for
  each.
- **FR-002**: The evaluation MUST document overlap and conflict for each of the five
  bundled extensions (`spex-gates`, `spex-worktrees`, `spex-teams`, `spex-deep-review`,
  `spex-collab`) against `speckit-lifecycle` (#124), the `review` bundle, and the
  `planning` bundle.
- **FR-003**: The evaluation MUST document a maintenance/trust check (release cadence and
  issue responsiveness) and record an explicit `autoUpdate` suitability recommendation.
- **FR-004**: The evaluation MUST record a single, unambiguous decision — adopt or don't
  adopt — with rationale, in GitHub issue #203.
- **FR-005**: On an "adopt" decision, the change MUST add a `docs/external-marketplaces.md`
  table row and installation steps that follow the existing table/steps format.
- **FR-006**: On an "adopt" decision, the change MUST add an `extraKnownMarketplaces` entry
  (keyed by the marketplace `name`) and an `enabledPlugins` line to `.claude/settings.json`,
  matching the existing curated-set wiring.
- **FR-007**: On an "adopt" decision, the `.claude/settings.json` change MUST be verified
  via `/reload-plugins` and the verification recorded.
- **FR-008**: The change MUST NOT re-host `cc-spex` content inside the `rdl` marketplace;
  the plugin is consumed from its upstream marketplace per the "why not re-host" rationale.
- **FR-009**: The change MUST include a `changie` fragment (per Definition of Done),
  recording either the curated-set addition (adopt) or the recorded decision (reject).
- **FR-010**: The evaluation MUST confirm the curated-set precondition — that
  `rhuss/cc-spex` is a real Claude Code marketplace (has `.claude-plugin/marketplace.json`)
  and that `spex@cc-rhuss-marketplace` is the correct plugin id — before proposing any
  wiring.

### Key Entities *(include if feature involves data)*

- **Evaluation dimension**: one of the three assessed axes — friction-point fit,
  overlap/conflict, and maintenance/trust — each producing a written finding.
- **Bundled extension**: one of the five `cc-spex` sub-plugins under evaluation
  (`spex-gates`, `spex-worktrees`, `spex-teams`, `spex-deep-review`, `spex-collab`), each
  mapped to a complementary/overlapping/conflicting relationship with existing tooling.
- **Decision record**: the adopt/reject verdict plus rationale, anchored in issue #203.
- **Curated-set entry**: the paired `docs/external-marketplaces.md` table row + install
  steps and `.claude/settings.json` `extraKnownMarketplaces`/`enabledPlugins` lines,
  created only on adopt.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A reader of issue #203 can state the final decision and its primary
  rationale in one sentence without consulting any outside notes.
- **SC-002**: All three evaluation dimensions (friction, overlap, maintenance) each have
  at least one written finding; none is left unaddressed.
- **SC-003**: The overlap analysis covers all 5 bundled extensions across all 3 comparison
  targets (15 relationship classifications, each labelled complementary, overlapping, or
  conflicting).
- **SC-004**: On an "adopt" outcome, a team member can enable `cc-spex` by following only
  the documented steps — with zero undocumented steps — and `/reload-plugins` resolves the
  plugin without error.
- **SC-005**: On a "reject" outcome, zero files under `docs/` or `.claude/settings.json`
  change, and the recorded rationale references at least one concrete evaluation finding.
- **SC-006**: The `autoUpdate` recommendation is backed by at least one concrete
  maintenance data point (a dated release/commit or an issue-response observation).
- **SC-007**: A `changie` fragment is present for the change, satisfying the
  `changelog-check.yml` gate.

## Assumptions

- **`speckit-lifecycle` (#124) is not yet merged** (sibling Wave-1 work), so the friction
  evaluation is performed against a representative dry run of the intended SpecKit +
  Superpowers workflow rather than the shipped skill.
- The adoptable unit is the single `spex` plugin from marketplace `cc-rhuss-marketplace`
  (repo `rhuss/cc-spex`), consumed upstream; individual sub-extensions are enabled through
  that plugin, not re-hosted.
- The existing curated-set format is the template: the `docs/external-marketplaces.md`
  table + "Adding or removing a marketplace" steps, and the `extraKnownMarketplaces` /
  `enabledPlugins` blocks already in `.claude/settings.json`.
- "Constitution drift" and "session continuity" are the two friction points named upstream
  and in the issue; they are the required evaluation lens, not an exhaustive list.
- The decision is authoritative for the "what" per constitution Principle I; if adoption
  later proves wrong, the fix is to amend the decision, not silently diverge.
- The evaluation may rely on the upstream repo's public README, releases, and issue tracker
  as maintenance evidence; no private or paid access is assumed.
