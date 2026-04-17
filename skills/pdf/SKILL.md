---
name: pdf
license: MIT
description: >-
  Use when extracting text, tables, or data from PDF files,
  especially academic papers. Also covers converting PDFs to markdown,
  batch-processing PDFs, or basic PDF creation.
compatibility: >-
  Requires Python 3.11+ (<3.14 for Docling/PyTorch), pymupdf4llm, pdfplumber,
  pdfminer-six, pandas, typer, rich, tabulate, docling
metadata:
  repo: https://github.com/nq-rdl/agent-skills
---

# PDF Data Extraction

## Overview

This skill extracts text and tables from academic PDFs using a **dual-pipeline architecture**:

```
PDF ──┬──► pymupdf4llm  ──► extracted/pymupdf/<stem>.md  ──┐
      │                                                      ├──► table-quality-checker agent ──► extracted/<stem>.md
      └──► Docling       ──► extracted/docling/<stem>.md  ──┘
```

Three extraction tools are available:

- **PyMuPDF4LLM** — fast (~0.12 s/page), clean text layout and reading order, built-in OCR.
- **Docling** — IBM AI-powered extraction with TableFormer model. Handles borderless tables, multi-level headers, and complex layouts. Slower; downloads ~1-2 GB of ML models on first run.
- **pdfplumber** — manual fallback with bounding-box control and visual debugging.

Recommended workflow:
1. `extract-dual` — run both pipelines on all PDFs
2. `check-quality` — automated heuristic comparison, flags papers needing review
3. `table-quality-checker` agent — reads both outputs, merges best-of-both per paper

## Dependencies

Install Python dependencies before first use:

```bash
bash scripts/ensure-deps.sh
```

This auto-detects your package manager (pixi, uv, mamba, conda, pip) and installs from `requirements.txt`.

Docling downloads its ML models (~1-2 GB) on first use, not at install time. They are cached in `~/.cache/docling/`.

### Python version note

Docling requires Python `>=3.11,<3.14` because PyTorch wheels are not yet available for Python 3.14+.

### Running scripts

All scripts use absolute paths for PDF files:

```bash
python scripts/extract_text.py /absolute/path/to/file.pdf
python scripts/extract_tables.py /absolute/path/to/file.pdf
python scripts/extract_all.py /absolute/path/to/input_dir/
python scripts/compare_extractors.py /absolute/path/to/file.pdf
```

**Important:** Scripts accept all paths as CLI arguments. There are no hardcoded project paths.

## Quick Reference

| Task | Tool | Command |
|------|------|---------|
| PDF → markdown | pymupdf4llm | `pymupdf4llm.to_markdown("file.pdf")` |
| PDF → page chunks | pymupdf4llm | `to_markdown("file.pdf", page_chunks=True)` |
| Extract tables (simple) | pymupdf4llm | `to_markdown("file.pdf", show_table_borders=True)` |
| Extract tables (AI) | Docling | `python scripts/extract_docling.py <file.pdf>` |
| Extract tables (complex/manual) | pdfplumber | `page.extract_tables(table_settings)` |
| Single PDF → markdown | script | `python scripts/extract_text.py <file.pdf>` |
| Single PDF → markdown (AI) | script | `python scripts/extract_docling.py <file.pdf>` |
| Tables → CSV | script | `python scripts/extract_tables.py <file.pdf>` |
| Batch extract all (pymupdf) | script | `python scripts/extract_all.py <input_dir>` |
| Batch extract both pipelines | script | `python scripts/extract_dual.py <input_dir>` |
| Quality report | script | `python scripts/check_quality.py <output_dir>` |
| Compare extractors | script | `python scripts/compare_extractors.py <file.pdf>` |
| Merge best-of-both | agent | use `table-quality-checker` agent |
| Plain text (CLI) | pdftotext | `pdftotext -layout input.pdf output.txt` |

## Script CLI Reference

### extract-pdf (extract_text.py)

```
Usage: python scripts/extract_text.py [OPTIONS] PDF_PATH

Arguments:
  PDF_PATH    Path to a PDF file

Options:
  -o, --output PATH       Output path (default: <pdf_stem>.md next to input)
  -p, --pages TEXT         Comma-separated 0-indexed pages, e.g. '0,1,5'
  -s, --strategy TEXT      Table strategy: lines_strict, lines, text [default: lines]
```

