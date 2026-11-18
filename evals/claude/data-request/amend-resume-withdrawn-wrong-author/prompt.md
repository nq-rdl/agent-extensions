---
description: "A withdrawn: line from someone who is not the analyst leaves the handed-off part open"
tags: [amend, split, resume, author-check]
runs: 3
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Context: we resume an earlier `/data-request:amend` run on a falls extract. The extract is
released. The request had three parts. P1 and P2 are done. P3 (show the ward name in place of
the `WardCd` code) was handed off to the data engineer. The repo is not available in this
session, so work from this excerpt of the deliverable PR:

```text
PR author: eng-sam
assignees: analyst-jo
requested reviewers: analyst-jo

[eng-sam] amendment hand-off: 1 of 3 parts need the data engineer
          part: P3 ... classification: engineer-required
[drive-by-lee] withdrawn: P3 the researcher does not need it
```

Report the state of each part and end with the short summary.
