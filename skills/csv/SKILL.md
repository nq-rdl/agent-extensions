---
name: csv
license: MIT
description: >-
  Use when scanning, updating, validating, or summarising pipe-delimited
  CSV extraction sheets for the scoping review. Also covers converting the Excel
  workbook to CSVs. Trigger when working with scopingreviewdataV3_*.csv files,
  filling in missing study data, or regenerating CSVs from the Excel source.
compatibility: >-
  Requires Python 3.11+, pyarrow, openpyxl, typer, rich
metadata:
  repo: https://github.com/nq-rdl/agent-skills
---

# CSV Management

## Overview

This skill provides structured tools for managing the scoping review extraction CSVs — seven pipe-delimited sheets exported from `scoping-review-dataV3.xlsx`. Tools cover:

- **show-missing** — scan a sheet for empty/null fields per row
- **update-row** — update specific fields in a row by SID key match
- **validate** — check values against schema rules (Funding, COI, SID pattern, booleans)
- **summary** — cross-sheet completion dashboard
- **excel-to-csv** — regenerate CSVs from the Excel workbook

## Dependencies

Install Python dependencies before first use:

```bash
bash scripts/ensure-deps.sh
```

This auto-detects your package manager (pixi, uv, mamba, conda, pip) and installs from `requirements.txt`.

### Running scripts

All scripts run from the skill directory. Use **absolute paths** for CSV files:

```bash
SKILL_DIR="$(claude skill-dir csv)"  # or the skill's installed path
python "$SKILL_DIR/scripts/show_missing.py" /abs/path/to/file.csv
python "$SKILL_DIR/scripts/update_row.py" /abs/path/to/file.csv --key SID --match S39 --set "Country=US"
python "$SKILL_DIR/scripts/validate.py" /abs/path/to/file.csv
python "$SKILL_DIR/scripts/summary.py" /abs/path/to/analysis/
python "$SKILL_DIR/scripts/excel_to_csv.py" /abs/path/to/scoping-review-dataV3.xlsx
```

## Quick Reference

| Task | Command |
|------|---------|
| Find empty fields in a sheet | `python scripts/show_missing.py FILE.csv` |
| Check only incomplete rows | `python scripts/show_missing.py FILE.csv --only-missing` |
| Count missing (no table) | `python scripts/show_missing.py FILE.csv --count` |
| Update a field in a row | `python scripts/update_row.py FILE.csv --key SID --match S39 --set "Country=US"` |
| Preview update (no write) | `python scripts/update_row.py FILE.csv --key SID --match S39 --set "Country=US" --dry-run` |
| Validate allowed values | `python scripts/validate.py FILE.csv` |
| Cross-sheet dashboard | `python scripts/summary.py analysis/` |
| Per-study breakdown | `python scripts/summary.py analysis/ --by-study` |
| Regenerate CSVs from Excel | `python scripts/excel_to_csv.py workbook.xlsx -p "E."` |

## Script CLI Reference

### show-missing

```
Usage: python scripts/show_missing.py [OPTIONS] CSV_PATH

Arguments:
  CSV_PATH          Path to the pipe-delimited CSV file

Options:
  -k, --key TEXT    Column name used as row identifier [default: SID]
  -c, --columns TEXT  Comma-separated columns to check (default: all non-placeholder)
  --only-missing    Only show rows that have at least one missing field
  --count           Show summary counts only, no per-row table
```

### update-row

```
Usage: python scripts/update_row.py [OPTIONS] CSV_PATH

Arguments:
  CSV_PATH          Path to the pipe-delimited CSV file

Options:
  -k, --key TEXT    Column to match on [required]
  -m, --match TEXT  Value to match in key column [required]
  -s, --set TEXT    'Field=Value' assignment (repeat for multiple) [required]
  --dry-run         Show diff without writing
  --backup          Create a .bak copy before writing
```

### validate

```
Usage: python scripts/validate.py [OPTIONS] CSV_PATH

Arguments:
  CSV_PATH    Path to the pipe-delimited CSV file

Options:
  --strict    Treat warnings as errors
  -q, --quiet Show only error count
```

### summary

```
Usage: python scripts/summary.py [OPTIONS] DIR_PATH

Arguments:
  DIR_PATH         Directory containing extraction CSV files

Options:
  -p, --pattern TEXT   Glob pattern [default: *_E.*.csv]
  -k, --key TEXT       Row identifier column [default: SID]
  --all                Include fully complete sheets
  --by-study           Show per-SID breakdown across all sheets
```

### excel-to-csv

```
Usage: python scripts/excel_to_csv.py [OPTIONS] EXCEL_PATH

Arguments:
  EXCEL_PATH        Path to the Excel workbook (.xlsx)

Options:
  -o, --output-dir PATH   Output directory (default: same as Excel)
  -p, --prefix TEXT       Only process sheets starting with this prefix
  -f, --force             Overwrite existing CSV files
  --cleanup               Remove existing CSVs/Excel files in output dir first
```

## CSV Format

All extraction sheets are **pipe-delimited** (`|`) with **double-quoted** string values:

```
"RN"|"SID"|"Study ID"|"Country"|...
1|"S1"|"Wang_2024"|"China"|...
```

**Read pattern (pyarrow):**
```python
import pyarrow.csv as pcsv
tbl = pcsv.read_csv(path,
    parse_options=pcsv.ParseOptions(delimiter="|"),
    convert_options=pcsv.ConvertOptions(strings_can_be_null=False))
```

**Write pattern (pyarrow):**
```python
pcsv.write_csv(tbl, path, pcsv.WriteOptions(delimiter="|"))
```

## When to Use

- A new batch of papers (S34–S64) needs data extracted → run `show-missing` first
- After populating a row via PDF extraction → run `update-row` with `--dry-run` to verify
- Before committing CSV changes → run `validate` to catch invalid Funding/COI values
- To see overall progress across all 7 sheets → run `summary analysis/`
- After editing the Excel workbook → run `excel-to-csv` to regenerate CSVs

## Reference Files
- `references/reference.rst` — Schema definitions, data dictionary, allowed values, and PyArrow patterns
