---
name: data-request-guardrails
license: CC-BY-4.0
description: >-
  Apply advisory RDL cohort-SQL guardrails when drafting, changing, mapping, validating
  or reviewing request pipelines, SQL and query-builder resolvers. Covers spec
  composition, indexed filters, source timezones, join evidence and researcher
  modelling choices, with pointers to authoritative sources.
argument-hint: '[request, SQL path or resolver]'
user-invocable: true
compatibility: >-
  RDL cohort SQL; DATEADD example targets SQL Server 2022 (16.x).
  Source patterns from issues 313 and 325 (2026-09-15 to 2026-09-17).
  Composition examples are schematic; verify pinned library APIs, deployed engine
  and current metadata.
allowed-tools: Read, Glob, Grep, AskUserQuestion
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

# Data Request — guardrails

The shared advisory spine for RDL request repos and query-builder. Apply it to the
request composition and SQL being worked on, including work outside a formal review.
It requires no `.sqlreview/` setup and adds no SQL lint gate or approval record.

## Confirm sources before using a fact

Locate the relevant sources in the supplied workspace or connected repositories:

- **dataops `CREATE TABLE` definitions and their comments** are authoritative for
  schema, field timezone and units; inspect DDL/index comments for join rationale.
  Record the file/table/column and revision read.
- **query-builder column-spec metadata** is the consumer-facing pointer to each
  field's meaning, timezone and units. Follow its provenance to the dataops DDL;
  read the existing resolver's docstring and tests for the implemented mapping,
  required joins and their performance or correctness rationale.
- **Current index definitions** establish key order and usable join/filter paths.
  Use an existing plan or authorised read-only plan inspection to check performance.
- **Request and confirmed scope** establish population, grain, anchor, time window
  and output meaning. They do not override storage facts.

Search by the actual table/column/resolver names; do not invent a column-spec path,
metadata key, missing sibling implementation or database access. When sources conflict,
show both locations and use dataops as ground truth for storage facts; flag stale
consumer metadata. Library behaviour comes from the pinned implementation and tests.
When evidence is unavailable, label the affected decision unverified and ask only
for the missing source/decision needed to proceed. Never fill gaps from a field name.

