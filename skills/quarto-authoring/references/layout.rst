Layout
======

Quarto provides column classes for controlling content width and
placement, including margin content.

Column Classes
--------------

Available Columns
~~~~~~~~~~~~~~~~~

======================== ===============================
Class                    Description
======================== ===============================
``.column-body``         Default body width
``.column-body-outset``  Slightly wider than body
``.column-page``         Page width (narrower than full)
``.column-page-inset``   Page width with inset
``.column-screen``       Full screen width
``.column-screen-inset`` Screen width with margins
``.column-margin``       Right margin
======================== ===============================

Body Column (Default)
~~~~~~~~~~~~~~~~~~~~~

Standard content width:

.. code:: markdown

   ::: {.column-body}
   Default body-width content.
   :::

Body Outset
~~~~~~~~~~~

Slightly wider than body:

.. code:: markdown

   ::: {.column-body-outset}
   ![Wide image](wide.png)
   :::

Page Width
~~~~~~~~~~

Extends to page margins:

.. code:: markdown

   ::: {.column-page}
   ![Page-width image](panorama.png)
   :::

Screen Width
~~~~~~~~~~~~

Full browser width (no margins):

.. code:: markdown

   ::: {.column-screen}
   ![Full-width image](banner.png)
   :::

Screen Inset
~~~~~~~~~~~~

Full width with small margins:

.. code:: markdown

   ::: {.column-screen-inset}
   Content with small margins.
   :::

Shaded Screen Inset
~~~~~~~~~~~~~~~~~~~

With background shading:

.. code:: markdown

   ::: {.column-screen-inset-shaded}
   Shaded full-width content.
   :::

Directional Variants
--------------------

Each column class has left/right variants:

.. code:: markdown

   ::: {.column-body-outset-left}
   Extends left only.
   :::

   ::: {.column-page-right}
   Extends to right page margin.
   :::

   ::: {.column-screen-left}
   Full width on left side.
   :::

Margin Content
--------------

Text in Margin
~~~~~~~~~~~~~~

.. code:: markdown

   ::: {.column-margin}
   This appears in the right margin.
   :::

Figures in Margin
~~~~~~~~~~~~~~~~~

.. code:: markdown

   ```{r}
   #| column: margin
   #| fig-cap: "Margin figure."

   plot(1:10)
   ```

Or for markdown images:

.. code:: markdown

   ::: {.column-margin}
   ![Margin image](small.png)
   :::

Tables in Margin
~~~~~~~~~~~~~~~~

.. code:: markdown

   ```{r}
   #| column: margin
   #| tbl-cap: "Margin table."

   knitr::kable(small_data)
   ```

Mixed Content
~~~~~~~~~~~~~

