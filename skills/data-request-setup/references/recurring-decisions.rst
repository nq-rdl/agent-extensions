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
* ``match``: lowercase term groups. An item matches when its text or rationale contains one
  term of every group as a whole word or phrase (case-insensitive). ``match`` checks only the
  list of the same kind (assumptions or limitations); ``--any-kind`` checks both.
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
changes a confirmation. Their output rows do not include it: when you re-draft an item that
they carry, copy ``upstream`` from the prior or scope item. Do not
mark an item that matches no listed decision. If you see a new recurrence, report it for the
lift close-out.

Close out (lift)
----------------

1. Run ``marked`` on the slug's ``scope.json`` and ``review.json``. It groups the items by
   decision, so an item in both records is one decision. Report them as **upstream decision
   candidates**, next to the three hand-SQL buckets. They are not lift-ledger entries: they
   have no workaround and do not authorise hand SQL.
2. Find the target issue for each decision. Use ``library_issue`` if it is set. If it is null,
   search the owning library's open and closed issues for an equivalent unit. If there is
   none, the target is the tracking epic. Several decisions can share one target.
3. Prevent duplicates for each pair of enquiry and decision ``id``. Read the target issue and
   its comments. If they already cite this enquiry for that decision, link the issue and add
   nothing for that pair. A comment that cites the enquiry for another decision does not count.
4. Put one evidence comment per target issue to the human (**Confirm** / **Reword** /
   **Reject**). It lists every remaining decision for that target: the decision ``id``, the
   enquiry, the ticket, the item ids and the confirmed wording. It never contains patient
   data. Add it only after confirmation.
5. File a new library issue only when all of these are true: ``library_issue`` is null, the
   search in step 2 found nothing, and the human confirms that the decision needs its own
   library unit. Otherwise use the target from step 2. Link the tracking epic from a new
   issue. After an uncertain response, search before you retry.
6. Propose a list change, as a pull request that edits the canonical list file, when:

   * you filed a new issue in step 5: set that entry's ``library_issue`` to it, so the next
     enquiry does not search and file again;
   * ``known`` is false, or you found a recurrence that the list does not have: add the entry
     and a row on the tracking epic.

   Never edit the installed plugin copy.
7. If the target issue is closed, check for a release that contains the unit. If one exists,
   propose to retire the entry (``status: retired`` and ``retired_by``) in the same way.

Report each decision with its target issue and what you did: linked, commented or filed, and
any proposed list change. Do not call a decision filed until the write has succeeded.

Maintain the list
-----------------

Edit only the canonical file. Put the enquiry evidence in a row on the tracking epic, not in
this file, and link that row from ``evidence``. Set ``updated``. Keep every proposal in short,
plain sentences, because bootstrap and analyse offer it verbatim. Keep match terms lowercase. Run ``tests/test_data_request_recurring_decisions.py`` before you open the
pull request.
