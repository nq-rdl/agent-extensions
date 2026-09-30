Delivery-format limits
======================

Read this at map and draft time, before choosing output grain or text columns.
The workbook is a presentation copy, not a lossless substitute for Parquet.

Limits and canonical behaviour
------------------------------

* **1,048,575 data rows per sheet**: one worksheet row holds the header.
* **16,384 columns per sheet**.
* **32,767 characters per cell**: splitting sheets does not fix long text.
* **31 characters per sheet name**, unique without regard to case.

The scaffold is the source of truth for delivery behaviour: inspect the child's
pinned `template/src/services/file_manager.py
<https://github.com/nq-rdl/data-analysis-scaffold/blob/main/template/src/services/file_manager.py>`_
and `template/scripts/run_extract.py
<https://github.com/nq-rdl/data-analysis-scaffold/blob/main/template/scripts/run_extract.py>`_
before promising a format. Verified at scaffold revision
``3a1099bfb283d6cb258803466599a17d6e45318a``; older child runners may differ.
``_EXCEL_DATA_ROWS`` and the column/name constants set the sheet limits;
``save_excel_workbook`` / ``build_workbook`` tile oversized frames across sheets
in both row and column dimensions. Sheet names are sanitised, shortened and
deduplicated case-insensitively, including tile suffixes.

The cell cap is an `Excel specification
<https://support.microsoft.com/en-us/office/excel-specifications-and-limits-1672b34d-7043-467e-8e27-269d656771c3>`_,
not a separate constant in those scaffold files. Their Excel writer paths can
truncate overlong text; do not promise full notes in the workbook. The runner
writes Parquet before constructing the workbook: Parquet retains every captured
row and the full cell text, unaffected by workbook tiling or cell truncation.
This does not recover text already shortened in SQL. Verify the pinned writer
behaviour when a lossless delivery claim matters; do not duplicate runner code.

Estimate each output
--------------------

At map and again at draft, estimate rows for **each output/result set** from
available authorised probe counts at the proposed final grain. Cite the probe's
population/window and explain joins, multiplicity, filters and uncertainty;
a patient count alone does not establish event or note output rows. Reuse
available evidence; this check does not authorise a new probe or database run.
Missing or incompatible counts mean **unverified**, not zero or a claim of fit.

Rounded counts suffice far from the row limit. An estimate **within 10% of
1,048,575** is **undecided** and goes to the engineer; do not decide fit from
"about 1.0M" or invent precision. If an authorised probe runner supplies
``rows_vs_limit`` computed on exact counts, read that claim rather than rounded
prose: ``under half``, ``between half and the limit`` or ``over the limit``.
It applies only to the same output grain/population; it is not an exact count.
Without a matching claim, leave the near-limit case undecided. This guidance
consumes claims when available; it does not implement the probe runner.

For text, use length bands such as **longer than 32,767 characters**, with a
rounded count of long notes, not note contents or precise lengths. Declared
unbounded/long-text columns without observed bands remain potential cell-limit
risks. Record known or possible exceedance, near-limit uncertainty and unavailable
evidence as delivery limitations, naming the affected output/column and consequence.
Also check projected column count and planned sheet-name collisions/shortening.

Engineer choice, flagged for the analyst
---------------------------------------

For oversized or uncertain outputs, put the alternatives and their effects to
the engineer and carry the choice into the analyst hand-off:

* **Accept the sheet split**: preserve the requested rows/columns; explain how
  tiles are recombined and that long cells can still lose text in Excel.
* **Deliver Parquet first**: keep full rows/text; establish that the recipient
  can use it and describe the workbook as a limited presentation copy.
* **Reduce or change the grain**: explain the lost detail and changed row count.
* **Cut text columns**: explain the omitted requested elements; retain full text
  in Parquet if only the workbook presentation omits them and the pin supports it.

These are engineer delivery decisions, flagged for the analyst, not automatic
agent fixes. Do not silently aggregate, drop requested text or truncate SQL to
make Excel fit. Preserve the requested cohort/grain/columns while the choice is
unresolved and continue independent work. Research-definition changes, known
governance restrictions and released-output grain changes retain the authority
rules in `decision-authority.rst <decision-authority.rst>`_.

Mapping returns limitations and choices as proposals. Draft records limitations
with ``pipeline.record_limitation(text, consequence=...)`` at the affected result
or text-selection logic, and records an evidenced choice with the shared
assumption/decision provenance rule. Carry the evidence, limitation, choice or
unresolved engineer question into the SQL header and analyst hand-off; never
invent a human login/date or confirmation.
