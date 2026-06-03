# Design spec — plugin grouping by subject (umbrella for #101 + #102)

**Date:** 2026-06-02
**Status:** Decisions locked below; ready for an implementation plan.
**Scope:** **Claude Code only.** Codex / multi-host packaging is explicitly **deferred** (see §6).

**Relationship to the issues:**

| Item | Role | State |
|---|---|---|
| [#101](https://github.com/nq-rdl/agent-extensions/issues/101) | **Strategy** — retire domain bundles, regroup by subject | **closed in #108** (proposal adopted; execution tracked here) |
| [#102](https://github.com/nq-rdl/agent-extensions/issues/102) | **Mechanism (packaging side)** — `agent-extensions` sync + packaging | **closed in #108**; revised to the registry-owned mapping (§3) |
| [agent-skills#118](https://github.com/nq-rdl/agent-skills/pull/118) | ~~Phase-1 upstream grouping contract~~ | **closed as superseded** — grouping is owned in the packaging repo; upstream stays flat (§3) |
| [#109](https://github.com/nq-rdl/agent-extensions/issues/109) | **Tracker** — outstanding/deferred Phase-3 work | **closed in #108**; remaining (registry-only) work tracked by this spec (§5/§7) |
| **This spec** | **Umbrella** — apply #101's policy via the §3 mechanism | — |

Together these meet **both** #101 and #102: the policy (this spec + `CONTRIBUTING.md`) rides on
the packaging mechanism (§3), as one phased — now single-repo — migration.

## 1. Problem & goals

Domain bundles (`swe`, `infra`, `informatics`, `dev-tools`, `meta`, `hooks`, `rust`, `lucid`)
cause arbitrary categorization (re-litigated per skill), `marketplace.json` metadata rot (#100),
and a registry-reconciliation tax. **Goals:** unambiguous membership; clean ordered workflow
namespaces; metadata that can't rot; **a dead-simple install for the team**.

## 2. Policy — group by subject

One plugin per **subject** (tool/library/language/app/workflow); file by **primary** subject
(`go-gh` → `go:gh`); facet is always an **action/stage**; no-tool skills named after the
**workflow**; agents need home + description (companion skill only for reusable methodology).
Full rules: `CONTRIBUTING.md`.

## 3. Mechanism — registry-owned `{source, leaf}` mapping (Option 2; revised 2026-06-03)

Grouping is a **packaging** decision, so it is owned **here** in `agent-extensions`; the upstream
`agent-skills` tree stays **flat**. No upstream restructure, no cross-repo contract, no
merge-and-release gate.

- **Upstream:** flat `skills/<skill>/SKILL.md`, unchanged. Host-neutral (per #102's locked
  decision); not reshaped to match Claude Code plugin names.
- **Registry:** a bundle sets `pluginName: <subject>` and lists each member as either a **flat
  string** `<name>` (`leaf == name`) or an explicit **`{source, leaf}` mapping** (e.g.
  `{source: go-gh, leaf: gh}`).
- **Sync (`sync-plugins.sh`):** copies `skills/<source>/` → `plugins/<subject>/skills/<leaf>/`,
  renaming to the leaf → plugin tree stays one level deep.
- **Claude Code invokes `<subject>:<leaf>`.** The **leaf folder name drives invocation** —
  confirmed by smoke test (2026-06-03): a skill at `plugins/<p>/skills/<leaf>/` registers as
  `<p>:<leaf>`, while the upstream frontmatter `name:` survives only as a cosmetic `userFacingName`
  (display label). So vendored copies stay **byte-identical** — no frontmatter rewrite.
- **Validators (`check_grouping.py`):** valid member shape · no dup leaf per bundle · `pluginName`
  unique across bundles. `check_bundle_refs.py` resolves each member's `source` against
  `skills/<source>/`; `validate-plugins.sh` checks the plugin copy by **leaf**.

To get `go:gh`: leave `skills/go-gh/` flat; map `{source: go-gh, leaf: gh}` under `pluginName: go`.
To get `obsidian:bases`: leave `skills/obsidian-bases/` flat; map `{source: obsidian-bases, leaf:
bases}`. The grouping decision lives in one place — the registry — beside every other packaging
decision.

*Why this changed:* the earlier plan pushed grouping upstream (agent-skills#118) to avoid a
sync-time rename. The smoke test showed invocation keys on the leaf *folder*, not frontmatter — so
there is nothing to rewrite; the rename is just the folder name `sync-plugins.sh` already controls.
That removes the cross-repo gate and keeps `agent-skills` host-neutral, so agent-skills#118 is
closed as superseded.

## 4. Decisions

### D-1 — Install UX: a `rdl` meta-plugin (one command installs everything)

`claude plugin install` installs one plugin at a time and `marketplace add` does not auto-install.
So we ship a **`rdl` meta-plugin that declares every subject plugin as a dependency** — the team
runs **`claude plugin install rdl@rdl`** once and gets all subjects (and `claude plugin autoremove`
cleans up). The granular subject plugins keep clean namespaces; the meta keeps install trivial.

- *To confirm at build time:* the exact dependency-declaration field (the CLI's `autoremove`
  confirms auto-installed dependencies exist; the manifest key isn't documented in the cache).
- *Complement for shared repos:* commit a project-scoped `.claude/settings.json` (marketplace +
  enabled plugins) so anyone working in the repo gets them with zero steps.
- *Not chosen:* a `/rdl:setup` skill that scripts installs — more manual + a hand-maintained list.

### D-2 — Subject grouping: `git` absorbs all git-related skills

Locked placement of the former tiebreak set into a single **`git`** subject:
`git:husky`, `git:lefthook`, `git:pre-commit`, `git:changie`, `git:conventional-commits`,
`git:send-pr`, `git:document-release`. Membership rule: *git-related → `git`*. Guard:
`go-gh` is **not** git (it's Go CI) → stays `go:gh`; this keeps `git` from becoming a catch-all.

### D-3 — Generate manifests from the registry

`plugin.json` + `marketplace.json` are **generated** from `registry/bundles/*.yaml`, not
hand-maintained. This is the structural fix for #100's metadata rot and makes many subject
plugins cheap to maintain (the meta-plugin's dependency list is generated too). Extend
`check_consistency.py` to assert registry ↔ generated manifests are atomic; golden-file tests.
(Independent of Codex — this is a #101 simplification.)

### D-4 — Doc division of labour

- **`CONTRIBUTING.md`** = policy, process, procedures, standards (the grouping rules live here).
- **`AGENTS.md`** = a lean "where things live in this repo" map for AI agents — **not** policy.
  AGENTS.md's current bundle/policy prose moves to `CONTRIBUTING.md`; the slim-down is a migration
  task (deferred until the bundle layout actually changes, so the map matches reality).

### D-5 — Issues

**#101, #102, and #109 are closed in PR #108** (the mechanism PR), which ships the packaging
mechanism, manifest generation (D-3), and the `rdl` meta-plugin (D-1). The closures record the
**decisions + machinery** — not a claim that the Phase-3 *content* migration has run. The remaining
work is now **registry-only and single-repo** (no upstream dependency) and is tracked by **this
spec** (§5 placement map + §7 phases, §6 Codex task) — not by an open issue. This spec is linked
from each closed issue. **agent-skills#118 is closed as superseded** (§3): grouping is owned here,
so no upstream change is required.

*(Earlier plan was to "close on completion"; superseded — the machinery shipped early in #108, so
the issues close with it and this spec becomes the durable tracker for what's left.)*

## 5. Placement map (final, tunable)

- **Tool subjects, multi-facet:** `obsidian` (bases/cli/markdown), `go` (naming/secure/gh),
  `r` (expert + lib-*), `shiny`, `quarto`, `jules` (dispatch/dispatch-creator),
  `claude-code` (agent-teams/hook).
- **`git`** (D-2): husky, lefthook, pre-commit, changie, conventional-commits, send-pr,
  document-release.
- **Tool subjects, single-facet:** `sops`, `pixi`, `lychee`, `charm-tui`, `starrocks`,
  `writerside`, `zod`, `defuddle`, `bitwarden`, `ansible`, `argo-cd`, `rust`.
- **Agent homes** — tool-anchored → their tool plugin (agent-only where no skill):
  `terraform` (×3), `postgres`, `mongodb`, `arch-linux`, `kubernetes`, `github-actions`,
  `go` (go-mcp-expert). Activity/role → workflow plugins:
  `review` (gem-reviewer, wg-code-sentinel, wg-code-alchemist, critical-thinking, doublecheck,
  agent-governance-reviewer, se-responsible-ai-code), `planning` (plan, context-architect,
  repo-architect, api-architect, hlbpa, adr-generator), `debug` (debug, janitor),
  `docs` (se-technical-writer), `research` (research-technical-spike, prompt-builder),
  `git` (address-comments, playwright-tester → or its own `playwright`).

## 6. Deferred / out of scope

**Codex / multi-host packaging — explicitly deferred.** No `.codex-plugin` dual-emit, no
host-neutral packaging in this work. The consolidation review's §7.4 (Codex dual-targeting) is
parked for a later effort. *Open task (separate, with owner sign-off): decide what existing Codex
references in the repo — README, ARCHITECTURE, CHANGELOG, `.changes/*`, `.claude/settings.json`,
the consolidation review — to remove or keep.*

## 7. Migration phases

> **Status (post-#108, revised 2026-06-03):** PR #108 delivered the packaging *mechanism* plus D-3
> (manifest generation) and D-1 (`rdl` meta-plugin), and **closed #101/#102/#109** (D-5). The
> mechanism was then **revised to the registry-owned `{source, leaf}` mapping (§3)**, which removes
> the upstream dependency — **agent-skills#118 is closed as superseded**. What remains is the
> registry-only Phase-3 rollout below, entirely in this repo.

1. ~~**Phase 1 — agent-skills#118 (source).**~~ **Dropped** — grouping is owned here (§3); the
   upstream tree stays flat, so there is no upstream merge/release gate.
2. **Phase 2 — packaging mechanism (built + tested):** registry `{source, leaf}` mapping,
   `sync-plugins.sh` leaf rename, `check_grouping.py` / `check_bundle_refs.py` /
   `validate-plugins.sh` updates, unit tests. Flat bundles re-sync **no-diff** (verified) →
   incremental migration, no big-bang.
3. **Phase 3 — #101 rollout (this spec):** migrate subjects per §5 by adding `{source, leaf}`
   mappings + new bundles (a **registry-only** change); retire domain bundles; slim `AGENTS.md` /
   move policy to `CONTRIBUTING.md` (D-4). (D-3 + D-1 already shipped in #108.)

A detailed implementation plan follows in the writing-plans step.

## 8. Success criteria

- Every skill + agent resolves to exactly one subject by the `CONTRIBUTING.md` rules.
- Plugin trees are one level (`plugins/<subject>/skills/<leaf>/`); `<subject>:<leaf>` resolves
  under `claude --plugin-dir`.
- `claude plugin install rdl@rdl` installs every subject; `autoremove` cleans up.
- No `<subject>:<subject>` redundant names; existing flat bundles re-sync with no diff mid-migration.
- `marketplace.json` + `plugin.json` are generated and consistency-checked in CI.
- No Codex artifacts introduced by this work.
