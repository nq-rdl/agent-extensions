# Evaluation: standardize worktree management on Worktrunk (#206)

Part of epic #207. Decides whether `speckit-lifecycle` (#124) should delegate its
worktree provisioning/merge to the Worktrunk (`wt`) CLI, or keep its bespoke scripts.

## Capability matrix — `wt` vs `speckit-lifecycle`'s script requirements

| Requirement (#124) | Worktrunk `wt` | Verdict |
|---|---|---|
| **NNN derivation** (max across `git branch -a`, `specs/`, `.claude/worktrees/`, +1, zero-padded) | ✗ `wt` names worktrees by branch/codename; it has no concept of speckit's sequential `NNN` anchored to `specs/` | **gap** |
| **Conflict guard** on the computed `NNN` slot/branch | ~ `wt` guards path/branch collisions generally, but not speckit-`NNN` semantics | partial |
| **`--base` parentage** (cut a spec off an integration/epic branch) | ✓ `wt switch --create <b> --base <ref>` (used throughout this very epic) | **match** |
| **Merge-target topology** (`git merge-base` → trunk *or* the integration branch it was cut from) | ~ `wt merge` targets the default/tracked branch; it does not preserve `specs/NNN-slug/` or the "NNN never reused" invariant | partial |
| **Post-merge cleanup** (remove worktree slot *before* `git branch -d`) | ✓ `wt merge`/`wt remove` handle worktree teardown cleanly | **match** |
| **`create-new-feature.sh` seeding** (speckit spec scaffold) | ✗ not `wt`'s concern | **gap** |
| **Worktree location** | ✓ configurable via `worktree-path` template — *see follow-up* | match (with caveat) |
| **No hard dependency** (skill must work in any repo, `wt` may be absent) | ✗ delegating would add a hard `wt` install requirement | **gap** |

## Overlap with `cc-spex`'s `spex-worktrees`

Per #203 the recommendation is **CONDITIONAL — do not adopt `cc-spex` now**, so
`spex-worktrees` is not in play. It provides general git-worktree isolation (overlapping
`wt`'s core function and Superpowers' `using-git-worktrees`); it does **not** provide the
speckit-`NNN`/`specs/` semantics either. No consolidation target there today.

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
- **Limitation:** `worktree-path` is **user-global** (affects every repo), and
  `.claude/worktrees/` is not gitignored by default here.
- **Because** automation uses read-execute of the speckit skill files (not `EnterWorktree`),
  aligning the location is **optional** — a convenience for interactive sessions, not a
  requirement. Recommendation: leave `wt` at its default sibling layout; document the remap
  as an opt-in for teams that want `EnterWorktree` compatibility.

## Outcome

Keep bespoke scripts; position `wt` as the recommended interactive complement; no #124
changes; revisit only if `cc-spex`/`spex-worktrees` is later adopted (#203).
