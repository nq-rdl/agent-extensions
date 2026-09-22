---
license: CC-BY-4.0
description: >-
  Scope a piece of SQL work with the Data Engineer before the SQL is written: an interview that
  produces .sqlreview/reviews/<slug>/scope.json and the rendered scope.md (intent, inputs,
  outputs, assumptions, open questions), with every assumption confirmed by the human. Re-running
  on an existing scope walks through what changed. Use at the start of the Data Request scoping workflow,
  after /data-request:setup and before /data-request:analyse.
argument-hint: '<intended sql path> [--update]'
user-invocable: true
compatibility: >-
  .sqlreview schema 2 (schema 1 remains readable) (docs/specs/2026-09-15-sql-review-plugin-design.md); bash 3.2+, jq >= 1.6,
  git optional.
allowed-tools: Bash, Read, Glob, Grep, Write, AskUserQuestion
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

# Data Request — bootstrap (Data Engineer)

For RDL cohort SQL, read `${CLAUDE_PLUGIN_ROOT}/skills/guardrails/SKILL.md` before
scoping or reviewing. Consult its dataops/column-spec sources and carry evidence or
unverified facts into the discussion; advisory findings do not replace human confirmation.

Arguments: `$ARGUMENTS` — the path the SQL *will* live at (it need not exist yet). The scope
directory is keyed by that path, so `reports/monthly.sql` and `audits/monthly.sql` never collide.

```bash
S="${CLAUDE_PLUGIN_ROOT}/skills/setup/scripts"
bash "$S/sqlreview.sh" status --json           # exit 3 → stop: not initialised, run /data-request:setup first
SLUG="$(bash "$S/sqlreview.sh" slug "<intended sql path>")"   # exit 5 → the slug is bound to another path; say so and stop
```

Read `definitions` from `.sqlreview/config.json` and use that wording, verbatim, whenever you
tell the engineer what counts as an assumption or a limitation. Do not paraphrase it.

## Existing scope → update path (#127 §2)

If `.sqlreview/reviews/$SLUG/scope.json` exists (or `--update`):

1. Show how the scope itself moved: `git log -p --follow -- .sqlreview/reviews/$SLUG/scope.json`
   when it is tracked (skip silently otherwise). Also inspect `git diff -- <scope path>` and
   `git diff --cached -- <scope path>` for unstaged and staged scope edits.
2. If the SQL now exists, use `git diff --no-index -- ".sqlreview/reviews/$SLUG/scope.source.sql" "<sql path>"`
   to show changes since the previous bootstrap (exit 1 means changes). If the baseline is absent,
   explicitly say a historical delta is unavailable and do a full reassessment. Read the SQL and compare it with the scope's intent, inputs and outputs —
   name each place the SQL does something the scope did not foresee.
3. **Re-put every existing assumption and limitation** to the engineer (confirm / reword / drop) and ask for new
   ones. No item keeps a confirmation from an earlier revision — the guard rejects it.
4. Continue at *Write* with `revision` incremented.

## Fresh scope → interview

Work through these in order, pausing (AskUserQuestion) on each scoping decision:

1. **Intent** — one paragraph: what question the SQL answers and for whom.
2. **Inputs** — each source table/view: name and what one row means.
3. **Outputs** — each output column (or the grain plus columns) and what one row means.
4. **Candidate assumptions** — every point where the request leaves more than one reasonable
   reading; propose the decision and its rationale. Offer them in batches of at most four per
   AskUserQuestion call, one question per item, options **Confirm (Recommended)** / **Reword** /
   **Reject**. A reworded item is asked again with the new text.
5. **Open questions** — anything the engineer must take back to the requester.

Keep the working set in `.sqlreview/reviews/$SLUG/scope.draft.json` (guard-exempt). If the
engineer stops, leave the draft and write nothing final — say so.

## Write, render, hand over

Only confirmed items go into `scope.json`. **Never fill `confirmed_by`, `confirmed_at` or
`confirmed_revision` from anything but an answered question** — `confirmed_by` is the user (name
or email from `git config user.name` / `user.email`, else ask), `confirmed_at` is now (UTC ISO),
`confirmed_revision` equals the document `revision`. Write the complete confirmed document to
`.sqlreview/reviews/$SLUG/scope.draft.json`, then publish it with the command below:

```json
{
  "schemaVersion": 2, "kind": "scope", "slug": "<SLUG>", "sql_path": "<intended sql path>",
  "title": "…", "revision": 1, "recorded_at": "<UTC ISO>", "recorded_by": "<user>",
  "git_commit": "<git rev-parse HEAD or null>",
  "intent": "…",
  "inputs":  [{"name": "schema.table", "description": "one row per …"}],
  "outputs": [{"name": "column", "description": "…"}],
  "assumptions": [{"id": "A1", "text": "…", "rationale": "…", "location": null,
                   "status": "confirmed", "confirmed_by": "<user>", "confirmed_at": "<UTC ISO>", "confirmed_revision": 1}],
  "limitations": [],
  "open_questions": ["…"]
}
```

```bash
bash "$S/sqlreview.sh" publish "$SLUG" scope ".sqlreview/reviews/$SLUG/scope.draft.json" || exit $?
```

Publish validates a staged copy, including confirmations and the next revision, before atomically
replacing `scope.json`. Never copy or patch the draft directly into the final path.
After publish succeeds, if SQL exists, copy its reviewed bytes to
`.sqlreview/reviews/$SLUG/scope.source.sql` (separate from analyse’s `source.sql`). Check copy success;
if it fails, remove any old scope baseline and report that the next bootstrap needs a full reassessment.
Preserve the previous revision and increment it on updates.


```bash
bash "$S/sqlreview.sh" render "$SLUG" scope || exit $?  # → reviews/<slug>/scope.md (never hand-write it)
rm -f ".sqlreview/reviews/$SLUG/scope.draft.json"
```


Show the rendered `scope.md`. Use `/data-request:map` for source mapping and
`/data-request:draft` to develop the scoped SQL. Next stage, once the SQL exists: `/data-request:analyse <sql path>`.
