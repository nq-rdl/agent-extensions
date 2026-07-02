# Plugin consolidation plan — 34 → 29 subjects

**Status:** ratified 2026-07-02 (bundling review); execution pending.
**Scope:** one breaking (major) release. All grouping changes are registry-only —
no canonical `skills/` or `agents/` content moves; deletions are recoverable from
git history.

## Why

The bundling review found the architecture sound — the registry
(`registry/bundles/*.yaml`) is the layer that absorbs renames and regroupings, so
the breaking-change surface is exactly: plugin rename/merge/split, leaf rename,
and moving content between plugins. The remaining risk sat in a handful of
workflow-bundle edges: an artificial `gh` / `github-actions` split, four
generic single-word plugin names, near-empty single-purpose bundles, and
undocumented agent cross-listing. This plan clears all of them in **one** major
release instead of dribbling breaks across several.

## Decisions

| Bundle | Decision | Disposition |
|---|---|---|
| `github-actions` | **Merge into `gh`** | `gh` gains `github-actions-expert` (home; stays guest in `go`) and `se-gitops-ci-specialist` (guest — home `argo-cd`). `gh` description/keywords absorb Actions CI/CD. |
| `/gh:go` (skill `go-gh`) | **Rename leaf to `actions-go`** | Registry mapping becomes `{source: go-gh, leaf: actions-go}` → `/gh:actions-go`. The plain `actions` leaf stays reserved for a future generic Actions skill. CONTRIBUTING §2's "one sanctioned exception" note is rewritten for the new leaf. |
| `hooks` | **Retire** | Only payload is the forced-eval hook. Single source becomes `skills/cc-setup/assets/forced-eval-hook.sh` (already byte-identical; `/rdl-team:cc-setup` is the real delivery vehicle). Root `hooks/forced-eval-hook.sh` and `plugins/hooks/` are deleted. `/claude-code:hook` remains the generic create/update/audit surface for Claude Code hooks. |
| `skill` | **Fold into `claude-code`** | Skills become `/claude-code:skill-audit`, `/claude-code:skill-review`, `/claude-code:skill-report-issue`; the `skill-auditor` agent and `skill-audit-nudge` hook move too. |
| `research` | **Retire** | `research-technical-spike` → `planning` (a spike is a planning activity); `prompt-builder` → `claude-code` (prompt engineering for Claude). |
| `review` | **Retire** | The team consumes a code-review plugin from an external marketplace. `wg-code-sentinel` and `terraform-iac-reviewer` survive untouched in their homes (`go`, `terraform`) — the review listing was only a guest slot. Five agents are homed **only** here and are deleted from the catalog: `wg-code-alchemist`, `critical-thinking`, `doublecheck`, `agent-governance-reviewer`, `se-responsible-ai-code`. Note: `critical-thinking`/`doublecheck` are fact-checkers rather than code reviewers, so the external plugin does not replace them — rehoming either is a one-line registry change later if wanted. |
| `docs` | **Rename to `tech-writing`** | Bundle YAML (`id`, `pluginName`, `displayName`), marketplace `order:` entry. |
| `debug`, `planning` | **Keep** | Names are generic but the alternatives are worse; contents are coherent. `planning` gains the spike agent. |

## Cross-listing policy (new CONTRIBUTING §5 text)

Agent reuse across bundles is deliberate and stays — but documented:

- Every agent has exactly **one home** (its subject bundle, per grouping rules 1–4).
- **Guest listings** in other bundles are allowed when the agent is load-bearing
  for that bundle's job; keep them rare and annotate in the YAML:
  `# guest — home: <bundle>`.
- Docs and hooks always reference the home-qualified name, so guest listings can
  be added or dropped without breaking references.

Current guest listings after this plan: `wg-code-sentinel` (home `go`),
`github-actions-expert` (home `gh`, guest `go`), `se-gitops-ci-specialist`
(home `argo-cd`, guest `gh`).

## Breaking-change inventory (changelog migration notes)

- **Removed install ids:** `github-actions@rdl`, `hooks@rdl`, `skill@rdl`,
  `research@rdl`, `review@rdl`.
- **Renamed install id:** `docs@rdl` → `tech-writing@rdl`.
- **Invocation changes:** `/gh:go` → `/gh:actions-go`;
  `/skill:audit|review|report-issue` → `/claude-code:skill-audit|skill-review|skill-report-issue`.
- **Agents removed:** `wg-code-alchemist`, `critical-thinking`, `doublecheck`,
  `agent-governance-reviewer`, `se-responsible-ai-code`.
- The `rdl` meta-plugin dependency list regenerates automatically; meta installs
  reinstall the new set.
- Changie kinds `Removed` + `Changed` auto-bump the release to **major**.

## Execution checklist

All commands via pixi (see AGENTS.md → Setup commands).

1. Registry edits: `gh.yaml` (merge `github-actions`, `actions-go` leaf, guest
   comments), `claude-code.yaml` (skill-* leaves, `skill-auditor`,
   `skill-audit-nudge`, `prompt-builder`), `planning.yaml`
   (`research-technical-spike`), rename `docs.yaml` → `tech-writing.yaml`;
   delete `github-actions.yaml`, `hooks.yaml`, `skill.yaml`, `research.yaml`,
   `review.yaml`; update `marketplace.yaml` `order:`.
2. Delete the five review-only canonical agents (`agents/<name>/`) and the
   duplicate `hooks/forced-eval-hook.sh`.
3. `pixi run bash scripts/sync-plugins.sh`; `git rm -r` the five stale
   `plugins/` trees; rename/regenerate `plugins/tech-writing/`.
4. `pixi run python3 scripts/generate_manifests.py .` and
   `pixi run python3 scripts/generate_bundles_doc.py .`
5. Docs: CONTRIBUTING §2 exception rewrite + §5 cross-listing policy;
   AGENTS.md `/skill:audit` reference → `/claude-code:skill-audit`, and the
   `plugins/hooks/hooks/hooks.json` example path in the build block.
6. Changie fragments (`Removed` + `Changed`) with the migration notes above.
7. Full check suite (CONTRIBUTING §"Packaging a new skill" step 6) + unit tests.

## Rejected alternatives

- **Rename `review` → `code-review`:** rejected — the name collides with the
  external code-review plugin the team already uses; retiring removes the
  duplication instead of rebranding it.
- **Agent + skill minimum per plugin:** rejected — an agent's `description`
  frontmatter is already the routing surface; a stub skill fails the
  non-inferable-delta rule and doubles maintenance. Where a user-invocable entry
  point is wanted, add a **command** (registry `prompts:` is reserved for this),
  not a stub skill.
- **Author content under `plugins/<name>/` directly:** rejected — it would force
  real duplicated copies for shared agents (drift) and bake grouping into the
  filesystem. This whole consolidation touches only registry YAML and docs; that
  is the property worth keeping.
