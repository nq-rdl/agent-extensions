Triage ledger (schema 1)
=======================

Read this before creating, updating or resuming a ledger. It is durable session
state, independent of SQL-bound scope/review records and the lift ledger.
A chat reply or temporary scratchpad alone does not count as persistence.

Where it lives
--------------

In co-development, the default is the selected child's ``.sqlreview/ledger.json``
on the agreed working branch, one entry per fully qualified service-desk ticket.
No service-desk write is needed. Once the human agrees work on that child branch,
use this default without asking them to invent a location. It needs no setup/init.
Writing, committing or pushing still stays within the agreed task and branch;
never write on another owner's branch or move ownership merely to resume.
If there is no writable agreed branch yet, use the session file instead.

In triage-only mode, return the entries as text **and** save with ``--session``.
The default session file is
``${XDG_STATE_HOME:-$HOME/.local/state}/rdl-agent-extensions/data-request/ledger.json``.
This is a narrow session-file exception: it writes only local user state and
private staging files, not children, libraries, service-desk, issues or projects.
It does not authorize child work. Do not put XDG_STATE_HOME inside a repository.
Disclose the actual saved path and say nothing was posted. If the helper, jq or
persistent user state is unavailable, return the full entries and report that
persistence failed; never claim a save. A later session must offer this saved
entry to the human for loading, not silently overwrite it with fresh guesses.

Commands
--------

``S`` is the installed setup skill's scripts directory. Use the host's installed
path, not a path in the user's child repository. In the child root (or with
``SQLREVIEW_ROOT`` explicitly set to that child)::

  bash "$S/sqlreview.sh" ledger get 'rdl-service-desk/service-desk#903'
  bash "$S/sqlreview.sh" ledger set 'rdl-service-desk/service-desk#903' /private/staging/entry.json
  bash "$S/sqlreview.sh" ledger check .sqlreview/ledger.json
  bash "$S/sqlreview.sh" ledger --session get 'rdl-service-desk/service-desk#903'
  bash "$S/sqlreview.sh" ledger --session set 'rdl-service-desk/service-desk#903' /private/staging/entry.json
  bash "$S/sqlreview.sh" ledger get 'rdl-service-desk/service-desk#903' --against /private/staging/current-revisions.json

``set`` takes one JSON entry, not the whole store. The wrapper is
``{"schemaVersion":1,"entries":[...]}``. Every entry and the existing store must
pass the jq schema before replacement. Duplicate tickets, malformed evidence,
missing completion metadata and email-like identities fail with exit 4.
``get`` never creates or repairs files; missing store/ticket exits 6, unsafe paths
or I/O/lock failures exit 2. A malformed store is an error, not a fresh start.
``set`` locks before reading the store, preserves other tickets, writes a private
temp file beside the final file and renames it atomically. Failure preserves the
old store. A busy ``.ledger.lock`` fails: reload, reconcile and retry; after a
crash, remove a stale lock only after verifying that no writer remains.
Do not directly Write/Edit the final store.

Entry fields
------------

Example entry (the same shape is returned as text; convert to JSON for ``set``):

