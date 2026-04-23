---
name: s3-explore
license: CC-BY-4.0
description: Explore and query data on S3, Cloudflare R2, GCS, MinIO, or compatible object storage with DuckDB. Use when the user mentions `s3://`, `r2://`, `gs://`, or `gcs://` URLs, asks what is in a bucket, or wants schema, size, sample, or query results from remote data without downloading it first.
---

# S3 Explore

Treat the user's object-storage URL as the target location. If the user asked a follow-up question, answer it after inspection.

## Step 1 - Detect The Provider And Set Up Credentials

Based on the URL or user context, prepend the appropriate secret configuration:

| Provider | URL patterns | Secret setup |
| --- | --- | --- |
| **AWS S3** | `s3://` | `CREATE SECRET (TYPE S3, PROVIDER credential_chain);` |
| **Cloudflare R2** | `r2://`, or `s3://` with an R2 endpoint | `CREATE SECRET (TYPE R2, PROVIDER credential_chain);` |
| **GCS** | `gs://`, `gcs://` | `CREATE SECRET (TYPE GCS, PROVIDER credential_chain);` |
| **MinIO or custom** | `s3://` with a custom endpoint | `CREATE SECRET (TYPE S3, KEY_ID '...', SECRET '...', ENDPOINT '...', USE_SSL true);` |

For R2, if the user provides an account ID, the endpoint is `<account_id>.r2.cloudflarestorage.com`. R2 URLs such as `r2://bucket/path` should be rewritten to `s3://bucket/path` with the R2 secret.

For public buckets, skip the secret setup.

Always prepend:

```sql
LOAD httpfs;
```

## Step 2 - Determine What The URL Points To

If the URL looks like a directory or bucket, meaning no file extension or a trailing slash, list its contents with sizes:

```bash
duckdb -c "
LOAD httpfs;
<SECRET_SETUP>
SELECT filename, (size / 1024 / 1024)::DECIMAL(10,1) AS size_mb, last_modified
FROM read_blob('<URL>/*')
ORDER BY filename
LIMIT 50;
"
```

Only select `filename`, `size`, and `last_modified`. Never select `content`, which would download file bodies.

If the URL points to a specific file or glob pattern, preview it:

```bash
duckdb -c "
LOAD httpfs;
<SECRET_SETUP>
DESCRIBE FROM '<URL>';
SELECT count(*) AS row_count FROM '<URL>';
FROM '<URL>' LIMIT 20;
"
```

For Parquet files, get row counts and sizes from metadata without downloading row data:

```bash
duckdb -c "
LOAD httpfs;
<SECRET_SETUP>
SELECT file_name,
       sum(row_group_num_rows) AS total_rows,
       (sum(row_group_compressed_bytes) / 1024 / 1024)::DECIMAL(10,1) AS compressed_mb
FROM parquet_metadata('<URL>')
GROUP BY file_name;
"
```

## Step 3 - Answer The Question

Using the listing, schema, or sample data, answer the user's question.

If the user asks an analytical question such as "how many rows match X", write and run the appropriate SQL query. DuckDB pushes predicates down into Parquet on object storage, so filtered queries can still be efficient.

## Error Handling

- **`duckdb: command not found`** -> open [../install-duckdb/SKILL.md](../install-duckdb/SKILL.md), install DuckDB, then retry
- **Access denied or 403** -> suggest checking credentials such as `aws configure`, environment variables, or explicit keys
- **Bucket not found or 404** -> check the URL and region
- **Timeout on a large listing** -> suggest narrowing the glob pattern or adding a prefix
