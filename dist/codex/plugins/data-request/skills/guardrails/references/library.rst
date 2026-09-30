Library release discovery
=========================

There is no fixed "current baseline" version in this catalog. Discover the latest
stable release for the owning library from its authoritative tag list:

* `query-builder tags <https://github.com/nq-rdl/query-builder/tags>`_
* For the archived ``nq-rdl/query-builder-plugins`` package, query its own tags
  with authenticated ``gh api --paginate repos/nq-rdl/query-builder-plugins/tags
  --jq '.[].name'``; do not substitute core tags.

For automated discovery, use read-only ``gh api --paginate
repos/nq-rdl/query-builder/tags --jq '.[].name'`` and select the numerically
highest stable ``v?X.Y.Z`` tag (not the first API row, a branch, or a prerelease).
Use the entry's own library for archived pins; consolidation is not proof that
an archived-package unit shipped there. Missing access means unverified, not absent.

The request's effective pin remains authoritative for what it can use. Check
``framework_ref``, manifest, lock and installed revision, and inspect that tagged
implementation and tests before adapting examples. Discovery never authorises a
pin change. API minimum versions and explicitly dated historical examples in the
skills are compatibility facts, not claims about today's latest release.

Core discovery paths: ``clinical/specifications.py``, ``clinical/resolver.py``,
``clinical/query.py``, ``pypika_queries/queries.py``. Since v0.5.0, source resolvers
live in the core package at ``resolvers/iemr/resolver.py`` and
``resolvers/hbcis/resolver.py``; the separate plugins package is archived.
