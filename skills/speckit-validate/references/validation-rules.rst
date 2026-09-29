<!-- Source: src/specify_cli/extensions/__init__.py (ExtensionManifest._validate, _collect_manifest_command_names, check_compatibility), src/specify_cli/agents.py, templates/commands/*.md, and extensions/EXTENSION-DEVELOPMENT-GUIDE.md at github/spec-kit tags v0.12.0, v0.14.0, v0.15.0, v0.16.2, v1.0.0 and v1.0.12 — read 2026-09-29. The 15-fixture isolated installer oracle ran on v1.0.12 on 2026-09-29 (see installer-oracle.rst); other tags and hook dispatch remain source-reviewed only. -->

spec-kit Extension — Validation Rule Catalog
============================================

Labels: **Rejects** (``specify extension add`` stops with an error),
**Warns** (accepted with a warning or rewrite), **Local** (accepted silently;
flagged here because it breaks later or is a convention). Version notes say
where behaviour differs across the checked tags.

Top-level structure
--------------------

- **Rejects:** the file is not UTF-8 YAML or its root is not a mapping.
- **Rejects:** a missing ``schema_version``, ``extension``, ``requires`` or
  ``provides``; ``extension``/``requires``/``provides`` that are not mappings.
- **Rejects:** ``schema_version`` other than the string ``"1.0"``. Invalid:
  ``"1"``, ``1.0`` (unquoted float), ``"1.1"``.

extension block
----------------

- **Rejects:** missing ``id``, ``name``, ``version`` or ``description``; from
  v0.16.2 also a non-string value (unquoted ``version: 1.0``, ``id: 2``).
  Before v0.16.2 the same slip fails with a raw ``TypeError``.
- **Rejects:** ``id`` not matching ``^[a-z0-9-]+$`` (``My_Ext``, ``my ext``).
- **Rejects:** ``id`` equal to a core command name (``analyze``, ``checklist``,
  ``clarify``, ``constitution``, ``converge``, ``implement``, ``plan``,
  ``specify``, ``tasks``, ``taskstoissues`` at v1.0.12).
- **Rejects:** ``version`` that ``packaging.version.Version`` cannot parse
  (``v1.0`` parses; ``latest`` does not).
- **Local:** ``version`` not strict ``X.Y.Z`` (``1.0``, ``1.0.0rc1`` parse).
- **Rejects:** ``effect`` other than ``read-only`` / ``read-write``
  (``readonly``, ``read_write``).
- **Rejects:** ``category`` present but empty or not a string. Values are free
  text; common ones are ``docs``, ``code``, ``process``, ``integration``,
  ``visibility``.

requires block
--------------

- **Rejects:** missing ``speckit_version``; from v0.16.2 also a non-string or
  empty value.
- **Rejects** (``CompatibilityError`` at install): a string that is not a
  version specifier, or a specifier the installed CLI does not satisfy.
- ``tools`` (optional list of ``{name, version, required}``) is not otherwise
  constrained.

provides block
---------------

- **Rejects:** nothing provided. Accepted providers by version: commands or
  hooks (v0.12–v0.14); plus top-level ``events`` (v0.15); plus
  ``provides.templates`` / ``provides.scripts`` (present at v0.16.2 and later).
- **Rejects:** ``commands``, ``templates`` or ``scripts`` that are not lists; a
  command entry that is not a mapping or lacks ``name`` or ``file``.
- **Rejects:** a command ``file`` that is absolute or contains ``..``.
- Command names must be ``speckit.<id>.<cmd>`` with ``<id>`` equal to
  ``extension.id``:

  - **Warns:** ``speckit.<cmd>`` and ``<id>.<cmd>`` are renamed to
    ``speckit.<id>.<cmd>`` with a warning (hook references to the old name are
    rewritten too).
  - **Rejects:** any other shape, or ``speckit.<other-id>.<cmd>``.

- **Rejects:** duplicate command or alias names; ``aliases`` not a list of
  strings, or an alias that is not a safe relative name (``../evil``). Aliases
  are otherwise free-form.
- **Local:** the command ``file`` does not exist — registration skips it
  silently, so the command never appears.
- **Local:** the command file has no ``description`` frontmatter — registration
  uses an empty description. ``tools`` and ``scripts.sh`` / ``scripts.ps`` are
  optional.
- ``templates`` / ``scripts`` entries (v0.16.2+): **Rejects** a non-mapping, a
  missing ``name``/``file``, a name not matching ``^[a-z0-9-]+$``, a duplicate
  name, an unsafe ``file``, a ``strategy`` key, or script ``runtimes`` outside
  ``bash``/``powershell``/``python``.
- **Local:** a ``provides.config[]`` entry whose ``template`` file is missing —
  it is skipped at install.

hooks (optional)
----------------

- **Rejects:** ``hooks`` that is not a mapping; an event whose value is an empty
  list, or whose entries are not mappings; an entry without a non-empty
  ``command``; ``priority`` that is not an int (``true`` counts as not an int)
  or is below 1. Default priority is 10.
- **Local:** an event name outside the core set. Upstream accepts any key, but
  only core events are dispatched, so an unknown one never fires. The core set
  at v0.12.0–v1.0.12 is ``before_``/``after_`` × ``specify``, ``plan``,
  ``tasks``, ``implement``, ``analyze``, ``checklist``, ``clarify``,
  ``constitution``, ``taskstoissues`` (the 18 in the development guide) **plus**
  ``converge``, whose core command template reads ``hooks.before_converge`` and
  ``hooks.after_converge``.
- **Local:** a hook ``command`` that names no command the extension provides.
- ``condition`` is evaluated when the hook would run (``config.<key> is set``,
  ``config.<key> == 'v'`` / ``!=``, ``env.<VAR> is set`` / ``==``). It is not
  validated at install; a condition that cannot be evaluated means the hook
  does not run.
- ``optional``, ``prompt`` and ``description`` may accompany an entry.

Not validated
-------------

- ``tags`` and per-extension ``defaults`` are read but not validated.
