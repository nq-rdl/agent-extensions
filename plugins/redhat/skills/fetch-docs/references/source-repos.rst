docs.redhat.com → source repository map
=======================================

Verified 2026-08-27 (nq-rdl/agent-extensions#262). ``docs.redhat.com`` serves HTTP 403
to curl/wget/WebFetch regardless of headers (Akamai edge, ``errors.edgesuite.net``
reference); the AsciiDoc source on GitHub is the route for products that publish it.

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
       under ``modules/`` and ``include::`` paths are repo-root relative. Anchors inside
       modules carry a ``_{context}`` suffix, so an anchor is not a file name here.
   * - Satellite
     - ``theforeman/foreman-documentation``
     - ``master`` + release branches
     - ``guides/doc-<Title>/``; Satellite is a build context (``make BUILD=satellite html``).
       Not yet wired into ``rh-fetch.sh`` — search it with ``gh``.
   * - ``red_hat_enterprise_linux``
     - **none public** (GitHub search: 0 hits; the ``redhat-documentation`` org holds
       style guides and tooling only)
     - —
     - Closed. Try ``rh-fetch.sh 'docs-text:<url>'`` (experimental, authenticated) or a
       browser.

How ``rh-fetch.sh`` resolves a URL
----------------------------------

1. Parse ``/<lang>/documentation/<product>/<ver>/<html|html-single>/<book>/<page>[#anchor]``.
2. Map product → repo/branch (table above). ``html-single`` URLs need the ``#anchor``.
3. Fetch the branch's git tree once (``gh api`` if logged in, else ``api.github.com`` —
   unauthenticated is limited to 60 requests/hour; cached 24 h in the runtime dir).
4. Find ``<slug>.adoc`` in the tree (prefer ``downstream/`` for AAP). If the anchor is
   also a file, print that module first, then the assembly.
5. Fetch from ``raw.githubusercontent.com`` (public, no auth). ``--includes`` inlines
   first-level ``include::`` targets, trying repo-root, file-relative, and
   ``downstream/modules/`` bases, then a basename lookup.

Provenance header emitted: ``// source: https://github.com/<repo>/blob/<ref>/<path>``.
