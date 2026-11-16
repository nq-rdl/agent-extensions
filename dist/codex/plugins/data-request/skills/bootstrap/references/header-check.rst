Read the SQL header comparison
==============================

Read this after ``sqlreview.sh notes "<sql path>" --against ... --questions ...`` in
"Check the SQL header before publish" in the bootstrap ``SKILL.md``.

Staged questions
----------------

With a published sibling ``questions.json``, comparison validates the staged questions against
its identity/history invariants before emitting pairs: retain every ID and its text/applicability,
keep closed rows unchanged, and add only open questions. Fix a rejected draft before publication.

Read ``scope_check``
--------------------

Read ``scope_check`` before publishing:

- ``unmatched_header``: warn for each header item with no exact same-list scope text match;
  show its ``header_id`` (``HA1``/``HL1``), SQL lines, text and rationale. These labels identify the
  current header only, not persistent scope IDs. Near-matches need source review, not automatic
  duplicate items. Also inspect ``rationale_differences`` with the matching scope ID.
- ``question_checks``: compare **every** open scope question with the header decisions and
  limitations, even when that header item already matches a scope item. The helper supplies
  both identities and wording, not a semantic conflict verdict. Warn when a header states
  as settled what the question leaves unresolved; quote the Q ID/text, header ID/lines/text
  and matching scope A/L ID if present. For example: ``Q7 asks which ieMR codes hold Actim
  Partus; HA1 (lines 3–4, scope A14 if matched) selects code 123``. Apply the same check to
  limitations such as a PAMG note's ability to name PartoSure. Unrelated pairs are not warnings.

Resolve each mismatch
---------------------

Put each mismatch to the engineer: add/reconcile the scope item and confirm its text and
rationale; request header rewording through ``/data-request:fix``; or keep the question open
and explicitly record the header choice as **provisional implementation only**. For that last
option, confirm a scope item's rationale naming the Q ID, the header choice and the unanswered
analyst decision; have ``/data-request:fix`` make the header equally explicit. Confirmation is of
that boundary, not of the research answer. Do not close a question from an engineer's technical
choice or from adding an A/L item; only an actual answered closure follows the shared store
rules. Known restrictions still apply.

Re-run comparison after reconciliation. After SQL edits, also re-run fingerprint and the
SQL-change checks in "SQL that changes during the interview"; changed framing or item wording
needs the appropriate reconfirmation.
Do not publish while a mismatch is unaddressed. If the matches are clean and no header settles
an open question (including explicitly acknowledged provisional choices),
there is nothing to report; publish.
Semantic checking is the agent/source-review obligation, not something ``publish`` proves.
