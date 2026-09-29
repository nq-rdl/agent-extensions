CRAN submission details
=======================

Detail and examples for the checklist in ``SKILL.md``. Each rule is labelled
with its source: **check** (``R CMD check --as-cran`` reports it),
**reviewer** (CRAN reviewers ask for it by email), **policy**/**WRE**/
**checklist** (the documents under Sources), or **convention**.

Contents
--------

- `Sources <#sources>`__
- `Title <#title>`__
- `Description <#description>`__
- `Function documentation and examples <#function-documentation-and-examples>`__
- `URLs and file URIs <#urls-and-file-uris>`__
- `Authors, copyright, and licence <#authors-copyright-and-licence>`__
- `Method references <#method-references>`__
- `Useful tools <#useful-tools>`__

Sources
-------

All fetched or executed on 2026-09-29:

- CRAN Repository Policy, revision 6875:
  https://cran.r-project.org/web/packages/policies.html
- Checklist for CRAN submissions:
  https://cran.r-project.org/web/packages/submission_checklist.html
- CRAN URL checks: https://cran.r-project.org/web/packages/URL_checks.html
- Writing R Extensions (R 4.5.3), "The DESCRIPTION file":
  https://cran.r-project.org/doc/manuals/r-release/R-exts.html
- Reviewer requests collected by maintainers: DavisVaughan/extrachecks
  (commit ``a37e1ee``) and ThinkR-open/prepare-for-cran (commit ``ec5bc06``).
  These report individual reviewer emails; treat them as recurring requests,
  not policy.
- Executed: ``R CMD check --as-cran`` and ``devtools::check()`` (devtools
  2.5.2) on R 4.5.3 against a fixture package with the problems below.

When a rule matters for a decision and the installed R or the current policy
may differ, recheck the source.

Title
-----

- **check**: title case (``tools::toTitleCase()``); must not start with or
  equal the package name.
- **WRE**: no markup, no continuation lines, no final period; listings may
  truncate after 65 characters; other packages and software in single quotes,
  book titles in double quotes.
- **reviewer**: remove redundant phrases such as "A Toolkit for", "Tools for",
  "for R", "in R", "with R"; an initial submission was returned with a request
  to shorten the title below 65 characters.

.. code:: r

   # BAD
   Title: A Toolkit for the Construction of Modeling Packages for R
   Title: Command Argument Parsing for R

   # GOOD
   Title: Construct Modeling Packages
   Title: Command Argument Parsing
   Title: Interface to 'Tiingo' Stock Price API

Description
-----------

- **check**: must not start with the package name, "This package", or similar;
  must start with a capital letter.
- **WRE**: a comprehensive description in one paragraph of complete sentences.
- **checklist**: be informative for new users ("if in doubt, make the
  Description longer rather than shorter"); functions as ``foo()`` without
  quotes; package, software, and API names in single quotes; citations as
  ``Author (year) <doi:10.prefix/suffix>`` and arXiv as
  ``<doi:10.48550/arXiv.ID>``; URLs as ``<https://...>``.
- **reviewer**: expand every acronym on first use; use double quotes only for
  publication titles; one-sentence Descriptions are returned for expansion.

.. code:: r

   # BAD
   Description: This package provides functions for rendering slides.
   Description: Uses 'case_when()' to process data.
   Description: Implements X-SAMPA processing.
   Description: Handles dates like "the first Monday of December".

   # GOOD
   Description: Render slides to different formats including HTML and PDF.
       Supports custom themes and progressive disclosure patterns. Integrates
       with 'reveal.js' for interactive presentations.
   Description: Uses case_when() to process data with 'dplyr'.
   Description: Implements Extended Speech Assessment Methods Phonetic
       Alphabet (X-SAMPA) processing.
   Description: Handles dates like the first Monday of December.

Function documentation and examples
-----------------------------------

None of these are reported by ``R CMD check --as-cran`` (verified); all are
recurring **reviewer** requests.

- Every exported function's Rd needs ``\value`` (``@return`` or ``@returns``
  in roxygen2), including topics marked ``@keywords internal``. Side-effect
  functions still document it:

  .. code:: r

     #' Print a message
     #' @param msg Message to print.
     #' @return No return value, called for side effects.
     #' @export
     print_msg <- function(msg) cat(msg, "\n")

- Exported functions with a meaningful result need runnable ``@examples``.
  **Policy**: examples should run in no more than a few seconds each, and never
  use more than two cores.
- Never comment out example code; reviewers write "Examples/code lines in
  examples should never be commented out. Ideally find toy examples that can
  be regularly executed and checked."
