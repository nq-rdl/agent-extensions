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

     {"decision": "generativeMode", "value": "direct", "by": "<who>", "at": "<ISO time>", "scope": "<owner/name>"}

  ``by`` is the GitHub login of the human who authorised it, never an email
  address, and ``at`` is when. Record ``scope`` as the repository
  ``owner/name`` (``nq-rdl/query-builder``), or as the worktree path when a worktree for the work already exists. Keep these five
  keys exactly. The workflow reuses a decision only when ``scope`` equals the
  unit's ``physicalWorktree``; the main session translates ``owner/name`` into
  that path when it passes the decision on. Do not ask again for the same scope.
* Routing ``/speckit.*`` through another agent (Codex, a subagent) to avoid
  ``disable-model-invocation`` is not a workaround: it bypasses a gate the team
  set on purpose. Direct mode is the supported path.
* Clarify, the choice of ``analyze`` remediations and constitution changes stay
  with the human in the main session. Never edit command frontmatter.

Hand-off to review
------------------

Run this after the Data Engineer's ``/data-request:analyse``, authorised operator run
and UAT, when the deliverable PR is ready for the Data Analyst's review. The request
runbook's Delivery section must point here. The engineer hands over; the analyst
explains, accepts for release preparation, sends back or amends presentation, then
prepares and publishes the release. Never direct the engineer to release.

1. **Gate.** Continue only when the PR is out of draft, its CI is green on the
   current head commit (read the run for that SHA, not an older one), and its
   SQL review status is ``current``. Match the review to the SQL that actually ran,
   using the recorded run commit and SQL fingerprint, not just the PR's current SQL.
   ``release.sh evidence`` reads review records and snapshots from the working tree,
   not the PR. Fetch the checked PR head SHA from GitHub and its commit locally; never
   substitute local ``HEAD``. For every review used in the evidence, set ``SLUG`` to
   its slug and ``PR_HEAD`` to that checked SHA, then run from the request project root:

   .. code-block:: bash

     for name in review.json source.sql; do
       path=".sqlreview/reviews/$SLUG/$name"
       tmp="$(mktemp)" || exit 2
       if ! git show "$PR_HEAD:./$path" > "$tmp" 2>/dev/null || ! cmp -s "$tmp" "$path"; then
         rm -f "$tmp"
         printf 'Stop: %s is absent or differs at checked PR head %s\n' "$path" "$PR_HEAD" >&2
         exit 4
       fi
       rm -f "$tmp"
     done

   Missing or differing records stop the hand-off, including uncommitted, untracked
   or locally committed but unpushed reviews. Retain any differing review draft and
   stop for the engineer to complete its unpublished work. Run
   ``bash "$S/release.sh" evidence "<run commit>"`` with ``S`` set to the installed
   setup scripts only after these checks pass. Any ``changed``, ``missing-at-ref``,
   ``unreviewed`` or invalid review, a missing snapshot, or unproven run provenance
   stops the hand-off. A header-only
   result needs proof that only the leading comments differ. Compare the run manifest
   and maintained pipeline too: a matching committed file alone does not prove it ran.
   Confirm DVC pointers and their corresponding objects are pushed, and that UAT sections
   1 to 3 are recorded for this run. Missing evidence is a failed gate, never a passed check.
   ``current`` only means the SQL bytes match the reviewed snapshot: also confirm that
   ``/data-request:analyse`` re-ran
   (with ``--reconfirm-all``) after any pre-release logic change. Name every
   open delivery gate, including known governance restrictions. Flag approval-sensitive
   requested outputs in at most one limitation, plus known restricted fields and flagged
   decisions for analyst review. The data analyst checks the delivered elements against
   the approval before release. An unchecked approval does not by itself prevent review;
   a known restriction remains a release gate. When the run-evidence or PR gate fails,
   report which part failed and stop. Re-read the PR head before steps 2 to 4; if it
   changed, recheck the gate on the new SHA. Without ``gh``, reading CI runs can need
   the GitHub MCP Actions toolset; if it is not enabled, say so.
2. **Assign** the PR to the reviewer the human names. Read ``roles.analyst`` from
   ``.sqlreview/config.json`` for the receiving role, not a person's login; if missing,
   ask for the role and reviewer. Never guess a reviewer. Re-resolve the child
   repository through the API before this write.
3. **Comment** on the child repository's tracking issue: the PR link, what is
   handed over, run commit and head SHA, review slugs/revisions and SQL fingerprints,
   counts-only QA, links to the run manifest, DVC pointers and UAT evidence, open questions,
   flagged decisions, known governance restrictions and the limitations the requester
   must hear. For each real technical choice include ``Engineer decision (<login>, <date>),
   flagged for the data analyst``, its rationale, SQL location and evidence;
   preserve original decision provenance, separate from later confirmation.
   List agent-applied technical defaults separately, never as human decisions.
   Include offered extras (not built), not additional unrequested extracts.
   Keep row-level data, identifiers and small cell counts out. The child
   issue is the hand-off destination; a PR comment alone is incomplete. Draft it for the
   human, or post it when the human authorises that post.
4. **Move** both the child issue and the service-desk request issue to
   **In-Review** on the Service Desk Request Tracking project board.
5. **Record** the hand-off in the ledger: PR, head SHA, reviewer, board state and
   date.

Each write in steps 2 to 4 needs the human's explicit instruction, as any write
to service-desk does. In triage-only mode, post nothing: return the paste-ready
comment, the reviewer to assign, and the list of board moves (issue, board and
target state) for the human.
