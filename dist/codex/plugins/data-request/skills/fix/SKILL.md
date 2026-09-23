---
name: fix
license: CC-BY-4.0
description: Fix reported defects in an RDL data-request repository's SQL and Python,
  including query results, transformations, identifier types and export formatting.
  Use for targeted corrections to existing code with a concrete expected result.
compatibility: RDL request repos; verify the repository's SQL dialect, Python environment
  and installed library versions at use time. record_assumption/record_limitation
  need query-builder 0.6.0 or later.
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

## Codex execution

Before shell examples, set PLUGIN_ROOT to the absolute installed plugin directory: two parent directories above this SKILL.md’s containing skill directory. Derive it from the loaded file path, never the working directory. This variable is not automatically supplied to ordinary shell tools. Quote it in commands.

Here $ARGUMENTS means the user’s supplied skill arguments. Codex does not populate a shell variable for them. Pass arguments with shell quoting that preserves literal text; never evaluate user text as shell code.

# Data Request — fix

Arguments: `$ARGUMENTS`. Read `${PLUGIN_ROOT}/skills/guardrails/SKILL.md`
and apply the rules relevant to the affected SQL or source mappings. This action
works without `.sqlreview/`; a small correction does not require setup, bootstrap
or a formal review before editing.

Locate the reported file and trace the affected output back through SQL aliases,
casts and joins, Python loaders and transformations, and the final serializer or
spreadsheet writer. Read repository instructions and the relevant request, schema,
column specs and tests. Follow generated SQL to its generator or resolver; fix the
maintained source and regenerate through the repository's existing workflow.

Establish the observed and expected values at the boundary where they diverge.
Inspect only the evidence needed for this defect; unrelated source metadata need
not block a formatting fix. If the file or expected meaning cannot be identified,
ask for the missing detail while continuing independent investigation. Implement
settled requirements directly; ask before choosing a different population, grain
or business meaning.

A reported “defect” that is really a change request belongs in `$data-request:amend`.

## Identifier and export defects

For a request such as “`Encounter_id`, `Test_encounter_id` and `Event_id` appear as
`123,456,789`; output `123456789`”, check whether commas exist in the serialized
value or only in the viewer's numeric format. Check the SQL result type, Python
dtype, formatter and export settings before selecting the correction. A screenshot
or grouped display alone does not establish that the stored identifier is wrong.

Treat identifiers according to the output contract, not as quantities to format.
Remove grouping at the responsible boundary; do not change database column types,
join keys or every numeric column to solve a presentation defect. Preserve leading
zeroes where meaningful, exact large identifiers, and nulls without turning them
into literal `"nan"`, `"None"` or `"<NA>"`. Avoid float round-trips: if precision or
leading zeroes were already lost upstream, fix ingestion from an authoritative
source rather than attempting to reconstruct the original ID. Do not strip all
punctuation from opaque IDs unless the contract establishes that it is formatting.

## Verify the correction

Make the smallest source change that resolves the reported defect, preserving
unrelated edits. When the fix changes a filter, join or meaning in pipeline or
resolver code, add or update its `record_assumption()` / `record_limitation()` call
at that point (guardrails); remove a record whose logic the fix removes. Use the
repository's managed environment and existing checks.
Inspect test/export commands before running them; exercise the affected path with
local synthetic fixtures, without querying a live database or publishing exports
as part of a code fix. Verify correctness-critical API behavior against the
installed version's canonical documentation when local code/tests do not settle it.

For an identifier correction, check the actual serialized value and, where relevant,
cell type/number format for an ordinary ID, a leading-zero ID, a null and an ID
beyond floating-point exactness. Confirm unrelated numeric outputs retain their
formats and row counts/keys are unchanged. Add a focused regression test when the
repository has a suitable test path. For SQL logic changes, use
`$data-request:validate` for the applicable static checks.

Report the cause, changed paths, resulting behavior, checks run and remaining gaps.
Preserve `.sqlreview/` snapshots, JSON confirmations and history; a code fix cannot
approve a review or clear stale state. Existing review fingerprints cover SQL only:
a Python-only change may affect delivered data without marking the review stale.
Call out that impact and recommend `$data-request:analyse` when a refreshed formal
handoff is needed; do not claim release approval from a passing local check.
