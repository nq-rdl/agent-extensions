# awesome-copilot agent review

Review of the 204 agents at <https://github.com/github/awesome-copilot/tree/main/agents> against the 53-skill corpus in `nq-rdl/agent-skills` surfaced through this repo.

- **Inventory date**: 2026-04-21
- **Deliverable**: decision recommendation only — no edits to `skills/`, `plugins/`, or `registry/bundles/`
- **Methodology**: plan at `~/.claude/plans/cozy-knitting-boole.md`

---

## Executive summary

| | Count | Share |
|---|---:|---:|
| Total agents reviewed | 204 | 100% |
| Stage 0 filtered (vendor-locked / proprietary-MCP / pipeline / novelty / migration) | 115 | 56% |
| Tier A — adopt (clean gap, mechanical conversion) | 15 | 7% |
| Tier B — overlap or "skip in favour of another survivor" | 53 | 26% |
| Tier C — deferred (conversion-risk or no-bundle-fit) | 21 | 10% |

**Adoption recommendation:** 15 tier-A adoptions + ~8 tier-B forks where the awesome-copilot content genuinely augments an existing skill. Everything else should be skipped.

**Biggest wins** (decisive gaps closed): Postgres/Mongo DBA guidance, Terraform/k8s/GitOps-CI in `infra`, debug-mode + code-janitor + playwright in `swe`, Go MCP authoring in `dev-tools`, prompt-authoring + agent-governance in `meta`.

**Proposed new bundles** (maintainer decision required):
- `NEW:training` — only if `mentor`, `mentoring-juniors`, `demonstrate-understanding` are adopted as a set; otherwise fold one into `meta`. Named `training` (not `mentoring`) so the bundle is extensible to future onboarding, tutorial, or study-mode skills rather than pinned to Socratic interpersonal-style content only.
- `NEW:product` — only if `prd`, `refine-issue`, `one-shot-feature-issue-planner`, `se-product-manager-advisor` are adopted as a set; otherwise skip all four.

---

## 1. Tier A — adopt

These agents fill a clean gap in the current corpus, pass all three conversion-risk flags (no `vscodeAPI`, no vendor-implicit CLI, no implicit UI state), and map to an existing bundle without conflict.

| # | filename | proposed-bundle | decision | overlap-with | conversion-cost | host-scope | license | upstream-PR-shape | rationale |
|---|---|---|---|---|---|---|---|---|---|
| A1 | `debug.agent.md` | swe | adopt | — | small | claude, gemini, pidev, opencode | MIT + open | `SKILL.md` only | No debug-mode skill exists; applicable across every language in the catalog. |
| A2 | `janitor.agent.md` | swe | adopt | — | small | all | MIT + open | `SKILL.md` only | Universal tech-debt cleanup is absent; pairs with `tdd` refactor guidance. |
| A3 | `playwright-tester.agent.md` | swe | adopt | — | medium (Playwright tool) | all | MIT + open | `SKILL.md` + references | E2E testing gap; Playwright is open-source and host-agnostic. |
| A4 | `adr-generator.agent.md` | swe | adopt | — | small | all | MIT + open | `SKILL.md` only | ADR authoring absent; applicable across bundles. |
| A5 | `context-architect.agent.md` | dev-tools | adopt | — | small | all | MIT + open | `SKILL.md` only | Multi-file change planning — no analogue in corpus. |
| A6 | `go-mcp-expert.agent.md` | dev-tools | adopt | — | small | all | MIT + open | `SKILL.md` only | Repo actively builds Go MCP servers (`mcp/pi-rpc-go`, `mcp/gemini-cli-go`); skill codifies the pattern. |
| A7 | `prompt-builder.agent.md` | meta | adopt | — | small | all | MIT + open | `SKILL.md` only | Prompt engineering missing from the meta bundle. |
| A8 | `postgresql-dba.agent.md` | infra | adopt | — | small | claude (MCP tools), others with degraded features | MIT + open | `SKILL.md` only | No relational DB admin; `starrocks` is analytical-only. |
| A9 | `mongodb-performance-advisor.agent.md` | infra | adopt | — | small | all | MIT + open | `SKILL.md` only | NoSQL admin gap. |
| A10 | `terraform.agent.md` | infra | adopt | — | medium (HCP Terraform MCP) | claude (MCP), gemini | MIT + open | `SKILL.md` + references | Vendor-neutral Terraform workflow; complements `argo-cd`. |
| A11 | `terraform-iac-reviewer.agent.md` | infra | adopt | — | small | all | MIT + open | `SKILL.md` only | State-safety + least-privilege review — companion to A10. |
| A12 | `terratest-module-testing.agent.md` | infra | adopt | — | small | all | MIT + open | `SKILL.md` only | Go-based Terraform testing — fits Go language policy. |
| A13 | `platform-sre-kubernetes.agent.md` | infra | adopt | — | small | all | MIT + open | `SKILL.md` only | k8s SRE gap. |
| A14 | `github-actions-expert.agent.md` | infra | adopt | — | small | all | MIT + open | `SKILL.md` only | CI security (action pinning, OIDC) absent; pairs with `pre-commit`, `husky`, `lefthook`. |
| A15 | `se-gitops-ci-specialist.agent.md` | infra | adopt | — | small | all | MIT + open | `SKILL.md` only | GitOps CI workflows — direct complement to existing `argo-cd` skill. |

