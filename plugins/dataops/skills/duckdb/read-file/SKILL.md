---
name: read-file
license: CC-BY-4.0
description: Read data files or remote URLs with DuckDB, including CSV, JSON, Parquet, Avro, Excel, spatial formats, and SQLite files. Use when the user asks what is in a dataset, wants a schema or sample, or needs quick profiling of a data file. Not for source code.
---

# Read File

Treat the user's file path or URL as the target dataset. If the user asks a follow-up question about the dataset, answer it after inspection.

## Step 1 - Read It

`RESOLVED_PATH` is the path or URL the user provided. If the user gave a bare filename with no `/`, resolve it to a full path with `find`.

Run a single DuckDB command that defines the `read_any` macro inline and reads the file.

For **remote files**, prepend the necessary `LOAD` and `CREATE SECRET` statements before the macro:

| Protocol | Prepend |
| --- | --- |
| `https://`, `http://` | `LOAD httpfs;` |
| `s3://` | `LOAD httpfs; CREATE SECRET (TYPE S3, PROVIDER credential_chain);` |
| `gs://`, `gcs://` | `LOAD httpfs; CREATE SECRET (TYPE GCS, PROVIDER credential_chain);` |
| `az://`, `azure://`, `abfss://` | `LOAD httpfs; LOAD azure; CREATE SECRET (TYPE AZURE, PROVIDER credential_chain);` |

For **local files**, no prefix is needed.

The SQLite branch of the `read_any` macro intentionally reads only the first table returned by `sqlite_master(file_name)`. If the user needs a specific SQLite table, list the tables first and then switch to an explicit call such as `sqlite_scan(file_name, '<table_name>')`.

```bash
duckdb -csv -c "
CREATE OR REPLACE MACRO read_any(file_name) AS TABLE
  WITH json_case AS (FROM read_json_auto(file_name))
     , csv_case AS (FROM read_csv(file_name))
     , parquet_case AS (FROM read_parquet(file_name))
     , avro_case AS (FROM read_avro(file_name))
     , blob_case AS (FROM read_blob(file_name))
     , spatial_case AS (FROM st_read(file_name))
     , excel_case AS (FROM read_xlsx(file_name))
     , sqlite_case AS (FROM sqlite_scan(file_name, (SELECT name FROM sqlite_master(file_name) LIMIT 1)))
     , ipynb_case AS (
         WITH nb AS (FROM read_json_auto(file_name))
         SELECT cell_idx, cell.cell_type,
                array_to_string(cell.source, '') AS source,
                cell.execution_count
         FROM nb, UNNEST(cells) WITH ORDINALITY AS t(cell, cell_idx)
         ORDER BY cell_idx
     )
  FROM query_table(
    CASE
      WHEN file_name ILIKE '%.json' OR file_name ILIKE '%.jsonl' OR file_name ILIKE '%.ndjson' OR file_name ILIKE '%.geojson' OR file_name ILIKE '%.geojsonl' OR file_name ILIKE '%.har' THEN 'json_case'
      WHEN file_name ILIKE '%.csv' OR file_name ILIKE '%.tsv' OR file_name ILIKE '%.tab' OR file_name ILIKE '%.txt' THEN 'csv_case'
      WHEN file_name ILIKE '%.parquet' OR file_name ILIKE '%.pq' THEN 'parquet_case'
      WHEN file_name ILIKE '%.avro' THEN 'avro_case'
      WHEN file_name ILIKE '%.xlsx' OR file_name ILIKE '%.xls' THEN 'excel_case'
      WHEN file_name ILIKE '%.shp' OR file_name ILIKE '%.gpkg' OR file_name ILIKE '%.fgb' OR file_name ILIKE '%.kml' THEN 'spatial_case'
      WHEN file_name ILIKE '%.ipynb' THEN 'ipynb_case'
      WHEN file_name ILIKE '%.db' OR file_name ILIKE '%.sqlite' OR file_name ILIKE '%.sqlite3' THEN 'sqlite_case'
      ELSE 'blob_case'
    END
  );

DESCRIBE FROM read_any('RESOLVED_PATH');
SELECT count(*) AS row_count FROM read_any('RESOLVED_PATH');
FROM read_any('RESOLVED_PATH') LIMIT 20;
"
```

If this fails:

- **`duckdb: command not found`** -> open [../install-duckdb/SKILL.md](../install-duckdb/SKILL.md), install DuckDB, then retry
- **Missing extension** for spatial files, xlsx, or sqlite -> retry with the matching `INSTALL` and `LOAD` statements prepended
- **Wrong reader or parse error** -> use the correct `read_*` function directly instead of `read_any`

## Step 2 - Answer

Using the schema, row count, and sample rows, answer the user's requested question, or provide a default summary of column types, row count, and notable patterns.
