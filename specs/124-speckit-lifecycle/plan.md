# Implementation Plan: SpecKit lifecycle skill for worktree-based development

**Branch**: `124-speckit-lifecycle` | **Date**: 2026-07-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/124-speckit-lifecycle/spec.md`

## Summary

Ship a single `speckit-lifecycle` skill — packaged as a new `speckit` marketplace
bundle — that drives the complete SpecKit development lifecycle for any repo following
SpecKit conventions (`.specify/`, `specs/NNN-slug/`, `.claude/worktrees/NNN`). The skill
detects its mode from the current branch (default branch → root/orchestration mode;
`^\d{3}-` → worktree/execution mode; anything else → halt-and-ask) and delegates the two
safety-critical, deterministic git operations — worktree provisioning and spec merge — to
two versioned bash scripts shipped under the skill's `scripts/`, unit-tested with `bats`
against throwaway fixture repos. Everything the skill does is discovered at runtime: trunk
branch, merge target, validation commands, PR forge/API, phase list, implement strategy,
and `CLAUDE.md` location are never hardcoded. The skill generalizes the `dst-autoloop`
prior art with all data-science specifics removed. Technical approach: Markdown skill body
+ two POSIX/bash scripts (modeled on `skills/bitwarden/scripts` and
`skills/cc-web-setup/scripts`) + a hidden `.tests/` bats suite (invisible to
`asctl repo-check`) + registry/manifest/docs wiring for the new bundle.

## Technical Context

**Language/Version**: Bash (bash 3.2+/POSIX-portable, macOS + Linux) for the two bundled
scripts; Markdown for `SKILL.md`; `bats-core` 1.13.0 (installed) for the test suite; YAML
for the registry bundle. No new Go or TypeScript — the deterministic operations ship as
skill-bundled shell scripts, matching the existing `bitwarden`/`cc-web-setup` precedent
(the Go-first Language Policy governs repo tooling under `tools/`/`mcp/`, not
content-authoring scripts that ship *inside* a skill).
**Primary Dependencies**: `git` (worktree, `merge-base`, `branch -a/-d`,
`symbolic-ref refs/remotes/origin/HEAD`); the target repo's
`.specify/scripts/bash/create-new-feature.sh` (runtime-probed, optional — bare-git
fallback when absent); `gh` (optional, for PR actioning; forge inferred from remote URL);
`python3` + `pyyaml` and the repo's existing pipeline scripts
(`sync-plugins.sh`, `generate_manifests.py`, `generate_bundles_doc.py`) for packaging.
**Storage**: Filesystem + git only — `specs/NNN-slug/` (durable record), `.claude/worktrees/NNN`
(ephemeral checkout slot), and git refs/branches. No database.
**Testing**: `bats-core` 1.13.0, each test spinning up an isolated throwaway `git init`
fixture in a temp dir; the tests live under `skills/speckit-lifecycle/.tests/` (hidden dir,
ignored by `asctl repo-check`). Skill structure validated by `asctl repo-check`; packaging
validated by `generate_manifests.py --check`, `generate_bundles_doc.py --check`,
`check_bundle_refs.py`, `check_grouping.py`, `check_consistency.py`, `validate-plugins.sh`.
**Target Platform**: macOS + Linux dev environments running Claude Code (POSIX shell
tooling required, per repo Platform Notes).
**Project Type**: Single project — a Claude Code documentation/CLI-script skill plus its
marketplace-bundle packaging. No frontend/backend split.
**Performance Goals**: Interactive dev tooling; scripts complete well under a second on a
normal repo. No throughput target.
**Constraints**: Zero hardcoded paths, commands, or forge API details — trunk, merge target,
validation, PR API, phase list, implement strategy, and `CLAUDE.md` location all discovered
at runtime (FR-015). Scripts are idempotent where specified (worktree removal), abort loudly
on conflict/uncommitted-changes, and never mutate state on a conflict-guard abort.
`asctl` structure rules: only `assets/`, `references/` (`.rst` only), `scripts/` allowed as
non-hidden subdirs; hidden dot-dirs ignored — hence `.tests/`.
**Scale/Scope**: 1 skill (`SKILL.md` + optional `references/`), 2 bundled scripts, ~6 bats
test areas, 1 new registry bundle, plus regenerated plugin tree + manifests + docs.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against the project constitution v1.0.0 (Principles I–V + Quality Gates).

- **I. Spec-First Authority — PASS.** The "what" lives in `specs/124-speckit-lifecycle/spec.md`
  (18 FRs, 6 SCs, 4 prioritized user stories). This plan derives only the "how"; any scope
  change routes back to the spec, not to code.
- **II. Execution via Superpowers — PASS.** Downstream execution follows worktree isolation
  (this work already runs in `.claude/worktrees/124`), TDD, and code review; the plan does not
  redefine scope.
- **III. Test-Driven Development (NON-NEGOTIABLE) — PASS by construction.** The two scripts are
  driven by the bats suite: each of the six required behaviors (NNN derivation, conflict-guard
  abort, branch/worktree creation, `--base` parentage, merge-target topology, post-merge cleanup)
  gets a failing bats test *before* the script logic that satisfies it. `/speckit-tasks` will
  order the test task ahead of its implementation task for every script behavior.
- **IV. Single-Executor Routing (NON-NEGOTIABLE) — PASS.** One executor per task; `/speckit-tasks`
  runs before any implementation begins (this plan does not hand off to execution). No dual
  `/speckit.implement` + Superpowers on the same task.
- **V. Definition of Done — PASS (planned).** Done requires green validation (bats suite +
  `asctl repo-check` + `--check` drift gates), a `changie` fragment, and local `lefthook`/CI-parity
  checks. Tasks will include a changie-fragment task and a final "run all Quality Gates" task.

**Quality Gates alignment**: After the skill/scripts land, `bash scripts/sync-plugins.sh speckit`,
`generate_manifests.py . --check`, `generate_bundles_doc.py . --check`, `validate-plugins.sh`,
the bundle/grouping/consistency checks, `asctl repo-check`, and the pipeline unit tests must all
pass — enumerated as SC-003 and mapped to concrete tasks in the Tasks phase.

**Result**: PASS — no violations; Complexity Tracking below intentionally empty.

## Project Structure

### Documentation (this feature)

```text
specs/124-speckit-lifecycle/
├── plan.md              # This file (/speckit-plan output)
├── research.md          # Phase 0 output — runtime-discovery decisions, script semantics, packaging
├── data-model.md        # Phase 1 output — Spec, Worktree slot, Phase, Parent branch, Bundled script
├── quickstart.md        # Phase 1 output — author + validate the skill/bundle end to end
├── contracts/           # Phase 1 output — CLI + skill contracts
│   ├── provision-worktree.md
│   ├── merge-spec.md
│   └── skill-modes.md
├── spec.md              # Feature spec (input)
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

