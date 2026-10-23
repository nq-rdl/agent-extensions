---
license: CC-BY-4.0
description: >-
  Walk a Data Analyst through reviewed SQL, step by step, against its review document, JSON and
  scope: each logic step with its lines, the assumptions and limitations that govern it (by id),
  outputs and open questions — pausing for the analyst at every step, then accept for release
  preparation, send back or amend presentation. Produces no formal review report; a
  small state marker lets a later run resume from what changed. Use after /data-request:analyse,
  when the analyst receives SQL for review or wants to understand a change to it.
argument-hint: '<sql path | slug> [hand-off comment URL]'
user-invocable: true
compatibility: >-
  .sqlreview schema 2 (schema 1 remains readable) (docs/specs/2026-09-15-sql-review-plugin-design.md); bash 3.2+, jq >= 1.6.
allowed-tools: Bash, Read, Glob, Grep, Write, AskUserQuestion
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

# Data Request — explain (Data Analyst)

The engineer completes `analyse`, the authorised operator run, UAT and the triage hand-off
before the analyst reviews the extract here. The analyst accepts for release preparation,
sends back or uses `amend`, then prepares and publishes the release. The engineer never releases.

For RDL cohort SQL, read `${CLAUDE_PLUGIN_ROOT}/skills/guardrails/SKILL.md` when
explaining storage facts or conversions. Label any conflict with current source
metadata and return it to `/data-request:analyse`; do not silently rewrite the reviewed record.

Arguments: `$ARGUMENTS` — a SQL path or a slug from `status`, optionally followed by
its child-issue hand-off comment URL.

```bash
S="${CLAUDE_PLUGIN_ROOT}/skills/setup/scripts"
bash "$S/sqlreview.sh" status --json                # exit 3 → stop: not initialised, run /data-request:setup first
SLUG="$(bash "$S/sqlreview.sh" slug "<sql path>")"  # or the slug given
```

No `reviews/$SLUG/review.json` → stop: there is nothing reviewed to explain; the engineer runs
`/data-request:analyse <sql path>` first. Read `review.json`, `review.md`, `scope.json` if present,
and its authenticated recorded render. Read `definitions` from `.sqlreview/config.json` and use that wording verbatim when
the analyst asks what an assumption or limitation is.

Load `bash "$S/sqlreview.sh" questions "$SLUG" review` on every resume, even when the
review revision matches. This reads authoritative `questions.json` (or a read-only legacy
projection); stale embedded strings and cached Markdown are not current question status.
Show closures by ID, answer and provenance as well as remaining open questions. Do not
change this store during a walkthrough; send reconciliation to the owning engineer/analyst.

## Staleness first — always

```bash
bash "$S/sqlreview.sh" delta "$SLUG"      # 0 current · 10 the SQL changed since it was reviewed · 6 no baseline
```

Exit 2: stop and resolve the operational/source failure with the engineer.
Exit 6: historical evidence is unavailable or corrupt; stop for full analyse reassessment.
Exit 10: ask **Ask the engineer to run /data-request:analyse --update first (Recommended)** /
**Explain the recorded revision**. The second option describes the recorded revision at every
step and cannot authorize acceptance of current SQL. Generated SQL need not be tracked.

Before reading SQL, materialize the exact recorded revision outside the repository:

```bash
bash -s -- "$S" "$SLUG" <<'SH'
set -e
S="$1"; SLUG="$2"
REVISION="$(jq -r '.revision' ".sqlreview/reviews/$SLUG/review.json")"
T="$(mktemp -d /tmp/sqlreview-explain.XXXXXX)" || exit 2
trap 'rm -rf "$T"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP
bash "$S/sqlreview.sh" materialize "$SLUG" review "$REVISION" "$T/reviewed.sql" || exit $?
nl -ba "$T/reviewed.sql"
bash "$S/sqlreview.sh" notes "$T/reviewed.sql" --against ".sqlreview/reviews/$SLUG/review.json" || exit $?
SH
```

Use this numbered recorded SQL output throughout the walkthrough. The shell deletes its
private directory when finished. Re-run this self-contained command if lines are needed again.
Exit 6 requires reassessment; never substitute current SQL for an unavailable recorded render.

## Load the durable hand-off

On every invocation, including a fresh session with no `explain.json`, read the hand-off
comment URL supplied by the analyst. If none is supplied, locate it through the request's
agreed durable triage ledger and child tracking issue; if ambiguous or unavailable, ask for
the exact comment URL. Read that comment and its linked evidence with `gh` or available
GitHub read tools, not a recollection of an earlier session. Make no GitHub writes.

Verify the child repository, tracking issue and deliverable PR match this request. Read the
current PR head SHA from GitHub and compare the hand-off's head SHA, run commit, review revision
and SQL fingerprint with the review being explained. Read the linked run manifest, counts-only
QA, DVC provenance and UAT sections 1 to 3 for that run, plus open questions, flagged decisions,
requester limitations and known approval restrictions. Read
`${CLAUDE_PLUGIN_ROOT}/skills/triage/references/handoff.rst`, *Hand-off to review*, and recheck
its gate, including the committed-review/source-evidence check and `release.sh evidence` at the run
commit. Recheck any referenced release gates against their current evidence before outcomes.

