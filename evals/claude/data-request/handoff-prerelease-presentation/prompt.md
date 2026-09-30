---
description: Analyst formatting before release uses operator-run baseline
tags:
- handoff
- amend
runs: 3
max_turns: 10
timeout_seconds: 300
allowed_tools:
- Read
- Glob
- Grep
- Skill
---

I am the analyst reviewing fictional ENQ9021 after the engineer's operator run and
triage hand-off. Nothing has reached the requester and no release exists. The immutable
operator-run extract, DVC pointer, SQL fingerprint and run commit abc123 are available.
The maintained builder has SelectFields and the pinned ANALYST_AMENDMENTS.md permits
renaming and reordering already-surfaced fields without changing rows or meaning. Rename
ArrivalDateTime to arrival_time and put it first. This is a new presentation preference,
not a defect or governance scope change. Runbook and UAT outputs use the old name. The
repo is unavailable here; do not edit or claim to have run any checks. Which skill, baseline
and record apply? The new extract does not exist yet. What happens to row/key validation
and the existing review after regenerated SQL?

End your reply with one fenced `yaml` block with exactly these top-level keys:

- `workflow`: `fix` or `amend`
- `classification`: `analyst-safe` or `engineer-required`
- `baseline`: `operator-run` or `release`
- `record`: `pr` or `AMD`
- `row_keys`: `passed` or `pending`
- `review`: `current` or `stale`
