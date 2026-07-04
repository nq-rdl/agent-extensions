---
status: "accepted"
date: 2026-07-04
deciders: [Josh Keogh]
---

# 0001. Own SpecKit-side pipeline mechanics as RDL extensions

## Context and Problem Statement

Epic #207 adopts SpecKit for planning and Superpowers for execution, handing off at the
task-list boundary, with worktree-per-spec isolation and ephemeral specs archived to
durable ADRs at trunk merge. Where should the speckit-side pieces of that pipeline —
routing-baseline install, worktree provision/merge, ADR finalization, brainstorm→spec
handoff — live, and who owns them?

An earlier revision of this ADR (2026-07-02, never merged to main) answered with a
layered recommendation: hand-rolled routing clause + opt-in adoption of the upstream
`superpowers-bridge` (`superb`) extension. The 2026-07-03 re-architecture of the epic
revisits that; this revision replaces it in place (no supersession chain, since no prior
revision ever landed on main).

## Decision Drivers

- **Agent-agnostic mechanics** — provisioning, merge/strip, and ADR finalization must be
  runnable by any agent or a human, not encoded only in Claude-side skill prose and bash.
- **Thin marketplace** — agent-extensions ships discovery + delegation skills; it must not
  become the owner of pipeline mechanics (wrong layer: its `docs/playbooks/` can describe,
  but cannot install, anything).
- **Scope-whittling** — adopt no surface area the pipeline doesn't need; `superb`'s gates
  (plan-gate, TDD controller, verify) duplicate discipline Superpowers already enforces
  Claude-side.
- **Pipeline coverage** — the mechanics RDL actually needs (speckit-`NNN` worktrees, spec
  seeding, ADR finalize + ephemeral strip, brainstorm handoff) exist in no upstream
  extension.
- **Dependency risk** — prefer the first-party `github/spec-kit` extension API over a
  single-maintainer third-party bridge; the original drivers (constitution drift,
  session continuity) must still hold.

## Considered Options

1. **RDL-owned extension set** in `nq-rdl/spec-kit-extensions`, delivered via one RDL catalog
2. **Layered `superb` adoption** — routing baseline + opt-in `superpowers-bridge` (the 2026-07-02 revision)
3. **cc-spex bundled extensions**
4. **Convention only** — constitution clause + CLAUDE.md routing block, no extensions
5. **Keep mechanics Claude-side** — the `speckit-lifecycle` skill's embedded scripts as the permanent home

## Decision Outcome

Chosen option: **1 — RDL-owned extension set**, because it is the only option satisfying
both *agent-agnostic mechanics* and *pipeline coverage* while keeping the marketplace
thin. Option 4 is retained inside it as the zero-dependency floor: the routing payload
must stand alone as copy-paste text for repos that install nothing, and is the interim
delivery until the extension ships.

Planned set (working names — ids settled per-extension at design time), built
**extensions-first** in `nq-rdl/spec-kit-extensions`, with the epic rewired after:

- **rdl-routing** — installs the routing baseline: the "SpecKit plans, Superpowers
  executes" clause, the CLAUDE.md routing block, and the ephemeral-specs/durable-ADRs
  principle
- **rdl-adr** — `speckit.adr.finalize`: archive spec decisions to `docs/adr/NNNN-*.md`,
  own the ephemeral strip
- **rdl-worktree** — provision/merge commands wrapping #124's script semantics (`NNN`
  derivation, spec seeding, topology-aware merge); owns branch creation
- **brainstorm-handoff** — versioned artifact contract seeding `/speckit.specify` from a
  Superpowers brainstorm design doc

Preceded by repo hygiene there (catalog.json + validation CI) and an API-fit spike
against a real spec-kit install. The breakdown is carried in PR #217; per team practice,
each work item's issue is posted just-in-time with its closing PR.

`superb` is **evaluated, not adopted**. `cc-spex` remains not adopted (#203, unchanged).

### Consequences

- Good, because pipeline mechanics become installable per target repo
  (`specify extension catalog add … --install-allowed`, then `specify extension add`) and
  runnable by any agent or human — copy-paste playbooks stop being the delivery mechanism.
- Good, because scope shrinks: no third-party bridge dependency, no Spec Kit `>=0.12.0`
  floor imposed by `superb`, no duplicate TDD gating layered over Superpowers.
- Good, because the semantics stay single-owner: worktree provision/merge and the
  ephemeral strip get one tested home instead of per-skill copies.
- Bad, because RDL becomes a producer: four extensions, a catalog, and validation CI to
  own indefinitely.
- Bad, because the spec-kit extension API is 0.x and moving (upstream already relocated
  branch creation from core into the first-party `git` extension) — version pinning and
  the API-fit spike are load-bearing.
- Bad, because until the extensions ship the baseline is convention-only, and ADR
  finalization on GitHub-PR merges stays a run-it step (the observed upstream hook events
  end at `after_implement`; there is no merge-time hook).

## Pros and Cons of the Options

### 1. RDL-owned extension set

- Good, because it covers exactly RDL's pipeline — `NNN` worktrees, finalize/strip,
  handoff — which no upstream extension provides.
- Good, because the only upstream dependency is the first-party extension API, and
  delivery uses the native catalog mechanism.
- Bad, because of ongoing ownership cost (build, maintain, CI, releases).

### 2. Layered `superb` adoption (the prior revision)

- Good, because mandatory evidence-first gates make routing mechanical at zero build cost.
- Bad, because it duplicates Superpowers' Claude-side discipline (double TDD gating)
  while providing none of RDL's pipeline mechanics.
- Bad, because it adds a single-maintainer third-party dependency, a Spec Kit `>=0.12.0`
  floor, and 10 commands / 6 hooks of adopted surface area — against the scope-whittling
  driver. If convention proves insufficient, RDL-owned gates can be added to our own
  extensions later.

### 3. cc-spex bundled extensions

- Bad, because #203 evaluated it CONDITIONAL — not adopted; its `spex-worktrees`
  registers a mandatory `after_specify` hook that conflicts with our worktree ownership.

### 4. Convention only

- Good, because zero-dependency; it survives as the floor and the interim delivery.
- Bad, because nothing is mechanical and none of the pipeline mechanics exist at all.

### 5. Keep mechanics Claude-side

- Good, because already built and tested (#124's scripts, 13 bats cases).
- Bad, because invisible to non-Claude agents and to humans; it makes the marketplace
  repo a pipeline owner (wrong layer). Retained only as the interim until rdl-worktree
  ships.

## Links

- Source spec / issue: #204 (epic #207). Prior revision: 2026-07-02 layered
  recommendation — this file's git history on PR #214.
- Routing payload (interim copy-paste delivery): `docs/playbooks/speckit-constitution-routing.md` (#205 / PR #216)
- Evaluations: #203 cc-spex (`docs/evaluations/203-cc-spex-evaluation.md`); #206
  Worktrunk (`docs/evaluations/206-worktrunk-consolidation.md`); `superb` —
  `RbBtSn0w/spec-kit-extensions` (`superpowers-bridge`, v1.8.0 at evaluation)
- Consumers: #124 `speckit-lifecycle` (offers rdl-routing at repo setup; delegates
  provision/merge to rdl-worktree when it ships); #202 `architecture-decision-records`
  (delegates finalize mechanics to rdl-adr when it ships)
- Target repo: `nq-rdl/spec-kit-extensions` (extension host + RDL catalog); upstream
  API: `github/spec-kit` → `extensions/EXTENSION-API-REFERENCE.md`
