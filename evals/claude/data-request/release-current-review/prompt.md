---
description: "A review that applies to the release tag feeds the release body: researcher-relevant items are kept, implementation detail stays internal, nothing holds the release"
tags: [release, analyst]
runs: 3
max_turns: 10
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, Skill]
---

Context: I am the Data Analyst on ENQ9140 (THHSAQUIRE-9940), an emergency department asthma
extract. I am about to release tag `v1.2.0` and need the researcher-facing release body. The repo
is not available in this session, so work from these excerpts.

`release.sh evidence v1.2.0` reported:

```json
{"ref": "v1.2.0", "reviews": [{"slug": "sql__v1__asthma_ed", "revision": 4, "applies": "current",
  "reviewed_commit_in_ref": true, "open_questions": []}]}
```

The confirmed review of `sql/v1/asthma_ed.sql` (revision 4) has these items:

- A1: Asthma presentations are those with a principal diagnosis code in J45 or J46.
- L1: Presentations recorded only by a free-text triage complaint, with no diagnosis code, are
  not included.
- L2: Source tables are read with a `NOLOCK` hint.
- L3: Output rows are not in any particular order.

The pipeline at `v1.2.0` generates exactly this SQL. The output manifest lists one file,
`ED_Presentations`, with one row per presentation, which matches the confirmed scope. The
validation counts at the tag reconcile with the frozen source snapshot. No requested element is
missing.

Which review items should the release body carry, and does anything hold the release?

End your reply with one fenced `yaml` block with exactly these top-level keys:

- `review`: `current` or `stale`
- `hold`: `yes` or `no`
- `include`: a list of the review item ids the release body carries
- `internal`: a list of the review item ids kept in the internal review only
