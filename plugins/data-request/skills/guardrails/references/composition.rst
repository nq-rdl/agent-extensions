Composition rules and a worked example
======================================

Read this with "Compose library units in requests" in the guardrails ``SKILL.md``.

Constitution rules
------------------

Confirm the applicable rules in the current ``.specify/memory/constitution.md``:

- ``nq-rdl/query-builder`` Constitution:
  core packages must not construct SQL with f-strings or string concatenation.
  Its narrow exception for commented resolver SQL that PyPika cannot express does
  not authorise raw SQL in a request pipeline.
- ``nq-rdl/data-analysis-scaffold`` Constitution:
  raw f-string SQL construction is prohibited outside template scripts.

Worked example
--------------

The ``falls_service_cohort.py`` Indigenous-status lookup in
`#325 <https://github.com/nq-rdl/agent-extensions/issues/325>`_ illustrates the change:

.. code-block:: python

   # Before: _build_indigenous_status_sql(...) hand-builds an SQL f-string.
   # After: compose verified library units (schematic; check pinned signatures).
   # resolver is a configured IEMRResolver instance.
   query = (
       CohortQuery(resolver)
       .add(EncounterIdAnchor(...))
       .add(WithIndigenousStatus(...))
   )

A query-builder issue tracked the active-current and display-resolution
enhancement behind this example. It closed for the v0.6.0 release.
A closed issue is a discovery pointer, not proof that a request's installed version has it.
