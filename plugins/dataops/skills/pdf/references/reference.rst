PDF Processing — Advanced Reference
===================================

Detailed API reference and troubleshooting for when SKILL.md isn’t
enough.

PyMuPDF4LLM API
---------------

``pymupdf4llm.to_markdown()``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Full parameter reference:

.. code:: python

   import pymupdf4llm

   md = pymupdf4llm.to_markdown(
       doc,                        # str | Path — path to PDF file
       pages=None,                 # list[int] | None — 0-indexed page numbers; None = all
       page_chunks=False,          # bool — return list of dicts instead of single string
       hdr_info=None,              # IdentifyHeaders | None — custom header detection
       write_images=False,         # bool — extract images alongside markdown
       image_path="",              # str — directory to save extracted images
       image_format="png",         # str — "png" or "jpg"
       image_size_limit=0,         # int — skip images smaller than this (bytes)
       force_text=True,            # bool — force text extraction even from image-only pages
       table_strategy="lines",     # str — "lines_strict", "lines", or "text"
       show_table_borders=False,   # bool — show table borders in markdown output
       margins=(0, 0, 0, 0),      # tuple — (top, right, bottom, left) margins to ignore
   )

Page Chunk Dict Structure
~~~~~~~~~~~~~~~~~~~~~~~~~

When ``page_chunks=True``, each element in the returned list is:

.. code:: python

   {
       "metadata": {
           "file_path": "paper.pdf",
           "page": 1,          # 1-indexed page number
           "page_count": 12,   # total pages in document
       },
       "text": "# Title\n\nParagraph text...",  # markdown string
       "tables": [...],   # list of tables found on this page
       "images": [...],   # list of images found on this page
   }

Table Strategy Deep Dive
~~~~~~~~~~~~~~~~~~~~~~~~

+--------------------+---------------------------------+----------------------------+
| Strategy           | Best For                        | How It Works               |
+====================+=================================+============================+
| ``lines_strict``   | Well-formatted tables with      | Only detects tables with   |
|                    | clear borders                   | explicit drawn lines       |
+--------------------+---------------------------------+----------------------------+
| ``lines``          | Most academic tables            | Detects tables using lines |
| (default)          |                                 | + heuristics               |
+--------------------+---------------------------------+----------------------------+
| ``text``           | Borderless/whitespace-separated | Uses text alignment to     |
|                    | tables                          | infer table structure      |
+--------------------+---------------------------------+----------------------------+

Recommendation for academic papers: try ``lines`` first, fall back to
``text`` for borderless tables.

Header Detection
~~~~~~~~~~~~~~~~

.. code:: python

   from pymupdf4llm import IdentifyHeaders
   import pymupdf4llm

   # Auto-detect headers based on font size analysis
   md = pymupdf4llm.to_markdown(
       "paper.pdf",
       page_chunks=True,
   )
   # Headers are automatically detected by font size differences
   # and converted to markdown heading levels (# ## ### etc.)

Image Extraction
~~~~~~~~~~~~~~~~

.. code:: python

   md = pymupdf4llm.to_markdown(
       "paper.pdf",
       write_images=True,
       image_path="extracted_images/",
       image_format="png",
   )
   # Images are saved to extracted_images/ and referenced in the markdown

pdfplumber Detailed Reference
-----------------------------

Table Settings Reference
~~~~~~~~~~~~~~~~~~~~~~~~

All available ``table_settings`` keys:

.. code:: python

   table_settings = {
       # Detection strategies: "lines", "text", or "explicit"
       "vertical_strategy": "lines",
       "horizontal_strategy": "lines",

       # Tolerance settings (in points)
       "snap_tolerance": 3,          # snap lines within this distance
       "snap_x_tolerance": 3,        # x-axis snap tolerance (overrides snap_tolerance)
       "snap_y_tolerance": 3,        # y-axis snap tolerance (overrides snap_tolerance)
       "join_tolerance": 3,          # join line segments within this distance
       "join_x_tolerance": 3,
       "join_y_tolerance": 3,
       "edge_min_length": 3,         # minimum line length to consider
       "min_words_vertical": 3,      # min words for "text" strategy vertical lines
       "min_words_horizontal": 1,    # min words for "text" strategy horizontal lines
       "intersection_tolerance": 3,  # tolerance for line intersections
       "intersection_x_tolerance": 3,
       "intersection_y_tolerance": 3,

       # Explicit edges (for "explicit" strategy)
       "explicit_vertical_lines": [],   # list of x-coordinates
       "explicit_horizontal_lines": [], # list of y-coordinates

       # Text extraction within cells
       "text_tolerance": 3,
       "text_x_tolerance": 3,
       "text_y_tolerance": 3,
   }

