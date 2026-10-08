---
name: bootstrap
license: CC-BY-4.0
description: 'Scope a piece of SQL work with the Data Engineer before the SQL is written:
  an interview that produces .sqlreview/reviews/<slug>/scope.json and the rendered
  scope.md (intent, inputs, outputs, assumptions, open questions), preserving recorded
  upstream confirmations. Re-running on an existing scope walks through what changed.
  Use at the start of the Data Request scoping workflow, after $data-request:setup
  and before $data-request:analyse.'
compatibility: .sqlreview schema 2 (schema 1 remains readable) (docs/specs/2026-09-15-sql-review-plugin-design.md);
  bash 3.2+, jq >= 1.6, git required for SQL-bound scopes. macOS and Linux.
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

## Codex execution

Before shell examples, set PLUGIN_ROOT to the absolute installed plugin directory: two parent directories above this SKILL.md’s containing skill directory. Derive it from the loaded file path, never the working directory. This variable is not automatically supplied to ordinary shell tools. Quote it in commands.

Here $ARGUMENTS means the user’s supplied skill arguments. Codex does not populate a shell variable for them. Pass arguments with shell quoting that preserves literal text; never evaluate user text as shell code.

# Data Request — bootstrap (Data Engineer)

The **Data Engineer** runs this stage after setup and the Data Analyst's
`answers.yaml` filling pass. The analyst records research decisions in the optional
`answers.intake.json` sidecar in that same pass. There is no separate intake skill.
The engineer owns technical sources, keys, timezones, joins and validity rules.

For RDL cohort SQL, read `${PLUGIN_ROOT}/skills/guardrails/SKILL.md` before
scoping or reviewing. Apply **Engineer decisions: proceed and flag** in its
`references/decision-authority.rst`: implement evidenced technical defaults within the agreed task,
flag them for analyst review, and batch only remaining research questions. This does not park the build for analyst approval
or replace formal engineer confirmation. Deliver requested outputs only; offer extras, do not build them.
Consult dataops/column-spec evidence; never invent human confirmation.

Arguments: `$ARGUMENTS` — the path the SQL *will* live at (it need not exist yet). The scope
directory is keyed by that path, so `reports/monthly.sql` and `audits/monthly.sql` never collide.

```bash
S="${PLUGIN_ROOT}/skills/setup/scripts"
bash "$S/sqlreview.sh" status --json           # exit 3 → stop: not initialised, run $data-request:setup first
SLUG="$(bash "$S/sqlreview.sh" slug "<intended sql path>")"   # exit 5 → the slug is bound to another path; say so and stop
```

Before either interview path, read the request's `answers.yaml` and run its
`validate-answers` check, which also validates the sibling `answers.intake.json`.
See `${PLUGIN_ROOT}/skills/setup/references/analyst-intake.rst` for the schema
and merge rules. Import with `bash "$S/sqlreview.sh" intake answers.intake.json <next-revision>`.
Copy its assumptions into the draft by ID, preserving analyst confirmation and
`upstream` fields. Do not ask the engineer a research question that the intake
answered. Confirm only its technical implementation with the engineer. Imported
confirmation dates come from the analyst's recorded answer, not this interview.
For legacy embedded arrays, prefer the helper's third-argument draft merge: it
refreshes sidecar-owned questions without removing other gaps. If copying manually,
copy `analyst_questions` into `open_questions` and record only the sidecar-owned
strings in `intake_questions`; preserve that field when drafting legacy updates.
For new or migrated shared-store work, import assumptions from the two-argument
helper output and reconcile `analyst_questions` in `questions.draft.json` instead:
retain existing IDs and closed rows, append missing scope questions, and close an
answered question only with the analyst's answer and provenance. Absence from a
sidecar is not closure evidence; never refresh shared history by deleting rows or
reintroduce embedded arrays. Any research question missed by intake also gets the
`Analyst question:` prefix and goes back to the analyst, who consults the requester. Missing intake permits legacy technical scoping; it gives
no analyst confirmation. Do not resolve a research gap by treating an engineer's
technical choice as the analyst's answer.

Settle the main grain from intake or cited prior-delivery/data-element evidence,
not the bare answers default, following guardrails `references/grain.rst`.
Record one confirmed source-citing grain item, describe each requested finer output
and check answers drift once; offer the answers correction in the same change.

