---
description: "Reordering output columns is analyst-safe: a new field order in the existing .select()"
tags: [amend, analyst-safe]
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

Can you put `EncounterId` first in the extract, then `MRN`, and leave the other columns in
their current order? Classify the amendment, then show me the change and how you would
check it.
