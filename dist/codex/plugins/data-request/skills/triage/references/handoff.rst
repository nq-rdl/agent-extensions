Hand-offs
=========

Read this when a request's library work goes to spec-kit, and when a request's
deliverable PR is ready for review. Observed in September 2026.

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
* Record the answer as a ledger decision: who gave it, when, and the repository
  or worktree it covers. Pass it to the workflow; do not ask again for the same
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
   SQL review status is ``current``. Name every open delivery gate, such as
   governance reconciliation. When the gate fails, report which part failed and
   stop.
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
