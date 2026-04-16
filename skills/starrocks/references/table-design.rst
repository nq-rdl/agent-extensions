StarRocks Table Design Quick Reference
======================================

Condensed from the `Table
Design <https://docs.starrocks.io/docs/category/table-design/>`__ and
`Best
Practices <https://docs.starrocks.io/docs/category/best-practices/>`__
docs.

Table Types
-----------

+-----------+-------------------------+---------+--------------+--------------------+----------------+
| Type      | Key Clause              | Dedup   | Aggregation  | Mutability         | Use Case       |
+===========+=========================+=========+==============+====================+================+
| Duplicate | ``DUPLICATE KEY(cols)`` | No      | No           | Append-only        | Raw logs,      |
| Key       |                         |         |              |                    | event streams  |
+-----------+-------------------------+---------+--------------+--------------------+----------------+
| Aggregate | ``AGGREGATE KEY(cols)`` | Yes (by | Yes (SUM,    | Aggregate-on-write | Pre-aggregated |
|           |                         | key)    | MAX, MIN,    |                    | metrics,       |
|           |                         |         | REPLACE,     |                    | counters       |
|           |                         |         | etc.)        |                    |                |
+-----------+-------------------------+---------+--------------+--------------------+----------------+
| Unique    | ``UNIQUE KEY(cols)``    | Yes     | No           | Merge-on-read      | Dimension      |
| Key       |                         | (latest |              |                    | tables,        |
|           |                         | wins)   |              |                    | slow-changing  |
|           |                         |         |              |                    | dims           |
+-----------+-------------------------+---------+--------------+--------------------+----------------+
| Primary   | ``PRIMARY KEY(cols)``   | Yes     | No           | Delete+insert      | Real-time      |
| Key       |                         | (latest |              |                    | upserts, CDC,  |
|           |                         | wins)   |              |                    | fast reads     |
+-----------+-------------------------+---------+--------------+--------------------+----------------+

Decision Flow
~~~~~~~~~~~~~

::

   Is the data append-only (no updates)?
     YES → Duplicate Key
     NO  → Do you need pre-aggregation (SUM/MAX on write)?
       YES → Aggregate
       NO  → Do you need real-time upserts with fast reads?
         YES → Primary Key
         NO  → Unique Key

Partitioning
------------

Strategy
~~~~~~~~

+-----------------------+-----------------------------------------+-------------------------+
| Pattern               | Syntax                                  | Best For                |
+=======================+=========================================+=========================+
| Expression-based      | ``PARTITION BY date_trunc('day', col)`` | Time-series,            |
| (recommended)         |                                         | auto-creates partitions |
+-----------------------+-----------------------------------------+-------------------------+
| Range                 | ``PARTITION BY RANGE(col) (...)``       | Custom ranges, non-time |
|                       |                                         | columns                 |
+-----------------------+-----------------------------------------+-------------------------+
| List                  | ``PARTITION BY LIST(col) (...)``        | Categorical values      |
|                       |                                         | (region, tenant)        |
+-----------------------+-----------------------------------------+-------------------------+

Guidelines
~~~~~~~~~~

- Partition on the column most used in WHERE and time-range filters
- Target 100 MB–10 GB per partition (before replication)
- Use ``date_trunc`` granularity matching query patterns: ``day`` for
  daily queries, ``month`` for monthly
- Set retention via ``DROP PARTITION`` or dynamic partition properties

Bucketing
---------

Hash vs Random
~~~~~~~~~~~~~~

+------------------------+----------------------------------------+------------------------+
| Strategy               | Syntax                                 | Best For               |
+========================+========================================+========================+
| Hash                   | ``DISTRIBUTED BY HASH(col) BUCKETS N`` | Queries filtering on   |
|                        |                                        | ``col``, colocate      |
|                        |                                        | joins                  |
+------------------------+----------------------------------------+------------------------+
| Random                 | ``DISTRIBUTED BY RANDOM BUCKETS N``    | Append-only tables     |
|                        |                                        | without clear filter   |
|                        |                                        | columns                |
+------------------------+----------------------------------------+------------------------+

Bucket Count
~~~~~~~~~~~~

