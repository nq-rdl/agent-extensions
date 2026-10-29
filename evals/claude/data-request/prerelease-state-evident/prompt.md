---
description: "Every release signal agrees the extract is unreleased: say so in one line and ask nothing"
tags: [amend, pre-release, release-evident]
runs: 3
max_turns: 10
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, Skill]
---

Context: the enquiry repo for ENQ9131 was generated from data-analysis-scaffold. I checked the
repo and the deliverable PR for you:

- there is no `data/Released/` folder;
- `git tag --list` prints nothing, and there are no published releases;
- there is nothing under `data/Review/`;
- the engineer's last comment on the deliverable PR says "operator run done, waiting on the
  column names before we hand it over to the researcher";
- the service-desk issue says "extract in progress, nothing sent yet".

The researcher wants the `AdmitDt` column, which the extract already shows, called
`admission_date`. The request SQL `sql/ward_request.sql` is generated from
`src/cohort/ward.py`. The repo is not available in this session, so do not edit anything.
Tell me the release state and what you would do next.

End your reply with one fenced `yaml` block with exactly these top-level keys:

- `release_status`: `unreleased`, `released` or `unconfirmed`
- `questions`: the number of questions you ask me about the release state
- `next_step`: `ask`, `edit via fix` or `edit via amend`
