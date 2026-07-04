<!-- Source: https://github.github.io/spec-kit/reference/extensions.html + EXTENSION-USER-GUIDE.md + src/specify_cli/extensions/_commands.py — fetched 2026-07-04. -->

specify extension — CLI & Catalog Stack
=======================================

CLI surface
-----------

``specify extension search [q]``
  Search all configured catalogs for extensions matching ``q`` (name,
  description, or tag substring). Flags:

  - ``--tag`` — restrict results to a tag (e.g. ``--tag jira``).
  - ``--author`` — restrict results to a publisher/author.
  - ``--verified`` — show only extensions from verified/official publishers.

``specify extension add <name>``
  Install an extension by id from the resolved catalog stack. Flags:

  - ``--dev <path>`` — install from a local directory in editable/dev mode
    instead of a catalog entry (for extension authors iterating locally).
  - ``--from <url>`` — install directly from a URL/git ref, bypassing catalog
    lookup.
  - ``--force`` — reinstall even if the extension (or a conflicting version)
    is already installed.
  - ``--priority N`` — set the extension's resolution priority at install
    time (lower ``N`` wins on conflicts; see Catalog stack below).

``specify extension remove <name>``
  Uninstall an extension. Flags:

  - ``--keep-config`` — leave the extension's ``<ext>-config.yml`` /
    ``<ext>-config.local.yml`` on disk instead of deleting them.
  - ``--force`` — remove without confirmation, even if other extensions
    declare a dependency on it.

``specify extension list``
  List installed extensions (id, version, enabled/disabled state, priority).
  Flags:

  - ``--available`` — also list extensions available in the catalog stack
    but not yet installed.
  - ``--all`` — include disabled extensions in the listing.

``specify extension info <name>``
  Print full detail for one extension: manifest metadata, schema_version,
  declared hooks/commands, install source, and current config values.

``specify extension update [name]``
  Update one named extension, or all installed extensions when ``name`` is
  omitted, to the latest version available from the catalog stack.

``specify extension enable <name>`` / ``specify extension disable <name>``
  Toggle whether an installed extension's hooks/commands are active, without
  uninstalling it. Disabled extensions are retained by ``list`` only under
  ``--all``.

``specify extension set-priority <name> <N>``
  Change an installed extension's resolution priority after install (see
  Catalog stack below for how ``N`` is used on id conflicts).

``specify extension catalog list`` / ``catalog add`` / ``catalog remove``
  Manage the catalog stack itself (as opposed to individual extensions).
  ``catalog add`` flags:

  - ``--name`` — catalog id/label used in precedence resolution and in
    ``extension-catalogs.yml``.
  - ``--priority`` — lower number wins when the same extension id appears in
    more than one catalog.
  - ``--install-allowed`` — whether extensions may be installed directly
    from this catalog (``false`` means discovery/search only, no install).

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
