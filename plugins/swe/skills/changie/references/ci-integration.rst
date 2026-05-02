Changie CI/CD Integration
=========================

Source: https://changie.dev/integrations/ci/

Overview
--------

Changie supports CI/CD pipeline integration to validate changelog
fragments before they’re committed. This prevents issues like typos in
fragment kinds or invalid custom field values.

Current Limitations
-------------------

The validation tool does not yet check whether custom prompts meet
validation rules such as minimum length requirements.

GitHub Actions
--------------

Official Action
~~~~~~~~~~~~~~~

.. code:: yaml

   uses: miniscruff/changie-action@v2.1.0
   with:
     version: latest
     args: <changie-command>

Repository: https://github.com/miniscruff/changie-action

Fragment Validation (PR check)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Validates that unreleased fragments are well-formed YAML with valid
``kind`` values:

.. code:: yaml

   name: Validate Changelog Fragments
   on:
     pull_request:
       branches: [main]
       paths:
         - '.changes/unreleased/**'

   jobs:
     validate:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - name: Validate fragments
           uses: miniscruff/changie-action@v2.1.0
           with:
             version: latest
             args: batch major --dry-run

Automated Batch + Merge (release workflow)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Batches unreleased fragments into a versioned release file and merges
into CHANGELOG.md:

.. code:: yaml

   name: Changelog
   on:
     workflow_dispatch:
       inputs:
         version:
           description: 'Version to batch (e.g. 0.2.1) — no v prefix'
           required: true
           type: string

   jobs:
     changelog:
       runs-on: ubuntu-latest
       permissions:
         contents: write
       steps:
         - uses: actions/checkout@v4

         - name: Validate fragments
           uses: miniscruff/changie-action@v2.1.0
           with:
             version: latest
             args: batch ${{ inputs.version }} --dry-run

         - name: Batch changelog
           uses: miniscruff/changie-action@v2.1.0
           with:
             version: latest
             args: batch ${{ inputs.version }}

         - name: Merge into CHANGELOG.md
           uses: miniscruff/changie-action@v2.1.0
           with:
             version: latest
             args: merge

         - name: Commit and push
           env:
             VERSION: ${{ inputs.version }}
           run: |
             git config user.name "github-actions[bot]"
             git config user.email "github-actions[bot]@users.noreply.github.com"
             git add .changes/ CHANGELOG.md
             git commit -m "chore(release): batch changelog for v${VERSION}"
             git push

Key Points
----------

- **Do NOT use ``v`` prefix** with ``changie batch`` —
  ``changie batch 0.2.1`` creates ``.changes/0.2.1.md`` (correct), while
  ``changie batch v0.2.1`` creates ``.changes/v0.2.1.md`` (wrong, breaks
  release workflow).
- **``--dry-run``** prints to stdout without writing files — useful for
  validation in CI.
- **Fragment files are plain YAML** — they can be edited manually after
  creation, but CI validation catches structural issues.
- The action uses the ``latest`` changie binary by default; pin a
  specific version for reproducibility.
