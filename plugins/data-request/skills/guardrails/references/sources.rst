Source evidence order and grain
===============================

Read this when dataops has no entry for a table, or its comments are empty; when a
request crosses HBCIS and ieMR; and when you choose joins for a source other than
the ieMR clinical-event pattern. It extends "Confirm sources before using a fact"
and "Join and index patterns" in ``SKILL.md``. Evidence: six enquiries across ieMR,
HBCIS and BI-Reporting (issue #371).

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
