---
name: data-request-guardrails
license: CC-BY-4.0
description: >-
  Apply advisory RDL cohort-SQL guardrails when drafting, changing, mapping, validating
  or reviewing request SQL and query-builder resolvers. Covers indexed filters,
  source timezones and encounter-mediated clinical-event joins, with evidence pointers.
argument-hint: '[request, SQL path or resolver]'
user-invocable: true
compatibility: >-
  RDL cohort SQL; DATEADD example targets SQL Server 2022 (16.x).
  Source patterns from issue 313 (2026-09-15); verify deployed engine and current metadata.
allowed-tools: Read, Glob, Grep, AskUserQuestion
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

# Data Request — guardrails

The shared advisory spine for RDL request repos and query-builder. Apply it to the
SQL being worked on, including work outside a formal review. It requires no
`.sqlreview/` setup and adds no SQL lint gate or approval record.

## Confirm sources before using a fact

Locate the relevant sources in the supplied workspace or connected repositories:

- **dataops `CREATE TABLE` definitions and their comments** are authoritative for
  schema, field timezone and units. Record the file/table/column and revision read.
- **query-builder column-spec metadata** is the consumer-facing pointer to each
  field's meaning, timezone and units. Follow its provenance to the dataops DDL;
  read the existing resolver and its tests for the implemented mapping.
- **Current index definitions** establish key order and usable join/filter paths.
  Use an existing plan or authorised read-only plan inspection to check performance.
- **Request and confirmed scope** establish population, grain, anchor, time window
  and output meaning. They do not override storage facts.

Search by the actual table/column/resolver names; do not invent a column-spec path,
metadata key, missing sibling implementation or database access. When sources conflict,
show both locations and use dataops as ground truth; flag stale consumer metadata.
When evidence is unavailable, label the affected decision unverified and ask only
for the missing source/decision needed to proceed. Never fill gaps from a field name.

Verify correctness-critical syntax against the deployed engine's canonical docs
([SQL Server documentation](https://learn.microsoft.com/en-us/sql/t-sql/language-reference))
and storage facts against the current dataops DDL before presenting a result as verified.

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

For person-level clinical-event selection, start with the known RDL pattern
**`CLINICAL_EVENT → ENCOUNTER → person`**: the seed environment has no person-leading
index on `CLINICAL_EVENT`. Confirm current key order, encounter/person keys and
cardinality in DDL/index definitions before choosing the exact join. Do not infer
that a person identifier's presence makes direct person filtering efficient.

Check whether multiple encounters/events multiply the intended output grain. Choose
joins or existence checks from the requested population and verified relationships;
do not conceal an incorrect join with `DISTINCT`. If current indexes justify a
different path, explain the evidence rather than treating the seed as timeless.

## Carry evidence into the task

For each applicable rule, report the relevant SQL location, evidence location and
result: supported, concern, or unverified. A static review is not a measured runtime
result. Keep business decisions separate from storage facts and never claim human
confirmation on the basis of an autonomous run. Future domain rules belong here only
when there is a concrete incident and an authoritative source to confirm the details.
