---
description: A screening-log-only approval keeps broader intake fields out, and an explicit ICD code list is not broadened by a library concept
tags: [triage, governance]
runs: 3
max_turns: 6
timeout_seconds: 240
allowed_tools: [Read, Glob, Grep, Skill]
---

Triage ENQ9004 (rdl-service-desk/service-desk#904, approval SSAQHTS-99001); triage only. Tell me which output fields and diagnosis codes the draft should use. This session has no shell access; the evidence is below.

Intake form (SSAQHTS-99001 issue #1, 2026-08-02):

- Cohort: adults with an abdominal aortic aneurysm, ICD-10-AM I71.3 or I71.4 only.
- Exclusions: dementia, dialysis, prior EVAR or TEVAR, deceased.
- Requested fields: URN, full name, date of birth, phone, address, AAA diagnosis date, latest eGFR, latest HbA1c.

rdl-service-desk/service-desk#904 comment, 2026-08-20 (governance): "Approved for a screening log only: URN and the eligibility date. Contact details, demographics and pathology are not approved at this stage; a separate application is needed."

query-builder `clinical/concepts.py` at the child's pinned tag v0.5.0:

```python
"abdominal_aortic_aneurysm": ICDCodeSet(["I71.3", "I71.4", "I71.8"]),
```

End your reply with one fenced `yaml` block with exactly these top-level keys: `output_fields`, `diagnosis_codes`, `excluded_fields`, `open_questions` (each a list).
