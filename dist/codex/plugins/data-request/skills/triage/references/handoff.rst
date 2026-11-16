Hand-offs
=========

Read this in co-development before fulfilment work, when a request's library
work goes to spec-kit, and when a request's deliverable PR is ready for review.
Observed in September 2026.

Communication channel
---------------------

The data-request skills cite this section. It applies in every mode.

* **The deliverable PR is the channel.** Write each hand-off, send-back, analyst
  question, flagged decision, engineer reply and status update on the deliverable
  PR. Address it to the person. A question about a review line can be a review
  comment on that line.
* **The service-desk request issue is read-only for agents.** Read it for the
  request text, the approval and the enquiry number. Never comment on it, label it,
  edit it or move its card. General authorisation, such as "yes, do that", does not
  change this. The human makes every service-desk change.
* **The child tracking issue gets no hand-off.** You can suggest a one-line link to
  the PR. Post that link only when the human asks for it.
* **Board moves stay with the human.** List each card to move, its board and its
  target state. Do not move cards.

Keep these states separate in each PR comment: progress, a request for human
confirmation, an operator run, analyst acceptance and publication. A progress note
does not ask for confirmation. Analyst acceptance does not publish the release.

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

     {
       "decision": "generativeMode",
       "value": "direct",
       "by": "engineer-handle",
       "at": "2026-11-04T09:30:00Z",
       "scope": "nq-rdl/query-builder"
     }

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

1. **Gate.** The PR stays a draft through this step. Continue only when its CI is
   green on the checked head commit (read the run for that SHA, not an older one), and its
   SQL review status is ``current``. Match the review to the SQL that actually ran,
   using the recorded run commit and SQL fingerprint, not just the current SQL in the PR.
   ``release.sh evidence`` reads review records from the working tree, not the PR, and
   the reviewed SQL from git at the ``git_commit`` of each record. Fetch the checked PR head SHA from GitHub and its commit locally; never
   substitute local ``HEAD``. For every review used in the evidence, set ``SLUG`` to
   its slug and ``PR_HEAD`` to that checked SHA, then run from the request project root:

   .. code-block:: bash

     for name in review.json; do
       path=".sqlreview/reviews/$SLUG/$name"
       # Compare the committed bytes directly; no temporary copy to clean up.
       if ! git cat-file -e "$PR_HEAD:./$path" 2>/dev/null ||
          ! git show "$PR_HEAD:./$path" | cmp -s - "$path"; then
         printf 'Stop: %s is absent or differs at checked PR head %s\n' "$path" "$PR_HEAD" >&2
         exit 4
       fi
     done

   Missing or differing records stop the hand-off, including uncommitted, untracked
   or locally committed but unpushed reviews. Retain any differing review draft and
   stop for the engineer to complete its unpublished work. Run
   ``bash "$S/release.sh" evidence --no-amend-hold "<run commit>"`` with ``S`` set to the installed
   setup scripts only after these checks pass. The flag stops the hand-off by the engineer from
   being held by a handed-off amend part: the script then never exits 11 and
   prints each open part as an ``amend note:`` on stderr. This mode verifies no commit, so it needs
   no fetch. Where a later step needs one, use the command that ``release.sh fetch-command``
   prints. It names the project root with ``-C``, so it runs from any directory. Name those notes in the hand-off as open delivery gates. The release run keeps the strict hold. Any ``changed``, ``missing-at-ref``,
   ``unreviewed``, ``unavailable`` or invalid review, or unproven run provenance
   stops the hand-off. A header-only
   result needs proof that only the leading comments differ. Compare the run manifest
   and maintained pipeline too: a matching committed file alone does not prove it ran.
   Confirm DVC pointers and their corresponding objects are pushed, and that UAT sections
   1 to 3 are recorded for this run. Missing evidence is a failed gate, never a passed check.
   ``current`` only means the SQL bytes match the reviewed SQL: also confirm that
   ``/data-request:analyse`` re-ran
   (with ``--reconfirm-all``) after any pre-release logic change. Name every
   open delivery gate, including known governance restrictions. Flag approval-sensitive
   requested outputs in at most one limitation, plus known restricted fields and flagged
   decisions for analyst review. The data analyst checks the delivered elements against
   the approval before release. An unchecked approval does not by itself prevent review;
   a known restriction remains a release gate. When the run-evidence or PR gate fails,
   report which part failed and stop. Re-read the PR head before each later step. If it
   changed, recheck the gate on the new SHA. Without ``gh``, reading CI runs can need
   the GitHub MCP Actions toolset; if it is not enabled, say so.

   **Known CI failure.** A red check passes the gate only when a waiver in the
   ``gate_waivers`` of the ledger names it for the checked head. Read the waivers with
   ``bash "$S/sqlreview.sh" ledger waivers "$TICKET" "$PR_HEAD"``, with ``TICKET`` set
   to the ticket of the entry. A ``waived`` row names the check, the login in ``by``, the
   date and the source comment. Open that comment.
   Confirm that its author is the login in ``by`` and that it names the check and the head.
   A ``lapsed`` row is a waiver for another head, and it does not pass the gate.
   A new failure that no waiver names stops the hand-off. Never write a waiver on your own.
   Record one only after the human writes the waiver comment on the deliverable PR.
   Never write or post that comment for the human, whatever the instruction.
   ``ledger.rst`` gives the waiver fields.
