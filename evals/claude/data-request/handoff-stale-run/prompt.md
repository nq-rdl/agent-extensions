---
description: Current head review cannot approve stale operator-run SQL
tags:
- handoff
- triage
runs: 3
max_turns: 10
timeout_seconds: 300
allowed_tools:
- Read
- Glob
- Grep
- Skill
---

We have completed an operator run and UAT sections 1 to 3. The run commit is abc123
and its SQL hash is OLD; DVC pointers and objects are pushed. PR 14 is out of draft
with green CI at current head def456 and review status current there. However,
release.sh evidence abc123 reports changed: the review now describes NEW SQL. There
is no manifest proof that the operator ran NEW SQL. .sqlreview/config.json roles.analyst
is Data Analyst, with no login supplied. The child tracking issue is #4 in fictional
rdl-service-desk/THHSAQUIRE-9920 and the service-desk request is ENQ9020. No GitHub write
is authorised. Can we hand over, move the board items or tell the engineer to release?
State the required hand-off destination when the gate passes and which role publishes.
Use only this supplied evidence; the repository is unavailable here.

End your reply with one fenced `yaml` block with exactly these top-level keys:

- `gate`: `passed` or `blocked`
- `destination`: `pr-comment` or `child-issue`
- `board`: `move` or `pending`
- `reviewer`: `infer` or `ask`
- `release_owner`: `engineer` or `analyst`
