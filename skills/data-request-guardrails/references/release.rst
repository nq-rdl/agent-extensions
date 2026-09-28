Release conventions
===================

Read this before delivery, and when a request asks for dates, validation listings,
study identifiers or aggregate counts. Evidence: ENQ1204 and ENQ1205 (issue #389).
The approval and the requester's confirmed scope override these conventions. Record
each choice you make under them as an assumption or a ledger decision.

Raw dates or a derived outcome
------------------------------

* Deliver raw dated events by default, with their source. Turning a date into an
  outcome is the researcher's modelling choice ("Leave modelling choices to the
  researcher" in ``SKILL.md``).
* Deliver a derived outcome instead of the raw date only when the approval or the
  confirmed scope names the derived outcome, or when the approval does not cover
  the raw date. For example, an approval can permit "died within 30 days" but not
  the date of death.
* For a derived outcome, record its rule (anchor, window and boundaries) with
  ``record_assumption()``. Keep the raw date for validation in an internal listing,
  not in the delivery.
* Do not deliver both unless the approval covers both.

Internal validation listings
----------------------------

Validation listings (row-level checks, samples and cross-source comparisons) stay
inside RDL. Mark each such result batch with ``-- @extract: <name> internal``.

* In the data-analysis-scaffold extract runner that supports it
  (``scripts/run_extract.py``, scaffold PR #247, unreleased on 2026-09-28), the
  batch's parquet is written to ``data/02_extracts/`` and saved as usual, but it
  gets no sheet in the delivered workbook. Any other trailing token refuses the run
  before SQL runs. A run whose every output is internal is refused.
* Older runners (scaffold v0.5.0 and earlier) accept ``-- @extract: <name>`` only.
  Their marker pattern does not match a line with a trailing ``internal``, so the
  batch falls back to an ``extract_NN`` name and **lands in the delivered
  workbook**. Read the child's pinned ``scripts/run_extract.py`` before you rely on
  the marker. When it lacks the flag, keep validation listings out of the delivery
  run and say so in the task output.
* query-builder v0.6.0 emits ``-- @extract: <name>`` markers but has no internal
  flag. Never hand-edit a generated marker (``/data-request:amend``).

Study IDs
---------

Use this pattern unless the approval or the data custodian sets a method:

1. Fix the final delivered cohort first.
2. Give each person one study ID. Draw the order at random (for example
   ``ORDER BY NEWID()``), then number with ``ROW_NUMBER()``. Never derive the ID
   from a URN, MRN, ``PERSON_ID``, date of birth or a hash of them, and never
   number in source or date order.
3. Store the link table (study ID to source person key) as an internal extract. It
   never goes in the delivery.
4. Reuse that link table for every amendment of the same enquiry, so the IDs stay
   stable. A random draw is not reproducible, so never regenerate it.
5. Record the method with ``record_assumption()``.

Small-cell suppression
----------------------

These skills set no organisation-wide threshold. Use the threshold that the
governing approval or the data custodian states. If none is stated, ask the
approver or requester, and record the answer as a decision before release. Do not
choose a number yourself.

Suppression applies to every aggregate that leaves RDL: counts, cross-tabulations,
summary tables, and probe results pasted into a task, issue or comment. Also
suppress a second cell wherever a total or a difference would reveal a suppressed
value. A row-level extract delivered under an approval is governed by that approval,
not by cell suppression.
