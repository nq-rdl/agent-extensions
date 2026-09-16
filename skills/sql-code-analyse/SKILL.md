---
name: sql-code-analyse
license: CC-BY-4.0
description: >-
  Review a finished SQL file for handoff: read it against its scope, record purpose, inputs,
  outputs, logic steps, assumptions and limitations in .sqlreview/reviews/<slug>/review.json,
  with every assumption and limitation confirmed by the human, and render the standardised
  review.md. Re-running on reviewed SQL diffs against the stored snapshot, walks the human through
  the change, and reassesses every item. Use when SQL is ready to hand to the Data Analyst.
argument-hint: '<sql path> [--update]'
user-invocable: true
compatibility: >-
  .sqlreview schema 1 (docs/specs/2026-09-15-sql-review-plugin-design.md); bash 3.2+, jq >= 1.6,
  git optional (provenance only — the diff baseline is the stored snapshot).
allowed-tools: Bash, Read, Glob, Grep, Write, AskUserQuestion
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

# SQL Code — analyse (Data Engineer)

For RDL cohort SQL, read `${CLAUDE_PLUGIN_ROOT}/skills/guardrails/SKILL.md` before
scoping or reviewing. Consult its dataops/column-spec sources and carry evidence or
unverified facts into the discussion; advisory findings do not replace human confirmation.

Arguments: `$ARGUMENTS`.

```bash
S="${CLAUDE_PLUGIN_ROOT}/skills/setup/scripts"
bash "$S/sqlreview.sh" status --json                # exit 3 → stop: not initialised, run /sql-code:setup first
SLUG="$(bash "$S/sqlreview.sh" slug "<sql path>")"  # exit 5 → bound to another path: offer `sqlreview.sh move OLD NEW`
bash "$S/sqlreview.sh" fingerprint "<sql path>"     # {sql_path, sql_sha256, git_commit, git_dirty} — embed as-is
```

Read `definitions` from `.sqlreview/config.json` and use that wording verbatim when deciding and
explaining what is an assumption and what is a limitation; never paraphrase it. If
`reviews/$SLUG/scope.json` exists, Read it — the review is written *against* the scope. If it does
not, offer `/sql-code:bootstrap` retroactively once, then continue without it if declined.

## Existing review → update path (#130 §2)

If `reviews/$SLUG/review.json` exists (or `--update`):

```bash
bash "$S/sqlreview.sh" delta "$SLUG"     # exit 0 unchanged (say so, stop) · 10 changed · 6 no baseline → full review below (retain revision history) · 2 missing SQL → stop/rebind
bash "$S/sqlreview.sh" impact "$SLUG"    # HINTS ONLY: identifiers from the changed lines traced into unchanged lines
```

1. Walk the human through each hunk of the delta: what it does, and what it changes about grain,
   filters, joins or output. Pause after each hunk (AskUserQuestion: **Continue** / **Discuss**).
2. Show the impact hints as *places to look*, then check the unchanged code yourself for indirect
   consequences the hints cannot see (a changed literal, join type or `DISTINCT` shifts grain
   without touching an identifier). Confirm or dismiss each candidate with the human.
3. **Reassess every existing assumption and limitation** — confirm / reword / drop each one
   (hint-flagged items first) and add new ones. A confirmation from an earlier revision never
   carries over; the guard rejects `confirmed_revision < revision`.
4. Set `revision` to the previous value + 1, append to `changes[]` `{revision, at, by, summary}`.
   Then *Confirm, write, render* below.

A missing baseline is still an update: preserve the existing `changes[]`, increment the previous
revision, and reassess every assumption and limitation. Never reset an existing review to revision 1.

## Full review

Read the SQL. Draft into `reviews/$SLUG/review.draft.json` (guard-exempt) as you go:

- **purpose** — one paragraph, in the analyst's terms.
- **inputs** — every source with what one row means; **outputs** — `grain` plus each column.
- **logic** — numbered steps with the SQL line range each covers (`lines: [from, to]`): CTE by CTE,
  then the final select; joins, filters and aggregations named explicitly.
- **assumptions** — every place the SQL commits to one reading where the request allowed more;
  **limitations** — every constraint the analyst must know before relying on the output. Give
  each the `location` lines it governs and a one-line rationale.
- **open_questions** — anything unresolved.

## Confirm, write, render

The human-in-the-loop trigger (#130 §1.1): put **each** candidate assumption and limitation to
the engineer via AskUserQuestion — batches of at most four per call, one question per item,
options **Confirm (Recommended)** / **Reword** / **Reject**. Reworded items are asked again.
Only confirmed items reach `review.json`; rejected ones stay in the draft. If the engineer stops,
leave the draft and write nothing final — say so.

**Never fill `confirmed_by`, `confirmed_at` or `confirmed_revision` from anything but an answered
question**: `confirmed_by` is the user (`git config user.name` / `user.email`, else ask),
`confirmed_at` is now (UTC ISO), `confirmed_revision` equals the document `revision`.

Re-run fingerprint and compare its SHA with the bytes you reviewed; if different, reassess the
change before continuing. Write the complete confirmed document to
`.sqlreview/reviews/$SLUG/review.draft.json`, then publish it with the command below:

```json
{
  "schemaVersion": 1, "kind": "review", "slug": "<SLUG>", "sql_path": "<sql path>", "title": "…",
  "revision": 1, "recorded_at": "<UTC ISO>", "recorded_by": "<user>",
  "sql_sha256": "<from fingerprint>", "git_commit": "<from fingerprint>", "git_dirty": "<boolean from fingerprint; preserve its JSON type>",
  "purpose": "…", "grain": "one row per …",
  "inputs":  [{"name": "schema.table", "description": "one row per …"}],
  "outputs": [{"name": "column", "description": "…"}],
  "logic":   [{"step": 1, "title": "…", "lines": [1, 12], "description": "…"}],
  "assumptions": [{"id": "A1", "text": "…", "rationale": "…", "location": {"lines": [3, 5]},
                   "status": "confirmed", "confirmed_by": "<user>", "confirmed_at": "<UTC ISO>", "confirmed_revision": 1}],
  "limitations": [{"id": "L1", "text": "…", "rationale": "…", "location": null,
                   "status": "confirmed", "confirmed_by": "<user>", "confirmed_at": "<UTC ISO>", "confirmed_revision": 1}],
  "open_questions": ["…"],
  "changes": [{"revision": 1, "at": "<UTC ISO>", "by": "<user>", "summary": "initial review"}]
}
```

```bash
bash "$S/sqlreview.sh" publish "$SLUG" review ".sqlreview/reviews/$SLUG/review.draft.json" || exit $?
bash "$S/sqlreview.sh" snapshot "$SLUG" "<sql path>" || exit $?  # only AFTER publish succeeds
bash "$S/sqlreview.sh" render "$SLUG" review || exit $?  # → reviews/<slug>/review.md (never hand-write it)
rm -f ".sqlreview/reviews/$SLUG/review.draft.json"
```

Show `review.md`. Hand over: the analyst runs `/sql-code:explain <sql path>`.

Publish validates a staged copy, confirmations, next revision and current SQL fingerprint before
atomically replacing `review.json`. Never copy or patch the draft directly into the final path.
Snapshot verifies the final review hash before advancing `source.sql` and preserves
`history/<revision>.sql` for resumed explanations. Stop on any failure and keep the draft. A failed
or interrupted publish must never advance the baseline; a failed snapshot leaves the review stale.
