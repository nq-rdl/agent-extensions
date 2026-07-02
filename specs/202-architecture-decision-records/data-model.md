# Phase 1 Data Model: Architecture Decision Records Skill

The "data" here is the set of Markdown documents the skill reads and writes, plus the
in-conversation trigger it recognizes. Each entity lists its fields, the rules that
govern it, and its lifecycle. Field names track Structured MADR v4 (see
`contracts/adr-madr-v4-template.md`).

## Entity: Architecture Decision Record (ADR)

A single Structured MADR v4 document on disk at `docs/adr/NNNN-title.md`.

| Field | Source | Required | Notes |
|---|---|---|---|
| `number` (NNNN) | derived | yes | 4-digit zero-padded; = `max(highest filename prefix, highest index entry) + 1` (R4). |
| `title` | decision moment | yes | Short, names problem + solution; slugged into filename. |
| `status` | user | yes | `proposed \| accepted \| rejected \| deprecated \| superseded by NNNN`. |
| `date` | today | yes | ISO `YYYY-MM-DD`. |
| `deciders` | session | optional | Who was involved; absent if unknown (not fabricated). |
| `context_and_problem_statement` | decision moment / spec | yes | 2–5 sentences. |
| `decision_drivers` | decision moment / spec | yes | **Listed first** among analytical sections; bulleted forces/concerns. |
| `considered_options` | decision moment / spec | yes | ≥ 1; typically ≥ 2. |
| `decision_outcome` | user | yes | "Chosen option: X, **because** …" — MUST reference a driver (FR-003). |
| `consequences` | decision moment | yes | Good / Bad / Neutral bullets. |
| `pros_and_cons` | decision moment | yes | **One block per considered option**, each Good/Bad/Neutral. |
| `links` | user / supersession | yes (section present) | Related + superseded-by/supersedes links (FR-003 supersession). |

**Validation rules**

- MADR-completeness (SC-001): `decision_drivers`, per-option `pros_and_cons`, a
  driver-linked `decision_outcome`, and a `links` section MUST all be present before a
  file is written.
- Consent (SC-002, FR-002): no ADR file is created/modified without a recorded
  affirmative user response in-session.
- Immutability of history (FR-008, SC-007): existing files under `docs/adr/` are never
  renamed or overwritten by capture; only new files are added (supersession writes a new
  file and edits only the superseded file's `status`/`links` — and only with consent).
- No fabrication (SC-005): a field with no source is written as explicitly absent
  ("Not recorded"), never invented.

**Lifecycle (status transitions)**

```
proposed ──▶ accepted ──▶ deprecated
                    └────▶ superseded by NNNN   (new ADR links back; old file preserved)
proposed ──▶ rejected
```

## Entity: ADR Index

The catalog at `docs/adr/README.md` — the source consulted for retrieval (US2) and
next-number derivation (R4). Format contract in `contracts/adr-index.md`.

| Field | Required | Notes |
|---|---|---|
| header | yes | `# Architecture Decision Records` + table header. |
| rows | one per ADR | `\| [NNNN](file.md) \| Title \| Status \| Date \|`. |

**Rules**: every written ADR appends/updates exactly one row (FR-005). Retrieval reads
the index first, then the matching file. The index is created only on the same consented
initialization that creates `docs/adr/` (FR-007).

## Entity: ADR Template

The skeleton used to create a new ADR consistently. Canonical copy authored at
`skills/architecture-decision-records/assets/madr-v4-template.md`; the skill offers
to drop a `docs/adr/template.md` copy at initialization (consent-gated). Mirrors the
Structured MADR v4 element set (R5).

## Entity: Speckit Spec (archival source)

`specs/NNN-slug/spec.md` (+ `plan.md`/`research.md` siblings) for a spec merged to
`main`. Read-only input to archival (US3). Field mapping → MADR in
`contracts/spec-to-adr-mapping.md`.

| Spec field | → MADR field |
|---|---|
| Context / Problem / Input | Context and Problem Statement |
| Success Criteria / Constraints (as forces) | Decision Drivers |
| Considered options / Alternatives / research.md options | Considered Options + Pros and Cons |
| Decision / chosen outcome | Decision Outcome |
| (silent) | field marked "Not recorded in the spec" |

**Rule**: no spec field is dropped and none is fabricated (SC-005).

## Entity: Decision Moment (transient trigger)

An in-session event that prompts the skill to offer capture (FR-001). Not persisted.

| Kind | Examples |
|---|---|
| Explicit cue | "let's record this decision", "ADR this", "why did we choose X?" |
| Implicit cue | user weighs significant alternatives (framework/library/db/pattern/API/auth/infra) and reaches a conclusion |
| Archival cue | a speckit spec is merged to `main` (#124 step) or the archival path is invoked |

**Rule**: detection only ever produces an **offer**; it never writes (FR-002). A
retrieval cue with no matching ADR yields an honest "not recorded" + an offer (FR-009).