---

## 2. Tier B — overlap (evaluate side-by-side)

These survivors either partially overlap an existing skill or duplicate another survivor. Decisions are split across `fork` (worth adopting despite overlap), `skip` (a cleaner survivor wins), and `fork-or-skip` (maintainer judgement needed).

| # | filename | proposed-bundle | decision | overlap-with | conversion-cost | host-scope | license | upstream-PR-shape | rationale |
|---|---|---|---|---|---|---|---|---|---|
| B1 | `wg-code-alchemist.agent.md` | swe | fork | `skills/tdd` (REFACTOR phase is thin) | small | all | MIT + open | `SKILL.md` only | Clean Code/SOLID guidance augments `tdd`'s bare refactor rules. |
| B2 | `wg-code-sentinel.agent.md` | swe | fork | `skills/go-secure` (Go-only) + `skills/sops` | small | all | MIT + open | `SKILL.md` only | Language-agnostic security review — `go-secure` covers Go only. |
| B3 | `se-security-reviewer.agent.md` | swe | skip | `skills/go-secure` + overlaps B2 | — | — | — | — | `go-secure` is stack-focused; B2 covers the broader case more cleanly. |
| B4 | `principal-software-engineer.agent.md` | meta | skip | — | — | — | — | — | Generic senior persona; no differentiable content. |
| B5 | `critical-thinking.agent.md` | meta | fork | `skills/skill-review` (narrower to skill authoring) | small | all | MIT + open | `SKILL.md` only | Cross-cutting verification mode; complements skill-review. |
| B6 | `devils-advocate.agent.md` | meta | skip | overlaps B5 | — | — | — | — | Duplicates critical-thinking intent. |
| B7 | `doublecheck.agent.md` | meta | fork | overlaps B5 | small | all | MIT + open | `SKILL.md` only | Three-layer verification pipeline — structurally distinct from B5. |
| B8 | `gem-critic.agent.md` | meta | skip | overlaps B5/B7 | — | — | — | — | gem-pipeline context reduces clarity; B5/B7 cleaner. |
| B9 | `gem-reviewer.agent.md` | swe | fork | `skills/go-secure` + B2 | small | all | MIT + open | `SKILL.md` only | OWASP + PRD-compliance slant — distinct scope from go-secure. |
| B10 | `gem-debugger.agent.md` | swe | skip | overlaps A1 (`debug.agent.md`) | — | — | — | — | Keep debug.agent.md; gem-pipeline framing unnecessary. |
| B11 | `mentor.agent.md` | NEW:training | fork | — | small | all | MIT + open | `SKILL.md` only | No training bundle exists; bundle decision gates adoption. |
| B12 | `mentoring-juniors.agent.md` | NEW:training | fork | overlaps B11 | small | all | MIT + open | `SKILL.md` only | Socratic/PEAR-loop variant; decide one. |
| B13 | `demonstrate-understanding.agent.md` | NEW:training | fork | overlaps B11 | small | all | MIT + open | `SKILL.md` only | Question-driven understanding check — complements mentor. |
| B14 | `repo-architect.agent.md` | dev-tools | fork | `skills/cc-agent-teams` (different scope) | small | all | MIT + open | `SKILL.md` only | Bootstraps agentic repos — cc-agent-teams is about runtime coordination, not scaffolding. |
| B15 | `meta-agentic-project-scaffold.agent.md` | dev-tools | skip | overlaps B14 | — | — | — | — | Pick B14; this is VS Code-flavoured. |
| B16 | `droid.agent.md` | dev-tools | skip | `skills/jules`, `skills/dispatch` | — | — | — | — | Another dispatch backend; dispatch skill covers multi-backend routing. |
| B17 | `context7.agent.md` | dev-tools | fork-or-skip | — | medium (+MCP config) | claude only (MCP) | MIT + open | `SKILL.md` + `.mcp.json` guidance | Requires accepting context7 MCP; maintainer decision on MCP vendor surface. |
| B18 | `arch-linux-expert.agent.md` | infra | fork | `skills/ansible` (broader) | small | all | MIT + open | `SKILL.md` only | pacman/rolling-release specifics complement Ansible automation. |
| B19 | `debian-linux-expert.agent.md` | infra | fork-or-skip | overlaps B18 | small | all | MIT + open | `SKILL.md` only | Adopt all four distros or just one — decide as a pack. |
| B20 | `fedora-linux-expert.agent.md` | infra | fork-or-skip | overlaps B18 | small | all | MIT + open | `SKILL.md` only | Same. |
| B21 | `centos-linux-expert.agent.md` | infra | fork-or-skip | overlaps B18 | small | all | MIT + open | `SKILL.md` only | Same. |
| B22 | `tdd-red.agent.md` | swe | skip | `skills/tdd-team-workflow` (protocol) + `skills/tdd` (principles) | — | — | — | — | Contract mismatch with tdd-team-workflow phase protocol — see `docs/tdd-workflow-review.md` § 2.2. GitHub-issue-coupled, user-confirmation-gated, no status-token output. |
| B23 | `tdd-green.agent.md` | swe | skip | `skills/tdd-team-workflow` (protocol) + `skills/tdd` (principles) | — | — | — | — | Same contract mismatch as B22. Triangulation/"fake it till you make it" prose is novel but thin. |
| B24 | `tdd-refactor.agent.md` | swe | skip-with-salvage | `skills/tdd-team-workflow` (protocol) + `skills/tdd` (principles) | small (checklist extraction) | all | MIT + open | `SKILL.md` diff | Same contract mismatch. OWASP refactor security checklist (~8 items) is the one salvageable piece — see `docs/tdd-workflow-review.md` § 3 Option B. |
| B25 | `implementation-plan.agent.md` | dev-tools | skip | overlaps B26/B27/B28 | — | — | — | — | Planning-mode duplication. |
| B26 | `planner.agent.md` | dev-tools | skip | overlaps B27 | — | — | — | — | Same. |
| B27 | `plan.agent.md` | dev-tools | fork | — | small | all | MIT + open | `SKILL.md` only | Pick this as the canonical plan-mode skill. |
| B28 | `task-planner.agent.md` | dev-tools | skip | overlaps B27; Azure-flavoured | — | — | — | — | B27 is cleaner. |
| B29 | `blueprint-mode.agent.md` | dev-tools | skip | overlaps B27 | — | — | — | — | Structured workflow already covered by plan.agent.md + dispatch. |
| B30 | `refine-issue.agent.md` | NEW:product | fork | — | small | all | MIT + open | `SKILL.md` only | Requirements refinement; no product bundle exists. |
| B31 | `one-shot-feature-issue-planner.agent.md` | NEW:product | fork | overlaps B30 | small | all | MIT + open | `SKILL.md` only | End-to-end issue planner; decide one with B30. |
| B32 | `prd.agent.md` | NEW:product | fork | — | small | all | MIT + open | `SKILL.md` only | PRD generation — missing from catalog. |
| B33 | `address-comments.agent.md` | dev-tools | fork | — | small | all | MIT + open | `SKILL.md` only | PR review-comment addresser — universal. |
| B34 | `tech-debt-remediation-plan.agent.md` | swe | skip | overlaps A2 (`janitor`) | — | — | — | — | Janitor covers this space. |
| B35 | `specification.agent.md` | meta | skip | overlaps B32 | — | — | — | — | Spec docs subset of PRD. |
| B36 | `rug-orchestrator.agent.md` | dev-tools | skip | `skills/cc-agent-teams`, `skills/dispatch` | — | — | — | — | Orchestration already covered. |
| B37 | `software-engineer-agent-v1.agent.md` | swe | skip | — | — | — | — | — | Generic SWE persona; no differentiation. |
| B38 | `swe-subagent.agent.md` | swe | skip | overlaps B37 | — | — | — | — | Same. |
| B39 | `devops-expert.agent.md` | infra | skip | `skills/ansible` + `skills/argo-cd` + A14 | — | — | — | — | Too broad; our bundle covers the slices already. |
| B40 | `hlbpa.agent.md` | swe | fork | overlaps B41/B42/B43 | small | all | MIT + open | `SKILL.md` only | High-level architecture + legacy review; pick this as canonical. |
| B41 | `project-architecture-planner.agent.md` | swe | skip | overlaps B40 | — | — | — | — | Pick B40. |
| B42 | `arch.agent.md` | swe | skip | overlaps B40 | — | — | — | — | Generic cloud architect. |
| B43 | `se-system-architecture-reviewer.agent.md` | swe | skip | overlaps B40 | — | — | — | — | Well-Architected framework content subset of B40. |
| B44 | `api-architect.agent.md` | swe | fork | — | small | all | MIT + open | `SKILL.md` only | API design mentoring — distinct from B40's system-level scope. |
| B45 | `se-technical-writer.agent.md` | dev-tools | fork | `skills/writerside`, `skills/document-release` | small | all | MIT + open | `SKILL.md` only | Broader than IDE-specific writerside; complements document-release. |
| B46 | `qa-subagent.agent.md` | swe | skip | overlaps A3 direction | — | — | — | — | QA subagent persona; too thin vs. playwright-tester. |
| B47 | `research-technical-spike.agent.md` | dev-tools | fork | — | small | all | MIT + open | `SKILL.md` only | Structured spike research — absent. |
| B48 | `task-researcher.agent.md` | dev-tools | skip | overlaps B47 | — | — | — | — | Azure-flavoured; B47 cleaner. |
| B49 | `se-responsible-ai-code.agent.md` | meta | fork | — | small | all | MIT + open | `SKILL.md` only | Responsible-AI guardrails — absent; high value as agent count grows. |
| B50 | `agent-governance-reviewer.agent.md` | meta | fork | — | small | all | MIT + open | `SKILL.md` only | Agent-system safety review — complements B49. |
| B51 | `se-product-manager-advisor.agent.md` | NEW:product | fork | — | small | all | MIT + open | `SKILL.md` only | PM guidance — completes product bundle if adopted. |
| B52 | `prompt-engineer.agent.md` | meta | skip | overlaps A7 (`prompt-builder`) | — | — | — | — | prompt-builder has cleaner scope. |
| B53 | `expert-cpp-software-engineer.agent.md` | swe | skip | — | — | — | — | — | C++ not in stack. |

