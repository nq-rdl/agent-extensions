---
license: CC-BY-4.0
description: >-
  Close out request pipelines: inspect the pinned library, classify lift candidates
  with the human, file reusable work on the owning library, and record delivered
  hand-SQL limitations. Revisit released lifts for explicitly recurring extracts.
argument-hint: '<pipeline path>'
user-invocable: true
compatibility: >-
  .sqlreview schema 2 (schema 1 remains readable); Bash 3.2+, jq >= 1.6.
  API baseline query-builder 0.4.0 and query-builder-plugins 0.3.0;
  inspect the enquiry's actual framework_ref before claiming availability.
allowed-tools: Bash, Read, Glob, Grep, Write, AskUserQuestion
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

# Data Request — lift

Close-out asks what belongs in the library; `/data-request:analyse` separately
reviews what the delivered pipeline does. Do not implement library fixes here.

Read `${CLAUDE_PLUGIN_ROOT}/skills/guardrails/SKILL.md` and the shared
ledger contract at `${CLAUDE_PLUGIN_ROOT}/skills/setup/references/lifts.rst` (canonical source:
`skills/data-request-setup/references/lifts.rst`). Verify correctness-critical API
claims against the pinned implementation and tests in
`nq-rdl/query-builder` and
`nq-rdl/query-builder-plugins`.
The baseline is a discovery aid, not evidence that a pin contains a unit.

## Discover before classifying

Resolve the helper at `${CLAUDE_PLUGIN_ROOT}/skills/setup/scripts/sqlreview.sh`.
Run `status --json`, `slug <pipeline path>` and `fingerprint <pipeline path>`.
If uninitialised, use `/data-request:setup --default --yes`; existing config and
custom templates are preserved. Read scope, review and `lifts.json` for that slug.
For schema-1 projects use the bundled lift definition/template when absent;
adding the new template through `init --apply templates/lifts.md` is additive.
Read `recurring` from the ledger or explicit request evidence; do not infer it
from a filename or propose a backport for a one-off extract.

Scan the whole pipeline and its local helpers, even when the ledger is populated:
f-string/concatenated SQL, raw query strings, secondary lookup queries, repeated
cohort execution, and inline modelling such as 30-day mortality or latest versus
at-time address. Inspect output/metadata construction too: manually assembled
spec descriptions or resolver provenance may expose a missing library capability.
Read canonical SQL, the dependency lock/framework_ref, matching specs, resolver
handlers and tests at that revision. Record actual paths/revisions and shortfalls;
missing access is unresolved evidence, never proof that a unit is absent.
Capture missed candidates before looking for existing library issues.
If the checkout is only a scaffold, locate the implemented pipeline revision
before claiming a close-out. Reconcile manifest, lock and installed revisions;
a manifest/lock disagreement makes the effective pin unresolved.

## Confirm the boundary

Propose a bucket for every candidate, including composition that should stay local:

- `new-capability`: no pinned unit expresses the reusable need.
- `existing-unit-gap`: a pinned unit exists but lacks required behaviour.
- `request-specific`: researcher modelling or composition using sufficient units.
  An agent not knowing an existing API is a composition error, not a library gap.

Put each candidate, classification, evidence and proposed disposition to the human
via AskUserQuestion, at most four per batch (use smaller batches if the host limit
requires). Options: **Confirm (Recommended)** / **Reword** / **Reject**. Ask again
after rewording. Rejected candidates remain in `lifts.draft.json` with the reason;
remove them from the published ledger so they cannot authorise future hand SQL.
Unanswered candidates stay `candidate`; stop dependent filing, keep the draft.
Never fill any confirmation field without the human's answered question.
The entry revision, not an unrelated newly appended candidate, binds the answer.

## File and record delivery

For confirmed library candidates, search the owning library's open and closed
issues for equivalent work before creating anything. Reuse a matching issue after
checking its evidence and scope; do not create a duplicate on retries. For new
issues use the fixed [evidence block](references/evidence.rst), with canonical SQL
and regression expectations grounded in inspected sources. The owning repo is
`nq-rdl/query-builder` for shared composition/spec infrastructure, or
`nq-rdl/query-builder-plugins` for source-specific resolvers. Invoking this skill
includes filing confirmed library candidates. Do not file on the enquiry repo.
Use a structured GitHub tool or `gh issue create --repo <owner> --body-file <file>`.
After success record the returned URL and `filed`; after an uncertain response,
search for the issue before retrying. Keep confirmed evidence intact across retries.
Publish/render the ledger through the shared helper after each successful filing.

For every delivered-by-hand library candidate, propose a review limitation with
`lift_id` and exactly this text, derived from the ledger:

> <need> resolved with in-repo SQL. Library unit tracked in <issue_url>. Not backported.

Confirm it with the human under the existing review contract. Never autonomously
stamp limitation confirmations. Increment the review revision and reassess every
assumption/limitation as analyse requires; publish, snapshot and render only after
confirmation and a current fingerprint. If no review exists, hand off to analyse
with the proposed limitation; report close-out incomplete until it is recorded.
For request-specific hand SQL there is no library issue: propose a truthful
limitation describing the local composition and no planned backport, without a
fabricated URL. Keep rejected/unconfirmed delivery risks visible in the draft.

## Recurring follow-up

For `filed` entries inspect the linked issue, merged change and release/tag that
contains it. A closed issue alone is not release evidence. On verified release,
record `release_evidence: {version, url}` and advance to `released`, retaining the
human-confirmed need. For an explicitly recurring extract propose the exact pin
bump and re-composition, with changed APIs and tests to verify. After the user
accepts, hand off to `/data-request:draft`, then `/data-request:analyse`; advance
to `recomposed` only after the workaround is removed, validation succeeds and the
updated review is confirmed. Record `recomposition_evidence` with the new `pin`,
`sql_sha256` and `review_revision`. Retain the original delivery limitation as history.
One-off extracts stay forward-only; do not open backport issues or modify pins.

Report candidates by bucket, issue links, unresolved confirmations/evidence and
review limitation publication status. Do not call a candidate filed or a close-out
complete until those writes have succeeded.
