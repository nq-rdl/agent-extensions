# Evaluation: standardize worktree management on Worktrunk (#206)

Part of epic #207. Decides whether `speckit-lifecycle` (#124) should delegate its
worktree provisioning/merge to the Worktrunk (`wt`) CLI, or keep its bespoke scripts.

## Capability matrix — `wt` vs `speckit-lifecycle`'s script requirements

| Requirement (#124) | Worktrunk `wt` | Verdict |
|---|---|---|
| **NNN derivation** (max across `git branch -a`, `specs/`, `.claude/worktrees/`, +1, zero-padded) | ✗ `wt` names worktrees by branch/codename; it has no concept of speckit's sequential `NNN` anchored to `specs/` | **gap** |
| **Conflict guard** on the computed `NNN` slot/branch | ~ `wt` guards path/branch collisions generally, but not speckit-`NNN` semantics | partial |
| **`--base` parentage** (cut a spec off an integration/epic branch) | ✓ `wt switch --create <b> --base <ref>` (used throughout this very epic) | **match** |
| **Merge-target topology** (`git merge-base` → trunk *or* the integration branch it was cut from) | ~ `wt merge [TARGET]` accepts an explicit target but has **no automatic topology detection**; it does not preserve `specs/NNN-slug/` or the "NNN never reused" invariant | partial |
| **Merge strategy** (#124's `merge-spec.sh` uses `--no-ff` merge commits to preserve branch topology) | ~ `wt merge` **defaults to squash + rebase + fast-forward** (linearizes history) — semantically opposite; `--no-ff` exists as a flag but is not the default | partial |
| **Post-merge cleanup** (remove worktree slot *before* `git branch -d`) | ✓ `wt merge`/`wt remove` handle worktree teardown cleanly | **match** |
| **`create-new-feature.sh` seeding** (speckit spec scaffold) | ✗ not `wt`'s concern | **gap** |
| **Worktree location** | ✓ configurable via `worktree-path` template — *see follow-up* | match (with caveat) |
| **No hard dependency** (skill must work in any repo, `wt` may be absent) | ✗ delegating would add a hard `wt` install requirement | **gap** |

## Overlap with `cc-spex`'s `spex-worktrees`

The #203 evaluation (`docs/evaluations/203-cc-spex-evaluation.md`, PR #213 — both land on the
epic branch before `main`) recommends **CONDITIONAL — do not adopt `cc-spex` now**, so
`spex-worktrees` is not enabled today. Assessing it against this issue, #203 flags worktrees as
the **sharpest conflict**: `spex-worktrees` registers a **mandatory `after_specify` hook** that
auto-creates a sibling worktree on every `/speckit.specify` — a second, competing worktree
mechanism at the SpecKit → Superpowers boundary. It provides only generic git-worktree isolation
(overlapping `wt`'s core function and Superpowers' `using-git-worktrees`) and does **not** provide
the speckit-`NNN`/`specs/` semantics `provision-worktree.sh`/`merge-spec.sh` exist for.

So `spex-worktrees` is not a consolidation target — it is an active conflict to avoid, and #203's
adoption conditions already prescribe keeping it **disabled** wherever the team runs its own
worktree tooling (the bespoke scripts and/or Worktrunk). This decision (keep bespoke, `wt`
complementary) is consistent with that either way: no `cc-spex` worktree mechanism is layered in.

## Decision: **keep the bespoke scripts** (do not consolidate onto `wt`)

Rationale:
1. `wt` covers the *generic* worktree mechanics (`--base`, teardown, location) but **not**
   the speckit-specific semantics that are the whole point of `provision-worktree.sh`/
   `merge-spec.sh`: `NNN` derivation anchored to `specs/`, never-reused numbering,
   `create-new-feature.sh` seeding, and `specs/NNN-slug/` preservation on merge.
2. `speckit-lifecycle` must stay **repo-agnostic and dependency-light** (its acceptance
   criteria forbid hardcoded tooling); a hard `wt` dependency would break repos without it.
   The scripts already *probe and fall back to bare git* — the correct portability posture.
3. `wt` is **complementary, not a replacement**: it is the ergonomic interactive worktree
   CLI for humans; the bundled scripts are the deterministic, testable automation the skill
   drives. `speckit-lifecycle`'s guidance should *recommend* `wt` for interactive use while
   keeping the scripts as the automation path.

**Consequence for #124:** its acceptance criteria need **no** Worktrunk dependency — they
stand as-is. No changes to #124 required.

## Follow-up (FR-5): `wt` worktree-location remap to `.claude/worktrees/`

Surfaced during this epic's own execution (Wave 0). Findings:
- `wt` **can** be pointed at `.claude/worktrees/` via the user-config `worktree-path`
  template (e.g. `worktree-path = "{{ repo_path }}/.claude/worktrees/{{ branch | sanitize }}"`),
  which would make `wt` worktrees match speckit/dst-autoloop convention **and** the harness
  `EnterWorktree` tool (which only accepts worktrees under `.claude/worktrees/`).
- **Limitation:** `worktree-path` is documented as **user-global** (user config; affects
  every repo — per Worktrunk's FAQ), and `.claude/worktrees/` is not gitignored by default
  here. (`wt` does support a per-repo project config at `.config/wt.toml`, but that is
  documented for hooks; whether it honors the `worktree-path` template at project scope is
  unconfirmed.)
- **Because** automation uses read-execute of the speckit skill files (not `EnterWorktree`),
  aligning the location is **optional** — a convenience for interactive sessions, not a
  requirement. Recommendation: leave `wt` at its default sibling layout; document the remap
  as an opt-in for teams that want `EnterWorktree` compatibility.

## Outcome

Keep bespoke scripts; position `wt` as the recommended interactive complement; no #124
changes. `cc-spex` is conditional-no per #203 (PR #213); if it is later adopted, keep
`spex-worktrees` **disabled** per that evaluation — so this decision stands either way.

## Addendum (2026-07-04): the bespoke semantics promote to the rdl-worktree extension

The epic's re-architecture (ADR-0001, #204) moves pipeline mechanics speckit-side: the
bespoke scripts' semantics (`NNN` derivation, spec seeding, topology-aware merge, strip
delegation) become the planned **rdl-worktree** extension in
`nq-rdl/spec-kit-extensions`, runnable by any agent or a human. This changes the *home*,
not the decision:

- `wt` remains the recommended **interactive complement**. The extension wraps our
  bespoke semantics, **not** `wt` — and its final id must avoid that product name.
- The scripts (13 bats cases @ `2787fc6`, PR #211) are the acceptance baseline for the
  extension; `speckit-lifecycle` prefers the extension commands when installed and keeps
  the scripts as its fallback until then.
- The FR-5 follow-up above (`wt` worktree-location remap) is unaffected — still an
  opt-in convenience for interactive sessions.
