Committed SQL source
====================

.. contents::
   :local:

Review records store hashes and a commit, never SQL. ``scope.json`` and
``review.json`` hold ``sql_sha256``, ``sql_body_sha256``, ``git_commit`` and
``git_dirty: false``. Nothing writes ``source.sql``, ``scope.source.sql`` or
``history/*.sql`` under ``.sqlreview/``. The request SQL stays committed in git,
so git history holds every reviewed revision. This applies to every SQL path,
whatever ``sql/provenance.json`` says produced it.

Fingerprint
-----------

``fingerprint`` refuses uncommitted changes outside the review store. The store
exemption covers ``reviews/``, ``releases/``, ``templates/``, ``ledger.json`` and
``.gitignore``. The SQL must be a regular file committed at ``HEAD``. The
recorded ``git_commit`` therefore identifies the SQL and every other input, such
as builders, configuration and pins. A later non-SQL change shows as a path
difference from that commit. ``release.sh evidence`` lists these paths.

Reading old SQL
---------------

Diff, carry, remap, explain and release read old SQL with
``git show <git_commit>:<sql_path>``. The bytes go to a private temporary file
outside the repository. The helper checks the full ``sql_sha256``, then the
optional ``sql_body_sha256``, before any comparison. Exit 6 means git cannot
supply that SQL or its SHA differs. Exit 2 means an operational or path failure.
Both require resolution. Never infer "unchanged" or "SQL absent" from them.
Replacement refs and grafts are refused.

``status`` compares the recorded ``sql_sha256`` with the SQL in the working
tree. It runs no git command, so uncommitted edits show as ``stale`` and never
block it. ``delta``, ``impact``, ``carryforward``, ``carryover`` and ``remap``
are read-only. They compare the old SQL from git with the working-tree SQL and
do not need a clean tree. ``fingerprint``, ``publish`` and ``snapshot`` need a
clean tree.

``materialize SLUG scope|review REVISION OUTPUT`` writes the SQL of that exact
recorded revision to an absolute temporary path outside the repository. The
caller deletes it. It reads ``history/<kind>/<revision>.json`` or the matching
published record.

Records and history
-------------------

``publish`` keeps each previous human revision at
``history/<kind>/<revision>.json``. A header-only update keeps the original full
SHA, commit and confirmations. It appends the new header hashes and commit to
helper-owned ``header_revisions``. ``snapshot`` verifies the published review
and writes nothing. A scope framed before SQL exists keeps ``sql_sha256: null``.

Legacy records with a clean immutable commit and a full hash work unchanged.
Records with a dirty or null commit report ``no-baseline`` and need
reassessment. Existing SQL copies under ``.sqlreview/`` are removed by the
maintainer cleanup in ``docs/sqlreview-snapshot-cleanup.md`` of the
agent-extensions repository. Fresh ``init`` writes ``.sqlreview/.gitignore``,
which ignores those legacy paths.
