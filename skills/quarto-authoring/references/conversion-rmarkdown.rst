Converting R Markdown to Quarto
===============================

Guide for converting R Markdown (.Rmd) documents to Quarto (.qmd).

Overview
--------

Most R Markdown documents can be rendered by Quarto with minimal
changes. The main differences are:

1. YAML structure (output → format)
2. Chunk options (inline → hashpipe)
3. Option naming (dots → dashes)

Quick Start
-----------

Rename File
~~~~~~~~~~~

.. code:: bash

   mv document.Rmd document.qmd

Update YAML
~~~~~~~~~~~

R Markdown
^^^^^^^^^^

.. code:: yaml

   output: html_document

Quarto
^^^^^^

.. code:: yaml

   format: html

Update Chunk Options
~~~~~~~~~~~~~~~~~~~~

.. _r-markdown-1:

R Markdown
^^^^^^^^^^

.. code:: markdown

   ```{r, echo=TRUE, fig.cap="My figure"}
   plot(1:10)
   ```

.. _quarto-1:

Quarto
^^^^^^

.. code:: markdown

   ```{r}
   #| echo: true
   #| fig-cap: "My figure"

   plot(1:10)
   ```

Format Mapping
--------------

=========================== ============
R Markdown                  Quarto
=========================== ============
``html_document``           ``html``
``pdf_document``            ``pdf``
``word_document``           ``docx``
``github_document``         ``gfm``
``beamer_presentation``     ``beamer``
``ioslides_presentation``   ``revealjs``
``slidy_presentation``      ``revealjs``
``powerpoint_presentation`` ``pptx``
=========================== ============

YAML Conversion
---------------

Basic Document
~~~~~~~~~~~~~~

.. _r-markdown-2:

R Markdown
^^^^^^^^^^

.. code:: yaml

   title: "My Document"
   author: "Jane Doe"
   date: "2024-01-15"
   output:
     html_document:
       toc: true
       toc_float: true
       code_folding: show

.. _quarto-2:

Quarto
^^^^^^

.. code:: yaml

   title: "My Document"
   author: "Jane Doe"
   date: 2024-01-15
   format:
     html:
       toc: true
       toc-location: left
       code-fold: show

Multiple Outputs
~~~~~~~~~~~~~~~~

.. _r-markdown-3:

R Markdown
^^^^^^^^^^

.. code:: yaml

   output:
     html_document:
       toc: true
     pdf_document:
       toc: true

.. _quarto-3:

Quarto
^^^^^^

.. code:: yaml

   format:
     html:
       toc: true
     pdf:
       toc: true

Common Options
~~~~~~~~~~~~~~

========================= ==========================
R Markdown                Quarto
========================= ==========================
``toc: true``             ``toc: true``
``toc_float: true``       ``toc-location: left``
``toc_depth: 3``          ``toc-depth: 3``
``number_sections: true`` ``number-sections: true``
``code_folding: show``    ``code-fold: show``
``theme: cosmo``          ``theme: cosmo``
``highlight: tango``      ``highlight-style: tango``
``fig_width: 8``          ``fig-width: 8``
``fig_height: 6``         ``fig-height: 6``
``df_print: kable``       (use knitr::kable or gt)
========================= ==========================

Chunk Options
-------------

Syntax Change
~~~~~~~~~~~~~

Options move inside the code block with ``#|`` prefix:

.. _r-markdown-4:

R Markdown
^^^^^^^^^^

.. code:: markdown

   ```{r my-chunk, echo=FALSE, fig.cap="Caption", fig.width=8}
   plot(1:10)
   ```

.. _quarto-4:

Quarto
^^^^^^

.. code:: markdown

   ```{r}
   #| label: my-chunk
   #| echo: false
   #| fig-cap: "Caption"
   #| fig-width: 8

   plot(1:10)
   ```

Option Naming: Dots to Dashes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

