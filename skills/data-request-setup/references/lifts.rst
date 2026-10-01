Lift ledger (schema 2)
======================

The per-slug record has an independent ``lifts.json`` beside ``scope.json`` and
``review.json``. This avoids reopening the handoff review while drafting. Use the
same ``slug`` and ``sql_path`` binding for pipeline paths of any extension; old
SQL slugs remain unchanged. Schema-1 scope/review files stay readable. New
scope/review documents may use schema 2 without changing their confirmation rules.

Candidate capture is silent. A pipeline stage that owns the record store (setup,
bootstrap, or a writable drafting run) initialises a missing store with
``sqlreview.sh init`` (non-destructive); never replace existing config or templates
mid-draft. A mapping run never initialises the store; without one it uses
proposal-only mode (below). Use ``slug PATH`` and write ``reviews/SLUG/lifts.draft.json`` with:

::

  {
    "schemaVersion": 2, "kind": "lifts", "slug": "pipeline.py",
    "sql_path": "pipeline.py", "revision": 1, "recurring": false,
    "lifts": [{
      "id": "LIFT-1", "revision": 1,
      "need": "Required composition",
      "library": "nq-rdl/query-builder", "pinned_version": "v0.6.0",
      "looked_in": [{"path": "resolvers/iemr/resolver.py", "revision": "v0.6.0"},
                    {"path": "tests/resolvers/test_iemr_resolver.py", "revision": "v0.6.0"}],
      "shortfall": "Observed gap after inspecting this pin",
      "workaround": {"file": "pipeline.py", "lines": [10, 20]},
      "classification": null, "status": "candidate", "issue_url": null,
      "confirmed_by": null, "confirmed_at": null, "confirmed_revision": null
    }]
  }

The example paths are placeholders: cite only files actually inspected. Source
resolvers live in ``nq-rdl/query-builder`` under ``resolvers/iemr`` and
``resolvers/hbcis``; the former separate plugins package is archived. The
workaround range may identify the planned insertion before writing; reconcile it
with actual lines at close-out. ``recurring: false`` means no recurring follow-up
is authorised; set true only from explicit request/scope evidence. It does not
exclude a read-only stale check or a re-pin proposal for a build not yet delivered.

Run ``publish SLUG lifts DRAFT`` before hand SQL, then ``render SLUG lifts``.
In an older project without ``templates/lifts.md``, ``render`` installs the
bundled template first (one stderr line) and never replaces an existing or
customised template; ``status`` lists missing templates with the fix command.
No published entry means no hand SQL. Classification may remain null during
capture; close-out settles it. A draft alone does not satisfy the hook.

Read-only release stale check
-----------------------------

An entry may carry optional ``units`` evidence, a nonempty array such as::

  "units": [
    {"path": "models/appointments.py", "symbol": "Appointments", "absent_tag": "v0.6.0"},
    {"path": "models/appointments.py", "symbol": "MissingColumn", "absent_tag": "v0.6.0"}
  ]

Use the exact inspected repository-relative file and identifier (class, function
or column name) and the stable tag where it was absent. These example names are
illustrative, not library facts. Add one reference per independently missing unit;
absence of an entire file also counts. Omit ``units`` for legacy entries or
behaviour-only shortfalls that symbol presence cannot test. Adding/changing this
evidence increments the entry revision and requires reconfirmation if confirmed.

Run ``sqlreview.sh lifts-stale SLUG --tag TAG`` with authenticated ``gh``. It
returns JSON ``{slug, tag, entries}``, including every entry's ``id``, ``library``,
``result``, ``message`` and per-unit results. It reads only GET tag refs, complete
recursive trees and blob bytes from that entry's library; it never checks out,
imports or executes library code. It confirms absence at ``absent_tag`` and exact
identifier-token presence in a numerically newer stable ``v?X.Y.Z`` tag. Annotated
tags are peeled. Older/equal tags return ``not-newer``; unsupported tag forms are
rejected. No ledger, history, render, config, status, confirmation or pin is written.

``may-be-resolved`` names newly present units; ``partly-resolved`` names partial
shortfalls, leaving remaining units visible. Other results are ``absent``,
``not-newer``, ``absence-contradicted`` (present at the claimed absence tag),
``untracked`` (no unit evidence), and ``unknown`` (missing tag/access, incomplete
tree, non-regular blob or unreadable evidence). Operational errors use the helper's
normal nonzero exits; unknown remote evidence is a successful report, not a pass
on availability. A symbol token in a comment/string can produce a nudge: this is
not a language parser and never proves working behaviour or complete resolution.

Triage includes the messages without writes. Discover latest stable tags using
guardrails' shared ``references/library.rst`` policy; mixed-library ledgers need
one run per library's latest tag, using only that library's rows in each run.
Do not use a core release as evidence for the archived package. Inspect actual
behaviour, all shortfalls, approved outputs and tests before a human decides on
adoption. Candidates in undelivered builds are eligible even when nonrecurring;
already-delivered one-off extracts remain forward-only. The check never advances
the filed/released/recomposed lifecycle or authorises automatic re-pinning.

Proposal-only mode and operator probes
--------------------------------------

Use proposal-only mode when the task is read-only, when the repository cannot be
written, or when a mapping run finds no ``.sqlreview/`` (for example a planning run
before the scaffold exists). Do not run ``init`` or ``publish``. Return the
candidate entry, in the draft shape above, as text in the task output. Label it
``proposal-only`` and give the reason. A proposal-only entry authorises no hand SQL:
none is committed or run, except exempt probes, until a writable run publishes the
entry.

Operator probes are outside this gate when each probe is aggregate-only,
small-cell suppressed, bounded to a single scan, returns no patient identifier,
and records any ``NOLOCK`` or ``READ UNCOMMITTED`` use. Such probes write nothing
to the repository and feed no delivered extract. Codes they return are category or
type codes, never staff or person keys. Clinician and resource names are not
patient identifiers (guardrails, "Personal information"). A probe that returns rows
or identifiers, or that feeds an extract, is hand SQL and needs an entry.
Guardrails' ``references/performance.rst`` gives the probe design rules.

**Code-discovery probes:** ``/data-request:lookup`` probes returning only codes,
labels and counts are exempt from the hand-SQL gate only under those same
operator-probe conditions. Before proposing or reporting one, read **Probe disclosure
control** in ``${CLAUDE_PLUGIN_ROOT}/skills/guardrails/references/release.rst`` for
its floor, formatter, structural-count treatment, rare-label folding and perimeter
rules. Gate exemption is not disclosure permission. Include matched-term provenance,
not patient values, dates, identifiers or free-text results.
The exemption waives only lift capture, not engineer review of a fallback probe,
authorisation or disclosure controls. The agent never runs the lookup query;
an authorised human runs it and pastes the labelled grids back. The private lookup
record holds reviewed code evidence, not patient rows or a delivered extract.

Increment the document revision on each publish. Each entry also has a revision:
new candidates start at 1; changes to need, pin, inspected evidence (including units), shortfall,
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
