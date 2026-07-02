# Evaluation: `rhuss/cc-spex` for the curated external-marketplace set

**Issue**: [#203](https://github.com/nq-rdl/agent-extensions/issues/203) (epic #207)
**Date**: 2026-07-02
**Kind**: research + recommendation (adopt decision is **user-gated**)
**Subject**: [`rhuss/cc-spex`](https://github.com/rhuss/cc-spex) — the `spex` plugin, a Spec-Kit
extension bundle for Claude Code, distributed as `spex@cc-rhuss-marketplace`.

> This document is **research and a recommendation only**. It does **not** edit
> `.claude/settings.json` or `docs/external-marketplaces.md`. The draft diffs in the last
> section are for the user to apply *after* approval and *after* the stated conditions are met.
> All facts were verified against live upstream sources on 2026-07-02 (see **Sources**).

## Summary

**Recommendation: CONDITIONAL — do not adopt today. Adopt later, scoped to `spex` core +
`spex-gates` with `autoUpdate: false` and a tag pin, once the epic's workflow items (#124,
#204, #206) have settled.**

cc-spex is a genuinely capable, actively maintained Spec-Kit extension bundle (latest **v5.8.0**,
2026-06-25) that mechanically fits the curated-set pattern. Three things argue against adopting
it *today*: (1) it is **not a standalone tool** — unlike every other curated entry (`ruff`, `uv`,
`worktrunk`, `svelte`), `spex` is a set of extensions layered on the Spec-Kit `specify` CLI, so it
only earns its keep once the team runs Spec-Kit for real; (2) several bundled extensions
**overlap or conflict** with things we already enable — `spex-worktrees` fires a **mandatory**
worktree-create hook that competes head-on with the curated `worktrunk` plugin and epic item
**#206**, and `spex-deep-review` duplicates the `review` bundle + `pr-review-toolkit`; and (3) the
distribution marketplace is a **fast-churning, single-maintainer** catalog whose `spex` entry
**lags the source repo** (pinned v5.6.0 vs source v5.8.0) and which carries **open
install-reliability issues** (#7, #11), so `autoUpdate: true` is not warranted.

On the epic's two named friction points, cc-spex is a **partial fit, not a null result**: it has
real **spec↔code drift** machinery (`/speckit-spex-evolve`, mid-implementation review checkpoints
at the 1/3 and 2/3 task marks, `spex-gates` deviation tracking + a `verify` drift check) and a
defined **session-continuity discipline** (fresh-session rule, `/clear` between phases, flow-state
tracking with a status line, subagent isolation in `ship`). But it does **not** target the SpecKit
**constitution / `CLAUDE.md`** document specifically, nor does it persist/restore session state —
those remain the remit of #205 (routing guidance) and #124 (lifecycle skill).

**Friction-point findings (representative dry run of the intended SpecKit + Superpowers workflow):**

| Friction point | Does cc-spex address it? | Evidence |
|---|---|---|
| **Constitution drift** (spec/intent decaying as work progresses) | **Partial.** Strong on *spec↔code* drift; silent on the *constitution/`CLAUDE.md`* document. | `/speckit-spex-evolve` reconciles spec/code mismatch; ship-pipeline **mid-implementation checkpoints** review all code-so-far against the spec at 1/3 & 2/3 "preventing drift from compounding"; `spex-gates` `review-code` does deviation tracking and `verify` runs a drift check. README never mentions the constitution or `CLAUDE.md`. |
| **Session continuity** (losing workflow state across sessions) | **Partial.** A working *discipline*, not state persistence. | README: "Start each spec-kit/spex session in a fresh Claude Code session"; `/clear` between phases; **flow-state tracking** (`.specify/.spex-state`) with a status line; `/speckit-spex-clear` to clear stuck state; subagent isolation in `/speckit-spex-ship`. No cross-restart state restore. |

A flat "adopt" is wrong (it doesn't fully solve the epic's friction, overlaps three things we
ship, and presumes an unformalized Spec-Kit commitment); a flat "don't adopt" is also wrong (it is
well-built, uses spec-kit's *native* extension system, and its per-extension `enable/disable` model
supports a clean scoped adoption). Hence **conditional**.

## Extensions overview

cc-spex extends [`github/spec-kit`](https://github.com/github/spec-kit). **Since v5.0.0
(2026-04-25) it uses spec-kit's native extension system** — the old traits/overlay mechanism
(`spex-traits.sh`, `spex-traits.json`, sentinel markers) was removed and replaced with
`extension.yml` manifests, lifecycle hooks, and `specify extension enable/disable`, with state in
`.specify/extensions/.registry`. Each manifest declares `schema_version: "1.0"` and
`requires.speckit_version: ">=0.5.2"`; `github/spec-kit` ships the mechanism itself
(`extensions/EXTENSION-API-REFERENCE.md`, `RFC-EXTENSION-SYSTEM.md`, first-party `agent-context`/`bug`
extensions; spec-kit latest **v0.12.3**, 2026-07-01). Everything ships inside a **single plugin,
`spex`**; the six extensions below are enabled/disabled within it.

| Extension | Status | Auto-hooks (from `extension.yml`) | Representative commands | Requires |
|---|---|---|---|---|
| `spex` (core) | always active | `before_finish` (smoke-test prompt), `after_finish` (flow-state cleanup) | `/speckit-spex-brainstorm`, `-ship`, `-evolve`, `-spec-refactoring`, `-clear`, `-smoke-test` | speckit ≥0.5.2 |
| `spex-gates` | stable | `after_specify` = review-spec (**mandatory**), `after_tasks` = review-plan (**mandatory**) | `-gates-review-spec`, `-review-plan`, `-review-code`, `-verify`, `-stamp` | speckit ≥0.5.2 |
| `spex-worktrees` | stable | `after_specify` = manage `create` (**mandatory**) | `-worktrees-manage` | speckit ≥0.5.2, git |
| `spex-teams` | **experimental** | `before_plan` = research (optional, prompted) | `-teams-orchestrate`, `-research`, `-implement` | speckit ≥0.5.2, **spex-gates** |
| `spex-deep-review` | stable | `after_implement` = run (optional, prompted) | `-deep-review-run` (5 agents + autonomous fix loop) | speckit ≥0.5.2, **spex-gates** |
| `spex-collab` | stable | (none auto; integrates into ship watch/triage) | `-collab-reviewers`, `-phase-split`, `-phase-manager`, `-revise`, `-reconcile`, `-triage` | speckit ≥0.5.2, **spex-gates** |

`spex-deep-review` runs **five** review agents (Correctness, Architecture & Idioms, Security,
Production Readiness, Test Quality) with a bounded autonomous fix loop. Note the **hard dependency
chain**: `spex-teams`, `spex-deep-review`, and `spex-collab` each require `spex-gates`, so the
minimal viable subset is **`spex` core + `spex-gates`**; the rest are strictly additive on top.

### Install path (two repos, not one — verified)

- **Source repo** `rhuss/cc-spex` — its repo-root `.claude-plugin/marketplace.json` is named
  **`spex-plugin-development`** ("Local development marketplace for the cc-spex plugin"). This is
  **not** the marketplace end users register.
- **Distribution marketplace** `rhuss/cc-rhuss-marketplace` — marketplace `name` is
  **`cc-rhuss-marketplace`**; it distributes `spex` (source `rhuss/cc-spex`, pinned **v5.6.0**)
  alongside four unrelated plugins (`threat-model-assessment`, `prose`, `memory`, `slidev`).

So the correct wiring is `extraKnownMarketplaces["cc-rhuss-marketplace"]` →
`github:rhuss/cc-rhuss-marketplace`, and `enabledPlugins["spex@cc-rhuss-marketplace"]`
(install: `/plugin marketplace add rhuss/cc-rhuss-marketplace` then
`/plugin install spex@cc-rhuss-marketplace`). **Dependency note:** `spex` is not self-contained —
its commands live in the `/speckit-spex-*` namespace and its hooks fire off Spec-Kit lifecycle
events, so it presumes the `specify` CLI and a `.specify/` project. Adopting it implies committing
to Spec-Kit as a workflow — a heavier commitment than any current curated-set entry.

## Overlap / conflict vs `speckit-lifecycle` (#124), `review`, and `planning`

Comparison targets: **`speckit-lifecycle`** (#124, the Wave-1 lifecycle-discipline skill — not yet
merged, evaluated against its intended shape); the **`review`** bundle (`wg-code-sentinel`,
`wg-code-alchemist`, `critical-thinking`, `doublecheck`, `agent-governance-reviewer`,
`se-responsible-ai-code`, `terraform-iac-reviewer`) plus the enabled
`pr-review-toolkit@claude-plugins-official`; and the **`planning`** bundle (`plan`,
`context-architect`, `hlbpa`, `adr-generator`). The 6×3 classification (complementary / overlapping /
conflicting):

| cc-spex extension | vs `speckit-lifecycle` (#124) | vs `review` bundle (+ `pr-review-toolkit`) | vs `planning` bundle |
|---|---|---|---|
| `spex` (core) | **Overlapping** — brainstorm→ship→evolve is a lifecycle front door, same arc #124 documents (and overlaps `superpowers` brainstorming/plans). | **Complementary** — orchestration, not review. | **Overlapping** — brainstorm/spec-refactoring touch planning territory. |
| `spex-gates` | **Overlapping (arguably complementary)** — automates review checkpoints at the *same* lifecycle boundaries #124 documents; duplication vs reinforcement depends on how #124 lands. | **Overlapping** — spec/plan/code review gates parallel our review agents. | **Complementary** — review gates aren't planning. |
| `spex-worktrees` | **Conflicting** — a **mandatory** `after_specify` worktree-create hook imposes a worktree mechanism at the lifecycle boundary. | **Complementary** — unrelated to review. | **Complementary** — unrelated to planning. |
| `spex-teams` | **Complementary** — parallel execution, orthogonal to lifecycle discipline (experimental both sides; `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` is already set here). | **Complementary** — execution, not review. | **Overlapping** — `before_plan` parallel *research* touches planning. |
| `spex-deep-review` | **Complementary** — post-implement review, orthogonal to lifecycle docs. | **Conflicting/duplicative** — its 5 perspectives (Correctness, Architecture, Security, Production Readiness, Test Quality) map almost 1:1 onto `pr-review-toolkit` + our sentinels; running both is redundant review capacity. | **Complementary**. |
| `spex-collab` | **Overlapping** — phase-split/revise/reconcile are lifecycle-management workflows. | **Overlapping** — `reviewers`/`triage` overlap review-guide + PR-comment handling. | **Overlapping** — phase management + spec revision touch planning/PR authoring (also overlaps the `gh` bundle's `send-pr`). |

**Sharpest conflict — worktrees (#206).** `spex-worktrees` registers a *mandatory* `after_specify`
hook that auto-creates a sibling worktree on every `/speckit.specify`. The team already enables the
curated **`worktrunk`** plugin, and epic item **#206** is deciding the canonical worktree tool.
Enabling `spex-worktrees` would install a second, competing worktree mechanism at the SpecKit →
Superpowers handoff boundary and pre-empt #206. If Worktrunk wins, `spex-worktrees` must be
disabled (`specify extension disable spex-worktrees`).

**Review overlap.** `spex-deep-review` + `spex-gates` substantially duplicate the `review` bundle
and `pr-review-toolkit`. The autonomous fix loop is a genuine differentiator, but running both
review stacks blind is wasted capacity — the choice (replace vs duplicate) must be made alongside #124.

## Maintenance / trust (+ `autoUpdate` suitability)

**Release cadence — active and current.** 14 GitHub releases; latest **v5.8.0 (2026-06-25)**. The
v5 line shipped fast: v5.0.0 (2026-04-25) through v5.7.0 (2026-05-30) — often every 1–3 days — then
v5.8.0. Earliest GitHub release is **v2.0.0 (2026-03-16)**; there is **no v1.0.0 release/tag**. The
project predates its first release under the former `sdd`/`cc-sdd` name (closed issue #2 dates to
2025-12-18; renamed `sdd`→`spex` at v3.0.0, whose release was published 2026-04-03 though the
CHANGELOG dates it 2026-03-28). Repo `pushed_at` 2026-06-28. Healthy, high-velocity — but high
velocity means high churn.

**Issue responsiveness — mixed; open reliability issues.** **5 open**, **2 closed** (both #2 and #4
closed 2026-04-03, so the maintainer does triage). Two open issues bear directly on how *we* would
consume it:
- **#7** (opened 2026-04-06, open) — "Plugin skills and commands not loaded when installed via
  marketplace (nested source directory structure)."
- **#11** (opened 2026-06-22, open) — "hooks call python3 (only py exists), and /spex:init hangs on
  the interactive script-type prompt."
- #9 (2026-06-16), #10 (2026-06-17), #12 (2026-06-28) round out the open set.

**Trust posture.** Single maintainer (Roland Huß, Red Hat), 100 stars, not archived. **License:**
the repo LICENSE is detected by GitHub as **Apache-2.0**, while the plugin/extension manifests and
the `cc-rhuss-marketplace` manifest declare **MIT** — a minor internal inconsistency; both are
permissive OSS licenses. The distribution marketplace bundles four unrelated plugins and its `spex`
entry **lags the source repo (v5.6.0 vs v5.8.0)**, so tracking its default branch does not even
give you the newest `spex`.

**`autoUpdate` suitability: NO (for now).** Given (a) fast churn, (b) open install-reliability
issues (#7, #11), and (c) a distribution marketplace that lags source and carries unrelated
plugins, tracking the default branch with `autoUpdate: true` is not warranted. If adopted, prefer
**`autoUpdate: false`** and pin the marketplace `source` to a known-good tag via `ref` (e.g.
`v5.8.0`), consistent with the "Auto-update and trust" guidance in `docs/external-marketplaces.md`.
Re-evaluate `autoUpdate: true` once #7 (marketplace-install skill loading) is closed.

## Recommendation

**CONDITIONAL — do not adopt now. Revisit when all of the following hold:**

1. **Spec-Kit is a committed team workflow.** `spex` is worthless without Spec-Kit running for
   real. Gate adoption on #124 (`speckit-lifecycle`) and #204 (SpecKit-side extension
   recommendation) landing and the team actually running `specify`.
2. **The worktree tool is decided (#206).** If the team standardizes on Worktrunk, adopt `spex`
   only with `spex-worktrees` **disabled** — its mandatory `after_specify` create-hook otherwise
   installs a competing worktree mechanism.
3. **Review overlap is deliberately scoped.** Decide, alongside #124, whether
   `spex-deep-review`/`spex-gates` *replace* or *duplicate* the `review` bundle +
   `pr-review-toolkit`. Don't run both blind.
4. **Pin, don't track.** Adopt with `autoUpdate: false` and a `ref` tag pin, given the churn + open
   reliability issues (#7, #11).

**Scoped adoption path (when the conditions are met):** enable **`spex` core + `spex-gates`** only
— the minimal subset that delivers the automated spec/plan quality gates and the spec↔code-drift
tooling that partially answer the epic's friction. Keep `spex-worktrees` disabled (defer to
Worktrunk/#206), and enable `spex-deep-review`/`spex-collab`/`spex-teams` only after the review-stack
and Agent-Teams decisions are made (note all three require `spex-gates`). The per-extension
`specify extension enable/disable` model makes this clean.

## Draft diffs (apply ONLY after approval + conditions met — NOT applied by this doc)

Provided so the adopt path is turnkey. **These are drafts. This deliverable does not edit
`.claude/settings.json` or `docs/external-marketplaces.md`.**

### 1. `docs/external-marketplaces.md` — add a row to "The curated set" table

```diff
 | `svelte` | `sveltejs/ai-tools` | `svelte` | Svelte 5 authoring + the Svelte MCP server |
+| `cc-rhuss-marketplace` | `rhuss/cc-rhuss-marketplace` | `spex` | Spec-Kit SDD extensions — spec/plan quality gates + spec↔code drift tooling (pinned; worktree/deep-review extensions disabled in favour of `worktrunk` + the `review` bundle) |
```

Also add a sentence to the "Auto-update and trust" section noting that `spex` is **pinned**
(`autoUpdate: false`, `ref` to a tag) because its distribution marketplace churns fast, lags the
source repo, and has open install-reliability issues.

### 2. `.claude/settings.json` — `enabledPlugins` + `extraKnownMarketplaces`

```diff
   "enabledPlugins": {
     "superpowers@claude-plugins-official": true,
     "gopls-lsp@claude-plugins-official": true,
     "pr-review-toolkit@claude-plugins-official": true,
     "codex@openai-codex": true,
     "modern-go-guidelines@goland-claude-marketplace": true,
     "astral@astral-sh": true,
     "worktrunk@worktrunk": true,
     "skill-creator@claude-plugins-official": true,
-    "plugin-dev@claude-plugins-official": true
+    "plugin-dev@claude-plugins-official": true,
+    "spex@cc-rhuss-marketplace": true
   },
   "extraKnownMarketplaces": {
@@
     "worktrunk": {
       "source": {
         "source": "github",
         "repo": "max-sixty/worktrunk"
       },
       "autoUpdate": true
-    }
+    },
+    "cc-rhuss-marketplace": {
+      "source": {
+        "source": "github",
+        "repo": "rhuss/cc-rhuss-marketplace",
+        "ref": "v5.8.0"
+      },
+      "autoUpdate": false
+    }
   },
```

> Pin note: `ref` pins the *marketplace* source to a known-good tag. If Claude Code rejects a `ref`
> on a marketplace source in your version, drop `ref` and keep `autoUpdate: false`, then update
> deliberately. After applying, **verify with `/reload-plugins`** (or restart) and confirm `spex`
> resolves and the `/speckit-spex-*` commands surface — open issue #7 reports skills sometimes not
> loading when installed via marketplace, so confirm before relying on them. Then scope extensions
> with `specify extension enable spex-gates` / `specify extension disable spex-worktrees`.

**Why not re-host:** per `docs/external-marketplaces.md`, external plugins are consumed from their
upstream marketplace, never copied into `rdl` — so no `rdl` bundle, `plugins/` tree, or
`registry/` entry is created for `spex`.

## Sources (fetched 2026-07-02)

- [rhuss/cc-spex — repo, releases, issues, tree, README, CHANGELOG](https://github.com/rhuss/cc-spex)
- [rhuss/cc-spex — dev marketplace `spex-plugin-development`](https://github.com/rhuss/cc-spex/blob/main/.claude-plugin/marketplace.json)
- [rhuss/cc-rhuss-marketplace — distribution marketplace `cc-rhuss-marketplace`](https://github.com/rhuss/cc-rhuss-marketplace/blob/main/.claude-plugin/marketplace.json)
- [rhuss/cc-spex — extension manifests](https://github.com/rhuss/cc-spex/tree/main/spex/extensions)
- [github/spec-kit — native extension system](https://github.com/github/spec-kit/tree/main/extensions)
- `docs/external-marketplaces.md` — this repo's curated-set pattern
