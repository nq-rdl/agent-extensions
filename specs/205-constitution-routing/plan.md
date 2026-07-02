# Implementation Plan: #205 constitution/CLAUDE.md routing templates

**Type**: documentation / templates (no code). TDD (constitution Principle III) is N/A —
a Markdown playbook has no executable surface to red-green-refactor; validation here is the
repo's CI-parity gates (changie present, no generated-artifact drift), not unit tests.

## Approach

Deliver copy-paste templates in a `docs/` playbook: (1) constitution clause, (2) CLAUDE.md
routing block, (3) anti-patterns. Keep consistent with the delivered epic constitution
(`da38e3d`); stay aligned with — but do not block on — #204's forthcoming recommendation
(#204 is open and is not a completion gate for #205, per spec.md Clarifications).

## Deliverable

- `docs/playbooks/speckit-constitution-routing.md`. No `skills/`/`registry/` changes.

## References

- Epic `.specify/memory/constitution.md`; #204; #203; #206; #124.
