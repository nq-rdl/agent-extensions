-- @extract: admissions
WITH EncounterFilter AS (
  SELECT
    [visit_occurrence_id] AS [visit_occurrence_id],
    [person_id] AS [person_id],
    [visit_concept_id] AS [visit_concept_id],
    [visit_start_date] AS [visit_start_date],
    [visit_end_date] AS [visit_end_date],
    [visit_type_concept_id] AS [visit_type_concept_id],
    [provider_id] AS [provider_id],
    [care_site_id] AS [care_site_id],
    [visit_source_value] AS [visit_source_value]
  FROM [omop].[visit_occurrence]
  WHERE
    [visit_concept_id] = 9201
)
SELECT
  [encounterfilter].[visit_occurrence_id],
  [encounterfilter].[person_id],
  [encounterfilter].[visit_concept_id],
  [encounterfilter].[visit_start_date],
  [encounterfilter].[visit_end_date],
  [encounterfilter].[visit_type_concept_id],
  [encounterfilter].[provider_id],
  [encounterfilter].[care_site_id],
  [encounterfilter].[visit_source_value]
FROM [EncounterFilter] AS [encounterfilter]