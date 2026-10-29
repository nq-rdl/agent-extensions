---
description: "Two safe parts and a code-to-label part: complete the safe parts, hand off only the label part"
tags: [amend, split, mixed]
runs: 3
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Context: our enquiry repo was generated from data-analysis-scaffold. Release v1.0.0 of
the falls extract went to the researcher last month (`data/Released/v1.0.0/falls.parquet`).
The request SQL `sql/v2/falls_request.sql` is generated from this builder, which a data
engineer wrote. The deliverable PR for this enquiry is still open. The repo is not available
in this session, so work from this excerpt:

```python
# src/cohort/falls.py (maintained source for sql/v2/falls_request.sql)
def build_falls(resolver):
    return (
        CohortQuery(resolver)
        .add(EncounterSpec(kind="inpatient", start="2024-01-01", end="2025-01-01"))
        .add(HasCondition(codes=["W19", "W18.30"]))  # ICD-10-AM falls codes
        .select("MRN", "EncounterId", "AdmitDateTime", "DischargeDateTime", "AgeAtAdmit",
                "WardCd", "SexCd")
    )
```

`WardCd` and `SexCd` are delivered as source codes. No lookup or label column is surfaced.

The researcher asked for three changes in one email:

1. Call the `MRN` column `URN`.
2. Drop the `AgeAtAdmit` column.
3. Show the ward name in place of the `WardCd` code.

Last time one hard change held up the whole list. Classify each change, tell me what you
would do for each, and summarise what is done and what goes to the engineer.
