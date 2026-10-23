Supplied cohorts: load at run time, never read or inline
========================================================

A supplied cohort is a list of people (study IDs, URNs) that the requester gives the data
team. Its values must never reach Git, an issue, a review record or a chat. This applies to
the agent too: you work from the cohort's *shape*, and the runner handles its *values*.

Sources, at query-builder ``v0.8.0``: ``docs/SUPPLIED_COHORTS.md``, the docstring of
``rdl_etl_helpers.harness.literals`` and the docstring of ``pypika_queries.identifier_columns``.
Read them in the pinned library rather than relying on this summary; a request on an older pin
has no supplied-cohort support (``SuppliedCohort`` and ``load_supplied()`` are in v0.8.0).

How the cohort is loaded
------------------------

1. The request package declares the shape once in Python: ``SuppliedCohort`` with a name, a file
   name, a ``#`` temp table, a key and typed columns, each with a sensitivity.
2. The built script holds the shape only. In order: one ``-- @supplied: {"format": 1, ...}``
   header line per cohort, ``CREATE TABLE "#<table>"``, a unique key index, then a
   ``-- @supplied-load: <name>`` batch whose guard fails if the table is empty. The join to the
   cohort follows. The script is the same for every file the researcher sends.
3. At run time the runner reads the file, checks every row against the declared types, then
   inserts all rows with one parameterised ``executemany`` (placeholders, no values in the SQL
   text) on the connection that ran the ``CREATE TABLE``. ``QueryExecutor`` and the scaffold
   runner (``pixi run extract``) do this; SSMS does not, and the guard batch stops there.
4. The file lives at ``data/00_raw/<file>``, saved with DVC and gitignored; Git holds only the
   ``.dvc`` pointer and a header-only ``conf/base/supplied/<name>.template.csv``.

A bad file fails the whole load with reason codes, row numbers and column names. No message
holds a value. Fix a load problem from those, with the researcher; do not open the file.

Never inline a value
--------------------

Do not write a cohort value into SQL, a Python builder, a code-set, a comment, a spec, a scope
or review record (``.sqlreview/``), an assumption or limitation text, a test fixture, an
issue, a pull request, a commit message or chat. That covers a sample "just for the example",
a partial list, a hash of a value and a count small enough to identify a person.

* No ``VALUES`` list, no ``IN (...)`` list and no ``=`` or ``<>`` literal carrying identifiers.
  Join to the ``#`` table instead.
* Do not load a cohort with ``CSVImporter``, ``ExcelImporter`` or
  ``InsertBuilder.insert_row()``/``insert_bulk()``/``batch_insert()``: they write each value into
  the SQL text and are deprecated for supplied data.
* v0.8.0's harness gate (``assert_no_sensitive_literals()``, run by ``check_case_fast()``) fails a
  literal ``VALUES`` list on a ``PERSONAL``, ``SENSITIVE`` or ``HEALTH`` column. It also fails a
  literal ``IN``/``=``/``<>``/``LIKE`` on an *identifier column* (see
  ``pypika_queries.identifier_columns.is_identifier_column()``) when a value has five or more
  digits, or is not one plain literal. On a column it cannot resolve it fails a value of up to
  three letters then seven or more digits. A coded column (``PERSON.SEX_CD``) passes, so a short
  code list is fine.
* Passing the gate is not permission. The gate may not see a short identifier, a value split
  across statements or a value in a comment. If the gate fails, move the list into a supplied
  cohort; never reshape the values to get past it.
* Test with ``SuppliedCohort.example_rows(n)``: synthetic, deterministic, generated in memory.
  Do not commit example rows as a file.

Describe a cohort by shape only: who supplies it, the columns, their types, the key, an
approximate row count and any instalments. Report unmatched or loaded counts only through the
rounded line of **Probe disclosure control** in ``release.rst``; exact counts stay in the
audit record under DVC.

Never read the supplied file
----------------------------

Do not open, ``Read``, ``cat``, ``head``, ``grep``, load into Polars, DuckDB or Excel, or
otherwise print any file under ``data/00_raw/``. That includes a quick format check, a "first
five rows" look and debugging a load error. The shape comes from the declaration, the
``-- @supplied:`` header line and the template; a load problem comes from the runner's reason
codes. When a file is wrong, say what the codes report and ask the researcher for a corrected
one.

Layers of protection
--------------------

* The data-request plugin's guard (``hooks/data-request-guard.sh``) denies the agent ``Read`` tool
  on any path under ``data/00_raw/``. It is the narrower layer: it covers that directory and the
  ``Read`` tool only, and a shell command is out of its reach by design. The rule above still
  holds for ``Bash``, ``Grep`` and every other route.
* A scaffold child separately denies ``Read(/data/**)`` and lets the runbook ``pixi run`` tasks
  through. The two are compatible: the child denies more, and the runbook tasks run the loader
  without showing you a value. The runbook is where the researcher's file is saved and a run is
  authorised.
* If a read or a run is denied, report it and stop. Do not retry in another form.
