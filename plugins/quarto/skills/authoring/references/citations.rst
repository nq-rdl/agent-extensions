Citations and Footnotes
=======================

Quarto uses Pandoc’s citation system with support for BibTeX, CSL
styles, and flexible citation formatting.

Citation Syntax
---------------

Basic Citations
~~~~~~~~~~~~~~~

.. code:: markdown

   According to @smith2020, the results indicate...
   The study showed significant results [@smith2020].

Variations
~~~~~~~~~~

======================= ==========================
Syntax                  Output
======================= ==========================
``@smith2020``          Smith (2020)
``[@smith2020]``        (Smith 2020)
``[-@smith2020]``       (2020) - author suppressed
``@Smith2020 [p. 10]``  Smith (2020, p. 10)
``[@smith2020, p. 10]`` (Smith 2020, p. 10)
======================= ==========================

Multiple Citations
~~~~~~~~~~~~~~~~~~

.. code:: markdown

   Several studies [@smith2020; @jones2021] found...
   [@smith2020; @jones2021; @williams2022]

Citation with Locators
~~~~~~~~~~~~~~~~~~~~~~

.. code:: markdown

   @smith2020 [p. 33]
   @smith2020 [chap. 2]
   [@smith2020, pp. 10-15]
   [@smith2020, fig. 3]

Common locators: ``p.``, ``pp.``, ``chap.``, ``sec.``, ``fig.``,
``eq.``, ``vol.``.

In-Text vs Parenthetical
~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: markdown

   @smith2020 says... → Smith (2020) says...
   As shown by @smith2020... → As shown by Smith (2020)...
   The results [@smith2020]... → The results (Smith 2020)...

Prefix and Suffix
~~~~~~~~~~~~~~~~~

.. code:: markdown

   [see @smith2020, pp. 10-15, for discussion]
   → (see Smith 2020, pp. 10-15, for discussion)

Bibliography Configuration
--------------------------

Basic Setup
~~~~~~~~~~~

.. code:: yaml

   bibliography: references.bib

Multiple Files
~~~~~~~~~~~~~~

.. code:: yaml

   bibliography:
     - references.bib
     - additional.bib

BibTeX File Example
~~~~~~~~~~~~~~~~~~~

.. code:: bibtex

   @article{smith2020,
     author = {Smith, John},
     title = {Article Title},
     journal = {Journal Name},
     year = {2020},
     volume = {10},
     pages = {1-20}
   }

   @book{jones2021,
     author = {Jones, Sarah},
     title = {Book Title},
     publisher = {Publisher},
     year = {2021}
   }

Other Formats
~~~~~~~~~~~~~

Quarto supports:

- BibTeX (``.bib``)
- BibLaTeX (``.bib``)
- CSL JSON (``.json``)
- CSL YAML (``.yaml``)

Citation Styles (CSL)
---------------------

Specify CSL File
~~~~~~~~~~~~~~~~

.. code:: yaml

   bibliography: references.bib
   csl: apa.csl

Find CSL Files
~~~~~~~~~~~~~~

- `Zotero Style Repository <https://www.zotero.org/styles>`__
- `CSL Repository <https://github.com/citation-style-language/styles>`__

Common Styles
~~~~~~~~~~~~~

.. code:: yaml

   csl: apa.csl           # APA 7th edition
   csl: chicago-author-date.csl
   csl: ieee.csl
   csl: nature.csl
   csl: vancouver.csl

Bibliography Placement
----------------------

By default, bibliography appears at end. Control placement:

.. code:: markdown

   ## References

   ::: {#refs}
   :::

   ## Appendix

   Additional content after references.

Suppress Bibliography
~~~~~~~~~~~~~~~~~~~~~

.. code:: yaml

   suppress-bibliography: true

Footnotes
---------

Inline Footnotes
~~~~~~~~~~~~~~~~

.. code:: markdown

   This is text with a footnote.^[This is the footnote content.]

Reference Footnotes
~~~~~~~~~~~~~~~~~~~

.. code:: markdown

   This is text with a footnote.[^1]

   [^1]: This is the footnote content.

Multi-Paragraph Footnotes
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: markdown

   [^longnote]: This is a long footnote.

       It has multiple paragraphs.

       And can include code:

       ```{.r}
       x <- 1
       ```

Citation Methods
----------------

Citeproc (Default)
~~~~~~~~~~~~~~~~~~

Standard Pandoc citation processing:

.. code:: yaml

   bibliography: references.bib

BibLaTeX (PDF)
~~~~~~~~~~~~~~

.. code:: yaml

   bibliography: references.bib
   format:
     pdf:
       cite-method: biblatex

Natbib (PDF)
~~~~~~~~~~~~

.. code:: yaml

   bibliography: references.bib
   format:
     pdf:
       cite-method: natbib

Reference Section Title
-----------------------

.. code:: yaml

   reference-section-title: "References"

Or for other languages:

.. code:: yaml

   lang: de
   reference-section-title: "Literaturverzeichnis"

Citation Links
--------------

Control hyperlinking:

.. code:: yaml

   link-citations: true # Link in-text to bibliography
   link-bibliography: true # Link URLs in bibliography

Citation Processing Options
---------------------------

.. code:: yaml

   citeproc: true # Enable citation processing
   citation-abbreviations: abbrev.json # Journal abbreviations
   notes-after-punctuation: true

DOI and URL Handling
--------------------

.. code:: yaml

   format:
     html:
       citations:
         link-citations: true
     pdf:
       include-in-header:
         - text: |
             \usepackage{hyperref}

Footnote Location
-----------------

Control where footnotes appear:

.. code:: yaml

   reference-location: document   # End of document
   reference-location: section    # End of section
   reference-location: block      # End of block
   reference-location: margin     # In margin (if supported)

Citation Hover (HTML)
---------------------

Enable hover previews:

.. code:: yaml

   format:
     html:
       citation-hover: true

Author-Date vs Numeric
----------------------

Controlled by CSL style:

.. code:: yaml

   # Author-date style
   csl: apa.csl

   # Numeric style
   csl: ieee.csl

Citing Software
---------------

.. code:: bibtex

   @software{tidyverse,
     author = {Wickham, Hadley},
     title = {tidyverse: Easily Install and Load the 'Tidyverse'},
     year = {2023},
     url = {https://CRAN.R-project.org/package=tidyverse}
   }

Or use ``@Manual`` for R packages.

Resources
---------

- `Quarto
  Citations <https://quarto.org/docs/authoring/citations.html>`__
- `Pandoc Citations <https://pandoc.org/MANUAL.html#citations>`__
- `CSL Styles <https://citationstyles.org/>`__
