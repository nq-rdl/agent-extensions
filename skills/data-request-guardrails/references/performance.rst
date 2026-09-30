Performance, probe and read-isolation fallbacks
===============================================

Read this when the operator cannot inspect an execution plan, when a table has no
usable index, before you propose an operator probe, and before you choose a read
isolation level. It extends "Performance: shift the anchor" and "Read isolation"
in ``SKILL.md``. Evidence: four enquiries whose operators lacked plan permissions
(issue #370).

No plan permission
------------------

Many operators have neither SHOWPLAN nor VIEW DATABASE STATE. Then do not ask for
an execution plan or for ``sys.dm_*`` views. Read catalog metadata instead: it
reads no table rows, and it needs only metadata visibility of the table. Run the
query in the table's own database:

::

  -- Index shape and approximate row count. Metadata only.
  SELECT i.index_id, i.name AS index_name, i.type_desc, i.is_unique,
         ic.key_ordinal, ic.is_included_column, c.name AS column_name,
         (SELECT SUM(p.rows) FROM sys.partitions AS p
           WHERE p.object_id = i.object_id AND p.index_id = i.index_id) AS approx_rows
  FROM sys.indexes AS i
  LEFT JOIN sys.index_columns AS ic
    ON ic.object_id = i.object_id AND ic.index_id = i.index_id
  LEFT JOIN sys.columns AS c
    ON c.object_id = ic.object_id AND c.column_id = ic.column_id
  WHERE i.object_id = OBJECT_ID(N'dbo.<table>')
  ORDER BY i.index_id, ic.is_included_column, ic.key_ordinal;

* ``index_id`` 0 is a heap and 1 is the clustered index. A table with only a
  clustered primary key has no usable index for any other filter column, so every
  such filter is a full clustered scan.
* ``sys.partitions.rows`` is approximate. Use it to size a scan, not as a count.
* ``mart_v`` views (HBCIS ``Inpatient`` and ``InpatientExtensions``) return no
  index rows. Their base tables are not visible. Treat a ``mart_v`` view as
  unindexed unless its owner supplies the base-table index definitions.
* Record the query, database and date run. The result is OBSERVED evidence for that
  server only.

Unindexed tables
----------------

When no index serves the filter, a bare column does not help. Use this pattern:

1. Bound the scan by date, using the narrowest window the confirmed scope allows.
2. Scan the source once into a ``#temp`` table that holds only the columns you need.
3. Do every later step (probes, joins, output) from ``#temp``. Never re-scan the
   source for each probe or output.

Local ``#temp`` tables belong to one session. DataGrip keeps them inside one console
session only, and an SSMS query window behaves the same way. Run repeat probes in
the same session, or run the bounded scan again. A ``CREATE INDEX`` on a ``#temp``
table fails under SNAPSHOT isolation (error 3964).

Probe design
------------

An operator probe is SQL the authorised operator runs by hand for source discovery
or to check finished SQL before a delivery run. A proposal grants no execution
authorisation; validate never connects to a database. Keep each probe:

* **Aggregate-only.** It returns counts, ranges and codes, never patient rows.
* **Small-cell suppressed.** Write the threshold as a parameter (for example
  ``@min_cell``). Its value comes from the request's de-identification assessment
  ("Cell suppression threshold"); when that states none, ask for it and record the
  answer (see ``release.rst``). Suppress the MIN and MAX of a small cell as well as
  its count.
* **One bounded scan.** Group on a few narrow keys and take MIN and MAX samples per
  group, instead of a full-table aggregate over many columns. Take MIN and MAX only
  of dates, category codes and numeric ranges, never of an identifier, name or
  free-text column. Avoid ``GROUPING SETS`` combined with ``COUNT(DISTINCT ...)`` on
  a full scan: it reads the table more than once.
* **Free of patient identifiers.** Never ask the operator to paste a column that can
  hold a patient identifier ("Personal information" in ``release.rst``). Clinician and
  resource names are not personal information (governance ruling, 2026-09-28): a
  probe may group on ``OPD_Appointments.Resource``, whose labels hold clinician
  names, and the operator pastes those labels as they are. Only a label that
  looks like a patient's name is written as "name removed"; mark a probe whose
  column can hold patient names local-only. Any codes it returns are category or
  type codes, never staff or person keys, into the task output.
* **Explicit about isolation.** Record any ``NOLOCK`` or ``READ UNCOMMITTED`` use
  beside the probe.

Tag each finding ``OBSERVED`` (measured) or ``INFERRED`` (reasoned from a result),
with its scope: server, database, table, bound and date run. A probe that meets
every rule above is outside the lift-ledger gate (see the setup skill's
``references/lifts.rst``).

Pre-run plausibility
--------------------

``validate`` and ``analyse`` own proposals, not execution. Inspect **every final
result set**, its final SELECT/resolver columns, scope and data dictionary. Return
**one row per label column**, starting with low-cardinality categories such as
sex, status and facility. Include code/label pairs separately; do not check sex
and assume the other labels share its format. Use this output table:

Column | Expected labels/format and source | Proposed probe | Bound/cost | Status

Qualify columns by result-set name and cite SQL lines. For each, propose a
**count-only** distinct-value distribution (raw category value and row count),
including NULL, blank and unmapped categories. Preserve **raw spelling**, case
and trailing spaces: case-insensitive grouping can hide the uppercase surprise.
Use an engine-verified binary comparison plus byte length where padding collapses
values. Do not UPPER, trim or normalise values in the probe. Escape whitespace in
safe returned labels so blank versus padded values remain visible. Suppressed
categories remain unknown; absent returned labels are not proof of absence.
Check the actual output representation, not only its source code column.

If cardinality or meaning is unverified, still list the column with a deferred
proposal and missing metadata, rather than omitting it. Exclude identifiers,
free text and patient-name fields explicitly, with the reason; never emit staff
or person keys. Report **no label columns** when that is the evidenced inventory.
Do not use a probe to discover high-cardinality personal values. Label spelling
is not a population filter: an uppercase sex label calls for dictionary or
presentation review, not a sex-based exclusion.

Apply all Probe design rules above. Plan **one bounded source scan per independent
source/cohort result** into a minimal ``#temp`` containing only safe category columns;
reuse each materialisation for that result's label aggregates. Share it across outputs
only when they have the same joins, filters, grain and label conversions. For example,
admissions and procedures from independent pipelines need separate materialisations;
do not pool their populations to fit one table. For every proposed probe, identify its
materialisation and verify that it matches the corresponding finished SQL result.
Prefer already authorised, bounded cohort materialisations; do not run the full delivery
pipeline as a probe and do not re-scan a source per column. State the cohort/time/facility
bounds, estimated rows and available runtime evidence for each materialisation, and assess
the combined scan cost. A narrowed preflight window must be marked partial coverage,
not a full-cohort check. No usable bound or scan plan means defer, not an unbounded
query. Temporary probe material feeds no delivered extract and returns no patient
rows. Record any NOLOCK or READ UNCOMMITTED use; never introduce either silently.

Parameterise ``@min_cell`` from the assessment/approval threshold; when unknown,
ask and mark the proposal not runnable. For a small cell **suppress the label**
and count, not just its number. Apply required complementary suppression so
visible totals, NULL/blank counts or a second probe cannot reveal hidden counts;
do not request unsuppressed totals for subtraction. Return only safe category
labels and counts, no identifiers, dates of birth, exact ages or patient examples.

For **expensive requests only**, add an age-band count probe before the operator
run: cite estimated rows, a prior runtime or another recorded cost assessment.
When cost is unknown, ask whether the run is expensive; omit the age-band probe
pending evidence, without dropping label proposals. Use the scoped age anchor
(for example age at index surgery, not age today), verified age calculation and
broad bands that test a stated boundary, with missing/invalid age counted and
suppressed alike. No stated age limit does not imply adult; an exploratory
under-18 band is not a new inclusion rule. Compute safe age-band categories in
the matching bounded materialisation for that result and age anchor; do not add another
source scan for age or store raw birth dates in the probe table. Do not expose MIN/MAX birth dates.

Mark every proposal ``proposed, not executed`` and identify the authorised
operator action separately. When results return, tag evidence OBSERVED or INFERRED
with server/database, bound, date and SQL revision as above. Compare safe values
with the expected labels and data dictionary; route surprises to the analyst
with no automatic exclusion. Unrun or suppressed probes do not establish
plausibility. Keep later UAT and ``validation_counts`` checks; machine checking
scope expectations against those counts in data-analysis-scaffold is a follow-up,
not implemented here. This guidance changes no runtime permissions.

Read isolation
--------------

The sources of truth are in ``nq-rdl/query-builder``:

* ``docs/READ_ISOLATION.md`` and ADR 0001 (v0.6.0). ``QueryExecutor(url,
  isolation_level=...)`` fixes the level for the executor's lifetime. It accepts
  ``SNAPSHOT``, ``READ COMMITTED`` or ``READ UNCOMMITTED``, and rejects the string
  ``NOLOCK``. Store ``executor.audit_metadata()`` with the extract: it records the
  configured and the effective level.
* ADR 0004 describes opt-in per-table ``WITH (NOLOCK)`` hints. Inspect the
  request's tagged implementation/tests before claiming availability or absence;
  a merge on ``main`` alone is not release evidence.

Where the request repo has its own ``docs/READ_ISOLATION.md``, follow it as well.

Choose the level in this order: a read replica or readable secondary; RCSI already
on; ``SNAPSHOT`` when the database allows it and the pipeline does not index
``#temp`` tables; otherwise the default. Check a database with
``SELECT snapshot_isolation_state_desc, is_read_committed_snapshot_on FROM
sys.databases WHERE name = DB_NAME();``.

``READ UNCOMMITTED`` and ``NOLOCK`` can return rolled-back rows, and can skip or
double-read rows. At most they suit feasibility counts and probes, and every use is
recorded. A final research
extract that reads uncommitted data needs DBA and requester agreement, a
``record_assumption()`` beside the read that says so, and a label wherever its
results are reported.
