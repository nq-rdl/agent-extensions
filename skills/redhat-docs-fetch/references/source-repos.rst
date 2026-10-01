docs.redhat.com → source repository map
=======================================

Updated 2026-10-01 from reported observations (#492): plain curl returned HTTP 200
with the full article. The 2026-08-27 spike (#262) saw Akamai 403 responses instead.
Edge/network/time can change the outcome; these are observations, not a guarantee.
``rh-fetch.sh`` tries direct HTML first, then GitHub source and indexed text.
This update was verified with offline fixtures, not a new live request.

.. list-table::
   :header-rows: 1

   * - Product slug in URL
     - Repository
     - Branch = version
     - Layout / recipe
   * - ``red_hat_ansible_automation_platform``
     - ``ansible/aap-docs``
     - ``2.1`` … ``2.6``, ``main``
     - ``downstream/assemblies/<area>/<assembly>.adoc`` and
       ``downstream/modules/<area>/<module>.adoc``. The URL page slug and every
       ``#anchor`` are file basenames whose ``[id="…"]`` equals the anchor. Assembly
       ``include::`` paths are relative to ``downstream/modules/``.
   * - ``openshift_container_platform``
     - ``openshift/openshift-docs``
     - ``enterprise-4.18`` … ``enterprise-4.22``
     - ``_topic_maps/_topic_map.yml`` (nested ``Dir``/``File`` groups) places the
       assembly at ``<dir>/…/<file>.adoc``; the page slug equals ``File``; modules live
       under ``modules/`` and ``include::`` paths are repo-root relative. Module ids are
       ``[id="<file-basename>_{context}"]`` (verified on ``enterprise-4.18``), so a rendered
       anchor such as ``nodes-pods-autoscaling-about_nodes-pods-autoscaling`` is the module file
       ``modules/nodes-pods-autoscaling-about.adoc`` plus a one-token context suffix.
   * - Satellite
     - ``theforeman/foreman-documentation``
     - ``master`` + release branches
     - ``guides/doc-<Title>/``; Satellite is a build context (``make BUILD=satellite html``).
       Not yet wired into ``rh-fetch.sh`` — search it with ``gh``.
   * - ``red_hat_enterprise_linux``
     - **none public** (GitHub search: 0 hits; the ``redhat-documentation`` org holds
       style guides and tooling only)
     - —
     - No public source. Direct HTML is tried first; indexed ``docs-text:<url>``
       (experimental, authenticated) is the fallback, or use a browser.

How ``rh-fetch.sh`` resolves a URL
----------------------------------

1. Parse ``/<lang>/documentation/<product>/<ver>/<html|html-single>/<book>/<page>[#anchor]``.
2. GET the page without credentials via curl/wget. Accept only HTTP 200 HTML with a
   non-empty article and no ``edgesuite`` / ``Access Denied`` markers. Emit article
   text, preserving preformatted whitespace and decoding common/numeric entities.
   The whole article is returned even for ``#anchor`` / ``html-single`` URLs.
3. If direct fails, map product → repo/branch (table above). Only the source fallback
   needs an anchor for ``html-single``. Fetch the branch's git tree once (``gh api`` if logged in, else ``api.github.com`` —
   unauthenticated is limited to 60 requests/hour; cached 24 h in the runtime dir).
4. Find ``<slug>.adoc`` in the tree (prefer ``downstream/`` for AAP). Anchors are resolved
   by ``resolve_anchor``: try ``<anchor>.adoc``, then strip ``_<suffix>`` from the right
   until a file matches (OpenShift's ``_{context}``). For ``/html/`` URLs a resolved anchor
   module is printed first, then the assembly; for ``html-single`` URLs (no page slug) the
   resolved file *is* the output, with a header line noting when the suffix was stripped.
5. Fetch from ``raw.githubusercontent.com`` (public, no auth). ``--includes`` inlines
   first-level ``include::`` targets, trying repo-root, file-relative, and
   ``downstream/modules/`` bases, then a basename lookup.

6. If the source route fails or has no known repository, try ``docs-text:`` automatically.
   Missing credentials need setup; missing entitlement needs subscription review, not setup.

Provenance header: ``// source: <docs URL>`` for direct HTML, or
``// source: https://github.com/<repo>/blob/<ref>/<path>`` for source fallback.
``--includes`` only affects AsciiDoc source fallback.