Generated SQL may be absent from the working tree and git: a declared generator still requires
a committed render-only adapter and fresh `fingerprint` evidence. Missing output is not a
scope-before-SQL decision. Commit maintained SQL or builder/cohort/spec, adapter, config and pins
first; read `${PLUGIN_ROOT}/skills/setup/references/sql-provenance.rst` for temporary
HEAD rendering and historical authentication. Use those rendered bytes when reading SQL.
Read `definitions` from `.sqlreview/config.json` and use that wording, verbatim, whenever you
tell the engineer what counts as an assumption or a limitation. Do not paraphrase it.

## Before presenting prose (fresh or update)

**Name the constant, never its value** in scope/review prose, drafts, logic descriptions,
questions and change summaries (for example, `EVENT_CD`, not its numeric value).
`code-value` scans string fields for maximal runs of 8 to 10 digits, except validated
machine metadata (SQL path/bound slug, fingerprints and ISO timestamps at known locations).
Keep that metadata as-is; lint exemptions do not waive `check` or publication validation.
Never add prose codes to `.pii-code-values` or suppress the PII gate to clear them.

Before every question batch or displayed summary, stage the proposed wording in
`.sqlreview/reviews/$SLUG/scope.draft.json`, including stored prose, recurring suggestions
and any history/SQL-delta explanations. Inspect raw helper/git output locally; do not paste
it into questions. Run:

```bash
bash "$S/sqlreview.sh" lint --ste ".sqlreview/reviews/$SLUG/scope.draft.json"
# exit 10 → <id>\t<field>\t<rule>\t<detail>, without code values; other failures → stop
```

Replace each prose code with its constant name and fix STE wording before showing it.
Re-run lint after edits; decision-source warnings require a source check, not a made-up source.
Reworded confirmed items need fresh human confirmation; do not retain their carried
confirmation or edit the final JSON. Lint cannot grant confirmation.

Apply guardrails **House defaults** without asking: reuse one standard assumption from
setup's `tuh-facility` entry, with its `upstream` marker and recorded house confirmation
(see `${PLUGIN_ROOT}/skills/setup/references/recurring-decisions.rst`). Do not ask a fresh facility question.
If the request explicitly changes the cohort's facility set to another facility, the whole HHS or a network-wide cohort, put one
`Analyst question:` about the facility set instead of the TUH default; do not apply or carry it.
Reuse an already answered intake/scope exception; do not ask it again or intersect it with TUH.
Continue independent work while the dependent facility scope remains unresolved.

