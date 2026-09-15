---
license: CC-BY-4.0
description: >-
  Propose evidence-backed RDL cohort source-table and query-builder resolver mappings
  from a request or scoped output; resolve grain, keys, timezone and units before SQL drafting.
argument-hint: '<request, scope path or resolver> [--autonomous|--co-develop]'
user-invocable: true
compatibility: RDL dataops DDL and query-builder column-spec metadata; inspect the checked-out schema and resolver API version.
allowed-tools: Read, Glob, Grep, AskUserQuestion
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

# SQL Code — map

Read `${CLAUDE_PLUGIN_ROOT}/skills/guardrails/SKILL.md` first and follow its source
hierarchy. This action proposes mappings; it requires no `.sqlreview/` setup.
Arguments: `$ARGUMENTS`.

Read the request and any supplied scope. Identify population, output grain, anchor,
window and requested concepts. Reuse a confirmed decision only when the supplied
request or scope records the human answer and it applies to this mapping; otherwise
label it unresolved. Autonomous mode never supplies business decisions or confirmations.
Inspect actual column specs, their dataops `CREATE TABLE` comments, resolver code and
tests. Verify the checked-out resolver API from that source before proposing an API change.

Return one mapping table: requested concept → table/column or resolver → source grain
and join keys → verified timezone/units → evidence file and revision → unresolved choice.
For competing candidates, explain the semantic difference and what evidence would
select one. Apply the encounter-mediated clinical-event pattern and indexed-bound
rules from guardrails. Mark missing metadata explicitly; do not fabricate a new
column-spec schema or resolve an ambiguity by matching names alone.

**Autonomous:** complete the proposal using explicit requirements and verified facts;
leave choices requiring business judgement unresolved. **Co-develop:** show those
choices with their consequences and ask focused questions, then revise the proposal.
Without a mode flag, infer the mode from the user's request; ask only when that affects
a decision. In either mode, an unanswered question is not agreement.

Finish with the proposed mapping, evidence and remaining decisions. Hand a defined
mapping to `/sql-code:draft`; use `/sql-code:bootstrap` when formal scope confirmation
is wanted. A proposal does not update resolver code, column specs or confirmed records.
