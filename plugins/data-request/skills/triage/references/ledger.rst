Triage ledger
=============

Read this when you create, update or resume the ledger. It is what lets a
multi-request session stop and resume without repeating completed stages.

Where it lives
--------------

The ledger must be durable: a file in a repository, a tracking issue body or a
project field that the human names. A session scratchpad disappears with the
session and does not count. In triage-only mode, return the entries as text for
the human to store. In co-development mode, write them only to the agreed
location.

When co-development starts and no location is agreed, ask once and propose the
child repository's tracking issue body. Until the human agrees a location,
return the full entries as text, as in triage-only mode, after each stage that
changes them. Do not pick a location yourself: every candidate is a write that
needs the human's instruction.

Entry fields
------------

Keep one entry per request:

.. code-block:: yaml

   ticket: rdl-service-desk/service-desk#903
   enquiry: ENQ9003
   approval_as_written: THHSAQUIRE9903
   approval: THHSAQUIRE-9903
   repo: rdl-service-desk/THHSAQUIRE-9903
   branch: triage/903
   owner: person or worker currently writing to the branch
   stage: validate          # intake, map, draft, validate, analyse, lift, report, review or parked
   stages_done: [intake, map, draft]
   evidence_revision:       # what was read, so a newer revision is noticed
     service-desk#903: last comment date read
     THHSAQUIRE-9903: commit
     query-builder: tag or commit
   decisions:
     - date: 2026-09-21
       who: GitHub login of the human who decided, never an email address
       decision: one sentence
       source: comment or PR link, or "unlinked (verbal)" until a written comment exists
     # spec-kit direct mode, in the exact shape /rdl-team:workflow reuses:
     - {"decision": "generativeMode", "value": "direct", "by": "<who>", "at": "<ISO time>", "scope": "<owner/name>"}
   blockers:
     - class: dependency
       detail: one sentence
   depends_on:
     - nq-rdl/query-builder change merged and released
     - child re-pinned, then scope re-bootstrapped
   next_action: one action and its owner
   handoff:                 # set by the hand-off to review
     pr: rdl-service-desk/THHSAQUIRE-9903#4
     head_sha: commit the gate was checked on
     reviewer: login the human named
     board_state: In-Review  # child issue and service-desk issue
     date: 2026-09-24
   verification:
     status: unverified     # unverified, partial or verified
     commands: [commands actually run, with results]
     at: 2026-09-23

Rules
-----

* Date every decision and record who made it. A business decision needs a named
  human; an agent never records itself as the decider.
* A verbal decision stays ``unlinked (verbal)`` until the decider writes a dated
  comment; then replace the source with its link.
* ``evidence_revision`` records what you read. When a later read shows a newer
  revision, re-check the affected stage before continuing.
* To resume, confirm that each completed stage's artefact still exists at its
  recorded revision (the commit on the branch, the scope revision, the PR), then
  continue from the first stage not done. Re-run a completed stage only when its
  evidence moved.
* ``depends_on`` records cross-repository order. One request waited on a
  query-builder change that had to merge and release before the child could
  re-pin and re-bootstrap its scope. Link a lift ledger entry to the release that
  unblocks it.
* For delegated stages, record the worker and the model by the name the host
  reports.
