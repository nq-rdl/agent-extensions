---
name: map
license: CC-BY-4.0
description: Propose evidence-backed RDL cohort source-table and query-builder resolver
  mappings from a request, scope, legacy answers.yaml or existing hand SQL; resolve
  grain, keys, timezone and units before SQL drafting. Supports a partial map.
compatibility: RDL dataops DDL and query-builder column-spec metadata; inspect the
  checked-out schema and resolver API version.
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

## Codex execution

Before shell examples, set PLUGIN_ROOT to the absolute installed plugin directory: two parent directories above this SKILL.md’s containing skill directory. Derive it from the loaded file path, never the working directory. This variable is not automatically supplied to ordinary shell tools. Quote it in commands.

Here $ARGUMENTS means the user’s supplied skill arguments. Codex does not populate a shell variable for them. Pass arguments with shell quoting that preserves literal text; never evaluate user text as shell code.

# Data Request — map

Invoke `$data-request:guardrails` first and follow its source hierarchy.
Arguments: `$ARGUMENTS`.

## Lift capture

Ordinary mapping needs no `.sqlreview/` setup. Mapping never initialises
`.sqlreview/`; stages that own the store (setup, bootstrap) still initialise it.
Before a mapping leads to hand SQL, inspect the pinned unit/resolver/tests and
silently publish a candidate for the target pipeline, following
`${PLUGIN_ROOT}/skills/setup/references/lifts.rst`. Record the pin,
evidence and shortfall; no entry means no hand SQL. If the target path is not
yet known, pass the gap to draft and require capture before writing.

**Proposal-only:** if the run is read-only, the child repo has no `.sqlreview/`
yet, or you cannot write to it, publish nothing. Return the candidate ledger
entry as text, marked proposal-only. A proposal-only entry authorises no hand SQL:
none is committed or run, except exempt probes, until a writable run publishes the entry.

**Exempt probes:** an operator probe is outside the hand-SQL gate only when it is
aggregate-only, small-cell-suppressed and single-scan, returns no identifying
values (no patient or clinician identifiers, no staff or person keys), and feeds
no delivered extract. Record any `NOLOCK` use. Guardrails is the source of truth
for these rules.
Classification and confirmation happen in `$data-request:lift` at close-out.

## Inputs

Read every supplied input and say which ones the mapping uses:

- The request, `cohort/request.json` or a confirmed scope.
- A legacy shell's `answers.yaml`, when there is no `cohort/request.json` and no
  confirmed scope.
- **From hand SQL:** existing hand SQL or a pipeline. Trace each output column,
  join and filter back to its requested concept and source. The SQL is evidence
  of intent, not of correctness; each hand-built block is a lift candidate.

Identify population, output grain, anchor, window and requested concepts. Reuse
a confirmed decision only when a supplied input records the human answer and it
applies to this mapping; otherwise label it unresolved. Autonomous mode never
supplies business decisions or confirmations. Inspect actual column specs, their
dataops `CREATE TABLE` comments, resolver code and tests. Verify the checked-out
resolver API from that source before proposing an API change.

**Ethnicity:** the records hold no ethnicity field. Map an "ethnicity" element to
Indigenous status from `PERSON_INFO`. Offer country of birth and preferred language
as optional surrogates; the requester or engineer decides. Record the limitation
that ethnicity is not held. Check the pinned library for surrogate units; a missing
unit is a lift candidate. Guardrails holds the convention.

## Mapping output

Return one row per requested element (event, date or output) and candidate:
requested concept → table/column or resolver → source grain and join keys →
verified timezone/units → library support → evidence file and revision →
unresolved choice. Library support names the pinned unit or resolver that
expresses the row, or `none` (a lift candidate). When one table is hard to read,
split the rows into one table per output or source system with the same columns.
For competing candidates, explain the semantic difference and what evidence would
select one. Apply the encounter-mediated clinical-event pattern and indexed-bound
rules from guardrails. Mark missing metadata explicitly; do not fabricate a new
column-spec schema or resolve an ambiguity by matching names alone.

**Partial map:** when cohort concepts are confirmed but no data elements are named
yet, map the confirmed cohort concepts only. List the pending data elements
separately, each with the question that would settle it. Do not guess them.

**Autonomous:** complete the proposal using explicit requirements and verified facts;
leave choices requiring business judgement unresolved. **Co-develop:** show those
choices with their consequences and ask focused questions, then revise the proposal.
Without a mode flag, infer the mode from the user's request; ask only when that affects
a decision. In either mode, an unanswered question is not agreement.

Finish with the proposed mapping, evidence and remaining decisions. Hand a defined
mapping to `$data-request:draft`; use `$data-request:bootstrap` when formal scope confirmation
is wanted. A proposal does not update resolver code, column specs or human confirmations.
