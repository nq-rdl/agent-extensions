Data Request — shared definitions
=================================

These definitions are the single source of truth for every ``/data-request:*`` stage. They ship as
the ``definitions`` object in the bundled default ``assets/sqlreview/config.json`` and are copied
into the project's ``.sqlreview/config.json`` by ``/data-request:setup``. Bootstrap, analyse and
explain read them from the project config at run time and never restate them; edit the project's
``config.json`` (via ``/data-request:setup``) to change the wording for one project, or this file and
the asset together to change the default for everyone.

Assumption
----------

**Decision points made by the RDL.** A choice the RDL (the Data Engineer's team) made where the
request, the data, or the business rule left room for more than one reasonable reading — for
example "a stay is complete when ``discharge_date`` is populated", or "transfers between wards
count as one stay". Each assumption is recorded with an id (``A1``, ``A2`` …), the decision, its
rationale, the SQL lines it governs, and who confirmed it.

Limitation
----------

*Draft — the epic (#131) marks this as still to be defined; ratify or replace it there.*

**A constraint on what the output can be relied on for that arises from the data, the source
system, or the request rather than from an RDL decision.** For example "the source only holds
admissions from 2019", or "ward codes were re-keyed in 2023 and older rows are not remapped".
Recorded (``L1``, ``L2`` …) so the analyst knows where the result must not be over-read.

Telling them apart
------------------

Ask *who could have chosen otherwise*. If the RDL could have decided differently, it is an
assumption. If nobody in the RDL could change it without different data or a different request,
it is a limitation. When both apply (a decision made *because of* a constraint), record the
constraint as a limitation and the choice as an assumption that references it.

Confirmation record
-------------------

Every assumption and limitation carries ``status``, ``confirmed_by``, ``confirmed_at`` and
``confirmed_revision``. Fill these from an answered ``AskUserQuestion`` or preserve
an evidenced imported confirmation: analyst intake (``analyst-intake.rst``) or the
exact recorded TUH house default (``recurring-decisions.rst``). A generic decision
origin or upstream marker supplies no confirmation. Never fabricate one. The
PreToolUse guard rejects a review or scope document in which any item lacks them.

``confirmed_revision`` is the revision at which a human confirmed the item. A freshly confirmed
item has ``confirmed_revision`` equal to the document ``revision``. On an update, an item may
instead be *carried* from the previous published revision: it keeps that revision's
``confirmed_by``, ``confirmed_at`` and ``confirmed_revision`` and records
``carried_from_revision`` (always ``revision - 1``). ``sqlreview.sh publish`` allows a carried item
only when the previous revision has the same id in the same list with identical text, rationale, decision origin and
confirmation, and its governed SQL is unchanged: the item's location lines (remapping allowed, the
line count may not change), or, with no location, the whole SQL. ``sqlreview.sh carryforward`` lists
which draft items qualify; every other item is re-put to the human. ``publish --reconfirm-all``
refuses carried items when a full re-walk is wanted.

Recorded identity
-----------------

Every ``by`` and ``*_by`` field (``confirmed_by``, ``recorded_by``, ``decided_by``,
``resolved_by``, the ``by`` of ``changes`` and ``explain.json``) records a person by handle: the
GitHub login where known, else ``git config user.name``. If neither is available, ask. Never use
``git config user.email``: these records are committed, so an email address in one is published
with the request. ``sqlreview.sh check``, ``release.sh check`` and the guard refuse any such value
that contains ``@``.

Lift candidate
--------------

A request need whose pinned library capability was inspected and found insufficient,
recorded before hand-written SQL or inline modelling so close-out can distinguish
reusable library work from request-specific composition. Its id is ``LIFT-n``;
classification is new-capability, existing-unit-gap or request-specific. Capture is
silent and unconfirmed. Only answered human questions supply confirmation fields.
See ``lifts.rst`` for independent entry revisions and the publication contract.

Decision origin
---------------

Scope and review assumptions and limitations may carry optional ``decided``
with four nonempty string fields: ``by`` (the human's handle), ``role`` (requester,
engineer, custodian or the role in the evidence), ``at`` (decision date or ISO time),
and ``source`` (comment/PR URL, dated document reference or ``unlinked (verbal)``).
Omit it when unknown; do not insert null or infer a reliable history from rationale
dates. Schema 1 and 2 records without it remain valid. This is separate from
``confirmed_by``: a requester may decide while an engineer confirms the item.
It records the available evidence, not authority or governance clearance.

``check`` validates its shape and refuses emails in ``decided.by``. ``render``
shows origin beside confirmation, with an UNLINKED marker for verbal sources.
Plain ``lint`` and ``lint --ste`` warn on unlinked explicit provenance at any
status, and on a rationale attributing a decision to a role or a named person
without a written source. This heuristic cannot identify all names or certify
that a reference is real; verify the source against the original document.
Keep origin unchanged across scope-to-review carryover and revision carryforward;
changing, adding or removing it requires fresh confirmation.
