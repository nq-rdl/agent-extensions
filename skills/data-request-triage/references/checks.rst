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
* **Source system and grain come before bootstrap.** ENQ1187's source moved from
  ieMR to HBCIS ``Inpatient.mart_v`` after its scope was published, which made
  that scope stale. Revising a published scope re-opens its confirmations.
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
* **Stale issue body.** A later dated amendment or comment supersedes the body.
  Cite both sources and carry the newer value.
* **Unanswered question.** Silence, a pending request for information or an
  assumption nobody contradicted is not approval.

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
