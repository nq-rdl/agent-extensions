# CSV Skill Reference

## Sheet Schema (Data Dictionary D1–D47)

| ID | Field | Type | Notes |
|----|-------|------|-------|
| D1 | SID | String | Unique study ID, pattern `S\d+` |
| D2 | Study ID | String | Human-readable, e.g. `Wang_2024` |
| D3 | Country | String | Free text |
| D4 | Authors | String | `LastName, Initials; LastName, Initials; ...` |
| D5 | Published Year | Integer | 4-digit year |
| D6 | Title of Paper | String | Free text |
| D7 | Journal / Publication Venue | String | Free text |
| D8 | Funding | String | Controlled vocab — see below |
| D9 | COI | String | Controlled vocab — see below |
| D10 | Healthcare Setting | String | Free text |
| D11 | Clinical Task/Application Area | String | Free text |
| D12 | Dataset Type | String | Free text |
| D13 | Dataset Used | String | Free text |
| D14 | Dataset Size | Integer | Free text (authors' reported figure) |
| D15 | Granularity | String | Free text |
| D16 | Threshold/Probability cutoff Reported | Boolean | `0` or `1` |
| D17 | Detection Method Name | String | Free text |
| D18 | Detection Method Formula | String | Free text |
| D19 | FID | String | Pattern `F\d+` |
| D20 | VID | String | Pattern `V\d+` |
| D21 | Validation strategy name | String | Free text |
| D22 | Underlying Performance Metric | String | e.g. Sensitivity, AUROC, PPV |
| D23 | SIGID | String | Pattern `SIG\d+` |
| D24 | Statistical Test | String | Free text |
| D25 | CI | Boolean | `0` or `1` |
| D26 | Bias Type Detected By Method | String | Free text |
| D27 | Page number | Integer | Page within manuscript |
| D28 | Attributes | String | e.g. sex, ethnicity, comorbidity |
| D29 | Reason for attribute | String | Free text |
| D30 | Number of subgroups | Integer | Per attribute |
| D31 | Subgroup definition source | String | Free text |
| D32 | Subgroup justification | String | Free text |
| D33–D39 | Cohort 1–7 | String | Subcohort definitions |
| D40 | Method Applied at Data Acquisition Stage | Boolean | `0` or `1` |
| D41 | Method Applied at Data Preparation Stage | Boolean | `0` or `1` |
| D42 | Method Applied at Modelling Stage | Boolean | `0` or `1` |
| D43 | Method Applied at Evaluation Stage | Boolean | `0` or `1` |
| D44 | Specific ML model(s) method applied to | List | Free text |
| D45 | Study utilised Traditional ML | Boolean | `0` or `1` |
| D46 | Study utilised Deep Learning | Boolean | `0` or `1` |
| D47 | Study utilised LLM | Boolean | `0` or `1` |

## Allowed Values for Controlled Vocabulary Fields

### Funding (D8)
```
"Public"
"Commercial"
"Mixed"
"Not Reported"
```

### COI (D9)
```
"None declared"
"Yes"
"Not Reported"
```

### Boolean columns (D16, D25, D40–D47)
```
0    (false)
1    (true)
     (empty = not assessed / not applicable)
```

## Extraction Sheets

| Sheet | CSV filename pattern | Primary key | Notes |
|-------|----------------------|-------------|-------|
| E.1 Paper Details | `*_E.1_Paper_Details.csv` | SID | One row per study |
| E.2 Setting | `*_E.2_Setting.csv` | SID | One row per study |
| E.3 Data | `*_E.3_Data.csv` | SID | One row per study |
| E.4 Detection Method | `*_E.4_Detection_Method.csv` | SID + FID | Multiple rows per study |
| E.5 Subgroup | `*_E.5_Subgroup.csv` | SID | Multiple rows per study |
| E.6 Lifecycle | `*_E.6_Lifecycle.csv` | SID + FID | Multiple rows per study |
| E.7 ML Approach | `*_E.7_ML_Approach.csv` | SID | One row per study |

## Known Data Quirks

- **Trailing blank rows** — Excel exports sometimes include blank rows at the end. `show_missing.py` will flag these. The `RN` (row number) column is often empty for blank rows.
- **`Column_N` placeholder headers** — Excel sheets have sparse headers; unnamed columns become `Column_0`, `Column_1`, etc. All scripts auto-exclude these from completeness checks.
- **Multi-row-per-SID sheets** — E.4, E.5, E.6 may have multiple rows per SID. `update-row` will error if multiple rows match; use a secondary filter or edit the CSV directly.
- **Date columns** — `Date of Extraction (Last Review)` appears as a datetime string `2025-07-25 00:00:00.000000` in the CSV. Treat as a string.
- **Integer columns as strings** — PyArrow reads all columns as strings when `strings_can_be_null=False`. Numeric comparisons require casting.

## PyArrow Pipe-Delimited CSV API

```python
import pyarrow.csv as pcsv

# Read
tbl = pcsv.read_csv(
    path,
    parse_options=pcsv.ParseOptions(delimiter="|"),
    convert_options=pcsv.ConvertOptions(strings_can_be_null=False),
)

# Access data
rows = tbl.to_pydict()          # dict[col_name → list]
n = tbl.num_rows
cols = tbl.column_names

# Modify a column (immutable table — must set_column)
import pyarrow as pa
col_data = rows["Funding"][:]
col_data[5] = "Public"
col_idx = cols.index("Funding")
tbl = tbl.set_column(col_idx, "Funding", pa.array(col_data, type=pa.string()))

# Write
pcsv.write_csv(tbl, path, pcsv.WriteOptions(delimiter="|"))
```

## Author Format

```
"LastName, Initials; LastName, Initials; ..."
```
Example: `"Wang, Y; Zhang, RC; Yang, Q"`

Initials are space-separated when multiple (e.g. `BJC, JKK` in reviewer fields).
