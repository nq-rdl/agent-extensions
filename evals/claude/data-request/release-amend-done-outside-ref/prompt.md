---
description: 'A `done:` comment whose commit is not in the release ref does not close the handed-off part'
tags: [release, amend-gate]
runs: 3
max_turns: 10
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, Skill]
---

Context: fictional ENQ9151. Release v1.0.0 of the falls extract went to the researcher. The
analyst ran `/data-request:amend` on a three-part request. The deliverable PR shows, in order:

1. The amend record lines: `P1: call MRN URN — done`, `P2: drop AgeAtAdmit — done`,
   `P3: show the ward name in place of WardCd — handed off`.
2. The analyst's comment, which starts `amendment hand-off: 1 of 3 parts need the data
   engineer`, with one entry `part: P3`.
3. A later comment by the engineer: `done: P3 9f8e7d6`.
4. You ran `git merge-base --is-ancestor 9f8e7d6 v1.1.0` for me. It exits 1, so 9f8e7d6 is
   not in v1.1.0.

Tag v1.1.0 exists. Should release preparation for v1.1.0 go ahead? Do not draft the body yet.
The repository is unavailable here, so use only this evidence.

End your reply with one fenced `yaml` block with exactly these top-level keys:

- `release_prep`: `stopped` or `continue`
- `blocking_part`: the open part's P number, or `none`
- `p3_closed_by`: `done`, `withdrawn` or `none`, for the comment that closes P3
