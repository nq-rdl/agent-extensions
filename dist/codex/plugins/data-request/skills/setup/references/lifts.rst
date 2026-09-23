Lift ledger (schema 2)
======================

The per-slug record has an independent ``lifts.json`` beside ``scope.json`` and
``review.json``. This avoids reopening the handoff review while drafting. Use the
same ``slug`` and ``sql_path`` binding for pipeline paths of any extension; old
SQL slugs remain unchanged. Schema-1 scope/review files stay readable. New
scope/review documents may use schema 2 without changing their confirmation rules.

Candidate capture is silent. Initialise a missing record store with
``sqlreview.sh init`` (non-destructive); never replace existing config or templates
mid-draft. Use ``slug PATH`` and write ``reviews/SLUG/lifts.draft.json`` with:

::

  {
    "schemaVersion": 2, "kind": "lifts", "slug": "pipeline.py",
    "sql_path": "pipeline.py", "revision": 1, "recurring": false,
    "lifts": [{
      "id": "LIFT-1", "revision": 1,
      "need": "Required composition",
      "library": "nq-rdl/query-builder-plugins", "pinned_version": "v0.1.1",
      "looked_in": [{"path": "qb_plugins/iemr/resolver.py", "revision": "v0.1.1"},
                    {"path": "tests/test_resolver.py", "revision": "v0.1.1"}],
      "shortfall": "Observed gap after inspecting this pin",
      "workaround": {"file": "pipeline.py", "lines": [10, 20]},
      "classification": null, "status": "candidate", "issue_url": null,
      "confirmed_by": null, "confirmed_at": null, "confirmed_revision": null
    }]
  }

The example paths are placeholders: cite only files actually inspected. The
workaround range may identify the planned insertion before writing; reconcile it
with actual lines at close-out. ``recurring: false`` means no recurring follow-up
is authorised; set true only from explicit request/scope evidence.

Run ``publish SLUG lifts DRAFT`` before hand SQL, then ``render SLUG lifts``.
In an older project without ``templates/lifts.md``, ``render`` installs the
bundled template first (one stderr line) and never replaces an existing or
customised template; ``status`` lists missing templates with the fix command.
No published entry means no hand SQL. Classification may remain null during
capture; close-out settles it. A draft alone does not satisfy the hook.

Increment the document revision on each publish. Each entry also has a revision:
new candidates start at 1; changes to need, pin, inspected evidence, shortfall,
workaround or classification increment that entry revision. A human answer binds
``confirmed_revision`` to the entry revision. This is the same confirmation rule
as assumptions, applied to the independently evolving entry: appending another
candidate or recording an issue URL must not manufacture a refreshed answer.
Unchanged confirmed evidence retains its original confirmation; changed evidence
requires a new answer. Candidate entries have all three confirmation fields null.
Never turn a confirmed item into a candidate just to bypass reconfirmation.

Only human-confirmed entries advance from ``candidate`` to ``confirmed``. Library
entries then advance ``filed`` → ``released`` → ``recomposed``; request-specific
entries end at confirmed. Publish checks shape and evidence revisions, not whether
the human really answered or the remote issue shipped. Those claims require the
skill's evidence and human-confirmation workflow. Record ``release_evidence: {version, url}`` before released and
``recomposition_evidence: {pin, sql_sha256, review_revision}`` before recomposed.
These operational facts do not revise the confirmed need; evidence changes do.
Stable ids are never reused for a different need. Allocate ids above all ids in
both the ledger and ``history/lifts/*.json``. Publish retains each previous ledger
revision there, including entries removed after human rejection. Keep the answered
rejection and reason in the draft; removal revokes that entry's hook coverage.

Review limitations referencing a filed lift carry ``lift_id: "LIFT-n"``.
``publish SLUG review DRAFT`` verifies that their wording matches the ledger's
need and issue URL exactly. Review confirmation still binds to the whole review
revision. Publishing the ledger does not publish or confirm review limitations.
``status --json`` reports counts per lift status, including alongside an existing
review; ``move`` rebinds all three documents and removes stale renders. After a
move, reconcile workaround paths/ranges and reconfirm changed evidence.

Experimental write guard
------------------------

``config.json`` has ``guard.require_lift_for_string_sql: false`` by default.
Only an explicit JSON boolean true enables the narrow check. It detects same-line
f-strings or concatenation passed directly to ``execute``, ``executemany``,
``query`` or ``read_sql`` calls in Python/SQL files; it does not perform dataflow
analysis of separately assigned variables, multi-line builders or arbitrary SQL.
A valid published ledger entry must name the file in ``workaround.file`` and be
candidate or later. This is a reminder, not a sandbox: shell writes bypass it.
Measure false positives on three backlog enquiries before enabling it. Codex
patches pass added lines to the same check; deletions do not require a candidate.