- ``\dontrun{}`` only for code that really cannot run (missing software, API
  keys). Reviewers ask to replace it with ``\donttest{}`` for slow examples.
  Wrap an example that demonstrates an error in ``try()``. Guard examples that
  need a suggested package:

  .. code:: r

     #' @examplesIf rlang::is_installed("dplyr")
     #' library(dplyr)
     #' my_data |> my_function()

  or use ``if (rlang::is_installed("dplyr")) { ... }`` inside ``@examples``.
  For credentials, use a predicate such as ``googlesheets4::sheets_has_token()``
  in ``@examplesIf``.
- Unexported functions should not have examples. A 2025 review asked to
  "omit these examples or export these functions" for an unexported function.
  Use ``@noRd`` for internal documentation that should not become an Rd file.
  Older advice to call them with ``pkg:::fun()`` in examples conflicts with
  this request; do not rely on it.

URLs and file URIs
------------------

``R CMD check --as-cran`` with remote checks (``devtools::check(remote = TRUE)``)
checks URLs in DESCRIPTION, CITATION, NEWS, README.md, Rd files, and vignettes,
as ``curl -I -L`` would.

- A permanent redirect is flagged; use the final URL. The most common case is
  ``http://`` redirecting to ``https://`` (verified: ``http://github.com/...``
  is reported as "moved to https://github.com/..."). Prefer ``https://``
  everywhere.
- ``urlchecker::url_check()`` finds these; ``urlchecker::url_update()``
  rewrites redirecting URLs to their final destination.
- Leave aspirational URLs that only resolve after acceptance (the package's
  CRAN page, CRAN badges, a pkgdown site deployed at release). Explain them in
  ``cran-comments.md`` if flagged.
- File URIs: CRAN's incoming check reports relative links in ``README.md`` to
  files that are not in the built package, for example a
  ``CODE_OF_CONDUCT.md`` listed in ``.Rbuildignore``::

     Found the following (possibly) invalid file URI:
       URI: CODE_OF_CONDUCT.md
         From: README.md

  A local run shows this only with
  ``_R_CHECK_CRAN_INCOMING_CHECK_FILE_URIS_=true`` (verified on R 4.5.3). Fix
  by linking to a full URL, removing the file from ``.Rbuildignore``, or using
  ``usethis::use_code_of_conduct()``, which writes a README section without a
  relative link.

Authors, copyright, and licence
-------------------------------

- **policy**: ownership of copyright must be clear, including from
  ``Authors@R``; where someone other than the authors holds copyright, indicate
  it with ``cph`` roles or a ``Copyright`` field (``inst/COPYRIGHTS``).
- **checklist**: give all authors, contributors, and copyright holders with
  roles; ORCID and ROR identifiers go in ``comment``.
- **reviewer**: "You also seem to be a copyright holder [cph]. Please add this
  information to the Authors@R field." Adding ``cph`` for a sole author avoids
  this round trip.

  .. code:: r

     Authors@R: person("John", "Doe", email = "john@example.org",
                       role = c("aut", "cre", "cph"))

- **convention** (Posit): packages in Posit organisations (posit-dev, rstudio,
  r-lib, tidyverse, tidymodels) or maintained from a ``@posit.co`` address add
  Posit as copyright holder and funder:

  .. code:: r

     person("Posit Software, PBC", role = c("cph", "fnd"),
            comment = c(ROR = "03wc8by49"))

- **reviewer**: a LICENSE file with ``YEAR:`` (MIT-style templates) that lags
  the submission year has prompted "Should the year in the LICENSE file be
  updated?"

Method references
-----------------

Reviewers often send this standard text:

   If there are references describing the methods in your package, please add
   these in the description field of your DESCRIPTION file in the form authors
   (year) <doi:...> authors (year, ISBN:...) or if those are not available:
   <https:...> with no space after 'doi:', 'arXiv:', 'https:' and angle
   brackets for auto-linking.

If there are none, reply saying so. A pre-emptive note in
``cran-comments.md`` can avoid the question:

.. code:: markdown

   ## Method references

   There are no published references describing the methods in this package.

Useful tools
------------

- ``devtools::check(remote = TRUE)``: runs the incoming and URL checks that
  the default ``devtools::check()`` skips.
- ``tools::toTitleCase()``: title case for ``Title``.
- ``urlchecker::url_check()`` / ``urlchecker::url_update()``: redirects and
  broken URLs.
- ``usethis::use_news_md()``, ``usethis::use_cran_comments()``,
  ``usethis::use_code_of_conduct()``, ``usethis::use_build_ignore()``,
  ``usethis::use_tidy_description()``.
- ``devtools::build_readme()``: re-render ``README.md`` from ``README.Rmd``.
