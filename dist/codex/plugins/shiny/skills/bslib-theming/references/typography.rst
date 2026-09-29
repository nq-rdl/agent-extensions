Typography
==========

Font helpers for ``bs_theme(base_font =, heading_font =, code_font =)``.
Each argument accepts a single font object, a ``font_collection()``, or a
character vector of font family names. ``font_scale`` scales every font
size (for example ``1.5`` for 150%).

Table of Contents
-----------------

- `font_google() <#font-google>`__
- `Fallbacks and FOIT <#fallbacks-and-foit>`__
- `font_link() <#font-link>`__
- `font_face() <#font-face>`__
- `font_collection() <#font-collection>`__
- `Fonts in R plots <#fonts-in-r-plots>`__

font_google()
-------------

Downloads and caches Google Fonts locally (``local = TRUE`` by default).
The internet is needed only for the first download.

.. code:: r

   bs_theme(
     base_font = font_google("Roboto"),
     heading_font = font_google("Montserrat"),
     code_font = font_google("Fira Code")
   )

Variable weights: ``font_google("Crimson Pro", wght = "200..900")``.

Specific weights: ``font_google("Raleway", wght = c(300, 400, 700))``.

Fallbacks and FOIT
------------------

Recommend fallbacks to avoid a Flash of Invisible Text (FOIT) on slow
connections:

.. code:: r

   bs_theme(
     base_font = font_collection(
       font_google("Lato", local = FALSE),
       "Helvetica Neue", "Arial", "sans-serif"
     )
   )

Font pairing resource: fontpair.co

font_link()
-----------

CSS web font interface for custom font URLs:

.. code:: r

   font_link("Crimson Pro",
     href = "https://fonts.googleapis.com/css2?family=Crimson+Pro:wght@200..900")

font_face()
-----------

For locally hosted font files with full ``@font-face`` control:

.. code:: r

   font_face(
     family = "Crimson Pro",
     style = "normal",
     weight = "200 900",
     src = "url(fonts/crimson-pro.woff2) format('woff2')"
   )

font_collection()
-----------------

Combine multiple fonts with a fallback order:

.. code:: r

   font_collection(font_google("Lato"), "Helvetica Neue", "Arial", "sans-serif")

Fonts in R plots
----------------

``bs_theme()`` fonts reach server-rendered plots only through thematic,
and only when you ask for them: ``thematic_shiny(font = "auto")``. The
default ``font = NA`` leaves plot fonts unchanged. thematic can download a
Google Font for plots when the ``ragg`` or ``showtext`` package is
installed (``font_spec(install =)`` defaults to that check). See "Theming
R plots" in SKILL.md.
