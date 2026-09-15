# SQL Code — development and review actions

Implements issues [#313](https://github.com/nq-rdl/agent-extensions/issues/313) and
[#314](https://github.com/nq-rdl/agent-extensions/issues/314), targeting `release/0.30.0`.
Extends the [original review design](2026-09-15-sql-review-plugin-design.md).

## One plugin, eight actions

`sql-code` owns the complete workflow. Setup carries the shared helpers used by scope,
review, explanation and the record guard. Keeping these together preserves a self-contained
install and avoids cross-plugin helper paths. The registry maps flat canonical
`skills/sql-code-<action>/` directories to these leaves:

| Action | Outcome | Needs `.sqlreview/`? |
|---|---|---|
| `setup` | Initialise config/templates | Creates it |
| `bootstrap` | Human-confirmed scope | Yes |
| `guardrails` | Shared advisory rules and source hierarchy | No |
| `map` | Evidence-backed source/resolver proposal | No |
| `draft` | SQL for settled requirements | No |
| `validate` | Technical findings, evidence and gaps | No |
| `analyse` | Human-confirmed handoff report | Yes |
| `explain` | Analyst walkthrough of reviewed SQL | Yes |

The new development actions support autonomous and co-development modes. Autonomous
work proceeds on explicit requirements and verified facts; missing business decisions
remain questions. Neither mode fabricates human confirmations. Technical validation
does not advance snapshots, clear stale state or replace formal review.

## Shared rules and facts

All cohort development/review actions read the packaged guardrails skill. It carries
the indexed-bound, source-timezone and encounter-mediated clinical-event seed rules
from #313. Source defaults are clues to verify, not permanent field facts. Dataops
`CREATE TABLE` comments are authoritative; query-builder column specs carry the field
metadata and its provenance. Current index definitions establish usable keys.

The sibling metadata work is external to this PR. Skills discover the actual files,
report missing/conflicting evidence, and do not invent paths or a column-spec schema.
No database execution or mechanical SQL enforcement is added.

## Discovery

The team's `forced-eval-hook.sh` now has two advisory paths:

- Explicit requests to use a skill retain the full catalogue.
- Prompts mentioning SQL, cohorts, `CLINICAL_EVENT`, or query-builder resolvers scan
  only the exact `sql-code@rdl-agent-extensions` installation fresh and surface its
  skills, including guardrails. Standalone skills and other plugins are not scanned.

SQL-specific discovery neither consumes nor overwrites the full-catalogue cache and
stays quiet when SQL Code is absent. Other prompts remain silent. This prompt gate is
best-effort discovery: a context-only follow-up such as "make it faster" does not itself
identify SQL. Once an action is loaded, its explicit guardrails read carries the rules
through the task. The hook is advisory and cannot guarantee model compliance.

## Migration

1. Install `sql-code@rdl-agent-extensions`.
2. In every initialized project, run `/sql-code:setup` and complete its SQL Review
   migration: confirm replacement of both default templates, or update only
   `/sql-review:` invocations in customised templates while preserving custom content.
   Plain `init` does not replace existing templates.
3. Rerender affected scope/review Markdown reports from their existing JSON using
   `sqlreview.sh render <slug> scope|review`. Verify active templates and reports
   contain no old invocations; resolve missing JSON or retained old links before
   declaring migration complete.
4. Change saved calls to `/sql-code:<action>`, then remove
   `sql-review@rdl-agent-extensions` so its hooks do not run twice.
   No compatibility alias is shipped.

Keep existing `.sqlreview/` directories, config schema 1, scope/review JSON, snapshots
and history. Preserve template customisations while migrating their invocations.
The `sqlreview.sh` helper name and persisted format stay stable.
Canonical hook names become `sql-code-preflight` and `sql-code-guard`; their configuration
lives in `hooks/sql-code/hooks.json`, and the existing sync script generates all packaged
hook files under `plugins/sql-code/hooks/`.

For users with an installed copy of the team's forced-eval hook, rerun
`/rdl-team:cc-setup` to refresh it. Updating SQL Code alone does not replace a copied
user/project hook. The existing setup flow handles the settings merge.

## Validation

The existing helper and record-guard tests continue against the new namespace, including
unchanged schema/history behaviour. Discovery tests use temporary user configuration and
real packaged skills to cover ordinary SQL prompts, unrelated prompts, absent/new installs,
and separation from the full-catalogue cache. The static SQL smoke test covers all eight
packaged actions. Registry, exposure, generated-copy and skill-spec checks cover packaging.
