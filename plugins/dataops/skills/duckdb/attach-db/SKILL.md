---
name: attach-db
license: CC-BY-4.0
description: Attach a DuckDB database file, inspect its tables and schema, and append an `ATTACH` entry to the shared DuckDB state file used by the sibling query workflow. Use when the user wants to open a `.duckdb` file or make a database available for repeated DuckDB queries.
---

# Attach DB

Treat the user's database path as the target database.

Follow these steps in order, stopping and reporting clearly if any step fails.

**State file convention**: All DuckDB subworkflows share one `state.sql` file per project. Once resolved, any workflow can reuse it with `duckdb -init "$STATE_DIR/state.sql" -c "<QUERY>"`.

## Step 1 - Resolve The Database Path

Start by assigning the user-supplied database path to a shell variable such as `USER_DB_PATH`. If the user gave a relative path, resolve it against `$PWD` to get an absolute path (`RESOLVED_PATH`).

```bash
USER_DB_PATH="<USER_DB_PATH>"
RESOLVED_PATH="$(cd "$(dirname "$USER_DB_PATH")" 2>/dev/null && pwd)/$(basename "$USER_DB_PATH")"
```

Check the file exists:

```bash
test -f "$RESOLVED_PATH"
```

- **File exists** -> continue to Step 2.
- **File not found** -> ask the user if they want to create a new empty database. DuckDB creates the file on first write. If yes, continue. If no, stop.

## Step 2 - Check DuckDB Is Installed

```bash
command -v duckdb
```

If not found, open [../install-duckdb/SKILL.md](../install-duckdb/SKILL.md), follow it to install DuckDB, then continue.

## Step 3 - Validate The Database

```bash
duckdb "$RESOLVED_PATH" -c "PRAGMA version;"
```

- **Success** -> continue.
- **Failure** -> report the error clearly, for example a corrupt file or a non-DuckDB database, and stop.

## Step 4 - Explore The Schema

First, list all tables:

```bash
duckdb "$RESOLVED_PATH" -csv -c "
SELECT table_name, estimated_size
FROM duckdb_tables()
ORDER BY table_name;
"
```

If the database has **no tables**, note that it is empty and skip to Step 5.

For each table discovered, up to 20 tables, run:

```bash
duckdb "$RESOLVED_PATH" -csv -c "
DESCRIBE <table_name>;
SELECT count() AS row_count FROM <table_name>;
"
```

Collect the column definitions and row counts for the summary.

## Step 5 - Resolve The State Directory

Check whether a state file already exists in either location:

```bash
test -f .duckdb-skills/state.sql && STATE_DIR=".duckdb-skills"

PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")"
PROJECT_ID="$(echo "$PROJECT_ROOT" | tr '/' '-')"
test -f "$HOME/.duckdb-skills/$PROJECT_ID/state.sql" && STATE_DIR="$HOME/.duckdb-skills/$PROJECT_ID"
```

If **neither exists**, ask the user:

> Where should DuckDB session state live for this project?
>
> 1. **In the project directory** (`.duckdb-skills/state.sql`) so it is easy to inspect locally.
> 2. **In the home directory** (`~/.duckdb-skills/<project-id>/state.sql`) so the project tree stays clean.

Based on their choice:

**Option 1:**

```bash
STATE_DIR=".duckdb-skills"
mkdir -p "$STATE_DIR"
```

Then ask whether they want `.duckdb-skills/` added to `.gitignore`. If yes:

```bash
echo '.duckdb-skills/' >> .gitignore
```

**Option 2:**

```bash
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")"
PROJECT_ID="$(echo "$PROJECT_ROOT" | tr '/' '-')"
STATE_DIR="$HOME/.duckdb-skills/$PROJECT_ID"
mkdir -p "$STATE_DIR"
```

## Step 6 - Append To The State File

`state.sql` is a shared, accumulative init file used by all DuckDB subworkflows. It may already contain macros, `LOAD` statements, secrets, or other `ATTACH` statements written by other workflows. **Never overwrite it**. Check for duplicates and append only when needed.

Derive the database alias from the filename without extension, for example `my_data.duckdb` -> `my_data`.

Before embedding the path in SQL, escape any single quotes by doubling them:

```bash
SQL_PATH=${RESOLVED_PATH//\'/\'\'}
```

Then check whether this `ATTACH` already exists:

```bash
grep -Fq "ATTACH IF NOT EXISTS '$SQL_PATH'" "$STATE_DIR/state.sql" 2>/dev/null
```

If it is not already present, append:

```bash
cat >> "$STATE_DIR/state.sql" <<'STATESQL'
ATTACH IF NOT EXISTS 'SQL_PATH' AS my_data;
USE my_data;
STATESQL
```

Replace `SQL_PATH` and `my_data` with the actual values. Use the escaped `SQL_PATH`, not the raw path, anywhere the path is inserted into SQL. If the alias would conflict with an existing one in the file, ask the user for a different alias.

## Step 7 - Verify The State File Works

```bash
duckdb -init "$STATE_DIR/state.sql" -c "SHOW TABLES;"
```

If this fails, fix the state file and retry.

## Step 8 - Report

Summarize for the user:

- **Database path**: the resolved absolute path
- **Alias**: the database alias used in the state file
- **State file**: the resolved `STATE_DIR/state.sql` path
- **Tables**: name, column count, and row count for each table, or note that the database is empty
- Confirm the database is now available to the sibling query workflow in [../query/SKILL.md](../query/SKILL.md)

If the database is empty, suggest creating tables or importing data.
