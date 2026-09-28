<!-- Source: https://github.github.io/spec-kit/reference/extensions.html + EXTENSION-USER-GUIDE.md — fetched 2026-07-04. CLI section re-verified 2026-09-28 against v1.0.12 src/specify_cli/extensions/command_*.py and catalog/command_add.py. -->

specify extension — CLI & Catalog Stack
=======================================

CLI surface
-----------

Flags change between releases, so do not rely on a copied table. The
installed CLI is authoritative::

    specify extension --help
    specify extension <cmd> --help        # search, add, remove, list, info,
                                          # update, enable, disable, set-priority
    specify extension catalog --help      # list, add, remove

Semantics ``--help`` does not make obvious:

- ``add <name-or-path>`` — with ``--dev`` (a boolean flag) the positional is a
  local extension directory; ``--from <url>`` installs from a URL and skips
  catalog lookup; ``--force`` overwrites an existing install.
- Priority — ``add --priority N``, ``set-priority <name> <N>``, and
  ``catalog add --priority N`` all use *lower number = higher precedence*,
  default 10.
- ``list`` shows every installed extension, enabled or disabled. To browse
  catalogs use ``search`` (in v1.0.12 ``list --available``/``--all`` only print
  an install hint). ``list --json`` emits installed extensions (with hooks)
  for scripting.
- ``update`` with no name updates every installed extension.
- ``remove --force`` skips the confirmation prompt; ``--keep-config`` keeps
  the extension's config files.
- ``catalog add <url> --name <n>`` — the URL must be HTTPS and ``--name`` is
  required. It appends to the project ``.specify/extension-catalogs.yml``
  (``--description`` is optional). ``--install-allowed/--no-install-allowed``
  defaults to **discovery-only**: enable install only for a catalog you own
  and vet, never an unvetted public one. The built-in community catalog is
  discovery-only by design; to install something found there, vet it and use
  ``specify extension add <name> --from <url>``.

Catalog Configuration
----------------------

The catalog stack is resolved in strict precedence order, highest first:

1. ``SPECKIT_CATALOG_URL`` environment variable — an ad-hoc override catalog
   URL, useful for CI or one-off testing without touching any config file.
2. Project catalog — ``.specify/extension-catalogs.yml`` in the repo. A
   non-empty project file takes full precedence over the user-level file.
3. User catalog — ``~/.specify/extension-catalogs.yml``, shared across all
   of a developer's projects.
4. Built-in defaults — the official catalog plus the community catalog
   shipped with spec-kit itself.

Within and across these catalog sources, an extension id can appear more than
once (e.g. a team fork of a community extension). Conflicts are resolved by
each catalog entry's ``priority``: the **lower** number wins. See
``assets/extension-catalogs.yml`` for a worked example that wires a team
catalog at ``priority: 1`` ahead of the community catalog at ``priority: 3``,
with ``install_allowed: true`` only on the trusted team catalog.

Configuration
-------------

Per-extension configuration is layered, later sources overriding earlier
ones:

1. Extension defaults — values baked into the extension's own manifest
   (``extension.yml``) / config template.
2. ``<ext>-config.yml`` — project-level override, committed to the repo so
   the whole team shares it.
3. ``<ext>-config.local.yml`` — developer-local override, not committed
   (secrets, machine-specific paths).
4. ``SPECKIT_<EXT>_*`` environment variables — highest precedence, for CI
   and ephemeral overrides without touching any file.

Commit vs gitignore
--------------------

Commit:

- ``.specify/extensions.yml`` — the project's installed-extension state
  (what's installed, enabled, and the global hook toggle). See
  ``assets/extensions.yml`` for the minimal shape.
- ``<ext>-config.yml`` — the shared, per-extension project config for each
  installed extension.

Gitignore:

- ``.specify/extensions/.cache/`` — downloaded catalog/extension artifacts.
- ``.backup/`` — pre-update/pre-remove backups kept for rollback.
- ``*.local.yml`` — developer-local config overrides (``<ext>-config.local.yml``).
- ``.registry`` — the resolved/materialized view of the catalog stack.
