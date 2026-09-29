Husky v9 reference
==================

Verified against husky 9.1.7 (package source and
`typicode/husky docs <https://typicode.github.io/husky/>`__) on 2026-09-29.
``SKILL.md`` owns hook execution, CI installs and troubleshooting; this file
holds setup variants and migrations.

Contents: migration, package managers, monorepos, CI install script,
lint-staged, commitlint, hook arguments, disabling hooks.

Migrating to v9
---------------

From v8 (``husky install``, ``husky add``):

1. Change ``"prepare": "husky install"`` to ``"prepare": "husky"``.
   ``husky add``, ``set`` and ``uninstall`` now exit with an error;
   ``husky install`` prints a deprecation warning.
2. Remove these two lines from the top of every ``.husky/<hook>`` file.
   Husky 9 prints a warning when they run, and they will fail in v10:

   .. code:: sh

      #!/usr/bin/env sh
      . "$(dirname -- "$0")/_/husky.sh"

3. Run ``npx husky`` (or the project's install) once. ``.husky/_/`` is
   regenerated and git-ignored; do not commit it.

From v4 (``"husky": {"hooks": …}`` in ``package.json`` or ``.huskyrc``):

- Copy each hook command into ``.husky/<hook-name>``. Commands can span
  several lines. Call locally installed binaries directly (``jest``) or
  through the package manager.
- ``HUSKY_GIT_PARAMS`` is gone; use ``$1``, ``$2``:
  ``commitlint -E HUSKY_GIT_PARAMS`` becomes ``commitlint --edit "$1"``.
- ``HUSKY_SKIP_HOOKS`` and ``HUSKY_SKIP_INSTALL`` are replaced by ``HUSKY=0``.

Package managers
----------------

.. code:: sh

   npm install --save-dev husky && npx husky init
   pnpm add --save-dev husky && pnpm exec husky init
   bun add --dev husky && bunx husky init

Yarn (Berry) does not run ``prepare``. Use ``postinstall`` instead, and add
``pinst`` only for packages published to npm, so consumers do not run it:

.. code:: json

   {
     "scripts": {
       "postinstall": "husky",
       "prepack": "pinst --disable",
       "postpack": "pinst --enable"
     }
   }

Package not at the repository root
----------------------------------

Husky refuses a hooks directory containing ``..`` and must run where ``.git``
is. Change directory in ``prepare`` and back in each hook:

.. code:: json

   // frontend/package.json
   { "scripts": { "prepare": "cd .. && husky frontend/.husky" } }

.. code:: sh

   # frontend/.husky/pre-commit
   cd frontend
   npm test

Silent CI and production install
--------------------------------

``"prepare": "husky || true"`` still prints ``command not found`` when
devDependencies are absent. To stay silent, import Husky only after the check:

.. code:: js

   // .husky/install.mjs
   if (process.env.NODE_ENV === 'production' || process.env.CI === 'true') {
     process.exit(0)
   }
   const husky = (await import('husky')).default
   console.log(husky())

.. code:: json

   { "scripts": { "prepare": "node .husky/install.mjs" } }

lint-staged
-----------

.. code:: sh

   npm install --save-dev lint-staged
   echo "npx lint-staged" > .husky/pre-commit

.. code:: json

   // package.json
   {
     "lint-staged": {
       "*.{js,ts,tsx}": "eslint --fix",
       "*.{css,md}": "prettier --write"
     }
   }

lint-staged stages task changes itself; do not add ``git add`` as a task.

commitlint
----------

.. code:: sh

   npm install --save-dev @commitlint/cli @commitlint/config-conventional
   echo "export default { extends: ['@commitlint/config-conventional'] };" > commitlint.config.mjs
   echo 'npx --no -- commitlint --edit "$1"' > .husky/commit-msg

Hook arguments
--------------

- ``commit-msg``: ``$1`` is the path of the message file. Read it with
  ``head -n1 "$1"`` and test it with ``grep -E`` or ``case`` (no ``[[ =~ ]]``
  in POSIX sh).
- ``prepare-commit-msg``: ``$1`` message file, ``$2`` source, ``$3`` SHA.
- ``pre-push``: ``$1`` remote name, ``$2`` URL; stdin lines are
  ``<local ref> <local sha> <remote ref> <remote sha>``.
- ``post-checkout``: ``$1`` previous HEAD, ``$2`` new HEAD, ``$3`` is ``1``
  for a branch checkout.

Disabling hooks
---------------

+-------------------------------+------------------------------------------+
| Scope                         | Method                                   |
+===============================+==========================================+
| One command                   | ``git commit -n`` / ``--no-verify``;     |
|                               | otherwise ``HUSKY=0 git …``              |
+-------------------------------+------------------------------------------+
| Several commands              | ``export HUSKY=0`` … ``unset HUSKY``     |
+-------------------------------+------------------------------------------+
| CI or Docker                  | ``HUSKY: 0`` in the job environment      |
+-------------------------------+------------------------------------------+
| One machine or a GUI client   | ``export HUSKY=0`` in                    |
|                               | ``~/.config/husky/init.sh``              |
+-------------------------------+------------------------------------------+
