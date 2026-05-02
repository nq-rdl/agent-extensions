---
name: duckdb
license: CC-BY-4.0
description: >-
  Work with DuckDB from the CLI: install or update DuckDB and extensions,
  attach database files, query local or remote data, convert formats, explore
  object storage, search DuckDB docs, run spatial analysis, and inspect prior
  session logs stored as JSONL. Use when the user mentions DuckDB, wants SQL
  over files or buckets, needs DuckDB-backed conversion or profiling, or asks
  for DuckDB extension help.
---

# DuckDB

Use this skill as a dispatcher. Start here, choose the closest DuckDB workflow, then open that nested `SKILL.md` before doing substantial work.

## Choose A Workflow

| Need | Read next |
| --- | --- |
| Attach a `.duckdb` database file and keep it available for repeated queries | [attach-db/SKILL.md](attach-db/SKILL.md) |
| Run SQL or turn a natural-language request into DuckDB SQL | [query/SKILL.md](query/SKILL.md) |
| Inspect a local file, remote URL, schema, or sample rows | [read-file/SKILL.md](read-file/SKILL.md) |
| Convert data between CSV, Parquet, JSON, Excel, or spatial formats | [convert-file/SKILL.md](convert-file/SKILL.md) |
| Install or update DuckDB and DuckDB extensions | [install-duckdb/SKILL.md](install-duckdb/SKILL.md) |
| Explore S3, R2, GCS, MinIO, or compatible object storage | [s3-explore/SKILL.md](s3-explore/SKILL.md) |
| Answer spatial questions or work with Overture Maps and spatial files | [spatial/SKILL.md](spatial/SKILL.md) |
| Search DuckDB or DuckLake docs using a local cached index | [duckdb-docs/SKILL.md](duckdb-docs/SKILL.md) |
| Search prior session logs stored as JSONL | [read-memories/SKILL.md](read-memories/SKILL.md) |

## Shared Conventions

- Prefer direct `duckdb` CLI invocations over ad-hoc helper scripts when one SQL call is enough.
- Reuse the shared DuckDB session state file when attaching databases. The supported locations are `.duckdb-skills/state.sql` in the project or `~/.duckdb-skills/<project-id>/state.sql`.
- Append to `state.sql`; never overwrite it. Other workflows may already have written macros, secrets, extension loads, or `ATTACH` statements there.
- In ad-hoc file mode, restrict DuckDB to explicit file paths and disable external access unless the user asked for remote data.
- Read only the nested references needed for the active workflow. The detailed procedures live in the subdirectories, not in this top-level dispatcher.
