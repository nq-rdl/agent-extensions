Render the scaffold over a request repository
=============================================

Read this before you render the data-analysis scaffold with copier. Intake renders in place
over a request-template seed. Triage renders a fresh copy into a scratch directory. Both use
this one procedure. Do not copy it into another skill.

Why the answers are explicit
----------------------------

A seed holds a ``.copier-answers.yml`` from an older render. Copier reads that file as the
default for every question, even with ``--defaults``. A seed value for ``framework_ref``,
``seed_mode`` or ``project_slug`` then wins over the template default and no diagnostic says so.
Pass the three answers that matter with ``--data``, so the rendered result never depends on the
seed.

Before the render
-----------------

1. Probe the tools and report each result: ``copier --version`` (9.15 or later), ``git`` and
   ``pixi``. Name any that is missing and stop. A missing tool is a capability the session lacks.
2. Read the tags again just before you ask the analyst or the engineer: ``git ls-remote --tags
   https://github.com/nq-rdl/data-analysis-scaffold.git``. A list from an earlier turn or
   session is stale. Propose the newest ``v*`` tag, v0.5.1 or later. Never render from a branch.
3. Read the chosen tag's ``copier.yaml`` and note the default of ``framework_ref``. Use that
   value. Do not use the seed's value or a value from memory.
4. Parse ``answers.yaml`` with ``yaml.safe_load``. If it does not parse, stop. Show the analyst
   the line and column, propose a repair, and render only after the analyst confirms it. Repair
   before you compute fingerprints.
5. Show the analyst the command, the tag and the three explicit values. Ask for approval.

The command
-----------

.. code-block:: bash

   copier copy --trust --defaults --vcs-ref <tag> --data-file answers.yaml \
     --data framework_ref=<default from step 3> --data seed_mode=no \
     --data project_slug=<approval number> \
     gh:nq-rdl/data-analysis-scaffold <destination>

* Intake: the destination is ``.`` and the command adds ``--overwrite``. Commit ``answers.yaml``
  and the sidecar on a branch first, so the render is a separate, reviewable diff.
* Triage: the destination is a scratch directory outside the repository.
* Use ``copier copy``, not ``recopy`` or ``update``. A seed names a retired template that copier
  9.15 cannot render. ``copier update`` cannot move a repository to another template.
* ``--trust`` runs the template's post-generation task. Use it only with the canonical
  ``gh:nq-rdl/data-analysis-scaffold`` at a pinned release tag.

Check the result
----------------

Run ``git status`` and ``git diff`` and confirm each of these:

* ``answers.yaml`` and ``answers.intake.json`` are unchanged.
* ``.copier-answers.yml`` names the scaffold, the chosen tag and the three values that you passed.
  A seed value that came through is a failed render. Render again.
* The seed's workflow files under ``.github/workflows/`` are unchanged. Check ``release.yaml``,
  ``template-sync.yml`` and ``copier-runner.yml`` when they exist. Triage lists each file that a
  fresh render drops, as ``repositories.rst`` describes.
* The rendered ``scripts/validate_answers.py`` passes. If the rendered ``scripts/`` has no
  ``analyst_intake.py``, report that the sidecar was not validated.

After the render
----------------

* Commit the render only when the analyst asks.
* Re-lock pixi as its own named step and its own commit: ``pixi install``, then ``pixi lock``.
  Never mix the lock file with the render diff.
* ``pixi run setup`` (DVC remote and credentials) belongs to the analyst or the engineer on the
  VM. Do not run it.
