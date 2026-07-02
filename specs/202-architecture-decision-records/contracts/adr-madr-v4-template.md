# Contract: Structured MADR v4 record

The exact skeleton the skill emits (canonical copy shipped at
`skills/architecture-decision-records/assets/madr-v4-template.md`). Drivers appear
**before** options and outcome; **each** option gets its own Pros/Cons block; the
outcome **references a driver**; a `Links` section supports supersession.

```markdown
---
status: "proposed"            # proposed | accepted | rejected | deprecated | superseded by NNNN
date: YYYY-MM-DD
deciders: "<names, or omit if unknown — do not fabricate>"
---

# NNNN. <short title: problem + chosen solution>

## Context and Problem Statement

<2–5 sentences on the situation, constraints, and forces. May be phrased as a question.>

## Decision Drivers

* <driver 1 — a force / facing concern>
* <driver 2>
* …

## Considered Options

* <option 1>
* <option 2>
* …

## Decision Outcome

Chosen option: "<option>", because <justification that names a Decision Driver above>.

### Consequences

* Good, because <positive consequence>
* Bad, because <negative consequence / trade-off>
* Neutral, because <neither good nor bad, if any>

## Pros and Cons of the Options

### <option 1>

* Good, because <argument>
* Neutral, because <argument>
* Bad, because <argument>

### <option 2>

* Good, because <argument>
* Bad, because <argument>

<!-- one block per Considered Option -->

## Links

* Supersedes / Superseded by: [NNNN. <title>](NNNN-title.md)   <!-- when applicable -->
* Related: <ADR / issue / doc links>
```

## Contract obligations (checked by quickstart AC1–AC2, SC-001)

- **Mandatory sections present**: Decision Drivers, Considered Options, Decision
  Outcome, one Pros/Cons block per option, Links. Optional MADR elements
  (`Confirmation`, `More Information`) MAY be omitted.
- **Ordering**: Decision Drivers precede Considered Options and Decision Outcome.
- **Driver linkage**: the Decision Outcome sentence references at least one named driver.
- **Filename**: `docs/adr/NNNN-<kebab-title>.md`, `NNNN` zero-padded (R3).
- **Supersession**: a superseding ADR links the old one and sets the old file's `status:`
  to `superseded by NNNN`; the old file is otherwise preserved (FR-003, edge case).
