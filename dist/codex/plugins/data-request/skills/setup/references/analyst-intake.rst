Analyst answers intake
======================

The engineer runs setup. The analyst fills ``answers.yaml`` from the enquiry
and records research decisions in sibling ``answers.intake.json`` in that same
pass. The engineer then runs bootstrap and draft. This is not a new stage or
skill. The analyst's handoff names the branch and any questions still requiring
the requester. Research gaps discovered later return to that analyst.
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

Scope import and updates
------------------------

After the answers validation succeeds, run
``bash "$S/sqlreview.sh" intake answers.intake.json <scope-revision>``.
The read-only helper returns ``present``, ``approval_number``, ``assumptions``
and ``analyst_questions``. A missing sidecar returns ``present: false`` with
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
