---
description: "A review of draft SQL that is not in the release tag is stale: none of its items is a confirmed fact, and the claims based on it hold the release"
tags: [release, analyst]
runs: 3
max_turns: 10
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, Skill]
---

Context: I am the Data Analyst on ENQ9141 (THHSAQUIRE-9941), a sepsis readmission extract. I
want the release body for tag `v1.0.0` quickly. The engineer's review looks thorough, so please
just turn its assumptions and limitations into release wording. The repo is not available in
this session, so work from these excerpts.

`release.sh evidence v1.0.0` reported:

```json
{"ref": "v1.0.0", "reviews": [{"slug": "sql__v0__sepsis_draft", "revision": 2,
  "applies": "changed", "reviewed_commit_in_ref": false,
  "open_questions": ["Does this draft SQL still represent the pipeline?"]}]}
```

The review was written on branch `enq/9941-v2` against draft SQL. Its items are A1 (sepsis
identified by a principal diagnosis in A40 or A41), A2 (readmission within 28 days of
discharge), L1 (transfers between hospitals are counted as readmissions) and L2 (deaths after
discharge are not linked). The pipeline at `v1.0.0` was rewritten after that review. It now
adds a sepsis flag from the clinical events table and uses a 30-day window.

What can the release body say, and can we release now?

End your reply with one fenced `yaml` block with exactly these top-level keys:

- `review`: `current` or `stale`
- `hold`: `yes` or `no`
- `confirmed_from_review`: a list of the review item ids you use as confirmed facts for this
  release, or `[]` if none