### extract-tables (extract_tables.py)

```
Usage: python scripts/extract_tables.py [OPTIONS] PDF_PATH

Arguments:
  PDF_PATH    Path to a PDF file

Options:
  -o, --output-dir PATH   Output directory (default: same as input PDF)
  -p, --pages TEXT         Comma-separated 1-indexed pages, e.g. '1,2,6'
  --vertical TEXT          Vertical strategy: lines, text, explicit [default: lines]
  --horizontal TEXT        Horizontal strategy: lines, text, explicit [default: lines]
  --snap-tolerance INT     Snap tolerance in points [default: 3]
  -d, --debug              Save annotated debug images
```

### extract-all (extract_all.py)

```
Usage: python scripts/extract_all.py [OPTIONS] INPUT_DIR

Arguments:
  INPUT_DIR   Directory containing PDF files

Options:
  -o, --output-dir PATH   Output directory (default: <input_dir>/extracted)
  -f, --force              Re-extract even if output already exists
  -s, --strategy TEXT      Table strategy: lines_strict, lines, text [default: lines]
```

### compare-extractors (compare_extractors.py)

```
Usage: python scripts/compare_extractors.py [OPTIONS] PDF_PATH

Arguments:
  PDF_PATH    Path to a PDF file

Options:
  -n, --preview INT       Number of characters to preview [default: 500]
```

### extract-docling (extract_docling.py)

```
Usage: python scripts/extract_docling.py [OPTIONS] PDF_PATH

Arguments:
  PDF_PATH    Path to a PDF file, or directory (with --batch)

Options:
  -o, --output PATH       Output path for single file, or output dir for batch
  -b, --batch             Treat PDF_PATH as a directory; extract all PDFs
  -f, --force             Re-extract even if output already exists
```

First run downloads Docling's ML models (~1-2 GB) to `~/.cache/docling/`.

### extract-dual (extract_dual.py)

```
Usage: python scripts/extract_dual.py [OPTIONS] INPUT_DIR

Arguments:
  INPUT_DIR   Directory containing PDF files

Options:
  -o, --output-dir PATH   Base output dir (default: <input_dir>/extracted)
  -f, --force             Re-extract even if outputs exist
  -s, --strategy TEXT     pymupdf4llm table strategy [default: lines]
  --skip-docling          Run only pymupdf4llm (quick first pass)
```

Outputs:
- `<output_dir>/pymupdf/<stem>.md` — pymupdf4llm version
- `<output_dir>/docling/<stem>.md` — Docling version

### check-quality (check_quality.py)

```
Usage: python scripts/check_quality.py [OPTIONS] BASE_DIR

Arguments:
  BASE_DIR    Output dir from extract-dual (must contain pymupdf/ and docling/ subdirs)

Options:
  -o, --output PATH       Save quality report CSV (default: <base_dir>/quality_report.csv)
  -a, --all               Show all papers, not just flagged ones
```

Quality scores are heuristic (higher = better):
- +10 per table detected, +2 per data row
- −20 per `Col1/Col2` placeholder header, −5 per `<br>` break, −15 per chart-as-table

## Docling — AI Table Extraction

### Basic Usage

```python
from docling.document_converter import DocumentConverter

converter = DocumentConverter()
result = converter.convert("paper.pdf")
markdown = result.document.export_to_markdown()
```

### Accessing Tables as DataFrames

```python
for table in result.document.tables:
    df = table.export_to_dataframe()
    print(df.to_markdown())
```

### Notes

- First run downloads TableFormer and layout models (~1-2 GB, cached in `~/.cache/docling/`)
- GPU speeds up extraction significantly; CPU works but is slower (~5-30 s/page)
- Handles borderless tables, multi-level headers, and rotated text better than pymupdf4llm
- May occasionally misidentify figure captions or lists as table rows

## PyMuPDF4LLM — Primary Tool

### Basic Extraction

```python
import pymupdf4llm

# Entire PDF → single markdown string
md_text = pymupdf4llm.to_markdown("paper.pdf")
```

### Page Chunks (Recommended for Academic Papers)

Returns a list of dicts, one per page. Best for per-page processing.

