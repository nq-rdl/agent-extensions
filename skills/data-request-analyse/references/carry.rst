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
   ``@extract:`` counts as a change.
``lines-unchanged``
   The item's location lines are unchanged (a remap is allowed; the line count is not).
``scope-before-sql``
   ``carryover`` only. The scope was confirmed before the SQL existed (``sql_sha256: null``, no
   baseline). The review adds each item's first ``location``.
``intent-unchanged``
   The SQL changed under a scope item with no location. A scope item states intent, not SQL
   lines. In ``carryforward "$SLUG" scope`` it carries without a question; in ``carryover`` it
   goes into ``carry_over_intent`` and is asked (below).

Changed text or rationale never carries. ``--reconfirm-all`` refuses every carried item.

Update path: ``carryforward``
-----------------------------

``carry`` items keep their confirmation. Copy each ``set`` onto the item verbatim,
``carried_basis`` included, and do not ask again.

``bulk`` items keep their wording, but the SQL changed under them: no location, or a location
added or removed. Move to the walk any bulk item the hunks or hints implicate. Then put the rest
in **one** AskUserQuestion. It shows a one-line summary of the SQL delta, then each item's id,
text, rationale and ``location`` lines (``null`` means the whole SQL). Options: **Carry these N
forward** / **Walk each individually**. Do not mark either option recommended: the SQL changed.
The answer is a fresh confirmation for this revision (``confirmed_*`` from the answer).

Scope to review: ``carryover``
------------------------------

Before any question, check the SQL against each row. Move to the walk any item the SQL
contradicts. The rows come in two lists, asked as two questions, each listing every item's id,
text, rationale, basis and ``location`` lines:

``carry_over``
   The SQL under the item did not change (``sql-unchanged``, ``sql-body-unchanged``,
   ``lines-unchanged``). Options: **Carry over all (Recommended)** / **Walk each individually**.
``carry_over_intent``
   The SQL changed or did not exist when the scope was confirmed (``intent-unchanged``,
   ``scope-before-sql``). Also move to the walk any item that a changed part of the SQL touches.
   Show a one-line summary of the SQL delta since ``scope.source.sql`` (or "SQL written after the
   scope"). Options: **Carry over all** / **Walk each individually**, neither recommended.

Carry over confirms the listed items, their locations included, from that answer. Walk moves
them to the per-item walk.
