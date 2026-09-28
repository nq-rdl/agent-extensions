---
description: "A decided logic change before the extract's first release goes to fix, not amend: change it with the runbook and UAT checklist, then re-run analyse"
tags: [fix, pre-release]
runs: 3
max_turns: 10
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, Skill]
---

Context: our enquiry repo for ENQ9120 was generated from data-analysis-scaffold. Nothing has
been released yet: there is no `data/Released/` folder, no release tag, and the researcher
has not received any extract. The request SQL `sql/v1/ed_request.sql` is generated from the
builder below. `.sqlreview/reviews/sql__v1__ed_request/review.json` holds a confirmed review of
the current SQL. The repo also has `docs/runbook.md`, `specs/uat-checklist.md` and the
validation query `sql/validation/ed_checks.sql`, whose output has a `distinct_mrn` column. The
repo is not available in this session, so work from this excerpt:

```python
# src/cohort/ed.py (maintained source for sql/v1/ed_request.sql)
def build_ed(resolver):
    return (
        CohortQuery(resolver)
        .add(EncounterSpec(kind="emergency", start="2025-01-01", end="2026-01-01"))
        .select("MRN", "EncounterId", "ArrivalDateTime", "Triage")
    )
```

A linkage probe showed that MRNs repeat across sites. The engineer and the requester agreed
decision D7: patients are keyed on site code plus MRN, not MRN alone. The validation output
column `distinct_mrn` becomes `distinct_patient_key`. Is this an amendment for
`/data-request:amend`? Tell me which workflow applies and what has to change, and what happens
to the existing review, before we release.
