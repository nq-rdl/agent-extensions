/* A hand-written script. This leading comment is not a notes header. */
-- @extract: summary file
SELECT 'GO' AS word, 'a
GO
b' AS multi_line;
go -- a lowercase separator with a note
CREATE TABLE [#staging] ([code] VARCHAR(10), [category] VARCHAR(128));
GO /* a separator with a block comment */
INSERT INTO [#staging] ([code], [category]) VALUES ('ZZ01', 'example'), ('it''s', 'example');
GO
DECLARE @query_builder_guard INT = (SELECT CAST(CASE WHEN COUNT(*)=0 THEN 'no rows' END AS INT) FROM [#staging]);
GO
SELECT * INTO #copy FROM [#staging];
GO
SELECT [code] FROM #copy
GO
DROP TABLE IF EXISTS [#staging];
GO
DROP TABLE #copy