---

## 3. Tier C — deferred

No ledger depth. Each agent carries one of two flags: `IDE-coupled` (fails conversion flag 1–3) or `no-bundle-fit` (survives conversion but lands outside any existing or proposed bundle).

| # | filename | flag |
|---|---|---|
| C1 | `accessibility.agent.md` | IDE-coupled (vscodeAPI in tools) |
| C2 | `accessibility-runtime-tester.agent.md` | IDE-coupled (openSimpleBrowser, VS Code) |
| C3 | `custom-agent-foundry.agent.md` | IDE-coupled (VS Code tool suite in body) |
| C4 | `devtools-regression-investigator.agent.md` | no-bundle-fit (Chrome DevTools MCP, frontend-web focus) |
| C5 | `frontend-performance-investigator.agent.md` | no-bundle-fit (same) |
| C6 | `markdown-accessibility-assistant.agent.md` | no-bundle-fit (narrow markdown-a11y) |
| C7 | `java-mcp-expert.agent.md` | no-bundle-fit (Java not in stack) |
| C8 | `kotlin-mcp-expert.agent.md` | no-bundle-fit |
| C9 | `php-mcp-expert.agent.md` | no-bundle-fit |
| C10 | `ruby-mcp-expert.agent.md` | no-bundle-fit |
| C11 | `rust-mcp-expert.agent.md` | no-bundle-fit |
| C12 | `swift-mcp-expert.agent.md` | no-bundle-fit |
| C13 | `typescript-mcp-expert.agent.md` | no-bundle-fit (TypeScript banned by CLAUDE.md policy) |
| C14 | `python-mcp-expert.agent.md` | no-bundle-fit (MCP policy is Go-only per CLAUDE.md) |
| C15 | `clojure-interactive-programming.agent.md` | no-bundle-fit |
| C16 | `spark-performance.agent.md` | no-bundle-fit (PySpark) |
| C17 | `openapi-to-application.agent.md` | no-bundle-fit (codegen direction unclear) |
| C18 | `se-ux-ui-designer.agent.md` | no-bundle-fit (no UX bundle) |
| C19 | `search-ai-optimization-expert.agent.md` | no-bundle-fit (SEO/GEO out of scope) |
| C20 | `technical-content-evaluator.agent.md` | no-bundle-fit (training material reviewer, narrow) |
| C21 | `simple-app-idea-generator.agent.md` | no-bundle-fit (brainstorming persona) |

