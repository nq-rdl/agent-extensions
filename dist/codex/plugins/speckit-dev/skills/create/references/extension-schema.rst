<!-- Source: https://raw.githubusercontent.com/github/spec-kit/main/extensions/EXTENSION-DEVELOPMENT-GUIDE.md and src/specify_cli/extensions/__init__.py (ExtensionManifest._validate) — fetched 2026-07-04. Canonical truth; re-check the live page for drift before authoring a manifest. -->

spec-kit extension.yml — Schema & Validation
============================================

Required top-level keys
-----------------------

``schema_version`` (== "1.0"), ``extension``, ``requires``, ``provides``.

extension
---------

Required: ``id``, ``name``, ``version``, ``description``.
Optional: ``author``, ``repository``, ``license``, ``homepage``, ``category``,
``effect``.

- ``id``      : ``^[a-z0-9-]+$``
- ``version`` : PEP 440 (``packaging.version.Version``); emit strict ``X.Y.Z``
- ``effect``  : enum ``read-only | read-write`` (enforced)
- ``category``: free string; common ``docs|code|process|integration|visibility``

requires
--------

- ``speckit_version`` (required specifier, e.g. ``">=0.12.0"``)
- ``tools`` (optional list of ``{name, version, required}``)

provides
--------

At least one command OR one hook is required.

- ``commands[].name``   : ``^speckit\.[a-z0-9-]+\.[a-z0-9-]+$``
- ``commands[].file``   : relative path (traversal-guarded)
- ``commands[].description`` (optional), ``commands[].aliases`` (free-form)
- ``config[]`` (optional): ``{name, template, description, required}``

hooks (optional)
----------------

Events (18): before_/after_ x {specify, plan, tasks, implement, analyze,
checklist, clarify, constitution, taskstoissues}. Each entry (single or list):
``command``, ``priority`` (int >= 1, default 10), ``optional``, ``prompt``,
``description``, ``condition`` (future).

Command file frontmatter
------------------------

``description`` (required), ``tools`` (optional list ``'tool/function'``),
``scripts.sh`` / ``scripts.ps`` (optional). Body placeholders: ``$ARGUMENTS``,
``{SCRIPT}`` (rewritten to ``.specify/scripts/...`` at install).

Minimal valid extension
------------------------

extension.yml::

    schema_version: "1.0"
    extension:
      id: "minimal"
      name: "Minimal Extension"
      version: "1.0.0"
      description: "Minimal example"
    requires:
      speckit_version: ">=0.12.0"
    provides:
      commands:
        - name: "speckit.minimal.hello"
          file: "commands/hello.md"

commands/hello.md::

    ---
    description: "Hello command"
    ---
    # Hello World
    echo "Hello, $ARGUMENTS!"
