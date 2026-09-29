---
description: Co-development routes each agreed task to its stage - a change to a released extract to amend, the researcher-facing release body to release, an export defect to fix
tags: [triage, co-develop, routing]
runs: 3
max_turns: 6
timeout_seconds: 240
allowed_tools: [Read, Glob, Grep, Skill]
---

Let's co-develop ENQ9140 with /data-request:triage.

This session has no shell or GitHub access, so everything I gathered is below. Plan only for now: do not start any task.

**rdl-service-desk/service-desk#940**, "THHSRDLENQ-9140 falls clinic follow-up", approval THHSAQUIRE-9940, child repository `rdl-service-desk/THHSAQUIRE-9940`.

- Extract v1.0.0 was released on 2026-09-02: `data/Released/v1.0.0/` exists, tag `v1.0.0` exists and the researcher has the file.
- Comment 2026-09-24 (researcher): "Please rename `appt_dt` to `appointment_date` in the extract. Nothing else changes."
- Comment 2026-09-25 (analyst): "In v1.0.0, `Encounter_id` is written to the CSV as `123,456,789` instead of `123456789`. The agreed output was the plain identifier."
- Comment 2026-09-26 (analyst): "Once both are in, I need the Extraction Summary and Important limitations text for the v1.1.0 release body."

The engineer and I have agreed all three tasks. For each one, name the single data-request stage skill that should do it.

End your reply with one fenced `yaml` block with exactly these top-level keys, each set to one stage name without the `/data-request:` prefix:

- `rename_stage`: the stage for the `appt_dt` rename
- `identifier_stage`: the stage for the `Encounter_id` export defect
- `release_body_stage`: the stage for the v1.1.0 release body text
