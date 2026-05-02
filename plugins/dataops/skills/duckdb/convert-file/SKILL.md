---
name: convert-file
license: CC-BY-4.0
description: Convert data files between CSV, Parquet, JSON, Excel, GeoJSON, and related formats with DuckDB. Use when the user asks to convert a file, export a dataset, save results in another format, or write binary outputs such as Parquet or XLSX.
---

# Convert File

Treat the first user-supplied path as the input file. If the user supplied a second path, treat it as the output file.

## Step 1 - Resolve Input And Output

**Input**: If the user gave a bare filename with no `/`, resolve it to a full path with:

```bash
INPUT_FILENAME="<INPUT_FILENAME>"
find "$PWD" -name "$INPUT_FILENAME" -not -path '*/.git/*' 2>/dev/null | head -1
```

**Output**: If the user supplied an explicit output path, use it. Otherwise default to the same stem as the input with a `.parquet` extension, for example `data.csv` -> `data.parquet`.

Infer the output format from the output file extension:

| Extension | Format clause |
| --- | --- |
| `.parquet`, `.pq` | default, no clause needed |
| `.csv` | `(FORMAT csv, HEADER)` |
| `.tsv` | `(FORMAT csv, HEADER, DELIMITER '\t')` |
| `.json` | `(FORMAT json, ARRAY true)` |
| `.jsonl`, `.ndjson` | `(FORMAT json, ARRAY false)` |
| `.xlsx` | `(FORMAT xlsx)` and requires `INSTALL excel; LOAD excel;` |
| `.geojson` | `(FORMAT GDAL, DRIVER 'GeoJSON')` and requires `LOAD spatial;` |
| `.gpkg` | `(FORMAT GDAL, DRIVER 'GPKG')` and requires `LOAD spatial;` |
| `.shp` | `(FORMAT GDAL, DRIVER 'ESRI Shapefile')` and requires `LOAD spatial;` |

## Step 2 - Convert

Run a single DuckDB command. Prepend extension loads as needed based on both the input and output formats.

```bash
duckdb -c "
<EXTENSION_LOADS>
COPY (FROM '<INPUT_PATH>') TO '<OUTPUT_PATH>' <FORMAT_CLAUSE>;
"
```

For remote inputs such as `s3://` or `https://`, prepend the same protocol setup as the sibling [../read-file/SKILL.md](../read-file/SKILL.md) workflow:

| Protocol | Prepend |
| --- | --- |
| `s3://` | `LOAD httpfs; CREATE SECRET (TYPE S3, PROVIDER credential_chain);` |
| `gs://`, `gcs://` | `LOAD httpfs; CREATE SECRET (TYPE GCS, PROVIDER credential_chain);` |
| `https://`, `http://` | `LOAD httpfs;` |

If the user mentions partitioning, for example "partition by year", add `PARTITION_BY (col)` to the format clause. This only works with Parquet and CSV output.

If the user mentions compression, for example "use zstd", add `CODEC 'zstd'` for Parquet output.

## Step 3 - Report

On success, report:

- Input file and detected format
- Output file, format, and size from `ls -lh`
- Row count if it is quick to compute

On failure:

- **`duckdb: command not found`** -> open [../install-duckdb/SKILL.md](../install-duckdb/SKILL.md), install DuckDB, then retry
- **Missing extension** -> install it and retry
- **Input parse error** -> suggest checking the input format or using [../read-file/SKILL.md](../read-file/SKILL.md) first to inspect it
