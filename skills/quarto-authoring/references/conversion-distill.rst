Converting distill to Quarto
============================

Guide for converting distill articles and blogs to Quarto format.

Overview
--------

Key differences:

1. Format: ``distill_article`` → ``html``
2. Configuration: R YAML → Quarto YAML
3. Asides: ``<aside>`` → ``::: {.column-margin}``
4. Appendices: Heading-based

Quick Start
-----------

1. Rename File
~~~~~~~~~~~~~~

.. code:: bash

   mv article.Rmd article.qmd

2. Update YAML
~~~~~~~~~~~~~~

distill
^^^^^^^

.. code:: yaml

   title: "My Article"
   author:
     - name: "Jane Doe"
       affiliation: University
   output: distill::distill_article

Quarto
^^^^^^

.. code:: yaml

   title: "My Article"
   author:
     - name: "Jane Doe"
       affiliations:
         - University
   format: html

YAML Conversion
---------------

Basic Article
~~~~~~~~~~~~~

.. _distill-1:

distill
^^^^^^^

.. code:: yaml

   title: "Research Article"
   description: "A brief description"
   author:
     - name: "Jane Doe"
       url: https://example.com
       affiliation: University Name
       affiliation_url: https://university.edu
       orcid_id: 0000-0000-0000-0000
   date: "2024-01-15"
   output:
     distill::distill_article:
       toc: true
       toc_depth: 3

.. _quarto-1:

Quarto
^^^^^^

.. code:: yaml

   title: "Research Article"
   description: "A brief description"
   author:
     - name: "Jane Doe"
       url: https://example.com
       affiliations:
         - name: University Name
           url: https://university.edu
       orcid: 0000-0000-0000-0000
   date: 2024-01-15
   format:
     html:
       toc: true
       toc-depth: 3

Author Metadata
~~~~~~~~~~~~~~~

.. _distill-2:

distill
^^^^^^^

.. code:: yaml

   author:
     - name: "First Author"
       affiliation: Institution A
       affiliation_url: https://a.edu
     - name: "Second Author"
       affiliation: Institution B

.. _quarto-2:

Quarto
^^^^^^

.. code:: yaml

   author:
     - name: "First Author"
       affiliations:
         - name: Institution A
           url: https://a.edu
     - name: "Second Author"
       affiliations:
         - Institution B

Citation Metadata
~~~~~~~~~~~~~~~~~

.. _distill-3:

distill
^^^^^^^

.. code:: yaml

   citation_url: https://example.com/article
   bibliography: references.bib

.. _quarto-3:

Quarto
^^^^^^

.. code:: yaml

   citation:
     url: https://example.com/article
   bibliography: references.bib

Aside Content
-------------

.. _distill-4:

distill
~~~~~~~

.. code:: html

   <aside>This content appears in the margin.</aside>

Or with R Markdown:

.. code:: markdown

   ::: {.l-body-outset}
   Wide content here.
   :::

.. _quarto-4:

Quarto
~~~~~~

.. code:: markdown

   ::: {.column-margin}
   This content appears in the margin.
   :::

Or inline:

.. code:: markdown

   Main text here.
   [This appears in the margin.]{.aside}

Layout Classes
--------------

.. _distill-5:

distill
~~~~~~~

.. code:: markdown

   ::: {.l-body}
   Default body width.
   :::

   ::: {.l-body-outset}
   Slightly wider than body.
   :::

   ::: {.l-page}
   Page width.
   :::

   ::: {.l-screen}
   Full screen width.
   :::

   ::: {.l-screen-inset}
   Screen width with padding.
   :::

.. _quarto-5:

Quarto
~~~~~~

.. code:: markdown

   ::: {.column-body}
   Default body width.
   :::

   ::: {.column-body-outset}
   Slightly wider than body.
   :::

   ::: {.column-page}
   Page width.
   :::

   ::: {.column-screen}
   Full screen width.
   :::

   ::: {.column-screen-inset}
   Screen width with padding.
   :::

Layout Mapping
~~~~~~~~~~~~~~