- Each bucket = one tablet
- Target: **100 MB–1 GB per tablet** after compression
- Formula: ``BUCKETS = data_size_gb / 0.5`` (rough starting point)
- Too few buckets → large tablets, poor parallelism
- Too many buckets → small tablets, metadata overhead

Sort Key (Table Clustering)
---------------------------

The sort key determines physical row ordering and the automatic prefix
index.

Rules
~~~~~

1. Place the **most selective filter column first**
2. Maximum 3 columns in the sort key for practical benefit
3. For Primary Key tables, the primary key IS the sort key
4. For Duplicate Key tables, specify with ``DUPLICATE KEY(col1, col2)``

Example
~~~~~~~

.. code:: sql

   -- Queries filter on tenant_id and event_time
   CREATE TABLE events (
       tenant_id   INT,
       event_time  DATETIME,
       event_type  VARCHAR(32),
       payload     JSON
   )
   DUPLICATE KEY(tenant_id, event_time)
   PARTITION BY date_trunc('day', event_time)
   DISTRIBUTED BY HASH(tenant_id) BUCKETS 32;

Indexes
-------

Prefix Index (Automatic)
~~~~~~~~~~~~~~~~~~~~~~~~

- Built from the sort key columns (first 36 bytes)
- Accelerates scans that filter on leading sort key columns
- No creation syntax needed — derived from table key

Bitmap Index
~~~~~~~~~~~~

.. code:: sql

   CREATE INDEX idx_status ON my_table (status) USING BITMAP;

- Best for low-cardinality columns (< 1000 distinct values)
- Accelerates ``=``, ``IN``, ``NOT IN`` on columns in WHERE

Bloom Filter Index
~~~~~~~~~~~~~~~~~~

.. code:: sql

   ALTER TABLE my_table SET ("bloom_filter_columns" = "user_id,session_id");

- Best for high-cardinality columns with equality filters
- Reduces I/O by skipping data pages that definitely don’t match

Ngram Bloom Filter
~~~~~~~~~~~~~~~~~~

.. code:: sql

   CREATE INDEX idx_content ON my_table (content) USING NGRAMBF
   PROPERTIES ("gram_num" = "4", "bloom_filter_fpp" = "0.05");

- Accelerates ``LIKE '%substring%'`` queries on text columns

Compression
-----------

============= ================= ========= ==============================
Algorithm     Compression Ratio Speed     Use When
============= ================= ========= ==============================
LZ4 (default) Medium            Fast      General purpose
ZSTD          High              Medium    Storage-constrained, cold data
Snappy        Low–Medium        Very fast Query-latency-sensitive
============= ================= ========= ==============================

.. code:: sql

   PROPERTIES ("compression" = "ZSTD");

Hybrid Row-Column Storage
-------------------------

For tables that need both analytical scans and point lookups:

.. code:: sql

   PROPERTIES ("store_type" = "column_with_row");

- Stores data in both columnar (for scans) and row (for point queries)
  format
- Trades storage for query flexibility
- Use when the same table serves both OLAP dashboards and key-value
  lookups

Anti-Patterns
-------------

+---------------------------------------------------+-------------------+
| Anti-Pattern                                      | Fix               |
+===================================================+===================+
| Partitioning on high-cardinality column           | Partition on time |
|                                                   | or                |
|                                                   | low-cardinality   |
|                                                   | dimension         |
+---------------------------------------------------+-------------------+
| Too many buckets for small tables                 | Start with fewer  |
|                                                   | buckets, scale up |
|                                                   | as data grows     |
+---------------------------------------------------+-------------------+
| Sort key with > 3 columns                         | Pick the top 2–3  |
|                                                   | most selective    |
|                                                   | filter columns    |
+---------------------------------------------------+-------------------+
| Using Unique Key for CDC workloads                | Use Primary Key   |
|                                                   | (better read      |
|                                                   | perf, same write  |
|                                                   | semantics)        |
+---------------------------------------------------+-------------------+
| No partition pruning in queries                   | Always include    |
|                                                   | partition column  |
|                                                   | in WHERE          |
+---------------------------------------------------+-------------------+
