# Phase 0 Research: Architecture Decision Records Skill

Resolves the three questions the spec deferred to implementation (FR-011, FR-012,
FR-013) plus the concrete shape of the Structured MADR v4 record and the numbering
rule. Each finding is recorded as Decision / Rationale / Alternatives so the choices
are reviewable and — fittingly — could themselves be captured as ADRs.

## R1 — ADR format (resolves FR-012)

- **Decision**: **Structured MADR v4** (MADR = Markdown Any Decision Records, project
  `adr/madr`, spec version **4.x**). The emitted record names **Decision Drivers first**,
  gives **each Considered Option its own Pros/Cons block**, states a **Decision Outcome
  that references the drivers**, and carries a **`Links` section** for supersession.
- **Rationale**: MADR v4 is the current, actively maintained ADR standard and is the
  richest of the common templates — it makes decision drivers and per-option trade-offs
  first-class, which is exactly what "why did we choose X?" retrieval (US2) needs. The
  spec already fixed v4 as the baseline (Assumptions), and the task decided v4.
- **Alternatives considered**:
  - *Nygard-lite* (the reference ECC skill's format: Context/Decision/Consequences with
    an ad-hoc Alternatives list) — rejected: no first-class decision drivers, weaker
    per-option structure; loses the driver→outcome linkage the spec mandates (FR-003).
  - *MADR "minimal" template* — rejected: omits per-option Pros/Cons and drivers, so it
    cannot satisfy SC-001.
  - *A bespoke house format* — rejected: reinvents a standard and defeats the
    verify-canonical guard (nothing authoritative to check against).
- **Pin & guard**: pin `MADR v4` in `SKILL.md` `compatibility:`; verify-canonical points
  at `https://adr.github.io/madr/` and `https://github.com/adr/madr` (FR-004, FR-014).

## R2 — Relationship to `agents/adr-generator/` (resolves FR-011)

- **Decision**: **Cross-link; keep both.** The existing `adr-generator` agent stays as
  the **one-shot, explicitly-dispatched** generator. The new skill adds **in-session
  auto-detection** and **speckit archival**. Each references the other: the agent's
  `agent.md` gains a note pointing at the skill for in-session capture; the skill notes
  the agent for one-shot generation.
- **Rationale**: they occupy different activation surfaces — an agent is dispatched on
  request, a skill triggers passively mid-session. Consolidating onto one would drop a
  working capability; cross-linking gives users a coherent map without duplication of
  the underlying MADR machinery being a blocker. The task explicitly decided CROSS-LINK.
- **Alternatives considered**:
  - *Consolidate onto the skill, delete the agent* — rejected: removes a public catalog
    member (a `Removed`/major change) with no user benefit, and the agent's one-shot mode
    is still useful.
  - *Keep both, no cross-reference* — rejected: leaves two overlapping ADR tools with no
    guidance on which to use, the confusion FR-011 exists to prevent.
- **Consequence to manage**: the two tools historically use **different filenames** (see
  R3) and both write to `docs/adr/`; the numbering rule (R4) must span both.

## R3 — Filename convention (resolves FR-013)

- **Decision**: the **skill** writes **`docs/adr/NNNN-title.md`** (zero-padded 4-digit
  number + kebab-case title slug, e.g. `0007-queue-over-cron-poller.md`). This is the
  MADR-idiomatic name and matches the reference skill. **Greenfield**: the skill never
  renames or rewrites the agent's pre-existing `adr-NNNN-slug.md` files (FR-008, SC-007).
- **Rationale**: `NNNN-title.md` is the MADR convention and the natural sort key for an
  index. Changing the agent's historical files would violate the "leave existing ADRs
  untouched" guarantee, so the two conventions **coexist**: the skill reads both when
  scanning, and writes only its own `NNNN-title.md`.
