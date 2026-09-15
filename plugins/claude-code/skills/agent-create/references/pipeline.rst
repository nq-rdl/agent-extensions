Packaging a delegatable skill
============================

Run from the repository root. All repository Python uses pixi.

1. Create or update ``skills/<source>/SKILL.md`` and its optional
   ``references/subagent.rst``. Check local links and read the reference as a
   worker would: it must contain the scope, inputs, procedure, and return contract.
2. Add ``{source: <source>, leaf: <action>}`` to the existing bundle's ``skills:``
   list. Do not add ``agents:``. Skip a member already present.
3. Refresh generated files:

   .. code:: bash

      pixi run bash scripts/sync-plugins.sh <bundle>
      pixi run python3 scripts/generate_manifests.py .
      pixi run python3 scripts/generate_bundles_doc.py .

4. Use ``changie new`` for one concise fragment per idea (200 characters maximum).
5. Validate the complete result:

   .. code:: bash

      pixi run python3 scripts/check_bundle_refs.py .
      pixi run python3 scripts/check_exposure.py .
      pixi run python3 scripts/check_grouping.py .
      pixi run python3 scripts/check_consistency.py .
      pixi run bash scripts/validate-plugins.sh
      pixi run bash scripts/sync-plugins.sh --check
      go -C tools/asctl build -o /tmp/asctl ./cmd/asctl/
      /tmp/asctl repo-check

Fix failures and report evidence. For a Codex-enabled bundle, also run the native
marketplace smoke test to verify installed skill and reference discovery. Do not
enable a new target until its content and dependencies are portable.
