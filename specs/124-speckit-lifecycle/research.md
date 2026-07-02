# Phase 0 Research: SpecKit lifecycle skill

The spec's Clarifications session (2026-07-02) resolved every open question, so no
`[NEEDS CLARIFICATION]` markers remained entering Plan. This document instead pins the
precise mechanisms, script contracts, and packaging sequence the downstream tasks depend
on. Each finding is stated as **Decision / Rationale / Alternatives considered**.

## 1. Runtime discovery — trunk detection

- **Decision**: Resolve trunk from `git symbolic-ref --short refs/remotes/origin/HEAD`
  (strip the `origin/` prefix). Fallback chain when that fails (no remote / unset HEAD):
  first existing of `main`, `master`, `trunk`; final fallback is the current branch **only
  if it does not match `^\d{3}-`** (a spec branch is never trunk).
- **Rationale**: `origin/HEAD` is the authoritative default-branch pointer and works for
  GitHub/Gitea/GitLab clones alike; the ordered name fallback covers fresh/local repos where
  `origin/HEAD` is unset. Matches FR-001/FR-015 and the spec's Assumptions.
- **Alternatives considered**: Hardcoding `main` (rejected — FR-015 forbids hardcoding and
  the repo may use `master`/`trunk`); parsing `git remote show origin` (rejected — needs a
  network round-trip and is slower/less reliable offline).

## 2. Runtime discovery — merge target topology

- **Decision**: The merge target for spec `NNN` is the branch the spec was cut from, found
  via git topology rather than assumed to be trunk. Candidate parents are the other live
  branches (trunk + any integration branches); the merge target is the candidate whose
  `git merge-base <candidate> <spec-branch>` tip is the spec branch's actual fork point
  (the nearest ancestor). Practically: compute `git merge-base` against trunk and against
  each integration branch and select the parent that is an ancestor of the spec branch with
  the most recent fork commit.
- **Rationale**: Supports the `--base <branch>` epic-grouping case (FR-006/FR-007) — a spec
  cut from an integration branch must merge back into that branch, not trunk. Uses only local
  git, no external metadata.
- **Alternatives considered**: Recording the parent in `specs/NNN-slug/` at provision time
  (viable, but adds a written side-channel that can drift; topology is self-describing);
  always merging to trunk (rejected — violates the non-trunk-merge acceptance scenario).

## 3. `provision-worktree.sh` — exact semantics

- **Decision**: `provision-worktree.sh <slug> [--base <branch>]`.
  1. **Derive NNN**: scan three sources — `git branch -a` (strip `remotes/*/`), `specs/*`,
     `.claude/worktrees/*` — extract every leading 3-digit number, take the max, add 1,
     zero-pad to 3 digits (`printf '%03d'`). Empty/none → `001`.
  2. **Conflict guard**: if the derived (or any intended) `NNN` already exists as a branch,
     a `specs/NNN-*` dir, or a `.claude/worktrees/NNN` slot, abort non-zero **before any
     mutation**. (Guards the concurrent-creation race — the losing session fails safely.)
  3. **Base**: `BASE=${--base:-<detected trunk>}`.
  4. **Create branch + worktree**: `git worktree add -b <NNN>-<slug> .claude/worktrees/NNN <BASE>`
     (single call creates the branch off BASE and checks it out into the slot).
  5. **create-new-feature probe**: if `.specify/scripts/bash/create-new-feature.sh` exists,
     invoke it with `--allow-existing-branch` (so it adopts the branch this script already
     created and writes `specs/NNN-slug/spec.md` from the template); if absent, bare-git
     fallback creates `specs/NNN-slug/` + a template `spec.md` directly.
  6. **Emit** the worktree path and `NNN` (JSON or key=value) for the skill to report the
     `claude --worktree .claude/worktrees/NNN` invocation.
- **Rationale**: One `git worktree add -b` is the minimal correct primitive; probing
  create-new-feature keeps the script authoritative for git while deferring SpecKit's own
  spec scaffolding when available (FR-006).
- **Alternatives considered**: `git branch` + `git worktree add` as two steps (rejected —
  `add -b` is atomic and avoids a dangling branch on failure); calling create-new-feature
  *first* to derive NNN (rejected — its numbering is timestamp/`--number`-driven and does
  not scan `.claude/worktrees/`, so the script must own NNN derivation itself).
