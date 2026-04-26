---
name: query
license: CC-BY-4.0
description: Run SQL against an attached DuckDB database or ad-hoc against files, including natural-language requests that need SQL generation. Use when the user asks a data question, provides DuckDB SQL, or wants to query files with DuckDB.
---

# Query

Treat the user's request as either SQL or a natural-language query.

Follow these steps in order.

## Step 1 - Resolve State And Determine The Mode

Look for an existing state file in either location:

```bash
STATE_DIR=""
test -f .duckdb-skills/state.sql && STATE_DIR=".duckdb-skills"
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")"
PROJECT_ID="$(echo "$PROJECT_ROOT" | tr '/' '-')"
test -f "$HOME/.duckdb-skills/$PROJECT_ID/state.sql" && STATE_DIR="$HOME/.duckdb-skills/$PROJECT_ID"
```

If a state file exists, verify the databases it references are still accessible:

```bash
duckdb -init "$STATE_DIR/state.sql" -c "SHOW DATABASES;"
```

Now determine the mode:

- **Ad-hoc mode** if the `--file` flag is present, the SQL references file paths or literals such as `FROM 'data.csv'`, or `STATE_DIR` is empty.
- **Session mode** if `STATE_DIR` is set and the input references table names, is natural language, or is SQL without file references.

If no state file exists and no file is referenced, fall back to ad-hoc mode against `:memory:`. The user must reference files directly in the SQL.

If the state file exists but any `ATTACH` in it fails, warn the user and fall back to ad-hoc mode.

## Step 2 - Check DuckDB Is Installed

```bash
command -v duckdb
```

If not found, open [../install-duckdb/SKILL.md](../install-duckdb/SKILL.md), follow it to install DuckDB, then continue.

## Step 3 - Generate SQL If Needed

If the input is natural language rather than valid SQL, generate SQL using the Friendly SQL reference below.

In **session mode**, first retrieve the schema to inform query generation:

```bash
duckdb -init "$STATE_DIR/state.sql" -csv -c "
SELECT table_name FROM duckdb_tables() ORDER BY table_name;
"
```

Then, for the relevant tables:

```bash
duckdb -init "$STATE_DIR/state.sql" -csv -c "DESCRIBE <table_name>;"
```

Use the schema context and the Friendly SQL reference to generate the most appropriate query.

## Step 4 - Estimate Result Size

Before executing, estimate whether the query could produce a very large result that would consume excessive tokens when returned in the conversation.

**Session mode**: check row counts for the tables involved:

```bash
duckdb -init "$STATE_DIR/state.sql" -csv -c "
SELECT table_name, estimated_size, column_count
FROM duckdb_tables()
WHERE table_name IN ('<table1>', '<table2>');
"
```

**Ad-hoc mode**: probe the source:

```bash
duckdb :memory: -csv -c "
SET allowed_paths=['FILE_PATH'];
SET enable_external_access=false;
SET allow_persistent_secrets=false;
SET lock_configuration=true;
SELECT count() AS row_count FROM 'FILE_PATH';
"
```

Evaluate the result:

- If the query already has a `LIMIT`, `count()`, or another aggregation that bounds the output, proceed.
- If the source has **more than 1M rows** and the query has no `LIMIT` or aggregation, tell the user that the result set will be large and suggest adding `LIMIT 1000` or an aggregation. Ask for confirmation before running it as-is.
- If the data size is **more than 10 GB**, also warn that the query may take a while. Proceed only if the user confirms.

Skip this step for intrinsically bounded queries such as `DESCRIBE`, `SUMMARIZE`, aggregations, or `count()`.

## Step 5 - Execute The Query

**Ad-hoc mode** with only the referenced files accessible:

```bash
duckdb :memory: -csv <<'SQL'
SET allowed_paths=['FILE_PATH'];
SET enable_external_access=false;
SET allow_persistent_secrets=false;
SET lock_configuration=true;
<QUERY>;
SQL
```

Replace `FILE_PATH` with the actual file path extracted from the query or `--file` argument. If multiple files are referenced, include all of them in the `allowed_paths` list.

**Session mode** against the user-trusted database:

```bash
duckdb -init "$STATE_DIR/state.sql" -csv -c "<QUERY>"
```

For multi-line queries, use a heredoc with `-init`:

```bash
duckdb -init "$STATE_DIR/state.sql" -csv <<'SQL'
<QUERY>;
SQL
```

Always use heredocs for multi-line queries to avoid shell-quoting problems.

## Step 6 - Handle Errors

- **Syntax error**: show the error, suggest a corrected query, and retry.
- **Missing extension**: open [../install-duckdb/SKILL.md](../install-duckdb/SKILL.md), install the missing extension, then retry.
- **Table not found** in session mode: list available tables from `duckdb_tables()` and suggest corrections.
- **File not found** in ad-hoc mode: use `find "$PWD" -name "<filename>" 2>/dev/null` to locate the file and suggest the corrected path.
- **Persistent or unclear DuckDB error**: open [../duckdb-docs/SKILL.md](../duckdb-docs/SKILL.md), search the docs for the error or feature, then apply the fix and retry.

## Step 7 - Present Results

Show the query output to the user. If the result has more than 100 rows, note the truncation and suggest adding `LIMIT`.

For natural-language questions, also provide a brief interpretation of the results.

## DuckDB Friendly SQL Reference

When generating SQL, prefer these idiomatic DuckDB constructs:

### Compact Clauses

- **FROM-first**: `FROM table WHERE x > 10`
- **GROUP BY ALL**: auto-groups by all non-aggregate columns
- **ORDER BY ALL**: orders by all columns for deterministic results
- **SELECT * EXCLUDE (col1, col2)**: drop columns from a wildcard
- **SELECT * REPLACE (expr AS col)**: transform a column in place
- **UNION ALL BY NAME**: combine tables with different column orders
- **Percentage LIMIT**: `LIMIT 10%`
- **Prefix aliases**: `SELECT x: 42`
- Trailing commas are allowed in `SELECT` lists

### Query Features

- `count()` instead of `count(*)`
- Reusable aliases in `WHERE`, `GROUP BY`, and `HAVING`
- Lateral column aliases such as `SELECT i+1 AS j, j+2 AS k`
- `COLUMNS(*)` for expressions across columns, including regex, `EXCLUDE`, `REPLACE`, and lambdas
- `FILTER` clauses for conditional aggregation
- `GROUPING SETS`, `CUBE`, and `ROLLUP`
- Top-N-per-group helpers such as `max(col, 3)`, `arg_max(arg, val, n)`, and `min_by(arg, val, n)`
- `DESCRIBE table_name`
- `SUMMARIZE table_name`
- `PIVOT` and `UNPIVOT`
- `SET VARIABLE x = expr` and `getvariable('x')`

### Data Import

- Direct file queries such as `FROM 'file.csv'` and `FROM 'data.parquet'`
- Globbing such as `FROM 'data/part-*.parquet'`
- Automatic CSV header and schema detection

### Expressions And Types

- Dot chaining such as `'hello'.upper()` or `col.trim().lower()`
- List comprehensions such as `[x*2 FOR x IN list_col]`
- List and string slicing such as `col[1:3]` and `col[-1]`
- `STRUCT.*` notation
- Square-bracket list literals such as `[1, 2, 3]`
- `format()` for string formatting

### Joins

- `ASOF` joins
- Positional joins
- Lateral joins

### Data Modification

- `CREATE OR REPLACE TABLE`
- `CREATE TABLE ... AS SELECT`
- `INSERT INTO ... BY NAME`
- `INSERT OR IGNORE INTO` and `INSERT OR REPLACE INTO`
