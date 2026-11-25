/*
inputs:
  - supplied cohort example_cohort
    file: example_cohort.csv
    table: #ExampleCohort
    key: study_id
    columns: study_id VARCHAR(20) personal, urn VARCHAR(10) health
assumptions:
  - Each person has one URN
    rationale: example rule
limitations:
  - Codes are matched exactly
    consequence: example effect
*/

-- @supplied: {"format": 1, "name": "example_cohort", "file": "example_cohort.csv", "table": "#ExampleCohort", "key": ["study_id"], "max_rows": 10000, "columns": [{"name": "study_id", "sql_type": "VARCHAR(20)", "dtype": "string", "sensitivity": "personal", "nullable": false}, {"name": "urn", "sql_type": "VARCHAR(10)", "dtype": "string", "sensitivity": "health", "nullable": false}]}
CREATE TABLE "#ExampleCohort" (
  "study_id" VARCHAR(20) COLLATE DATABASE_DEFAULT NOT NULL,
  "urn" VARCHAR(10) COLLATE DATABASE_DEFAULT NOT NULL
);
GO
CREATE UNIQUE INDEX "IX_ExampleCohort_study_id" ON "#ExampleCohort" ("study_id");
GO
-- @supplied-load: example_cohort
DECLARE @query_builder_guard INT = (SELECT CAST(CASE WHEN COUNT(*)=0 THEN 'Supplied cohort example_cohort has no row. Run this script through the query-builder runner or QueryExecutor, which loads example_cohort.csv before this batch. In SSMS later batches still run.' END AS INT) FROM "#ExampleCohort");
GO
-- @supplied-unmatched: example_cohort
SELECT "study_id" FROM "#ExampleCohort";
GO
CREATE TABLE "#dx_QB" (
  "code" VARCHAR(50) COLLATE DATABASE_DEFAULT,
  "category" VARCHAR(128)
);
GO
INSERT INTO "#dx_QB" ("code","category") VALUES ('ZZ01','example_a'),('ZZ02','example_a'),('ZZ03','example_b');
GO
CREATE UNIQUE INDEX "IX_dx_QB_code_category" ON "#dx_QB" ("code", "category");
GO
CREATE TABLE "#people_QB" (
  "urn" VARCHAR(10),
  "dx" VARCHAR(10)
);
GO
INSERT INTO "#people_QB" SELECT "urn","dx" FROM "people_source";
GO
CREATE INDEX "IX_people_QB_urn" ON "#people_QB" ("urn");
GO
DECLARE @query_builder_guard INT = (SELECT CAST(CASE WHEN COUNT(*)>0 THEN CONCAT('found ',COUNT(*),' rows with no urn') END AS INT) FROM (SELECT "urn" FROM "#people_QB" WHERE "urn" IS NULL) "violations");
GO
-- @extract: people
SELECT "urn" FROM "#people_QB";
GO
-- @extract: diagnoses internal
SELECT "dx" FROM "#people_QB";
GO
-- @extract: detail file
SELECT "urn","dx" FROM "#people_QB";
GO
DROP TABLE IF EXISTS "#ExampleCohort";
GO
DROP TABLE IF EXISTS "#dx_QB";
GO
DROP TABLE IF EXISTS "#people_QB"