Canonical content is authored under `skills/`; the plugin tree under `plugins/speckit/` is a
generated real-file copy (never hand-edited), refreshed by `scripts/sync-plugins.sh`.

```text
skills/speckit-lifecycle/
├── SKILL.md                     # skill body: description frontmatter (generic triggers) +
│                                #   context detection, root mode, worktree mode, phase table
├── scripts/
│   ├── provision-worktree.sh    # NNN derivation, conflict guard, branch+worktree, create-new-feature probe
│   └── merge-spec.sh            # merge-base target, --no-ff merge, worktree remove BEFORE branch delete
└── .tests/                      # hidden → ignored by asctl repo-check
    ├── provision-worktree.bats  # NNN derivation, conflict abort, branch/worktree, --base parentage
    ├── merge-spec.bats          # merge-target topology, worktree-before-branch cleanup, uncommitted refusal
    └── helpers.bash             # fixture-repo setup/teardown, shared assertions

registry/bundles/speckit.yaml    # new bundle: id speckit, displayName SpecKit, skills:[speckit-lifecycle]
registry/marketplace.yaml        # add `speckit` to `order` (meta deps regenerate from enabled bundles)

plugins/speckit/                 # GENERATED by sync-plugins.sh + generate_manifests.py
├── .claude-plugin/plugin.json   # GENERATED
└── skills/speckit-lifecycle/    # real-file copy of skills/speckit-lifecycle/ (scripts included)

.claude-plugin/marketplace.json  # GENERATED — gains the speckit entry
docs/bundles.md                  # GENERATED — gains the speckit row
```

**Structure Decision**: Single-project skill authored once under
`skills/speckit-lifecycle/`, packaged into `plugins/speckit/` via the repo's existing
canonical→plugin sync pipeline. Deterministic git logic is factored into two `scripts/`
files (testable in isolation) rather than embedded in the skill prose (FR-005); the bats
suite lives in a hidden `.tests/` dir so it ships with the skill yet stays invisible to
`asctl`'s allowed-subdir check (verified: `allowedSubdirs = {assets, references, scripts}`,
dot-prefixed entries skipped in `tools/asctl/internal/structure/structure.go`).

## Complexity Tracking

> No Constitution Check violations — this table is intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Phase notes

- **Phase 0 (`research.md`)**: no `[NEEDS CLARIFICATION]` remained after the spec's
  Clarifications session; Phase 0 instead pins the exact runtime-discovery mechanisms, the
  two scripts' precise semantics/exit contracts, the bats fixture strategy, and the
  bundle-packaging sequence.
- **Phase 1 (`data-model.md`, `contracts/`, `quickstart.md`)**: models the five spec entities
  and documents the two script CLIs + the skill mode-detection contract as the feature's
  external interfaces.
- **Agent context**: `.specify/scripts/bash/update-agent-context.sh claude` was **not** run —
  in this repo `CLAUDE.md` is a symlink to the hand-authored 16 KB `AGENTS.md`, and the updater
  would append generated content to it. Skipping it avoids polluting the canonical project doc
  (consistent with the spec's own "never overwrite `CLAUDE.md`" invariant); no plan artifact
  depends on it.
