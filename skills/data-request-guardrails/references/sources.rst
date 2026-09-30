Source evidence order and grain
===============================

Read this when dataops has no entry for a table, or its comments are empty; when a
request crosses HBCIS and ieMR; and when you choose joins for a source other than
the ieMR clinical-event pattern. It extends "Confirm sources before using a fact"
and "Join and index patterns" in ``SKILL.md``. Evidence: six enquiries across ieMR,
HBCIS and BI-Reporting (issue #371).

House default: TUH facility
--------------------------

Apply the ``SKILL.md`` House defaults rule when facility scope is unstated or
explicitly TUH. The maintained wording, ``tuh-facility`` marker and original
confirmation live in setup's ``references/recurring-decisions.rst`` and shared
list. Preserve the code as the string ``'00200'`` with its leading zeros in SQL,
YAML, JSON and spec arguments. Never turn it into numeric ``200``.

* **HBCIS:** filter the cohort's ``FacilityCode`` to ``'00200'``. Check the
  pinned ``resolvers/hbcis/tables.py`` and schema extracts for each participating
  mart. ``SiteCode`` is a different key: a site can contain several facilities.
  Admission-from and discharge-to facility fields are not the cohort facility.
* **ePADT:** filter the cohort's ``FacilityCode`` to ``'00200'``. Verify the
  actual ePADT source table/view and type at the request's pin; a BI-Reporting
  field with the same name is not proof that it uses ePADT's representation.
* **ieMR institution:** resolve TUH through the current **facility crosswalk**
  to the institution key used by the chosen ieMR source/resolver. HBCIS/ePADT
  facility codes, ``SiteCode`` and ieMR institution/location keys are not interchangeable.
  Verify and cite the crosswalk table/columns, mapped institution value, revision
  and uniqueness at the required grain before composing its join/predicate.
  Do not invent an institution id, crosswalk name or join from ``00200``; the
  episode-to-encounter mapping below is not itself a facility crosswalk. If the
  mapping is unavailable, flag only that implementation as unverified, request
  the missing evidence and continue independent work; do not re-ask the TUH choice.

Compose the pinned facility unit where supported, otherwise follow the lift rules.
``FacilitySpec('00200')`` and the HBCIS scope handler exist on query-builder main
at ``2767aec2bf6a837cf054811e981eecf067d5cb4d`` (``clinical/specifications.py``,
``resolvers/hbcis/resolver.py``, ``tests/clinical/test_facility_spec.py``).
This unpinned upstream discovery is not evidence of availability in a request's
installed release or of an ieMR/ePADT handler. Inspect that pin before use;
``SiteCode`` alone is not the TUH facility filter.

An explicit other facility, whole HHS or network-wide cohort gets one
``Analyst question:`` about the facility set and code mapping instead of the TUH
assumption. Batch it with remaining research questions. Reuse an already recorded
analyst answer; do not ask again or silently intersect it with TUH. Until answered,
leave only the dependent facility scope unresolved and continue independent work.
This rule does not authorise a broader cohort, database execution or new outputs.

Where dataops lives
-------------------

All paths are in ``nq-rdl/dataops``:

* Catalogue YAML: ``src/da/mappings/catalog/ieMR/*.yaml``. Many ``source_comment``
  values are blank, and the catalogue has no index definitions.
* DDL: ``marts/bronze/iemr/ddl/*.sql``. It describes ``ieMR_Raw.Raw``, the SQL05
  copy that dataops ingests. It does not describe ``ieMR.dbo`` or the SQL02
  instance. Check which schema and instance the request reads before you cite it.
* Caveats: ``docs/sources/data-caveats.md``.

dataops covers ieMR only. HBCIS (``Inpatient`` and ``InpatientExtensions``
``mart_v``) and BI-Reporting have no dataops entry. dataops states no timezone for
the ieMR ``*_DT_TM`` columns.

Fallback evidence order
-----------------------

Use the first source that answers the question. Cite each source you read, with its
path and revision.

1. **dataops** DDL and comments, as above.
2. **query-builder** ``schema_extracts/<instance>/<database>/<schema>/`` at the
   pinned revision. These are ``INFORMATION_SCHEMA`` dumps: names, types and
   nullability. They give no timezone, unit or index. HBCIS evidence starts here.
3. **query-builder** ``ColumnMeta`` on the pinned ``TypedTable``
   (``resolvers/iemr/tables.py``, ``resolvers/hbcis/tables.py``,
   ``resolvers/bireporting/tables.py``). It can state meaning, timezone and unit.
   For ieMR ``CLINICAL_EVENT`` datetimes, only ``ColumnMeta`` states UTC; for
   BI-Reporting ``ED_Extract_THHS`` it states ``Australia/Brisbane``.
4. **An operator probe** (see ``performance.rst``), tagged ``OBSERVED`` or
   ``INFERRED`` with its scope. An hour-of-day histogram of a datetime column is a
   probe for its timezone. A finding from a sibling repository applies only inside
   its tagged scope.

An uncurated dump (marked "not yet curated", or ``review_status: UNREVIEWED``) is
schema evidence only. Cite its path, revision and status. Grade each decision that
depends on it as unverified, and never read meaning, timezone or units from it.

Grain per source
----------------

Every source needs its own grain check before a join or a count. Name the key that
makes one row unique, and count rows per intended output unit.

* ieMR ``CLINICAL_EVENT → ENCOUNTER → person``: several events per encounter and
  several encounters per person. See ``SKILL.md``.
* ieMR scheduling (``SCH_APPT`` and related tables): one row per role per
  appointment. Filter to the role that the output needs before you count
  appointments.
* A flat table, such as BI-Reporting ``OPD_Appointments``: no encounter join. The
  grain is what the table's key says. Confirm it from the key and a probe, not from
  the table name.

HBCIS and ieMR crosswalk
------------------------

Join HBCIS to ieMR through the ``mart_iemr_hbcis_mapping_*`` views in
``InpatientExtensions.mart_v``, for example
``mart_iemr_hbcis_mapping_episode_encounter_view`` (``TypedTable``
``MartIemrHbcisMappingEpisodeEncounterView`` in ``resolvers/hbcis/tables.py``).
Guard uniqueness before the join: check that each key you join from maps to exactly
one row, and stop and report when it does not. A silent fan-out multiplies the
output grain.

CLINICAL_EVENT currency
-----------------------

On the ieMR source of truth, ``VALID_UNTIL_DT_TM`` is not closed off consistently.
Superseded rows can keep the ``2100-12-31`` sentinel, so ``VALID_UNTIL_DT_TM >
now`` can return several rows per ``EVENT_ID``. The BI copy closes them
consistently. See dataops ``docs/sources/data-caveats.md``. Use the pinned
resolver's currency rule, check for duplicate ``EVENT_ID`` rows, and record a
limitation wherever the logic depends on currency.
