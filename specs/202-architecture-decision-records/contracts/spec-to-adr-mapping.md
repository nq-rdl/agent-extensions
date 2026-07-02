# Contract: Speckit spec → MADR archival mapping

Governs User Story 3 (FR-010, SC-005). On a **merged** `specs/NNN-slug/`, the skill
offers (consent-gated) to archive it as an ADR by mapping spec fields to MADR fields.
Canonical copy shipped at
`skills/architecture-decision-records/references/spec-to-adr-mapping.md`.

## Field mapping

| Source (speckit spec / plan / research) | → MADR v4 field | Rule |
|---|---|---|
| `spec.md` **Input** / **Context** / problem framing | Context and Problem Statement | Condense to 2–5 sentences. |
| `spec.md` **Success Criteria** + **Constraints** (as forces) | Decision Drivers | List the forces that shaped the choice. |
| `research.md` / `plan.md` **considered options / Alternatives** | Considered Options + one Pros/Cons block each | Preserve every option; carry its rationale into Good/Bad bullets. |
| The chosen decision / **Structure Decision** / accepted outcome | Decision Outcome | State the choice + link it to a driver. |
| **Anything the spec is silent on** | the corresponding MADR field, marked absent | Write `Not recorded in the spec` — never invent (SC-005). |
| `spec.md` link / branch | Links | Reference the source `specs/NNN-slug/`. |

## Contract obligations

- **Offer + consent (FR-010)**: the archival path OFFERS and writes nothing without an
  explicit affirmative response.
- **No field dropped, none fabricated (SC-005)**: every listed source field is
  represented; a silent field is explicitly marked absent, not filled from guesswork.
- **Numbering + filename**: the archived ADR gets the next number (R4) and the
  `NNNN-title.md` filename (R3), and updates the index (FR-005).
- **Trigger source**: "merged to `main`" comes from the #124 speckit lifecycle merge
  step or an explicit user invocation — no bespoke forge polling (spec Assumptions).
- **Purpose**: preserves rationale that would otherwise vanish at worktree teardown,
  closing the #124 gap — this is what distinguishes the skill from the one-shot agent.