=================== ========================
distill             Quarto
=================== ========================
``.l-body``         ``.column-body``
``.l-body-outset``  ``.column-body-outset``
``.l-page``         ``.column-page``
``.l-page-outset``  ``.column-page-outset``
``.l-screen``       ``.column-screen``
``.l-screen-inset`` ``.column-screen-inset``
``.l-gutter``       ``.column-margin``
=================== ========================

Figures
-------

.. _distill-6:

distill
~~~~~~~

.. code:: markdown

   ```{r, layout="l-body-outset", fig.cap="Caption"}
   plot(1:10)
   ```

.. _quarto-6:

Quarto
~~~~~~

.. code:: markdown

   ```{r}
   #| column: body-outset
   #| fig-cap: "Caption"

   plot(1:10)
   ```

Appendices
----------

.. _distill-7:

distill
~~~~~~~

.. code:: markdown

   ## Appendix

   ### Acknowledgments

   Thanks to...

   ### Author Contributions

   Author A did...

.. _quarto-7:

Quarto
~~~~~~

.. code:: markdown

   ## Acknowledgments {.appendix}

   Thanks to...

   ## Author Contributions {.appendix}

   Author A did...

Or use an appendix section:

.. code:: markdown

   ::: {#appendix}

   ## Additional Details

   More content here.
   :::

Code Display
------------

.. _distill-8:

distill
~~~~~~~

.. code:: yaml

   output:
     distill::distill_article:
       code_folding: true

.. _quarto-8:

Quarto
~~~~~~

.. code:: yaml

   format:
     html:
       code-fold: true
       code-tools: true

Blog Migration
--------------

distill Blog Structure
~~~~~~~~~~~~~~~~~~~~~~

.. code:: txt

   _site.yml
   _posts/
     2024-01-01-first-post/
       first-post.Rmd
     2024-01-15-second-post/
       second-post.Rmd

Quarto Blog Structure
~~~~~~~~~~~~~~~~~~~~~

.. code:: txt

   _quarto.yml
   posts/
     first-post/
       index.qmd
     second-post/
       index.qmd

Site Configuration
~~~~~~~~~~~~~~~~~~

Distill (``_site.yml``)
^^^^^^^^^^^^^^^^^^^^^^^

.. code:: yaml

   name: "My Blog"
   title: "My Blog"
   navbar:
     right:
       - text: "About"
         href: about.html

Quarto (``_quarto.yml``)
^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: yaml

   project:
     type: website

   website:
     title: "My Blog"
     navbar:
       right:
         - text: "About"
           href: about.qmd

   format:
     html:
       theme: cosmo

Blog Listing
~~~~~~~~~~~~

- ``_quarto.yml``

  .. code:: yaml

     website:
       title: "My Blog"

- ``index.qmd``

  .. code:: markdown

     ---
     title: "My Blog"
     listing:
       contents: posts
       type: default
       sort: "date desc"
     ---

Post Front Matter
-----------------

.. _distill-9:

distill
~~~~~~~

.. code:: yaml

   title: "Post Title"
   description: "Brief description"
   author:
     - name: "Author Name"
   date: 2024-01-15
   categories:
     - R
     - Data Science
   preview: preview.png
   output:
     distill::distill_article:
       self_contained: false

.. _quarto-9:

Quarto
~~~~~~

.. code:: yaml

   title: "Post Title"
   description: "Brief description"
   author: "Author Name"
   date: 2024-01-15
   categories:
     - R
     - Data Science
   image: preview.png

Creative Commons
----------------

.. _distill-10:

distill
~~~~~~~

.. code:: yaml

   creative_commons: CC BY

.. _quarto-10:

Quarto
~~~~~~

.. code:: yaml

   license: "CC BY"

Or more detailed:

.. code:: yaml

   license:
     type: CC BY
     url: https://creativecommons.org/licenses/by/4.0/

Resources
---------

- `Quarto HTML
  Documents <https://quarto.org/docs/output-formats/html-basics.html>`__
- `Quarto Websites <https://quarto.org/docs/websites/>`__
- `Article
  Layout <https://quarto.org/docs/authoring/article-layout.html>`__
