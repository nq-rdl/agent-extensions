Skill review worker outline
===========================

Read this reference when delegating a second opinion or fulfilling an explicit
subagent request. Use the host's available worker mechanism; this file does not
register a custom agent type. Inherit the session model unless a model is selected
by the user or applicable project instructions.

Handoff
-------

Give the worker the structured session summary, resolved paths to the touched
skills and contributor instructions, the owning SKILL.md, and the review output
path. Include user corrections, tested API names or versions, and open questions;
the worker cannot infer the conversation from a file path.

Worker task
-----------

Read each touched SKILL.md and changed resource. Cross-check the contributor
instructions and session evidence. Identify actionable bugs, missing constraints,
incorrect APIs, and valuable corrections not yet captured in the skill.

Return severity-grouped findings (CRITICAL, MODERATE, MINOR), each with a file
location, evidence, and a suggested correction. State validation limits rather
than claiming unperformed tests. Save that review to the assigned path and return
its full text. Review target skills read-only; the report is the only write.
Do not delegate further or apply fixes without an explicit assignment.

Completion
----------

Wait for the review before presenting final findings. The parent checks evidence
and highlights the most consequential corrections. If workers are unavailable,
review directly unless the user requires an independent worker; then report the
limitation. Do not portray a self-review as an independent review.
