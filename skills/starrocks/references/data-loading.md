# StarRocks Data Loading Quick Reference

Condensed from the [Data Loading](https://docs.starrocks.io/docs/loading/) and
[Data Unloading](https://docs.starrocks.io/docs/unloading/) docs.

## Loading Methods Comparison

| Method | Source | Latency | Throughput | Use Case |
|--------|--------|---------|-----------|----------|
| Stream Load | HTTP POST | Low | Medium | Real-time micro-batch (< 10 GB) |
| Broker Load | S3/HDFS/GCS | Medium | High | Batch import from object storage |
| INSERT INTO | SQL | Low | Low | Small inserts, internal ETL |
| Routine Load | Kafka | Continuous | Medium | Streaming ingestion from Kafka |
| Spark connector | Spark | Medium | High | ETL pipelines via Spark |
| Flink connector | Flink | Continuous | High | Streaming ETL via Flink |
| Pipe | S3 (auto) | Continuous | High | Auto-discovery of new S3 files |

## Stream Load

HTTP-based push. Best for micro-batch or programmatic loading.

```bash
curl -XPUT "http://<fe_host>:8030/api/<db>/<table>/_stream_load" \
  -H "Authorization: Basic <base64>" \
  -H "format: json" \
  -H "strip_outer_array: true" \
  -T data.json
```

**Key parameters:**
- `format`: `json`, `csv`
- `column_separator`: delimiter for CSV (default: `\t`)
- `max_filter_ratio`: fraction of bad rows tolerated (0.0–1.0)
- `columns`: column mapping and transformation expressions
- `jsonpaths`: extract specific fields from JSON

## Broker Load

For large-scale batch import from remote storage.

```sql
LOAD LABEL my_db.load_20240101 (
    DATA INFILE ("s3://bucket/path/*.parquet")
    INTO TABLE my_table
    FORMAT AS "parquet"
)
WITH BROKER
PROPERTIES (
    "timeout" = "3600",
    "aws.s3.access_key" = "...",
    "aws.s3.secret_key" = "..."
);
```

**Monitor progress:**
```sql
SHOW LOAD WHERE LABEL = 'load_20240101';
-- Or via information_schema:
SELECT * FROM information_schema.loads
WHERE label = 'load_20240101';
```

## Routine Load (Kafka)

Continuous ingestion from Kafka topics.

```sql
CREATE ROUTINE LOAD my_db.kafka_load ON my_table
COLUMNS TERMINATED BY ",",
COLUMNS (col1, col2, col3)
PROPERTIES (
    "desired_concurrent_number" = "3",
    "max_error_number" = "1000",
    "format" = "json"
)
FROM KAFKA (
    "kafka_broker_list" = "broker1:9092,broker2:9092",
    "kafka_topic" = "my_topic",
    "kafka_partitions" = "0,1,2",
    "property.group.id" = "starrocks_consumer"
);
```

**Monitor:**
```sql
SHOW ROUTINE LOAD FOR my_db.kafka_load;
-- Or:
SELECT * FROM information_schema.routine_load_jobs
WHERE name = 'kafka_load';
```

**Control:**
```sql
PAUSE ROUTINE LOAD FOR my_db.kafka_load;
RESUME ROUTINE LOAD FOR my_db.kafka_load;
STOP ROUTINE LOAD FOR my_db.kafka_load;
```

## Pipe (Continuous S3 Ingestion)

Auto-discovers and loads new files from S3 (v3.2+).

```sql
CREATE PIPE my_db.s3_pipe
PROPERTIES ("auto_ingest" = "true")
AS INSERT INTO my_table
SELECT * FROM FILES (
    "path" = "s3://bucket/incoming/",
    "format" = "parquet",
    "aws.s3.access_key" = "...",
    "aws.s3.secret_key" = "..."
);
```

**Monitor:**
```sql
SELECT * FROM information_schema.pipes;
SELECT * FROM information_schema.pipe_files;
```

## INSERT INTO (SQL)

For small inserts, CTAS, or internal ETL.

```sql
-- Direct values
INSERT INTO my_table VALUES (1, 'alice', 100);

-- From query (internal ETL)
INSERT INTO summary_table
SELECT date_trunc('day', event_time), COUNT(*)
FROM events
GROUP BY 1;

-- CTAS
CREATE TABLE snapshot AS
SELECT * FROM events WHERE dt = '2024-01-01';
```

## Data Transformation at Load

Transform data during loading to avoid post-load ETL:

```sql
-- Stream Load with column mapping
curl -XPUT ... \
  -H "columns: col1, col2, col3, dt=date_trunc('day', col1)"

-- Broker Load with WHERE and expressions
LOAD LABEL my_db.filtered_load (
    DATA INFILE ("s3://bucket/data.csv")
    INTO TABLE my_table
    COLUMNS TERMINATED BY ","
    (raw_ts, user_id, amount)
    SET (event_date = date_trunc('day', raw_ts))
    WHERE amount > 0
);
```

## Data Unloading

### INSERT INTO FILES (Recommended)

```sql
INSERT INTO FILES (
    "path" = "s3://bucket/export/",
    "format" = "parquet",
    "partition_by" = "dt",
    "aws.s3.access_key" = "...",
    "aws.s3.secret_key" = "..."
)
SELECT * FROM my_table WHERE dt >= '2024-01-01';
```

### EXPORT

```sql
EXPORT TABLE my_table
TO "s3://bucket/export/"
PROPERTIES (
    "column_separator" = ",",
    "line_delimiter" = "\n"
)
WITH BROKER
PROPERTIES (
    "aws.s3.access_key" = "...",
    "aws.s3.secret_key" = "..."
);
```

### Arrow Flight SQL

High-throughput programmatic access (v3.5+). Connect via any Arrow Flight SQL client
on port 8040 (default). Useful for data science tools (Pandas, Polars, DuckDB).

## Strict Mode

Controls how StarRocks handles rows that fail type conversion:

```sql
-- During load
PROPERTIES ("strict_mode" = "true");
```

- **strict_mode = true**: reject rows with conversion failures
- **strict_mode = false** (default): convert failures to NULL

Enable strict mode for production data pipelines to catch data quality issues early.

## Loading Anti-Patterns

| Anti-Pattern | Fix |
|-------------|-----|
| Many small Stream Loads per second | Batch into larger micro-batches (1–10 second windows) |
| Broker Load without monitoring | Check `information_schema.loads` or `SHOW LOAD` |
| Routine Load with no error budget | Set `max_error_number` to tolerate transient bad records |
| Loading without strict mode | Enable strict mode for production pipelines |
| Post-load transformation queries | Use column expressions during load instead |
