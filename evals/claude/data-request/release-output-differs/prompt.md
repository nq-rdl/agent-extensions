---
description: "A release whose pipeline and outputs differ from the SQL-only review and the scope is held: the inclusion rule, grain and missing requested element are blockers, not boilerplate"
tags: [release, analyst]
runs: 3
max_turns: 10
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, Skill]
---

Context: I am the Data Analyst on ENQ9136 (THHSAQUIRE-9936), a falls extract. Please polish the
existing release body for tag `v1.0.0` so I can publish it. The repo is not available in this
session, so work from these excerpts.

Existing release body draft:

> Patients aged 18 or over whose "Presenting complaint" and "Presenting problem" both mention
> "Fall". One row per patient. Includes mechanism of injury.

`release.sh evidence v1.0.0` reports the SQL review of `sql/v1/falls_encounters.sql` as
`current`. That review describes one encounter query only, with a grain of one row per
encounter and an OR rule over the complaint fields.

The pipeline at `v1.0.0` (`src/pipelines/falls_service_extract.py`) composes
`HasDiagnosisText("FALL") | HasClinicalEventText("chief_complaint", "FALL") |
HasClinicalEventText("visit_reason", "FALL")` and declares two outputs, `Encounter_Level` and
`Clinical_events`. The confirmed `.copier-answers.yml` says `measurement_granularity: Patient`.
The confirmed scope requested mechanism of injury, and neither output has a mechanism of injury
field.

What should happen to this release body?

End your reply with one fenced `yaml` block with exactly these top-level keys:

- `hold`: `yes` or `no`
- `blockers`: a list of the blocking discrepancies, each one of `inclusion-rule`, `grain`,
  `outputs`, `age-basis` or `missing-element`
