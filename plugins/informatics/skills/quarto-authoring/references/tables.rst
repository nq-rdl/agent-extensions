Tables
======

Quarto supports multiple table formats including pipe tables, list
tables, and computational tables with extensive styling options.

Pipe Tables
-----------

The most common table format:

.. code:: markdown

   | Column 1 | Column 2 | Column 3 |
   | -------- | -------- | -------- |
   | Row 1    | Data     | More     |
   | Row 2    | Data     | More     |

Column Alignment
~~~~~~~~~~~~~~~~

Use colons to specify alignment:

.. code:: markdown

   | Left    | Center  |   Right |
   | :------ | :-----: | ------: |
   | Left    | Center  |   Right |
   | aligned | aligned | aligned |

- ``:---`` Left align
- ``:---:`` Center align
- ``---:`` Right align

With Caption
~~~~~~~~~~~~

.. code:: markdown

   ::: {#tbl-example}

   | Column 1 | Column 2 |
   | -------- | -------- |
   | Data     | Data     |

   Table caption.
   :::

Reference with ``@tbl-example``.

Column Widths
-------------

Using Dashes
~~~~~~~~~~~~

More dashes = wider column:

.. code:: markdown

   | Narrow | Wide Column |
   | ------ | ----------- |
   | A      | B           |

This creates approximately 33%/67% split.

Explicit Widths
~~~~~~~~~~~~~~~

.. code:: markdown

   | Column 1 | Column 2 |
   | -------- | -------- |
   | Data     | Data     |

   : Caption {tbl-colwidths="[25,75]"}

Document Level
~~~~~~~~~~~~~~

.. code:: yaml

   tbl-colwidths: [40, 60]

Or auto-fit:

.. code:: yaml

   tbl-colwidths: auto

List Tables
-----------

For complex content including multiple paragraphs, lists, and code
blocks. Quarto natively supports pandoc list table syntax.

Basic Syntax
~~~~~~~~~~~~

Use bullet lists where top-level items (``-``) are columns and nested
items are rows:

.. code:: markdown

   ::: {.list-table}

   - - Header 1
     - Row 1, Col 1
     - Row 2, Col 1
   - - Header 2
     - Row 1, Col 2
     - Row 2, Col 2

   :::

List Table Caption
~~~~~~~~~~~~~~~~~~

Add a paragraph at the start for the caption:

.. code:: markdown

   ::: {.list-table #tbl-example}

   Table caption here.

   - - Column A
     - Column B
     - Column C
   - - Data 1
     - Data 2
     - Data 3

   :::

List Table Attributes
~~~~~~~~~~~~~~~~~~~~~

+-----------------+-------------------------------+------------------------+
| Attribute       | Description                   | Example                |
+=================+===============================+========================+
| ``header-rows`` | Rows in header (default: 1)   | ``header-rows=2``      |
+-----------------+-------------------------------+------------------------+
| ``header-cols`` | Columns as headers            | ``header-cols=1``      |
+-----------------+-------------------------------+------------------------+
| ``aligns``      | Column alignment              | ``aligns="l,c,r"``     |
+-----------------+-------------------------------+------------------------+
| ``widths``      | Relative column widths        | ``widths="30,70"``     |
+-----------------+-------------------------------+------------------------+

Header Configuration
~~~~~~~~~~~~~~~~~~~~

.. code:: markdown

   ::: {.list-table header-rows=1 header-cols=1}

   - - 
     - Col Header 1
     - Col Header 2
   - - Row Header
     - Data 1
     - Data 2

   :::

Set ``header-rows=0`` for tables without headers.

Row and Column Spans
~~~~~~~~~~~~~~~~~~~~

Use empty spans with ``colspan`` or ``rowspan``:

.. code:: markdown

   ::: {.list-table}

   - - Column A
     - Column B
     - Column C
   - - []{colspan=2}Spans two columns
     - Normal
   - - Normal
     - Normal
     - Normal
   - - []{rowspan=2}Spans two rows
     - Data 1
     - Data 2
   - - Data 3
     - Data 4

   :::

List tables also support row/cell attributes (``[]{.highlight}``,
``[]{align=r}``), empty cells (lone ``-``), and any markdown content in
cells.

Computational Tables
--------------------

Tables generated from code:

R with knitr
~~~~~~~~~~~~

.. code:: markdown

   ```{r}
   #| label: tbl-summary
   #| tbl-cap: "Summary statistics."

   knitr::kable(summary_data)
   ```

R with gt
~~~~~~~~~

.. code:: markdown

   ```{r}
   #| label: tbl-styled
   #| tbl-cap: "Styled table."

   library(gt)
   gt(data) |>
     tab_header(title = "My Table")
   ```

Python with pandas
~~~~~~~~~~~~~~~~~~

.. code:: markdown

   ```{python}
   #| label: tbl-pandas
   #| tbl-cap: "Data summary."

   import pandas as pd
   df.to_markdown()
   ```

Table Options
~~~~~~~~~~~~~

==================== ================ ==============
Option               Description      Example
==================== ================ ==============
``tbl-cap``          Table caption    ``"Summary."``
``tbl-subcap``       Subcaptions      ``["A", "B"]``
``tbl-colwidths``    Column widths    ``[40, 60]``
``tbl-cap-location`` Caption position ``"top"``
==================== ================ ==============

Caption Location
----------------

.. _document-level-1:

Document Level
~~~~~~~~~~~~~~

.. code:: yaml

   tbl-cap-location: top

Per Table
~~~~~~~~~

.. code:: markdown

   ```{r}
   #| label: tbl-data
   #| tbl-cap: "Data."
   #| tbl-cap-location: bottom

   knitr::kable(data)
   ```

Options: ``top``, ``bottom``, ``margin``.

Subtables
---------

Multiple tables with shared caption:

.. code:: markdown

   ::: {#tbl-panel layout-ncol=2}

   ::: {#tbl-first}

   | A   | B   |
   | --- | --- |
   | 1   | 2   |

   First.
   :::

   ::: {#tbl-second}

   | C   | D   |
   | --- | --- |
   | 3   | 4   |

   Second.
   :::

   Combined tables.
   :::

   See @tbl-panel, including @tbl-first.

From Code
~~~~~~~~~

.. code:: markdown

   ```{r}
   #| label: tbl-multi
   #| tbl-cap: "Multiple tables."
   #| tbl-subcap:
   #|   - "Summary"
   #|   - "Details"
   #| layout-ncol: 2

   knitr::kable(summary_df)
   knitr::kable(detail_df)
   ```

Bootstrap Styling (HTML)
------------------------

Add Bootstrap classes for styling:

.. code:: markdown

   ::: {#tbl-styled .striped .hover}

   | A   | B   |
   | --- | --- |
   | 1   | 2   |

   Styled table.
   :::

Available classes:

=============== ======================
Class           Effect
=============== ======================
``.striped``    Alternating row colors
``.hover``      Highlight on hover
``.bordered``   Add borders
``.borderless`` Remove borders
``.sm``         Smaller text
``.responsive`` Horizontal scroll
=============== ======================

Combine multiple classes: ``::: {#tbl-name .striped .hover .bordered}``.
Use ``classes: plain`` in code cells to disable default striping.

Quarto also processes HTML tables with ``data-qmd`` attribute for
markdown content. Disable with ``html-table-processing: none``.

Table Layouts
-------------

Same as figures:

.. code:: markdown

   ::: {layout-ncol=2}

   | A   | B   |
   | --- | --- |
   | 1   | 2   |

   | C   | D   |
   | --- | --- |
   | 3   | 4   |

   :::

Long Tables
-----------

For tables spanning multiple pages (PDF):

.. code:: markdown

   ```{r}
   #| label: tbl-long
   #| tbl-cap: "Long table."

   knitr::kable(long_data, longtable = TRUE)
   ```

Cross-Referencing
-----------------

Tables are referenced with ``tbl-`` prefix:

.. code:: markdown

   ::: {#tbl-summary}

   | Data |
   | ---- |
   | 1    |

   Summary.
   :::

   See @tbl-summary for details.

Resources
---------

- `Quarto Tables <https://quarto.org/docs/authoring/tables.html>`__
- `Table
  Cross-References <https://quarto.org/docs/authoring/cross-references.html#tables>`__
- `Pandoc List Tables <https://github.com/pandoc-ext/list-table>`__
