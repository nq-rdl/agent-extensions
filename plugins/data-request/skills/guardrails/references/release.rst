Release conventions
===================

Read this before delivery, and when a request asks for dates, validation listings,
study identifiers, aggregate counts or clinician names. Evidence: two related
enquiries whose builder had to decide each point from first principles (issue #389),
and the governance ruling below (issue #413). Known approval restrictions and the
requester's confirmed scope override these conventions. Record each choice you make
under them as an assumption or a ledger decision.

Approved enquiry: build, then analyst review
-------------------------------------------

The approval of an enquiry is the permission to build, commit and push its request code
(issue #445, JoshKgh decision, 2026-09-29). The engineer does not need a separate
permission step for that in-scope work. During review, the data analyst checks the
delivered elements against the approval before release; do not claim that check is
complete during the build.

* Build every requested element as usual, including identifiers and free text:
  for example ``clinic_notes``, outwards correspondence and URN/MRN keys.
  Do not withhold a requested output or mark it ``internal`` just because the
  approval is unchecked. This does not authorise extra, unrequested elements.
* Unchecked coverage is not a blocker, open question or Ben note item.
  At most one limitation names all approval-sensitive requested elements for the
  analyst's review. Reuse it in the analyst hand-off; do not repeat the question
  at each stage. For example: "Analyst review: check the requested clinic notes,
  correspondence and MRN against the approval before release."
* A known restriction or custodian decision still comes first: cite it, do not
  build the prohibited output, and route the conflict to the approver or custodian.
  Validation listings and study-ID link tables remain undelivered, as below.
* Enquiry approval does not override runtime tool permissions, hooks or the
  selected task's scope. Triage-only stays read-only. Warehouse queries,
  service-desk writes and release actions retain their separate authorisation.
  If a runtime action is denied, report it and stop; never retry in another form
  or route through another agent to evade the denial. Only the engineer may
  change host permission settings, not the agent.

Personal information
--------------------

On 2026-09-28 the RDL governance owner ruled that clinician names are not personal
information for RDL work (issue #413). It applies to clinic, clinician and other
resource labels in any source.

* Patient identifiers are personal information: name, URN/MRN, date of birth,
  address, Medicare number and free text.
* A request may select on or deliver clinician and resource labels, for example the
  nurse and doctor names in ``BI-Reporting.dbo.OPD_Appointments.Resource``, and a
  probe may return them (``performance.rst``, "Probe design"). Staff and person keys
  stay out of probe output, and small-cell suppression still applies.
* An approval or de-identification assessment that restricts clinician names
  overrides this ruling.
* The child's pre-push PII scan (Presidio ``PERSON``, data-analysis-scaffold v0.5.0)
  can flag such a label in request SQL. Add that exact label to the child's
  ``.pii-allowlist`` and cite the ruling in the commit or PR. Never allowlist a
  patient's name.

Raw dates or a derived outcome
------------------------------

* Deliver raw dated events by default, with their source. Turning a date into an
  outcome is the researcher's modelling choice ("Leave modelling choices to the
  researcher" in ``SKILL.md``).
* Deliver a derived outcome instead of the raw date only when the approval or the
  confirmed scope names the derived outcome, or when a known approval restriction
  excludes the raw date. For example, an approval can permit "died within 30 days" but not
  the date of death.
* For a derived outcome, record its rule (anchor, window and boundaries) with
  ``record_assumption()``. Keep the raw date for validation outside the delivery
  run.
* Deliver both only when both are requested and no known restriction excludes
  them. Unchecked approval alone does not withhold either requested output; the
  analyst checks coverage during review.

Validation listings stay out of the delivery
--------------------------------------------

Validation listings (row-level checks, samples and cross-source comparisons) stay
inside RDL. By default, keep them out of the delivery run: put them in a separate
run or script whose output is never delivered, and say so in the task output.

Use the ``-- @extract: <name> internal`` marker only after you read the child's
pinned ``scripts/run_extract.py`` and confirm that it supports the flag:

* The flag exists only in data-analysis-scaffold PR #247, open and unreleased on
  2026-09-28. There, the batch's parquet is written to ``data/02_extracts/`` and
  saved as usual, but it gets no sheet in the delivered workbook. Any other
  trailing token refuses the run before SQL runs. A run whose every output is
  internal is refused.
* Every released runner (scaffold v0.5.0 and earlier) accepts
  ``-- @extract: <name>`` only. Its marker pattern does not match a line with a
  trailing ``internal``, so the batch falls back to an ``extract_NN`` name and
  **lands in the delivered workbook**.
* At query-builder tag v0.6.0, ``-- @extract: <name>`` markers had no internal
  flag. Check the request's pin for current behaviour. Never hand-edit a generated
  marker (``/data-request:amend``).

Study IDs
---------

This pattern is a default that RDL has not yet confirmed as a house convention. An
approval, the data custodian or the de-identification assessment overrides it.

1. Fix the final delivered cohort first.
2. Give each person one study ID. Draw the order at random (for example
   ``ORDER BY NEWID()``), then number with ``ROW_NUMBER()``. Never derive the ID
   from a URN, MRN, ``PERSON_ID``, date of birth or a hash of them, and never
   number in source or date order.
3. The link table (study ID to source person key) is a re-identification key. It
   never goes in any extract of the delivery run. Store it only in a separate,
   undelivered run or RDL-only store. Use an ``internal`` marker for it only when
   the pinned runner supports the flag, as above.
4. Reuse that link table for every amendment of the same enquiry, so the IDs stay
   stable. A random draw is not reproducible, so never regenerate it.
5. Record the method with ``record_assumption()``.

Small-cell suppression
----------------------

These skills set no organisation-wide threshold. The governing threshold is the
"Cell suppression threshold" field of the request's de-identification assessment
(``nq-rdl/documentation``,
``zensical/governance/docs/governance/deidentification-assessment.md``), or a
threshold stated in the approval. If neither states one, ask the approver or
requester, and record the answer as a decision before release. Do not choose a
number yourself.

Apply the assessment's suppression to every delivered aggregate, including
cross-tabulations and summary tables, with the complementary controls below.
A row-level extract delivered under an approval is governed by that approval,
not by cell suppression. Probe output uses the stricter controls below.

Probe disclosure control
------------------------

Authority: Queensland Health *De-identification and anonymisation of data
guideline* v2.0 (March 2026). Verify against that canonical guideline and the
request's assessment before sharing; an inaccessible private ``nq-rdl/pynon``
copy is not required reading. The guideline describes k-anonymity with k = 5,
small-cell wording of both "less than 5" and "no cell may be ≤ 5", random
rounding (base 3 as an example), open-ended banding and primary/secondary
suppression; it warns that suppression does not protect against differencing.
The following are RDL probe conventions decided by JoshKgh on 2026-09-30,
not claims that the guideline mandates these particular tiers.

Perimeter and fact kinds
~~~~~~~~~~~~~~~~~~~~~~~~

* **RDL-only:** the runbook and exact results file may retain exact evidence in
  an access-controlled RDL store. A committed file is not automatically RDL-only:
  if the repo is handed over, exclude these files and review its history first.
  Do not paste their exact cohort counts into an AI-agent conversation.
* **Handover:** SQL headers, scope and review files use these controls.
* **Open channels:** issues, PR bodies and chat (including AI-agent output) use
  these controls too. Restrict the audience as well; rounding is not approval.

Counts of people, episodes, admissions and events (including grid and temp-table
fill counts) use the floor and rounding below in handover/open output. Structural
counts of distinct codes, labels, fields, tables and columns remain exact, as do
run metadata (timings, run dates and versions). Exception: a grid folding rare
labels into "other" must omit the distinct-label total, which reveals how many
labels were folded. A patient duration or event date is not run metadata.
Ask the assessment owner whether facts about the delivered cohort, which an
analyst can recompute from the extract, need rounding in the handover tier;
pending that decision, keep these controls. An approved extract is not changed.

Floor and rounding
~~~~~~~~~~~~~~~~~~

Use an effective floor F = max(7, assessment/approval threshold), interpreting
any inclusive suppression boundary before taking that maximum. Counts from 1
through F-1 show only ``<F`` (``<7`` at the default); never the exact count.
An assessment may raise this floor, never lower it. If its threshold is unknown,
ask and record the answer before sharing; do not assume that 7 is sufficient.
Zero may show as ``about 0`` only after the differencing check below.

For unsuppressed counts, select the step from the **exact integer**:

* 7–14: ``between 7 and 14``; if F cuts into this band, suppress the whole band
  rather than implying values below F.
* 15–99: nearest 5.
* 100–999: nearest 10.
* 1,000 and above: two significant figures, step = 10 ** (digits(n) - 2).

Use decimal half-up, never binary floats or ties-to-even: for nonnegative n and
step s, rounded = s * floor((2*n + s) / (2*s)), using integer arithmetic.
Every displayed rounded count carries ``about``, even when rounding leaves it
unchanged. Suppression tokens and the explicit low-end range are exceptions,
not exact-count disclosures. The same qualifier applies to shown rounded shares
and derived values, not to structural counts, metadata or band boundaries.
Choose the display unit **after rounding**: below 1,000 use an integer; from
1,000 use k, from 1,000,000 use M (then powers of 1,000 as needed). Preserve two
significant figures for unit displays, including a trailing decimal zero.

Boundary test table (F = 7; exact inputs are synthetic, not probe evidence)::

  Exact | Shown
  0 | about 0
  1 | <7
  6 | <7
  7 | between 7 and 14
  14 | between 7 and 14
  15 | about 15
  17 | about 15
  18 | about 20
  99 | about 100
  100 | about 100
  104 | about 100
  105 | about 110
  994 | about 990
  995 | about 1.0k
  996 | about 1.0k
  999 | about 1.0k
  1000 | about 1.0k
  1049 | about 1.0k
  1050 | about 1.1k
  9999 | about 10k
  10000 | about 10k
  99949 | about 100k
  99999 | about 100k
  100000 | about 100k
  994999 | about 990k
  995000 | about 1.0M
  999499 | about 1.0M
  999500 | about 1.0M
  999999 | about 1.0M
  1000000 | about 1.0M

Unlike the guideline's random-rounding example, this rule is deterministic for
reproducible header builds and provenance hashes. It is not differential privacy:
rebuilding for a changed cohort, overlapping grids or old exact text can expose
a change despite rounding. Review the combined releases, not just one output.

Coverage, equality and derived evidence
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Never write unquantified "almost all". Use only these coverage forms:

* "all" only when the runner checked equality on exact counts;
* "all but fewer than F" for a positive remainder below the effective floor;
* "about P% of about N (about R without)", with R using the count formatter
  (substitute its low-end range where required);
* open end bands such as "more than 97%" or "under 0.05%", built from the exact
  remainder and denominator. Widen or omit the band if, combined with all shown
  evidence, it narrows a positive remainder below F; do not use a near-100%
  rounded percentage to evade suppression.

Preserve a checked equality as a claim in words: "for every cohort case",
"equal to the cohort size" or "the rule removed no case", followed by a safely
shown size. Rounded operands that happen to match are not equality evidence.
Compute differences, ratios and shares from **exact operands**, then round the
result, never subtract displayed operands. If the displayed difference is wrong
by more than one rounding step for the exact difference, print the safely shown
derived value as well; suppress it if small or disclosive. For shares/ratios use
decimal half-up to two significant figures, subject to the coverage bands and
combined-disclosure check; a positive result must not be shown as exact zero.

Complementary controls
~~~~~~~~~~~~~~~~~~~~~~

Check every total and part in **every file of the handover set**, including
prose, SQL headers and any runbook that would accompany it, against grids, fill
counts, other probes and prior releases. Mask another cell/part, coarsen or omit
values whenever subtraction or combined rounding intervals could recover or
narrow a masked count. Rounding alone is not proof of safety. Old exact text in
git history remains a risk; editing the current header does not erase it.

Band patient durations and date differences with open-ended ends (for example
"91 to 365 days" and "over 365 days"); show patient/event dates by month or
coarser. Fold every code/label occurring on fewer cases than F into one "other"
row; apply the floor to that pooled count too, and omit labels that remain
identifying through rarity even above F. Never show free text. A grid crosses at
most two quasi-identifiers (for example age band, sex, facility or specialty)
besides the measure. Mask MIN and MAX for small cells; take them only from dates,
category codes and numeric ranges, then apply the date/range controls above.

Provenance and lint
~~~~~~~~~~~~~~~~~~~

Engineer rationale cites the stable probe result id and states the conclusion
in words. Analyst-facing limitations add a safely shown value from that result.
Cite its SQL revision and scoped population with the id; a rerun must not silently
retarget old evidence or force a scope revision merely to refresh a number.
Use one shared formatter in a request's builder for every displayed value, not
hand rounding. Check new results for changed conclusions before updating text.

Lint contract for a probe sentence: fail on a bare integer of 7 or more or any
comma-grouped integer. Accept formatted ``about`` values, approved range/band
boundaries, suppression tokens and provenance/run-metadata tokens; a local
``[structural-count]`` marker exempts only an explicitly identified structural
count, never a population count or folded-label total. Review exemptions and
coverage/equality claims as well as the numeric check. This is an authored review
rule, not an installed lint tool; automated sentence classification and the
shared builder formatter belong in the request/scaffold follow-up.

Context only: issue #464 rule 8's retrofit of in-progress request repositories
and data-analysis-scaffold #280's second-check runner are outside this catalog
change. Do not retrofit released/handed-over repositories or claim runner
coverage here. Delivery-format limits are a separate workstream (#463).
