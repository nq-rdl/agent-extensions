---
description: "Two engineer-required parts: one hand-off with an entry per part, nothing done by the analyst"
tags: [amend, split, engineer-required]
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

The researcher asked for two changes in one email:

1. Add a `LengthOfStayDays` column. It is only `DischargeDateTime` minus `AdmitDateTime`.
2. Keep only patients aged 65 or over at admission.

Classify each change, tell me what you would do for each, and summarise what is done and
what goes to the engineer.
