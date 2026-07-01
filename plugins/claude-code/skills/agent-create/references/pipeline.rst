The Wiring Pipeline
===================

Each command that turns ``agents/<name>/agent.md`` into a CI-green change, in order:
what it produces, and **which CI gate it satisfies** (so you understand *why* the step
exists). Commands are run from the **repo root**. These mirror CLAUDE.md's "Build,
test, lint" section — the same checks run in ``validate.yml`` and via ``lefthook``.

--------------

1. Register the agent in the bundle
-----------------------------------

Add the kebab-case ``<name>`` to the ``agents:`` list of
``registry/bundles/<bundle>.yaml`` (idempotent — skip if present).

- **Artifact:** the registry now names the agent.
- **Gate:** ``check_bundle_refs.py`` (every ``agents:`` entry resolves to
  ``agents/<name>/agent.md``) and ``validate-plugins.sh`` (bundle ↔ source cross-check).

--------------

2. Sync the plugin tree
-----------------------

.. code:: bash

   bash scripts/sync-plugins.sh <bundle>

Copies ``agents/<name>/agent.md`` → ``plugins/<bundle>/agents/<name>.md`` as a
real-file copy (installs are self-contained; see CLAUDE.md).

- **Artifact:** ``plugins/<bundle>/agents/<name>.md``.
- **Gate:** ``validate-plugins.sh`` requires the plugin copy to exist for every
  Claude-target bundle agent; ``validate-symlinks`` requires plugin-tree links resolve.

--------------

3. Regenerate manifests
-----------------------

.. code:: bash

   python3 scripts/generate_manifests.py .

Regenerates ``plugins/<bundle>/.claude-plugin/plugin.json`` and
``.claude-plugin/marketplace.json`` from the registry + ``VERSION``. **Never
hand-edit those** — they are generated. For a pure agent addition they are often
unchanged (agents are auto-discovered, not manifest-listed), but run it so any drift
is captured.

- **Artifact:** regenerated ``plugin.json`` + ``marketplace.json`` (if changed).
- **Gate:** ``generate_manifests.py --check`` fails CI on drift.

--------------

4. Consistency checks
---------------------

.. code:: bash

   python3 scripts/check_bundle_refs.py .
   python3 scripts/check_consistency.py .

- **Artifact:** none — read-only verification.
- **Gate:** ``check_bundle_refs.py`` (registry refs resolve to ``skills/`` & ``agents/``)
  and ``check_consistency.py`` (registry ↔ ``marketplace.json`` ↔ ``plugins/`` agree).
- If you also added or regrouped a **skill**, run ``python3 scripts/check_grouping.py .``
  as well.

--------------

5. Changelog fragment
---------------------

.. code:: bash

   changie new

Create an unreleased fragment describing the added agent. Adding an agent is
``kind: Added``. Name the agent in the body. If ``changie`` is not installed, write an
equivalent YAML fragment under ``.changes/unreleased/`` matching the existing files
(``kind:``, ``body:``, ``time:``).

- **Artifact:** ``.changes/unreleased/Added-*.yaml``.
- **Gate:** ``changelog-check.yml`` fails a PR with no fragment (bypass label:
  ``skip-changelog``).

--------------

6. Validate
-----------

.. code:: bash

   bash scripts/validate-plugins.sh

Validates plugin manifests, hooks, skills, ``.mcp.json`` wiring, agent symlinks, and
that **every** ``agents/<name>/agent.md`` has frontmatter ``name`` + ``description``.
Must exit 0. Fix any failure and re-run.

- **Artifact:** none — pass/fail gate.
- **Gate:** the ``validate-plugins`` job (and the agent-frontmatter check within it).

Optionally also run the wider CI set locally:

.. code:: bash

   python3 scripts/generate_manifests.py . --check
   go -C tools/asctl build -o /tmp/asctl ./cmd/asctl/ && /tmp/asctl repo-check
   python3 -m unittest discover -s tests -p 'test_*.py'

--------------

The session guard
-----------------

``assets/session-hooks.json`` holds two **session-scoped** hooks the skill installs at
the start of the run and removes at the end. They enforce the pipeline above so the
session cannot end with a half-wired agent.

- **Placeholders.** Substitute ``__AGENT_NAME__`` with the kebab-case agent name and
  ``__BUNDLE__`` with the target bundle before installing.
- **Install.** Merge the ``hooks`` object into ``.claude/settings.local.json``
  (gitignored) — **never clobber** existing hooks. Both injected entries carry the
  marker string ``rdl-agent-create-guard`` inside their command.
- **Stop hook** (``type: command``): every turn it runs the cheap checks and collects
  *all* the hints they produce — ``agents/<name>/agent.md`` exists; ``<name>`` is a member
  of the ``agents:`` list in ``registry/bundles/<bundle>.yaml`` (the YAML is **parsed and
  the list membership tested exactly**, not substring-grepped, so a name that merely
  appears elsewhere in the file can't pass); a changie fragment **word-boundary-matches**
  the agent name (so a longer name mentioned in a fragment doesn't satisfy a shorter one);
  ``sync-plugins.sh --check <bundle>`` reports no drift (catches a **stale** plugin copy,
  not just a missing one, so it can't unblock with drift the CI drift gate would later
  reject); and ``generate_bundles_doc.py . --check`` / ``generate_manifests.py . --check``
  report no generated-artifact drift (adding an agent to a bundle regenerates
  ``docs/bundles.md``). Those are all sub-second, so they run unconditionally and surface
  together. Only the one heavy gate — ``validate-plugins.sh`` — is **deferred until every
  other check is already clean**, so it never burns its 120 s timeout budget on a
  half-wired change. Any gap ⇒ ``{"decision":"block","reason":"…"}`` so the turn continues.
  It **respects the ``stop_hook_active`` cap** — when that is ``true`` it exits 0, so it can
  redirect but never infinite-loops (so a missing ``pyyaml`` at worst costs one extra cycle,
  not a loop).
- **PostToolUse hook** (matcher ``Write|Edit``, gated to ``agents/*/agent.md``): exits
  0 with a **declarative** ``additionalContext`` that states which wiring steps remain.
  The phrasing is factual, not imperative, so it is not mistaken for prompt injection.
- **Teardown.** Remove only the two entries whose command contains
  ``rdl-agent-create-guard``; leave every pre-existing hook in place.
