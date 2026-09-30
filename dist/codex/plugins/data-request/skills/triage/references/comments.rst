Queue and comment formats
=========================

Read this when you write the triage output. In triage-only mode the human posts
everything; in both modes, copyedit human-facing text with
``/tech-writing:copyedit`` before handing it over.

Ordered queue
-------------

Number the queue, one line per request, highest first:

.. code-block:: text

   1. service-desk#901 ENQ9001 (THHSAQUIRE-9901) – Urgent label, 54 calendar days.
      Blocked: scaffold. Next: review PR 12 – owner.

Give the verified priority and its source, the age and how it was counted, the
primary blocker class, and the next action with its owner. List the exclusions
and unresolved inputs after the queue.

Paste-ready comment
-------------------

Write one comment per request in a fenced ``text`` block, so that it pastes
verbatim. Use assessment-only status in triage-only mode. Only use
``Proceeding on an engineer decision, flagged`` when authorised execution is actually
proceeding on an evidenced human decision; include its login, date and evidence.
For execution with no human decision, say ``Proceeding on agent-applied technical defaults``
or give the evidenced task status, not fabricated human provenance.
Omit ``Engineer decisions`` when no human decision is evidenced.
Only include ``Independent work continuing`` for work actually executed in an authorised run,
with its paths/evidence; in triage-only mode describe safe work as planned, not implemented.
Omit any other row with no evidenced entries, including confirmed requirements and questions.
Do not turn this assessment example into a completion claim:

.. code-block:: text

   Triage – ENQ9003 (THHSAQUIRE-9903)

   Status: Assessment only; no work executed in this run.
   Blocked (cannot proceed): clarification / requester-defined measure — dependent portion only;
   question, missing evidence and owner. Omit this line when nothing is blocked.
   Repository: rdl-service-desk/THHSAQUIRE-9903 (approval as written: THHSAQUIRE9903).
   Confirmed: population, window and outputs, each with its source.
   Engineer decisions: choice, actual login/date, rationale, SQL location and evidence.
   Agent-applied technical defaults: choice, rationale, evidence; engineer review, not human-confirmed.
   Proposed research choices, awaiting confirmation: each with its reason.
   One batched message for the analyst to consult the requester:
   1. Remaining authority question and class. Proposed default: safe unchanged scope,
      with evidence (for V2, the V1 answer: confirm or change), or no executable measure default.
   Planned safe work (not implemented): independent portions and supported technical defaults.
   Offered extras (not built): optional output for a later instruction.
   Next action: one action – owner.

Keep confirmed requirements, flagged engineer decisions, agent defaults and
proposed research choices on separate lines. "Blocked (cannot proceed)" must
name a guardrails authority class (governance, cohort expansion, released grain,
requester-defined measure) or an evidenced operational class from ``checks.rst``;
never report a technical choice merely as "waiting for the analyst". When a
deliverable PR is ready for review, add the hand-off comment and the board moves
from ``handoff.rst``. Include no patient data, credentials or identifiers beyond
the enquiry, approval and issue references. In triage-only mode, end the reply by
stating that nothing was posted, pushed or changed in this run.
For an execution run, report the actual actions and evidence, including any work
not completed; do not use the triage-only no-change claim.
