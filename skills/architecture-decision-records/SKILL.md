---
name: architecture-decision-records
description: >-
  Capture architectural decisions as Structured MADR records, in-session and on
  demand. Use when the user says "record this decision", "ADR this", "why did we
  choose X?", when they weigh significant alternatives (framework, library, database,
  pattern, API, auth, infra) and reach a conclusion, or when a merged speckit spec
  should be archived as a durable decision record. Detects the moment and always
  OFFERS — never writes a file without explicit consent. Also answers "why did we
  choose X?" from the existing ADR index.
license: MIT
compatibility: Structured MADR (adr/madr) v4
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
  spec_url: https://adr.github.io/madr/
---

# Architecture Decision Records (Structured MADR)

Capture the *why* behind architectural choices as [Structured MADR](https://adr.github.io/madr/)
v4 records, so rationale survives the session and the worktree. This skill detects
decision moments and **offers** to record them; it never writes without consent.

**Verify canonical:** the MADR format is defined upstream at
<https://adr.github.io/madr/> (repo <https://github.com/adr/madr>). Pin **v4**. This
skill encodes only the repo-specific *delta* (when to offer, consent gate, numbering,
store location, speckit archival) — not a restatement of the public MADR spec. If the
upstream template has moved past v4, prefer the upstream field set and flag the drift.

## Non-negotiable: consent gate

**Never create or modify any file without explicit affirmative consent.** On every
trigger, respond with an OFFER ("Want me to record this as an ADR?") and act only after
the user says yes. This includes initializing `docs/adr/`, writing a new ADR, and
editing a superseded ADR's status.

## Relationship to the `adr-generator` agent

The `agents/adr-generator/` agent stays for **one-shot, explicitly-dispatched**
generation. This skill is the **in-session** surface: it auto-detects decision moments,
answers retrieval questions, and handles speckit archival. They are cross-linked; both
write to `docs/adr/`. (Decision recorded in the changelog: cross-link, keep both.)

## When to offer (decision-moment detection)

- **Explicit cue** — "let's record this decision", "ADR this", "why did we choose X?".
- **Implicit cue** — the user weighs significant alternatives (framework / library /
  database / pattern / API / auth / infrastructure) and reaches a conclusion. Offer to
  capture it; do not assume.
- **Archival cue** — a `specs/NNN-slug/` spec has merged (the speckit lifecycle merge
  step) or the user asks to archive one. Offer to archive it as an ADR.

## Numbering & store

- Store: `docs/adr/`. Index: `docs/adr/README.md`.
- Filename: `docs/adr/NNNN-<kebab-title>.md` (zero-padded 4-digit). First ADR = `0001`.
- Next number = **`max(highest numeric filename prefix, highest number in the index) + 1`**,
  scanning filenames (**both** `NNNN-*.md` and legacy `adr-NNNN-*.md`) **and**
  `docs/adr/README.md`. Numbers are sequential and **never reused**: a manual delete
  leaves the index row behind, so even deleting the highest-numbered ADR does not free its
  number. Never rename or overwrite a pre-existing file.
- Initialize `docs/adr/` (seed `README.md` from `assets/index-template.md` and copy
  `assets/madr-v4-template.md` → `docs/adr/template.md`) **only on explicit consent**,
  on the first capture if absent.

## Capture flow (on consent)

1. Fill `assets/madr-v4-template.md`: **Decision Drivers first**, one Pros/Cons block
   **per option**, a Decision Outcome that **names a driver**, and a `Links` section.
2. Assign the next number (above); write `docs/adr/NNNN-<kebab-title>.md`.
3. If `docs/adr/` is absent, initialize it (index + `template.md`) — consent-gated.
4. Append exactly **one** row to `docs/adr/README.md`, linking the ADR by its real
   filename so retrieval can resolve it: `| [NNNN](NNNN-<kebab-title>.md) | Title | Status | Date |`.

### Supersession

A superseding ADR is a **new** file that links the old one, sets the old file's
`status:` to `superseded by NNNN`, and updates the old index row. Otherwise the old
file is preserved byte-for-byte. All consent-gated.

## Retrieval — "why did we choose X?"

Read `docs/adr/README.md`; match the question first against index **titles**, and if none
matches, against the **Decision Drivers** of the indexed ADRs. Open the matched file and
answer from its **Decision Drivers** + **Decision Outcome**. On no match (or no store), say
it is **not recorded** and offer to capture it — **never fabricate a rationale**.

## Speckit archival (on a merged spec)

Trigger: a `specs/NNN-slug/` merged via the speckit lifecycle merge step, or an
explicit user request (no forge polling). OFFER to archive; on consent, map fields per
`assets/spec-to-adr-mapping.md`:

| Spec source | MADR field |
|---|---|
| Context / Problem | Context and Problem Statement |
| Success Criteria / Constraints | Decision Drivers |
| Considered options / Alternatives | Considered Options + per-option Pros/Cons |
| Chosen decision | Decision Outcome |
| Spec link | Links |

A field the spec is silent on is written **"Not recorded in the spec"** — never
fabricated. Assign the next number, write `docs/adr/NNNN-<title>.md`, update the index.
