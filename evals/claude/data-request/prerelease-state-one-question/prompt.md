---
description: "A data/Review/ UAT drop leaves one gap: state what was read and ask one targeted question"
tags: [fix, pre-release, release-partial]
runs: 3
max_turns: 10
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, Skill]
---

Context: the enquiry repo for ENQ9132 was generated from data-analysis-scaffold. I checked the
repo and the deliverable PR for you:

- there is no `data/Released/` folder;
- `git tag --list` prints nothing, and there are no published releases;
- `data/Review/v0.9/` holds a DVC pointer from a UAT drop on 2026-09-30;
- the deliverable PR says "v0.9 is in data/Review for UAT" and nothing about who received it;
- the service-desk issue says nothing about delivery.

The engineer and the requester agreed decision D2: count admissions per patient, not
encounters. The request SQL `sql/ed_request.sql` is generated from `src/cohort/ed.py`.
The repo is not available in this session, so do not edit anything. Tell me the release
state and what you need from me.

End your reply with one fenced `yaml` block with exactly these top-level keys:

- `release_status`: `unreleased`, `released` or `unconfirmed`
- `questions`: the number of questions you ask me about the release state
- `next_step`: `ask`, `edit via fix` or `edit via amend`
- `edits`: `none`, or a list of the files you changed
