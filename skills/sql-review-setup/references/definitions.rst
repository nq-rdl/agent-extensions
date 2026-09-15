SQL Review — shared definitions
===============================

These definitions are the single source of truth for every ``/sql-review:*`` stage. They ship as
the ``definitions`` object in the bundled default ``assets/sqlreview/config.json`` and are copied
into the project's ``.sqlreview/config.json`` by ``/sql-review:setup``. Bootstrap, analyse and
explain read them from the project config at run time and never restate them; edit the project's
``config.json`` (via ``/sql-review:setup``) to change the wording for one project, or this file and
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
``confirmed_revision``. These fields are filled only from an answered ``AskUserQuestion``; the
PreToolUse guard rejects a review or scope document in which any item lacks them or was confirmed
for an earlier revision. On every update the whole list is re-put to the human — a confirmation
never survives a revision it was not given for.
