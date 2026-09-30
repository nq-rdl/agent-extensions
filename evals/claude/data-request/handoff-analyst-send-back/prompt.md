---
description: Analyst sends logic to engineer and presentation to amend
tags:
- handoff
- explain
runs: 3
max_turns: 10
timeout_seconds: 300
allowed_tools:
- Read
- Glob
- Grep
- Skill
---

I am the analyst reviewing fictional ENQ9022 following analyse, the operator run,
UAT and triage hand-off. I choose Send back. Finding F1: the cohort uses all hospitals,
but the requested output is only site A; that logic decision is still unconfirmed.
Finding F2: show already-surfaced arrival_time first, an independent presentation request.
Give a paste-ready note naming both findings, expected results and affected paths
(builder and generated SQL for F1, projection plus runbook/UAT for F2). The known
approval restriction excludes contact details; carry it into open gates without
claiming a governance decision. I have not authorised posting or release. Do not
modify the SQL, review or marker schema. The repository is unavailable here; use
only this evidence. Which route applies to each finding and does send-back approve release?

End your reply with one fenced `yaml` block with exactly these top-level keys:

- `outcome`: `accepted` or `send-back`
- `logic_route`: `fix` or `amend`
- `presentation_route`: `fix` or `amend`
- `release`: `approved` or `held`
- `posted`: `yes` or `no`