.. code-block:: yaml

   ticket: rdl-service-desk/service-desk#903
   enquiry: ENQ9003
   approval_as_written: THHSAQUIRE9903
   approval: THHSAQUIRE-9903
   repo: rdl-service-desk/THHSAQUIRE-9903
   branch: enq/9003
   owner: engineer-handle
   stage: validate
   stages_done: [intake, map, draft]
   evidence_revision:
     ticket: '2026-09-29'    # actual last body/comment revision read
     mapping: query-builder-v1.2.3
     sql: child-commit-sha
   stage_evidence:
     intake: {sources: [ticket], artifacts: []}
     map: {sources: [ticket, mapping], artifacts: []}
     draft:
       sources: [ticket, mapping, sql]
       artifacts:
         - {path: sql/cohort.sql, sha256: '<64 lowercase hex characters>'}
   decisions:
     - decision: Use supplied cohort
       decided: {by: analyst-handle, role: Requester, at: '2026-09-29', source: 'unlinked (verbal)'}
     # spec-kit direct mode, in the shape /rdl-team:workflow reuses:
     - {decision: generativeMode, value: direct, by: engineer-handle, at: '2026-09-29', scope: nq-rdl/query-builder}
   blockers:
     - {class: dependency, detail: Waiting on the resolver release}
   depends_on: [query-builder change merged and released, child re-pinned then scope re-bootstrapped]
   next_action: 'engineer-handle: validate'
   handoff:                 # optional until review handoff exists
     pr: rdl-service-desk/THHSAQUIRE-9903#4
     head_sha: commit-the-gate-was-checked-on
     reviewer: reviewer-handle
     board_state: In-Review
     date: '2026-09-29'
   verification: {status: partial, commands: ['mapping check: pass'], at: '2026-09-29'}

Required: ticket, enquiry, stage, stages_done, evidence_revision, stage_evidence,
decisions, blockers, depends_on, next_action and verification. Repo, approval,
branch, owner and handoff may be omitted until known; never invent them.
For unresolved intake use ``stages_done: []`` and ``stage_evidence: {}``.
Every completed stage needs a nonempty ``sources`` list naming recorded revision
keys and an ``artifacts`` list (empty only when no local artifact is expected).
Paths are child-relative, traversal-free, non-symlink paths; digests are SHA-256.
Allowed stages: intake, bootstrap, map, draft, validate, analyse, lift, report,
review, fix, amend, release, parked. Verification status is unverified, partial or
verified; commands record only actual runs and their results.

Decisions use #434/#437's independent ``decided: {by,role,at,source}`` origin;
``role`` is a display label, ``by`` a human handle, not a confirmer inferred from
config. Preserve date-only precision; never invent midnight. Legacy
``{date,who,decision,source}`` and spec-kit direct-mode records remain accepted.
Business decisions require a human origin; never promote an engineer technical
choice into an analyst research answer. A verbal decision stays explicitly
``unlinked (verbal)`` until written evidence is supplied.

Resume first, selective recheck
-------------------------------

1. Load the child's stored entry before assessing its stages. In triage-only
   mode read the child without modifying it, and offer the user-state entry too.
   If both exist and differ, show the conflict (including branch/owner), ask which
   to resume, and reconcile explicitly; no blind precedence or automatic import.
   A missing ledger allows fresh triage; invalid/unsafe evidence is a blocker.
2. Probe capabilities and read current ticket/amendment, branch/PR and governance
   metadata every session. This is an evidence freshness check, not a rerun of
   every stage. Populate current-revisions.json with actual current source values;
   missing keys mean unavailable evidence, never copy old values to look current.
3. ``get --against`` returns ``{entry,recheck,unchanged}``. It compares each done
   stage's source revisions and checks its artifacts' current existence/digest.
   Only changed/unavailable sources or missing/stale artifacts mark that stage
   for recheck. Run from the correct child root for session entries too. Added
   sources must be attached to affected stages explicitly; the helper cannot
   infer dependencies. Downstream stages must list all sources they rely on.
4. Recheck those affected stages, preserve unchanged completions, then continue
   from the first unfinished stage with its recorded owner and next action.
   Confirm the branch still exists and its owner still permits writes; a matching
   revision is not authorization. Never take over another writer's worktree.
5. Read live ``questions.json`` (when present) every resume: #437 question closure
   does not advance scope/review revisions. The ledger is not a second question
   store and must not reopen closed questions or invent confirmation. Record its
   current evidence separately when a stage depends on it.
6. Save after each state-changing stage and before handoff. ``depends_on`` keeps
   the cross-repository merge/release/re-pin/re-bootstrap order; link a lift to
   the release that unblocks it. For delegation, record the actual host-reported
   worker/model in the handoff evidence. Ledger verification is not SQL approval.
