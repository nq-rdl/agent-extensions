Requirement checks and blocker taxonomy
=======================================

Read this when you settle a request's requirements and when you classify its
blockers. Apply guardrails' "Engineer decisions: proceed and flag" first:
evidenced technical choices proceed within the agreed task and are flagged,
not parked as analyst questions. Keep human decisions distinct from agent defaults.

Read-only stale lift check
-------------------------

For each existing ``lifts.json``, read the stale-check contract at
``${CLAUDE_PLUGIN_ROOT}/skills/setup/references/lifts.rst``. Discover the latest
stable tag of the entry's owning library through the shared tag-list policy at
``${CLAUDE_PLUGIN_ROOT}/skills/guardrails/references/library.rst``. Run the shared
helper's ``lifts-stale SLUG --tag TAG`` in the child's read-only checkout/scratch
view; it never edits a ledger. Mixed-library ledgers need a run per library's
latest tag, using only matching-library rows from each result.

Include messages in queue output and paste-ready comments, e.g. "LIFT-1 may be
resolved in v0.7.0" (example, not a baseline). Name partly resolved units and
remaining shortfalls; report unknown access/tags and untracked legacy entries.
Do not initialise a store, publish or render, update pins/statuses or adopt a unit.
Symbol presence is not behavioural or approval evidence; route an undelivered
candidate to lift for a human-decided re-pin. If execution is unavailable, perform
equivalent read-only tagged-tree inspection with the GitHub read tools and
disclose the missing capability. Never treat inaccessible evidence as absence.

Interpretation checks
---------------------

* **Known approval restrictions come first.** Apply explicit restrictions in an
  available screening log, governance comment or approval letter. A
  screening-log approval limits the output to screening fields. Contact,
  identity and pathology fields from the intake stay out, and the report says
  why. If the approval is unchecked, build the requested fields, including death
  dates, lab organisation and accession number; the analyst checks them against
  the approval during review. Follow the build/review rule in
  ``/data-request:guardrails`` ("Approved enquiry: build, then analyst review").
  Do not turn unchecked coverage into a blocker or recurring scope question.
* **Source system and grain come before bootstrap.** In one request the source moved
  from ieMR to HBCIS ``Inpatient.mart_v`` after its scope was published, which
  made that scope stale. Settle technical readings with the engineer, not the
  analyst; a released-output row-count change needs an analyst/requester answer.
  Revising a published scope re-opens its confirmations.
* **Date windows.** A window written as ``BETWEEN '2021-01-01' AND
  '2025-12-31'`` on a datetime column drops most of 31 December. Propose a
  half-open window (on or after the start, before the day after the end) to the
  engineer, proceed and flag when it implements the requested full-day range.
  A different research window is not a technical default.
* **Time zone.** ieMR stores UTC, while HBCIS and BI-Reporting store AEST.
  Decide the delivery time zone explicitly, and verify each field through
  ``/data-request:guardrails``.
* **Raw versus derived.** Deliver the requested raw dated events or supported
  derived outcomes, respecting known approval restrictions. An unsupported
  clinical outcome definition goes to the analyst; do not invent it.
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
  and offer country of birth or preferred language in the hand-off as unbuilt
  optional surrogates; do not add them unasked. Record the
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
  assumption nobody contradicted is not approval to cross an authority boundary.
  It does not block evidenced technical defaults or independent work.

Open questions
--------------

Give each open question a proposed default, so that the engineer can accept it as
a scope assumption or send it to the requester. Before you ask, look for a prior
version of the request: a V2 request's V1 repository, its SQL and its delivery.
When the prior version answers the question, turn it into a confirm-or-change
question that quotes the prior answer and its source. In September 2026, reading
a V1 request's SQL removed the last open question for its V2. A proposed default
is not human confirmation until a named human accepts it; an engineer-owned
technical choice is not a clarification blocker. Batch remaining research
questions into one analyst message, each with a default and evidence. Keep
building independent portions and safe defaults; do not execute a prohibited
output, cohort expansion, released grain change or invented clinical definition.

Blocker taxonomy
----------------

Give each blocker one primary class, the dependent portion, evidence, owner
and action that unblocks it. Distinguish authority questions from operational
failures; technical defaults are not blockers.

clarification
   Name the authority subclass: cohort expansion beyond the request,
   released-output grain change affecting row count, or unsupported requester
   clinical definition. Stop only dependent work; batch a question and default
   in the analyst message. Preserve the requested cohort and released grain
   meanwhile. Mere technical ambiguity is not this class.

source availability
   The data is not in any source the team can reach, or access is not granted.
   Name the source and whoever can grant or confirm it.

governance
   A known approval restriction (including a screening-log restriction) or a
   custodian decision limits a field or an action. Cite that evidence and unblock
   through the approver or custodian; never widen the output meanwhile.
   Unchecked approval alone is not a governance blocker. Build the requested
   elements and, if useful, carry one approval-sensitive limitation to analyst
   review, not an open question or Ben note item.

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
