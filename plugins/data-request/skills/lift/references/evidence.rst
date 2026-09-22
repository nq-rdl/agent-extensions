Library issue evidence block
============================

Use these headings in every newly filed issue. Keep one reusable change per issue;
link related candidates rather than expanding a resolver fix into core redesign.
Do not include patient rows, identifiers or credentials.

* **Enquiry and pin** — enquiry reference, pipeline path/revision, owning library,
  actual ``framework_ref``/lock version checked, and ledger id.
* **Need and classification** — required composition and new-capability or
  existing-unit-gap, including output grain.
* **Pinned capability inspected** — unit, module/resolver and test paths with
  revision; describe the search when no matching unit exists.
* **Shortfall** — observable missing behaviour; distinguish absence from a
  composition error or researcher choice.
* **Delivered workaround** — file, lines, revision, and what is hand-built.
* **Canonical SQL / expected contract** — minimal canonical SQL and its source
  path/revision, with join, validity, cardinality and output expectations. For a
  non-SQL capability include the expected metadata/API contract as well; never
  invent SQL for an introspection feature. Unavailable canonical evidence blocks
  filing until resolved.
* **Proposed fix and tests** — core or plugin owner, bounded implementation scope,
  regressions proving equivalence with the canonical contract, and exclusions.
* **Rollout** — delivered under the old pin; additive/forward release, no enquiry
  backport. Explicitly recurring extracts may later bump the pin and re-compose.
