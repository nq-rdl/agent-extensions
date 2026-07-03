---
title: Enforce Superpowers execution discipline in SpecKit repos via a layered extension recommendation
status: Accepted
date: 2026-07-02
authors:
  - Josh Keogh
supersedes: none
superseded_by: none
---

# ADR-0001: Enforce Superpowers execution discipline in SpecKit repos via a layered extension recommendation

## Status

Accepted — distilled from feature `204-speckit-extension-recommendation` at its merge into
epic #207 (per the branch's clarification: capture preconditions in `plan.md` on-branch;
defer the durable ADR to the epic merge).

## Context

Epic #207 adopts **SpecKit** for planning and **Superpowers** for execution, with a hard
handoff at the task-list boundary (see the project constitution). Target speckit repos need
a way to enforce the Superpowers execution discipline —
`worktree → TDD → subagent → review → finish` — rather than relying on convention alone.

Two friction points motivated this decision:

- **CON-001 — `constitution.md` drift during execution.** The routing clause (#205) fixes
  ownership (SpecKit owns the "what", Superpowers the "how") but is *convention*; nothing
  mechanically stops execution from silently diverging.
- **CON-002 — session continuity across pauses.** Vocabulary and definition-of-done must
  survive a `/clear` or a resumed session, or enforcement evaporates between sessions.

Constraints shaping the decision:

- **CON-003** — SpecKit's own extension layer (`specify extension add`, scoped per target
  repo) is a *different* layer from this repo's Claude Code plugin set (#203); the
  recommendation targets the SpecKit-native layer.
- **CON-004** — must stay consistent with #203 (cc-spex evaluated CONDITIONAL / not adopted)
  and #205 (the routing baseline).
- **CON-005** — the deliverable is a `docs/` playbook a **target** repo consumes, not a
  change to this marketplace's `skills/`/`registry/`.

## Decision

Adopt a **layered** recommendation:

1. **Baseline (every repo, zero-dependency).** Apply the #205 constitution clause + CLAUDE.md
   routing block. This is the floor; it needs no install and re-establishes vocabulary and
   definition-of-done every session (addressing CON-002 by convention).
2. **Opt-in enforcement (recommended for teams wanting hard gates).** Install
   `superpowers-bridge` (catalog id `superb`, from `RbBtSn0w/spec-kit-extensions`). Its
   evidence-first, **mandatory** gates map 1:1 to the discipline: `plan-gate` (`after_plan`),
   a TDD/RED-GREEN-REFACTOR `controller` (`before_implement`), and `verify` requiring fresh
   test evidence (`after_implement`/`after_converge`), plus `review`/`critique` and `finish`
   gates. This makes CON-001 *mechanical* — execution cannot silently diverge — and the gates
   fire regardless of session state (CON-002).
3. **Do not adopt `cc-spex` for this purpose now** — consistent with #203 (CONDITIONAL / not yet).

**Operational preconditions** for the `superb` layer (verified against `catalog.json` +
`superpowers-bridge/extension.yml`):

- **PRE-001** — `superb` v1.8.0 requires **Spec Kit `>=0.12.0`**; `specify extension add superb`
  fails on older CLIs. Target repos must check `specify --version` and upgrade first.
- **PRE-002** — the catalog must be registered with `--install-allowed`, or `extension add` is
  blocked. Orgs that disallow external catalogs use the release-pin fallback
  (`specify extension add superpowers-bridge --from <release-zip>`).
- **PRE-003** — the baseline (layer 1) must stand alone: it is the zero-dependency floor for
  repos that cannot or will not install `superb`; the recommendation degrades gracefully to
  convention-only enforcement.

## Consequences

Positive:

- **POS-001** — enforcement becomes mechanical: `/speckit.implement` is gated on
  RED-GREEN-REFACTOR + verify evidence, so execution cannot silently diverge from the constitution.
- **POS-002** — gates are session-state-independent; a resumed session (post-pause or `/clear`)
  hits the same evidence checks.
- **POS-003** — graceful degradation: the baseline clause works with zero install, so repos that
  cannot add `superb` still get a defined floor.
- **POS-004** — reuses a maintained upstream extension covering the full
  worktree→TDD→subagent→review→finish chain; no new bridge to build or own.

Negative:

- **NEG-001** — adds an external dependency (`superb` v1.8.0) and a Spec Kit `>=0.12.0` floor;
  external-catalog-disallowed orgs must use the release-pin fallback (PRE-002).
- **NEG-002** — enforcement is opt-in, so baseline-only repos still rely on convention, not
  mechanical gates.
- **NEG-003** — the enforcement tier is coupled to the stability of upstream
  `RbBtSn0w/spec-kit-extensions`.

## Alternatives Considered

- **ALT-001 — `cc-spex` bundled extensions.** A broader plugin suite (quality gates, worktrees,
  teams, deep-review) registered at SpecKit hooks. Rejected *for now*: #203 recommends not
  adopting cc-spex yet (CONDITIONAL). Revisit if #203's conditions are met.
- **ALT-002 — hand-rolled constitution clause only (the #205 baseline).** Zero-dependency, but
  convention-only and not mechanically enforced. Retained as layer 1, but insufficient alone for
  teams wanting hard gates — hence the layered approach rather than baseline-only.
- **ALT-003 — build a new SpecKit bridge extension from scratch.** Rejected as a non-goal:
  `superb` already covers the whole discipline, so a bespoke bridge would duplicate a maintained
  upstream at ongoing cost.

## Implementation Notes

- Target-repo setup steps live in
  [`docs/playbooks/speckit-superpowers-extension.md`](../playbooks/speckit-superpowers-extension.md)
  (run inside the team's speckit repo, not this one).
- `speckit-lifecycle` (#124) should reference the playbook at repo-setup time and point at #205
  for the constitution/CLAUDE.md templates.
- **Success metric** — SC-1 met when the playbook exists with the comparison, a clear
  recommendation, and target-repo setup steps; the three mandatory gates observably fire on
  `/speckit.plan`, `/speckit.implement`, and completion.

## References

- [`docs/playbooks/speckit-superpowers-extension.md`](../playbooks/speckit-superpowers-extension.md)
- `specs/204-speckit-extension-recommendation/spec.md`, `.../plan.md`
- #203 — cc-spex evaluation (conditional, not adopted)
- #205 — constitution / CLAUDE.md routing templates
- #124 — `speckit-lifecycle`
- #207 — epic (SpecKit + Superpowers)
- `RbBtSn0w/spec-kit-extensions` → `superpowers-bridge` (`superb`)
