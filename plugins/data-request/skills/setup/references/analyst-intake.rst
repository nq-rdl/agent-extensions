Analyst answers intake
======================

The engineer runs setup. The analyst fills ``answers.yaml`` from the enquiry
and records research decisions in sibling ``answers.intake.json`` in that same
pass. The engineer then runs bootstrap and draft. This is not a new stage: the
**Data Analyst** runs ``/data-request:intake`` to interview them through that
pass, and the **Data Engineer** runs ``/data-request:bootstrap`` to interview the
engineer on the technical scope. Intake needs no ``.sqlreview/``, so it can run
before setup. On a ``request-template`` copy, intake also renders the scaffold with
copier once the analyst approves. The analyst's handoff names the branch and any questions still requiring
the requester. Research gaps discovered later return to that analyst, who
records the answers with an intake re-run.
For code discovery during this pass, use ``/data-request:lookup`` and cite its record
in the ``rationale`` of a ``topic: codes`` decision. Cite the record, not its counts:
``answers.intake.json`` is handover tier.

The sidecar schema below is the shared contract with
``data-analysis-scaffold validate-answers answers.yaml`` and a generated child's
``pixi run python scripts/validate_answers.py answers.yaml``. Both automatically
validate a present sibling sidecar, including its approval number against the
answers file. Existing answers files without a sidecar remain valid. The helper
cannot establish human truth: actors and dates must come from actual answers,
never defaults, prose inference or the agent's identity.

Schema version 1
----------------

Required top-level fields are ``schemaVersion: 1``, ``approval_number`` matching
``answers.yaml``, ``decisions`` (array) and ``open_questions`` (array of nonempty
strings). Partial intake is valid: use questions for unresolved research
decisions. Topics need not all be represented; absence does not imply consent.
Do not copy identifiable patient data into either file.

Each decision requires a unique ``id`` matching ``[A-Za-z0-9][A-Za-z0-9_-]*``,
``topic`` (``cohort``, ``codes``, ``outcomes``, ``outputs``, ``grain`` or
``governance``), nonempty ``text`` and ``rationale``, ``confirmed_by`` (analyst
handle, never email), ``confirmed_role: analyst`` and ``confirmed_at`` (UTC
``YYYY-MM-DDTHH:MM:SSZ``). Multiple distinct decisions may share a topic, except
``grain`` occurs at most once. Roles in configuration are display labels;
they do not identify the person who supplied the answer.

For ``grain``, require ``unit``: the cohort's one-row-per-unit choice (patient,
admission, encounter, or a clearly named study unit). ``text`` states that
choice. Optional ``finer_outputs`` is an array of objects, each with unique
``name``, nonempty ``unit`` and ``description``. These describe linked detail
outputs; they do not silently replace the cohort grain. Bootstrap confirms
how source keys implement this choice with the engineer.

Ask explicitly in the same answers filling pass: "What does one row represent —
one row per <unit>, in clinical terms? Are any requested outputs finer, such as
per surgery or per ward stay?" Record the actual answer as the grain decision
and named ``finer_outputs``, not by copying ``measurement_granularity: Patient``.
A recorded patient answer is valid; an untouched default is not an answer.
If unsettled, put the clinical-unit question in ``open_questions`` rather than
inventing confirmation. Prior SQL/delivery and requested elements can support
an engineer technical proposal, not an analyst research answer. Guardrails'
``references/grain.rst`` owns evidence selection and once-only drift handling.

Optional ``decided`` is ``{by, role, at, source}``, separate from confirmation:
nonempty actor handle, role and evidence source; ``at`` uses the same UTC form
or a real ``YYYY-MM-DD`` date when the source gives only the day.
The requester who made a decision can differ from the analyst who confirmed
the intake. Omit provenance not actually known; never manufacture a dated
decision from prose. An explicit governance restriction applies immediately;
an approval identifier alone is not proof that every delivered element was
checked against approval. The analyst performs that check at delivery review.