Character-Level Extraction
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: python

   import pdfplumber

   with pdfplumber.open("paper.pdf") as pdf:
       page = pdf.pages[0]

       # All characters with position data
       for char in page.chars[:10]:
           print(f"'{char['text']}' font={char['fontname']} "
                 f"size={char['size']:.1f} at ({char['x0']:.1f}, {char['y0']:.1f})")

       # Filter by font size (e.g., find headings)
       headings = [c for c in page.chars if c['size'] > 14]

Bounding Box Extraction
~~~~~~~~~~~~~~~~~~~~~~~

Extract text from a specific region of a page:

.. code:: python

   with pdfplumber.open("paper.pdf") as pdf:
       page = pdf.pages[0]

       # Crop to region: (x0, y0, x1, y1) in points from top-left
       cropped = page.within_bbox((50, 100, 400, 300))
       text = cropped.extract_text()

       # Also works for tables within a region
       tables = cropped.extract_tables()

Visual Debugging
~~~~~~~~~~~~~~~~

.. code:: python

   with pdfplumber.open("paper.pdf") as pdf:
       page = pdf.pages[0]
       img = page.to_image(resolution=150)

       # Show detected table borders
       img.debug_tablefinder()
       img.save("debug_tables.png")

       # Draw custom rectangles
       img.draw_rects(page.extract_words())
       img.save("debug_words.png")

       # Draw lines found on the page
       img.draw_lines(page.lines)
       img.save("debug_lines.png")

CLI Tools
---------

pdftotext (poppler-utils)
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: bash

   # Basic extraction
   pdftotext input.pdf output.txt

   # Preserve layout (useful for multi-column papers)
   pdftotext -layout input.pdf output.txt

   # Specific pages (1-indexed)
   pdftotext -f 1 -l 5 input.pdf output.txt

   # Extract with bounding box coordinates (XML)
   pdftotext -bbox-layout input.pdf output.xml

   # Raw text (no layout heuristics)
   pdftotext -raw input.pdf output.txt

qpdf
~~~~

.. code:: bash

   # Repair corrupted PDF
   qpdf --check input.pdf
   qpdf --replace-input damaged.pdf

   # Extract specific pages
   qpdf input.pdf --pages . 1-5 -- pages1-5.pdf

   # Merge PDFs
   qpdf --empty --pages file1.pdf file2.pdf -- merged.pdf

   # Split into individual pages
   qpdf --split-pages input.pdf output_%02d.pdf

   # Decrypt password-protected PDF
   qpdf --password=secret --decrypt encrypted.pdf decrypted.pdf

   # Linearize for web streaming
   qpdf --linearize input.pdf optimized.pdf

pdftoppm (poppler-utils)
~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: bash

   # Convert PDF pages to PNG images
   pdftoppm -png -r 300 input.pdf output_prefix

   # Single page, high resolution
   pdftoppm -png -r 600 -f 1 -l 1 input.pdf page1

   # JPEG with quality setting
   pdftoppm -jpeg -jpegopt quality=85 -r 200 input.pdf output

pdfimages (poppler-utils)
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: bash

   # Extract all embedded images
   pdfimages -j input.pdf output_prefix

   # List image info without extracting
   pdfimages -list input.pdf

   # Extract in original format
   pdfimages -all input.pdf images/img

PDF Creation (Condensed)
------------------------

ReportLab Basics
~~~~~~~~~~~~~~~~

