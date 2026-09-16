<!-- Source: EXTENSION-PUBLISHING-GUIDE.md + extensions/catalog.community.json — fetched 2026-07-04. -->

spec-kit Extension — Publishing & Catalog Entry Schema
======================================================

Release & tag flow
-------------------

1. Bump ``extension.version`` in ``extension.yml`` (PEP 440, strict
   ``X.Y.Z``) to match the release you are about to cut.
2. Tag the extension repo ``vX.Y.Z`` and push the tag; create a GitHub
   release from it (release notes = changelog entries since the prior tag).
3. GitHub auto-generates the source archive at
   ``https://github.com/<owner>/<repo>/archive/refs/tags/vX.Y.Z.zip`` — this
   is the ``download_url`` consumers fetch on install; no separate build/
   publish step is required for a pure-manifest extension.
4. Compute the archive's ``sha256`` (e.g. ``curl -sL <zip-url> | sha256sum``)
   and record it on the catalog entry. Optional but recommended: catalog
   consumers that see a ``sha256`` verify it before install and refuse a
   corrupted or tampered download; omitting it (``""``) skips that check.
5. Write or update the catalog entry (schema below) and submit it via one of
   the two distribution paths.

Distribution paths
-------------------

There are exactly two ways to get an entry into a catalog — direct PRs to
the community catalog file are not accepted.

Team catalog (default)
  Add or update the entry directly in ``nq-rdl/spec-kit-extensions``'s
  ``catalog.json`` via a normal PR/commit to that repo. This catalog is
  wired with ``install_allowed: true``, so a merged entry is installable by
  anyone with the catalog configured (see ``/speckit-dev:manage`` and
  ``.specify/extension-catalogs.yml``). No external review process; the
  team catalog's own PR review is the gate.

Public community catalog (``github/spec-kit``)
  Do **not** open a PR against ``extensions/catalog.community.json``
  directly. Instead file the ``extension_submission.yml`` issue template on
  ``github/spec-kit`` with the catalog-entry fields filled in; a spec-kit
  maintainer reviews the submission (typical SLA 3–7 business days) and
  merges the entry into ``catalog.community.json`` on acceptance. The
  ``verified`` field is maintainer-set on acceptance, never author-set.

Catalog file structure
----------------------

A catalog is a single JSON object (not a bare list). Top-level keys:

- ``schema_version`` — catalog schema version, currently ``"1.0"``.
- ``updated_at`` — ISO 8601, when the catalog file was last changed.
- ``catalog_url`` — the raw URL the catalog is served from.
- ``extensions`` — an **object keyed by extension id** (NOT an array). Each
  value is one entry object (fields below).

To publish, add or replace the entry at ``extensions["<your-extension-id>"]``.
The reader looks entries up by id, so appending to an array — or using a key
that does not match the entry's ``extension.id`` — leaves the entry
undiscoverable/uninstallable.

Catalog entry schema
----------------------

Each entry (the value stored under ``extensions["<id>"]``) is one JSON object;
see ``assets/catalog-entry.json`` for a filled-in example of a single entry.
Fields:

- ``name`` — display name.
- ``id`` — matches the extension manifest's ``extension.id``
  (``^[a-z0-9-]+$``).
- ``description`` — under 200 characters.
- ``author`` — publisher/org name.
- ``version`` — PEP 440, strict ``X.Y.Z``, matching the tagged release.
- ``download_url`` — the release archive URL (see release flow above).
- ``sha256`` — optional; archive checksum, verified before install when
  present.
- ``repository`` — source repo URL.
- ``homepage`` — optional.
- ``documentation`` — optional.
- ``changelog`` — optional.
- ``license`` — SPDX identifier.
- ``category`` — free string; common values ``docs``, ``code``, ``process``,
  ``integration``, ``visibility``.
- ``effect`` — enum ``read-only`` or ``read-write``.
- ``requires`` — ``{speckit_version, tools}`` (same shape as the extension
  manifest's ``requires`` block).
- ``provides`` — ``{commands: int, hooks: int}`` counts (not the full
  command/hook detail — just how many of each the extension declares).
- ``tags`` — 2 to 10 free-form strings.
- ``verified`` — maintainer-set; never set this yourself in a submission.
- ``downloads`` — maintainer/catalog-tracked install count.
- ``stars`` — maintainer/catalog-tracked, mirrors the repo's star count.
- ``created_at`` — ISO 8601, entry creation date.
- ``updated_at`` — ISO 8601, last entry-update date.
