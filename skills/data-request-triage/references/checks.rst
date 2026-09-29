Requirement checks and blocker taxonomy
=======================================

Read this when you settle a request's requirements and when you classify its
blockers. Each check comes from the September 2026 triage. Raise a finding as a
proposed assumption or a question for the requester, never as a decision.

Interpretation checks
---------------------

* **Approval restrictions come first.** Read the approval (screening log,
  governance comment or approval letter) before the intake's field list. A
  screening-log approval limits the output to screening fields. Contact,
  identity and pathology fields from the intake stay out, and the report says
  why. Reconcile fields added during review (death dates, lab organisation,
  accession number) with the approval before delivery.
* **Source system and grain come before bootstrap.** In one request the source moved
  from ieMR to HBCIS ``Inpatient.mart_v`` after its scope was published, which
  made that scope stale. Revising a published scope re-opens its confirmations.
* **Date windows.** A window written as ``BETWEEN '2021-01-01' AND
  '2025-12-31'`` on a datetime column drops most of 31 December. Propose a
  half-open window (on or after the start, before the day after the end) and
  confirm it with the requester.
* **Time zone.** ieMR stores UTC, while HBCIS and BI-Reporting store AEST.
  Decide the delivery time zone explicitly, and verify each field through
  ``/data-request:guardrails``.
* **Raw versus derived.** Ask for raw dated events rather than derived outcomes
  (early or late stroke, death within a number of days) unless the approval asks
  for derived ones.
* **Supplied cohort.** When the requester supplies the cohort (a URN list or a
  prior extract), the work is linkage to that supplied cohort. Do not plan cohort
  discovery or map inclusion criteria.
* **Explicit code list.** Use the requested codes exactly. A library concept with
  a different code set is a mismatch to raise, not a substitute: an aneurysm
  concept that adds I71.8 to a request for I71.3 and I71.4 broadens the cohort.
* **Internal range conflict.** One field can name a code range that is wider
  than the conditions it also names: C00 to C80 beside eight named cancer types.
  This is a conflict inside the request, not a library-concept broadening. Raise
  it as a clarification for the requester, and propose the narrower reading (the
  named conditions) as the default.
* **Classification edition change.** A window can span a change of coding
  edition, such as ICD-10-AM 12th to 13th edition. Name the edition in force at
  each end of the window, and list the requested code sets and reference tables
  (code lookups, library concepts, DRG or grouper tables) to re-verify for codes
  that were added, retired or retitled. Record the edition as an assumption.
* **Ethnicity.** The records hold no ethnicity field. When a request asks for
  ethnicity, propose Indigenous status from ``PERSON_INFO`` (the RDL convention)
  and ask once, during scoping, whether to add country of birth or preferred
  language as optional surrogates; the requester or engineer decides. Record the
  limitation that ethnicity is not held. ``/data-request:guardrails`` owns the
  convention.
* **Stale issue body.** A later dated amendment or comment supersedes the body.
  Cite both sources and carry the newer value.
* **Verbal decision.** When a decision given in a call or a chat contradicts the
  newest written comment, ask the decider for a written, dated comment. Until it
  exists, record the decision as unlinked in the ledger, and show both values in
  the triage comment as a conflict to settle.
* **Recorded decision origin.** Read current ``scope.json`` and ``review.json``
  items when present. An absent or ``unlinked (verbal)`` ``decided.source`` for
  an attributed requester or other third-party decision is a clarification blocker:
  name the item, decider and reported date, and ask for a dated written source.
  An engineer confirmation does not supply that source or establish the requester's
  authority. Copy the evidence to the ledger without marking the decision linked.
  An engineer's own technical choice is not an unanswered governance blocker;
  governance requires a known approval restriction or custodian decision.
  Legacy items without ``decided`` remain readable: check attributed rationales
  against written evidence rather than inventing an origin or blocking every item.
* **Unanswered question.** Silence, a pending request for information or an
  assumption nobody contradicted is not approval.

Open questions
--------------

Give each open question a proposed default, so that the engineer can accept it as
a scope assumption or send it to the requester. Before you ask, look for a prior
version of the request: a V2 request's V1 repository, its SQL and its delivery.
When the prior version answers the question, turn it into a confirm-or-change
question that quotes the prior answer and its source. In September 2026, reading
a V1 request's SQL removed the last open question for its V2. A default is a proposal;
it becomes a requirement only when a named human accepts it.

Blocker taxonomy
----------------

Give each blocker one primary class and the action that unblocks it.

clarification
   The request has more than one reasonable reading, or a decision belongs to
   the requester. Unblock with a question in the paste-ready comment.

source availability
   The data is not in any source the team can reach, or access is not granted.
   Name the source and whoever can grant or confirm it.

governance
   The approval, a screening-log restriction or a data custodian limits a field
   or an action. Unblock through the approver; never widen the output meanwhile.

scaffold
   The child repository is a legacy shell, unapplied or outdated, or carries a
   workflow hazard. Propose the step; agents never run ``copier update``.

dependency
   The request waits on another repository's change, release or re-pin. Record
   the order in the ledger's ``depends_on``.

correctness bug
   An existing library unit or pipeline produces a wrong result. Fix it upstream
   with a regression test, through ``/data-request:fix`` or ``/data-request:lift``.

missing capability
   After a recheck against the current release, the library lacks the unit the
   request needs. Capture it through ``/data-request:lift``.
