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

**Independent Test**: Read the evaluation doc `docs/evaluations/203-cc-spex-evaluation.md`
and confirm a reader can state the recommendation (adopt / don't adopt / conditional-adopt)
and its primary rationale without consulting outside notes.

**Acceptance Scenarios**:

1. **Given** the two named friction points, **When** the maintainer runs `cc-spex`
   through a representative `speckit-lifecycle` dry run, **Then** each friction point has
   a written finding (does `cc-spex` address it, partially, or not).
2. **Given** those findings, **When** the evaluation concludes, **Then** the evaluation doc
   carries a single, unambiguous recommendation (adopt / don't adopt / conditional-adopt)
   with rationale.
3. **Given** a "don't adopt" outcome, **When** the recommendation is recorded, **Then** the
   rationale is stated and (optionally) an alternative is proposed, and no curated-set draft
   diffs are required.

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
six extensions (the `spex` core plus the five bundled extensions) against each of the three
comparison targets (`speckit-lifecycle`, `review`, `planning`).

**Acceptance Scenarios**:

1. **Given** the six extensions (the `spex` core plus the five bundled), **When** the
   overlap check runs, **Then** each extension is classified as complementary, overlapping,
   or conflicting versus `speckit-lifecycle`, `review`, and `planning`.
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

If, and only if, the recommendation is adopt or conditional-adopt, the doc provides an
exact, ready-to-apply set of curated-set draft diffs (marked "draft only; apply after
approval + stated conditions"): a new row in the `docs/external-marketplaces.md` table plus
installation steps in the existing format, and matching `extraKnownMarketplaces` +
`enabledPlugins` entries for `.claude/settings.json`. Applying the diffs and verifying via
`/reload-plugins` is a user-gated follow-up, not part of this deliverable.

**Why this priority**: This is what lets the team actually *use* the tool, but it is
entirely gated on the P1 verdict — a flat "don't adopt" outcome produces no draft diffs, and
in no case does this deliverable edit the curated-set files itself.

**Independent Test**: On an adopt or conditional-adopt outcome, applying only the doc's
draft diffs and running `/reload-plugins` resolves and enables `spex@cc-rhuss-marketplace`;
in every case, confirm `.claude/settings.json` and `docs/external-marketplaces.md` are
unchanged by this deliverable.

**Acceptance Scenarios**:

1. **Given** an adopt or conditional-adopt recommendation, **When** the doc is written,
   **Then** it contains a fenced draft diff adding a `docs/external-marketplaces.md` table
   row + install steps consistent with the existing entries, and a fenced draft diff adding
   an `.claude/settings.json` `extraKnownMarketplaces` entry (key `cc-rhuss-marketplace`) and
   an `enabledPlugins` line (`spex@cc-rhuss-marketplace`).
2. **Given** the draft diffs, **When** a user later applies them and runs `/reload-plugins`,
   **Then** the plugin resolves and enables without error; the doc names this as the
   required post-apply verification step.
3. **Given** any outcome, **When** the change ships, **Then** a `changie` fragment is
   added (per the constitution's Definition of Done).

---

### Edge Cases

- **`speckit-lifecycle` (#124) not yet merged**: it is a sibling Wave-1 item, so the
  evaluation MUST proceed against a *representative dry run* of the intended workflow
  rather than blocking on the merged skill.
- **Don't-adopt outcome**: the doc records the rationale (and optionally an alternative) and
  omits the curated-set draft diffs; in no outcome are `docs/external-marketplaces.md` or
  `.claude/settings.json` edited — the changie fragment records the evaluation doc itself,
  not a wiring change.
- **Partial fit**: `cc-spex` solves one friction point but not the other, or a subset of
  its extensions conflict — the decision MUST state which parts are adopted/enabled and
  which are declined, rather than an all-or-nothing verdict.
- **Marketplace shape mismatch**: if the distribution marketplace
  `cc-rhuss-marketplace` (repo `rhuss/cc-rhuss-marketplace`) lacks a valid
  `.claude-plugin/marketplace.json` or the `spex@cc-rhuss-marketplace` id does not resolve,
  it fails the curated-set precondition and cannot be adopted as-is. (Note: `rhuss/cc-spex`'s
  own repo-root marketplace is `spex-plugin-development`, dev-only, and is not the wiring target.)
- **Auto-update risk**: if maintenance evidence is weak, the recommendation must be a
  pinned `ref` with `autoUpdate: false` rather than tracking the default branch.

## Clarifications

### Session 2026-07-02

- Q: Where is the evaluation recommendation recorded — a comment on GitHub issue #203, or a versioned doc in the repo? → A: A versioned doc at `docs/evaluations/203-cc-spex-evaluation.md` is the authoritative deliverable; issue #203 may carry a short pointer/summary, but the doc is the record.
- Q: On an "adopt" recommendation, does this deliverable apply the curated-set wiring (edit `.claude/settings.json` + `docs/external-marketplaces.md`) or only propose it? → A: Research + recommendation only — the doc provides exact, unapplied draft diffs for both files; it never edits `.claude/settings.json` or `docs/external-marketplaces.md` (applying them is a user-gated follow-up).
- Q: Is the recommendation binary (adopt / don't adopt) or does it allow a middle outcome? → A: Three-way — adopt / don't adopt / conditional-adopt (conditions enumerated), with per-extension scoping when only a subset fits.
- Q: When the recommendation is conditional-adopt (not a flat "adopt"), must the doc still include the curated-set draft diffs? → A: Yes — include the draft diffs (marked "draft only; apply after approval + stated conditions") for any adopt or conditional-adopt outcome; omit them only on a flat "don't adopt".
- Q: Which repo/marketplace does the wiring target — `rhuss/cc-spex` or a separate distribution marketplace? → A: `extraKnownMarketplaces` key `cc-rhuss-marketplace` → repo `rhuss/cc-rhuss-marketplace` (the distribution marketplace); `rhuss/cc-spex`'s own repo-root marketplace is `spex-plugin-development` (dev-only) and MUST NOT be used for wiring.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The evaluation MUST assess `cc-spex` against the two upstream-reported
  friction points — constitution drift and session continuity — using real
  `speckit-lifecycle` usage or a representative dry run, and record a written finding for
  each.
- **FR-002**: The evaluation MUST document overlap and conflict for each of the six
  extensions — the always-on `spex` core plus the five bundled extensions (`spex-gates`,
  `spex-worktrees`, `spex-teams`, `spex-deep-review`, `spex-collab`) — against
  `speckit-lifecycle` (#124), the `review` bundle, and the `planning` bundle.
- **FR-003**: The evaluation MUST document a maintenance/trust check (release cadence and
  issue responsiveness) and record an explicit `autoUpdate` suitability recommendation.
- **FR-004**: The evaluation MUST record a single, unambiguous recommendation — adopt,
  don't adopt, or conditional-adopt (with conditions enumerated) — with rationale, in the
  evaluation doc `docs/evaluations/203-cc-spex-evaluation.md`. Issue #203 may carry a short
  pointer to that doc, but the doc is the authoritative record.
- **FR-005**: On an adopt or conditional-adopt recommendation, the doc MUST include an
  exact, unapplied draft diff (a fenced code block) that adds a `docs/external-marketplaces.md`
  table row and installation steps in the existing table/steps format. The deliverable MUST
  NOT edit `docs/external-marketplaces.md` itself — applying the diff is a user-gated follow-up.
- **FR-006**: On an adopt or conditional-adopt recommendation, the doc MUST include an
  exact, unapplied draft diff (a fenced code block) that adds an `extraKnownMarketplaces`
  entry (key `cc-rhuss-marketplace` → repo `rhuss/cc-rhuss-marketplace`) and an
  `enabledPlugins` line (`spex@cc-rhuss-marketplace`) to `.claude/settings.json`, matching
  the existing curated-set wiring. The deliverable MUST NOT edit `.claude/settings.json` itself.
- **FR-007**: `/reload-plugins` verification of the `.claude/settings.json` change is
  deferred to the user's post-approval apply step and is out of scope for this
  research-only deliverable; the doc MUST name it as the required verification step for
  whoever applies the draft diff.
- **FR-008**: The change MUST NOT re-host `cc-spex` content inside the `rdl` marketplace;
  the plugin is consumed from its upstream marketplace per the "why not re-host" rationale.
- **FR-009**: The change MUST include a `changie` fragment (per Definition of Done)
  recording the evaluation deliverable (the recommendation doc), regardless of the
  adopt / don't-adopt / conditional-adopt outcome.
- **FR-010**: The evaluation MUST confirm the curated-set precondition — that the plugin is
  consumed from the distribution marketplace `cc-rhuss-marketplace` (repo
  `rhuss/cc-rhuss-marketplace`, which has `.claude-plugin/marketplace.json`) as
  `spex@cc-rhuss-marketplace`, and that `rhuss/cc-spex`'s own repo-root marketplace
  (`spex-plugin-development`) is a dev-only marketplace that MUST NOT be used for wiring —
  before proposing any wiring.

### Key Entities *(include if feature involves data)*

- **Evaluation dimension**: one of the three assessed axes — friction-point fit,
  overlap/conflict, and maintenance/trust — each producing a written finding.
- **Bundled extension**: one of the five `cc-spex` sub-plugins under evaluation
  (`spex-gates`, `spex-worktrees`, `spex-teams`, `spex-deep-review`, `spex-collab`), each
  mapped to a complementary/overlapping/conflicting relationship with existing tooling; the
  overlap matrix additionally classifies the always-on `spex` core, for six rows total.
- **Decision record**: the adopt / don't-adopt / conditional-adopt recommendation plus
  rationale, anchored in the evaluation doc `docs/evaluations/203-cc-spex-evaluation.md`.
- **Curated-set entry**: the paired `docs/external-marketplaces.md` table row + install
  steps and `.claude/settings.json` `extraKnownMarketplaces`/`enabledPlugins` lines,
  delivered as unapplied draft diffs on an adopt or conditional-adopt recommendation and
  never applied to those files by this deliverable.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A reader of the evaluation doc can state the final recommendation
  (adopt / don't adopt / conditional-adopt) and its primary rationale in one sentence
  without consulting any outside notes.
- **SC-002**: All three evaluation dimensions (friction, overlap, maintenance) each have
  at least one written finding; none is left unaddressed.
- **SC-003**: The overlap analysis covers all 6 extensions (the `spex` core plus the 5
  bundled extensions) across all 3 comparison targets (18 relationship classifications,
  each labelled complementary, overlapping, or conflicting).
- **SC-004**: On an adopt or conditional-adopt outcome, a team member can enable `cc-spex`
  by applying only the doc's draft diffs — with zero undocumented steps; `/reload-plugins`
  resolving the plugin is the user's post-apply verification, not part of this deliverable.
- **SC-005**: This deliverable never edits `.claude/settings.json` or
  `docs/external-marketplaces.md` for any outcome (adopt wiring is user-gated); on a
  don't-adopt or conditional-adopt outcome the recorded rationale references at least one
  concrete evaluation finding.
- **SC-006**: The `autoUpdate` recommendation is backed by at least one concrete
  maintenance data point (a dated release/commit or an issue-response observation).
- **SC-007**: A `changie` fragment is present for the change, satisfying the
  `changelog-check.yml` gate.

## Assumptions

- **`speckit-lifecycle` (#124) is not yet merged** (sibling Wave-1 work), so the friction
  evaluation is performed against a representative dry run of the intended SpecKit +
  Superpowers workflow rather than the shipped skill.
- The adoptable unit is the single `spex` plugin from the distribution marketplace
  `cc-rhuss-marketplace` (repo `rhuss/cc-rhuss-marketplace`), consumed upstream — not the
  dev-only `spex-plugin-development` marketplace at the root of `rhuss/cc-spex`; individual
  sub-extensions are enabled through that plugin, not re-hosted.
- The existing curated-set format is the template: the `docs/external-marketplaces.md`
  table + "Adding or removing a marketplace" steps, and the `extraKnownMarketplaces` /
  `enabledPlugins` blocks already in `.claude/settings.json`.
- "Constitution drift" and "session continuity" are the two friction points named upstream
  and in the issue; they are the required evaluation lens, not an exhaustive list.
- The decision is authoritative for the "what" per constitution Principle I; if adoption
  later proves wrong, the fix is to amend the decision, not silently diverge.
- The evaluation may rely on the upstream repo's public README, releases, and issue tracker
  as maintenance evidence; no private or paid access is assumed.
