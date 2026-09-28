Recurring scope decisions
=========================

Some assumptions and limitations get the same answer in every enquiry. Examples are the raw
ieMR date of death and the ieMR result validity bundle. Each repeat is a signal that the
library should answer the decision once. This is a different signal from the lift ledger
(``lifts.rst``): the ledger records hand SQL, and a recurring decision can occur with no hand
SQL at all.

One home
--------

The list lives in one file: ``assets/recurring-decisions.json`` in this skill (canonical source
``skills/data-request-setup/assets/recurring-decisions.json`` in ``nq-rdl/agent-extensions``).
Do not copy its entries into a skill, a project, ``.sqlreview/`` or a record. Read it through
the helper beside ``sqlreview.sh`` (``$S`` is this skill's ``scripts`` directory):

::

  bash "$S/recurring-decisions.sh" list              # the whole list
  bash "$S/recurring-decisions.sh" match DRAFT       # HINTS ONLY: draft items that match a listed decision
  bash "$S/recurring-decisions.sh" marked RECORD...  # items with an upstream marker (for lift)

nq-rdl/query-builder#172 is the tracking epic and the evidence log. Each entry names the
library issue that would retire it. Each entry has these fields:

* ``id``, ``title``, ``kind`` (``assumption`` or ``limitation``) and ``status`` (``open`` or
  ``retired``).
* ``proposal``: the ``text`` and ``rationale`` to offer. This is the prior wording.
* ``match``: term groups. An item matches when its text or rationale contains one term of
  every group (case-insensitive).
* ``evidence``: links to the library issue rows that name the prior enquiries, their tickets
  and the item ids. This repository is public, so the list never names an enquiry. The
  per-enquiry evidence stays in the private library issue.
* ``library_issue`` (URL or null), ``related_issues``, and ``retired_by`` (``{unit, version}``
  when retired).

Detect (bootstrap and analyse)
------------------------------

1. Before you draft candidate items, run ``list``. For each open decision that applies to the
   request's sources and outputs, offer the listed text and rationale as the candidate item.
2. Before each batch of questions, run ``match`` on the draft. The result is a set of hints.
   Decide each hit yourself. A miss does not prove that no listed decision applies.
3. For each match, read the prior enquiries from the ``evidence`` links at run time
   (``gh issue view <number> --repo <owner/repo> --comments``). Show them in the question
   (enquiry, ticket and item ids) with the library issue. If you cannot read the links, show
   them and say that the prior enquiries are not available. Offer the listed wording as the
   proposal, unless this request needs a different reading. Say that the item is an upstream
   candidate. Do not copy enquiry ids into this list or into a skill.
4. Mark the item with ``"upstream": {"decision": "<id>"}``. Human confirmation is still
   required: the options stay **Confirm** / **Reword** / **Reject**. A rejected item is not
   published. After a reword, keep the marker only if the item still states the listed decision.
5. For a ``retired`` decision, do not ask the question again as a new decision. Check that the
   pin contains ``retired_by.unit`` at ``retired_by.version``, compose that unit, and cite it.
   If the pin is older, ask as before and name the unit as the upgrade path.

The marker is metadata. ``publish``, ``carryforward`` and ``carryover`` ignore it, so it never
changes a confirmation. Keep the marker when an item is carried forward or carried over. Do not
mark an item that matches no listed decision. If you see a new recurrence, report it for the
lift close-out.

Close out (lift)
----------------

1. Run ``marked`` on the slug's ``scope.json`` and ``review.json``. Report the items as
   **recurring decisions**, next to the three hand-SQL buckets. They are not lift-ledger
   entries: they have no workaround and do not authorise hand SQL.
2. Find the target issue. Use ``library_issue`` if it is set. If it is null, search the owning
   library's open and closed issues for an equivalent unit. If there is none, use the tracking
   epic.
3. Prevent duplicates. Read the target issue and its comments. If they already cite this
   enquiry (the ENQ id or the ticket), link the issue and add nothing.
4. Otherwise, put the evidence comment to the human (**Confirm** / **Reword** / **Reject**).
   The comment gives the enquiry, the ticket, the item ids, the decision ``id`` and the
   confirmed wording. It never contains patient data. Add it only after confirmation.
5. File a new issue only when the human confirms that the decision needs its own library unit
   and no issue exists. Link the tracking epic from it. After an uncertain response, search
   before you retry.
6. If ``known`` is false, or you found a recurrence that the list does not have, propose a list
   change: a row on the tracking epic and a pull request that edits the canonical list file.
   Never edit the installed plugin copy.
7. If the target issue is closed, check for a release that contains the unit. If one exists,
   propose to retire the entry (``status: retired`` and ``retired_by``) in the same way.

Report each recurring decision with its target issue and what you did: linked, commented or
filed. Do not call a decision filed until the write has succeeded.

Maintain the list
-----------------

Edit only the canonical file. Put the enquiry evidence in a row on the tracking epic, not in
this file, and link that row from ``evidence``. Set ``updated``. Keep every proposal in short, plain sentences, because bootstrap and analyse
offer it verbatim. Run ``tests/test_data_request_recurring_decisions.py`` before you open the
pull request.
