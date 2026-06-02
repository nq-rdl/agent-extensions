# Design spec — plugin grouping by subject (umbrella for #101 + #102)

**Date:** 2026-06-02
**Status:** Decisions locked below; ready for an implementation plan.
**Scope:** **Claude Code only.** Codex / multi-host packaging is explicitly **deferred** (see §6).

**Relationship to the issues:**

| Item | Role | State |
|---|---|---|
| [#101](https://github.com/nq-rdl/agent-extensions/issues/101) | **Strategy** — retire domain bundles, regroup by subject | open → close on completion |
| [agent-skills#118](https://github.com/nq-rdl/agent-skills/pull/118) | **Phase 1 mechanism (source side)** — upstream grouping contract + validators | PR open, **not merged**; upstream still flat |
| [#102](https://github.com/nq-rdl/agent-extensions/issues/102) | **Phase 2 mechanism (packaging side)** — `agent-extensions` sync + packaging | open → close on completion |
| **This spec** | **Umbrella** — apply #101's policy via the #118/#102 mechanism | — |

Together these meet **both** #101 and #102: the policy (this spec + `CONTRIBUTING.md`) rides on
the mechanism (#102/#118), as one phased migration.

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

## 3. Mechanism — the #102/#118 grouping contract (adopted as-is)

- **Upstream:** flat `skills/<skill>/SKILL.md` **or** grouped `skills/<group>/<leaf>/SKILL.md`
  (one level; group folder has no direct `SKILL.md`). **Group folder == plugin name**; **leaf ==
  facet**; frontmatter **`name:` == leaf**.
- **Registry:** bundle sets `pluginName: <group>`; members path-qualified as `<group>/<leaf>`.
- **Sync (`sync-plugins.sh`):** copies `skills/<group>/<leaf>/` → `plugins/<group>/skills/<leaf>/`,
  **dropping the `<group>/` prefix** → plugin tree stays one level deep.
- **Claude Code invokes `<group>:<leaf>`.**
- **Validators** (across #118 + #102): `name:`==leaf · group==`pluginName` · no dup leaf per
  bundle · `pluginName` unique across bundles · flat skill never descended into. (#102 MF-1/MF-3
  + #118 source-side checks.)

The facet name is the upstream leaf folder, chosen once — **no sync-time rename, no extra
validation tooling from us.** To get `obsidian:bases`: `skills/obsidian/bases/SKILL.md`,
`name: bases`. To get `go:gh`: move `skills/go-gh/` → `skills/go/gh/`, `name: gh`.

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

**Update #101 and #102 now** with this consolidated plan; **close both on completion** (the work
satisfies both). Link this spec from each.

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

1. **Phase 1 — agent-skills#118 (source):** land upstream contract + validators; pilot one group.
   **Must merge + release first.**
2. **Phase 2 — #102 (packaging):** `sync-plugins.sh` leaf handling, grouped `sync-skills.yml`,
   `validate.yml` MF-1/MF-3, first grouped bundle. Verify flat bundles re-sync **no-diff**
   (backward compatible → incremental migration, no big-bang).
3. **Phase 3 — #101 rollout (this spec):** migrate subjects per §5; add manifest generation (D-3)
   + the `rdl` meta-plugin (D-1); retire domain bundles; slim `AGENTS.md` / move policy to
   `CONTRIBUTING.md` (D-4); update + close #101/#102 (D-5).

A detailed implementation plan follows in the writing-plans step.

## 8. Success criteria

- Every skill + agent resolves to exactly one subject by the `CONTRIBUTING.md` rules.
- Plugin trees are one level (`plugins/<subject>/skills/<leaf>/`); `<subject>:<leaf>` resolves
  under `claude --plugin-dir`.
- `claude plugin install rdl@rdl` installs every subject; `autoremove` cleans up.
- No `<subject>:<subject>` redundant names; existing flat bundles re-sync with no diff mid-migration.
- `marketplace.json` + `plugin.json` are generated and consistency-checked in CI.
- No Codex artifacts introduced by this work.
