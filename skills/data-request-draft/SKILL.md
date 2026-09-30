---
name: data-request-draft
license: CC-BY-4.0
description: >-
  Draft or revise RDL cohort SQL from a defined request and verified source mappings,
  working autonomously on settled requirements or co-developing unresolved decisions.
argument-hint: '<request or scope path> <target sql path> [--autonomous|--co-develop]'
user-invocable: true
compatibility: >-
  RDL cohort SQL; verify target engine/version, dataops schema and query-builder column-spec metadata at use time.
  record_assumption/record_limitation need query-builder 0.6.0 or later.
allowed-tools: Bash, Write, Read, Glob, Grep, Edit, AskUserQuestion
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

# Data Request — draft

The **Data Engineer** runs draft from the Data Analyst's request and confirmed
intake carried into scope by bootstrap. Preserve analyst upstream decisions and
their actors. Label missing research decisions `Analyst question:` and return
them to the analyst to consult the requester; engineer technical choices do not
replace those answers.

Read `${CLAUDE_PLUGIN_ROOT}/skills/guardrails/SKILL.md` first, including **Engineer decisions: proceed and flag**
in its `references/decision-authority.rst`. Arguments: `$ARGUMENTS`.
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

**Autonomous:** implement evidenced engineer-owned technical defaults and flag them, without
waiting for analyst approval. Do not attribute an agent default to the engineer. Stop only the
dependent portion for known governance restrictions, cohort expansion, released-output row-count
changes or an unsupported requester clinical definition; name the class and continue independent work.
Batch remaining questions with defaults/evidence into one analyst message; keep building on safe defaults.
Deliver only the narrowest supported request; offer extras in hand-off, do not build them.
**Co-develop:** present alternatives and effects to the owning engineer or analyst, obtain the
decision, then proceed and flag. Infer mode if absent. Neither mode manufactures confirmation fields.

Write the requested SQL, preserving unrelated edits. Keep indexed filter columns
bare, transform verified anchors, and use verified encounter/event join keys. Trace
the resulting grain through joins and exclusions. Keep unresolved placeholders out
of executable SQL; if only a partial draft is possible, present it as incomplete
and explain the missing decision before creating a runnable file.
In pipeline or resolver code, record each reading you commit to with
`pipeline.record_assumption(text, rationale=...)` and each accepted weakness with
`pipeline.record_limitation(text, consequence=...)` at the line that introduces it
(guardrails), not in a separate notes file. For a genuinely stated engineer decision,
record `Engineer decision (<login>, <date>), flagged for the data analyst` as the rationale
(or limitation consequence). Use the actual human handle and original date or UTC ISO
instant, never a role label, recorder or inferred approval. Preserve any independently
known decision origin/source. Unknown attribution stays unknown and is walked in analyse.
Include real engineer login/date and decision evidence in the generated SQL header and
analyst hand-off per the shared authority rule.

Return the path, implemented cohort definition, evidence locations for mappings and
conversions, and any unresolved limitations. Perform a static check using
`/data-request:validate`; do not execute SQL against a database as part of drafting.
For a formal handoff, proceed to `/data-request:analyse`. Leave existing `.sqlreview/`
snapshots and confirmations untouched: edits to SQL must remain visible as stale
until a fresh review is completed.
Child tests must check item identifier lists and must not pin revision numbers in scope/review records.