---

## 4. Stage 0 rejection index

All 115 agents dropped before triage. Listed verbatim for auditability.

### 4.1 Vendor-locked (52)

`CSharpExpert.agent.md`, `WinFormsExpert.agent.md`, `aem-frontend-specialist.agent.md`, `azure-iac-exporter.agent.md`, `azure-iac-generator.agent.md`, `azure-logic-apps-expert.agent.md`, `azure-policy-analyzer.agent.md`, `azure-principal-architect.agent.md`, `azure-saas-architect.agent.md`, `azure-verified-modules-bicep.agent.md`, `azure-verified-modules-terraform.agent.md`, `bicep-implement.agent.md`, `bicep-plan.agent.md`, `code-tour.agent.md`, `csharp-dotnet-janitor.agent.md`, `csharp-mcp-expert.agent.md`, `declarative-agents-architect.agent.md`, `defender-scout-kql.agent.md`, `dotnet-maui.agent.md`, `dotnet-self-learning-architect.agent.md`, `dotnet-upgrade.agent.md`, `drupal-expert.agent.md`, `electron-angular-native.agent.md`, `expert-dotnet-software-engineer.agent.md`, `expert-nextjs-developer.agent.md`, `expert-react-frontend-engineer.agent.md`, `insiders-a11y-tracker.agent.md`, `kusto-assistant.agent.md`, `laravel-expert-agent.agent.md`, `mcp-m365-agent-expert.agent.md`, `microsoft-study-mode.agent.md`, `microsoft_learn_contributor.agent.md`, `ms-sql-dba.agent.md`, `nuxt-expert.agent.md`, `pimcore-expert.agent.md`, `power-bi-data-modeling-expert.agent.md`, `power-bi-dax-expert.agent.md`, `power-bi-performance-expert.agent.md`, `power-bi-visualization-expert.agent.md`, `power-platform-expert.agent.md`, `power-platform-mcp-integration-expert.agent.md`, `python-notebook-sample-builder.agent.md`, `salesforce-apex-triggers.agent.md`, `salesforce-aura-lwc.agent.md`, `salesforce-expert.agent.md`, `salesforce-flow.agent.md`, `salesforce-visualforce.agent.md`, `shopify-expert.agent.md`, `terraform-azure-implement.agent.md`, `terraform-azure-planning.agent.md`, `vuejs-expert.agent.md`, `winui3-expert.agent.md`.

