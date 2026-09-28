Hand-offs
=========

Read this in co-development before fulfilment work, when a request's library
work goes to spec-kit, and when a request's deliverable PR is ready for review.
Observed in September 2026.

Fulfilment
----------

* Request pipelines compose library units, and committed SQL is generated from
  them with parity coverage.
* Reusable correctness fixes belong upstream in the library, captured through
  ``/data-request:lift``.
* Re-pin a child only after the library change it needs is available; then
  regenerate and verify its SQL. Record the cross-repository order in the
  ledger's ``depends_on``.
* Open PRs as drafts by default, so that a coordinated change set cannot merge
  early.

Library work through spec-kit
-----------------------------

Library work that ``/data-request:lift`` files goes through the house-style
workflow (``/rdl-team:workflow``). Spec-kit's generated skills carry
``disable-model-invocation: true``, so in the default ``generativeMode:
"invoke"`` every ``specify``, ``plan``, ``tasks`` and ``analyze`` stage stops and
hands a ``/speckit.*`` command back to the human.

* When triage decides that an item needs library work through spec-kit, ask the
  human once, at that point, whether to authorise ``generativeMode: "direct"``
  for ``specify``, ``plan``, ``tasks`` and ``analyze``. In an agent-driven or
  cloud session, recommend direct mode.
* Record the answer in the ledger's ``decisions``, and pass it to the
  workflow's ``decisions``, in exactly this shape:

  .. code-block:: json

     {"decision": "generativeMode", "value": "direct", "by": "<who>", "at": "<ISO time>", "scope": "<repo or physicalWorktree>"}

  ``by`` is the human who authorised it and ``at`` is when. ``scope`` must equal
  the workflow unit's ``repo`` or ``physicalWorktree`` exactly; any other value,
  or a missing field, makes the workflow ask again. Do not ask again for the same
  scope.
* Routing ``/speckit.*`` through another agent (Codex, a subagent) to avoid
  ``disable-model-invocation`` is not a workaround: it bypasses a gate the team
  set on purpose. Direct mode is the supported path.
* Clarify, the choice of ``analyze`` remediations and constitution changes stay
  with the human in the main session. Never edit command frontmatter.

Hand-off to review
------------------

Run this when the deliverable PR of the selected request is ready for review.

1. **Gate.** Continue only when the PR is out of draft, its CI is green on the
   current head commit (read the run for that SHA, not an older one), and its
   SQL review status is ``current``. ``current`` only means the SQL bytes match
   the reviewed snapshot: also confirm that ``/data-request:analyse`` re-ran
   (with ``--reconfirm-all``) after any pre-release logic change. Name every
   open delivery gate, such as governance reconciliation. When the gate fails,
   report which part failed and stop. Without ``gh``, reading CI runs can need
   the GitHub MCP Actions toolset; if it is not enabled, say so.
2. **Assign** the PR to the reviewer the human names, usually the analyst who
   receives the deliverable. Never guess a reviewer. Re-resolve the child
   repository through the API before this write.
3. **Comment** on the child repository's tracking issue: the PR link, what is
   handed over, and the open gates. Draft it for the human, or post it when the
   human authorises that post.
4. **Move** both the child issue and the service-desk request issue to
   **In-Review** on the Service Desk Request Tracking project board.
5. **Record** the hand-off in the ledger: PR, head SHA, reviewer, board state and
   date.

Each write in steps 2 to 4 needs the human's explicit instruction, as any write
to service-desk does. In triage-only mode, post nothing: return the paste-ready
comment, the reviewer to assign, and the list of board moves (issue, board and
target state) for the human.
