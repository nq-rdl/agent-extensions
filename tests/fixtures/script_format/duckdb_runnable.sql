CREATE TABLE "#people_QB" (
  "urn" VARCHAR(10),
  "dx" VARCHAR(10)
);
GO
INSERT INTO "#people_QB" SELECT "urn","dx" FROM "people_source";
GO
CREATE INDEX "IX_people_QB_urn" ON "#people_QB" ("urn");
GO
-- @extract: people
SELECT "urn" FROM "#people_QB";
GO
-- @extract: detail file
SELECT "urn","dx" FROM "#people_QB";
GO
DROP TABLE IF EXISTS "#people_QB"