### 4.2 Proprietary-MCP-dependent (23)

`amplitude-experiment-implementation.agent.md`, `apify-integration-expert.agent.md`, `atlassian-requirements-to-jira.agent.md`, `cast-imaging-impact-analysis.agent.md`, `cast-imaging-software-discovery.agent.md`, `cast-imaging-structural-quality-advisor.agent.md`, `comet-opik.agent.md`, `diffblue-cover.agent.md`, `dynatrace-expert.agent.md`, `elasticsearch-observability.agent.md`, `jfrog-sec.agent.md`, `launchdarkly-flag-cleanup.agent.md`, `lingodotdev-i18n.agent.md`, `monday-bug-fixer.agent.md`, `neo4j-docker-client-generator.agent.md`, `neon-migration-specialist.agent.md`, `neon-optimization-analyzer.agent.md`, `octopus-deploy-release-notes-mcp.agent.md`, `pagerduty-incident-responder.agent.md`, `reepl-linkedin.agent.md`, `scientific-paper-research.agent.md`, `stackhawk-security-onboarding.agent.md`, `taxcore-technical-writer.agent.md`.

### 4.3 Pipeline-ensemble (31)

React 18 migration (6): `react18-auditor.agent.md`, `react18-batching-fixer.agent.md`, `react18-class-surgeon.agent.md`, `react18-commander.agent.md`, `react18-dep-surgeon.agent.md`, `react18-test-guardian.agent.md`.

