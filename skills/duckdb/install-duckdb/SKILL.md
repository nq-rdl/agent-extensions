---
name: install-duckdb
license: CC-BY-4.0
description: Install or update DuckDB extensions, or update the DuckDB CLI itself when needed. Use when DuckDB is missing, an extension needs to be installed or refreshed, or another DuckDB workflow reports a missing extension.
---

# Install DuckDB

Treat each requested argument as either `name` or `name@repo`. Use `--update` to switch from install mode to update mode.

Each extension argument has the form `name` or `name@repo`.

- `name` -> `INSTALL name;`
- `name@repo` -> `INSTALL name FROM repo;`

## Step 1 - Locate DuckDB

```bash
DUCKDB=$(command -v duckdb)
```

If DuckDB is not found, tell the user:

> **DuckDB is not installed.** Install it first with one of:
> - macOS: `brew install duckdb`
> - Linux: `curl -fsSL https://install.duckdb.org | sh`
> - Windows: `winget install DuckDB.cli`
>
> Then retry this install workflow.

Stop if DuckDB is not found.

## Step 2 - Check For `--update`

If `--update` is present, remove it from the argument list and set mode to **update**. Otherwise set mode to **install**.

## Step 3 - Build And Run Statements

**Install mode**

Parse each remaining argument:

- If it contains `@`, split on `@` -> `INSTALL <name> FROM <repo>;`
- Otherwise -> `INSTALL <name>;`

Run all statements in a single DuckDB call:

```bash
"$DUCKDB" :memory: -c "INSTALL <ext1>; INSTALL <ext2> FROM <repo2>; ..."
```

**Update mode**

First, check whether the DuckDB CLI itself is up to date:

```bash
CURRENT=$(duckdb --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
LATEST=$(curl -fsSL https://duckdb.org/data/latest_stable_version.txt)
```

- If `CURRENT == LATEST`, report that the DuckDB CLI is current.
- If `CURRENT != LATEST`, ask the user whether to upgrade now.

If the user agrees, detect the platform and run the appropriate upgrade command:

- macOS with Homebrew: `brew upgrade duckdb`
- Linux: `curl -fsSL https://install.duckdb.org | sh`
- Windows: `winget upgrade DuckDB.cli`

Then update extensions:

- No extension names -> update all: `UPDATE EXTENSIONS;`
- With extension names -> update specific extensions in one call, ignoring any `@repo` suffixes:

```bash
"$DUCKDB" :memory: -c "UPDATE EXTENSIONS;"
```

or

```bash
"$DUCKDB" :memory: -c "UPDATE EXTENSIONS (<ext1>, <ext2>, ...);"
```

Report success or failure after the call completes.

## Validation

For manual smoke tests of representative install commands, use [scripts/eval.sh](scripts/eval.sh).
