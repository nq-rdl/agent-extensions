StarRocks Query Acceleration Quick Reference
============================================

Condensed from the `Query
Acceleration <https://docs.starrocks.io/docs/category/query-acceleration/>`__
docs.

Acceleration Toolkit Overview
-----------------------------

+--------------------+--------------+--------------+------------------+
| Technique          | Effort       | Impact       | Use When         |
+====================+==============+==============+==================+
| CBO statistics     | Low          | High         | Always — run     |
|                    |              |              | after bulk loads |
+--------------------+--------------+--------------+------------------+
| Sync materialized  | Low          | High         | Single-table     |
| view               |              |              | aggregates       |
+--------------------+--------------+--------------+------------------+
| Async materialized | Medium       | High         | Multi-table      |
| view               |              |              | joins +          |
|                    |              |              | aggregates       |
+--------------------+--------------+--------------+------------------+
| Colocate join      | Medium       | High         | Frequent joins   |
|                    |              |              | between large    |
|                    |              |              | tables           |
+--------------------+--------------+--------------+------------------+
| Bloom filter index | Low          | Medium       | High-cardinality |
|                    |              |              | equality filters |
+--------------------+--------------+--------------+------------------+
| Query cache        | Low          | Medium       | Repeated         |
|                    |              |              | identical        |
|                    |              |              | queries          |
|                    |              |              | (dashboards)     |
+--------------------+--------------+--------------+------------------+
| Flat JSON          | Low          | Medium       | Frequent JSON    |
|                    |              |              | field extraction |
+--------------------+--------------+--------------+------------------+
| JIT compilation    | Low          | Low–Medium   | Complex          |
|                    |              |              | expressions      |
+--------------------+--------------+--------------+------------------+

Cost-Based Optimizer (CBO) Statistics
-------------------------------------

The CBO requires accurate statistics to choose optimal plans.

Collection
~~~~~~~~~~

.. code:: sql

   -- Full collection (all columns)
   ANALYZE TABLE my_table;

   -- Specific columns only
   ANALYZE TABLE my_table (col1, col2);

   -- Sample-based for large tables (faster, slightly less accurate)
   ANALYZE SAMPLE TABLE my_table;

   -- Automatic collection (recommended)
   SET GLOBAL enable_statistic_collect = true;

Verification
~~~~~~~~~~~~

.. code:: sql

   -- Check column statistics
   SHOW COLUMN STATS my_table;

   -- Check table-level stats
   SHOW TABLE STATS my_table;

When to Collect
~~~~~~~~~~~~~~~

- After initial data load
- After large batch loads (> 10% data change)
- Periodically (daily for frequently changing tables)
- When query plans look suboptimal (unexpected full scans or bad join
  orders)

Materialized Views
------------------

Synchronous (Single-Table)
~~~~~~~~~~~~~~~~~~~~~~~~~~

Auto-refreshed on data load. Transparent query rewrite — the optimizer
automatically uses the MV when it matches the query pattern.

.. code:: sql

   CREATE MATERIALIZED VIEW mv_hourly_events AS
   SELECT
       date_trunc('hour', event_time) AS hour,
       event_type,
       COUNT(*) AS cnt,
       SUM(amount) AS total
   FROM events
   GROUP BY date_trunc('hour', event_time), event_type;

**Limitations:** - Single base table only - No joins - Limited to simple
aggregations (SUM, COUNT, MIN, MAX, HLL_UNION, BITMAP_UNION) - Cannot
include WHERE clause

Asynchronous (Multi-Table)
~~~~~~~~~~~~~~~~~~~~~~~~~~

Scheduled or manual refresh. Supports joins, complex aggregations, and
query rewrite.

.. code:: sql

   CREATE MATERIALIZED VIEW mv_user_metrics
   REFRESH ASYNC EVERY (INTERVAL 1 HOUR)
   PROPERTIES ("replication_num" = "3")
   AS
   SELECT
       u.region,
       date_trunc('day', o.order_time) AS dt,
       COUNT(DISTINCT o.user_id) AS unique_users,
       SUM(o.amount) AS revenue
   FROM orders o
   JOIN users u ON o.user_id = u.id
   GROUP BY u.region, date_trunc('day', o.order_time);

**Refresh strategies:** - ``REFRESH ASYNC EVERY (INTERVAL ...)`` —
periodic - ``REFRESH MANUAL`` — on-demand via
``REFRESH MATERIALIZED VIEW mv_name`` - ``REFRESH ASYNC`` — auto-refresh
when base table changes

**Monitor:**

.. code:: sql

   SELECT * FROM information_schema.materialized_views
   WHERE table_name = 'mv_user_metrics';

   -- Check refresh history
   SELECT * FROM information_schema.task_runs
   WHERE task_name LIKE '%mv_user_metrics%';

MV Design Guidelines
~~~~~~~~~~~~~~~~~~~~

1. Match MV GROUP BY columns to common query dimensions
2. Include all columns that appear in WHERE, GROUP BY, or SELECT
3. For joins: ensure join keys match common query patterns
4. Refresh interval should balance freshness vs. compute cost
5. Use ``REFRESH MANUAL`` for MVs over external catalog tables

