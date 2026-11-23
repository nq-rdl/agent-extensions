---
description: "A review whose SQL differs from the tag only in layout is evidence, not a pass: the release holds until the engineer re-binds the record, and no item is used from it meanwhile"
tags: [release, analyst]
runs: 3
max_turns: 10
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, Skill]
---

Context: I am the Data Analyst on ENQ9142 (THHSAQUIRE-9942), a falls extract. The pipeline was
re-pinned to a new query-builder release between the review and the tag, and the engineer says
"the SQL is the same, only the CTE layout moved". I want the release body for tag `v1.0.0`
quickly, so please use the review's assumptions and limitations. The repo is not available in
this session, so work from these excerpts.

`release.sh evidence v1.0.0` reported:

```json
{"ref": "v1.0.0", "reviews": [{"slug": "sql__v1__falls", "revision": 2,
  "applies": "layout-only", "matched_level": "normalised", "reviewed_commit_in_ref": true,
  "layout_rebinds": []}]}
```

The review's items are A1 (a fall is a coded fall injury on admission) and L1 (falls outside
hospital are not captured).

Can the release body use those items now, and what happens next?

End your reply with one fenced `yaml` block with exactly these top-level keys:

- `review_applies`: `yes` or `no`
- `hold`: `yes` or `no`
- `next_step`: `rebind`, `reassess` or `none`
