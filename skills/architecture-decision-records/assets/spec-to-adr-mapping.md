# Spec → MADR field mapping (speckit archival)

When archiving a merged `specs/NNN-slug/` as an ADR, map fields as below. A field the
spec is silent on is written **"Not recorded in the spec"** — never fabricated.

| Speckit spec source | Structured MADR v4 field |
|---|---|
| Context / Problem Statement | Context and Problem Statement |
| Success Criteria, Constraints, Non-functional requirements | Decision Drivers |
| Considered options / Alternatives considered | Considered Options + one Pros/Cons block per option |
| Chosen approach / decision | Decision Outcome (name the driver it satisfies) |
| Consequences / tradeoffs noted in the spec | Consequences |
| Spec path / PR / issue link | Links |
| (spec is silent) | "Not recorded in the spec" |

Numbering follows the skill's rules: next = `max(highest filename prefix, highest index
entry) + 1`, zero-padded, never reused. Write to `docs/adr/NNNN-<kebab-title>.md` and
append one index row.