Example::

  {
    "schemaVersion": 1,
    "approval_number": "THHSAQUIRE-9901",
    "decisions": [{
      "id": "age", "topic": "cohort",
      "text": "Include patients aged 18 and over.",
      "rationale": "The requester studies adults.",
      "confirmed_by": "analyst-login", "confirmed_role": "analyst",
      "confirmed_at": "2026-09-29T10:00:00Z",
      "decided": {"by": "requester-login", "role": "requester",
                  "at": "2026-09-28T10:00:00Z", "source": "enquiry reply"}
    }],
    "open_questions": ["Which TIA subcodes count?"]
  }

Capture the clinical cohort and age limits, code-set edges/edition, outcomes
and windows and who applies them, required identifiers/presentation and known
approval restrictions. Ask the requester through the analyst for anything
unsettled. Do not require the engineer to answer these research questions.

Schema version 2
----------------

Schema version 2 keeps every schema 1 field and adds two optional top-level
fields, ``criteria`` and ``fingerprints``. ``schemaVersion`` is ``1`` or ``2``;
``criteria`` or ``fingerprints`` under schema 1 is invalid. The scaffold release
that accepts schema 2 is a prerequisite: write ``schemaVersion: 2`` only after
the installed ``validate-answers`` accepts it, and keep writing schema 1 until it
does.

``criteria`` itemises the four free-text answers in ``answers.yaml``
(``cohort_entry_event``, ``inclusion_criteria``, ``exclusion_criteria`` and
``requested_data_elements``) into one entry per item, in the researcher's own
wording. Each criterion requires:

- ``id``: ``N``, ``I``, ``E`` or ``D`` plus a number without a leading zero, where
  the letter matches ``kind`` (``N`` for ``entry_event``, ``I`` for ``inclusion``,
  ``E`` for ``exclusion``, ``D`` for ``data_element``). Ids are unique in the
  array and never renumbered or reused.
- ``kind``: ``entry_event``, ``inclusion``, ``exclusion`` or ``data_element``.
- ``text``: nonempty, one item in the researcher's wording.
- ``confirmed_by`` (analyst handle, never email), ``confirmed_role: analyst`` and
  ``confirmed_at`` (UTC ``YYYY-MM-DDTHH:MM:SSZ``), as for decisions.

Optional fields are ``decided`` (as for decisions), ``applied_by`` and
``withdrawn``. ``applied_by`` is ``rdl`` or ``researcher`` and is allowed only on ``inclusion``
and ``exclusion``. When the request says who applies the item (for example
"project team to apply the exclusion criteria"), record it with a ``decided``
naming the enquiry as its ``source``. Ask the analyst only where the request is
unclear, and omit ``applied_by`` when it stays unknown.

``withdrawn`` is ``{reason, at}`` with a
nonempty ``reason`` and ``at`` as a UTC time or ``YYYY-MM-DD``, plus an optional
``replaced_by`` naming another criterion of the same kind. The target may itself
be withdrawn.

Rewording versus change of meaning: ask the analyst to classify every wording
change.

- A rewording keeps the ``id`` and the new ``text`` gets a fresh confirmation
  (``confirmed_by`` and ``confirmed_at``).
- A change of meaning withdraws the old criterion, with ``replaced_by`` naming the
  new one, and adds a new ``id``. A criterion that is dropped without a
  replacement is withdrawn without ``replaced_by``.

Never delete a criterion and never renumber: later stages refer to the ``id``.
The next ``id`` of a kind is one more than the highest ever used, withdrawn ones
included.

