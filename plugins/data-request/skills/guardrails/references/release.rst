Release conventions
===================

Read this before delivery, and when a request asks for dates, validation listings,
study identifiers or aggregate counts. Evidence: two related enquiries whose builder
had to decide each point from first principles (issue #389). The approval and the
requester's confirmed scope override these conventions. Record each choice you make
under them as an assumption or a ledger decision.

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
  ``record_assumption()``. Keep the raw date for validation outside the delivery
  run.
* Do not deliver both unless the approval covers both.

Validation listings stay out of the delivery
--------------------------------------------

Validation listings (row-level checks, samples and cross-source comparisons) stay
inside RDL. By default, keep them out of the delivery run: put them in a separate
run or script whose output is never delivered, and say so in the task output.

Use the ``-- @extract: <name> internal`` marker only after you read the child's
pinned ``scripts/run_extract.py`` and confirm that it supports the flag:

* The flag exists only in data-analysis-scaffold PR #247, open and unreleased on
  2026-09-28. There, the batch's parquet is written to ``data/02_extracts/`` and
  saved as usual, but it gets no sheet in the delivered workbook. Any other
  trailing token refuses the run before SQL runs. A run whose every output is
  internal is refused.
* Every released runner (scaffold v0.5.0 and earlier) accepts
  ``-- @extract: <name>`` only. Its marker pattern does not match a line with a
  trailing ``internal``, so the batch falls back to an ``extract_NN`` name and
  **lands in the delivered workbook**.
* query-builder v0.6.0 emits ``-- @extract: <name>`` markers but has no internal
  flag. Never hand-edit a generated marker (``/data-request:amend``).

Study IDs
---------

This pattern is a default that RDL has not yet confirmed as a house convention. An
approval, the data custodian or the de-identification assessment overrides it.

1. Fix the final delivered cohort first.
2. Give each person one study ID. Draw the order at random (for example
   ``ORDER BY NEWID()``), then number with ``ROW_NUMBER()``. Never derive the ID
   from a URN, MRN, ``PERSON_ID``, date of birth or a hash of them, and never
   number in source or date order.
3. The link table (study ID to source person key) is a re-identification key. It
   never goes in any extract of the delivery run. Store it only in a separate,
   undelivered run or RDL-only store. Use an ``internal`` marker for it only when
   the pinned runner supports the flag, as above.
4. Reuse that link table for every amendment of the same enquiry, so the IDs stay
   stable. A random draw is not reproducible, so never regenerate it.
5. Record the method with ``record_assumption()``.

Small-cell suppression
----------------------

These skills set no organisation-wide threshold. The governing threshold is the
"Cell suppression threshold" field of the request's de-identification assessment
(``nq-rdl/documentation``,
``zensical/governance/docs/governance/deidentification-assessment.md``), or a
threshold stated in the approval. If neither states one, ask the approver or
requester, and record the answer as a decision before release. Do not choose a
number yourself.

Suppression applies to every aggregate that leaves RDL: counts, cross-tabulations,
summary tables, and probe results pasted into a task, issue or comment. Also
suppress a second cell wherever a total or a difference would reveal a suppressed
value. A row-level extract delivered under an approval is governed by that approval,
not by cell suppression.