.. code:: markdown

   Main text here.

   ::: {.column-margin}
   Margin note explaining the main content.
   :::

   More main text.
   ```

   ## Code Cell Layout Options

   Control output placement from code cells:

   ### Column Option

   ````markdown
   ```{r}
   #| column: page

   # Output spans page width
   plot(1:100)
   ```

Options: ``body``, ``body-outset``, ``page``, ``page-inset``,
``screen``, ``screen-inset``, ``margin``.

Figure Column
~~~~~~~~~~~~~

Target figure outputs specifically:

.. code:: markdown

   ```{r}
   #| fig-column: margin

   plot(1:10)
   ```

Table Column
~~~~~~~~~~~~

Target table outputs:

.. code:: markdown

   ```{r}
   #| tbl-column: page

   knitr::kable(wide_data)
   ```

Caption Location
----------------

In Margin
~~~~~~~~~

.. code:: markdown

   ```{r}
   #| fig-cap: "Figure with margin caption."
   #| cap-location: margin

   plot(1:10)
   ```

Document Default
~~~~~~~~~~~~~~~~

.. code:: yaml

   fig-cap-location: margin
   tbl-cap-location: margin

References in Margin
--------------------

Footnotes in Margin
~~~~~~~~~~~~~~~~~~~

.. code:: yaml

   reference-location: margin

Citations in Margin
~~~~~~~~~~~~~~~~~~~

.. code:: yaml

   citation-location: margin

Combined
~~~~~~~~

.. code:: yaml

   reference-location: margin
   citation-location: margin

Page Layout
-----------

Document-Wide Settings
~~~~~~~~~~~~~~~~~~~~~~

.. code:: yaml

   format:
     html:
       page-layout: article   # Default
       page-layout: full      # Full width
       page-layout: custom    # Custom layout

Grid Customization
~~~~~~~~~~~~~~~~~~

.. code:: yaml

   format:
     html:
       grid:
         sidebar-width: 300px
         body-width: 800px
         margin-width: 300px
         gutter-width: 1.5rem

Two-Column Layout
-----------------

Create side-by-side columns:

.. code:: markdown

   ::: {.columns}

   ::: {.column width="50%"}
   Left column content.
   :::

   ::: {.column width="50%"}
   Right column content.
   :::

   :::

Adjust ``width`` percentages for unequal columns (e.g.,
``30%``/``70%``).

Content Layout Divs
-------------------

Arrange any content (images, tables, text) in grid layouts.

Column Layout
~~~~~~~~~~~~~

.. code:: markdown

   ::: {layout-ncol=2}
   ![](image1.png)

   ![](image2.png)
   :::

Row Layout
~~~~~~~~~~

.. code:: markdown

   ::: {layout-nrow=2}
   Content 1.

   Content 2.
   :::

Complex Layouts
~~~~~~~~~~~~~~~

Use layout array for precise control. Values represent relative widths:

.. code:: markdown

   ::: {layout="[[1,1], [1]]"}
   First row, left.

   First row, right.

   Second row, full width.
   :::

With Spacing
~~~~~~~~~~~~

Negative values add spacing between elements:

.. code:: markdown

   ::: {layout="[[40,-20,40], [100]]"}
   Content 1.

   Content 2.

   Full width below.
   :::

Vertical Alignment
~~~~~~~~~~~~~~~~~~

.. code:: markdown

   ::: {layout-ncol=2 layout-valign="bottom"}
   Tall content.

   Short content.
   :::

Options: ``top``, ``center``, ``bottom``.

Layout Attributes
~~~~~~~~~~~~~~~~~

================= =================== ========================
Attribute         Description         Example
================= =================== ========================
``layout-ncol``   Number of columns   ``layout-ncol=3``
``layout-nrow``   Number of rows      ``layout-nrow=2``
``layout``        Custom layout array ``layout="[[1,2],[1]]"``
``layout-valign`` Vertical alignment  ``layout-valign=center``
================= =================== ========================

Tabsets
-------

Create tabbed content:

.. code:: markdown

   ::: {.panel-tabset}

   ## Tab 1

   Content for tab 1.

   ## Tab 2

   Content for tab 2.

   :::

With Groups
~~~~~~~~~~~

.. code:: markdown

   ::: {.panel-tabset group="language"}

   ## R

   ```r
   x <- 1
   ```

   ## Python

   ```python
   x = 1
   ```

   :::

Tabs with same group stay synchronized.

Asides
------

For inline margin notes:

.. code:: markdown

   Main text content.
   [This is an aside that appears in the margin.]{.aside}
   More main text.

PDF Layout
----------

PDF uses different layout system. Key options:

.. code:: yaml

   format:
     pdf:
       documentclass: article
       geometry:
         - margin=1in
       classoption:
         - twocolumn

Margin Notes in PDF
~~~~~~~~~~~~~~~~~~~

.. code:: yaml

   format:
     pdf:
       documentclass: scrartcl # KOMA-Script

KOMA classes support margin content automatically.

Resources
---------

- `Quarto Article
  Layout <https://quarto.org/docs/authoring/article-layout.html>`__
- `Page
  Layout <https://quarto.org/docs/output-formats/page-layout.html>`__
- `Figures
  Layout <https://quarto.org/docs/authoring/figures.html#figure-panels>`__
