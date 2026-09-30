Engineer decisions: proceed and flag
===================================

Apply this rule to an authorised build, not as permission to act outside it.
The engineer owns technical implementation; the analyst consults the requester
on research decisions. A technical choice is not an analyst research answer.

Decide, proceed, flag
--------------------

On an engineer decision, proceed without waiting for the analyst. This covers
source and table choice, join keys, tie-breaks, time zones, the house-style
facility default ``00200``, holding and placeholder codes, null handling,
column naming and order, presentation, and readings one authorised probe can
settle. Cite metadata, prior SQL/delivery or the probe's population and result.
A facility fallback is not a new cohort filter; a holding-code interpretation
is not a clinical definition. Check the requested population and output before
applying either. Unsupported storage facts remain unverified, not invented.

Within the agreed task, implement evidenced technical defaults without a new
analyst round trip. If the engineer has not personally decided the item, label
it an agent-applied technical default for engineer review. Never attribute an
autonomous agent choice to a human or call it analyst-confirmed. If a human
technical decision is needed, batch it for the engineer, not the analyst.

Record a real decision as ``Engineer decision (<login>, <date>), flagged for the
data analyst`` using the actual engineer login and decision date. Include the
choice, rationale, evidence and governed SQL location in the SQL header via
``pipeline.record_assumption(text, rationale=...)`` at the implementing logic
(verify the installed analysis-notes API), and in the analyst hand-off. Do not
keep the decision only in a chat or a separate note. A limitation records a
source weakness, not the engineer's choice. For a pin lacking the API, follow
the guardrails pin rule; do not hand-write a generated header.

For formal scope/review items, optional ``decided: {by, role, at, source}``
preserves decision origin independently of the confirmer. The role is a display
label; config roles are display labels, not logins. Date-only origins retain
that precision; never invent midnight. Carry the original source and actor
through later confirmation. A decision origin does not fill confirmation fields:
publication still requires an answered human question or valid carried/imported
confirmation under the existing schema. The exact recorded TUH house confirmation
is an upstream import, not a new autonomous decision (see House defaults in
``SKILL.md`` and setup's recurring-decisions reference). Building on any other technical default does
not manufacture ``confirmed_by``, ``confirmed_at`` or ``confirmed_revision``.

Only these unanswered authority questions block
----------------------------------------------

Stop only the dependent portion, name the class below and its evidence, and
continue independent work. A question by itself is not a blocker.

* **Governance:** a known approval restriction or custodian decision excludes
  an element or requires authority the engineer cannot grant. Never implement
  a prohibited output while waiting. Unchecked approval alone is not a blocker:
  build requested identifiers and free text; the analyst checks delivered
  approval coverage at review. Carry at most one review limitation, not a
  recurring question (see ``release.rst``).
* **Cohort expansion:** a cohort change beyond the request. Default: keep the
  requested cohort. For I71.3/I71.4, do not add I71.8 merely because a library
  concept contains it; ask only if the expansion is needed.
* **Released grain:** a grain change that alters the row count of a released
  output. Default: preserve the released grain until the analyst/requester
  answers; use the existing fix/amend routing and review gates. An evidenced
  technical reading of an unreleased requested output is not a released-output
  grain change. Do not use this distinction to expand the requested cohort or
  add an output.
* **Requester-defined measure:** an unsupported clinical, research or business definition
  that changes inclusion or output meaning belongs to the analyst/requester, even
  without cohort expansion or a released row-count change. Examples: length of stay
  calculation, rate denominator, qualifying business states or a 30-day outcome.
  Default: continue independent work, but do not invent a 30-day outcome, its anchor
  or qualifying states from a raw date, or a business measure from storage facts.
  An existing recorded requester definition is evidence; an engineer's implementation
  choice is not. Stop the dependent SQL until that definition is supported.

Batch the remaining research questions into one analyst message, each with its
default and its evidence (or the missing evidence). Avoid repeating answered
intake or prior-delivery choices. Keep building on safe defaults while answers
are pending: unchanged requested cohort/grain, evidenced technical choices and
independent portions. Silence is not approval to cross any boundary above.
A necessary unanswered requester-defined measure has no executable invented default.

Deliver only the request
------------------------

Use the narrowest reading supported by the request and evidence. Deliver what
was asked. Offer extras in the hand-off note; do not build them without a new
instruction. An extra output's file size or Excel row limit is not a blocker
for the requested output.

For example, a request for Admitting Ward and Facility Code is not a request
for a ward-stay list. When a bounded probe establishes ``00200`` throughout the
relevant ward stays and establishes TWAA as a holding code, implement and flag
the evidenced ward-selection/facility reading at the requested grain. Record
the probe's population: this is not a universal facility or TWAA fact. Offer a
ward-stay list only as an unbuilt extra. If this would change a released row
count, apply the released-grain question above instead.

Status and unchanged operational gates
-------------------------------------

Report ``Proceeding on an engineer decision, flagged`` separately from
``Blocked (cannot proceed)``. For a block name the authority class, affected
portion, evidence, question and owner, not just "waiting for the analyst".
Report safe work continuing alongside it. Agent defaults use their own label.

These are decision-authority classes, not a waiver of operational failures:
source availability, dependency, scaffold, missing capability and correctness
bugs still use triage's taxonomy. A failed formal review/publication gate is
reported as that gate, not as an analyst question; triage-only stays read-only;
warehouse queries/extracts, service-desk writes, releases, merges, main pushes,
hook bypasses and scaffold updates retain their explicit authorisation rules.
On a runtime denial, report and stop; no alternative-action retry. Enquiry
approval never overrides those controls.
