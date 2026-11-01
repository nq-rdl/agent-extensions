---
description: "A send-back note carries everything the engineer needs, so the reply is the fix, not a question"
tags: [handoff, explain, send-back]
runs: 3
max_turns: 10
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, Skill]
---

I am the analyst reviewing fictional ENQ9141 after analyse, the operator run, UAT and the
triage hand-off on the deliverable PR (head 1a2b3c4, run commit 5d6e7f8, review slug
`los` revision 3). I choose Send back. Finding F1: `los_days` counts calendar dates, but
scope item A4 says length of stay is whole 24-hour periods. The requester confirmed A4
again by email on 2026-10-20 (`jsmith-example` asked). The review shows the calculation at
SQL lines 40 to 48 of `sql/los_request.sql`, which is generated from `src/cohort/los.py`.
The runbook and `specs/uat-checklist.md` describe `los_days`. Governance: no new data
element, so no scope question. Give me the paste-ready note for the engineer. I have not
authorised posting. The repository is unavailable here, so use only this evidence.

End your reply with one fenced `yaml` block with exactly these top-level keys:

- `outcome`: `accepted` or `send-back`
- `route`: `fix` or `amend`
- `engineer_follow_up`: `none`, or what the engineer would still need to ask
- `posted`: `yes` or `no`