```python
import pymupdf4llm

chunks = pymupdf4llm.to_markdown("paper.pdf", page_chunks=True)

for chunk in chunks:
    print(f"Page {chunk['metadata']['page']}: {len(chunk['text'])} chars")
    # chunk['text']     — markdown text for this page
    # chunk['metadata'] — dict with 'file_path', 'page', 'page_count'
    # chunk['tables']   — list of tables detected on this page
    # chunk['images']   — list of images detected on this page
```

### Table Strategies

Control how tables are detected in the markdown output:

```python
# Strict line-based detection (best for well-formatted tables)
md = pymupdf4llm.to_markdown("paper.pdf", table_strategy="lines_strict")

# Standard line-based (default, good general-purpose)
md = pymupdf4llm.to_markdown("paper.pdf", table_strategy="lines")

# Text-based detection (for tables without visible borders)
md = pymupdf4llm.to_markdown("paper.pdf", table_strategy="text")
```

### Header Detection

Identify headers by font size analysis — useful for building document structure:

```python
from pymupdf4llm import IdentifyHeaders

# Auto-detect headers and include them as markdown headings
md = pymupdf4llm.to_markdown("paper.pdf", page_chunks=True)
```

### Selective Page Extraction

```python
# Extract only specific pages (0-indexed)
md = pymupdf4llm.to_markdown("paper.pdf", pages=[0, 1, 5])
```

### Write to File

```python
import pymupdf4llm
from pathlib import Path

md_text = pymupdf4llm.to_markdown("paper.pdf")
Path("output.md").write_text(md_text, encoding="utf-8")
```

## pdfplumber — Complex Table Fallback

Use pdfplumber when pymupdf4llm's table output is insufficient — typically for tables with merged cells, inconsistent borders, or complex multi-row headers.

### When to Use Instead of PyMuPDF4LLM

- Tables with merged/spanning cells
- Need precise bounding-box control
- Visual debugging of table detection
- Character-level text extraction needed

### Table Extraction

```python
import pdfplumber
import pandas as pd

with pdfplumber.open("paper.pdf") as pdf:
    for i, page in enumerate(pdf.pages):
        tables = page.extract_tables()
        for j, table in enumerate(tables):
            if table:
                df = pd.DataFrame(table[1:], columns=table[0])
                df.to_csv(f"table_p{i+1}_t{j+1}.csv", index=False)
```

### Custom Table Settings

```python
table_settings = {
    "vertical_strategy": "lines",      # "lines", "text", or "explicit"
    "horizontal_strategy": "lines",
    "snap_tolerance": 3,
    "intersection_tolerance": 15,
}

with pdfplumber.open("paper.pdf") as pdf:
    tables = pdf.pages[0].extract_tables(table_settings)
```

### Visual Debugging

Annotate a page image to see what pdfplumber detects:

```python
with pdfplumber.open("paper.pdf") as pdf:
    page = pdf.pages[0]
    img = page.to_image(resolution=150)
    img.debug_tablefinder()
    img.save("debug_tables.png")
```

### Tables to DataFrames

```python
import pdfplumber
import pandas as pd

with pdfplumber.open("paper.pdf") as pdf:
    all_tables = []
    for page in pdf.pages:
        for table in page.extract_tables():
            if table and len(table) > 1:
                df = pd.DataFrame(table[1:], columns=table[0])
                all_tables.append(df)

    if all_tables:
        combined = pd.concat(all_tables, ignore_index=True)
        combined.to_excel("all_tables.xlsx", index=False)
```

## Common Issues with Academic PDFs

| Issue | Solution |
|-------|----------|
| Multi-column layout | pymupdf4llm handles most; for stubborn cases try `pdftotext -layout` |
| Scanned/image-only PDF | pymupdf4llm has built-in OCR; ensure `pymupdf` is installed |
| Page-spanning tables | Extract pages individually, concatenate DataFrames manually |
| Equations as images | Will appear as image placeholders in markdown |
| Headers/footers in output | Use page chunk metadata to trim first/last lines |
| Garbled text encoding | Try `qpdf --replace-input file.pdf` to repair, then re-extract |

## PDF Creation (Brief)

For creating PDFs with reportlab or manipulating with qpdf, see `references/reference.rst`. Key warning:

**Never use Unicode subscript/superscript characters** (₀₁₂, ⁰¹²) in ReportLab — they render as black boxes. Use `<sub>` and `<super>` tags in Paragraph objects instead.