- **Alternatives considered**:
  - *Adopt the agent's `adr-NNNN-slug.md` for the skill too* — rejected: diverges from
    MADR idiom and from the reference skill; no upside.
  - *Rename existing agent files to the new convention* — rejected: violates FR-008 /
    SC-007 (byte-unchanged pre-existing files) and Out-of-Scope ("Renaming or rewriting
    existing ADRs").
- **Collision handling**: numbering is derived from the **numeric prefix** regardless of
  the `adr-` prefix, so `0003-...md` and `adr-0003-...md` are recognized as the same
  number and never both minted (see R4).

## R4 — Numbering rule (supports FR-006, SC-003, edge cases)

- **Decision**: next number = **(highest numeric prefix found in `docs/adr/`) + 1**,
  scanning **both** `NNNN-*.md` and `adr-NNNN-*.md`. Numbers are **sequential and never
  reused**, even if a file was deleted (the max, not the count, drives it). Zero-padded
  to 4 digits. First ADR is `0001`.
- **Rationale**: max+1 is the only rule that survives deleted/renamed files and mixed
  conventions without reuse; counting files would recycle a deleted number and break
  supersession links.
- **Alternatives considered**: *count-based* (`count+1`) — rejected: reuses numbers after
  deletion. *Date/UUID names* — rejected: not sequential, breaks the index ordering and
  the spec's monotonic-numbering requirement.

## R5 — Structured MADR v4 record shape (supports FR-003, SC-001)

The canonical v4 "full" template, reduced to the elements the spec requires as
mandatory and ordered drivers-first. Full skeleton lives in
`contracts/adr-madr-v4-template.md`; the mandatory-for-this-skill elements are:

1. **Title** — `# NNNN. <short title of decision + solution>`
2. **Status + Date + Deciders** (front matter or a status block; `status:` carries
   `proposed | accepted | rejected | deprecated | superseded by NNNN`).
3. **Context and Problem Statement**.
4. **Decision Drivers** — *named first among the analytical sections* (bulleted forces).
5. **Considered Options** — the list of options.
6. **Decision Outcome** — "Chosen option: X, **because** <references a driver/force>";
   the driver linkage is mandatory (FR-003), plus Consequences (Good/Bad/Neutral).
7. **Pros and Cons of the Options** — **one block per option**, each with Good/Bad/Neutral
   bullets (this is the per-option pros/cons the spec requires).
8. **Links** — supersession + related-ADR links (MADR "More Information", surfaced as a
   `Links` section per the task's decided shape).

- **Rationale**: this is the v4 element set; keeping drivers before options/outcome and
  one Pros/Cons block per option is what makes SC-001 mechanically checkable.
- **Alternatives considered**: dropping the optional `Confirmation`/`More Information`
  subsections — acceptable (MADR marks them optional); `Links` is retained because
  supersession (edge case) depends on it.

## R6 — Speckit archival mapping (supports FR-010, SC-005)

- **Decision**: on a **merged** `specs/NNN-slug/`, the skill offers (consent-gated) to
  map spec fields → MADR fields: spec **Context/Problem** → *Context and Problem
  Statement*; spec success criteria / constraints acting as forces → *Decision Drivers*;
  spec **considered options / alternatives** → *Considered Options* + per-option *Pros and
  Cons*; spec **decision/outcome** → *Decision Outcome*. Any MADR-relevant field the spec
  is **silent** on is written as **explicitly absent** ("Not recorded in the spec"), never
  fabricated. Full table in `contracts/spec-to-adr-mapping.md`.
- **Rationale**: closes the #124 rationale-preservation gap by giving worktree-scoped
  spec rationale a durable home; honesty-about-absence prevents invented history (SC-005).
- **Merge signal**: relies on the #124 speckit lifecycle merge step or the user invoking
  the archival path at that point — **no bespoke forge polling** (spec Assumptions /
  Non-goals). This makes US3 depend on #124 for the trigger but independently testable by
  invoking the path against a merged spec.
- **Alternatives considered**: auto-archiving on merge without consent — rejected
  (violates FR-002/FR-010, Non-goal "Auto-writing ADRs without user confirmation").

## R7 — Skill authoring conventions (supports FR-014, Constitution Quality Gates)

- **Decision**: follow CONTRIBUTING "Skill content conventions": encode the
  **non-inferable delta** (the repo's numbering-across-two-conventions rule, the
  consent gate, the speckit-mapping table, the cross-link to the agent) — **not** a
  restatement of the public MADR spec; **pin** MADR v4 in `compatibility:`; include a
  **verify-canonical guard** pointing at the authoritative MADR source. Supporting
  material goes under `references/`; top level holds only `SKILL.md`.
- **Rationale**: matches the model skills (`skills/rust-explain/SKILL.md` for the guard
  pattern) and is exactly what `asctl repo-check` + `/skill:audit` enforce.
- **Alternatives considered**: inlining the whole MADR template into `SKILL.md` prose —
  rejected: "comprehensive" recital scores worst (Biggs/SkillsBench) and bloats the
  manifest; the template belongs in `references/`.

## Open items after Phase 0

**None.** FR-011, FR-012, FR-013 are resolved above and will be documented in the skill
body and recorded in the `changie` fragment (FR-011 requires the relationship decision
be recorded there). No `NEEDS CLARIFICATION` remains.
