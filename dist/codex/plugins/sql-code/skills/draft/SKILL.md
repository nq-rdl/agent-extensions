---
name: draft
license: CC-BY-4.0
description: Draft or revise RDL cohort SQL from a defined request and verified source
  mappings, working autonomously on settled requirements or co-developing unresolved
  decisions.
compatibility: RDL cohort SQL; verify target engine/version, dataops schema and query-builder
  column-spec metadata at use time.
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

## Codex execution

Before shell examples, set PLUGIN_ROOT to the absolute installed plugin directory: two parent directories above this SKILL.md’s containing skill directory. Derive it from the loaded file path, never the working directory. This variable is not automatically supplied to ordinary shell tools. Quote it in commands.

Here $ARGUMENTS means the user’s supplied skill arguments. Codex does not populate a shell variable for them. Pass arguments with shell quoting that preserves literal text; never evaluate user text as shell code.

# SQL Code — draft

Read `${PLUGIN_ROOT}/skills/guardrails/SKILL.md` first. Arguments: `$ARGUMENTS`.
Use the requested SQL path, existing SQL, request and any supplied scope. Drafting
does not require `.sqlreview/` or create a formal scope/review record.

Establish the population, exclusions, output grain, anchor, window boundaries and
required columns from explicit instructions or confirmed scope. Consult column-spec
metadata and dataops DDL comments for every field whose interpretation affects the
result; use `$sql-code:map` for unresolved source/resolver choices. Verify dialect and
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
`$sql-code:validate`; do not execute SQL against a database as part of drafting.
For a formal handoff, proceed to `$sql-code:analyse`. Leave existing `.sqlreview/`
snapshots and confirmations untouched: edits to SQL must remain visible as stale
until a fresh review is completed.