Colocate Join
-------------

Eliminates network shuffle by ensuring joined tables are physically
co-located.

Setup
~~~~~

.. code:: sql

   -- Both tables must share the same colocate group
   CREATE TABLE orders (
       user_id BIGINT,
       order_time DATETIME,
       amount DECIMAL(10,2)
   )
   DISTRIBUTED BY HASH(user_id) BUCKETS 32
   PROPERTIES ("colocate_with" = "user_group");

   CREATE TABLE user_profiles (
       user_id BIGINT,
       name VARCHAR(128),
       region VARCHAR(32)
   )
   DISTRIBUTED BY HASH(user_id) BUCKETS 32
   PROPERTIES ("colocate_with" = "user_group");

Requirements
~~~~~~~~~~~~

- Same colocate group name
- Same number of buckets
- Same bucket column types (not necessarily same names)
- Same replication number

.. _verification-1:

Verification
~~~~~~~~~~~~

.. code:: sql

   SHOW PROC '/colocation_group';

Lateral Join with unnest()
--------------------------

Expand arrays or JSON arrays into rows:

.. code:: sql

   SELECT event_id, tag
   FROM events, unnest(split(tags, ',')) AS t(tag);

   -- JSON array expansion
   SELECT event_id, item
   FROM events, unnest(cast(json_query(payload, '$.items') AS ARRAY<VARCHAR>)) AS t(item);

Skew Join
---------

Handles data skew by broadcasting frequently occurring values (v3.1+):

.. code:: sql

   SET skew_join_data_skew_threshold = 100000;
   -- The optimizer auto-detects and optimizes skewed joins

Caching
-------

Query Cache
~~~~~~~~~~~

Caches results of identical queries. Effective for dashboard use cases.

.. code:: sql

   -- Enable for a session
   SET enable_query_cache = true;

   -- Set cache TTL
   SET query_cache_entry_max_bytes = 4194304;  -- 4 MB per entry
   SET query_cache_entry_max_rows = 100000;

Data Cache (Shared-Data Mode)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Caches remote storage data on local disks. Configured at the BE level —
not a DBA concern (platform engineering).

Flat JSON
---------

Automatically extracts frequently accessed JSON fields into columnar
storage for faster access (v3.3+):

.. code:: sql

   -- Enable flat JSON for a table
   ALTER TABLE my_table SET ("flat_json_meta" = '["payload.user_id", "payload.event_type"]');

Useful when JSON columns contain semi-structured data with stable
top-level fields.

JIT Compilation
---------------

Compiles complex expressions to native code at runtime:

.. code:: sql

   -- Enable globally
   SET GLOBAL enable_jit = true;

   -- Check if JIT was used in a query
   EXPLAIN <query>;  -- Look for "JIT" in the plan

Best for queries with complex CASE/WHEN, arithmetic, or string
expressions.

Sorted Streaming Aggregate
--------------------------

When data is sorted by the GROUP BY columns (matching the sort key),
StarRocks can use a streaming aggregate instead of a hash aggregate —
using less memory and running faster:

.. code:: sql

   -- Enable
   SET enable_sort_aggregate = true;

Works automatically when GROUP BY columns match the table’s sort key
prefix.

Query Tuning Checklist
----------------------

1. **Check statistics**: ``SHOW COLUMN STATS`` — are they fresh?
2. **Check the plan**: ``EXPLAIN`` — any unexpected full scans?
3. **Partition pruning**: does the WHERE include the partition column?
4. **Bucket pruning**: does the WHERE filter on the bucket column?
5. **Index usage**: bloom filter or bitmap for selective predicates?
6. **MV rewrite**: does ``EXPLAIN`` show the MV being used?
7. **Join strategy**: colocate, broadcast, or shuffle? Is colocate
   possible?
8. **Resource groups**: is the query competing for resources?

Anti-Patterns
-------------

+---------------------------------------------------+-------------------+
| Anti-Pattern                                      | Fix               |
+===================================================+===================+
| No CBO stats collected                            | Run               |
|                                                   | ``ANALYZE TABLE`` |
|                                                   | after loads       |
+---------------------------------------------------+-------------------+
| MV not being used in query rewrite                | Check column      |
|                                                   | alignment; run    |
|                                                   | ``EXPLAIN``       |
+---------------------------------------------------+-------------------+
| Colocate join not triggered                       | Verify same       |
|                                                   | bucket count,     |
|                                                   | column types, and |
|                                                   | group             |
+---------------------------------------------------+-------------------+
| Query cache on frequently changing data           | Disable cache for |
|                                                   | real-time tables  |
+---------------------------------------------------+-------------------+
| JSON field access without flat JSON               | Enable flat JSON  |
|                                                   | for stable        |
|                                                   | top-level fields  |
+---------------------------------------------------+-------------------+
| GROUP BY on non-sort-key columns                  | Consider sort key |
|                                                   | redesign or add a |
|                                                   | sync MV           |
+---------------------------------------------------+-------------------+
