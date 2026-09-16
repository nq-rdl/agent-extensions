Customer Portal (KCS) API
=========================

Endpoint
--------

``GET https://api.access.redhat.com/support/search/kcs`` (alias:
``https://access.redhat.com/hydra/rest/search/kcs``). Solr-style parameters:
``q``, ``fq`` (filter, repeatable), ``fl`` (field list), ``rows``, ``start``, ``sort``,
``facet=true&facet.field=documentKind``.

Useful filters: ``fq=documentKind:Solution`` (also ``Article``, ``Documentation``,
``Errata``, ``Cve``, ``Packages``), ``fq=id:<id>`` (fetch one document),
``fq=boostProduct:openshift``.

Solution fields: ``publishedTitle``, ``view_uri``, ``lastModifiedDate``,
``solution_environment``, ``issue``, ``solution_resolution``, ``solution_rootcause``,
``solution_diagnosticsteps``, ``abstract``, ``caseCount``. Documentation entries are
keyed by their ``docs.redhat.com`` URL (``id`` == URL) and carry ``docs_text_store`` /
``large_text_store`` (empty unauthenticated; whether they populate for an entitled
account is the experimental ``docs-text:`` route).

Gotchas (all observed 2026-08-27)
---------------------------------

* **There is no per-id endpoint.** Results advertise
  ``resource_uri: https://api.access.redhat.com/rs/solutions/<id>`` — the Strata API,
  decommissioned: HTTP 410 ``"API has been decomissioned. Please check
  https://access.redhat.com/articles/6873281"``. Replacement bases are
  ``https://api.access.redhat.com/support`` and ``/account``. Fetch a body with
  ``q=*&fq=id:<id>&fl=…`` on the search endpoint.
* **Metadata is public; bodies are entitled.** Unauthenticated (or with a bad token)
  the endpoint answers **HTTP 200** with body fields set to the literal
  ``"subscriber_only"``. Status codes do not signal authentication; the placeholder does.
* **Locale redirect.** ``access.redhat.com/solutions/<id>`` 302s to ``/ja/…`` from some
  networks regardless of ``Accept-Language``, an ``rh_locale`` cookie, or an explicit
  ``/en/`` path (edge geo logic), and the HTML body is login-gated. Treat ``view_uri`` as
  provenance only.

Authentication
--------------

Personal **offline token** ("Red Hat API token") generated once per person at
https://access.redhat.com/management/api . Exchange::

    POST https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token
    grant_type=refresh_token&client_id=rhsm-api&refresh_token=<offline token>

→ ``access_token`` valid ~15 minutes (``expires_in``), sent as
``Authorization: Bearer``. The offline token never expires while used at least once every
**30 days**; afterwards the exchange returns ``invalid_grant`` and a new one must be
generated. Source: https://access.redhat.com/articles/3626371 .

Hybrid Cloud Console **service accounts** (``client_credentials``) are the documented
replacement for basic auth on ``console.redhat.com`` APIs (Insights, Lightspeed, RHSM —
https://access.redhat.com/articles/7036194) and are org-level identities. They are not
documented for the Customer Portal content APIs and do not give per-person entitlement,
so this plugin does not implement them; if that changes, ``rh-token.sh`` is the single
place to add the grant.

Corroborating implementations of the same flow: ``openshift-eng/ai-helpers``
(``plugins/node-team/skills/node/references/support.md``) and
``redhat-cop/infra.support_assist`` (``roles/rh_token_refresh``).
