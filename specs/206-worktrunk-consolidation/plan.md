# Implementation Plan: #206 Worktrunk consolidation (decision)

**Type**: evaluation / decision doc (no code, no skill changes).

## Approach

1. Build a capability matrix of `wt` against each requirement of #124's
   `provision-worktree.sh`/`merge-spec.sh` (NNN derivation, conflict guard, `--base`,
   merge topology, cleanup, location, dependency posture).
2. Fold in #203's outcome for `spex-worktrees` overlap.
3. Record a decision with rationale; confirm the #124 impact.
4. Capture the `wt`-location remap follow-up surfaced in Wave 0.

## Structure / deliverable

- `docs/evaluations/206-worktrunk-consolidation.md` — matrix + decision + follow-up.
- No changes to `skills/`, `registry/`, or `#124`'s acceptance criteria (decision = keep bespoke).

## Research inputs

- Worktrunk `reference/config.md` (worktree-path template, `--base`, `wt merge`).
- #124 `provision-worktree.sh`/`merge-spec.sh` semantics.
- #203 cc-spex evaluation (conditional — not adopted).