.. code:: python

   from reportlab.lib.pagesizes import letter
   from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
   from reportlab.lib.styles import getSampleStyleSheet

   doc = SimpleDocTemplate("output.pdf", pagesize=letter)
   styles = getSampleStyleSheet()
   story = [
       Paragraph("Title", styles['Title']),
       Spacer(1, 12),
       Paragraph("Body text here. " * 20, styles['Normal']),
       PageBreak(),
       Paragraph("Page 2", styles['Heading1']),
   ]
   doc.build(story)

ReportLab Tables
~~~~~~~~~~~~~~~~

.. code:: python

   from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
   from reportlab.lib import colors

   data = [
       ['Header 1', 'Header 2', 'Header 3'],
       ['Row 1', 'Data', 'Data'],
       ['Row 2', 'Data', 'Data'],
   ]

   table = Table(data)
   table.setStyle(TableStyle([
       ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
       ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
       ('GRID', (0, 0), (-1, -1), 1, colors.black),
   ]))

Subscripts and Superscripts Warning
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Never use Unicode subscript/superscript characters** (₀₁₂₃₄₅₆₇₈₉,
⁰¹²³⁴⁵⁶⁷⁸⁹) in ReportLab. Built-in fonts don’t include these glyphs —
they render as solid black boxes.

Use XML markup in Paragraph objects:

.. code:: python

   Paragraph("H<sub>2</sub>O", styles['Normal'])        # subscript
   Paragraph("x<super>2</super>", styles['Normal'])      # superscript

For canvas-drawn text, manually adjust font size and position.

Troubleshooting
---------------

Multi-Column Academic Papers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

pymupdf4llm generally handles two-column layouts. If columns merge:

1. Try ``pdftotext -layout`` as a fallback

2. Use pdfplumber’s bounding box extraction to target each column
   separately:

   .. code:: python

      left_col = page.within_bbox((0, 0, page.width/2, page.height))
      right_col = page.within_bbox((page.width/2, 0, page.width, page.height))

Page-Spanning Tables
~~~~~~~~~~~~~~~~~~~~

When a table continues across multiple pages:

.. code:: python

   import pdfplumber
   import pandas as pd

   with pdfplumber.open("paper.pdf") as pdf:
       all_rows = []
       header = None
       for page in pdf.pages[3:6]:  # pages where table spans
           tables = page.extract_tables()
           if tables:
               table = tables[0]
               if header is None:
                   header = table[0]
                   all_rows.extend(table[1:])
               else:
                   all_rows.extend(table)  # skip repeated header if present

       df = pd.DataFrame(all_rows, columns=header)

Scanned / Image-Only PDFs
~~~~~~~~~~~~~~~~~~~~~~~~~

pymupdf4llm has built-in OCR via Tesseract (if installed):

.. code:: python

   # pymupdf4llm will automatically OCR image-only pages
   # when force_text=True (default)
   md = pymupdf4llm.to_markdown("scanned_paper.pdf")

If OCR quality is poor, ensure Tesseract is installed:

.. code:: bash

   brew install tesseract  # macOS

Encoding Issues / Garbled Text
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: bash

   # Repair PDF structure first
   qpdf --replace-input problematic.pdf

   # Then re-extract
   pixi run extract-pdf -- problematic.pdf

If text is still garbled, the PDF may use custom font encodings. Try:

.. code:: python

   # pdfplumber sometimes handles these better
   with pdfplumber.open("problematic.pdf") as pdf:
       text = pdf.pages[0].extract_text()

Corrupted PDFs
~~~~~~~~~~~~~~

.. code:: bash

   # Check PDF integrity
   qpdf --check file.pdf

   # Attempt repair
   qpdf --replace-input file.pdf

   # If qpdf can't fix it, try re-saving via pymupdf
   python -c "
   import pymupdf
   doc = pymupdf.open('corrupted.pdf')
   doc.save('repaired.pdf', garbage=4, deflate=True)
   "

License Information
-------------------

- **pymupdf4llm / PyMuPDF**: AGPL-3.0 (free for open-source/academic
  use)
- **pdfplumber**: MIT License
- **pdfminer.six**: MIT License (included via markitdown)
- **reportlab**: BSD License
- **poppler-utils**: GPL-2 License
- **qpdf**: Apache License
