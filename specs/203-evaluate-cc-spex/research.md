# Phase 0 Research: cc-spex evaluation

**Method**: Every claim below was re-verified on 2026-07-02 against live upstream sources via
the GitHub API (`gh api`), the two `marketplace.json` manifests, the cc-spex README/CHANGELOG,
and the `github/spec-kit` repo. Where the prior draft research
(`scratchpad/wave1-prior/203-cc-spex-evaluation.md`) was wrong, the correction is called out.

**Second verification pass (also 2026-07-02)**: every `extension.yml` was re-read at **both** the
distributed tag `v5.6.0` and `v5.8.0`/main, and the `github/spec-kit` latest release re-checked.
This pass corrected three hook-wiring claims from the first pass (see D3 corrections **#1**, **#6**,
**#7**) and refreshed the spec-kit version (D4). None of the corrections change the verdict; they
sharpen the "scope carefully" case, since the minimal `spex` core + `spex-gates` subset is more
invasive than first described.

## Decision log

### D1 — Wiring target: distribution marketplace, not the dev marketplace

- **Decision**: Wire via `extraKnownMarketplaces["cc-rhuss-marketplace"]` → `github:rhuss/cc-rhuss-marketplace`, enable `spex@cc-rhuss-marketplace`.
- **Rationale**: The source repo's own repo-root marketplace is named **`spex-plugin-development`**
  ("Local development marketplace for the cc-spex plugin") — dev-only, not the end-user channel.
  The distribution marketplace `cc-rhuss-marketplace` distributes `spex` (and 4 unrelated plugins).
- **Evidence**: `rhuss/cc-spex/.claude-plugin/marketplace.json` → `"name": "spex-plugin-development"`;
  `rhuss/cc-rhuss-marketplace/.claude-plugin/marketplace.json` → `"name": "cc-rhuss-marketplace"`.
- **Alternatives considered**: Registering `rhuss/cc-spex` directly — rejected because its root
  marketplace is the dev marketplace, per FR-010.

### D2 — Extension set (all six confirmed in the repo tree)

- **Decision**: The adoptable unit is one plugin `spex` containing 6 extensions: `spex` (core),
  `spex-gates`, `spex-worktrees`, `spex-teams`, `spex-deep-review`, `spex-collab`.
- **Evidence**: `git/trees/main?recursive=1` lists `spex/extensions/{spex,spex-gates,spex-worktrees,spex-teams,spex-deep-review,spex-collab}/extension.yml`.
- **Correction vs prior**: prior research's overview was right that all 6 exist; the v5.0.0
  CHANGELOG only enumerated 5 (core + gates/worktrees/teams/deep-review) — `spex-collab` was added later.

### D3 — Hook wiring (corrected from prior research)

Read from each `extension.yml` at `main` (v5.8.0 line):

| Extension | Hook(s) registered | Standalone commands | Requires |
|---|---|---|---|
| `spex` (core) | **mandatory** flow-state hooks on every lifecycle event (`after_specify`, `before/after_clarify`, `before/after_plan`, `before/after_tasks`, `before/after_implement`, `after_finish`) + `before_finish` (smoke-test, **optional**) | brainstorm, ship, evolve, spec-refactoring, help, extensions, finish, … | speckit ≥0.5.2 |
| `spex-gates` | `after_specify` = review-spec (**mandatory**), `after_tasks` = review-plan (**mandatory**), `after_implement` = review-code (**mandatory**) | review-spec, review-plan, review-code, verify, stamp | speckit ≥0.5.2 |
| `spex-worktrees` | `after_specify` = manage `create` (**mandatory**) | manage | speckit ≥0.5.2, git |
| `spex-teams` | `before_plan` = research (**optional**, prompted) | orchestrate, research, implement | speckit ≥0.5.2, **spex-gates** |
| `spex-deep-review` | `after_implement` = run (**optional**, prompted) | run | speckit ≥0.5.2, **spex-gates** |
| `spex-collab` | `after_tasks` = reviewers (**mandatory**), `before_implement` = phase-split (**optional**, prompted) | reviewers, phase-split, phase-manager, revise, reconcile, triage | speckit ≥0.5.2, **spex-gates** |

- **Corrections vs prior research**:
  1. `after_implement` is hooked by **both** `spex-gates` (review-code, **mandatory**) **and**
     `spex-deep-review` (run, optional/prompted) — confirmed by reading each `extension.yml` at
     **both** the distributed tag `v5.6.0` and `v5.8.0`/main (identical wiring). Enabling
     `spex-gates` therefore auto-runs a **mandatory** code review at `after_implement`, not only
     the spec/plan gates. (This corrects a first-pass error in an earlier draft of this file, which
     claimed gates does *not* auto-hook `after_implement`; the live manifests show it does at every
     relevant version, so `spex` core + `spex-gates` already introduces a code-review gate.)
  2. `spex-worktrees` **also** registers a mandatory `after_specify` hook — so enabling it makes
     worktree creation fire automatically on every `/speckit.specify`.
  3. `spex-teams` **does** ship standalone commands (orchestrate/research/implement) and a
     `before_plan` hook — prior research's "no standalone command" was wrong.
  4. **Hard dependency chain**: `spex-teams`, `spex-deep-review`, and `spex-collab` each declare
     `requires.extensions: spex-gates`. You cannot enable any of them without `spex-gates`.
     The minimal scoped adoption is therefore **spex core + spex-gates only**.
  5. deep-review command is `speckit.spex-deep-review.run` → `/speckit-spex-deep-review-run`
     (prior research wrote `-review`).
  6. `spex-collab` is **not** hook-free: it registers a **mandatory** `after_tasks` = reviewers
     hook (generates `REVIEWERS.md`) and an optional `before_implement` = phase-split hook
     (confirmed at `v5.6.0` and `v5.8.0`) — an earlier draft's "(none auto)" was wrong.
  7. `spex` **core** registers **mandatory** flow-state hooks on essentially every lifecycle event
     (`after_specify` … `after_implement`, plus `after_finish`), alongside an optional
     `before_finish` smoke-test — so enabling core alone stamps flow state on every `/speckit.*`
     step, including a mandatory `after_specify`. An earlier draft listed only the two finish hooks.

### D4 — Native extension system confirmed

- **Decision**: cc-spex v5.x uses **spec-kit's native extension system** (not a bespoke traits hack).
- **Evidence**: cc-spex CHANGELOG v5.0.0 (2026-04-25): "Traits replaced by spec-kit native
  extensions … `extension.yml` manifests, lifecycle hooks, `specify extension enable/disable`,
  state in `.specify/extensions/.registry`." Each `extension.yml` sets `schema_version: "1.0"` and
  `requires.speckit_version: ">=0.5.2"`. `github/spec-kit` ships the mechanism:
  `extensions/{README.md,EXTENSION-API-REFERENCE.md,RFC-EXTENSION-SYSTEM.md,EXTENSION-*-GUIDE.md}`
  plus first-party extensions (`agent-context`, `bug`, …). spec-kit latest release: **v0.12.4 (2026-07-02)**.

### D5 — Friction-point fit (nuanced from prior "does not address")

- **Decision**: cc-spex **partially** addresses both named friction points; it does not fully solve
  either, and neither maps to the SpecKit *constitution/CLAUDE.md* document specifically.
- **Evidence (README)**:
  - Spec↔code **drift**: `/speckit-spex-evolve` reconciles spec/code mismatch; **mid-implementation
    review checkpoints** at the 1/3 and 2/3 task marks "review all code so far against the spec …
    preventing drift from compounding"; `spex-gates` review-code does "deviation tracking" and
    `verify` runs a "drift check". This addresses the *spec-intent-decay* half of "constitution
    drift" — but the README never mentions the constitution or `CLAUDE.md` as a document.
  - **Session continuity**: guidance to "Start each spec-kit/spex session in a fresh Claude Code
    session," `/clear` between phases, **flow-state tracking** with a status line, `/speckit-spex-clear`
    to clear stuck state, and subagent isolation in `/speckit-spex-ship`. This is a *discipline* for
    working across sessions, not persistence/restore of session state.
- **Correction vs prior research**: prior said cc-spex "does not directly address" the friction —
  too strong. It offers real spec↔code-drift machinery and a defined session-continuity discipline;
  it just doesn't target constitution/CLAUDE.md drift or state persistence, which remain #205/#124's remit.

### D6 — Maintenance / trust facts (several date/license corrections)

- **Release cadence**: 14 GitHub releases, **v5.8.0 (2026-06-25)** latest. v5 line shipped fast:
  v5.0.0 (2026-04-25) … v5.7.0 (2026-05-30) → v5.8.0 (2026-06-25). Repo `pushed_at` 2026-06-28.
  - **Correction vs prior**: prior claimed "v1.0.0 (2025-11-11)" and "v3.0.0 (2026-03-28)". There is
    **no v1.0.0 release/tag**; the earliest GitHub release is **v2.0.0 (2026-03-16)**. The v3.0.0
    **release** was published **2026-04-03** (the CHANGELOG *dates* it 2026-03-28). The project
    predates its first release under the former `sdd`/`cc-sdd` name (closed issue #2 dates to
    2025-12-18; renamed `sdd`→`spex` at v3.0.0).
- **Issues**: 5 open (`#7` marketplace-install skills-not-loading, opened 2026-04-06;
  `#9`,`#10`,`#11`,`#12`), 2 closed (`#2`,`#4`, both closed **2026-04-03**). `#11` (2026-06-22, open):
  "hooks call python3 (only py exists), and /spex:init hangs on the interactive script-type prompt."
- **License**: repo LICENSE detected by GitHub as **Apache-2.0**; the plugin/extension manifests and
  the `cc-rhuss-marketplace` manifest declare **MIT**. Minor internal inconsistency; both are permissive.
  - **Correction vs prior**: prior said "MIT-licensed" flatly. Repo is Apache-2.0; MIT appears only in manifests.
- **Version lag**: distribution `cc-rhuss-marketplace` pins `spex` at **v5.6.0** while source is
  **v5.8.0** — tracking the distribution channel does not deliver the newest spex. Distribution
  bundles 5 plugins total (`spex` + `threat-model-assessment`, `prose`, `memory`, `slidev`).
- **`autoUpdate` decision**: **NO** for now → prefer `autoUpdate: false` + `ref` pin to a known-good
  tag (e.g. `v5.8.0`), given fast churn, open install-reliability issues (`#7`, `#11`), and a
  distribution channel that lags source. Single maintainer (Roland Huß, Red Hat), 100 stars, not archived.

## Sources (all fetched 2026-07-02)

- cc-spex repo/releases/issues/tree/README/CHANGELOG: https://github.com/rhuss/cc-spex
- cc-spex dev marketplace (`spex-plugin-development`): https://github.com/rhuss/cc-spex/blob/main/.claude-plugin/marketplace.json
- Distribution marketplace (`cc-rhuss-marketplace`): https://github.com/rhuss/cc-rhuss-marketplace/blob/main/.claude-plugin/marketplace.json
- extension manifests: https://github.com/rhuss/cc-spex/tree/main/spex/extensions
- spec-kit native extension system: https://github.com/github/spec-kit/tree/main/extensions
- this repo's curated-set pattern: `docs/external-marketplaces.md`
