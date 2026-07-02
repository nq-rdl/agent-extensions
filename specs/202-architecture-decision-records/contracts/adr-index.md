# Contract: ADR index (`docs/adr/README.md`)

The catalog the skill maintains and reads back. Created only on the consented
initialization that creates `docs/adr/` (FR-007); updated on every write (FR-005);
consulted for retrieval (FR-009) and next-number derivation (R4).

## Format

```markdown
# Architecture Decision Records

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [0001](0001-use-queue-over-cron.md) | Use a queue over a cron poller | accepted | 2026-07-02 |
| [0002](0002-postgres-over-mongo.md) | PostgreSQL over MongoDB | accepted | 2026-07-03 |
```

## Contract obligations

- **One row per ADR (FR-005)**: writing an ADR appends exactly one row; updating status
  (e.g. supersession) updates that ADR's existing row in place.
- **Mixed conventions (R3/R4)**: the index links each ADR by its real filename, so a
  legacy `adr-NNNN-slug.md` row and a new `NNNN-title.md` row can coexist. Next-number
  derivation scans the numeric prefix of every entry/file (`max + 1`).
- **Retrieval (FR-009, SC-004)**: "why did we choose X?" is answered by matching against
  index titles (and, failing that, the indexed ADRs' Decision Drivers), reading the matched
  file, and quoting its Decision Drivers + Decision Outcome. No index match → the skill
  states "not recorded" and offers to capture — it MUST NOT fabricate a rationale.
- **Missing store**: if `docs/adr/README.md` does not exist, retrieval reports none
  recorded and offers to initialize (consent-gated); it never creates it silently.