============== ==========================
R Markdown     Quarto
============== ==========================
``fig.cap``    ``fig-cap``
``fig.width``  ``fig-width``
``fig.height`` ``fig-height``
``fig.align``  ``fig-align``
``fig.alt``    ``fig-alt``
``out.width``  (use ``fig-width`` or CSS)
``results``    ``output``
``message``    ``message``
``warning``    ``warning``
``include``    ``include``
============== ==========================

Results Option
~~~~~~~~~~~~~~

.. _r-markdown-5:

R Markdown
^^^^^^^^^^

.. code:: yaml

   results='asis'
   results='hide'
   results='markup'

.. _quarto-5:

Quarto
^^^^^^

.. code:: yaml

   #| output: asis
   #| output: false
   #| output: true

Setup Chunks
------------

.. _r-markdown-6:

R Markdown
~~~~~~~~~~

.. code:: markdown

   ```{r setup, include=FALSE}
   knitr::opts_chunk$set(
     echo = TRUE,
     warning = FALSE,
     message = FALSE,
     fig.width = 8,
     fig.height = 6
   )
   ```

.. _quarto-6:

Quarto
~~~~~~

Use YAML instead:

.. code:: yaml

   execute:
     echo: true
     warning: false
     message: false
   format:
     html:
       fig-width: 8
       fig-height: 6

Or keep setup chunk for R-specific options.

Inline Code
-----------

.. _r-markdown-7:

R Markdown
~~~~~~~~~~

.. code:: markdown

   The value is `r mean(x)`.

.. _quarto-7:

Quarto
~~~~~~

Same syntax works:

.. code:: markdown

   The value is `r mean(x)`.

Or with explicit language:

.. code:: markdown

   The value is `{r} mean(x)`.

Cross-References
----------------

Figures
~~~~~~~

R Markdown (requires bookdown)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: markdown

   ```{r my-fig, fig.cap="Caption"}
   plot(1:10)
   ```

   See Figure \@ref(fig:my-fig).

.. _quarto-8:

Quarto
^^^^^^

.. code:: markdown

   ```{r}
   #| label: fig-myplot
   #| fig-cap: "Caption"

   plot(1:10)
   ```

   See @fig-myplot.

Tables
~~~~~~

.. _r-markdown-requires-bookdown-1:

R Markdown (requires bookdown)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: markdown

   ```{r my-table}
   knitr::kable(mtcars[1:5,], caption = "My table")
   ```

   See Table \@ref(tab:my-table).

.. _quarto-9:

Quarto
^^^^^^

.. code:: markdown

   ```{r}
   #| label: tbl-mydata
   #| tbl-cap: "My table"

   knitr::kable(mtcars[1:5,])
   ```

   See @tbl-mydata.

Note: Quarto uses ``tbl-`` prefix (not ``tab-``).

Package Dependencies
--------------------

Quarto doesn’t require ``rmarkdown`` or ``knitr``, but ``knitr`` remains
useful for tables and chunk processing. Most R Markdown features
(``knitr::kable()``, ``knitr::include_graphics()``) work in Quarto
without changes.

Note: Quarto can render ``.Rmd`` files directly
(``quarto render document.Rmd``) using R Markdown compatibility mode,
which allows incremental migration.

Common Issues
-------------

Output Not Found
~~~~~~~~~~~~~~~~

.. code:: txt

   ERROR: Unknown format

Check format name mapping (e.g., ``html_document`` → ``html``).

Figure Not Appearing
~~~~~~~~~~~~~~~~~~~~

Ensure label starts with ``fig-`` for cross-references.

Table Cross-Reference Fails
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use ``tbl-`` prefix (not ``tab-``).

Chunk Options Ignored
~~~~~~~~~~~~~~~~~~~~~

Verify ``#|`` syntax and dashes (not dots).

Resources
---------

- `Quarto for R Markdown
  Users <https://quarto.org/docs/faq/rmarkdown.html>`__
- `Quarto vs R
  Markdown <https://quarto.org/docs/faq/rmarkdown.html#quarto-vs.-r-markdown>`__
