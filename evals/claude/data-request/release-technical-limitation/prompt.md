---
description: "A technical limitation with a researcher-facing consequence is kept and translated into plain language; a harmless locking hint stays internal"
tags: [release, analyst]
runs: 3
max_turns: 10
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, Skill]
---

Context: I am the Data Analyst on ENQ9142 (THHSAQUIRE-9942), a paediatric fracture extract. I
am drafting the release body for tag `v2.1.0`. The repo is not available in this session, so
work from these excerpts.

`release.sh evidence v2.1.0` reports the review `sql__v2__fractures` (revision 3) as `current`,
with `reviewed_commit_in_ref: true`. Among its confirmed limitations:

- L3: Source tables are read with a `NOLOCK` hint. The validation counts at the tag reconcile
  with the frozen source snapshot.
- L4: Sex, postcode and Indigenous status come from a `LEFT JOIN` to the `PERSON` table on MRN,
  which holds the patient's current record, not the values at the presentation.

The researcher will compare fracture rates by postcode and Indigenous status over ten years.

Which of these belong in the release body, and how would you word them for the researcher?

End your reply with one fenced `yaml` block with exactly these top-level keys:

- `include`: a list of the review item ids the release body carries
- `internal`: a list of the review item ids kept in the internal review only
- `claims`: a list of the proposed release wording, one string per claim
