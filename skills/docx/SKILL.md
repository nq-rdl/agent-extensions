---
name: docx
license: MIT
description: >-
  Use this skill whenever the user wants to create, read, edit, or manipulate
  Word documents (.docx files). Triggers include: any mention of 'Word doc',
  'word document', '.docx', or requests to produce professional documents with
  formatting like tables of contents, headings, page numbers, or letterheads.
  Also use when extracting or reorganizing content from .docx files, inserting
  or replacing images in documents, performing find-and-replace in Word files,
  working with tracked changes or comments, or converting content into a
  polished Word document. If the user asks for a 'report', 'memo', 'letter',
  'template', or similar deliverable as a Word or .docx file, use this skill.
  Do NOT use for PDFs, spreadsheets, Google Docs, or general coding tasks
  unrelated to document generation.
compatibility: >-
  Requires Python 3.11+, defusedxml, lxml. Also requires pandoc binary on PATH
  and LibreOffice for PDF conversion / accepting tracked changes.
metadata:
  repo: https://github.com/nq-rdl/agent-skills
---

# DOCX creation, editing, and analysis

## Overview

A .docx file is a ZIP archive containing XML files.

## Dependencies

Install Python dependencies before first use:

```bash
bash scripts/ensure-deps.sh
```

This auto-detects your package manager (pixi, uv, mamba, conda, pip) and installs from `requirements.txt`.

**Additional system dependencies:**
- **pandoc** -- text extraction (`apt install pandoc` / `brew install pandoc`)
- **LibreOffice** -- PDF conversion and accepting tracked changes
- **docx** -- `npm install -g docx` (new documents)
- **Poppler** -- `pdftoppm` for images

### Running scripts

All scripts use absolute paths for document files:

```bash
python scripts/office/unpack.py /absolute/path/to/document.docx /absolute/path/to/output/
python scripts/office/pack.py /absolute/path/to/unpacked/ /absolute/path/to/output.docx
python scripts/office/validate.py /absolute/path/to/document.docx
python scripts/accept_changes.py /absolute/path/to/input.docx /absolute/path/to/output.docx
python scripts/comment.py /absolute/path/to/unpacked/
```

## Quick Reference

| Task | Approach |
|------|----------|
| Read/analyze content | `pandoc` or unpack for raw XML |
| Create new document | Use `docx-js` -- see `references/creating-documents.rst` |
| Edit existing document | Unpack, edit XML, repack -- see Editing Existing Documents below |

### Converting .doc to .docx

Legacy `.doc` files must be converted before editing:

```bash
soffice --headless --convert-to docx document.doc
```

### Reading Content

```bash
# Text extraction with tracked changes
pandoc --track-changes=all document.docx -o output.md

# Raw XML access
python scripts/office/unpack.py document.docx unpacked/
```

### Converting to Images

```bash
soffice --headless --convert-to pdf document.docx
pdftoppm -jpeg -r 150 document.pdf page
```

### Accepting Tracked Changes

To produce a clean document with all tracked changes accepted (requires LibreOffice):

```bash
python scripts/accept_changes.py input.docx output.docx
```

---

## Creating New Documents

See `references/creating-documents.rst` for the full docx-js creation guide, including setup, page sizing, styles, lists, tables, images, hyperlinks, footnotes, tab stops, multi-column layouts, TOC, headers/footers, and all critical rules.

Key points to remember:
- Install: `npm install -g docx`
- Always validate after creation: `python scripts/office/validate.py doc.docx`
- Set page size explicitly (defaults to A4, not US Letter)
- Never use `\n` -- use separate Paragraph elements
- Never use unicode bullets -- use `LevelFormat.BULLET`
- Always use `WidthType.DXA` for tables (never `PERCENTAGE`)
- Tables need dual widths: `columnWidths` on the table AND `width` on each cell

---

## Editing Existing Documents

**Follow all 3 steps in order.**

### Step 1: Unpack
```bash
python scripts/office/unpack.py document.docx unpacked/
```
Extracts XML, pretty-prints, merges adjacent runs, and converts smart quotes to XML entities (`&#x201C;` etc.) so they survive editing. Use `--merge-runs false` to skip run merging.

### Step 2: Edit XML

Edit files in `unpacked/word/`. See `references/xml-reference.rst` for tracked changes, comments, and image patterns.

**Use "Claude" as the author** for tracked changes and comments, unless the user explicitly requests use of a different name.

**Use the Edit tool directly for string replacement. Do not write Python scripts.** Scripts introduce unnecessary complexity. The Edit tool shows exactly what is being replaced.

**CRITICAL: Use smart quotes for new content.** When adding text with apostrophes or quotes, use XML entities to produce smart quotes:
```xml
<!-- Use these entities for professional typography -->
<w:t>Here&#x2019;s a quote: &#x201C;Hello&#x201D;</w:t>
```
| Entity | Character |
|--------|-----------|
| `&#x2018;` | ' (left single) |
| `&#x2019;` | ' (right single / apostrophe) |
| `&#x201C;` | " (left double) |
| `&#x201D;` | " (right double) |

**Adding comments:** Use `comment.py` to handle boilerplate across multiple XML files (text must be pre-escaped XML):
```bash
python scripts/comment.py unpacked/ 0 "Comment text with &amp; and &#x2019;"
python scripts/comment.py unpacked/ 1 "Reply text" --parent 0  # reply to comment 0
python scripts/comment.py unpacked/ 0 "Text" --author "Custom Author"  # custom author name
```
Then add markers to document.xml (see Comments in `references/xml-reference.rst`).

### Step 3: Pack
```bash
python scripts/office/pack.py unpacked/ output.docx --original document.docx
```
Validates with auto-repair, condenses XML, and creates DOCX. Use `--validate false` to skip.

**Auto-repair will fix:**
- `durableId` >= 0x7FFFFFFF (regenerates valid ID)
- Missing `xml:space="preserve"` on `<w:t>` with whitespace

**Auto-repair won't fix:**
- Malformed XML, invalid element nesting, missing relationships, schema violations

### Common Pitfalls

- **Replace entire `<w:r>` elements**: When adding tracked changes, replace the whole `<w:r>...</w:r>` block with `<w:del>...<w:ins>...` as siblings. Don't inject tracked change tags inside a run.
- **Preserve `<w:rPr>` formatting**: Copy the original run's `<w:rPr>` block into your tracked change runs to maintain bold, font size, etc.

---

## XML Reference

See `references/xml-reference.rst` for the full XML reference, including schema compliance rules, tracked change patterns (insert, delete, reject, restore), comment markers, and image embedding via XML.
