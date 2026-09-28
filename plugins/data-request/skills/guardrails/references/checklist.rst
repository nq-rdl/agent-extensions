Hand-SQL review checklist
=========================

Read this when you write, lift or review hand SQL, and when you review generated
SQL that someone edited by hand. Each pattern repeated in the hand SQL behind
three reviewed enquiries (issue #388). Report each finding with its SQL
location, the pattern name and the fix. A pattern that does not apply is not a
finding.

1. End-of-day literal
---------------------

Symptom
   A bound such as ``DATETIME '2025-12-31 23:59:59.999'`` includes rows at midnight
   of the next day. ``DATETIME`` stores time in steps of about 3 ms, so ``.999``
   rounds up to ``00:00:00.000`` of the next day on conversion.
Fix
   Use a half-open window: ``>= start`` and ``< the day after the end``. Never write
   an end-of-day literal.

2. Unique index on a one-to-many link
-------------------------------------

Symptom
   A ``CREATE UNIQUE INDEX`` or primary key on a ``#temp`` table fails with a
   duplicate-key error, or somebody removes rows to make it pass. The link is
   one-to-many: one URN to several ``PERSON_ID`` values, or one episode to several
   encounters.
Fix
   Count rows per key before you index. Use a non-unique index, or settle the link
   rule as an explicit, recorded choice. Never drop duplicates to satisfy an index.

3. Substring drug match
-----------------------

Symptom
   ``LIKE '%adrenaline%'`` also matches Noradrenaline. A name pattern also misses
   Australian spellings, such as ciclosporin or frusemide.
Fix
   Use a coded concept or an explicit, reviewed list of names with their spelling
   variants. List the distinct matched values and review them before you use the
   match.

4. Mixed time zones
-------------------

Symptom
   A comparison across sources shifts by the offset. OPD times in AEST against ieMR
   times in UTC gave a ten-hour shift inside a ten-day window.
Fix
   Verify each field's timezone ("Timezone and source system" in ``SKILL.md``),
   then transform the anchor into the filtered column's timezone.

5. Dates formatted with ``FORMAT``
----------------------------------

Symptom
   ``FORMAT()`` returns text that depends on the culture, runs slowly per row, and
   delivers dates as strings.
Fix
   Deliver typed ``date`` or ``datetime2`` values. When text is required, use
   ``CONVERT`` with an explicit style, or format at export.

6. Different join rules for cohort and output
---------------------------------------------

Symptom
   Cohort members have empty output, or counts do not reconcile. For example, the
   cohort takes orders on any encounter, but the output takes orders on the ED
   encounter only.
Fix
   Define the join rule once, in one ``#temp`` table or spec, and use it for both
   the cohort and the output. Record the rule as an assumption.

7. Full event-set explode
-------------------------

Symptom
   Expanding a whole event-set hierarchy returns one row per level, and an ordered
   listing or a "first" row then comes out in the wrong order.
Fix
   Restrict the explode to the event sets you need, reduce to one row per event
   before you order, and end with an explicit ``ORDER BY`` that has a unique
   tiebreak (for example, event time then ``EVENT_ID``).

Verify engine behaviour against the SQL Server documentation for the deployed
version before you present a finding as verified.
