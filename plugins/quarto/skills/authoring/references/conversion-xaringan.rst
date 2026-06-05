Converting xaringan to Quarto RevealJS
======================================

Guide for converting xaringan presentations to Quarto RevealJS format.

Overview
--------

Key differences:

1. Format: ``moon_reader`` → ``revealjs``
2. Slide separators: ``---`` → headers
3. Incremental: ``--`` → ``::: {.incremental}``
4. Speaker notes: ``???`` → ``::: {.notes}``

Quick Start
-----------

1. Rename File
~~~~~~~~~~~~~~

.. code:: bash

   mv slides.Rmd slides.qmd

2. Update YAML
~~~~~~~~~~~~~~

Xaringan
^^^^^^^^

.. code:: yaml

   output:
     xaringan::moon_reader:
       lib_dir: libs
       nature:
         highlightStyle: github

Quarto
^^^^^^

.. code:: yaml

   format:
     revealjs:
       theme: default
       highlight-style: github

3. Convert Slides
~~~~~~~~~~~~~~~~~

Replace ``---`` with headers:

.. code:: markdown

   # xaringan

   ---

   # Slide Title

   Content

   ---

   # Next Slide

   # Quarto

   ## Slide Title

   Content

   ## Next Slide

YAML Conversion
---------------

Basic Presentation
~~~~~~~~~~~~~~~~~~

.. _xaringan-1:

Xaringan
^^^^^^^^

.. code:: yaml

   title: "My Presentation"
   author: "Jane Doe"
   date: "2024-01-15"
   output:
     xaringan::moon_reader:
       css: ["default", "custom.css"]
       nature:
         ratio: "16:9"
         highlightStyle: github
         highlightLines: true
         countIncrementalSlides: false

.. _quarto-1:

Quarto
^^^^^^

.. code:: yaml

   title: "My Presentation"
   author: "Jane Doe"
   date: 2024-01-15
   format:
     revealjs:
       theme: default
       css: custom.css
       slide-number: true
       highlight-style: github
       code-line-numbers: true
       width: 1600
       height: 900

Common Options
~~~~~~~~~~~~~~

========================== =======================================
xaringan                   Quarto RevealJS
========================== =======================================
``ratio: "16:9"``          ``width: 1600`` / ``height: 900``
``highlightStyle: github`` ``highlight-style: github``
``highlightLines: true``   ``code-line-numbers: true``
``countdown``              ``chalkboard: true`` or timer extension
``autoplay: 30000``        ``auto-slide: 30000``
========================== =======================================

Slide Separators
----------------

.. _xaringan-2:

xaringan
~~~~~~~~

Uses ``---`` to separate slides:

.. code:: markdown

   # First Slide

   Content

   ---

   # Second Slide

   More content

   ---

   class: center, middle

   # Centered Slide

.. _quarto-2:

Quarto
~~~~~~

Uses headers (level 1 or 2):

.. code:: markdown

   # First Slide

   Content

   ## Second Slide

   More content

   ## Centered Slide {.center}

Or with explicit separators:

.. code:: yaml

   format:
     revealjs:
       slide-level: 2

Incremental Reveals
-------------------

.. _xaringan-3:

xaringan
~~~~~~~~

Uses ``--`` within a slide:

.. code:: markdown

   # Incremental

   - ## First point

   - ## Second point

   - Third point

.. _quarto-3:

Quarto
~~~~~~

Use incremental class:

.. code:: markdown

   ## Incremental

   ::: {.incremental}

   - First point
   - Second point
   - Third point

   :::

Or globally:

.. code:: yaml

   format:
     revealjs:
       incremental: true

Per-slide opt-out:

.. code:: markdown

   ## Non-Incremental {.nonincremental}

   - All at once
   - All at once

Speaker Notes
-------------

.. _xaringan-4:

xaringan
~~~~~~~~

Uses ``???``:

.. code:: markdown

   # Slide Title

   Content here.

   ???

   Speaker notes go here.
   They can span multiple lines.

.. _quarto-4:

Quarto
~~~~~~

Uses notes div:

