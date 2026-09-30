Modelling choices: sequences and ethnicity
==========================================

Read this when a request defines a cohort by the order of events, or asks for
ethnicity. It extends "Leave modelling choices to the researcher" in ``SKILL.md``
(issues #374 and #386).

Cohort sequence or transition date
----------------------------------

A "first X, then later Y" definition is a researcher modelling choice. In one
paediatric-to-adult transition request, the requester had to choose:

* **The paediatric rule:** the clinic label, age under 18, or both; and whether the
  rule is a hard gate or a check only.
* **The transition date:** the first adult appointment after the first paediatric
  appointment, the first adult appointment after the last paediatric appointment, or
  the referral date.
* **The attended states:** which appointment states count as an attended
  appointment, on each side of the transition.

Supply the dated events with their states and labels. Ask the researcher to settle
each choice, and express the answers in the request's spec composition. Never pick
an ordering rule or a state list as a default.

Ethnicity
---------

RDL sources hold no ethnicity field. By RDL convention:

* An "ethnicity" request gets Indigenous status from ieMR ``PERSON_INFO``
  (``WithIndigenousStatus``). It is collected regularly and is relevant to First
  Nations studies.
* Offer country of birth and preferred language as optional surrogates. The
  requester or engineer decides whether to include them.
* Record a limitation that ethnicity is not held.

Inspect the request's pinned query-builder enrichment for either surrogate before
claiming a gap. Candidate sources to verify are ieMR ``PERSON.LANGUAGE_CD`` and the HBCIS ``mart_patient_view``
birth-country and language columns (see ``schema_extracts/``). Compose a surrogate
over a local ``TypedTable``; any hand SQL for it falls under the lift-ledger rules.
