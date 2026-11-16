Carrying confirmations into a review
====================================

Read this when ``carryforward`` or ``carryover`` returns rows (analyse's update path, and
*Confirm, write, render*). Both commands are read-only. Publish re-proves every carried item.

Bases
-----

A ``basis`` is the evidence that an item's confirmation still holds.

``sql-unchanged``
   The SQL SHA is the same as at the previous revision (``carryforward``) or at scope publish
   (``carryover``).
``sql-body-unchanged``
   Only the leading comment header changed, such as the scope items copied into the SQL
   ``/* ... */`` header. The rest of the file is byte-identical. A comment edit after the first
   line of code is a change. A header that is not terminated, has a nested ``/*`` or mentions
   ``@extract:`` counts as a change. So does text after a lone CR in a header comment line (CR
   breaks lines for databases and editors), and a ``/*!`` or ``/*+`` opening (executable).
``lines-unchanged``
   The item's location lines are unchanged. ``carryforward`` allows a remap (same line count).
   ``carryover`` compares the draft's line numbers in both files, so a shifted item is not
   ``lines-unchanged`` there.
``scope-before-sql``
   ``carryover`` only. The scope was confirmed before the SQL existed (``sql_sha256: null``, no
   SQL source). The review adds each item's first ``location``.
``intent-unchanged``
   The SQL changed under a scope item with no location. A scope item states intent, not SQL
   lines. In ``carryforward "$SLUG" scope`` it carries without a question; in ``carryover`` it
   goes into ``carry_over_intent`` and is asked (below).

Changed text or rationale never carries. ``--reconfirm-all`` refuses every carried item.

Update path: ``carryforward``
-----------------------------

The re-walk rule (decided by the Data Engineer): after a change, walk only the items that the
change touches. Then ask **one** carry question for all the other items. The helper decides
what the change touches, from the diff and each item's recorded location. Do not add items to
the walk by your own judgement.

``walk``
   The items that the change touches. This includes changed text or rationale, governed lines
   that the diff changes or cannot re-locate, and a criteria row whose state or intake changed.
   When ``reproof_failed`` is true (exit 6), git cannot supply the recorded SQL with its SHA,
   so every item is in ``walk``. Walk each item.
``carry_question``
   Every other item. A ``carry`` row keeps the earlier confirmation. A ``bulk`` row keeps its
   wording, but the SQL changed under it because it has no location. Its answer is a fresh
   confirmation.

Run ``carry-list "$SLUG" carryforward <draft>`` before you ask. The one question lists each
item's id and its confirmed text, copied verbatim from ``carry-list.md``. Ids alone are not
enough. Options: **Carry all** / **Name the items to re-walk**. Do not mark either option
recommended. When the impact hints or your reading show an indirect effect on a listed item,
say so in the question. The human decides whether to re-walk it.

On **Carry all**, copy each ``carry`` row's ``set`` onto the item verbatim, ``carried_basis``
included. Give each ``bulk`` row fresh ``confirmed_*`` from the answer. The items that the human
names go to the walk. An unanswered question confirms nothing.

A ``walk`` or ``bulk`` row can list ``clear`` fields, such as ``carried_basis``. The draft item
still holds them from an earlier carry. Remove them before you record the fresh answer, or
``check`` and ``publish`` refuse the item.

When ``first_binding`` is true, the previous scope was confirmed before the SQL existed. Read the
SQL against each carried item. Move to the walk any item the SQL contradicts, such as an item
that names a table the SQL does not read.

An item marked ``sql_status: "not-implemented"`` states that this SQL does not implement it.
The mark carries like the text. ``carryover`` never carries such a scope item into the review.
It lists the item under ``not_implemented`` and in ``walk``.

Scope to review: ``carryover``
------------------------------

Before any question, check the SQL against each row. Move to the walk any item the SQL
contradicts. The rows come in two lists, asked as two questions. Each question shows every
item's id, text, rationale, basis and ``location`` lines, or uses ``carry-list`` (below):

``carry_over``
   The SQL under the item did not change (``sql-unchanged``, ``sql-body-unchanged``,
   ``lines-unchanged``). Options: **Carry over all (Recommended)** / **Walk each individually**.
``carry_over_intent``
   The SQL changed or did not exist when the scope was confirmed (``intent-unchanged``,
   ``scope-before-sql``). Also move to the walk any item that a changed part of the SQL touches.
   Show a one-line summary of the SQL delta since the scope's recorded commit (or "SQL written after the
   scope"). Options: **Carry over all** / **Walk each individually**, neither recommended.

Copy each row's optional ``decided`` object onto the draft item verbatim, separate from the new confirmer.
Preserve the original actor, role, source and date precision; do not invent an origin when absent.
Moving an item to the walk does not erase a decision origin that still applies.
Carry over confirms the listed items, their locations included, from that answer. It does not
replace decision origin with confirmation provenance. Walk moves them to the per-item walk.

Long lists: ``carry-list``
--------------------------

A carry question must show what it confirms. For the update path, always run ``carry-list``.
For the scope lists, run it when a list has more than four items. Use ``carryover`` for the
scope lists and ``carryforward`` for the ``carry_question`` list of an update:

.. code-block:: bash

   bash "$S/sqlreview.sh" carry-list "$SLUG" carryover ".sqlreview/reviews/$SLUG/review.draft.json"

It writes ``reviews/<slug>/carry-list.md`` with each item's stored text and rationale verbatim.
A criteria row shows its state, reason and flag. It prints the count, ids, bases and lines of
each list. The question shows each id with its confirmed text and gives the file path for the
rationale and basis. The answer confirms the listed items only. Delete the file after the answer.

Header to review: ``notes --against --confirmed-by``
---------------------------------------------------

``header_carry_over`` is eligibility for a fresh answer, not an old confirmation.
``header_settled`` lists the items that already hold a confirmation for this revision.
``header_walk`` leaves them out. Do not ask them again.
An explicit named engineer attribution must match the intended human handle exactly.
Show every kind/id, text, rationale, governed location, independent ``decided`` and
``evidence.commit`` / ``committed_at`` in ONE question: **Carry over all (Recommended)** /
**Walk each individually**. An unanswered or interrupted question does not count as a confirmation.

A date-only decision keeps that precision. Its first recorded source may be committed
on the same day; display the observed time and explain that unchanged-content evidence
starts then, not at midnight. A precise UTC ISO decision requires a source no later
than that instant. Git timestamps and handles are recorded claims, not authenticated
human identities. Read the source and ask the human; never treat ``roles`` or
``recorded_by`` as the confirmer.

Proof checks the selected source, every subsequent relevant path revision and the
committed source history, not just HEAD. Readable pre-source header/merge/time failures do not
poison a new decision; missing ancestry or objects still fail closed. The exact unique
governed snippet and its body prefix must survive; later lines may change, and leading comments may grow. Repeated snippets, relocation, body-prefix
changes, missing objects, shallow ancestry, nonmonotonic source times and path renames
are conservative walks. A merge is ambiguous when the SQL blob differs from any parent;
identical-path unrelated PR merges are allowed. Renames are not followed to invent a
source for a new path. These limitations affect batching, not the ability to review.

After the answered bulk question, copy ``decided`` verbatim, set fresh ``confirmed_*``
and ``carried_basis: header-decision`` only on its listed items. Never overwrite a
separate existing origin to match the helper's source; walk the mismatch. Publish
re-proves the basis and requires confirmation fields but cannot authenticate an answer.
Later carryforward preserves ``decided`` and uses its normal ``set`` fields, not a
fresh header claim. Changed or unproven items remain in the per-item walk.

Old SQL comes from ``git show`` at the recorded commit. Its full SHA must match the record.
Missing or corrupt evidence in git requires reassessment before all SQL-bound carry.
