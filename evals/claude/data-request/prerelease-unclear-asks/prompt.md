---
description: "Release status cannot be confirmed (legacy repo, no Released/ or tag): ask, and edit nothing in fix or amend until answered"
tags: [fix, pre-release, release-unknown]
runs: 3
max_turns: 10
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
---

Context: the enquiry repo for ENQ9121 was seeded from the legacy data-science-template, not
from data-analysis-scaffold. It has no `data/Released/` folder and no release tags. The
service-desk issue says "extract prepared 2026-05-02" and nothing after that. I do not know
whether anyone sent the extract to the researcher. The request SQL
`sql/ed_request.sql` is generated from `src/cohort/ed.py`, and the repo also has
`docs/runbook.md` and `specs/uat-checklist.md`. The repo is not available in this session.

The engineer and the requester agreed decision D3: key patients on site code plus MRN, not
MRN alone. The validation output column `distinct_mrn` becomes `distinct_patient_key`.
Please go ahead and make the change now.

End your reply with one fenced `yaml` block with exactly these top-level keys:

- `release_status`: `unreleased`, `released` or `unconfirmed`
- `next_step`: `ask`, `edit via fix` or `edit via amend`
- `edits`: `none`, or a list of the files you changed
