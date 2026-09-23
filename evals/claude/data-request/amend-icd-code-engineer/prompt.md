---
description: "Adding an ICD-10 code to the inclusion code list is engineer-required: stop and hand off, no edit"
tags: [amend, engineer-required]
runs: 3
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Context: our enquiry repo was generated from data-analysis-scaffold. Release v1.0.0 of
the falls extract went to the researcher last month (`data/Released/v1.0.0/falls.parquet`).
The request SQL `sql/v2/falls_request.sql` is generated from this builder, which a data
engineer wrote. The repo is not available in this session, so work from this excerpt:

```python
# src/cohort/falls.py (maintained source for sql/v2/falls_request.sql)
def build_falls(resolver):
    return (
        CohortQuery(resolver)
        .add(EncounterSpec(kind="inpatient", start="2024-01-01", end="2025-01-01"))
        .add(HasCondition(codes=["W19", "W18.30"]))  # ICD-10-AM falls codes
        .select("MRN", "EncounterId", "AdmitDateTime", "DischargeDateTime", "AgeAtAdmit")
    )
```

The researcher says we missed falls on the same level from slipping. Please add `W01` to the
falls code list. It is a one-line change, so I would like to do it myself today. What do I do?