React 19 migration (5): `react19-auditor.agent.md`, `react19-commander.agent.md`, `react19-dep-surgeon.agent.md`, `react19-migrator.agent.md`, `react19-test-guardian.agent.md`.

Polyglot test pipeline (8): `polyglot-test-builder.agent.md`, `polyglot-test-fixer.agent.md`, `polyglot-test-generator.agent.md`, `polyglot-test-implementer.agent.md`, `polyglot-test-linter.agent.md`, `polyglot-test-planner.agent.md`, `polyglot-test-researcher.agent.md`, `polyglot-test-tester.agent.md`.

gem-pipeline non-cherry-picked (12): `gem-orchestrator.agent.md`, `gem-planner.agent.md`, `gem-researcher.agent.md`, `gem-implementer.agent.md`, `gem-implementer-mobile.agent.md`, `gem-designer.agent.md`, `gem-designer-mobile.agent.md`, `gem-browser-tester.agent.md`, `gem-mobile-tester.agent.md`, `gem-documentation-writer.agent.md`, `gem-devops.agent.md`, `gem-code-simplifier.agent.md`.

(The three cherry-picked gem-* agents — `gem-critic`, `gem-reviewer`, `gem-debugger` — appear in tier B, not here.)

### 4.4 Novelty / persona (5)

`gilfoyle.agent.md`, `ember.agent.md`, `Thinking-Beast-Mode.agent.md`, `Ultimate-Transparent-Thinking-Beast-Mode.agent.md`, `linkedin-post-writer.agent.md`.

### 4.5 Migration-one-shot (4)

`arm-migration.agent.md`, `oracle-to-postgres-migration-expert.agent.md`, `github-actions-node-upgrade.agent.md`, `modernization.agent.md`.

---

## 5. Next steps

Tier-A adoption ordered by value-per-PR:

1. **`nq-rdl/agent-skills`** PRs (one SKILL.md per PR):
   1. `postgresql-dba` → infra (A8)
   2. `mongodb-performance-advisor` → infra (A9)
   3. `terraform` → infra (A10) — ships with `references/`
   4. `terraform-iac-reviewer` → infra (A11)
   5. `platform-sre-kubernetes` → infra (A13)
   6. `github-actions-expert` → infra (A14)
   7. `se-gitops-ci-specialist` → infra (A15)
   8. `terratest-module-testing` → infra (A12)
   9. `debug` → swe (A1)
   10. `janitor` → swe (A2)
   11. `playwright-tester` → swe (A3) — ships with `references/`
   12. `adr-generator` → swe (A4)
   13. `go-mcp-expert` → dev-tools (A6)
   14. `context-architect` → dev-tools (A5)
   15. `prompt-builder` → meta (A7)

