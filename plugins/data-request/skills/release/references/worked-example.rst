Worked example: a falls extract release
=======================================

A fictional enquiry, THHSAQUIRE-9936, modelled on a real release (issue #407). It shows
the order of work in ``/data-request:release``: check that the review applies, compare the
sources, and only then select and word the claims.

The sources
-----------

- The release tag ``v1.0.0``. Its pipeline ``src/pipelines/falls_service_extract.py``
  admits an emergency presentation when "FALL" appears in the diagnosis **or** chief
  complaint **or** visit reason. It declares two outputs, ``Encounter_Level`` and
  ``Clinical_events``, and describes the cohort as patients aged 18 or over at arrival.
- The legacy ``.copier-answers.yml``, with ``measurement_granularity: Patient``:
  a bare default, not a confirmed grain. No recorded patient-grain answer accompanies it.
- A ``.sqlreview`` review made on the branch ``enq/9936-v2``. It describes **draft SQL**
  written before the pipeline, and it asks whether that SQL still represents the pipeline.
- An earlier draft release body. It says that "Fall" must appear in "Presenting complaint"
  and in "Presenting problem".

Does the review apply?
----------------------

Run ``release.sh evidence v1.0.0`` first. Here it reports ``missing-at-ref`` (the draft SQL
file is not in the release) and ``reviewed_commit_in_ref: false``. The review describes a
draft, not the release. No review item is a confirmed fact for ``v1.0.0``. Each item below
is a lead: check it against the tagged pipeline, its generated SQL and the output manifest
before it becomes a claim. Offer the engineer ``/data-request:analyse`` on the release SQL.

Compare before wording
----------------------

Compare three leads. A real meaning-changing conflict is a blocking discrepancy,
recorded with both sources and a proposed correction; bare configuration drift is not:

- **Q1, inclusion rule.** The draft body says complaint **and** problem. The pipeline says
  diagnosis **or** chief complaint **or** visit reason, and the review describes an OR rule
  over different fields. Proposed correction: state the pipeline's OR rule, after the analyst
  confirms that the pipeline is what was agreed.
- **Q2, unit of observation.** Answers says ``measurement_granularity: Patient`` without
  confirmation. The stale review and the pipeline describe encounter-level records. Check
  the tagged SQL, output manifest and intake/prior-delivery or requested-element evidence
  to settle the main grain and the finer ``Clinical_events`` output. Record the evidenced
  grain, not the bare Patient value. Reuse one ``L-grain-answers`` finding and offer the
  answers correction to the engineer; do not hold the claim for stale configuration alone.
  A genuine conflict with confirmed grain or missing grain evidence still needs resolution.
- **Q3, age basis.** The review reads age from ``Present Age in Years``, which is age today.
  The pipeline says "aged 18 or over at arrival". Check the resolver and the produced SQL.
  The answer changes both who is in the cohort and what the age field means.

Only after these are resolved does a prose pass make sense.

Each review item
----------------

Researcher-relevant, subject to the release check:

- **A1** How falls are identified. Cohort membership. It becomes the inclusion claim, worded
  from the resolved Q1, not from the review.
- **A3** Age basis. Cohort membership and field meaning. It waits for Q3.
- **A4** Present-day demographics. Field meaning: sex and address fields reflect the patient
  record now, not at the presentation. Keep it as a limitation if the pipeline still reads
  the current patient record.
- **L1** Text-match precision. Cohort membership: "FALL" also matches text that is not a fall,
  and a fall recorded in other words is missed. Keep it, in plain language.
- **L2** A requested element absent from the draft SQL. Check the delivered files. If it is
  still absent, it is a question for the analyst and a stated limitation, never a footnote.
- **L5** and **L6** Completeness limits from the review. Keep each one that the release
  pipeline still has, and say what the researcher cannot see.

Included only where the effect on the delivered data is material:

- **A2** A locking hint on the source reads. Keep it internal: the tagged validation counts
  reconcile, so it has no visible effect. Raise it if validation shows unstable counts.
- **L3** Unordered rows. Keep it internal: the order carries no meaning for the researcher.
- **L4** Keep it internal unless its effect reaches the delivered files. If it does, state the
  effect on the data, not the mechanism.

Show the analyst this internal list with the reasons, so nothing is left out silently.

The draft
---------

The Extraction Summary names the population (from Q1 and Q3), the site and period, the grain
(from Q2), and the two delivered files, ``Encounter_Level`` and ``Clinical_events``. The
Extraction Assumptions / Important limitations section carries A1, A4, L1, L2, L5 and L6 as
the release confirms them. Each claim cites the pipeline at ``v1.0.0`` and, where it helped,
the review item by id. The analyst accepts, rewords or rejects each claim. The record keeps
the wording and the sources, and the review itself is unchanged.