.. code:: markdown

   ## Slide Title

   Content here.

   ::: {.notes}
   Speaker notes go here.
   They can span multiple lines.
   :::

Two-Column Layouts
------------------

.. _xaringan-5:

xaringan
~~~~~~~~

.. code:: markdown

   .pull-left[
   Left content
   ]

   .pull-right[
   Right content
   ]

.. _quarto-5:

Quarto
~~~~~~

.. code:: markdown

   ::: {.columns}

   ::: {.column width="50%"}
   Left content
   :::

   ::: {.column width="50%"}
   Right content
   :::

   :::

Slide Classes
-------------

.. _xaringan-6:

xaringan
~~~~~~~~

.. code:: markdown

   ---

   class: inverse, center, middle

   # Dark Slide

.. _quarto-6:

Quarto
~~~~~~

.. code:: markdown

   ## Dark Slide {.inverse .center .middle}

   Or use theme variants.

Background options:

.. code:: markdown

   ## Slide with Background {background-color="black"}

Code Highlighting
-----------------

.. _xaringan-7:

xaringan
~~~~~~~~

.. code:: markdown

   ```{r, highlight.output=c(1,3)}
   # Highlighted output
   ```

.. _quarto-7:

Quarto
~~~~~~

.. code:: markdown

   ```{r}
   #| code-line-numbers: "1,3"

   # Highlighted lines
   ```

Or in output:

.. code:: markdown

   ```{r}
   #| output-line-numbers: "1,3"
   ```

CSS Customization
-----------------

.. _xaringan-8:

xaringan
~~~~~~~~

.. code:: yaml

   output:
     xaringan::moon_reader:
       css: ["default", "my-theme.css"]

.. _quarto-8:

Quarto
~~~~~~

.. code:: yaml

   format:
     revealjs:
       theme: [default, custom.scss]
       css: styles.css

Custom SCSS
~~~~~~~~~~~

.. code:: scss

   // custom.scss
   $body-bg: #f0f0f0;
   $body-color: #333;
   $link-color: #007bff;

   .reveal h1 {
     color: navy;
   }

Fragments (Animations)
----------------------

.. _xaringan-9:

xaringan
~~~~~~~~

.. code:: markdown

   .animated.fadeIn[
   Content fades in
   ]

.. _quarto-9:

Quarto
~~~~~~

.. code:: markdown

   ::: {.fragment .fade-in}
   Content fades in
   :::
   ```

   Fragment types:

   - `.fade-in`
   - `.fade-out`
   - `.fade-up`
   - `.highlight-red`
   - `.strike`

   ## Images and Figures

   ### xaringan

   ````markdown
   ![](image.png)

   .center[
   ![](centered.png)
   ]

.. _quarto-10:

Quarto
~~~~~~

.. code:: markdown

   ![](image.png)

   ![](centered.png){fig-align="center"}

Full-Screen Background
~~~~~~~~~~~~~~~~~~~~~~

.. code:: markdown

   ## {background-image="image.jpg" background-size="cover"}

   Content overlaid on image.

Special Slides
--------------

Title Slide
~~~~~~~~~~~

Automatic in Quarto from YAML.

Section Headers
~~~~~~~~~~~~~~~

.. code:: markdown

   # Section Title {.section}

Thank You Slide
~~~~~~~~~~~~~~~

.. code:: markdown

   ## Thank You! {.center .middle}

   Questions?

Common xaringan Features
------------------------

Countdown Timer
~~~~~~~~~~~~~~~

Install extension:

.. code:: bash

   quarto add gadenbuie/countdown

Chalkboard
~~~~~~~~~~

.. code:: yaml

   format:
     revealjs:
       chalkboard: true

Self-Contained
~~~~~~~~~~~~~~

.. code:: yaml

   format:
     revealjs:
       embed-resources: true

Resources
---------

- `Quarto RevealJS <https://quarto.org/docs/presentations/revealjs/>`__
- `RevealJS
  Options <https://quarto.org/docs/reference/formats/presentations/revealjs.html>`__
- `Presentation Features <https://quarto.org/docs/presentations/>`__
