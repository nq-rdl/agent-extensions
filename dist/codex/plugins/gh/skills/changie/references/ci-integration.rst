Changie in CI
=============

Sources: `changie CI integration <https://changie.dev/integrations/ci/>`__ and
`miniscruff/changie-action <https://github.com/miniscruff/changie-action>`__
(``v3``, checked 2026-09-29 with changie 1.26.0).

Validate fragments on pull requests
-----------------------------------

A dry-run batch parses every unreleased fragment and fails on invalid YAML or
an unknown kind, without writing files:

.. code:: yaml

   name: Validate changelog fragments
   on:
     pull_request:
       paths: ['.changes/unreleased/**']

   jobs:
     validate:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v7
         - uses: miniscruff/changie-action@v3
           with:
             version: v1.26.0        # pin; the default is "latest"
             args: batch major --dry-run

It does **not** check ``body.maxLength`` or custom-prompt rules (verified with
changie 1.26.0: an over-long hand-written body passes). ``changie new``
enforces the cap only when it creates the fragment. Add a separate length
check if hand-edited fragments are allowed.

Releases
--------

Follow the project's release process. Upstream's example batches with
``batch auto``, runs ``changie merge`` and opens a release pull request; see the
``changie-action`` README. Pass versions without a ``v`` unless the project's
existing ``.changes/<version>.md`` files use one: ``changie batch v0.2.1``
writes ``.changes/v0.2.1.md``.