2. **`nq-rdl/agent-extensions`** follow-up (single PR after submodule bump):
   - Bump `skills/` submodule pin to include all 15 new skills
   - Add 15 symlinks under `plugins/<bundle>/skills/`
   - Update `registry/bundles/{swe,infra,dev-tools,meta}.yaml` with the new skill names
   - CI runs `scripts/validate-plugin-hooks.sh` and `validate.yml` to confirm symlinks resolve

3. **Tier-B decisions requiring maintainer input before adoption**:
   - [ ] Pick one of `mentor` / `mentoring-juniors` / `demonstrate-understanding` OR commit to a `NEW:training` bundle with all three. Bundle is named `training` (not `mentoring`) to remain extensible to future onboarding / tutorial / study-mode skills.
   - [ ] Pick one of `prd` / `refine-issue` / `one-shot-feature-issue-planner` OR commit to a `NEW:product` bundle with all three + `se-product-manager-advisor`.
   - [ ] Decide Linux-distro pack: adopt one (recommend `arch-linux-expert`) or all four.
   - [ ] Decide whether to accept the `context7` MCP vendor surface (B17).
   - [ ] Pick canonical refactor/review skills from `wg-code-alchemist` (B1), `wg-code-sentinel` (B2), `gem-reviewer` (B9) — recommend all three as distinct scopes.
   - [ ] Pick canonical architect skill: `hlbpa` (B40) + `api-architect` (B44).
   - [ ] Pick canonical plan-mode skill: `plan.agent.md` (B27) — others skip.
   - [ ] Adopt `critical-thinking` (B5) + `doublecheck` (B7) alongside existing skill-review, or pick one.
   - [ ] Adopt `se-responsible-ai-code` (B49) + `agent-governance-reviewer` (B50) as a pair for `meta`.
   - [ ] Adopt `address-comments` (B33), `research-technical-spike` (B47), `se-technical-writer` (B45) as independent `dev-tools` additions.
   - [ ] **Option B (tdd-refactor salvage)** — extract the OWASP refactor security checklist from `tdd-refactor.agent.md` into `skills/go-secure/` or a new checklist skill. See `docs/tdd-workflow-review.md` § 3.
   - [ ] **Future project (not part of this review)** — consider authoring net-new `tdd-red-team` / `tdd-green-team` / `tdd-refactor` phase-agent skills that implement the tdd-team-workflow protocol (5-field input, `DONE|<phase>` token output). See `docs/tdd-workflow-review.md` § 3 Option C.

4. **Conversion risk reminder** for every adoption PR:
   - Strip VS Code-specific `tools:` frontmatter (e.g. `codebase`, `vscodeAPI`, `openSimpleBrowser`) before vendoring.
   - Rewrite "the currently open file" / "selected text" references into explicit `$ARGUMENTS` or tool-invocation prose.
   - Re-license under the MIT header already used in the submodule; verify awesome-copilot's upstream license is compatible (it is — MIT).
   - Add `metadata.repo: https://github.com/nq-rdl/agent-skills` to the frontmatter per corpus convention.

---

## Appendix — methodology traceability

- Stage 0 filter rules and tier definitions: `~/.claude/plans/cozy-knitting-boole.md`.
- Skill authoring conventions: `CLAUDE.md` (§ Language Policy, § How skills flow into plugins), `docs/ARCHITECTURE.md` (lines 439, 449–457).
- Canonical skill examples referenced during triage: `skills/tdd/SKILL.md` (short), `skills/ansible/SKILL.md` (long), `skills/cc-agent-teams/SKILL.md` (disambiguation from gem-*), `skills/tdd-team-workflow/SKILL.md` (disambiguation from tdd-red/green/refactor).
- Source inventory fetched from `https://api.github.com/repos/github/awesome-copilot/contents/agents?ref=main` on 2026-04-21.
