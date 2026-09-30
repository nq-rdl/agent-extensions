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

Header to review: ``notes --against --confirmed-by``
---------------------------------------------------

``header_carry_over`` is eligibility for a fresh answer, not an old confirmation.
An explicit named engineer attribution must match the intended human handle exactly.
Show every kind/id, text, rationale, governed location, independent ``decided`` and
``evidence.commit`` / ``committed_at`` in ONE question: **Carry over all (Recommended)** /
**Walk each individually**. No answer or an interrupted question supplies no confirmation.

A date-only decision keeps that precision. Its first recorded source may be committed
on the same day; display the observed time and explain that unchanged-content evidence
starts then, not at midnight. A precise UTC ISO decision requires a source no later
than that instant. Git timestamps and handles are recorded claims, not authenticated
human identities. Read the source and ask the human; never treat ``roles`` or
``recorded_by`` as the confirmer.

Proof checks every subsequent relevant path revision and the working tree, not just
HEAD. The exact unique governed snippet and its body prefix must survive; later lines
may change, and leading comments may grow. Repeated snippets, relocation, body-prefix
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
