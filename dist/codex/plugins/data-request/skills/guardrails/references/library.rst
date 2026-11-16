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

Check the library first
=======================

Before proposing new code, a config format, a helper or a text parser, search for an
existing route. Search the request's pinned library source and the child's own
``sql/README.md``. Name the path you searched in the proposal. A route that exists is
used. A missing route is a library gap, so file or cite it as a lift candidate.

Check these, in this order:

#. **T-SQL helpers.** The pinned library's ``mssql`` module ships date arithmetic,
   safe casts and similar helpers. Do not write a request-local copy.
#. **Code lists.** Use ``create_code_set_table`` and the child's documented code-list
   route. Reference code values are schema, so never invent a config format for them.
#. **Schema extraction.** Use ``extract_mssql_schema.py`` for column metadata before
   you read a table by hand.
#. **Coded result rows.** A multi-select or per-option answer often has its own coded
   rows. Check for them and for ``string_agg`` before you parse concatenated text with
   ``LIKE`` terms.
#. **Supplied cohorts.** Use ``SuppliedCohort``, as ``supplied-cohorts.rst`` describes.

Verify each name against the pinned tag, because names move between releases. A library
default is not overridden without a probe that shows why. A new reference constant
cites the probe or the library default that supports it.
