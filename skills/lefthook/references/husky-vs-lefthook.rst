Choosing and migrating hook managers
===================================

Verified with husky 9.1.7 and lefthook 2.1.12 on 2026-09-29.

Decision order
--------------

1. **Existing configuration wins.** ``.husky/`` → Husky,
   ``lefthook.yml`` → lefthook, ``.pre-commit-config.yaml`` → pre-commit.
   Extend it; running two managers means one silently bypasses the other
   (each owns Git's hook directory).
2. **An explicit request wins next.** If the user asks for a different tool
   than the one configured, migrate (below) rather than adding a second one.
3. **Nothing configured, nothing requested:** present the trade-offs and let
   the team choose. ``package.json`` alone does not decide it.

Trade-offs
----------

+-----------------------+-----------------------------+-----------------------------+-----------------------------+
|                       | Husky 9                     | lefthook 2                  | pre-commit                  |
+=======================+=============================+=============================+=============================+
| Runtime               | Node.js package             | single Go binary (npm, pip, | Python; builds isolated     |
|                       |                             | Homebrew, Go, … packages)   | per-hook environments       |
+-----------------------+-----------------------------+-----------------------------+-----------------------------+
| Config                | shell scripts in            | ``lefthook.yml`` jobs       | ``.pre-commit-config.yaml`` |
|                       | ``.husky/``                 |                             | with pinned hook repos      |
+-----------------------+-----------------------------+-----------------------------+-----------------------------+
| Install for the team  | ``prepare`` on npm install  | npm postinstall, or         | ``pre-commit install``      |
|                       |                             | ``lefthook install``        | per clone                   |
+-----------------------+-----------------------------+-----------------------------+-----------------------------+
| Staged-file filtering | via lint-staged             | built in (``glob``,         | built in (``files``,        |
|                       |                             | ``{staged_files}``)         | ``types``)                  |
+-----------------------+-----------------------------+-----------------------------+-----------------------------+
| Parallel jobs         | no                          | ``parallel: true``          | no                          |
+-----------------------+-----------------------------+-----------------------------+-----------------------------+
| Disable               | ``HUSKY=0``                 | ``LEFTHOOK=0``              | ``SKIP=<id>``, or           |
|                       |                             |                             | ``--no-verify``             |
+-----------------------+-----------------------------+-----------------------------+-----------------------------+

Husky to lefthook
-----------------

Husky sets ``core.hooksPath`` to ``.husky/_``; ``lefthook install`` refuses to
install while it is set.

.. code:: bash

   npm uninstall husky                  # and remove "prepare": "husky"
   git rm -r .husky                     # after porting each hook to lefthook.yml
   npm install --save-dev lefthook      # or another install method
   lefthook install --reset-hooks-path  # unsets core.hooksPath, installs hooks
   lefthook run pre-commit              # test without committing

``git config --unset-all --local core.hooksPath`` followed by
``lefthook install`` does the same. Port lint-staged tasks to jobs with
``glob``, ``{staged_files}`` and ``stage_fixed: true``:

.. code:: yaml

   pre-commit:
     jobs:
       - name: eslint
         glob: "*.{js,ts,tsx}"
         run: npx eslint --fix {staged_files}
         stage_fixed: true

lefthook to Husky
-----------------

.. code:: bash

   lefthook uninstall                   # removes lefthook's .git/hooks files
   npm uninstall lefthook && git rm lefthook.yml
   npm install --save-dev husky && npx husky init

Move each job's command into ``.husky/<hook>`` as POSIX sh (Husky runs hooks
with ``sh -e``) and use lint-staged for staged-file filtering.
