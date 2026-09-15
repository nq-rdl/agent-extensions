---
name: sql-review-explain
license: CC-BY-4.0
description: >-
  Walk a Data Analyst through reviewed SQL, step by step, against its review document, JSON and
  scope: each logic step with its lines, the assumptions and limitations that govern it (by id),
  outputs and open questions — pausing for the analyst at every step. Produces no report; a
  small state marker lets a later run resume from what changed. Use after /sql-review:analyse,
  when the analyst receives SQL for review or wants to understand a change to it.
argument-hint: '<sql path | slug>'
user-invocable: true
compatibility: >-
  .sqlreview schema 1 (docs/specs/2026-09-15-sql-review-plugin-design.md); bash 3.2+, jq >= 1.6.
allowed-tools: Bash, Read, Glob, Grep, Write, AskUserQuestion
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

# SQL Review — explain (Data Analyst)

Arguments: `$ARGUMENTS` — a SQL path or a slug from `status`.

```bash
S="${CLAUDE_PLUGIN_ROOT}/skills/setup/scripts"
bash "$S/sqlreview.sh" status --json                # exit 3 → stop: not initialised, run /sql-review:setup first
SLUG="$(bash "$S/sqlreview.sh" slug "<sql path>")"  # or the slug given
```

No `reviews/$SLUG/review.json` → stop: there is nothing reviewed to explain; the engineer runs
`/sql-review:analyse <sql path>` first. Read `review.json`, `review.md`, `scope.json` if present,
and the SQL. Read `definitions` from `.sqlreview/config.json` and use that wording verbatim when
the analyst asks what an assumption or limitation is.

## Staleness first — always

```bash
bash "$S/sqlreview.sh" delta "$SLUG"      # 0 current · 10 the SQL changed since it was reviewed · 6 no baseline
```

Exit 10 or 6: the review no longer describes the file. Ask (AskUserQuestion): **Ask the engineer
to run /sql-review:analyse --update first (Recommended)** / **Explain the reviewed snapshot** — the
second explains `reviews/$SLUG/source.sql`, and every step is labelled as describing the
snapshot, not the current file.

## Resume from a previous explanation (#128 §2)

If `reviews/$SLUG/explain.json` exists and its `sql_sha256` or `review_revision` differs from
now, walk the change first:

```bash
bash "$S/sqlreview.sh" delta "$SLUG"      # the hunks (when the SQL changed)
bash "$S/sqlreview.sh" impact "$SLUG"     # HINTS: identifiers from the hunks traced into unchanged lines
```

1. Explain each hunk in the analyst's terms; pause after each.
2. Then the indirect consequences (#128 §2.1): the hinted lines *and* your own check of the
   unchanged code for grain, filter or join effects the hints cannot see.
3. Then the review items whose `confirmed_revision` is newer than `explain.json.review_revision`
   — what changed in the assumptions and limitations and why.

Offer to continue with the full walkthrough or stop.

## Walkthrough

In review order, one step per turn, pausing each time with AskUserQuestion — options
**Continue** / **I have a question** / **Stop here**:

1. **Purpose and grain** — what one output row is.
2. **Inputs** — each source and what one row of it means.
3. **Each logic step** — Read and show the SQL lines it covers; then the assumptions and
   limitations whose `location` falls in those lines, **by id** (`A1`, `L2`), with the decision,
   its rationale and who confirmed it — this is the cross-reference (#128 §1.2).
4. **Outputs** — each column; then items with no `location` (global ones).
5. **Open questions** — what is still with the requester.

"I have a question" → answer from the SQL and the documents, then re-offer the same step. Never
change the SQL or the review; if the analyst disagrees with an item, note it for the engineer
(`/sql-review:analyse --update`).

## Record where you got to

Write `reviews/$SLUG/explain.json` (state marker only — not a report):

```json
{"sql_sha256": "<current sha from fingerprint>", "review_revision": <review.json revision>,
 "at": "<UTC ISO>", "by": "<analyst>", "completed": true, "last_step": "outputs"}
```

A stop writes `completed: false` with the step reached, so the next run can resume.
