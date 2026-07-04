<!-- Source: src/specify_cli/extensions/__init__.py (ExtensionManifest._validate) + EXTENSION-DEVELOPMENT-GUIDE.md "Validation Rules" — fetched 2026-07-04. -->

spec-kit Extension — Validation Rule Catalog
============================================

Top-level structure
--------------------

- ``schema_version`` must equal ``"1.0"`` exactly (constant compare, not a
  range). Valid: ``schema_version: "1.0"``. Invalid: ``schema_version: "1"``,
  ``schema_version: 1.0`` (unquoted float), ``schema_version: "1.1"``.
- Required top-level keys: ``schema_version``, ``extension``, ``requires``,
  ``provides``. Missing any one fails validation.

extension block
----------------

- ``id``, ``name``, ``version``, ``description`` are all required.
- ``id`` must match ``^[a-z0-9-]+$``. Valid: ``my-ext``. Invalid: ``My_Ext``
  (uppercase, underscore), ``my ext`` (space).
- ``version`` must be parseable by Python ``packaging`` (PEP 440); emit strict
  ``X.Y.Z``. Valid: ``1.0.0``. Invalid: ``v1.0`` (not a bare PEP 440 version
  string), ``1.0`` (missing patch — accepted by ``packaging`` but should be
  emitted as strict ``X.Y.Z``).
- ``effect``, if present, is an **enforced enum**: ``read-only`` or
  ``read-write``. Valid: ``effect: read-only``. Invalid: ``effect: readonly``,
  ``effect: read_write``.
- ``category``, if present, is a free string (not validated); common values
  are ``docs``, ``code``, ``process``, ``integration``, ``visibility``.

requires block
--------------

- ``speckit_version`` is required and must be a valid version specifier.
  Valid: ``">=0.12.0"``. Invalid: missing the key, or a non-specifier string
  like ``"latest"``.
- ``tools`` (optional list of ``{name, version, required}``) is not otherwise
  constrained.

provides block
---------------

- **At least one command OR one hook is required.** An extension with neither
  ``provides.commands`` nor top-level ``hooks`` fails validation.
- ``commands[].name`` must match ``^speckit\.[a-z0-9-]+\.[a-z0-9-]+$`` and the
  middle segment must equal ``extension.id``. Valid (for ``id: my-ext``):
  ``speckit.my-ext.hello``. Invalid: ``speckit.hello`` (missing the id
  segment), ``speckit.other-ext.hello`` (id segment does not match
  ``extension.id``), ``my-ext.hello`` (missing the ``speckit.`` prefix).
- ``commands[].file`` must be a relative path that exists, with no directory
  traversal (no ``..``) and not absolute. Valid: ``commands/hello.md``.
  Invalid: ``../hello.md``, ``/etc/hello.md``.
- ``commands[].aliases`` is free-form and **not** pattern-enforced — still
  keep the ``speckit.<id>.*`` shape by convention, but it will not fail
  validation if broken.
- Each referenced command file's frontmatter must include ``description``
  (required); ``tools`` (optional list of ``'tool/function'`` strings) and
  ``scripts.sh`` / ``scripts.ps`` (optional) may also be present.
- ``provides.config[]``, if present, is a list of
  ``{name, template, description, required}``; each ``template`` file must
  exist.

hooks (optional)
----------------

- Each hook key should be one of the 18 documented event names: ``before_``/``after_``
  crossed with ``specify``, ``plan``, ``tasks``, ``implement``, ``analyze``,
  ``checklist``, ``clarify``, ``constitution``, ``taskstoissues`` (the
  Development Guide lists these as the valid set). Valid: ``before_plan``,
  ``after_implement``. An unrecognized key (e.g. ``before_build`` — not a known
  phase, or ``pre_plan`` — wrong prefix) is not bound to any workflow stage, so
  the hook silently never fires — flag it even though the installer may not
  reject it outright.
- Each hook entry (single object or list of objects) must have a non-empty
  ``command``. ``priority``, if present, must be an int ≥ 1 (default 10 when
  omitted). Valid: ``priority: 1``. Invalid: ``priority: 0``,
  ``priority: "high"``.
- ``optional``, ``prompt``, ``description`` may accompany a hook entry;
  ``condition`` is reserved for future use and not currently validated.

Traps and non-enforced fields
------------------------------

- ``tags`` and ``defaults`` (if present anywhere in the manifest) are read
  but **not** validated — do not rely on them for correctness.
- ``commands[].aliases`` (see above) is likewise unenforced.
