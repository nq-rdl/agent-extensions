Shared questions (#437)
=======================

``.sqlreview/reviews/<slug>/questions.json`` is the single mutable question
record. Scope and review remain SQL-bound documents: question closure changes
neither their bytes, revisions, confirmations nor SQL snapshots. Never run
carryforward merely to close a question. A resulting change in cohort meaning
still requires bootstrap/analyse; the closure itself does not approve SQL.

Record format (independent schemaVersion 1, no revision)::

  {
    "schemaVersion": 1, "kind": "questions", "slug": "q", "sql_path": "q.sql",
    "questions": [
      {"id": "Q1", "text": "Which wards?", "applies": "scope",
       "owner": "requester-login", "status": "open"},
      {"id": "Q2", "text": "Count transfers?", "applies": "review",
       "owner": null, "status": "closed",
       "closed": {"answer": "Exclude transfers.", "by": "engineer-login",
                  "at": "2026-09-29", "source": "request.md#answer"},
       "decided": {"by": "requester-login", "role": "requester",
                   "at": "2026-09-28", "source": "request.md#decision"}}
    ]
  }

``applies: scope`` is shared: both reports show it. ``applies: review`` is
SQL-specific and shown only by review. ``owner`` is the responsible human handle,
not a config role/display label; use null when unknown. IDs are unique ``Q1``,
``Q2``, ... within the slug; append unused IDs, never recycle them. Text and
applicability are immutable after publication. If wording needs correction, add
a new ID, then close the old one with a supersession answer and actual evidence.
Closed rows cannot be deleted, reopened or edited; retain their audit history.

Closure requires a human answer and provenance: ``closed.by`` records who supplied
or recorded the closure, ``at`` preserves the actual date/time precision, and
``source`` points to the answer. Use ``unlinked (verbal)`` honestly where necessary;
check the source, do not infer approval from a timestamp or status. Optional
``decided`` is independent decision origin, following #434's ``by,role,at,source``
convention, not an engineer confirmation. Unknown origin stays omitted. Closure
must not turn an engineer technical choice into an analyst research answer.

Commands (``S`` is the installed setup scripts directory)::

  bash "$S/sqlreview.sh" questions "$SLUG" scope    # read-only, scope questions
  bash "$S/sqlreview.sh" questions "$SLUG" review   # shared + review-only, including closed rows
  bash "$S/sqlreview.sh" migrate-questions "$SLUG"  # optional one-time legacy migration
  bash "$S/sqlreview.sh" publish-questions "$SLUG" ".sqlreview/reviews/$SLUG/questions.draft.json"

For new work, publish scope/review with ``question_store: "questions.json"``
instead of ``open_questions``; then publish the question draft before rendering.
The first store may contain only open rows (including an empty list); to close
one, publish an answered update. If the first question publication fails, retain
the draft and report the handoff incomplete. A missing declared store is invalid
for readers. Reads/render never create or migrate it implicitly.

For old work, migrate first. Scope strings come first, then review-only strings;
only exact identical strings are deduplicated, never semantic near-matches.
No owner, decision or closure is invented. Embedded arrays stay byte-identical
historical input; after migration the store is authoritative, so a closed legacy
string is not still open. Retry preserves IDs and closures. New unmatched legacy
strings fail visibly rather than disappear. To reconcile a mistaken legacy edit,
append the missing question with a new ID through ``publish-questions``; its staged
draft must cover every legacy string before readers accept it. Existing closed
rows and IDs remain unchanged. Subsequent semantic revisions can
replace historical arrays with ``question_store``; do not republish just for that.

To add/close: load ``questions`` first, retain all existing rows, write the complete
``questions.draft.json``, then run ``publish-questions``. Direct Write/Edit of the
final store is guard-denied. The helper validates identity, closure evidence,
bindings and retained history before one atomic rename; failures leave it intact.
Publication and migration share a per-slug ``.questions.lock`` directory, acquired
before loading history. A busy lock fails with exit 2: reload the current store,
reconcile your draft and retry. Normal exits and handled signals remove the lock.
After an uncatchable termination, remove a leftover lock with ``rmdir`` only after
verifying no writer remains; never steal an active lock. No SQL is required, and
missing SQL does not block a governance closure. Rerender reports explicitly after
publication when needed; closure alone edits one file.
Readers must fetch questions on every resume, even when document revisions match.
Reports keep ``open_questions_list`` open-only; default templates show closed rows
under ``Closed questions`` via ``question_history_list``. Existing custom templates
are not overwritten: add that history placeholder explicitly to display closures.
Release evidence emits ``applies: invalid`` and exit 10 for malformed or missing
declared question stores, just as for invalid review documents; unknown refs/slugs
and unsafe paths remain operational errors (exit 2).

Do not maintain a second question list in review or seed one from scope. If an
``answers.yaml`` copy predates this store, surface the obsolete copy and reconcile
it in its owning intake workflow; do not silently treat its stale status as live.
The store does not automatically edit analyst intake or external tickets. Release
evidence exposes structured ``questions`` plus open-only text ``open_questions``
for compatibility. Evidence uses current working handoff records against the
requested SQL ref, not historical question status at that ref; label it accordingly.