If the record, linked evidence or tools are missing, or any identity/revision differs, name
what is missing or stale and do not offer acceptance. A SQL-only walkthrough and **Send back**
remain available; neither clears the gate. Do not infer acceptance from `explain.json`.

## Resume from a previous explanation (#128 §2)

If `reviews/$SLUG/explain.json` exists and its `sql_sha256` or `review_revision` differs from
now, walk the change first:

```bash
bash -s -- "$S" "$SLUG" <<'SH'
set -e
S="$1"; SLUG="$2"
REVISION="$(jq -r '.revision' ".sqlreview/reviews/$SLUG/review.json")"
PREVIOUS="$(jq -r '.review_revision' ".sqlreview/reviews/$SLUG/explain.json")"
# Each invocation owns its own external directory and cleanup.
T="$(mktemp -d /tmp/sqlreview-explain.XXXXXX)" || exit 2
trap 'rm -rf "$T"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP
bash "$S/sqlreview.sh" materialize "$SLUG" review "$REVISION" "$T/reviewed.sql" || exit $?
bash "$S/sqlreview.sh" materialize "$SLUG" review "$PREVIOUS" "$T/previous.sql" || exit $?
git diff --no-index -- "$T/previous.sql" "$T/reviewed.sql"  # exit 1 means changes
SH
```

1. Explain each hunk in the analyst's terms; pause after each.
2. Then the indirect consequences (#128 §2.1): trace identifiers in those hunks and check the
   unchanged code for grain, filter or join effects the hints cannot see.
3. Then the review items whose `confirmed_revision` is newer than `explain.json.review_revision`
   — what changed in the assumptions and limitations and why.

If either authenticated historical render is unavailable, say the historical delta is unavailable
and offer a full walkthrough of an authenticated selected revision, or reassessment when that
revision cannot be reproduced. Never substitute `delta` against current SQL. The helper validates
positive revisions and reads `history/review/<revision>.json` or the matching published record.

Offer to continue with the full walkthrough or stop.

## Walkthrough

In review order, one step per turn, pausing each time with AskUserQuestion — options
**Continue** / **I have a question** / **Stop here**:

1. **Purpose and grain** — what one output row is.
2. **Inputs** — each source and what one row of it means.
3. **Each logic step** — Read and show the SQL lines it covers; then the assumptions and
   limitations whose `location` falls in those lines, **by id** (`A1`, `L2`), with the decision,
   its rationale and who confirmed it — this is the cross-reference (#128 §1.2). If the SQL
   explained opens with a query-builder analysis-notes header, use the notes emitted by
   the materialization command before its temporary file was deleted, and name the review
   id each header item matches. A header item with `match: null` is
   unreviewed: say so and note it for the engineer; the confirmed review is the authority.
4. **Outputs** — each column; then items with no `location` (global ones).
5. **Open questions** — what is still with the requester.

"I have a question" → answer from the SQL and the documents, then re-offer the same step. Never
change the SQL or the review; if the analyst disagrees with an item, note it for the engineer
(`/data-request:analyse --update`).

## Record where you got to

Write `reviews/$SLUG/explain.json` (state marker only — not a report):

```json
{"sql_sha256": "<SHA of the recorded render actually explained>", "review_revision": <review.json revision>,
 "at": "<UTC ISO>", "by": "<analyst>", "completed": true, "last_step": "outputs"}
```

`by` is the analyst's handle: GitHub login where known, else `git config user.name`, else ask.
Never use `user.email`: the file is committed, and the guard refuses a `by` with an `@`.

A stop writes `completed: false` with the step reached, so the next run can resume.

## Analyst outcome

A completed explanation is not acceptance of the extract. Only after the durable hand-off
has been loaded and rechecked, show run QA, open questions, flagged decisions and known approval
restrictions from it. Ask the analyst for
**Accept for release preparation** / **Send back** / **Presentation amendment**. Do not
offer acceptance of stale SQL, an explained historical revision, missing run/UAT evidence or an
unresolved release gate. Leave acceptance pending when the analyst stops.

Acceptance permits `/data-request:release <candidate ref>` to draft the researcher-facing
summary; it does not publish. A presentation request goes to `/data-request:amend`, including
before the first release. Logic changes and defects go to the engineer through
`/data-request:fix`; a disagreement with a review item also requires `analyse --update`.
Classify each finding; do not make the change or approve new meaning during explanation.

For **Send back**, return this paste-ready note, with one finding block per change:

```text
outcome: send-back
run commit: <operator run SHA, or missing>
finding: <F1: observed issue and affected files>
expected result: <analyst's requested outcome; mark undecided meaning explicitly>
classification: <logic or defect | presentation>
route: </data-request:fix | /data-request:amend>
evidence: <review item/revision, SQL lines, run QA or output schema; no row-level data>
open gates: <unanswered decisions, governance restrictions and missing evidence>
return to review: <refresh analyse, operator-run/UAT evidence and triage hand-off>
```

Present the note to the analyst; post nothing unless explicitly instructed. Keep
`explain.json.completed` about the walkthrough only. Preserve review confirmations and
release records; send-back does not create a new approval field or approve the release.