- **create-new-feature interface note (verified)**: it accepts `--json`,
  `--allow-existing-branch`, `--number N`, `--short-name`; emits `BRANCH_NAME`, `SPEC_FILE`,
  `FEATURE_NUM`; and creates the branch **in the current working tree** via `git checkout -b`.
  Therefore the probe must run **with the worktree slot as CWD** (so its checkout/adoption
  targets the slot's branch) and be passed `--number 10#$NNN` / `--allow-existing-branch` so
  it reuses the already-created `NNN-slug` branch instead of minting a new number.

## 4. `merge-spec.sh` — exact semantics

- **Decision**: `merge-spec.sh <NNN>`.
  1. Resolve the spec branch (`NNN-*`) and its slot (`.claude/worktrees/NNN`).
  2. **Uncommitted-changes guard**: if the slot has a dirty working tree
     (`git -C <slot> status --porcelain` non-empty) or unpushed spec work that would be lost,
     **refuse loudly and abort non-zero** — never auto-stash/discard.
  3. Resolve the **merge target** via topology (§2); `git checkout <target>`.
  4. `git merge --no-ff <NNN>-slug -m "<conventional message>"`. **On merge conflict**: run
     `git merge --abort` to restore a clean tree, print a loud message, and **exit non-zero
     before any cleanup runs** — the worktree slot and branch are left intact so conflict
     resolution stays a human/skill task outside the deterministic script (spec Clarification
     2026-07-02; FR-007). The script never auto-resolves (no `-X ours/theirs`).
  5. **Cleanup order (critical)**: remove the worktree slot **first**
     (`git worktree remove .claude/worktrees/NNN`), *then* `git branch -d <NNN>-slug`, then
     `git push origin --delete <NNN>-slug`. Git refuses `branch -d` while the branch is checked
     out in a worktree, so slot removal must precede branch deletion.
  6. **Idempotency**: worktree removal tolerates an already-absent slot (check `git worktree list`
     / path existence before removing); re-running after a partial failure completes cleanly.
  7. `specs/NNN-slug/` is **left in place** as the durable record; `NNN` is never reused.
- **Rationale**: Encodes the spec's hardest safety guarantees — cleanup ordering and the
  loud uncommitted-changes refusal — as testable script logic (FR-007, SC-006).
- **Alternatives considered**: `git branch -D` force-delete (rejected — masks unmerged work;
  `-d` is the safe verb after a confirmed `--no-ff` merge); deleting the branch before the slot
  (rejected — Git errors, and it is the exact ordering bug the spec calls out).

## 5. Bats test strategy & `asctl` compatibility

- **Decision**: Tests live in `skills/speckit-lifecycle/.tests/` (`*.bats` + `helpers.bash`).
  Each test `setup()` builds an isolated fixture: `mktemp -d`, `git init`, seed an initial
  commit on a configurable default branch, optionally pre-create spec branches / `specs/*` /
  `.claude/worktrees/*` slots to exercise NNN derivation and conflict guards, then run the
  script under test with the fixture as CWD. `teardown()` removes the temp dir. Fixtures set
  `git config user.email/name` locally so commits work in CI.
- **Rationale (asctl)**: Verified against `tools/asctl/internal/structure/structure.go`:
  `allowedSubdirs = {assets, references, scripts}` and any dot-prefixed entry is skipped
  (`isHidden`), so a hidden `.tests/` dir ships with the skill without tripping the
  disallowed-subdir check. `references/` may hold only `.rst`, so tests cannot live there;
  `scripts/` is reserved for shipped runtime scripts, so a separate hidden dir keeps test code
  out of the plugin's runtime surface. (FR-018, SC-002, US4 acceptance #2.)
- **Alternatives considered**: Putting tests under `scripts/` (rejected — pollutes the copied
  plugin runtime tree with test files); a top-level `tests/` outside the skill (rejected — would
  not ship with the skill and breaks "deploy everywhere at once"); `references/*.rst` (rejected —
  bats files are not `.rst`).
- **Six required coverage areas** (SC-002): NNN derivation (max+1 across all three sources,
  zero-pad); conflict-guard abort (no state mutation); branch + worktree creation off trunk;
  `--base` parentage (branch cut from the named base); merge-target topology (trunk vs
  integration branch); post-merge cleanup (slot removed before branch delete + idempotency +
  uncommitted refusal).
- **Additional case beyond the six** (spec Clarification 2026-07-02): merge-conflict abort —
  a diverged spec branch → `git merge --abort`, non-zero exit, and **no cleanup** (slot + branch
  intact). Added to `merge-spec.bats` so the abort-path safety guarantee is verified, not just
  the happy-path merge.

## 6. PR actioning — forge inference

- **Decision**: Infer the forge from the `origin` remote URL host (github.com → `gh`;
  gitea/gitlab hosts → their APIs), overridable via a `CLAUDE.md` key. Fetch review summaries
  and inline thread comments from **separate endpoints** (on GitHub: `gh pr view --json reviews`
  for summaries; `gh api .../pulls/<PR>/comments` for inline threads), triage HIGH/MEDIUM/LOW,
  and post replies to inline threads (`.../comments/<id>/replies`).
- **Rationale**: Matches FR-009 and generalizes `dst-autoloop`'s GitHub-specific block into a
  forge-inferred one. GitHub via `gh` is the practical default; bespoke forges beyond inference
  are an explicit non-goal.
- **Alternatives considered**: A single combined comments endpoint (rejected — GitHub genuinely
  splits summary reviews from inline thread comments; fetching only one loses feedback).

## 7. Packaging sequence (new `speckit` bundle)

- **Decision**: (1) author `registry/bundles/speckit.yaml` modeled on
  `registry/bundles/pixi.yaml` (`id: speckit`, `displayName: SpecKit`,
  `skills: [speckit-lifecycle]` as a flat member so leaf == source, empty
  agents/hooks/prompts/mcp, `targets.claude` `enabled: true` / `pluginName: speckit` /
  `marketplaceName: rdl`); (2) add `speckit` to `registry/marketplace.yaml` `order`; (3) run
  `bash scripts/sync-plugins.sh speckit` → real-file copy into `plugins/speckit/`; (4)
  `python3 scripts/generate_manifests.py .` → `plugin.json` + `marketplace.json`
  (the `rdl` meta-plugin deps regenerate automatically from enabled bundles); (5)
  `python3 scripts/generate_bundles_doc.py .` → `docs/bundles.md`.
- **Rationale**: This is the repo's documented canonical→plugin pipeline; following it keeps
  all `--check` drift gates green (FR-017, SC-003). `pixi.yaml` is the closest single-flat-skill
  precedent.
- **Alternatives considered**: Hand-editing the generated manifests (rejected — CI
  `generate_manifests.py --check` fails on drift and CLAUDE.md forbids it); a `{source, leaf}`
  rename (unnecessary — the skill invokes cleanly as `speckit:speckit-lifecycle` with a flat
  member).
- **Open packaging detail for Tasks**: `pixi.yaml` carries `owners:`/`channels:` keys not in
  the CLAUDE.md schema snippet — the Tasks phase should mirror `pixi.yaml` exactly, then let
  `generate_manifests.py --check` + `check_consistency.py` confirm the shape is accepted.

## 8. Skill body structure (generalizing `dst-autoloop`)

- **Decision**: `SKILL.md` frontmatter uses the issue's exact generic `description` (no
  repo-specific references — no "template", no data-science terms). Body sections: (1) Context
  detection (branch → mode table, then discover+read `CLAUDE.md` at root **or** `docs/`); (2)
  Root mode — survey-first, create-spec-+-worktree (with `.specify/` restore-if-missing), merge,
  PR actioning; (3) Worktree mode — spec identification, phase table
  (`specify→clarify→plan→tasks→[checklist]→analyze→implement`), implementation loop with
  runtime-discovered validation and pluggable implement strategy.
- **Rationale**: Preserves the prior art's proven skeleton while stripping every hardcoded path/
  command (`make worktree-new`, `make test-template`, `docs/CLAUDE.md`) in favor of runtime
  discovery + the two bundled scripts (FR-001..FR-016).
- **Alternatives considered**: Keeping `dst-autoloop`'s `make`-based provisioning inline
  (rejected — non-portable and violates "no hardcoded commands"); splitting root/worktree into
  two skills (rejected — the issue requires one skill invoked identically everywhere).
