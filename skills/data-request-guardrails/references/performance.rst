Performance, probe and read-isolation fallbacks
===============================================

Read this when the operator cannot inspect an execution plan, when a table has no
usable index, before you propose an operator probe, and before you choose a read
isolation level. It extends "Performance: shift the anchor" and "Read isolation"
in ``SKILL.md``. Evidence: ENQ1160, ENQ1204, ENQ1217 and ENQ1219 (issue #370).

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

An operator probe is SQL the operator runs by hand to learn about a source before
pipeline SQL exists. Keep each probe:

* **Aggregate-only.** It returns counts, ranges and codes, never patient rows.
* **Small-cell suppressed.** Apply the threshold from ``release.rst``. When no
  threshold is known yet, write it as a parameter (for example ``@min_cell``) that
  the operator sets, and record the value used.
* **One bounded scan.** Group on a few narrow keys and take MIN and MAX samples per
  group, instead of a full-table aggregate over many columns. Avoid ``GROUPING SETS``
  combined with ``COUNT(DISTINCT ...)`` on a full scan: it reads the table more than
  once.
* **Free of identifying values.** Never ask the operator to paste a column that can
  hold an identifying value, such as a clinician or resource name. In ENQ1204,
  ``OPD_Appointments.Resource`` held doctor names. Mark such a probe local-only, and
  let it return codes only, never names, into the task output.
* **Explicit about isolation.** Record any ``NOLOCK`` or ``READ UNCOMMITTED`` use
  beside the probe.

Tag each finding ``OBSERVED`` (measured) or ``INFERRED`` (reasoned from a result),
with its scope: server, database, table, bound and date run. A probe that meets
every rule above is outside the lift-ledger gate (see the setup skill's
``references/lifts.rst``).

Read isolation
--------------

The sources of truth are in ``nq-rdl/query-builder``:

* ``docs/READ_ISOLATION.md`` and ADR 0001 (v0.6.0). ``QueryExecutor(url,
  isolation_level=...)`` fixes the level for the executor's lifetime. It accepts
  ``SNAPSHOT``, ``READ COMMITTED`` or ``READ UNCOMMITTED``, and rejects the string
  ``NOLOCK``. Store ``executor.audit_metadata()`` with the extract: it records the
  configured and the effective level.
* ADR 0004 adds opt-in per-table ``WITH (NOLOCK)`` hints. It is on ``main`` and is
  not in v0.6.0. Check the request's pin before you use a table hint.

Where the request repo has its own ``docs/READ_ISOLATION.md``, follow it as well.

Choose the level in this order: a read replica or readable secondary; RCSI already
on; ``SNAPSHOT`` when the database allows it and the pipeline does not index
``#temp`` tables; otherwise the default. Check a database with
``SELECT snapshot_isolation_state_desc, is_read_committed_snapshot_on FROM
sys.databases WHERE name = DB_NAME();``.

``READ UNCOMMITTED`` and ``NOLOCK`` can return rolled-back rows, and can skip or
double-read rows. Use them for feasibility counts and probes only. A final research
extract that reads uncommitted data needs DBA and requester agreement, a
``record_assumption()`` beside the read that says so, and a label wherever its
results are reported.
