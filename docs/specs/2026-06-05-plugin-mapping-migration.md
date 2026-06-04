# Plugin-mapping migration — Phase-3 rollout (subject grouping)

**Date:** 2026-06-05
**Status:** Implemented; all validators green.
**Builds on:** `docs/specs/2026-06-02-plugin-grouping-design.md` (the design + mechanism).

## 1. Problem

The catalog was supposed to publish one Claude Code plugin **per subject**, with skills invoked
as `/<subject>:<facet>` (e.g. `/go:secure`, `/git:send-pr`). Instead it still shipped the old
**domain bundles** (`swe`, `infra`, `informatics`, `dev-tools`, `meta`, plus `rust`, `hooks`,
`lucid`), so skills invoked as `/swe:go-secure`. New skills synced from `nq-rdl/agent-skills` had
no plugin home, so they were invisible to users — blocking the intake of new skills. The repo also
carried Codex/Gemini multi-host packaging remnants, contrary to the "Claude Code only" scope.

## 2. Findings (diagnosis)

- **The mechanism was fully built; the rollout never ran.** PR #108 shipped the registry-owned
  `{source, leaf}` mapping, `sync-plugins.sh` leaf-rename, manifest generation, the `rdl`
  meta-plugin, and the validators — and **closed #101/#102/#109**. That made it look done. But the
  spec's Phase 3 (the content migration) was explicitly left as "registry-only work tracked by
  this spec" and was never executed. The plumbing was perfect; the water was never turned on.
- **The registry still defined 8 domain bundles.** Every skill was a flat string, so the
  invocation namespace was `domain:skill`, not `subject:facet`.
- **9 skills were orphaned** (synced but in no bundle, therefore unpublished): `argo-cd`,
  `bitwarden`, `conventional-commits`, `defuddle`, `obsidian-bases`, `obsidian-cli`,
  `obsidian-markdown`, `pre-commit`, `zod`.
