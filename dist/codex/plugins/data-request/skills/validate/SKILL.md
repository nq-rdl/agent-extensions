---
name: validate
license: CC-BY-4.0
description: Validate RDL request or cohort SQL against its requirements, column specs
  and shared guardrails; report technical findings and evidence without creating a
  confirmed review.
compatibility: RDL cohort SQL; verify deployed SQL dialect/version and current dataops
  schema/index metadata.
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

## Codex execution

Before shell examples, set PLUGIN_ROOT to the absolute installed plugin directory: two parent directories above this SKILL.md’s containing skill directory. Derive it from the loaded file path, never the working directory. This variable is not automatically supplied to ordinary shell tools. Quote it in commands.

Here $ARGUMENTS means the user’s supplied skill arguments. Codex does not populate a shell variable for them. Pass arguments with shell quoting that preserves literal text; never evaluate user text as shell code.

# Data Request — validate

Read `${PLUGIN_ROOT}/skills/guardrails/SKILL.md` first. Arguments: `$ARGUMENTS`.
Read the SQL, request and available scope; validate the actual SQL bytes, not a stale
review snapshot. This action needs no `.sqlreview/` setup and creates no review record.

Trace population, exclusions, grain, window boundaries and output columns against the
request. Follow column-spec provenance to dataops DDL comments for timezone/units and
check current index definitions for filter and join choices. Inspect resolver code
and tests when SQL is generated. Apply each relevant guardrail with file/line evidence.

Use an existing repository lint/parser command when its dialect is configured and
it is a local, read-only check. Inspect the command before running it; do not install
a new lint stack, execute SQL against a database or modify data as a side effect.
When no suitable tool is available, perform a static review and say so. Parser success
does not establish cohort correctness, and a static index assessment is not a plan.

Return findings with severity, SQL location, rule/requirement, observed evidence,
effect on the result and a proposed correction. Distinguish **observed problems**,
**unverified facts** and **checks passed**, and list commands actually run with their
results. Missing DDL/column specs or an unresolved population definition prevents a
fully verified conclusion; report the gap without claiming the SQL is correct.

**Autonomous:** finish every check supported by available evidence and return remaining
questions. **Co-develop:** discuss ambiguous intent or competing corrections with the
human and update the findings. Infer mode from the request when omitted. Do not edit
SQL or carry an unanswered question forward as confirmation.

Use `$data-request:fix` for targeted corrections or `$data-request:draft` to develop SQL.
`$data-request:analyse` remains the separate
human-confirmed handoff: this technical validation does not approve assumptions,
advance snapshots or clear stale review state.
