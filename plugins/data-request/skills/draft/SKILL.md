---
license: CC-BY-4.0
description: >-
  Draft or revise RDL cohort SQL from a defined request and verified source mappings,
  working autonomously on settled requirements or co-developing unresolved decisions.
argument-hint: '<request or scope path> <target sql path> [--autonomous|--co-develop]'
user-invocable: true
compatibility: RDL cohort SQL; verify target engine/version, dataops schema and query-builder column-spec metadata at use time.
allowed-tools: Bash, Write, Read, Glob, Grep, Edit, AskUserQuestion
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

# Data Request — draft

Read `${CLAUDE_PLUGIN_ROOT}/skills/guardrails/SKILL.md` first. Arguments: `$ARGUMENTS`.
Use the requested SQL path, existing SQL, request and any supplied scope. Drafting
requires no formal scope/review record. Before writing SQL outside the composition
API, silently publish a lift candidate under the pipeline path, following
`${CLAUDE_PLUGIN_ROOT}/skills/setup/references/lifts.rst`. Cite the actual pin,
inspected unit/resolver/tests and shortfall first. No entry means no hand SQL;
leave classification and confirmation for `/data-request:lift` at close-out.

Establish the population, exclusions, output grain, anchor, window boundaries and
required columns from explicit instructions or confirmed scope. Consult column-spec
metadata and dataops DDL comments for every field whose interpretation affects the
result; use `/data-request:map` for unresolved source/resolver choices. Verify dialect and
correctness-critical syntax using the canonical docs linked by guardrails.

**Autonomous:** implement the well-defined portion without repeated confirmation.
If a missing clinical/business decision changes who is included or what an output
means, stop the dependent portion and report the precise question; do not invent a
cohort definition. **Co-develop:** present alternatives and their population/grain
effects, obtain the decision, then continue. Infer mode from the request if no flag
is supplied. Neither mode permits manufacturing human-confirmation fields.

Write the requested SQL, preserving unrelated edits. Keep indexed filter columns
bare, transform verified anchors, and use verified encounter/event join keys. Trace
the resulting grain through joins and exclusions. Keep unresolved placeholders out
of executable SQL; if only a partial draft is possible, present it as incomplete
and explain the missing decision before creating a runnable file.

Return the path, implemented cohort definition, evidence locations for mappings and
conversions, and any unresolved limitations. Perform a static check using
`/data-request:validate`; do not execute SQL against a database as part of drafting.
For a formal handoff, proceed to `/data-request:analyse`. Leave existing `.sqlreview/`
snapshots and confirmations untouched: edits to SQL must remain visible as stale
until a fresh review is completed.
