Settle the output grain from evidence
=====================================

``answers.yaml`` (or a child's ``.copier-answers.yml``) is configuration, not
proof of a human answer. In legacy children, ``measurement_granularity: Patient``
often means nobody changed Copier's default. The bare default is never evidence
of the requested grain. Report ``Grain unconfirmed (answers says Patient)`` when
no actual recorded analyst answer or confirmed scope supports it. Other bare
values, including ``Admission``, missing values and ``unspecified``, also need a
source. A genuinely confirmed patient grain remains valid; do not override it
merely because its spelling matches the old default.

Triage/map: propose and cite, do not invent confirmation
------------------------------------------------------

Read the following before proposing the main output's clinical unit:

1. The analyst's ``answers.intake.json`` grain decision and any later recorded
   answer or scope amendment. Quote the clinical ``one row per <unit>`` wording,
   preserve its confirmer/date and ``decided`` origin, and include its source.
2. A prior version's SQL or delivery, when present. Read the output manifest,
   selected keys, joins and grouping; cite the path and revision or release tag.
   The prior SQL is evidence of intent, not correctness: verify its key/grain and
   whether the current request changes it. Do not deduplicate a delivered
   admission/presentation extract to patients because answers says Patient.
3. The requested data elements and their source semantics. Cite the enquiry
   element and the metadata/SQL that establishes its unit. A patient identifier
   is a linkage key, not proof of one row per patient. A source table's grain is
   not automatically the delivered file's grain.

Where sources conflict, show both and route the unsettled research choice to
the analyst. Where none establishes a unit, report it as unknown; for a request
that refers to earlier SQL, read the prior SQL before choosing. Continue
independent work; do not invent a clinical unit from the answers value.

For an evidenced technical reading of the requested elements, propose the
narrowest grain and proceed under ``decision-authority.rst``. Record a real
``Engineer decision (<login>, <date>), flagged for the data analyst`` with its
actual actor, date, source and rationale. An autonomous choice is an
agent-applied technical default for engineer review, not analyst-confirmed.
Triage-only and mapping return proposals; they never manufacture confirmation
or initialise a store. An unrecorded human decision stays unconfirmed.

Bootstrap: one confirmed item with its source
--------------------------------------------

Use the intake grain, not the bare ``measurement_granularity``. Import its
``A-intake-<id>`` assumption with the original analyst confirmation, source and
``finer_outputs`` metadata. Confirm only how source keys implement it with the
engineer; do not ask the clinical unit again. A missing grain in a partial or
absent intake is unanswered, not patient consent. Batch any remaining clinical
question for the analyst/requester alongside other research gaps.

For a legacy request whose prior version or requested data elements support a
technical grain decision, use one ``A-grain`` assumption (or retain the existing
grain item's ID). Its text states ``one row per <unit>``; its text and rationale
cite the intake, prior SQL/delivery or data elements, including file/revision or
enquiry reference, never the bare default. Include decision attribution in the
rationale so SQL notes and hand-off retain it. Preserve optional ``decided``
independently of the confirmer. Formal publication still needs an answered
engineer question for this new item; evidence alone does not fill
``confirmed_by`` or other confirmation fields. An engineer-confirmed technical
reading is not analyst-confirmed research consent.

Name the grain and key in each scope output's description and in review
``grain``/outputs. Distinguish the main/cohort output from each linked detail
file. Requested finer outputs keep their own clinical units and linking keys;
they do not silently change the main grain. Do not collapse detail records with
``DISTINCT`` or choose a first event merely to fit Patient. Conversely, do not
build an unrequested detail output: offer it as an extra only.

Examples of evidence, not defaults to copy
------------------------------------------

* Prior admissions delivery and requested admission fields: one row per admission.
* Arrival codes for each ED visit: one row per ED presentation.
* Requested transfer records: one row per transfer episode.
* Confirmed patient intake: one row per patient; requested details per surgery
  or per ward stay remain at those finer grains, linked to the patient/cohort.
* A reference to a prior enquiry without its SQL: unknown until that evidence is read.

Bootstrap/analyse: report answers drift once
--------------------------------------------

At bootstrap and analyse, compare the evidenced main grain and each delivered
file's actual key/grouping with the answers value and confirmed per-file scope.
Run this check before the unchanged-SQL early return in analyse: an intake or
answers edit can matter even when SQL bytes do not change. A new drift finding
can stay in the draft/handoff while the unchanged review is rendered. If a new
confirmed finding or changed grain must enter the review, take the normal full
review/update path despite unchanged SQL: increment the revision, preserve
``changes[]`` and apply confirmation/carry gates. Do not silently publish it in
the old revision. Do not run an extract or a warehouse query for this check
without explicit authorisation.

A delivered/planned main output differing from the bare answers value is one
configuration-drift finding, not a blocker by itself. Use ``L-grain-answers``
(or reuse an existing equivalent ID) with the stale value, evidenced main grain,
per-file detail grains and source. Show it once, offer the correction in the
same analyst hand-off, then reuse the same ID across scope/review and reruns:
do not duplicate it as a new limitation, open question or blocker per stage or
file. Existing confirmation/carry rules still apply; an unconfirmed finding
stays in the draft/handoff, not in a final confirmed document. An expected finer
output is not a conflicting main grain; name it in the same comparison rather
than forcing every delivered file to match the single answers value.

Offer to update ``measurement_granularity`` in ``answers.yaml`` (or the child's
actual answers path) in the same change to the nearest supported label for the
settled main grain. Preserve exact clinical units, per-file grains and evidence
in intake/scope when the scaffold choices are coarser. Edit only when authorised
and accepted; preserve other answers and run ``validate-answers``. Never patch
Copier history blindly or run ``copier update`` for this correction. If declined,
keep the existing drift record visible; do not re-ask on each run. When corrected,
mark the finding resolved in the hand-off and retire it from the next confirmed
revision through the normal update/review process, preserving history.

Correcting stale configuration is not permission to change SQL, broaden the
cohort or alter a released row count. A real conflict with an analyst-confirmed
grain, requested meaning or released output uses the existing analyst question,
fix/amend routing and publication gates. Release compares against that evidenced
scope, not against the bare default; it holds a genuinely unresolved grain claim,
not a known configuration-drift correction alone. Release stays read-only for
answers/SQL: offer the correction to the engineer, do not apply it there.
