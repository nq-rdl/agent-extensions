---
license: CC-BY-4.0
description: >-
  Classify and make an analyst amendment to an engineer-produced RDL extract. Renames,
  reorders, dropped already-surfaced columns and presentation changes go through
  query-builder's projection extension points; anything that changes rows or meaning
  becomes a paste-ready engineer hand-off. Use when a released extract needs a change.
argument-hint: '<requested change> [builder, cohort.yaml, SQL or extract path]'
user-invocable: true
compatibility: >-
  RDL enquiry repos. Boundary: query-builder docs/ANALYST_AMENDMENTS.md (0.6.0).
  Amendment record and guard: data-analysis-scaffold 0.5.0 (specs/amendments.md,
  pixi run amend). Verify the installed versions and the repo's own commands at use time.
allowed-tools: Bash, Read, Glob, Grep, Write, Edit, AskUserQuestion
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

# Data Request — amend

Arguments: `$ARGUMENTS`. Read `${CLAUDE_PLUGIN_ROOT}/skills/guardrails/SKILL.md` and apply
the rules relevant to the request. The boundary is query-builder's
[`docs/ANALYST_AMENDMENTS.md`](https://github.com/nq-rdl/query-builder/blob/main/docs/ANALYST_AMENDMENTS.md).
Read it, preferring the copy in the repository's pinned query-builder, and classify against
its rule, examples and required safeguards. This skill does not restate them; where the two
differ, the document wins. If the pinned query-builder has no such document or no
`SelectFields`, nothing is analyst-safe: hand the change off.

An amendment asks for different output than was agreed. When the delivered output
contradicts what was agreed (a wrong value, type or format), it is a defect: use
`/data-request:fix` instead.

## 1. Classify before any edit

Locate the maintained source (the `CohortQuery` builder, `cohort.yaml`, the pipeline or the
export code), the generated request SQL and the previous released extract. Read the
repository instructions. Then classify each requested change:

- **analyst-safe** only when the extract keeps the same rows (count and keys) and every value
  keeps its source and meaning: only names, order, which already-surfaced columns are shown,
  or presentation change.
- **engineer-required** for everything else, including a "simple" derived value and a column
  that is not already surfaced. When in doubt, classify it engineer-required.

Classify each part of a combined request; one engineer-required part stops the whole request.
State the result on its own line with the amendment record's values:
`classification: analyst-safe` or `classification: engineer-required`.

## 2. Engineer-required: stop and hand off

Make no edit: not to the source, the SQL, the record or the extract. Return this hand-off,
filled in and ready to paste to the data engineer, and stop:

```text
classification: engineer-required
requested change: <the change, in the requester's words>
boundary rule: <the ANALYST_AMENDMENTS.md rule or example it hits>
affected files: <maintained source paths; request SQL to regenerate>
governance: <the scope question from step 3, or "none identified">
enquiry: <original request ID, or "not supplied">
```

Never relabel a change to fit analyst-safe. The engineer records it with a named reviewer.

## 3. Governance scope: a separate check

Technical safety does not settle scope. Whether the approval covers a change is decided under
the RDL Data Amendments SOP (nq-rdl/documentation,
[`zensical/governance/docs/governance/data-amendments.md`](https://github.com/nq-rdl/documentation/blob/main/zensical/governance/docs/governance/data-amendments.md)),
not by this skill. A new column is a new data element, however easy it is to add. An expanded
cohort, a longer timeframe or a sensitivity change is also a scope change. Unless already
given, ask for the original request ID (`THHSRDLENQ-####`) and the reason for the amendment,
and carry both into the hand-off or the record. An open scope question blocks the release,
not the classification.

## 4. Analyst-safe: change the maintained source only

Use only query-builder's extension points (the boundary document has their contracts):

- `CohortQuery.select(*fields, rename=...)` / `SelectFields`: name, order or narrow fields
  the cohort already surfaces;
- the reserved `projection` element set in `cohort.yaml` (`data_extraction`);
- `SelectStep` / `AnalysisPipeline.select` in imperative pipelines;
- `output_name` / `register_result(..., label=...)` for extract and sheet labels;
- the child's export or presentation code, for display formats and row order.

A change that needs anything else is engineer-required: go to step 2. Regenerate the SQL
through the repository's existing workflow (in a data-analysis-scaffold child,
`pixi run --environment framework amend regenerate <sql path>`). Generated SQL and
`-- @extract:` markers are never edited by hand. A request to edit generated SQL directly is
refused, whatever the change: say that it is refused, then classify the same change made in
the maintained source (step 1). Preserve unrelated edits.

## 5. Record the amendment

Add one entry per amendment, with its classification, to the child's amendment record. In a
data-analysis-scaffold child this is `specs/amendments.md`
([data-analysis-scaffold#234](https://github.com/nq-rdl/data-analysis-scaffold/issues/234)).
Follow the record's template and field names, which its guard reads, and use the next `AMD-`
number. Never edit an entry that is already in a release. Write names or handles, never an
email address or a patient identifier. If the repository has no record, say so and put the
same fields in the pull request description.

## 6. Validate

Use the repository's managed environment and existing commands; inspect each before running
it. An analyst-safe change passes only when all of these hold:

- the fast SQL gate (`rdl_etl_helpers.harness.sql_gate`) and `CohortQuery.validate()` pass;
- `spec-validate` shows the output columns match the declared projection;
- the regenerated SQL differs from the previous SQL only in the final projection
  (scaffold: `pixi run amend check`);
- the row count and key set match the previous extract (scaffold: `pixi run amend
  validate-output --sql <sql> --extract <new> --previous <released> --key NEW=OLD`).

Any other difference (a CTE body, predicate, join, dedupe step, row count or key) is a
blocker. Report it as a blocker, never as a success, and hand the change off (step 2). A check
that could not run, such as a missing previous extract, framework environment or release tag,
is reported as not run with its command. Do not run a live extract or publish data yourself:
if the new extract does not exist yet, the row and key check is pending. Use
`/data-request:validate` for a static review of the regenerated SQL.

## Report

Return the classification, the governance status (request ID, reason, open questions), the
changed paths, the regenerated SQL, the record entry, the checks run with their results and
any blocker. Regenerated SQL leaves an existing `.sqlreview/` review stale; recommend
`/data-request:analyse` when a refreshed formal handoff is needed. A passing check is not
release approval.
