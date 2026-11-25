CREATE TABLE "#admissions_ENQ90210" (
    [visit_occurrence_id] BIGINT NULL,
    [person_id] BIGINT NULL,
    [visit_concept_id] INTEGER NULL,
    [visit_start_date] DATE NULL,
    [visit_end_date] DATE NULL,
    [visit_type_concept_id] INTEGER NULL,
    [provider_id] BIGINT NULL,
    [care_site_id] BIGINT NULL,
    [visit_source_value] VARCHAR(50) NULL
);
GO
WITH EncounterFilter AS (SELECT "visit_occurrence_id","person_id","visit_concept_id","visit_start_date","visit_end_date","visit_type_concept_id","provider_id","care_site_id","visit_source_value" FROM "omop"."visit_occurrence" WHERE "visit_concept_id"=9201)
INSERT INTO "#admissions_ENQ90210" ("visit_occurrence_id", "person_id", "visit_concept_id", "visit_start_date", "visit_end_date", "visit_type_concept_id", "provider_id", "care_site_id", "visit_source_value")
SELECT "visit_occurrence_id", "person_id", "visit_concept_id", "visit_start_date", "visit_end_date", "visit_type_concept_id", "provider_id", "care_site_id", "visit_source_value"
FROM "EncounterFilter";
GO
-- @extract: admissions
SELECT * FROM "#admissions_ENQ90210"