- **`docs/bundles.md` had rotted** — it still advertised the retired domain bundles (the exact
  #100 metadata-rot failure mode, but for a hand-maintained doc instead of a manifest).
- **Codex/Gemini remnants:** a `gemini:` target stanza in `lucid.yaml`; a `.claude/settings.json`
  that registers an `openai-codex` marketplace and enables `codex@openai-codex`; an unreleased
  `Added-…-codex-plugin.yaml` fragment; and "Other hosts (Codex, OpenCode, pi.dev)" prose in
  `README.md` / `docs/ARCHITECTURE.md`.

## 3. Decisions (user responses)

- **Migrate agents now too** (not later): the only way to truly retire the domain bundles, since
  ~30 agents lived inside them. Agents move into subject and workflow plugins.
- **Map all skills today**, including the 9 orphans — unblock the whole catalog in one pass.
- **Approach: big-bang registry rewrite** — replace the domain bundles with subject bundles in one
  coherent change. The diff is large but ~99% generated; the human-review surface is the registry.
- **`hooks` and `lucid` kept as-is** this round (hooks deferred per the user; `lucid` is already a
  clean single-subject MCP plugin — only its dead `gemini:` stanza was dropped).
- **Invocation reality recorded:** agent-only plugins are delegated as subagents (auto-routed by
  `description`), **not** `/<agent>` slash commands. Only skills get the `/<subject>:<facet>` form.

## 4. Solution — what changed

### 4.1 Registry (the only hand-authored change)
- Deleted `registry/bundles/{dev-tools,informatics,infra,meta,swe}.yaml`.
- Authored **33 subject bundles** (+ rewrote `rust`, `lucid`); kept `hooks`. Total **35 bundles**.
- Rewrote the `order:` list in `registry/marketplace.yaml` to the 35 subjects.

### 4.2 Generated / derived (by existing + new scripts)
- `bash scripts/sync-plugins.sh` rebuilt all 35 plugin trees (skills renamed to leaves; agents copied).
- Removed the 5 obsolete `plugins/<domain>/` dirs; created `plugins/playwright/.mcp.json`
  (the Playwright MCP moved off the retired `swe` plugin).
- `python3 scripts/generate_manifests.py .` regenerated 36 `plugin.json` + `marketplace.json`;
  the `rdl` meta-plugin's dependency list auto-tracked to all 35 subjects.

### 4.3 New durability + CI-clarity work
- **`scripts/generate_bundles_doc.py`** generates `docs/bundles.md` from the registry (depends only
  on `registry/`, not churny skill frontmatter); wired `--check` into `validate.yml` so it can't rot.
- **`scripts/sync_pr_body.py`** is now registry-aware: the sync PR body explicitly states the
  workflow **only copies**, and flags every synced-but-unmapped skill under "📦 Action required —
  map these to publish", linking to the new CONTRIBUTING walkthrough. (+4 unit tests.)

### 4.4 Cleanup
- Dropped the `gemini:` stanza from `lucid.yaml`; removed "Other hosts (Codex/OpenCode/pi.dev)"
  prose from `README.md` and `docs/ARCHITECTURE.md` (replaced with "Claude Code is the only target").
- Refreshed stale `swe`/`dev-tools` examples and MCP-binary paths across `AGENTS.md`,
  `ARCHITECTURE.md`, `local-testing.md`, `mcp/README.md`.
- **Deliberately left** `.claude/settings.json` (the `openai-codex` marketplace) and its changelog
  fragment, because they power the maintainer's `codex:rescue` review workflow — flagged for the
  user to confirm removal. *(This is the one open cleanup decision.)*

## 5. Placement map (final)

**Multi-facet skill subjects:** `go` (gh/naming/secure + `go-mcp-expert` agent) · `git`
(changie/conventional-commits/document-release/husky/lefthook/pre-commit/send-pr + `address-comments`)
· `obsidian` (bases/cli/markdown) · `r` (expert + lib-*) · `shiny` (bslib/bslib-theming) · `quarto`
(authoring/alt-text) · `jules` (dispatch/dispatch-creator) · `claude-code` (agent-teams/hook) ·
`skill` (review/report-issue).

**Single-facet skill subjects:** `sops:encrypt` · `pixi:env` · `lychee:check` · `charm-tui:build`
· `starrocks:sql` · `writerside:authoring` · `zod:schema` · `defuddle:extract` · `bitwarden:secrets`
· `ansible:playbook` · `argo-cd:manage` · `rust:explain`.

**Agent-only / workflow subjects:** `terraform` (×3) · `postgres` · `mongodb` · `kubernetes` ·
`arch-linux` · `github-actions` (expert + se-gitops-ci-specialist) · `playwright` (tester + MCP) ·
`review` (×7) · `planning` (×6) · `debug` (×2) · `docs` · `research` (×2). **MCP-only:** `lucid`.
**Hooks-only:** `hooks` (deferred).

## 6. Verification

`check_bundle_refs` · `check_grouping` · `generate_manifests --check` · `generate_bundles_doc
--check` · `check_consistency` · `validate-plugins.sh` · **67 unit tests** — all green. 35 subject
plugins + `worktrunk` + `rdl` = 37 marketplace entries; `rdl` declares all 35 subjects as deps.

## 7. Open questions / follow-ups (tunable)

1. **`.claude/settings.json` (Codex):** remove it (full "Claude Code only" cleanup) or keep it
   (maintainer `codex:rescue` tooling)? Left in place pending the user's call.
2. **Single-facet leaf names** are the most bikesheddable: `argo-cd:manage`, `bitwarden:secrets`,
   `zod:schema`, `starrocks:sql`, `sops:encrypt`. Easy to rename via the `{source, leaf}` map.
3. **`se-gitops-ci-specialist`** is parked in `github-actions`; it spans CI/CD + GitOps and could
   move if a better home emerges.
4. **`hooks` plugin** could fold into `claude-code` when the hooks workstream is picked up.
5. **`skill` subject name** — confirm it reads well vs. e.g. `skills` / `skill-dev`.