Some decisions recur in every enquiry (#362). Before you put candidate items to the engineer, run
`bash "$S/recurring-decisions.sh" match ".sqlreview/reviews/$SLUG/scope.draft.json"`. For each other match,
show the prior enquiries, offer the listed wording and mark the item `upstream`, as
`${PLUGIN_ROOT}/skills/setup/references/recurring-decisions.rst` says. The engineer still confirms each other item;
the exact recorded TUH house default is imported, not put in a new confirmation batch.
Rows from `carryforward` include recorded `upstream` and `decided` fields: preserve them.

## Decision origin (#434)

Keep decision origin separate from engineer confirmation. When evidence identifies the
decider, attach optional `decided: {by, role, at, source}` to the item: a human handle,
role, decision date or ISO time, and comment/PR URL or dated document reference.
Use `unlinked (verbal)` for a reported verbal decision; never invent a source, decider
or date from rationale wording. If origin is unknown, omit `decided` and surface the
attribution question. Show the provenance with the item before confirmation.
Preserve `decided` verbatim when re-drafting, including header candidates, carryover
and carryforward; adding, changing or removing it requires fresh confirmation. Run plain
`lint` before publish: provenance warnings need a source check, separate from wording
reconfirmation. A lint hint is advisory; it does not establish who decided.

## Shared questions (#437)

Load `bash "$S/sqlreview.sh" questions "$SLUG" scope` on resume. Keep questions in
`questions.json`, not duplicate scope/review lists; follow
`${PLUGIN_ROOT}/skills/setup/references/questions.rst` for IDs, owner and answered
closure provenance. Migrate legacy strings once with `migrate-questions`; retain historical
embedded arrays untouched. Closing a question publishes only that store, without a scope
revision or renewed confirmations. If its answer changes SQL meaning, use the update path.
Prepare `questions.draft.json` alongside the scope draft before the pre-publish header check,
including an empty question list when none remain. On resume, retain all existing IDs and
closed rows; stage any new questions. For a fresh scope, publish the scope first, then
`publish-questions` its open question draft before rendering; failed question publication
leaves the handoff incomplete.

## Population limits

Before either interview path, check **age, sex and facility** against the request wording,
intake and existing scope item. Ask whether the wording implies a limit and whether the SQL
applies it; reuse an already answered decision rather than asking again. Do not infer adult
from a service name or from an earlier run's surprise. Do not add a filter to settle ambiguity.

Record an answer for each dimension in `scope.draft.json`, then confirm and publish through
*Write* below. Cite the source path/revision and request wording; state the limit or
**no stated limit** / **unclear**. Choose the record kind using the shared definitions:

- Stated requester limits belong in `intent`, not a new RDL assumption. Put an explicit
  no-limit answer there too; do not omit a dimension because it has no filter.
- Use `A-population-age` or `A-population-sex` only for an actual RDL interpretation choice,
  reusing an existing choice's ID. Request facts are not RDL choices;
  implementation defects are not confirmed decisions.
- Record missing or contradicted implementation in `limitations`, using `L-population-age`
  or `L-population-sex` (or the existing defect ID), with source evidence and SQL lines.
  Any existing misclassification needs explicit reclassification and confirmation through *Write*;
  do not carry a defect forward as an agreed choice or fabricate carried fields.

Keep imported `A-intake-<id>` items verbatim: text, rationale, actor/date, confirmation revision,
`upstream` and `decided`. These IDs retain the intake schema's assumption-list placement;
reference them from intent rather than moving or rewriting them. Do not duplicate an answered
intake decision as `A-population-*`. Keep the exact `tuh-facility` house-default wording and
confirmation too; reuse the existing facility exception instead of another decision.

Record the engineer-confirmed SQL implementation separately: **applied**, **missing**,
**contradicted**, **unverified** or **not yet written**, with SQL revision/lines when available.
Use `intent` for status/evidence that is not a limitation; use a separate limitation for a defect
or unresolved constraint. Never append that assessment to imported text or rationale or attribute
it to the analyst/house confirmer. A sex label is not a sex restriction. For age, record the
age anchor: **age at index surgery** and age today differ. For facility, check the verified
crosswalk/filter and retain the house default and exception routing above.

An unclear research limit goes in the shared `questions.draft.json` / `questions.json` store
as one `Analyst question:` with the proposed interpretation and missing anchor. Follow *Shared
questions* above; retain legacy `open_questions` history, but do not add a new embedded list.
Record that gap in intent or a confirmed limitation, not as an agreed population restriction.
An engineer's confirmation of the static SQL finding is not an analyst research answer.
Continue independent work under the shared authority rule; do not widen or narrow a cohort
silently. Recheck these answers on updates, including when SQL first becomes available.

## Existing scope → update path (#127 §2)

If `.sqlreview/reviews/$SLUG/scope.json` exists (or `--update`):

For `scoped-header-only` status, inspect the header diff against the authenticated
historical scope render and reconcile its notes with the confirmed scope. If only header wording
changed, run the pre-publish header check below with the current shared questions, then
republish the existing `scope.json` and render it to record a header revision without
repeating unchanged confirmations or incrementing the semantic revision. Changed item text,
rationale or framing still follows the update path below. A body change is stale; unavailable or corrupt historical evidence requires reassessment.

1. First inspect locally how the scope itself moved: `git log -p --follow -- .sqlreview/reviews/$SLUG/scope.json`
   when it is tracked (skip silently otherwise). Also inspect `git diff -- <scope path>` and
   `git diff --cached -- <scope path>` for unstaged and staged scope edits.
2. Run `bash "$S/sqlreview.sh" delta "$SLUG" scope` to inspect changes since the previous
   bootstrap (exit 10 means body changes; exit 0 can include a header diff). Show only linted
   explanations, not raw diffs. Exit 6 means an authenticated historical render is unavailable:
   say so and do a full reassessment; exit 2 means an operational/source failure to resolve.
   Read a fresh HEAD render and compare its intent, inputs and outputs with the scope.
3. Before re-putting intent, inputs and outputs, stage and lint their proposed wording using
   the pre-presentation check above. **Re-put technical implementation of intent, inputs and outputs** to the engineer;
   retain answered research decisions from intake. Compare the current sidecar with
   imported upstream items first; changed or removed decisions go to the analyst
   for a recorded answer before dependent work proceeds. Then find which existing items keep
   their confirmation (#348): draft the next revision with each unchanged item's `id`, `text` and
   `rationale` verbatim and its old `location` lines. When an authenticated historical render
   exists, compute unchanged ranges first; missing/corrupt evidence means a manual reassessment,
   not a guessed offset:

   ```bash
   bash "$S/sqlreview.sh" remap "$SLUG" ".sqlreview/reviews/$SLUG/scope.draft.json"
   # → {document, prior_revision, remapped: [{kind, id, from, to}], walk: [{kind, id, lines, why}]}
   bash "$S/sqlreview.sh" carryforward "$SLUG" scope ".sqlreview/reviews/$SLUG/scope.draft.json"
   # → {prior_revision, revision, sql_unchanged, carry: [{kind, id, basis, set}], walk: [{kind, id, why}]}
   ```

   Remap changes only draft ranges, never confirmations, revisions or fingerprints. Its `walk`
   ranges (changed, split by an insertion, or ambiguous repeated text) stay untouched; reassess
   their current lines with the human before carryforward. It preserves new/manual ranges and
   is safe to retry. The explicit draft must be directly inside this slug's review directory,
   not a published JSON or historical record.

   Copy each `carry` item's `set` fields onto it verbatim; it keeps the confirmation a human gave
   at `confirmed_revision` and is not asked again. Re-run the pre-presentation lint before each `walk` batch,
   including new items; reworded carried items need fresh confirmation. Walk **only** the `walk` items
   (confirm / reword / drop, showing text and rationale, with `why`), plus any `carry` item the SQL diff or framing
   change still implicates, and ask for new ones. When the engineer asks for a full re-walk, walk
   every item and publish with `--reconfirm-all`. Never set `carried_from_revision` by hand.
4. Continue at *Write* with `revision` incremented.

## Fresh scope → interview

Apply the pre-presentation check above to every interview batch, including framing and open questions.
Work through these in order with the engineer. Formal scope publication still needs answered
the host user-question tool confirmations; it does not require analyst approval of engineer-owned choices.
Keep build progress distinct from an unpublished scope draft.

1. **Intent** — one paragraph: what question the SQL answers and for whom.
2. **Inputs** — each source table/view: name and what one row means.
3. **Outputs** — each output column (or the grain plus columns) and what one row means.
4. **Candidate assumptions** — every point where the request leaves more than one reasonable
   reading; propose the decision and its rationale. Exclude imported house/intake confirmations.
   Offer the remaining items in batches of at most four per
   the host user-question tool call, one question per item, options **Confirm (Recommended)** / **Reword** /
   **Reject**. Each question shows the item's `text` **and** its `rationale`: both are the
   confirmed record, so a rationale the engineer never saw must not be published. Reword may change
   either; a reworded item is asked again with its new text and rationale.
   Before each batch, run `bash "$S/sqlreview.sh" lint --ste ".sqlreview/reviews/$SLUG/scope.draft.json"` (intent too; exit 10 → one `<id>\t<field>\t<rule>\t<detail>` line per hit) and reword each hit first.
5. **Open questions** — technical gaps for the engineer, research gaps labelled
   `Analyst question:` for the analyst to take back to the requester. First look for a
   prior version's SQL or delivery (a V2 request's V1 repository or release). When it answers the
   question, ask it as confirm-or-change, quoting the prior answer and its source. Propose a
   default answer for each open question: the engineer can accept it as a candidate assumption
   (confirmed as in step 4), or keep the question open with the default noted for the requester.
   Apply the shared authority classes: batch research questions into one analyst message,
   continue independent work and safe defaults, and stop only a dependent portion that crosses
   a known restriction, expands the cohort, changes released row count or invents a
   requester-defined measure (clinical, research or business definition) affecting inclusion or output meaning.
   An engineer technical decision proceeds and is flagged; it is not an analyst answer.

Keep the working set in `.sqlreview/reviews/$SLUG/scope.draft.json` (guard-exempt). If the
engineer stops, leave the draft and write nothing final — say so.

## SQL that changes during the interview

When SQL is available through maintained source or its declared generator, the framing is
confirmed against a fresh committed render. Embed all `fingerprint` fields, including
`sql_provenance`, `git_commit` and `git_dirty: false`, in the draft. Do not write SQL under
`.sqlreview/`. A scope intentionally framed before SQL exists uses `sql_sha256: null` and
omits SQL provenance; a missing adapter or failed render never qualifies.

Before publishing, commit source edits and re-run `fingerprint`. Authenticate the draft's
original full SHA with `sr_source_auth`, then compare it with `sr_source_render HEAD` in
a private temporary directory outside the repository (see the setup provenance reference).
A changed full hash with the same non-null body hash is a header revision: reconcile notes
without reconfirming unchanged items. Changed bodies require a diff and fresh confirmation
of affected intent, inputs, outputs and items, then refresh all fingerprint fields. Missing
or corrupt historical evidence requires reassessment. Always delete temporary SQL on exit.

Also self-check the confirmed wording before publish:

```bash
bash "$S/sqlreview.sh" lint ".sqlreview/reviews/$SLUG/scope.draft.json"  # exit 10 → one "<id>\t<field>\t<phrases>" per hit
```

A `code-value` hit needs the constant name, not a numeric exemption. A provisional-wording
text or rationale hit is a confirmed item whose wording still reads as provisional ("should be
confirmed", "proposed", "needs confirming"). Re-put it, showing text and rationale, with the
wording rewritten to state the confirmed decision.

## Write, render, hand over

Only confirmed items go into `scope.json`. **Never fill `confirmed_by`, `confirmed_at` or
`confirmed_revision` from anything but an answered question or a recorded imported confirmation**
(analyst intake or the exact TUH house default above) — `confirmed_by` is the user's handle
(GitHub login where known, else `git config user.name`, else ask; never `user.email` — `check`
refuses an `@`), `confirmed_at` is now (UTC ISO),
`confirmed_revision` equals the document `revision` — imported intake takes the original
analyst actor/date and the import revision; a carried item takes exactly
the `set` fields `carryforward` printed; the imported house default keeps its original actor/date and import revision.
Write the complete confirmed document to
`.sqlreview/reviews/$SLUG/scope.draft.json`, then publish it with the command below:

For a scope before SQL, omit `sql_provenance` and retain a null SQL hash/commit.

```json
{
  "schemaVersion": 2, "kind": "scope", "slug": "<SLUG>", "sql_path": "<intended sql path>",
  "title": "…", "revision": 1, "recorded_at": "<UTC ISO>", "recorded_by": "<user>",
  "git_commit": "<fingerprint immutable source commit or null>", "sql_sha256": "<fingerprint SHA the framing was confirmed against, or null>",
  "sql_body_sha256": "<fingerprint body SHA, or null>",
  "git_dirty": false, "sql_provenance": {"mode": "<rendered or tracked>", "project_root": "<fingerprint prefix>", "commit": "<fingerprint commit>"},
  "intent": "…",
  "inputs":  [{"name": "schema.table", "description": "one row per …"}],
  "outputs": [{"name": "column", "description": "…"}],
  "assumptions": [{"id": "A1", "text": "…", "rationale": "…", "location": null,
                   "status": "confirmed", "confirmed_by": "<user>", "confirmed_at": "<UTC ISO>", "confirmed_revision": 1}],
  "limitations": [],
  "question_store": "questions.json"
}
```

### Check the SQL header before publish (#433)

After the scope and question drafts are complete, **before every scope publication**
(including header-only updates), run this for an SQL-bound draft:

```bash
bash -s -- "$S" "$SLUG" "<sql path>" <<'SH'
set -e
S="$1"; SLUG="$2"; SQL_PATH="$3"
. "$S/sqlreview-lib.sh"
SR_ROOT="$(sr_find_root)" || exit 3
T="$(mktemp -d /tmp/sqlreview-notes.XXXXXX)" || exit 2
trap 'rm -rf "$T"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP
sr_source_clean || exit $?
sr_source_render HEAD "$SQL_PATH" "$T/current.sql" || exit $?
bash "$S/sqlreview.sh" notes "$T/current.sql" \
  --against ".sqlreview/reviews/$SLUG/scope.draft.json" \
  --questions ".sqlreview/reviews/$SLUG/questions.draft.json" || exit $?
SH
```

With a published sibling `questions.json`, comparison validates the staged questions against
its identity/history invariants before emitting pairs: retain every ID and its text/applicability,
keep closed rows unchanged, and add only open questions. Fix a rejected draft before publication.

Scope intentionally framed before SQL: skip the comparison, not the scope. Missing generated
working SQL is not that condition; its declared adapter must render. An absent analysis-notes header means no
header mismatch; a malformed header or missing/invalid questions is not a clean result —
stop and surface the diagnostic, retain drafts, and use `$data-request:fix` for SQL edits.
Verify the header contract against query-builder's canonical
https://github.com/nq-rdl/query-builder/blob/main/docs/ANALYSIS_NOTES.md when syntax is uncertain.

Read `scope_check` before publishing:

- `unmatched_header`: warn for each header item with no exact same-list scope text match;
  show its `header_id` (`HA1`/`HL1`), SQL lines, text and rationale. These labels identify the
  current header only, not persistent scope IDs. Near-matches need source review, not automatic
  duplicate items. Also inspect `rationale_differences` with the matching scope ID.
- `question_checks`: compare **every** open scope question with the header decisions and
  limitations, even when that header item already matches a scope item. The helper supplies
  both identities and wording, not a semantic conflict verdict. Warn when a header states
  as settled what the question leaves unresolved; quote the Q ID/text, header ID/lines/text
  and matching scope A/L ID if present. For example: `Q7 asks which ieMR codes hold Actim
  Partus; HA1 (lines 3–4, scope A14 if matched) selects code 123`. Apply the same check to
  limitations such as a PAMG note's ability to name PartoSure. Unrelated pairs are not warnings.

Put each mismatch to the engineer: add/reconcile the scope item and confirm its text and
rationale; request header rewording through `$data-request:fix`; or keep the question open
and explicitly record the header choice as **provisional implementation only**. For that last
option, confirm a scope item's rationale naming the Q ID, the header choice and the unanswered
analyst decision; have `$data-request:fix` make the header equally explicit. Confirmation is of
that boundary, not of the research answer. Do not close a question from an engineer's technical
choice or from adding an A/L item; only an actual answered closure follows the shared store
rules. Known restrictions still apply.

Re-run comparison after reconciliation. After SQL edits, also re-run fingerprint and the
SQL-change checks above; changed framing or item wording needs the appropriate reconfirmation.
Do not publish while a mismatch is unaddressed. If the matches are clean and no header settles
an open question (including explicitly acknowledged provisional choices), give no warning.
Semantic checking is the agent/source-review obligation, not something `publish` proves.

```bash
bash "$S/sqlreview.sh" publish "$SLUG" scope ".sqlreview/reviews/$SLUG/scope.draft.json" || exit $?
bash "$S/sqlreview.sh" publish-questions "$SLUG" ".sqlreview/reviews/$SLUG/questions.draft.json" || exit $?
```

Publish validates a staged copy and the next revision, then atomically replaces `scope.json`.
It re-proves every carried item against the previous document and authenticated historical render;
on refusal, re-run `carryforward` and walk what it lists. Never copy the draft into the final path.
Publish stores previous human revisions at `history/scope/<revision>.json` without SQL.
Header-only publication keeps the original full SHA, source commit and confirmations, recording
new header evidence in `header_revisions`. Unavailable history requires fresh reassessment.
Preserve the previous revision and increment it for confirmed semantic updates.

```bash
bash "$S/sqlreview.sh" render "$SLUG" scope || exit $?  # → reviews/<slug>/scope.md (never hand-write it)
rm -f ".sqlreview/reviews/$SLUG/scope.draft.json"
```


Show the rendered `scope.md`. Use `$data-request:map` for source mapping and
`$data-request:draft` to develop the scoped SQL. Next stage, once the SQL exists: `$data-request:analyse <sql path>`.