2. **Refresh** the PR title and body so that they describe the current outputs, run plan
   and open gates. Draft the new text for the human, or write it on their explicit
   instruction.
   Then check output coverage. Every output that an ``-- @extract:`` marker names in the
   reviewed SQL must appear in the runbook outputs, the data dictionary and the UAT
   checklist.
   Each must show its delivery kind (sheet, file or internal). A missing or extra output stops
   the hand-off. Name each such output and the document that omits it.
3. **Record** the hand-off in the ledger before the comment: PR, the checked head SHA,
   reviewer, board state ``pending`` and date, with ``stage: handoff``. Commit and push the
   ledger on the agreed branch. The ledger commit moves the PR head. Confirm with
   ``git diff --name-only "$PR_HEAD" "$NEW_HEAD"``, with ``NEW_HEAD`` set to the new head
   SHA, that it changed only ``.sqlreview/ledger.json``. If it did, the gate result and
   the waivers read at the checked head also hold for the new head. A ``ledger waivers``
   run for the new head shows them as ``lapsed``, because each waiver names the checked
   head. That is expected, and no new waiver is needed. Any other change needs the gate again. The comment then names the head that
   includes the ledger commit, so the head it names does not move.
4. **Ready.** The human marks the PR ready for review. This takes it out of draft. Ask
   for it when steps 1 to 3 pass. Mark it ready yourself only on an explicit
   instruction from the human.
5. **Assign** the PR to the reviewer the human names. Read ``roles.analyst`` from
   ``.sqlreview/config.json`` for the receiving role, not the login of a person; if missing,
   ask for the role and reviewer. Never guess a reviewer. Re-resolve the child
   repository through the API before this write.
6. **Comment** on the deliverable PR, addressed to the reviewer: what is
   handed over, run commit, the checked head SHA and the head that includes the ledger
   commit, review slugs/revisions and SQL fingerprints,
   counts-only QA, links to the run manifest, DVC pointers and UAT evidence, open questions,
   flagged decisions, known governance restrictions and the limitations the requester
   must hear. For each real technical choice include ``Engineer decision (<login>, <date>),
   flagged for the data analyst``, its rationale, SQL location and evidence;
   preserve original decision provenance, separate from later confirmation.
   List agent-applied technical defaults separately, never as human decisions.
   Include offered extras (not built), not additional unrequested extracts.
   List each waiver in the hand-off comment with its check, ``by``, date, issue and source.
   Keep row-level data, identifiers and small cell counts out. This PR comment is the
   hand-off. Do not post it on the child issue or the service-desk issue. Draft it for
   the human, or post it when the human authorises that post.
7. **Move** (human only): list the child tracking issue card and the service-desk
   request issue card, each to **In-Review** on the Service Desk Request Tracking
   project board. The human moves them. Make no write to service-desk. When the human
   reports the move, update the board state in the ledger record. That commit moves the
   head again. Check as in step 3 that it changed only ``.sqlreview/ledger.json``, and tell the
   reviewer the new head.

Steps 2 to 6 each write only on an explicit instruction from the human. Step 7 is never an agent
write, whatever the instruction. In triage-only mode, post nothing: return the
paste-ready PR comment, the new PR title and body, the reviewer to assign, and the list of
board moves (card, board and target state) for the human.