When the request states no separate entry event ("all patients with diagnosis
X"), do not invent an ``N1``. Ask which item fixes the index date, and record the
answer as a ``cohort`` decision that names that item by its ``id``, or as an open
question when the analyst cannot answer. Do not infer an index date.

``fingerprints`` records which free text the itemisation was made from. It has
exactly four keys (the same four field names), each ``sha256:`` followed by 64
lowercase hex digits. It is required when ``criteria`` is nonempty. The values are
never computed by hand: after writing ``answers.yaml``, run
``data-analysis-scaffold validate-answers answers.yaml --fingerprints`` (or
``pixi run python scripts/validate_answers.py answers.yaml --fingerprints`` in a
generated child) and store the JSON it prints as ``fingerprints``. The scaffold
owns the canonical form, so a hand-made hash would drift.

Drift warning: when the free text in ``answers.yaml`` no longer matches its
stored fingerprint, ``validate-answers`` exits 0 and warns, per field,
``intake.fingerprints.<field>: free text changed since itemisation; re-run
intake``. The warning never prints the text or either hash. Re-run intake to
itemise the change.

Example (a schema 2 addition to the schema 1 document above)::

  {
    "schemaVersion": 2,
    "criteria": [
      {"id": "N1", "kind": "entry_event", "text": "First AAA admission",
       "confirmed_by": "analyst-login", "confirmed_role": "analyst",
       "confirmed_at": "2026-10-13T01:00:00Z"},
      {"id": "E1", "kind": "exclusion", "text": "Deceased patients",
       "applied_by": "researcher", "confirmed_by": "analyst-login",
       "confirmed_role": "analyst", "confirmed_at": "2026-10-13T01:00:00Z",
       "withdrawn": {"reason": "Researcher narrowed it to death before index",
                     "at": "2026-10-20", "replaced_by": "E2"}},
      {"id": "E2", "kind": "exclusion", "text": "Died before the index admission",
       "confirmed_by": "analyst-login", "confirmed_role": "analyst",
       "confirmed_at": "2026-10-20T01:00:00Z"}
    ],
    "fingerprints": {
      "cohort_entry_event": "sha256:<64 hex digits>",
      "inclusion_criteria": "sha256:<64 hex digits>",
      "exclusion_criteria": "sha256:<64 hex digits>",
      "requested_data_elements": "sha256:<64 hex digits>"
    }
  }

Diagnostics name the path only, as ``intake.criteria[n].id: invalid or missing``,
and never the value.

Scope import and updates
------------------------

After the answers validation succeeds, run
``bash "$S/sqlreview.sh" intake answers.intake.json <scope-revision>``.
The read-only helper returns ``present``, ``approval_number``, ``assumptions``
and ``analyst_questions``. For a schema 2 sidecar it also returns ``criteria``
and ``fingerprints``, copied verbatim (``[]`` and ``null`` when the sidecar has
none); schema 1 output is unchanged. A missing sidecar returns ``present: false`` with
empty arrays. Invalid fields fail with exit 4 without exposing values.

Imported scope IDs are ``A-intake-<id>``; reserve that prefix. Items are
assumptions with null SQL location, the analyst's original actor/date, and the
current scope ``confirmed_revision``. ``upstream`` contains ``source:
analyst-intake``, ``file`` (stable source filename, never a workstation path),
``intake_id``, ``approval_number``, ``role: analyst``
and ``topic``; grain metadata and optional ``decided`` are preserved.
Questions become strings prefixed ``Analyst question:`` so legacy renderers and
schemas remain readable.

Optionally pass the draft as a third argument to return a merged scope JSON.
Use a separate temporary output path; never redirect over the input draft.
Merge by ID; an identical imported item is kept once. A collision, changed
answer/provenance (including SQL location), wrong revision or conflicting
approval fails rather than replacing engineer work. Existing imported items'
approval IDs must match even when the scope lacks a document-level approval.
The merge records sidecar-owned strings in ``intake_questions`` and replaces
only those strings on refresh, including when the new question list is empty.
Other technical and analyst questions stay. Preserve ``intake_questions`` in
update drafts; for manual imports, record only the sidecar-owned questions.
For legacy drafts without ownership metadata, identify the old sidecar's
questions with the analyst and seed that array before refresh. Do not assume
every ``Analyst question:`` string came from the sidecar.
Compare removed intake IDs separately: route any
change/removal to the analyst for a recorded answer before dependent work.
Updates keep unchanged confirmed items through ``carryforward``; its ``set``
now includes existing upstream and decision provenance. Never rebadge analyst
confirmation as engineer confirmation. A new analyst answer may be imported
at the new revision; unchanged items retain their original confirmation via
carryforward.