Verify correctness-critical syntax against the deployed engine's canonical docs
([SQL Server documentation](https://learn.microsoft.com/en-us/sql/t-sql/language-reference))
and storage facts against the current dataops DDL before presenting a result as verified.

## Compose library units in requests

Atomic, testable Layer-1 `Spec`s, `@resolves` resolver handlers and reusable helpers
belong in `query-builder` / `query-builder-plugins`. Request pipelines compose those
units: `CohortQuery(Resolver).add(SpecA).add(SpecB)`. If a unit is missing or incorrect,
identify the library enhancement and its tests; do not work around it with hand-rolled
SQL in request code. Check the request's dependency pin before using an enhancement.

Confirm the applicable rules in the current `.specify/memory/constitution.md`:

- `nq-rdl/query-builder` Constitution:
  core packages must not construct SQL with f-strings or string concatenation.
  Its narrow exception for commented resolver SQL that PyPika cannot express does
  not authorise raw SQL in a request pipeline.
- `nq-rdl/data-analysis-scaffold` Constitution:
  raw f-string SQL construction is prohibited outside template scripts.

The `falls_service_cohort.py` Indigenous-status lookup in
[#325](https://github.com/nq-rdl/agent-extensions/issues/325) illustrates the change:

```python
# Before: _build_indigenous_status_sql(...) hand-builds an SQL f-string.
# After: compose verified library units (schematic; check pinned signatures).
query = (
    CohortQuery(IEMRResolver)
    .add(EncounterIdAnchor(...))
    .add(WithIndigenousStatus(...))
)
```

`nq-rdl/query-builder-plugins` issue #26 tracks the active-current and
display-resolution enhancement behind this example.
The issue is a discovery pointer, not proof that a request's installed version has it.

## Performance: shift the anchor

Keep a filtered indexed column bare. In the incident behind #313, wrapping
`PERFORMED_DT_TM` in `DATEADD` prevented an index-friendly range predicate.
Transform the bounds into the column's stored timezone instead. Illustrative T-SQL
using [DATEADD](https://learn.microsoft.com/en-us/sql/t-sql/functions/dateadd-transact-sql),
**only after confirming UTC storage and fixed UTC+10 anchors**:

```sql
WHERE ce.PERFORMED_DT_TM >= DATEADD(hour, -10, @window_start_aest)
  AND ce.PERFORMED_DT_TM <  DATEADD(hour, -10, @window_end_aest)
```

The half-open interval above is illustrative: preserve the request's agreed boundary
semantics. Do not silently replace an inclusive endpoint, choose nine months, or
substitute a fixed offset where daylight-saving rules apply. Check bound types and
implicit conversions too; a bare column alone does not prove an index seek.

## Timezone and source system

The seed incident involved **BI-Reporting AEST** and **ieMR/emr UTC**. Treat these as
source-level clues to verify, not a per-field truth table. Confirm each participating
field and anchor via its DDL comments and column spec before comparing timestamps.
Reconcile into the filtered column's timezone by transforming the anchor; avoid
double conversion when a view or resolver already normalises it. Record the verified
source and conversion in the task output, rather than copying field facts into this skill.

## Join and index patterns

For any spec/resolver that requires a join, make the requirement and its rationale
discoverable in the resolver's docstring/tests, column-spec metadata and dataops
DDL/index comments. Inspect those sources for the actual tables and pinned resolver;
cite which locations and revisions you checked, what each establishes, and any
missing evidence. When changing a resolver, document and test its join requirement
and flag missing or stale metadata/comments for the owning repository.

For person-level clinical-event selection, start with the known RDL pattern
**`CLINICAL_EVENT → ENCOUNTER → person`**: the seed environment has no person-leading
index on `CLINICAL_EVENT`. Confirm current key order, encounter/person keys and
cardinality in DDL/index definitions before choosing the exact join. Do not infer
that a person identifier's presence makes direct person filtering efficient.

Check whether multiple encounters/events multiply the intended output grain. Choose
joins or existence checks from the requested population and verified relationships;
do not conceal an incorrect join with `DISTINCT`. If current indexes justify a
different path, explain the evidence rather than treating the seed as timeless.

## Leave modelling choices to the researcher

The library supplies atomic, verified facts and flags known intrinsic data-quality
caveats. The researcher chooses how those facts define an outcome or exposure;
encode that choice in the request's spec composition, not an implicit resolver default.

- **Mortality:** supply date of death with its source limitation.
  `nq-rdl/query-builder` issue #79 describes an ieMR source that undercounts deaths
  outside hospital and over longer follow-up
  without death-registry linkage. Verify the current source and limitation; do not
  assume the proposed automatic annotation mechanism is installed. Carry the caveat
  into the task output even if it must be recorded manually. Turning that date into
  **30-day mortality**, including the anchor and window boundaries, is the researcher's
  modelling choice, expressed in the request's own spec composition.
- **Suburb/postcode:** latest address and address at the time of an encounter answer
  different questions. Leave that choice and its temporal anchor to the researcher/spec;
  verify whether the source supports it rather than silently substituting latest data.

When request logic crosses this boundary, flag the modelling decision and its effect.
Use an already-confirmed scope choice where available; otherwise ask the researcher
to settle the affected choice and continue work that does not depend on it. Do not
treat source limitations as permission to choose a model or promise unavailable facts.

## Carry evidence into the task

For each applicable rule, report the relevant SQL location, evidence location and
result: supported, concern, or unverified. A static review is not a measured runtime
result. Keep business decisions separate from storage facts and never claim human
confirmation on the basis of an autonomous run. Future domain rules belong here only
when there is a concrete incident and an authoritative source to confirm the details.
